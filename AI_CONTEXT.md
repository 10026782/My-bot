# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב-26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 09/08/2026 · **origin/main:** `7dbdddd` (PR #571 — docs, סוגר את פער
התיעוד ל-PR #562–#570). `ROADMAP.md`/`CHANGELOG.md` מעודכנים עד commit זה —
אין פער תיעוד ידוע כרגע.

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- שרשרת BUG-153/154/155/156/158/159 — כולם ✅ **מוזגו + פרוסו + VERIFIED IN
  PROD**. BUG-157 (race ב-`propose_action()`) מוזג+פרוס, אך production-verified
  רק ב-test evidence (34/34), לא בתרחיש race אמיתי — נשאר 🟡.
- BUG-160/161/162/163 (מרכאה לא-מאוזנת, reconfirmation, turn-ownership,
  intent-coverage) — **מוזגו ל-`main` (PR #560), טרם deployed/verified
  בפרודקשן.** ללא שינוי מאז העדכון הקודם.
- **פער deploy הולך וגדל:** אחרון-פרוס מאומת הוא `44fe0fb` (07/08, עד PR
  #557). PR #558–#571 (כולל BUG-160–163 ו-TC5/TC4/TC6/F14/Emergency-Stop
  hardening) מוזגו ל-`main` אך **UNVERIFIED כפרוסים** — לא אומת מול Render.
- שמונה PRs נוספים (#562–#570) מוזגו מאז 08/08: TC5 (entity resolver), TC4
  (lead builders + task-proposal hardening), TC6 WS2+integrator
  (reply-ownership, flag כבוי), F14-A1/B1 (contact resolution gate), Emergency
  Stop backing hardening (fail-closed). כל השמונה **מוזגו בפועל**, מרביתם
  structural/unwired — ראו סעיף 2.
- ממצא ארכיטקטוני קריטי (לא באג חדש, אושש ב-production ב-07/08 E2E audit,
  8/12 ממצאים): `Handler.TOOL` דטרמיניסטי קיים רק ל-`CREATE_TASK`, לא ל-
  `UPDATE_TASK`/`COMPLETE_TASK`, למרות שה-resolver/gateway כבר בנוי ומחובר.
  `PA-01_PLANNING_GATE.md` (המסמך הספציפי לפער הזה) הוא **עדיין PLANNING
  ONLY, אין קוד runtime**. (שם "PA-01" מכפיל גם ל-PR #352 — Phantom Approval
  Prompt Structural Enforcement — שכן **מוזג**, קוד הושלם, אך דגלו
  `FEATURE_PA01_ENFORCEMENT_STATE` כבוי כברירת מחדל; שני מסמכים נפרדים.)
- BUG-152 — עדיין פתוח, לא root-caused.

## 2. Current System State

**תפעולי (מאומת ב-grep/`git show` על `main`):**

- ActionContracts הוא מקור האמת היחיד למחזור-חיי approval; שחזור מ-EventBus
  TTL (BUG-158) ופרסר `parse_deterministic_create_task()` המורחב (BUG-159) —
  **VERIFIED IN PROD**.
- `claim_fingerprint_cas()`/`release_fingerprint_claim()` (BUG-157) — CAS
  אטומי, production-verified חלקית (test-only).
- Emergency Stop — כעת **fail-closed**: אם ה-backing store (Airtable) לא
  זמין, `is_enabled()` חוסם במקום להמשיך בשקט (PR #567, לא flag-gated, חי
  מיידית עם המיזוג).
- `prepare_task_proposal()` מאמת עכשיו גם `decision.owner` (לא רק
  `resolver_required`) לפני בניית הצעה — fail-closed על אי-התאמה (PR #565,
  לא flag-gated, חי מיידית).
- Airtable Gateway (`tools/airtable_gateway.py`) — נתיב הכתיבה היחיד ל-
  Airtable, ללא שינוי.
- `feature_flags.py` — אין flag חי חדש הופעל; `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`
  (TC6) ו-`FEATURE_PA01_ENFORCEMENT_STATE` (three-state) קיימים אך כבויים
  כברירת מחדל.

**מיושם חלקית / לא production-active:**

- **PA-01 Planning Gate** (Handler.TOOL ל-update/complete task) — **PLANNING
  ONLY**, אין קוד runtime. גורם היום להתנהגות לא-דטרמיניסטית אמיתית
  ב-update/complete task (Agent-driven) — אושש שוב ב-07/08 E2E audit.
- **TC6** (reply-ownership) — WS2 projection (PR #566) + `app.py` integrator
  cutover (PR #569) שניהם מוזגו; **byte-identical** להתנהגות legacy כל עוד
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` כבוי. "Duplicate authority" (שני
  מנגנונים נפרדים לחישוב gateway-ownership, מ-BUG-162) מתועד, לא אוחד.
- **TC5** (entity resolver framework, PR #562) ו-**TC4** (lead builders, PR
  #564) — קוד structural מוזג, **ללא חיווט לניתוב חי**.
- **F14** (contact resolution gate) — Phase A1 (`crm.py`, PR #568) ו-B1
  (מיגרציית callers ישנים, PR #570) מוזגו; ה-gate **תמיד-פעיל** אך עדיין
  **ללא effect התנהגותי** על משתמש הקצה — אכיפה מלאה ממתינה ל-Phase A2/B2.
- F52 Unified Status Formatter — shadow/comparison בלבד, מאחורי flag כבוי.

**חסום:** BUG-130/134/136/137/140/150/152 (וכן 126/127B/127C/138/139/142/148) —
ממתינים להחלטת owner; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.

| באג | Severity | קוד מוזג ל-main | Deployed | Production-verified |
|---|---|---|---|---|
| BUG-153/154/155/156 | גבוה/קריטי | ✅ (PR #550) | ✅ | ✅ |
| BUG-157 | גבוה, נגיש בפועל | ✅ (PR #552/#555) | ✅ | ❌ (test-only) |
| BUG-158 | גבוה | ✅ (PR #556) | ✅ | ✅ |
| BUG-159 | בינוני-גבוה | ✅ (PR #557) | ✅ | ✅ |
| BUG-160/161/162/163 | גבוה-בינוני | ✅ (PR #560) | ❌ UNVERIFIED | ❌ |

## 3. Completed Since Last Update (מאז 08/08/2026, `e9525b5..7dbdddd`, PR #562–#571)

- **PR #562 — TC5: entity resolver framework** — bounded resolver policy
  enforcement ל-AC/session/callback sources. Structural, unwired.
- **PR #564/#565 — TC4: lead builders + task-proposal hardening** — validation
  קפדנית של owner/tenant scope; `prepare_task_proposal()` מאמת גם owner
  (fail-closed, חי מיידית).
- **PR #567 — Emergency Stop backing hardening** — fail-closed כש-backing
  store לא זמין. חי מיידית, לא flag-gated.
- **PR #568/#570 — F14-A1/B1: contact resolution gate** — gate חדש ב-`crm.py`
  + מיגרציית callers ישנים דרכו; ללא effect התנהגותי עדיין.
- **PR #566/#569 — TC6 WS2 + integrator: reply-ownership cutover ב-`app.py`**
  — מאחורי `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, כבוי כברירת מחדל.
- **PR #571 — docs** — סגר את פער התיעוד ל-PR #562–#570 ב-`ROADMAP.md`/
  `CHANGELOG.md`; אין עוד פער תיעוד ידוע נכון להיום.
- BUG-105 — verification חוזר (docs-only, ללא שינוי קוד): regex זהה
  לפני/אחרי, 204 suites + 11 בדיקות מטריצת פורמטים עברו.

## 4. Next Priorities

1. **Deploy + אימות production** ל-PR #558–#571 — הפער בין `main` (`7dbdddd`)
   לבין ה-deploy החי האחרון המאומת (`44fe0fb`) הולך וגדל; לאמת commit נוכחי
   מול Render לפני כל טענת "פרוס".
2. **תעדוף מימוש PA-01 Planning Gate** (`Handler.TOOL` ל-`UPDATE_TASK`/
   `COMPLETE_TASK`) — הפער אושש חי ב-production פעמיים כעת (8/12 ממצאי
   E2E); דורש Cross-Layer Impact Matrix לפני כל קוד runtime.
3. **החלטת owner על הפעלת TC6** (`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`) —
   WS2+integrator מוזגו במלואם; גם להכריע על "duplicate authority"
   (BUG-162) ותזמון איחוד ה-interim patch.
4. **חיווט F14 Phase A2/B2** — ה-gate קיים ותמיד-פעיל אך ללא אכיפה בפועל על
   נתיבי כתיבת Contact.
5. חקור את BUG-152 (עדיין לא root-caused) ואת שאר הבאגים החסומים
   (130/134/136/137/140).
