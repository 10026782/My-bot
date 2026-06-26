# BOSS Bot — ROADMAP
**מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE.**
עודכן: 25/06/2026 (מאוחר ביותר) — main = `78f9bae` (אומת, GitHub MCP `pull_request_read` + `git merge-base --is-ancestor`). **PR #157 מוזג** — Decision Hub Stage 2 (F17, Smart Trust Layer): AI Conflict Detection Lazy+Cached (לא Eager — לא רץ ב-ingest, רק בפתיחת/Refresh של `/decision status`, מוגבל ל-Claim Topic זהה + Trust>=T1, deduped לפי `event_pair_hash`, מוגבל ל-5 קריאות Claude חדשות לריצה), Decision Confidence Score, Evidence Graph, Missing Evidence Detector (template-based, לא LLM). 3 סטיות מהטקסט המילולי של הספק תועדו ומומשו (ראו F17 למטה). 25/25 self-tests עוברים (`test_decision_confidence.py`); 33/33 Stage 1 ללא רגרסיה. דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל — אפס שינוי התנהגות בפרודקשן. 4 שדות Airtable חדשים עדיין לא נוצרו ביד; פריסה בפועל ל-Render **לא אומתה** (אין גישת dashboard/egress מה-sandbox). ראו פירוט: F17 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — branch `claude/new-session-be1ckb`. **F17 Decision Hub Stage 2 (Smart Trust Layer) — קוד הושלם**, אישור הבעלים בכפוף לתנאי: AI Conflict Detection הוא Lazy+Cached, לא Eager — לא רץ ב-ingest, רק בפתיחת/Refresh של `/decision status`, מוגבל ל-Claim Topic זהה + Trust>=T1, deduped לפי `event_pair_hash`, מוגבל ל-5 קריאות Claude חדשות לריצה. קובץ חדש `decision_confidence.py`: `calc_confidence()` (ממוצע משוקלל של Trust מינוס קנס קונפליקטים/חסר, clamped 0-1), `detect_conflicts_ai_lazy()`, `detect_missing_evidence()` (template-based, לא LLM), `build_evidence_summary()`. מוזרק ל-`_format_decision_card()` ב-`cmd_decision.py` (אין `get_decision()` במערכת — נקודת החיווט הקיימת). 3 סטיות מהטקסט המילולי של הספק תועדו (ראו F17 למטה) — בעיקר: מיקום הקובץ (root, לא `core/`), `REQUIRED_EVIDENCE` ממופה על `DecisionDomain` הקיים במקום "decision_type" לא-מוגדר, ונקודת החיווט (`_format_decision_card` במקום `get_decision()`). 25/25 self-tests עוברים (`test_decision_confidence.py`); 33/33 Stage 1 ללא רגרסיה. 4 שדות Airtable חדשים (`Evidence Ids`/`Evidence Summary`/`Confidence Score`/`Missing Evidence`) **לא נוצרו עדיין ביד ב-Airtable חי** — `airtable_patch()` משמיט אותם בשקט עד אז; תצוגת הטלגרם תקינה בכל מקרה (חישוב in-memory). דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל. **🟡 CODE DONE — לא מאומת בפרודקשן.** ראו פירוט: F17 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — branch `claude/new-session-be1ckb`. **C60 Tool Context Awareness — קוד הושלם** לפי `SPEC_C59_Tool_Context_Awareness.md` (אישור הבעלים דרך `AskUserQuestion`: "Yes, implement now"; ⚠️ הספק תייג עצמו "C59" — מתנגש עם C59 הקיים (Trust Layer, PR #151) — תויג מחדש **C60**): `last_tool_result` נשמר ב-session אחרי כל tool dispatch אמיתי, מוזרק ל-system prompt כ-"🔧 הקשר כלים" (TTL 5 דקות), ו-`resolve_context_pronouns()` מחליף כינויי הצבעה עבריים בהתייחסות מפורשת לפני ה-Router. 3 סטיות מהספק תועדו ומומשו (ראו C60 ב-`CHANGE_CONTROL_LOG.md`) — בעיקר: חוזה tool_result האמיתי (C53-A: `{ok,tool,external_id,evidence,user_message}`) שונה מהשדות שהספק הניח (`id`/`record_id`/`url`/`drive_url`). 40/40 self-tests עוברים. **🟡 CODE DONE — לא מאומת בפרודקשן** (§10 פריט 7 בספק — "העלה קובץ → 'תעלה לדסישנס' → BOSS זוכר" — פתוח עד בדיקת לייב). ראו פירוט: `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `b289ab6` (אומת, GitHub MCP `pull_request_read` + `git log`). **PR #151 מוזג** — Decision Hub Stage 1 (Trust Layer): `gate_trust` ב-`decision_pipeline.py` ממומש במלואו (Authority×Medium×Verify, Claim Topic אוטומטי, Supersedes בטוח) לפי `SPEC_Decision_Hub_Stage1_Trust_Rev2.md`. 9 סטיות מהטקסט המילולי של הספק תועדו ומומשו (ראו N13 למטה) — בעיקר: `VerifierPort` dict-לא-object, `decision["id"]` חסר (הוזרק כ-`event["_decision_id"]`), tags אנגלית-לא-קיימת (נעשה שימוש בקבוע עברי קיים + 2 קבועים חדשים **לא מאומתים מול Airtable חי**), `_has_keyword_conflict` מוגדר ב-spec אך לא יושם (stub). 33/33 self-tests עוברים (`test_decision_trust.py`). דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל; §10 פריט 11 בספק (T0 אמיתי→user_flag בטלגרם) עדיין לא אומת בפרודקשן. ראו פירוט: N13 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `d6b6bc7` (אומת, GitHub MCP `pull_request_read` + `git log`). **PR #150 מוזג** — C58 Universal Sessions: `session_store.py` כותב/קורא מ-`Tables.SESSIONS` (טבלה אמיתית, `tblHLfE24lTkVUhz0`) במקום `Tables.LEAD_SESSIONS` (טבלה שלא קיימת בפועל — הייתה 403 בכל כתיבה). 4 סטיות מהספק תועדו ומומשו במקום הטקסט המילולי (ראו C58 למטה). 36/36 self-tests עברו במיזוג (כולל תיקון באג קדם-קיים ב-mock שהיה מסתיר כשלי DB-sync). סעיף 7 בספק (רשומה אמיתית ב-Sessions ב-Airtable חי) עדיין לא אומת בפרודקשן. ראו פירוט: C58 למטה (Sprint 19/06/2026), `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `1d08402` (אומת, `git fetch origin main` + `git merge-base --is-ancestor`). **PR #149 מוזג** — C57 Agent Tool Awareness (commit `cc6142b`): דיכוי `text_block` מוקדם שנוצר באותה תשובה עם `tool_use` (`app.py`) + כלל 7 ב-`core_knowledge.py`. ⚠️ הספק החיצוני (`SPEC_C54_Agent_Tool_Awareness.md`) קרא לזה "C54" — מתנגש עם C54 הקיים (Business Memory /update, PR #85); תויג מחדש **C57** בתיעוד (הלוג בקוד עצמו עדיין `[C54]`, לא שונה). ראו פירוט: C57 למעלה (Sprint 19/06/2026), `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `483851f` (אומת, `git merge-base --is-ancestor` + `git log`). **PR #147 מוזג** — Decision Hub Stage 0.5 (File/Voice Precedence Routing) ו-Stage 0.6 (File Context Reference) הושלמו והתחברו ל-pipeline החי מאחורי `FEATURE_DECISION_HUB` (כבוי כברירת מחדל); BUG-017 (`session_store._sync_to_db` קרא את חוזה ה-dict של `airtable_add`/`airtable_update` כ-string) ו-BUG-B (LeadSessions תחת schema governance) תוקנו; `MODULE_RULES.md` קיבל חוקים 7-10 ו-12 (Ports / Tool↔Gate / Input Precedence / Raw-First / Domain-Agnostic Core); נוסף `docs/governance/PLANNING_GATE.md`. **N13 (Decision Hub) נוסף לראשונה לקובץ זה** — ראו למטה; לא היה מתועד כאן לפני כן. ראו פירוט: N13, `CHANGE_CONTROL_LOG.md`, `BUG_AUDIT_LOG.md`.

עודכן (קודם): 23/06/2026 (מאוחר יותר) — main = `f737f61` (אומת). **F13 (TenantConfig + Provider Interfaces) סומן במפורש כ-DEAD CODE** — אזהרת "אין לחבר" הוספה מיד אחרי כותרת הסעיף (קוד קיים, אפס imports מקוד חי, כפילות עם `TenantConfig` ב-`tenant_provisioner.py`, הכרעת F12-מול-F13 עדיין לא בוצעה). ראו SPEC-C / PR בענף `claude/fix-f13-status-docs`.

עודכן (קודם): 23/06/2026 (מאוחר) — main = `d1c48a1` (אומת). **ניקוי ענפי `claude/*` ישנים** —
בוצע audit מלא של 29+8 ענפים לא ממוזגים מול `main` (ancestry/diff/content, לא רק
תאריך/שם): 34 ענפים נמחקו בפועל (ממוזגים בפועל / זהים תוכן ל-main / orphan history /
היסטוריית collision שנפתרה כבר בעבר לטובת גרסה אחרת). שני ענפים הכילו עבודה אמיתית
שחולצה לפני המחיקה — **N12** (למטה) ותיקון תיעוד C56 (PR #112). מסמך audit ארכיטקטוני
(`APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md`, 257 שורות, ללא קוד) שוחזר ונשמר ישירות ל-main
(commit `783a680`) לפני שהענף המקורי נמחק. בנוסף: **BUG-014** (`core/anti_hallucination.py`
— Drive נוסף ל-NO-TOOL-EVIDENCE gate, PR #115) ו-**תיקון תיעוד ל-BUG-011** (תועד "לא
ממוזג" בטעות, PR #110 מוזג בפועל ב-`a4c8f27`, PR #116).

עודכן (קודם): 23/06/2026 — main = `29b009e` (אומת). **C56 (Approval Policy: Emergency Window + OTP + Policy Gate) — תועד כ"לא ממוזג" ב-`BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` ולא היה ב-ROADMAP בכלל, אבל בפועל מוזג ל-`main` כבר ב-17/06/2026** (PR #69, merge commit `4e933b0`, מאומת דרך `gh pr view 69` + `git merge-base --is-ancestor`) — נוסף ל-ROADMAP, תוקן בשני המסמכים האחרים. דגל `EMERGENCY_WINDOW` נשאר כבוי — אין שינוי התנהגות בפרודקשן.

עודכן (קודם): 22/06/2026 — main = `24237e6` (אומת, PR #96/#97/#98/#99/#100/#101/#103/#104 ממוזגים). **F16 (Media Layer) הושלם** — כל שבעת ה-batches (א-ז) קיימים ומחוברים ל-pipeline החי, מאחורי דגלים כבויים כברירת מחדל (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`). ⚠️ ה-spec החיצוני קרא לפיצ'ר "F12" ואז "F09" — שני ה-IDs תפוסים (F12=Model Provider Adapter, F09=Lead Qualifier Wire-up); הוקצה F16 כדי למנוע התנגשות בסטייל C20/C21/F14/F15. **N07 (Schema Governance) הושלם** — `tools/schema_governance.py` (PR #101), standalone read-only drift detector, ראו פירוט למטה. **N08 (CI/CD) ו-N09 (Monitoring/Alerting) הושלמו** (PR #103/#104) — תוקנו כ-PLANNED בטעות, ראו פירוט למטה. **N11 (Finance Pulse wiring) התגלה כממוזג מ-PR #77 קודם** — תועד כ-PLANNED בטעות, תוקן.

עודכן (קודם): 20/06/2026 — main = `62eddda` (אומת). PR #85/#86/#87/#88/#89 ממוזגים (ראה C54/C55 למטה + CHANGE_CONTROL_LOG.md). F13 (TenantConfig + Provider Interfaces) — קוד נכתב ומוזג (PR #87), **לא מחובר ל-pipeline**; ⚠️ חפיפה עם F12 עדיין לא הוכרעה, אל תחבר ל-pipeline לפני הכרעה. `contact_merge.py` (PR #88) — כלי CLI עצמאי למיזוג אנשי קשר, לא ב-ROADMAP (admin utility, לא feature). נוספו F14 (Contact Gate: find_or_create_contact) ו-F15 (crm.py → airtable_gateway write path migration) — ⚠️ הספק ביקש F12/F13, אך שני ה-IDs האלה תפוסים (F12=Model Provider Adapter, F13=TenantConfig); הוקצו F14/F15 כדי למנוע התנגשות בסטייל C20/C21.

---

## עיקרון ניהול
- **C** = Completed — הושלם ובפרודקשן
- **W** = Completed (World 2 sprint) — נוסף במהלך Lead Flow Audit
- **N** = Next — הבא בתור, מסודר לפי תלויות
- **F** = Future — מתוכנן, אין תאריך

כל פיצ'ר חדש נרשם כאן לפני שנוגעים בקוד.
כל batch מתחיל מקריאת ROADMAP — לא מזיכרון.

---

## C — הושלם

### CORE — תשתית
| ID | שם | קבצים |
|----|----|--------|
| C01 | Identity + Roles | identity.py, tool_registry.py, context.py |
| C02 | Router — Intent / Domain / Risk | core/router/ (7 קבצים) |
| C03 | Anti-Hallucination | core/anti_hallucination.py |
| C04 | Feature Flags | feature_flags.py |
| C05 | Action Validator | action_validator.py |
| C06 | Event Bus + Approval Flow | event_bus.py |
| C07 | Domain Prompts (לפי דומיין) | domain_prompts.py |
| C08 | Memory Store (שיחה קצרת-טווח, TTL) | memory_store.py |
| C09 | Circuit Breaker + Rate Limiter | circuit_breaker.py, rate_limiter.py |

### Lead System
| ID | שם | קבצים | הערה |
|----|----|----|------|
| C12 | Lead Events (audit log) | core/lead_events.py | |
| C13 | Shared Memory (תובנות עסקיות לפי דומיין) | core/shared_memory.py | |
| ~~C14~~ | ~~Lead Scoring~~ | ~~lead_scoring.py~~ | **הוסר — zombie file; scoring consolidated ל-lead_capture.py (N02/N03)** |

### CRM + Storage
| ID | שם | קבצים |
|----|----|--------|
| C16 | CRM Repository (get_lead / save_lead) | crm.py |
| C17 | Airtable Search + Schema Self-Sync | airtable_tools.py |
| C18 | Store Protocol (LeadStore / EventStore) | core/stores/base.py |

### App Layer
| ID | שם | קבצים |
|----|----|--------|
| C19 | app.py — 4 Hooks (H1–H4) | app.py |
| C20 | Scheduler (jobs קיימים) | scheduler.py |
| C21 | Daily Digest | daily_digest.py |

### חוזה (Contract Fix)
| ID | שם | מה תוקן |
|----|----|---------|
| C22 | feature_flags — is_enabled() alias | 3 קבצים שיובאו בשם לא קיים |
| C23 | config — תיעוד input provider בלבד | מנע מקור אמת כפול עם domain_router |
| C24 | lead_qualifier — detect_domain() | get_domain(channel,sender) לא קיים |

### Stabilization Sprint — 07/06/2026
| ID | שם | מה תוקן | קבצים |
|----|----|---------| ------|
| C25 | Google Tools merge conflict | SyntaxError שורה 21 — נפתר | tools/google_tools.py |
| C26 | lead_qualifier TypeError | get_domain signature mismatch — תוקן | lead_qualifier.py |
| C27 | Event Bus fail-closed | confirm() מחזיר הצלחה רק אם handler רץ בפועל | event_bus.py |
| C28 | email_inbound honest stub | ImportError → mock הוסר; stub כנה | email_inbound.py |
| C29 | TMA approval stubs | TODO הוחלף ב-coming_soon / רשימה ריקה | tma_api.py |
| C30 | tool_registry sync | כלים מיושרים: schemas / validator / registry / dispatcher | tool_registry.py, schemas.py |
| C31 | Airtable shim | תיקון imports עקביים לכל מודולי עזר | airtable_tools.py |
| C32 | Twilio signature validation | WhatsApp webhook מאמת חתימה | app.py |
| C33 | Emergency Stop persistence | flag נשמר ב-restart | feature_flags.py |
| C34 | Mock data removed | דוחות מציגים כשלים אמיתיים | daily_digest.py, workers |
| C35 | Approval subscribers x4 | send_email_reply, send_followup, send_recovery, send_bounce | event_bus.py |
| C36 | Approval UX honest | הצלחה מוצגת רק אחרי פעולה אמיתית | app.py |
| C37 | Payment Reminder fix | self-test עובר (commit 0744ce9) | payment_reminder.py |
| C38 | WhatsApp outbound honest stub | לא מעמיד פנים — מחזיר stub כנה | app.py / whatsapp tools |
| C39 | TMA CORS + auth 401 | CORS origin נוסף ל-Render env; 401 נפתר | tma_api.py, Render env |
| C40 | Golden Path Approval Gate | TMA write endpoints now require approval before Airtable writes: POST /api/projects, PATCH /api/leads/<lead_id>/status, POST /api/followup. Writes execute only after approve; reject does not write; receipt returned after execution; audit runs only after successful execution. | tma_api.py (commit 4e5d00d on origin/approval-gate; supersedes local f3172ba) |

### World 2 — Lead Flow Sprint (08/06/2026)
| ID | שם | מה נעשה | קבצים | commit |
|----|----|---------|--------|--------|
| W0 | WhatsApp Lead Capture | ליד נכנס ← נוצר/מתעדכן Leads ב-Airtable | lead_capture.py, app.py | 2b861bd |
| W1 | Airtable Schema Fix (N01) | LeadFields.SCORE/TIER + schema_intelligence sync | airtable_schema.py, schema_intelligence.py, tma_api.py, daily_digest.py | f095036 |
| W1b | W1 Completion — Score/Next Followup case fix | LeadFields.SCORE "score"→"Score"; FIELD_ALIASES aligned; schema_cache.json updated | airtable_schema.py, schema_cache.json, schema_intelligence.py, lead_memory.py, tools/airtable_tools.py | a6b471c |
| W2 | Airtable Gateway — single write path | tools/airtable_gateway.py: normalize→validate→audit→httpx; tma/agent/lead_capture migrated; 22-test regression suite | tools/airtable_gateway.py, tma_api.py, airtable_tools.py, lead_capture.py, app.py | b43357e |

### Sprint 16/06/2026
| ID | שם | מה נעשה | קבצים | PR |
|----|----|---------|--------|-----|
| C41 | LLM Fallback Handlers | APIStatusError + APITimeoutError → flag-gated OpenAI fallback או Hebrew error נקי | app.py | — |
| C42 | FEATURE_LLM_FALLBACK flag | default=False, registry comment | feature_flags.py | — |
| C43 | Hebrew Mojibake fix | כל Hebrew error strings תוקנו ב-byte level | app.py | — |
| C44 | ⏳ thinking indicator restored | C1 control char → ⏳ תקין | app.py | — |
| C45 | BossCheckin duplicate block removed | TS2451/TS1308 Vercel build errors נפתרו | tma-frontend/ | PR #59 + UX follow-up |
| C46 | Furniture WhatsApp Funnel | Deterministic flow + app.py intercept — rebased on main | app.py | PR #61 |
| C47 | Game today task filtering | Roadmap_Tasks filtered by Due_Date ≤ Today + Owner | tma_api.py | PR #62 |
| C48 | Coins Log schema fix + approval concurrency hardening | Note→Notes תוקן; approval 3-state atomic hardened | tma_api.py | PR #63 |
| C49 | Ops Docs | README, CHANGELOG, RUNBOOK, DEPLOYMENT נוצרו | docs/, root | PR #60 |
| C50 | F12 Model Provider Adapter | תועד כ-Future item ב-ROADMAP | ROADMAP.md | — |
| C51 | Approval Concurrency Regression Test | test ל-3-state approval flow: pending→processing→approved/failed + double approve guard | test_approval_concurrency.py | branch furniture-funnel-clean |
| C52 | Customer Output Gateway (COG) | נקודת כניסה יחידה לכל שליחה ללקוח — Financial Gate (shadow mode), ESCALATE לא BLOCK, Secondary Guard ב-Send Adapters | core/output_gateway.py, core/financial_gate.py, tools/whatsapp_adapter.py | PR #70 |

### Sprint 18/06/2026
| ID | שם | מה נעשה | קבצים | PR |
|----|----|---------|--------|-----|
| C53 | Screen Filter Gateway | `SCREEN_CONFIGS` + `_build_formula()` — Gateway מבצע, Screen מחליט. `get_leads()` (`GET /api/leads`) תומך ב-`?view=active\|monitoring\|all` + `available_views` בתשובה; view לא חוקי → fallback ל-`active` (לא 400). `_get_project_cards()` ו-`get_project_dashboard()` חוברו ל-`project_hub_kpi` config לספירת לידים אחידה. תשתית additive ל-multi-tenant עתידי (`finance_pulse`, `assets_overview`, `activity_feed` configs מוכנים בזמן הכתיבה; `finance_pulse` חובר בפועל ב-PR #77, ראו O4 למטה) | tma_api.py בלבד (commit `5b07088`) | **PR #75 — ממוזג ל-`main`** (merge commit `6218155`, 18/06/2026) |

### Sprint 19/06/2026
| ID | שם | מה נעשה | קבצים | PR |
|----|----|---------|--------|-----|
| O4 | Finance Pulse — English schema + Screen Filter Gateway wiring | `Tables.PAYMENTS`/`EXPENSES` ו-`PaymentFields`/`ExpenseFields`/`PaymentStatus` עברו לשמות השדות האנגליים החיים ב-Airtable (מיגרציה ידנית בוצעה מראש). `finance_pulse()` עבר דרך `SCREEN_CONFIGS["finance_pulse"]` + `_build_formula()`, כמו `/api/leads`. נוסף `?view=active\|overdue\|all` + `available_views`. שני gaps קיימים תועדו ב-CHANGELOG.md ולא נסגרו במכוון (מחוץ ל-scope): `crm.py`'s `PaymentFields.CONTACT/NOTES` מצביעים על שדות שלא קיימים בטבלת Payments החיה; case-mismatch ב-`_build_formula()` לדומיין Payments/Expenses | airtable_schema.py, tma_api.py, smoke_tests.py | **PR #77 — ממוזג ל-`main`** (merge commit `0608798`, commits `f7d7e4f`+`daab73e`) |
| C53-A | Structured tool results + verify_execution dict contract | טפסי tool-result עברו מ-string חופשי ל-contract structured: `{ok, tool, external_id, evidence, user_message}`. מוחל על `airtable_add`/`airtable_update`/`gmail_draft`/`gmail_send_draft`/`calendar_create_event`. `core/anti_hallucination.verify_execution()` עכשיו בודק `ok`+`external_id`/evidence ייעודי per-tool (לא substring matching). `guards/rate_limiter.validate_tool_output()` משמר dict (לא הופך ל-string). `_handle_approval_callback` ב-app.py בודק `verify_execution()` אחרי dispatch ומודיע למשתמש על כשל ביצוע בלי לדווח הצלחה כוזבת. | app.py, core/anti_hallucination.py, guards/rate_limiter.py, tools/airtable_tools.py, tools/google_tools.py, tools/schemas.py | **PR #79 — ממוזג ל-`main`** (merge commit `be65801`, commits `ffa3afc`+`3a34529`) |
| A32 / C53-A Hotfix | identity-based NO-TOOL-EVIDENCE enforcement + app.py crash fix | PR #79's dict contract לא נגע ב-`app.py` — קריאה ישירה (לא approval) ל-4/5 tools קרסה (`KeyError: slice(...)`), ו-approval callback דיווח הצלחה בלי לבדוק `verify_execution()`. תוקן עם helper `_tool_user_message()` בשתי הנקודות. בנוסף חוּזק A32's NO-TOOL-EVIDENCE gate ב-`core/anti_hallucination.py` — evidence נבדק לפי tool identity+ok per-claim-category, לא keyword guessing; `_NO_TOOL_EVIDENCE_FALLBACK` ספציפי יותר. נוסף `test_a32_enforcement.py` (end-to-end run_agent). | app.py, core/anti_hallucination.py, test_a32_enforcement.py, test_c53a.py | **PR #80 — ממוזג ל-`main`** (merge commit `7496628`, commit `42dd137`) |
| C54 | Business Memory /update command | פקודת `/update` לboss_hq — שמירת הקשר עסקי שקיים "בראש" (פגישות, החלטות, שיחות). tenant isolation, TTL, `/cancel` support, context injection cap. | cmd_update.py, app.py, context.py | **PR #85 — ממוזג ל-`main`** |
| C55 | Origin Lead backlink (Lead→Contact + Lead→Deal) | שדה "Origin Lead" (linked record) נוסף ל-Contacts (`fldGE1seCyCdWJGCO`) ו-Deals (`fldoobGq4PS78C0Em`). Contact/Deal שנוצרו מליד מקושרים חזרה לרשומת הליד המקורית. | airtable_schema.py, crm.py, lead_conversion.py | **PR #86 — ממוזג ל-`main`** |
| C56 | Approval Policy: Emergency Window + OTP + Policy Gate | שכבת אישור מדורגת לפי סיכון (Low/Medium/High/Critical) × פלטפורמה (mobile/desktop). Low תמיד מותר; Medium מהטלפון דורש אישור כפול; High מהטלפון דורש Emergency Window פעיל + OTP; Critical לעולם לא מהטלפון ודורש OTP בכל מצב. `web` מסווג כ-mobile (fail-closed). ⚠️ לא תועד ב-ROADMAP עד 23/06/2026 — `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` תיעדו "Merged: לא" בזמן שהקוד היה כבר מוזג בפועל; תוקן. `EMERGENCY_WINDOW` flag כבוי כברירת מחדל — אין שינוי התנהגות בפרודקשן. | core/emergency_window.py, core/otp.py, tma_api.py, tma-frontend/src/api.ts | **PR #69 — ממוזג ל-`main`** (merge commit `4e933b0`, 17/06/2026) |
| C57 | Agent Tool Awareness — דיכוי text_block מוקדם לצד tool_use | Claude מחזיר לעיתים text+tool_use באותה תשובה — ה-text נכתב לפני שראה תוצאת כלי, נשלח למשתמש ומבלבל ("לא הבנתי" לצד כלי שרץ בהצלחה). תיקון כפול: (1) `app.py` — אם `tool_uses and text_blocks` באותה response, ה-text מבוטל (`text_blocks = []`) ולוג `[C54] Suppressed premature text_block...` נכתב; הלולאה ממשיכה לתוצאה האמיתית ב-turn הבא. (2) `core_knowledge.py` — כלל 7 חדש ב-`_NEVER_FAKE_CONTROL`: לא לכלול טקסט הסבר/הבהרה באותה תשובה עם הפעלת כלי. ⚠️ **הערת מספור:** מסמך המקור (`SPEC_C54_Agent_Tool_Awareness.md`) קרא לזה "C54" — מתנגש עם C54 הקיים מעלה (Business Memory /update, PR #85). לוג הקוד עצמו עדיין מתויג `[C54]` (string בקוד, לא שונה כדי לא לגעת בלוג production ללא צורך) — אך **בתיעוד** (ROADMAP/CHANGE_CONTROL/BUG_AUDIT) המספור הוא **C57**. | app.py, core_knowledge.py | **PR #149 — ממוזג ל-`main`** (merge commit `1d08402`, commit `cc6142b`) |
| C58 | Universal Sessions — Sessions table (לא LeadSessions) | `LeadSessions` לא קיימת בפועל ב-Airtable (הייתה גורמת ל-403 בכל כתיבה); הוחלפה ב-`Tables.SESSIONS` (`tblHLfE24lTkVUhz0`, טבלה קיימת) עם schema גנרי משותף לכל הדומיינים: `Context Type` (select) + `State JSON` (כל ה-state הקיים — domain/step/answers/done/drop_off_step/score/tier/last_uploaded_file — בשדה טקסט יחיד, אפס אובדן מידע) + שדות `Linked *` אופציונליים. `context_type="lead"` ברירת מחדל — תאימות לאחור מלאה לזרימת lead_qualifier הקיימת. `Tables.LEAD_SESSIONS` הוצא משימוש (deprecated, לא נמחק מהקוד). ⚠️ **4 סטיות מהספק (`SPEC_C58_Universal_Sessions.md`), כולן מתועדות ב-commit ו-`CHANGE_CONTROL_LOG.md`:** (1) `external_id` נקרא ישירות מ-`result.get("external_id", "")` לפי חוזה C53-A האמיתי, לא שרשרת fallback שגויה שהספק הציע; (2) `last_uploaded_file` נוסף ל-State JSON (הספק השמיט אותו, בסתירה לעקרון "אפס אובדן מידע" שהוא עצמו הצהיר); (3) `SF.LINKED_MEDIA_FILE` מקושר רק כש-`last_uploaded_file.type == "drive_file"` (Media Files record) — לא כש-`type == "inbox_file"` (Decision Inbox record, טבלה אחרת; קישור היה גורם ל-`INVALID_RECORD_ID`); (4) `_delete_from_db` משמר את כל ה-state הקודם ב-tombstone (`done`/`deleted=True` בתוך State JSON הקיים), לא מוחק אותו כמו שהספק הציע. תוקן גם באג קדם-קיים (לא קשור ל-C58): mock ה-self-tests רשם `sys.modules["airtable_tools"]` במקום `sys.modules["tools.airtable_tools"]` — היה גורם לכל בדיקות ה-DB-sync "לעבור" בלי לבדוק כלום (ImportError נתפס בשקט). | airtable_schema.py, session_store.py | 🟡 CODE DONE — לא נוצרה PR; ממתין לאימות רשומה אמיתית ב-Sessions בפרודקשן |

---

## N — הבא בתור

**סדר ביצוע קשיח — כל N תלוי ב-N שלפניו.**

### N01 — ✅ הושלם (W1 לעיל)

### N02 / N03 — Lead Scoring + Lead Memory Wire-up ✅ מיושם
**lead_capture.py בלבד** — single path:
1. יצירת Lead ב-Airtable (`LEAD_CAPTURE=true`)
2. `_score_inbound_message()` → `airtable_patch(Score)` (`LEAD_SCORING=true`)
3. `lead_memory.update()` עם `domain/channel/contact_name/summary/last_message` — **תמיד** בעת create, גייטד ב-`LEAD_MEMORY` בלבד (N04-A)
4. `lead_memory.update()` עם `tier/score/record_id` אחרי scoring (N04-B)
**lead_scoring.py** הוסר — היה zombie code.
**flags:** LEAD_SCORING, LEAD_MEMORY (שניהם כבויים ברירת מחדל).
**commits:** 4d1130a (consolidation), 02f7e75 (N04-A/B wiring)

### N04 — Followup Activation ✅ scheduler מחובר (flag כבוי)
`scheduler._job_followup_scan()` רץ כל 60 דקות, קורא ל-`followup_engine.run_followup_scan()`.
גייטד ב-`FOLLOWUP_AUTOMATION=true` — כבוי ברירת מחדל.
`lead_memory.all_active()` מחזיר כעת entries אמיתיים (N04-A/B — commit 02f7e75).
**המתנה לפני הפעלה**: לאמת ב-Render env עם הודעת WhatsApp אמיתית + `LEAD_CAPTURE=true`.
**קבצים:** `scheduler.py` (קיים), `followup_engine.py` (קיים).

### N05-B — send_followup.confirmed handler ✅ מיושם (commit 643f929)
Owner מאשר followup → טיוטה מגיעה ב-Telegram לשליחה ידנית.
`lead_memory.followup_count` מתעדכן אחרי כל אישור.
**אין שליחה יוצאת לליד** — Meta outbound blocked עד N05-C.
**flag:** `FOLLOWUP_AUTOMATION` (אותו gate כמו N04).

### N05 — Daily Digest שדרוג ✅ מיושם
**תלוי ב:** N02 (כדי שציונים אמיתיים יופיעו בדוח).
**מה:** חיבור score + tier לדוח הבוקר. `_hot_leads()` עבר מפילטר
status='hot' מת (לא נכתב לעולם בקוד) לפילטר `Score>=50` עם fallback
ל-status הישן. tier מחושב בזיכרון מ-Score (אותם ספים כמו
`lead_capture._score_inbound_message`) — לא נקרא משדה Airtable, כי
`LeadFields.TIER` לא קיים בסכמת הפרודקשן (ראה Known Issues).
**קבצים:** daily_digest.py בלבד.

### N06 — Ventures Screen (TMA) ✅ מיושם
**תלוי ב:** N05 (Daily Digest שדרוג).
**מה:** מסך TMA חדש — 🔭 Ventures. חילוץ Strategic Pipeline מ-OCC + 
חיבור לטבלת Ventures הקיימת ב-Airtable.

**החלטה ארכיטקטונית (17/06/2026 — סופית):**
- Ventures = טבלה נפרדת (קיימת: tblsXFq5AwxUkdAJ7)
- לא הרחבת Deals.Status (גישה ישנה מ-13/06 — בוטלה)
- Deals = כסף שכבר על השולחן
- Ventures = האם בכלל כדאי לפתוח שולחן (לפני ליד, לפני עסקה)

**Airtable — כבר מוכן לחלוטין:**
- טבלת Ventures קיימת ומחוברת ל: Profile, Contacts, Deals, 
  Business Memory, Interaction Log
- שדות מרכזיים: Venture Name, Stage, Domain, Conviction, 
  Estimated Potential (NIS), Target Decision Date, Decision Log,
  Next Action, Linked Contacts, Interaction Log, Business Memory,
  Converted To Deal (multipleRecordLinks), Owner, Created At

**שלבי ה-Venture (דומיין-אגנוסטי):**
Research → Supplier/Source → Due Diligence → Smoke Test → GO/NO-GO → [Convert]

**קבצים לכתוב:**
- `src/screens/Ventures.tsx` (חדש)
- `tma_api.py` — endpoints: GET /api/ventures, GET /api/ventures/<id>,
  POST /api/ventures, PATCH /api/ventures/<id>
- `airtable_schema.py` — הוסף Tables.VENTURES = "Ventures"
- `_TMA_WRITE_ALLOWED_TABLES` — הוסף "Ventures"

**קבצים לשנות:**
- `OwnerControlCenter.tsx` — חלץ את Strategic Pipeline לקומפוננטה
  נפרדת; ה-OCC יציג רק summary (count by stage), קישור ל-Ventures

**מה לא לגעת בו:**
- Approval Gate — כל PATCH/POST עובר דרכו כרגיל
- Lead Capture, Scoring, Routing — לא נוגעים

**UX — מסך Ventures:**
```
┌─────────────────────────────────┐
│ 🔭 Ventures                     │
│ [Research] [DD] [Smoke] [GO/NO] │ ← פילטר לפי Stage
├─────────────────────────────────┤
│ 🏗️ ייבוא ריהוט עץ              │
│ Stage: Due Diligence            │
│ Conviction: גבוה                │
│ ₪ 2.4M פוטנציאל | 30/07 deadline│
│ Next: פגישה עם עמיל מכס        │
├─────────────────────────────────┤
│ 🏠 פרויקט יבניאל 2              │
│ Stage: Smoke Test               │
│ ...                             │
├─────────────────────────────────┤
│ [+ Venture חדש]                 │
└─────────────────────────────────┘
```

**כלל ברזל לפי ROADMAP #6:** N06 = קובץ אחד ראשי (Ventures.tsx) + 
endpoints ב-tma_api.py + שורה ב-airtable_schema.py. לא יותר.

**הערות מימוש (סטייה מהתכנון המקורי, מתועדת):**
- `Ventures.tsx` נוצר ב-`tma-frontend/src/components/` ולא ב-`src/screens/` —
  בקונבנציה הקיימת ברפו אין תיקיית `screens/` כלל; כל מסכי ה-TMA חיים שטוח
  ב-`components/`. נשמרה הקונבנציה הקיימת על פני הנתיב התיאורטי במסמך.
- כתיבות (POST/PATCH) הן ישירות ל-Owner בלבד, ללא Approval Gate — כמו
  Assets (`update_asset`), לא כמו ה-flow המתואר ב"מה לא לגעת בו". הוחלט
  כי Venture הוא כלי אסטרטגי owner-only (זהה ל-OCC) ולא דורש תור אישורים,
  ולכן `_TMA_WRITE_ALLOWED_TABLES` לא עודכן (לא בשימוש ע"י venture writes).
- `strategic_pipeline` ב-OCC שונה משלוש-דליים (`new_opportunities`/
  `in_evaluation`/`pending_decision`) לפורמט `{stage_counts, total, active}` —
  count-by-stage אמיתי לפי 8 השלבים בטבלת Ventures, כפי שהמסמך דרש.

### N07 — Schema Governance script ✅ הושלם (PR #101, `e465eff`)
**מה:** `tools/schema_governance.py` — סקריפט standalone שמשווה live Airtable
schema (Metadata API, `GET /meta/bases/{baseId}/tables`) מול `airtable_schema.py`
(import, לא parse), בעזרת `TABLE_CLASS_MAP`/`_class_values` הקיימים מ-`schema_audit.py`.
מזהה: שדה בקוד שחסר ב-live (התאמה whitespace-tolerant) → ERROR; שדה ב-live
שלא בקוד → WARNING; trailing/leading spaces בשמות שדות → WARNING (ממוזג עם
ה-whitespace-tolerant match, לא משוכפל); trailing/leading spaces ב-select
options → WARNING; שינוי סוג שדה → ERROR (מול ריצה קודמת שנשמרה ב-
`schema_drift_report.json`, כי `airtable_schema.py` לא מכיל מטא-דאטה של סוגים).
מדפיס דוח עברית ל-console, exit code 1 אם יש ERROR. READ ONLY לחלוטין — אפס
כתיבה ל-Airtable, לא נוגע ב-`schema_cache.json`. self-test (`--self-test`,
ללא רשת) כלול בקובץ.
**מניע:** BUG-008 (`Leads."Business Outcome"` trailing space) התגלה
ad-hoc תוך כדי חקירת באג, לא דרך audit שיטתי — ראו `AI_CONTEXT.md` §8.
**מצב נוכחי:** קוד הושלם ומוזג ל-main, עדיין לא רץ ב-CI (אין CI בריפו —
ראו N08 למטה) — הרצה היא manual לעת עתה (ראו `RELEASE_CHECKLIST.md`).

### N08 — CI/CD GitHub Actions ✅ הושלם (PR #103, `abf4835`)
**מה:** `.github/workflows/ci.yml` — מריץ `smoke_tests.py`/`test_integration.py` +
`npm run build` (frontend, skip חינני אם `tma-frontend/package.json` חסר) על כל PR.
Secrets נכונים (`TELEGRAM_TOKEN` וכו') ממופים מ-GitHub secrets.
**מצב נוכחי:** ממוזג ל-main, פעיל על כל PR.

### N09 — Monitoring / Alerting ✅ הושלם (PR #104, `4ac6d24`)
**מה:** `core/error_reporter.py` — `report_error(error, context, level)` שולח
התראת Telegram על שגיאות פרודקשן בלבד (`RENDER=="true"` + `ERROR_REPORTING` flag),
rate-limited (10/שעה), בלי payload/תוכן הודעות/מידע לקוח (context = שם פונקציה בלבד,
traceback גולמי). מחובר ב-`app.py` ב-3 נקודות: `_handle_approval_callback`,
`webhook_telegram`, `webhook_whatsapp`.
**מצב נוכחי:** ממוזג ל-main, פעיל בפרודקשן (תלוי ב-`ERROR_REPORTING`/`ELIYAHU_CHAT_ID`).

### N10 — Rollback אוטומטי 🔲 PLANNED
**תלוי ב:** N08 (CI/CD — הושלם).
**מה:** rollback אוטומטי ל-commit יציב אחרון כש-health check/monitoring
מזהה כשל אחרי deploy.
**עד שמיושם:** manual gate בלבד (ראו `RELEASE_CHECKLIST.md`).

### N11 — Screen Filter Gateway: Finance Pulse wiring ✅ הושלם (PR #77, `f7d7e4f`/`daab73e`)
**תלוי ב:** C53 (Screen Filter Gateway — מיושם, PR #75).
**מה:** `GET /api/finance/pulse` מחובר ל-`SCREEN_CONFIGS["finance_pulse"]` +
`_build_formula()` עם `entity="Payment"` (`status_field=PaymentFields.STATUS`),
תומך ב-`?view=active|overdue|all` ומחזיר `available_views`. סיווג overdue/pending/
income לפי תאריך מתבצע ב-Python על תוצאת ה-formula (status-based, לא raw_formula
דינמי לתאריך — נמצא מספיק כש-`exclude_statuses`/`include_statuses` עושים את הסינון
העיקרי והקטגוריזציה לפי תאריך נשארת בקוד האפליקציה, לא ב-Airtable formula).
אפס שינוי ל-`_build_formula()` עצמה.
**עתידי (multi-tenant):** override per-tenant מ-`ProjectsHub.screen_overrides`
(JSON, נדרש שדה חדש בסכמה) — ראו הערה ב-`tma_api.py` ליד `SCREEN_CONFIGS`.
**מצב נוכחי:** ממוזג ל-main (`tma_api.py`/`airtable_schema.py`), לפני הסשן הנוכחי —
תועד כ-PLANNED ב-ROADMAP בטעות; תוקן כאן.

### N12 — Daily Git Audit scheduler wiring ✅ הושלם, דגל כבוי (PR #108, `c26c5e1`)
**מה:** `daily_git_audit.py` (קיים מ-GOV-02) חוּבר ל-`scheduler.py` (`_job_daily_git_audit`,
`schedule.every().day.at(git_audit_time)`, `GIT_AUDIT_TIME` env var, ברירת מחדל `06:45`
כדי לא להתנגש עם digest ה-game ב-07:00/digest רגיל ב-07:30). נוספו ל-`daily_git_audit.py`
עצמו: `check_unmerged_vs_roadmap()` (משווה ענפים לא ממוזגים מול טענות ✅/DONE ב-ROADMAP.md —
**ROADMAP.md ראשון בעדיפות**, לא BOSS_CURRENT_STATE.md, כדי לא לסתור את הכרזת הקובץ
עצמו כ"מקור האמת היחיד"), `check_duplicate_schemas()` (שמות tool כפולים ב-
`tools/schemas.py`/`tool_registry.py`), `check_recent_commits()`, `check_cors_env_drift()`
(`tma_api.py` מול `.env.example`).
**Feature Flag:** `GIT_AUDIT_SCHEDULER` — כבוי כברירת מחדל (נשאר manual-only, תואם
ל-docstring הקיים של `daily_git_audit.py`).
**מניע:** נמצא תוך כדי ניקוי ענפי `claude/*` ישנים — `claude/lucid-franklin-0os9ma`
ו-`claude/tender-hypatia-h5n0d3` הכילו את המימוש הזה אבל לא מוזגו מעולם; חולץ ותוקן
(ה-bug ב-precedence) לפני שהענפים נמחקו.
**מצב נוכחי:** ממוזג ל-main, דגל כבוי — אין שינוי התנהגות בפרודקשן.

### N13 — Decision Hub (Stage 0 / 0.5 / 0.6) ✅ הושלם, דגל כבוי (PR #147, `4ac2a05`/`e0f0111`)
**מה:** ליבת "החלטה" domain-agnostic (`Decision`, `decision_pipeline.py`) עם Inbox raw-first
(Stage 0), File/Voice Precedence Routing (Stage 0.5) ו-File Context Reference — קישור
"זה הנספח" לקובץ האחרון שהועלה (Stage 0.6). מימוש ראשון של MODULE_RULES חוקים 7-10 בקוד
חי (`decision_ports.py`/`DecisionPorts`, `GateResult`/`_GATE_REGISTRY`).
**קבצים:** `cmd_decision.py` (`decision_context_active`, `route_file_to_decision_inbox`,
`_suggest_decision_link`, `is_attachment_reference`, `handle_attachment_reference`),
`decision_pipeline.py`, `decision_ports.py`, `app.py` (`_handle_telegram_media` precedence
gate + Drive-upload `set_last_file` hook + `_webhook_telegram_impl` "זה הנספח" gate),
`session_store.py` (`FileUploadResult`, `set_last_file`/`get_last_file`), `airtable_schema.py`
(Decision Hub tables/fields).
**Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן.
**מצב נוכחי:** Stage 0/0.5/0.6 ממוזגים ל-`main` (PR #147). **Stage 1 (Trust Layer) — מוזג ל-`main`
(PR #151, commit `73f6fe8`), עדיין לא מאומת בפרודקשן** — לפי `SPEC_Decision_Hub_Stage1_Trust_Rev2.md`
(אישור אליהו: "ניתן ליישם ספק"). Stage 2-4 (AI Conflict Detection/Readiness Engine/Attention Engine) —
○ לא התחילו. ראו `archive/BOSS_MASTER_PLAN_One_Road.md` לעקרון "כביש אחד, יציאות רבות"
(ARCHIVE — לא מקור אמת, ראו הערת מקור בראש אותו קובץ).
**Verification ראיה:** `py_compile` נקי על שלושת הקבצים; `session_store.py` self-test
18/20 עברו (2 כשלים קיימים מראש, mock-import-path בלתי תלוי בשינוי זה); אין אימות
בפרודקשן עדיין — דגל כבוי.

**Stage 1 — Trust Layer (Rev 2):** `gate_trust` מחושב לפי `AUTHORITY_SCORE`×`MEDIUM_SCORE`
(`compute_trust`/`score_to_level`), `extract_claim_topic` אוטומטי (4 מקורות + ידני כ-fallback,
מורחב ל-(topic, source, confidence) סביב 2 השדות שאליהו הוסיף מעבר לספק — `Claim Topic Source`/
`Claim Topic Confidence`), `maybe_supersede` בטוח (אותו Claim Topic בלבד + Trust גבוה יותר בלבד).
**9 סטיות מהטקסט המילולי של הספק, מתועדות (לא הוסתרו):**
1. `VerifierPort.verify()` מחזיר `dict` לא object — שונה ל-`{"status": ..., "reason": ...}`.
2. `decision` שמועבר ל-`run_pipeline` הוא `decision["fields"]` בלבד (אין `"id"`) — `maybe_supersede`
   קורא את ה-ID מ-`event["_decision_id"]` שמוזרק ב-`cmd_decision.py` לפני הקריאה, לא מ-`decision["id"]`.
3. Tags: "potential_conflict"/"low_confidence"/"pressure_high_risk" (אנגלית, בספק) לא קיימים
   כאופציות Multi-Select חיות — נעשה שימוש ב-`DecisionEventTag.CONFLICT`("קונפליקט") הקיים,
   ונוספו 2 קבועים עבריים חדשים (`LOW_CONFIDENCE`="אמינות_נמוכה", `PRESSURE_HIGH_RISK`="לחץ_סיכון_גבוה")
   **שלא אומתו מול Airtable חי** — ייתכן שיידרש ליצור אותם כאופציות לפני כתיבה ראשונה בפרודקשן.
4. `_has_keyword_conflict()` — הספק מפנה לפונקציה זו (§5 שלב ו') אך לא הגדיר את גוף הלוגיקה כלל.
   מומשה כ-stub שמחזיר `False` — נתיב ה-"potential_conflict"/`DecisionEventTag.CONFLICT` לא ייושם
   בפועל עד שתוגדר לוגיקת ה-keyword-conflict (Stage 1.x/Stage 2).
5. `DecisionSourceReliability` היו חסרים 4 מתוך 10 מפתחות `AUTHORITY_SCORE` — נוספו
   `DOCUMENT`/`MANUAL`/`EMPLOYEE`/`UNKNOWN`.
6. `event["Channel"]`/`event["Source Reliability"]` לא היו מועברים ל-`gate_trust` כלל לפני התיקון —
   Channel תוקן ב-2 נקודות הקריאה ב-`cmd_decision.py` (`_handle_update_step`/`_link_inbox_to_decision`).
   **Source Reliability עדיין לא מוזן ע"י שום UI קיים** — `gate_trust` ייפול תמיד ל-default "ידני"
   (ציון authority=55) עד שתיווסף שאלת "מי אמר/כמה אמין" לדיאלוג `/decision update` — מחוץ לטקסט
   המילולי של הספק, לא תוקן בסבב הזה.
7. פלטי ה-Trust Layer לא נכתבו ל-Airtable כלל — `_create_decision_event`/`event_fields`
   (`_link_inbox_to_decision`) הורחבו עם `_add_trust_fields()` חדשה (Trust Level/Confidence/Tags/
   Claim Topic+Source+Confidence/Source Reliability/Supersedes).
8. `run_pipeline()` היה מזניח את `user_flag` של שערים שעברו (fabricate `GateResult` חדש) —
   נוסף `collected_flag` שעוקב ומועבר ל-`GateResult` הסינתטי בסוף, כדי שההודעה "לא זיהיתי נושא"
   (T2/T3) תוצג בפועל.
9. `_format_pipeline_outcome` לא טיפל ב-`halted_at == "trust"` ולא בדק `result.user_flag` בנתיב
   ההצלחה — נוסף branch מפורש + הצמדת `user_flag` להודעת ההצלחה.

**§10 פריט 11 (אימות פרודקשן — T0 אמיתי → user_flag בטלגרם) נשאר פתוח עד פריסה.**
**קבצים שנוספו/שונו:** `airtable_schema.py` (קבועים), `decision_ports.py` (verifier stub),
`decision_pipeline.py` (Trust Model מלא), `cmd_decision.py` (חיווט), `test_decision_trust.py`
(33 self-tests, כולם עוברים).

### F17 — Decision Hub Stage 2: Smart Trust Layer (PR #157, מוזג ל-`main`, commit `9252b1e`/merge `78f9bae`)
**מה:** שכבת ביטחון על גבי Stage 1 — מסתכלת על ה-Decision כולו (לא Event בודד): האם
האירועים התומכים מסכימים, מה חסר, כמה ביטחון לפני חתימה. 4 יכולות: (1) AI Conflict
Detection — Lazy+Cached (תנאי אישור אליהו, לא Eager): רץ רק בפתיחת/Refresh של Decision,
לא ב-ingest, מוגבל ל-Claim Topic זהה + Trust>=T1, dedup לפי `event_pair_hash`, מוגבל
ל-`_MAX_AI_COMPARISONS_PER_RUN=5` קריאות Claude חדשות לריצה (זוגות ב-cache לא נספרים).
(2) Evidence Graph — `evidence_ids`/`evidence_summary` על ה-Decision. (3) Decision
Confidence Score — ממוצע משוקלל של Trust מינוס 0.15×קונפליקטים, clamped [0,1]. (4)
Missing Evidence Detector — בדיקת מילת-מפתח (לא LLM) מול תבנית `REQUIRED_EVIDENCE` לפי
Domain.
**זה ממלא בפועל** את ה-stub `_has_keyword_conflict()` שStage 1 השאיר פתוח (ראו N13 סטייה
4 למעלה) — לא כתחליף, אלא כאיתות AI מקביל (`DecisionEventTag.CONFLICT`).
**3 סטיות מהטקסט המילולי של הספק, מתועדות:**
1. הספק כתב `core/decision_confidence.py` — נכתב ב-root, לצד `decision_pipeline.py`/
   `decision_ports.py`/`cmd_decision.py` (שאר מודולי Decision Hub), לעקביות ארכיטקטונית.
2. הספק הגדיר `REQUIRED_EVIDENCE` לפי "decision_type" — קונספט שלא קיים בסכמה (ל-Decisions
   יש רק Domain). נמופה על `DecisionDomain` הקיים (`REAL_ESTATE`/`IMPORT`/`PARTNERSHIP`/
   `RECRUITMENT`/`GENERAL`); `IMPORT` ו-`PARTNERSHIP` משתפים את אותה רשימת ראיות (אין
   ל-spec רשימה ספציפית יותר לאף אחד מהם).
3. הספק הניח `get_decision()` — פונקציה כזו לא קיימת. החיווט נעשה ב-`_format_decision_card()`
   (הנקודה הקיימת היחידה שמרכיבה כרטיס Decision מלא, נקראת מ-`/decision status`, כבר
   מאחורי `FEATURE_DECISION_HUB`).
**שדות Airtable חדשים (לא נוצרו עדיין ביד):** `Evidence Ids` (Long text JSON), `Evidence
Summary` (Long text), `Confidence Score` (Number 0.0-1.0), `Missing Evidence` (Long text
JSON) — `airtable_patch()` משמיט שדות לא-מוכרים בשקט (`schema_cache.json` עדיין לא מכיר
אותם), כך שתצוגת הטלגרם תקינה בלי תלות בהשלמת השדות; הפרסיסטנס הוא best-effort עד שהם
ייוצרו ו-`schema_audit.py` ירוץ מחדש.
**Verification ראיה:** `py_compile` נקי על `decision_confidence.py`/`cmd_decision.py`/
`airtable_schema.py`/`app.py`; `test_decision_confidence.py` 25/25 עוברים (`detect_conflict_ai`
מ-mock — אפס קריאות רשת); `test_decision_trust.py` 33/33 ללא רגרסיה; `smoke_tests.py` —
אותם 2 כשלים קיימים מראש (`flask`/`httpx` חסרים בסביבה), אין כשלים חדשים.
**קבצים שנוספו/שונו:** `decision_confidence.py` (חדש), `cmd_decision.py`
(`_format_confidence_block`/`_persist_confidence`/`_list_decision_events` + תיקון רגרסיה
ב-`_latest_event` inline שבדק `not events` הפוך), `airtable_schema.py` (4 קבועי שדה חדשים),
`test_decision_confidence.py` (חדש, 25 self-tests).
**מצב נוכחי:** מוזג ל-`main` (PR #157, commit `9252b1e`, merge commit `78f9bae`) —
אומת עצמאית דרך `mcp__github__pull_request_read` (`merged:true`) + `git merge-base
--is-ancestor`. **פריסה ל-Render לא אומתה** (אין גישת dashboard/egress מה-sandbox), דגל
`FEATURE_DECISION_HUB` כבוי כברירת מחדל. Stage 3-4 (Readiness Engine/Attention Engine) —
לא התחילו.

**C60 — Tool Context Awareness (`claude/new-session-be1ckb`, 🟡 CODE DONE, לא ממוזג):**
לפי `SPEC_C59_Tool_Context_Awareness.md` (הועלה ע"י הבעלים בלי טקסט מלווה; אישור דרך
`AskUserQuestion`: "Yes, implement now"). ⚠️ **ID collision מתועד** — הספק תייג עצמו "C59",
מתנגש עם C59 הקיים (Trust Layer שלעיל, PR #151) — תויג מחדש **C60** בתיעוד בלבד; כותרת
הספק וכל מחרוזות הקוד נשארו ללא שינוי (אותו דגם כמו C54→C57). פותר עיוורון כלים בין סבבי
agent: `last_tool_result` נשמר ב-session אחרי כל tool dispatch אמיתי (`session_store.py`:
`set_last_tool_result`/`get_last_tool_result`, מסונכרן ל-`State JSON` כמו `last_uploaded_file`
מ-C58), מוזרק ל-system prompt כ-"🔧 הקשר כלים" (`_build_tool_context()`, TTL 5 דקות),
ו-`resolve_context_pronouns()` מחליף כינויי הצבעה עבריים ("זה"/"הנספח"/"הקודם"/"ההוא"/"אותו")
בהתייחסות מפורשת לפני ה-Router (שלב חדש "2.6" ב-`run_agent()`).
**3 סטיות מהטקסט המילולי של הספק, מתועדות:**
1. הספק מניח חוזה `tool_result` עם `id`/`record_id`/`url`/`drive_url` — החוזה האמיתי בקוד
   (C53-A, `test_c53a.py`) הוא `{ok, tool, external_id, evidence, user_message}` בלבד. תוקן:
   `record_id` ← `external_id`, `url` ← `evidence.get("htmlLink") or evidence.get("url")`.
2. `_seconds_ago()` מוזכר ב-§5 בלי הגדרה (כמו `_has_keyword_conflict` ב-C59) — מומש inline
   כ-diff בין `datetime.now(timezone.utc)` ל-`datetime.fromisoformat(timestamp)`.
3. §6 "Table Registry fix" — אומת מראש ש-4 קבועי Decision Tables כבר קיימים (מ-C59) — no-op.
**Verification ראיה:** `py_compile` נקי על `app.py`/`session_store.py`/`airtable_schema.py`;
`session_store.py` self-test 40/40 עברו (4 חדשים ל-C60); `test_c53a.py` 50/50; `test_integration.py`
4/4; §9 greps כולם תקינים. §10 פריט 7 בספק (בדיקת לייב) פתוח עד מיזוג+פריסה.
**קבצים שנוספו/שונו:** `session_store.py` (`last_tool_result` + 2 מתודות + 4 self-tests),
`app.py` (`_capture_last_tool_result`/`_build_tool_context`/`resolve_context_pronouns`/`CONTEXT_PRONOUNS`
+ 3 נקודות חיווט).

### F05a — Meta WhatsApp Phase 1 (Inbound, ללא תעבורת פרודקשן)
**מה:** `/webhooks/meta/whatsapp` (GET verify + POST inbound) — נתיב נפרד מ-Twilio.
מנרמל payload → אותו pipeline של `run_agent()` כמו Twilio. Outbound נשאר stub כנה.
**קבצים:** `app.py` (2 helpers + 1 route, additive בלבד).
**guard:** `EMERGENCY_STOP_WHATSAPP` נבדק לפני כל processing.
**env:** `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`.
**סטטוס:** test-only — אין תעבורת לידים אמיתית עד F05 (חיבור Meta מלא).

---

## 📌 Business Lifecycle Gap Analysis (נוסף 2026-06-13)

ה-CRM/Workflow הקיים מכסה כ-20-25% ממחזור החיים העסקי המלא.
מיפוי 8 השלבים:

| שלב | תיאור | סטטוס |
|---|---|---|
| 1. Opportunity Pipeline | איתור הזדמנויות (Ventures) | ✅ טבלה קיימת → N06 TMA screen |
| 2. Deal Evaluation | בדיקת כדאיות (שמאי/עו"ד/רו"ח/מיסוי/סיכונים) | ❌ לא קיים → **Future** |
| 3. Demand Research | מחקר שוק (לקוחות/מתחרים/תמחור) | ❌ לא קיים → **Future** |
| 4. Deal Structuring | בניית עסקה (מימון/שותפים/מבנה רווחים) | ❌ לא קיים → **Future** |
| 5. Marketing & Sales | קמפיינים/לידים/פולואפים | ✅ הכי מפותח - הליבה הקיימת |
| 6. Execution | חוזים/גבייה/תשלומים/מסירה | 🟡 חלקי (Payments table קיים) |
| 7. Profit Distribution | חלוקת רווחים לשותפים/משקיעים | ❌ לא קיים → **Future** |
| 8. Capital Management | מעקב הון - כמה נשאר/מושקע/חוזר/יוצא | ❌ לא קיים → **Future** |

**החלטה (2026-06-13)**: לא בונים שלבים חדשים כרגע. ממשיכים ברודמאפ הקיים
(Cost Watchdog → Meta WhatsApp → N04/N05 → Digest). שלבים 1-4, 7-8
מתועדים כ-Future items, יישקלו לאחר השלמת השכבה התפעולית.

**עקרון מנחה**: המערכת היום היא "Operating Layer" (תפעול). שכבת
"Business Management" (ניהול העסק - הזדמנויות, כדאיות, הון) היא
השכבה הבאה, אחרי שהתפעול מבוסס לחלוטין.

---

## 📌 CORE_05 Cost Watchdog — Spec v2 (גנרי, multi-source)

### תיקון תיעוד חשוב
`interaction_engine.py` (שהוזכר כקורא Sonnet כל 15 דקות) **לא קיים בקודבייס**.
הארכיטקטורה התפתחה ל-`context.py` שכולל `_select_model()` חכם:
- Owner + הודעה מתחילה ב-`#` → Sonnet (מצב מחקר)
- כל שאר המקרים → Haiku

**נקודת הדליפה האמיתית**: `creative_generator.py` קרא ל-Sonnet תמיד — **תוקן** (Haiku עכשיו).

### מרכיבי הפתרון (מיושם 2026-06-13)
- `core/cost_watchdog.py` (חדש) — `log_usage(source_type, units, meta, user_id)` → `logs/usage.jsonl`
- `creative_generator.py` — עבר ל-Haiku + log_usage אחרי כל קריאה
- `app.py` — `log_usage()` אחרי כל `client.messages.create` (source_type לפי model name)
- `scheduler.py` — `_job_daily_usage_report` כל יום 08:00 → aggregation + Airtable + alert
- `airtable_schema.py` → `Tables.AI_USAGE_DAILY = "AI_Usage_Daily"` (טבלה חדשה, 1 שורה/יום)
- Feature flag: `COST_WATCHDOG_ENABLED=true` (default on)
- ספים: `SONNET_DAILY_LIMIT=50` (configurable), `WHATSAPP_CONV_DAILY_LIMIT` (להגדיר עם Meta)

### עלויות נסתרות (לא בקוד — מעקב ידני)
- Meta WhatsApp Cloud API: per-conversation pricing (utility/marketing/auth) — לבדוק לפני חיבור
- Render: per-plan-tier (compute/RAM), לא per-call — רלוונטי לסקלביליות 1000 משתמשים
- Airtable: rate limit 5 req/sec/base — סיכון 429 errors בעומס גבוה

---

## F — עתיד (אין תאריך, יש spec)

### F01 — Lead Recovery
מה: לידים שדעכו → זיהוי אוטומטי → הצעת פנייה מחדש לowner.
תלוי ב: N04 Followup.

### F02 — Learning Engine
מה: מעל lead_events (C12). לומד מדפוסים, התנגדויות, מה סגר עסקאות.
תלוי ב: N04, כמה חודשי דאטה.

### F03 — Revenue Attribution
תלוי ב: F02.

### F04 — KPI Engine
תלוי ב: C21 Daily Digest + F03.

### F05 — WhatsApp Production (Meta Cloud API)
חסם: אישור Meta Cloud API. כרגע honest stub.

### F06 — Email Channel (Inbound)
תלוי ב: Google Tools הפשרה.

**תלות דגלים (אומת בקוד, 19/06/2026):** F06 **לא** תלוי רק ב-`EMAIL_INBOUND`. `email_inbound.run_email_poll()` נכנס ל-loop רק אם `EMAIL_INBOUND=true`, אבל מעביר כל מייל ל-`inbound_handler.handle_inbound()` (`inbound_handler.py:155`) שעושה `if not is_enabled("LEAD_CAPTURE"): return` — early-return בלי ליצור/לעדכן שום רשומת Lead. כלומר אם `EMAIL_INBOUND=true` ו-`LEAD_CAPTURE=false`: המיילים *נסרקים* (ונספרים כ-`routed` ב-`PollResult`, מטעה — אין כתיבה בפועל ל-Airtable), אבל שום ליד לא נוצר/מתעדכן בשקט. **שני הדגלים חייבים להיות `true` יחד כדי ש-F06 יעבוד בפועל.** שניהם כבויים כיום ברירת מחדל — `EMAIL_INBOUND` נשאר `false` עד שתתקבל החלטה מודעת על השלכת הפעלת `LEAD_CAPTURE` (שמשפיעה גם על WhatsApp lead capture, לא רק email).

### F07 — Voice / IVR
מודל עסקי: White-Glove.

### F08 — SaaS Multi-Tenant
תלוי ב: הכל לפניו.

### F09 — Lead Qualifier Wire-up
מה: חיבור lead_qualifier.handle_lead_message() לתוך run_agent — state machine שאלון לכל ליד WhatsApp.
מצב: **בנוי ובדוק** — lead_qualifier.py קיים ומלא. לא מחובר לפרודקשן.
תלוי ב: N04 (קודם צריך scoring + followup פשוטים). אחר כך להחליט: לחבר או להחליף ב-Claude-native scoring.
קבצים: lead_qualifier.py (קיים), app.py (hook).

### F10 — Lead Memory Wire-up
מה: חיבור lead_memory.update() לתוך lead_capture — זיכרון ארוך-טווח per lead.
מצב: **בנוי ובדוק** — core/lead_memory.py קיים כולל debounce, flush, TTL, feature flag.
תלוי ב: N02 (scoring קודם — אין טעם לזכור ליד ללא ציון).
קבצים: core/lead_memory.py (קיים), lead_capture.py.

### F11 — Followup Engine Full Activation
מה: הפעלת core/followup_engine.py המלא — determine_followup_needed, יצירת טיוטות, שליחה לאישור.
מצב: **תשתית קיימת** — followup_engine.py בנוי. scheduler job קיים (כבוי).
תלוי ב: N04 (N04 הוא גרסת MVP — F11 הוא הגרסה המלאה עם טיוטות וזיכרון).
קבצים: core/followup_engine.py (קיים), scheduler.py.

### F14 — Contact Gate: find_or_create_contact()
מה: פונקציה יחידה ב-`crm.py` — בודקת קיום איש קשר לפי טלפון לפני כל כתיבה.
סיבה: התכונה "חפש לפי טלפון" נדרשת בשלושה מקומות: import ידני, `crm_add_contact`, המרת ליד→contact (עתידי). ללא gate — כפילויות בלתי נמנעות.
ממשק: `find_or_create_contact(phone, name, **fields) → (record_id, created: bool)`
Piggyback trigger: כשמחברים המרת ליד → contact (אחרי N04).
קבצים: crm.py

### F15 — crm.py → airtable_gateway (write path migration)
מה: החלפת `_post` / `_patch` הישירים ב-`crm.py` בקריאות ל-`airtable_gateway.upsert()`.
סיבה: `crm.py` עוקף את כלל הברזל — "ALL writes go through airtable_gateway.py". drift מודע.
Piggyback trigger: כשנוגעים ב-`crm.py` לסיבה אחרת (F14 או lead→contact).
קבצים: crm.py, airtable_gateway.py

### F12 — Model Provider Adapter
מה: abstraction layer אחיד ל-LLM providers — interface יחיד `generate(prompt, context, model_tier) → text` שמאחד Anthropic, OpenAI, ו-providers עתידיים.
מטרה: שינוי provider = שינוי config בלבד, לא קוד. כולל sanitization עקבי (A32) בכל provider.
פרטים:
- interface: `LLMProvider.generate(prompt, context, model_tier) → text`
- כל implementation עוטף API ספציפי + sanitize_agent_response
- selection: env config / cost watchdog / health-based fallback אוטומטי
- כל domain יכול לבחור model tier שונה (domain skill documents)
מצב: **לא קיים** — Fix #1/#3 + `FEATURE_LLM_FALLBACK` מטפלים בעכשיו. זהו ה-design הנכון לטווח ארוך.
תלוי ב: domain skill documents (F-future), `FEATURE_LLM_FALLBACK` יציב בפרודקשן.
קבצים לעתיד: `providers/` (חדש), `llm_fallback.py` (migrate/replace).

### F13 — TenantConfig + Provider Interfaces
⚠️ **STATUS: DEAD CODE — DO NOT WIRE**
- קיים: `core/tenant_config.py` + `providers/` (5 קבצים)
- לא מחובר: אפס imports מקוד חי
- כפילות: `TenantConfig` קיים גם ב-`tenant_provisioner.py`
- הכרעה נדרשת: F12 vs F13 overlap ב-`providers/` — אין לחבר לפני הכרעה
- Piggyback Trigger: sprint multi-tenancy בלבד

מה: שכבת תשתית SaaS — `TenantConfig` (dataclass: storage/LLM/memory/channel/features/allowed_tools per tenant) + `Protocol`-based interfaces (`StorageProvider`, `LLMProvider`, `ChannelAdapter`) + שלושה shims שעוטפים את האינטגרציות הקיימות (`AirtableStorageProvider`, `AnthropicLLMProvider`, `TwilioChannelAdapter`) בלי לשנות אותן.
scope: **infrastructure only — אפס שינוי runtime behavior** בשלב זה. שלב 1 = hardcoded default tenant (`boss_hq`) + env override; `get_tenant_config()` תמיד מחזיר singleton. שלב 3 (חלק מ-F08) = loader מטבלת Tenants ב-Airtable.
תלוי ב: C01 (Identity), W2 (`airtable_gateway`), C52 (COG / `core/output_gateway.py`).
חוסם: F08 (SaaS Multi-Tenant) — F08 לא יכול להיבנות בלי החוזה הזה קודם.
⚠️ **חפיפה עם F12** — שני הספקים מציעים `providers/` כתיקייה חדשה ל-LLM abstraction (F12: `LLMProvider.generate(prompt, context, model_tier)`; F13: `LLMProvider.generate(messages, system, model, max_tokens, tools)` + עוד שני providers ל-storage/channel). **לא להתחיל מימוש של אף אחד מהשניים לפני שמחליטים אם F13 סופג את F12 או שהם משלימים זה את זה** — אחרת ניצור שתי תיקיות `providers/` עם interfaces סותרים, כמו התנגשות ה-ID של C20/C21 שתועדה ב-`AI_CONTEXT.md`.
מצב: **CODE COMPLETE, לא מחובר ל-pipeline** — כל 6 הקבצים קיימים (PR #87, מוזג ל-`main`). אפס import מקוד קיים אליהם — `app.py`/`tools/dispatcher.py` לא משתמשים בהם, `get_tenant_config()` תמיד מחזיר את `boss_hq` הקשיח. ⚠️ ה-spec המקורי הניח חתימות פונקציות שלא קיימות בקוד (`gateway_add`/`gateway_update`/`gateway_delete`, `send_via_cog`, `airtable_get(max_records=...)` כ-`list[dict]`, `_validate_twilio_signature(headers, body)`) — תוקן מול הקוד האמיתי, מתועד ב-`BUG_AUDIT_LOG.md` כ-SPEC-001. הכרעת F12-מול-F13 (השורה הקודמת) **עדיין לא בוצעה** — הקבצים קיימים אך לא נבחרו כפתרון הסופי.
קבצים שנוצרו: `core/tenant_config.py`, `providers/__init__.py`, `providers/interfaces.py`, `providers/airtable_shim.py`, `providers/anthropic_shim.py`, `providers/twilio_shim.py`.

### F16 — Media Layer (voice notes + file uploads → Drive + Airtable) — ✅ הושלם
מה: שכבת מדיה מלאה — קליטת קובץ/הקלטה מ-Telegram או TMA, העלאה ל-Google Drive, תמלול (STT), ושמירת metadata בטבלת Airtable "Media Files". מחולק לשבעה batches (א-ז).
⚠️ היסטוריית ID: הספק החיצוני קרא לפיצ'ר "F12" בהתחלה (תפוס — Model Provider Adapter, ראה מעלה) ואז "F09" (תפוס — Lead Qualifier Wire-up, ראה מעלה). הוקצה F16 כדי למנוע התנגשות, באותו דפוס שתועד עבור C20/C21 (`AI_CONTEXT.md`) ו-F14/F15 (מעלה).
מצב Batches:
- **Batch א — `voice_stt_adapter.py`** (PR #96, מוזג): STT provider = OpenAI Whisper (PRIMARY, חי — `OPENAI_API_KEY` קיים בסביבה). Groq רשום כ-stub מוער ("Phase 2") — לא מחובר ל-`transcribe()`. קודי שגיאה: `OVERSIZED`/`STT_FAILED` (אין `EMPTY_AUDIO` בספק הנוכחי). `_normalize_hebrew()` — הסרת ניקוד + כיווץ רווחים. **אומת מוזג ל-`main` — grep על `OVERSIZED`/`STT_FAILED` תואם.**
- **Batch ב — `drive_adapter.py`** (PR #97, מוזג): `upload_file(file_bytes, filename, mime_type, parent_folder_id)` — `parent_folder_id` חובה, אין default. Temp file נמחק תמיד ב-`finally`. `_safe_filename` מנקה רק תווים אסורים ל-Drive (עברית נתמכת native). `GOOGLE_DRIVE_FOLDER_ID` (BOSS root, מאומת) הוא ה-parent, לא תיקייה ליצירה. **אומת מוזג ל-`main` — grep על `parent_folder_id` בחתימת `upload_file`/`_upload_to_drive` תואם.**
- **Batch ג — `media_gateway.py`** (PR #97, מוזג): טבלה `"Media Files"` (לא "Assets" — collision עם נדל"ן), `MediaFileFields`, כתיבה דרך `tools/airtable_gateway.airtable_create` בלבד (אין `httpx` ישיר), `linked_lead_id` → `[record_id]` (array), `raw_transcript`+`normalized_transcript` שניהם נשמרים, `save_asset()` מחזיר `record_id: str | None`. הקובץ נמצא **תואם 100% לספק כבר מהבנייה המקורית — אפס שינויי קוד בסשן הזה**.
- **Batch ד — `media_handler.py`** (PR #98, מוזג, `8dd3bca`): כניסה יחידה `handle_voice_note()`/`handle_file_upload()`/`handle_tma_upload()` (שמות נשמרו כפי שהיו בקוד הקיים — לא שונו ל-`handle_telegram_media()` כפי שהוצע ב-spec החיצוני, ראה החלטת המשתמש בסשן). שכבות גודל: `normal` ≤10MB / `large` 10-50MB / `oversized` >50MB (reject מיידי, בלי upload). Idempotency: `source:file_id:user_id` → hash (16 תווים). Approval רק ל-Business Memory write (לא לשמירת ה-asset עצמו — Drive+Airtable נשמרים סינכרונית, ללא approval). PR #98 תיקן שני באגים אמיתיים שהיו קיימים בקוד מאז `ee4d2ed` (לפני כל מאמץ הבאצ'ים): (1) `upload_file()` נקרא עם חתימה לא תקפה (`domain=domain` קיים שלא קיים בפונקציה האמיתית — `TypeError` מובטח עם כל flag דלוק); (2) כשל כתיבה ל-Airtable לאחר Drive upload מוצלח הוחזר כ-`ok=True` בשקט (קודי שגיאה חדשים: `DRIVE_FAILED`/`ASSET_SAVE_FAILED`).
- **Batch ה — `app.py` hooks**: ✅ מוזג. `_handle_telegram_media()` כבר היה מחובר ל-webhook (voice/photo/document) מאז `ee4d2ed`; PR #99 הוסיף `send_chat_action` לפני עיבוד (typing/upload_document) שהיה חסר.
- **Batch ו — `tma_api.py` endpoint**: ✅ מוזג. `POST /api/tma/upload` (multipart, `@require_tma_auth`) כבר היה מחובר ל-`handle_tma_upload()` מאז `ee4d2ed`, כולל `coming_soon` כש-`FEATURE_MEDIA_UPLOAD` כבוי; PR #99 הוסיף קליטת `linked_lead_id` מה-form ומעביר אותו ל-`handle_file_upload()`. `domain` נשאר נגזר מה-identity המאומת בלבד (לא משדה form של הלקוח) — tenant scope לא נקבע ע"י הלקוח.
- **Batch ז — `airtable_schema.py`**: ✅ קיים מהבנייה המקורית — `Tables.MEDIA_FILES = "Media Files"` ו-`MediaFileFields` (NAME/FILE_TYPE/MIME_TYPE/DRIVE_URL/DRIVE_FILE_ID/DOMAIN/SOURCE/SIZE_BYTES/CREATED_BY/TELEGRAM_FILE_ID/LINKED_LEAD/RAW_TRANSCRIPT/NORMALIZED_TRANSCRIPT) מכסים את כל מה ש-`media_gateway.py` כותב. `AssetsFields` (נדל"ן) לא נגע. ⚠️ הטבלה עצמה חייבת להיווצר ידנית ב-Airtable לפני הדלקת flag — הקוד לא יוצר טבלה.
תלוי ב: כלום (עומד בפני עצמו). דגלים `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` קיימים ב-`feature_flags.py`, **כבויים כברירת מחדל** (`is_enabled()` חוזר `False` ללא env var) — הקוד רץ במלואו אך אינו פעיל בפרודקשן עד הדלקה מפורשת.
קבצים: `voice_stt_adapter.py`, `drive_adapter.py`, `media_gateway.py`, `media_handler.py`, `app.py`, `tma_api.py`, `airtable_schema.py` — כולם מוזגים ל-`main`. בדיקות: `test_media_layer.py` (33/33).

---

## Known Issues / Tech Debt (מתועד, לא קריטי)

| פריט | תיאור | מתי לטפל |
|------|--------|----------|
| `_ALIAS_MAP` כפול | מיפוי English→Hebrew זהה קיים גם ב-`tools/dispatcher.py:43` וגם ב-`tools/airtable_tools.py:111`. סנכרוני כרגע, אבל עדכון ב-אחד לא יתפשט לשני — סיכון drift שקט. | בפעם הבאה שנוגעים באחד |
| `crm_mark_payment_paid` — approval חובה | כאשר כלי זה יוממש, **חייב** להירשם עם `requires_approval=True` לפי `SECURITY_CHECKLIST.md:62`. פעולות סימון תשלום דורשות Golden Path Approval Gate. | לפני מימוש הכלי |
| `lead_memory.py:155` — dead write | שדה `"updated_at"` נכתב ל-Leads אך אינו קיים בסכמת Airtable — הכתיבה נדחית בשקט ע"י gateway. | ניקוי בפגישת Tech Debt הבאה |
| Worlds table — constraint חסר | `game_today()` מחפש `Status=Active` עם `max_records=1`. אם שני Worlds מסומנים Active, התוצאה לא צפויה. אין constraint ב-Airtable. | לפני F12 / aggregator |
| `/api/game/today` — shared endpoint | גם `BossCheckin.tsx` (Screen #1) וגם `GameScreen.tsx` (Screen #2) משתמשים באותו endpoint. aggregator F12 חייב לשמור על filter הנוכחי (NOT Done + Due_Date≤today + Owner) כדי לא לשבור את Screen #2. | לפני פיתוח F12 |
| `LeadFields.TIER = "tier"` — שדה לא קיים ב-Airtable | schema dump 2026-06-15 אימת: אין שדה `tier` / `Tier` בטבלת Leads ב-`app4bcgoX7t0HUVnm`. gateway חוסם כתיבה. **החלטה נדרשת:** (1) ליצור שדה `Tier` ב-Airtable (singleSelect), (2) להסיר `LeadFields.TIER` מהקוד, (3) להשאיר כ-no-op. | לפני פעילות scoring בפרודקשן |
| Assets schema drift | שמות שדות ב-live שונים מ-MIGRATION doc: `"Mortgage Balance"` (לא `"Mortgage"`), אין `"Purchase Cost"`, אין `"Documents"`. `AssetFields` בקוד עשוי להשתמש בשמות לא נכונים. | לפני פיתוח Assets tools |
| `Table 16` ב-Airtable | טבלת placeholder ריקה (`tblXeDnLTAvpej3cC`) — לא בשימוש. למחוק ידנית מ-Airtable UI. | Housekeeping הבא |
| `/status` Telegram handler חסר | `@bot.message_handler(commands=["status"])` decorator הוסר ב-PR #55; `cmd_status` קיים אבל לא מרשם. הפקודה שקטה לowner. | N הבא שנוגע ב-app.py |

---

## פערים ידועים (לא באגים — החלטות מודעות)

| פער | סיבה | מתי נטפל |
|-----|-------|----------|
| F09 lead_qualifier — לא מחובר | state machine בנוי, מחכה ל-N04 | F09 |
| F10 lead_memory — לא מחובר | debounce בנוי, מחכה ל-N02 | F10 |
| F11 followup_engine — חלקי | תשתית בנויה, מחכה ל-N04 MVP | F11 |
| core_knowledge.py smoke test false positive | _NEVER_FAKE_CONTROL מכיל פראזה שהtest מזהה בטעות | לתעד כ-known false positive |
| Voice/IVR Twilio signature validation | לא קריטי עד שF07 פעיל | לפני F07 |
| /status handler חסר decorator | @bot.message_handler הוסר בשלב לא ידוע | מחר — תיקון שורה אחת |
| schema_cache.json stale | Coins_Log, Roadmap_Tasks, Leads מציגים [] | רענון בסשן הבא |

---

## כללי ברזל — לא לגעת בלי אישור

1. **Feature flag = כבוי ברירת מחדל.**
2. **app.py — 4 hooks בלבד (H1–H4).**
3. **Agent לא נוגע ב-Airtable ישירות.** תמיד דרך crm.py.
4. **זיכרון ליד = identity.memory_key בלבד.**
5. **מקור אמת לדומיין = detect_domain() בלבד.**
6. **לא בונים batch לפי פיצ'ר — בונים לפי קובץ.**
7. **schema_intelligence.SCHEMA["Leads"] חייב להיות מסונכרן לפני כל כתיבה.**

---

## ארכיב מסמכים

| קובץ | תפקיד |
|------|--------|
| ROADMAP.md | **זה. מקור האמת היחיד.** |
| BOSS_CURRENT_STATE.md | מצב מודולים בפועל |
| CLAUDE.md | הוראות לקלוד קוד — קרא ראשון |
| ARCHIVE_additions_log.md | specs מפורטים A01–A43, היסטוריה |
| SETUP.md | env vars, טבלאות Airtable, הפעלה ראשונה |
## Audit note - 2026-06-14

Active planning source of truth is now limited to:
- `ROADMAP.md`: priorities, blockers, next actions.
- `BOSS_CURRENT_STATE.md`: current architecture, implemented features, decisions, known risks.

All other planning/report Markdown files are archived historical evidence unless a future batch explicitly promotes content back into one of these two files.

Current verified status for N02-N05:
- N02 Live Lead Scoring: PARTIAL. Code exists in `lead_capture.py` behind `LEAD_SCORING`; default off and not verified active in production.
- N03 Lead Memory Wire-up: PARTIAL. `lead_memory.update()` is wired from `lead_capture.py` after successful scoring behind `LEAD_MEMORY`; default off and not verified active in production.
- N04 Followup Activation: PARTIAL. Scheduler job and approval queuing exist behind `FOLLOWUP_AUTOMATION`, but the flow depends on populated `lead_memory` and is not active end-to-end.
- N05 Daily Digest upgrade: PARTIAL. Digest reads `Score`, but hot-lead filtering still uses status only and does not filter by score/tier as documented.

Recommended next action: Fix docs first, then choose whether to activate/ship the intended single N02 path.

Archived / historical Markdown disposition:

| File | Disposition | Destination / section |
|---|---|---|
| `BOSS_MASTER_PLAN_2026_v2.md` | ARCHIVE | Historical strategy notes; active priorities live in `ROADMAP.md`. |
| `BOSS_MASTER_PLAN_GAP_ANALYSIS.md` | ARCHIVE | Historical audit notes; superseded by `BOSS_CURRENT_STATE.md`. |
| `boss_bot_summary.md` | ARCHIVE | Early generated implementation summary; superseded by current code and `BOSS_CURRENT_STATE.md`. |
| `PATCH_REPORT.md` | ARCHIVE | Historical patch log; keep as evidence, not active plan. |
| `SECURITY_CHECKLIST.md` | MERGE / ARCHIVE | Security triggers and open findings summarized in `BOSS_CURRENT_STATE.md`. |
| `reports/capability_map.md` | ARCHIVE | Historical generated report; high-signal blockers reflected in `BOSS_CURRENT_STATE.md`. |
| `reports/governance_mapping_report.md` | ARCHIVE | Historical governance map; table decisions reflected in `BOSS_CURRENT_STATE.md`. |
| `reports/registry_calibration_report.md` | ARCHIVE | Historical registry calibration; keep as evidence. |
| `reports/system_registry_report.md` | ARCHIVE | Generated environment snapshot; not an active plan. |
| `reports/airtable_structure_governance_audit.md` | ARCHIVE | Historical Airtable governance audit; keep as evidence. |
| `BOSS_Refactor_Plan.md` | ACTIVE REFERENCE | תוכנית 8 מסכים + BOSS Layer — Stage 0 הושלם, N06 = Stage 1 |
### F52 — Tool Architecture Audit Maps

Status: Implemented but not yet verified.

What: audit-only documentation before F52 implementation. The current branch adds:

- `docs/f52/F52_CURRENT_TOOL_MAP.md`
- `docs/f52/F52_CONTRACT_COVERAGE_MAP.md`
- `docs/f52/F52_BYPASS_MAP.md`

Scope guard: no production behavior changes, no `app.py` changes, no refactor, and no Airtable schema changes. The audit maps current tool architecture, contract coverage, bypass categories, high-risk bypasses, safe audit tests, and design-review items.
