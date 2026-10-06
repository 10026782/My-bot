#!/usr/bin/env bash
# scripts/neon/pg_transfer.sh — Neon migration M0 readiness.
#
# Logical dump / restore / row-count verification between two PostgreSQL
# endpoints (current Render/Oracle PG -> Neon, or Neon -> off-platform backup).
# Needs only pg_dump / pg_restore / psql on PATH — no docker, no VM.
# URLs are read from ENVIRONMENT VARIABLES, never argv (argv shows up in `ps`).
#
#   SOURCE_DATABASE_URL   endpoint to read from (dump / counts / verify)
#   TARGET_DATABASE_URL   endpoint to write to  (restore / verify)
#
# Use a DIRECT (non-"-pooler") Neon endpoint for dump/restore.
#
# Usage:
#   SOURCE_DATABASE_URL=... ./scripts/neon/pg_transfer.sh dump
#   TARGET_DATABASE_URL=... ./scripts/neon/pg_transfer.sh restore <dump-file> --yes
#   SOURCE_DATABASE_URL=... TARGET_DATABASE_URL=... ./scripts/neon/pg_transfer.sh verify
#   SOURCE_DATABASE_URL=... ./scripts/neon/pg_transfer.sh counts SOURCE_DATABASE_URL
#
# Backup use (Neon -> off-platform copy; free-plan PITR is short, so this is the
# real backup): run `dump` with SOURCE_DATABASE_URL=<neon direct url> and set
# BACKUP_DEST_CMD='rclone copy {} remote:boss-bot-backups/' ({} = dump path).
# Left unset the dump stays LOCAL ONLY and a loud warning is printed.
#
# `restore` is destructive (pg_restore --clean --if-exists) and requires --yes.
# It REFUSES to run if TARGET_DATABASE_URL equals SOURCE_DATABASE_URL.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./pg_dumps}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

die() { echo "[pg_transfer] $*" >&2; exit 1; }

need_env() { [ -n "${!1:-}" ] || die "environment variable $1 is not set"; }

need_tools() {
  for t in "$@"; do command -v "$t" >/dev/null 2>&1 || die "required tool not found on PATH: $t"; done
}

# Exact per-table row counts (public schema, base tables), "table<TAB>count", sorted.
counts_for() {
  local url="${!1}"
  psql "$url" -X -At -F $'\t' -v ON_ERROR_STOP=1 -c "
    SELECT table_name,
           (xpath('/row/c/text()',
                  query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text::bigint
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY 1;"
}

cmd_dump() {
  need_tools pg_dump gzip
  need_env SOURCE_DATABASE_URL
  mkdir -p "$BACKUP_DIR"
  local ts dump
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  dump="${BACKUP_DIR}/boss_bot_${ts}.dump"
  echo "[pg_transfer] dumping source -> ${dump}" >&2
  if ! pg_dump "$SOURCE_DATABASE_URL" --format=custom --no-owner --no-privileges --file="$dump"; then
    rm -f "$dump"
    die "FAILED — pg_dump did not complete (partial file removed). Check the client/server major version: pg_dump must be >= the server."
  fi
  [ -s "$dump" ] || { rm -f "$dump"; die "FAILED — dump file is empty."; }
  pg_restore --list "$dump" >/dev/null || die "FAILED — dump is not readable by pg_restore (kept at ${dump} for inspection)."
  echo "[pg_transfer] dump OK: ${dump} ($(du -h "$dump" | cut -f1))" >&2

  if [ -n "${BACKUP_DEST_CMD:-}" ]; then
    local cmd="${BACKUP_DEST_CMD//\{\}/$dump}"
    echo "[pg_transfer] shipping off-platform: ${cmd}" >&2
    eval "$cmd" || die "FAILED — off-platform copy did not complete. Local dump retained at ${dump}."
  else
    echo "[pg_transfer] WARNING — BACKUP_DEST_CMD is not set: this dump is LOCAL ONLY. Not a real backup until an off-platform destination is configured." >&2
  fi

  find "$BACKUP_DIR" -name 'boss_bot_*.dump' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
  echo "$dump"
}

cmd_restore() {
  need_tools pg_restore
  need_env TARGET_DATABASE_URL
  local dump="${1:-}" confirm="${2:-}"
  [ -n "$dump" ] && [ -f "$dump" ] || die "usage: $0 restore <dump-file> --yes"
  [ "$confirm" = "--yes" ] || die "REFUSING without --yes — this DROPS and recreates every object in the target. Re-run: $0 restore ${dump} --yes"
  if [ -n "${SOURCE_DATABASE_URL:-}" ] && [ "$SOURCE_DATABASE_URL" = "$TARGET_DATABASE_URL" ]; then
    die "REFUSING — TARGET_DATABASE_URL equals SOURCE_DATABASE_URL; a restore must never run onto its own source."
  fi
  echo "[pg_transfer] restoring ${dump} into target (single transaction, stops at first error)" >&2
  pg_restore --dbname="$TARGET_DATABASE_URL" --clean --if-exists --no-owner --no-privileges \
    --exit-on-error --single-transaction "$dump" \
    || die "FAILED — restore aborted; --single-transaction means the target was rolled back, not half-restored."
  echo "[pg_transfer] restore done — now run: $0 verify" >&2
}

cmd_counts() {
  need_tools psql
  local var="${1:-}"
  [ -n "$var" ] || die "usage: $0 counts <ENV_VAR_NAME>"
  need_env "$var"
  counts_for "$var"
}

cmd_verify() {
  need_tools psql diff
  need_env SOURCE_DATABASE_URL
  need_env TARGET_DATABASE_URL
  local a b
  a="$(counts_for SOURCE_DATABASE_URL)" || die "could not count source tables"
  b="$(counts_for TARGET_DATABASE_URL)" || die "could not count target tables"
  if [ "$a" = "$b" ]; then
    echo "[pg_transfer] VERIFY OK — identical row counts in $(printf '%s\n' "$a" | grep -c .) table(s):" >&2
    printf '%s\n' "$a" >&2
  else
    echo "[pg_transfer] VERIFY FAILED — row counts differ (< source / > target):" >&2
    diff <(printf '%s\n' "$a") <(printf '%s\n' "$b") >&2 || true
    exit 1
  fi
}

case "${1:-}" in
  dump)    shift; cmd_dump "$@" ;;
  restore) shift; cmd_restore "$@" ;;
  counts)  shift; cmd_counts "$@" ;;
  verify)  shift; cmd_verify "$@" ;;
  *) die "usage: $0 {dump | restore <dump-file> --yes | counts <ENV_VAR_NAME> | verify}" ;;
esac
