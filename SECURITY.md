# Security Guidelines

## API Keys and Secrets

### Storage
- **ALL API keys and secrets MUST be stored in `.env` file only**
- Never commit `.env` file to git (already in `.gitignore`)
- Use `.env.example` as a template (no real keys)

### Current Secrets
The following secrets are required in `.env`:
- `GOOGLE_API_KEY` - Google AI Studio API key
- `SLACK_BOT_TOKEN` - Slack bot OAuth token (starts with `xoxb-`)
- `SLACK_APP_TOKEN` - Slack app-level token (starts with `xapp-`)
- `SLACK_SIGNING_SECRET` - Slack signing secret
- `LANGCHAIN_API_KEY` - (Optional) LangSmith API key

### Getting API Keys

#### Google AI Studio API Key
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key (starts with `AIzaSy...`)
5. Add to `.env`: `GOOGLE_API_KEY=AIzaSy...`

#### Slack Tokens
1. Go to https://api.slack.com/apps
2. Select your app
3. Get tokens from "OAuth & Permissions" and "Basic Information"

### Checking for Leaks

Before committing code, verify no secrets are exposed:

```bash
# Check git status (should NOT show .env)
git status

# Search for potential API key patterns
grep -r "AIzaSy" . --exclude-dir=.git --exclude="*.md" --exclude=".env"
grep -r "xoxb-" . --exclude-dir=.git --exclude="*.md" --exclude=".env"

# Verify .env is in .gitignore
grep "^\.env$" .gitignore
```

### If API Key is Leaked

1. **Immediately revoke** the leaked key:
   - Google AI Studio: https://aistudio.google.com/app/apikey (delete the key)
   - Slack: Regenerate tokens in your app settings

2. **Generate new key** and update `.env`

3. **Remove from git history** (if committed):
   ```bash
   # Use git filter-branch or BFG Repo-Cleaner
   # Then force push (destructive operation)
   ```

### Best Practices

✅ DO:
- Store all secrets in `.env`
- Use `.env.example` for documentation
- Add `.env` to `.gitignore`
- Rotate keys periodically
- Use different keys for dev/prod

❌ DON'T:
- Commit `.env` file
- Put keys in code comments
- Put keys in TODO, README, or other docs
- Share keys via chat/email (use secure channels)
- Use production keys for testing

## Current Security Status

✅ `.env` file in `.gitignore`
✅ `.env.example` contains placeholders only
✅ No API keys in tracked files (TODO.txt, README.md, etc.)
✅ All secrets properly isolated

## Verification

Run this command to verify no secrets in tracked files:
```bash
git ls-files | xargs grep -l "AIzaSy\|xoxb-\|xapp-" || echo "✅ No secrets found in tracked files"
```
