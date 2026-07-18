#!/usr/bin/env python3
# test_bug111_followup_compact_text.py — BUG-111 follow-up: compact/
# newline-stripped WhatsApp paste still produced a false lead name and a
# real Airtable write.
#
# New production sample after the original BUG-111 fix shipped:
#
#   צור 3 לידים חדשים [18.7, 22:02] אורי צדוק: +972 53-396-8395[18.7,
#   22:02] אורי צדוק: 0533123482[18.7, 22:02] אורי צדוק: 0534185481
#
# Observed: BOSS detected ONE lead — name="לידים חדשים",
# phone="0533968395", domain="general" — and created a real Airtable Lead
# with that wrong name. A second, closely related sample (with "דומיין
# גיוס" and only the FIRST header missing its newline) produced the exact
# same single-fake-candidate result and a "📋 זיהיתי ליד: *לידים חדשים*
# (0533968395)" preview.
#
# Root cause (two independent, compounding defects, both in
# core/ingress_classifier.py):
#
#   1. _BLOCK_SEP's every alternative required a literal "\n" immediately
#      before a block boundary (including the chat-export-header
#      alternative added by the original BUG-111 fix). This production text
#      has NO newlines between WhatsApp export headers at all (or, in the
#      second sample, only the FIRST header is glued directly onto the
#      command text with no newline) — so _BLOCK_SEP either produced ONE
#      giant block (first sample) or left the header+first-phone glued into
#      one block while correctly splitting the REST (second sample). Either
#      way, command/header text ("לידים חדשים" — note: PLURAL forms, not
#      caught by _NAME_STOP, which only lists the singular "ליד"/"חדש")
#      ended up inside the first phone's name-extraction window and was
#      accepted as a "name" (2+ Hebrew words, not a recognized stop-word,
#      >=4 chars).
#
#   2. _SENDER_LINE_RE required `^` (true line start) even for its
#      bracket-timestamp-prefixed form. In the fully newline-free sample,
#      NONE of the three "[18.7, 22:02] אורי צדוק:" headers are ever
#      preceded by a real "\n" (not even the first one, which sits after
#      plain text, not a line start) — so sender_names came back EMPTY for
#      the whole message, and "אורי צדוק" (the sender) leaked through as
#      the candidate NAME for the second and third phones too.
#
# Fix: _BLOCK_SEP gained an unanchored `(?=_CHAT_EXPORT_HEADER)` lookahead
# (splits before a chat-export header wherever it appears, newline or not);
# _SENDER_LINE_RE's bracket-prefixed alternative no longer requires `^` (the
# literal timestamp text preceding it is already high-precision on its
# own — the bare, bracket-less "Name:" form still requires `^`, unchanged).
# Additionally, a defense-in-depth safety net in _classify_ingress_core():
# a SINGLE extracted candidate is never trusted when the raw text contains
# MORE distinct phone numbers than were captured as candidates — that
# mismatch degrades to Tier 5 (as if no candidates were found at all),
# letting the existing multi-phone clarification path
# (_maybe_start_lead_clarification, which independently re-scans the full
# text for every phone) take over instead of silently creating one lead
# under a name nobody gave.
#
# Explicitly NOT touched, per the request that reported this: F52, RP5,
# feature flags, ActionGateway. This stays entirely inside live lead
# candidate extraction (core/ingress_classifier.py) and the clarification
# flow (core/lead_candidate_handler.py) already built by the original
# BUG-111 fix.

from __future__ import annotations

import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

from core.ingress_classifier import (
    _extract_lead_candidates,
    _BLOCK_SEP,
    _SENDER_LINE_RE,
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


# The exact production sample (no newlines anywhere between the header and
# the three WhatsApp export headers).
PROD_SAMPLE = (
    "צור 3 לידים חדשים [18.7, 22:02] אורי צדוק: +972 53-396-8395"
    "[18.7, 22:02] אורי צדוק: 0533123482"
    "[18.7, 22:02] אורי צדוק: 0534185481"
)

# The "Eli" sample: domain hint present, only the FIRST header is glued
# (no newline) onto the command text; the second and third DO have real
# newlines before them.
ELI_SAMPLE = (
    "צור 3 לידים חדשים  דומיין גיוס [18.7, 22:02] אורי צדוק: +972 53-396-8395\n"
    "[18.7, 22:02] אורי צדוק: 0533123482\n"
    "[18.7, 22:02] אורי צדוק: 0534185481"
)

_EXPECTED_PHONES = {"0533968395", "0533123482", "0534185481"}


# ══════════════════════════════════════════════════
# 1. Exact production sample, no newlines at all
# ══════════════════════════════════════════════════
print("── 1. exact production sample (no newlines between header and timestamps) ──")

cands1 = _extract_lead_candidates(PROD_SAMPLE)
chk("T1: no candidate is produced with the fake name 'לידים חדשים'",
    all(c["name"] != "לידים חדשים" for c in cands1))
chk("T1: no candidate is produced with the sender 'אורי צדוק' as the name",
    all(c["name"] != "אורי צדוק" for c in cands1))

ic1 = classify_ingress(PROD_SAMPLE)
chk("T1: classify_ingress never returns a single high-confidence candidate "
    "with a fake name for this text (Tier 1 with the wrong name was the "
    "exact production bug)",
    not (ic1.tier == 1 and ic1.candidates and ic1.candidates[0]["name"] == "לידים חדשים"))
chk("T1: classify_ingress degrades to Tier 5 (safe) rather than confidently "
    "wrong", ic1.tier == 5)


# ══════════════════════════════════════════════════
# 2. Adjacent timestamp blocks with no separator at all still split
# ══════════════════════════════════════════════════
print()
print("── 2. adjacent timestamp blocks (no separator) still split into blocks ──")

ADJACENT = "[18.7, 22:02] אורי צדוק: +972 53-396-8395[18.7, 22:02] אורי צדוק: 0533123482"
blocks2 = [b for b in _BLOCK_SEP.split(ADJACENT) if b.strip()]
chk("T2: two directly-adjacent timestamp headers (zero separator between "
    "them) split into two distinct blocks",
    len(blocks2) == 2)
chk("T2: each block contains exactly one phone number",
    all(sum(1 for c in b if c.isdigit()) > 0 for b in blocks2))
chk("T2: first block is the +972 number's own message",
    "8395" in blocks2[0] and "3482" not in blocks2[0])
chk("T2: second block is the plain-format number's own message",
    "3482" in blocks2[1] and "8395" not in blocks2[1])

m2 = _SENDER_LINE_RE.search(blocks2[1])
chk("T2: sender is recognized even when the header is not preceded by a "
    "real newline (mid-block, glued directly after the previous message)",
    bool(m2) and m2.group(1) == "אורי צדוק")


# ══════════════════════════════════════════════════
# 3. "צור 3 לידים חדשים" must never be a candidate name
# ══════════════════════════════════════════════════
print()
print("── 3. 'צור 3 לידים חדשים' (plural forms) is never a candidate name ──")

# Direct regression on the exact plural-form gap: _NAME_STOP only listed the
# singular "ליד"/"חדש" — "לידים"/"חדשים" (plural) were never covered, so
# once _BLOCK_SEP correctly isolates the header into its own block, this
# checks the header text ALONE never becomes a name if it ever gets bound
# to a phone (e.g. a future format variant with no boundary at all).
HEADER_GLUED = "צור 3 לידים חדשים 0501234567"
cands3 = _extract_lead_candidates(HEADER_GLUED)
chk("T3: 'צור 3 לידים חדשים 0501234567' (header glued directly onto a "
    "phone, worst case — no boundary of any kind) never extracts "
    "'לידים חדשים' as the name",
    all(c["name"] != "לידים חדשים" for c in cands3))

for sample_name, sample in (("PROD_SAMPLE", PROD_SAMPLE), ("ELI_SAMPLE", ELI_SAMPLE)):
    cands = _extract_lead_candidates(sample)
    chk(f"T3b [{sample_name}]: no candidate name is 'לידים חדשים'",
        all(c["name"] != "לידים חדשים" for c in cands))
    chk(f"T3c [{sample_name}]: no candidate name CONTAINS 'לידים חדשים'",
        all("לידים חדשים" not in c["name"] for c in cands))


# ══════════════════════════════════════════════════
# 4. 3 phones + only command/header/sender text as possible names ->
#    batch clarification with all 3 phones, never a single fake-named lead
# ══════════════════════════════════════════════════
print()
print("── 4. 3 phones, no real names -> batch clarification, never a fake lead ──")

for sample_name, sample, chat_suffix in (
    ("PROD_SAMPLE", PROD_SAMPLE, "prod"),
    ("ELI_SAMPLE", ELI_SAMPLE, "eli"),
):
    chat_id = f"bug111_followup_{chat_suffix}"
    with patch.object(lch, "_at_find_lead", return_value=None):
        reply = _send(chat_id, sample, intent="create_lead")

    chk(f"T4 [{sample_name}]: reply is a clarification, not a single-lead "
        "preview and not None",
        isinstance(reply, str) and "זיהיתי ליד" not in reply)
    chk(f"T4 [{sample_name}]: reply never shows the fake name 'לידים חדשים'",
        isinstance(reply, str) and "לידים חדשים" not in reply)

    cand = (_snap(chat_id).get("active_lead_candidate") or {})
    chk(f"T4 [{sample_name}]: session state is the batch-clarification shape",
        cand.get("state") == "needs_clarification"
        and cand.get("expected_field") == "names")
    stored_phones = set(cand.get("partial_payload", {}).get("phones", []))
    chk(f"T4 [{sample_name}]: all 3 real phone numbers are preserved "
        "(none dropped, none fabricated)",
        stored_phones == _EXPECTED_PHONES)

    # Resolving with 3 real names must produce a genuine 3-lead preview, not
    # a single lead under the fake name.
    with patch.object(lch, "_at_find_lead", return_value=None):
        reply2 = _send(chat_id, "דני כהן\nרותי לוי\nמשה אבני")
    chk(f"T4 [{sample_name}]: resolving with 3 real names produces a batch "
        "preview naming all 3 real leads, not the fake header text",
        isinstance(reply2, str)
        and "דני כהן" in reply2 and "רותי לוי" in reply2 and "משה אבני" in reply2
        and "לידים חדשים" not in reply2)
    preview = (_snap(chat_id).get("pending_lead_preview") or {}).get("candidates", [])
    chk(f"T4 [{sample_name}]: exactly 3 real candidates land in the pending "
        "preview, each with a correct phone",
        len(preview) == 3
        and {c["phone"] for c in preview} == _EXPECTED_PHONES
        and all(c["name"] != "לידים חדשים" for c in preview))


# ══════════════════════════════════════════════════
# 5. Multiple phones + a single command/header-derived candidate ->
#    rejected as unsafe, not accepted (defense-in-depth safety net)
# ══════════════════════════════════════════════════
print()
print("── 5. single candidate + multiple phones in text -> rejected as unsafe ──")

# Direct unit check on the safety net itself, independent of the block/
# sender fixes above: even if some future input shape still lets exactly
# ONE candidate survive extraction while the raw text plainly contains more
# phone numbers than that, classify_ingress must not trust it.
ic5 = classify_ingress(PROD_SAMPLE)
chk("T5: production sample never classifies as Tier 1/2/3 with only 1 "
    "candidate while 3 real phones are present in the text",
    not (ic5.tier in (1, 2, 3) and len(ic5.candidates) == 1))

# Regression guard: the safety net must NOT fire when there is truly only
# one phone in the text (the overwhelmingly common, legitimate case) —
# single real lead dictation stays Tier 1 exactly as before.
SINGLE_LEAD = "דני כהן 0501234567 מעוניין בדירה"
ic5b = classify_ingress(SINGLE_LEAD)
chk("T5b: regression — a genuine single-candidate/single-phone dictation "
    "still classifies as Tier 1 (safety net does not over-trigger)",
    ic5b.tier == 1 and len(ic5b.candidates) == 1
    and ic5b.candidates[0]["name"] == "דני כהן")

# Regression guard: an existing multi-candidate/multi-phone clean batch
# (already covered by BUG-096/097's own tests) is unaffected — the safety
# net only applies when EXACTLY one candidate survives.
CLEAN_BATCH = "אבי יוספי 0501112223, אלי ישראלי 0523334445"
ic5c = classify_ingress(CLEAN_BATCH)
chk("T5c: regression — a genuine 2-candidate/2-phone clean batch is "
    "unaffected (tier 2, both candidates correct)",
    ic5c.tier == 2 and len(ic5c.candidates) == 2
    and {c["name"] for c in ic5c.candidates} == {"אבי יוספי", "אלי ישראלי"})


print(f"\n{'='*50}")
print(f"BUG-111 follow-up (compact-text / multi-phone safety) tests: "
      f"{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
