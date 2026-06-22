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
- [ ] Schema sync: השווה live Airtable vs airtable_schema.py (manual עד N07)
- [ ] Tests: py_compile + npm build (manual עד N08)
- [ ] Deploy אומת ב-Render (manual עד N09)
- [ ] Rollback plan מוגדר (manual עד N10)

## Bug Fix
- [ ] הבאג מתועד (ROADMAP / issue / audit log)
- [ ] Root cause מובן (לא רק symptom)
- [ ] תיקון בקובץ הנכון — לא workaround
- [ ] py_compile / build עובר
- [ ] לא שבר כלום אחר (regression check)
- [ ] Deploy + verify בפרודקשן
- [ ] ROADMAP עודכן
- [ ] AI_CONTEXT KNOWN_GAPS עודכן אם רלוונטי
- [ ] Schema sync: השווה live Airtable vs airtable_schema.py (manual עד N07)
- [ ] Tests: py_compile + npm build (manual עד N08)
- [ ] Deploy אומת ב-Render (manual עד N09)
- [ ] Rollback plan מוגדר (manual עד N10)

## Security Fix
- [ ] תיעוד מלא של הפגיעות
- [ ] Fix בענף נפרד
- [ ] Review על ידי owner
- [ ] Deploy לפרודקשן בהקדם
- [ ] אימות שהפגיעות נסגרה בפרודקשן
- [ ] SECURITY_CHECKLIST.md עודכן
- [ ] AI_CONTEXT עודכן
- [ ] Schema sync: השווה live Airtable vs airtable_schema.py (manual עד N07)
- [ ] Tests: py_compile + npm build (manual עד N08)
- [ ] Deploy אומת ב-Render (manual עד N09)
- [ ] Rollback plan מוגדר (manual עד N10)

## Airtable Schema Change
- [ ] שינוי מתועד לפני שנוגעים ב-Airtable
- [ ] airtable_schema.py עודכן להתאמה
- [ ] schema_cache.json נמחק / מסונכרן
- [ ] schema_intelligence sync נבדק
- [ ] כל קבצים שמשתמשים בשם השדה עודכנו
- [ ] AI_CONTEXT עודכן (WHERE TO FIND TRUTH)
- [ ] כל singleSelect options — וודא exact match כולל trailing spaces
- [ ] typecast=off → כל ערך חייב להתאים בדיוק ל-live Airtable
- [ ] OPTIONS preflight parameters — וודא שם משתנה תואם URL rule (ללא _ prefix)
- [ ] Schema sync: השווה live Airtable vs airtable_schema.py (manual עד N07)
- [ ] Tests: py_compile + npm build (manual עד N08)
- [ ] Deploy אומת ב-Render (manual עד N09)
- [ ] Rollback plan מוגדר (manual עד N10)

## Hotfix
- [ ] Emergency Stop פעיל אם נדרש
- [ ] Fix ממוקד — שורות מינימליות
- [ ] Deploy מיידי
- [ ] CHANGE_CONTROL_LOG עודכן
- [ ] Post-mortem קצר תועד
- [ ] Schema sync: השווה live Airtable vs airtable_schema.py (manual עד N07)
- [ ] Tests: py_compile + npm build (manual עד N08)
- [ ] Deploy אומת ב-Render (manual עד N09)
- [ ] Rollback plan מוגדר (manual עד N10)

## Rollback
- [ ] זוהה commit יציב אחרון
- [ ] Rollback בוצע
- [ ] אומת שהמערכת יציבה
- [ ] Root cause תועד
- [ ] CHANGE_CONTROL_LOG עודכן עם "ROLLBACK" entry
- [ ] Schema sync: השווה live Airtable vs airtable_schema.py (manual עד N07)
- [ ] Tests: py_compile + npm build (manual עד N08)
- [ ] Deploy אומת ב-Render (manual עד N09)
- [ ] Rollback plan מוגדר (manual עד N10)

## GOVERNANCE ROADMAP
> מה מתוכנן אבל לא פעיל עדיין.
> עד שמיושם — manual gate בלבד.

| כלי | סטטוס | עדיפות | מה נדרש |
|-----|-------|--------|---------|
| Schema Governance script | 🔲 PLANNED | N07 — גבוהה | השוואת live Airtable vs airtable_schema.py |
| CI/CD GitHub Actions | 🔲 PLANNED | N08 | pytest + build על כל PR + Render hook |
| Monitoring / Alerting | 🔲 PLANNED | N09 | Render alerts + Sentry |
| Rollback אוטומטי | 🔲 PLANNED | N10 | תלוי ב-N08 |

## דוגמה אחרונה — PR #69 (C56, Approval Policy Gate, מוזג 17/06/2026)
> Security Fix checklist כפי שיושם בפועל — לתיעוד, לא לשינוי התבנית למעלה.
> ⚠️ נוסף 23/06/2026: עד תאריך זה `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` תיעדו "Merged: לא" עבור PR זה במשך 6 ימים, אף שה-merge עצמו קרה ב-17/06/2026 — ראו `CHANGE_CONTROL_LOG.md` C56 לתיקון המלא.
- [x] תיעוד מלא של השינוי — `Approval_Policy_Spec.md`, `BUG_AUDIT_LOG.md` (FEATURE entry), `CHANGE_CONTROL_LOG.md` C56
- [x] Fix בענף נפרד — `claude/meta-whatsapp-phase-1-q6pp3e`
- [x] Review על ידי owner — מאומת ב-GitHub API (`mergedBy: 10026782`)
- [x] **Merged ל-main** — PR #69, merge commit `4e933b0` (17/06/2026), מאומת דרך `gh pr view 69` + `git merge-base --is-ancestor`
- [ ] Deploy לפרודקשן בהקדם — Render Auto-Deploy מוגדר על `main`, **לא אומת ידנית**
- [ ] אימות שהשינוי נכון בפרודקשן — ממתין (תלוי בהדלקת `EMERGENCY_WINDOW`)
- [x] AI_CONTEXT עודכן
- [x] Schema sync: RISK_LEVEL נבדק מול live Airtable choices (`low`/`medium`/`high`)
- [x] Tests: py_compile + npm build + smoke_tests.py 5/6 + מטריצת 12 תרחישים
- [ ] Deploy אומת ב-Render — לא
- [x] Rollback plan מוגדר — revert ל-merge commit `4e933b0` על `main`; `EMERGENCY_WINDOW` כבוי כך שאין סיכון פונקציונלי מיידי
