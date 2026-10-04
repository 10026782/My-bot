# Privacy Foundation — owner-of-record scoping (PRIV-FCC-01) — 04/10/2026

**Truth Reset:** `origin/main` = `d784ae67d07e3913b58561c56be10ad0f9c90136`. **Scope:** privacy foundation only — no Financial Goals/Events/screen/writer/schema. **Evidence level:** `STATIC_VERIFIED` (unit tests + CI-style local run). Not merged, not deployed, not runtime-verified.

Follows `docs/architecture/financial-control-center/FCC_MAPPING_REPORT_20261004.md` §0 (reference commit `f261526`, not on this branch).

## Root causes
| # | Exposure | Root cause |
|---|----------|-----------|
| P1 | manager/employee/owner read `Loans`/`Assets` via `airtable_get` | `enforce_tenant_scope` returned params unfiltered for every `is_internal` identity; no table/owner policy existed; raw `tbl…` ids would also dodge any name rule |
| P2 | `/api/assets*` returned every asset + totals to any owner / `"personal"` partner | endpoint gated by role/`allowed_domains` only; `Owner` link never consulted; PATCH had no record-ownership check |
| P3 | partner scoped by `Domain` only; partner `airtable_add/update` had no table restriction | partner branch handled `airtable_get` only; add/update fell to the internal pass-through |
| P4 | ownerless Task served to *every* owner | `_process_owner_tasks` / PATCH defaulted ownerless → requester, assuming a single owner |
| P5 | Profile resolved by case-insensitive name, `[0]` of up to 5 | no uniqueness check |
| P6 | no reusable "personal financial scope" primitive | business role was the only authorization concept |

## Access policy chosen — `core/data_access_policy.py` (single decision point)
* **business role ≠ personal authorization.** For an `OWNER_SCOPED` table (`Assets`, `Loans`) every actor — including `owner` — sees/changes only records whose `Owner` link contains their **own unique Profile record** (owner-of-record).
* **Fail closed:** no identity / external / Profile missing, ambiguous or lookup failed → denied; ownerless record → visible to nobody; unreadable record on update → denied; raw `tbl…` ids on generic paths → denied; reads of a policy table without a filter callback → refused (`airtable_tools.airtable_get`).
* `RECORD_MARKER` mode (Tasks): business tasks keep today's rules; a task marked private (`Visibility = Private`, **proposed, not yet in the live schema**) is visible only to its owner-of-record, ownerless private → nobody.
* **Ownerless business Tasks:** served to the requester only while they are the **sole** business owner in the identity registry (`identity.business_owner_user_ids()`); a second owner-role user flips this to deny. Preserves today's behaviour, no silent fan-out.
* **Profile resolution is strict** (`core/owner_resolution.resolve_profile_record_strict`): exactly one match, else `None` (reasons: `empty_id|not_found|ambiguous|lookup_failed`). The shared `resolve_profile_record_id` now uses it, so Leads/Tasks owner resolution also stops choosing a first row.
* Adding a protected table later (Financial Goals/Events) = **one entry in `_POLICIES`**.

Enforcement points (all call the same module): `airtable_security.enforce_tenant_scope` (runs first, every role, incl. partner) → dispatcher `airtable_get` (post-filter), `airtable_add` (owner-stamp / refuse foreign Owner), `airtable_update` (existing record must be visible); `tma_api` `/api/assets`, `/api/assets/<id>`, `PATCH /api/assets/<id>`, `/api/owner/my-work`, `PATCH /api/tasks/<id>`, project-dashboard/KPI task counts; `approval_actions.tma_write` (execution-time re-check for the frozen requester).

## Privacy matrix (this PR, unit-tested)
| Actor | Own asset/loan | Other owner's | Ownerless record | Private task of other | Notes |
|-------|:-:|:-:|:-:|:-:|-------|
| owner-self (eliyahu) | ✅ | ❌ | ❌ | ❌ | needs unique Profile row |
| owner-other (2nd owner) | ✅ own only | ❌ | ❌ | ❌ | hypothetical: registry today has 1 owner |
| manager | ✅ if owner-of-record | ❌ | ❌ | ❌ | was: all |
| employee | ✅ if owner-of-record | ❌ | ❌ | ❌ | was: all |
| partner (avi) | ✅ if owner-of-record | ❌ | ❌ | ❌ | domain no longer opens personal tables; business tasks by Domain unchanged |
| unresolved / ambiguous / external | ❌ | ❌ | ❌ | ❌ | 403 / refusal |

## Assets Owner backfill — DONE live (owner-approved 04/10/2026, data only, no schema change)
Method: Airtable MCP `update_records_for_table`, single field `Assets.Owner` (`fldFLgcPtJwk8JcJa`) ← Profile `Eliyahu` (`recKJvNFiTYMXKkwO`, Role=Owner). Pre-write listing and post-write re-read of all 9 rows; no other field touched.

| record | Name | Evidence | Result |
|--------|------|----------|--------|
| `recIZaIj5AQX4by2R` | קרקע ליפתא | Domain=Personal, Next Step Owner=אליהו | ✅ Owner=Eliyahu |
| `recrnyIjnRghHSszE` | בית קרית ספר | Domain=Personal, Next Step Owner=אליהו | ✅ |
| `rec4yxZIaQztHLZc3` | קרית ספר (קבוצת רכישה) | Domain=Personal, no contrary signal | ✅ |
| `recjyWS7QcMt5yILr` | קרקע יבניאל | Domain=Personal, no contrary signal | ✅ |
| `recxI3JGYnVK4N76Z` | בית שמש | Domain=Personal, no contrary signal | ✅ |
| `recXqelINKDD6OCEq` | נוף הגליל גדול | Personal, but Next Step Owner=אהרן, Ownership 50% | ⛔ HELD — not provably Eliyahu's |
| `recwTAkCyOlMiKl2U` | נוף הגליל קטן | same | ⛔ HELD |
| `recDO0mDpxbmqORpq`, `recoc7q79oMpIdkya` | (blank rows) | no name/domain/data | ⛔ HELD |

Counts: **updated 5, failed 0, held 4**. Consequence: until the owner decides the 4 held rows, `/api/assets` returns 5 assets for Eliyahu (the two נוף הגליל rows are hidden from everyone — fail-closed). Decision needed: assign them (Eliyahu / Ahron / co-owner model) or delete the blank rows.

Simulated route check on the live-shaped post-backfill data (no network): Eliyahu → 5 assets, total value = sum of the 5; Avi (partner, recruitment) → 403; Avi/Ahron with `personal` → 0 assets, total 0.

`Tasks`: 0/23 rows have `Owner` → all ownerless business tasks, served to Eliyahu as before (sole owner).

## Bypass audit (grep, `origin/main` + branch)
* `airtable_get` runtime callers: dispatcher (policy-wrapped), `cmd_update` (Business Memory), `interaction_engine` (Interaction Log), `tenant_provisioner` ("Tenants", unwired) — none can reach Assets/Loans/Tasks; the function itself now refuses policy tables without a filter.
* `enforce_tenant_scope` callers: dispatcher (get/add/update + crm_*), `commercial_crm` (Contacts/Charges), `airtable_tools.search_lead` — all pass through the new hook.
* `"Assets"` references: `tma_api` (3 routes, now scoped), `approval_actions._TMA_WRITE_ALLOWED_TABLES` (execution re-check added), gateway field map. `"Loans"`: none besides schema constant. `SCREEN_CONFIGS["assets_overview"]` is config only — no route consumes it.
* `Tables.TASKS` readers: my-work + PATCH (scoped), KPIs/dashboard counts (filtered), `crm._get` partner contact scope & `daily_digest._fetch` (partner → Tasks not in allowlist → raises), router/turn-coordinator task lookups (title match for the owner's own flows, no private marker exists yet).
* Table is never taken from request params in `tma_api`/`app` (`grep (args|json|form).get('table')` → 0).
* Raw table-id bypass (new finding, fixed): generic `airtable_get("tbl…")` would have skipped any name-based rule.

## Remaining gaps (not fixed here, deliberate)
1. **`REVIEW_REQUIRED_FOR_PERSONAL_FINANCE_SCOPE`** — `Payments`, `Expenses`, `Deals`: business ledgers, **unchanged by this PR (owner decision 04/10/2026)**; readable by manager/employee/owner through `airtable_get` (partner is domain-scoped). `/api/finance/pulse` is owner-only, not owner-of-record. When the Financial Control Center is built it may only *reference* a row of these tables when that row is authorized under its own table's policy; personal data must never be copied out of them into new tables to sidestep permissions.
2. **No live `Tasks.Visibility` (owner decision 04/10/2026).** The code marker (`TASK_PRIVATE_MARKER = ("Visibility", "Private")`) is inert placeholder support: the field does not exist and none will be created now, because 23/23 live Tasks have no `Owner` and an existing-task migration/classification policy must come first. In the FCC phase the owner decides the representation (Visibility / Scope / Task Type / an existing primitive); the placeholder name is not a commitment.
3. `IDENTITY_MAP` supplied in this task (Eliyahu=owner, Avi=partner/recruitment) was verified against the policy by tests; the live Render env is unverified.
4. `daily_digest` "done tasks" section for the owner is not owner-of-record scoped (single owner today).
5. Approvals list (`/api/approvals`) shows action labels with record ids only; not payload-scoped here.
6. `Profile` has a junk row ("ליד חדש") — harmless to unique matching, worth cleaning.
