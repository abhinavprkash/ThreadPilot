"""
AWS Lambda handler for ThreadPilot digest generation.

This function:
1. Fetches messages from Slack channels
2. Uses Amazon Bedrock (Nova Micro) for AI analysis
3. Optionally stores results in DynamoDB and S3
4. Sends digests back to Slack

Handler: aws.lambda_handler.lambda_handler
Runtime: python3.12
Timeout: 900s (15 min)
Memory: 1024 MB
"""

import asyncio
import json
import os
import urllib.request
import urllib.error
import boto3
from datetime import datetime
from typing import Dict, Any, Optional

# Import ThreadPilot modules (src/ is on PYTHONPATH via Lambda layer / zip layout)
from daily_digest.config import DigestConfig
from daily_digest.slack_client import SlackClient
from daily_digest.orchestrator import DigestOrchestrator
from daily_digest.distributor import DigestDistributor
from daily_digest.formatter import DigestFormatter

# Lazy AWS clients (only created when env vars are present)
_s3_client: Optional[Any] = None
_dynamodb: Optional[Any] = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb')
    return _dynamodb


async def _run_pipeline(config: DigestConfig, preview_mode: bool, run_id: str) -> dict:
    """Async core pipeline: fetch → analyse → distribute."""
    slack_client = SlackClient()
    orchestrator = DigestOrchestrator(config=config, mock_mode=False)
    formatter = DigestFormatter()
    distributor = DigestDistributor(slack_client, config, formatter)

    # Run: returns a DigestOutput dataclass
    output = await orchestrator.run(slack_client, since=None)
    team_analyses = output.team_analyses

    dist_result = {}
    if not preview_mode:
        dist_result = await distributor.distribute(output, team_analyses, run_id=run_id)
    else:
        print("Preview mode: skipping Slack distribution")

    return {"output": output, "team_analyses": team_analyses, "dist_result": dist_result}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler.

    Triggered by:
    - EventBridge cron (scheduled daily)
    - API Gateway (manual trigger)
    - Slack webhook (user command)

    Event format:
    {
        "source": "eventbridge" | "api-gateway" | "slack",
        "channels": {"team_name": "C123", ...},  # optional: specific channels
        "preview_mode": false,                    # optional: don't post to Slack
    }
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        preview_mode = event.get('preview_mode', False)
        channels_override = event.get('channels')

        # Ensure Bedrock is the LLM provider
        os.environ.setdefault('LLM_PROVIDER', 'bedrock')

        # Load configuration from Lambda environment variables
        config = DigestConfig.from_env()
        if channels_override and isinstance(channels_override, dict):
            config.channels = channels_override

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        print(f"Starting digest generation (run_id={run_id})...")
        pipeline = asyncio.run(_run_pipeline(config, preview_mode, run_id))

        output = pipeline["output"]
        team_analyses = pipeline["team_analyses"]
        dist_result = pipeline["dist_result"]

        print(f"Digest generated successfully: {run_id}")

        # ── Optional: store digest snapshot in S3 ──────────────────────────
        s3_bucket = os.getenv('DIGEST_S3_BUCKET')
        s3_location = None
        if s3_bucket:
            digest_data = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "global_digest": {
                    "date": output.global_digest.date,
                    "cross_team_highlights": output.global_digest.cross_team_highlights,
                    "total_events": output.global_digest.total_events,
                },
                "team_analyses": {
                    name: {
                        "summary": getattr(ta, "summary", ""),
                        "blockers": [str(b) for b in getattr(ta, "blockers", [])],
                        "decisions": [str(d) for d in getattr(ta, "decisions", [])],
                        "action_items": [str(a) for a in getattr(ta, "action_items", [])],
                    }
                    for name, ta in team_analyses.items()
                },
            }
            s3_key = f"digests/{run_id}.json"
            _get_s3().put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(digest_data, indent=2, default=str),
                ContentType='application/json',
            )
            s3_location = f"s3://{s3_bucket}/{s3_key}"
            print(f"Stored digest in S3: {s3_location}")

        # ── Optional: update last-run record in DynamoDB ───────────────────
        state_table_name = os.getenv('STATE_TABLE_NAME')
        if state_table_name:
            state_table = _get_dynamodb().Table(state_table_name)
            state_table.put_item(
                Item={
                    'id': 'latest',
                    'run_id': run_id,
                    'timestamp': datetime.now().isoformat(),
                    'total_events': output.global_digest.total_events,
                    'teams_processed': len(team_analyses),
                }
            )
            print(f"Updated state in DynamoDB: {state_table_name}")

        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'run_id': run_id,
                'total_events': output.global_digest.total_events,
                'teams_processed': len(team_analyses),
                'preview_mode': preview_mode,
                's3_location': s3_location,
            }),
            'headers': {'Content-Type': 'application/json'},
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
            }),
            'headers': {'Content-Type': 'application/json'},
        }


def slack_webhook_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle Slack slash-command webhooks: /digest generate

    Slack sends an HTTP POST with URL-encoded body; API Gateway passes it as
    event['body'] (base64-decoded string when isBase64Encoded=true).
    """
    print(f"Slack webhook event: {json.dumps(event)}")

    try:
        from urllib.parse import parse_qs
        raw_body = event.get('body', '')
        if event.get('isBase64Encoded'):
            import base64
            raw_body = base64.b64decode(raw_body).decode('utf-8')

        params = parse_qs(raw_body)
        command = params.get('command', [''])[0]
        text = params.get('text', [''])[0].strip()

        if command == '/digest' and text in ('generate', ''):
            result_body = json.loads(
                lambda_handler({'source': 'slack'}, context)['body']
            )
            msg = (
                f"✅ Digest posted! run_id=`{result_body.get('run_id', '?')}` "
                f"({result_body.get('teams_processed', '?')} teams)"
                if result_body.get('success')
                else f"❌ Digest failed: {result_body.get('error', 'unknown error')}"
            )
            return {
                'statusCode': 200,
                'body': json.dumps({'response_type': 'in_channel', 'text': msg}),
                'headers': {'Content-Type': 'application/json'},
            }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'response_type': 'ephemeral',
                    'text': "Usage: `/digest generate`",
                }),
                'headers': {'Content-Type': 'application/json'},
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'response_type': 'ephemeral', 'text': f"Error: {str(e)}"}),
            'headers': {'Content-Type': 'application/json'},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lambda Function URL handler  (Auth: NONE  →  public demo endpoint)
# ─────────────────────────────────────────────────────────────────────────────
_CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
}


def _post_slack_message(token: str, channel: str, text: str, blocks: list = None) -> str:
    """Fire-and-forget Slack message. Returns the message ts or empty string."""
    import urllib.request
    payload = {'channel': channel, 'text': text}
    if blocks:
        payload['blocks'] = blocks
    req = urllib.request.Request(
        'https://slack.com/api/chat.postMessage',
        data=json.dumps(payload).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get('ts', '')
    except Exception as e:
        print(f"Slack notification error: {e}")
        return ''


# Realistic team conversations — posted server-side so judges need zero config
_DEMO_MESSAGES = {
    'mechanical': [
        "Morning everyone! Servo calibration data from yesterday's run is in the shared drive. Numbers look solid — within 0.3% of target. ✅",
        "🚨 *Blocker*: Still waiting on RF module datasheets from the supplier. ETA 2 days. This will delay antenna placement finalization.",
        "Gyro mount bracket tolerance issue from last week is fully resolved — new parts arrived and fit within spec.",
        "*Action item*: Update BOM with revised bracket part numbers by EOD.",
        "Design review meeting tomorrow at 10:00. Please have your subsystem status updated in Confluence before then.",
    ],
    'electrical': [
        "⚠️ *Potential blocker*: 5V rail on board rev3 showing a 0.2V drop under 2A load. Flagging before the integration test this afternoon.",
        "Battery thermal tests complete. Peak temp 42°C under 2C discharge — well within the 60°C limit. 🔋",
        "*Decision*: Apply firmware calibration offset to compensate voltage drop rather than a hardware fix. Will revisit in rev4.",
        "*Action item*: Document voltage compensation values and add to hardware spec sheet by EOD.",
        "Sharing an older RF datasheet from a similar module — should unblock initial layout planning.",
    ],
    'software': [
        "API endpoint for sensor telemetry deployed to staging. Can electrical team test against the latest firmware build?",
        "CI pipeline was failing on nav module tests — dependency version conflict. Fixed now. Tests are green ✅",
        "*Pushing nav module v2.1 to staging.* Includes the ADC calibration hook for electrical's voltage compensation.",
        "Full system integration test scheduled for tomorrow 15:00. All interfaces need to be locked by 12:00. 🚀",
        "Telemetry dashboard update is live — everyone can now see live sensor feeds.",
    ],
}

_CHANNEL_ENV_MAP = {
    'mechanical': 'CHANNEL_MECHANICAL',
    'electrical':  'CHANNEL_ELECTRICAL',
    'software':    'CHANNEL_SOFTWARE',
}


def _channel_already_seeded(token: str, channel_id: str, within_seconds: int = 3600) -> bool:
    """
    Return True if the channel already contains the demo messages seeded
    within the last `within_seconds` (default 1 hour).  This prevents
    posting the same hardcoded messages again on repeated demo triggers,
    which would cause the AI to see duplicate content.
    """
    import time as _time
    cutoff = _time.time() - within_seconds
    req = urllib.request.Request(
        f'https://slack.com/api/conversations.history?channel={channel_id}&limit=20',
        headers={'Authorization': f'Bearer {token}'},
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        messages = data.get('messages', [])
        # Look for any recent message whose text matches one of the demo strings
        for msg in messages:
            if float(msg.get('ts', '0')) < cutoff:
                continue
            for team_msgs in _DEMO_MESSAGES.values():
                if msg.get('text', '') in team_msgs:
                    return True
    except Exception as e:
        print(f"Seed check error: {e}")
    return False


def _seed_demo_messages(token: str) -> int:
    """
    Post demo messages to all team channels. Returns total posted count.

    Skips a channel if it already has fresh demo messages (seeded within the
    last hour) to avoid accumulating duplicate content across repeated demo
    triggers.
    """
    import time as _time
    posted = 0
    for team, env_key in _CHANNEL_ENV_MAP.items():
        channel_id = os.getenv(env_key, '')
        if not channel_id:
            print(f"Seed: skipping {team} — {env_key} not set")
            continue
        if _channel_already_seeded(token, channel_id):
            print(f"Seed: {team} already has fresh demo messages, skipping re-seed")
            continue
        for text in _DEMO_MESSAGES[team]:
            payload = json.dumps({
                'channel': channel_id,
                'text': text,
                'unfurl_links': False,
            }).encode()
            req = urllib.request.Request(
                'https://slack.com/api/chat.postMessage',
                data=payload,
                headers={'Authorization': f'Bearer {token}',
                         'Content-Type': 'application/json'},
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if data.get('ok'):
                        posted += 1
                    else:
                        print(f"Seed warning ({team}): {data.get('error')}")
            except Exception as e:
                print(f"Seed error ({team}): {e}")
            _time.sleep(1.1)   # Slack tier-1 rate limit
    print(f"Seeded {posted} messages across {len(_CHANNEL_ENV_MAP)} channels")
    return posted


def function_url_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for Lambda Function URL (unauthenticated public endpoint).

    This is the judge-facing demo trigger. Curl command:
        curl -X POST https://<id>.lambda-url.<region>.on.aws/

    Flow:
      1. Return CORS preflight immediately for OPTIONS.
      2. For POST:
         a. Seed team channels with realistic demo messages (server-side).
         b. Post "⚙️ Analyzing..." to the demo Slack channel immediately.
         c. Run the full digest pipeline (30–90 s).
         d. The pipeline posts the AI digest to Slack automatically.
         e. Return a summary JSON to curl.

    Optional JSON body params:
        { "demo_channel": "C...", "preview": true, "seed": false }
    """
    method = event.get('requestContext', {}).get('http', {}).get('method', 'POST').upper()

    # ── CORS preflight ────────────────────────────────────────────────────────
    if method == 'OPTIONS':
        return {'statusCode': 204, 'headers': _CORS_HEADERS, 'body': ''}

    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': _CORS_HEADERS,
            'body': json.dumps({'error': 'Method not allowed. Use POST.'}),
        }

    triggered_at = datetime.now()
    run_id = triggered_at.strftime("%Y%m%d_%H%M%S")

    # ── Parse optional body ───────────────────────────────────────────────────
    raw_body = event.get('body', '') or ''
    if event.get('isBase64Encoded'):
        import base64
        raw_body = base64.b64decode(raw_body).decode('utf-8')
    try:
        body_params = json.loads(raw_body) if raw_body.strip() else {}
    except json.JSONDecodeError:
        body_params = {}

    preview_mode = body_params.get('preview', False)
    # seed=true (default) posts demo messages before running the pipeline
    do_seed = body_params.get('seed', True)

    # ── Resolve demo channel ──────────────────────────────────────────────────
    slack_token = os.getenv('SLACK_BOT_TOKEN', '')
    # DEMO_CHANNEL env var → fallback to CHANNEL_DIGEST
    demo_channel = (
        body_params.get('demo_channel')
        or os.getenv('DEMO_CHANNEL')
        or os.getenv('CHANNEL_DIGEST', '')
    )

    # ── Step 1: Seed team channels with demo conversations ───────────────────
    if do_seed and slack_token:
        print(f"[{run_id}] Seeding team channels with demo messages...")
        _seed_demo_messages(slack_token)

    # ── Step 2: Immediate "thinking" acknowledgement in Slack ─────────────────
    print(f"[{run_id}] Posting acknowledgement to {demo_channel}...")
    ack_blocks = [
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': (
                    f"*⚙️ ThreadBrief is on it!*\n"
                    f"Demo triggered at `{triggered_at.strftime('%H:%M:%S UTC')}` "
                    f"(run `{run_id}`).\n"
                    f"Team channels seeded ✅ — running AI analysis via Amazon Bedrock… "
                    f"your digest will appear here in ~60 seconds."
                ),
            },
        },
        {'type': 'divider'},
    ]
    ack_ts = _post_slack_message(slack_token, demo_channel, '⚙️ ThreadBrief is analyzing…', ack_blocks)

    # ── Step 2: Run the full pipeline ─────────────────────────────────────────
    try:
        os.environ.setdefault('LLM_PROVIDER', 'bedrock')
        # Demo messages are posted by the bot token, so Slack marks them with
        # bot_id.  Without this override the noise filter drops every seeded
        # message and the pipeline sees 0 messages → "no digest".
        os.environ['FILTER_BOTS'] = 'false'

        config = DigestConfig.from_env()

        # Override digest channel to demo channel so output lands there too
        if demo_channel:
            config.digest_channel = demo_channel

        pipeline = asyncio.run(_run_pipeline(config, preview_mode, run_id))

        output   = pipeline['output']
        team_analyses = pipeline['team_analyses']
        elapsed  = (datetime.now() - triggered_at).total_seconds()

        # Optional S3 store (reuse main handler logic with no DynamoDB dependency)
        s3_bucket   = os.getenv('DIGEST_S3_BUCKET')
        s3_location = None
        if s3_bucket:
            digest_data = {
                'run_id': run_id,
                'timestamp': triggered_at.isoformat(),
                'total_events': output.global_digest.total_events,
                'teams': list(team_analyses.keys()),
            }
            s3_key = f"digests/{run_id}.json"
            _get_s3().put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(digest_data, indent=2, default=str),
                ContentType='application/json',
            )
            s3_location = f"s3://{s3_bucket}/{s3_key}"

        print(f"[{run_id}] Pipeline complete in {elapsed:.1f}s")

        return {
            'statusCode': 200,
            'headers': _CORS_HEADERS,
            'body': json.dumps({
                'success': True,
                'message': 'Digest posted to Slack! Check the demo channel.',
                'run_id': run_id,
                'elapsed_seconds': round(elapsed, 1),
                'total_events': output.global_digest.total_events,
                'teams_processed': len(team_analyses),
                'slack_channel': demo_channel,
                's3_location': s3_location,
            }),
        }

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"[{run_id}] Pipeline error: {err}")

        # Post failure notice to Slack so the channel isn't left hanging
        if slack_token and demo_channel:
            _post_slack_message(
                slack_token, demo_channel,
                f"❌ ThreadBrief run `{run_id}` failed: `{type(e).__name__}: {e}`"
            )

        return {
            'statusCode': 500,
            'headers': _CORS_HEADERS,
            'body': json.dumps({
                'success': False,
                'run_id': run_id,
                'error': str(e),
                'error_type': type(e).__name__,
            }),
        }
