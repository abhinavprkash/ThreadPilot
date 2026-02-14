# ThreadPilot - Daily Digest PoC

A proof-of-concept for generating daily team digests from Slack channels using AI agents.

## How to Run

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Get a Google AI Studio API key from https://aistudio.google.com/app/apikey

3. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env and add your GOOGLE_API_KEY
   ```

4. Generate test data and run:
   ```bash
   ./generate_data.sh --days 3 --channels 3
   python -m daily_digest.main --mock
   ```

## Features

- **Multi-team aggregation**: Fetches messages from mechanical, electrical, and software team channels
- **AI-powered analysis**: Uses specialized agents powered by Google Gemini:
  - **TeamAnalyzer**: Extracts updates, blockers, and decisions
  - **DependencyLinker**: Detects cross-team dependencies
  - **Feedback System**: Learns from user reactions
  - **Personalization**: Ranks content by persona (Lead, IC, PM, Executive)
- **Smart distribution**: Posts to digest channel, threads details, and DMs leadership
- **Mock testing**: In-process mock Slack client for development
- **Synthetic data generation**: Creates realistic multi-day conversations for testing

## Quick Start

```bash
# 1. Install dependencies
poetry install

# 2. Set up environment variables
cp .env.example .env
# Edit .env and add your Google AI Studio API key:
#   GOOGLE_API_KEY=your-key-here
#   CHAT_MODEL=models/gemini-2.5-flash

# 3. Generate synthetic conversation data (for testing)
./generate_data.sh --days 5 --channels 5

# 4. Run digest with mock Slack data + real AI analysis
poetry run python -m daily_digest.main --mock --preview

# 5. View results in terminal or check data/memory/*.json files
```

### What You'll See

When you run with `--mock --preview`:
- **Real Gemini AI** analyzes the generated conversations
- **Terminal output** shows the formatted digest
- **Memory files** updated:
  - `data/memory/blockers.json` - Tracked blockers
  - `data/memory/decisions.json` - Team decisions
  - `data/memory/dependency_graph.json` - Cross-team dependencies

**Expected output:**
- Agent analysis takes 15-20 seconds (real API calls)
- Extracts 9+ events, action items, dependencies
- Shows formatted digest preview in terminal

## Command Reference

### Generate Synthetic Data

Creates realistic multi-day Slack conversations for testing the digest pipeline.

**Simple command (works from anywhere):**
```bash
/path/to/ThreadPilot/generate_data.sh --days 5 --channels 5
```

**From project directory:**
```bash
cd ThreadPilot
poetry run generate-data --days 5 --channels 5 --output data/my_conversations.json
```

**Options:**
- `--days N`: Number of days to generate (default: 5)
- `--channels N`: Number of channels to generate (default: 5, max: 5)
- `--output PATH`: Output file path (default: data/synthetic_conversations.json)

**Generated data includes:**
- 16 personas across 5 teams (mechanical, electrical, software, product, QA)
- Story arcs spanning multiple days with dependencies and blockers
- Realistic conversation patterns (standups, bug reports, decisions)
- Thread replies and emoji reactions
- Cross-team dependencies

### Run Digest Pipeline

**Test with mock Slack data + real AI analysis (recommended for testing):**
```bash
poetry run python -m daily_digest.main --mock --preview
```
- Uses fixture data from `fixtures/slack_mock.json`
- **Real Gemini AI** analyzes the conversations
- Shows preview in terminal (doesn't post to Slack)
- Takes 20-30 seconds for AI analysis

**With mock data, post results to mock Slack:**
```bash
poetry run python -m daily_digest.main --mock
```

**With real Slack (production):**
```bash
poetry run python -m daily_digest.main
```

**Preview mode (generate but don't post):**
```bash
python -m daily_digest.main --preview
```

**Debug mode:**
```bash
python -m daily_digest.main --debug
```

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=daily_digest
```

## Project Structure

```
src/daily_digest/
├── config.py              # Channel and distribution configuration
├── slack_client.py        # Real + Mock Slack client wrapper
├── message_aggregator.py  # Fetch and filter messages
├── agents/                # LangChain agents
│   ├── base.py
│   ├── extractor.py
│   ├── blocker_detector.py
│   ├── decision_tracker.py
│   └── summarizer.py
├── digest_generator.py    # Orchestrates agents
├── formatter.py           # Formats Slack output
├── distributor.py         # Posts to Slack
├── state.py              # Last-run tracking
├── observability.py      # Metrics logging
└── main.py               # CLI entry point

scripts/
└── generate_synthetic_data.py  # Synthetic conversation generator

data/
├── synthetic_conversations.json  # Generated test data
├── memory/                       # Persistent memory stores
│   ├── blockers.json
│   └── decisions.json
└── last_run.json                # State tracking
```

## Common Workflows

### Test Full Pipeline with Synthetic Data

```bash
# Step 1: Generate test conversations
cd ThreadPilot
./generate_data.sh --days 3 --channels 3

# Step 2: Run digest with mock Slack + real AI
poetry run python -m daily_digest.main --mock --preview

# Step 3: View results
# - Check terminal output for formatted digest
# - Open data/memory/blockers.json to see extracted blockers
# - Open data/memory/decisions.json to see tracked decisions
```

**What to expect:**
- Generation takes 2-3 minutes (creates realistic conversations)
- Analysis takes 20-30 seconds (Gemini API calls)
- You'll see HTTP 200 OK logs when Gemini API is working
- Preview shows full digest with extracted events, blockers, decisions

### Preview Digest without Posting

```bash
python -m daily_digest.main --preview
```

## Important Notes

- **API Key required**: Get free key from https://aistudio.google.com/app/apikey and add to `.env`
- **Model configuration**: Use `CHAT_MODEL=models/gemini-2.5-flash` (requires "models/" prefix)
- **Mock mode**: The `--mock` flag only mocks Slack client, NOT the AI agents (real Gemini analysis happens)
- **Rate limits**: Free Gemini API has rate limits, data generation includes 5s delays
- **Project directory**: Poetry commands must be run from the directory containing `pyproject.toml`
- **Viewing logs**: Run with `--preview` to see output in terminal, or check `data/memory/*.json` files
- **Security**: Never commit `.env` file (already in `.gitignore`)

## Architecture

```
Slack Channels → Aggregator → Agents → Generator → Formatter → Distributor → Slack
      ↓              ↓           ↓          ↓           ↓            ↓
 mechanical     filter noise   extract   combine    format      #daily-digest
 electrical                   blockers   insights   blocks      leadership DMs
 software                    decisions              threads
```
