#!/usr/bin/env bash
set -Eeuo pipefail

REPO="modasrdorkhane11251-alt/All_GPTbot"
BRANCH="${BRANCH:-main}"
BASE="/opt/all-gptbot"
SRC="$BASE/source"
ENV_FILE="$BASE/.env"
DATA="$BASE/data"
BACKUP="$BASE/backups"
VENV="$BASE/.venv"

# curl | sudo bash has a pipe as stdin; read interactive answers from the terminal.
if [[ ! -r /dev/tty ]]; then
  echo "Run this command from an interactive SSH terminal." >&2
  exit 1
fi
ask() {
  local prompt="$1" var="$2" default="${3:-}" secret="${4:-false}" value=""
  if [[ -n "$default" ]]; then prompt="$prompt [$default]"; fi
  if [[ "$secret" == true ]]; then read -r -s -p "$prompt: " value </dev/tty; echo >/dev/tty
  else read -r -p "$prompt: " value </dev/tty; fi
  value="${value:-$default}"
  printf -v "$var" '%s' "$value"
}
set_env_if_missing() {
  local key="$1" value="$2"
  if ! grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}
get_env() { sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | tail -n1; }

if [[ $EUID -ne 0 ]]; then echo "Run as root: sudo bash install.sh" >&2; exit 1; fi

command -v apt-get >/dev/null || { echo "This installer currently supports Ubuntu/Debian." >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl ca-certificates unzip openssl rsync

mkdir -p "$BASE" "$DATA" "$BACKUP"
chmod 750 "$BASE" "$DATA" "$BACKUP"

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
URL="https://codeload.github.com/${REPO}/zip/refs/heads/${BRANCH}"
if ! curl -fL --retry 2 --connect-timeout 15 "$URL" -o "$TMP/repo.zip"; then
  if [[ "$BRANCH" == main ]]; then
    echo "Could not download branch main. Trying master..."
    curl -fL --retry 2 --connect-timeout 15 "https://codeload.github.com/${REPO}/zip/refs/heads/master" -o "$TMP/repo.zip"
  else exit 1; fi
fi
unzip -q "$TMP/repo.zip" -d "$TMP/unpacked"
PROJECT="$(find "$TMP/unpacked" -mindepth 1 -maxdepth 1 -type d | head -n1)"
[[ -f "$PROJECT/requirements.txt" && -f "$PROJECT/app/__main__.py" ]] || { echo "Downloaded repository does not look like All_GPTbot." >&2; exit 1; }

# Back up current source and database before replacing files; never replace .env.
STAMP="$(date +%Y%m%d-%H%M%S)"
if [[ -d "$SRC" ]]; then tar -czf "$BACKUP/source-$STAMP.tar.gz" -C "$BASE" source; fi
if [[ -f "$DATA/bot.sqlite3" ]]; then cp -a "$DATA/bot.sqlite3" "$BACKUP/bot-$STAMP.sqlite3"; fi
mkdir -p "$SRC"
rsync -a --delete --exclude='.env' --exclude='data/' --exclude='.venv/' "$PROJECT/" "$SRC/"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$SRC/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Initial setup: enter bot and AI credentials. Existing .env, if present, is preserved."
fi

TOKEN="$(get_env TELEGRAM_BOT_TOKEN)"
if [[ -z "$TOKEN" || "$TOKEN" == replace_me ]]; then
  ask "Telegram bot token from @BotFather" TOKEN "" true
  [[ -n "$TOKEN" ]] || { echo "Token is required." >&2; exit 1; }
  set_env_if_missing TELEGRAM_BOT_TOKEN "$TOKEN"
  if [[ "$(get_env TELEGRAM_BOT_TOKEN)" == replace_me || -z "$(get_env TELEGRAM_BOT_TOKEN)" ]]; then
    sed -i '/^TELEGRAM_BOT_TOKEN=/d' "$ENV_FILE"; printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TOKEN" >> "$ENV_FILE"
  fi
fi
ADMINS="$(get_env ADMIN_IDS)"
if [[ -z "$ADMINS" || "$ADMINS" == 123456789 ]]; then
  ask "Telegram admin ID(s), comma-separated" ADMINS
  [[ -n "$ADMINS" ]] || { echo "Admin ID is required." >&2; exit 1; }
  sed -i '/^ADMIN_IDS=/d' "$ENV_FILE"; printf 'ADMIN_IDS=%s\n' "$ADMINS" >> "$ENV_FILE"
fi

# Ask for provider keys only when not already configured.
if [[ -z "$(get_env OPENAI_API_KEY)" ]]; then
  ask "OpenAI API key (Enter to skip)" OPENAI_KEY "" true
  if [[ -n "$OPENAI_KEY" ]]; then sed -i '/^OPENAI_API_KEY=/d' "$ENV_FILE"; printf 'OPENAI_API_KEY=%s\n' "$OPENAI_KEY" >> "$ENV_FILE"; fi
fi
if [[ -z "$(get_env GEMINI_API_KEY)" ]]; then
  ask "Gemini API key (Enter to skip)" GEMINI_KEY "" true
  if [[ -n "$GEMINI_KEY" ]]; then sed -i '/^GEMINI_API_KEY=/d' "$ENV_FILE"; printf 'GEMINI_API_KEY=%s\n' "$GEMINI_KEY" >> "$ENV_FILE"; fi
fi
if [[ -z "$(get_env OPENAI_API_KEY)" && -z "$(get_env GEMINI_API_KEY)" ]]; then
  echo "Warning: no AI provider key is configured yet; the bot can start but AI answers will fail." >&2
fi

PANEL_PASSWORD="$(get_env ADMIN_PANEL_PASSWORD)"
if [[ -z "$PANEL_PASSWORD" || "$PANEL_PASSWORD" == change_this_to_a_long_random_password ]]; then
  ask "Strong password for web admin panel" PANEL_PASSWORD "" true
  [[ ${#PANEL_PASSWORD} -ge 12 ]] || { echo "Panel password must be at least 12 characters." >&2; exit 1; }
  sed -i '/^ADMIN_PANEL_PASSWORD=/d' "$ENV_FILE"; printf 'ADMIN_PANEL_PASSWORD=%s\n' "$PANEL_PASSWORD" >> "$ENV_FILE"
fi
PANEL_SECRET="$(get_env ADMIN_PANEL_SECRET)"
if [[ -z "$PANEL_SECRET" || "$PANEL_SECRET" == replace_with_a_long_random_secret ]]; then
  PANEL_SECRET="$(openssl rand -hex 32)"
  sed -i '/^ADMIN_PANEL_SECRET=/d' "$ENV_FILE"; printf 'ADMIN_PANEL_SECRET=%s\n' "$PANEL_SECRET" >> "$ENV_FILE"
fi

# Make paths deterministic regardless of current working directory.
for pair in \
  "DATABASE_PATH=$DATA/bot.sqlite3" \
  "ENV_FILE_PATH=$ENV_FILE" \
  "ADMIN_PANEL_HOST=127.0.0.1" \
  "ADMIN_PANEL_PORT=8091"; do
  key="${pair%%=*}"; val="${pair#*=}"
  if grep -qE "^${key}=" "$ENV_FILE"; then sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"; else printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"; fi
done
chmod 600 "$ENV_FILE"

python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r "$SRC/requirements.txt"
mkdir -p "$DATA"
cd "$SRC"
"$VENV/bin/python" - <<'PY'
from app.db import init_db
init_db()
print('Database initialized.')
PY

cat > /etc/systemd/system/all-gptbot.service <<EOF
[Unit]
Description=All GPTbot Telegram AI bot
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$SRC
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python -m app
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$BASE
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/all-gptbot-panel.service <<EOF
[Unit]
Description=All GPTbot web admin panel
After=network-online.target all-gptbot.service
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$SRC
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python -m app.admin_panel
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$BASE
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable all-gptbot.service all-gptbot-panel.service
systemctl restart all-gptbot.service all-gptbot-panel.service
sleep 2
if ! systemctl is-active --quiet all-gptbot.service; then
  echo "Bot service did not start. Logs:"; journalctl -u all-gptbot.service -n 60 --no-pager; exit 1
fi
if ! systemctl is-active --quiet all-gptbot-panel.service; then
  echo "Panel service did not start. Logs:"; journalctl -u all-gptbot-panel.service -n 60 --no-pager; exit 1
fi

cat <<EOF

Install/update finished.
Bot service:   systemctl status all-gptbot
Panel service: systemctl status all-gptbot-panel
Panel local:   http://127.0.0.1:8091 (keep private; expose only through HTTPS reverse proxy)
Environment:   $ENV_FILE
Database:      $DATA/bot.sqlite3
Backups:       $BACKUP

IMPORTANT: Web panel login cookie requires HTTPS. For a public panel, create a separate DNS record and an Nginx HTTPS virtual host proxying to 127.0.0.1:8091.
This installer does not modify existing Nginx/Cloudflare configuration or the /opt/modasr-arz project.
EOF
