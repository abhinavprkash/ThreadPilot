# AWS Deployment Guide for ThreadPilot

## Prerequisites

1. **AWS Account** with Bedrock access
2. **AWS CLI** installed and configured
3. **AWS SAM CLI** installed (`pip install aws-sam-cli`)
4. **Slack App** created with bot token

## Quick Start (15 minutes)

### Step 1: Enable Amazon Bedrock Access

1. Go to AWS Console → Amazon Bedrock
2. Navigate to "Model access"
3. Click "Request model access"
4. Select **"Anthropic Claude 3 Sonnet"**
5. Submit request (usually approved instantly)

### Step 2: Configure AWS Credentials

```bash
# Configure AWS CLI
aws configure

# Enter your credentials:
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region: us-east-1
# Default output format: json
```

### Step 3: Get Slack Credentials

From your Slack App settings:
- Bot  OAuth Token: `Settings → Install App` (starts with `xoxb-`)
- Signing Secret: `Settings → Basic Information`

### Step 4: Deploy to AWS

```bash
cd ThreadPilot

# Install dependencies
pip install -r aws/requirements-lambda.txt -t .

# Build and deploy using SAM
sam build --template-file aws/template.yaml
sam deploy --guided

# You'll be prompted for:
# - Stack Name: threadpilot
# - AWS Region: us-east-1
# - SlackBotToken: xoxb-your-token
# - SlackSigningSecret: your-secret
# - BedrockModelId: anthropic.claude-3-sonnet-20240229-v1:0
# - BedrockRegion: us-east-1
```

### Step 5: Update Slack App

1. Copy the `SlackWebhookUrl` from deployment outputs
2. Go to Slack App → **Slash Commands**
3. Create command: `/digest`
4. Request URL: `<SlackWebhookUrl>` (from outputs)
5. Save changes

### Step 6: Test!

In Slack:
```
/digest generate
```

The bot will:
1. Fetch messages from your channels
2. Analyze with Claude 3 (Bedrock)
3. Post digest to Slack
4. Store results in S3

## Architecture Deployed

```
EventBridge (cron) ──┐
                     │
API Gateway ─────────┼──→ Lambda (digest-generator)
                     │         │
Slack (/digest) ─────┘         ├──→ Bedrock (Claude 3)
                               ├──→ S3 (digests)
                               ├──→ DynamoDB (state)
                               └──→ Slack (posts)
```

## Configuration

### Environment Variables (Lambda)

Set in AWS Lambda console or SAM template:

```bash
# AWS Services
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1
DIGEST_S3_BUCKET=threadpilot-digests-123456789
STATE_TABLE_NAME=threadpilot-state

# Slack (stored in Secrets Manager)
SLACK_SECRETS_ARN=arn:aws:secretsmanager:...

# Channels (update these!)
CHANNEL_MECHANICAL=C0A5HE4MY3U
CHANNEL_ELECTRICAL=C0A5M2C539A
CHANNEL_SOFTWARE=C0A5FD731PY
CHANNEL_DIGEST=C0A5M2D6284
```

### Scheduled Triggers

Default: Daily at 9 AM UTC

To change schedule:
1. AWS Console → EventBridge → Rules
2. Find `threadpilot-DailySchedule`
3. Edit cron expression: `cron(0 9 * * ? *)`

Examples:
- `cron(0 9 * * ? *)` - Daily at 9 AM UTC
- `cron(0 */6 * * ? *)` - Every 6 hours
- `cron(0 9 * * MON-FRI *)` - Weekdays at 9 AM

## Manual Testing

### Via API Gateway

```bash
# Get API endpoint from deployment outputs
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name threadpilot \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

# Trigger digest generation
curl -X POST $API_ENDPOINT/generate-digest \
  -H "Content-Type: application/json" \
  -d '{}'

# Check with preview mode (doesn't post to Slack)
curl -X POST $API_ENDPOINT/generate-digest \
  -H "Content-Type: application/json" \
  -d '{"preview_mode": true}'
```

### Via AWS CLI

```bash
# Invoke Lambda directly
aws lambda invoke \
  --function-name threadpilot-digest-generator \
  --payload '{"source":"manual"}' \
  response.json

cat response.json
```

### Via Slack

```
/digest generate
```

## Viewing Results

### CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/threadpilot-digest-generator --follow
```

### S3 Digests

```bash
# List all digests
aws s3 ls s3://threadpilot-digests-YOUR-ACCOUNT-ID/digests/

# Download latest
aws s3 cp s3://threadpilot-digests-YOUR-ACCOUNT-ID/digests/latest.json .
```

### DynamoDB State

```bash
# Get latest run info
aws dynamodb get-item \
  --table-name threadpilot-state \
  --key '{"id": {"S": "latest"}}'
```

## Cost Estimation

For 10 teams, 100 users, 1 digest/day:

| Service | Monthly Cost |
|---------|--------------|
| Bedrock (Claude 3) | $15 |
| Lambda | $1 |
| DynamoDB | $3 |
| S3 | $0.50 |
| API Gateway | $1 |
| **Total** | **~$20/month** |

**Free Tier Coverage:** First year free for most services!

## Troubleshooting

### "Access Denied" for Bedrock

**Solution:** Enable model access in Bedrock console
```bash
aws bedrock list-foundation-models --region us-east-1
```

### Lambda Timeout

**Solution:** Increase timeout in template.yaml
```yaml
Globals:
  Function:
    Timeout: 900  # 15 minutes
```

### Slack Command Not Working

**Solution:** Check webhook URL in Slack app matches API Gateway endpoint

### No Messages Fetched

**Solution:**
1. Invite bot to channels: `/invite @ThreadPilot`
2. Verify channel IDs in Lambda environment variables

## Updating Deployment

```bash
# Make code changes, then:
sam build
sam deploy  # Uses previous parameters
```

## Clean Up (Delete Everything)

```bash
# Delete the stack
sam delete --stack-name threadpilot

# Note: S3 bucket must be empty first
aws s3 rm s3://threadpilot-digests-YOUR-ACCOUNT-ID --recursive
```

## For Judges: Demo Setup

We've deployed ThreadPilot to AWS for your evaluation:

1. **Install Slack App:** [Install Link]
2. **Invite to Channel:** `/invite @ThreadPilot`
3. **Run Digest:** `/digest generate`
4. **View Output:** Check #digest channel

**Architecture Demo:**
- Real-time generation using AWS Lambda + Bedrock
- Results stored in S3 for audit
- Fully serverless, auto-scaling

**API Endpoint:** `https://your-api.execute-api.us-east-1.amazonaws.com/prod`

## Next Steps

1. ✅ Deploy to AWS
2. ✅ Test with real Slack data
3. Configure personalization features
4. Set up monitoring dashboards
5. Enable multi-team support
