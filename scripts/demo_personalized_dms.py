#!/usr/bin/env python3
"""
Demo script showing how to generate and export personalized DMs.

This demonstrates the two-step workflow:
1. Generate digest + export personalized DMs to JSON
2. Use send_dm_bot.py to send the DMs

Usage:
    # Step 1: Generate digest and export DMs
    python scripts/demo_personalized_dms.py --export

    # Step 2: Send DMs (in another terminal or after step 1)
    python scripts/send_dm_bot.py --input data/personalized_dms.json --dry-run
    python scripts/send_dm_bot.py --input data/personalized_dms.json  # actual send
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from daily_digest.config import DigestConfig
from daily_digest.slack_client import SlackClient
from daily_digest.orchestrator import DigestOrchestrator
from daily_digest.distributor import DigestDistributor
from daily_digest.formatter import DigestFormatter


async def generate_and_export_dms(
    output_path: str = "data/personalized_dms.json",
    leadership_only: bool = False,
    mock_mode: bool = False,
):
    """
    Generate digest and export personalized DMs to JSON.

    Args:
        output_path: Where to save the JSON file
        leadership_only: If True, only generate DMs for leadership users
        mock_mode: If True, use mock data instead of real Slack
    """
    print(f"{'='*60}")
    print("Step 1: Generate Digest & Export Personalized DMs")
    print(f"{'='*60}\n")

    # Load configuration
    config = DigestConfig.from_env()

    # Initialize clients
    if mock_mode:
        print("🧪 Running in MOCK mode with fixture data")
        slack_client = SlackClient(mock_data_path="fixtures/slack_mock.json")
    else:
        print("🔴 Running in LIVE mode with real Slack data")
        slack_client = SlackClient()

    # Create orchestrator and distributor
    orchestrator = DigestOrchestrator(slack_client, config)
    distributor = DigestDistributor(slack_client, config)

    print("\n📊 Generating digest...")

    # Generate the digest
    result = await orchestrator.run()

    if not result.get("success"):
        print(f"❌ Failed to generate digest: {result.get('error')}")
        return False

    output = result["output"]
    team_analyses = result["team_analyses"]

    print(f"✅ Digest generated successfully")
    print(f"   - Date: {output.global_digest.date}")
    print(f"   - Teams: {', '.join(team_analyses.keys())}")

    # Export personalized DMs to JSON
    print(f"\n📤 Exporting personalized DMs to {output_path}...")

    export_result = distributor.export_personalized_dms(
        output=output,
        team_analyses=team_analyses,
        output_path=output_path,
        include_leadership_only=leadership_only,
    )

    print(f"✅ Export complete:")
    print(f"   - Total users: {export_result['total_users']}")
    print(f"   - Messages generated: {export_result['messages_generated']}")
    print(f"   - Errors: {export_result['errors_count']}")
    print(f"   - Output: {export_result['output_path']}")

    if export_result['errors']:
        print(f"\n⚠️  Errors encountered:")
        for error in export_result['errors']:
            print(f"   - {error}")

    print(f"\n{'='*60}")
    print("Next Steps:")
    print(f"{'='*60}")
    print(f"\n1. Review the generated DMs:")
    print(f"   cat {output_path}")
    print(f"\n2. Test sending (dry-run):")
    print(f"   python scripts/send_dm_bot.py --input {output_path} --dry-run")
    print(f"\n3. Actually send DMs:")
    print(f"   python scripts/send_dm_bot.py --input {output_path}")
    print()

    return True


async def demo_full_workflow():
    """
    Demo the full workflow: generate digest, export DMs, and show next steps.
    """
    print("\n" + "="*60)
    print("PERSONALIZED DM WORKFLOW DEMO")
    print("="*60 + "\n")

    print("This demo will:")
    print("1. Generate a daily digest from Slack messages")
    print("2. Create personalized DMs for users")
    print("3. Export them to JSON for the bot to send")
    print("\n⚠️  This will use MOCK data for safety")
    print()

    input("Press Enter to continue...")

    # Run with mock data for demo
    success = await generate_and_export_dms(
        output_path="data/demo_dms.json",
        leadership_only=False,
        mock_mode=True,
    )

    if success:
        print("✅ Demo completed successfully!\n")
        return 0
    else:
        print("❌ Demo failed\n")
        return 1


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate digest and export personalized DMs"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export DMs to JSON (uses live Slack data)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/personalized_dms.json",
        help="Output path for JSON file",
    )
    parser.add_argument(
        "--leadership-only",
        action="store_true",
        help="Only generate DMs for leadership users",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of live Slack",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run interactive demo with mock data",
    )

    args = parser.parse_args()

    if args.demo:
        return await demo_full_workflow()

    if args.export:
        success = await generate_and_export_dms(
            output_path=args.output,
            leadership_only=args.leadership_only,
            mock_mode=args.mock,
        )
        return 0 if success else 1

    # Default: show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
