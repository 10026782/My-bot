#!/usr/bin/env bash
# scripts/oracle/restore_postgres.sh — M0 Oracle migration readiness.
#
# Restores a backup produced by backup_postgres.sh INTO the running
# postgres container. Destructive (drops and recreates the target
# database) — requires an explicit --yes flag, refuses to run otherwise.
#
# Usage:
#   ./scripts/oracle/restore_postgres.sh /var/backups/boss-bot/postgres/boss_bot_20260901T030000Z.sql.gz --yes

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.oracle.yml}"
POSTGRES_DB="${POSTGRES_DB:-boss_bot}"
POSTGRES_USER="${POSTGRES_USER:-boss_bot}"

DUMP_PATH="${1:-}"
CONFIRM="${2:-}"

if [ -z "$DUMP_PATH" ] || [ ! -f "$DUMP_PATH" ]; then
  echo "usage: $0 <path-to-dump.sql.gz> --yes" >&2
  exit 1
fi

if [ "$CONFIRM" != "--yes" ]; then
  echo "[restore_postgres] REFUSING to run without --yes — this DROPS and recreates '${POSTGRES_DB}'." >&2
  echo "[restore_postgres] Re-run as: $0 ${DUMP_PATH} --yes" >&2
  exit 1
fi

echo "[restore_postgres] restoring ${DUMP_PATH} into ${POSTGRES_DB}" >&2

if ! gunzip -c "$DUMP_PATH" | docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" --set ON_ERROR_STOP=on; then
  echo "[restore_postgres] FAILED — restore did not complete cleanly. Database may be partially restored; verify manually before resuming traffic." >&2
  exit 1
fi

echo "[restore_postgres] done — verify application-level sanity (e.g. run_migrations()/schema checks) before resuming traffic." >&2
