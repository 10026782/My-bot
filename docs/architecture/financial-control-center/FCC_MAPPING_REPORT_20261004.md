# Private Financial Control Center — דוח מיפוי (שלב A+B) — 04/10/2026

**Truth Reset:** `origin/main` = `d784ae67d07e3913b58561c56be10ad0f9c90136` (`git rev-parse HEAD origin/main` זהים, ענף `claude/quirky-pasteur-rkm5ih`).
**Pre-session gate:** exit 0 — "אין ענפות claude/* פתוחות".
**Context Librarian:** `suggest-profile` → `no_match` (כל הציונים 0). נבחר ידנית `tool_execution`; `build` נכשל (`last_verified_commit 202af60…` לא זמין בשכפול הרדוד — exit 128). לא נבנה bundle; נעשה אימות ישיר מול הקוד.
**סטטוס:** מיפוי בלבד. **לא נכתב קוד פיצ'ר. לא נוצר/שונה schema חי.** ראה §0 — עצירה לפי כלל הפרטיות של המשימה.
**Evidence level:** מיפוי סטטי + reproduction מקומי אחד. אין אימות Airtable חי (אין `AIRTABLE_API_KEY` בסנדבוקס; `schema_cache.json` מ-04/09/2026).

הערת מסמכים: `PLANNING_GATE.md` בשורש לא קיים; הקנוני הוא `docs/governance/PLANNING_GATE.md` (+ `docs/context_librarian/PLANNING_GATE.md`). קבצי F52 נמצאים תחת `docs/architecture/f52-unified-approval-runtime/audits/original/`.

---

## 0. ממצא פרטיות קיים — PRIV-FCC-01 (נעצר כאן)

**הכלל במשימה:** אם קיים סיכון שמאפשר למשתמש אחד לראות נתונים אישיים של אחר — לעצור, לתעד, לדווח.

| # | ממצא | ראיה | מצב |
|---|------|------|-----|
| 1 | **קריאה גנרית של Airtable אינה owner-scoped ואינה table-scoped.** `enforce_tenant_scope()` מחזיר params ללא סינון לכל `identity.is_internal` (owner/manager/employee); `airtable_get` רשום עם `roles_allowed=_ALL_EXTERNAL`. | `tools/airtable_security.py:enforce_tenant_scope` ("owner/staff — מותר הכל"), `tool_registry.py:275`, `tools/dispatcher.py:367-405`. **שוחזר מקומית:** `enforce_tenant_scope("airtable_get", Identity(role=manager/employee/owner), {"table":"Loans"})` → `<NO FILTER>` (ל-`Loans` יש שדה `Owner`). partner נחסם (`לא הוגדר תחום`) רק כי אין לו allowlist ל-Loans. | **מאומת סטטית + repro** |
| 2 | `GET /api/assets`, `GET /api/assets/<id>`: כל `is_owner` או כל מי ש-`"personal" in allowed_domains` מקבל **כל** ה-Assets וסכומים מצטברים; אין סינון לפי `Assets.Owner` (שדה קיים) ואין בדיקת בעלות ל-`<id>`. | `tma_api.py:3848-3902`. | **מאומת סטטית** (repro ב-Flask לא רץ — `flask` לא מותקן בסנדבוקס) |
| 3 | `partner` על Tasks/Leads/Deals/Payments מסונן לפי `Domain` בלבד, לא לפי Owner. | `airtable_security.py` partner branch. | מאומת סטטית |
| 4 | `_process_owner_tasks`: Task ללא `Owner` מוגש לכל מי ש-`is_owner`. | `tma_api.py:3085-3130`. | מאומת סטטית |

**מה לא ידוע:** האם ב-`IDENTITY_MAP` החי יש כרגע יותר מזהות אחת עם role=owner/manager/employee, או partner עם `"personal"`. אם יש משתמש יחיד (אליהו) — אין דליפה בפועל היום; הסיכון **לטנטי ומותנה קונפיגורציה**. אבי מתוכנן כ-`partner` (`docs/architecture/AVI_PILOT_PREPARATION_20260901.md`).

**למה זה חוסם את הפיצ'ר:** כל טבלה פיננסית חדשה בבסיס הראשי תהיה קריאה מיד ע"י כל manager/employee/owner דרך `airtable_get` של ה-agent, ו-Tasks שיווצרו מ-Goals (כותרות כמו "להשיג יתרות") קריאות גנרית לכל מי שיש לו `airtable_get`. לכן לא ניתן לבנות את המרכז הכלכלי "פרטי" בלי להחליט תחילה על שני סגירות (ראה §5/§7):
1. **Deny-list גנרי:** `airtable_get/add/update` (dispatcher + ActionGateway resolve) חייב לחסום את טבלאות Financial_* לכל הזהויות, ללא יוצא מן הכלל; גישה רק דרך מודול `financial_scope` ייעודי.
2. **Tasks פיננסיות:** צריך מנגנון שמוציא אותן מקריאות Tasks גנריות (`airtable_get`, `/api/owner/my-work`, digest, `_get_global_kpis`) — החלטת מוצר/סכמה (ראה §5).

**נדרשת החלטת בעלים לפני המשך** (לא נעשה כאן שום שינוי בנתיבים הקיימים — תיקון `/api/assets` ו-`enforce_tenant_scope` הוא שינוי התנהגות מחוץ לסקופ המבוקש):
- (א) האם לתקן את הנתיבים הקיימים (Assets owner-of-record; table deny-list) כ-PR נפרד **לפני** ה-FCC, או
- (ב) לבנות FCC עם מודול גישה עצמאי + deny-list ייעודי בלבד, ולהשאיר את הקיימים כחוב מתועד.

---

## 1. Existing → Reusable → Missing → Proposed

מקור ל"Existing": `airtable_schema.py` + `schema_cache.json` (04/09/2026). לא אומת חי.

| נתון | Existing (SSOT) | Reusable | Missing | Proposed |
|------|-----------------|----------|---------|----------|
| הלוואות | `Loans` (Loan Amount, Interest Rate, Term, Outstanding Balance, Next Payment Due, Principal Repaid, Interest Paid, Payment Status, `Owner`→Profile, Domain). **מצב:** מכוון לפרויקטים (שדה `Project`, `Lender`) | כ-reference בלבד (link מ-Goal/Event אל רשומת Loan) | הבחנה הלוואה אישית/עסקית; הרשאת קריאה owner-of-record | לא להעתיק; לא לקרוא אותה דרך ה-FCC עד שיוגדר scope (Loans נחשפת גנרית — §0) |
| Payments | `Payments` (amount, date, status, Direction, Paid At, owner, Counterparty…) — ledger של עסקאות/חיובים עסקיים | כ-reference אירוע (`source_ref`) כשתשלום מסוים הוא "גביית כסף שמגיע" | אינו מייצג חיסכון/קרן חירום/החזר חוב אישי | אירוע FCC מצביע ל-Payment id, לא משכפל סכום |
| Deals / Organizations / Contacts | `עסקאות (Deals)`, `Organizations`, `אנשי קשר (Contacts)` + Payment Terms/Charges | link ליעד "הכנסה עסקית/ייבוא/גביית כספים" | — | link בלבד |
| Tasks | `משימות (Tasks)`: כותרת, תיאור, תאריך יעד, סטטוס, **Owner→Profile**, **Priority**, **Topic**, Domain, **Cadence** (recurring), Required, Xp, links ל-Leads/Deals/Contacts/Decisions/Sessions | **כן — Reuse first** | link ל-Goal; מזהה dedup | שדה link אחד `Financial Goal` (additive) — ראה §5 |
| נכסים | `Assets` (Current Value, Monthly Income, Mortgage Balance, Equity, Ownership %, `Owner`, Next Step) | reference/הצגה ב-Long-term | סינון Owner ב-API (§0 #2) | link בלבד, **אחרי** תיקון §0 |
| הוצאות | `Expenses` (name, amount, category, date, status, owner, domain) — **עסקיות** (domain) | reference | אין "הוצאה קבועה אישית" | אירוע FCC מסוג `recurring_expense_cancelled` עם סכום חודשי; לא ledger כפול |
| הכנסות | אין טבלת הכנסות אישית; `Payments`(Direction) עסקי | — | **חסר** | אירוע FCC (`income`) |
| השקעות / שוק ההון / פנסיה / קרן חירום | אין שום SSOT (grep: `קרן חירום`, `פנסיה`, `emergency fund` — אפס בקוד חי) | — | **חסר** | Goal + Events (ללא SSOT כפול) |
| חובות | `Loans`, `Company A - Debt Management` (VAT refunds, עסקי) | reference | חוב אישי | Goal מסוג "סגירת חובות" + Events `debt_repaid`; reference ל-Loan אם רלוונטי |
| יעדים | `Weekly_Goals` (Goal, Target_Date, Status Todo/Done/Missed, Owner, Coins) — **טבלת Game/TMA**; `Ventures` — צנרת עסקית | **לא מתאים**: אין סכום/תקופה/חישוב; סמנטיקה גיימיפיקציה | **חסר** | טבלת `Financial Goals` |
| אירועי התקדמות | `Decision Events`/`Lead Events`/`Business Memory`/`Interaction Log` — אירועים של Decision/Lead/איכותניים | **תבנית** (append-only + link-to-parent + `Supersedes`), לא טבלה | אין אירוע סכומי | טבלת `Financial Progress Events` |
| Media/Source files | `Media Files` (drive_url + metadata) | `raw_ref` לראיה (הקלטה/קובץ) | — | reference |
| Owner/tenant/user | `identity.user_id` (למשל `eliyahu`) → `Profile` (שורה לכל איש צוות) → `Tasks.Owner`/`Leads.Owner` (multipleRecordLinks, `core/owner_resolution.resolve_profile_record_id`, התאמה case-insensitive לפי שם) | **כן** כמפתח בעלות | אין enforcement של owner-of-record בנתיבי קריאה (§0) | ראה §3 |
| בסיס ישן / legacy | `MIGRATION_AIRTABLE_ENGLISH_SCHEMA.md`, `_ALIAS_MAP`, `OLD_TABLE_NAMES` (smoke) | — | — | לא נגע; אין נתונים פיננסיים אישיים ב-legacy שנמצאו |
| Audit/revision | `ActionContracts` (normalized_payload, status, approved_by, versions), `audit_log_airtable`, `_audit()` ב-TMA; `Supersedes` ב-Decision Events | **כן** — אין צורך במנוע revision חדש | היסטוריית target לפי תקופה | `Financial Goals` שומרת שורת revision append-only דרך `Supersedes` (תבנית Decision Events) או אירוע `target_change` |
| Scheduler | `scheduler.py` (`schedule` in-process) + `Cadence` ב-Tasks (השלמה מקדמת תאריך על אותה רשומה — `core/task_writer.recurring_completion`) | **כן** — reviews כ-Tasks חוזרות, בלי scheduler חדש | — | seed Tasks חוזרות (Weekly/Monthly) |

---

## 2. Existing Architecture Map (שרשרת חוזה — Rule 00)

1. **Entry:** TMA (`require_tma_auth` → `resolve_identity("telegram", id)`) / Telegram+WhatsApp `app.py` (`resolve_identity → route_request → build_context → run_agent`).
2. **Public API:** TMA writes → `tma_api._queue_or_owner_execute(action, payload, identity, label)` → `_queue_tma_write_approval` → `ActionGateway.propose_action(...)`; owner auto-approves via `_claim_and_execute_approval`. Agent writes → `ActionGateway.propose_action` → `tools/dispatcher.dispatch_tool`.
3. **Data contract:** `ActionContract` (tenant_id, canonical_user_id=memory_key, tool_name, normalized_payload, `business_action_fingerprint`=hash(tenant+user+tool+payload), actor_*, approval_policy `approval|self_confirm`, trusted_source).
4. **Execution point:** `_make_dispatch_executor` → `dispatch_tool` → `airtable_gateway.airtable_create/airtable_patch` (field validation vs schema cache/runtime provider; audit log).
5. **Verification:** `core/anti_hallucination.verify_execution`, structured tool-result `{ok, tool, external_id, evidence, user_message}` (`tools/airtable_tools._tool_result`), ExecutionLedger/evidence projection.

Approval: `classify_approval_policy()` → `self_confirm` רק ל-allowlist צר של Leads/Interaction Log/Tasks-מ-scheduler; **כל השאר = `approval`** (owner/`actions.approve`). זה מפריד "הבנתי אותך" (preview/draft) מ"מורשה לבצע". מחיקה/העברת בעלות/bulk נשארים fail-closed.

## 3. Privacy / Owner Isolation Map

- מודל זהות: `Identity(user_id, role, tenant_id, domain_id, allowed_domains)`; כולם ב-`boss_hq` → **tenant לבדו אינו מבדיל** (אומת).
- Owner-of-record קיים רק כ-link ל-Profile ב-Tasks/Leads/Assets/Loans/Payments/Expenses/Ventures; נאכף רק ב: `/api/owner/my-work`, `PATCH /api/tasks/<id>` (בדיקת Owner link), lead-service Owner contract. **לא** נאכף ב-`airtable_get`, `/api/assets*`, `/api/finance/pulse`.
- `role=owner` ≠ הרשאה פיננסית פרטית — מדיניות מוצעת: **owner-of-record only**, ללא delegation אלא אם תועדה במפורש (שדה/רשומת delegation + audit).
- Fail-closed: `resolve_identity` מחזיר `READONLY` (לא None) למזהה לא מוכר, ו-`resolve_profile_record_id` מחזיר None לשם לא-מוכר/כשל — **אך** התאמה case-insensitive לפי שם ולא ייחודית (`max_records=5`, לוקח `[0]`). לפיצ'ר פרטי: חובה דרישת **התאמה יחידה** (0 או >1 → fail closed).
- Enforcement מוצע (לא ממומש): מודול `financial_scope` יחיד; `owner_record_id` נגזר **רק** מ-`identity` (לעולם לא מ-body/query/LLM); כל read/aggregate/search/export/free-text-resolution/Task-link עובר דרכו; deny-list גנרי (§0).

## 4. Tasks / Follow-up Map

`TaskFields`: NAME, DESCRIPTION, DUE_DATE, STATUS (ממתין|בביצוע|בוצע), CONTACTS_LINK, DEALS_LINK, DOMAIN, OWNER (Profile link), LEAD_LINK, RECURRENCE=`Cadence`. בנוסף בסכמה החיה: Priority, Topic, Required, Xp, Decisions, Sessions. `core/task_writer.py` = Golden Writer (כותרת חובה, verify links, Diamond completion, recurrence). `ActionGateway.complete_task_proposal` מפעיל אותו ב-Gate 1.
**מסקנה:** Tasks מספיקה ל-0..N פעולות עוקבות (Owner/status/priority/due/description/Cadence). **חסר רק** link ל-Goal ומפתח dedup. `Impact` ו-type → description/Topic או שדות ב-Goal. אין צורך ב-`Financial Actions`.
**Dedupe:** `ActionContract.business_action_fingerprint` מונע כפילות contracts; dedup ל-Task פתוחה זהה (אותה Goal + כותרת מנורמלת + סטטוס≠בוצע) דורש בדיקה לפני propose (לא קיים כרגע ל-Tasks גנריות).

## 5. Writer / Gold Path Map

קנוני היום: `Raw → route_request (deterministic parsers, e.g. parse_deterministic_create_task) → ActionGateway.propose_action (resolve_canonical_call → complete_task_proposal → validate → fingerprint → classify_approval_policy) → preview/confirm (route_confirmation_word) → approve (enforce re-run for requester) → dispatch_tool → airtable_gateway → verify_execution/evidence`. Draft/free-text: `core/business_draft.py` (BusinessDraft envelope; edit vocabulary `draft_fields.py`), `core/draft_flow.py` (filling→review→confirm), `core/structured_command.py`, `commercial_completion*.py` (Diamond completion), `session_store.py` (durable). Raw evidence: `Interaction Log`/`Lead Events`/`Media Files`.
**המלצה:** FCC מרחיב את אותו מסלול — entity חדש ב-BusinessDraft/Entity-Adapter + כלי ב-registry (`roles_allowed` מפורש, `requires_approval` לפי מדיניות) + dispatcher + `tools/schemas.py`; **אין** parser נקודתי ו-**אין** Airtable HTTP ישיר. סיווג כוונה בשפה חופשית = שכבת Classify קיימת של ה-agent/router עם resolve מול רשומות אמיתיות; עמימות → disambiguation (`route_disambiguation`).

## 6. Gaps

1. אין SSOT ל-Goal, ל-Progress סכומי, להכנסה אישית, חיסכון, קרן חירום, פנסיה.
2. אין owner-of-record enforcement בקריאה גנרית ובנתיבי Assets (§0).
3. אין link Task→Goal ואין dedup ל-Tasks לפי Goal.
4. אין deny-list לפי טבלה ב-dispatcher/registry.
5. Profile resolution אינה דורשת התאמה יחידה.
6. אין סמנטיקה `one_time|monthly_recurring` לאירועים.
7. `PLANNING_GATE.md` בשורש חסר (הפניה בבקשה); Context Librarian bundle אינו נבנה בסביבה הרדודה.

## 7. Proposed minimal schema (הצעה בלבד — לא נוצר דבר)

| רכיב | סוג | למה |
|------|-----|-----|
| `Financial Goals` | טבלה חדשה | אין SSOT מתאים (Weekly_Goals=גיימיפיקציה, Ventures=צנרת). שדות: title, category, status, active, priority, display_order, period_type, start_date, end_date, target_amount, min/max, calc_method, notes, **financial_owner** (Profile link — מפתח בעלות; שם סופי נקבע לאחר החלטת §0), supersedes (self-link), refs ל-Loan/Asset/Deal אופציונליים. אין enum קשיח; seed = רשומות. |
| `Financial Progress Events` | טבלה חדשה append-only | אין SSOT לאירוע סכומי. שדות: goal (link), amount, `kind` (`one_time`/`monthly_recurring`), occurred_at, recorded_by, financial_owner, source, source_ref (Payment/Loan/Media id), note, idempotency_key, supersedes. |
| `Tasks.Financial Goal` | שדה link אחד (additive) | שימוש חוזר ב-Tasks; Owner/Priority/Cadence/Status קיימים. |
| חישובים | **בקוד, derived** | Actual/Remaining/Remaining periods/Dynamic target/Monthly Cash Improvement — לא נשמרים כמספר מצטבר. |
| Reviews/Hygiene | Tasks חוזרות (`Cadence`) | בלי scheduler/טבלה. |
| revision | `Supersedes` + ActionContracts | בלי מנוע revision חדש. |

סקירת אבטחה נדרשת לפי `docs/governance/SECURITY_CHECKLIST.md` (כלי חדש + endpoint + קבצים שנוגעים ב-dispatcher/identity). Cross-Layer Planning Gate: **FULL** (authority, persistence, routing, approval, multi-layer).

## 8. Risks

duplicated SSOT (Loans/Assets/Payments — הפתרון: reference בלבד) · privacy leak (§0, עיקרי) · bypass write (`airtable_add` גנרי יכול לכתוב לטבלה חדשה — דורש deny-list) · stale schema (`schema_cache.json` ידני; שדות חדשים חייבים הוספה + `schema_audit`) · ambiguous free-text ("הפקדתי 5000" עם כמה Goals → disambiguation, לא בחירה) · cross-owner link (Task/Event→Goal של אחר — לאמת `goal.financial_owner == caller` ב-propose וב-execute) · accidental aggregation (one_time מול monthly_recurring; אין סכימה בין Owners; aggregates רק אחרי סינון owner).

## 9. תוכנית בדיקות (טרם נכתבו)

18 הבדיקות שהוגדרו במשימה → `test_financial_control_center_*.py` ליד הקיימים (סגנון script עם runner עצמי, נקלט ב-CI דרך `test_*.py`); בנוסף: (א) `airtable_get` על כל טבלת Financial_* נחסם לכל role; (ב) Task עם Financial Goal לא מופיע ב-my-work/generic reads של אחר.

---

## 10. אימות חי (Airtable MCP, read-only, 04/10/2026, base `app4bcgoX7t0HUVnm`)

נעשו רק קריאות (`list_tables_for_base`, `get_table_schema`, `list_records_for_table`). לא נוצר/שונה דבר.

| בדיקה | תוצאה |
|-------|--------|
| טבלאות חיות | 53 (ב-`schema_cache.json`: 46). 7 חסרות ב-cache: Allocation Rules, Allocation Snapshots, Deal Economics, Organizations, Worker Assignments, Monthly Calculation Batches, Worker Monthly Results (כולן עסקיות/Deal-Payment). **אין** טבלה פיננסית-אישית קיימת; ההנחה "אין SSOT ל-Goals/Events/הכנסה אישית" אומתה. |
| `Tasks` | `Priority`=High/Medium/Low, `Topic` כולל `כספים`, `Cadence`=Daily/Weekly/Monthly/One Time/One-time, `סטטוס`=ממתין/בביצוע/בוצע/**Open** (אופציה legacy נוספת), `Owner`→Profile. אין שדה link ל-Goal (כצפוי). |
| `Profile` (5 שורות) | Eliyahu=Owner, Ahron=Partner, Orri=Partner, Avi=**Marketing** (לא Partner כפי שהוזכר ב-AVI_PILOT doc), ועוד שורה זבל בשם "ליד חדש" ללא Role. |
| `Assets` | 9 רשומות, **7 מסומנות `Domain=Personal`**, ו-**אף רשומה לא מקושרת ל-`Owner`**. |
| `Loans` | ריקה (0 רשומות). |

**השלכות:**
1. §0 #2 חמור יותר מהמוערך: ל-Assets האישיים אין בעלים כלל, לכן גם תיקון "סינון לפי Owner" ידרוש backfill של `Owner` (החלטת בעלים) — אחרת ה-API יחזיר 0 רשומות.
2. `Profile.name` קיים כשורה כללית ("ליד חדש") — מחזק את הדרישה להתאמה יחידה ב-`resolve_profile_record_id`.
3. מי שמחזיק `IDENTITY_MAP` חי עדיין לא נבדק (env, לא Airtable) — מידת הדליפה בפועל נשארת "לא ידוע".
4. `Loans` ריקה → ההנחה שהלוואות אישיות יימשכו מ-Loans אינה ישימה היום; חובות אישיים יהיו Goals+Events בלבד.
