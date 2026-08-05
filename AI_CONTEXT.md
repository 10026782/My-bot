# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב-26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 05/08/2026 · **origin/main:** `9a62e6f` (PR #548)
**פער תיעוד גדל:** `ROADMAP.md`/`CHANGELOG.md` מעודכנים רק עד PR #524 (02/08/2026).
`origin/main` הנוכחי כולל 24 PRs נוספים (#525–#548) שלא תועדו כלל ב-ROADMAP ורק ברמז חלקי
אחד ב-CHANGELOG ("Unreleased"). הסעיפים למטה נבנו ישירות מ-`git log`/`git show`/grep על
`origin/main`, לא מהמסמכים — תואם הנחיית "MAIN > DOCS".

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- **⚠️ ממצא חדש (לא מתועד עדיין באף מקום אחר):** אצווה של PRs #529–#548 (routing/status
  hardening) הוסיפה קוד regex דטרמיניסטי **חי וללא flag** — `parse_deterministic_create_task()`
  ב-`core/router/router.py` (רץ תמיד עבור `Intent.CREATE_TASK`) ו-`_CANCELLED_STATUS_QUESTION_RE`
  וסיבלינגים ב-`app.py` (מיירטים ניסוחים עבריים ספציפיים לפני שהם מגיעים ל-Agent). זהו אותו
  דפוס בדיוק כמו D-018/PR #524 ("לא מאחורי flag, משנה טקסט/התנהגות חי") — כאן חוזר על עצמו
  לאורך ~5 קומיטים נוספים. לא נמצא flag רישום חדש ב-`feature_flags.py` בטווח הזה כלל.
- **פער deploy מתרחב עוד יותר:** ה-deploy החי האחרון המתועד הוא `5ec37b8` (עד PR #516);
  `origin/main` כעת (`9a62e6f`) כולל בנוסף 32 PRs (#517–#548) שעדיין לא אומתו כפרוסים.
- TurnCoordinator Phase 2: WS1 (חוזי בעלות) מוזג (PR #536); אינטגרציית runtime צרה (PR #545,
  follow-up #546) מוזגה — מחווטת נתיב הצעת-משימה דטרמיניסטי בודד לראוטר. **WS2 (lifecycle/
  evidence projections) ו-WS3 (MessageContract adapters + surfaces harness) מוזגים כמודולים
  עצמאיים אך לא מחווטים לנתיב ה-runtime החי** — כך per `docs/architecture/turn-coordinator/README.md` עצמו (עודכן ב-PR #547).
- F52 Unified Status Formatter (D-014–D-018) — ללא שינוי מהעדכון הקודם: D-014–D-017 עדיין
  מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (shadow/כבוי); D-018 (PR #524) עדיין היוצא מהכלל
  הישן — לא-מאחורי-flag, ממתין ל-deploy.
- דגלי approval כפי שאומתו ב-Render ב-30–31/07/2026: `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`,
  `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, `FEATURE_ACTION_GATEWAY` — כולם `true` ב-Render;
  ברירת המחדל בקוד נשארת `off` בכל השלושה. **לא אומת מחדש בעדכון הזה.**
- Emergency Stop (5 דגלים, durable ב-Airtable) נשאר מאומת בפרודקשן (ללא שינוי בטווח הזה).
- **BUG-152** — עדיין נרשם, לא root-caused, ללא PR/commit משויך. `BUG_AUDIT_LOG.md` **לא
  השתנה** בטווח `7c3833a..9a62e6f` (אומת ב-`git diff`) — אין פריט 🔴 חדש.

## 2. Current System State

**תפעולי (מאומת ב-grep/`git show` על `main`):**

- ActionContracts הוא מקור האמת היחיד למחזור חיי approval; מסלולי legacy (`app.py`
  `_pending_approvals`) ו-TMA קיימים במקביל.
- `parse_deterministic_create_task()` — פרסור עברי דטרמיניסטי לבקשות "צור משימה" מובנות, רץ
  ללא flag בכל קריאה ל-`route_request()`/`run_agent()` עבור `Intent.CREATE_TASK`.
- יירוטי status/cancellation דטרמיניסטיים חדשים ב-`app.py` (סטטוס "האם בוטל?" וכו') — ללא
  flag, עוקפים את ה-Agent לניסוחים ספציפיים.
- תיקון fingerprint לזהות-משימה (PR #546 follow-up, `6aa82c6`) — סוגר תשובות כפולות על אותה
  בקשת יצירת-משימה; חי, ללא flag.
- דליפת `tool_name` גולמי ב-reconfirmation (D-018, PR #524) — עדיין תוקנה, ממתינה ל-deploy.
- Airtable Gateway (`tools/airtable_gateway.py`) הוא נתיב הכתיבה היחיד ל-Airtable — ללא שינוי.
- Lead Capture / Scoring / Memory / Followup — קיימים בקוד, כולם flag-gated וכבויים כברירת מחדל.

**מיושם חלקית / לא production-active:**

- TurnCoordinator WS2/WS3 — מוזגו כקוד עצמאי (contracts/projections/adapters/test harness)
  אך **לא מחווטים** לנתיב ה-runtime החי; ה-README הארכיטקטוני עצמו קובע "staging and rollout
  gates still required" לפני שלב הבא.
- F52 Unified Status Formatter — shadow/comparison בלבד עבור רוב המסלולים (D-014–D-017).
- Daily Digest lead-temperature summary (PR #517) — קוד קיים, טרם אומת כפרוס.
- Cost Telemetry (`core/usage_telemetry.py`) — shadow-only.
- Meta WhatsApp outbound — honest stub, חסום ע"י אישור Meta Cloud API.

**חסום:**

- BUG-130/134/136/137/140/150/152 (וכן BUG-126/127B/127C/138/139/142/148) — ממתינים להחלטת
  owner או לחקירה נוספת; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.
- `sheets_append` positional canonicalization ו-mutation-budget exception — מאומתים ביחידה
  בלבד, לא בנתיב production מדויק.

## 3. Completed Since Last Update (מאז 02/08/2026, PR #524 — `7c3833a..9a62e6f`, 24 PRs)

תיעוד זה מקובץ לפי נושא, לא PR-by-PR — ROADMAP.md/CHANGELOG.md עדיין לא סגרו את הפער הזה
(ראו Priority #2 למטה).

- **Context Librarian automation hardening** (PRs #525, #526, #534) — תיקוני gate/catalog/
  provenance; dev tooling בלבד, ללא שינוי runtime לבוט העסקי.
- **Status-routing / terminal-replay bug fixes** (PRs #528–#533, למשל `cd85a21`/`fc0bd85`/
  `70ee337`) — תיקנו: contract שנדחה/בוטל שאיבד סטטוס terminal מחוץ לחלון "אחרונה"; שאילתות
  סטטוס על פעולה מבוטלת שלא נותבו דטרמיניסטית. **כולם חיים, ללא flag**, ב-`app.py`/
  `core/action_gateway.py`.
- **TurnCoordinator Phase 2** (PRs #536–#544) — WS1 (חוזי בעלות) מוזג; WS2 (lifecycle/evidence
  projections) ו-WS3 (MessageContract adapters + cross-surface harness) מוזגו כמודולים חדשים,
  לא מחווטים.
- **אינטגרציית runtime צרה + תיקון fingerprint** (PRs #545/#546, follow-up ב-#547/#548) —
  מחווטת נתיב הצעת-משימה דטרמיניסטי בודד לראוטר; קנוניזציית זהות-משימה לפני dedup תיקנה
  תשובות כפולות. `docs/architecture/turn-coordinator/README.md` עודכן לשקף את מצב המיזוג.
- **לא נרשם flag חדש** ב-`feature_flags.py` בטווח כולו. `BUG_AUDIT_LOG.md` ללא שינוי (`git diff`
  ריק) — אין ממצא 🔴 חדש.

## 4. Next Priorities

1. **אישור owner נדרש** על תוספות ה-regex הדטרמיניסטיות החיות (`parse_deterministic_create_task`,
   יירוטי סטטוס-ביטול) שהצטרפו ב-PR #529–#548 ללא flag ומשנות טקסט/התנהגות בפרודקשן — אותו
   דפוס בדיוק כמו D-018; מומלץ סקירה מפורשת לפני שעוד שינוי ראוטינג ייכנס ללא דגל.
2. סגור את פער התיעוד — 24 PRs (#525–#548) לא תועדו ב-ROADMAP.md/CHANGELOG.md (מלבד רמז חלקי
   אחד); דורש הצעת catch-up (כמו שPR #521 עשה לפער #517–#520).
3. סגור את פער ה-deploy המתרחב — `origin/main` כעת 32 PRs (#517–#548) לפני ה-deploy החי
   האחרון (`5ec37b8`); לאמת hash נוכחי ב-Render.
4. חקור את BUG-152 עם Render logs ותרחיש מבודד (עדיין לא root-caused, ללא PR/commit משויך).
5. קבל החלטות owner ל-BUG-130/134, לחיווט TurnCoordinator WS2/WS3 לנתיב runtime (staging/
   rollout gates), ולשאר הבאגים החסומים.
