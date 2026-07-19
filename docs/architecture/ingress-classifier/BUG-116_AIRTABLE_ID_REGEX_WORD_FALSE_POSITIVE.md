# BUG-116 — Tier-4 `_AIRTABLE_ID_RE` false-positives on plain English words

**Status:** ✅ Fixed, tests green (15 new + full 138-file regression sweep clean), **not yet production-verified**.
**Scope:** narrow regex tightening in `core/ingress_classifier.py` only. Not related to BUG-114/BUG-115 (ActionGateway/ActionContract confirmation routing) — this is a Tier-4 ingress-classification false positive that blocks a message *before* routing/lead-extraction ever runs.

## 1. Production evidence

```
Eli: צור ליד חדש לדומיין recruitment
     יהודה גרוס  0533968395

BOSS: 📄 זה נראה כמו טבלה/ייצוא/פלט מודבק — לא ביצעתי שום פעולה אוטומטית.
      אם התכוונת לבקש משהו ספציפי, כתוב את זה במשפט רגיל.
```

Repeated verbatim on a second identical attempt, and again on a third rephrased attempt ("זה משפט רגיל צור ליד").

Log line:
```
[IngressClassifier] tier=4 conf=1.00 class=table reason=airtable_id candidates=0 chat=boss_hq:eliyahu
[Route] ... handler=clarify confidence=0.95
[LCH] Tier 4 — not a lead dictation (reason=airtable_id), skip
```

A plain, unambiguous lead-creation sentence with a real name and real phone number never reached lead extraction — `classify_ingress()` short-circuited to Tier 4 before any candidate parsing ran.

## 2. Root cause

`core/ingress_classifier.py:90` (before fix):

```python
_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)[A-Za-z0-9]{8,}\b")
```

This is meant to catch a real Airtable record/field ID (`recXXXXXXXXXXXXXX`, always `rec`/`fld` + 14 base62 chars) leaking into pasted export/log text — a legitimate, strong Tier-4 signal used elsewhere in this codebase's own verification logic (`core/action_gateway.py:684`, `core/anti_hallucination.py:27`, both `rec[A-Za-z0-9]{14}` exact).

But the ingress-classifier's copy has **no upper bound and no shape constraint** — any word starting with `rec`/`fld` followed by 8 or more letters matches, real ID or not. `recruitment` = `rec` + `ruitment` (8 letters) → matches. Confirmed directly:

```python
>>> _AIRTABLE_ID_RE.search("צור ליד חדש לדומיין recruitment \nיהודה גרוס  0533968395")
<re.Match object; span=(20, 31), match='recruitment'>
```

Any English word starting with `rec`/`fld` followed by 8+ letters is affected: `recruitment`, `recommendation`, `reconnect`, `reciprocity`, `fieldwork`, etc. — independent of any other Hebrew content in the message.

Note: this is a different word than the codebase's usual convention. BUG-111's own domain-hint tests (`test_bug111_lead_domain_and_sender_prefix.py`) only ever type the **Hebrew** hint `"גיוס"` in raw message text; `"recruitment"` there only appears as the *canonical value* `_detect_domain()`/`_extract_domain_hint()` resolve to internally, never as literal user-typed text. This production message is the first observed case of the **English** word itself being typed directly as the domain hint — an edge case existing tests never exercised.

## 3. Why a tighter length/exact-shape bound alone would have broken existing tests

The obvious first fix — matching the codebase's other Airtable-ID regexes exactly (`rec[A-Za-z0-9]{14}`, fixed length) — was tried and rejected: `test_c89_tier4_precedence.py`'s existing "Airtable rec ID" fixture uses a *synthetic* fake ID, `recABC1234567890`, whose tail is only **13** characters (`ABC1234567890`), not 14. Requiring an exact 14-char tail would have broken that pre-existing, already-merged test for no reason related to this bug.

## 4. Fix

Require the matched alphanumeric run to contain **at least one digit**, via a lookahead, instead of bounding its length exactly:

```python
_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{8,}\b")
```

Rationale: every genuine-ID fixture already relied on across this test suite mixes letters and digits (`recABC1234567890`, `recRvK6hFTNgyj8ag`, `rec3YS5Zcr2FenX7z`, `rec62b86WqBpaWPaG`, `recTIER3TESTREC001`, `recRAWOBS0000001`, ...) — verified programmatically across every Tier-4-relevant fixture in the suite before implementing. A plain English word never contains a digit. This is a pure tightening of a false-positive-prone gate, not a new mechanism:

- `recruitment`, `recommendation`, `reconnect`, `reciprocity`, `fieldwork` → no longer match (no digit in the run).
- `recABC1234567890`, `recRvK6hFTNgyj8ag`, real pasted Airtable IDs → still match (digit present).

**Residual risk (accepted, out of scope):** a genuine random-base62 Airtable ID that happens to contain zero digits in its 14-char tail is theoretically possible (~6.5% probability for a uniformly random string) and would now be missed by this specific signal alone — but Tier-4 detection is defense-in-depth; such a paste would still very likely trip one of the other Tier-4 signals in the same function (`"airtable"` literal + colon/newline, `_LITERAL_MARKERS`, table/CSV/timestamp patterns) before ever reaching lead extraction. Not addressed here — narrow fix only.

**Explicitly out of scope:** `core/agent_message_formatter.py:106`'s separate `_AIRTABLE_ID_RE = re.compile(r"\brec[A-Za-z0-9]{10,}\b")` — used for redacting record IDs from *agent-facing output* text, a different risk profile (over-redaction of an output word, not a full input-blocking refusal) and a different call site. Not touched by this fix; flagged here for awareness only.

## 5. Verification

- New `test_bug116_airtable_id_word_false_positive.py` (15 checks): exact production reproduction now classifies as tier≠4 with a real candidate extracted; a set of other `rec`/`fld`-prefixed English words confirmed non-matching; all pre-existing real-ID fixtures from this suite confirmed still matching; the pre-existing genuine-pasted-ID scenario (`test_c89_tier4_precedence.py`'s "Airtable rec ID" case, `recABC1234567890`) confirmed still triggers tier=4 end-to-end.
- `test_c89_tier4_precedence.py` (13 checks, pre-existing) re-run clean — no regression to any Tier-4 marker.
- Full regression sweep: all 138 `test_*.py` files, exit 0, no failures.
- `smoke_tests.py` PASS, `python3 -m compileall -q .` clean, `git diff --check` clean.
- **Not yet production-verified** — awaiting a real post-deploy sample confirming the exact reported message (or an equivalent English-domain-word lead dictation) now classifies as tier=1/lead instead of tier=4/table.
