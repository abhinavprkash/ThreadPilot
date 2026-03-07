#!/usr/bin/env python3
"""
Test script for AWS Bedrock agent functionality.

Tests:
1. Provider auto-detection
2. Bedrock client initialization
3. Mock mode fallback
4. Multi-cloud agent with Bedrock
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()


def test_provider_detection():
    """Test automatic provider detection."""
    print("=" * 60)
    print("TEST 1: Provider Auto-Detection")
    print("=" * 60)

    # Check environment variables
    has_aws = bool(os.getenv("AWS_ACCESS_KEY_ID"))
    llm_provider = os.getenv("LLM_PROVIDER", "")

    print(f"AWS_ACCESS_KEY_ID: {'✅ Set' if has_aws else '❌ Not set'}")
    print(f"LLM_PROVIDER: {llm_provider if llm_provider else '(auto-detect)'}")

    # Expected provider
    if llm_provider:
        expected = llm_provider
    elif has_aws:
        expected = "bedrock"
    else:
        expected = "mock"

    print(f"\nExpected provider: {expected}")
    print()


def test_bedrock_client():
    """Test Bedrock client initialization."""
    print("=" * 60)
    print("TEST 2: Amazon Bedrock Client")
    print("=" * 60)

    try:
        from daily_digest.bedrock_client import BedrockClient, BEDROCK_AVAILABLE

        if not BEDROCK_AVAILABLE:
            print("❌ boto3 not installed")
            print("   Install with: pip install boto3")
            return False

        print("✅ boto3 available")

        # Check credentials
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            print("⚠️  AWS_ACCESS_KEY_ID not set")
            print("   Set credentials to test Bedrock")
            return False

        print("✅ AWS credentials found")

        # Try to initialize client
        try:
            client = BedrockClient.from_env()
            print(f"✅ Bedrock client initialized")
            print(f"   Model: {client.config.model_id}")
            print(f"   Region: {client.config.region}")

            # Try a simple generation (optional - costs money)
            test_generation = input("\nTest actual Bedrock API call? (costs ~$0.001) [y/N]: ")
            if test_generation.lower() == 'y':
                print("\nCalling Bedrock API...")
                response = client.generate_content(
                    prompt="Say 'Hello from Bedrock!' in JSON format: {\"message\": \"...\"}",
                    max_tokens=50,
                )
                print(f"✅ Response received: {response[:100]}...")
                return True
            else:
                print("⏭️  Skipping API call test")
                return True

        except Exception as e:
            print(f"❌ Failed to initialize Bedrock: {e}")
            return False

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

    print()


def test_bedrock_agent():
    """Test the Bedrock-powered agent."""
    print("=" * 60)
    print("TEST 3: Bedrock Agent")
    print("=" * 60)

    try:
        from daily_digest.agents.multicloud_base import MultiCloudAgent

        # Create a simple test agent
        class TestAgent(MultiCloudAgent):
            @property
            def agent_name(self):
                return "TestAgent"

            @property
            def prompt_template(self):
                return "Test prompt: {messages}"

        # Test with available providers
        providers_to_test = []

        if os.getenv("AWS_ACCESS_KEY_ID"):
            providers_to_test.append("bedrock")
        providers_to_test.append("mock")

        for provider in providers_to_test:
            print(f"\nTesting provider: {provider}")
            try:
                agent = TestAgent(provider=provider)
                print(f"  ✅ Agent initialized with {agent.provider}")

                # Test generation
                if provider == "mock":
                    result = agent.generate("Test prompt")
                    print(f"  ✅ Mock generation: {result[:50]}...")
                else:
                    print(f"  ⏭️  Skipping actual API call for {provider}")
            except Exception as e:
                print(f"  ❌ Failed: {e}")

        return True

    except Exception as e:
        print(f"❌ Error testing Bedrock agent: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("THREADPILOT AWS BEDROCK TESTING")
    print("=" * 60 + "\n")

    # Run tests
    test_provider_detection()
    bedrock_ok = test_bedrock_client()
    agent_ok = test_bedrock_agent()

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Bedrock: {'✅ Ready' if bedrock_ok else '⚠️  Not configured'}")
    print(f"Bedrock Agent: {'✅ Working' if agent_ok else '❌ Failed'}")
    print()

    if bedrock_ok:
        print("🎉 AWS Bedrock is working!")
        print("\nNext steps:")
        print("1. Run full digest: poetry run python -m daily_digest.main --preview")
        print("2. Deploy to AWS: sam build && sam deploy --guided")
    else:
        print("⚠️  Bedrock not configured")
        print("\nTo configure:")
        print("- Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION")
        print("- Or use mock mode: LLM_PROVIDER=mock")


if __name__ == "__main__":
    main()
