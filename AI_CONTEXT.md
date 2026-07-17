# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026, עם תוספות עד 07/07) —
> **לא** מקור אמת נוכחי; main + ROADMAP גוברים עליו בכל סתירה.

**עודכן:** 2026-07-17 · **main:** `b344b02` · **סטטוס:** ראו §1 — אין ענף פעיל פתוח כרגע (כל PRs #367–#372 ממוזגים)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, Identity→Router→Context→Agent, Airtable כ-CRM. אין שינוי במסלול הזה.
- **BUG-104 — VERIFIED IN PROD:** Phase 1 (reasoning projection) + Phase 1.1 (status vocabulary + linkage hardening) + TMA Lead Event Bridge (PR #354/#357/#360) אומתו קצה-לקצה בפרודקשן. ראו `BUG_AUDIT_LOG.md`'s BUG-104 להיסטוריה המלאה.
- **BUG-104 Phase 2A.0 + 2A.1 — SPEC-only, ללא קוד (PR #370, #371):** שני מסמכי audit+SPEC חדשים תחת `docs/architecture/bug-104/` — (2A.0) אינוונטר סכמת Leads חי + ערכים חיים + מפת read/write בקוד + מודל קנוני מוצע (`status`/`Business Outcome`/`Score`/`domain` כקנוניים; 6 שדות formula כ-display-only; `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` כמועמדי-ניקוי — ריקים/לא-אמינים בפועל); (2A.1) מדיניות precedence מוצעת בין `status`/`Business Outcome` ל-`state` המוקרן, כולל תיעוד עובדתי (לא הנחה) ש-**`Business Outcome` לא נכנס בכלל ל-`ReasoningEntity` היום** — רק `status` (וגם הוא ממופה נכון רק ל-2 מתוך 10 ערכים חיים). **אין קוד runtime בשני המסמכים — Phase 2A (יישום) עדיין ממתין לאישור owner.**
- **BUG-110 — VERIFIED (PR #372):** שני נתיבי כתיבה (`lead_conversion.py`, `ad_attribution.py::mark_converted`) כתבו `status="converted"` — ערך לא-קנוני, לא ב-`LeadStatus.ALL`. תוקנו לכתוב `status=LeadStatus.DONE` + `Business Outcome=LeadOutcome.CONVERTED`. **⚠️ הערת מספור:** התיקון תויג `BUG-105` בקוד/PR/commit/שם קובץ הבדיקה (`test_bug105_non_canonical_converted_status.py`) לפני שהתגלה ש-`BUG-105` כבר תפוס ב-`BUG_AUDIT_LOG.md` (פורמט טלפון בין-לאומי עם מקף, 12/07/2026, לא קשור, עדיין פתוח) — התיעוד כאן ובקבצי הממשל משתמש ב-`BUG-110` (המספר הפנוי הבא) לפי החלטת owner מפורשת; שמות הקבצים/ה-PR עצמם **לא** שונו רטרואקטיבית. `ad_attribution.py::mark_converted()` **עדיין לא** עבר ל-canonical gateway (`tools/airtable_gateway.py`) — נשאר על `tools.airtable_tools.airtable_update` כדי לא לשבור את `test_response_contract_fixes.py`'s חוזה `result.get("ok")`; חוב טכני נפרד, מתועד לא מתוקן.
- **תיקון debug-logging זמני — VERIFIED (PR #369):** `_log_projects_auth_debug()` (`tma_api.py`, הוכנס `9b51537` 10/07) הוסר כליל כולל 5 call sites — 19 שורות, ללא שינוי אחר להתנהגות auth. §5 למטה עודכן בהתאם (כבר לא "ממצא פתוח").
- **TMA Projects Hub read-path optimization — VERIFIED IN PROD (PR #365):** `GET /api/projects` ירד ל-3 קריאות Airtable; `income_this_month`/`pending_payments_count`/`pending_payments_amount` הוסרו; `hot_leads_count` שינה משמעות (מאושר).
- **PA-01 / RP0-RP4 / F52** — ללא שינוי מהותי מאז הבריפינג הקודם: כולן flag-gated `off` פרט ל-RP1 (תמיד-פעיל, מקומי). F52 PR #366 מוזג (§3).
- פריטים שנשארו כפי שהיו, **לא נבדקו בסבב הזה**: PR #341 (Single-Speaker fix) — ממוזג, לא production-verified; C81-FU/C82-FU — ללא ראיה שטופלו; נזק ידוע ברשומת Airtable `recRvK6hFTNgyj8ag`; חשד לקבצי `test_*.py` בסגנון pytest שרצים ירוק ב-CI בלי assertion אמיתי.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow; Daily Digest; Finance Pulse; TMA (read path מותאם, ללא debug-log רעש); Cost Watchdog; C94 Ingress Envelope; חילוץ-ליד מ-WhatsApp; RP1 tool-registry invariants (תמיד פעיל); TMA Lead Event Bridge (verified in prod); **`lead_conversion.py`/`ad_attribution.py::mark_converted()` כותבים `status=done`+`Business Outcome=converted` (לא `status="converted"`) — BUG-110, PR #372.**

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- BUG-104 Core Reasoning Phase 1 (+1.1) — קוד וקריאה/כתיבה אומתו בפרודקשן; החלטת owner על הפעלת `FEATURE_CORE_REASONING_LEADS_STATE` בקנה מידה עדיין לא התקבלה.
- BUG-104 Phase 2A — **SPEC מאושר-לתיעוד קיים (2A.0+2A.1), יישום קוד עדיין לא התחיל.** ממתין לאישור owner על נקודות ההחלטה הפתוחות ב-SPEC (ראו §11 שם: שמות enum ל-state, מיפוי terminal-administrative, טיפול ב-`status=done` בלי Business Outcome).
- PA-01 structural enforcement — `off`, ממתין להחלטת shadow rollout.
- RP2/RP3 Tool Availability Filter — `off`. RP4 Evidence Finalizer — `off`, shadow-only גם ב-"enforce".
- Phase 4B Atomic Claims — ללא שינוי, `off`.
- F52 Unified Approval Runtime PR 0 — מוזג (PR #366), documentation-only. PR 1 (Message Contract Foundation) עדיין לא נפתח.
- C90, Lead Scoring/Memory/Followup (N02-N04), Decision Hub — ללא שינוי, code done/flags off.

**חסום:**
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- PA-01/RP2-4/BUG-104 production activation בקנה מידה — כולם ללא staged rollout plan כתוב.
- PR #341, C81-FU/C82-FU, רשומת `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו.
- **חוב טכני מתועד (BUG-110):** `ad_attribution.py::mark_converted()` לא עובר דרך canonical gateway; `ad_attribution.py::build_attribution_report()` ו-`audience_intelligence.py` עדיין קוראים `status=="converted"` לצורכי דיווח/סגמנטציה — יחסרו לידים שהומרו **אחרי** PR #372 (אין backfill).

---

## 3. Completed Since Last Update (17/07, המשך אותו יום)

1. **PR #367 — docs activity sync (#363/#364)** (merge `8d0cccc`) — ריבייס + פתרון קונפליקט מול PR #365/#366 שהתקדמו בינתיים; מיזג את עדכוני BUG-104 production-verification ו-ממצא ה-debug-log לתוך `AI_CONTEXT.md`/`BUG_AUDIT_LOG.md`.
2. **PR #368 — RP5 evidence/UX contract alignment** (`3bb1537`, merge `2f364a1`) — לא נפתח בסבב הזה על ידינו; מוזג ל-main בין הפעולות.
3. **PR #369 — הסרת TMA auth debug logging** (`62be9a8`, merge `f48741e`) — `_log_projects_auth_debug()` + 5 call sites הוסרו (19 שורות), ללא שינוי אחר. ראו §1/§5.
4. **PR #370 — BUG-104 Phase 2A.0 SPEC** (`8b4d51e`, merge `a4d04c0`) — `docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md` חדש. Audit+SPEC בלבד, אין קוד.
5. **PR #371 — BUG-104 Phase 2A.1 SPEC** (`fde5c51`, merge `7894bd0`) — `docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md` חדש. Audit+SPEC בלבד, אין קוד; מתעד עובדתית ש-`Business Outcome` לא נכנס ל-reasoning entity היום.
6. **PR #372 — BUG-110: תיקון non-canonical `status="converted"`** (`fa1506e`, merge `b344b02`) — ראו §1. 4 קבצים, כולל בדיקה חדשה (10/10) ותיקון line-number מכני ב-baseline קיים.

---

## 4. Next Priorities

1. **החלטת owner: לאשר או לא את יישום Phase 2A (קוד)** — ה-SPEC (2A.0+2A.1) מוכן; היישום בפועל (נורמליזציה + הרחבת entity + טסטים) ממתין לאישור מפורש על נקודות ההחלטה הפתוחות ב-`PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md` §11.
2. **חוב טכני (BUG-110, נשאר פתוח במכוון):** `ad_attribution.py::mark_converted()` ל-canonical gateway; `build_attribution_report()`/`audience_intelligence.py` לעדכן את בדיקת `status=="converted"` הישנה (יחסירו לידים חדשים).
3. **החלטת owner: מצב `FEATURE_CORE_REASONING_LEADS_STATE` בפרודקשן** — לוודא/לתעד אם חזר ל-`off` או נשאר `on`/`shadow` אחרי הבדיקה החיה הקודמת.
4. **החלטת owner לגבי backfill היסטורי** — #348–#353 ב-`CHANGELOG.md`, #327–#353 ב-`CHANGE_CONTROL_LOG.md`. עדיין מסומן, לא backfilled.
5. **החלטת owner: הפעלת PA-01/RP2-RP3/RP4 shadow modes בפרודקשן** — קוד-מוכן, `off`, ללא staged rollout plan כתוב.
6. **🔴 Production-verify PR #341** (Single-Speaker fix) — ללא שינוי, לא נבדק.
7. **🔴 C81-FU / C82-FU** — ללא ראיה שטופלו, carried over.
8. **לבדוק wiring של קבצי בדיקה בסגנון pytest** מול `ci.yml` בפועל — עדיין לא אומת.

---

## 5. Finding — TMA auth debug logging — ✅ RESOLVED (PR #369)

`_log_projects_auth_debug()` (`tma_api.py`, הוכנס `9b51537` 10/07) הוסר כליל, כולל 5 call sites בתוך `require_tma_auth()`. Diff: 19 שורות הוסרו, אין שינוי אחר — HMAC validation / 401 responses / `resolve_identity()` נשארו זהים בית-לבית. אומת: `test_bug104_leads_reasoning_projection.py`'s Flask test-client section ירוק ללא שינוי. שום ממצא פתוח חדש לא נמצא במקומו בסבב הזה.
