# RELEASE_CHECKLIST.md
> העתק checklist זה לכל PR לפני merge ל-main.

## Feature Development
- [ ] פריט קיים ב-ROADMAP עם ID
- [ ] קובץ אחד ראשי — לא batch לפי פיצ'ר
- [ ] Feature flag הוגדר וכבוי ברירת מחדל
- [ ] אם כותבים ל-Airtable: דרך airtable_gateway.py בלבד
- [ ] אם מוסיפים טבלה: עודכן airtable_schema.py
- [ ] אם מוסיפים כתיבה: עודכן _TMA_WRITE_ALLOWED_TABLES
- [ ] npm run build / py_compile עובר
- [ ] ROADMAP עודכן (סטטוס + commit reference)
- [ ] BOSS_CURRENT_STATE.md עודכן
- [ ] AI_CONTEXT.md עודכן
- [ ] Render deploy הצליח
- [ ] אומת ידנית בפרודקשן (מה נבדק + תוצאה)

## Bug Fix
- [ ] הבאג מתועד (ROADMAP / issue / audit log)
- [ ] Root cause מובן (לא רק symptom)
- [ ] תיקון בקובץ הנכון — לא workaround
- [ ] py_compile / build עובר
- [ ] לא שבר כלום אחר (regression check)
- [ ] Deploy + verify בפרודקשן
- [ ] ROADMAP עודכן
- [ ] AI_CONTEXT KNOWN_GAPS עודכן אם רלוונטי

## Security Fix
- [ ] תיעוד מלא של הפגיעות
- [ ] Fix בענף נפרד
- [ ] Review על ידי owner
- [ ] Deploy לפרודקשן בהקדם
- [ ] אימות שהפגיעות נסגרה בפרודקשן
- [ ] SECURITY_CHECKLIST.md עודכן
- [ ] AI_CONTEXT עודכן

## Airtable Schema Change
- [ ] שינוי מתועד לפני שנוגעים ב-Airtable
- [ ] airtable_schema.py עודכן להתאמה
- [ ] schema_cache.json נמחק / מסונכרן
- [ ] schema_intelligence sync נבדק
- [ ] כל קבצים שמשתמשים בשם השדה עודכנו
- [ ] AI_CONTEXT עודכן (WHERE TO FIND TRUTH)

## Hotfix
- [ ] Emergency Stop פעיל אם נדרש
- [ ] Fix ממוקד — שורות מינימליות
- [ ] Deploy מיידי
- [ ] CHANGE_CONTROL_LOG עודכן
- [ ] Post-mortem קצר תועד

## Rollback
- [ ] זוהה commit יציב אחרון
- [ ] Rollback בוצע
- [ ] אומת שהמערכת יציבה
- [ ] Root cause תועד
- [ ] CHANGE_CONTROL_LOG עודכן עם "ROLLBACK" entry
