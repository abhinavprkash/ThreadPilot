#!/usr/bin/env python3
"""
ThreadBrief — One-Command Hackathon Demo
==========================================
Posts realistic team conversations to Slack, then triggers the
AI digest via Lambda so judges see the result appear in real time.

Usage:
    python scripts/demo_trigger.py

Or without poetry (after installing deps):
    pip install slack-sdk python-dotenv requests
    python scripts/demo_trigger.py
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
LAMBDA_URL = "https://xtqlsab3xyy3mw4nn6orzgbz7a0ellze.lambda-url.us-east-1.on.aws/"
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")

CHANNELS = {
    "mechanical": os.getenv("CHANNEL_MECHANICAL", ""),
    "electrical":  os.getenv("CHANNEL_ELECTRICAL", ""),
    "software":    os.getenv("CHANNEL_SOFTWARE", ""),
}

# ── Realistic engineering messages to seed ───────────────────────────────────
SEED_MESSAGES = {
    "mechanical": [
        "Morning everyone! Servo calibration data from yesterday's run is in the shared drive. Numbers look solid — within 0.3% of target. ✅",
        "🚨 *Blocker*: Still waiting on RF module datasheets from the supplier. ETA 2 days. This will delay antenna placement finalization.",
        "Gyro mount bracket tolerance issue from last week is fully resolved — new parts arrived and fit within spec.",
        "*Action item*: Update BOM with revised bracket part numbers by EOD.",
        "Reminder: design review meeting tomorrow at 10:00. Please have your subsystem status updated in Confluence before then.",
    ],
    "electrical": [
        "⚠️ *Potential blocker*: 5V rail on board rev3 showing a 0.2V drop under 2A load. Flagging this before the integration test this afternoon.",
        "Battery thermal tests complete. Peak temp 42°C under 2C discharge — well within the 60°C limit. 🔋",
        "*Decision*: Apply firmware calibration offset to compensate for the voltage drop rather than a hardware fix. Will revisit in rev4.",
        "*Action item for me*: Document the voltage compensation values and add to the hardware spec sheet by EOD.",
        "Sharing an older RF datasheet from a similar module in this channel — should unblock the initial layout planning.",
    ],
    "software": [
        "API endpoint for sensor telemetry deployed to staging. Can someone on electrical test against the latest firmware build?",
        "CI pipeline was failing on nav module tests — turned out to be a dependency version conflict. Fixed now, tests are green ✅",
        "*Pushing nav module v2.1 to staging.* Includes the ADC calibration hook for the electrical team's voltage compensation.",
        "Full system integration test is scheduled for tomorrow at 15:00. Please have all interfaces locked by 12:00. 🚀",
        "Telemetry dashboard update is live — everyone can now see live sensor feeds.",
    ],
}

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m";  BOLD = "\033[1m"
GREEN  = "\033[92m"; CYAN = "\033[96m"
YELLOW = "\033[93m"; RED  = "\033[91m"
DIM    = "\033[2m"


def slack_post(channel_id: str, text: str) -> bool:
    payload = json.dumps({"channel": channel_id, "text": text,
                          "unfurl_links": False}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={"Authorization": f"Bearer {SLACK_TOKEN}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("ok", False)
    except Exception as e:
        print(f"  {RED}Slack error:{RESET} {e}")
        return False


def seed_channels():
    print(f"\n{BOLD}Step 1 — Seeding team channels with conversations{RESET}")
    total = sum(len(v) for v in SEED_MESSAGES.values())
    posted = 0
    for team, channel_id in CHANNELS.items():
        if not channel_id:
            print(f"  {YELLOW}Skipping {team}: channel ID not set in .env{RESET}")
            continue
        print(f"  Posting to #{team} …", end="", flush=True)
        for text in SEED_MESSAGES[team]:
            ok = slack_post(channel_id, text)
            posted += 1 if ok else 0
            print(".", end="", flush=True)
            time.sleep(1.2)   # Slack tier-1 rate limit
        print(f" {GREEN}done{RESET}")
    print(f"  {GREEN}✓ {posted}/{total} messages posted{RESET}")


def trigger_lambda() -> dict:
    print(f"\n{BOLD}Step 2 — Triggering AI digest via Lambda{RESET}")
    print(f"  POST {LAMBDA_URL}")
    print(f"  {DIM}Waiting for AI analysis (this takes ~30–90 seconds)…{RESET}")

    req = urllib.request.Request(
        LAMBDA_URL,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {"success": False, "error": body}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    print()
    print(BOLD + CYAN + "╔══════════════════════════════════════════════════════════╗" + RESET)
    print(BOLD + CYAN + "║          🧵  ThreadBrief  —  Live Hackathon Demo          ║" + RESET)
    print(BOLD + CYAN + "╚══════════════════════════════════════════════════════════╝" + RESET)

    if not SLACK_TOKEN:
        print(f"{RED}Error:{RESET} SLACK_BOT_TOKEN not set in .env")
        sys.exit(1)

    # 1. Seed messages
    seed_channels()

    # 2. Trigger Lambda
    result = trigger_lambda()

    # 3. Print result
    print()
    if result.get("success"):
        print(BOLD + GREEN + "✅  Digest complete!" + RESET)
        print(f"  run_id         : {result.get('run_id')}")
        print(f"  teams analysed : {result.get('teams_processed')}")
        print(f"  total events   : {result.get('total_events')}")
        print(f"  elapsed        : {result.get('elapsed_seconds')}s")
        print(f"  slack channel  : {result.get('slack_channel')}")
        print()
        print(f"  {BOLD}👉 Check your Slack digest channel — the AI summary is live!{RESET}")
    else:
        print(BOLD + RED + "❌  Pipeline error" + RESET)
        print(f"  error : {result.get('error')}")
        print(f"  type  : {result.get('error_type')}")
        print()
        print("  Check CloudWatch logs for the full traceback.")
    print()


if __name__ == "__main__":
    main()
