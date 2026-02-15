#!/usr/bin/env python3
"""
Standalone Slack DM Bot
Reads personalized messages from JSON and sends them to users.

Usage:
    python scripts/send_dm_bot.py --input data/personalized_dms.json
    python scripts/send_dm_bot.py --input data/personalized_dms.json --dry-run
    python scripts/send_dm_bot.py --input data/personalized_dms.json --delay 1.5
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from daily_digest.slack_client import SlackClient
from dotenv import load_dotenv

load_dotenv()


class DMBot:
    """Bot that sends personalized DMs from JSON file."""

    def __init__(
        self,
        slack_token: Optional[str] = None,
        delay_seconds: float = 1.0,
        dry_run: bool = False,
    ):
        """
        Initialize the DM bot.

        Args:
            slack_token: Slack bot token (defaults to SLACK_BOT_TOKEN env var)
            delay_seconds: Delay between messages to respect rate limits
            dry_run: If True, only simulate sending without actual API calls
        """
        self.slack_token = slack_token or os.getenv("SLACK_BOT_TOKEN")
        self.delay_seconds = delay_seconds
        self.dry_run = dry_run

        if not self.slack_token:
            raise ValueError("SLACK_BOT_TOKEN not found in environment")

        self.client = SlackClient(token=self.slack_token)
        self.stats = {
            "total": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None,
        }

    async def send_from_json(self, json_path: str) -> dict:
        """
        Load messages from JSON and send them.

        Args:
            json_path: Path to JSON file with messages

        Returns:
            Dict with sending statistics and results
        """
        print(f"{'[DRY RUN] ' if self.dry_run else ''}Loading messages from {json_path}")

        # Load JSON file
        with open(json_path, "r") as f:
            data = json.load(f)

        messages = data.get("messages", [])
        run_id = data.get("run_id", "unknown")
        date = data.get("date", "unknown")

        self.stats["total"] = len(messages)
        self.stats["start_time"] = datetime.now()

        print(f"\n{'='*60}")
        print(f"Run ID: {run_id}")
        print(f"Date: {date}")
        print(f"Total messages to send: {len(messages)}")
        print(f"Rate limit delay: {self.delay_seconds}s between messages")
        print(f"{'='*60}\n")

        if self.dry_run:
            print("⚠️  DRY RUN MODE - No messages will actually be sent\n")

        # Send messages with rate limiting
        results = []
        for i, message in enumerate(messages, 1):
            user_id = message.get("user_id")
            user_name = message.get("user_name", user_id)
            text = message.get("text", "")
            message_type = message.get("message_type", "standard")

            if not user_id or not text:
                print(f"⚠️  [{i}/{len(messages)}] Skipping invalid message")
                self.stats["skipped"] += 1
                continue

            print(f"📤 [{i}/{len(messages)}] Sending {message_type} DM to {user_name} ({user_id})...")

            try:
                if self.dry_run:
                    # Simulate sending
                    result = {
                        "ok": True,
                        "user_id": user_id,
                        "dry_run": True,
                        "preview": text[:100] + "..." if len(text) > 100 else text,
                    }
                    print(f"✅ [DRY RUN] Would send: {result['preview']}")
                else:
                    # Actually send the DM
                    result = await self.client.send_dm(
                        user_id=user_id,
                        text=text,
                    )

                    if result.get("ok"):
                        print(f"✅ Sent successfully")
                        self.stats["sent"] += 1
                    else:
                        error = result.get("error", "unknown error")
                        print(f"❌ Failed: {error}")
                        self.stats["failed"] += 1

                results.append({
                    "user_id": user_id,
                    "user_name": user_name,
                    "success": result.get("ok", False),
                    "error": result.get("error"),
                    "message_type": message_type,
                })

                # Rate limiting delay
                if i < len(messages):  # Don't delay after last message
                    await asyncio.sleep(self.delay_seconds)

            except Exception as e:
                print(f"❌ Exception: {e}")
                self.stats["failed"] += 1
                results.append({
                    "user_id": user_id,
                    "user_name": user_name,
                    "success": False,
                    "error": str(e),
                    "message_type": message_type,
                })

        self.stats["end_time"] = datetime.now()
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        # Print summary
        print(f"\n{'='*60}")
        print(f"{'DRY RUN ' if self.dry_run else ''}SUMMARY")
        print(f"{'='*60}")
        print(f"Total messages: {self.stats['total']}")
        print(f"✅ Sent successfully: {self.stats['sent']}")
        print(f"❌ Failed: {self.stats['failed']}")
        print(f"⚠️  Skipped: {self.stats['skipped']}")
        print(f"⏱️  Duration: {duration:.1f}s")
        print(f"📊 Rate: {self.stats['total'] / duration:.2f} msg/s")
        print(f"{'='*60}\n")

        return {
            "run_id": run_id,
            "stats": self.stats,
            "results": results,
            "dry_run": self.dry_run,
        }

    async def send_test_dm(self, user_id: str, message: str = None) -> dict:
        """
        Send a test DM to a single user.

        Args:
            user_id: Slack user ID
            message: Custom message (defaults to test message)

        Returns:
            Result dict from Slack API
        """
        if message is None:
            message = (
                "*🧪 Test Message from ThreadPilot DM Bot*\n\n"
                "This is a test message to verify the DM bot is working correctly.\n"
                f"Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        print(f"Sending test DM to {user_id}...")

        if self.dry_run:
            print(f"[DRY RUN] Would send: {message}")
            return {"ok": True, "dry_run": True}

        result = await self.client.send_dm(user_id=user_id, text=message)

        if result.get("ok"):
            print(f"✅ Test DM sent successfully")
        else:
            print(f"❌ Failed to send test DM: {result.get('error')}")

        return result


async def main():
    parser = argparse.ArgumentParser(
        description="Send personalized DMs to Slack users from JSON file"
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to JSON file with messages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate sending without actually sending messages",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.0,
        help="Delay in seconds between messages (default: 1.0)",
    )
    parser.add_argument(
        "--test",
        metavar="USER_ID",
        help="Send a test message to a specific user instead of running full job",
    )

    args = parser.parse_args()

    # Initialize bot
    bot = DMBot(
        delay_seconds=args.delay,
        dry_run=args.dry_run,
    )

    # Test mode
    if args.test:
        result = await bot.send_test_dm(args.test)
        sys.exit(0 if result.get("ok") else 1)

    # Normal mode: send from JSON
    if not args.input:
        parser.error("--input/-i is required when not using --test mode")

    if not Path(args.input).exists():
        print(f"❌ Error: File not found: {args.input}")
        sys.exit(1)

    try:
        result = await bot.send_from_json(args.input)

        # Exit with error code if any messages failed
        if result["stats"]["failed"] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
