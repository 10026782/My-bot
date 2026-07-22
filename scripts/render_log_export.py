#!/usr/bin/env python3
"""
render_log_export.py — read-only Render log exporter + local search tool.

Design source: docs/architecture/turn-coordinator/PHASE_2_SHADOW_PLANNING_GATE.md §6.
Automated tests: test_render_log_export.py (run: python3 test_render_log_export.py).

Canonical syntax — global flags always go AFTER the subcommand name. Use
`python3` (not `python`) on every platform this has been run on, including
the owner's Windows machine, where `python3` is what's on PATH:
    python3 scripts/render_log_export.py check-env
    python3 scripts/render_log_export.py export --owner-id <id> --service-id srv-xxxxxxxx --marker "BUG-130" --dry-run
    python3 scripts/render_log_export.py export --owner-id <id> --service-id srv-xxxxxxxx --marker "BUG-130"
    python3 scripts/render_log_export.py search "BUG-130" --since 2026-07-01
    python3 scripts/render_log_export.py search "ERROR" --field message

Transport (`export` only — `search`/`check-env` never touch the network):
`--transport auto` (default) picks `curl` on Windows when `curl.exe` is on
PATH (Python's `requests`/certifi trust store has been observed to fail
TLS verification against api.render.com on at least one Windows machine
with `CERTIFICATE_VERIFY_FAILED`, while curl.exe/Schannel validates the
same certificate successfully), else `requests`. `--transport requests` or
`--transport curl` force one explicitly. Neither transport ever disables
certificate verification — there is no `-k`/`--insecure`/`verify=False`
anywhere in this file, and none is ever added as a fallback on failure.
`--ssl-no-revoke` is accepted only for the Windows curl transport; it maps
to curl's own `--ssl-no-revoke`, which disables the *revocation-status*
check (OCSP/CRL) only — it does not weaken certificate trust-chain
validation, and curl's own docs describe it exactly this way. This mirrors
the flag combination that produced a real, successful, verified probe
against the live API (see PHASE_2_SHADOW_PLANNING_GATE.md §6.3).

There is exactly one supported order. `--export-dir`/`--api-key-env` are
defined only on each subcommand's own parser, not on the top-level parser,
specifically to avoid a real argparse gotcha: when the same option is
defined on both a parent parser and reused via `parents=[...]` on a
subparser, the subparser's own default silently overwrites a value already
set before the subcommand name, even if the user never touched that flag
at the subcommand level. Putting `--export-dir CUSTOM export ...` before
`export` would silently revert to the default — confirmed via a standalone
repro before this file was written this way, not assumed.

Never reads, prints, logs, or writes the API key value anywhere — only
whether the configured environment variable is set (`check-env`). All
network calls are GET-only against Render's official Logs API
(GET /v1/logs); nothing in this script can deploy, restart, or write to
the Render service, and nothing here touches Airtable, app.py, or the live
bot process.

Collection is narrow by default: `export` requires an approved server-side
marker (`--marker`, matched against each fetched entry's message text
before anything is written — see `--allow-full-export` to override) and
defaults to `type=app` (application logs only, not build/deploy logs).
Only a fixed, minimal set of fields is persisted per entry (see
_SHADOW_EVIDENCE_FIELDS) — not the raw Render response verbatim.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
MAX_RETRIES_429 = 5
BACKOFF_BASE_S = 2

# Transport safety invariant, checked by test_render_log_export.py: neither
# transport implementation below may ever construct one of these.
_FORBIDDEN_TLS_BYPASS_FLAGS = ("-k", "--insecure")

# Only these fields are persisted per log entry — a narrow, fixed allowlist,
# not the raw Render response. `id` and `timestamp` are load-bearing for
# idempotency (§ export_logs) and are validated as present before anything
# is written, not merely copied if present.
_SHADOW_EVIDENCE_FIELDS = ("id", "timestamp", "message", "type", "resource")


# ── credential handling — never touches the value except in the Authorization header ──

def _read_api_key(env_var: str) -> str:
    value = os.environ.get(env_var)
    if not value:
        raise SystemExit(
            f"Environment variable {env_var} is not set. This script never reads "
            f"credentials from anywhere else (no config file, no CLI flag) — set it "
            f"in your local shell before running `export`."
        )
    return value


def check_env(env_var: str) -> None:
    print(f"{env_var}: {'SET' if os.environ.get(env_var) else 'NOT SET'}")


# ── checkpoint — one per service, durable after every successfully written page ──

@dataclass
class Checkpoint:
    owner_id: Optional[str]
    service_id: Optional[str]
    last_completed_end_time: Optional[str]
    last_run_at: Optional[str]

    @classmethod
    def load(cls, path: Path) -> "Checkpoint":
        if not path.exists():
            return cls(owner_id=None, service_id=None, last_completed_end_time=None, last_run_at=None)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            owner_id=data.get("owner_id"),
            service_id=data.get("service_id"),
            last_completed_end_time=data.get("last_completed_end_time"),
            last_run_at=data.get("last_run_at"),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "owner_id": self.owner_id,
            "service_id": self.service_id,
            "last_completed_end_time": self.last_completed_end_time,
            "last_run_at": self.last_run_at,
        }, indent=2), encoding="utf-8")


class ServiceMismatchError(Exception):
    pass


def _service_export_dir(base_export_dir: Path, service_id: str) -> Path:
    """One subdirectory (and therefore one checkpoint) per service — the
    primary defense against cross-service checkpoint/data mixing."""
    return base_export_dir / service_id


def _verify_checkpoint_identity(checkpoint: Checkpoint, owner_id: str, service_id: str) -> None:
    """Defense-in-depth on top of the subdirectory scheme (e.g. if a
    checkpoint file were ever copied between service directories by hand)."""
    if checkpoint.service_id and checkpoint.service_id != service_id:
        raise ServiceMismatchError(
            f"Checkpoint belongs to service {checkpoint.service_id!r}, not {service_id!r}. "
            f"Refusing to continue — this would silently mix two services' cursors/dedup state."
        )
    if checkpoint.owner_id and checkpoint.owner_id != owner_id:
        raise ServiceMismatchError(
            f"Checkpoint belongs to owner {checkpoint.owner_id!r}, not {owner_id!r}. "
            f"Refusing to continue."
        )


# ── Transport abstraction ────────────────────────────────────────────────
#
# _fetch_log_page() below owns retry/backoff and is transport-agnostic; it
# calls _http_get(), which dispatches to exactly one of the two
# implementations below based on the resolved transport. Neither
# implementation ever disables TLS verification, and neither falls back to
# the other (or to an insecure flag) on failure — a failure is a failure,
# reported to the caller, full stop.

@dataclass
class HttpResponse:
    status_code: int
    reason: str
    headers: dict
    json_body: Optional[dict]


def select_transport(requested: str) -> str:
    """
    'auto' resolves once per export_logs() call, not per-request — the
    resolved transport is used for every page of a given run, never
    re-decided mid-run.
    """
    if requested != "auto":
        return requested
    if platform.system() == "Windows" and shutil.which("curl.exe"):
        return "curl"
    return "requests"


def _http_get_requests(url: str, api_key: str, params: dict, timeout: int) -> HttpResponse:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        params=params,
        timeout=timeout,
    )
    try:
        body = resp.json()
    except ValueError:
        body = None
    return HttpResponse(resp.status_code, resp.reason, dict(resp.headers), body)


def _http_get_curl(url: str, api_key: str, params: dict, timeout: int, ssl_no_revoke: bool) -> HttpResponse:
    """
    Invokes curl.exe directly (resolved via shutil.which, never the bare
    string "curl" — on Windows that can resolve to a PowerShell alias
    instead of the real binary; passing a fully-resolved path to
    subprocess.run bypasses PowerShell's alias/function resolution
    entirely, since subprocess does not go through a shell here).

    The Authorization header is passed via a curl -K config file, not as a
    command-line argument — argv is visible to other processes/process
    listings on the same machine; a -K config file's *contents* are not.
    The config file is written with a random temp name and deleted in a
    finally block; its contents are never logged, printed, or included in
    any exception message this function raises.
    """
    curl_path = shutil.which("curl.exe")
    if not curl_path:
        raise RuntimeError("--transport curl requested (or auto-selected) but curl.exe was not found on PATH.")

    config_fd, config_path = tempfile.mkstemp(prefix="render_log_export_", suffix=".curlcfg")
    body_fd, body_path = tempfile.mkstemp(prefix="render_log_export_", suffix=".body")
    header_fd, header_path = tempfile.mkstemp(prefix="render_log_export_", suffix=".headers")
    os.close(body_fd)
    os.close(header_fd)
    try:
        with os.fdopen(config_fd, "w", encoding="utf-8") as f:
            f.write(f'header = "Authorization: Bearer {api_key}"\n')
            f.write('header = "Accept: application/json"\n')

        argv = [curl_path, "-G", url, "-K", config_path,
                "--max-time", str(timeout), "-D", header_path, "-o", body_path,
                "-w", "%{http_code}", "-sS"]
        for key, value in params.items():
            argv += ["--data-urlencode", f"{key}={value}"]
        if ssl_no_revoke:
            argv.append("--ssl-no-revoke")

        for forbidden in _FORBIDDEN_TLS_BYPASS_FLAGS:
            assert forbidden not in argv, "TLS-bypass flag construction bug — must never happen"

        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout + 5)
        if proc.returncode != 0:
            # proc.stderr may contain curl diagnostics but never the key —
            # the key was never in argv, only in the (now-deleted) config file.
            raise RuntimeError(
                f"curl.exe exited {proc.returncode}: {proc.stderr.strip()[:500]}. "
                f"Not retrying with an insecure flag — fix the underlying TLS/network "
                f"issue, or confirm --ssl-no-revoke is appropriate for your network."
            )

        status_code = int(proc.stdout.strip())
        headers = {}
        header_text = Path(header_path).read_text(encoding="utf-8", errors="replace")
        for line in header_text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip()] = v.strip()
        reason = http.client.responses.get(status_code, "")
        body_text = Path(body_path).read_text(encoding="utf-8", errors="replace")
        try:
            json_body = json.loads(body_text) if body_text else None
        except json.JSONDecodeError:
            json_body = None
        return HttpResponse(status_code, reason, headers, json_body)
    finally:
        for p in (config_path, body_path, header_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _http_get(transport: str, url: str, api_key: str, params: dict, timeout: int, ssl_no_revoke: bool) -> HttpResponse:
    if transport == "requests":
        if ssl_no_revoke:
            raise SystemExit("--ssl-no-revoke is only meaningful with --transport curl on Windows; "
                              "refusing to silently ignore it under --transport requests.")
        return _http_get_requests(url, api_key, params, timeout)
    if transport == "curl":
        return _http_get_curl(url, api_key, params, timeout, ssl_no_revoke)
    raise ValueError(f"unknown transport {transport!r}")


# ── Render API access (official /v1/logs shape) ──

def _fetch_log_page(
    api_key: str,
    owner_id: str,
    service_id: str,
    start_time: str,
    end_time: str,
    log_type: str,
    direction: str,
    text_marker: Optional[str] = None,
    limit: int = PAGE_LIMIT,
    transport: str = "requests",
    ssl_no_revoke: bool = False,
) -> dict:
    """
    GET {RENDER_API_BASE}/logs — official Render Logs API request shape,
    verified against a real, working, owner-run call (not speculative):
    ownerId and resource are required; type/startTime/endTime/limit/
    direction/text are all accepted. `direction` is always sent explicitly
    (no evidence it has a safe default) — export_logs() always calls this
    with direction="forward", since the checkpoint-advancement logic in
    export_logs() assumes nextStartTime/nextEndTime move monotonically
    forward in time; a caller wanting "backward" (e.g. an ad hoc "most
    recent N matching logs" lookup) must not reuse export_logs()'s
    checkpoint logic unmodified. Retries on HTTP 429 with Retry-After
    (falling back to exponential backoff) up to MAX_RETRIES_429 times.
    Never prints response body content on error — only status code and
    reason phrase. Delegates the actual request to _http_get() (transport
    abstraction, above); retry/backoff logic here is identical regardless
    of which transport is in use.
    """
    params = {
        "ownerId": owner_id,
        "resource": service_id,
        "type": log_type,
        "startTime": start_time,
        "endTime": end_time,
        "direction": direction,
        "limit": limit,
    }
    if text_marker:
        params["text"] = text_marker
    attempt = 0
    while True:
        resp = _http_get(transport, f"{RENDER_API_BASE}/logs", api_key, params, REQUEST_TIMEOUT_S, ssl_no_revoke)
        if resp.status_code == 429 and attempt < MAX_RETRIES_429:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else BACKOFF_BASE_S * (2 ** attempt)
            attempt += 1
            time.sleep(delay)
            continue
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(
                f"Render logs request failed: HTTP {resp.status_code} {resp.reason}. "
                f"401/403 usually means the API key or its scopes; 400/404 usually means "
                f"_fetch_log_page()'s request shape no longer matches the official API — "
                f"verify at https://api-docs.render.com. (Response body intentionally not "
                f"printed here.)"
            )
        return resp.json_body


def _parse_log_response(payload: dict) -> tuple[list[dict], bool, Optional[str], Optional[str]]:
    """
    Official response shape only — no speculative fallback key names.
    Returns (logs, has_more, next_start_time, next_end_time).
    """
    try:
        logs = payload["logs"]
        has_more = payload["hasMore"]
    except KeyError as exc:
        raise RuntimeError(
            f"Render log response missing required field {exc}. Top-level keys present: "
            f"{sorted(payload.keys()) if isinstance(payload, dict) else type(payload)}."
        ) from exc
    next_start_time = payload.get("nextStartTime")
    next_end_time = payload.get("nextEndTime")
    return logs, has_more, next_start_time, next_end_time


def _validate_and_project(entry: dict) -> dict:
    """
    Fail closed: an entry without both id and timestamp cannot be
    deduplicated or checkpointed safely, so it is never written — this
    raises rather than silently dropping or guessing.
    """
    if "id" not in entry or entry["id"] in (None, ""):
        raise RuntimeError(f"Log entry missing required field 'id': {sorted(entry.keys())}")
    if "timestamp" not in entry or entry["timestamp"] in (None, ""):
        raise RuntimeError(f"Log entry missing required field 'timestamp': {sorted(entry.keys())}")
    return {k: entry.get(k) for k in _SHADOW_EVIDENCE_FIELDS if k in entry}


def _matches_marker(entry: dict, marker_re: Optional[re.Pattern]) -> bool:
    """
    Defense-in-depth, not the primary narrowing mechanism: the marker is
    also sent server-side as the `text` request param (_fetch_log_page),
    which is what actually reduces what's transferred. This local check
    additionally guarantees nothing gets persisted unless it strictly
    matches our own regex, independent of whatever matching semantics
    Render's server-side `text` filter uses internally (substring, fuzzy,
    tokenized — not confirmed, and this check doesn't need to assume).
    """
    if marker_re is None:
        return True
    return bool(marker_re.search(str(entry.get("message", ""))))


def _existing_ids(day_file: Path) -> set:
    if not day_file.exists():
        return set()
    ids = set()
    with day_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("id"))
            except json.JSONDecodeError:
                continue
    return ids


# ── export ──

def export_logs(
    api_key_env: str,
    owner_id: str,
    service_id: str,
    base_export_dir: Path,
    dry_run: bool,
    catch_up_days: int,
    log_type: str,
    marker: Optional[str],
    allow_full_export: bool,
    transport: str = "auto",
    ssl_no_revoke: bool = False,
) -> None:
    if not marker and not allow_full_export:
        raise SystemExit(
            "export requires --marker (a required, approved server-side text marker to "
            "narrow what gets written) unless you explicitly pass --allow-full-export. "
            "Exporting an entire service's logs by default is not supported."
        )
    marker_re = re.compile(re.escape(marker)) if marker else None

    resolved_transport = select_transport(transport)
    if ssl_no_revoke and not (resolved_transport == "curl" and platform.system() == "Windows"):
        raise SystemExit(
            "--ssl-no-revoke is only supported for the curl transport on Windows "
            f"(resolved transport here: {resolved_transport!r} on {platform.system()!r}). "
            "Refusing to accept a flag that would silently have no effect."
        )

    export_dir = _service_export_dir(base_export_dir, service_id)
    checkpoint_path = export_dir / CHECKPOINT_NAME
    checkpoint = Checkpoint.load(checkpoint_path)
    _verify_checkpoint_identity(checkpoint, owner_id, service_id)

    now = datetime.now(timezone.utc).isoformat()
    outer_start = checkpoint.last_completed_end_time or (
        datetime.now(timezone.utc) - timedelta(days=catch_up_days)
    ).isoformat()
    outer_end = now

    print(f"Export window: {outer_start} -> {outer_end} (owner {owner_id}, service {service_id}, "
          f"type={log_type}, marker={marker!r}, transport={resolved_transport})")

    if dry_run:
        print("--dry-run: no network call made, no files written. "
              "Omit --dry-run once the window above looks right.")
        return

    api_key = _read_api_key(api_key_env)

    cursor_start, cursor_end = outer_start, outer_end
    total_written = 0
    total_skipped_marker = 0
    total_skipped_dup = 0

    while True:
        # direction is fixed to "forward" here, not exposed as a CLI option
        # for export — see _fetch_log_page()'s docstring for why "backward"
        # would break this function's checkpoint-advancement assumption.
        payload = _fetch_log_page(api_key, owner_id, service_id, cursor_start, cursor_end, log_type,
                                   direction="forward", text_marker=marker,
                                   transport=resolved_transport, ssl_no_revoke=ssl_no_revoke)
        logs, has_more, next_start_time, next_end_time = _parse_log_response(payload)

        by_day: dict[str, list[dict]] = {}
        for raw_entry in logs:
            if not _matches_marker(raw_entry, marker_re):
                total_skipped_marker += 1
                continue
            projected = _validate_and_project(raw_entry)  # raises on missing id/timestamp — fail closed
            day = projected["timestamp"][:10]
            by_day.setdefault(day, []).append(projected)

        export_dir.mkdir(parents=True, exist_ok=True)
        for day, day_entries in by_day.items():
            day_file = export_dir / f"{day}.jsonl"
            existing_ids = _existing_ids(day_file)
            new_entries = [e for e in day_entries if e["id"] not in existing_ids]
            total_skipped_dup += len(day_entries) - len(new_entries)
            if new_entries:
                with day_file.open("a", encoding="utf-8") as f:
                    for entry in new_entries:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        f.flush()
                total_written += len(new_entries)

        # Checkpoint durably right after this page's writes are on disk —
        # before requesting the next page, so a crash before the next
        # request leaves the checkpoint at a safely-resumable boundary.
        checkpoint.owner_id = owner_id
        checkpoint.service_id = service_id
        checkpoint.last_completed_end_time = next_start_time if has_more else cursor_end
        checkpoint.last_run_at = datetime.now(timezone.utc).isoformat()
        checkpoint.save(checkpoint_path)

        if not has_more:
            break
        cursor_start, cursor_end = next_start_time, next_end_time

    print(f"Wrote {total_written} entries (skipped {total_skipped_marker} non-matching, "
          f"{total_skipped_dup} already-present). Checkpoint: {checkpoint_path}")


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
    files = sorted(export_dir.rglob("*.jsonl"))
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
                    yield f"{path.relative_to(export_dir)}:{line_no}: {line.rstrip()}"
                    if count >= max_results:
                        return


# ── CLI — canonical syntax: global flags always after the subcommand (see module docstring) ──

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--export-dir", default=str(DEFAULT_EXPORT_DIR),
                         help=f"default: {DEFAULT_EXPORT_DIR} (must stay out of git — see .gitignore)")
    common.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV,
                         help=f"name of the environment variable holding the Render API key (default: {DEFAULT_API_KEY_ENV})")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-env", parents=[common],
                    help="report whether the API key env var is set, without ever printing its value")

    p_export = sub.add_parser("export", parents=[common], help="fetch new log entries since the last checkpoint")
    p_export.add_argument("--owner-id", required=True, help="Render workspace/owner id (official API requires this)")
    p_export.add_argument("--service-id", required=True, help="Render service id, e.g. srv-xxxxxxxx")
    p_export.add_argument("--marker", help="required approved text marker to narrow what gets written (see --allow-full-export)")
    p_export.add_argument("--allow-full-export", action="store_true",
                           help="override the required-marker default; exports without any text filter")
    p_export.add_argument("--log-type", default="app", help="Render log type filter (default: app)")
    p_export.add_argument("--dry-run", action="store_true", help="print the export window and exit, no network call")
    p_export.add_argument("--catch-up-days", type=int, default=1, help="window to use on the very first run (no checkpoint yet)")
    p_export.add_argument("--transport", choices=["auto", "requests", "curl"], default="auto",
                           help="auto (default): curl.exe on Windows if present, else requests. Never disables TLS verification.")
    p_export.add_argument("--ssl-no-revoke", action="store_true",
                           help="Windows curl transport only: skip the certificate REVOCATION check "
                                "(OCSP/CRL), not certificate trust validation. Rejected under any other transport.")

    p_search = sub.add_parser("search", parents=[common], help="search already-exported JSONL files locally")
    p_search.add_argument("pattern", help="regex pattern to search for")
    p_search.add_argument("--since", help="YYYY-MM-DD, inclusive")
    p_search.add_argument("--until", help="YYYY-MM-DD, inclusive")
    p_search.add_argument("--field", help="restrict the search to one JSON field instead of the whole raw line")
    p_search.add_argument("--max-results", type=int, default=200)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    export_dir = Path(args.export_dir)

    if args.command == "check-env":
        check_env(args.api_key_env)
    elif args.command == "export":
        export_logs(
            args.api_key_env, args.owner_id, args.service_id, export_dir, args.dry_run,
            args.catch_up_days, args.log_type, args.marker, args.allow_full_export,
            args.transport, args.ssl_no_revoke,
        )
    elif args.command == "search":
        for line in search_logs(export_dir, args.pattern, args.since, args.until, args.field, args.max_results):
            print(line)


if __name__ == "__main__":
    main()
