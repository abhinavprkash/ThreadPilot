# ThreadPilot - AI-Powered Slack Digest Generator

To evaluate the project, run `python judge_demo.py` — it triggers the live Lambda endpoint, seeds realistic messages into the Slack channels, runs the full AI pipeline, and prints the result. No credentials needed on your end.

---

## What It Does

ThreadPilot automatically generates intelligent daily digests from team Slack conversations using Amazon Bedrock (Nova Micro). It fetches messages from engineering channels, runs specialized AI agents to extract blockers, decisions, and cross-team dependencies, then posts a structured digest to Slack and DMs leadership.

## AWS Integration

- Amazon Bedrock - Nova Micro for intelligent message analysis
- AWS Lambda - Serverless digest generation (zero server management)
- Amazon DynamoDB - State management and memory persistence
- Amazon S3 - Audit logs and digest storage
- AWS Secrets Manager - Secure credential management
- Amazon EventBridge - Scheduled daily execution

## Quick Start - Local Development

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Choose your LLM provider:

   Option A: AWS Bedrock (Recommended for production)
   ```bash
   cp .env.example .env
   export AWS_ACCESS_KEY_ID=your-key
   export AWS_SECRET_ACCESS_KEY=your-secret
   export LLM_PROVIDER=bedrock
   ```

   Option B: Google Gemini (For local testing)
   ```bash
   cp .env.example .env
   export GOOGLE_API_KEY=your-key
   export LLM_PROVIDER=gemini
   ```

3. Run locally:
   ```bash
   poetry run python -m daily_digest.main --mock --preview
   ```

## Deploy to AWS

```bash
# Prerequisites: AWS CLI + SAM CLI installed
sam build --template-file aws/template.yaml
sam deploy --guided
```

## Features

- Multi-team aggregation: Fetches messages from mechanical, electrical, and software team channels
- AI-powered analysis via specialized agents:
  - TeamAnalyzer: Extracts updates, blockers, and decisions
  - DependencyLinker: Detects cross-team dependencies
  - Feedback System: Learns from user reactions
  - Personalization: Ranks content by persona (Lead, IC, PM, Executive)
- Smart distribution: Posts to digest channel, threads details, and DMs leadership
- Mock testing: In-process mock Slack client for development
- Synthetic data generation: Creates realistic multi-day conversations for testing

## Command Reference

### Generate Synthetic Data

```bash
poetry run generate-data --days 5 --channels 5 --output data/my_conversations.json
```

Options:
- `--days N`: Number of days to generate (default: 5)
- `--channels N`: Number of channels to generate (default: 5, max: 5)
- `--output PATH`: Output file path

### Run Digest Pipeline

Test with mock Slack data and real AI analysis:
```bash
poetry run python -m daily_digest.main --mock --preview
```

With real Slack (production):
```bash
poetry run python -m daily_digest.main
```

Preview mode (generate but do not post):
```bash
python -m daily_digest.main --preview
```

Debug mode:
```bash
python -m daily_digest.main --debug
```

### Run Tests

```bash
pytest tests/ -v
pytest tests/ --cov=daily_digest
```

## Project Structure

```
src/daily_digest/
├── config.py              # Channel and distribution configuration
├── slack_client.py        # Real + Mock Slack client wrapper
├── message_aggregator.py  # Fetch and filter messages
├── distributor.py         # Posts to Slack + exports DMs
├── formatter.py           # Formats Slack blocks and messages
├── agents/                # AI agents
│   ├── base.py
│   ├── team_analyzer.py
│   └── dependency_linker.py
├── orchestrator.py        # Orchestrates agents
├── state.py               # Last-run tracking
├── observability.py       # Metrics logging
└── main.py                # CLI entry point

aws/
├── lambda_handler.py      # Lambda handlers (public demo endpoint + scheduled)
├── template.yaml          # SAM template
├── deploy.sh              # Packaging script
└── requirements-lambda.txt

scripts/
├── generate_synthetic_data.py   # Synthetic conversation generator
├── demo_trigger.py              # Local seeding + Lambda trigger
└── send_dm_bot.py               # Standalone DM sender

judge_demo.py              # Zero-dependency judge script (runs the full pipeline)
slack_manifest.yaml        # Slack app manifest for one-click bot install
```

## Notes

- The `--mock` flag only mocks the Slack client, not the AI agents (real API calls happen)
- Mock mode uses fixture data from `fixtures/slack_mock.json`
- Memory files are written to `data/memory/` locally and `/tmp/data/memory/` on Lambda
- Never commit `.env` (already in `.gitignore`)
