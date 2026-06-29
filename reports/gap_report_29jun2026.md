# Gap Report — קוד vs תיעוד | 29/06/2026

מבוסס על `SPEC_GIT_DIFF_GAP_FINDER.md`. main בבדיקה: `debb270` (אומת `git fetch origin main`,
`git log origin/main --oneline -30`). חלון הבדיקה: `--since="5 days ago"` (≈ 24/06/2026 ואילך)
+ סריקה ידנית נוספת על קבצים/commits ספציפיים שעלו מתוך ההשוואה.

## קבצים חדשים ב-main שלא מתועדים (או מתועדים בצורה שגויה)

| קובץ/מודול | נוצר | יש caller? | יש טסט? | פעולה נדרשת |
|---|---|---|---|---|
| `document_converter/` (חבילה שלמה, 9 קבצים) | מוזג PR #158, commit `db719ab`, 26/06/2026 | ❌ אפס caller חיצוני ל-package מעבר ל-tests | ✅ `test_document_converter.py`, 6/6 דרך `pytest` בלבד — **אך CI מריץ `python test_document_converter.py` (לא `pytest`), שלא מבצע אף assertion (exit 0, 0 נבדקו)** | תעד מחדש (תיקון סטטוס שגוי) + EXISTS_UNWIRED |
| `core/action_result.py`, `core/claim_gate.py`, `core/request_context.py` (CXX) | מוזג קודם, מתועד ב-ROADMAP/CHANGE_CONTROL_LOG | ✅ מחובר (`app.py`, `tools/whatsapp_adapter.py`) | ✅ `test_cxx_action_integrity.py` — רץ תקין דרך `python` (יש `unittest.main()`) | אין — תועד ומחובר כבר |
| `decision_attention_policy.py` | קודם | ✅ מחובר דרך `decision_attention.py` | ✅ `test_decision_attention.py` | אין — תועד ב-ROADMAP:560 |

## קבצים שהשתנו ולא עודכן תיעוד

| קובץ | שונה (commit) | מה השתנה (בקצרה) | פעולה |
|---|---|---|---|
| `app.py`, `core/anti_hallucination.py` | `4e1d7ed` "Wire lead capture evidence into A32" — PR #171, מוזג 29/06/2026 | נוספה `_action_result_to_a32_entry()` ב-`app.py` (ממירה `ActionResult`/`ClaimType` של lead_capture ל-רשומת A32 `tool_results_log`, FOUND≠CREATED). **קריאה אמיתית מאומתת:** `app.py:1124`. | תעד ב-CHANGE_CONTROL_LOG.md + ROADMAP.md — בוצע בסשן זה |
| `airtable_schema.py`, `lead_capture.py` | `257a5e4` "Fix safe lead metadata patch" — PR #172, מוזג 29/06/2026 | נוספה `capture_lead_event()` ב-`lead_capture.py` — כותבת ל-`Tables.LEAD_EVENTS` כש-`capture_inbound_lead` מוצא ליד קיים (FOUND) עם הודעה חדשה; לא דורסת/יוצרת ליד. **קריאה אמיתית מאומתת:** `lead_capture.py:215`. | תעד ב-CHANGE_CONTROL_LOG.md + ROADMAP.md — בוצע בסשן זה |

## reports/daily_changes
[x] קיים ב-remote — `reports/daily_changes/AUDIT_SUMMARY.md` (נוצר ב-PR #173, מוזג כ-`debb270`,
תוצאה של `SPEC_DAILY_CHANGES_AUDIT.md` מהסשן הקודם: התיקייה לא הייתה קיימת קודם בכלל, לא
ב-`main`, לא בשום branch, לא בהיסטוריית git — תועד כ-BUG-022).
אין קבצים מקומיים-בלבד שצריך להעלות — לא נמצאו במהלך בדיקה זו.

## סיכום פעולות
1. **קבצים לתיעוד ב-ROADMAP:** סעיף "Fxx — Safe Document Converter" תוקן — היה כתוב "Not merged
   to main" כש-בפועל מוזג מ-26/06/2026 (PR #158); סופף ממצא EXISTS_UNWIRED (אותו pattern כמו
   F20/F22) + ממצא CI (test file לא רץ בפועל תחת ה-invocation של `ci.yml`).
2. **קבצים לתיעוד ב-AI_CONTEXT:** עודכן הציון "main" ל-`debb270`; תוקן הסטטוס של Fxx; נוספה
   התייחסות לשני commits לא-מתועדים (`4e1d7ed`, `257a5e4`).
3. **BUGs חדשים לפתוח:** לא נפתח BUG נוסף — שני הממצאים (`4e1d7ed`/`257a5e4`) הם MISSING_FROM_DOCS
   עם caller אמיתי (לא MISSING קוד, לא EXISTS_UNWIRED), והממצא של `document_converter` הוא
   תיקון תיעוד + EXISTS_UNWIRED (מתועד ב-ROADMAP, לא BUG_AUDIT_LOG, לפי הדגם של F20/F22). ה-CI
   gap של `test_document_converter.py` (רץ ב-CI בלי לבצע אף assertion) **לא תוקן בקוד** (אין
   שינוי קוד לפי כלל הברזל של הספק) — מתועד כממצא פתוח כאן, להחלטה עתידית (להוסיף
   `if __name__ == "__main__": pytest.main()` או לשנות את `ci.yml` להריץ pytest על קבצים
   מסוג זה).
4. **קבצים להעלות מהמקומי:** אין — לא נמצאו local-only files בסשן זה.
