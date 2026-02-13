# Issue: LangChain Google GenAI Package Incompatible with Google AI Studio API Keys

**Status: ✅ RESOLVED (Feb 13, 2026)**

## Problem Summary

The digest pipeline agents were configured to use the `langchain-google-genai` package for LLM integration. This package is designed to work with Google Cloud Platform's Vertex AI service and requires Application Default Credentials (ADC) for authentication. It was incompatible with free Google AI Studio API keys, causing all agents to fall back to mock mode and preventing real AI analysis of Slack messages.

## Solution Implemented (Jan 18, 2026)

Replaced `langchain-google-genai` with direct `google-genai` SDK integration.

## Technical Details

### Root Cause

The `langchain-google-genai` package authenticates through Google Cloud's credential chain:
- Expects ADC (Application Default Credentials)
- Requires a GCP project with billing enabled
- Does not support direct API key authentication

Google AI Studio provides free API keys through a different authentication mechanism that `langchain-google-genai` does not support.

### Affected Components

1. `src/daily_digest/agents/base.py` - BaseAgent class initialization
2. `src/daily_digest/simulation/evaluator.py` - DigestEvaluator LLM calls
3. All agent implementations inheriting from BaseAgent

### Observed Behavior

```
Failed to initialize LLM, falling back to mock mode:
Your default credentials were not found. To set up Application Default Credentials...
```

All agents returned hardcoded mock responses instead of performing actual analysis:
- TeamAnalyzerAgent produced fake updates, blockers, and decisions
- DependencyLinker returned empty dependency lists
- No real insight extraction from synthetic conversation data

### Impact

- Complete pipeline executed successfully but produced meaningless output
- Synthetic data generation worked correctly using `google-genai` package
- Testing and validation impossible due to mock responses
- Production deployment blocked

## Solution Implemented

Replaced `langchain-google-genai` with direct `google-genai` SDK integration:

### Changes Made

1. **Removed Dependencies**
   - `langchain` (0.3.3)
   - `langchain-google-genai` (2.0.0)

2. **Updated BaseAgent Class**
   - Replaced `ChatGoogleGenerativeAI` with `genai.Client`
   - Implemented direct API calls using `client.models.generate_content()`
   - Added JSON response MIME type specification
   - Maintained same prompt structure and error handling

3. **Updated DigestEvaluator**
   - Replaced LangChain message chain with direct API calls
   - Simplified authentication to single API key

### Code Changes

**Before:**
```python
from langchain_google_genai import ChatGoogleGenerativeAI
self.llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=self.temperature)
```

**After:**
```python
from google import genai
api_key = os.getenv("GOOGLE_API_KEY")
self.client = genai.Client(api_key=api_key)
```

### Benefits

- Works with free Google AI Studio API keys
- Simpler authentication (single environment variable)
- Consistent with existing synthetic data generator implementation
- No GCP project or billing setup required
- Direct control over API request parameters

## Additional Fix Required (Feb 13, 2026)

After the Jan 18 migration, discovered the `--mock` flag was still forcing agents into mock mode:

### Problem
- `--mock` flag controlled BOTH Slack client AND LLM agents
- When testing with mock Slack data, agents were also mocked
- Real Gemini analysis wasn't happening even with API key configured

### Solution
Updated [src/daily_digest/main.py](src/daily_digest/main.py#L80) line 80:
```python
# OLD: orchestrator = DigestOrchestrator(config=config, mock_mode=mock)
# NEW: orchestrator = DigestOrchestrator(config=config, mock_mode=False)
```

Now `--mock` only mocks the Slack client, allowing real AI analysis of fixture data.

### Model Configuration
Also updated model name format in `.env`:
- Model names require `models/` prefix for v1beta API
- Working model: `models/gemini-2.5-flash`
- Invalid: `gemini-1.0-pro` (404 error)
- Valid: `models/gemini-2.5-flash`, `models/gemini-2.0-flash`

## Verification Steps

1. Obtain Google AI Studio API key from https://aistudio.google.com/app/apikey
2. Set `GOOGLE_API_KEY=your_key` in `.env` file
3. Set `CHAT_MODEL=models/gemini-2.5-flash` in `.env` file
4. Run digest pipeline: `poetry run python -m daily_digest.main --mock --preview`
5. Verify agents produce real analysis (9+ events, not 3-4 mock items)
6. Check logs show "HTTP 200 OK" from Gemini API
7. Agent durations should be 15-20 seconds (real API calls, not 0ms)

## Verification Results

✅ Tested Feb 13, 2026:
- Extracted 9 events from conversations
- Found 1 cross-team dependency
- Extracted 9 action items
- Generated detailed digest with real insights
- Agent durations: ~18 seconds (real API calls)

## Alternative Considered

**Option: Set up Google Cloud credentials**
- Requires GCP project creation
- Requires billing account (even for free tier)
- More complex credential management
- Unnecessary overhead for development and testing

**Decision:** Direct `google-genai` SDK is simpler and sufficient for project requirements.

## Related Files

- `pyproject.toml` - Dependency management
- `src/daily_digest/agents/base.py` - Agent base class
- `src/daily_digest/main.py` - Main entry point (mock_mode fix)
- `src/daily_digest/simulation/evaluator.py` - Evaluation system
- `.env` - Environment configuration (NOT tracked in git)

## Commit Reference

Commit: 81985aa
Branch: ritvik_branchmain/fix-gemini-api
