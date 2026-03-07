#!/usr/bin/env python3
"""
ThreadBrief — Hackathon Demo Setup
====================================
Run this ONCE before the demo to:
  1. Find (or create) the #hackathon-live-demo channel.
  2. Invite the bot to the channel.
  3. Seed it with 24 h of synthetic team conversations (so the AI has data).
  4. Post a "ready" banner so judges know where to look.
  5. Print the exact curl command to give to judges.

Usage:
    poetry run python scripts/setup_demo.py
    poetry run python scripts/setup_demo.py --function-url https://abc123.lambda-url.us-east-1.on.aws/
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ── ANSI helpers ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"

DEMO_CHANNEL_NAME = "hackathon-live-demo"

# ── Synthetic conversations to seed the demo channel ─────────────────────────
SEED_MESSAGES = [
    # Simulates a multi-team engineering workspace
    ("*[Sarah / Mechanical]*: Morning everyone! FYI the servo calibration data "
     "from yesterday's run is in the shared drive. Numbers look solid."),
    ("*[James / Software]*: Got the API endpoint for sensor telemetry deployed "
     "to staging. Can you test against your latest firmware build? @Priya"),
    ("*[Priya / Electrical]*: On it. Side note — the 5V rail on board rev3 is "
     "showing a 0.2V drop under load. Flagging as a *potential blocker* before "
     "the integration test this afternoon."),
    ("*[James / Software]*: That's going to affect our ADC readings. Can we "
     "compensate in firmware or do we need a hardware fix?"),
    ("*[Priya / Electrical]*: Let's do a quick firmware workaround first. "
     "*Decision: apply calibration offset in firmware, revisit hardware in rev4.*"),
    ("*[Sarah / Mechanical]*: The gyro mount bracket tolerance issue from last "
     "week is resolved — new parts arrived and fit within spec. ✅"),
    ("*[James / Software]*: Great news. Pushing the telemetry dashboard update "
     "now. Everyone should be able to see live sensor feeds after 14:00."),
    ("*[Priya / Electrical]*: *Action item for me*: document the voltage "
     "compensation values and add them to the hardware spec sheet by EOD."),
    ("*[Sarah / Mechanical]*: Reminder — design review meeting tomorrow at 10:00. "
     "Please have your subsystem status updated in Confluence before then."),
    ("*[James / Software]*: The CI pipeline is failing on the new nav module "
     "tests. Looks like a dependency version conflict — investigating."),
    ("*[Priya / Electrical]*: Also — battery thermal tests completed. Peak "
     "temperature 42°C under 2C discharge. Well within limits. 🔋"),
    ("*[James / Software]*: Dependency issue fixed. Tests green now. "
     "*Pushing nav module v2.1 to staging.*"),
    ("*[Sarah / Mechanical]*: *Blocker*: we're waiting on the RF module "
     "datasheets from the supplier before we can finalize the antenna placement. "
     "ETA from supplier: 2 days."),
    ("*[Priya / Electrical]*: I have an older version of the datasheet from a "
     "similar module — sharing now in #electrical. Should unblock initial layout."),
    ("*[James / Software]*: Full system integration test scheduled for tomorrow "
     "15:00. Please have all interfaces locked by 12:00. Thanks everyone! 🚀"),
]


def find_or_create_channel(client: WebClient, name: str) -> str:
    """Return the channel ID for the given channel name, creating it if needed."""
    print(f"\n{CYAN}[1/4]{RESET} Looking for #{name}...")

    # Search in public channels
    try:
        for page in client.conversations_list(types="public_channel", limit=200):
            for ch in page.get("channels", []):
                if ch["name"] == name:
                    cid = ch["id"]
                    print(f"      Found existing channel: {cid}")
                    return cid
    except SlackApiError as e:
        print(f"      {YELLOW}Warning:{RESET} Could not list channels: {e.response['error']}")

    # Create the channel
    try:
        resp = client.conversations_create(name=name, is_private=False)
        cid = resp["channel"]["id"]
        print(f"      {GREEN}Created #{name}:{RESET} {cid}")
        return cid
    except SlackApiError as e:
        err = e.response["error"]
        if err == "name_taken":
            print(f"      {YELLOW}Channel exists but bot can't see it.{RESET} "
                  "Please invite the bot manually and re-run.")
            sys.exit(1)
        raise


def invite_bot(client: WebClient, channel_id: str):
    """Join / invite the bot to the channel."""
    print(f"\n{CYAN}[2/4]{RESET} Inviting bot to channel...")
    try:
        client.conversations_join(channel=channel_id)
        print(f"      {GREEN}Bot joined channel.{RESET}")
    except SlackApiError as e:
        err = e.response["error"]
        if err in ("already_in_channel", "method_not_applicable"):
            print(f"      Bot is already in the channel.")
        else:
            print(f"      {YELLOW}Warning:{RESET} {err} — you may need to /invite @ThreadBrief manually.")


def seed_channel(client: WebClient, channel_id: str):
    """Post synthetic team messages to give the AI something to digest."""
    print(f"\n{CYAN}[3/4]{RESET} Seeding channel with synthetic team conversations...")
    posted = 0
    for i, text in enumerate(SEED_MESSAGES):
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=text,
                unfurl_links=False,
                unfurl_media=False,
            )
            posted += 1
            print(f"      {DIM}[{i+1}/{len(SEED_MESSAGES)}] posted{RESET}", end="\r")
            time.sleep(1.1)   # respect Slack tier-1 rate limit
        except SlackApiError as e:
            print(f"\n      {YELLOW}Warning:{RESET} Could not post message {i+1}: {e.response['error']}")

    print(f"      {GREEN}✓ Seeded {posted} messages.{RESET}          ")


def post_ready_banner(client: WebClient, channel_id: str, function_url: str):
    """Post a welcome banner so judges know this channel is live."""
    print(f"\n{CYAN}[4/4]{RESET} Posting ready banner...")
    curl_cmd = f"curl -X POST {function_url}" if function_url else "curl -X POST <your-lambda-url>"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🧵 ThreadBrief — Live Demo Channel"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Welcome, judge!* 👋\n"
                    "This channel shows ThreadBrief in action.\n\n"
                    "The bot just had 15 team messages seeded above — "
                    "real engineering conversations about blockers, decisions and action items.\n\n"
                    "*To trigger the AI digest, run this in your terminal:*"
                ),
            },
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_preformatted",
                    "elements": [{"type": "text", "text": curl_cmd}],
                }
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Watch this channel. Within ~60 seconds the AI will post a "
                    "structured digest — blockers surfaced, decisions captured, "
                    "action items listed. No polling, no refresh needed. 🤖"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Powered by *Amazon Bedrock (Nova Micro)* · *AWS Lambda* · "
                        f"*Python 3.12*  |  Setup at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
                    ),
                }
            ],
        },
    ]

    try:
        client.chat_postMessage(
            channel=channel_id,
            text="🧵 ThreadBrief Live Demo — run the curl command to trigger the AI digest!",
            blocks=blocks,
        )
        print(f"      {GREEN}✓ Banner posted.{RESET}")
    except SlackApiError as e:
        print(f"      {YELLOW}Warning:{RESET} Could not post banner: {e.response['error']}")


def print_summary(channel_id: str, function_url: str):
    curl_cmd = f"curl -X POST {function_url}" if function_url else "curl -X POST <paste-your-lambda-function-url>"
    workspace_url = "https://slack.com/signin"

    print()
    print(BOLD + CYAN + "╔══════════════════════════════════════════════════════════════╗" + RESET)
    print(BOLD + CYAN + "║            🎉  ThreadBrief Demo is LIVE!                     ║" + RESET)
    print(BOLD + CYAN + "╚══════════════════════════════════════════════════════════════╝" + RESET)

    print(f"""
{BOLD}For judges:{RESET}

  1. Join the Slack workspace (send them your workspace invite link)
     Then navigate to:  #{DEMO_CHANNEL_NAME}  (channel ID: {channel_id})

  2. In their terminal, run:

       {BOLD}{GREEN}{curl_cmd}{RESET}

  3. Watch #{DEMO_CHANNEL_NAME} — the AI digest will appear in ~60 s.

{BOLD}If you don't have a Function URL yet:{RESET}
  • Go to Lambda Console → your function → Configuration → Function URL → Create
  • Auth type: NONE
  • CORS: Allow origin *, method POST
  • Copy the URL and re-run:
      poetry run python scripts/setup_demo.py --function-url <url>

{BOLD}Your DEMO_CHANNEL ID to add to Lambda env vars:{RESET}
  DEMO_CHANNEL = {channel_id}
""")


def parse_args():
    p = argparse.ArgumentParser(description="Set up ThreadBrief hackathon demo channel")
    p.add_argument(
        "--function-url",
        default=os.getenv("LAMBDA_FUNCTION_URL", ""),
        help="Lambda Function URL (https://...lambda-url...on.aws/). "
             "Can also be set via LAMBDA_FUNCTION_URL env var.",
    )
    p.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip seeding messages (use if channel already has data)",
    )
    p.add_argument(
        "--channel",
        default=DEMO_CHANNEL_NAME,
        help=f"Demo channel name without # (default: {DEMO_CHANNEL_NAME})",
    )
    return p.parse_args()


def main():
    args = parse_args()

    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print(f"{RED}Error:{RESET} SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)

    client = WebClient(token=token)

    print()
    print(BOLD + "ThreadBrief Demo Setup" + RESET)
    print(DIM + "─" * 40 + RESET)

    # 1. Find / create channel
    channel_id = find_or_create_channel(client, args.channel)

    # 2. Invite bot
    invite_bot(client, channel_id)

    # 3. Seed messages
    if not args.no_seed:
        seed_channel(client, channel_id)
    else:
        print(f"\n{CYAN}[3/4]{RESET} Skipping seed (--no-seed)")

    # 4. Post banner
    post_ready_banner(client, channel_id, args.function_url)

    # Summary
    print_summary(channel_id, args.function_url)


if __name__ == "__main__":
    main()
