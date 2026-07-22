#!/usr/bin/env python3
"""
render_log_export.py — read-only Render log exporter + local search tool.

Design source: docs/architecture/turn-coordinator/PHASE_2_SHADOW_PLANNING_GATE.md §6.

Usage:
    python scripts/render_log_export.py check-env
    python scripts/render_log_export.py export --service-id srv-xxxxxxxx
    python scripts/render_log_export.py export --service-id srv-xxxxxxxx --dry-run
    python scripts/render_log_export.py search "BUG-130" --since 2026-07-01
    python scripts/render_log_export.py search "ERROR" --field message

Never reads, prints, logs, or writes the API key value anywhere — only
whether the configured environment variable is set. All network calls are
GET-only against Render's logs endpoint; nothing in this script can deploy,
restart, or write to the Render service, and nothing here touches Airtable
or the live bot process.

UNVERIFIED AGAINST THE LIVE RENDER API: research for the Planning Gate above
hit HTTP 403 on every attempt to fetch Render's current API docs from that
session. The request parameters and response-shape assumptions below
(_fetch_log_page, _parse_log_response) are best-available knowledge, not
confirmed live. Run `export --dry-run` first; if a real `export` run fails
or returns an unexpected shape, the error message names the exact function
to fix — the rest of the script (checkpointing, JSONL writing, search) does
not depend on those assumptions being exactly right.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

import requests

RENDER_API_BASE = "https://api.render.com/v1"
DEFAULT_API_KEY_ENV = "RENDER_API_KEY"
DEFAULT_EXPORT_DIR = Path("render_logs")
CHECKPOINT_NAME = ".checkpoint.json"
PAGE_LIMIT = 100
REQUEST_TIMEOUT_S = 30


# ── credential handling — never touches the value except in the Authorization header ──

def _read_api_key(env_var: str) -> str:
    import os
    value = os.environ.get(env_var)
    if not value:
        raise SystemExit(
            f"Environment variable {env_var} is not set. This script never reads "
            f"credentials from anywhere else (no config file, no CLI flag) — set it "
            f"in your local shell before running `export`."
        )
    return value


def check_env(env_var: str) -> None:
    import os
    print(f"{env_var}: {'SET' if os.environ.get(env_var) else 'NOT SET'}")


# ── checkpoint ──

@dataclass
class Checkpoint:
    last_exported_timestamp: Optional[str]
    last_run_at: Optional[str]
    service_id: Optional[str]

    @classmethod
    def load(cls, path: Path) -> "Checkpoint":
        if not path.exists():
            return cls(last_exported_timestamp=None, last_run_at=None, service_id=None)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            last_exported_timestamp=data.get("last_exported_timestamp"),
            last_run_at=data.get("last_run_at"),
            service_id=data.get("service_id"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "last_exported_timestamp": self.last_exported_timestamp,
            "last_run_at": self.last_run_at,
            "service_id": self.service_id,
        }, indent=2), encoding="utf-8")


# ── Render API access — the one place to fix if the live shape differs ──

def _fetch_log_page(
    api_key: str,
    service_id: str,
    start_time: str,
    end_time: str,
    limit: int = PAGE_LIMIT,
) -> dict:
    """
    Best-available-knowledge request shape for GET {RENDER_API_BASE}/logs.
    If this returns a non-2xx status or a body that _parse_log_response()
    can't recognize, verify the current shape at https://api-docs.render.com
    and update this function and _parse_log_response() together — nothing
    else in this script assumes anything about Render's response format.
    """
    resp = requests.get(
        f"{RENDER_API_BASE}/logs",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        params={
            "resource": service_id,
            "startTime": start_time,
            "endTime": end_time,
            "direction": "forward",
            "limit": limit,
        },
        timeout=REQUEST_TIMEOUT_S,
    )
    if not resp.ok:
        raise RuntimeError(
            f"Render logs request failed: HTTP {resp.status_code} — {resp.text[:500]}\n"
            f"If this is 401/403, the API key or its scopes are the likely cause, not this "
            f"script's logic. If this is 404/400, the endpoint path or query parameter names "
            f"in _fetch_log_page() likely no longer match Render's current API — verify at "
            f"https://api-docs.render.com and update this function."
        )
    return resp.json()


def _parse_log_response(payload: dict) -> tuple[list[dict], Optional[str]]:
    """
    Returns (entries, next_start_time_or_None). Tries a few plausible response
    shapes defensively (Render's exact field names were not confirmed live —
    see module docstring) rather than assuming one specific shape silently.
    """
    entries = payload.get("logs") or payload.get("data") or (
        payload if isinstance(payload, list) else None
    )
    if entries is None:
        raise RuntimeError(
            f"Unrecognized Render log response shape — top-level keys: "
            f"{list(payload.keys()) if isinstance(payload, dict) else type(payload)}. "
            f"Update _parse_log_response() to match the actual shape."
        )

    next_cursor = (
        payload.get("nextStartTime")
        or payload.get("nextCursor")
        or payload.get("cursor")
    )
    return entries, next_cursor


def _entry_timestamp(entry: dict) -> Optional[str]:
    return entry.get("timestamp") or entry.get("time") or entry.get("createdAt")


# ── export ──

def export_logs(
    api_key_env: str,
    service_id: str,
    export_dir: Path,
    dry_run: bool,
    catch_up_days: int,
) -> None:
    checkpoint_path = export_dir / CHECKPOINT_NAME
    checkpoint = Checkpoint.load(checkpoint_path)

    now = datetime.now(timezone.utc)
    if checkpoint.last_exported_timestamp:
        start_time = checkpoint.last_exported_timestamp
    else:
        start_time = (now - timedelta(days=catch_up_days)).isoformat()
    end_time = now.isoformat()

    print(f"Export window: {start_time} -> {end_time} (service {service_id})")

    if dry_run:
        print("--dry-run: no network call made, no files written. "
              "Set --dry-run off (omit the flag) once the window above looks right.")
        return

    api_key = _read_api_key(api_key_env)

    written = 0
    latest_timestamp = checkpoint.last_exported_timestamp
    cursor_start = start_time

    while True:
        payload = _fetch_log_page(api_key, service_id, cursor_start, end_time)
        entries, next_cursor = _parse_log_response(payload)
        if not entries:
            break

        by_day: dict[str, list[dict]] = {}
        for entry in entries:
            ts = _entry_timestamp(entry)
            day = (ts or now.isoformat())[:10]
            by_day.setdefault(day, []).append(entry)
            if ts and (latest_timestamp is None or ts > latest_timestamp):
                latest_timestamp = ts

        for day, day_entries in by_day.items():
            export_dir.mkdir(parents=True, exist_ok=True)
            day_file = export_dir / f"{day}.jsonl"
            with day_file.open("a", encoding="utf-8") as f:
                for entry in day_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += len(day_entries)

        if not next_cursor or len(entries) < PAGE_LIMIT:
            break
        cursor_start = next_cursor

    checkpoint.last_exported_timestamp = latest_timestamp
    checkpoint.last_run_at = now.isoformat()
    checkpoint.service_id = service_id
    checkpoint.save(checkpoint_path)

    print(f"Wrote {written} log entries. Checkpoint updated: {checkpoint_path}")


# ── local search over already-exported JSONL — the "identify relevant logs" step ──

def search_logs(
    export_dir: Path,
    pattern: str,
    since: Optional[str],
    until: Optional[str],
    field: Optional[str],
    max_results: int,
) -> Iterator[str]:
    regex = re.compile(pattern)
    files = sorted(export_dir.glob("*.jsonl"))
    count = 0
    for path in files:
        day = path.stem
        if since and day < since:
            continue
        if until and day > until:
            continue
        with path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                haystack = line
                if field:
                    try:
                        entry = json.loads(line)
                        haystack = str(entry.get(field, ""))
                    except json.JSONDecodeError:
                        continue
                if regex.search(haystack):
                    count += 1
                    yield f"{path.name}:{line_no}: {line.rstrip()}"
                    if count >= max_results:
                        return


# ── CLI ──

def main() -> None:
    # Shared as a parent parser (not just top-level args) so --export-dir/
    # --api-key-env work whether they're typed before or after the
    # subcommand name — argparse only accepts parent-parser args before the
    # subcommand otherwise, which is a common gotcha.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--export-dir", default=str(DEFAULT_EXPORT_DIR),
                         help=f"default: {DEFAULT_EXPORT_DIR} (must stay out of git — see .gitignore)")
    common.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV,
                         help=f"name of the environment variable holding the Render API key (default: {DEFAULT_API_KEY_ENV})")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check-env", parents=[common], help="report whether the API key env var is set, without ever printing its value")

    p_export = sub.add_parser("export", parents=[common], help="fetch new log entries since the last checkpoint")
    p_export.add_argument("--service-id", required=True, help="Render service id, e.g. srv-xxxxxxxx (see Planning Gate §13 item 2 — not documented in this repo)")
    p_export.add_argument("--dry-run", action="store_true", help="print the export window and exit, no network call")
    p_export.add_argument("--catch-up-days", type=int, default=1, help="window to use on the very first run (no checkpoint yet)")

    p_search = sub.add_parser("search", parents=[common], help="search already-exported JSONL files locally")
    p_search.add_argument("pattern", help="regex pattern to search for")
    p_search.add_argument("--since", help="YYYY-MM-DD, inclusive")
    p_search.add_argument("--until", help="YYYY-MM-DD, inclusive")
    p_search.add_argument("--field", help="restrict the search to one JSON field instead of the whole raw line")
    p_search.add_argument("--max-results", type=int, default=200)

    args = parser.parse_args()
    export_dir = Path(args.export_dir)

    if args.command == "check-env":
        check_env(args.api_key_env)
    elif args.command == "export":
        export_logs(args.api_key_env, args.service_id, export_dir, args.dry_run, args.catch_up_days)
    elif args.command == "search":
        for line in search_logs(export_dir, args.pattern, args.since, args.until, args.field, args.max_results):
            print(line)


if __name__ == "__main__":
    main()
