# MAINTENANCE_DEFERRED_REGISTER

**Created:** 23/08/2026 (docs-only; companion to [MAINTENANCE_STATUS_MATRIX.md](MAINTENANCE_STATUS_MATRIX.md))
**Baseline:** `origin/main` @ START_SHA `2b0c08e` — re-verify against END_SHA before acting on any row.
**Rule:** every item records why deferred, risk, reopen condition, runtime/deployment dependency. "OPEN ≠ IMPLEMENT" (`docs/governance/GAP_QUALIFICATION.md`). No code change is a valid successful outcome when recording is the correct action.

---

## Section R — Deferred remediation items from tracks A/B/C00–C08

| ID | Item | Why deferred | Risk | Reopen condition | Runtime/deployment dependency |
|---|---|---|---|---|---|
| R-C00-1 | worker.py deadline-nudge capability (NEEDS_PRODUCT_DECISION) | Unique useful behavior exists but unwired; whether product still wants push nudges now that TMA surfaces overdue tasks (pull-based) is an owner call | Low today (dormant); drift risk if scheduler evolves without deciding | Explicit owner decision: migrate to scheduler OR delete | None while dormant; migration would touch scheduler job registration + Render cron |
| R-C01-1 | M01 flag findings awaiting owner env decisions (`FEATURE_PA01_ENFORCEMENT_STATE=shadow.` invalid value; persistence/atomic child flags set while parent gateway flag absent) | M01's own no-deploy boundary: static audit must not change Render values | Invalid-value flag silently off; children active without parent gate → activation drift | Owner reviews Render env; then deploy + runtime verify | Render env-var change + redeploy |
| R-C01-2 | VOICE_IVR `/voice/step` ungated (asymmetric with `/voice/incoming`) | No-deploy boundary; feature default-off so exposure currently nil | If VOICE_IVR enabled, step endpoint runs ungated | Voice-feature activation work package | Render env + Twilio wiring |
| R-C05-9 | ActionContract orphan `draft` state | LOW severity, structurally unreachable | Cosmetic contract drift only | ActionContract schema cleanup cycle | None |
| R-C06-1 | Full bypass-baseline re-baseline (both audit scripts' BASELINE constants) | 23/08 refresh deliberately scoped to inventory only; line-tuple baselines make bulk reclassification noisy without per-entry diffing | Stale baselines keep producing false new/resolved signals (37 "new"/28 "resolved" plausibly line-shift noise) | Dedicated tooling pass; consider symbol-anchored baselines | Dev-side only; no deployment |
| R-C06-5 | Approval-clicker tenant match vs original requester (BUG-074) | Dormant in single-tenant deployment | Real authz gap once a second tenant exists | Any multi-tenant / F08 activation — hard precondition | Tenant model activation |
| R-C06-8 | identity.py fail-open vs documented hard-fail rule | Contract/doc mismatch; fallback is lowest-privilege (not exploitable) | Doc/code divergence confuses future agents | Documentation pass OR real hard-fail implementation decision | None (docs option) / identity path change (code option) |
| R-C06-10 | Scheduler game jobs direct mutation outside dispatcher/tool_registry | LOW — gamification data only; no requester identity exists in that context | Writer-coverage inconsistency, not business-data risk | Writer-coverage backlog pass | Scheduler job changes |
| R-C07-A2 | Interaction-generated Tasks (`scheduler.py` → `interaction_engine.run_interaction_scan()` → `create_tasks_from_analysis()`) | LOW — system/service actor performs a direct Tasks mutation through `tools.airtable_tools.airtable_add`; no requester or approval context is present | Policy decision required: route system-generated business Tasks through ActionGateway, define an explicit service policy, or retain a bounded exception | Owner/product policy decision, then a focused writer-coverage review | Potentially interaction_engine, scheduler, and the chosen policy boundary; no change in this docs-only PR |
| R-C07-6 | Three parallel approval-state representations reconciled by hand (EventBus / ActionContract / Airtable projection) | Requires architecture review; terminal-state protection currently solid (compare-and-set) | Hand-reconciled point-patches are drift-prone (BUG-SB-02/158/112 pattern) | Approval architecture review cycle | Potentially wide: event_bus, core/action_gateway.py, app.py patches |
| R-C07-US | `update_lead_status` owner-wait inconsistency (found during #847 PART 4) | Out of declared remediation scope ("exactly these two findings"); folding in would widen PR beyond stated boundary | Policy inconsistency within Leads family; both roles still go through approval there (not a security hole) | Next writer-coverage pass over TMA Leads endpoints | Same pipeline as PR #847 |

**24/08/2026 final C02–C04 recheck:** `R-C07-A2` remains the sole
policy-dependent Approval Coverage queue item. No duplicate deferred-register
entry was created; A1 remains a code item and is intentionally not listed here.

---

## Section D — EFFICIENCY & OPERATIONAL DEBT

Legend: **implemented** = merged on main · **exercised** = actually run against real usage · **measured** = numbers recorded. Implemented ≠ proved useful. Tests pass ≠ cost saved.

### D1 — Context Librarian token-estimation benchmark (N17 item 1)
- **Repo evidence:** `docs/context_librarian/TOKEN_ESTIMATION_BENCHMARK.md` ("script written, not yet executed"); `tools/context_librarian/benchmark_token_estimate.py`; ROADMAP N17 item 1.
- **Implemented:** yes (`chars/4` estimator + benchmark script). **Exercised:** no — never executed (sandbox lacked ANTHROPIC_API_KEY; script fails closed). **Measured:** no — divisor stays `4` per Rule 15.
- **Risk/cost:** every bundle budget number agents act on is an unvalidated heuristic; Hebrew text may deviate most from chars/4.
- **Next verification step:** run the benchmark with an API key; record results in TOKEN_ESTIMATION_BENCHMARK.md before touching the divisor.
- **Status:** NEEDS_MEASUREMENT.

### D2 — Context Librarian Phase-1 non-inferiority pilot
- **Repo evidence:** `docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md`; ROADMAP N17 §5 update (PR #483, merge `51d370b`).
- **Pilot executed:** partially — 2026-07-28 advancement ran all 5 pilot tasks Librarian-track vs independent Authority Gold Sets: **1/5 clean PASS; 4/5 with Medium→Critical discovery misses** (surfaced BUG-150, `_execute_contract` fail-open, BUG-130/140).
- **Non-inferiority demonstrated:** NO — Phase 1 acceptance explicitly not established; dual-vendor bundle-hash equality not performed.
- **Token savings measured:** NO. **Monetary savings measured:** NO.
- **Risk:** librarian mandated as bootstrap gate while its quality advantage is unproven; Critical-class misses occurred under it.
- **Next step:** dual-vendor acceptance runs per the pilot doc's fixed-comparison protocol; record per-run fields.
- **Status:** OPEN (acceptance pending).

### D3 — Real-consumption pilot & token/monetary savings measurement
- **Repo evidence:** absence — no consumption-measurement artifacts found on main under docs/context_librarian/ or ROADMAP N17.
- **Implemented/exercised/measured:** none.
- **Risk:** the central context-efficiency claim has zero recorded baseline or delta anywhere.
- **Next step:** minimal telemetry (bundle sizes, tokens actually read, task outcomes) across adoption windows.
- **Status:** OPEN / NEEDS_MEASUREMENT.

### D4 — Consumption Enforcement (N17 items 8→10)
- **Repo evidence:** plan PR #488 (`abf2804`, planning approved by owner); Phase 1 merged PR #490 (`7ee5c5b`) — sections 5.1-5.3+5.5+7 incl. `consumption_checklist()` + regressions. Note: plan doc header still says implementation blocked — stale vs #490 merge (original preserved).
- **Implemented:** Phase 1 yes. **Exercised:** CI/regression only; no recorded real-session consumption run. **Measured:** no effect/savings numbers.
- **Risk:** enforcement machinery unproven on real sessions.
- **Next verification step:** one live session consuming the checklist end-to-end; record misses/overrides.
- **Status:** NEEDS_RUNTIME_VERIFICATION.

### D5 — Dry-run estimation mode (librarian `estimate` subcommand)
- **Repo evidence:** ROADMAP.md:351; `estimate_bundle()`/`estimate_all_profiles()` verified present in `tools/context_librarian/librarian.py`; feature-flag-off; "Phase 2 enablement + consumption gating deferred".
- **Implemented:** yes. **Exercised/measured:** no production usage recorded.
- **Risk/cost:** low; idle capability.
- **Reopen condition:** Phase 2 enablement decision once D1 validates the divisor.
- **Status:** DEFERRED.

### D6 — Multi-session coordination (N17 item 5)
- **Repo evidence:** ROADMAP N17 §5 — planned-not-started; requirements recorded (ownership areas, bundle hash, stale/conflict detection, no process-local truth).
- **Implemented/exercised/measured:** none.
- **Risk:** concurrent agent sessions can collide undetected.
- **Dependency:** design-before-implement mandate; Turn Coordinator layering decisions.
- **Status:** OPEN (planning not started).

### D7 — Librarian dogfooding / Verification Coverage Model nodes (N17 item 6)
- **Repo evidence:** VCM plan merged PR #482 (`ffa678a`) → `docs/context_librarian/VERIFICATION_COVERAGE_MODEL_PLAN.md`; dogfooding nodes left as separate future task.
- **Implemented:** plan half only. **Exercised:** no self-knowledge nodes written.
- **Risk:** "what is built/verified in the librarian?" remains memory-answerable — the exact failure mode this repo prohibits.
- **Next step:** author nodes per VCM's six coverage dimensions.
- **Status:** DEFERRED (nodes); plan itself MERGED/CLOSED.

### D8 — Cost watchdog measurement (token/model-cost & usage attribution)
- **Repo evidence:** `cost_monitor.py` logs each Claude call (tokens_in/out, model, caller) with $ computation + hourly/daily limits; gated `COST_WATCHDOG_LIVE`, default off; M01 flags `COST_WATCHDOG_ENABLED` override precedence as undocumented READ_PATH_DRIFT.
- **Implemented:** yes. **Exercised:** flag-off → no production attribution stream. **Measured:** no spend/attribution report exists in repo.
- **Risk:** token/model-cost exposure unquantified; limits never proven live.
- **Next verification step:** staging enablement decision; document override precedence; produce one attribution report.
- **Status:** NEEDS_RUNTIME_VERIFICATION; enablement DEFERRED (owner).

### D9 — Session lifecycle debt (session_store / LeadSessions)
- **Repo evidence:** C05-C07 F4 fixed lead_draft persistence (PR #845); same finding documents LRU-eviction/restart loss as the failure class; broader persisted-vs-volatile field inventory does not exist on main; dedicated stale-LeadSessions audit: NOT FOUND in repo (recorded as UNKNOWN, not guessed).
- **Implemented:** partial (one field family). **Exercised:** regression tests only. **Measured:** n/a.
- **Risk:** other in-memory-only session state silently lost on restart/eviction.
- **Next step:** enumerate session_store fields; close or document each gap.
- **Status:** OPEN (inventory missing).

### D10 — Long-log / context-growth debt
- **Repo evidence:** searched docs/, ROADMAP, AI_CONTEXT, *.py for log-growth/rotation/context-size optimization debt — no dedicated repo artifact found (only unrelated F52 spec token-TTL text). Recorded UNKNOWN rather than inferred.
- **Implemented/exercised/measured:** unknown.
- **Risk:** unknown by definition — cannot be sized from repository evidence.
- **Next verification step:** if suspected, first create a repo-evidence inventory (log call-site volume, retention config) before any optimization claim.
- **Status:** UNKNOWN / OPEN (evidence absent).

### D11 — Deployed-SHA & canary gaps (HORIZON REAL CURRENT GAPS)
- **Repo evidence:** `docs/governance/HORIZON_STATUS_AND_NEXT_STEPS_AUDIT_20260821.md` §5-6: deployed SHA unknowable from repo; H6 `/api/owner/command-center` route canary pending; N18 full Draft→Approval→Write→Evidence chain lacks current-deployment canary. AI_CONTEXT "Next Priorities" adds H0 deploy of current SHA + N18 Phase 3 activation canaries (4 cutover flags off pending owner decision).
- **Implemented:** code merged (H6/N18 slices). **Exercised:** locally tested. **Measured:** no current-deployment runtime evidence.
- **Risk:** merged ≠ running; status claims rest on code+tests alone.
- **Next verification step:** deploy current SHA; run the three bounded canaries; reconcile source state.
- **Status:** NEEDS_RUNTIME_VERIFICATION.

### D12 — Memory durability & related blocked efficiency work
- **Repo evidence:** AI_CONTEXT "Blocked (Owner Decision)": Layer-2 TurnCoordinator formal class (de-facto replaced by router.py); memory durability blocks full lead-memory + learning activation; FINANCIAL_COMMITMENT_GATE shadow mode requires 7-14 days zero-FP validation.
- **Implemented:** partial/shadow. **Exercised/measured:** shadow-only; validation window not started/completed in repo evidence.
- **Risk:** RAM-only memory loss; financial gate unenforced (shadow logs only).
- **Reopen condition:** explicit owner decisions listed in AI_CONTEXT.
- **Status:** DEFERRED (owner-blocked) / FINANCIAL_GATE NEEDS_RUNTIME_VERIFICATION.

### D13 — Architecture Drift Map piggyback queue
- **Repo evidence:** `docs/governance/ARCHITECTURE_DRIFT_MAP.md` tracking table — 6×TODO (Emergency-Stop coverage P0, messaging facade P0, approvals canonicalization P0, task taxonomy P1, audit-event schema P1, Airtable read gateway P2), 1×DEFERRED (Google risk metadata, frozen), identity normalization smoke PASS 2026-06-14. Bodies intentionally not duplicated here (map is its own SSOT; do-not-autonomously-execute rule at map §"חשוב"). Note 23/08 file/drift pass: map row 1 (emergency /tmp persistence TODO) is now SUPERSEDED by the durable `evaluate_emergency_stop()` cutover (`feature_flags.py:260-281`) — status column in the map itself not yet updated.
- **Status:** DEFERRED (piggyback triggers must arrive organically).

---

## Section E — FILE / DRIFT / ARTIFACT PASS (23/08/2026, baseline `0e356ad`)

Full bodies live in **[MAINTENANCE_FILE_DRIFT_REGISTER.md](MAINTENANCE_FILE_DRIFT_REGISTER.md)**; summaries only here.

| ID | Item | Status | Future audit |
|---|---|---|---|
| E-F | Legacy/unwired module cluster: worker.py, knowledge_engine.py (+root router.py dead-chain), lead_qualifier.py (separate dead chain — correction: knowledge_engine does NOT import it), memory.py, profile.py, creative_generator.py, tenant_provisioner.py (test-only/parked), benchmark_token_estimate.py | OPEN / NEEDS_PRODUCT_DECISION (retirement-vs-wiring per module) — **RESOLVED / #12 CLOSED 25/08/2026**: 7 of 8 modules removed from main via PRs #909/#911/#915/#919/#922/#931 (+ an earlier worker-module removal); `tenant_provisioner.py` remains parked by owner decision, not a gap; `benchmark_token_estimate.py` remains parked (routed to #21, see next row). Historical per-module classification preserved above; per-file evidence in `MAINTENANCE_FILE_DRIFT_REGISTER.md` §F1 "Current disposition" column and `docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md`. | #12/#21 |
| E-A | Orphan-suspect tracked artifacts: `config.json`, `import_knowledge_base.json` (zero references repo-wide) | OPEN — **RESOLVED / #21 CLOSED 25/08/2026**: both removed (deletion commits `7a76754`, `97c256d`). Historical classification preserved above; see `docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md`. | #21 |
| E-G | Doc drift: CLAUDE.md:116 + ROADMAP F13 listed deleted core/tenant_config.py; AI_CONTEXT.md:66 cited nonexistent `*_CUTOVER` flag names; AGENTS.md self-stale lines; CONSUMPTION_ENFORCEMENT_PLAN header (=D4); AI_CONTEXT freshness lag | **RESOLVED / DOC DRIFT REMEDIATED** via #882, #893, #896, and this closure PR; historical records preserved | #19 |
| E-H | Code→docs gaps ×5: media result contract, WhatsApp ACK behavior, last_uploaded_file architecture (+dangling SPEC_File_Context_Reference.md citation at session_store.py:98), Media Files table responsibility, idempotency overview | OPEN (documentation work) | #20 |
| E-I | Naming debt: owner-field semantic fragmentation (12 constants); provider IDs funneled into "Telegram File ID"; hand-copied alias duplicates dispatcher/tma_api; English-schema migration plan never executed | **CLOSED IN #13 OWNED SCOPE** — cross-track items remain with #2, #3, and #20; no #13 remediation | #2/#3/#20 |
| E-J | Compatibility debt: llm_fallback load-bearing (keep); approval legacy values EXECUTED/LEGACY aging candidates; duplicate Media Files transcript writer bypassing media_gateway; memory.ConversationMemory zero importers | DEFERRED | #14 |
| E-K | Schema/data-contract follow-ups ×10 incl. FileUploadResult.file_id dual-table overloading; Media Files write-only identity columns; "Status" field hardcoded outside schema constants; State JSON unversioned blob | NEEDS_DEDICATED_AUDIT | #2/#3 |
| E-L | Media/file-ingestion: four-clause verdict **STILL HOLDS** (no stable logical key / durable Drive mapping / cross-process retry safety / metadata reconciliation on ingestion path). NEW: PR #859 fixed WhatsApp false-success ACK + adapter failure reporting (MERGED) | DEFERRED until media architecture work package | #3/#15/#16 |
| E-M | Missing historical artifacts ×6 re-checked: C00/C08 body, C02-C04 body (3 remediation docs exist; findings #2/#4/#5/#6/#9/#10 unevidenced), C04 idempotency inventory, LeadSessions audit, long-log audit, Approval_Policy_Spec.md (dangling refs ×3 docs) | UNKNOWN / MISSING ARTIFACT | — |

### Track F follow-up closure — 24/08/2026

Current statuses were re-verified against `origin/main` at
`7e38c8e4274285bb548e02830d8ef959148fb31a`:

- #4 Exception Taxonomy — **ALREADY CLOSED**.
- #15 Recovery / Fallback — bounded retry/idempotency finding **CLOSED / MERGED via #871**; broader recovery/reconciliation remains **DEFERRED ARCHITECTURE**.
- #16 Tool Contract — **ALREADY CLOSED**; known contract/data items remain cross-track.
- #5 Async / Concurrency — bounded voice STT retry finding **CLOSED / MERGED via #878**; process-local/shared-lock limitation remains **DEFERRED ARCHITECTURE**.
- #6 Scheduler — **DEFERRED ARCHITECTURE**; R-C06-10 retained with no demonstrated functional defect.
- #8 Test Gap — **ALREADY CLOSED**; placement concern is #12 only.
- #14 Deprecated Compatibility — **DEFERRED ARCHITECTURE**; active compatibility remains load-bearing.
- #19 Docs-to-Code — **CLOSED / DOC DRIFT REMEDIATED** after #882, #893, #896, and this G7 correction.

### #12 / #21 closure reconciliation — 25/08/2026

Docs-only pass reconciling this register's E-F/E-A rows (and
`MAINTENANCE_FILE_DRIFT_REGISTER.md`'s §F1/§F2/cross-reference table) against
current `origin/main`. Not a new audit — no new orphan candidates inspected,
no code changed.

- **#12 File / Folder Ownership** — **CLOSED**. 7 of 8 E-F cluster modules
  removed (see E-F row above for commits); `tenant_provisioner.py` remains
  parked by owner decision — not a live gap.
- **#21 Orphan Artifact** — **CLOSED for the identified orphan candidates**
  (unchanged verdict; `docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md:42`).
  `config.json`/`import_knowledge_base.json` removed (E-A row above);
  `review_diffs.txt`/`ledger-premerge-approval-ux.json` retained by design
  (never OPEN); `benchmark_token_estimate.py` remains parked, not a gap.
- **Out-of-scope, not resolved by this pass:** the `reports/` provenance
  question `MAINTENANCE_FILE_DRIFT_REGISTER.md`'s #21 cross-reference row
  mentions (hands ownership to #12 without its own closure statement) —
  recorded here only, not investigated.
