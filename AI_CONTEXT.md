# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקורות הקנוניים ראו `ROADMAP.md`, `CHANGELOG.md`, `BUG_AUDIT_LOG.md`,
> `CHANGE_CONTROL_LOG.md` ומסמכי הארכיטקטורה. `CANONICAL_STATE.md` **לא קיים**.
> `BOSS_CURRENT_STATE.md` עודכן לאחרונה ב-26/06/2026 והוא ארכיון היסטורי בלבד.
> **main גובר על מסמכי תכנון בכל סתירה. "תוקן" ≠ "מאומת בפרודקשן".**

**עודכן:** 01/08/2026 · **origin/main:** `9f203f4` (PR #520)
**פער תיעוד ידוע:** `ROADMAP.md`/`CHANGELOG.md` עדיין לא מתעדים PRs #517–#520 (עודכנו לאחרונה
עד PR #515/#516) — נכתב כאן ישירות מ-`git log origin/main`, לא מהמסמכים. תואם הנחיית
"MAIN > DOCS".

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM.
- **פער deploy ידוע וממשיך:** ה-deploy החי האחרון המתועד הוא `5ec37b8` (עד PR #516);
  `origin/main` הנוכחי (`9f203f4`) כולל בנוסף PR #517–#520 שעדיין **לא פרוסים**.
  ראו `docs/architecture/action-gateway/PRODUCTION_30JUL2026_RENDER_VERIFICATION.md`.
- Emergency Stop (5 דגלים, durable ב-Airtable) הושלם ואומת בפרודקשן ישירות ע"י הבעלים (restart אמיתי).
- שלושת דגלי ה-approval (`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`,
  `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, `FEATURE_ACTION_GATEWAY`) דווחו כ-`true` ב-Render
  ב-30–31/07/2026; ברירת המחדל בקוד נשארת `off` בכל השלושה.
- **BUG-152** (בקשת אישור שנעצרה, נדרשה שליחה חוזרת) — נרשם, לא root-caused.
- 14 פריטי BUG-* פתוחים (🔴) ב-`BUG_AUDIT_LOG.md`, בעיקר בגבולות ingress/approval-lifecycle;
  אין פריט חדש שנוסף מאז הבריפינג הקודם.
- ענף `claude/rp5-staging-fault-injection-v4akit` נשאר לא-ממוזג ל-`main` **במכוון** —
  ענף staging בלבד (לא abandoned work), כפי שמתועד ב-`CHANGELOG.md`.

## 2. Current System State

**תפעולי (מאומת ב-grep על `main` ו/או ב-CI):**

- ActionContracts הוא מקור האמת למחזור חיי approval; קיימים במקביל מסלולי legacy (`app.py`
  `_pending_approvals`) ו-TMA — יש להבחין ביניהם, לא לערבב.
- `describe_pending_queue()` עונה על "מה ממתין לאישור" רק מתוך `ActionContracts`.
- Context Librarian (`tools/context_librarian`) — כלי פנימי ל-agents, budget enforcement ו-notes
  rendering תוקנו ב-PR #520; אין שינוי לבוט העסקי.
- Airtable Gateway (`tools/airtable_gateway.py`) הוא נתיב הכתיבה היחיד ל-Airtable.
- Lead Capture / Scoring / Memory / Followup — קיימים בקוד, כולם flag-gated וכבויים כברירת מחדל.

**מיושם חלקית / לא production-active:**

- F52 Unified Status Formatter (`FEATURE_UNIFIED_STATUS_FORMATTER`) — עדיין shadow/comparison
  בלבד; PR #518 (31/07) הרחיב את חיווט ה-`MessageContract` מ-outcome `failed` בלבד גם ל-`pending`,
  אך זה עדיין מאחורי אותו דגל shadow, לא enforce.
- Daily Digest lead-temperature summary (PR #517, 31/07) — קוד קיים ב-`daily_digest.py`, **טרם
  פרוס** (אחרי ה-deploy החי `5ec37b8`).
- Cost Telemetry (`core/usage_telemetry.py`) — shadow-only, לא מפעיל את ה-trigger החי.
- TurnCoordinator / Cross-Layer Authority Contract V1 — תכנון בלבד, `READY FOR OWNER DECISION`.
- Meta WhatsApp outbound — honest stub, חסום ע"י אישור Meta Cloud API.

**חסום:**

- BUG-130/134/136/137/140/150/152 (וכן BUG-126/127B/127C/138/139/142/148) — ממתינים להחלטת
  owner או לחקירה נוספת; חלקם חסומים ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.
- `sheets_append` positional canonicalization ו-mutation-budget exception — מאומתים ביחידה בלבד,
  לא בנתיב production מדויק.

## 3. Completed Since Last Update (מאז 31/07/2026, PR #509/#519)

- **PR #515** — Context Librarian: dry-run estimate mode (`estimate_bundle`/`estimate_all_profiles`
  + CLI `estimate`), flag-off, dev tooling בלבד.
- **PR #516** — תיעוד: השלמת רישום PR #506–#515 ב-`CHANGELOG.md`/`ROADMAP.md`.
- **PR #517** — `daily_digest.py`: סיכום טמפרטורת-לידים (HOT/WARM/COLD) חדש בדוח היומי. **לא
  פרוס עדיין.**
- **PR #518** — "PR E": חיווט outcome `pending` (בנוסף ל-`failed` הקיים) דרך
  `MessageContract`/`ActionFact` adapter, עדיין מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER`
  (shadow), ללא שינוי ל-authority/evidence.
- **PR #519** — רגנרציה קודמת של `AI_CONTEXT.md` (הוחלפה במסמך הזה).
- **PR #520** — תיקון אכיפת token-budget ו-refactor ל-rendering של notes ב-Context Librarian —
  dev tooling, אין שינוי runtime לבוט.
- כל חמשת ה-PRs נמזגו ל-`main` ואומתו ב-`git log`; אף אחד מהם לא שינה התנהגות-ברירת-מחדל של
  הבוט העסקי (כל שינוי אמיתי ל-runtime נשאר מאחורי flag כבוי או טרם פרוס).

## 4. Next Priorities

1. עדכן `ROADMAP.md`/`CHANGELOG.md` עם PR #517–#520 (פער תיעוד פתוח שצוין למעלה).
2. סגור את פער ה-deploy: פרוס את `origin/main` הנוכחי (כולל PR #517 digest summary) ל-Render.
3. חקור את BUG-152 עם Render logs ותרחיש מבודד.
4. קבל החלטות owner ל-BUG-130/134 ול-TurnCoordinator Phase 2 (חסומים ע-Cross-Layer gate).
5. אמת בנפרד את `sheets_append` positional canonicalization ואת mutation-budget exception
   בנתיב production אמיתי (לא רק unit tests).
