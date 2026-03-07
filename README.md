# ThreadBrief — AI-Powered Slack Digest

Automatically summarises your team's Slack conversations every day using Amazon Bedrock, extracts blockers, decisions and cross-team dependencies, then posts a structured digest back to Slack and DMs leadership.

---

## Step 1 — Join the Demo Slack Workspace

See the live output in real time:

**[→ Join the ThreadBrief Demo Slack Workspace](https://join.slack.com/t/testing-bc66069/shared_invite/zt-3rxd9kuwy-K9GDpJvEF3zaArjctcTDhQ)**

Once inside, watch these channels:
| Channel | Purpose |
|---|---|
| `#mechanical-team` | Synthetic engineering conversations posted by the bot |
| `#electrical-team` | Synthetic conversations — electrical subteam |
| `#software-team` | Synthetic conversations — software subteam |
| `#all-digest` | **Where the AI digest appears** |

---

## Step 2 — Trigger the Live Demo (no install needed)

Run one of the following in any terminal — VS Code terminal, macOS Terminal, Windows CMD, or PowerShell. No Python packages, no credentials.

### macOS / Linux / VS Code terminal
```bash
curl -s -X POST https://xtqlsab3xyy3mw4nn6orzgbz7a0ellze.lambda-url.us-east-1.on.aws/ \
  -H "Content-Type: application/json" \
  -d '{"seed": true}' | python3 -m json.tool
```

### Windows CMD
```cmd
curl -s -X POST https://xtqlsab3xyy3mw4nn6orzgbz7a0ellze.lambda-url.us-east-1.on.aws/ -H "Content-Type: application/json" -d "{\"seed\": true}"
```

### Windows PowerShell
```powershell
Invoke-RestMethod -Uri "https://xtqlsab3xyy3mw4nn6orzgbz7a0ellze.lambda-url.us-east-1.on.aws/" -Method POST -ContentType "application/json" -Body '{"seed": true}'
```

### Python (zero dependencies — any Python 3.6+)
```bash
python judge_demo.py
```

The command will take **~30–90 seconds** while the AI runs, then print a summary and post the digest to `#all-digest` in Slack.

---

## Architecture

```
Slack Channels
   |  (conversations from mechanical / electrical / software teams)
   |
   v
MessageAggregator          -- fetches & filters messages via Slack SDK
   |
   v
TeamAnalyzerAgent --------- Amazon Bedrock (Nova Micro)
   |   extracts: blockers, decisions, action items, tone per team
   |
DependencyLinker ---------- Amazon Bedrock (Nova Micro)
   |   finds: cross-team dependencies (e.g. electrical waiting on mechanical)
   |
   v
DigestFormatter            -- builds Slack Block Kit payloads
   |
DigestDistributor
   |-- #all-digest channel  -- org-wide summary + individual items
   |-- #team-channels       -- detailed per-team breakdown
   +-- Leadership DMs       -- executive summary with blockers & decisions
```

---

## AWS Services

### Amazon Bedrock — `amazon.nova-micro-v1:0`

The core AI engine. Every digest run makes **two Bedrock `InvokeModel` calls per team**:

1. **TeamAnalyzerAgent** — given the raw Slack messages for a team, returns structured JSON with:
   - `summary` — one-paragraph narrative of the team's day
   - `blockers` — list of blocking issues with owner, severity, status
   - `decisions` — decisions made, who made them, impact
   - `action_items` — next steps with owners and deadlines
   - `tone` — productive / collaborative / challenging / routine

2. **DependencyLinker** — given events from all teams, identifies cross-team dependencies and generates `CrossTeamAlert` objects (e.g. "Electrical is blocked on Mechanical's motor mount dimensions").

Nova Micro is Amazon's fastest and cheapest Bedrock model, ideal for structured JSON extraction from short-to-medium text. Prompts are engineered so the model always returns clean, parseable JSON.

---

### AWS Lambda — Serverless Digest Engine

The entire pipeline runs inside a single Lambda function (`threadpilot-digest-generator`):

| Property | Value |
|---|---|
| Runtime | Python 3.11 |
| Timeout | 900 s (15 min) — enough for multi-team analysis |
| Memory | 1024 MB |
| Trigger (scheduled) | EventBridge cron — every day at 09:00 UTC |
| Trigger (on-demand) | Public Lambda Function URL (no auth) — used by `judge_demo.py` |

Why serverless instead of a server:
- No EC2, no containers to keep alive, no SSH
- Pay-per-execution — fractions of a cent per run; $0 when idle
- Scales automatically — adding more channels requires no infrastructure changes
- Lambda retries on transient failures without any custom logic
- IAM-scoped permissions — the function only has access to exactly what it needs

A second Lambda (`threadpilot-demo-trigger`) serves as the public HTTP endpoint — it has a Function URL with `AuthType: NONE` so anyone can POST to it without credentials.

---

### Amazon DynamoDB — State and Memory

Two tables, both on PAY_PER_REQUEST billing:

| Table | Purpose |
|---|---|
| `threadpilot-state` | Tracks the last successful run timestamp so each run only fetches new messages |
| `threadpilot-memory` | Persists blockers, decisions, and dependency graph across runs |

---

### Amazon S3 — Audit Logs

Every digest output is written to `threadpilot-digests-{account-id}` as a timestamped JSON file. Objects expire after 90 days via a lifecycle rule.

---

### AWS Secrets Manager — Credential Security

Slack tokens (`SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`) are stored under `threadpilot/slack`, not in environment variables. Lambda retrieves them at startup via `GetSecretValue`. Credentials are encrypted at rest with KMS and rotatable without redeployment.

---

### Amazon EventBridge — Scheduled Execution

A cron rule fires daily at 09:00 UTC, invoking the digest Lambda automatically. No cron jobs on servers, no schedulers to maintain.

---

## Full Request Flow

```
Your terminal
   |  POST {"seed": true}
   v
Lambda Function URL (threadpilot-demo-trigger)   <- public HTTPS, no auth
   |
   |-- Clear old bot messages from team channels
   |-- Generate synthetic engineering conversations (Bedrock)
   |-- Post messages to #mechanical-team, #electrical-team, #software-team
   |
   +-- Run digest pipeline:
        |-- Fetch messages back via Slack API
        |-- TeamAnalyzerAgent x 3 teams   (Bedrock InvokeModel)
        |-- DependencyLinker              (Bedrock InvokeModel)
        |-- Format into Slack Block Kit
        +-- Post to #all-digest + send leadership DMs
   |
   v
HTTP 200 { "success": true, "teams_processed": 3, "elapsed_seconds": 47 }
```

---

## Feedback and Personalization

ThreadBrief learns from Slack emoji reactions on digest items:

| Reaction | Signal |
|---|---|
| checkmark | Accurate — boost this type of item |
| cross | Wrong — suppress similar items |
| puzzle | Missing context — add more detail |
| mute | Not relevant — lower priority for this persona |

Reactions are processed before the next digest run. A `PromptEnhancer` injects learned directives into the AI prompts (e.g. "For mechanical team, always include tolerance specs in blocker descriptions").

Personas (Lead, IC, PM, Executive) each receive a differently-ranked digest via `DigestRanker`.

---

## Project Structure

```
src/daily_digest/
├── main.py                # CLI + async entry point
├── orchestrator.py        # Wires all agents together
├── slack_client.py        # Real + Mock Slack client
├── message_aggregator.py  # Fetch, filter, enrich messages
├── formatter.py           # Slack Block Kit formatting
├── distributor.py         # Posts to channels + DMs
├── config.py              # Channel/model configuration
├── state.py               # Last-run timestamp tracking
├── observability.py       # Structured metrics logging
├── agents/
│   ├── team_analyzer.py   # Bedrock: extract blockers/decisions/updates
│   └── dependency_linker.py # Bedrock: cross-team dependency detection
├── feedback/              # Reaction-based learning system
├── memory/                # Persistent blocker/decision graph
└── personalization/       # Per-persona content ranking

aws/
├── lambda_handler.py      # Lambda entrypoints (digest + demo URL + webhook)
├── template.yaml          # SAM / CloudFormation — full infra as code
└── requirements-lambda.txt

scripts/
├── full_demo.py           # One-command local demo (generate -> seed -> digest)
└── generate_synthetic_data.py  # AI-powered conversation generator

judge_demo.py              # Zero-dependency trigger script (standard library only)
```

---

## Local Development

```bash
# Install dependencies
poetry install

# Run full end-to-end demo locally (generates data, seeds Slack, runs digest)
poetry run python scripts/full_demo.py

# Run against real Slack (production mode)
poetry run daily-digest

# Preview mode — generate digest but don't post
poetry run daily-digest --preview

# Mock mode — use fixture data, don't touch real Slack
poetry run daily-digest --mock --preview
```

---

## Deploy to AWS

Requires AWS CLI + SAM CLI:

```bash
sam build --template-file aws/template.yaml
sam deploy --guided
```

The guided deploy prompts for your `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and channel IDs — everything else is wired automatically via the SAM template.
