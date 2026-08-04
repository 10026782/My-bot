# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב-26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 02/08/2026 · **origin/main:** `7c3833a` (PR #524)
**פער תיעוד שנסגר בעדכון זה:** `ROADMAP.md`/`CHANGELOG.md` עדיין לא תיעדו PRs #521–#524
(עודכנו לאחרונה עד PR #517–#520) — נכתב כאן ובקטע ה-catch-up ישירות מ-`git log`/`git show`
על `origin/main`, לא מהמסמכים. תואם הנחיית "MAIN > DOCS".

**עדכון (04/08/2026):** ארבעה באגים חדשים נרשמו מאימות Staging ל־PR #546 (Turn Coordinator) ב־03/08/2026:
- **BUG-153** — בקשת create חדשה אחרי rejection נחסמת (גבוה)
- **BUG-154** — ניסוח "ל־תאריך" מפיל את parser (גבוה)
- **BUG-155** — TTL expiry אינו סוגר את ה־ActionContract (קריטי)
- **BUG-156** — השעה משתתפת בזהות אך אינה נשמרת בכתיבה (בינוני-גבוה)
כולם רשומים ב-`BUG_AUDIT_LOG.md` עם פרטים מלאים. בנוסף דורשת בדיקה: fault injection ל-suppression fallback כשל בשליחת notification ראשונה.

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- **פער deploy מתרחב:** ה-deploy החי האחרון המתועד הוא `5ec37b8` (עד PR #516);
  `origin/main` הנוכחי (`7c3833a`) כולל בנוסף PR #517–#524 (8 PRs) שעדיין **לא פרוסים**.
  ביניהם **D-018 (PR #524) אינו מאחורי flag** — תיקון טקסט משתמש שכבר "חי" ברגע ה-deploy.
- F52 Unified Status Formatter המשיך: D-014 עד D-018 (ניסוח `approval_pending` שאושר ע"י
  הבעלים, פתרון Approval Pending Batch Migration OQ1–OQ5, תיקון דליפת `tool_name` גולמי
  ב-reconfirmation) — רובם עדיין מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (shadow/כבוי);
  D-018 הוא היוצא מן הכלל, לא-מאחורי-flag.
- דגלי approval כפי שאומתו ב-Render ב-30–31/07/2026: `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`,
  `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, `FEATURE_ACTION_GATEWAY` — כולם `true`;
  ברירת המחדל בקוד נשארת `off` בכל השלושה. לא אומת מחדש בעדכון הזה (ראה המסמך המקורי).
- Emergency Stop (5 דגלים, durable ב-Airtable) נשאר מאומת בפרודקשן.
- **BUG-152** — נרשם, לא root-caused. `BUG_AUDIT_LOG.md` **לא השתנה** מאז הבריפינג הקודם
  (אומת ב-`git diff 9f203f4..7c3833a`) — אין פריט 🔴 חדש.
- ענף `claude/rp5-staging-fault-injection-v4akit` נשאר לא-ממוזג ל-`main` **במכוון** —
  ענף staging בלבד, כמתועד ב-`CHANGELOG.md`.

## 2. Current System State

**תפעולי (מאומת ב-grep/`git show` על `main`):**

- ActionContracts הוא מקור האמת היחיד למחזור חיי approval; מסלולי legacy (`app.py`
  `_pending_approvals`) ו-TMA קיימים במקביל — יש להבחין ביניהם, לא לערבב.
- `describe_pending_queue()`/`query_execution_status()` מתכנסים (D-017, מאחורי flag כבוי
  כרגע) לניסוח משותף ל-count=0/1/batch; טקסט legacy ("ActionContracts") נשאר בשימוש כל עוד
  הדגל כבוי.
- דליפת `tool_name` גולמי ב-`_describe_contract_for_reconfirmation()` תוקנה (D-018,
  **לא מאחורי flag**) בשלושה מסלולים חיים — `describe_pending_queue()`,
  `describe_superseded_reason()`, פרומפט reconfirmation — ממתין ל-deploy.
- Airtable Gateway (`tools/airtable_gateway.py`) הוא נתיב הכתיבה היחיד ל-Airtable.
- Lead Capture / Scoring / Memory / Followup — קיימים בקוד, כולם flag-gated וכבויים כברירת מחדל.

**מיושם חלקית / לא production-active:**

- F52 Unified Status Formatter — shadow/comparison בלבד עבור רוב המסלולים (D-014–D-017);
  D-018 הוא היחיד שאינו shadow — משנה טקסט חי ברגע ה-deploy.
- Daily Digest lead-temperature summary (PR #517) — קוד קיים, **טרם פרוס**.
- Cost Telemetry (`core/usage_telemetry.py`) — shadow-only.
- TurnCoordinator / Cross-Layer Authority Contract V1 — תכנון בלבד, `READY FOR OWNER DECISION`.
- Meta WhatsApp outbound — honest stub, חסום ע"י אישור Meta Cloud API.

**חסום:**

- BUG-130/134/136/137/140/150/152 (וכן BUG-126/127B/127C/138/139/142/148) — ממתינים להחלטת
  owner או לחקירה נוספת; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.
- `sheets_append` positional canonicalization ו-mutation-budget exception — מאומתים ביחידה
  בלבד, לא בנתיב production מדויק.

## 3. Completed Since Last Update (מאז 01/08/2026, PR #520)

- **PR #521** — רגנרציית `AI_CONTEXT.md` הקודמת + סגירת פער תיעוד ROADMAP/CHANGELOG ל-PR
  #517–#520 (הוחלפה בעדכון הנוכחי).
- **PR #522** — תיקון פער parity ב-shadow של outcome `pending`: `_compose_status_reply_unified()`
  תיאר כל חוזה pending גנרית, בעוד המסלול החי כבר מציג את כותרת המשימה ל-Task-creation
  contracts — נסגר; shadow בלבד, אין שינוי flag.
- **PR #523** — F52 D-014 עד D-017: אישור בעלים לניסוח `approval_pending` הקנוני (D-014);
  פיצול ניסוח prompt-חדש מול status-query (D-015); חיווט המקרה היחיד-ב-queue של
  `query_execution_status()` (D-016); פתרון 5 השאלות הפתוחות (OQ1–OQ5) של Approval Pending
  Batch Migration — count=0/1/batch מתכנסים ל-renderers משותפים, שם "ActionContracts" יורד
  מהטקסט היעד (D-017). כולם עדיין מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (כבוי). כולל
  שני מסמכי scope תכנוניים ותיקון תאריכים בעקבות ביקורת CodeRabbit.
- **PR #524** — D-018: תיקון דליפת `tool_name` גולמי ב-`_describe_contract_for_reconfirmation()`
  בשלושה מסלולים חיים ללא flag — משפיע על טקסט משתמש בפועל ברגע ה-deploy הבא. תיקן גם
  assertion ישן שהתבסס על הדליפה.
- כל ארבעת ה-PRs נמזגו ל-`main` ואומתו ב-`git log`; מבין כולם, **רק D-018** משנה טקסט חי
  ללא flag — כל השאר shadow/dev-tooling בלבד. אף אחד לא פרוס עדיין.

## 4. Next Priorities

1. סגור את פער ה-deploy המתרחב — `origin/main` כעת 8 PRs (#517–#524) לפני ה-deploy החי
   האחרון (`5ec37b8`); D-018 בפרט הוא תיקון טקסט-משתמש ללא flag שממתין לשילוח.
2. עדכון זה סוגר את פער התיעוד ל-PR #521–#524 — לשמור על קצב עדכון שוטף כדי שלא יצטבר שוב.
3. חקור את BUG-152 עם Render logs ותרחיש מבודד (עדיין לא root-caused).
4. קבל החלטות owner ל-BUG-130/134 ול-TurnCoordinator Phase 2 (חסומים ע"י Cross-Layer gate).
5. אמת בנפרד את `sheets_append` positional canonicalization ואת mutation-budget exception
   בנתיב production אמיתי (לא רק unit tests).
