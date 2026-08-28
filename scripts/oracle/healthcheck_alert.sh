#!/usr/bin/env bash
# scripts/oracle/healthcheck_alert.sh — M0 Oracle migration readiness.
#
# Low-overhead observability for a single VM: HTTP health, container
# status, disk space — alerts via a direct Telegram Bot API call (the same
# channel the bot already uses for owner alerts), NOT by calling into
# app.py/telegram_adapter.py. This is a standalone ops script; it does not
# change any production messaging code path.
#
# Not installed as a cron/systemd timer by this commit — no VM exists yet.
# Intended M1+ install (documented here, not executed):
#   */5 * * * * BOSS_ENV_FILE=/etc/boss-bot/backend.env /opt/boss-bot/scripts/oracle/healthcheck_alert.sh
#
# Requires (from BOSS_ENV_FILE, sourced by the caller before running this):
#   TELEGRAM_TOKEN, ADMIN_CHAT_ID (or ELIYAHU_CHAT_ID) — alert recipient
#   BOSS_HEALTH_URL — e.g. https://bot.example.com/health
#
# Exit code reflects overall health (0 = OK) so this also composes with any
# external uptime monitor, not just its own Telegram alert.

set -uo pipefail  # not -e: we want to run every check even if one fails

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.oracle.yml}"
DISK_WARN_PCT="${DISK_WARN_PCT:-85}"
FAILURES=()

# 1. HTTP health
if [ -n "${BOSS_HEALTH_URL:-}" ]; then
  if ! curl -fsS --max-time 10 "$BOSS_HEALTH_URL" > /dev/null; then
    FAILURES+=("HTTP /health unreachable or non-2xx at ${BOSS_HEALTH_URL}")
  fi
else
  FAILURES+=("BOSS_HEALTH_URL not set — HTTP health not checked")
fi

# 2. Container status
UNHEALTHY="$(docker compose -f "$COMPOSE_FILE" ps --format '{{.Name}} {{.State}} {{.Health}}' 2>/dev/null \
  | awk '$2 != "running" || ($3 != "" && $3 != "healthy") {print}')"
if [ -n "$UNHEALTHY" ]; then
  FAILURES+=("Non-running/unhealthy containers: ${UNHEALTHY}")
fi

# 3. Disk space
DISK_PCT="$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')"
if [ -n "$DISK_PCT" ] && [ "$DISK_PCT" -ge "$DISK_WARN_PCT" ]; then
  FAILURES+=("Disk usage ${DISK_PCT}% >= warning threshold ${DISK_WARN_PCT}%")
fi

if [ "${#FAILURES[@]}" -eq 0 ]; then
  echo "[healthcheck_alert] OK"
  exit 0
fi

MSG="⚠️ BOSS Oracle healthcheck failed:"
for f in "${FAILURES[@]}"; do
  MSG="${MSG}
- ${f}"
done
echo "[healthcheck_alert] $MSG" >&2

CHAT_ID="${ADMIN_CHAT_ID:-${ELIYAHU_CHAT_ID:-}}"
if [ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "$CHAT_ID" ]; then
  curl -fsS --max-time 10 \
    "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${MSG}" > /dev/null \
    || echo "[healthcheck_alert] WARNING — alert delivery itself failed" >&2
else
  echo "[healthcheck_alert] WARNING — TELEGRAM_TOKEN/ADMIN_CHAT_ID not set, no alert sent" >&2
fi

exit 1
