# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing) תמציתי, לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו. `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה
> 26/06/2026) — **לא** מקור אמת נוכחי. **main גובר על כל מסמך תכנון בכל סתירה.**
> **פער תיעוד ידוע, מעודכן 29/07/2026:** `CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` היו לא-מעודכנים
> מ-PR #471 (27/07) ועד PR #492 — נסגר עכשיו (C175–C180, ראו התוספת מ-29/07/2026 למטה).
> **הפער שעדיין פתוח:** הגוף הראשי של המסמך הזה (§1–§4 למטה) עדיין לא זז מ-27/07/2026 —
> BUG-130/134/136-140, TurnCoordinator, Cost Telemetry לא נבדקו/עודכנו מאז. אל תניחו שהם
> נפתרו. ראו `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` (מקור-אמת מלא ומעודכן) לפני כל טענה
> על נושאים שאינם ה-approval/Context-Librarian track.

**עודכן:** 27/07/2026 (+ תוספת PR #471, + תוספת 29/07/2026 ל-approval/Context-Librarian
track בלבד — ראו למטה) · **main:** `b872e46` (מיזוג PR #499)

**תוספת (30/07/2026) — סבב אימות חי בפרודקשן, PR2 staging acceptance audit נסגר ברובו:**
הבעלים אישר: `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`,
ו-`FEATURE_ACTION_GATEWAY` **שלושתם `true` בפרודקשן כרגע** (לא רק staging) — זה משנה את
הקביעה הקודמת ("שני הדגלים כבויים") שהייתה נכונה בזמן כתיבתה (29/07 מוקדם) ולא מאז. 4 בדיקות
חיות רצו (`my-bot-jqz2.onrender.com`, Telegram, 30/07/2026):
- **Hotfix E (PR #497) ✅ Verified בפרודקשן** — "כן" בלי live contract → "אין פעולה שממתינה
  לאישור" הקנוני, `agent_calls=0` `deterministic=True`. פרטים: `CHANGE_CONTROL_LOG.md` C183.
- **Hotfix C (PR #498+#499) ✅ Verified בפרודקשן** — "תייצר משימה..." זוהה נכון כ-CREATE_TASK
  דרך הכלל עם ה-`\b` (מוודא שגרסת PR #499 היא הפרוסה, לא רק #498). פרטים: C184.
- **BUG-151 — היכולת העסקית הכללית ✅ Verified בפרודקשן** — יצירת Tasks עם תאריך יעד עברה
  קצה-לקצה, ללא `CanonicalizationError`. **חשוב לדייק בהיקף:** זו **לא** אימות של Fix #1
  (הממיר `sheets_append→airtable_add`) ולא של Fix #2 (חריגת ה-mutation-budget עבור
  `CanonicalizationError`) — שניהם דורשים ש-`CanonicalizationError` יקרה בפועל כדי להיבדק,
  וזה לא קרה כאן: ה-Agent בחר `airtable_add` ישירות בשני סבבי הבדיקה
  (29/07, 30/07). נשאר מאומת בבדיקת יחידה בלבד. פרטים: BUG-151 תוספת, C181 תוספת.
- **Hotfix B (PR #496)** — לא ניתן לאימות חי במצב-הדגלים הנוכחי: המסלול הישן ב-`app.py:3391`
  רדום כש-PR2 דלוק (`_resolve_pr2_deterministic_approval()` מיירט קודם). Verified by test בלבד.
  פרטים: C182.

**ממצא חדש, לא מתוקן (BUG-152):** תוך כדי בדיקת BUG-151, בקשה חדשה דומה (אחרי ביטול משימה)
נעצרה פעם אחת ע"י ה-Agent ורק בשליחה חוזרת נוצר כרטיס אישור. לא root-caused — 3 השערות
פתוחות (השפעת היסטוריית-שיחה / שער דדופ-fingerprint / race זמנים). דורש שחזור מבוקר עם לוג
מלא. פרטים: `BUG_AUDIT_LOG.md` BUG-152.

**נפרד, לא קשור לסבב הזה, נצפה באותה שיחה:** בקשה ל"לידים בענף גיוס" נכשלה כי ה-Agent ניחש
`domain='hr'` בפילטר Airtable — הערך הקנוני האמיתי (`airtable_schema.py:917`) הוא `recruitment`.
שורש כפול: (1) `tools/schemas.py`'s `airtable_get` לא חושף למודל אף enum של ערכי-שדה תקפים,
כך שהוא מנחש בלי עוגן; (2) שאילתת Business Memory מוגבלת-domain (התאמה לפי domain של הטורן
הנוכחי) יכולה "לשכוח" עובדות-מילון שנלמדו תחת domain אחר. **לא תוקן, לא דחוף** — הבעלים ביקש
לטפל בזה במסגרת תכנית ה-4-layers (Agent Surface Reduction / grounding), לא כ-hotfix נפרד.

**תוספת (27/07/2026):** PR #471 — Single-Speaker Approval UX Base — מוזג ל-`main`. `ApprovalLifecycleResult` הוא תוצאת ה-UX הקנונית למסלולי approval; Gateway מקבל בעלות על התשובה כשהדגל מופעל וה-Agent נעצר לאחר handoff. BUG-144 (reject callback שלא סגר `ActionContract`), BUG-145 (שתי הודעות סופיות) ו-BUG-118 (חשיפת tool/contract/record identifiers בתשובות הצלחה) מיושמים וממוזגים. Redaction של מזהים הוא בלתי-מותנה גם כשהדגל כבוי. `ActionContracts` נשאר מקור האמת היחיד. `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false` בקוד וב-`.env.example`; לא הופעל ב-staging/production. callback payload מקסימלי שנבדק: 53 bytes מתוך 64. `backend-ci`/`frontend-ci` עברו על `dadf851`. **סטטוס אימות, מדויק לפי סביבה (עודכן 29/07/2026,
ראו `CHANGE_CONTROL_LOG.md` C175):** staging — 🟡 **חלקית** מאומת (Telegram/owner-role בלבד,
לאחר rebase; ראו `SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md`). production —
⏳ **לא** מאומת, `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false` שם. אימות-staging חלקי אינו אימות-
production — אין לסמן את העבודה כ-Production Verified. deterministic cost cuts והיקפי PR2
נשארו במפורש מחוץ ל-PR הזה.

**תוספת (23/07/2026, אחרי כתיבת הבריפינג הזה):** PR #449 (branch `claude/findings-exam-wikon-25zzkm`, שני commits תיקון+review-pass) — סבב ממצאים מ-`my-bot-approval-staging` (7 ממצאים, כולל דגימת production אמיתית מהבעלים). ראו §3 למטה לפירוט מלא. **הענף `claude/rp5-staging-fault-injection-v4akit` עבר rebase על גבי `main` (כולל PR #449) והועלה מחדש (force-push) — staging מריץ עכשיו את התיקון.**

**תוספת (25/07/2026):** BUG-141..146 (24/07/2026, ראו `BUG_AUDIT_LOG.md`) עדיין לא משוקפים למעלה — הבריפינג הזה לא עודכן מאז. בנוסף, דוח בדיקות Post-Merge של הבעלים (תרחישים 1–5, `claude/telegram-task-approval-audit-il29sj`) הוסיף: עדכון-ראיות ל-BUG-143 (מופע רביעי) ול-BUG-145 (כפל-הודעות נצפה גם בענף כישלון, לא רק הצלחה); ראיה **סותרת-לכאורה** ל-BUG-144 (תרחיש-דחייה עבר `rejected` כראוי — אבל קריאת קוד מאשרת שכפתור-הדחייה של Telegram, `app.py:2409-2449`, עדיין לא תוקן; סביר שהדוח תרגל מסלול-ביטול-מילולי נפרד שכבר עובד — לא הוכרע, דורש בירור); ו-**BUG-147 חדש** — `tools/dispatcher.py`'s `airtable_add` מחזיר מחרוזת גולמית (לא dict מובנה) בשני מסלולי-חסימה, משחזר עצמאית את "expected structured result dict; got plain string". תיעוד-בלבד, אין קוד runtime שהשתנה — ראו BUG_AUDIT_LOG.md/CHANGE_CONTROL_LOG.md C172.

**תוספת (29/07/2026) — פער-תיעוד גדל, לא נסגר: עודכן רק מה שאומת ישירות בסבב הזה.**
גוף הבריפינג הזה (§1–4 למטה, לא הכותרת למעלה — ראו שם את ה-commit העדכני) עדיין לא זז
מ-27/07/2026 עבור רוב הנושאים —
BUG-130/134/136-140, TurnCoordinator, Cost Telemetry — **אף אחד מאלה לא נבדק/עודכן בסבב
הזה**, אל תניחו שהם נפתרו או השתנו. מה שכן אומת ישירות ב-`origin/main` (grep, לא רק PR
status) ועודכן כאן:
- **PR #479** (ממוזג `e663818`) — סוגר בפועל את הפער שנמצא ב-claim 4 של
  `SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md`: `_describe_contract_for_reconfirmation()`
  כבר לא חושף שם-טבלה גולמי ב-fallback הכללי. אומת ישירות מקריאת הפונקציה על `main`.
- **PR #480** (ממוזג `11e58df`) — D-012: `MessageContract` מאושר כקלט הפורמטר הקנוני היחיד,
  סוגר את D-011 (drift מ-PR #471) בפיוס לא מחיקה. תיעוד-תכנון בלבד, implementation לא מאושר.
- **PR #488–#491** (Context Librarian: תכנון Consumption Enforcement + audit-remediation +
  PR2 preflight) — תיעוד-תכנון בלבד, מתועד במלואו ב-`ROADMAP.md`'s N17.
- **PR #490** (ממוזג `7ee5c5b`) — Consumption Enforcement Phase 1 מיושם: `consumption_checklist()`,
  `verify-consumption` CLI, Consumption Ledger. Phase 3 (CI gate) במפורש לא מיושם עדיין.
- **PR #492** (ממוזג `db51afc`) — PR2 (Deterministic Approval Cost Cuts) מיושם: resolver
  דטרמיניסטי מוקדם ל-approve/reject/pending-query/`יצרת?`, מאחורי `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`
  (כבוי כברירת מחדל, דורש `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`). ריויו רב-שכבתי (Claude + CodeRabbit)
  מצא ותיקן 10 ממצאים אמיתיים לפני מיזוג — כולל אחד שביטל בשקט את הגבלת ה-24h על terminal
  replay. **אין claim ל-staging/production verification** — שני הדגלים כבויים.
- פירוט מלא של כל אלה: `ROADMAP.md` (N17 items 8–11), `CHANGELOG.md`, `CHANGE_CONTROL_LOG.md`
  C175–C180.

**תוספת (29/07/2026, המשך אותו יום) — PR #494 (Hotfix A) מוזג, BUG-151 (חדש) ✅ תוקן ומאומת
ב-staging עם הסתייגות מדויקת:** תוך כדי audit קבלה ל-PR2 עצמו נתפס תרחיש staging אמיתי (לוגי
Render + רשומות `ActionContracts` בפועל): בקשת "צור משימה באיירטאבל" נכשלה פעמיים
(`CanonicalizationError` — הממיר ה-positional ל-Tasks תמך בערך אחד בלבד, ה-payload בפועל כלל 2),
בלי שנוצר `ActionContract` כלשהו; "כן" הבא (בלי live contract) שיחזר `ActionContract` **לא-קשור**
(ליד שהושלם ~4 שעות קודם) ודיווח "הפעולה כבר הושלמה" — לא נוצרה שום משימה. **PR #494 (ממוזג
`186832a`)** תיקן שלושה דברים: (1) הממיר תומך עכשיו ב-1 או 2 ערכים positional ל-Tasks; (2) כשל
canonicalization לא נספר יותר נגד תקציב ה-mutation של BUG-122; (3) `_resolve_pr2_deterministic_
approval()`'s ענפי "כן"/"לא" בלי live contract כבר לא קוראים ל-`find_recent_terminal_by_user()`
בכלל — recency אינה correlation, בשום חלון (חלון-ביניים של 10 דק' עדיין נכשל בבדיקה עצמאית). Full
sweep 175/175 + `smoke_tests.py`/`test_integration.py`/`core/router/test_router.py` לפני המיזוג.
**✅ Verified ב-staging בפועל** (contract `a428e48b`, 14:25–14:29) — **אך בנתיב-כשל שונה** מהמקורי:
`ActionContract` כן נוצר הפעם (calendar_create_event, לא sheets_append/airtable_add), נכשל בביצוע
(Google OAuth חסר — פער-סביבה, לא קוד), "כן" הבא נכון החזיר "אין פעולה שממתינה לאישור" ולא שחזר את
ה-contract הכושל — מאמת את אינווריאנט תיקון #3, **לא** מאמת עצמאית את תיקון #1 (positional
canonicalization) בנתיב-הכשל המקורי המדויק. פירוט מלא: `BUG_AUDIT_LOG.md` BUG-151,
`CHANGE_CONTROL_LOG.md` C181, `docs/architecture/f52-unified-approval-runtime/audits/
PR_HOTFIX_A_CROSS_LAYER_IMPACT_MATRIX.md`. פתוח לפר הבא: Router regex ל-"תייצר", אכיפת
Single-Speaker בפועל (כרגע log-only), הסתרת sheets_append/drive_* מהכלים כברירת מחדל, מסלול cancel
ישן (`app.py:3391`) שעדיין לא מעביר `recent_terminal=None` (ממצא CodeRabbit).

**תוספת (26/07/2026) — BUG-143/144/145/147 כולם ✅ תוקנו בפועל ומאומתים חי ב-staging, ו-BUG-149 חדש נמצא ותוקן:**
- **BUG-143** (PR #461, `70093f0`/`719bb86`), **BUG-144+145** (PR #460, `006506d`/`0c06f4c`), **BUG-147** (PR #469 "Patch A", `3b111f6`/`e946225`) — כולם ממוזגים ל-`main`, ו**מאומתים חי ב-staging** דרך סבב הבדיקה החוזרת של הבעלים (PM460-RETEST, 26/07/2026): תרחיש 3 (canonicalization) ✅ PASS, תרחיש 4 (reject lifecycle, כולל כפתור inline עצמו — פותר סופית את אי-הוודאות שנרשמה ב-BUG-144) ✅ PASS, תרחיש 5 — BUG-147 עצמו לא חזר (✅), אבל נחשף **BUG-149 חדש** באותו תרחיש. פירוט מלא + git evidence: `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md` C173.
- **BUG-149 (חדש, 26/07/2026)** — תרחיש 5 חשף שהמערכת ביצעה payload ישן/כבר-נדחה (מתרחיש 3) במקום הבקשה הנוכחית של המשתמש. שורש: `memory.add()` לא שומר תוצאת-אישור/דחייה, כך שה-Agent "זוכר" בקשות ישנות כפתוחות-לכאורה ומנסה ליצור אותן מחדש יחד עם הבקשה הנוכחית; שער BUG-122 הקיים שומר רק את tool_use הראשון מבין כמה, שיכול להיות דווקא הישן. **תוקן (PR #470, `ceb9148`/`59e74be`)** — שתי שכבות: (1) `ActionResolutionEvent`/`core/action_resolution_projection.py` (חדשים) מזרימים תוצאת-lifecycle אמיתית לתוך context נפרד ומסומן ב-`memory_store.py`, ללא ש-`ActionGateway` נוגע ב-`memory_store` ישירות (DI, אותו דפוס כמו `tool_executor`); (2) שער דטרמיניסטי חדש `MULTI_MUTATION_CONTEXT_MISMATCH` — תגובת-מודל עם 2+ tool_use מוטטים חוסמת את **כולם**, לא שומרת ראשון/אחרון. עבר תכנון מלא עם Cross-Layer Impact Matrix לפני מימוש. 38 בדיקות חדשות + 2 test blocks קיימים עודכנו, full sweep 172/172. פירוט מלא: `BUG_AUDIT_LOG.md`'s BUG-149, `CHANGE_CONTROL_LOG.md` C174.
- **`claude/rp5-staging-fault-injection-v4akit` עבר rebase פעמיים בסבב הזה** — פעם אחת מעל PR #469 (force-push, `da7a8ab`), ופעם שנייה מעל PR #470 (force-push, `67c595d`) — שתי הרבייזים נקיים לחלוטין (0 קונפליקטים), עם שימור מלא של RP5-only hooks ואי-שחזור מכוון של commit-ה-PM460 העצמאי הישן של הענף (התנהגותו כבר קיימת ב-`main` דרך PR #460/#461). Full sweep על הענף המרובייז הסופי: 175/175. **טרם בוצע deploy ידני + re-run של תרחיש 5 נגד `67c595d` ספציפית** — נדרש לפני שניתן לקבוע "BUG-149 VERIFIED IN STAGING" לפי "כלל ברזל".

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד — ללא שינוי במסלול הזה בסבב הזה.
- **Emergency Stop (PATCH 3B) הושלם ואומת בפרודקשן ישירות ע"י הבעלים** — 5 דגלי `EMERGENCY_STOP_*` דביקים ב-Airtable (שורדים restart אמיתי), TMA UI עם כפתורי Stop/Clear מלאים כולל Stop All.
- **סבב תיקוני-באג נרחב באישור/ניתוב-הודעות (BUG-111 עד BUG-127, כולל 114/115/116/117/121-124) — כולם ✅ VERIFIED IN PROD** עם evidence מלוגים אמיתיים.
- **Cost Telemetry Reliability (`usage_events`) — shadow בלבד.** לא מזיז את ה-trigger החי (`COST_WATCHDOG_LIVE=false`); PR3 (cutover) חסום בכוונה עד שיצטברו ימי-נתונים מול חיוב פרודקשן.
- **ארבעה באגים פתוחים, לא מטופלים, ממתינים להחלטת owner:** BUG-130 (עדכון-ליד קיים מנותב כיצירת-ליד חדש — כעת נצפה פעמיים נוספות בדגימת staging נוספת, ראו §3), BUG-134 (מרוץ TTL גנרי מול C84 שעלול להשאיר Approvals row תקוע `pending` שקרי — **24/07/2026: אומת ישירות מ-Airtable, 3 רשומות תקועות 4-14 ימים**), ו-BUG-136/BUG-137 (חדשים, 23/07/2026 — "בצע שוב \<קוד\>" נופל ל-Agent כשעטוף ב-markdown bold ומקבל תשובה מומצאת; הודעת הצלחת עדכון-ליד מרכיבה domain פנימי בלי תווית לתוך הטקסט). **בנוסף, 24/07/2026:** BUG-139 (RP5 shadow false-failure-claim, 47% mismatch rate) ו-BUG-140 (בקשת-ליד-חדש מנותבת כ-update נגד ליד לא-קשור עם טלפון משותף — contract עדיין pending, טרם אושר) — שניהם חדשים, מאומתים מלוגים/Airtable אמיתיים, לא תוקנו.
- **TurnCoordinator / Cross-Layer Authority Contract V1 (PR #446/#447)** — יוזמת תכנון חדשה למיזוג BUG-104/F52/Approval layer; **תכנון בלבד, אפס קוד runtime**. Phase 2 Shadow Planning סטטוס סופי: `READY FOR OWNER DECISION` (לא לביצוע), 3 החלטות פתוחות.
- **פער תיעוד פתוח:** `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` לא עודכנו מאז 21/07/2026 למרות ~9 PRs נוספים שמוזגו מאז (#440–#448). `BUG_AUDIT_LOG.md` גם מציג "Merged: ⏳ טרם" שגוי עבור BUG-129/133/135 — כולם בפועל כבר מוזגו ל-main (מאומת ב-git log), התיעוד לא עודכן אחרי המיזוג.
- **BUG-141 (AG-01, 24/07/2026) — ✅ VERIFIED IN PROD + STAGING.** תוקן (PR #457, `9d156d9`, ממוזג `c12a19b`), נבדק ב-2 סביבות נפרדות אחרי deploy: (א) production (`my-bot-jqz2`) — "מה ממתין לאישור" → "אין פעולה שממתינה לאישור... (הבדיקה מכסה את מערכת ActionContracts בלבד)", בדיוק ה-reply המצופה מ-`describe_pending_queue()`; (ב) staging (`my-bot-approval-staging`, אחרי deploy ידני של ה-owner ל-branch המרובייז `claude/rp5-staging-fault-injection-v4akit`) — אותה שאלה בדיוק, לוג מלא: `[ActionGateway] describe_pending_queue: user=boss_hq:eliyahu pending_count=0 scope=action_contracts result_code=empty`, `HTTP 200`, **ואין שום קריאת Anthropic בלוג** (בניגוד לפני התיקון, שם השאלה הזו יצרה tool loop מלא + קריאת LLM). **תצפית עלות (חלקית מאומתת):** ה-turn הספציפי הזה אכן לא מפעיל LLM כלל כרגע (מאומת ישירות מהיעדר `POST api.anthropic.com` בלוג) — ירידת-עלות מבנית אמיתית לדפוס-השאלה הזה. **תצפית הבעלים** ש"הלוגים נקיים" ו"העלות ירדה" באופן כללי (24/07/2026) **לא אומתה עדיין מול נתוני `cost_monitor`/`usage_events` בפועל** — נדרשת בדיקת hourly/daily cost אמיתית לפני שקובעים ירידת-עלות כוללת, לא רק לדפוס-שאלה בודד.

---

## 2. Current System State

**עובד בפרודקשן, מאומת:**
- Identity→Router→Context→Agent; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed).
- Approval flow: TTL אכיפה בטלגרם (BUG-112) ו-TMA (C84, 24h); תיקוני BUG-111/114/115/116/117/121-124 (batch/domain lead-parsing, confirm-word hijack ע"י contracts ישנים, Tier-4 false-positive, context-interrupt amplification, `/status` crash, pending-approval UX) — כולם עם evidence production.
- Emergency Stop: 5 דגלים דביקים ב-Airtable, `is_enabled()`/`set_flag()` מיירטים אותם, מנגנון `/tmp` הישן הוסר לגמרי. TMA Stop/Clear מלא.
- F52 Unified Status Formatter + RP5 Evidence Finalizer — **shadow logging פעיל בפרודקשן בפועל** (evidence בלוגים אמיתיים לרוב מצבי הסיווג); `enforce`/`on` **לא** הופעלו.

**מיושם חלקית / flag off / shadow:**
- Cost Telemetry (`core/usage_telemetry.py`, PostgreSQL `usage_events`) — shadow-only, מחווט ל-6 נקודות-קריאה אמיתיות (Anthropic + OpenAI Whisper), לא מניע את ה-trigger החי. PR3 (cutover מ-`cost_monitor.py`) לא נפתח.
- BUG-104 Core Reasoning (Phases 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests, `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow. Phase 2A.0 (ניקוי סכמה) עדיין SPEC-בלבד.
- TurnCoordinator Contract V1 — תכנון בלבד (`docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` + `turn-coordinator/`), `PLANNING BLOCKED`/`READY FOR OWNER DECISION`, אין flag ואין קוד.

**חסום / פתוח:**
- BUG-130 — עדכון-ליד קיים מנותב ליצירת-ליד חדש; רשום, לא תוקן. **דגימת staging נוספת (23/07/2026)** אישרה שוב את אותה תבנית פעמיים באותה שיחה (כולל על ליד שעודכן בהצלחה turn קודם), מחזקת ל-root-cause דטרמיניסטי (ראו `BUG_AUDIT_LOG.md`). סיכון collision-לפי-טלפון-בלבד (רשומה לא-קשורה עם domain שונה) נצפה גם הוא, לא אומת ישירות.
- BUG-134 — TTL גנרי (`ActionContractRepository`, 24h) עלול ליירט contract לפני שלוגיקת C84 מספיקה לרוץ; רשום, לא תוקן. **עדכון 24/07/2026:** אומת ישירות מ-Airtable (טבלת `Approvals`) — 3 מ-4 הרשומות בטבלה כולה תקועות `pending` 4-14 ימים (`recyoMWRE2Lv8Fzvk`, `recnFF6VCBVcR8apL`, `rec9VBFoLUoEX71bD`), כולן מאושרות בנפרד כ-404/409 בלוגי production. כבר לא "סביר" בלבד — מאומת עם ראיה ישירה.
- BUG-136 (חדש) — "בצע שוב `<קוד>`" עטוף ב-`*...*` (כפי שהבוט עצמו מציע) לא תואם את ה-regex המעוגן ב-`app.py`, נופל ל-Agent שמאלתר תשובה שגויה; רשום, לא תוקן.
- BUG-137 (חדש) — `_describe_contract_for_reconfirmation()` מרכיבה domain (למשל "finance") בלי תווית לתוך הודעת "✅ בוצע: עדכון ליד"; רשום, לא תוקן.
- BUG-138 (חדש) — כפתור אישור טלגרם לא נעלם אחרי אישור/דחייה; שש קריאות `edit_message_text()` ב-`app.py` לא מנקות `reply_markup`. השערה מבוססת-קוד בלבד, טרם אומתה מול Telegram/לוגים בפועל.
- BUG-139 (חדש, 24/07/2026) — RP5 shadow: `response_claim=failure`/`mixed` כשאין שום tool call בתור כלל (`evidence_status=no_evidence`); נמצא מלוגי staging אמיתיים (5/15 דגימות היום, 47% mismatch rate כולל), נשלל במפורש כארטיפקט של RP5 fault-injection (0 אירועי `[RP5FaultInjection]` באותו חלון). Root cause בקוד עדיין לא אותר. ראו `RP5_LOG_OBSERVATION_23JUL2026.md`.
- BUG-140 (חדש, 24/07/2026) — בקשה מפורשת ל"ליד חדש" (דנה כהן) יוצרה כ-`airtable_update` נגד ליד קיים ולא-קשור (ישראל כהן), ככל הנראה collision-לפי-טלפון-בלבד — בדיוק הסיכון שתועד תחת BUG-130 בלי אישור, עכשיו עם מופע קונקרטי. Contract `0e8a155c-...` עדיין `pending` (לא אושר, לא בוצע נזק) — מומלץ דחייה ידנית. אומת ישירות מ-Airtable.
- RP5 enforcement — shadow evidence קיים לרוב מצבי הסיווג (5/9 אומתו מלוגי staging אמיתיים היום, ראו BUG-139), טרם נאסף לכל 9 המצבים.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- ענף `claude/rp5-staging-fault-injection-v4akit` — staging-only בכוונה, לעולם לא ימוזג ל-main.

---

## 3. Completed Since Last Update

*(מקבץ PR #397–#448; לפירוט מלא ראה `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` C156–C168)*

- **תיקוני אישור/ניתוב (BUG-111 עד BUG-127):** סדרת תיקונים ל-`ActionGateway`/`core/ingress_classifier.py`/`app.py` — חטיפת confirm-word ע"י contracts ישנים, false-positive של Tier-4 על מילים אנגליות, הכפלת burst קריאות Airtable, קריסת `/status`, חסימת פעולה חדשה ע"י תור אישורים ישן, false-positive של פסוקית הקשר. כולם ✅ VERIFIED IN PROD עם evidence מדויק מלוגים.
- **PATCH 3B הושלם:** Steps 2–6 + prerequisite (הקשחת CI מפני credentials חיים) + TMA frontend (#425, #427, #432, #433, #436) — Emergency Stop דביק לגמרי, אומת בפרודקשן כולל restart אמיתי.
- **Cost Telemetry Reliability:** PR1 (#435, תיקון BUG-131 — כתיבה שקטה שנכשלה) → hotfix (#437, תיקון BUG-132 — השוואת טקסט מול שדה DATE) → hotfix-followup (#438, תיקון smoke script) → PR2 (#439, `usage_events` חדש, shadow טהור).
- **BUG-129/131/132/133/135 תוקנו:** self-quote ("זיהיתי") ופקודת-מחיקה שהפיקו שם-ליד מזויף (#444); כתיבה שקטה ל-`AI_Usage_Daily` (#435); השוואת טקסט/DATE שגויה (#437); test שדלף 310 רשומות אמיתיות ל-Interaction Log בפרודקשן — תוקן + הרשומות נמחקו ע"י הבעלים (#442).
- **N16:** Git Audit הוצא לגמרי מהבוט העסקי (היה כפילות מול ה-Routine) — הבוט כבר לא נוגע ב-git כלל.
- **TurnCoordinator / Cross-Layer Authority Contract V1 (#446, #447):** מסמכי תכנון חדשים — שער חובה למניעת שינוי לא-מתואם בין 4 שכבות (Core Reasoning/TurnCoordinator/F52/Approval). נמצאה והוסרה התנגשות שם (`ActionFact`). Phase 2 Shadow תוכנן במלואו, מחכה להחלטת owner — **אין קוד production שהשתנה**.
- **`scripts/render_log_export.py` (#448):** כלי דיאגנוסטיקה אופליין לחילוץ/חיפוש לוגי Render — לא מיובא ע"י `app.py`, אין סיכון production.

**פער תיעוד היסטורי שנשאר פתוח:** `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` עדיין לא סונכרנו ל-#440–448; `BUG_AUDIT_LOG.md` עדיין מציג "Merged: ⏳ טרם" שגוי ל-BUG-129/133/135.

**PR #449 (23/07/2026) — סבב ממצאים מ-`my-bot-approval-staging`, 7 ממצאים, ראו `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` לכתיבה המלאה כולל Cross-Layer Impact Matrix:**
- **תוקן (קוד+tests):** Finding #4 — `describe_pending_queue()` חדש עונה על "מה ממתין לאישור" ישירות מ-`ActionContracts` (במקום שהסוכן ינחש טבלה כמו `Tasks`) — הניסוח מצוין במפורש שהוא מכסה `ActionContracts` בלבד, לא תורי legacy נוספים (`_pending_approvals`/`event_bus.pending`). Finding #3 — `route_disambiguation()`/`route_combined_word()` מגלים עכשיו למשתמש כמה siblings נדחו אוטומטית; הספירה מבוססת על אישור-מעבר אמיתי מ-`reject()`, לא הנחה מראש (נבדק, מוגן בבדיקת רגרסיה). תוקן גם דליפת PII בלוג — שורת `describe_pending_queue()` כתבה טקסט-משתמש גולמי + תוכן-תשובה; עכשיו רק שדות מובנים (`pending_count`/`scope=action_contracts`/`result_code`).
- **תוקן חלקית — 🟡 לא FIXED מלא:** Finding #1 — `ExecutionLedger.find_live_by_user()` (`core/action_gateway.py`) לא אכף `_is_expired()`/`CONTRACT_PENDING_TTL_SECONDS` על מסלול ה-warm-cache (רק על cold-cache/repository recovery) — עכשיו עקבי בשני המסלולים. **זה תיקון-עקביות בלבד, לא הכרעת-מדיניות** — חלון ה-24h עצמו (שהוגדר במקור עבור TMA) לא שונה, ונשאר שאלת-owner פתוחה אם הוא מתאים גם לזרימות האישור האינטראקטיביות. **קשור ל-BUG-134 (למעלה, §2) — אותו קבוע `CONTRACT_PENDING_TTL_SECONDS`/`_is_expired()`, תסמין שונה:** BUG-134 הוא מרוץ בתוך *נקודת-האכיפה הקיימת* מול C84; Finding #1 היה מסלול ש*עקף* את אותה נקודת-אכיפה לגמרי. שני הבאגים לא תוקנו יחד ולא אמורים להיות מבולבלים זה בזה. אומת עם real production data (owner-supplied `ActionContracts` export + Render logs): 3 מ-6 siblings שנדחו היו בני 27-38 שעות (מעבר ל-TTL, היו נחסמים ע"י התיקון), אבל ה-contract שבפועל בוצע היה בן 14.65 שעות — בתוך ה-TTL, לא היה נחסם. אזהרת-גיל (`⚠️ ממתין מ-N שעות`, סף שעה) נוספה כמיטיגציה מיידית, בלתי-תלויה בהכרעת-ה-TTL.
- **תועד בכוונה, לא מומש — ממתין ל-TurnCoordinator:** Finding #2 (סמנטיקת §21 sibling-reject — עיצוב-במכוון לפרשנויות-חלופיות של בקשה אחת, לא לפריטים בלתי-קשורים שמצטברים; דורש classification signal חדש שלא קיים), Finding #6 (`DESTRUCTIVE_ENTITY_CLARIFICATION`/§3.2 בחוזה TurnCoordinator — עדיין לא ממומש), **Finding #7 (חדש, התגלה מנתוני הרשומה שבוצעה בפועל)** — "תוסיף איש קשר X" תמיד יוצר Lead (עם "איש קשר" מוטבע בשם + metadata של lead-funnel), אף ש-`intent_router.py` כבר מזהה נכון `Intent.CREATE_CONTACT` — `core/lead_candidate_handler.py` לא קורא לסיווג הזה בכלל. זו בדיוק תרחיש 7 המילולי בחוזה הקפוא (`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`) — אישור-ריאלי לתרחיש שכבר תוכנן, לא ממצא חדש שדורש תכנון.
- **manual action items שנשארו פתוחים:** רשומת `recK8RdYkdDmTGdob` (Leads, `my-bot-approval-staging`) — לא זבל, נראית כבקשת-contact לגיטימית שביצעה באיחור של 14.65 שעות; דורשת אישור-owner אם רצויה. הכרעת-owner על חלון ה-TTL (30 דק'/שעה/24h) ל-Finding #1.
- **`claude/rp5-staging-fault-injection-v4akit` עבר rebase על `main` (כולל PR #449) והועלה מחדש (force-push)** — staging מריץ עכשיו את כל התיקונים למעלה.

---

## 4. Next Priorities

1. **החלטת owner: BUG-130** — כיוון תיקון לעדכון-ליד-קיים המנותב כיצירה חדשה (מתח ארכיטקטוני מול השומר של BUG-094). דגימה נוספת (23/07/2026) מחזקת עדיפות.
2. **החלטת owner: BUG-134** — כיוון תיקון למרוץ ה-TTL הגנרי מול C84 (Approvals row עלול להישאר `pending` שקרי).
2א. **החלטת owner: BUG-136/BUG-137 (חדשים, 23/07/2026)** — תיקון markdown-stripping ל-override regex, ותיוג שדה domain בהודעת הצלחה. שני אלה נוגעים ב-F52/Approval layer (`core/action_gateway.py`) — טעונים שער Cross-Layer Authority Contract לפני מימוש.
3. **החלטת owner: Finding #1 (PR #449) — חלון TTL לאישור אינטראקטיבי** — האם 30 דק'/שעה/24h (הקיים), נפרד משאלת BUG-134.
4. **TurnCoordinator Phase 2 Shadow** — 3 החלטות owner פתוחות (סביבת staging, איחוד ActionGateway, scope של CapabilityScope) לפני שקוד shadow ראשון נכתב. **תרחיש 7 בחוזה (CREATE_CONTACT ownership) קיבל אישור-ריאלי נוסף (Finding #7 למעלה) — עוד נימוק לתעדף.**
5. **המשך shadow soak ל-F52/RP5** — לצבור את שאר מצבי הסיווג הנדרשים לפני שיקול הפעלת `enforce`/`on`.
6. **סנכרון תיעוד** — לעדכן `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` ל-PR #440–449 ולתקן את סטטוסי "Merged: ⏳ טרם" השגויים ב-`BUG_AUDIT_LOG.md`/`CHANGELOG.md`.
7. **manual: `recK8RdYkdDmTGdob`** — owner לאשר אם רצוי לשמור.
