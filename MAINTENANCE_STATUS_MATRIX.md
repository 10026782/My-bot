# MAINTENANCE_STATUS_MATRIX — Governance SSOT Consolidation

**Created:** 23/08/2026 (docs-only consolidation; no runtime code touched)
**START_SHA:** `2b0c08ed8782d6cafb02a1541036c9b74841ed34` (origin/main, fetched at session start)
**END_SHA:** `2b0c08ed8782d6cafb02a1541036c9b74841ed34` — closing fetch returned identical SHA; all status claims re-checked and valid against END_SHA.
**Re-baselined 23/08/2026 (file/drift pass):** main advanced to `0e356ad5a1f2abf9a05ac572c4fdfc249fa9a382` (merges #859 media-failure reporting + #860 this SSOT). Rows affected were re-verified against `0e356ad` and updated in place; original 23/08 morning text otherwise unchanged. File/module ownership, docs-drift, naming, orphan-artifact and schema follow-up findings: see [MAINTENANCE_FILE_DRIFT_REGISTER.md](MAINTENANCE_FILE_DRIFT_REGISTER.md).
**Method:** mandatory audit Truth-Reset — every status below was extracted from documents and merged history physically present on current `origin/main`; no chat-history or memory authority. All referenced PR/commit IDs were verified with `git merge-base --is-ancestor <sha> origin/main` on END_SHA day.

Deferred items live separately in **[MAINTENANCE_DEFERRED_REGISTER.md](MAINTENANCE_DEFERRED_REGISTER.md)** (including section **D — EFFICIENCY & OPERATIONAL DEBT**).

---

## Track ID warning (read first)

This matrix uses the **maintenance-audit series** semantics:
A = Env/Config, B = Dead Code, C00 = Route & Entry Points, C01 = Feature Flags,
C02 = Error Handling, C03 = Logging & Observability, C04 = Idempotency,
C05 = State Transitions, C06 = Permission & Ownership, C07 = Approval Coverage,
C08 = Import/Module Boundaries.

These are **NOT** the ROADMAP.md "C-numbers" CORE-component table (`ROADMAP.md:717-724`, where e.g. C04 = Feature Flags) nor the historical TC-era "Track A" (relative-date canonicalization, closed via PRs #581/#582). ROADMAP.md:139-141 itself records a prior C-number mapping conflict. Findings here are cited by content + document path, never by letter alone.

## Evidence levels

- **STATIC FINDING** — established from source/doc inspection only.
- **LIVE STRUCTURE CONFIRMED** — confirmed against live files/config/scripts re-run on main.
- **RUNTIME BEHAVIOR VERIFIED** — direct execution/deployment evidence exists.

Per GOVERNANCE_RULES.md Rule 15: nothing in this matrix is marked production-verified without production evidence. **Every row below is production-verified=NO unless explicitly stated otherwise.**

## Architecture decisions recorded in the repository

| Decision | Canonical record |
|---|---|
| **SINGLE BUSINESS WRITE PATH** — all meaningful business mutations enter through ActionGateway | `docs/governance/C05_C07_STATE_PERMISSION_APPROVAL_AUDIT_20260823.md` §DECISION (approved 2026-08-23) |
| **Owner uses canonical gateway path with no manual approval burden** — Owner never bypasses ActionGateway with a direct business write; identity/validation still run, then auto-approve/immediate execution with full contract+evidence+audit | same DECISION § owner policy; implemented by PR #847 (`_queue_or_owner_execute()`); regression `test_my_work_end_to_end.py:527` |
| **Root `worker.py` is legacy/unwired** — zero importers; `POST /worker/trigger` forwards `[system event]` to `run_agent()` and never calls worker.py; the Tasks-deadline push-nudge capability is a **future scheduler-migration decision**, not an active worker dependency (NEEDS_PRODUCT_DECISION) | `CLAUDE.md` "Background workers" (corrected 23/08/2026); `BUG_AUDIT_LOG.md` entry "C00-F1 — worker.py Truth-Reset + Survey-Worker Finding Closure"; PR #854 |
| **Mandatory audit Truth-Reset rule** — work from current `origin/main`, record START_SHA/END_SHA, never treat branches/memory/chat as authority | GOVERNANCE_RULES.md Rules 13-15; `docs/governance/HORIZON_STATUS_AND_NEXT_STEPS_AUDIT_20260821.md` protocol; applied by this document |

---

## Master status table (tracks A, B, C00–C08)

Status vocabulary: OPEN · CODE_DONE · MERGED · SUPERSEDED · DEFERRED · NEEDS_RUNTIME_VERIFICATION · CLOSED · UNKNOWN (evidence missing).

| Track | Finding / item | Original finding (short) | Current status | Evidence level | Remediation ref | Prod verified | Reopen condition |
|---|---|---|---|---|---|---|---|
| A | M01a dead env cleanup | Dead `OPENAI_FALLBACK_ENABLED` env read + unwired `tenant_config` env vars undocumented | **MERGED** | STATIC FINDING | PR #841 (`d089989`), commit `4c4df42` | No | — |
| A | Render flag invalid value | `FEATURE_PA01_ENFORCEMENT_STATE=shadow.` trailing period fails closed to `off` | **OPEN** (owner env decision) | LIVE STRUCTURE CONFIRMED | none (no-deploy boundary in M01 audit) | No | Fix requires deployment-side env change + runtime verification |
| A | Parent-flag drift | Render sets `FEATURE_ACTION_CONTRACT_PERSISTENCE=true`, `FEATURE_ATOMIC_CLAIMS=true` while parent `FEATURE_ACTION_GATEWAY` absent (default off) | **OPEN** (owner env decision) | LIVE STRUCTURE CONFIRMED | none | No | Same as above |
| B | dead-01 survey worker | `workers/survey_worker.py` orphan handlers, no callers | **MERGED / finding SUPERSEDED** | LIVE STRUCTURE CONFIRMED | PR #836 (`636aebd`), commit `2540eb3` | No | — |
| B | dead-02 tenant config | Dead tenant-config module on main | **MERGED** | LIVE STRUCTURE CONFIRMED | PR #851 (`0646ae3`) | No | — |
| B | FLASK_ROUTES_PATCH | Non-executable route-patch string in `voice_adapter.py` (routes already live in app.py) | **MERGED** | LIVE STRUCTURE CONFIRMED (URL map parity 43==43 vs main baseline) | PR #854 (`482e267`) | No (runtime-neutral docs/dead-string change) | — |
| C00 | C00-F1 worker.py truth-reset | worker.py unwired legacy; CLAUDE.md claimed it was the Render Cron target — stale | **MERGED** (docs truth-reset; capability decision DEFERRED → register R-C00-1) | LIVE STRUCTURE CONFIRMED (zero importers, grep on main) | PR #854 (`e116516`); `BUG_AUDIT_LOG.md` C00-F1; `CLAUDE.md:159` (line updated at re-baseline; was :155 pre-#860) | n/a — behavior unchanged | Deadline-nudge migration = explicit product/scheduler decision before any wiring or deletion |
| C00 | Full C00 route-audit body | Route & entry-point audit (10-finding series incl. core→app back-edges) | **UNKNOWN — body not preserved in repo** (chat-origin); only C00-F1 summary entry is on main | UNKNOWN | n/a | — | Re-run route/entry-point audit against current main if the full findings set is needed |
| C01 | M01 Feature Flag Consistency Audit | ~65-flag inventory; classifications NAME_DRIFT / READ_PATH_DRIFT / REGISTRATION_DRIFT / DEFAULT_DRIFT / DEAD_FLAG; 5 top findings | **AUDIT PRESERVED (MERGED)**; top findings OPEN pending owner decisions; safe-cleanup candidates partially executed (via #841) | MIXED: STATIC FINDING + LIVE STRUCTURE CONFIRMED (explicitly no runtime claims) | Doc: PR #842 (`a5c6716`,`b3882bd`); cleanup: PR #841 | No | Per-finding reopen when owner touches Render flags or scheduler registration |
| C01 | VOICE_IVR gate asymmetry | `/voice/incoming` flag-checked, `/voice/step` not (`app.py` voice routes) | **OPEN** | LIVE STRUCTURE CONFIRMED | none (no-deploy boundary) | No | Fix together with any voice-feature activation decision |
| C02 | Original C02–C04 audit body | Error-handling/idempotency audit (findings #1-#10) | **UNKNOWN — body not preserved in repo**; only #3, #7, #8 evidenced via remediation docs | UNKNOWN for unevidenced findings | n/a | — | Preserve original body if recovered; else re-audit |
| C02 | F3 swallowed gateway failure | `core/lead_service.create_lead()` caught ActionGateway exception and continued to direct Airtable write | **MERGED** | LIVE STRUCTURE CONFIRMED (re-confirmed at remediation time vs `0646ae3`) | PR #853 (`38a382c`); `docs/audit/C02_C04_REMEDIATION_1_FINDING_3.md`; tests `test_c02_c04_finding3_remediation.py`, `ea456d9` | No | — |
| C02 | F7+F8 sensitive payload logging | `media_handler.py` logged raw transcripts; `app.py` logged raw tool input/result around agent tool invocation | **MERGED** (content-bearing logs replaced with metadata) | LIVE STRUCTURE CONFIRMED (truth-reset vs `38a382c`) | PR #857 (`2b0c08e`); `docs/audit/C02_C04_REMEDIATION_2_FINDINGS_7_8.md`; test `test_c02_c04_findings_7_8_remediation.py` | No | — |
| C02 | F1 WhatsApp false-success ACK + silent adapter failures | Meta/Twilio media adapters returned success-shaped results on upload failure; ACK sent before processing outcome known | **MERGED** — ACK separated from processing status; both adapters now report failures (`6f74a71`, `9561ed6`, `d70a59f`) | LIVE STRUCTURE CONFIRMED (commits in main history at re-baseline) | PR #859 (merge `5f0763f`); `docs/audit/C02_C04_REMEDIATION_3_FINDING_1.md`; test `test_c02_c04_finding1_remediation.py` | No | Current-deployment canary of WhatsApp media failure path |
| C02/C04 note | Stale status lines in remediation docs | All THREE remediation docs say "not merged/not deployed" — written pre-merge; merges #853/#857/#859 happened later. Original text preserved per rule; actual merge state per git log | Documented here only | RUNTIME OF GIT HISTORY (merge commits verified ancestors of main) | see rows above | — | Update docs' status lines in a future docs PR (originals must not be rewritten retroactively) |
| C03 | Dedicated C03 track | Logging & observability audit | **UNKNOWN — no standalone C03 document on main.** Logging-sensitive-payload work landed under C02-C04 Remediation 2 (#857). RP4/RP5 evidence shadow remains gated off (`FEATURE_EVIDENCE_FINALIZER`) per AI_CONTEXT.md | UNKNOWN | n/a | No | Open a dedicated C03 audit if observability debt needs its own track |
| C04 | Idempotency inventory | Dedicated idempotency findings | **UNKNOWN — no preserved idempotency-specific inventory on main.** Related atomicity fixes exist under C05-C07 (#2 OTP race, #7 emergency window) | UNKNOWN | see C05/C06 rows | No | Re-audit required for a real C04 track |
| C05 | F2 OTP verify race | Unlocked check-increment-consume race on Critical approval gate (`core/otp.py:76-99`) | **MERGED** | LIVE STRUCTURE CONFIRMED | PR #845 (`f2030b0`, "C05-C07 FIX BATCH 1"); regression `test_otp_concurrency.py` | No | — |
| C05 | F4 lead_draft persistence gap | `session_store.set_lead_draft()` in-memory only; lost on restart/LRU eviction | **MERGED** | LIVE STRUCTURE CONFIRMED | PR #845 (`f2030b0`) | No | — |
| C05 | F7 emergency-window races | Non-atomic "no stacking"; `_auto_expire()` ignores patch result | **CODE_DONE/MERGED** — re-audit confirmed both claims, added lock + patch-return ERROR surfacing; feature dormant (zero live callers) | Upgraded to LIVE STRUCTURE CONFIRMED + race reproduced in harness | PR #849 (`4af1a39`); `test_emergency_window_concurrency.py` 12/12 | No (flag-gated off, no active entrypoint) | Becomes real-risk the moment anything wires `activate_window()` |
| C05 | F9 ActionContract orphan draft state | `status=="draft"` declared but unreachable | **DEFERRED** (LOW) | STATIC FINDING | none | — | See deferred register R-C05-9 |
| C06 | F1 LEGACY_WRITER bypass ecosystem | ~25+ modules write via gateway/dispatcher bypasses; tracking scripts stale (baseline 2026-07-03) | **OPEN / NEEDS_RUNTIME_VERIFICATION** — refresh run 23/08 (#849): dispatcher-bypass 51 sites (23 new vs baseline), gateway-bypass 25 sites all `[read]`, **zero direct Airtable writes outside gateway**; line-tuple baseline fragility discovered; full re-baseline deferred | LIVE STRUCTURE CONFIRMED (scripts re-run) | Refresh: PR #849; canonical writer list in `docs/governance/C05_C07_STATE_PERMISSION_APPROVAL_AUDIT_20260823.md` §REFRESH | No | Re-baseline both audit scripts' BASELINE constants; decide whether read-bypass flagging should be scoped out |
| C06 | F5 approval-clicker tenant match | Approver check lacks tenant match vs original requester (dormant, single-tenant today) | **DEFERRED** (must fix before multi-tenant/F08) | LIVE STRUCTURE CONFIRMED | none | — | Any multi-tenant activation |
| C06 | F8 identity fail-open | `resolve_identity()` never returns None; contradicts documented hard-fail rule | **DEFERRED** (fix docs or add real hard-fail path) | STATIC FINDING | none | — | Documentation pass or identity contract change |
| C06 | F10 scheduler game jobs direct mutation | Game jobs write via `_at_patch` outside dispatcher/tool_registry | **DEFERRED** (LOW, gamification data only) | STATIC FINDING (grep-confirmed) | none | — | Writer-coverage backlog |
| C07 | F3 DUPLICATE_APPROVAL_PATH | TMA owner-direct-write vs manager-full-approval split for identical actions (`patch_lead`, `set_lead_outcome`, `create_lead_task`) | **MERGED** (+ architecture decision) | LIVE STRUCTURE CONFIRMED | PR #847 (`ab49cc4`,`fc90d14`): shared `_queue_or_owner_execute()`; Owner auto-executes via `_claim_and_execute_approval()`, Manager unchanged | No — doc itself states "Runtime verification: NOT YET VERIFIED" | Current-deployment canary of the unified path |
| C07 | F6 three parallel approval-state representations | EventBus / ActionContract / Airtable Approvals projection reconciled by hand via point-patches | **DEFERRED** (architecture review) | STATIC FINDING | none | — | Approval-architecture review cycle |
| C07 | update_lead_status inconsistency (new during #847 PART 4 check) | After #847, Owner gets immediate execution on three Leads endpoints but still waits for manual approval on the fourth Leads PATCH endpoint | **DEFERRED** to writer-coverage backlog (preserved verbatim in C05-C07 doc's deferral section) | LIVE STRUCTURE CONFIRMED (at remediation time) | none | — | Next writer-coverage pass |

## Cross-track notes

- **C08 — Import/Module Boundaries:** no dedicated preserved audit body on main (**UNKNOWN** beyond C00-F1). Directly verifiable current-main fact observed during this consolidation (STATIC FINDING, new observation, not retro-fitted into any old audit): `tma_api.py:563` imports `_build_and_log_turn_envelope` from `app` inside a function — a core→app back-edge present at START_SHA **and re-confirmed at re-baseline `0e356ad`**. Recorded here so it is not lost; not counted as an old finding. Broader file/module ownership inventory: see [MAINTENANCE_FILE_DRIFT_REGISTER.md](MAINTENANCE_FILE_DRIFT_REGISTER.md) §F.
- **Preservation rules honored:** original audit texts were not edited by later fixes; remediations/decisions/re-audits were appended as separate dated sections (C05-C07 doc does this explicitly and states the rule). Remediation-doc status lines that predate their own merge are noted above rather than silently rewritten.
- **Evidence hierarchy used:** current origin/main code/tests > canonical governance docs > historical audit/planning text (per HORIZON doc protocol).
