# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב-26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 08/08/2026 · **origin/main:** `e9525b5` (PR #560)
**פער תיעוד:** `ROADMAP.md`/`CHANGELOG.md` מעודכנים רק עד PR #552 (07/08/2026).
8 PRs נוספים (#553–#560) מוזגו מאז ולא תועדו שם. הסעיף למטה נבנה ישירות
מ-`git log`/`BUG_AUDIT_LOG.md` על `origin/main` — תואם "MAIN > DOCS".

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- שרשרת התיקונים סביב PR #546 (BUG-153/154/155/156/158/159) — כולם ✅
  **מוזגו + פרוסו + VERIFIED IN PROD** (ראיות לוג אמיתיות מ-owner).
- BUG-157 (race ב-`propose_action()`, לא latent — נגיש בין scheduler
  thread ל-webhook thread) — מוזג + פרוס, אך production-verified רק
  ב-test evidence (34/34), לא בתרחיש race אמיתי.
- אימות ה-production של BUG-157 חשף 3 באגים חדשים סביב Agent fallback
  ל-approval turn (BUG-160/161/162), פלוס באג נפרד שנמצא ב-E2E נוסף
  (BUG-163). כולם **קוד תוקן ונבדק (PR #560), מוזג ל-`main` היום —
  אך טרם deployed/verified בפרודקשן.**
- ממצא ארכיטקטוני קריטי (לא באג חדש): `Handler.TOOL` דטרמיניסטי קיים
  רק ל-`CREATE_TASK`, לא ל-`UPDATE_TASK`/`COMPLETE_TASK` — למרות
  שה-resolver/gateway המלא כבר בנוי ומחובר. זה בדיוק הפער ש-**PA-01
  (עדיין PLANNING ONLY, אין קוד)** נועד לסגור; 8 מתוך 12 ממצאי E2E
  שסיפק ה-owner הם אישוש-production לפער הזה, לא באגים נפרדים.
- פער deploy: אחרון-פרוס מאומת הוא `44fe0fb` (07/08 11:34, כולל עד
  PR #557); PR #559–#560 מוזגים ל-`main` אך טרם אומתו כפרוסים.
- BUG-152 — עדיין פתוח, לא root-caused (ללא שינוי בטווח הזה).

## 2. Current System State

**תפעולי (מאומת ב-grep/`git show` על `main`):**

- ActionContracts הוא מקור האמת היחיד למחזור-חיי approval; `_recover_pending_item_from_contract()`
  (BUG-158) כעת מונע "הפעולה אינה זמינה" כוזב כש-contract עדיין pending — **VERIFIED IN PROD**.
- `parse_deterministic_create_task()` — כולל כעת גם "משימת"/הוסף/תוסיף (BUG-159, VERIFIED IN PROD)
  וגם strip בטוח למרכאה לא-מאוזנת (BUG-160, מוזג היום, טרם deployed).
- `claim_fingerprint_cas()`/`release_fingerprint_claim()` — CAS אטומי עם claim-ownership token
  סוגר את מרוץ ה-fingerprint (BUG-157); production-verified רק חלקית.
- Airtable Gateway (`tools/airtable_gateway.py`) — נתיב הכתיבה היחיד ל-Airtable, ללא שינוי.
- `feature_flags.py` — אין flag חדש נרשם; `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`
  ו-`FEATURE_PA01_ENFORCEMENT_STATE` (three-state) קיימים אך כבויים כברירת מחדל בקוד.

**מיושם חלקית / לא production-active:**

- **PA-01** (Phantom Approval / Handler.TOOL ל-update/complete task) — **PLANNING ONLY**, אין
  קוד runtime. גורם היום להתנהגות לא-דטרמיניסטית אמיתית ב-update/complete task (Agent-driven).
- BUG-161/162 (Agent reconfirmation promise + turn-ownership) — root cause אותר, interim patch
  תוקן (honesty rule ב-`core_knowledge.py` + `reply_owner` fix בבלוק הגנרי), **לא** TC6 הרשמי
  (עדיין `NEXT_IMPLEMENTATION` ב-TurnCoordinator WS2). "Duplicate authority" (שני מנגנונים
  נפרדים לחישוב gateway-ownership) מתועד, לא אוחד.
- TurnCoordinator WS2/WS3 — מוזגו כקוד עצמאי, לא מחווטים לנתיב runtime חי.
- F52 Unified Status Formatter — shadow/comparison בלבד, מאחורי flag כבוי.

**חסום:** BUG-130/134/136/137/140/150/152 (וכן 126/127B/127C/138/139/142/148) —
ממתינים להחלטת owner; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.

| באג | Severity | קוד מוזג ל-main | Deployed | Production-verified |
|---|---|---|---|---|
| BUG-153/154/155/156 | גבוה/קריטי | ✅ (PR #550) | ✅ | ✅ |
| BUG-157 | גבוה, נגיש בפועל | ✅ (PR #552/#555) | ✅ | ❌ (test-only) |
| BUG-158 | גבוה | ✅ (PR #556) | ✅ | ✅ |
| BUG-159 | בינוני-גבוה | ✅ (PR #557) | ✅ | ✅ |
| BUG-160 — מרכאה לא מאוזנת | גבוה | ✅ (PR #560) | ❌ | ❌ |
| BUG-161 — reconfirmation לא עקבי | גבוה | 🟡 חלקי (PR #560) | ❌ | ❌ |
| BUG-162 — turn-ownership violation | בינוני-גבוה | 🟡 interim patch (PR #560) | ❌ | ❌ |
| BUG-163 — intent coverage complete/update | גבוה | ✅ (PR #560) | ❌ | ❌ |

## 3. Completed Since Last Update (מאז 06/08/2026, `c5dbe86..e9525b5`, PR #553–#560)

- **PR #553/#555 — BUG-157 hardening (סבב 2/3)** — המתנה ל-claim משתחרר
  + claim-ownership token אטום (מונע read-path משחרר claim פעיל של caller אחר). 34/34 טסטים.
- **PR #556 — BUG-158** — שחזור item מה-`ActionContract` כש-EventBus TTL (30 דק') פג לפני
  ה-contract עצמו (24h). **VERIFIED IN PROD** עם לוג אמיתי מ-owner.
- **PR #557 — BUG-159** — הרחבת הפרסר הדטרמיניסטי ל"משימת"/הוסף/תוסיף. **VERIFIED IN PROD**.
- **PR #558 — תיעוד**: קטלוג ROADMAP ל-PR #525–#552 + תיקון סטטוס TurnCoordinator WS1/WS2/WS3.
- **PR #559 — ביקורת post-merge**: תיקון שדות "Merged" מיושנים ב-`BUG_AUDIT_LOG.md` עצמו
  (BUG-153–159) + אימות production נוסף ל-BUG-153/155/156/158/159.
- **PR #560 — BUG-160/161/162/163 + Turn Coordinator E2E audit**: תיקון מרכאה לא-מאוזנת,
  כלל-כנות למניעת הבטחת-reconfirmation, root-cause fix ל-`reply_owner` בבלוק הגנרי, הרחבת
  intent regex ל-complete/update_task. שילוב 12 ממצאי E2E מה-owner — 8 מהם אישוש-production
  לפער PA-01 הקיים (לא באגים חדשים), אחד חדש (BUG-163), שניים ירושה מ-BUG-126/127C, אחד
  פער-testability. **כל התיקונים מוזגים ל-`main`, טרם deployed.**

## 4. Next Priorities

1. **Deploy + אימות production** ל-PR #560 (BUG-160/161/162/163) — הפער בין `main` (`e9525b5`)
   לבין ה-deploy החי האחרון המאומת (`44fe0fb`) גדל; לאמת commit נוכחי מול Render.
2. **תעדוף מימוש PA-01** (`Handler.TOOL` ל-`UPDATE_TASK`/`COMPLETE_TASK`) — הפער אושש חי
   ב-production (8/12 ממצאי E2E), לא רק תיאורטי; המסמך עצמו כבר קיים ומוכן ל-Cross-Layer Matrix.
3. **סגור את פער התיעוד** — 8 PRs (#553–#560) לא תועדו ב-`ROADMAP.md`/`CHANGELOG.md`.
4. **החלטת owner** על "duplicate authority" ב-BUG-162 (שני מנגנונים לחישוב gateway-ownership)
   ועל תזמון מימוש TC6 הרשמי (WS2) שיחליף את ה-interim patch.
5. חקור את BUG-152 (עדיין לא root-caused) ואת שאר הבאגים החסומים (130/134/136/137/140).
