#!/usr/bin/env python3
"""
ThreadBrief — Judge Demo Trigger
==================================
No setup needed. Just run this script.

Requires only Python's standard library (no pip installs).

Usage:
    python judge_demo.py
"""

import json
import sys
import urllib.request
import urllib.error

# ── The public Lambda endpoint — no auth required ─────────────────────────────
LAMBDA_URL = "https://xtqlsab3xyy3mw4nn6orzgbz7a0ellze.lambda-url.us-east-1.on.aws/"

# ── ANSI colours (disabled automatically on Windows) ─────────────────────────
_USE_COLOUR = sys.stdout.isatty() and sys.platform != "win32"
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def bold(t):   return _c("1",  t)
def green(t):  return _c("92", t)
def cyan(t):   return _c("96", t)
def yellow(t): return _c("93", t)
def red(t):    return _c("91", t)
def dim(t):    return _c("2",  t)


def main():
    print()
    print(bold(cyan("╔══════════════════════════════════════════════════════════╗")))
    print(bold(cyan("║          🧵  ThreadBrief  —  Hackathon Demo               ║")))
    print(bold(cyan("║     AI-powered Slack digest · Powered by Amazon Bedrock   ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════════════╝")))
    print()
    print(dim("  What this does:"))
    print(dim("  1. Posts realistic engineering team conversations to Slack"))
    print(dim("  2. Triggers an AI analysis via AWS Lambda + Amazon Bedrock"))
    print(dim("  3. A structured digest appears in Slack within ~60 seconds"))
    print()
    print(f"  Endpoint: {dim(LAMBDA_URL)}")
    print()
    print(bold("  Triggering… (please wait, AI is running)"))
    print()

    payload = json.dumps({"seed": True}).encode()
    req = urllib.request.Request(
        LAMBDA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            result = json.loads(e.read())
        except Exception:
            print(red(f"  ✗ HTTP {e.code}: {e.reason}"))
            sys.exit(1)
    except urllib.error.URLError as e:
        print(red(f"  ✗ Connection error: {e.reason}"))
        print(yellow("    Check your internet connection and try again."))
        sys.exit(1)

    print()
    if result.get("success"):
        print(bold(green("  ✅  Digest complete!")))
        print(f"  run_id         : {result.get('run_id')}")
        print(f"  teams analysed : {result.get('teams_processed')}")
        print(f"  total events   : {result.get('total_events')}")
        print(f"  elapsed        : {result.get('elapsed_seconds')}s")
        print()
        print(bold("  👉 Open Slack and check the #all-digest channel!"))
        print(dim("     The AI summary of all team activity is posted there."))
    else:
        print(bold(red("  ✗  Something went wrong")))
        print(f"  error : {result.get('error')}")
        print()
        print(yellow("  The demo infrastructure may be temporarily unavailable."))
        print(yellow("  Please notify the team and try again in a minute."))

    print()


if __name__ == "__main__":
    main()
