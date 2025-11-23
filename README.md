# Crypto AI Twitter Bot

Autonomous AI-driven Twitter (X) bot for posting project updates and replying to mentions, with **production-grade safety controls**.

## Key Features

### 🤖 AI-Powered Generation
- OpenAI integration for tweet & reply generation
- Context-aware prompts preventing financial advice
- Concise, factual language

### 🛡️ Production Safety (Default: ON)
- **Rate Limiting**: Automatic exponential backoff on 429 errors
- **Multi-Layer Checks**: Profanity, financial advice, toxicity detection
- **Manual Review Queue**: Flagged tweets queued for human approval
- **Audit Trail**: SQLite database logs all drafts, decisions, posts
- **DRY-RUN Mode**: Enabled by default (no tweets posted until disabled)

### 🔐 Security
- Secrets management support (AWS Secrets Manager, GCP, Vault, .env)
- No credentials in git
- Encrypted credential handling

### 📊 Compliance
- Full audit trail exportable as JSON
- Tracks all generated content and decisions
- CLI tool for manual review

## Quick Start

### 1. Configure Credentials
```bash
cp .env.example .env
# Edit .env with your Twitter API & OpenAI keys
nano .env
```

### 2. Install & Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Runs in DRY_RUN mode by default (safe!)
python3 -m app.main
```

### 3. Review & Approve Tweets
```bash
# List pending reviews
python3 -m app.review_cli list

# Approve a draft
python3 -m app.review_cli approve 1

# View statistics
python3 -m app.review_cli stats

# Export audit log
python3 -m app.review_cli export
```

## Safety Features Explained

### Rate Limiting
- Detects 429 (rate limit) responses
- Retries with exponential backoff (1s → 5min max)
- Respects `X-Rate-Limit-Reset` header
- Queues for retry on persistent failures

### Content Safety Checks
1. **Length**: Max 280 characters
2. **Profanity**: Keyword-based filter
3. **Financial Advice**: "buy now", "guaranteed returns", etc.
4. **URLs**: Flags suspicious shorteners (bit.ly, tinyurl)
5. **Toxicity**: Detects serious accusations without context

### Manual Review Queue
- Failed safety checks → automatic review queue
- Rate limit failures → high-priority queue
- API errors → logged with error message
- CLI tool to approve/reject drafts

### Audit Trail
```bash
# Database schema:
# - drafts: All generated tweets with safety results
# - safety_checks: Individual check results
# - review_queue: Pending human reviews
# - posts: Successfully posted tweets
```

## Configuration

### .env Variables
```bash
# Twitter API (required)
X_BEARER_TOKEN=...
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_SECRET=...

# OpenAI (required)
OPENAI_API_KEY=...

# Bot Config
BOT_HANDLE=your_handle
PROJECT_KEYWORDS=Solstice,solsticefi,flares

# Safety (defaults recommended)
DRY_RUN=true           # Set to false ONLY after testing
LOG_LEVEL=INFO
POST_INTERVAL_HOURS=3
MENTION_POLL_MINUTES=1
```

### Production Secrets Management
```bash
# AWS Secrets Manager
export USE_AWS_SECRETS=true
export AWS_REGION=us-east-1

# GCP Secret Manager (optional)
export USE_GCP_SECRETS=true
export GCP_PROJECT_ID=your-project

# Or use Vault (optional)
export VAULT_ADDR=https://vault.example.com
export VAULT_TOKEN=...
```

See `SECRETS_MANAGEMENT.md` for detailed setup.

## Production Checklist

- [ ] Test in DRY_RUN mode first
- [ ] Review pending tweets daily (`python3 -m app.review_cli list`)
- [ ] Export audit logs weekly
- [ ] Monitor error logs for rate limits
- [ ] Use secrets manager instead of .env
- [ ] Set `DRY_RUN=false` only after manual testing
- [ ] Add account disclaimer (automated bot)
- [ ] Monitor for content policy violations

## Deployment

### Docker
```bash
docker build -t crypto-ai-bot:latest .
docker run --env-file .env -v $(pwd)/bot_audit.db:/app/bot_audit.db \
  crypto-ai-bot:latest
```

### Kubernetes Secret
```bash
kubectl create secret generic twitter-bot --from-file=.env
kubectl apply -f bot-deployment.yaml
```

### Systemd Service
See `systemd/crypto-ai-bot.service` for Linux deployment.

## File Structure

```
app/
├── main.py              # Entry point with validation
├── config.py            # Config + secrets management
├── llm_provider.py      # OpenAI integration
├── rate_limit.py        # Rate limiting wrapper
├── safety_enhanced.py   # Multi-layer safety checks
├── audit_db.py          # SQLite audit trail
├── poster_safe.py       # Safe posting pipeline
├── scheduler.py         # Job scheduling
├── review_cli.py        # Manual review CLI
└── logger.py            # Logging

docs/
├── SECRETS_MANAGEMENT.md
├── ...
```

## Troubleshooting

### "Missing required secrets"
- Verify all 6 API keys in .env
- Check AWS region if using Secrets Manager
- Ensure OPENAI_API_KEY is set

### Rate Limit Errors (429)
- Bot automatically retries with backoff
- Check `bot_audit.db` for high-priority queue
- Reduce POST_INTERVAL_HOURS if consistent

### Nothing Being Posted
- Check DRY_RUN setting (default: true)
- Review pending queue: `python3 -m app.review_cli list`
- Check logs for safety violations

### Database Locked
- Only one bot instance should run at a time
- Check for orphaned processes: `ps aux | grep app.main`

## Advanced

### Custom Safety Rules
Edit `app/safety_enhanced.py`:
- Add keywords to PROFANITY_KEYWORDS, FINANCIAL_ADVICE_KEYWORDS
- Modify check functions for custom logic
- Add new safety checks to SAFETY_CHECKS pipeline

### Replace LLM Provider
Edit `app/llm_provider.py`:
- Swap OpenAI for Claude, Llama, etc.
- Implement custom generation logic
- Add fallback providers

### Extend Audit Trail
`app/audit_db.py` is fully customizable:
- Add new tables for custom tracking
- Implement webhooks on draft approval
- Export to external compliance systems

## License

MIT

## Support

- Report issues on GitHub
- Check `bot_audit.db` for detailed logs
- Export audit log for debugging: `python3 -m app.review_cli export`
