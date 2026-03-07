"""
AWS Lambda handler for ThreadPilot digest generation.

This function:
1. Fetches messages from Slack channels
2. Uses Amazon Bedrock (Claude 3) for AI analysis
3. Stores results in DynamoDB and S3
4. Sends digests back to Slack
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any

# Import ThreadPilot modules
from daily_digest.config import DigestConfig
from daily_digest.slack_client import SlackClient
from daily_digest.orchestrator import DigestOrchestrator
from daily_digest.distributor import DigestDistributor

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')


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
        "channels": ["C123", "C456"],  # optional: specific channels
        "preview_mode": false,  # optional: don't post to Slack
    }
    """
    print(f"Received event: {json.dumps(event)}")

    try:
        # Parse event
        source = event.get('source', 'unknown')
        preview_mode = event.get('preview_mode', False)
        channels_override = event.get('channels')

        # Set environment for Bedrock
        os.environ['LLM_PROVIDER'] = 'bedrock'

        # Load configuration
        config = DigestConfig.from_env()
        if channels_override:
            config.channels = {f"team_{i}": ch for i, ch in enumerate(channels_override)}

        # Initialize clients
        slack_client = SlackClient()
        orchestrator = DigestOrchestrator(slack_client, config)
        distributor = DigestDistributor(slack_client, config)

        # Generate digest
        print("Starting digest generation...")
        result = orchestrator.run()

        if not result.get("success"):
            raise Exception(f"Digest generation failed: {result.get('error')}")

        output = result["output"]
        team_analyses = result["team_analyses"]
        run_id = result.get("run_id", datetime.now().strftime("%Y%m%d_%H%M%S"))

        print(f"Digest generated successfully: {run_id}")

        # Store digest in S3
        s3_bucket = os.getenv('DIGEST_S3_BUCKET')
        if s3_bucket:
            digest_data = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "global_digest": {
                    "date": output.global_digest.date,
                    "summary": output.global_digest.summary,
                    "total_messages": output.global_digest.total_messages,
                },
                "team_analyses": {
                    name: {
                        "summary": ta.summary,
                        "blockers": ta.blockers,
                        "decisions": ta.decisions,
                        "action_items": ta.action_items,
                    }
                    for name, ta in team_analyses.items()
                },
            }

            s3_key = f"digests/{run_id}.json"
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(digest_data, indent=2),
                ContentType='application/json',
            )
            print(f"Stored digest in S3: s3://{s3_bucket}/{s3_key}")

        # Store state in DynamoDB
        state_table_name = os.getenv('STATE_TABLE_NAME')
        if state_table_name:
            state_table = dynamodb.Table(state_table_name)
            state_table.put_item(
                Item={
                    'id': 'latest',
                    'run_id': run_id,
                    'timestamp': datetime.now().isoformat(),
                    'message_count': output.global_digest.total_messages,
                    'teams_processed': len(team_analyses),
                }
            )
            print(f"Updated state in DynamoDB: {state_table_name}")

        # Distribute to Slack (unless preview mode)
        if not preview_mode:
            print("Distributing digest to Slack...")
            dist_result = distributor.distribute(
                output=output,
                team_analyses=team_analyses,
                run_id=run_id,
            )
            print(f"Distribution complete: {dist_result['main_post']}")
        else:
            print("Preview mode: skipping Slack distribution")
            dist_result = {"preview": True}

        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'run_id': run_id,
                'message_count': output.global_digest.total_messages,
                'teams_processed': len(team_analyses),
                'distribution': dist_result,
                's3_location': f"s3://{s3_bucket}/{s3_key}" if s3_bucket else None,
            }),
            'headers': {
                'Content-Type': 'application/json',
            }
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
            'headers': {
                'Content-Type': 'application/json',
            }
        }


def slack_webhook_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle Slack webhook events (user commands).

    Slack sends commands like: /digest generate
    """
    print(f"Slack webhook event: {json.dumps(event)}")

    try:
        # Parse Slack command
        body = json.loads(event.get('body', '{}'))
        command = body.get('command', '')
        text = body.get('text', '')
        user_id = body.get('user_id', '')

        if command == '/digest' and text == 'generate':
            # Trigger digest generation
            digest_result = lambda_handler({'source': 'slack'}, context)

            # Return Slack response
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'response_type': 'in_channel',
                    'text': f"✅ Digest generation started! Run ID: {digest_result.get('run_id', 'unknown')}",
                }),
                'headers': {
                    'Content-Type': 'application/json',
                }
            }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'response_type': 'ephemeral',
                    'text': f"Unknown command. Try: `/digest generate`",
                }),
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'response_type': 'ephemeral',
                'text': f"Error: {str(e)}",
            }),
        }
