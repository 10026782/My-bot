#!/usr/bin/env bash
# scripts/oracle/backup_postgres.sh — M0 Oracle migration readiness.
#
# Runs pg_dump INSIDE the postgres container (docker compose exec) so the
# host needs no postgres-client tools installed. Requires no VM/DNS/secret
# beyond what docker-compose.oracle.yml already needs to be running.
#
# Usage:
#   BOSS_ENV_FILE=/etc/boss-bot/backend.env ./scripts/oracle/backup_postgres.sh
#
# Off-VM destination (REQUIRED before this can replace a real backup plan —
# see docs/operations/ORACLE_MIGRATION_M0.md "unresolved infrastructure
# decision"): set BACKUP_DEST_CMD to a command that receives the local
# dump path as $1, e.g.:
#   BACKUP_DEST_CMD='rclone copy {} remote:boss-bot-backups/'
#   BACKUP_DEST_CMD='aws s3 cp {} s3://my-bucket/boss-bot-backups/'
# {} is replaced with the dump's path. Left unset, this script keeps the
# dump LOCAL ONLY and prints a loud warning — a local-only dump on the same
# VM is not a real backup (single failure domain, see the audit's Phase 13).

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.oracle.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/boss-bot/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
POSTGRES_DB="${POSTGRES_DB:-boss_bot}"
POSTGRES_USER="${POSTGRES_USER:-boss_bot}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_NAME="boss_bot_${TIMESTAMP}.sql.gz"
DUMP_PATH="${BACKUP_DIR}/${DUMP_NAME}"

mkdir -p "$BACKUP_DIR"

echo "[backup_postgres] dumping ${POSTGRES_DB} -> ${DUMP_PATH}" >&2
if ! docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$DUMP_PATH"; then
  echo "[backup_postgres] FAILED — pg_dump did not complete. Removing partial file." >&2
  rm -f "$DUMP_PATH"
  exit 1
fi

if [ ! -s "$DUMP_PATH" ]; then
  echo "[backup_postgres] FAILED — dump file is empty." >&2
  rm -f "$DUMP_PATH"
  exit 1
fi

echo "[backup_postgres] local dump OK: ${DUMP_PATH} ($(du -h "$DUMP_PATH" | cut -f1))" >&2

if [ -n "${BACKUP_DEST_CMD:-}" ]; then
  CMD="${BACKUP_DEST_CMD//\{\}/$DUMP_PATH}"
  echo "[backup_postgres] shipping off-VM: $CMD" >&2
  if ! eval "$CMD"; then
    echo "[backup_postgres] FAILED — off-VM copy did not complete. Local dump retained at ${DUMP_PATH}." >&2
    exit 1
  fi
else
  echo "[backup_postgres] WARNING — BACKUP_DEST_CMD is not set. This dump is LOCAL ONLY on the same VM as the database it backs up. This is NOT a real backup (see Phase 13 of the migration audit) until an off-VM destination is configured." >&2
fi

echo "[backup_postgres] pruning local dumps older than ${RETENTION_DAYS} days" >&2
find "$BACKUP_DIR" -name 'boss_bot_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete

echo "[backup_postgres] done" >&2
