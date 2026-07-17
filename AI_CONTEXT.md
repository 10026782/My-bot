# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026, עם תוספות עד 07/07) —
> **לא** מקור אמת נוכחי; main + ROADMAP גוברים עליו בכל סתירה.

**עודכן:** 2026-07-17 · **main:** `b5ca7a5` · **branch status:** PR #366 Draft, documentation-only · **סטטוס:** ראו §1

**✅ פער #354–#362 נסגר בתיעוד:** PR #364 (`1d31aab`, merge `80fdfae`) עדכן בפועל את `ROADMAP.md`, `CHANGELOG.md` ו-`CHANGE_CONTROL_LOG.md`. PR #363 / merge `60991c1` שקדם לו היה רענון briefing בלבד ונגע רק ב-`AI_CONTEXT.md`; הוא **לא** היה תיקון לפער בשלושת מסמכי הממשל. **⚠️ פער היסטורי נפרד נשאר פתוח במכוון:** `CHANGELOG.md` אינו מפרט בנפרד את PRs #348–#353 (PA-01), ו-`CHANGE_CONTROL_LOG.md` חסר רשומות עבור #327–#353 אחרי C111. PR #364 סימן את הגבולות האלה במפורש ולא ביצע backfill מחוץ לסקופ.

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, Identity→Router→Context→Agent, Airtable כ-CRM. אין שינוי במסלול הזה.
- **PA-01 (Phantom Approval Prompt enforcement)** — קוד הושלם ומאומת (110/110+117/117), ממוזג, **`FEATURE_PA01_ENFORCEMENT_STATE` נשאר `off`** — לא הופעל בפרודקשן, אין staged rollout plan כתוב.
- **BUG-104 (Core Reasoning Activation, Phase 1 — Leads read-only reasoning projection)** התקדם מאז 16/07: שני סבבי re-audit נוספים (P1-A/B/C — lookup לפי record ID, נורמליזציית live-schema, readiness כן ("honest")+1.1 — status vocabulary תואם ל-`DecisionStatus` + אימות linkage). `FEATURE_CORE_REASONING_LEADS_STATE` נשאר `off` כברירת מחדל, ללא mutation/persistence.
- **סדרת PR-RP0→RP4 חדשה (Runtime Reliability & Permission Hardening)** — לא הייתה קיימת בעדכון הקודם: RP0 (ספק תכנון, docs-only), RP1 (ולידציית invariants ל-`tool_registry.py`, **תמיד פעילה, לא flag-gated**), RP2 (shadow diagnostics לזמינות כלים), RP3 (מסנן schema לכלים לא-זמינים בפועל — `FEATURE_TOOL_AVAILABILITY_FILTER` off/shadow/**enforce**, ברירת מחדל `off`), RP4 (evidence finalizer — `FEATURE_EVIDENCE_FINALIZER` off/shadow/enforce, ברירת מחדל `off`, "enforce" עדיין comparison-only עד RP5). כל השרשרת flag-gated OFF/לא-פעילה בפרודקשן פרט ל-RP1 (תמיד-פעיל, מקומי בלבד — לא נוגע ב-runtime dispatch).
- **BUG-104 bridge** — כתיבות ליד מה-TMA (owner-immediate + manager-approved) עכשיו כותבות גם ל-`Lead Events` (לא רק inbound chat) — סוגר פער-ראיה שה-reasoning projection היה תלוי בו.
- **TMA:** כרטיס domain="saas" הוסתר זמנית מ-Projects Hub (display-only filter, אין שינוי נתונים/Airtable).
- **F52 Unified Approval Runtime — Unified User Messages** (`docs/architecture/f52-unified-approval-runtime/`) — PR #366 הוא Draft documentation-only: תקן UX, מפת נקודות פלט, החלטת `display_payload` ותוכנית יישום מדורגת. התכנון והאודיט הושלמו ותועדו; היישום טרם התחיל. הצעד הבא לאחר מיזוג ובדיקה הוא PR 1 — Message Contract Foundation בלבד, מנותק מנתיבי production. **שונה מ-PA-01**: PA-01 חי תחת `docs/architecture/turn-coordinator/` — תוכנית TurnCoordinator נפרדת שצורכת את audit maps של F52 כקלט אך אינה מחליפה אותה.
- פריטים שנשארו כפי שהיו מהעדכון הקודם, **לא נבדקו בסבב הזה**: PR #341 (Single-Speaker fix) — ממוזג, לא production-verified; C81-FU/C82-FU — ללא ראיה שטופלו; נזק ידוע ברשומת Airtable `recRvK6hFTNgyj8ag`; חשד לקבצי `test_*.py` בסגנון pytest שרצים ירוק ב-CI בלי assertion אמיתי.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow (Airtable `Approvals` כנתיב אמיתי, projection חדש דורם); Daily Digest; Finance Pulse; TMA (ללא כרטיס saas); Cost Watchdog; C94 Ingress Envelope; חילוץ-ליד מ-WhatsApp; RP1 tool-registry invariants (תמיד פעיל).

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- PA-01 structural enforcement — `off`, ממתין להחלטת shadow rollout.
- BUG-104 Core Reasoning Phase 1 (+1.1) — `off`, read-only Leads projection בלבד, אין קורא production.
- RP2/RP3 Tool Availability Filter — `off`, shadow diagnostics קיימות אך לא נצפו בפרודקשן.
- RP4 Evidence Finalizer — `off`, shadow-only גם ב-"enforce" (עד RP5).
- Phase 4B Atomic Claims — ללא שינוי, `off`, תכנון/קוד ממתין.
- F52 Unified Approval Runtime — Unified User Messages — PR #366 documentation-only מוכן לבדיקת מיזוג אחרונה. התכנון והאודיט הושלמו ותועדו; היישום טרם התחיל. PR 1 הבא מוגבל ל־Message Contract Foundation מנותק מנתיבי production; אין קוד production במסגרת PR #366.
- C90, Lead Scoring/Memory/Followup (N02-N04), Decision Hub — ללא שינוי, code done/flags off.

**חסום:**
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- PA-01/BUG-104/RP2-4 production activation — כולם ללא staged rollout plan כתוב.
- PR #341, C81-FU/C82-FU, רשומת `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו, ראו §1.

---

## 3. Completed Since Last Update (16/07 → 17/07) — מתועד ב-PR #364

1. **BUG-104 P1-A/B/C re-audit** (`71f04fb`, PR #354) — Lead Events lookup לפי record IDs אמיתיים (לא scan מלא), נורמליזציית שדות live-schema לפני ה-adapter, readiness מחושב אמיתי (לא מונח שווה ל-phase).
2. **PR-RP0** (`4efb61b`, PR #355) — מסמכי תכנון בלבד (`RUNTIME_RELIABILITY_AND_PERMISSION_HARDENING_SPEC.md`, `BOSS_PRODUCTION_RUNTIME_MAP.md`). נפתח ב-`--force` על `pre_session_gate.sh` (מאושר ע"י המשתמש במפורש).
3. **PR-RP1** (`b29fbcb`, PR #356) — `tool_registry.py` מקבל `validate_tool_invariants()`/`ToolRegistryInvariantError` — בדיקת מבנה registry תמיד-פעילה (לא flag), 120 טסטים חדשים.
4. **BUG-104 Phase 1.1** (`08ad671`, PR #357) — תיקון status vocabulary (Lead status עכשיו תואם מילולית ל-`DecisionStatus`) + אימות linkage ל-Lead Events.
5. **PR-RP2** (`1b17337`, PR #358) — shadow diagnostics לזמינות כלים per-role (`tool_registry.py`+`context.py`), `FEATURE_TOOL_AVAILABILITY_FILTER=shadow` לוגים בלבד.
6. **PR-RP3** (`59eafd1`, PR #359) — `enforce` מסנן בפועל schemas של כלים לא-זמינים מה-agent (ברירת מחדל עדיין `off`).
7. **BUG-104 TMA bridge** (`0a0c331`, PR #360) — `core/lead_event_writer.write_tma_lead_event()` חדש, מחווט ל-`tma_api.py`/`tools/approval_actions.py` — כתיבות ליד מה-TMA נכתבות גם ל-Lead Events.
8. **TMA saas-card hide** (`bee46b5`, PR #361) — `tma_api.py::_get_project_cards()` מסנן domain="saas" מהתצוגה בלבד. נפתח ב-`--force` (3 ענפים לא-ממוזגים לא-קשורים).
9. **PR-RP4** (`3a3edbe`, PR #362) — `core/turn_evidence.py` חדש, evidence finalizer shadow-mode, `FEATURE_EVIDENCE_FINALIZER=off`.
10. **PR #363 — daily briefing refresh** (`28d4f09`, merge `60991c1`) — עדכון `AI_CONTEXT.md` בלבד. לא שינה `ROADMAP.md`, `CHANGELOG.md` או `CHANGE_CONTROL_LOG.md`, ולכן לא סגר בעצמו את פער הממשל.
11. **PR #364 — governance docs sync** (`1d31aab`, merge `80fdfae`) — עדכן את `ROADMAP.md`, `CHANGELOG.md` ו-`CHANGE_CONTROL_LOG.md` עבור #354–#362; סימן במפורש את הפערים הישנים #348–#353 / #327–#353 בלי להרחיב את הסקופ ל-backfill.
12. **לא בוצע בסבב זה:** אימות פרודקשן לאף אחד מהפריטים ב-#1-9; עדכון `BUG_AUDIT_LOG.md` לא נדרש לסנכרון הפעילות הזה.

---

## 4. Next Priorities

1. **החלטת owner לגבי backfill היסטורי** — האם לפרט בנפרד את #348–#353 ב-`CHANGELOG.md` ואת #327–#353 ב-`CHANGE_CONTROL_LOG.md`. הפער מסומן ואינו מוסתר; הוא לא נחסם בטעות כעבודה שכבר בוצעה.
2. **החלטת owner: הפעלת PA-01/RP2-RP3/RP4 shadow modes בפרודקשן** — כולן קוד-מוכן, `off`, ללא production evidence וללא staged rollout plan כתוב לאף אחת.
3. **🔴 Production-verify PR #341** (Single-Speaker fix) — ללא שינוי מהעדכון הקודם, לא נבדק.
4. **🔴 C81-FU / C82-FU** — ללא ראיה שטופלו, carried over.
5. **לבדוק wiring של קבצי בדיקה בסגנון pytest** מול `ci.yml` בפועל (חשד מהעדכון הקודם, לא אומת).
