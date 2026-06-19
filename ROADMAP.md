# BOSS Bot — ROADMAP
**מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE.**
עודכן: 19/06/2026 — main = `7df22c3` (אומת: `git log origin/main -1`). PR #75/#76/#77/#79/#80/#81/#82/#83 ממוזגים (ראה C53/O4/C53-A/A32 למטה + Sprint 19/06/2026 + CHANGE_CONTROL_LOG.md ל-PR #82/#83).

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

### N07 — Schema Governance script 🔲 PLANNED
**עדיפות:** גבוהה.
**מה:** סקריפט שמשווה live Airtable schema (דרך Airtable MCP/API) מול
`airtable_schema.py` באופן שיטתי, ומדגיש drift (כולל trailing spaces
ב-singleSelect/multipleSelects, שדות חדשים/חסרים, סוגי שדה שהשתנו).
**מניע:** BUG-008 (`Leads."Business Outcome"` trailing space) התגלה
ad-hoc תוך כדי חקירת באג, לא דרך audit שיטתי — ראו `AI_CONTEXT.md` §8.
**עד שמיושם:** manual gate בלבד (ראו `RELEASE_CHECKLIST.md`).

### N08 — CI/CD GitHub Actions 🔲 PLANNED
**מה:** הרצת `pytest`/`smoke_tests.py`/`test_integration.py` + `npm run build`
על כל PR, ו-hook ל-Render לאימות שה-deploy תואם את ה-commit שעבר CI.
**עד שמיושם:** manual gate בלבד (ראו `RELEASE_CHECKLIST.md`).

### N09 — Monitoring / Alerting 🔲 PLANNED
**מה:** Render alerts + Sentry (או שווה-ערך) לזיהוי שגיאות בפרודקשן
בלי תלות בדיווח ידני של המשתמש.
**עד שמיושם:** manual gate בלבד (ראו `RELEASE_CHECKLIST.md`).

### N10 — Rollback אוטומטי 🔲 PLANNED
**תלוי ב:** N08 (CI/CD).
**מה:** rollback אוטומטי ל-commit יציב אחרון כש-health check/monitoring
מזהה כשל אחרי deploy.
**עד שמיושם:** manual gate בלבד (ראו `RELEASE_CHECKLIST.md`).

### N11 — Screen Filter Gateway: Finance Pulse wiring 🔲 PLANNED
**תלוי ב:** C53 (Screen Filter Gateway — מיושם, PR #75).
**מה:** שלב 2 של ה-Gateway — `SCREEN_CONFIGS["finance_pulse"].views.active.raw_formula`
ייעודכן עם formula דינמית לתאריך (תשלומים overdue/קרובים), ו-`GET /api/finance/pulse`
יחובר ל-`_build_formula()` עם `entity="Payment"`. אפס שינוי ל-`_build_formula()` עצמה —
ה-config-driven design מאפשר זאת בלי לגעת ב-Gateway.
**עתידי (multi-tenant):** override per-tenant מ-`ProjectsHub.screen_overrides`
(JSON, נדרש שדה חדש בסכמה) — ראו הערה ב-`tma_api.py` ליד `SCREEN_CONFIGS`.
**קבצים:** `tma_api.py` בלבד (לפי העיקרון של C53 — additive, לא נוגע ב-Gateway).

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
