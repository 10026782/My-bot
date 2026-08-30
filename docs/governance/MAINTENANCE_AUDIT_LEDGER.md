# MAINTENANCE AUDIT PROGRAM — AUTHORITATIVE HISTORICAL LEDGER

**Purpose:** authoritative historical-identity and final audit-program
reconciliation ledger for the numbered maintenance-audit program (#1–#24).
This is a reconciliation artifact, not a new audit.

**Authority boundary:** this ledger is authoritative for historical audit
identity and final program reconciliation only. It does not create a second
live operational SSOT. Current operational and deferred state remains owned by
`MAINTENANCE_STATUS_MATRIX.md`, `MAINTENANCE_DEFERRED_REGISTER.md`,
`MAINTENANCE_FILE_DRIFT_REGISTER.md`, and `docs/governance/HORIZON.md`; this
ledger records their reconciled program-level result and points back to them.

**Truth-reset basis:** `origin/main` @
`233dea50fdfa4418b502c09fcb49dda726fc8770` (26/08/2026).

## Namespace rules

The following namespaces are distinct and must not be silently equated:

- Audit IDs: #1–#24.
- Finding numbers: local to an audit or report.
- Maintenance slices: M01–M04.
- Later ownership: Track F, D-CORE, D-STRUCTURE.
- Maintenance audit series: C00–C08.
- PR numbers and commit hashes: Git history evidence only.

## Reconciled audit ledger

| ID | Historical identity | Decision / current disposition | Remediation / merge evidence | Deferred, cross-track, or runtime remainder | Terminal status |
|---:|---|---|---|---|---|
| #1 | Historical pre-track audit; original identity not recovered | No canonical name is asserted. Finding #1 “Scheduler Idempotency” is not treated as the audit identity. | No authoritative audit-specific closure record recovered | Historical provenance limitation only | HISTORICAL PRE-TRACK AUDIT — ORIGINAL IDENTITY NOT RECOVERED; NON-BLOCKING |
| #2 | Schema Drift | Static findings reconciled; no current static gap established | `BUG_AUDIT_LOG.md:23-32`; existing schema evidence | Live schema verification; reopen on live access or active schema/runtime change | CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION REMAINS |
| #3 | Data Contract | Current code gaps closed; I3 closed/static verified | PRs #1000, #1002, #1023; `BUG_AUDIT_LOG.md:52-70` | Finding #2 live/schema contract decision | CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION REMAINS |
| #4 | Exception Taxonomy | No current owned follow-up or regression | Maintenance status/deferred closure records | None | CLOSED / VERIFIED |
| #5 | Async / Concurrency | Bounded retry finding closed | PR #878; maintenance closure records | Process-local/shared-lock architecture | CLOSED / ACCEPTED DEFERRED ITEM REMAINS |
| #6 | Scheduler | No demonstrated functional defect | Maintenance closure records | R-C06-10 scheduler architecture | CLOSED / ACCEPTED DEFERRED ITEM REMAINS |
| #7 | CLI / Admin Tools | Owned CLI/admin findings closed | PRs #936, #939, #940, #943–#946; PR #930 for import safety | Routed items owned elsewhere | CLOSED / VERIFIED |
| #8 | Test Gap | Both current test gaps remediated and CI-enforced | PR #1024; `HORIZON.md` #8 closure | None | CLOSED / VERIFIED |
| #9 | Mock Fidelity | All four findings closed | PR #1017; `HORIZON.md` #9 closure | Broader test-gap handoff to #8 resolved by #1024 | CLOSED / VERIFIED |
| #10 | Dependency Risk | DG-1–DG-6 closed; no current HIGH/MEDIUM gap | PRs #1003, #1004, #1006 | DG-7/DG-8 LOW; package lifecycle/EOL external verification | CLOSED / ACCEPTED DEFERRED ITEM REMAINS |
| #11 | Security Surface | Static security gaps closed; CI guard present | PR #1014; `HORIZON.md` #11 closure | Production reachability remains unestablished | CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION REMAINS |
| #12 | File / Folder Ownership | Owned file/module findings closed | Existing F1/E-F evidence; Audit #18 reconciliation | `reports/` provenance owned by #12; explicit reopen triggers | CLOSED / ACCEPTED DEFERRED ITEM REMAINS |
| #13 | Naming Consistency | Closed in owned scope; no rename/schema migration owned here | Matrix Track #13 closure; drift register | Provider/data → #3; owner/schema → #2; docs → #20 | CLOSED / VERIFIED |
| #14 | Deprecated Compatibility | No current defect requiring removal | Maintenance closure records | Load-bearing compatibility architecture | CLOSED / ACCEPTED DEFERRED ITEM REMAINS |
| #15 | Recovery / Fallback | Bounded retry/idempotency finding closed | PR #871; maintenance closure records | Broader recovery/reconciliation architecture | CLOSED / ACCEPTED DEFERRED ITEM REMAINS |
| #16 | Tool Contract | No independent current gap | Maintenance closure records | Known contract/data items routed elsewhere | CLOSED / VERIFIED |
| #17 | UNKNOWN / UNASSIGNED | No primary source explicitly assigns an original identity to #17; later topic ordering is insufficient | No authoritative audit-specific execution or closure record recovered | Historical provenance limitation only | HISTORICAL IDENTITY NOT RECOVERED — NON-BLOCKING |
| #18 | SSOT Audit | All three findings closed/static verified | PRs #1008, #1009; `HORIZON.md` #18 closure | None | CLOSED / VERIFIED |
| #19 | Docs-to-Code | Owned doc drift remediated | PRs #882, #893, #896; current closure records | Historical G17 retained; I8 routed to #23 | CLOSED / VERIFIED |
| #20 | Code-to-Docs | H1–H6 and H9/O1–O6 documented | PR #1030, merge `15bad2e08129b96954dacfee442da7501f622040` | Production/deployed-SHA verification was not claimed and is outside the static Code-to-Docs scope | CLOSED / STATIC VERIFIED |
| #21 | Orphan Artifact | Identified orphan candidates closed | PR #1019 and orphan remediation inventory | `reports/` handoff → #12 acknowledged | CLOSED / VERIFIED |
| #22 | Performance Smell | P22-01 instrumentation complete; no current MEDIUM/HIGH owned static gap | PR #1031, merge `233dea50fdfa4418b502c09fcb49dda726fc8770`; instrumentation remains on main | Runtime measurement pending; P22-02 → #5; P22-03 LOW accepted | CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION REMAINS |
| #23 | Cost Audit | Current reachable paid-call accounting statically reconciled | Existing final closure capture on current main | Live usage/deployment/policy evidence | CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION REMAINS |
| #24 | Architecture Drift | Capability, execution-class, identity, context, and producer boundaries statically reconciled | PR #1028; existing final closure capture | Live deployment/execution-authority evidence; optional workflow correlation | CLOSED / STATIC VERIFIED — RUNTIME VERIFICATION REMAINS |

## Accepted deferred items

Accepted deferrals do not reopen their source audit and do not count as current
owned static gaps:

- #2: live schema evidence; reopen on live access or active schema/runtime change.
- #3: live/schema contract decision for Finding #2.
- #5: process-local/shared-lock architecture; revisit in the concurrency work.
- #6: R-C06-10 scheduler architecture decision.
- #10: DG-7/DG-8 LOW and package lifecycle/EOL external verification.
- #12: `reports/` provenance; owner #12, with the existing explicit reopen triggers.
- #14: load-bearing compatibility architecture.
- #15: broader recovery/reconciliation architecture.
- #22: runtime performance measurement; non-blocking for static closure.
- #24: optional workflow correlation.

All listed deferrals are **non-blocking** unless a future authoritative record
explicitly changes that decision.

## Terminal cross-track handoffs

Each handoff has one owning destination, a terminal disposition, and is not
counted open in both tracks:

- #22 P22-02 → #5 Async / Concurrency; acknowledged and disposition recorded.
- #24 recovery → #15, concurrency → #5, cost/accounting → #23, documentation → #20; destinations terminal or explicitly deferred.
- #13 provider/data semantics → #3, owner/schema semantics → #2, documentation → #20; terminal.
- #9 broader Test Gap → #8; resolved by #1024.
- #21 `reports/` provenance → #12; acknowledged/closed handoff.
- #19 I8 → #23; terminal.

## Runtime-only limitations

The following remain **RUNTIME VERIFICATION NOT ESTABLISHED** and are not
converted into static gaps: #2 live schema, #3 live/schema contract evidence,
#11 production reachability, #22 performance measurement, #23 live usage /
deployment / policy evidence, and #24 live deployment / execution-authority
evidence.

## Program closure result

- Namespace size: 24 audit IDs.
- Canonical identities recovered: 22 (all except #1 and #17).
- Historical identity-unrecovered slots: 2 (#1 and #17).
- Audits with terminal execution evidence: 22 (#2–#16 and #18–#24).
- Historical-only slots: 2 (#1 and #17).
- Closed: 22 audits, including those with accepted deferrals or runtime remainder.
- Open: 0 numbered audits based on current terminal evidence.
- Blocked: 0.
- Current HIGH gaps: 0.
- Current MEDIUM gaps: 0.
- Dangling handoffs: 0.
- Ownerless deferred items: 0.
- SSOT contradictions: 0 after this reconciliation.
- Unknown blockers: 0. #1 and #17 are historical provenance gaps, not current
  blockers.
- Current owned static engineering gaps: **0**.

This ledger does not claim production verification and does not replace the
individual historical audit bodies.

## Track 8 — Schema / Data-Contract Reconciliation (30/08/2026)

Not one of the numbered audits #1–#24 (namespace closed above at 24) — a
separate, later "Track" identity, same category as Track F/D-CORE/D-STRUCTURE
in the Namespace rules. Requested as the dedicated static audit that #2/#3's
Accepted Deferrals and `MAINTENANCE_FILE_DRIFT_REGISTER.md` Section K
(K3/K6/K9/K10) had been waiting on. Static-only: no live Airtable access, no
`schema_cache.json` regeneration, no runtime behavior change beyond two
LOW-risk docs/test commits (see below).

**Truth-reset basis:** `origin/main` @ `b238379ac2f8d42806df34c4a691c8c85f516537`
(30/08/2026) — the commit the Canonical Deal/Payment Architecture track
(Payment Terms table, Deals/Payments field additions, `commercial_crm.py`)
landed on.

**Terminal status: `CLOSED / STATIC VERIFIED / LIVE VERIFICATION NOT ESTABLISHED`.**

| ID | Finding | Severity | Classification | Current impact |
|---|---|---|---|---|
| F1 | `commercial_crm.py`'s Deal/Payment-Term/Payment writers: every field constant resolves against `schema_cache.json`; all linked-record fields written as record-ID lists, never display-name strings | — | STATIC VERIFIED (positive) | Confirms ROADMAP's SCHEMA_DATA_CONTRACTS 30/08/2026 claims independently |
| F2 | `smoke_tests.py`'s `OLD_TABLE_NAMES` sentinel treats literal `"Payments"` as purely legacy, but `Tables.PAYMENTS` is now also the canonical English live table for the new track, distinct from the Hebrew `תשלומים (Payments)` table | LOW | DOC DRIFT — **FIXED** | Comment-only clarification; AST check only flags hardcoded literals, not `Tables.PAYMENTS`, so behavior unaffected |
| F3 | `test_commercial_crm.py`'s original 54 tests asserted only internal contract consistency (constant in → same constant out of the mock), never truth against `schema_cache.json` | LOW | MOCK FIDELITY GAP — **FIXED** | 43 new snapshot-fidelity checks added (97/97 passing) |
| F4 | `PaymentFields.CONTACT = "contact_id"` (used only by `crm.py:crm_add_payment()`) is absent from the live-cached `Payments` (English) field list | LOW (would be MEDIUM if reachable) | STATIC GAP / SNAPSHOT DRIFT | `crm_add_payment()` confirmed unwired — zero references in `tool_registry.py`/`tools/dispatcher.py`/`tools/schemas.py`; called only from tests/scripts. No live agent path exercises it |
| F5 | `data_engines._basic_kpi()` filters `Tables.DEALS`/`Tables.PAYMENTS` on a literal `"Status"` (renamed to `DEPRECATED - Status` on Deals; wrong case on Payments) and Leads on tier values `"HOT"`/`"WARM"` (live options are Hebrew) | LOW (would be MEDIUM if enabled) | STATIC GAP | `KPI_ENGINE` flag defaults off (no `_DEFAULTS` override) — matches CLAUDE.md's documented "intentionally blocked" status for `data_engines.py` |
| F6 | `tools/airtable_tools._TABLE_FIELDS[Tables.PAYMENTS]` holds the OLD Hebrew `תשלומים (Payments)` table's field set, not the new canonical English `Payments` table's fields | LOW | STATIC GAP / SNAPSHOT DRIFT, DEAD CODE | `_sanitize_fields()`, the sole consumer, has zero callers anywhere in the repo (grep-confirmed) — inert unless revived |
| F7 | 14 of the 29 tables `schema_audit.py`'s own `TABLE_CLASS_MAP` covers (Sessions, ActionContracts, Business Memory, Profile, Ventures, Expenses, Decision Events, Decisions, Decision Inbox, Decision Stakeholders, Marketing Demand, Marketing Publications, Emergency Stop Flags, External Execution Jobs) have zero field data in `schema_cache.json` | MEDIUM (in principle) / ACCEPTED-DEFERRED (in practice) | SNAPSHOT DRIFT | `schema_validator.validate_fields()` is a total no-op for writes to any of these 14 tables. **Confirmed pre-existing, not a regression from the 30/08/2026 commercial_crm.py commit** — `git show 28a44c0:schema_cache.json` shows the cache was already 17/19 partial before that commit added 2 more tables |
| F8 | Live `Deals` fields `Decisions`, `Sessions`, `Role (from Owner)` not modeled in `DealFields` | INFO | DOC DRIFT (trivial) | Confirmed harmless — auto-generated inverse-link/lookup fields, no writer targets them |
| F9 | K3 (LeadOutcome trailing-space) and K10 (owner-field fragmentation) from `MAINTENANCE_FILE_DRIFT_REGISTER.md` Section K | — | RECONFIRMED, NOT REOPENED | K3's hardening unchanged; K10's fragmentation pattern unchanged, with one new confirmed instance: `PaymentFields.OWNER="owner"` (lowercase) vs `DealFields.OWNER="Owner"` (capitalized) — both individually correct against their live-cached tables, naming inconsistency itself not resolved. See `MAINTENANCE_FILE_DRIFT_REGISTER.md` Section K for the full K1–K10 disposition table |

**Closure basis:** no owned MEDIUM/HIGH static contract gap remains (F4–F6 are
LOW-severity and unreachable/flag-off; F7 is a pre-existing, already-accepted
snapshot limitation under #2/#3, not new). Snapshot/mock reconciliation for
the new Deal/Payment/Payment-Term contract passes (F1, machine-verified by
F3's added tests). All tests pass: `test_commercial_crm.py` 97/97,
`test_airtable_gateway.py` 37/37, `smoke_tests.py` all-pass,
`schema_audit.py --offline` run as the primary static-diff instrument.

**Live verification backlog (explicitly NOT closed by static evidence):**
- Full live schema/cache refresh for the 14 tables in F7.
- Exact live select options for the Deal/Payment/Payment-Term enums
  (`PaymentTermCalcType`, `PaymentTermTrigger`, `PaymentTermCadence`,
  `VATRule`, `PaymentTermBasis`, `DealStage`, `PaymentStatus`) — the
  checked-in cache is name-only by design and cannot carry this.
- Live relationship/type verification anywhere the snapshot cannot encode
  field type or a linked field's target table.
- Whether `Tables.LEAD_EVENTS` ("Lead Events") has actually been created live
  — the inline comment says "create manually before use" while
  `lead_capture.py`/`core/lead_event_writer.py` actively write to it; this
  tension is unresolved from repo state alone.

None of the above are converted into static defects — they remain LIVE
VERIFICATION REQUIRED, same disposition as #2/#3's existing runtime remainder.

**Evidence:** commit `9ebaa1e` (this worktree, local/unpushed) — the two
LOW-risk fixes (F2, F3). Full findings detail and reconciliation method: see
this session's Track 8 audit report (not itself a repo artifact).

**Not closed by this pass:** F4/F6 (dead/stale code paths) remain
unremediated by design — fixing them touches canonical writer behavior
(`crm.py`) or a validation dict (`tools/airtable_tools.py`), both outside a
static-audit's Remediation Gate. Separate, explicitly-approved slices only.

## Track 8B — Live Airtable Schema Reconciliation (30/08/2026)

Follow-on to Track 8, closing its explicitly-deferred "live verification
backlog" using read-only live Airtable MCP access (`list_tables_for_base`,
`get_table_schema` — no mutating tool ever called; no code file changed;
`schema_cache.json` not regenerated). Distinguishes two separate
verification dimensions from here on: **STATIC VERIFIED** (Track 8, true
since 30/08/2026) and **LIVE SCHEMA VERIFIED** (Track 8B, also true since
30/08/2026) — the two are not the same claim and this ledger no longer
conflates them.

**Terminal status: `CLOSED / STATIC VERIFIED + LIVE SCHEMA VERIFIED (31/31 mapped tables)`.**

Full table-by-table evidence, F7's individual 14-table resolution, the
enum/select-option live verification for the Deal/Payment/Payment-Term
contract, and two new live-only findings (N1: `PaymentStatus.CANCELLED`
spelling drift vs live `canceled`; N2: `ContactFields.TYPE` phantom field)
are in the dedicated report:
[`TRACK_8B_LIVE_SCHEMA_RECONCILIATION_30082026.md`](TRACK_8B_LIVE_SCHEMA_RECONCILIATION_30082026.md).

Headline resolution of F7: **all 14 tables it named (Sessions,
ActionContracts, Business Memory, Profile, Ventures, Expenses, Decision
Events, Decisions, Decision Inbox, Decision Stakeholders, Marketing Demand,
Marketing Publications, Emergency Stop Flags, External Execution Jobs)
exist live**, with real field sets that match code (11/14 exact 1:1,
3/14 with only auto-generated extra fields). None were missing or
misconfigured. Root cause confirmed as operational (no full live
`schema_audit.py` run has ever completed in-session, per the cache's own
seed note), not a scope gap in `schema_audit.py` itself. `Tables.LEAD_EVENTS`
("Lead Events") — a separate open question from F7 — is also confirmed to
exist live (8/8 exact field match), closing that question definitively.

F4 (`PaymentFields.CONTACT = "contact_id"`) and F6
(`tools/airtable_tools._TABLE_FIELDS[Tables.PAYMENTS]`) are now
**live-confirmed as genuinely dead** (no such live field/table backs them);
both remain open pending the same dead-code-deletion slice Track 8 already
deferred — this pass adds live confirmation, not a new remediation path.
K3 is closed specifically for the `Leads.Business Outcome` field (8/8 live
options confirmed trimmed, no trailing spaces); its broader "verify other
tables' option strings" claim stays open. K10 is narrowed: every Owner-link
field across every table checked resolves to the same live Profile table
regardless of `Owner`/`owner` casing — live-confirmed as a naming-only
issue with zero relationship-integrity risk.

`schema_cache.json` can safely be regenerated by a live `schema_audit.py`
run whenever `AIRTABLE_API_KEY` is available in-session (see the report's
§6 for rationale) — not run this pass, read-only mandate.

## Track 8C — Cache + Code Cleanup (30/08/2026)

Remediation follow-on to Track 8B: unlike 8/8B (audit/docs-only), this slice
makes real code changes to close the specific code- and cache-side gaps
Track 8B identified as safe to fix. Read-only Airtable MCP access only
(`list_tables_for_base` against `app4bcgoX7t0HUVnm`) — no mutating Airtable
tool ever called.

**Terminal status: `CLOSED / F4 + F6 + N1 + N2 REMEDIATED`.**

1. **`schema_cache.json` regenerated** from a fresh `list_tables_for_base`
   pull (45 live tables, same field-name-only shape the file already used).
   The stale `תשלומים (Payments)` entry (7 fields, describing a table Track
   8B confirmed doesn't exist live) is gone — it was dropped naturally by
   the regeneration, not special-cased. This mechanically resolves F7's
   remaining "cache never captured these 14 tables" gap and the
   `אנשי קשר (Contacts)`/Leads cache-staleness Track 8B flagged as the
   largest gap in that pass.
2. **F4 CLOSED (`PaymentFields.CONTACT`):** deleted the `CONTACT = "contact_id"`
   constant (`airtable_schema.py`); removed the dead `contact_id` param and
   its field-write from `crm.py`'s `crm_add_payment()` (still zero
   dispatcher/registry callers — reconfirmed by grep before deleting);
   removed the one test (`test_audit3_findings3_6_contracts.py`) that
   exercised the phantom field, since it was testing behavior tied to a
   field that never existed live.
3. **N2 CLOSED (`ContactFields.TYPE`):** deleted the `TYPE = "Type"` constant
   — grep reconfirmed zero usages anywhere in the repo (not even tests)
   before deleting.
4. **N1 CLOSED (`PaymentStatus.CANCELLED` spelling):** changed
   `"cancelled"` → `"canceled"` to match the live single-select option.
   Grepping `"cancelled"` (double-L) after the fix surfaced one other
   live-relevant hit beyond the already-known `tma_api.py:2251` read-path
   compare (which is fixed automatically since it references the constant):
   `tma_api.py`'s `finance_pulse` `SCREEN_CONFIGS["active"]["exclude_statuses"]`
   list held a hardcoded `"cancelled"` literal used to build the actual
   Airtable `filterByFormula` — this was a second, previously-undocumented
   instance of the same live bug (the "active" view's exclude-canceled
   filter silently never matched), now fixed alongside it. Every other
   `"cancelled"` grep hit is unrelated prose/enum values in the
   message-contract/approval-lifecycle system, not this Airtable field —
   left untouched per the task's explicit scope boundary.
5. **F6 CLOSED (`tools/airtable_tools.py` dead code):** `_sanitize_fields()`
   (and its supporting `_TABLE_FIELDS` dict and module-local
   `_ALWAYS_FORBIDDEN` set, both used only by it) had zero callers
   repo-wide (grep-confirmed) — deleted the whole dead path rather than
   leaving an unreachable function with a stale/wrong Payments field list
   behind. The now-unused `Tables` import was also removed.
6. **K10-adjacent stale alias removed (judgment call, see below):**
   `tools/dispatcher.py`'s local `_ALIAS_MAP` had `"Payments": "תשלומים
   (Payments)"` — mapping the live alias key "Payments" to a table Track 8B
   confirmed no longer exists. Traced every consumer of this map
   (`real_t` in the dedup-field lookup, and two `== "אנשי קשר (Contacts)"`
   branch checks) and confirmed none of them produce a different result for
   Payments with the entry removed — the actual Airtable write calls
   (`airtable_add(table, fields)` / `airtable_update(...)`) use the raw
   `table` string, not this map, and go through the separate canonical
   `airtable_schema.TABLE_ALIASES` (already correctly `"Payments" ->
   Tables.PAYMENTS == "Payments"`). Removed the entry (functionally a
   no-op today, but stops a stale/wrong value from sitting in a map whose
   own comment says it mirrors the canonical source of truth). The other 4
   entries (Tasks/Contacts/Deals/Expenses → their Hebrew live names) were
   left untouched — Track 8B confirmed those Hebrew tables still exist
   live, so those aliases remain correct, active migration-compat logic.

**Tests:** `schema_audit.py --offline` (no CONTACT/TYPE/CANCELLED-related
mismatch; pre-existing DOC-DRIFT gaps unchanged), `smoke_tests.py`,
`test_commercial_crm.py` (97/97), `test_airtable_gateway.py` (37/37),
`test_audit3_findings3_6_contracts.py`, `test_f15_crm_write_migration.py`,
`test_preview_content_fix.py`, `test_f14_b2_contact_integration.py`,
`test_f52_g1_execution_proof.py`, `test_bug_approval_callback_hardening.py`,
`test_f14_contact_gate.py`, `test_integration.py` — all pass. `py_compile`
clean on every edited file.

**Evidence:** commit `0f1bcd4` (this worktree, local/unpushed at time of
writing).

**Post-push CI addendum:** PR #1129's `backend-ci` run caught one real
regression the local test sweep above missed —
`test_runtime_schema_provider.py`'s "seed/cache contract alignment" block
(added by `28a44c0`, "Schema Drift #1: align Airtable seed cache with
current contract", closing `BUG_AUDIT_LOG.md`'s Audit #2 Finding #1)
asserted *exact* set equality between `schema_cache.json`'s Leads/Assets/Media
Files entries and the corresponding `*Fields` constants — a check that only
held because that cache had, until this Track, always been a hand-typed
mirror of the code contract (`"note": "seed — run schema_audit.py to refresh
from live Airtable"`), never an actual live pull. Regenerating the whole file
from live truth (item 1 above) legitimately introduced extra fields on those
3 tables — the same auto-generated link/lookup columns already classified
SAFE/EXPECTED for every other table in Track 8B/`schema_audit.py`'s
`missing_from_code` bucket — which the strict equality check had no way to
distinguish from a real regression. Fixed by narrowing the assertion to what
actually matters for the seed tier's job (feeding
`schema_validator.validate_fields()`'s unknown-field gate): extra cache
fields never cause a false rejection, only *missing* ones would, so only "no
missing fields" remains a hard check; "cache == contract" / "no stale extras"
are removed as an artifact of the old hand-seeding process, not a real
invariant. Fixed in this same commit.

Also surfaced by the same CI run, and explicitly **not** fixed here as
out of scope: `test_bug153_create_task_reconfirmation_after_rejection.py`
fails identically (3/16 sub-checks) on a clean `origin/main` checkout
(confirmed via a throwaway worktree at tip `8574e9a`) — a pre-existing,
already-broken-on-`main` approval/task-reconfirmation test unrelated to
schema/Airtable and untouched by this Track. `origin/main`'s own recent CI
runs are red for the same reason. Flagged for separate triage; not this
Track's scope.
