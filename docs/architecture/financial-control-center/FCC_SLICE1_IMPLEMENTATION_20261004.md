# FCC Slice 1 — Goal → Progress → Dynamic calc → Follow-up → Free-text writer (backend) — 04/10/2026

סטטוס: 🟡 CODE DONE, NOT VERIFIED LIVE. Flag `FEATURE_FINANCIAL_CONTROL_CENTER` כבוי כברירת מחדל. **לא נוצרה שום טבלה/שדה חי ב-Airtable.**

## מה ממומש
| רכיב | קובץ |
|------|------|
| חישוב נגזר (Actual/Remaining/Remaining periods/Dynamic target/Monthly Cash Improvement; `target_change` כאירוע) | `core/financial_control/calc.py` |
| קריאות owner-scoped (`filter_records` לפני כל aggregate), מדריך dedupe למשימות, בדיקת בעלות Goal | `core/financial_control/service.py` |
| כותב: intent מובנה → resolve מול Goals של המשתמש בלבד → validate → preview → proposals; אין כתיבה | `core/financial_control/writer.py` |
| Classify (LLM, ללא parser נקודתי) | `core/financial_control/classifier.py` |
| מדיניות: `Financial Goals`/`Financial Progress Events` = OWNER_SCOPED, `Goal` link חייב להיות של אותו owner (create + update) | `core/data_access_policy.py` (`linked_owner_checks`) |
| ביצוע: רק `_queue_or_owner_execute` → ActionGateway → dispatcher → `tma_write` (נוספו 2 הטבלאות ל-allowlist; re-check בבעלות בזמן ביצוע) | `tma_api.py`, `tools/approval_actions.py` |
| API: `GET /api/fcc/overview`, `POST /api/fcc/write` (בלי `confirm` = preview בלבד; עמימות → `needs_goal`) | `tma_api.py` |
| קבועי סכמה (PROPOSED) | `airtable_schema.py` (`FinGoalFields`, `FinEventFields`) |
| בדיקות | `test_financial_control_center.py` (15) |

## החלטות תכנון
- **Tasks ממוחזרת, בלי שינוי סכימה**: משימת המשך = שורה ב-Tasks עם `Owner`=המשתמש ותגית `[FCC:<goal_id>]` בתיאור; dedupe = אותה תגית + כותרת מנורמלת + לא "בוצע". שדה link ייעודי `Financial Goal` נדחה (לא נדרש ל-slice).
- **שינוי יעד באמצע תקופה** = אירוע `target_change` (append-only); היסטוריה לא משתנה, ה-Remaining מחושב מול היעד התקף היום.
- **one_time מול monthly_recurring**: `Actual` סוכם רק מ-`one_time`; `monthly_recurring` נכנס רק ל-Monthly Cash Improvement.
- **שבוע** = ראשון–שבת. `calc_method`: `period_sum` | `cumulative` | `recurring_level` (נתון, לא enum שמשנה התנהגות עסקית אחרת).

## סכימה חיה נדרשת (ממתינה לאישור בעלים — לא בוצע)
`Financial Goals`: Title, Category, Status, Priority, Display Order, Period Type, Start Date, End Date, Target Amount, Min/Max Amount, Calc Method, Notes, **Financial Owner** (link→Profile).
`Financial Progress Events`: Goal (link), Amount, Kind (one_time|monthly_recurring|target_change|note), Occurred At, Recorded By, Source, Source Ref, Raw Text, Note, Idempotency Key, Superseded By, **Financial Owner** (link→Profile).
עד היצירה + רענון `schema_cache.json`, `airtable_gateway` ידחה כתיבה לטבלאות (שדות לא ידועים) — ולכן הפיצ'ר כבוי.

## לא ממומש ב-slice הזה
מסך TMA (React), כלי agent לשיחה חופשית בטלגרם (רק TMA endpoint), Tasks חוזרות seed (reviews), קרן חירום/פנסיה כתצוגה ייעודית, חישוב Months-coverage, פריסה, אימות חי.

## חשיפות שהתגלו
ללא חדשות. נשארות הפתוחות מ-PRIV-FCC-01 (Payments/Expenses/Deals גנרי, `/api/finance/pulse`) — `REVIEW_REQUIRED_FOR_PERSONAL_FINANCE_SCOPE`. משימת follow-up של FCC נראית בקריאות Tasks כלליות לבעליה לפי כללי Tasks הקיימים (אין `Tasks.Visibility` חי) — הכותרת נגזרת מכותרת היעד; להחליט אם להסתיר.
