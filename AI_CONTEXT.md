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
- **BUG-104 — VERIFIED IN PROD (חדש מאז הבריפינג הקודם):** Phase 1 (reasoning projection) + Phase 1.1 (status vocabulary + linkage hardening) + TMA Lead Event Bridge (PR #354/#357/#360) אומתו קצה-לקצה בפרודקשן על ליד אמיתי (`recI5JAgcGc07DlOa`, domain=`recruitment`): TMA lead update → Lead Event נוצר עם Lead/Domain/Channel נכונים → BUG-104 קורא אותו → מנוע ה-reasoning צורך אותו (`events.count` 0→2, `state=REVIEW`, `confidence=0.2`). ראו `BUG_AUDIT_LOG.md`'s BUG-104 "עדכון 17/07/2026" לפירוט מלא ולראיות. **פתוח:** מצב `FEATURE_CORE_REASONING_LEADS_STATE` הנוכחי בפרודקשן לא אומת (ראו הערה שם) — אין להסיק "on בפרודקשן כברירת מחדל" מהאימות הזה.
- **TMA Projects Hub read-path optimization — VERIFIED IN PROD (PR #365):** `GET /api/projects` ירד מ-8 קריאות Airtable (כולל 2 Payments שנכשלו 403) ל-3 (ProjectsHub+Leads מרוכז+Tasks). `GET /api/leads?domain=X` ירד מ-2 ל-1 (frontend שולח domain ישירות). `income_this_month`/`pending_payments_count`/`pending_payments_amount` הוסרו מה-response (Payments שייך למסך finance בלבד). `hot_leads_count` שינה משמעות (מאושר): רק leads בפרויקטים מוצגים ובסטטוסים פעילים, לא כל hot lead בבסיס.
- **PA-01 (Phantom Approval Prompt enforcement)** — ללא שינוי: קוד מוזג, `FEATURE_PA01_ENFORCEMENT_STATE` נשאר `off`, אין staged rollout plan כתוב.
- **סדרת PR-RP0→RP4 (Runtime Reliability & Permission Hardening)** — ללא שינוי מאז הבריפינג הקודם: RP0 (docs-only), RP1 (tool_registry invariants, תמיד-פעיל), RP2 (shadow diagnostics), RP3 (enforce filter, `off`), RP4 (evidence finalizer shadow, `off`). כולן flag-gated OFF פרט ל-RP1.
- **F52 Unified Approval Runtime — Unified User Messages** (`docs/architecture/f52-unified-approval-runtime/`) — PR #366 הוא Draft documentation-only: תקן UX, מפת נקודות פלט, החלטת `display_payload` ותוכנית יישום מדורגת. התכנון והאודיט הושלמו ותועדו; היישום טרם התחיל. הצעד הבא לאחר מיזוג ובדיקה הוא PR 1 — Message Contract Foundation בלבד, מנותק מנתיבי production. **שונה מ-PA-01**: PA-01 חי תחת `docs/architecture/turn-coordinator/` — תוכנית TurnCoordinator נפרדת שצורכת את audit maps של F52 כקלט אך אינה מחליפה אותה.
- **חדש, לא תוקן עדיין (נמצא בסבב הזה):** `require_tma_auth`'s `_log_projects_auth_debug()` (`tma_api.py:792`) — לוגינג דיבאג "זמני" (לפי ה-docstring שלו) שהוכנס ב-10/07 (`9b51537`) ומעולם לא הוסר; יוצר עד 3 שורות `logger.info` בכל בקשה ל-`/api/projects` בלבד (שאר ה-endpoints קוראים לו אך הוא no-op בשקט). לא קריאות Airtable נוספות — רעש לוגים בלבד. ממצא מתועד ב-§5, תיקון מוצע טרם מומש.
- פריטים שנשארו כפי שהיו, **לא נבדקו בסבב הזה**: PR #341 (Single-Speaker fix) — ממוזג, לא production-verified; C81-FU/C82-FU — ללא ראיה שטופלו; נזק ידוע ברשומת Airtable `recRvK6hFTNgyj8ag`; חשד לקבצי `test_*.py` בסגנון pytest שרצים ירוק ב-CI בלי assertion אמיתי.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow (Airtable `Approvals` כנתיב אמיתי, projection חדש דורם); Daily Digest; Finance Pulse; TMA (ללא כרטיס saas, read path מותאם — ראו §1); Cost Watchdog; C94 Ingress Envelope; חילוץ-ליד מ-WhatsApp; RP1 tool-registry invariants (תמיד פעיל); **TMA Lead Event Bridge (verified in prod — TMA lead writes כותבות Lead Events אמיתיים)**.

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי — אך המסלול הטכני אומת קצה-לקצה):**
- BUG-104 Core Reasoning Phase 1 (+1.1) — קוד וקריאה/כתיבה אומתו בפרודקשן (§1); **החלטת owner על הפעלת `FEATURE_CORE_REASONING_LEADS_STATE` בקנה מידה עדיין לא התקבלה**, וההחלטה הארכיטקטונית הרחבה יותר (U1 — חיבור `leads_adapter.py`/`FEATURE_DECISION_HUB`) עדיין פתוחה — ראו `BUG_AUDIT_LOG.md` BUG-104.
- PA-01 structural enforcement — `off`, ממתין להחלטת shadow rollout.
- RP2/RP3 Tool Availability Filter — `off`, shadow diagnostics קיימות אך לא נצפו בפרודקשן.
- RP4 Evidence Finalizer — `off`, shadow-only גם ב-"enforce" (עד RP5).
- Phase 4B Atomic Claims — ללא שינוי, `off`, תכנון/קוד ממתין.
- F52 Unified Approval Runtime — Unified User Messages — PR #366 documentation-only מוכן לבדיקת מיזוג אחרונה. התכנון והאודיט הושלמו ותועדו; היישום טרם התחיל. PR 1 הבא מוגבל ל־Message Contract Foundation מנותק מנתיבי production; אין קוד production במסגרת PR #366.
- C90, Lead Scoring/Memory/Followup (N02-N04), Decision Hub — ללא שינוי, code done/flags off.

**חסום:**
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- PA-01/RP2-4 production activation — כולם ללא staged rollout plan כתוב.
- BUG-104 production activation (rollout בקנה מידה, לא shadow test בודד) — ממתין להחלטת owner.
- PR #341, C81-FU/C82-FU, רשומת `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו, ראו §1.

---

## 3. Completed Since Last Update (16/07 → 17/07, כולל המשך אותו יום)

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
12. **PR #365 — TMA read-path optimization** — ראו §1. `test_tma_projects_read_path_optimization.py` (32/32).
13. **BUG-104 full production verification** — לא PR, בדיקה חיה בפרודקשן ע"י הבעלים. ראו §1 + `BUG_AUDIT_LOG.md` BUG-104 "עדכון 17/07/2026" לראיות המלאות (before/after `events.count`, שתי רשומות Lead Events בפועל).
14. **ממצא חדש, לא תוקן:** `_log_projects_auth_debug()` — לוגינג דיבאג זמני שנשאר מ-10/07, רעש בלוגי פרודקשן. תיקון מוצע, טרם מומש — ראו §5.
15. **PR #366 (Draft)** — F52 Unified Approval Runtime PR 0, documentation-only. ראו §1/§2.

---

## 4. Next Priorities

1. **Phase 2A — Current State Policy (Audit + SPEC בלבד, ללא קוד)** — השלב הבא המתוכנן ל-BUG-104 אחרי אימות ה-bridge; לא הוחל עדיין.
2. **תיקון `_log_projects_auth_debug()`** — הצעת תיקון מוכנה (§5), ממתינה לאישור מפורש לפני קוד.
3. **החלטת owner: מצב `FEATURE_CORE_REASONING_LEADS_STATE` בפרודקשן אחרי הבדיקה** — לוודא/לתעד אם חזר ל-`off` או נשאר `on`/`shadow`.
4. **החלטת owner לגבי backfill היסטורי** — האם לפרט בנפרד את #348–#353 ב-`CHANGELOG.md` ואת #327–#353 ב-`CHANGE_CONTROL_LOG.md`. הפער מסומן ואינו מוסתר; הוא לא נחסם בטעות כעבודה שכבר בוצעה.
5. **החלטת owner: הפעלת PA-01/RP2-RP3/RP4 shadow modes בפרודקשן** — כולן קוד-מוכן, `off`, ללא production evidence וללא staged rollout plan כתוב לאף אחת.
6. **🔴 Production-verify PR #341** (Single-Speaker fix) — ללא שינוי, לא נבדק.
7. **🔴 C81-FU / C82-FU** — ללא ראיה שטופלו, carried over.
8. **לבדוק wiring של קבצי בדיקה בסגנון pytest** מול `ci.yml` בפועל — עדיין לא אומת.

---

## 5. Finding — TMA auth debug logging (documented, fix proposed, not yet implemented)

**מיקום:** `tma_api.py:792-830` — `_log_projects_auth_debug(stage)` + 5 קריאות לה בתוך `require_tma_auth()` (הדקורטור המשותף לכל endpoint מאומת ב-TMA, לא רק `/api/projects`).

**מקור:** הוכנס ב-`9b51537` (10/07/2026, "fix(tma): align task and deal schema field values" — תוספת צדדית לא קשורה לכותרת ה-commit), עם docstring מפורש "**Temporary** safe auth diagnostics for /api/projects only". מעולם לא הוסר מאז — 7 ימים בפרודקשן.

**התנהגות בפועל:** `require_tma_auth()` קורא ל-`_log_projects_auth_debug()` 2-3 פעמים בכל בקשה, לכל endpoint מאומת ב-TMA (leads/projects/approvals/וכו'). הפונקציה עצמה בודקת `request.path != "/api/projects"` ומחזירה מיד אם לא — כך שרק בקשות ל-`/api/projects` בפועל כותבות ללוג (עד 3 שורות `logger.info` לבקשה: `start`, `telegram_branch`, ואז `telegram_success` או אחד משני מצבי 401). לשאר ה-endpoints זו קריאת פונקציה מבוזבזת (no-op), לא רעש לוג.

**השפעה:** אין קריאות Airtable נוספות (לא בעיית ביצועים). רעש בלוגי הפרודקשן — עד 3 שורות `[TMA auth debug] path=/api/projects stage=...` בכל טעינת Projects Hub, כולל אחרי שהבעיה שלשמה זה נכתב (כנראה תקלת auth/CORS סביב `/api/projects`) כבר אומתה כפתורה (§1: PR #365 verified in prod, אין 401/403 בלתי-מוסברים בסבב האימות הזה).

**תיקון מוצע (טרם מומש — ממתין לאישור מפורש):**
- הסרת `_log_projects_auth_debug()` כליל, וחמשת ה-call sites שלה בתוך `require_tma_auth()` (`tma_api.py:814,815,818,823,828`).
- ללא שינוי אחר ב-`require_tma_auth()` — הלוגיקה של HMAC validation / 401 responses / `resolve_identity()` נשארת זהה בית-לבית; רק שורות ה-log מוסרות.
- אין שינוי ל-response contract, ל-status codes, או להתנהגות auth בפועל — ניקוי לוגים בלבד.
- בדיקה: לוודא ש-`test_bug104_leads_reasoning_projection.py`'s Flask test-client section (וכל בדיקה אחרת שעוברת דרך `require_tma_auth`) עדיין ירוקה ללא שינוי.
