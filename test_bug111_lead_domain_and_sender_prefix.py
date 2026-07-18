# test_bug111_lead_domain_and_sender_prefix.py — BUG-111 (lead batch parsing:
# domain/context text and WhatsApp sender prefixes mistaken for lead names)
#
# Three observed production-shaped bugs, all in the live extraction path
# (core/ingress_classifier.py's _extract_lead_candidates() — see BUG-096's
# own comment on why lead_candidate_handler.py's parse_batch_dictation()/
# parse_lead_dictation() cluster is dead code and must never be "fixed"
# again by mistake):
#
#   1. "צור ליד דומיין גיוס 0504025707" -> name="דומיין גיוס", domain=general.
#      Root cause: "דומיין"/the domain-hint word that follows it are not
#      stop-words, so the segment-splitting logic in
#      _extract_name_from_window() picks the "דומיין גיוס" phrase as the
#      longest surviving segment. Separately, no code anywhere recognized
#      "גיוס" (recruiting) as a routing/domain value at all — it always fell
#      back to "general".
#   2. "צור 3 לידים חדשים לדומיין גיוס\n[18.7, 22:02] אורי צדוק: ...\n..." ->
#      a batch header word leaked into a candidate name ("שים לדומיין
#      גיוס"). Root cause: the WhatsApp-style "[D.M, HH:MM]" timestamp (day.
#      month, NO year) used by these lines didn't match _CHAT_EXPORT_TIMESTAMP
#      (which required a full day.month.year), so _BLOCK_SEP never split the
#      header from the phone lines and the whole message was treated as one
#      giant block/window.
#   3. "[18.7, 22:02] אורי צדוק: 0504142604" -> name="אורי צדוק" (the WhatsApp
#      sender prefix, not a lead). Same root cause as #2 (the no-year
#      timestamp also defeats _SENDER_LINE_RE's bracket-prefix match), plus a
#      SEPARATE accidental Tier-4 "json_block" misclassification for the
#      standalone single-line case (a leading "[" was assumed to be JSON).
#
# Additional failing case (reported separately, same root families):
#   "צור ליד דומיין גיוס +972 53-396-8395" -> BOSS replies that manual lead
#   creation through chat is blocked (tools/airtable_security.py's
#   LeadsWriteGate). Root cause: _PHONE_RE didn't match a phone grouped with
#   TWO internal separators ("XX-XXX-XXXX" — mobile local, or the
#   international "+972 XX-XXX-XXXX" form; BUG-101's own comment already
#   flagged the international shape as a known, deliberately deferred gap).
#   With no phone match at all, _maybe_start_lead_clarification() (the
#   Tier-5-but-a-phone-is-present clarification path) also found nothing, so
#   handle_lead_candidate() returned None and the message fell all the way
#   through to the Agent's own tool_use loop, which attempted a direct
#   airtable_add on Leads and was correctly (but unhelpfully, from the user's
#   perspective) blocked by the gate.
#
# Fix summary (core/ingress_classifier.py unless noted):
#   - _PHONE_RE: two NEW alternatives for two-separator local ("05X-XXX-XXXX")
#     and international ("+972-XX-XXX-XXXX") numbers.
#   - _CHAT_EXPORT_TIMESTAMP: year group made optional ("[D.M, HH:MM]" now
#     matches, not just "[D.M.YYYY, HH:MM]") — fixes _BLOCK_SEP splitting and
#     _SENDER_LINE_RE's bracket-prefixed sender recognition for this format.
#   - _JSON_BLOCK_RE: no longer treats a leading "[" immediately followed by
#     a day.month digit pair as JSON.
#   - _DOMAIN_HINT_RE/_extract_domain_hint()/_strip_domain_hint(): recognizes
#     an explicit "דומיין X"/"לדומיין X" annotation, strips the WHOLE phrase
#     from the name-extraction window (never just the keyword — a lone
#     leftover hint word like "גיוס" would otherwise win an unintended
#     segment tie-break, since single-word Hebrew names are legitimately
#     supported elsewhere, see BUG-101 T16/"שמואל"), and exposes the
#     canonical routing value (e.g. "recruitment") on each candidate as
#     candidate["domain_hint"], never silently discarded.
#   - core/lead_candidate_handler.py: _detect_domain() consults the same
#     explicit hint FIRST (highest precision), then a new recruiting/גיוס
#     content pattern in _DOMAIN_PATTERNS (mirrors the existing verticals);
#     _maybe_start_lead_clarification() now normalizes the phone through
#     _normalize_phone() before storing/showing it (it was previously stored
#     as the raw regex match, spaces/dashes/"+972" and all).
#
# Follow-up fix (same file, review of the first version of this PR): the
# first version above stopped the CORRUPTION (fake names) but introduced a
# new, narrower data-loss bug of its own — a 3-phone-only batch collapsed
# into a SINGLE-phone clarification, because _maybe_start_lead_clarification()
# still only ever called _PHONE_RE.search() (first match only) instead of
# finding every distinct phone in the text. Fixed: it now uses .finditer(),
# normalizes + de-duplicates every match, and for 2+ phones stores a NEW
# batch-clarification shape (expected_field="names", partial_payload["phones"]
# = the full list — nothing dropped) with a reply that explicitly states the
# count and, when known, the domain
# ("זיהיתי 3 מספרים לדומיין גיוס, אבל חסרים שמות. איך לשמור אותם?"), plus the
# actual phone numbers themselves. A NEW _resolve_batch_name_clarification()
# resolves it: exactly one name per line, in the same order as the stored
# phones — a count mismatch or an invalid name line asks again WITHOUT
# clearing state (so a phone is never silently dropped just because the
# reply was malformed); a valid reply routes through the SAME
# _store_pending_preview()/resolve_pending_lead_preview() mechanism the
# existing Tier-2 clean-batch flow (BUG-058) already uses, rather than
# inventing a second batch-write path. That confirm-time rendering (record
# id shown inline per lead, the "עובדתי N לידים" summary header) is
# pre-existing in _handle_batch() and intentionally NOT touched by this PR —
# a separate, already-tracked F52/UX concern.
#
# Explicitly NOT touched: F52/agent_message_formatter, RP5/evidence
# finalizer, ActionGateway execution, approval policy, feature flags,
# TMA/frontend. tools/airtable_security.py's LeadsWriteGate itself is also
# untouched — the fix is that a valid candidate/clarification is now found
# BEFORE the message would ever reach the Agent's own tool_use loop, so the
# gate is simply never hit for these inputs, not that the gate's own
# behavior changed.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

from core.ingress_classifier import (
    _extract_lead_candidates,
    _extract_domain_hint,
    _normalize_phone,
    _PHONE_RE,
    _SENDER_LINE_RE,
    _BLOCK_SEP,
    classify_ingress,
)
import core.lead_candidate_handler as lch
from session_store import lead_sessions

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class MockIdentity:
    is_internal = True
    tenant_id   = "boss_hq"
    memory_key  = "boss_hq/eliyahu@owner"
    domain_id   = "general"
    role        = "owner"


identity = MockIdentity()


def _snap(chat_id: str) -> dict:
    return lead_sessions.get_or_create(chat_id)


def _send(chat_id: str, text: str, intent: str = "") -> "str | None":
    return lch.handle_lead_candidate(
        identity, text, chat_id, "telegram", intent=intent, session=_snap(chat_id),
    )


# ══════════════════════════════════════════════════
# 1. Domain/context phrase must never become the lead name
# ══════════════════════════════════════════════════
print("── 1. domain/context phrase is not mistaken for a lead name ──")

T1 = "צור ליד דומיין גיוס 0504025707"
cands = _extract_lead_candidates(T1)
chk("T1: no candidate has name 'דומיין גיוס'",
    all(c["name"] != "דומיין גיוס" for c in cands))
chk("T1: no candidate has name 'גיוס' either (the bare hint word alone)",
    all(c["name"] != "גיוס" for c in cands))
chk("T1: no candidate contains 'דומיין' anywhere in its name",
    all("דומיין" not in c["name"] for c in cands))

ic1 = classify_ingress(T1)
chk("T1: classify_ingress degrades safely (never a false Tier 1 with a wrong name)",
    ic1.tier != 1 or all(c["name"] != "דומיין גיוס" for c in ic1.candidates))

chk("T1: _detect_domain resolves the explicit hint to the canonical Leads value",
    lch._detect_domain(T1) == "recruitment")


# ══════════════════════════════════════════════════
# 2. Batch header context must not leak into any candidate name
# ══════════════════════════════════════════════════
print()
print("── 2. batch header context does not leak into a candidate name ──")

T2 = (
    "צור 3 לידים חדשים לדומיין גיוס\n"
    "[18.7, 22:02] אורי צדוק: 053-311-6744\n"
    "[18.7, 22:02] אורי צדוק: 0504142604\n"
    "[18.7, 22:02] אורي צדוק: 0504107630"
).replace("אורي", "אורי")  # keep the literal Hebrew consistent if copy/pasted oddly
cands2 = _extract_lead_candidates(T2)
chk("T2: no candidate name contains 'לדומיין' or 'דומיין'",
    all("לדומיין" not in c["name"] and "דומיין" not in c["name"] for c in cands2))
chk("T2: no candidate name is the WhatsApp sender 'אורי צדוק'",
    all(c["name"] != "אורי צדוק" for c in cands2))
chk("T2: not exactly the two wrongly-named candidates the bug produced "
    "(garbage header fragment + sender name)",
    not (len(cands2) == 2 and any("לדומיין" in c["name"] for c in cands2)))

blocks2 = [b for b in _BLOCK_SEP.split(T2) if b.strip()]
chk("T2: the header line is now split into its own block (root-cause fix)",
    len(blocks2) == 4)
chk("T2: each phone line is its own block, not merged with the header",
    all(sum(1 for _ in _PHONE_RE.finditer(b)) <= 1 for b in blocks2))


# ══════════════════════════════════════════════════
# 3. A WhatsApp sender prefix is a sender, never a lead name
# ══════════════════════════════════════════════════
print()
print("── 3. WhatsApp sender-prefix line: source_sender, not lead name ──")

T3 = "[18.7, 22:02] אורי צדוק: 0504142604"
m3 = _SENDER_LINE_RE.search(T3)
chk("T3: the sender-line pattern recognizes 'אורי צדוק' as the sender",
    bool(m3) and m3.group(1) == "אורי צדוק")

cands3 = _extract_lead_candidates(T3)
chk("T3: no candidate is produced with 'אורי צדוק' as the name",
    all(c["name"] != "אורי צדוק" for c in cands3))

# Same shape without the bracket timestamp — still a sender line, not a name.
T3b = "אורי צדוק: 0504142604"
cands3b = _extract_lead_candidates(T3b)
chk("T3b: plain 'Name: phone' (no bracket) is also never extracted as a "
    "candidate — this format is not, and was never, treated as a real lead "
    "name annotation by this module's design (see _SENDER_LINE_RE docstring)",
    cands3b == [])


# ══════════════════════════════════════════════════
# 4. Three phone-only WhatsApp lines: ALL THREE phones must be preserved
#    (not silently reduced to one, not wrongly named). This is the BUG-111
#    follow-up blocker: the first version of this fix correctly stopped the
#    fake-name/sender-as-name corruption, but _maybe_start_lead_clarification()
#    still only ever stored the FIRST phone_match, silently discarding the
#    other two into a single-phone clarification. Fixed: it now detects ALL
#    distinct phones and, for 2+, stores a batch clarification carrying
#    every one of them — never inventing names, never using the sender
#    prefix as a name, never dropping a phone.
# ══════════════════════════════════════════════════
print()
print("── 4. three phone-only lines: not two wrongly-named candidates, "
      "and no phone silently dropped ──")

cands4 = _extract_lead_candidates(T2)
chk("T4: not exactly 2 candidates with sender/garbage names (the observed bug)",
    not (len(cands4) == 2))
chk("T4: at least — if any candidates ARE produced, none is named after the sender",
    all(c["name"] != "אורי צדוק" for c in cands4))

ic4 = classify_ingress(T2)
chk("T4: classify_ingress never returns exactly the 2 wrong candidates as Tier 2",
    not (ic4.tier == 2 and len(ic4.candidates) == 2
         and any(c["name"] == "אורי צדוק" for c in ic4.candidates)))

# Per BUG-099c's existing flow: Tier 5 + a phone present + Router-confirmed
# create_lead intent asks for the missing name(s) instead of silently losing
# the request.
chat_batch = "bug111_batch"
with patch.object(lch, "_at_find_lead", return_value=None):
    reply4 = _send(chat_batch, T2, intent="create_lead")

chk("T4a: batch header + sender-prefixed phones triggers a clarification "
    "reply (not None -> would fall through toward the Agent)",
    isinstance(reply4, str))
chk("T4b: the reply explicitly mentions 3 numbers (the count, not silently "
    "reduced to 1)",
    isinstance(reply4, str) and "3" in reply4 and "מספרים" in reply4)
chk("T4c: the reply mentions the domain hint ('גיוס') too, not just the count",
    isinstance(reply4, str) and "גיוס" in reply4)
chk("T4d: none of the actual 3 normalized phone numbers is missing from the reply",
    isinstance(reply4, str)
    and "0533116744" in reply4 and "0504142604" in reply4 and "0504107630" in reply4)

snap_batch = _snap(chat_batch)
cand_batch = (snap_batch.get("active_lead_candidate") or {})
chk("T4e: session state is the new batch-clarification shape "
    "(expected_field='names', not the single-phone 'name' shape)",
    cand_batch.get("state") == "needs_clarification"
    and cand_batch.get("expected_field") == "names")
stored_phones = cand_batch.get("partial_payload", {}).get("phones", [])
chk("T4f: ALL THREE normalized phones are preserved in session state — "
    "none silently dropped",
    sorted(stored_phones) == sorted(["0533116744", "0504142604", "0504107630"]))
chk("T4g: the stored batch payload carries the recruiting domain hint",
    cand_batch.get("partial_payload", {}).get("domain") == "recruitment")

# ── Resolving the batch clarification: one name per line, in order ───────
with patch.object(lch, "_at_find_lead", return_value=None):
    reply4b = _send(chat_batch, "דני כהן\nרותי לוי\nמשה אבני")
chk("T4h: supplying 3 names (one per line) resolves into a batch preview, "
    "not a single-lead preview — no name/phone silently dropped",
    isinstance(reply4b, str)
    and "דני כהן" in reply4b and "רותי לוי" in reply4b and "משה אבני" in reply4b
    and "0533116744" in reply4b and "0504142604" in reply4b and "0504107630" in reply4b)

snap_batch2 = _snap(chat_batch)
preview = snap_batch2.get("pending_lead_preview") or {}
preview_candidates = preview.get("candidates", [])
chk("T4i: all 3 candidates (correct name+phone pairs) landed in the pending "
    "batch preview — the existing Tier-2 confirm mechanism (BUG-058), reused "
    "rather than re-invented",
    len(preview_candidates) == 3
    and {c["phone"] for c in preview_candidates}
        == {"0533116744", "0504142604", "0504107630"}
    and {c["name"] for c in preview_candidates}
        == {"דני כהן", "רותי לוי", "משה אבני"})
chk("T4j: the clarification state itself is cleared once resolved into the preview",
    _snap(chat_batch).get("active_lead_candidate") is None)

# ── Wrong name-count: state must NOT drop any phone, must ask again ───────
chat_wrong_count = "bug111_batch_wrong_count"
with patch.object(lch, "_at_find_lead", return_value=None):
    _send(chat_wrong_count, T2, intent="create_lead")
    reply_wc = _send(chat_wrong_count, "דני כהן\nרותי לוי")   # only 2 names for 3 phones
chk("T4k: a wrong name count does not silently drop a phone — it asks again",
    isinstance(reply_wc, str) and "3" in reply_wc)
still_pending = (_snap(chat_wrong_count).get("active_lead_candidate") or {}) \
    .get("partial_payload", {}).get("phones", [])
chk("T4l: after a wrong-count reply, all 3 phones are STILL preserved in "
    "session state (not reduced to 2, not cleared)",
    sorted(still_pending) == sorted(["0533116744", "0504142604", "0504107630"]))

# ── Cancellation still works for the batch shape ──────────────────────────
chat_cancel_batch = "bug111_batch_cancel"
with patch.object(lch, "_at_find_lead", return_value=None):
    _send(chat_cancel_batch, T2, intent="create_lead")
    reply_cancel = _send(chat_cancel_batch, "בטל")
chk("T4m: cancelling a batch clarification returns the standard cancel message",
    reply_cancel == "ביטלתי את יצירת הליד.")
chk("T4n: cancelling clears the batch clarification state",
    _snap(chat_cancel_batch).get("active_lead_candidate") is None)


# ══════════════════════════════════════════════════
# 5. Repeated sender prefix does not collapse distinct people into one
# ══════════════════════════════════════════════════
print()
print("── 5. repeated sender prefix does not merge distinct leads ──")

T5 = (
    "[18.7, 22:02] אורי צדוק: דני כהן 0501112222\n"
    "[18.7, 22:02] אורי צדוק: רותי לוי 0522223333\n"
    "[18.7, 22:02] אורי צדוק: משה אבני 0533334444"
)
cands5 = _extract_lead_candidates(T5)
names5 = sorted(c["name"] for c in cands5)
phones5 = {c["name"]: c["phone"] for c in cands5}
chk("T5: three distinct candidates extracted (not collapsed into one/two)",
    len(cands5) == 3)
chk("T5: all three real names recovered correctly",
    names5 == ["דני כהן", "משה אבני", "רותי לוי"])
chk("T5: none of the three candidates is named after the repeated sender",
    all(c["name"] != "אורי צדוק" for c in cands5))
chk("T5: each candidate keeps their own distinct phone (not merged)",
    phones5.get("דני כהן") == "0501112222"
    and phones5.get("רותי לוי") == "0522223333"
    and phones5.get("משה אבני") == "0533334444")


# ══════════════════════════════════════════════════
# 6. Domain/routing hint is preserved separately from the name
# ══════════════════════════════════════════════════
print()
print("── 6. domain/routing hint preserved separately from name ──")

T6 = "צור ליד לדומיין גיוס דני כהן 0501112222"
cands6 = _extract_lead_candidates(T6)
chk("T6: the real name is still extracted correctly alongside the hint",
    len(cands6) == 1 and cands6[0]["name"] == "דני כהן")
chk("T6: the candidate carries the canonical domain hint separately",
    len(cands6) == 1 and cands6[0].get("domain_hint") == "recruitment")
chk("T6: the hint word never appears inside the name itself",
    len(cands6) == 1 and "גיוס" not in cands6[0]["name"]
    and "דומיין" not in cands6[0]["name"])

chk("T6b: _extract_domain_hint() itself resolves 'לדומיין גיוס' (attached ל-prefix)",
    _extract_domain_hint("לדומיין גיוס") == "recruitment")
chk("T6c: _extract_domain_hint() returns None when no explicit annotation is present",
    _extract_domain_hint("דני כהן 0501112222") is None)


# ══════════════════════════════════════════════════
# 7. Regression guard: "שם: טלפון" is not (and was never) a supported
#    name:phone dictation format — this module always treats text before a
#    colon as a SENDER, never as an explicit lead-name annotation. Confirms
#    that stays true (no accidental flip introduced by this fix).
# ══════════════════════════════════════════════════
print()
print("── 7. regression: 'שם: טלפון' stays sender-prefix, never a lead name ──")

chk("T7: 'דני כהן: 0501234567' still produces no candidate (unsupported format, unchanged)",
    _extract_lead_candidates("דני כהן: 0501234567") == [])
chk("T7b: a real (non-colon) dictation with the same name+phone still works normally",
    [c["name"] for c in _extract_lead_candidates("דני כהן 0501234567")] == ["דני כהן"])


# ══════════════════════════════════════════════════
# Additional failing case — "+972 53-396-8395" (hyphenated intl format)
# ══════════════════════════════════════════════════
print()
print("── Additional case: hyphenated +972 phone, no direct-write denial ──")

T8 = "צור ליד דומיין גיוס +972 53-396-8395"

m8 = _PHONE_RE.search(T8)
chk("T8: +972 phone with spaces/hyphens is recognized at all",
    bool(m8))
chk("T8: normalizes to the local canonical format (0 + 9 digits, no separators)",
    bool(m8) and _normalize_phone(m8.group()) == "0533968395")

cands8 = _extract_lead_candidates(T8)
chk("T8: the domain hint is not treated as the lead name "
    "(no candidate named 'דומיין גיוס' or 'גיוס')",
    all(c["name"] not in ("דומיין גיוס", "גיוס") for c in cands8))

chk("T8: _detect_domain resolves to the canonical recruiting value",
    lch._detect_domain(T8) == "recruitment")

with patch.object(lch, "_at_find_lead", return_value=None):
    reply8 = _send("bug111_intl_phone", T8, intent="create_lead")

chk("T8: missing name triggers clarification/confirmation, not a bare None "
    "(which would fall through toward the Agent's own tool_use loop)",
    isinstance(reply8, str))
chk("T8: the clarification asks for the missing name with the CORRECT, "
    "normalized phone number",
    isinstance(reply8, str) and "0533968395" in reply8)
chk("T8: the LeadsWriteGate direct-denial message is NOT what the user sees "
    "(a valid clarification was found before ever reaching the Agent/gate)",
    isinstance(reply8, str)
    and "יצירת ליד חדש ידנית דרך הצ׳אט חסומה כרגע" not in reply8)

snap8 = _snap("bug111_intl_phone")
cand8 = snap8.get("active_lead_candidate") or {}
chk("T8: the stored clarification payload has the normalized phone",
    cand8.get("partial_payload", {}).get("phone") == "0533968395")
chk("T8: the stored clarification payload carries the recruiting domain hint",
    cand8.get("partial_payload", {}).get("domain") == "recruitment")


print(f"\n{'='*50}")
print(f"BUG-111 (lead batch parsing: domain context / sender prefix) tests: "
      f"{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
