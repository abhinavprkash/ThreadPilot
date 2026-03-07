# ThreadPilot AWS Architecture

## Overview

ThreadPilot leverages AWS Generative AI and infrastructure services to automatically analyze team communication patterns and generate intelligent daily digests.

## Why AI is Required

**Problem:** Engineering teams generate hundreds of messages daily across multiple channels. Critical information (blockers, decisions, dependencies) gets buried in noise.

**AI Solution:**
- **Natural Language Understanding** - Extract structured insights from unstructured Slack conversations
- **Contextual Analysis** - Identify cross-team dependencies and blockers
- **Intelligent Summarization** - Generate personalized digests based on role and team
- **Pattern Recognition** - Learn from feedback to improve relevance over time

**Without AI:** Manual digest creation would require 2-3 hours daily. AI reduces this to seconds while improving quality.

## How AWS Services Are Used

### 1. Amazon Bedrock (Generative AI)
**Model:** Claude 3 Sonnet (Anthropic)

**Purpose:**
- **Team Analysis Agent** - Extracts updates, blockers, decisions from messages
- **Dependency Detection** - Identifies cross-team coordination needs
- **Summarization** - Generates concise, actionable summaries
- **Personalization** - Ranks content by user role (Lead, IC, Executive)

**Why Bedrock:**
- Managed foundation models (no model hosting)
- Enterprise security & compliance
- Pay-per-use pricing
- Multiple model options (Claude, Titan, Jurassic)

### 2. AWS Lambda
**Functions:**
- `digest-generator` - Main orchestration (invoked by cron/API)
- `slack-webhook-handler` - Process Slack events
- `dm-sender` - Batch DM distribution with rate limiting

**Benefits:**
- Serverless (no server management)
- Auto-scaling
- Pay-per-execution
- Event-driven architecture

### 3. Amazon DynamoDB
**Tables:**
- `digest-state` - Last run timestamps, incremental fetching
- `digest-memory` - Persistent blockers, decisions, dependencies
- `user-feedback` - Reaction tracking for personalization
- `user-personas` - Role-based preferences

**Benefits:**
- Fully managed NoSQL
- Single-digit millisecond latency
- Auto-scaling capacity
- Global tables support

### 4. Amazon S3
**Buckets:**
- `threadpilot-digests` - JSON outputs, audit logs
- `threadpilot-web` - Static web UI (Amplify frontend)
- `threadpilot-assets` - Templates, configurations

**Benefits:**
- Durable storage (99.999999999%)
- Versioning for audit trails
- Lifecycle policies for cost optimization
- CloudFront integration

### 5. Amazon API Gateway
**Endpoints:**
- `POST /generate-digest` - Trigger digest generation
- `POST /slack/events` - Slack webhook receiver
- `GET /status/{run_id}` - Check digest status
- `POST /feedback` - Submit user feedback

**Benefits:**
- RESTful API with authentication
- Request/response transformation
- Rate limiting & throttling
- CloudWatch logging

### 6. AWS Amplify
**Purpose:** Judge demo interface

**Features:**
- One-click Slack app installation
- Real-time digest preview
- Configuration UI (channels, users)
- Live status dashboard

### 7. Amazon EventBridge
**Rules:**
- `daily-digest-cron` - Scheduled daily at 9 AM
- `feedback-processor` - Process reactions every hour

**Benefits:**
- Serverless event routing
- Cron-like scheduling
- Event filtering & transformation

### 8. AWS Secrets Manager
**Secrets:**
- Slack bot tokens
- API keys
- Database credentials

**Benefits:**
- Automatic rotation
- Fine-grained access control
- Audit logging

## What Value the AI Layer Adds

### 1. **Time Savings**
- **Manual Approach:** 2-3 hours/day to read messages and create digest
- **AI Approach:** 30 seconds automated analysis
- **ROI:** 99% time reduction, ~40 hours/month saved per team

### 2. **Information Quality**
- AI extracts structured data (blockers, dependencies) that humans might miss
- Cross-team dependency detection prevents integration delays
- Confidence scoring highlights items needing verification

### 3. **Personalization**
- AI learns from user feedback (reactions) to improve relevance
- Role-based ranking (Leads see blockers, ICs see action items)
- Reduces information overload (only show what matters)

### 4. **Proactive Insights**
- Detects emerging patterns (repeated blockers, decision delays)
- Identifies coordination gaps between teams
- Flags high-severity issues automatically

### 5. **Continuous Improvement**
- Feedback loop learns user preferences
- Adapts to team communication style
- Improves prompt quality over time

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     AWS Cloud                           │
│                                                          │
│  ┌──────────────┐      ┌─────────────────┐             │
│  │ EventBridge  │─────→│  Lambda         │             │
│  │ (Cron)       │      │  digest-        │             │
│  └──────────────┘      │  generator      │             │
│                        └────────┬────────┘             │
│  ┌──────────────┐              │                       │
│  │ API Gateway  │              │                       │
│  │ /generate    │──────────────┘                       │
│  └───────┬──────┘              │                       │
│          │                     │                       │
│  ┌───────▼──────────────────────▼──────────┐          │
│  │        Amazon Bedrock                   │          │
│  │        (Claude 3 Sonnet)                │          │
│  │  - Team Analysis Agent                  │          │
│  │  - Dependency Detection                 │          │
│  │  - Summarization                        │          │
│  └───────┬─────────────────────────────────┘          │
│          │                                             │
│  ┌───────▼──────┐   ┌──────────────┐   ┌───────────┐ │
│  │  DynamoDB    │   │     S3       │   │  Secrets  │ │
│  │  - State     │   │  - Digests   │   │  Manager  │ │
│  │  - Memory    │   │  - Logs      │   │  - Tokens │ │
│  │  - Feedback  │   │  - UI        │   └───────────┘ │
│  └──────────────┘   └──────────────┘                  │
│                                                         │
│  ┌──────────────┐          ┌─────────────┐            │
│  │   Amplify    │          │   Lambda    │            │
│  │   (Web UI)   │          │   dm-sender │            │
│  └──────────────┘          └─────────────┘            │
└─────────────────────────────────────────────────────────┘
        │                              │
        │                              │
        ▼                              ▼
   Judge Demo                      Slack DMs
   Interface                       (Users)
```

## Cost Estimation (Monthly)

**Assumption:** 10 teams, 100 users, 1 digest/day

| Service | Usage | Cost |
|---------|-------|------|
| Bedrock (Claude 3 Sonnet) | 1M tokens/day | $15 |
| Lambda | 30 invocations/day | $1 |
| DynamoDB | 10GB, 1K reads/writes | $3 |
| S3 | 5GB storage, 10K requests | $0.50 |
| API Gateway | 1K requests/day | $1 |
| **Total** | | **~$20/month** |

**Hackathon Demo:** Free tier covers all usage!

## Security & Compliance

- **Encryption:** All data encrypted at rest (S3, DynamoDB) and in transit (TLS)
- **IAM Roles:** Least privilege access for Lambda functions
- **Secrets:** Managed by Secrets Manager, automatic rotation
- **Audit Logs:** CloudWatch Logs + CloudTrail for all API calls
- **VPC:** Optional VPC deployment for enhanced isolation

## Scalability

- **Lambda:** Auto-scales to 1000 concurrent executions
- **DynamoDB:** Auto-scaling read/write capacity
- **S3:** Unlimited storage
- **Bedrock:** Managed scaling, no provisioning needed
- **Result:** Supports 10K+ users without infrastructure changes

## Monitoring & Observability

- **CloudWatch Dashboards:** Real-time metrics (latency, errors, costs)
- **X-Ray Tracing:** End-to-end request tracing
- **CloudWatch Alarms:** Alert on failures, high latency
- **Custom Metrics:** Digest quality scores, user engagement

## Next Steps for Production

1. **Multi-region deployment** - High availability
2. **CI/CD pipeline** - CodePipeline + CodeBuild
3. **Blue/green deployments** - Zero-downtime updates
4. **Load testing** - Verify 10K+ user scale
5. **Cost optimization** - Reserved capacity, S3 lifecycle policies
