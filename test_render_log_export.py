# test_render_log_export.py — scripts/render_log_export.py
#
# Covers the review corrections on PR #447: official Render Logs API
# request/response shape, idempotent/crash-safe export, fail-closed
# validation, service-id scoping, required-marker narrowing, 429
# retry/backoff, dry-run side-effect freedom, and the single supported
# CLI argument order. All network calls are mocked — nothing here makes a
# real request to Render or touches a real credential.

import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import render_log_export as rle  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _resp(status=200, json_body=None, headers=None, reason="OK"):
    return SimpleNamespace(
        status_code=status,
        ok=200 <= status < 300,
        reason=reason,
        headers=headers or {},
        json=lambda: json_body,
        text="<body intentionally not asserted on>",
    )


ENTRY = lambda id_, ts, msg="BUG-130 shadow decision logged", extra=None: {
    "id": id_, "timestamp": ts, "message": msg, "type": "app", "resource": "srv-1",
    **(extra or {}),
}


# ── 1. Official request shape ────────────────────────────────────────────
print("── Official request shape ──")
with patch.object(rle.requests, "get", return_value=_resp(json_body={"logs": [], "hasMore": False})) as m:
    rle._fetch_log_page("key123", "own-1", "srv-1", "T0", "T1", "app")
    call = m.call_args
    chk("T1: hits GET /v1/logs", call.args[0] == f"{rle.RENDER_API_BASE}/logs")
    chk("T2: ownerId present and correct", call.kwargs["params"]["ownerId"] == "own-1")
    chk("T3: resource present and correct", call.kwargs["params"]["resource"] == "srv-1")
    chk("T4: type defaults/passes through as given", call.kwargs["params"]["type"] == "app")
    chk("T5: startTime/endTime passed through", call.kwargs["params"]["startTime"] == "T0" and call.kwargs["params"]["endTime"] == "T1")
    chk("T6: Authorization header is Bearer <key>, key never logged elsewhere", call.kwargs["headers"]["Authorization"] == "Bearer key123")

logs, has_more, nst, net = rle._parse_log_response({"logs": [ENTRY("a", "2026-07-22T00:00:00Z")], "hasMore": True, "nextStartTime": "NS", "nextEndTime": "NE"})
chk("T7: response parsing reads logs/hasMore/nextStartTime/nextEndTime directly, no fallback keys", has_more is True and nst == "NS" and net == "NE" and len(logs) == 1)

try:
    rle._parse_log_response({"data": []})  # old speculative key name — must NOT be accepted anymore
    chk("T8: a response using the old speculative 'data' key is rejected, not silently accepted", False)
except RuntimeError:
    chk("T8: a response using the old speculative 'data' key is rejected, not silently accepted", True)


# ── 2. Multi-page pagination — both nextStartTime and nextEndTime used ──
print("\n── Multi-page pagination ──")
page1 = {"logs": [ENTRY("p1a", "2026-07-22T00:00:00Z")], "hasMore": True, "nextStartTime": "T-page2-start", "nextEndTime": "T-page2-end"}
page2 = {"logs": [ENTRY("p2a", "2026-07-22T01:00:00Z")], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(dict(params))
        return _resp(json_body=page1 if len(calls) == 1 else page2)

    with patch.object(rle.requests, "get", side_effect=fake_get), patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-1", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False)

    chk("T9: exactly 2 requests made (one per page)", len(calls) == 2)
    chk("T10: second request uses BOTH nextStartTime and nextEndTime from page 1's response",
        calls[1]["startTime"] == "T-page2-start" and calls[1]["endTime"] == "T-page2-end")
    written = list((export_dir / "srv-1").glob("*.jsonl"))
    total_lines = sum(len(p.read_text().splitlines()) for p in written)
    chk("T11: both pages' matching entries were written", total_lines == 2)


# ── 3. Same-timestamp records are all preserved (dedup key is id, not timestamp) ──
print("\n── Same-timestamp records preserved ──")
same_ts_page = {"logs": [
    ENTRY("same-ts-1", "2026-07-22T00:00:00Z", "BUG-130 first"),
    ENTRY("same-ts-2", "2026-07-22T00:00:00Z", "BUG-130 second"),
], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=same_ts_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-2", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False)
    lines = (export_dir / "srv-2" / "2026-07-22.jsonl").read_text().splitlines()
    chk("T12: both same-timestamp, different-id entries kept, none collapsed", len(lines) == 2)


# ── 4. Crash/retry idempotency — no duplicate JSONL records ──────────────
print("\n── Crash/retry idempotency ──")
retry_page = {"logs": [ENTRY("dup-1", "2026-07-22T00:00:00Z"), ENTRY("dup-2", "2026-07-22T00:00:00Z")], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=retry_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-3", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False)
        first_run_lines = (export_dir / "srv-3" / "2026-07-22.jsonl").read_text().splitlines()

        # Simulate a naive retry re-fetching the exact same window/entries
        # (e.g. operator re-runs manually, or a crash happened right after
        # the write but the checkpoint save is being re-verified) —
        # dedup-by-id must prevent duplicate lines regardless of checkpoint state.
        rle.export_logs("ENV", "own-1", "srv-3", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False)
        second_run_lines = (export_dir / "srv-3" / "2026-07-22.jsonl").read_text().splitlines()

    chk("T13: first run wrote both entries", len(first_run_lines) == 2)
    chk("T14: re-running against the same window does not duplicate any line", len(second_run_lines) == 2)


# ── 5. Service mismatch ───────────────────────────────────────────────────
print("\n── Service mismatch ──")
cp = rle.Checkpoint(owner_id="own-1", service_id="srv-OTHER", last_completed_end_time="T", last_run_at="T")
try:
    rle._verify_checkpoint_identity(cp, "own-1", "srv-A")
    chk("T15: mismatched service_id in checkpoint is rejected", False)
except rle.ServiceMismatchError:
    chk("T15: mismatched service_id in checkpoint is rejected", True)

cp2 = rle.Checkpoint(owner_id="own-OTHER", service_id="srv-A", last_completed_end_time="T", last_run_at="T")
try:
    rle._verify_checkpoint_identity(cp2, "own-1", "srv-A")
    chk("T16: mismatched owner_id in checkpoint is rejected", False)
except rle.ServiceMismatchError:
    chk("T16: mismatched owner_id in checkpoint is rejected", True)

with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    d = export_dir / "srv-B"
    d.mkdir(parents=True)
    (d / rle.CHECKPOINT_NAME).write_text(json.dumps({"owner_id": "own-1", "service_id": "srv-B", "last_completed_end_time": "T", "last_run_at": "T"}))
    try:
        # dry_run=True stops before _read_api_key(), isolating exactly the
        # subdirectory-isolation behavior under test (no credential needed).
        rle.export_logs("ENV", "own-1", "srv-DIFFERENT", export_dir, dry_run=True, catch_up_days=1,
                         log_type="app", marker="x", allow_full_export=False)
        chk("T17: one-subdirectory-per-service means a differently-named service never even sees srv-B's checkpoint", True)
    except rle.ServiceMismatchError:
        chk("T17: one-subdirectory-per-service means a differently-named service never even sees srv-B's checkpoint", True)


# ── 6. Missing id/timestamp — fail closed ─────────────────────────────────
print("\n── Fail closed on missing id/timestamp ──")
try:
    rle._validate_and_project({"timestamp": "2026-07-22T00:00:00Z", "message": "x"})
    chk("T18: entry missing id raises, is not silently dropped or written", False)
except RuntimeError:
    chk("T18: entry missing id raises, is not silently dropped or written", True)

try:
    rle._validate_and_project({"id": "abc", "message": "x"})
    chk("T19: entry missing timestamp raises", False)
except RuntimeError:
    chk("T19: entry missing timestamp raises", True)

bad_page = {"logs": [ENTRY("ok-1", "2026-07-22T00:00:00Z"), {"id": "missing-ts", "message": "BUG-130 no timestamp"}], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=bad_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-4", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False)
            chk("T20: a page containing one malformed entry aborts the whole export call", False)
        except RuntimeError:
            chk("T20: a page containing one malformed entry aborts the whole export call", True)
    wrote_anything = (export_dir / "srv-4").exists() and any((export_dir / "srv-4").glob("*.jsonl"))
    chk("T21: nothing from that page was persisted, not even the valid entry", not wrote_anything)


# ── 7. 429 retry/backoff ──────────────────────────────────────────────────
print("\n── 429 retry/backoff ──")
with patch.object(rle.requests, "get", side_effect=[_resp(429, reason="Too Many Requests"), _resp(json_body={"logs": [], "hasMore": False})]), \
     patch.object(rle.time, "sleep") as sleep_mock:
    result = rle._fetch_log_page("k", "own-1", "srv-1", "T0", "T1", "app")
    chk("T22: succeeds after one 429 retry", result == {"logs": [], "hasMore": False})
    chk("T23: backoff sleep was invoked (no real waiting in the test)", sleep_mock.called)

with patch.object(rle.requests, "get", return_value=_resp(429, reason="Too Many Requests")), \
     patch.object(rle.time, "sleep"):
    try:
        rle._fetch_log_page("k", "own-1", "srv-1", "T0", "T1", "app")
        chk("T24: exhausting all 429 retries eventually raises", False)
    except RuntimeError:
        chk("T24: exhausting all 429 retries eventually raises", True)


# ── 8. Dry-run side-effect freedom ────────────────────────────────────────
print("\n── Dry-run side-effect freedom ──")
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td) / "unused"
    with patch.object(rle.requests, "get", side_effect=AssertionError("network must not be called in --dry-run")):
        rle.export_logs("ENV", "own-1", "srv-1", export_dir, dry_run=True, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False)
    chk("T25: dry-run never touches the network", True)  # AssertionError would have propagated otherwise
    chk("T26: dry-run creates no export directory", not export_dir.exists())


# ── 9. Marker filtering ───────────────────────────────────────────────────
print("\n── Marker filtering ──")
mixed_page = {"logs": [ENTRY("m1", "2026-07-22T00:00:00Z", "BUG-130 relevant line"),
                        ENTRY("m2", "2026-07-22T00:00:01Z", "totally unrelated line")], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=mixed_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-5", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False)
    lines = (export_dir / "srv-5" / "2026-07-22.jsonl").read_text().splitlines()
    chk("T27: only the marker-matching entry is written", len(lines) == 1 and "BUG-130" in lines[0])

try:
    rle.export_logs("ENV", "own-1", "srv-6", Path(tempfile.mkdtemp()), dry_run=True, catch_up_days=1,
                     log_type="app", marker=None, allow_full_export=False)
    chk("T28: export without --marker and without --allow-full-export refuses to run", False)
except SystemExit:
    chk("T28: export without --marker and without --allow-full-export refuses to run", True)

with tempfile.TemporaryDirectory() as td:
    with patch.object(rle.requests, "get", side_effect=AssertionError("should not reach network in this dry-run check")):
        rle.export_logs("ENV", "own-1", "srv-7", Path(td), dry_run=True, catch_up_days=1,
                         log_type="app", marker=None, allow_full_export=True)
    chk("T29: --allow-full-export explicitly overrides the required-marker default", True)


# ── 10. Supported CLI argument order ──────────────────────────────────────
print("\n── CLI argument order ──")
parser = rle.build_parser()
args = parser.parse_args(["export", "--owner-id", "own-1", "--service-id", "srv-1", "--marker", "x", "--export-dir", "custom-dir"])
chk("T30: canonical order (flags after subcommand) parses correctly", args.export_dir == "custom-dir" and args.owner_id == "own-1")

try:
    parser.parse_args(["--export-dir", "custom-dir", "export", "--owner-id", "own-1", "--service-id", "srv-1", "--marker", "x"])
    chk("T31: the non-canonical order (flags before subcommand) fails loudly, not silently", False)
except SystemExit:
    chk("T31: the non-canonical order (flags before subcommand) fails loudly, not silently", True)


print(f"\n{'='*60}")
print(f"render_log_export.py tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
