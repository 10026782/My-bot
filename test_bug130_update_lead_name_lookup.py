# test_bug130_update_lead_name_lookup.py — BUG-130 (explicit update intent
# routed into a new-lead preview instead of resolving the existing record)
#
# Production repro: "תעדכן את הטלפון של דני לוי" / "תעדכן את הטלפון של משה
# חביב ל-0501112222" — the owner expected an UPDATE of the existing lead's
# phone field. The system instead treated it as a brand-new lead and showed
# the create-preview ("📋 זיהיתי ליד: ...") instead of the update-preview
# ("📋 מצאתי ליד קיים: ...").
#
# Contract Chain (see BUG_AUDIT_LOG.md BUG-130 for the full trace):
#   1. core/router/intent_router.py's UPDATE_LEAD pattern required the
#      LITERAL word "ליד"/"lead" — "תעדכן את הטלפון של X" (no such word)
#      fell through every rule straight to Intent.UNKNOWN.
#   2. Even when intent WAS correctly detected, core/lead_candidate_handler.
#      py's Tier-1 dispatch (handle_lead_candidate -> _handle_single_
#      candidate) never received `intent` at all — dropped it silently.
#   3. _at_find_lead(name, phone) (BUG-094) requires an EXACT phone match to
#      call a record "the same lead" — but in an update, the phone in the
#      message IS THE NEW VALUE, different by definition from what's on
#      file, so the exact-match guard can never find the record it should
#      be updating.
#
# Fix (two independent, minimal changes):
#   A. intent_router.py: a new UPDATE_LEAD rule matching an update verb +
#      a phone-ish noun + "של" (anchoring the field to a PERSON), without
#      requiring the word "ליד"/"lead".
#   B. lead_candidate_handler.py: `intent` is now threaded through
#      _handle_single_candidate() and _propose_lead_write() (the call that
#      actually decides airtable_update vs airtable_add for the dispatched
#      ActionContract). A NEW _at_find_lead_by_name_only() is consulted as
#      a fallback ONLY when intent == Intent.UPDATE_LEAD and the exact-
#      match lookup found nothing, and ONLY returns a record when the name
#      match is UNAMBIGUOUS (exactly 1 record) — 0 or 2+ matches fall back
#      to the original, safe "can't find it, treat as new" behavior. The
#      default create/lookup path (no confirmed update intent) never calls
#      this fallback at all, so BUG-094's cross-lead-contamination guard is
#      untouched there.
#
# Out of scope (explicitly, per BUG_AUDIT_LOG.md): no disambiguation UI for
# the 2+-matches case, no change to Tier 2/3 (batch) lookup, no change to
# _write_one_lead()'s own (separate, auto-write-only) _at_find_lead() call.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import uuid
from unittest.mock import patch

from core.router.intent_router import detect_intent
from core.router.route_decision import Intent
import core.lead_candidate_handler as lch
from session_store import lead_sessions

passed = failed = 0
_RUN = uuid.uuid4().hex[:10]


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
# A. Router: "תעדכן את הטלפון של X" now classified as UPDATE_LEAD
# ══════════════════════════════════════════════════
print("── A. intent_router: update-phone-of-a-person phrasing ──")

for text in (
    "תעדכן את הטלפון של דני לוי",
    "תעדכן את הטלפון של משה חביב ל-0501112222",
    "תעדכן טלפון של ביבי נתניהו ל053434444",
    "עדכן את המספר של רותי כהן",
):
    intent, conf, _ = detect_intent(text)
    chk(f"T1: '{text}' -> UPDATE_LEAD (conf={conf})",
        intent == Intent.UPDATE_LEAD and conf >= 0.75)

# Regression: existing CREATE_LEAD / UNKNOWN classifications untouched
chk("T2: 'תוסיף ליד חדש משה כהן טלפון 0501112222' still CREATE_LEAD",
    detect_intent("תוסיף ליד חדש משה כהן טלפון 0501112222")[0] == Intent.CREATE_LEAD)
chk("T3: 'ספר לי משהו מעניין' still UNKNOWN",
    detect_intent("ספר לי משהו מעניין")[0] == Intent.UNKNOWN)
chk("T4: 'עדכן ליד דני לוי' (the pre-existing literal-ליד rule) still UPDATE_LEAD",
    detect_intent("עדכן ליד דני לוי")[0] == Intent.UPDATE_LEAD)


# ══════════════════════════════════════════════════
# B. _at_find_lead_by_name_only(): unambiguous-only name lookup
# ══════════════════════════════════════════════════
print()
print("── B. _at_find_lead_by_name_only(): single match only, never guesses ──")


class _FakeResponse:
    def __init__(self, records):
        self.status_code = 200
        self._records = records

    def json(self):
        return {"records": self._records}


with patch("httpx.get", return_value=_FakeResponse([{"id": "recSingleMatch111"}])):
    chk("T5: exactly 1 name match -> returns its record id",
        lch._at_find_lead_by_name_only("דני לוי") == "recSingleMatch111")

with patch("httpx.get", return_value=_FakeResponse([])):
    chk("T6: 0 matches -> None",
        lch._at_find_lead_by_name_only("שם לא קיים") is None)

with patch("httpx.get", return_value=_FakeResponse(
        [{"id": "recA"}, {"id": "recB"}])):
    chk("T7: 2+ matches (ambiguous, same name different people) -> None, "
        "never guesses which one",
        lch._at_find_lead_by_name_only("דני לוי") is None)


# ══════════════════════════════════════════════════
# C. End-to-end: explicit update intent resolves the EXISTING lead
# ══════════════════════════════════════════════════
print()
print("── C. handle_lead_candidate(): explicit update intent finds the "
      "existing lead by name when the exact-phone match fails ──")

chat_c = f"bug130_update_{_RUN}"
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_at_find_lead_by_name_only", return_value="recExisting222") as _mock_name_only:
    reply_c = _send(chat_c, "תעדכן את הטלפון של דני לוי ל0501112222", intent=Intent.UPDATE_LEAD)

chk("T8: the fallback name-only lookup was actually consulted",
    _mock_name_only.called)
chk("T9: reply is the EXISTING-lead preview ('מצאתי ליד קיים'), not a new-lead preview",
    isinstance(reply_c, str) and "מצאתי ליד קיים" in reply_c)
chk("T10: reply does NOT say '📋 זיהיתי ליד' (the new-lead wording)",
    isinstance(reply_c, str) and "זיהיתי ליד" not in reply_c)
chk("T11: reply carries the correct name and (new) phone",
    isinstance(reply_c, str) and "דני לוי" in reply_c and "0501112222" in reply_c)


# ══════════════════════════════════════════════════
# D. Regression: default path (no confirmed update intent) is UNCHANGED —
#    BUG-094's cross-lead-contamination guard stays fully intact
# ══════════════════════════════════════════════════
print()
print("── D. Regression: without a confirmed update intent, the name-only "
      "fallback is never consulted — behaves exactly as before BUG-130 ──")

chat_d = f"bug130_no_intent_{_RUN}"
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_at_find_lead_by_name_only", return_value="recExisting222") as _mock_name_only_d:
    reply_d = _send(chat_d, "תעדכן את הטלפון של דני לוי ל0501112222", intent="")

chk("T12: with NO confirmed update intent, the name-only fallback is NEVER called",
    not _mock_name_only_d.called)
chk("T13: reply falls back to the ORIGINAL new-lead preview wording",
    isinstance(reply_d, str) and "זיהיתי ליד" in reply_d)


# ══════════════════════════════════════════════════
# E. Regression: an unambiguous exact-phone match still wins outright —
#    the name-only fallback is never even reached when it's not needed
# ══════════════════════════════════════════════════
print()
print("── E. Regression: exact phone match already found -> fallback skipped ──")

chat_e = f"bug130_exact_match_{_RUN}"
with patch.object(lch, "_at_find_lead", return_value="recExactPhoneMatch333"), \
     patch.object(lch, "_at_find_lead_by_name_only") as _mock_name_only_e:
    reply_e = _send(chat_e, "תעדכן את הטלפון של דני לוי ל0501112222", intent=Intent.UPDATE_LEAD)

chk("T14: exact-phone match already succeeded -> name-only fallback never called",
    not _mock_name_only_e.called)
chk("T15: reply is still the existing-lead preview",
    isinstance(reply_e, str) and "מצאתי ליד קיים" in reply_e)


# ══════════════════════════════════════════════════
# F. Regression: ambiguous name match under update intent -> safe fallback
#    to "can't find it, treat as new" (no guessing which record was meant)
# ══════════════════════════════════════════════════
print()
print("── F. Regression: ambiguous name match under update intent never "
      "guesses -> falls back to new-lead preview, same as before the fix ──")

chat_f = f"bug130_ambiguous_{_RUN}"
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_at_find_lead_by_name_only", return_value=None):
    # Distinct name/phone from test D — same tenant+tool(airtable_add)+payload
    # would otherwise collide on the Gateway's own dedup-by-fingerprint check
    # (a real "already proposed this exact action" dedup, not a BUG-130 bug).
    reply_f = _send(chat_f, "תעדכן את הטלפון של יוסי אלון ל0507654321", intent=Intent.UPDATE_LEAD)

chk("T16: ambiguous/no-match name lookup falls back to the new-lead preview, "
    "never a silent wrong-record update",
    isinstance(reply_f, str) and "זיהיתי ליד" in reply_f)


print(f"\n{'='*50}")
print(f"BUG-130 (update-intent lead lookup) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
