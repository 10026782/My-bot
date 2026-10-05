# FCC Canary Runbook — production, Eliyahu only (05/10/2026)

החלטת בעלים: קנרית ב-production, למשתמש `eliyahu` בלבד; תנאי הצלחה = smoke מלא + 24 שעות ללא שגיאות לפני הרחבה.

## מנגנון הגנה (בקוד)
`tma_api._fcc_enabled(identity)` = `FEATURE_FINANCIAL_CONTROL_CENTER` **וגם** `FCC_CANARY_USER_IDS` מכיל את `identity.user_id`. ריק/חסר = אף אחד (fail closed). משתמש אחר מקבל 404 משני ה-endpoints, גם אם ה-flag דלוק. בנוסף: owner-of-record policy (נתונים), כפתור ה-Hub לבעלים בלבד.

## תנאי קדם (לפני הדלקה)
1. ה-PR של Slice 2 + canary gate ממוזג, ו-Render פרוס על ה-commit (השוואת hash ב-dashboard מול `origin/main`).
2. `IDENTITY_MAP` ב-Render מפיק `eliyahu` ← telegram `7228089151`, ושורת Profile בשם `Eliyahu` יחידה (strict-unique; אחרת fail closed ⇒ 403).
3. `schema_cache.json` בפריסה כולל את `Financial Goals` / `Financial Progress Events` (או `python3 schema_audit.py --live` עם המפתח האמיתי).
4. שתי הטבלאות החיות ריקות / ללא רשומות בדיקה.

## הדלקה (Render env, בעלים)
`FCC_CANARY_USER_IDS=eliyahu` → ואז `FEATURE_FINANCIAL_CONTROL_CENTER=true` → redeploy. סדר חשוב: ה-allowlist קודם.

## Smoke (מתוך ה-TMA של אליהו, או curl עם initData)
| # | צעד | צפוי |
|---|-----|------|
| 1 | פתיחת "המרכז הכלכלי" | מסך ריק, ללא שגיאה |
| 2 | עדכון מהיר: "תוסיף יעד חדש הכנסה נוספת 12000" → אשר | יעד נוצר, `Financial Owner`=Eliyahu |
| 3 | "השבוע עשיתי 2500" → אשר | אירוע `one_time`, Actual=2,500, Remaining/Dynamic מתעדכנים |
| 4 | "תעלה את יעד ההכנסה ל-18000" → אשר | אירוע `target_change`; אירועים קודמים נשמרים; Remaining מחושב מחדש |
| 5 | אותו טקסט פעמיים באותו יום | רק אירוע אחד (duplicate) |
| 6 | "שמתי כסף" (בלי סכום) | משימת המשך (`Topic=כספים`, `[FCC:…]`) לאליהו; אין אירוע |
| 7 | עם 2 יעדי חיסכון: "הפקדתי 5000" | רשימת candidates, לא נבחר יעד |
| 8 | קריאה כ-`avi` (initData של אבי) ל-`/api/fcc/overview` | 404 |
| 9 | Airtable: שורות חדשות עם `Financial Owner` מלא, `Recorded By`=eliyahu | ✓ |
| 10 | Approvals/ActionContracts: ה-contracts נוצרו דרך ActionGateway | ✓ |

אחרי ה-smoke: מחיקת רשומות הבדיקה (יעד/אירועים/משימה) ביד, ורישום בראיות.

## 24 שעות ניטור
לוגים: `[data_access_policy]` (denied), `tma_write` failures, שגיאות 5xx ב-`/api/fcc/*`, `partial_failure`. קריטריון הצלחה: אפס 5xx, אפס `partial_failure` לא מוסבר, אפס רשומה ללא `Financial Owner`.

## Rollback
מיידי: `FEATURE_FINANCIAL_CONTROL_CENTER=false` (או ריקון `FCC_CANARY_USER_IDS`) ⇒ שני ה-endpoints 404, המסך מציג "טרם הופעל". אין מיגרציה לשחזר; הנתונים נשארים.

## הרחבה (רק אחרי 24 שעות נקיות, החלטה נפרדת)
הוספת `user_id` ל-`FCC_CANARY_USER_IDS`. שותפים (אהרן/אורי) דורשים החלטת co-owner נפרדת.
