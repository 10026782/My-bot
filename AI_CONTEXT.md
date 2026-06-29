# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-29 (מאוחר ביותר) — Manual Verification Checklist session
**עודכן על ידי:** Claude Code — `claude/new-session-be1ckb`, `BOSS_Manual_Verification_ChecklIST_UPDATED2.docx`

> מקור אמת: `ROADMAP.md` + `BOSS_CURRENT_STATE.md` (מיושן, 19/06) + `CHANGELOG.md` + git log. `CANONICAL_STATE.md` לא קיים בריפו. כאשר המסמכים סתרו זה את זה, עדיפות: main (git) > ROADMAP.md > AI_CONTEXT.md הקודם > BOSS_CURRENT_STATE.md.

---

## 0.2 Manual Verification Checklist — 2026-06-29 (קרא לפני 0.1)

**`main` = `e735bf7`** (אומת `git fetch origin main` + `git rev-parse origin/main`).

**מקור:** `BOSS_Manual_Verification_ChecklIST_UPDATED2.docx` (הועלה ע"י הבעלים, חולץ עם `python-docx`). המסמך מכיל שלושה חלקים נפרדים שטופלו בנפרד: (1) הצ'קליסט הפורמלי המקורי (V0-V5, Lead Flow, Security, Airtable, Cost) עם תאריך יוני 2026; (2) עדכון סטטוס מאוחר יותר (28/06/2026) עם טבלת "מאומת תקין" לא-פורמלית + 10 בדיקות חדשות **LL-01 עד LL-10** (Lead Lifecycle) + טבלת "אומתו מהסשן הקודם"; (3) שרידי שיחת פיתוח (Codex Handoff על תיקוני lead_capture/identity) — **לא צ'קליסט, סומן בנפרד למטה, לא הומר לפריטי בדיקה מזויפים.**

**כלל הסיווג שהופעל (לפי הוראת הבעלים):** PASS+evidence אמיתי → ✅ VERIFIED IN PROD (מצוטט). FAIL/ריק → 🟡 OPEN. evidence מצוטט בתוך בדיקה *אחרת* באותו מסמך נחשב evidence תקף לבדיקה הנושא שלו (כדי לא לאבד מידע) — מתועד בנפרד כ"cross-referenced". PASS בטבלת הסיכום **בלי** evidence בשום מקום במסמך — **לא קודם** ל-VERIFIED, מתועד כ"PASS מוצהר, evidence חסר".

### טבלת סיכום (68 פריטים: V0-V5, LF, SEC, AT, CP, LL)

| קבוצה | ✅ VERIFIED | ⚠️ PARTIAL | 🟡 OPEN | הערות |
|---|---|---|---|---|
| V0 Processing (7) | V0-02,03,06,07 | V0-04 | V0-01¹, V0-05² | |
| V1 Understanding (7) | V1-01,02,03³,04,07³ | — | V1-05 | V1-06 דחוי (Decision Hub) |
| V2 Memory (6) | — | — | כולן | אפס evidence בקובץ |
| V3 Conversation (7) | — | — | כולן | אפס evidence בקובץ |
| V4 Output (6) | — | — | כולן | אפס evidence בקובץ |
| V5 Five Gates (5) | — | — | כולן | V5-01,02 דחויים (Decision Hub) |
| Lead Flow (6) | LF-01³ | LF-05³ | LF-02,03,04,06 | |
| Security (6) | SEC-06⁴ | — | SEC-01..05 | |
| Airtable (5) | AT-03³ | — | AT-01,02,04⁵,05⁶ | |
| Cost & Perf (3) | CP-02³ | — | CP-01,03 | |
| LL Lead Lifecycle (10) | — | — | כולן | חדש, לא נבדק עדיין |

¹ PASS מסומן אך evidence הוא רק `[pass 28/06/26]` — אין השוואת hash בפועל, לא עומד בכלל הראיה של המסמך עצמו.
² evidence ריק; קיים BUG פתוח מתאים — **BUG-011** (`app.py` run_agent fallback), 🟡 MERGED TO MAIN, ממתין לאימות פרודקשן.
³ evidence "cross-referenced" — מצוטט בבדיקה אחרת באותו מסמך, לא תחת ה-ID של הבדיקה עצמה: V1-03/V1-07/LF-01/LF-05/AT-03/CP-02 כולם נשענים על הלוגים המצוטטים תחת V0-03/V0-04/V1-01/V1-02/V1-04.
⁴ אומת ב-grep ישיר על הקוד (השיטה שהצ'קליסט עצמו מציע כתחליף לבדיקה ידנית כש"אין substring collision") — `tma_api.py:732-733`: `_owner_ids = [x.strip() for x in str(f.get("owner_ids","") or "").split(",")]` + `if identity.user_id not in _owner_ids` — list comparison אמיתי, לא `in str()`.
⁵ הרצתי את ה-grep שהצ'קליסט עצמו מציין (`httpx.post\|requests.post` מחוץ ל-gateway) — מצא תוצאות ב-`crm.py`/`profile.py`/`project_timeline.py`/`worker.py`/`drive_adapter.py`/`tools/google_tools.py` ועוד. רובם לא-Airtable (Drive/Google/Telegram/Supabase) או מודולים מתועדים כ-unwired (`profile.py`/`project_timeline.py`, ראו CLAUDE.md). `crm.py:70` הוא הפניה ל-Airtable ישירה שדורשת בדיקה נפרדת — **לא נפתח BUG** כי לא בוצע root-cause מלא (אין אישור אם crm.py נגיש מנתיב כתיבה חי) — מסומן למעקב, לא קביעה.
⁶ הקוד הבסיסי (BUG-008, trailing space) אומת קיים (`airtable_schema.py:354` `NEEDS_FOLLOWUP = "needs_followup "`), אך הבדיקה הידנית הספציפית מה-TMA לא בוצעה.

**⚠️ "PASS מוצהר, evidence חסר" — לא קודם ל-VERIFIED, כלל המסמך עצמו לא מתקיים:** טבלת "בדיקות שכבר אומתו" בחלק 2 של המסמך מסמנת `LF-01`, `LF-05 (חלקי)`, `CP-02` כ-✅ PASS בתאריך 28/06/2026 — אבל למעשה יש להן evidence אמיתי (cross-referenced, ראו הערה ³ מעל), כך שהן קודמו כראוי. שאר 9 הבדיקות באותה טבלה (V0-01..07, V1-01..04) נבדקו אחת-אחת מול גוף המסמך ואומתו (V0-01 הוא היחיד שנשאר 🟡 בגלל evidence חלש).

**⏸️ דחוי במפורש (לא 🟡 OPEN, לא באג):** V1-06, V2-02, V5-01, V5-02 + "Decision Hub creation/Event creation/Session↔Decision link/ראוטר Decision לפני Chat Fallback" — מסומנים בקובץ עצמו "לא לבדוק עכשיו" כי `FEATURE_DECISION_HUB=false`. אין צורך בפעולה עד הפעלה מסודרת.

**BUG-023 נפתח** — באג ישן ב-`identity.py`/`lead_capture.py` (כתיבת "ליד חדש" לשדה Name, Primary Field, על כל ליד) שהתגלה תוך קריאת חלק 3 של המסמך (שרידי שיחת פיתוח). **כבר תוקן ומוזג** ב-`ca1f5a0` (28/06/2026, מאומת `merge-base --is-ancestor` מול `origin/main`) — אך הלוג שמצוטט ב-V1-04 מציג רשומות שנוצרו **לפני** התיקון, כך שאין עדיין ראיה על ליד טרי אחרי ה-fix. ראו BUG_AUDIT_LOG.md.

**חלק 3 (שרידי שיחת פיתוח) — דגל מפורש, לא נשמט:** המסמך המקורי הכיל גם דיון פיתוח לא-פורמלי (ActionResult/RequestContext/ClaimGate, "Codex Handoff — Lead Capture Regression", ניתוח `claim_type` FOUND-vs-CREATED) — ללא מבנה PASS/FAIL, לא תואם את כללי הסיווג. לא הומר לפריטי checklist מזויפים; המידע היחיד שחולץ ממנו בפועל הוא BUG-023 מעל (כי הניתן לאימות מול קוד).

**מסקנה מעשית:** 13/68 פריטים ✅ VERIFIED (כולל 6 cross-referenced), 2 ⚠️ PARTIAL, 53 🟡 OPEN (כולל כל 10 ה-LL החדשות וכל V2/V3/V4 — אפס evidence קיים), 4 דחויים במפורש (Decision Hub). ה-"25 בדיקות חובה" שמוגדרות בסוף החלק הפורמלי של המסמך (`Definition of Stage 0-V Complete`) **עדיין לא הושלמו** — מתוכן V0-01, V0-05, V2-01/02/03, V3-01..04, V4-01..04, LF-02/03/04/06, SEC-01/02/04/05, AT-01/04/05 נשארים 🟡 OPEN.

## 0.1 Git Diff Gap Report — 2026-06-29 (קרא לפני 0, שלא עודכן בסשן זה)

**`main` = `debb270`** (אומת `git fetch origin main` + `git log origin/main --oneline -30`; ה-`6b20028` בסעיף 0 למטה מיושן — מ-`6b20028` יש 3 commits נוספים: `f48e4a1`/`6fab36c` שלי עצמי + merge `debb270`).

- **Fxx Safe Document Converter — תיקון תיעוד.** ROADMAP.md/סעיף 4 למטה אמרו "Not merged to main" / "Next: open PR, merge" — **שגוי**: מוזג בפועל ב-PR #158 (`db719ab`, 26/06/2026). מצב אמיתי: **מוזג אך לא מחובר** (EXISTS_UNWIRED, pattern F20/F22) — `convert_document()` נקרא רק מתוך `test_document_converter.py`. ראו ROADMAP.md §Fxx לפירוט מלא + ממצא CI (הקובץ רץ ב-CI בלי לבצע assertion — pytest-style קובץ בלי `__main__` guard, ו-`ci.yml` מריץ `python "$f"` ולא `pytest`).
- **שני commits לא-מתועדים נמצאו ותועדו:** `4e1d7ed` "Wire lead capture evidence into A32" (PR #171) ו-`257a5e4` "Fix safe lead metadata patch" (PR #172), שניהם מוזגים 29/06/2026, שניהם **מחוברים בפועל** (caller אמיתי: `app.py:1124`, `lead_capture.py:215`) — MISSING_FROM_DOCS בלבד, לא EXISTS_UNWIRED. ראו CHANGE_CONTROL_LOG.md GAP-29062026.
- **`reports/daily_changes/`** — מאומת קיים ב-`debb270` (תוצאה של BUG-022, סשן קודם). אין עוד ממצא local-only.
- דוח מלא: `reports/gap_report_29jun2026.md`. לא בוצע שינוי קוד/wiring בסשן זה.

## 0. Governance Repair — 2026-06-29

**`main` = `6b20028`** (אומת ב-`git fetch origin main` + `git merge --ff-only`; השורה `main = b289ab6` בסעיף 1 למטה מיושנת — מ-`b289ab6` ל-`6b20028` יש עשרות commits כולל F17–F22 שלא תועדו כשהשורה ההיא נכתבה).

- **F20 (Decision Hub Stage 5, Auto Ingestion) — מוזג, לא מחובר.** `decision_auto_ingestion.py`/`ingest_message()` אין קורא חי באף אחד מ-`app.py`/`inbound_handler.py`/`email_inbound.py`/`voice_adapter.py`/נתיב מדיה (grep מלא על הריפו). `decision_matching.py` (matcher משותף) **כן** מחובר, בנפרד, דרך `cmd_decision.py`. לא חובר כחלק מהתיקון הזה (חיווט לתוך נתיבי inbound חיים = שינוי ארכיטקטוני, לא תיקון תיעוד). ראו ROADMAP.md §F20 לפירוט מלא.
- **F22 (Core Reasoning Layer) — לא היה מתועד בכלל, נמצא קיים ב-`main` ולא מחובר.** `core/reasoning_engines.py`+`core/reasoning_entity.py`+`core/reasoning_ports.py`+`core/adapters/decision_adapter.py`+`core/adapters/leads_adapter.py` — 59/59 בדיקות (`test_core_reasoning.py`) עוברות, אך אפס קריאה חיה (`append_reasoning_block()`/`run()` נקראים רק מתוך הבדיקות של עצמם). הועלו ישירות ל-`main` ב-28/06/2026 23:06–23:09 דרך "Add files via upload" — לא דרך PR/CI. ראו ROADMAP.md §F22.
- **נוסף guard:** `smoke_tests.py::check_decision_hub_call_sites` — משווה מצב חיווט מוצהר (manifest בקוד) מול גרף import אמיתי מתוך entrypoints חיים בלבד (`app.py`/`cmd_decision.py`/`inbound_handler.py`/`email_inbound.py`/`voice_adapter.py`/`scheduler.py`/`worker.py`/`daily_digest.py`/`daily_collector.py`/`tools/dispatcher.py`). נכשל אם F19/F21/`decision_matching` יאבדו את הקריאה החיה שלהם, או אם F20/F22 "יתוקנו" ל-wired=True במצהר בלי קריאה אמיתית.
- **Schema governance — עדיין לא live.** `schema_cache.json.fetched_at == "seed-from-schema-py"` (אומת ישירות). אין credentials של Airtable ב-shell env. שלושת כלי ה-Airtable MCP (`search_bases`/`list_tables_for_base`/`get_table_schema`) החזירו "MCP tool call requires approval" על **כל** קריאה בסשן הזה — לא permission prompt חד-פעמי אלא חסימת-סשן. `schema_cache.json` **לא נערך ולא נמחק** (תקדים מ-BUG_AUDIT_LOG FLAGGED: לא לגעת בלי אישור מפורש).
- **Decision Hub Airtable readiness (Evidence Ids / Evidence Summary / Confidence Score / Missing Evidence / DecisionReadiness.REVIEW) — לא אומת מול Airtable חי**, מהסיבה לעיל. נשאר **activation blocker** ל-`FEATURE_DECISION_HUB` עד שמישהו עם גישת MCP/credentials מאשר ידנית.
- **בדיקות שהורצו:** `py_compile` נקי על כל הקבצים הרלוונטיים; `test_core_reasoning.py` 59/59, `test_decision_orchestrator.py` 13/13, `test_decision_auto_ingestion.py` 18/18, `test_decision_attention.py` 11/11, `test_cxx_action_integrity.py` 6/6, `test_decision_confidence.py` 28/28, `test_decision_readiness.py` 25/25, `test_integration.py` 4/4. `smoke_tests.py`: 2 כשלים קיימים-מראש (`flask`/`httpx` חסרים בסביבת ה-sandbox, לא רגרסיה מהתיקון הזה), הבדיקה החדשה (`check_decision_hub_call_sites`) עוברת.

## 1. Executive Summary
- **Fxx Safe Document Converter — Implemented but not yet verified** — standalone `document_converter` package exposes `convert_document(input_file, input_type, output_type)` and supports deterministic Markdown/HTML/TXT/DOCX/CSV/XLSX MVP conversions. It is not wired into `app.py`, Telegram, TMA, Airtable, or agent tools. It explicitly rejects PDF/OCR/scanned/complex layout reconstruction and returns no output file unless confidence is high.
- **F52 tool architecture audit maps — Implemented but not yet verified** — audit-only docs exist under `docs/f52/`: `F52_CURRENT_TOOL_MAP.md`, `F52_CONTRACT_COVERAGE_MAP.md`, and `F52_BYPASS_MAP.md`. No production behavior changes, no `app.py` changes, and no Airtable schema changes.
- **C60 Tool Context Awareness — 🟡 CODE DONE, על branch בלבד, לא מוזג** — `last_tool_result` נשמר ב-session אחרי כל tool dispatch אמיתי ומוזרק ל-system prompt כ-"🔧 הקשר כלים" (TTL 5 דקות); `resolve_context_pronouns()` מחליף כינויי הצבעה עבריים ("זה"/"הנספח"/"הקודם") בהתייחסות מפורשת לפני ה-Router. 40/40 self-tests עוברים, **3 סטיות מתועדות מהספק** (העיקרית: הספק הניח חוזה `tool_result` שגוי — `id`/`record_id`/`url`/`drive_url` — מול החוזה האמיתי C53-A `{ok,tool,external_id,evidence,user_message}`). ⚠️ הספק תייג עצמו "C59" — מתנגש עם C59 הקיים (Trust Layer, מוזג, ראו למטה) — תויג מחדש **C60**. ראו פירוט מלא: ROADMAP.md/CHANGE_CONTROL_LOG.md (C60).
- **C59 Decision Hub Stage 1 Trust Layer — מוזג ל-`main` (PR #151, commit `73f6fe8`), לא מאומת בפרודקשן** — `gate_trust` ב-`decision_pipeline.py` עבר ממ-stub למודל אמינות אמיתי (Authority×Medium, מתואם ע"י Verify status) שמייצר Trust Level (T0-T3)+Confidence מספרי+Claim Topic אוטומטי לכל Decision Event, עם Supersedes בטוח (אותו נושא + Trust גבוה יותר בלבד). 33/33 self-tests עוברים, **9 סטיות מתועדות מהספק** (כולל `_has_keyword_conflict` שהספק קורא לו ב-§5 אך לא מגדיר את גופו בשום מקום — מומש כ-stub). ראו פירוט מלא: ROADMAP.md/CHANGE_CONTROL_LOG.md (C59).
- `main` = `b289ab6` (PR #151 מוזג, אומת GitHub MCP `pull_request_read` + `git log`). Identity → Router → Context → Agent + Approval flow (3-state, fail-closed) — **תקינים ופעילים בפרודקשן**.
- **C58 Universal Sessions — מוזג ל-`main` (PR #150, commit `84f2ef3`), לא מאומת בפרודקשן** — `session_store.py` עבר מ-`Tables.LEAD_SESSIONS` (טבלה שלא קיימת בפועל ב-Airtable — כל כתיבה הייתה 403, באג latent לא-מתועד) ל-`Tables.SESSIONS` (טבלה אמיתית, `tblHLfE24lTkVUhz0`) עם schema גנרי (`Context Type`+`State JSON`+`Linked *`). 36/36 self-tests עברו במיזוג; **לא אומת מול Airtable חי** — סעיף 5 בספק המקורי ("רשומה אמיתית נוצרת ב-Sessions בייצור") עדיין פתוח. ראו פירוט: ROADMAP.md/CHANGE_CONTROL_LOG.md.
- **C57 Agent Tool Awareness הושלם ומוזג** (לא flag-gated, תיקון התנהגות בסיסי) — `app.py` מדכא `text_block` שנוצר באותה תשובה עם `tool_use` (Claude כותב טקסט לפני שראה תוצאת כלי); `core_knowledge.py` קיבל כלל 7 (אל תכלול הסבר/שאלה לצד הפעלת כלי). ⚠️ הספק תייג זאת "C54" — מתנגש עם C54 הקיים (Business Memory /update); תויג מחדש C57 בתיעוד, ראו ROADMAP.md/CHANGE_CONTROL_LOG.md.
- **Decision Hub Stage 0.5/0.6 הושלמו** (File/Voice Precedence Routing + File Context Reference "זה הנספח") — code-complete ומחובר, **כבוי בפרודקשן** מאחורי `FEATURE_DECISION_HUB`. נוסף ל-ROADMAP.md לראשונה כ-N13 (לא היה מתועד קודם). MODULE_RULES.md קיבל חוקים 7-10+12; נוסף `docs/governance/PLANNING_GATE.md`; BUG-017 (`session_store._sync_to_db` dict-vs-string) נסגר.
- **F16 Media Layer הושלם (7/7 batches)** — code-complete ומחובר ל-pipeline החי, אך **כבוי בפרודקשן** מאחורי `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` (off by default). דורש יצירת טבלת "Media Files" ידנית ב-Airtable לפני הדלקה.
- **N07/N08/N09/N11/N12 הושלמו** (Schema Governance, CI/CD, Monitoring, Finance Pulse wiring, Daily Git Audit scheduler) — כולם code-complete ומוזגים; N12 ו-N10 (Rollback) נשארים flag-off/planned בהתאמה.
- כל פיצ'רי הצמיחה (Lead Scoring/Memory/Followup, N02-N04) — **קוד מוכן, דגלים כבויים כברירת מחדל**, אפס תעבורת ייצור אמיתית אומתה עד כה.
- 4 באגים תועדו ונסגרו בסשן האחרון (BUG-013/014/015/016) — כולם **מוזגים ל-main**, טרם אומתו בפרודקשן.
- מצב Render: דיפלוי קודם אושר ע"י המשתמש ל-`d91a9df`; **לא אומת עצמאית מהסביבה הזו** (אין egress/Dashboard access).
- WhatsApp outbound (Meta Cloud API) — חסום, ממתין לאישור Meta.

## 2. Current System State

**עובד (Operational):** Identity/Router/Context/Agent core; `tool_registry`+`dispatcher` enforcement; Approval flow (`verify_execution()` נבדק לפני דיווח הצלחה); Airtable single-write-path gateway (`tools/airtable_gateway.py`); Daily Digest; Payment Reminder; Twilio signature validation; TMA auth+CORS; Screen Filter Gateway; Finance Pulse (Payments/Expenses חיים); A32 anti-hallucination evidence gate (כולל Drive מאז BUG-014).

**חלקי (קוד קיים, כבוי/לא מאומת):** Lead Scoring/Memory/Followup (`LEAD_SCORING`/`LEAD_MEMORY`/`FOLLOWUP_AUTOMATION`=off, שרשרת תלויה); F16 Media Layer (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`=off, טבלת Media Files חסרה ב-Airtable); Approval Policy Emergency Window/OTP (`EMERGENCY_WINDOW`=off); N12 Daily Git Audit (`GIT_AUDIT_SCHEDULER`=off); WhatsApp outbound = honest stub; Google integrations (OAuth נדרש).

**חסום:** F05 WhatsApp Production (Meta approval). TMA Activity Feed / Assets / Personal Mode (`coming_soon` stubs, כנים).

## 3. Completed Since Last Update

**C60 Tool Context Awareness (25/06/2026, branch `claude/new-session-be1ckb`, 🟡 CODE DONE — לא ממוזג, לא מאומת בפרודקשן):**
- **מקור:** `SPEC_C59_Tool_Context_Awareness.md` (הועלה ע"י הבעלים בלי טקסט מלווה; אישור התקבל דרך `AskUserQuestion`: "Yes, implement now", מקיים את שער "SPEC ONLY — אין קוד עד אישור אליהו").
- ⚠️ **ID collision מתועד (כמו C54→C57):** הספק תייג עצמו "C59" — מתנגש עם C59 הקיים (Decision Hub Stage 1 Trust Layer, מוזג, ראו לעיל). תויג מחדש **C60** בכל מסמכי התיעוד; כותרת הספק וכל מחרוזות הקוד נשארו ללא שינוי.
- **הבעיה שנפתרה:** הסוכן לא זוכר מה כלים עשו בסבב הקודם → intent שגוי (למשל "תעלה לדסישנס" אחרי שקובץ כבר נמצא ב-context, בלי שהסוכן יודע).
- **`session_store.py`** — `last_tool_result` נוסף ל-`_new_session()`; `set_last_tool_result`/`get_last_tool_result` חדשים ב-`PersistentSessionStore`, מסונכרנים ל-`State JSON` (sync/load/delete) באותו דגם כמו `last_uploaded_file` מ-C58.
- **`app.py`** — `_capture_last_tool_result()` נקרא אחרי כל tool dispatch אמיתי בלולאת ה-agent (לא על branches חסומים/ממתינים לאישור); `_build_tool_context()` מזריק "🔧 הקשר כלים" ל-`ctx.system_prompt` (TTL 5 דקות לפי timestamp, כולל `last_file` מ-Stage 0.6); `resolve_context_pronouns()` + `CONTEXT_PRONOUNS` מחליפים כינויי הצבעה עבריים בהתייחסות מפורשת לפני ה-Router (שלב חדש "2.6" ב-`run_agent()`).
- ⚠️ **3 סטיות מתועדות מהספק:** (1) הספק מניח חוזה `tool_result` עם `id`/`record_id`/`url`/`drive_url` — החוזה האמיתי בקוד (C53-A, `test_c53a.py`: `{ok,tool,external_id,evidence,user_message}` בלבד) שונה; תוקן ל-`external_id`→`record_id`, `evidence.get("htmlLink") or evidence.get("url")`→`url`. (2) `_seconds_ago()` מוזכר ב-§5 בלי הגדרה (כמו `_has_keyword_conflict` ב-C59) — מומש inline. (3) §6 "Table Registry fix" (4 קבועי Decision Tables) — אומת מראש שכבר קיימים מ-C59 — no-op.
- **Verification:** `python3 -m py_compile` נקי על `app.py`/`session_store.py`/`airtable_schema.py`; `session_store.py` self-test → **40/40 עוברים** (4 חדשים ל-C60); `test_c53a.py` → 50/50 (ללא רגרסיה בחוזה); `test_integration.py` → 4/4; `smoke_tests.py` — 2 כשלים קיימים-מראש (`flask`/`httpx` חסרים בסביבת dev, אומת זהה ב-`git stash`); §9 greps של הספק כולם תקינים.
- **ממתין:** §10 פריט 7 של הספק (בדיקת לייב: העלה קובץ → "תעלה לדסישנס" → BOSS זוכר ומנתב נכון) — פתוח עד merge+deploy; commit+push לענף עדיין לא בוצעו בזמן כתיבת שורות אלו (ראו §4 Next Priorities).

**C59 Decision Hub Stage 1 — Trust Layer (25/06/2026, מוזג ל-`main` — PR #151, commit `73f6fe8` — לא מאומת בפרודקשן):**
- **מקור:** `SPEC_Decision_Hub_Stage1_Trust_Rev2.md` (הועלה ע"י הבעלים; 3 שדות חדשים נוצרו ב-Airtable Decision Events — Claim Topic/Claim Topic Source/Claim Topic Confidence — ואושר מפורשות "ניתן ליישם ספק", מקיים את שער "SPEC ONLY — אין קוד עד אישור אליהו").
- **הבעיה שנפתרה:** `gate_trust` ב-`decision_pipeline.py` היה stub (`return GateResult(True, "trust stub")`) — שום Decision Event לא קיבל ניקוד אמינות אמיתי לפני שלב 1.
- **`airtable_schema.py`** — 3 שדות חדשים ב-`DecisionEventFields` (Claim Topic/Source/Confidence); `DecisionSourceReliability` הורחב ל-10 קבועים (נוספו DOCUMENT/MANUAL/EMPLOYEE/UNKNOWN שחיו רק ב-AUTHORITY_SCORE ולא בשכבת ה-schema); class חדש `DecisionClaimTopicSource` (Auto/Filename/Keyword/Event Type/Manual); 2 תגיות חדשות ב-`DecisionEventTag` (LOW_CONFIDENCE/PRESSURE_HIGH_RISK — **לא אומתו מול Multi-Select אמיתי ב-Airtable**).
- **`decision_pipeline.py`** — `compute_trust(authority, medium, verify_status)` (Authority 60%/Medium 40%, medium ceiling, verify="warn"→×0.85, verify∈{hallucination,failed}+authority≥65→T0/conf=10 ישירות); `extract_claim_topic()` מחזיר `(topic, source, confidence)` בעדיפות filename→Event Type→Delta Type→keyword→None; `maybe_supersede()` (אותו Claim Topic בלבד + Trust rank גבוה יותר בלבד); `gate_trust` מחובר במלואו (T0→Review+flag, T1→Draft שקט, T2/T3→ממשיך, פלאג "לא זיהיתי נושא" אופציונלי).
- **`decision_ports.py`** — `_AntiHallucinationVerifierAdapter.verify()` תוקן לחזיר `{"status": ..., ...}` (היה `{"verified": bool, ...}` — לא תואם את החוזה ש-`gate_trust` קורא).
- **`cmd_decision.py`** — `event["Channel"]`/`event["_decision_id"]` מוזרקים לפני `run_pipeline()` בשני call sites; helper חדש `_add_trust_fields()` מעביר את פלט gate_trust (Trust Level/Confidence/Tags/Claim Topic*/Source Reliability/Supersedes) ל-fields שנכתבים בפועל ל-Airtable; `_format_pipeline_outcome` קיבל branch ל-`halted_at=="trust"` ומציג `result.user_flag` גם בהצלחה.
- ⚠️ **9 סטיות מתועדות מהספק** (מלא ב-ROADMAP.md §N13/CHANGE_CONTROL_LOG.md §C59): (1) verifier מחזיר dict לא object; (2) `decision["id"]` לא קיים בפועל בנקודת הקריאה → `event["_decision_id"]` הוזרק כפתרון; (3) ערכי Tag באנגלית בספק מול עברית בקוד הקיים — נוספו 2 קבועים עבריים לא-מאומתים; (4) **`_has_keyword_conflict` מוזכר ב-§5 שלב ו' אך גופו לא הוגדר בשום מקום בספק** — מומש כ-stub שמחזיר `False`, conflict-tag path לא נגיש בפועל עד Stage 1.x/2; (5) 4 קבועי `DecisionSourceReliability` היו חסרים מ-schema אף שקיימים ב-AUTHORITY_SCORE — נוספו; (6) Channel תוקן (הוזרק TELEGRAM), אך Source Reliability עדיין אין לו UI input ב-`/decision update` — יישאר "ידני"(55) דיפולטיבי עד שתיווסף שאלה שיחתית; (7) Trust Layer outputs חושבו אך לא נשמרו ל-Airtable — נוסף `_add_trust_fields()`; (8) `run_pipeline()` השליך `user_flag` בהצלחה מלאה — תוקן עם `collected_flag`; (9) `_format_pipeline_outcome` לא הכיל branch ל-trust ולא הציג flag בהצלחה — תוקן.
- **Verification:** `python3 -m py_compile` נקי על כל 6 הקבצים שהשתנו; `test_decision_trust.py` (חדש, 33 self-tests) → **33/33 עוברים**; §9 greps של הספק כולם תקינים/סטיות מתועדות; `python3 smoke_tests.py`/`test_integration.py` ללא רגרסיה (2 כשלים קיימים-מראש ב-smoke_tests, אומתו זהים ב-`git stash`+rerun מול `main` נקי — תלות `flask`/`httpx` חסרה בסביבה, לא קשור).
- **ממתין:** §10 פריט 11 של הספק (T0 event אמיתי → user_flag מוצג בטלגרם בפרודקשן) — פתוח עד פריסה. PR #151 מוזג ל-`main` (אומת GitHub MCP), branch מרוחק נמחק.

**C58 Universal Sessions (25/06/2026, מוזג ל-`main` — PR #150, commit `84f2ef3` — לא מאומת בפרודקשן):**
- **מקור:** `SPEC_C58_Universal_Sessions.md` (הועלה ע"י הבעלים עם הוראה מפורשת "implement" — אישור ה-"SPEC ONLY עד אישור אליהו" gate שבכותרת הספק).
- **הבעיה שנפתרה:** `Tables.LEAD_SESSIONS` ("LeadSessions") **לא קיימת בפועל ב-Airtable** — כל כתיבה הייתה מחזירה 403. זה היה באג latent שלא תועד קודם ב-`BUG_AUDIT_LOG.md` (BUG-017/BUG-B הקודמים תיקנו רק את חוזה ה-dict/schema-governance, לא את עצם אי-קיום הטבלה).
- **`airtable_schema.py`** — `Tables.SESSIONS = "Sessions"` (`tblHLfE24lTkVUhz0`) נוסף; `class SessionsFields` חדש (Context Type/State JSON/Sender ID/Channel/Created At/Updated At + 10 שדות Linked * אופציונליים). `Tables.LEAD_SESSIONS` סומן deprecated בהערה, לא נמחק.
- **`session_store.py`** — `_sync_to_db`/`_load_from_db`/`_delete_from_db` נכתבו מחדש לכתוב/לקרוא מ-`Tables.SESSIONS`; כל ה-state (domain/step/answers/done/drop_off_step/score/tier/**last_uploaded_file**) נשמר במאוחד בשדה `State JSON` יחיד. **משנה את הערת C58 הקודמת ב-§Stage 0.6 למטה: `last_uploaded_file`/`FileUploadResult` כבר לא RAM-only — נכתב ל-Airtable מ-C58 ואילך** (ראה תיקון 2 למטה). `_extract_balanced_json()` חדש מחלץ JSON מקונן מתוך הפלט הטקסטואלי של `airtable_get()` בספירת עומק סוגריים (לא regex naive).
- ⚠️ **4 סטיות מכוונות ומתועדות מהטקסט המילולי של הספק** (מלא ב-`CHANGE_CONTROL_LOG.md`): (1) `external_id` נקרא לפי חוזה C53-A האמיתי, לא שרשרת fallback שגויה; (2) `last_uploaded_file` נוסף ל-State JSON (הספק השמיט, בסתירה לעקרון "אפס אובדן מידע" שהוא עצמו הצהיר); (3) `LINKED_MEDIA_FILE` מקושר רק כש-`type=="drive_file"` (Media Files record) ולא `"inbox_file"` (Decision Inbox record — טבלה אחרת, היה גורם ל-`INVALID_RECORD_ID`); (4) `_delete_from_db` משמר state קודם ב-tombstone, לא מוחק אותו.
- **תיקון נלווה (לא קשור ל-C58):** mock ה-self-tests רשם `sys.modules["airtable_tools"]` במקום `sys.modules["tools.airtable_tools"]` — היה מסתיר בשקט כל כשל DB-sync (ImportError נתפס). זה ה-2 כשלים שתועדו ב-N13 כ"קיימים מראש, לא קשורים" — כעת מתוקנים.
- **Verification:** `python3 -m py_compile session_store.py airtable_schema.py app.py cmd_decision.py` נקי; `python3 session_store.py` → **36/36** self-tests עוברים. spec §6 greps כולם תקינים, כולל `grep -c "LeadSessions" session_store*.py` → 0.
- **ממתין:** ספק §7 item 5 — אימות שרשומה אמיתית נוצרת ב-Sessions ב-Airtable בפרודקשן (לא בוצע עדיין). שמות השדות ב-`SessionsFields` הותאמו לטקסט הספק בלבד — לא אומתו ישירות מול schema חי ב-Airtable. PR #150 מוזג ל-`main` (אומת GitHub MCP), branch מרוחק נמחק.

**C57 Agent Tool Awareness (25/06/2026, PR #149, `main` = `1d08402`):**
- **`app.py`** — בלולאת ה-agent, אחרי חילוץ `tool_uses`/`text_blocks` מ-`response.content`: אם שניהם קיימים באותה תשובה (Claude מחזיר text+tool_use יחד — ה-text נכתב לפני שראה תוצאת כלי), `text_blocks` מאופס ל-`[]` ונכתב `logger.info("[C54] Suppressed premature text_block alongside tool_use: ...")`. הלולאה ממשיכה כרגיל, הכלי רץ, התשובה האמיתית מגיעה ב-turn הבא עם תוצאת הכלי בפועל — מונע תשובה סותרת/מבלבלת למשתמש (למשל "לא הבנתי מה לעלות" לצד כלי upload שרץ בהצלחה).
- **`core_knowledge.py`** — כלל 7 חדש בבלוק `_NEVER_FAKE_CONTROL`: לא לכלול טקסט הסבר/שאלת הבהרה באותה תשובה עם הפעלת כלי; להפעיל את הכלי, לקבל תוצאה, ואז לענות.
- **מקור:** `SPEC_C54_Agent_Tool_Awareness.md` (הועלה ע"י הבעלים, אושר במלואו לפני כתיבת קוד — "SPEC ONLY" gate).
- ⚠️ **ID collision:** הספק תייג זאת "C54" — מתנגש עם C54 הקיים ב-ROADMAP.md (Business Memory /update command, PR #85). תויג מחדש **C57** בכל מסמכי התיעוד; `logger.info`/docstring בקוד עצמו נשארו `[C54]` כפי שנכתבו (לא נגענו בלוג production string ללא צורך).
- **לא flag-gated** — שינוי התנהגות תמיד-פעיל בלולאת ה-agent, לא פיצ'ר ניתן-לכיבוי.
- **Verification:** `git fetch origin main` + `git merge-base --is-ancestor cc6142b origin/main` → exit 0; `py_compile` נקי על `app.py`/`core_knowledge.py`.
- **ממתין:** אימות לייב — לחפש `[C54] Suppressed premature text_block` ב-Render logs אחרי deploy; אם לא מופיע תוך שבוע, ה-prompt rule (כלל 7) הספיק לבד.

**Decision Hub Stage 0.5/0.6 + governance docs (25/06/2026, PR #147, `main` = `483851f`):**
- **Stage 0.5 — File/Voice Precedence Routing** (`4ac2a05`): `cmd_decision.decision_context_active()`/`route_file_to_decision_inbox()` מוטמע ב-`app.py::_handle_telegram_media`, גרור ל-Decision Inbox כש-context פעיל, fail-safe לדרך הדיפולט (Drive/Voice) אם משהו נכשל. מימוש חוק 9 (Input Precedence) בקוד חי לראשונה.
- **Stage 0.6 — File Context Reference** (`e0f0111`): `FileUploadResult`/`set_last_file()`/`get_last_file()` ב-`session_store.py` (RAM-only, לא נכתב ל-Airtable — אין עמודה `last_uploaded_file` ב-LeadSessions, ראו `SPEC_BUG_B_LeadSessions_Schema.md` §8); `is_attachment_reference()`/`handle_attachment_reference()` ב-`cmd_decision.py` לזיהוי "זה הנספח" וכו'. **הוטמע ב-`_webhook_telegram_impl` (טלגרם-ספציפי), לא ב-`run_agent()` (משותף לכל הערוצים)** — תוקן תוך כדי בנייה לאחר שזוהה ש-`run_agent()` נקרא גם מ-WhatsApp שאין לו אובייקט `bot` טלגרם.
- **BUG-017** (`fdeb039`) — `session_store._sync_to_db` קרא את חוזה ה-dict של `airtable_add`/`airtable_update` (C53-A) כ-string; תוקן רק ב-`_sync_to_db`, לא ב-`_load_from_db` (שמשתמש בפונקציה אחרת, `airtable_get`, שמחזירה string).
- **BUG-B** — LeadSessions הובאה תחת schema governance (additive, אפס שינוי התנהגות).
- **MODULE_RULES.md** (`a6483c8` + תיקון מספור 25/06) — חוקים 7 (Ports), 8 (Tool↔Gate registry), 9 (Input Precedence), 10 (Raw-First), 12 (Domain-Agnostic Core — ממוספר 12 לא 11, כדי לא להתנגש עם חוק 11 הקיים: כתיב שמות שדות ב-airtable_schema.py).
- **נוסף `docs/governance/PLANNING_GATE.md`** — שער תכנון של 5 שערים ארכיטקטוניים + 3 השאלות הקיימות, עובר תמיד לפני קוד (להבדיל מ-MODULE_RULES, רפרנס לפי דרישה).
- **נוסף `archive/BOSS_MASTER_PLAN_One_Road.md`** — תיעוד ARCHIVE של עקרון "כביש אחד, יציאות רבות"; הקובץ המקורי הכריז על עצמו "ACTIVE REFERENCE" — תוקן ב-provenance note בראש הקובץ, כי זה מתנגש עם הצהרת `ROADMAP.md`/`CLAUDE.md` שROADMAP הוא מקור האמת היחיד.
- **N13 נוסף ל-ROADMAP.md** — Decision Hub לא היה מתועד שם בכלל לפני תיקון זה.
- **Verification:** `git fetch origin main` + `git merge-base --is-ancestor origin/claude/new-session-be1ckb origin/main` → exit 0; `py_compile` נקי על `app.py`/`cmd_decision.py`/`session_store.py`.

**BUG_AUDIT_LOG.md תוקן (commit `881b41e`/`01558a0`):**
- **BUG-013** (PR #117, `aae59c4`) — קובץ Telegram oversized (voice/photo/document >50MB) הוריד את כל הקובץ *לפני* בדיקת גודל; כעת `_classify_size(file_size)` נבדק מול `message.voice/photo/document.file_size` **לפני** `bot.get_file()`/`download_file()` — דוחה מיידית עם `FILE_TOO_LARGE`, ללא הורדה כושלת/תקועה.
- **BUG-014 תיעוד תוקן** — סטטוס "Merged: לא עדיין" היה שגוי; PR #115 מוזג בפועל (`cf0ded7`, אומת מול GitHub API).
- **BUG-015** (PR #108, `095b59d`) — `MediaFileFields` לא היה ב-`TABLE_CLASS_MAP` (`schema_audit.py`) → N07 לא בדק את טבלת Media Files בכלל; נוסף ל-map, וטבלה חסרה ב-live עכשיו `❌`+exit 1 (לא `⚠️` שקט).
- **BUG-016** (PR #108, `095b59d`) — תזכורת אבטחה שבועית הציגה תמיד "999 ימים" כי שום קוד לא כתב ל-`LAST_SECURITY_REVIEW`; נוסף `record_security_review()` הכותב ל-`/tmp/security_review.json` (תבנית זהה ל-emergency flags).

**ניקוי ענפים (סשן 23/06/2026):** audit מלא של 37 ענפי `claude/*` לא ממוזגים → 34 נמחקו (ממוזגים בפועל/זהי-תוכן/orphan/collision שנפתר בעבר). שני ענפים הכילו עבודה אמיתית שחולצה לפני מחיקה: N12 (PR #108) ותיקון תיעוד C56 (PR #112). מסמך `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` שוחזר ישירות ל-`main` (`783a680`).

**F16 Media Layer — הושלם במלואו (PR #96/#97/#98/#99/#100/#101):** STT (Whisper), Drive upload, Airtable Media Files metadata, `app.py`/`tma_api.py` hooks, schema — קוד שלם ומחובר, flags כבויים. תוקנו בדרך 2 באגים חוסמים (`upload_file()` kwarg שגוי, כשל Airtable מוסתר) ו-2 gaps קטנים (`send_chat_action`, `linked_lead_id` ב-TMA).

**N07/N08/N09/N11 — תוקן תיעוד:** שלושתם תועדו בטעות כ-`🔲 PLANNED` ב-ROADMAP אף שהיו ממוזגים; תוקן אחרי grep ישיר על `main` (לא git log/PR status).

**שאר ה-PRs האחרונים (לפירוט מלא ראו `CHANGELOG.md`/`CHANGE_CONTROL_LOG.md`):** C22 Weekly Business Summary (PR #94, off by default), C53/O4 Screen Filter Gateway + Finance Pulse, C53-A structured tool-result contract + A32 hardening (PR #80), C54/C55 Business Update command + Origin Lead linking (PR #85/#86), C56 Approval Policy stack (PR #69, off by default).

## 4. Next Priorities
0. **Fxx Safe Document Converter — כבר מוזג ל-`main`** (PR #158, `db719ab`, 26/06/2026; תוקן 29/06/2026 Gap Report — לא "open PR, merge" כמו שכתוב היה). הבא בתור: לחבר ל-נתיב חי (drive/voice upload) **רק** אחרי PLANNING_GATE, או להחליט במפורש להשאיר merged-but-unreachable. בנפרד: לתקן את `test_document_converter.py` כך שירוץ בפועל ב-CI (אין `__main__` guard, ו-`ci.yml` מריץ `python` ולא `pytest`). 6/6 tests עוברים דרך `pytest` ישירות עם `beautifulsoup4`/`markdown`/`python-docx`/`openpyxl` (כבר ב-`requirements.txt`). Pandoc אופציונלי, מועדף כשמותקן.
0. **F52 audit branch** — open/refresh PR for `f52-current-tool-map-audit`; docs only, no production code changes.
0. **C60 Tool Context Awareness — 🟡 CODE DONE, לא ממוזג** — לבצע commit+push ל-`claude/new-session-be1ckb`, ואז PR (רק אם יתבקש)+merge+deploy; לאחר deploy, לאמת §10 פריט 7 של הספק (העלה קובץ → "תעלה לדסישנס" → BOSS זוכר ומנתב נכון). **Decision Hub Stage 1 (Trust Layer) — מוזג** (PR #151); לאחר deploy יש לאמת §10 פריט 11 (T0 event אמיתי מציג flag בטלגרם). Stage 2-4 (ליבה) ממשיכים לפני יציאות נוספות (דומיינים/ערוצים/ייעודים), לפי `archive/BOSS_MASTER_PLAN_One_Road.md` (ARCHIVE, לא מקור אמת).
1. **לאמת BUG-013/014/015/016/017 בפרודקשן בפועל** — כולם מוזגים ל-`main`, אפס אימות ידני עד כה (קובץ >50MB אמיתי / Drive evidence gate / N07 מול live Airtable / security-review persistence).
2. **F16 — הדלקת flags** (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`) — אך ורק אחרי יצירת טבלת "Media Files" ידנית ב-Airtable.
3. **להריץ N07 (`tools/schema_governance.py`) מול live Airtable** — עדיין לא רץ פעם ראשונה (אין credentials בסביבת sandbox).
4. **לאמת מצב Render בפועל מול `main` HEAD (`01558a0`)** — לא ניתן מהסביבה הזו (egress חסום); סיכון פתוח שתועד כבר בגרסאות קודמות.
5. **החלטה על הדלקת N02-N04** (Lead Scoring/Memory/Followup) — קוד מוכן ושלם, אפס תעבורת ייצור אמיתית אומתה עד כה.
