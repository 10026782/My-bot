# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing) תמציתי, לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו. `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה
> 26/06/2026, כחודש ישן) — **לא** מקור אמת נוכחי. **main גובר על כל מסמך תכנון בכל סתירה.**
> **פער תיעוד ידוע:** `ROADMAP.md` עודכן לאחרונה 21/07/2026; `CHANGELOG.md`/`CHANGE_CONTROL_LOG.md`
> מסונכרנים רק עד PR #449. `main` בפועל התקדם 5 PRs נוספים (#450–#454, כולם עדכוני-תיעוד/רישום-באגים
> בלבד — אין קוד production שהשתנה בהם). מסמך זה נכתב ישירות מ-`main` (`5491de3`) +
> `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md`, לא מ-`ROADMAP.md` בלבד, כדי לגשר על הפער.

**עודכן:** 24/07/2026 · **main:** `5491de3` (מיזוג PR #454, מאומת מול `origin/main`)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד — ללא שינוי במסלול הזה בסבב הזה.
- **Emergency Stop (PATCH 3B) הושלם ואומת בפרודקשן ישירות ע"י הבעלים** — 5 דגלי `EMERGENCY_STOP_*` דביקים ב-Airtable (שורדים restart אמיתי), TMA UI עם כפתורי Stop/Clear מלאים כולל Stop All.
- **סבב תיקוני-באג נרחב באישור/ניתוב-הודעות (BUG-111 עד BUG-127, כולל BUG-129/131/132/133/135) — כולם ✅ VERIFIED IN PROD** עם evidence מלוגים אמיתיים.
- **Cost Telemetry (`usage_events`) — shadow בלבד**, לא מזיז את ה-trigger החי (`COST_WATCHDOG_LIVE=false`); cutover ל-trigger חסום בכוונה עד שיצטברו ימי-נתונים מול חיוב פרודקשן אמיתי.
- **שישה באגים פתוחים, לא מטופלים, ממתינים להחלטת owner:** BUG-130, BUG-134, BUG-136, BUG-137, BUG-138, BUG-139, BUG-140 — פירוט מלא בסעיף 2.
- **TurnCoordinator / Cross-Layer Authority Contract V1 (#446/#447/#451)** — יוזמת תכנון למיזוג שכבות BUG-104/TurnCoordinator/F52/Approval; **תכנון בלבד, אפס קוד runtime**. Phase 2 Shadow: `READY FOR OWNER DECISION`, 3 החלטות פתוחות; תרחיש 7 בחוזה (CREATE_CONTACT ownership) קיבל אישור-ריאלי נוסף.
- **פער תיעוד פתוח:** `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` לא סונכרנו מעבר ל-PR #449, למרות 5 PRs נוספים שמוזגו מאז (#450–#454, כולם docs-only).

---

## 2. Current System State

**עובד בפרודקשן, מאומת:**
- Identity→Router→Context→Agent; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed).
- Approval flow: TTL אכיפה בטלגרם (BUG-112) ו-TMA (C84, 24h); תיקוני BUG-111/114-117/121-124 — כולם עם evidence production.
- Emergency Stop: 5 דגלים דביקים ב-Airtable, `is_enabled()`/`set_flag()` מיירטים אותם. TMA Stop/Clear מלא.
- F52 Unified Status Formatter + RP5 Evidence Finalizer — shadow logging פעיל בפרודקשן; `enforce`/`on` לא הופעלו.
- PR #449 (warm-cache TTL consistency, sibling-rejection disclosure, `describe_pending_queue()`) — ממוזג ומבודק, staging (`rp5-staging-fault-injection-v4akit`) הועלה מחדש עם התיקון.

**מיושם חלקית / flag off / shadow:**
- Cost Telemetry (`core/usage_telemetry.py`, PostgreSQL `usage_events`) — shadow-only, מחווט ל-6 נקודות-קריאה אמיתיות, לא מניע את ה-trigger החי.
- BUG-104 Core Reasoning — ממוזג ומאומת ב-tests, `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow. Phase 2A.0 (ניקוי סכמה) עדיין SPEC-בלבד.
- TurnCoordinator Contract V1 — תכנון בלבד, `PLANNING BLOCKED`/`READY FOR OWNER DECISION`, אין flag ואין קוד. תרחישים 26-27 נוספו מדגימת staging שנייה (#451).

**חסום / פתוח:**
- **BUG-130** — עדכון-ליד קיים מנותב ליצירת-ליד חדש; לא תוקן. אושרר שוב פעמיים בדגימות staging נוספות (23-24/07), כולל סיכון collision-לפי-טלפון-בלבד — עכשיו עם מופע קונקרטי (ראו BUG-140).
- **BUG-134** — TTL גנרי (`ActionContractRepository`, 24h) עלול ליירט contract לפני שלוגיקת C84 מספיקה לרוץ; **אומת ישירות מ-Airtable (24/07)** — 3 מ-4 הרשומות בטבלת `Approvals` תקועות `pending` 4-14 ימים.
- **BUG-136** (חדש) — "בצע שוב `<קוד>`" עטוף ב-`*...*` (כפי שהבוט עצמו מציע) לא תואם את ה-regex המעוגן ב-`app.py`, נופל ל-Agent שמאלתר תשובה שגויה.
- **BUG-137** (חדש) — הודעת "✅ בוצע: עדכון ליד" מרכיבה domain פנימי (למשל "finance") בלי תווית לתוך הטקסט.
- **BUG-138** (חדש) — כפתור אישור טלגרם לא נעלם אחרי אישור/דחייה (`edit_message_text()` לא מנקה `reply_markup`). השערה מבוססת-קוד בלבד, טרם אומתה מול Telegram/לוגים בפועל.
- **BUG-139** (חדש) — RP5 shadow: `response_claim=failure/mixed` כשאין tool call בתור כלל; נמצא מלוגי staging אמיתיים (47% mismatch rate), נשלל כארטיפקט fault-injection. Root cause בקוד עדיין לא אותר.
- **BUG-140** (חדש) — בקשה מפורשת ל"ליד חדש" יוצרה כ-`airtable_update` נגד ליד קיים ולא-קשור (collision-לפי-טלפון). Contract עדיין `pending`, לא בוצע נזק; מומלץ דחייה ידנית. אומת ישירות מ-Airtable.
- RP5 enforcement — shadow evidence ל-5/9 מצבי סיווג, טרם הושלם לכל 9.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- `claude/rp5-staging-fault-injection-v4akit` — staging-only בכוונה, לעולם לא ימוזג ל-main.

---

## 3. Completed Since Last Update

*(מקבץ PR #440–#454; לפירוט מלא ראה `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` C160–C169)*

- **תיקוני אישור/ניתוב (BUG-111 עד BUG-127):** סדרת תיקונים ל-`ActionGateway`/`core/ingress_classifier.py`/`app.py` — כולם ✅ VERIFIED IN PROD עם evidence מדויק מלוגים.
- **PATCH 3B הושלם:** Emergency Stop דביק לגמרי, אומת בפרודקשן כולל restart אמיתי, TMA frontend (#425–#436).
- **Cost Telemetry Reliability:** PR1 (#435) → hotfix (#437, BUG-132) → hotfix-followup (#438) → PR2 (#439, `usage_events` חדש, shadow טהור).
- **BUG-129/131/132/133/135 תוקנו** — self-quote/מחיקה שהפיקו שם-ליד מזויף (#444); כתיבה שקטה ל-`AI_Usage_Daily` (#435); test שדלף 310 רשומות אמיתיות ל-Interaction Log — תוקן + נמחקו (#442).
- **N16:** Git Audit הוצא לגמרי מהבוט העסקי.
- **TurnCoordinator Contract V1 (#446/#447):** שער חובה למניעת שינוי לא-מתואם בין 4 שכבות. **#451:** תרחישים 26-27 נוספו מדגימת staging שנייה.
- **`scripts/render_log_export.py` (#448):** כלי דיאגנוסטיקה אופליין, לא מיובא ע"י `app.py`.
- **PR #449 (23/07):** warm-cache TTL consistency, sibling-rejection disclosure, `describe_pending_queue()` — אומת מול ActionContracts export אמיתי + Render logs. Finding #7 (CREATE_CONTACT תמיד יוצר Lead) תועד, לא תוקן — ממתין ל-TurnCoordinator.
- **#452 (23/07):** BUG-136/BUG-137 נרשמו; ראיית BUG-130 חוזקה (2 מופעים נוספים).
- **#453 (23-24/07):** BUG-139 נרשם + דוחות log-observation ל-RP5/TurnCoordinator.
- **#454 (24/07):** BUG-140 נרשם; BUG-134/137/138 נבדקו ישירות מול Airtable — BUG-134 אומת עם 3 רשומות תקועות בפועל.

**פער תיעוד היסטורי שנשאר פתוח:** `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עדיין לא סונכרנו ל-#450–454 (docs-only, אין סיכון קוד).

---

## 4. Next Priorities

1. **החלטת owner: BUG-130** — כיוון תיקון לעדכון-ליד-קיים המנותב כיצירה חדשה (מתח מול השומר של BUG-094). מחוזק ע"י 2 דגימות נוספות + מופע קונקרטי (BUG-140).
2. **החלטת owner: BUG-134** — כיוון תיקון למרוץ ה-TTL הגנרי מול C84; כעת עם ראיה ישירה (3 רשומות תקועות ב-Airtable).
3. **החלטת owner: BUG-136/BUG-137** — נוגעים ב-F52/Approval layer (`core/action_gateway.py`) — טעונים שער Cross-Layer Authority Contract לפני מימוש.
4. **TurnCoordinator Phase 2 Shadow** — 3 החלטות owner פתוחות (סביבת staging, איחוד ActionGateway, scope של CapabilityScope) לפני קוד shadow ראשון.
5. **סנכרון תיעוד** — לעדכן `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` ל-PR #450–454.
6. **אימות BUG-138/BUG-139** — שניהם ממתינים לאימות ישיר נוסף מול Telegram/לוגי production (BUG-138 השערת-קוד בלבד; BUG-139 root-cause טרם אותר).
7. **manual:** רשומת `recK8RdYkdDmTGdob` (Leads) — owner לאשר אם רצוי לשמור; contract `0e8a155c-...` (BUG-140) — מומלץ דחייה ידנית.
