# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב-26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 06/08/2026 · **origin/main:** `c5dbe86` (PR #552)
**פער תיעוד ממשיך לגדול:** `ROADMAP.md`/`CHANGELOG.md` מעודכנים רק עד PR #524
(02/08/2026). `origin/main` כעת כולל 28 PRs נוספים (#525–#552) שלא תועדו
ב-ROADMAP; CHANGELOG מתעד רק PR #521–#524 בפירוט ורמז חלקי אחד ל-PR #546/#549
תחת "Unreleased". הסעיפים למטה נבנו ישירות מ-`git log`/`git show`/grep על
`origin/main` והשוואה מול טקסט `BUG_AUDIT_LOG.md` עצמו — תואם "MAIN > DOCS".

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- **תיקון סתירת תיעוד:** `BUG_AUDIT_LOG.md` מתאר את BUG-153/154/155/156/157
  (מסלול create_task דטרמיניסטי + concurrency) כ**"לא מוזג עדיין"** בטקסט הפנימי
  של כל סעיף — אך `git log origin/main` מוכיח שכל חמשת התיקונים **כן מוזגו**
  (PR #550 עבור 153/154/155/156, PR #552 עבור 157). הטקסט הפנימי לא עודכן
  לאחר המיזוג בפועל. לפי "MAIN > DOCS": **מוזג = כן, פרוס = לא, מאומת
  בפרודקשן = לא** לכל החמישה (אין hash חדש שאומת ב-Render).
- כל חמשת התיקונים נוגעים לאותו קוד ראוטינג ללא-flag (`parse_deterministic_create_task()`
  ב-`core/router/router.py`, `core/action_gateway.py`) שכבר סומן בעדכון הקודם
  כמשנה התנהגות/טקסט חי בלי מנגנון rollback — המשמעות: ברגע ה-deploy הבא הם
  ישפיעו על production מיידית, ללא flag.
- BUG-157 (race condition ב-`propose_action()` בין scheduler thread לבין
  webhook thread — לא latent, נגיש בפועל תחת `workers=1`) נסגר ב-CAS אטומי
  חדש על אינדקס fingerprint; 18/18 בדיקות חדשות כולל race אמיתי עם 8 threads.
- פער deploy: ה-deploy החי המתועד האחרון הוא `5ec37b8` (עד PR #516); `origin/main`
  כעת (`c5dbe86`) כולל 36+ PRs נוספים (#517–#552) שטרם אומתו כפרוסים.
- TurnCoordinator WS2/WS3 ו-F52 D-014–D-017 — ללא שינוי מהעדכון הקודם, נשארים
  לא מחווטים ל-runtime החי / מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (כבוי).
- BUG-152 — עדיין פתוח, לא root-caused, ללא PR/commit משויך (ללא שינוי בטווח הזה).

## 2. Current System State

**תפעולי (מאומת ב-grep/`git show` על `main`):**

- ActionContracts הוא מקור האמת היחיד למחזור חיי approval; מסלולי legacy
  (`app.py` `_pending_approvals`) ו-TMA קיימים במקביל.
- `parse_deterministic_create_task()` — פרסור עברי דטרמיניסטי ל-"צור משימה",
  רץ ללא flag לכל `Intent.CREATE_TASK`. חמשת התיקונים (BUG-153–157) עכשיו
  מוזגים לתוכו/סביבו: reconfirmation אחרי rejection, פרסור תאריך "ל-", TTL
  expiry contract lookup, שמירת/אי-שמירת שעה, ו-atomic fingerprint claim.
- Airtable Gateway (`tools/airtable_gateway.py`) הוא נתיב הכתיבה היחיד ל-Airtable — ללא שינוי.
- Lead Capture / Scoring / Memory / Followup — קיימים בקוד, כולם flag-gated וכבויים כברירת מחדל.
- `feature_flags.py` — אין flag חדש נרשם בטווח `9a62e6f..HEAD` (verified: `git diff` ריק על הקובץ).

**מיושם חלקית / לא production-active:**

- TurnCoordinator WS2/WS3 (lifecycle/evidence projections, MessageContract
  adapters) — מוזגו כקוד עצמאי, לא מחווטים לנתיב runtime החי.
- F52 Unified Status Formatter (D-014–D-017) — shadow/comparison בלבד, מאחורי flag כבוי.
- BUG-153/154/155/156/157 — **קוד מוזג ל-`main`, לא פרוס, לא מאומת בפרודקשן** (ראו טבלה).

**חסום:**

- BUG-130/134/136/137/140/150/152 (וכן BUG-126/127B/127C/138/139/142/148) —
  ממתינים להחלטת owner או חקירה נוספת; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.

| באג | Severity | קוד מוזג ל-main | Deployed | Production-verified |
|---|---|---|---|---|
| BUG-153 — create חדש אחרי rejection נחסם | גבוה | ✅ (PR #550) | ❌ | ❌ |
| BUG-154 — "ל-תאריך" מפיל parser | גבוה | ✅ (PR #550) | ❌ | ❌ |
| BUG-155 — TTL expiry לא סוגר contract | קריטי | ✅ (PR #550) | ❌ | ❌ |
| BUG-156 — שעה לא נשמרת ב-Airtable | בינוני-גבוה | ✅ (PR #550) | ❌ | ❌ |
| BUG-157 — propose_action() לא-אטומי (race) | גבוה, נגיש בפועל | ✅ (PR #552) | ❌ | ❌ |

## 3. Completed Since Last Update (מאז 05/08/2026, `9a62e6f..c5dbe86`, PR #549–#552)

- **PR #550 — BUG-153/154/155/156 fixes** (`core/router/router.py`,
  `core/action_gateway.py`, `app.py`) — ארבעת התיקונים שאותרו באימות Staging
  ל-PR #546 ב-03/08 מומשו ונבדקו מקומית (11–15 בדיקות חדשות כל אחד, כולן
  ירוקות), כולל Cross-Layer Impact Matrix מלא לכל אחד תחת
  `docs/architecture/action-gateway/`. **מוזג בפועל.**
- **PR #552 — BUG-157 atomic fingerprint claim** (`core/action_gateway.py`)
  — CAS חדש (`claim_fingerprint_cas`/`release_fingerprint_claim`) סוגר race
  אמיתי בין scheduler thread ל-webhook thread סביב `propose_action()`; 18/18
  בדיקות חדשות כולל race עם 8 threads בו-זמנית. **מוזג בפועל.**
- **PR #549 — תיקון תיעוד** (`CHANGELOG.md`,
  `DETERMINISTIC_TASK_ROUTING_AND_REPLAY_POLICY_20260802.md`) — מבהיר את
  ההבדל בין retry מפורש (מותר, contract חדש) לבין replay אוטומטי של פעולה
  שנדחתה (עדיין חסום). דוקומנטציה בלבד.
- **PR #551 — רגנרציית `AI_CONTEXT.md`** (עד PR #548) — הקודמת למסמך הנוכחי.
- אין flag חדש נרשם; `BUG_AUDIT_LOG.md` גדל (+400 שורות) עם תיעוד מלא לחמשת
  התיקונים אך שדות "Merged" בתוך הטקסט הפנימי של כל סעיף נשארו לא-מעודכנים
  (ראו §1 — פער בין main לתוכן הטקסט של הדוח עצמו).

## 4. Next Priorities

1. **אישור owner נדרש לפני deploy** — BUG-153/154/155/156/157 מוזגים ל-`main`
   וכולם ללא flag; ה-deploy הבא ישנה התנהגות routing/approval חיה מיידית.
   מומלץ סקירה מפורשת + עדכון `BUG_AUDIT_LOG.md`'s "Merged" fields לפני deploy.
2. סגור את פער התיעוד — 28 PRs (#525–#552) לא תועדו ב-`ROADMAP.md` (רק חלק
   קטן ב-`CHANGELOG.md`); דורש הצעת catch-up כמו ש-PR #521 עשה בעבר.
3. סגור את פער ה-deploy המתרחב — `origin/main` כעת 36+ PRs לפני ה-deploy החי
   האחרון (`5ec37b8`); לאמת hash נוכחי מול Render.
4. חקור את BUG-152 עם Render logs ותרחיש מבודד (עדיין לא root-caused).
5. קבל החלטות owner ל-BUG-130/134, לחיווט TurnCoordinator WS2/WS3 לנתיב
   runtime (staging/rollout gates), ולשאר הבאגים החסומים.
