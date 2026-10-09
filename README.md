# All_GPTbot — upgraded self-hosted package

A self-hosted Telegram AI subscription bot with OpenAI-compatible and Gemini providers, daily free quota, user-selected provider/model, document extraction, manual payment review, an owner web panel, and an Ubuntu/Debian installer.

## One-command install/update

Upload the contents of this project to the **root** of the public GitHub repository `modasrdorkhane11251-alt/All_GPTbot`, including `install.sh`. Then run on an interactive Ubuntu/Debian SSH session:

```bash
curl -fsSL https://raw.githubusercontent.com/modasrdorkhane11251-alt/All_GPTbot/main/install.sh | sudo bash
```

The installer downloads the current repository, asks for missing Telegram token, admin ID(s), provider key(s), and panel password, installs dependencies, creates/enables two systemd services, and checks that they start. If the `main` branch is not available, it tries `master`.

### What installation does and does not do

- Bot service: `all-gptbot.service`
- Web admin service: `all-gptbot-panel.service`, bound only to `127.0.0.1:8091`
- Config: `/opt/all-gptbot/.env` (preserved on updates)
- SQLite database: `/opt/all-gptbot/data/bot.sqlite3`
- Backups: `/opt/all-gptbot/backups/`
- Updates back up the current source and database before replacing source files.
- Does not edit `/opt/modasr-arz`, existing Nginx sites, or Cloudflare configuration.
- Does not automatically expose the panel publicly. Configure a **separate hostname** and an HTTPS Nginx reverse proxy to `127.0.0.1:8091`. The panel's authentication cookie is secure-only, so use HTTPS.

Check services and logs:

```bash
systemctl status all-gptbot all-gptbot-panel
journalctl -u all-gptbot -n 100 --no-pager
journalctl -u all-gptbot-panel -n 100 --no-pager
```

## Web owner panel

The panel provides summary statistics, recent users, manual payment approval/rejection, user quota adjustments, subscription extension, and price/currency editing. Set `ADMIN_PANEL_PASSWORD` and `ADMIN_PANEL_SECRET` in `.env`; the installer prompts for a strong password and generates a secret. Keep the panel private behind HTTPS.

## Telegram commands

User: `/start`, `/help`, `/plans`, `/buy day|week|month|quarter`, `/status`, `/provider openai|gemini`, `/model <name>`, `/analyze`.

Admin: `/admin_stats`, `/admin_users`, `/pending`, `/approve <payment_id>`, `/reject <payment_id> [reason]`, `/grant <telegram_user_id> <days>`, `/setquota <telegram_user_id> <daily_count>`.

## Payments: important limitation

The current payment flow is **manual bank-transfer review**. The included HMAC callback is an integration contract only; it is not a real payment gateway and must not be treated as proof that money was received. No live Zarinpal, IDPay, Zibal, or other gateway is claimed to be implemented in this package. Before accepting live online payments, implement and test the selected provider's official create-payment and server-side verification APIs, checking merchant/order reference, amount, currency, and final paid status. Never activate subscriptions solely because a browser was redirected to a success URL.

## AI providers

Set `OPENAI_API_KEY` or `GEMINI_API_KEY` in `.env`. Gemini API keys are sent using the `x-goog-api-key` header, not embedded in request URLs. API errors are intentionally summarized without logging credentials.

## Local development/tests

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m app
python -m app.admin_panel
```

For local panel development, remember that the production session cookie is `Secure` and therefore expects HTTPS.

## Security

Never commit `.env`, database files, API keys, or bot tokens. If a token/key was exposed, rotate it. Use HTTPS, regular backups, provider spending limits, and sandbox payment tests.
