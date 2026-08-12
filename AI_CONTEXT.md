# AI CONTEXT

**עודכן:** 12/08/2026 · **origin/main:** `4c94d68` (PR #605 — merge of F23 M1
batch, internal history #601–#604).

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך תמציתי, לא תיעוד מלא.
> למקור האמת ראו `ROADMAP.md` (קודם כול), `CHANGELOG.md`, ו-
> `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` (קנוני ל-CORE, מבוסס main
> `134148e`; ללא drift פונקציונלי מאז ל-CORE עצמו). `BOSS_CURRENT_STATE.md`
> **stale מ-26/06/2026** — ארכיון היסטורי, לא לצטט כמצב נוכחי. **main גובר
> על מסמכי תכנון בכל סתירה. "מוזג" ≠ "פרוס" ≠ "מאומת בפרודקשן."**

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity → Router →
  Context → Agent, Airtable כ-CRM.
- **CORE v1 — COMPLETE / READY TO FREEZE** (freeze עצמו = החלטת owner, לא
  מוכרז). קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`, נבנה מול
  main `134148e`, כולל אימות Production+Staging חי (Render API + logs).
  ללא שינוי בסבב הזה.
- **חדש: F23 — BOSS Marketing Bridge M1** (`/marketing_new` wizard ב-
  Telegram) מוזג ומדווח **✅ VERIFIED IN PROD** ב-ROADMAP, עם ראיה ישירה
  (רשומת Demand אמיתית, deploy-SHA מול Render API — ראו סעיף 3). **פער
  ממשל שנסגר בסבב הזה:** `CHANGELOG.md` לא כלל רשומה לבאץ' הזה עד לעדכון
  הנוכחי — נוספה רשומה מתאימה (ראו סעיף 3), אז ה-cross-doc gap כבר סגור.
- שני פערים לא-חוסמים ב-CORE נותרים ללא שינוי: (1) CI של `main` אדום על
  שער ה-freshness של Context Librarian (governance, לא regression
  פונקציונלי); (2) `TurnCoordinator` הפורמלי (Layer 2) — אפס מימוש,
  מוחלף כיום ע"י `router.py::route_request()`.
- TC7-B1 (`core/claim_authorization.py`) — עדיין **אפס קוראים חיים**, ללא
  שינוי מהסבב הקודם.
- RP5 enforcement ו-F52 unification (`FEATURE_UNIFIED_STATUS_FORMATTER`) —
  עדיין shadow/כבוי כברירת מחדל, לא הופעלו.

## 2. Current System State

**תפעולי** (מאומת ב-grep/log/Render API על `main`):

- ActionGateway/ActionContract lifecycle — מקור אמת יחיד, חי, ✅.
- CORE v1 (ActionGateway, TC6/TC8/TC9, F14/F15, PA-01, Track D, RP4/RP5
  shadow) — ✅ כפי שתועד בסבבים קודמים, ללא שינוי.
- **F23 M1 (`/marketing_new`)** — Demand→intake conversational→Brief
  דטרמיניסטי→קריאת AI יחידה→3 רעיונות→בחירה בכפתור→Production Handoff
  דטרמיניסטי. `FEATURE_MARKETING_BRIDGE=true` **דלוק בפרודקשן כרגע** (לא
  ברירת מחדל בקוד — הודלק לבדיקה חיה ולא כובה מאז). בחירת קריאייטיב וקישור
  Publication נשארים ידניים דרך Airtable; UI מלא/TMA נדחו ל-M2 (לא התחיל).
  ✅ תפעולי לפי ROADMAP+ראיה ישירה.

**מיושם חלקית / לא production-active:**

- TC7-B1/B1.1 (`core/claim_authorization.py`) — בנוי, אפס קוראים חיים.
- RP4/RP5 shadow (`FEATURE_EVIDENCE_FINALIZER=shadow`) — comparison
  logging בלבד; enforcement חסום עד אישור owner מפורש.
- F52 Unified Status Formatter — shadow/comparison בלבד, כבוי כברירת מחדל.
- ws2/ws3 evidence/lifecycle projection modules — מוזגים, לא מחווטים
  ל-`core/action_gateway.py`, לא רשומים ב-Context Librarian catalog.
- **F23 Marketing Rules (Business Memory)** — `marketing_gateway.
  save_marketing_rule()` קיימת אך **אפס caller בקוד החי** — אין מסלול
  שכותב אליה, שכבה ריקה בפועל. `get_marketing_rules()` **כן נקראת בפועל**
  (`cmd_marketing.py:445`/`:513`, לפני הרכבת ה-Brief/Production Handoff)
  אך תמיד מחזירה ריק כרגע כי אין רשומות — לא unwired, פשוט ללא תוכן. כתיבה
  לשכבה זו נדחתה במפורש (12/08/2026) ל-"Later — Structured Company Brain",
  לא M1.
- **F23 `business_rules` תוכן עסקי** — רק ל-recruitment יש תוכן אמיתי;
  4 סוגי דרישה נותרים (furniture_import/fiber_equipment/
  real_estate_listing/service) מחזיקים ערך ניטרלי מפורש, ממתינים לקלט
  עסקי מה-owner.

**חסום:**

- `TurnCoordinator` הפורמלי (Layer 2) — אפס מימוש; ממתין להחלטת owner.
- BUG-130/134/136/137/140/150/152 (וכן 126/127B/127C/138/139/142/148) —
  ממתינים להחלטת owner; חלקם חסומים ע"י
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`.
- Context Librarian catalog refresh — CI push-to-main אדום (4 STOP / 21
  REVIEW_REQUIRED / 98 WARNING) — לא חוסם פונקציונלי, דורש הרצת
  `refresh-after-merge --apply`.

## 3. Completed Since Last Update (מאז 11/08/2026, `f69d7b3..4c94d68`)

- **F23 — BOSS Marketing Bridge M1**, נבנה ב-4 PRs (מתועד ב-ROADMAP כ-#601–
  #604, ממוזג ל-`main` דרך PR #605): #601 בנייה ראשונית עם record ID גלוי
  בטקסט (הפר עקרון `ux_no_internal_ids`); **#602 — תוקן ע"י הבעלים
  בבדיקה חיה (לא ע"י review)**: נבנה מחדש כ-wizard `/marketing_new` ללא ID
  גלוי, ה-ID עובר רק ב-`callback_data` הבלתי-נראה של טלגרם; #603 — הוחלף
  `key_points` הגנרי ב-`business_rules` אמיתי (recruitment) + נוסף שלב
  `Constraints` ל-wizard; **#604 — באג ארכיטקטוני אמיתי, נמצא רק בבדיקה
  חיה**: טקסט חופשי (למשל "כן") נפל בשקט ל-`run_agent()` הכללי במקום
  ל-`cmd_marketing.py` — תוקן ע"י `cmd_marketing.has_pending_capture()` +
  בדיקה מקבילה ב-`app.py`, עם governance check חדש ב-`smoke_tests.py`
  שמונע רגרסיה שקטה של סדר הבדיקות.
- **אימות חי (12/08/2026)**: simulated webhook POSTs אמיתיים מול
  `/telegram` בפרודקשן — רשומת Demand אמיתית (`recfrUEj6e7uHEEf9`) +
  Creative (`recMyaGzpIvYfNX0i`) עם 3 רעיונות, Render logs מאשרים אפס
  פעילות `run_agent`/Router (קריאת Anthropic יחידה בלבד). Render deploy
  `dep-d9tr91jl550s738take0`=`live`.
- **פער ממשל שנסגר בסבב הזה**: `CHANGELOG.md` לא כלל רשומה לבאץ' F23/PR
  #601–605 עד לעדכון הזה — נוספה רשומה מתאימה (ראו `CHANGELOG.md`
  "Unreleased").

## 4. Next Priorities

1. **סגור את שני הפערים הלא-חוסמים מה-audit הקנוני** — הרץ
   `python -m tools.context_librarian refresh-after-merge --apply`; קבע/
   דחה במפורש מול owner את מעמד `TurnCoordinator` הפורמלי (Layer 2).
2. **חבר TC7-B1 (`authorize_claim()`) לצרכן אמיתי** — עדיין 0 קוראים.
3. **F23: קלט עסקי אמיתי ל-`business_rules`** מה-owner לארבעת סוגי
   הדרישה הנותרים; **אל תיישם** כתיבה לשכבת Marketing Rules (Business
   Memory) או Prompt 2 כקריאת AI שנייה בלי אישור owner מפורש (נדחו
   במכוון מ-M1).
4. **אימות production טרי ל-Track D ול-TC8 reject/cancel** — קוד פרוס,
   אין ראיות log לאחר ה-deploy האחרון (היעדר תעבורה, לא כשל).
