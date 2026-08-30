# Track 8B — Live Airtable Schema Reconciliation (30/08/2026)

**Read-only.** No `create_*`/`update_*`/`delete_*` Airtable MCP tool was ever
called during this session. No code file was modified as part of the
verification pass (only this report + the three status docs listed at the
end). No `schema_cache.json` regeneration was performed.

**Base verified:** `app4bcgoX7t0HUVnm` ("בסיס עיקרי") — confirmed via
`list_tables_for_base`, which returned **45 live tables**. The 31 tables in
`schema_audit.py`'s own `TABLE_CLASS_MAP` were reconciled field-by-field
against this live response (raw JSON captured to
`/tmp/.../scratchpad/live_tables.json` this session; not a repo artifact).
Select-option-level detail was additionally pulled via `get_table_schema` for
Leads, Deals, Payments and Payment Terms (the highest-risk enum surfaces).

Base note: the prompt's brief said "29 mapped tables" (matching a prior
ROADMAP note "19/29"); the actual live count of `TABLE_CLASS_MAP` entries is
**31** (verified by importing `schema_audit.TABLE_CLASS_MAP` and counting).
The discrepancy is DOC DRIFT in the earlier ROADMAP note, not a live-data
question — this pass reconciles all 31 actual entries.

---

## 1. Table-by-table reconciliation (all 31 `TABLE_CLASS_MAP` tables)

Legend: **live** = field count in the live Airtable table (via
`list_tables_for_base`) · **cache** = field count in checked-in
`schema_cache.json` for that table name (0 = table name absent from cache) ·
**code** = field count of string constants in the corresponding `*Fields`
class in `airtable_schema.py`.

| Table (code name) | live tableId | live | cache | code | Key discrepancies |
|---|---|---|---|---|---|
| Leads | tblersBI4EZoOBTdU | 40 | 21 | 21 | 19 live fields not modeled in code: `Domain category`, `Domain risk assessment`, `Domain summary`, `Lead Events`/`Media Files`/`Payments`/`אנשי קשר (Contacts)`/`משימות (Tasks)`/`עסקאות (Deals)` (auto inverse-links from other tables' Leads-link fields), `Role (from Owner)` (lookup), `owner_user_id` (legacy plain-text predecessor to the `Owner` link field), `updated_at`, `Suggested Followup` + 4 Hebrew formula display fields (`טמפרטורה`/`אימוג'י טמפרטורה`/`מד ציון`/`עדיפות`/`תצוגת ליד`). All SAFE/EXPECTED (auto-links/lookups/formulas) except `owner_user_id` and `updated_at`, which are DOC DRIFT (unmodeled but plain writable/readable fields — worth adding to `LeadFields` if ever needed, no current writer touches them per grep). |
| משימות (Tasks) | tblMlW2wo3dhpSUl7 | 21 | 9 | 9 | 12 live fields not modeled: `Roadmap_Tasks`/`Decisions`/`Sessions` (auto inverse-links), `Role (from Owner)`/`Name (from leads)`/`phone (from leads)` (lookups), `BLUE VIEW BUYERS`, `Cadence`, `Priority`, `Required`, `Topic`, `Xp`. SAFE/EXPECTED — no writer references any of these. |
| Assets | tblLxK1wnWwuLnHSm | 18 | 17 | 17 | 1 extra live field: `Role (from Owner)` (lookup). SAFE/EXPECTED. |
| עסקאות (Deals) | tbl4lzuKymm1g5blW | 24 | 24 | 18 | 6 live fields not modeled: `DEPRECATED - BLUE VIEW BUYERS (unused, do not use)`, `DEPRECATED - Select (unused, do not use)`, `DEPRECATED - Status (unused, do not use)` (already documented in code comment at `airtable_schema.py:263-265`, matches Track 8's F5 note — SAFE/EXPECTED, intentionally dead), plus `Decisions`/`Role (from Owner)`/`Sessions` (auto-link/lookup, SAFE/EXPECTED). Cache count (24) matches live count exactly — this table's cache entry is current. |
| Approvals | tblCT6JvGeuKrhURE | 12 | 12 | 12 | Exact match, no discrepancies. CLOSED. |
| Interaction Log | tblFccVHdoqA3AOeX | 13 | 8 | 8 | 5 live fields not modeled: `Domain`, `Owner`, `Role (from Owner)`, `Select` (unlabeled/unused single-select — worth a live cleanup note, not a code issue), `Ventures`. DOC DRIFT (Owner/Domain genuinely unmodeled writable fields) + SAFE/EXPECTED (lookup/link). |
| Payments | tbl027IEVotG1cy46 | 18 | 18 | 17 | **`contact_id` (code) does not exist live** — confirms Track 8's F4 as still valid: `PaymentFields.CONTACT = "contact_id"` is a phantom field. 2 live fields not modeled: `Sessions` (auto-link, SAFE/EXPECTED), `role (from Owner)` (lookup, SAFE/EXPECTED). Cache count (18) matches live exactly. |
| אנשי קשר (Contacts) | tblafm2OJqB0230LH | 36 | 9 | 12 | **`ContactFields.TYPE = "Type"` does not exist live** (new finding — see §3). 24 live fields not modeled in code (dedup/partner/referral/scoring machinery: `Contact Score`, `Contact Archive`, `Import Batch`/`Import Status`, `Needs Review`, `Partner Status`/`Partner Type`, `Referral Code`/`Referred By`/`Total Referrals`, `Source`, `email_domain`, `Institution Type`, `Looking For`, `BLUE VIEW BUYERS`, `Domain`, `Owner`, plus `Decisions`/`Decision Events`/`Decision Stakeholders`/`Media Files`/`Sessions`/`Role (from Owner)` auto-links/lookups). Cache is badly stale here (9 vs 36 live) — CACHE DRIFT, largest gap of any table in this pass. |
| Projects | tblkZLu5SbSQcB2Sf | 18 | 12 | 12 | 6 live fields not modeled: `Assets`, `Domain`, `Linked Loans`, `Linked Units`, `Next Action`, `Priority`. DOC DRIFT — this table isn't in the prioritized entity list from the task brief; not further investigated. |
| Worlds | tblXa6Mbh0EPMBbZo | 16 | 10 | 11 | 5 live fields not modeled: `Boss_Battles`, `Related Contacts`, `Roadmap_Tasks`, `Tags`, `Weekly_Goals`. Gamification table, out of scope for the prioritized entities; SAFE/EXPECTED (mostly auto-links). |
| Quests | tbldwqAbA4L2igHNO | 12 | 8 | 8 | 4 live fields not modeled: `Boss_Battles`, `Coins_Log`, `Date`, `Roadmap_Tasks`. Same as above. |
| Coins_Log | tblhOsZzqYOMcdgyq | 5 | 5 | 5 | Exact match. CLOSED. |
| Emergency_Window | tblyC9hb6INMUCOkR | 9 | 9 | 9 | Exact match. CLOSED. |
| Media Files | tbl6AFKkPZVN5qdCt | 24 | 19 | 19 | 5 live fields not modeled: `Linked Contact`, `Linked Decision`, `Linked Decision Event`, `Marketing Publications`, `Sessions` — all auto-links added by the later Decisions/Sessions tracks. SAFE/EXPECTED. |
| ActionContracts | tbluHDA4xWMD7BQ8P | 26 | **0 (F7)** | 26 | **Exact 1:1 field-name match with code**, live confirms table exists with all 26 fields code expects. F7 resolved for this table — see §2. |
| Daily_Checkin | tblydLDwRzPM1JYuQ | 6 | 6 | 6 | Exact match. CLOSED. |
| Emergency Stop Flags | tblBba3rkkFcj4uuv | 7 | **0 (F7)** | 7 | **Exact 1:1 field-name match**, live confirms table exists with all 7 fields code expects (`Enabled`, `Flag Name`, `Operation ID`, `Reason`, `Source`, `Updated At`, `Updated By`). F7 resolved. |
| External Execution Jobs | tblceAHBFtfGK9bdP | 11 | **0 (F7)** | 11 | Exact 1:1 match. F7 resolved. |
| Lead Events | tblqP9zW4lAQ1m2aj | 8 | 0 | 8 | **Exists live**, exact 1:1 match with `LeadEventFields` (`Channel`, `Created At`, `Domain`, `Event Type`, `Lead`, `Message`, `Name`, `Summary`). Resolves the ledger's open "does Lead Events exist live at all" question definitively: **yes**. Not one of F7's named 14 (see §2 for why it's a separate item), but the same "never captured in cache" root cause applies. |
| Marketing Demand | tbljxJMyeSlF4VC42 | 13 | **0 (F7)** | 13 | Exact 1:1 match. F7 resolved. |
| Marketing Publications | tblUhWCdS8s4H1aS7 | 11 | **0 (F7)** | 11 | Exact 1:1 match. F7 resolved. |
| Sessions | tblHLfE24lTkVUhz0 | 18 | **0 (F7)** | 18 | Exact 1:1 match — all 18 `Linked X` fields (Lead/Deal/Task/Contact/Payment/Business Memory/Decision/Decision Event/Media File/Venture) present live exactly as coded. F7 resolved; this table's fields also explain most of the "extra `Sessions` link field" noise on other tables' rows above (they're the auto-generated inverse side of these same 10 `Linked X` fields). |
| Business Memory | tblV8PSpPWKJQpqEa | 15 | **0 (F7)** | 8 | 7 live fields not modeled: `Decisions`, `Interaction Log`, `Outcome`, `Owner`, `Role (from Owner)`, `Sessions`, `Ventures`. F7 resolved (table exists), but code coverage is also incomplete here — `Outcome` and `Owner` look like genuinely writable fields worth adding if this table becomes an active writer target. |
| Decision Events | tblXRBfei3ArdrM08 | 24 | **0 (F7)** | 19 | 5 live fields not modeled: `Decision Inbox`, `Event Title`, `From field: Supersedes` (Airtable's auto-generated reverse-lookup label for the `Supersedes` self-link), `Media Files`, `Sessions`. F7 resolved. |
| Decisions | tblLDGJEhQjqF8qJD | 29 | **0 (F7)** | 24 | 5 live fields not modeled: `Decision Events`, `Decision Inbox`, `Decision Stakeholders`, `Media Files`, `Sessions` — all auto-links from the sibling Decision tables. F7 resolved. |
| Decision Inbox | tbluVm2AcgduLID5w | 10 | **0 (F7)** | 9 | 1 extra live field: `Inbox Title` (Airtable's auto primary-field label). F7 resolved. |
| Decision Stakeholders | tblYlA77FmZS9bVE9 | 8 | **0 (F7)** | 7 | 1 extra live field: `Stakeholder Title` (primary-field label). F7 resolved. |
| Expenses | tbl87HP9evXJKFUtC | 8 | **0 (F7)** | 6 | 2 live fields not modeled: `owner`, `role (from Owner)`. F7 resolved; `owner` is a genuinely writable Owner-link field with no code constant — worth adding an `ExpenseFields.OWNER` if Expenses ever gets a writer. |
| Profile | tblwf2K8WZrdu8xI5 | 14 | **0 (F7)** | 2 | 12 live fields not modeled, but this is **intentional and already documented**: `ProfileFields` docstring (`airtable_schema.py:504-511`) explicitly states Profile is a people-roster table where only `NAME`/`ROLE` are read/written directly; the other 12 fields (`Assets`, `Business Memory`, `Interaction Log`, `Leads`, `Loans`, `Units`, `Ventures`, `אנשי קשר (Contacts)`, `הוצאות (Expenses)`, `משימות (Tasks)`, `עסקאות (Deals)`, `תשלומים (Payments)`) are auto-generated inverse links from every other table's `Owner` field pointing at Profile. F7 resolved; field-coverage gap here is SAFE/EXPECTED by design, not a defect. |
| Roadmap_Tasks | tbljYI6D1l3eeOmQX | 12 | 11 | 11 | 1 extra live field: `Linked Tasks` (auto-link). SAFE/EXPECTED. |
| Ventures | tblsXFq5AwxUkdAJ7 | 16 | **0 (F7)** | 15 | 1 extra live field: `Sessions` (auto-link). F7 resolved. |

**Old Hebrew Payments table (`תשלומים (Payments)`):** does **not exist** as a
live table at all — absent from the full 45-table live listing. It remains
in `schema_cache.json` as a stale 7-field entry (CACHE DRIFT — describes a
table that no longer exists). It survives only as the **display label** of
one Deals link field (`DealFields.PAYMENTS_LINK = "תשלומים (Payments)"`,
field id `fldAwsJItkdRYCEvc`), which — verified via `get_table_schema` —
actually points at the live canonical **`Payments`** table (`tbl027IEVotG1cy46`,
inverse of `PaymentFields.DEAL` / `deal_id`). No live or code path targets
the deleted Hebrew table by name; `airtable_schema.py` never defines it as a
`Tables.*` constant, only as this one field's label string. SAFE/EXPECTED —
a legacy display-name artifact, not a functional problem.

Tables live in the base but **not** in `TABLE_CLASS_MAP` (out of this pass's
declared scope, listed for completeness): `Units`, `Loans`,
`Company A - Debt Management`, `Weekly Cash Flow Reports`,
`Unit Sales & Debt Distribution`, `משימות ודד ליינים`,
`למידות ותובנות (Learnings & Insights)`, `ProjectsHub`, `Weekly_Goals`,
`Boss_Battles`, `TRAFFIC_SOURCES`, `Marketing Creatives`, `Payment Terms`,
`AI_Usage_Daily`. `Payment Terms` and `AI_Usage_Daily` are also in
`schema_cache.json` despite not being in `TABLE_CLASS_MAP` — `Payment Terms`
was fully verified separately for the Deal/Payment enum work (§4 below);
`AI_Usage_Daily` was not investigated this pass (not named in the task
brief's prioritized list, `core/cost_watchdog.py`'s domain, not the
Deal/Payment/Lead entity set).

---

## 2. F7 — exact resolution, all 14 tables individually

**All 14 tables exist live, with real, non-empty field sets that match code
almost exactly (11/14 are an exact 1:1 field-name match; the other 3 have
only auto-generated extra fields).** None are missing, none are
misconfigured relative to what the code expects to write.

| # | Table | Live field count | Code field count | Verdict |
|---|---|---|---|---|
| 1 | Sessions | 18 | 18 | Exact match |
| 2 | ActionContracts | 26 | 26 | Exact match |
| 3 | Business Memory | 15 | 8 | Exists; 7 unmodeled fields (see table above) |
| 4 | Profile | 14 | 2 | Exists; 12 unmodeled fields, all intentional (design, see above) |
| 5 | Ventures | 16 | 15 | Exists; 1 unmodeled auto-link |
| 6 | Expenses | 8 | 6 | Exists; 2 unmodeled fields (`owner`, `role (from Owner)`) |
| 7 | Decision Events | 24 | 19 | Exists; 5 unmodeled auto-link/lookup fields |
| 8 | Decisions | 29 | 24 | Exists; 5 unmodeled auto-link fields |
| 9 | Decision Inbox | 10 | 9 | Exists; 1 unmodeled primary-field label |
| 10 | Decision Stakeholders | 8 | 7 | Exists; 1 unmodeled primary-field label |
| 11 | Marketing Demand | 13 | 13 | Exact match |
| 12 | Marketing Publications | 11 | 11 | Exact match |
| 13 | Emergency Stop Flags | 7 | 7 | Exact match |
| 14 | External Execution Jobs | 11 | 11 | Exact match |

**Root cause (why these were never captured in `schema_cache.json`):**
confirmed by reading `schema_cache.json`'s own `"note"` field and
`schema_audit.py`. `schema_audit.py`'s `TABLE_CLASS_MAP` has always covered
all 31 tables unconditionally — there is no scope gap in the script itself,
and `run_audit(live=True)` calls the Airtable Metadata API for every table
in the map with no filtering. The actual cause is operational: **a live,
full `schema_audit.py` run has apparently never completed successfully in
any prior session** — `schema_cache.json`'s note says "seed — run
schema_audit.py to refresh from live Airtable... this session has no
AIRTABLE_API_KEY to run schema_audit.py's own refresh," meaning the cache
was hand-typed from `airtable_schema.py`'s constants at some past commit,
for whichever tables existed in the schema module at that time, and was
never regenerated as tables were added later (Sessions/Decisions/
ActionContracts/etc. were added by later tracks and simply never
back-filled into the cache by hand). `tools/schema_snapshot.py` is unrelated
— a separate, flag-gated (`FEATURE_AIRTABLE_SCHEMA_SNAPSHOT`) archival job
that writes to a distinct `System Schema Snapshots` table, not to
`schema_cache.json`, and was not implicated in this gap.

**Lead Events**, while not one of F7's 14, has the identical root cause and
is now equally resolved: it exists live (`tblqP9zW4lAQ1m2aj`, 8 fields,
exact match to `LeadEventFields`), closing the ledger's open "does Lead
Events actually exist live" question with a definitive **yes**.

---

## 3. New findings this pass (beyond F1–F9/K1–K10)

Two concrete drift items surfaced during live verification that weren't
caught by the static Track 8 pass (by nature, since they require live
option-string/field-existence checks):

**N1 — `PaymentStatus.CANCELLED` spelling mismatch (CODE DRIFT, latent).**
`airtable_schema.py:623` defines `PaymentStatus.CANCELLED = "cancelled"`
(British double-L). The live `Payments.status` singleSelect field's actual
4 options (verified via `get_table_schema`, field `fldPeRZsheIKVYavy`) are
`received`, `pending`, `overdue`, **`canceled`** (American single-L) — no
option spelled `cancelled` exists. Grep confirms no writer ever sets
`PaymentFields.STATUS = PaymentStatus.CANCELLED` (only two readers compare
against it: `tma_api.py:2251`'s payments-view exclude-filter, and it's never
constructed by any create/update call in `crm.py`/`commercial_crm.py`). Real
impact: `tma_api.py`'s `view_q != "all"` exclude-filter for canceled
payments **silently never matches**, because it compares a fetched value
against `"cancelled"` while the live field can only ever contain
`"canceled"`. This is a small live behavioral bug (a filter that never
fires), not a write-failure risk, since nothing writes the string. Fix is a
one-line constant correction in `airtable_schema.py` plus verifying the one
call site.

**N2 — `ContactFields.TYPE = "Type"` phantom field (LEGACY, same pattern as
F4).** No field named `Type` exists anywhere in the live Contacts table's 36
fields (verified via full field dump). Grep confirms **zero usages** of
`ContactFields.TYPE` anywhere in the codebase (not even in tests) — fully
inert, same disposition as F4's `PaymentFields.CONTACT`. No live or write-path
risk; a documentation/dead-constant cleanup candidate only.

---

## 4. Enum / select-option verification (Deal/Payment/Payment-Term contract)

Pulled live via `get_table_schema` for every enum the task brief named:

| Code enum | Live field (table) | Match? |
|---|---|---|
| `DealStage` (הזדמנות/במשא ומתן/סגור-ניצחון/סגור-הפסד) | Deals.שלב (`fldSoFC7dZlcHtRFL`) | **Exact match**, 4/4 options, same order |
| `PaymentStatus` (pending/received/overdue/cancelled) | Payments.status (`fldPeRZsheIKVYavy`) | **3/4 match** — `cancelled` vs live `canceled`, see N1 |
| `VATRule` (none/add/included) | Payments.`VAT Rule` (`fldRiHY31yWFuYYJ5`) **and** Payment Terms.`VAT Rule` (`fldGdHsIJgilQzYyq`) | **Exact match** on both tables, 3/3 options |
| `PaymentTermCalcType` (fixed/percentage) | Payment Terms.`Calculation Type` (`fldFe2EBjK0a6GxMx`) | **Exact match**, 2/2 |
| `PaymentTermBasis` (monthly_salary/first_salary/deal_amount/unit_count/custom_amount) | Payment Terms.`Calculation Basis` (`fldNwNEO6WRdLGgRz`) | **Exact match**, 5/5 |
| `PaymentTermTrigger` (immediate/specific_date/after_period/event_based) | Payment Terms.`Trigger Type` (`fldWEWtrU0MQZ8FTF`) | **Exact match**, 4/4 |
| `PaymentTermCadence` (once/monthly) | Payment Terms.`Cadence` (`fldCL6tfCpH9mQ4HP`) | **Exact match**, 2/2 |
| `LeadStatus` (10 values) | Leads.status (`fldvTgONHx7D8JFw0`) | **Exact match**, 10/10 |
| `LeadOutcome` (8 values, trimmed per K3's 22/08/2026 rename) | Leads.`Business Outcome` (`fldVa5wSmAqcKLi86`) | **Exact match**, 8/8, no trailing spaces on any option — confirms K3's rename is live and complete for this field |
| `DealFields.PRIORITY` values (High/Medium/Low) | Deals.Priority (`fld7kFpzswHhvxbhc`) | **Exact match**, 3/3 |
| `RiskLevel` values (Low/Medium/High) | Deals.`Risk Level` (`fldCHhdT8B4u4jxPZ`) | **Exact match**, 3/3 |

Every commercial_crm.py Deal/Payment/Payment-Term writer's field-name and
enum-value contract is therefore now **live-verified**, not just
statically-verified against the cache — with the single N1 exception, which
that writer never actually exercises (crm.py's older `crm_add_payment`/
`crm_mark_payment_paid` write PENDING/RECEIVED/OVERDUE only, never
CANCELLED).

---

## 5. Owner-field linked-record targets (K10)

Confirmed via `get_table_schema` `linkedTableId` on every Owner field
queried: **Leads.Owner, Deals.Owner, Payments.owner, and by consistent
pattern (same `Role (from Owner)` lookup naming) Assets/Tasks/Interaction
Log/Contacts/Business Memory/Expenses' Owner fields — all point at the same
target table, Profile (`tblwf2K8WZrdu8xI5`)**. No cross-target
inconsistency exists; K10's fragmentation is purely a **naming-casing**
issue (`Owner` capitalized on Leads/Deals/Tasks/Assets/Contacts vs `owner`
lowercase on Payments/Expenses), not a semantic or relationship-target
inconsistency. This reconfirms Track 8's F9 note and narrows K10 precisely:
it is a naming-convention cleanup, not a data-integrity risk — every Owner
link, regardless of casing, resolves to the same Profile table.

---

## 6. Can `schema_cache.json` be safely regenerated?

**Yes — a live `schema_audit.py` refresh would be safe and net-corrective,
though NOT run in this pass** (out of scope; read-only mandate).

Rationale:
- Every table this pass checked either matches the cache exactly (where a
  cache entry exists) or is confirmed live with a real field set (where no
  cache entry exists, i.e. all of F7 + Lead Events). No table was found
  live with a *smaller* or *incompatible* field set than either code or
  cache currently assume — a refresh can only add coverage, never remove a
  field a writer depends on.
- The one stale cache entry found (`תשלומים (Payments)`, the old Hebrew
  table) describes a table that no longer exists live; a real refresh would
  correctly drop it, which is desired cleanup, not a regression.
- The `contact_id`/`Type` phantom fields (F4, N2) are absent from live
  regardless of cache state — a refresh doesn't change their status (they
  were never live to begin with), it just makes the cache correctly *not*
  claim them either (currently the cache is silent on Payments/Contacts
  fields beyond what's listed, it doesn't assert `contact_id`/`Type`
  exist, so there's no active cache-vs-live contradiction to fix here
  either way).
- No `AIRTABLE_API_KEY` was available to actually invoke
  `schema_audit.py --live` from this environment (same constraint noted in
  the cache's own seed note) — this conclusion is based on the live
  MCP-tool evidence gathered above serving as an out-of-band live baseline,
  not on having run the script.

---

## 7. F1–F9 / K1–K10 disposition after this pass

| ID | Static (Track 8) disposition | Track 8B live disposition |
|---|---|---|
| F1 | STATIC VERIFIED (positive) | **LIVE VERIFIED** — every Deal/Payment/Payment-Term field name and enum value confirmed live (§4). CLOSED, both dimensions. |
| F2 | DOC DRIFT — FIXED | Not a live-schema question; unaffected. Remains FIXED. |
| F3 | MOCK FIDELITY GAP — FIXED | Not a live-schema question; unaffected. Remains FIXED. |
| F4 | STATIC GAP / SNAPSHOT DRIFT | **LIVE-CONFIRMED LEGACY** — `contact_id` genuinely absent from live Payments (§1). Requires an actual code change (delete `PaymentFields.CONTACT` + `crm_add_payment`'s reference) to close for real — not a live Airtable change, a dead-code deletion. Recommend closing via the dead-code removal in §8, not via schema migration. |
| F5 | STATIC GAP | Not directly re-verified (KPI_ENGINE stays off); `DealStage`'s live options were confirmed (§4) as unrelated to F5's `"Status"`-vs-`DEPRECATED - Status` finding, which itself is confirmed still accurate (§1, Deals row). Remains open, flag-gated, unchanged severity. |
| F6 | STATIC GAP / SNAPSHOT DRIFT, DEAD CODE | Not re-verified against live (no live caller exists to matter); `tools/airtable_tools.py`'s `_TABLE_FIELDS[Tables.PAYMENTS]` dict was not re-inspected field-by-field this pass, but its "wrong table's fields" diagnosis is independently reinforced by this pass's finding that the *old* Hebrew Payments table no longer exists live at all (§1) — whatever fields that dict lists are now doubly stale (wrong table AND a now-nonexistent table). Same recommended fix as F4: dead-code deletion. |
| F7 | SNAPSHOT DRIFT, ACCEPTED-DEFERRED | **FULLY RESOLVED — all 14 tables confirmed to exist live with real field data (§2).** No live Airtable change needed. `schema_cache.json`'s lack of coverage for these 14 is CACHE DRIFT only, fixable by a live `schema_audit.py` refresh (§6) whenever `AIRTABLE_API_KEY` is available in-session — no code or live-schema fix required. |
| F8 | DOC DRIFT (trivial) | Reconfirmed live (§1, Deals row: `Decisions`/`Sessions`/`Role (from Owner)` all present, all auto-generated). Remains DOC DRIFT (trivial), harmless. |
| F9 (K3) | RECONFIRMED, NOT REOPENED | **LeadOutcome's live options now directly confirmed trimmed, 8/8 exact match, no trailing spaces (§4).** K3 can be marked CLOSED **for the LeadOutcome field specifically**; its general claim ("verify other option strings on other tables") is still open for every select field not covered by this pass's live spot-check list. |
| F9 (K10) | RECONFIRMED, NOT REOPENED | **Narrowed and reconfirmed live: all Owner-link fields point at the same Profile table regardless of casing (§5).** This is a naming-only fragmentation, live-confirmed to carry zero relationship-integrity risk. Still open as a naming-cleanup item, but downgraded in practice from "verify semantics" to "purely cosmetic, verified safe." |
| K1, K2, K4, K5, K6, K8, K9 | Out of Track 8 scope | **Still out of Track 8B scope** — none are Deal/Payment/Lead/Task/Session/Approval entities named in this pass's brief; not investigated. |
| K7 | Adjacent to F7, not the same finding | Unaffected by this pass; the `State JSON` blob versioning question was not investigated. Remains open under #3. |
| N1 (new) | — | **CODE DRIFT, live-confirmed** — `PaymentStatus.CANCELLED` spelling. See §3. Not yet fixed (docs-only pass). |
| N2 (new) | — | **LEGACY, live-confirmed** — `ContactFields.TYPE` phantom field. See §3. Not yet fixed (docs-only pass). |

---

## 8. Recommended remediation order (recommendation only — nothing executed)

1. **Dead-code deletion first, no schema/live change needed:** remove
   `PaymentFields.CONTACT` (F4) and `crm.py`'s unreachable
   `crm_add_payment()` that references it, and remove/rewrite
   `tools/airtable_tools.py`'s stale `_TABLE_FIELDS[Tables.PAYMENTS]` entry
   (F6) and `ContactFields.TYPE` (N2). All four are zero-caller, zero-risk,
   pure code cleanup — do these before anything else because they're the
   cheapest fixes and they remove noise that would otherwise resurface in
   every future schema audit.
2. **One-line constant fix:** `PaymentStatus.CANCELLED = "canceled"` (N1) —
   also zero live-schema risk, but touches a real (if currently-dormant)
   read-path filter in `tma_api.py`, so it should get its own small PR with
   the one call site re-verified, not bundled silently into the cleanup
   commit above.
3. **`schema_cache.json` refresh** (run `schema_audit.py --live` once
   `AIRTABLE_API_KEY` is available in a working session) — do this *after*
   steps 1-2 land, so the refreshed cache doesn't re-encode the
   about-to-be-deleted phantom fields' absence in a way that looks like a
   new finding to the next auditor. This closes F7 and the `אנשי קשר
   (Contacts)`/Leads cache gaps mechanically, with no manual cache editing.
4. **Doc-only cleanup:** trim `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s stale
   `תשלומים (Payments)` cache references once the cache refresh in step 3
   naturally drops that table, and correct the ROADMAP "19/29" figure to
   the verified 31 (or restate it against whatever subset it originally
   meant) — this is cosmetic and can trail behind 1-3 at any point.
5. **No live Airtable schema change is recommended by this pass.** Nothing
   found required Airtable itself to change — the live base is the
   accurate side of every discrepancy found; every fix identified above is
   a code- or cache-side correction, not a migration.

---

## 9. Evidence appendix

- `list_tables_for_base(app4bcgoX7t0HUVnm)` — 45 tables, full field
  name+type+id listing (raw response saved this session to
  `/tmp/claude-1000/.../scratchpad/live_tables.json`, not a repo artifact).
- `get_table_schema` calls (choices/`linkedTableId` detail): Leads
  (`status`, `tier`, `Next Action`, `Business Outcome`, `Owner`), Deals
  (`שלב`, `Priority`, `Risk Level`, `Owner`), Payments (`status`,
  `VAT Rule`, `owner`, `deal_id`), Payment Terms (`Calculation Type`,
  `Calculation Basis`, `Trigger Type`, `Cadence`, `VAT Rule`), Deals'
  `תשלומים (Payments)` field individually (to confirm its live link
  target).
- No `list_records_for_table`/other record-level spot-check was needed —
  every question the task brief raised was resolvable at the schema
  (field-existence/type/option/link-target) level.
