# Personalized DM Feature

## Overview

ThreadPilot now supports sending personalized daily digests via Direct Messages to Slack users. This uses a decoupled two-step architecture:

1. **Backend generates digest + exports to JSON** - Fast, idempotent
2. **Standalone bot sends DMs from JSON** - Handles rate limits, retries

## Architecture Benefits

✅ **Reliability**: JSON acts as audit log, easy to retry failures
✅ **Scalability**: Bot handles Slack rate limits independently
✅ **Flexibility**: Can re-send same digest or customize distribution
✅ **Testing**: Dry-run mode for safe testing

## Quick Start

### 1. Configure Environment

Add to your `.env` file:

```bash
# Required
SLACK_BOT_TOKEN=xoxb-your-token-here
CHANNEL_DIGEST=C0123456789

# Optional - for leadership DMs
LEADERSHIP_USERS=U0123456789,U9876543210
```

### 2. Required Slack Permissions

Your bot needs these OAuth scopes:
- `chat:write` - Send messages
- `users:read` - Get user info
- `im:write` - Open DMs with users
- `channels:history` - Read channel messages

### 3. Generate Digest & Export DMs

```bash
# Generate digest and export personalized DMs to JSON
python scripts/demo_personalized_dms.py --export

# Or export only for leadership users
python scripts/demo_personalized_dms.py --export --leadership-only

# Custom output path
python scripts/demo_personalized_dms.py --export --output data/my_dms.json
```

This creates a JSON file like:
```json
{
  "run_id": "20260215_140000",
  "date": "2026-02-15",
  "total_messages": 25,
  "messages": [
    {
      "user_id": "U123456",
      "user_name": "Jane Doe",
      "text": "📰 Personalized Digest...",
      "message_type": "leadership"
    }
  ]
}
```

### 4. Send DMs

```bash
# Test with dry-run first (recommended)
python scripts/send_dm_bot.py --input data/personalized_dms.json --dry-run

# Actually send DMs
python scripts/send_dm_bot.py --input data/personalized_dms.json

# Adjust rate limit delay (default: 1.0s)
python scripts/send_dm_bot.py --input data/personalized_dms.json --delay 1.5
```

### 5. Send Test DM

```bash
# Send test DM to yourself first
python scripts/send_dm_bot.py --test U123456789
```

## Message Personalization

### Leadership Users
- Executive summary with cross-team insights
- Top blockers, decisions, and action items
- Ranked by relevance and severity
- "Why you got this" explanations

### Regular Users
- Team-focused digest
- Key blockers and decisions
- Concise summary format
- Link to full digest channel

## Usage Examples

### Example 1: Daily Automated Workflow

```bash
#!/bin/bash
# daily_digest_with_dms.sh

# Generate digest and export DMs
python scripts/demo_personalized_dms.py --export

# Send DMs after successful generation
if [ $? -eq 0 ]; then
    python scripts/send_dm_bot.py --input data/personalized_dms.json --delay 1.5
fi
```

### Example 2: Leadership Only

```bash
# Generate and send DMs only to leadership
python scripts/demo_personalized_dms.py --export --leadership-only
python scripts/send_dm_bot.py --input data/personalized_dms.json
```

### Example 3: Test with Mock Data

```bash
# Use mock data for testing
python scripts/demo_personalized_dms.py --export --mock
python scripts/send_dm_bot.py --input data/personalized_dms.json --dry-run
```

### Example 4: Interactive Demo

```bash
# Run interactive demo
python scripts/demo_personalized_dms.py --demo
```

## API Usage (Python)

```python
from daily_digest.config import DigestConfig
from daily_digest.slack_client import SlackClient
from daily_digest.orchestrator import DigestOrchestrator
from daily_digest.distributor import DigestDistributor

# Setup
config = DigestConfig.from_env()
slack_client = SlackClient()
orchestrator = DigestOrchestrator(slack_client, config)
distributor = DigestDistributor(slack_client, config)

# Generate digest
result = await orchestrator.run()
output = result["output"]
team_analyses = result["team_analyses"]

# Export personalized DMs
export_result = distributor.export_personalized_dms(
    output=output,
    team_analyses=team_analyses,
    output_path="data/personalized_dms.json",
    include_leadership_only=False,  # Set True for leadership only
)

print(f"Exported {export_result['messages_generated']} DMs")
```

## Rate Limits

Slack rate limits for `chat.postMessage`:
- **Tier 3**: ~1 message per second per workspace
- **Burst**: Up to 20 messages, then throttles

**Best practices:**
- Use `--delay 1.0` or higher (default: 1.0s)
- For 100 users: ~100 seconds (~1.7 minutes)
- For 1000 users: ~1000 seconds (~16.7 minutes)

## Error Handling

The bot automatically handles:
- ✅ Network failures - logs error and continues
- ✅ Invalid user IDs - skips and logs
- ✅ Missing permissions - logs error
- ✅ Rate limit errors - respects delay between messages

Failed messages are logged in the output. You can:
1. Check the bot output for errors
2. Fix issues (e.g., permissions, user IDs)
3. Re-run with same JSON file

## User Privacy & Consent

**Important considerations:**
- Users can block/mute your bot
- Some orgs restrict bot DMs
- Consider opt-in/opt-out mechanism
- Add unsubscribe message in DMs

**Example opt-out message:**
```python
text = f"""
📰 Daily Digest - {date}

{content}

_To stop receiving these DMs, type `/threadpilot unsubscribe` or DM the bot._
"""
```

## Troubleshooting

### "Error: SLACK_BOT_TOKEN not found"
- Make sure `.env` file has `SLACK_BOT_TOKEN` set
- Run `source .env` or load environment variables

### "Error sending DM: not_in_channel"
- Bot needs `im:write` permission
- Reinstall bot with updated scopes

### "Rate limit exceeded"
- Increase `--delay` value
- Slack tier 3 methods allow ~1 msg/sec

### "User not found"
- User may be deactivated
- Check user ID is valid with `users.info` API

## Production Deployment

For production use:

1. **Scheduling**: Use cron or workflow scheduler
   ```cron
   # Run daily at 9 AM
   0 9 * * * /path/to/daily_digest_with_dms.sh
   ```

2. **Monitoring**: Log outputs, track failures

3. **Testing**: Always run dry-run first in new environments

4. **Scaling**: For large workspaces (1000+ users), consider:
   - Breaking into batches
   - Running bot on separate server
   - Using message queues (Redis, RabbitMQ)

## See Also

- [Main README](../README.md) - General ThreadPilot documentation
- [Slack API Docs](https://api.slack.com/methods/chat.postMessage) - Rate limits & permissions
- [scripts/send_dm_bot.py](send_dm_bot.py) - Bot source code
