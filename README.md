# Telegram AI Subscription Bot

Self-hostable Telegram AI bot starter with subscription periods (1/7/30/90 days), daily free quota, usage tracking, provider selection, document extraction, manual payment approval, admin commands, and a generic HMAC-signed payment callback.

## Important
This is a functional starter, **not a production-certified payment/SaaS platform**. The generic callback is an integration contract. Before taking real payments, implement the payment provider's official signature, amount/currency/order reconciliation, and final-status verification. Hosted mode is a marker, not a complete multi-tenant SaaS implementation.

## Setup
1. Copy `.env.example` to `.env`; configure `TELEGRAM_BOT_TOKEN`, numeric `ADMIN_IDS`, and at least one AI provider key.
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python -m app`

Docker: `cp .env.example .env`, edit `.env`, then `docker compose up --build -d`.

## Commands
User: `/start`, `/help`, `/plans`, `/buy day|week|month|quarter`, `/status`, `/provider openai|gemini`, `/model <name>`, `/analyze`.
Admin: `/admin_stats`, `/admin_users`, `/pending`, `/approve <payment_id>`, `/reject <payment_id> [reason]`, `/grant <telegram_user_id> <days>`, `/setquota <telegram_user_id> <daily_count>`.

Manual payment flow: user creates a request with `/buy`; operator verifies transfer externally and approves with `/approve ID`.

## AI providers
OpenAI-compatible chat completions and Google Gemini are implemented. Set `OPENAI_BASE_URL` for a compatible endpoint. Provider keys are server-side environment variables; users cannot supply arbitrary URLs. Voice transcription, audio generation, Claude/Mistral-specific adapters, and Telegram Business integration are not implemented in this starter.

## Generic payment callback
Run `python -m app.webhook`. Endpoint: `POST /payment/callback`, header `X-Signature: sha256=<HMAC-SHA256 of exact raw JSON body>`. Body:
`{"event_id":"unique-event","telegram_user_id":123456789,"plan":"month","status":"paid"}`
Set a long random `PAYMENT_WEBHOOK_SECRET`. This only authenticates the integration caller; it does not independently verify a gateway transaction. Add the provider's official verification and reconcile amount, currency, merchant reference, and final status before live use.

## Security
Never commit `.env`; rotate exposed credentials. Use HTTPS/reverse proxy, backups, spending limits, monitoring, and sandbox payment tests. Never collect Telegram login codes, 2FA passwords, or personal-account session files.
