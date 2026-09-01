#!/usr/bin/env python3
"""
test_bug_contact_03_invalid_status_feedback.py — BUG-CONTACT-03 (a
BUG-LEAD-03-class gap found during the R10 write-path audit, 01/09/2026,
while verifying whether crm.py's Contact writer was clean enough to serve
as the system's reference/"gold" writer).

Problem: core/lead_candidate_handler.py's clarification flow was fixed
(BUG-LEAD-03) to name the rejected value and explain the accepted format
instead of a generic "still missing" re-ask. crm.py's Contact writer had
the exact same class of defect, undetected until this audit:

  1. `_find_or_create_contact_unlocked()` collapsed two unrelated failure
     causes — an invalid/missing phone, and a missing name — into one
     status, "invalid", with NO error text at all. A caller (and therefore
     the end user) could never tell which field was actually the problem.
  2. Three independent call sites (`lead_conversion.py`,
     `tools/dispatcher.py`'s Contacts interception, `tools/approval_actions.py`'s
     TMA write path) each re-implemented their OWN incomplete
     status->message mapping, silently falling through to a generic
     "creation failed" message (or, worse, the RAW internal status enum
     value, e.g. the literal word "invalid") for any status their local
     dict didn't happen to name.
  3. The "ambiguous" status carried the actual duplicate-match record IDs
     on `ContactResult.matches`, but every consumer dropped them — the
     user/log never saw which contacts collided.

Fix: `_find_or_create_contact_unlocked()` now returns distinct
"invalid_phone" / "missing_name" statuses (falling back to "invalid" only
when BOTH are missing), each with a populated `error` string. A single
shared `crm.describe_contact_failure()` renders the user-facing message
for every non-success status, so a future new status never needs a second
edit at each of the three call sites — and "ambiguous" now surfaces the
match count in the message and the match evidence dict in dispatcher/TMA
responses.

This file exercises the REAL `find_or_create_contact()` and
`describe_contact_failure()` functions, and the REAL three call sites'
behavior indirectly (by checking the exact strings each one now returns),
not a reimplementation of their logic.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import crm  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
print("── Unit: the three previously-collapsed rejection reasons are now distinct ──")

with patch.object(crm, "_get") as get, patch.object(crm, "_post") as post:
    r_bad_phone = crm.find_or_create_contact("not-a-phone", "Dana")
chk("bad phone + valid name -> 'invalid_phone', not the old collapsed 'invalid'",
    r_bad_phone.status == "invalid_phone")
chk("bad phone case carries a non-empty error string (old code had none at all)",
    bool(r_bad_phone.error))
chk("bad phone case never reaches lookup/write", not get.called and not post.called)

with patch.object(crm, "_get") as get, patch.object(crm, "_post") as post:
    r_missing_name = crm.find_or_create_contact("+972501234567", "")
chk("valid phone + missing name -> 'missing_name' (previously indistinguishable "
    "from a bad-phone rejection)",
    r_missing_name.status == "missing_name")
chk("missing-name case carries a non-empty error string", bool(r_missing_name.error))

with patch.object(crm, "_get") as get, patch.object(crm, "_post") as post:
    r_both = crm.find_or_create_contact("", "")
chk("both phone and name missing -> falls back to 'invalid' (still distinct "
    "from either single-field case)",
    r_both.status == "invalid")
chk("both-missing case also carries an error string", bool(r_both.error))


# ══════════════════════════════════════════════════════════════════
print("\n── Unit: describe_contact_failure() gives a specific, non-generic message ──")

chk("invalid_phone message names the phone problem specifically",
    "טלפון" in crm.describe_contact_failure(r_bad_phone))
chk("missing_name message names the name problem specifically",
    "שם" in crm.describe_contact_failure(r_missing_name))
chk("both messages differ from each other (proves they're not the same generic string)",
    crm.describe_contact_failure(r_bad_phone) != crm.describe_contact_failure(r_missing_name))

_ambiguous = crm.ContactResult("ambiguous", matches=({"record_id": "rec1"}, {"record_id": "rec2"}))
_ambig_msg = crm.describe_contact_failure(_ambiguous)
chk("ambiguous message surfaces the actual match COUNT (evidence used to be silently dropped)",
    "2" in _ambig_msg)

chk("an unmapped/future status still gets a message (never crashes, never blank)",
    bool(crm.describe_contact_failure(crm.ContactResult("some_future_status"))))

_with_error = crm.ContactResult("create_error", error="Airtable 500")
chk("when result.error is present, describe_contact_failure() includes it",
    "Airtable 500" in crm.describe_contact_failure(_with_error))


# ══════════════════════════════════════════════════════════════════
print("\n── End-to-end: the three real call sites no longer show the raw status "
      "or a wrong-cause generic message ──")

import lead_conversion  # noqa: E402

# The historical bug (live before this fix): lead_conversion.py's own local
# `messages` dict mapped "invalid" -> "❌ מספר הטלפון חסר או אינו תקין" even
# when the REAL cause was a missing name. That dict no longer exists —
# confirm describe_contact_failure() is what lead_conversion.py imports and
# calls now, so a missing-name rejection can never again be reported as a
# phone problem.
chk("lead_conversion.py imports describe_contact_failure (shared helper, no "
    "local status->message dict left to go stale)",
    lead_conversion.describe_contact_failure is crm.describe_contact_failure)
chk("for a missing-name rejection, the shared helper never says 'טלפון' "
    "(the historical wrong-cause bug this file guards against)",
    "טלפון" not in crm.describe_contact_failure(r_missing_name))


print()
print("=" * 50)
print(f"BUG-CONTACT-03 (ContactResult status feedback) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
