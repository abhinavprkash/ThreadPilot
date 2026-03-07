#!/usr/bin/env python3
"""Test script to verify AWS Bedrock integration works."""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from daily_digest.bedrock_client import BedrockClient, BedrockConfig
from daily_digest.config import get_config
from daily_digest.agents.team_analyzer import TeamAnalyzerAgent


def test_bedrock_client():
    """Test basic Bedrock client connectivity."""
    print("🔍 Testing AWS Bedrock Client...")
    print("-" * 60)

    try:
        # Check AWS credentials
        config = get_config()
        region = config.aws_region
        model_id = config.chat_model
        print(f"AWS Region:   {region}")
        print(f"Model ID:     {model_id}")

        # Check if credentials are configured
        import boto3
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials and credentials.access_key:
            print(f"✅ AWS Credentials: Found ({credentials.access_key[:8]}...)")
        else:
            print("❌ AWS Credentials: Not found")
            print("   Configure with: aws configure")
            print("   Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
            return False

        # Test Bedrock client initialisation
        bedrock_config = BedrockConfig(
            model_id=model_id,
            region=region,
            temperature=config.temperature,
        )
        client = BedrockClient(config=bedrock_config)
        print(f"✅ Bedrock Client: Initialised")

        # Test simple generation
        print("\n📝 Testing content generation...")
        response = client.generate_content(
            prompt="Say exactly: Hello from AWS Bedrock!",
            system_prompt="You are a test assistant. Reply with the exact text requested.",
        )
        print(f"✅ Response: {response.strip()}")

        # Test structured output
        print("\n📊 Testing structured JSON output...")
        structured = client.generate_structured(
            prompt='Return JSON: {"benefits": ["benefit1", "benefit2"]} listing 2 benefits of AWS Bedrock.',
            system_prompt="You are a JSON generator. Return only valid JSON.",
        )
        print(f"✅ Structured output:")
        for benefit in structured.get("benefits", []):
            print(f"   • {benefit}")

        print("\n✅ Bedrock Client Test: PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Bedrock Client Test: FAILED")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Configure credentials: aws configure")
        print("2. Verify Bedrock model access: https://console.aws.amazon.com/bedrock/home#/modelaccess")
        print("3. Check IAM permissions: bedrock:InvokeModel")
        return False


def test_multicloud_agent():
    """Test MultiCloudAgent with Bedrock provider."""
    print("\n" + "=" * 60)
    print("🤖 Testing MultiCloud Agent with Bedrock...")
    print("-" * 60)

    try:
        config = get_config()
        print(f"LLM Provider: {config.llm_provider}")
        print(f"Model:        {config.chat_model}")
        print(f"Region:       {config.aws_region}")

        # Test TeamAnalyzerAgent
        print("\n📊 Testing TeamAnalyzerAgent...")
        analyzer = TeamAnalyzerAgent(
            model_name=config.chat_model,
            temperature=config.temperature,
        )

        # Sample messages
        messages = [
            {"user": "Alice", "text": "Completed the API integration. Ready for testing.", "ts": "1234567890.123456"},
            {"user": "Bob",   "text": "Great! I'll test it this afternoon.", "ts": "1234567891.123456"},
        ]

        result = analyzer.analyze_team("Software", "C123", messages)
        print(f"✅ Analysis complete:")
        print(f"   Summary:   {result.summary[:100]}...")
        print(f"   Updates:   {len(result.updates)}")
        print(f"   Blockers:  {len(result.blockers)}")
        print(f"   Decisions: {len(result.decisions)}")

        print("\n✅ MultiCloud Agent Test: PASSED")
        return True

    except Exception as e:
        print(f"\n❌ MultiCloud Agent Test: FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def estimate_costs():
    """Estimate monthly costs for Bedrock usage."""
    print("\n" + "=" * 60)
    print("💰 AWS Bedrock Cost Estimation")
    print("-" * 60)

    # Claude 3 Sonnet pricing (as of 2024)
    input_price = 0.003  # per 1K input tokens
    output_price = 0.015  # per 1K output tokens

    # Estimated usage per digest
    digests_per_day = 1
    input_tokens_per_digest = 3000  # 3K tokens
    output_tokens_per_digest = 1000  # 1K tokens

    # Monthly calculation
    days_per_month = 30
    total_digests = digests_per_day * days_per_month

    monthly_input_tokens = (input_tokens_per_digest * total_digests) / 1000
    monthly_output_tokens = (output_tokens_per_digest * total_digests) / 1000

    monthly_cost = (monthly_input_tokens * input_price) + (monthly_output_tokens * output_price)

    print(f"Assumptions:")
    print(f"  • Digests per day: {digests_per_day}")
    print(f"  • Input tokens per digest: {input_tokens_per_digest:,}")
    print(f"  • Output tokens per digest: {output_tokens_per_digest:,}")
    print(f"\nMonthly Usage:")
    print(f"  • Total digests: {total_digests}")
    print(f"  • Input tokens: {monthly_input_tokens * 1000:,.0f}")
    print(f"  • Output tokens: {monthly_output_tokens * 1000:,.0f}")
    print(f"\nMonthly Cost: ${monthly_cost:.2f}")
    print(f"\nYour AWS Credits: $220.00")
    print(f"Months covered: {220 / monthly_cost:.1f} months")
    print(f"\n✅ Well within your free tier credits!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("AWS BEDROCK INTEGRATION TEST")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Test 1: Bedrock client
    client_ok = test_bedrock_client()

    # Test 2: MultiCloud agent (only if client works)
    agent_ok = False
    if client_ok:
        agent_ok = test_multicloud_agent()

    # Cost estimation
    estimate_costs()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("-" * 60)
    print(f"Bedrock Client: {'✅ PASSED' if client_ok else '❌ FAILED'}")
    print(f"MultiCloud Agent: {'✅ PASSED' if agent_ok else '❌ FAILED (or skipped)'}")
    print("=" * 60)

    if client_ok and agent_ok:
        print("\n🎉 All tests passed! Your AWS Bedrock integration is ready.")
        print("\nNext steps:")
        print("1. Run the digest: python -m daily_digest.main")
        print("2. Or test with demo: python scripts/demo_run.py")
        print("3. Deploy to AWS: sam build && sam deploy --guided")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check configuration above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
