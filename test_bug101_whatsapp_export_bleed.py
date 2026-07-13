# test_bug101_whatsapp_export_bleed.py — BUG-101a/b/c (WhatsApp chat-export
# ingestion: cross-message bleed)
#
# BUG-101 (umbrella): a pasted WhatsApp chat export — several "[date, time]
# sender: text" messages concatenated into one inbound message — produced
# 5/5 wrong Lead records in production (Record IDs: rec62b86WqBpaWPaG,
# rec0n8JxF4m1wMBOt, recxNHP1uzw7ip4N1, reczrNXFy5BvwRLme, recrzwkBQwdWBv6HW).
# Three independent, co-occurring defects had to ALL be true to produce the
# symptom (Contract Chain result, see BUG_AUDIT_LOG.md):
#
#   101a — _is_tier4()/_TIMESTAMP_RE broke on invisible bidi control chars
#          (RLM/LRM — a real copy-paste-from-phone artifact, e.g.
#          "[נייד] ‏ +972 54-211-6211 ‏" from the actual production
#          text) inside the "[date, time]" bracket, letting export text that
#          SHOULD have been Tier 4 fall through into lead extraction.
#   101b — _BLOCK_SEP had no condition recognizing "[date, time] sender:" as
#          a new-message boundary, so an export header line got swallowed
#          into the PRECEDING block — the direct cause of names/phones
#          bleeding across different original WhatsApp messages.
#   101c — _SENDER_LINE_RE was anchored to `^` (line start) only, so a
#          quoted sender name preceded by an export timestamp ("[12.9.2023,
#          14:25] אורי צדוק: ...") was never recognized as a sender line and
#          leaked into candidate extraction as if "אורי צדוק" were a lead.
#
# Fix: (a) strip bidi control chars once, at the top of classify_ingress(),
# so every downstream regex sees the same clean text; (b) _BLOCK_SEP gained
# a lookahead for the export-header pattern; (c) _SENDER_LINE_RE gained an
# optional export-timestamp prefix before the existing name+colon capture.
# (a)/(b)/(c) share one _CHAT_EXPORT_TIMESTAMP sub-pattern so they can't
# drift apart on what counts as an export timestamp.
#
# Known, explicitly out-of-scope residual gap found while verifying this fix
# (not part of 101a/b/c's DoD): a hyphenated international-format phone like
# "+972 54-211-6211" (multiple internal hyphens) is not matched by _PHONE_RE
# at all — that candidate silently drops (Family C: unclear -> silent
# omission) rather than bleeding into a neighbor. Silent omission is a
# strictly safer failure mode than corruption, but is not fixed here.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.ingress_classifier import (
    _is_tier4,
    _strip_bidi_controls,
    _BLOCK_SEP,
    _SENDER_LINE_RE,
    _extract_lead_candidates,
    classify_ingress,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


RLM = "‏"

# The actual production text (reconstructed from the 5 wrong records' summary
# fields, in calendar order) — same evidence used for the Contract Chain.
PROD_REPRO = (
    "[12.9.2023, 14:25] אורי צדוק: ד טבריה מוכר במעלה עמוס\n"
    "0583290628\n"
    "לחזור אחרי החגים\n"
    "[12.9.2023, 14:38] אורי צדוק: ד דב אטינגר טבריה\n"
    "0527118045\n"
    "לחזור בערב. רוצה להתקדם.\n"
    "[12.9.2023, 14:57] אורי צדוק: [שם] ד אליאב לוי טבריה\n"
    f"[נייד] {RLM} +972 54-211-6211 {RLM}\n"
    "לחזור מיד אחרי החגים.\n"
    "[8.4.2024, 20:18] אליהו: ד שמואל טבריה\n"
    "+972527163148\n"
    "עומד להתקשר. רציני.\n"
    "[14.4.2024, 11:38] אליהו: 0533175204\n"
    "אמור להתקשר אליך. 2 חד'.\n"
    "[14.4.2024, 11:38] אליהו: ד ירמיהו ישורון טבריה\n"
    "0548410116\n"
    "[14.4.2024, 11:38] אליהו: ד שמואל טבריה\n"
    "+972527163148\n"
    "עומד להתקשר. רציני.\n"
)


# ── BUG-101a: Tier-4 hardening against invisible bidi marks ──────────────
print("── BUG-101a: bidi-control marks no longer defeat Tier-4 ──")

clean_bracket = "[12.9.2023, 14:25] אורי צדוק: hello"
bidi_bracket = f"{RLM}[12.9.2023,{RLM} 14:25]{RLM} אורי צדוק: hello"

chk("T1: clean bracket already matched Tier-4 before this fix (sanity)",
    _is_tier4(clean_bracket)[0] is True)
chk("T2: RLM-polluted bracket, UNSTRIPPED, would defeat _is_tier4 (documents the bug)",
    _is_tier4(bidi_bracket) == (False, ""))
chk("T3: after _strip_bidi_controls(), the same text IS caught as Tier-4",
    _is_tier4(_strip_bidi_controls(bidi_bracket))[0] is True)
chk("T4: _strip_bidi_controls() removes RLM/LRM but leaves ordinary text untouched",
    _strip_bidi_controls("שלום עולם") == "שלום עולם"
    and RLM not in _strip_bidi_controls(f"a{RLM}b"))
chk("T5: full production text (with embedded RLM) now classifies as Tier 4 end-to-end",
    classify_ingress(PROD_REPRO, source_type="text").tier == 4)


# ── BUG-101b: _BLOCK_SEP recognizes a chat-export header as a boundary ───
print()
print("── BUG-101b: export header starts a new block, doesn't get swallowed ──")

clean_repro = PROD_REPRO.replace(RLM, "")  # isolate 101b/c from 101a's Tier-4 short-circuit
blocks = _BLOCK_SEP.split(clean_repro)

chk("T6: at least 6 blocks produced (one per original WhatsApp message)",
    len(blocks) >= 6)
chk("T7: no block contains more than one export-timestamp header (no merge across messages)",
    all(b.count("[12.9.2023") + b.count("[8.4.2024") + b.count("[14.4.2024") <= 1
        for b in blocks))
chk("T8: 'לחזור אחרי החגים' (message 1's trailing note) is NOT in the same block as "
    "message 2's phone (0527118045) — the exact cross-message bleed from production",
    not any("לחזור אחרי החגים" in b and "0527118045" in b for b in blocks))


# ── BUG-101c: _SENDER_LINE_RE recognizes a sender preceded by a timestamp ─
print()
print("── BUG-101c: quoted sender name behind an export timestamp is recognized ──")

chk("T9: 'דני: 050...' (no prefix) still matches — regression on the existing behavior",
    bool(_SENDER_LINE_RE.search("דני: 050 1234567"))
    and _SENDER_LINE_RE.search("דני: 050 1234567").group(1) == "דני")
chk("T10: '[12.9.2023, 14:25] אורי צדוק: ...' now matches, sender captured correctly",
    bool(_SENDER_LINE_RE.search("[12.9.2023, 14:25] אורי צדוק: ד טבריה מוכר"))
    and _SENDER_LINE_RE.search("[12.9.2023, 14:25] אורי צדוק: ד טבריה מוכר").group(1) == "אורי צדוק")
chk("T11: 'אורי צדוק' (the quoted sender) does not appear as any candidate's name",
    not any(c["name"] == "אורי צדוק" for c in _extract_lead_candidates(clean_repro)))


# ── End-to-end: the specific wrong outputs from production are gone ──────
print()
print("── End-to-end: the exact wrong outputs from production no longer occur ──")

candidates = _extract_lead_candidates(clean_repro)
names = [c["name"] for c in candidates]
phones = {c["name"]: c["phone"] for c in candidates}

chk("T12: 'אחרי החגים' is not produced as any candidate's name (was דב אטינגר's phone before)",
    "אחרי החגים" not in names and "לחזור אחרי החגים" not in names)
chk("T13: 'חזור מיד אחרי החגים' is not produced as any candidate's name",
    not any("חזור מיד אחרי החגים" in n for n in names))
chk("T14: 'עומד להתקשר' is not produced as any candidate's name",
    not any("עומד להתקשר" in n for n in names))
chk("T15: דב אטינגר is captured with his own correct phone",
    phones.get("דב אטינגר") == "0527118045")
chk("T16: שמואל is captured (was silently lost entirely in production, phone deduped away)",
    "שמואל" in phones and phones["שמואל"] == "0527163148")
chk("T17: ירמיהו ישורון is captured with his own correct phone",
    phones.get("ירמיהו ישורון") == "0548410116")


# ── Regression guard: plain single-lead dictation, unaffected ────────────
print()
print("── Regression: plain (non-export) lead dictation is unaffected ──")

chk("T18: simple single-lead text still extracts correctly",
    [c["name"] for c in _extract_lead_candidates("משה יצחקוב 0501234567 מעוניין בדירה")]
    == ["משה יצחקוב"])
chk("T19: existing bullet/numbering/blank-line block boundaries still work",
    len(_extract_lead_candidates(
        "דני כהן 0501112222\n\nיוסי לוי 0523334444"
    )) == 2)


print(f"\n{'='*50}")
print(f"BUG-101a/b/c (WhatsApp export bleed) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
