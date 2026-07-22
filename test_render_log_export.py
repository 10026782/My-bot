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


ENTRY = lambda id_, ts, msg="BUG-130 shadow decision logged", resource="srv-1", type_="app", extra=None: {
    "id": id_, "timestamp": ts, "message": msg, "type": type_, "resource": resource,
    **(extra or {}),
}


# ── Hermetic guard — installed BEFORE any test runs, active for the whole
# suite. Every test block below that touches the network locally overrides
# this via its own `with patch.object(rle.requests, "get", ...)` /
# `patch.object(rle.subprocess, "run", ...)`, which correctly restores this
# guard on exit. Anything NOT locally mocked falls through to here and
# fails loudly instead of making a real request/subprocess call — this is
# what makes the suite safe to run unmodified on a Windows machine with
# curl.exe on PATH (see select_transport(): 'auto' picks curl there).
def _unmocked_network_guard(*args, **kwargs):
    raise AssertionError(
        "requests.get was reached without being mocked in this test — the suite must "
        "never make a real network call. Wrap this block in patch.object(rle.requests, 'get', ...)."
    )


def _unmocked_subprocess_guard(*args, **kwargs):
    raise AssertionError(
        "subprocess.run was reached without being mocked in this test — the suite must "
        "never invoke curl.exe for real. Wrap this block in patch.object(rle.subprocess, 'run', ...)."
    )


_network_guard = patch.object(rle.requests, "get", side_effect=_unmocked_network_guard)
_subprocess_guard = patch.object(rle.subprocess, "run", side_effect=_unmocked_subprocess_guard)
_network_guard.start()
_subprocess_guard.start()


# ── 1. Official request shape ────────────────────────────────────────────
print("── Official request shape ──")
with patch.object(rle.requests, "get", return_value=_resp(json_body={"logs": [], "hasMore": False})) as m:
    rle._fetch_log_page("key123", "own-1", "srv-1", "T0", "T1", "app", direction="forward", text_marker="BUG-130")
    call = m.call_args
    chk("T1: hits GET /v1/logs", call.args[0] == f"{rle.RENDER_API_BASE}/logs")
    chk("T2: ownerId present and correct", call.kwargs["params"]["ownerId"] == "own-1")
    chk("T3: resource present and correct", call.kwargs["params"]["resource"] == "srv-1")
    chk("T4: type defaults/passes through as given", call.kwargs["params"]["type"] == "app")
    chk("T5: startTime/endTime passed through", call.kwargs["params"]["startTime"] == "T0" and call.kwargs["params"]["endTime"] == "T1")
    chk("T6: Authorization header is Bearer <key>, key never logged elsewhere", call.kwargs["headers"]["Authorization"] == "Bearer key123")
    chk("T6b: direction is sent explicitly (owner-confirmed real param, no assumed default)", call.kwargs["params"]["direction"] == "forward")
    chk("T6c: text (server-side marker) is sent when a marker is given (owner-confirmed real param)", call.kwargs["params"]["text"] == "BUG-130")

with patch.object(rle.requests, "get", return_value=_resp(json_body={"logs": [], "hasMore": False})) as m:
    rle._fetch_log_page("key123", "own-1", "srv-1", "T0", "T1", "app", direction="forward", text_marker=None)
    chk("T6d: text is omitted entirely (not sent as text=None) when no marker is given", "text" not in m.call_args.kwargs["params"])

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
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")

    chk("T9: exactly 2 requests made (one per page)", len(calls) == 2)
    chk("T10: second request uses BOTH nextStartTime and nextEndTime from page 1's response",
        calls[1]["startTime"] == "T-page2-start" and calls[1]["endTime"] == "T-page2-end")
    written = list((export_dir / "srv-1").glob("*.jsonl"))
    total_lines = sum(len(p.read_text().splitlines()) for p in written)
    chk("T11: both pages' matching entries were written", total_lines == 2)


# ── 3. Same-timestamp records are all preserved (dedup key is id, not timestamp) ──
print("\n── Same-timestamp records preserved ──")
same_ts_page = {"logs": [
    ENTRY("same-ts-1", "2026-07-22T00:00:00Z", "BUG-130 first", resource="srv-2"),
    ENTRY("same-ts-2", "2026-07-22T00:00:00Z", "BUG-130 second", resource="srv-2"),
], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=same_ts_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-2", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
    lines = (export_dir / "srv-2" / "2026-07-22.jsonl").read_text().splitlines()
    chk("T12: both same-timestamp, different-id entries kept, none collapsed", len(lines) == 2)


# ── 4. Crash/retry idempotency — no duplicate JSONL records ──────────────
print("\n── Crash/retry idempotency ──")
retry_page = {"logs": [ENTRY("dup-1", "2026-07-22T00:00:00Z", resource="srv-3"),
                       ENTRY("dup-2", "2026-07-22T00:00:00Z", resource="srv-3")], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=retry_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-3", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
        first_run_lines = (export_dir / "srv-3" / "2026-07-22.jsonl").read_text().splitlines()

        # Simulate a naive retry re-fetching the exact same window/entries
        # (e.g. operator re-runs manually, or a crash happened right after
        # the write but the checkpoint save is being re-verified) —
        # dedup-by-id must prevent duplicate lines regardless of checkpoint state.
        rle.export_logs("ENV", "own-1", "srv-3", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
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
    rle._validate_and_project({"timestamp": "2026-07-22T00:00:00Z", "message": "x"}, "srv-x", "app")
    chk("T18: entry missing id raises, is not silently dropped or written", False)
except RuntimeError:
    chk("T18: entry missing id raises, is not silently dropped or written", True)

try:
    rle._validate_and_project({"id": "abc", "message": "x"}, "srv-x", "app")
    chk("T19: entry missing timestamp raises", False)
except RuntimeError:
    chk("T19: entry missing timestamp raises", True)

bad_page = {"logs": [ENTRY("ok-1", "2026-07-22T00:00:00Z", resource="srv-4"), {"id": "missing-ts", "message": "BUG-130 no timestamp"}], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=bad_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-4", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T20: a page containing one malformed entry aborts the whole export call", False)
        except RuntimeError:
            chk("T20: a page containing one malformed entry aborts the whole export call", True)
    wrote_anything = (export_dir / "srv-4").exists() and any((export_dir / "srv-4").glob("*.jsonl"))
    chk("T21: nothing from that page was persisted, not even the valid entry", not wrote_anything)


# ── 7. 429 retry/backoff ──────────────────────────────────────────────────
print("\n── 429 retry/backoff ──")
with patch.object(rle.requests, "get", side_effect=[_resp(429, reason="Too Many Requests"), _resp(json_body={"logs": [], "hasMore": False})]), \
     patch.object(rle.time, "sleep") as sleep_mock:
    result = rle._fetch_log_page("k", "own-1", "srv-1", "T0", "T1", "app", direction="forward")
    chk("T22: succeeds after one 429 retry", result == {"logs": [], "hasMore": False})
    chk("T23: backoff sleep was invoked (no real waiting in the test)", sleep_mock.called)

with patch.object(rle.requests, "get", return_value=_resp(429, reason="Too Many Requests")), \
     patch.object(rle.time, "sleep"):
    try:
        rle._fetch_log_page("k", "own-1", "srv-1", "T0", "T1", "app", direction="forward")
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
mixed_page = {"logs": [ENTRY("m1", "2026-07-22T00:00:00Z", "BUG-130 relevant line", resource="srv-5"),
                        ENTRY("m2", "2026-07-22T00:00:01Z", "totally unrelated line")], "hasMore": False}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=mixed_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-5", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
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


# ── 11. Transport abstraction ─────────────────────────────────────────────
print("\n── Transport abstraction ──")

with patch.object(rle.platform, "system", return_value="Windows"), \
     patch.object(rle.shutil, "which", return_value=r"C:\Windows\System32\curl.exe"):
    chk("T32: auto chooses curl on Windows when curl.exe is on PATH", rle.select_transport("auto") == "curl")

with patch.object(rle.platform, "system", return_value="Windows"), \
     patch.object(rle.shutil, "which", return_value=None):
    chk("T33: auto falls back to requests on Windows when curl.exe is not found", rle.select_transport("auto") == "requests")

with patch.object(rle.platform, "system", return_value="Linux"):
    chk("T34: auto uses requests on non-Windows", rle.select_transport("auto") == "requests")

chk("T35: --transport requests remains selectable explicitly regardless of platform", rle.select_transport("requests") == "requests")
chk("T36: --transport curl remains selectable explicitly regardless of platform", rle.select_transport("curl") == "curl")

FAKE_KEY = "SECRET_KEY_MUST_NEVER_APPEAR_ANYWHERE_abc123"

with patch.object(rle.shutil, "which", return_value="/usr/bin/curl.exe"), \
     patch.object(rle.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="200", stderr="")) as run_mock:
    rle._http_get_curl("https://api.render.com/v1/logs", FAKE_KEY,
                        {"ownerId": "own-1", "resource": "srv-1", "type": "app"}, 30, ssl_no_revoke=False)
    argv = run_mock.call_args.args[0]
    chk("T37: no -k/--insecure flag is ever constructed for the curl transport",
        all(f not in argv for f in rle._FORBIDDEN_TLS_BYPASS_FLAGS))
    chk("T38: the API key never appears anywhere in the constructed argv (it's in the -K config file, not argv)",
        all(FAKE_KEY not in str(a) for a in argv))
    chk("T39: curl.exe is invoked directly (resolved path), not the bare string 'curl'", argv[0] != "curl")

with patch.object(rle.shutil, "which", return_value="/usr/bin/curl.exe"), \
     patch.object(rle.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="200", stderr="")) as run_mock:
    rle._http_get_curl("https://api.render.com/v1/logs", FAKE_KEY,
                        {"ownerId": "own-1", "resource": "srv-1"}, 30, ssl_no_revoke=True)
    argv = run_mock.call_args.args[0]
    chk("T40: --ssl-no-revoke maps to curl's own --ssl-no-revoke flag, not an insecure flag",
        "--ssl-no-revoke" in argv and all(f not in argv for f in rle._FORBIDDEN_TLS_BYPASS_FLAGS))

with patch.object(rle.shutil, "which", return_value="/usr/bin/curl.exe"), \
     patch.object(rle.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="curl: (60) SSL certificate problem")) as run_mock:
    try:
        rle._http_get_curl("https://api.render.com/v1/logs", FAKE_KEY, {"ownerId": "own-1"}, 30, ssl_no_revoke=False)
        chk("T41: a curl failure raises rather than succeeding", False)
    except RuntimeError as exc:
        chk("T41: a curl failure raises rather than succeeding", True)
        chk("T42: curl failure does not retry with an insecure flag — subprocess.run called exactly once", run_mock.call_count == 1)
        chk("T43: the error message never contains the API key", FAKE_KEY not in str(exc))

try:
    rle._http_get("requests", "https://api.render.com/v1/logs", "k", {}, 30, ssl_no_revoke=True)
    chk("T44: --ssl-no-revoke under --transport requests is rejected, not silently ignored", False)
except SystemExit:
    chk("T44: --ssl-no-revoke under --transport requests is rejected, not silently ignored", True)

with tempfile.TemporaryDirectory() as td:
    try:
        rle.export_logs("ENV", "own-1", "srv-9", Path(td), dry_run=False, catch_up_days=1,
                         log_type="app", marker="x", allow_full_export=False,
                         transport="requests", ssl_no_revoke=True)
        chk("T45: export_logs() itself also rejects --ssl-no-revoke under a non-curl-Windows transport", False)
    except SystemExit:
        chk("T45: export_logs() itself also rejects --ssl-no-revoke under a non-curl-Windows transport", True)

with patch.object(rle.requests, "get", return_value=_resp(json_body={"logs": [], "hasMore": False})):
    chk("T46: --transport requests remains fully usable end-to-end (explicit, not just auto-fallback)",
        rle._fetch_log_page("k", "own-1", "srv-1", "T0", "T1", "app", direction="forward", transport="requests") == {"logs": [], "hasMore": False})


# ── 12. Empty/null logs response — Render returns logs=null (not []) on a zero-match page ──
print("\n── Empty/null logs response ──")

# logs=null + hasMore=false: normalized to [], page succeeds, writes zero, checkpoint advances.
null_empty_page = {"hasMore": False, "logs": None, "nextStartTime": "NS", "nextEndTime": "NE"}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=null_empty_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-null-1", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
    chk("T47: logs=null with hasMore=false succeeds (no exception)", True)
    written = list((export_dir / "srv-null-1").glob("*.jsonl"))
    chk("T48: logs=null with hasMore=false writes zero records", len(written) == 0)
    cp = json.loads((export_dir / "srv-null-1" / rle.CHECKPOINT_NAME).read_text())
    chk("T49: logs=null with hasMore=false advances the checkpoint", cp["last_completed_end_time"] is not None)

# logs=null + hasMore=true: contradictory, fails closed, checkpoint left untouched.
null_more_page = {"hasMore": True, "logs": None, "nextStartTime": "NS", "nextEndTime": "NE"}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=null_more_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-null-2", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T50: logs=null with hasMore=true fails closed", False)
        except RuntimeError:
            chk("T50: logs=null with hasMore=true fails closed", True)
    checkpoint_path = export_dir / "srv-null-2" / rle.CHECKPOINT_NAME
    chk("T51: logs=null with hasMore=true leaves no checkpoint written", not checkpoint_path.exists())

# logs=[] (already an empty list, not null) — still succeeds normally.
empty_list_page = {"hasMore": False, "logs": []}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=empty_list_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-empty-list", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
    chk("T52: logs=[] (already a list) still succeeds normally",
        (export_dir / "srv-empty-list" / rle.CHECKPOINT_NAME).exists())


# ── 13. Labels-based provenance extraction and validation ──────────────────
print("\n── Labels-based provenance ──")

def LABELED_ENTRY(id_, ts, msg="BUG-130 via labels", resource="srv-labels-1", log_type="app"):
    return {"id": id_, "timestamp": ts, "message": msg,
            "labels": [{"name": "resource", "value": resource}, {"name": "type", "value": log_type}]}

# nested labels: resource and type are extracted and persisted onto the entry.
labels_page = {"hasMore": False, "logs": [LABELED_ENTRY("lbl-1", "2026-07-22T00:00:00Z", resource="srv-labels-1")]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=labels_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-labels-1", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
    rec = json.loads((export_dir / "srv-labels-1" / "2026-07-22.jsonl").read_text().splitlines()[0])
    chk("T53: nested-labels resource extracted and persisted", rec.get("resource") == "srv-labels-1")
    chk("T54: nested-labels type extracted and persisted", rec.get("type") == "app")

# top-level resource/type remains supported (Render supplying them directly, no labels array).
top_level_page = {"hasMore": False, "logs": [ENTRY("tl-1", "2026-07-22T00:00:00Z", "BUG-130 top-level", resource="srv-toplevel")]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=top_level_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-toplevel", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
    lines = (export_dir / "srv-toplevel" / "2026-07-22.jsonl").read_text().splitlines()
    chk("T55: top-level resource/type still supported when Render supplies them directly",
        len(lines) == 1 and json.loads(lines[0])["resource"] == "srv-toplevel")

# top-level vs labels conflict: must fail closed, not silently pick one.
conflict_entry = {
    "id": "conflict-1", "timestamp": "2026-07-22T00:00:00Z", "message": "BUG-130 conflict",
    "resource": "srv-top", "type": "app",
    "labels": [{"name": "resource", "value": "srv-different"}, {"name": "type", "value": "app"}],
}
conflict_page = {"hasMore": False, "logs": [conflict_entry]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=conflict_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-top", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T56: conflicting top-level vs labels resource fails closed, does not silently pick one", False)
        except RuntimeError:
            chk("T56: conflicting top-level vs labels resource fails closed, does not silently pick one", True)
    chk("T57: conflicting-provenance page wrote nothing",
        not (export_dir / "srv-top").exists() or not any((export_dir / "srv-top").glob("*.jsonl")))

# missing resource entirely (no top-level, no labels): whole-page abort, zero writes —
# including the OTHER, otherwise-valid entry on the same page.
no_resource_entry = {"id": "no-res-1", "timestamp": "2026-07-22T00:00:00Z", "message": "BUG-130 no resource", "type": "app"}
ok_entry_same_page = ENTRY("ok-same-page", "2026-07-22T00:00:01Z", "BUG-130 would otherwise be fine", resource="srv-missing-res")
missing_resource_page = {"hasMore": False, "logs": [ok_entry_same_page, no_resource_entry]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=missing_resource_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-missing-res", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T58: an entry missing resource entirely aborts the whole page", False)
        except RuntimeError:
            chk("T58: an entry missing resource entirely aborts the whole page", True)
    chk("T59: nothing written from that page, not even the otherwise-valid entry",
        not (export_dir / "srv-missing-res").exists() or not any((export_dir / "srv-missing-res").glob("*.jsonl")))

# wrong resource (present but does not match requested service_id): whole-page abort, zero writes.
wrong_resource_page = {"hasMore": False, "logs": [ENTRY("wrong-res-1", "2026-07-22T00:00:00Z", "BUG-130 wrong resource", resource="srv-OTHER")]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=wrong_resource_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-wrong-res", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T60: an entry with a mismatched resource aborts the whole page", False)
        except RuntimeError:
            chk("T60: an entry with a mismatched resource aborts the whole page", True)
    chk("T61: nothing written when resource mismatches the requested service_id",
        not (export_dir / "srv-wrong-res").exists() or not any((export_dir / "srv-wrong-res").glob("*.jsonl")))

# wrong type: whole-page abort, zero writes.
wrong_type_page = {"hasMore": False, "logs": [ENTRY("wrong-type-1", "2026-07-22T00:00:00Z", "BUG-130 wrong type", resource="srv-wrong-type", type_="build")]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=wrong_type_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-wrong-type", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T62: an entry with a mismatched type aborts the whole page", False)
        except RuntimeError:
            chk("T62: an entry with a mismatched type aborts the whole page", True)
    chk("T63: nothing written when type mismatches the requested log_type",
        not (export_dir / "srv-wrong-type").exists() or not any((export_dir / "srv-wrong-type").glob("*.jsonl")))

# missing type entirely: whole-page abort, zero writes.
missing_type_entry = {"id": "no-type-1", "timestamp": "2026-07-22T00:00:00Z", "message": "BUG-130 no type", "resource": "srv-missing-type"}
missing_type_page = {"hasMore": False, "logs": [missing_type_entry]}
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=missing_type_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        try:
            rle.export_logs("ENV", "own-1", "srv-missing-type", export_dir, dry_run=False, catch_up_days=1,
                             log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
            chk("T64: an entry missing type entirely aborts the whole page", False)
        except RuntimeError:
            chk("T64: an entry missing type entirely aborts the whole page", True)


# ── 14. Immediate second export with no new logs (the real-world crash scenario) ──
print("\n── Immediate rerun, no new logs ──")
first_page = {"hasMore": False, "logs": [ENTRY("rerun-1", "2026-07-22T00:00:00Z", "BUG-130 first run", resource="srv-rerun")]}
second_page = {"hasMore": False, "logs": None}  # the exact real-world shape that used to crash export_logs
with tempfile.TemporaryDirectory() as td:
    export_dir = Path(td)
    with patch.object(rle.requests, "get", return_value=_resp(json_body=first_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-rerun", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
    lines_after_first = (export_dir / "srv-rerun" / "2026-07-22.jsonl").read_text().splitlines()
    cp_after_first = json.loads((export_dir / "srv-rerun" / rle.CHECKPOINT_NAME).read_text())

    with patch.object(rle.requests, "get", return_value=_resp(json_body=second_page)), \
         patch.object(rle, "_read_api_key", return_value="k"):
        rle.export_logs("ENV", "own-1", "srv-rerun", export_dir, dry_run=False, catch_up_days=1,
                         log_type="app", marker="BUG-130", allow_full_export=False, transport="requests")
        chk("T65: immediate rerun with logs=null exits without raising", True)
    lines_after_second = (export_dir / "srv-rerun" / "2026-07-22.jsonl").read_text().splitlines()
    cp_after_second = json.loads((export_dir / "srv-rerun" / rle.CHECKPOINT_NAME).read_text())

    chk("T66: rerun with no new logs writes zero additional records", len(lines_after_second) == len(lines_after_first) == 1)
    ids = [json.loads(l)["id"] for l in lines_after_second]
    chk("T67: no duplicate ids after rerun", len(ids) == len(set(ids)))
    chk("T68: checkpoint advances (never regresses) past the first run's boundary",
        cp_after_second["last_completed_end_time"] >= cp_after_first["last_completed_end_time"])


# ── 15. Hermetic guard — the whole suite above made zero real network/subprocess calls ──
print("\n── Hermetic guard ──")
_found_curl = rle.shutil.which("curl.exe")
if _found_curl:
    print(f"  curl.exe present on this machine's real PATH at {_found_curl} — every test above still ran hermetically")
else:
    print("  curl.exe not present on this machine's real PATH")
chk("T69: reaching this line proves no unmocked requests.get/subprocess.run call happened above "
    "(the outer guard installed near the top of this file raises immediately otherwise)", True)

_network_guard.stop()
_subprocess_guard.stop()

print(f"\n{'='*60}")
print(f"render_log_export.py tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
