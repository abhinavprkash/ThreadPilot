#!/usr/bin/env python3
"""
ThreadBrief Full Demo Script
=============================
Runs the complete end-to-end pipeline in one command:

  Step 1 — AI generates realistic Slack conversation data (AWS Bedrock)
  Step 2 — Messages are posted to real Slack channels
  Step 3 — Digest pipeline fetches messages, runs AI analysis, posts summaries

Usage:
    poetry run python scripts/full_demo.py

Requirements:
    - .env with SLACK_BOT_TOKEN, AWS credentials, and channel IDs configured
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────
# Setup paths
# ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

load_dotenv(ROOT / ".env")

# Force bot messages to not be filtered (we post data as the bot)
os.environ["FILTER_BOTS"] = "false"

# ─────────────────────────────────────────────────────────────
# Color helpers (ANSI, safe for most terminals)
# ─────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"

def banner():
    print()
    print(BOLD + CYAN + "╔══════════════════════════════════════════════════════════╗" + RESET)
    print(BOLD + CYAN + "║              🧵  ThreadBrief  —  Full Demo               ║" + RESET)
    print(BOLD + CYAN + "║     AI-powered Slack digest, end-to-end in one script    ║" + RESET)
    print(BOLD + CYAN + "╚══════════════════════════════════════════════════════════╝" + RESET)
    print()

def step_header(n: int, title: str):
    print()
    print(BOLD + YELLOW + f"  ── Step {n}: {title} " + "─" * max(0, 52 - len(title)) + RESET)

def ok(msg: str):
    print(GREEN + f"  ✓  {msg}" + RESET)

def info(msg: str):
    print(DIM + f"     {msg}" + RESET)

def err(msg: str):
    print(RED + f"  ✗  {msg}" + RESET)

def separator():
    print(DIM + "  " + "─" * 60 + RESET)


# ─────────────────────────────────────────────────────────────
# Step 1 — Generate synthetic data with Bedrock
# ─────────────────────────────────────────────────────────────
def generate_data(days: int = 1, channels: int = 3, output: str = "fixtures/slack_mock.json"):
    """Use Bedrock/Claude to generate a realistic day of Slack conversations."""
    step_header(1, "AI generates synthetic Slack conversations")
    info(f"Generating {days} day(s) of conversations across {channels} channels …")
    info(f"Output → {output}")
    print()

    output_path = ROOT / output

    # Import the generator
    from generate_synthetic_data import main as gen_main, parse_args as gen_parse_args

    original_cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        gen_args = gen_parse_args([
            "--days",     str(days),
            "--channels", str(channels),
            "--output",   str(output),
        ])
        gen_main(gen_args)
    finally:
        os.chdir(original_cwd)

    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
        total_msgs = sum(
            len(ch.get("messages", []))
            for ch in data.get("channels", {}).values()
        )
        ok(f"Generated {total_msgs} messages across {len(data.get('channels', {}))} channels")
        ok(f"Saved to {output_path.relative_to(ROOT)}")
    else:
        err("Output file not found — generation may have failed")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# Step 2 — Seed real Slack channels
# ─────────────────────────────────────────────────────────────
def clear_channel(client, channel_id: str, bot_user_id: str):
    """Delete all messages posted by the bot in a channel."""
    from slack_sdk.errors import SlackApiError
    deleted = 0
    try:
        cursor = None
        while True:
            kwargs = {"channel": channel_id, "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            resp = client.conversations_history(**kwargs)
            messages = resp.get("messages", [])
            for msg in messages:
                # Only delete messages posted by our bot
                if msg.get("bot_id") or msg.get("user") == bot_user_id:
                    try:
                        client.chat_delete(channel=channel_id, ts=msg["ts"])
                        deleted += 1
                        time.sleep(0.5)  # rate limit
                    except SlackApiError:
                        pass
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError:
        pass
    return deleted


def seed_channels(fixture_path: str = "fixtures/slack_mock.json"):
    """Push generated messages to real Slack channels."""
    step_header(2, "Posting messages to Slack channels")

    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        err("SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)

    fixture_file = ROOT / fixture_path
    if not fixture_file.exists():
        err(f"Fixture file not found: {fixture_file}")
        sys.exit(1)

    with open(fixture_file) as f:
        data = json.load(f)

    users    = data.get("users", {})
    channels = data.get("channels", {})

    channel_map = {
        "C_MECHANICAL": os.getenv("CHANNEL_MECHANICAL"),
        "C_ELECTRICAL": os.getenv("CHANNEL_ELECTRICAL"),
        "C_SOFTWARE":   os.getenv("CHANNEL_SOFTWARE"),
    }

    client = WebClient(token=token)
    try:
        auth = client.auth_test()
        bot_user_id = auth.get("user_id", "")
        ok(f"Connected to Slack as  @{auth['user']}  in workspace  {auth['team']}")
    except SlackApiError as e:
        err(f"Slack connection failed: {e.response['error']}")
        sys.exit(1)

    # Clear old bot messages first so channels stay clean across demo runs
    info("Clearing previous bot messages from channels …")
    for fixture_id, real_id in channel_map.items():
        if not real_id:
            continue
        n = clear_channel(client, real_id, bot_user_id)
        if n:
            info(f"  Removed {n} old message(s) from {real_id}")

    total_posted = 0
    for fixture_id, real_id in channel_map.items():
        if not real_id:
            info(f"Skipping {fixture_id} (no channel ID in .env)")
            continue

        ch_data  = channels.get(fixture_id, {})
        messages = ch_data.get("messages", [])
        ch_name  = ch_data.get("name", fixture_id)

        if not messages:
            info(f"No messages for {fixture_id} in fixture — skipping")
            continue

        info(f"Posting {len(messages)} message(s) to #{ch_name}  ({real_id}) …")

        posted = 0
        for msg in messages:
            user_id  = msg.get("user", "")
            user_name = users.get(user_id, {}).get("name", "Team Member")
            text = f"*[{user_name}]*: {msg['text']}"

            try:
                client.chat_postMessage(
                    channel=real_id,
                    text=text,
                    unfurl_links=False,
                    unfurl_media=False,
                )
                posted += 1
                total_posted += 1
                preview = msg['text'][:80].strip().replace('\n', ' ')
                print(f"  {DIM}  [{posted}/{len(messages)}] {user_name}: {preview}{RESET}")
                time.sleep(1.1)   # Slack rate limit: ~1 msg/sec
            except SlackApiError as e:
                info(f"  Failed: {e.response['error']}")

        ok(f"Posted {posted}/{len(messages)} messages to #{ch_name}")

    separator()
    ok(f"Total posted: {total_posted} messages")


# ─────────────────────────────────────────────────────────────
# Step 3 — Reset state so digest picks up fresh messages
# ─────────────────────────────────────────────────────────────
def reset_state():
    state_file = ROOT / "data" / "digest_state.json"
    yesterday  = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).strftime(
        "%Y-%m-%dT00:00:00"
    )
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
        # Set last_run to start of today so all messages posted moments ago are included
        state["last_run"] = yesterday
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    # If no state file, the pipeline will use lookback_hours from config (defaults to 24 h)
    info(f"State reset — digest will fetch messages since {yesterday}")


# ─────────────────────────────────────────────────────────────
# Step 4 — Run digest pipeline
# ─────────────────────────────────────────────────────────────
async def run_digest_pipeline():
    """Fetch → Analyze → Post digest to Slack."""
    step_header(3, "Running AI digest pipeline → posting to Slack")

    from daily_digest.config import get_config
    from daily_digest.slack_client import SlackClient
    from daily_digest.orchestrator import DigestOrchestrator
    from daily_digest.formatter import DigestFormatter
    from daily_digest.distributor import DigestDistributor
    from daily_digest.state import DigestState, DigestRun
    from daily_digest.observability import logger

    # Suppress noisy INFO logs during the demo — only show our own prints
    import logging
    logging.getLogger("daily_digest").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    config = get_config()
    slack  = SlackClient()   # Real Slack
    state  = DigestState()

    since = state.get_last_run()
    info(f"Fetching messages since  {since.isoformat() if since else 'all time'}")

    run_ts = datetime.now()
    run_id = run_ts.strftime("%Y%m%d_%H%M%S")

    # ── Fetch messages ────────────────────────────────────────
    from daily_digest.message_aggregator import MessageAggregator
    aggregator      = MessageAggregator(slack, config)
    channel_messages = await aggregator.fetch_all_channels(since)
    total_msgs       = sum(cm.message_count for cm in channel_messages)

    ok(f"Fetched {total_msgs} messages from {len(channel_messages)} channels")
    for cm in channel_messages:
        info(f"  #{cm.channel_name}: {cm.message_count} messages")

    # ── Analyze teams (Bedrock) ───────────────────────────────
    print()
    info("Analyzing teams with AI (AWS Bedrock) …")
    orchestrator = DigestOrchestrator(config=config, mock_mode=False)
    output        = await orchestrator.run(slack, since)

    teams = output.team_analyses
    ok(f"Analyzed {len(teams)} team(s)")
    for name, ta in teams.items():
        b = len(ta.blockers);  d = len(ta.decisions);  a = len(ta.action_items)
        info(f"  {name.capitalize():12s}  tone={ta.tone:12s}  blockers={b}  decisions={d}  actions={a}")

    total_events = output.global_digest.total_events
    ok(f"Extracted {total_events} events total")

    cross = output.global_digest.cross_team_highlights
    if cross:
        ok(f"Detected {len(cross)} cross-team dependency alert(s)")

    # ── Format & distribute ───────────────────────────────────
    print()
    info("Posting digest to Slack …")
    formatter    = DigestFormatter()
    distributor  = DigestDistributor(slack, config, formatter)
    result       = await distributor.distribute(output, teams, run_id=run_id)

    errors = result.get("errors", [])
    items  = result.get("item_posts", [])
    dms    = result.get("dms", [])

    ok(f"Posted {len(items)} digest item(s) to main #digest channel")
    for name in teams:
        ok(f"Posted team breakdown to #{name} channel")
    if dms:
        ok(f"Sent {len(dms)} leadership DM(s)")

    if errors:
        for e in errors:
            info(f"  ⚠ {e}")

    # ── Save state ────────────────────────────────────────────
    run_record = DigestRun(
        run_id=run_id,
        timestamp=run_ts.isoformat(),
        channels_processed=list(teams.keys()),
        message_counts={n: ta.message_count for n, ta in teams.items()},
        success=not errors,
    )
    state.save_run(run_record)
    info(f"State saved — next run will start from {run_ts.isoformat()}")

    return result


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="ThreadBrief full end-to-end demo")
    parser.add_argument("--days",     type=int, default=1,    help="Days of data to generate (default: 1)")
    parser.add_argument("--channels", type=int, default=3,    help="Channels to populate (default: 3)")
    parser.add_argument("--skip-generate", action="store_true", help="Skip data generation (use existing fixtures)")
    parser.add_argument("--skip-seed",     action="store_true", help="Skip seeding Slack channels")
    args = parser.parse_args()

    banner()

    start = time.time()

    # Step 1: Generate data
    if not args.skip_generate:
        generate_data(days=args.days, channels=args.channels)
    else:
        info("Skipping data generation (--skip-generate)")

    # Step 2: Seed channels
    if not args.skip_seed:
        seed_channels()
    else:
        info("Skipping channel seeding (--skip-seed)")

    # Step 2.5: Reset state
    reset_state()

    # Step 3: Run digest
    asyncio.run(run_digest_pipeline())

    # Done
    elapsed = time.time() - start
    print()
    separator()
    print()
    print(BOLD + GREEN + f"  ✅  ThreadBrief demo complete!  ({elapsed:.1f}s)" + RESET)
    print()
    print(f"  Check Slack — digest posted to:")
    digest_ch = os.getenv("CHANNEL_DIGEST", "digest")
    print(f"    • #digest channel  ({digest_ch})")
    print(f"    • Each team channel (breakdowns)")
    print(f"    • Leadership DMs")
    print()


if __name__ == "__main__":
    main()
