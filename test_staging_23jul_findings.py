# test_staging_23jul_findings.py — regression tests for the TurnCoordinator
# staging session findings, 2026-07-23 (my-bot-approval-staging,
# boss_hq:eliyahu@owner, 13:15:35-13:16:58, policy_snapshot_version=
# phase0-static-v1 — all pre-existing production/staging behavior, not a
# TurnCoordinator/Shadow Decision artifact).
#
# See docs/architecture/action-gateway/
# STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md for the full Cross-Layer Impact
# Matrix and root-cause writeup. Covers three of the six findings that were
# fixed directly (the others were either already fixed on main before the
# TTL bug resurfaced them — see the audit doc — or require an owner decision
# and are documented, not implemented, here):
#
#   Finding #1 (P0) — ExecutionLedger.find_live_by_user()'s warm-cache path
#   never re-applied CONTRACT_PENDING_TTL_SECONDS/_is_expired(), unlike the
#   durable repository's own recovery path — a "pending" contract that
#   outlived the 24h TTL kept showing up as live once cached. Also verifies
#   the age-warning suffix now shown on every multi-item listing.
#
#   Finding #3 (P1) — approve() via route_disambiguation()/route_combined_word()
#   silently rejected sibling contracts with no disclosure to the user.
#
#   Finding #4 (P1) — a natural-language "what's pending approval?" question
#   used to fall through to the general agent instead of a deterministic
#   ActionContracts-backed answer.

import sys
import time

from core.action_gateway import ActionGateway, ExecutionLedger, action_gateway
from core.action_contract_repository import CONTRACT_PENDING_TTL_SECONDS

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _make_gw():
    executions = []

    def _executor(tool_name, tool_inputs, contract_id):
        executions.append(tool_name)
        return {"ok": True, "external_id": "rec00000000000001", "tool": tool_name}

    gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_executor)
    return gw, executions


def _propose(gw, user_id, tool_name, chat_id="tg:1"):
    return gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=user_id,
        tool_name=tool_name, tool_inputs={"table": "Tasks", "row": tool_name},
        origin_channel="telegram", origin_chat_id=chat_id,
        requires_approval=True,
        trusted_source="test_harness",
    )


# ══════════════════════════════════════════════════
# Finding #1 — warm-cache TTL enforcement
# ══════════════════════════════════════════════════
print("\n── Finding #1: find_live_by_user() enforces TTL on the warm-cache path ──")
gw, _ = _make_gw()
r1 = _propose(gw, "boss_hq:u1", "airtable_add")
chk("propose succeeds", r1.ok)

live_before = gw.find_live_contracts("boss_hq:u1")
chk("fresh contract is live", len(live_before) == 1)

# Backdate the cached contract past CONTRACT_PENDING_TTL_SECONDS without
# touching the repository (no repository wired here) — this reproduces the
# exact staging bug: an in-RAM "pending" contract that has aged out.
stale_contract = gw.find_contract(r1.contract_id)
stale_contract.created_at = time.time() - CONTRACT_PENDING_TTL_SECONDS - 60

live_after = gw.find_live_contracts("boss_hq:u1")
chk("expired-but-still-'pending'-status contract no longer returned as live",
    live_after == [])

# A contract inside the TTL window must still be returned (no over-filtering).
gw2, _ = _make_gw()
r2 = _propose(gw2, "boss_hq:u2", "airtable_add")
fresh_contract = gw2.find_contract(r2.contract_id)
fresh_contract.created_at = time.time() - (CONTRACT_PENDING_TTL_SECONDS - 3600)
chk("a contract just inside the TTL window is still live",
    len(gw2.find_live_contracts("boss_hq:u2")) == 1)


# ══════════════════════════════════════════════════
# Finding #1 (interim mitigation) — age warning on multi-item listings
# ══════════════════════════════════════════════════
print("\n── Finding #1 mitigation: age warning shown on stale-but-live items ──")
gw3, _ = _make_gw()
r_old = _propose(gw3, "boss_hq:u3", "airtable_add")
r_new = _propose(gw3, "boss_hq:u3", "gmail_send_draft")
old_contract = gw3.find_contract(r_old.contract_id)
old_contract.created_at = time.time() - (3 * 3600)  # 3h old — inside 24h TTL

listing = gw3.route_confirmation_word("boss_hq:u3", approver_role="owner")
chk("multi-item listing shows the numbered list", "יש כמה פעולות" in listing)
chk("stale (3h old) item is annotated with an age warning", "⚠️" in listing and "3 שעות" in listing)
lines = listing.splitlines()
new_item_line = next(l for l in lines if "gmail_send_draft" in l or "2." in l)


# ══════════════════════════════════════════════════
# Finding #3 — disclosure when siblings are auto-rejected
# ══════════════════════════════════════════════════
print("\n── Finding #3: disclosure text on mass sibling-rejection ──")
gw4, executions4 = _make_gw()
r1 = _propose(gw4, "boss_hq:u4", "airtable_add")
r2 = _propose(gw4, "boss_hq:u4", "gmail_send_draft")
r3 = _propose(gw4, "boss_hq:u4", "calendar_create_event")

# force the numbered-list/disambiguation state exactly as route_confirmation_word() does
gw4.route_confirmation_word("boss_hq:u4", approver_role="owner")
reply = gw4.route_disambiguation("boss_hq:u4", "2", approver_role="owner")
chk("route_disambiguation: targeted contract executed", executions4 == ["gmail_send_draft"])
chk("route_disambiguation: disclosure mentions the 2 auto-rejected siblings",
    reply is not None and "2 פעולות נוספות" in reply and "בוטלו אוטומטית" in reply)

gw5, executions5 = _make_gw()
r1b = _propose(gw5, "boss_hq:u5", "airtable_add")
r2b = _propose(gw5, "boss_hq:u5", "gmail_send_draft")
reply_combined = gw5.route_combined_word("boss_hq:u5", "כן 1", approver_role="owner")
chk("route_combined_word confirm: disclosure mentions the 1 auto-rejected sibling",
    reply_combined is not None and "1 פעולות נוספות" in reply_combined and "בוטלו אוטומטית" in reply_combined)

# Single live contract (no siblings) must NOT get a disclosure suffix.
gw6, _ = _make_gw()
r_solo = _propose(gw6, "boss_hq:u6", "airtable_add")
gw6.route_confirmation_word("boss_hq:u6", approver_role="owner")  # sets disambiguation? no — single resolves directly
reply_solo = gw6.route_disambiguation("boss_hq:u6", "1", approver_role="owner")
# route_confirmation_word() on a single live contract resolves directly and never
# populates self._disambiguation, so route_disambiguation() here correctly sees
# no pending state and returns None — asserting that no disclosure text leaks in.
chk("no disambiguation state left over for a single-contract resolution",
    reply_solo is None)


# ══════════════════════════════════════════════════
# Review finding #4 — disclosure count must come from CONFIRMED transitions
# only, never a pre-loop assumption. rejected_siblings is incremented inside
# the loop, strictly after reject()'s own "🚫" success confirmation — if any
# single sibling rejection fails to confirm, the (pre-existing, not touched
# by this session) `if not rejection.startswith("🚫"): return rejection`
# guard aborts the whole call immediately: no approval, no disclosure, no
# partial/misleading count. This test simulates that failure directly.
# ══════════════════════════════════════════════════
print("\n── Review finding #4: disclosure never overclaims on a failed sibling-reject ──")
gw4b, executions4b = _make_gw()
ra = _propose(gw4b, "boss_hq:u4b", "airtable_add")
rb = _propose(gw4b, "boss_hq:u4b", "gmail_send_draft")
rc = _propose(gw4b, "boss_hq:u4b", "calendar_create_event")
gw4b.route_confirmation_word("boss_hq:u4b", approver_role="owner")

# Force reject() itself to fail (durable-write failure, not a stale-status
# skip) for exactly one sibling — a monkeypatch is the only way to reach
# this path deterministically: mutating .status directly instead would just
# make the pre-loop "sibling.status == 'pending'" check skip it silently
# (a different, already-correct behavior — confirmed while writing this test).
_real_reject = gw4b.reject
def _flaky_reject(contract_id, rejected_by=""):
    if contract_id == rb.contract_id:
        return "❌ לא ניתן לשמור את ביטול הפעולה באופן עמיד. הפעולה לא סומנה כמבוטלת."
    return _real_reject(contract_id, rejected_by=rejected_by)
gw4b.reject = _flaky_reject

reply_partial = gw4b.route_disambiguation("boss_hq:u4b", "1", approver_role="owner")
chk("a failed sibling-reject aborts immediately — no approval happened",
    executions4b == [])
chk("a failed sibling-reject surfaces the raw error, not a disclosure count",
    reply_partial is not None and "פעולות נוספות" not in reply_partial and "לא ניתן לשמור" in reply_partial)
chk("the originally-targeted contract was never approved on partial failure",
    gw4b.find_contract(ra.contract_id).status == "pending")
chk("the sibling whose reject() didn't fail is untouched (no partial mutation)",
    gw4b.find_contract(rc.contract_id).status == "pending")


# ══════════════════════════════════════════════════
# Finding #4 — describe_pending_queue() deterministic listing
# ══════════════════════════════════════════════════
print("\n── Finding #4: describe_pending_queue() read-only listing ──")
gw7, executions7 = _make_gw()
empty_reply = gw7.describe_pending_queue("boss_hq:u7")
chk("no pending → informative empty message, not a crash", empty_reply is not None)
chk("no pending → does not silently imply completeness (review finding #3)",
    "legacy" in empty_reply or "ActionContracts בלבד" in empty_reply)

r1c = _propose(gw7, "boss_hq:u7", "airtable_add")
r2c = _propose(gw7, "boss_hq:u7", "gmail_send_draft")
queue_text = gw7.describe_pending_queue("boss_hq:u7")
chk("lists both pending contracts", "1." in queue_text and "2." in queue_text)
chk("describe_pending_queue never executes/rejects anything", executions7 == [])
chk("both contracts still pending after a pure listing query",
    gw7.find_contract(r1c.contract_id).status == "pending" and
    gw7.find_contract(r2c.contract_id).status == "pending")
chk("review finding #3: reply explicitly scopes itself to ActionContracts, "
    "never implies coverage of legacy _pending_approvals/event_bus stores",
    "legacy" in queue_text)

# A follow-up bare ordinal after the query must resolve via route_disambiguation()
# exactly like it would after route_confirmation_word()'s own listing.
follow_up = gw7.route_disambiguation("boss_hq:u7", "2", approver_role="owner")
chk("follow-up '2' after describe_pending_queue() resolves the right contract",
    executions7 == ["gmail_send_draft"])
chk("follow-up disclosure mentions the 1 auto-rejected sibling",
    follow_up is not None and "1 פעולות נוספות" in follow_up)


# ══════════════════════════════════════════════════
# Finding #4 — _PENDING_QUERY_RE trigger phrasing (app.py)
# ══════════════════════════════════════════════════
print("\n── Finding #4: _PENDING_QUERY_RE matches natural-language pending-approval queries ──")
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-staging-findings-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:STAGING_FINDINGS_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patStagingFindingsTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appStagingFindingsTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "999999999")

import app  # noqa: E402

for text in (
    "לאשר את הפעולות שממתינות לאישור",
    "מה ממתין לאישור",
    "אילו פעולות ממתינות",
    "רשימת פעולות ממתינות",
):
    chk(f"matches: {text!r}", app._PENDING_QUERY_RE.search(text) is not None)

for text in (
    "מאשר",  # exact confirm word — handled by a different branch, not this one
    "כן",
    "מה קורה היום",
    "תוסיף איש קשר בדיקה טלפון 0500000000",
):
    chk(f"does NOT match: {text!r}", app._PENDING_QUERY_RE.search(text) is None)


# ══════════════════════════════════════════════════
# Review finding: describe_pending_queue()'s call site must not log raw user
# text or reply content (RP5/TurnCoordinator-Shadow sampling hygiene) —
# structural source check, since exercising the actual logger.info() call
# requires the full Flask/Telegram-mocked app.py request path.
# ══════════════════════════════════════════════════
print("\n── Review finding: describe_pending_queue() log line is PII-free ──")
import inspect
_app_source = inspect.getsource(app)
_pq_log_start = _app_source.index('"[ActionGateway] describe_pending_queue:')
_pq_log_line = _app_source[_pq_log_start:_pq_log_start + 200]
chk("log format string does not interpolate raw user text",
    "text=%.40r" not in _pq_log_line and "_stripped" not in _pq_log_line)
chk("log format string does not interpolate reply content",
    "reply=%.60s" not in _pq_log_line and "_pq_reply," not in _pq_log_line)
chk("log format string uses the structured PII-free fields instead",
    "pending_count=%d" in _pq_log_line
    and "scope=action_contracts" in _pq_log_line
    and "result_code=%s" in _pq_log_line)


print(f"\n{'='*50}")
print(f"Staging 23/07/2026 findings tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
