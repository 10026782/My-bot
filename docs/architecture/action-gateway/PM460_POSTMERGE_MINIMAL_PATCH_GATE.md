# PM460 Post-Merge Minimal Patch Gate — BUG-147 (Patch A)

> **חובה:** מסמך זה כפוף ל-`docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — שער חובה
> לכל שינוי שנוגע (ישירות/בעקיפין) ב-Core Reasoning/BUG-104, TurnCoordinator, F52/Phase 4C, או
> ה-Durable Atomic Approval layer (`ActionContract`/`ActionGateway`). ללא Cross-Layer Impact Matrix
> מלא — `STATUS = PLANNING BLOCKED`. מסמך זה **הוא** אותו Impact Matrix, עבור Patch A בלבד.

**תאריך:** 26/07/2026.
**מקור:** דוח בדיקות Post-Merge של הבעלים (BUG_AUDIT_LOG.md §BUG-143/144/145/147,
CHANGE_CONTROL_LOG.md §C172) — הבעלים ביקש תיקון-זמני מינימלי כדי לאפשר להשלים את סבב הבדיקות
(תרחישים 3–5), וסיפק בעצמו שלוש הצעות patch (A/B/C).

## עדכון-היקף חשוב — Patch B/C ירדו מההיקף, לא בוצעו על ידי הענף הזה

תוך כדי הכנת המימוש התגלה ש-`main` כבר התקדם משמעותית מאז שהענף הזה נוצר, ושני PRs נפרדים (לא
מהסבב הזה) כבר סגרו את BUG-143/144/145 בפועל, ברמה **מקיפה יותר** ממה שהוצע כאן:

- **PR #460** (`codex/july24-sampling-blockers`, `006506d`) — sinks BUG-144 (reject עכשיו קורא
  ל-`ActionGateway.reject()`) ו-BUG-145 (helper אחיד להודעה-סופית-יחידה, מיושם **גם** ב-approve
  **וגם** ב-reject — Patch C המקורי כיסה approve בלבד).
- **PR #461** (`codex/pm460-drive-fail-closed`, `70093f0`) — סוגר BUG-143 עם המרת-payload אמיתית
  (`_sheets_payload_to_airtable()`, עם field-allowlist ו-fail-closed מפורש) — לא רק מיטיגציה
  (Patch B המקורי היה רק fail-closed, בלי המרה בפועל).

**המסקנה:** Patch B (`app.py::_queue_approval_detailed_impl`, fail-closed לפני `propose_action`)
ו-Patch C (`app.py::_handle_approval_callback_impl`, single-final-message) **לא בוצעו** על ידי הענף
הזה — היו מיותרים/עלולים להתנגש עם התיקונים השלמים יותר שכבר ב-`main`. **רק Patch A** (על
`tools/dispatcher.py`, שאף PR אחר לא נגע בו) נשאר בהיקף ומומש בפועל.

**היקף מוצהר בפועל — Patch A בלבד:**
`tools/dispatcher.py`'s `dispatch_tool()`: הגילוי ש-BUG-147's ה-root cause שנרשם ב-C172 היה שגוי
(שני מסלולי `str(e)` בתוך `case "airtable_add"` שנחשדו כבר היו "❌"-prefixed ומסווגים נכון) הוביל
לאיתור ה-root cause **האמיתי** — ה-gate הכללי אחרי `action_validator.validate_action()` (שורות
156-162) מחזיר `validation.reason` גולמי (בלי "❌") לכל tool, כולל structured write tools. תוקן:
tools ב-`core.anti_hallucination._EVIDENCE_VALIDATORS` מקבלים `{ok: False, tool, user_message}`
במקום מחרוזת גולמית; tools אחרים (read-only) ללא שינוי. שני המסלולים המקוריים בהשערה גם הם עודכנו
לעקביות (hardening, לא כי היו שבורים בפועל).

---

## Cross-Layer Impact Matrix — Patch A

### שכבה 1 — Core Reasoning / BUG-104
touched: **not touched**
input/output/authority impact: אין — Patch A לא קורא/כותב ל-`core/leads_reasoning_projection.py`
או כל state/evidence/phase/confidence.
shared identifiers: אין חפיפה.
invariants/failure semantics/observability/cross-layer tests: לא רלוונטי.

### שכבה 2 — TurnCoordinator
touched: **not touched**
`tools/dispatcher.py` לא מכיל ולא קורא ל-`core.turn_envelope`/`TurnCoordinator` בשום מקום
(מאומת: `grep -n "TurnCoordinator\|turn_envelope" tools/dispatcher.py` → 0 תוצאות).
input/output/authority impact: אין. shared identifiers: אין import חדש.

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: **directly**
input impact: `dispatch_tool()`'s return-shape על ה-`ActionBlocked` branch עבור structured write
tools משתנה ממחרוזת גולמית ל-`dict` בעל צורת C53-A (`{ok, tool, user_message}`, subset תואם
ל-`_tool_result()`'s המלא). מיישר את ה-branch הזה לאותו חוזה שכל שאר `dispatch_tool()` כבר מקיים.
output impact: הצרכן היחיד (`verify_execution()`, שכבר יודע לפרש `dict` עם `ok=False`) לא צריך
שינוי — זה בדיוק המסלול שכל שאר ה-tool executors כבר עוברים.
authority impact: אין — לא ניתנת סמכות חדשה, רק מתוקן shape.
shared identifiers: `ok`/`tool`/`user_message` — שדות קיימים ב-C53-A contract
(`tools/airtable_tools.py:13-28`), אין שם חדש.
invariants: "כל write tool מחזיר structured dict" (`core/anti_hallucination.py:426-431`) —
Patch A מתקן הפרה קיימת של ה-invariant הזה.
failure semantics: fail-safe ללא שינוי — לפני הפאטצ' זה כבר היה "כישלון" (לא success שקרי), רק עם
קטגוריית-שגיאה גנרית ("expected structured result dict") במקום הסיבה האמיתית (presence-check).
אחרי — אותו fail-safe, סיבה מדויקת.
observability: אין log-line חדש; `user_message` מגיע ל-`verify_execution()`'s reason-string הקיים.
cross-layer tests: `test_c53a.py` (regression, ללא שינוי נדרש) + `test_bug147_dispatcher_structured_error_shape.py` (חדש).

### שכבה 4 — Durable Atomic Approval
touched: **indirectly**
input/output impact: אין שינוי בקלט/פלט ל-`ActionGateway`/`ActionContractRepository` עצמם —
Patch A משנה רק את מה ש-`dispatch_tool()` (הצרכן, לא היוצר, של contracts) מחזיר ל-executor.
authority impact: אין.
shared identifiers: `contract_id`/`status`/`ActionContract` — לא נוצרים/משתנים ב-Patch A.
invariants: לא רלוונטי — Patch A לא נוגע ביצירת/אישור/דחיית contracts.
failure semantics: `ActionGateway._execute_contract()`'s `verify_execution()` call מקבל עכשיו
`user_message` מדויק יותר על כישלון-חסימה — אותו failure path, סיבה טובה יותר.
observability/cross-layer tests: כנ"ל בשכבה 3.

### Proof of Non-Impact — שכבות 1/2

1. **grep evidence:**
   ```
   $ grep -n "leads_reasoning_projection\|FEATURE_CORE_REASONING\|BUG-104\|TurnCoordinator\|turn_envelope" tools/dispatcher.py
   (0 תוצאות)
   ```
2. **unchanged-tests evidence:** `test_bug104_*.py` (6 קבצים) ו-`test_turn_envelope.py` רצים ללא
   שינוי, ירוקים לפני/אחרי Patch A (ראו CHANGE_CONTROL_LOG.md §C173 לפירוט sweep).
3. **no-new-coupling evidence:** ה-import החדש היחיד ב-Patch A הוא
   `from core.anti_hallucination import _EVIDENCE_VALIDATORS` — לא קשור לשכבה 1/2, ואין circular
   import (`core/anti_hallucination.py` לא מייבא מ-`tools/`).

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: **yes** — Patch A משנה איך `verify_execution()` (חי היום, לא RP5-shadow) מסווג
`ActionBlocked` failures ל-structured write tools — מ"כישלון גנרי מטעה" ל"כישלון עם סיבה מדויקת".
לא נוסף מנגנון-grounding עצמאי חדש — `verify_execution()` הקיים ממשיך להיות המקור הסמכותי היחיד.

---

## מה לא בוצע (במפורש)

1. **Patch B (fail-closed על legacy Sheets payload ב-`app.py`) — לא בוצע, מיותר.** BUG-143 כבר
   תוקן ב-`main` (PR #461) עם המרה אמיתית, לא רק חסימה.
2. **Patch C (single-final-message ב-`app.py`'s approve callback) — לא בוצע, מיותר.** BUG-145 כבר
   תוקן ב-`main` (PR #460), כולל reject (מקיף יותר מהתוכנית המקורית שכיסתה approve בלבד).
3. **אין המרת payload שקטה נוספת, אין special-case מפוזר, אין השתקת הודעת-כשל, אין סימון contract
   כ-`completed` מלאכותית** — עקרונות אלה עדיין תקפים, גם אם לא רלוונטיים ל-Patch A עצמו.
4. **`airtable_update`'s case ב-`tools/dispatcher.py`** — לא נבדק/תוקן (אותו gate כללי חל עליו
   דרך ה-`ActionBlocked` branch המשותף, אבל הענפים הפנימיים לא נבדקו לתסמינים דומים).

## בדיקות

- `test_bug147_dispatcher_structured_error_shape.py` — 8/8 עברו, מורץ מול `main` הנוכחי (אחרי
  PR #460/#461).
- `python3 -m py_compile tools/dispatcher.py` — נקי.
- `test_c53a.py`, `test_bug104_*.py` (6), `test_turn_envelope.py` — ירוקים ללא שינוי (proof of
  non-impact לשכבות 1/2/3).
