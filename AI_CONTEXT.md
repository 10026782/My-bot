# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md`, `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5
> ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` מסומן **stale** (26/06/2026) בראש הקובץ עצמו — ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 10/08/2026 · **origin/main:** `cec3f83` (PR #588). `ROADMAP.md`/
`CHANGELOG.md`/`BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1 מעודכנים עד commit זה באותו
סבב תיעוד — אין פער תיעוד ידוע כרגע. **גם** `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`
§3.5.2 (target chain diagram) ו-§3.5 (Runtime Capability Status) נשארו
מתוארכים 09/08/2026 — לא עודכנו בסבב הזה, לא לצטט כעדכניים מעבר למה ש-§3.5.1 קובע במפורש.

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- **פער deploy ממשיך לגדול, לא נסגר:** אחרון-פרוס מאומת נשאר `44fe0fb` (07/08, עד
  PR #557) — **ללא שינוי מאז אתמול**. PR #558–#588 (31 PRs, כולל BUG-160–163,
  TC5/TC4/TC6/F14/Emergency-Stop, וכעת גם TC7-A/B/B1/B1.1, TC8, TC9, Track A/D)
  מוזגו ל-`main` אך **UNVERIFIED כפרוסים** — לא אומת מול Render מאז 07/08.
- **17 PRs נוספים מוזגו מאז אתמול (#572–#588)** — עדכון משמעותי בהיקף Turn
  Coordinator: **TC8 (durable turn-state) ו-TC9 (MessageContract boundary) עברו
  מ-PLANNING ל-MERGED**, TC8 **חי וללא flag** (מחווט לכל 4 נקודות
  approve/reject/cancel ב-`app.py`). TC7-B1/B1.1 (`core/claim_authorization.py`)
  גם מוזג — אך **grep מאשר אפס קוראים בפועל**; למרות השם, עדיין לא מחבר את TC7-A
  ל-RP4 לכדי החלטה חיה (המטרה הארכיטקטונית של TC7-B). ראו סעיף 3 לפירוט מלא.
- שרשרת BUG-153/154/155/156/158/159 — כולם ✅ **מוזגו + פרוסו + VERIFIED IN
  PROD**. BUG-157 (race ב-`propose_action()`) מוזג+פרוס, test-evidence בלבד — נשאר 🟡.
- BUG-160/161/162/163 — **מוזגו ל-`main`, טרם deployed/verified בפרודקשן.** ללא שינוי מאז אתמול.
- ממצא ארכיטקטוני קריטי שלא נסגר: `Handler.TOOL` דטרמיניסטי קיים רק ל-
  `CREATE_TASK`, לא ל-`UPDATE_TASK`/`COMPLETE_TASK` — `PA-01_PLANNING_GATE.md`
  עדיין **PLANNING ONLY**, אין קוד runtime.
- BUG-152 — עדיין פתוח, לא root-caused, ללא שינוי.
- `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1 (Program Map) עודכן
  היום לשורות A/F/H/I/J בלבד; §3.5/§3.5.2 (Runtime Capability Status, target
  chain diagram) **נשארו מתוארכים 09/08** — לא נסקרו מחדש בסבב הזה.

## 2. Current System State

**תפעולי (מאומת ב-grep/`git show` על `main`):**

- ActionContracts הוא מקור האמת היחיד למחזור-חיי approval; TC6 reply-ownership
  (`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, verified `true` בפרוד 09/08, לא אומת
  מחדש היום) — **VERIFIED IN PROD** (חלקי, 3/6 תרחישים).
- **TC8 durable turn-state (PR #585) — חי, ללא flag**, `core/turn_state_repository.py`
  מחווט ל-4 נקודות approve/reject/cancel ב-`app.py`, fail-closed בכשל. "Staging
  verified" הוא טענת-תיעוד בלבד, לא artifact מאומת — טעון אימות עצמאי.
- **TC9 MessageContract (PR #588) — בנייה חיה תמיד**, אך המרת-הטקסט בפועל עדיין
  מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (כבוי כברירת מחדל); `GatewayReply.contract`
  ללא קורא downstream.
- **Track A** (PR #581/#582) — קנוניזציה של "מחר" בכותרת משימה ל-due-date, ללא
  flag, חי; staging-verified, מוכרז "COMPLETE".
- **Track D** (PR #580) — logging חדש אמיתי ל-RuntimeSchemaProvider/IngressEnvelope
  (סוגר observability gap שתועד ב-§3.5), אך code/test-verified בלבד — לא production-verified.
- Emergency Stop — fail-closed (PR #567). `prepare_task_proposal()` מאמת גם
  `decision.owner` (PR #565). Airtable Gateway — נתיב הכתיבה היחיד, ללא שינוי.

**מיושם חלקית / לא production-active:**

- **TC7-B1/B1.1** (`core/claim_authorization.py`, PR #583/#587) — **BUILT_UNWIRED**,
  grep מאשר אפס קוראים מחוץ למודול/לטסט. אינו מחבר TC7-A ל-RP4 בפועל.
- **TC7/RP5 execution-shadow** (PR #579) — מחבר בפועל את TC7-A ל-RP4 (shadow
  comparison logging) תחת `FEATURE_EVIDENCE_FINALIZER` (כבוי כברירת מחדל,
  production value לא אומת מ-28/07). זה **לא** claim-authorization — מנגנון
  נפרד מ-TC7-B1 לעיל.
- **PA-01 Planning Gate** (Handler.TOOL ל-update/complete task) — **PLANNING
  ONLY**, אין קוד runtime.
- **TC5/TC4** — קוד structural מוזג, ללא חיווט לניתוב חי.
- **F14** — A1/B1/**B2 (PR #577, חדש)** מוזגו: `find_or_create_contact()` מכסה
  עכשיו 4 קוראים (`crm_add_contact`, `convert_lead_to_contact`, dispatcher
  `airtable_add`→Contacts, `tma_write` Contacts POST) — **עדיין אין gate מרכזי**
  ב-`ActionGateway`/dispatcher; נתיבי agent-tool אחרים ל-Contacts לא מוגנים.
- F52 Unified Status Formatter — shadow/comparison בלבד, מאחורי flag כבוי.
- **TC10 — עודכן (מסבב תיעוד זה)**: כבר לא PLANNING/אפס-קוד. הרמוניית
  isolated regression נבנתה (`scripts/run_isolated_regression.py` +
  `scripts/regression_matrix.py` + `scripts/staging_identity.py`), תוקן
  ה-root-cause של זיהום ה-BUG-122 ב-`scripts/verify_tc8_staging.py`
  (הרצת FULL_REGRESSION כבר לא נעשית מול staging בכלל), ונוסף
  `scripts/verify_tc9_staging.py` (canary ל-MessageContract, טרם הורץ מול
  staging אמיתי — נדרשים secrets אמיתיים). ראו
  `docs/architecture/turn-coordinator-full/TC10_OPERATIONAL_VERIFICATION_HARNESS.md`.
  סטטוס: **IMPLEMENTATION COMPLETE / STAGING VERIFICATION PENDING** — אימות
  Staging אמיתי (TC9 canary + TC8 PG checks) עדיין לא בוצע בסבב הזה.

**חסום:** BUG-130/134/136/137/140/150/152 (וכן 126/127B/127C/138/139/142/148) —
ממתינים להחלטת owner; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.

| באג | Severity | קוד מוזג ל-main | Deployed | Production-verified |
|---|---|---|---|---|
| BUG-153/154/155/156 | גבוה/קריטי | ✅ (PR #550) | ✅ | ✅ |
| BUG-157 | גבוה, נגיש בפועל | ✅ (PR #552/#555) | ✅ | ❌ (test-only) |
| BUG-158 | גבוה | ✅ (PR #556) | ✅ | ✅ |
| BUG-159 | בינוני-גבוה | ✅ (PR #557) | ✅ | ✅ |
| BUG-160/161/162/163 | גבוה-בינוני | ✅ (PR #560) | ❌ UNVERIFIED | ❌ |

## 3. Completed Since Last Update (מאז 09/08/2026, `7dbdddd..cec3f83`, PR #572–#588)

- **PR #583/#587 — TC7-B1/B1.1: claim-authorization module** — `core/claim_authorization.py`
  חדש (`authorize_claim()`); **grep מאשר: אפס קוראים חיים**. לא סוגר את הפער
  הארכיטקטוני שתועד ב-§3.5.2 (חיבור TC7-A↔RP4).
- **PR #579 (מחליף #576) — TC7/RP5 execution-shadow wiring** — מחבר TC7-A
  ל-RP4 בפועל, shadow, תחת `FEATURE_EVIDENCE_FINALIZER` (כבוי).
- **PR #585 — TC8: durable turn-state** — `core/turn_state_repository.py`, **חי
  ללא flag**, מחווט ל-4 נקודות ב-`app.py`. Staging-verified claim לא-מאומת עצמאית.
- **PR #588 — TC9: MessageContract at ActionGateway boundary** — בנייה חיה,
  פלט-טקסט עדיין מאחורי flag כבוי.
- **PR #577 — F14-B2** — שני קוראים חדשים ל-`find_or_create_contact()`; עדיין
  אין gate מרכזי.
- **PR #581/#582 — Track A** — קנוניזציית "מחר" ב-due-date, ללא flag, חי,
  staging-verified, סגור.
- **PR #580 — Track D** — logging חדש אמיתי ל-RuntimeSchemaProvider/IngressEnvelope.
- **PR #573/#574/#575/#578 — TC7-A closure, TC6 docs closure, Program Map
  consolidation, runtime-audit docs** — כולם docs/review, ללא שינוי runtime.
- **PR #584/#586 — CI/test hardening** — Postgres service ל-CI, בדיקת confirmation
  AST-based במקום string-match.
- **תיעוד:** ROADMAP.md/CHANGELOG.md/`BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1 עודכנו
  היום (10/08) לסגור את פער התיעוד לכל 17 ה-PRs הנ"ל.

## 4. Next Priorities

1. **סגור את פער ה-deploy שהולך וגדל** — 31 PRs (#558–#588) מוזגו אך לא אומתו
   כפרוסים מאז 07/08; לאמת commit נוכחי מול Render לפני כל טענת "פרוס".
2. **חבר בפועל את TC7-B1 (`authorize_claim()`) לצרכן אמיתי** — הקוד קיים אך לא
   קורא לו אף אחד; זו עדיין ה-gate המרכזית החסרה בשרשרת claim-authorization.
3. **תעדוף PA-01 Planning Gate** (`Handler.TOOL` ל-`UPDATE_TASK`/`COMPLETE_TASK`) —
   דורש Cross-Layer Impact Matrix לפני כל קוד runtime.
4. **אימות production עצמאי ל-TC8** — הטענה ל-staging closure בתיעוד בלבד, לא
   artifact; TC8 כבר חי בפרודקשן ללא flag, אז זו לא "בחירה", אלא חוב-אימות דחוף.
5. **רענון מלא של §3.5/§3.5.2 ב-`BOSS_UNIFIED_MASTER_PLAN.md`** (Runtime
   Capability Status + target chain diagram) — עודכנו רק שורות ספציפיות ב-§3.5.1
   היום; שאר המסמך עדיין מתוארך 09/08.
