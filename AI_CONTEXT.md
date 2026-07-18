# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026) — **לא** מקור אמת נוכחי;
> main + ROADMAP גוברים עליו בכל סתירה.
> `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עצמם מפגרים אחרי `main` בסבב הזה —
> ראו §3/§4 (PR #380–#383 עדיין לא מתועדים שם; MAIN > DOCS עד שיתוקן).

**עודכן:** 2026-07-18 · **main:** `c1b00c0` · **סטטוס:** אין ענף פעיל פתוח כרגע (כל PRs עד #383 ממוזגים)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד. אין שינוי במסלול הזה.
- **BUG-104** (ליבת reasoning ל-Leads): Phase 1/1.1/2A.1/2A.2 קוד ממוזג ומאומת ב-main+tests. `FEATURE_CORE_REASONING_LEADS_STATE` נשאר `off`/`shadow` — **אין effect על תגובות פרודקשן בפועל**. Phase 2A.0 (ניקוי סכמה) — SPEC בלבד, ממתין להחלטת owner.
- **F52 (Message Contract Foundation)** — 3 PRs חדשים מאז הסבב הקודם (#381–#383): פורמטר סמנטי חדש (`core/agent_message_formatter.py`) + דלגציה ב-`ActionGateway.compose_status_reply()` מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (off/shadow/on, **ברירת מחדל off**) + מיפוי `display_payload` קנוני. **כל השלושה foundation-only — אין הפעלת flag, אין שינוי התנהגות בפרודקשן.**
- **RP5 (Evidence Finalizer enforcement) — חסום**: RP4 קוד-שלם אך `FEATURE_EVIDENCE_FINALIZER=off` בפרודקשן; אין עדיין דגימות shadow אמיתיות. פעולה הבאה תלויה ב-operator (מחוץ ליכולת סשן קוד).
- **BUG-110 — VERIFIED**: שני נתיבי כתיבה תוקנו מ-`status="converted"` הלא-קנוני ל-`status=done`+`Business Outcome=converted`. חוב טכני מתועד: `ad_attribution.py::mark_converted()` עדיין לא עובר דרך ה-gateway הקנוני.
- **פער תיעוד ידוע**: `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עדיין לא מכילים רשומות עבור PR #380–#383 (F52 החדש). `main` הוא המקור המאומת בסבב הזה; שלושת המסמכים דורשים סנכרון.
- פריטים ללא שינוי/לא נבדקו בסבב הזה: PR #341 (Single-Speaker fix, לא production-verified), C81-FU/C82-FU, רשומת Airtable `recRvK6hFTNgyj8ag`.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram+WhatsApp inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow; Daily Digest; Finance Pulse; TMA read path; Cost Watchdog; חילוץ-ליד מ-WhatsApp; RP1 tool-registry invariants (תמיד פעיל); TMA Lead Event Bridge; `lead_conversion.py`/`ad_attribution.py::mark_converted()` כותבים ערכים קנוניים (BUG-110).

**מיושם חלקית / קוד מוכן אך flag כבוי:**
- BUG-104 Core Reasoning (Phase 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests בלבד, לא runtime-verified מול תעבורה חיה. `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow.
- F52 Message Contract Foundation + reconciliation + display_payload mapping (PR #381–#383) — קוד foundation חדש, אין שום צריכה חיה (`app.py`/dispatcher/scheduler לא מייבאים אותו); `FEATURE_UNIFIED_STATUS_FORMATTER` off.
- RP2/RP3 Tool Availability Filter — off. RP4 Evidence Finalizer — off, גם "enforce" הוא comparison-only.
- PA-01 structural enforcement — off, ממתין להחלטת shadow rollout.
- Phase 4B Atomic Claims — off, ללא שינוי.
- BUG-104 Phase 2A.0 — SPEC בלבד; ניקוי שדות `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` טרם בוצע.

**חסום:**
- RP5 enforcement — ממתין לדגימות shadow אמיתיות; operator בתהליך הפעלת `FEATURE_EVIDENCE_FINALIZER=shadow` ב-Render (מחוץ לסבב קוד).
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- BUG-110 חוב טכני: `ad_attribution.py::mark_converted()` לא עובר דרך canonical gateway; `build_attribution_report()`/`audience_intelligence.py` עדיין קוראים `status=="converted"` הישן — יחסירו לידים שהומרו לאחר התיקון.
- PR #341, C81-FU/C82-FU, רשומת `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו.

---

## 3. Completed Since Last Update (17/07 → 18/07)

1. **PR #381 — F52 PR1: Message Contract Foundation** (`a90b583`) — `core/agent_message_formatter.py` חדש: פורמטר סמנטי עצמאי (stdlib בלבד), **לא מחובר** ל-`app.py`/ActionGateway/scheduler/tool registry. 10 מצבי הודעה (success/failure/approval_pending(_batch)/clarification_needed/idle/outcome_unknown/unverified_effect/mixed(_with_unknown)) — לעולם לא משדרג מצב לא-success ל-success.
2. **PR #382 — F52: reconcile compose_status_reply** (`3a331d9`) — `ActionGateway.compose_status_reply()` נשאר נקודת הכניסה היחידה אך מאציל ניסוח לפורמטר הקנוני, מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` (off/shadow/on, **ברירת מחדל off**, fail-closed). `off` = טקסט legacy זהה-ל-byte; `shadow` = מחשב טקסט מאוחד ללוג בלבד; `on` = שולח את הטקסט המאוחד. חריגה בפורמטר → נופל חזרה ל-legacy תמיד. אין שינוי ל-approval policy/executor/ledger.
3. **PR #383 — F52: canonical display_payload + unified payload mapping** (`f0ad36c`) — `_normalize_payload()` ממפה שמות שדה קנוניים (`action`/`entity_type`/`key_fields`/`execution_verified`/`occurred_at` וכו') + תאימות לאחור לשמות legacy; `execution_verified=False` לעולם לא success; `human_summary` הפך ל-hint בלבד. 29+13 בדיקות ירוקות, אין הפעלת flag, אין שינוי סכמה/frontend.

**פער תיעוד פתוח:** PR #380–#383 עדיין לא מתועדים ב-`ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` — סנכרון הממשל טרם בוצע בסבב הזה (ראו §4 סעיף 1).

---

## 4. Next Priorities

1. **סנכרון מסמכי ממשל** — להוסיף רשומות ל-`ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עבור PR #380–#383 (F52 Message Contract Foundation + reconciliation + display_payload), כדי ש-MAIN ו-DOCS יתאמו שוב.
2. **operator: RP5 preflight** — הפעלת `FEATURE_EVIDENCE_FINALIZER=shadow` ב-Render, ואיסוף דגימה אחת לפחות לכל אחד מ-9 מצבי הסיווג (`RP5_PREFLIGHT_BLOCKER.md` §3) לפני שRP5 עצמו יכול להתחיל.
3. **החלטת owner: הפעלת `FEATURE_CORE_REASONING_LEADS_STATE`** — קוד BUG-104 מוכן ומאומת ב-main; טרם נצפה על תעבורה חיה.
4. **החלטת owner: ניקוי סכמת BUG-104 Phase 2A.0** — `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` מועמדי-מחיקה, טרם טופלו.
5. **חוב טכני BUG-110** — להעביר את `ad_attribution.py::mark_converted()` ל-canonical gateway ולעדכן את `build_attribution_report()`/`audience_intelligence.py` שעדיין בודקים `status=="converted"` הישן.
