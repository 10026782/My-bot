# BOSS_BOT_SPEC_FIXES.md
> מסמך מעקב ממצאי-אימות (evidence checklists) לספקים/features שנבנו — נפרד מ-`BUG_AUDIT_LOG.md` (באגים) ומ-`CHANGE_CONTROL_LOG.md` (שינויים שמוזגו). כל סעיף כאן הוא שאלת אימות קונקרטית + ממצא מבוסס-קוד/בדיקה, לא תיקון.

## C90 — Structured File Capture

### שאלת אימות: fallback ל-raw_ref ברמת שורה בודדת כשכתיבת Airtable נכשלת

**השאלה:** ב-`core/lead_candidate_handler.py` (וכל מקום שכותב `AgentObservation`/`raw_ref`) — האם קיים מנגנון fallback ל-`raw_ref` מקומי **ברמת שורה בודדת** (לא רק ברמת קובץ שלם) כשכתיבת Airtable נכשלת עבור שורה ספציפית מתוך קובץ מרובה-שורות?

**ממצא: (א) כבר קיים, ירושה אוטומטית מ-C89 — אין קוד נוסף נדרש.**

**למה:** `_process_structured_file_upload()` (`app.py:2005-2009`) קורא ל-`classify_ingress(row_text, source_type="file")` **בנפרד לכל שורה**, בתוך לולאה:
```python
for row_text in rows_to_process:
    ic = classify_ingress(row_text, source_type="file")   # ← קריאה נפרדת לכל שורה
    ...
    reply = lch.handle_lead_candidate(identity, row_text, chat_id, channel, domain=domain, ic=ic)
```
`classify_ingress()` (`core/ingress_classifier.py:394-417`) הוא ה-single entry point היחיד, וללא special-casing ל-`source_type="file"` (עקרון הליבה של C90) — כל קריאה, מכל source_type, עוברת דרך אותה `_save_raw_capture()` (`core/ingress_classifier.py:336-366`):

```python
def _save_raw_capture(text: str, source_type: str) -> str:
    local_ref = f"local:{uuid.uuid4().hex[:16]}"   # ← מחושב טרי בכל קריאה
    try:
        if not is_enabled("FEATURE_RAW_CAPTURE"):
            return local_ref
        rec = airtable_create(Tables.DECISION_INBOX, {...}, source="ingress_classifier")
        if rec and rec.get("id"):
            return rec["id"]
        return local_ref
    except Exception as exc:
        logger.debug(...)
        return local_ref   # ← fallback על כשל כתיבה, per-call
```

מאחר ש-`local_ref`/ה-`try/except` נמצאים **בתוך** `_save_raw_capture()`, וכל שורה בקובץ קוראת ל-`classify_ingress()` (וממילא ל-`_save_raw_capture()`) **בנפרד**, כשל בכתיבת Airtable עבור שורה 2 לא משפיע על שורה 1 או שורה 3 — לכל שורה יש fallback עצמאי משלה, ולא רק fallback ברמת "כל הקובץ ביחד". זו ירושה ישירה ממנגנון C89-RAW-OBS (BUG-065) — C90 לא הוסיף ולא שינה שום דבר כאן, בדיוק לפי העיקרון שלו ("אותה `classify_ingress()` בדיוק, ללא special-casing").

**אימות אמפירי (לא רק קריאת קוד):**

1. שלוש שורות שונות דרך `classify_ingress(row, source_type="file")` (ללא `FEATURE_RAW_CAPTURE`, ברירת המחדל) — כל שורה קיבלה `raw_ref` נפרד מסוג `local:<hex>`, כל הערכים שונים זה מזה (`all distinct: True`).
2. הדמיית כשל Airtable אמיתי: `FEATURE_RAW_CAPTURE=True` + `tools.airtable_gateway.airtable_create` הוחלף בפונקציה שזורקת `RuntimeError` בכל קריאה. הרצת 2 שורות: שתיהן ניסו לכתוב (2 קריאות ל-`airtable_create`, שתיהן נכשלו), ושתיהן נפלו בנפרד ל-`local:<hex>` משלהן (`all fell back to local ref despite Airtable failure: True`, `still distinct per row: True`) — כשל בשורה אחת לא "דלף" לשורה השנייה ולא מנע ממנה fallback עצמאי.

**מסקנה:** אין תיקון נדרש. הסעיף הזה ב-evidence checklist של C90 ✅ מאומת — fallback per-row קיים ופועל אוטומטית, לא צריך קוד נוסף.

**סטטוס:** ✅ מאומת (05/07/2026) — לא תוקן כי אין מה לתקן.
