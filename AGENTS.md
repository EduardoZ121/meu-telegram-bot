# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a Python Telegram bot ("Remake Pixel Bot") for AI image generation with Stripe payments. It consists of a single Python process (`start.py`) that runs an embedded Flask web server plus the Telegram bot polling loop.

### Running the application

```bash
# Without API keys (Flask health server only, bot.py will error but Flask stays up):
python3 start.py

# With API keys (full bot):
TELEGRAM_TOKEN=<token> REPLICATE_API_TOKEN=<token> OPENAI_API_KEY=<key> STRIPE_SECRET_KEY=<key> python3 start.py
```

The Flask server listens on `PORT` (default 10000). The `/` endpoint returns `{"status": "ok"}`.

### Key gotchas

- **httpx compatibility**: `openai==1.54.4` requires `httpx<0.28` because httpx 0.28+ removed the `proxies` kwarg. The update script pins `httpx<0.28` after installing from `requirements.txt`.
- **Port conflict**: Both `start.py` and `bot.py` try to start Flask on the same port. In practice `start.py`'s Flask wins (starts first), and `bot.py`'s Flask fails silently with "Address already in use" — this is by design.
- **Graceful degradation**: `start.py` catches all exceptions from `bot.py` and keeps Flask running. Missing env vars cause bot.py to fail but the health endpoint stays alive.
- **No formal test suite or linter config**: Use `python3 -m py_compile <file>` for syntax validation.

### Required environment variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_TOKEN` | Telegram Bot API token (required for bot) |
| `REPLICATE_API_TOKEN` | Replicate API key (image generation) |
| `OPENAI_API_KEY` | OpenAI API key (prompt enhancement + gpt-image-1) |
| `STRIPE_SECRET_KEY` | Stripe secret key (payments) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (optional for dev) |
| `PORT` | Flask port (default: 10000) |

### Lint / syntax check

```bash
python3 -m py_compile bot.py && python3 -m py_compile bot2.py && python3 -m py_compile start.py
```
