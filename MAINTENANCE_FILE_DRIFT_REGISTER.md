# MAINTENANCE_FILE_DRIFT_REGISTER

**Created:** 23/08/2026 (docs-only FILE / DRIFT / ARTIFACT pass; no runtime code touched)
**Baseline:** `origin/main` @ START_SHA = END_SHA = `0e356ad5a1f2abf9a05ac572c4fdfc249fa9a382` (closing fetch identical; all claims valid against it).
**Companions:** [MAINTENANCE_STATUS_MATRIX.md](MAINTENANCE_STATUS_MATRIX.md) · [MAINTENANCE_DEFERRED_REGISTER.md](MAINTENANCE_DEFERRED_REGISTER.md) (short summaries there; full bodies here only).
**Method:** mandatory Truth-Reset; consolidation of findings ALREADY surfaced across maintenance audits, remediation docs, governance docs and merged PR history — no new broad code audit. Every path cited was verified to exist at this commit. Originals preserved; later changes recorded as separate notes. "No importer found" ≠ safe to delete. Generated ≠ orphan. UNKNOWN preferred over guessing.

Status vocabulary: OPEN · DEFERRED · UNKNOWN · DOC_DRIFT · SUPERSEDED · NEEDS_DEDICATED_AUDIT · NEEDS_PRODUCT_DECISION · NEEDS_RUNTIME_VERIFICATION · CLOSED.

---

## Section F — FILE & MODULE OWNERSHIP DEBT

### F1 — Legacy / unwired module cluster (all STATIC FINDING unless noted; zero runtime importers verified by bare+relative import grep)

| Module | Importer/caller evidence | Classification | Status | Future audit | Current disposition (25/08/2026) |
|---|---|---|---|---|---|
| `worker.py` (root) | 0 imports; `/worker/trigger` (`app.py:6800`) forwards `[system event]` to `run_agent()` and never calls it; `schedule_background_worker` defined `worker.py:153`, zero call sites | LEGACY UNWIRED (documented `CLAUDE.md:159`; BUG_AUDIT_LOG C00-F1) | NEEDS_PRODUCT_DECISION (= R-C00-1) → **RESOLVED / #12 CLOSED** (module removed; decision moot) | #12 | REMOVED (deletion commit `6b8573b`) — **#12 CLOSED**; per-file product decision moot (module no longer exists). See `docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md`. |
| `knowledge_engine.py` (root) | 0 importers repo-wide (only a comment at `tools/audit_result_parsing.py:15`); imports root `router.py`; `KNOWLEDGE_ENGINE` flag default-off | LEGACY UNWIRED / ORPHAN SUSPECT; C95A recommends formal retirement ("C98"), superseded functionally by `core_knowledge.py` + `cmd_update.get_recent_business_context()` | OPEN (retirement decision) → **RESOLVED / #12 CLOSED** (module removed; decision moot) | #12 | REMOVED (deletion commit `b393313`) — **#12 CLOSED**. |
| `router.py` (root, 342B) | Exactly 1 importer: `knowledge_engine.py:4` — itself dead. NOT the same file as `core/router/router.py` (package) | DEAD-CHAIN MEMBER (drags root router down with it) | OPEN (decide together with knowledge_engine) → **RESOLVED / #12 CLOSED** (module removed; decision moot) | #12 | REMOVED (deletion commit `48efa3f`) — **#12 CLOSED**. |
| `lead_qualifier.py` (root) | 0 real importers (24 grep hits are comments/string literals/enums). **Correction to earlier belief:** knowledge_engine does NOT import it — these are TWO separate dead chains, not one chain | LEGACY UNWIRED (F09 built-not-wired; `ROADMAP.md:2134-2137,2316` states "לא מחובר לפרודקשן") | OPEN (wiring or retirement = product call) → **RESOLVED / #12 CLOSED** (module removed; decision moot) | #12 | REMOVED (deletion commit `8b4a89d`) — **#12 CLOSED**. |
| `memory.py` (root, 992B) | 0 importers; referenced only from `archive/boss_bot_summary.md` | ORPHAN SUSPECT (superseded by session_store/memory_store) | OPEN | #21 | REMOVED (deletion commit `4ff9604`) — **#21 CLOSED**. |
| `profile.py` (root) | 0 importers | LEGACY UNWIRED (documented parked, `CLAUDE.md:116`) | DEFERRED (parked) → **RESOLVED / #12 CLOSED** (module removed; decision moot) | #12 | REMOVED (deletion commit `cb0e0ff`) — **#12 CLOSED**. |
| `creative_generator.py` | 0 importers (it consumes llm_fallback, not vice versa) | LEGACY UNWIRED (flag-gated) | DEFERRED (parked) → **RESOLVED / #12 CLOSED** (module removed; decision moot) | #12 | REMOVED (deletion commit `72b91dc`) — **#12 CLOSED**. |
| `data_engines.py` | 0 importers; self-referential importlib demo `:302-304` | INTENTIONALLY PARKED STUB (F02/F03/F04 blocked pending data) | CLOSED (by design) | — | OUT-OF-SCOPE for this pass (not routed to #12/#21; already CLOSED by design at original baseline, unchanged). |
| `tenant_provisioner.py` | Only importer is `test_response_contract_fixes.py` | TEST-ONLY + DOCUMENTED PARKED ("needs to stay parked — business/model decision", POST_N15 survey :129) | DEFERRED (owner-blocked) | #12 | PARKED BY OWNER DECISION (re-verified 25/08/2026: still test-only import) — **no live #12 gap**. |
| `tools/context_librarian/benchmark_token_estimate.py` | 0 importers, no non-test references | ORPHAN SUSPECT (one-off benchmark; ad-hoc agent use possible) — see also D1 measurement debt | OPEN | #21 | PARKED — intentional manual verification tool (re-verified 25/08/2026: only a file-path string in `tools/context_librarian/librarian.py`'s allowlist, not a functional import) — **not a live #21 gap**. |

### F2 — Orphan-suspect tracked artifacts

| Artifact | Evidence | Classification | Status | Current disposition (25/08/2026) |
|---|---|---|---|---|
| `config.json` (root, 1.5K) | ZERO references repo-wide (keys `bot_settings`/`free_commands` appear nowhere else; unrelated to `config.py`) | POSSIBLE ORPHAN (intent UNKNOWN — planned loader never built?) | OPEN | REMOVED (deletion commit `7a76754`) — **#21 CLOSED**. |
| `import_knowledge_base.json` (root, 4.6K) | ZERO references repo-wide (incl. docs/, archive/) | POSSIBLE ORPHAN | OPEN | REMOVED (deletion commit `97c256d`) — **#21 CLOSED**. |
| `review_diffs.txt` (root, 29K) | Dated 2026-05-28 diff dump; sole live ref `docs/governance/ARCHITECTURE_DRIFT_MAP.md:3` | HISTORICAL EVIDENCE | KEEP (evidence) | HISTORICAL EVIDENCE, retained by design — **not an #21 gap** (never OPEN; unchanged). |
| `ledger-premerge-approval-ux.json` (79K) | PR #534 pre-merge receipt; governance tooling itself classifies `"GOVERNANCE_ARTIFACT"` | GOVERNANCE ARTIFACT | KEEP | GOVERNANCE ARTIFACT, retained by design — **not an #21 gap** (never OPEN; unchanged). |

### F3 — Live tooling ownership snapshot (for future audits #7 CLI/Admin Tools and #12 File/Folder Ownership)

**#7 CLOSED 25/08/2026** — see `docs/governance/HORIZON.md` §CLOSED and `CHANGE_CONTROL_LOG.md`. `diagnose_airtable.py`'s no-`__main__`-guard note below is **SUPERSEDED** (fixed by PR #930, `949e66b`, merged before this cluster's baseline SHA — original text preserved per this register's own rule).

**#12 CLOSED 25/08/2026** — see §F1's "Current disposition" column and `docs/governance/HORIZON.md` §CLOSED. Does not affect this section's own live-tooling inventory, which remains current.

- **Manual ops/governance CLIs (LIVE):** `audit_truth_gate.py`, `daily_git_audit.py` (+ library `branch_cemetery_cleanup.py`), `system_registry_audit.py` (generates tracked `reports/system_registry_report.{json,md}`), `scan_ghost_buttons.py`, `diagnose_airtable.py` (no `__main__` guard — top-level side effects on execution), `contact_merge.py`, `project_timeline.py`, `scripts/classify_contacts_for_airtable.py`, `scripts/render_log_export.py`, `tools/check_airtable_schema_runtime.py`, `tools/dev_registry_reconcile.py`, `tools/smoke_ai_usage_daily_upsert.py` (deliberately CI-excluded manual prod smoke).
- **CI-invoked (LIVE):** `smoke_tests.py` (blocking), `tools/schema_governance.py` (warning), `tools/audit_dispatcher_bypass.py` + `tools/audit_gateway_bypass.py` + `tools/audit_result_parsing.py` (warning-only), `scripts/run_isolated_regression.py` (+ `regression_matrix.py`, `staging_identity.py` chain), `tools/dev_registry_validator.py` (blocking), context-librarian subcommands + `refresh_after_merge.py`.
- **Runtime-wired:** scheduler lazy-imports 14 workers (`scheduler.py:22-834`); app.py wires startup/memory/cost/adapters/schema/boss_doctor/cmd_* modules; `cost_monitor.py` imported top-level (`app.py:74`) + watchdog job (`scheduler.py:739`); `gunicorn.conf.py` pins workers=1.
- **One-off migration/verification generators (HISTORICAL EVIDENCE, retained):** six `scripts/verify_*_staging.py` (registered canonical evidence sources in librarian RECONCILIATION/GAP_QUALIFICATION docs — do NOT treat as removable), five `phase_4b_*` rollout tools + shared common lib (documented cutover procedure), three research POC scripts (`crawl4ai/research_crawler/stirling_pdf`) + fixtures.
- **Placement oddity (not an orphan):** `tc8_test_repo_stub.py` and `emergency_stop_test_support.py` live at repo root but are test-support/fixture libraries imported only by tests.
- **Clean sweeps (negative results, LIVE STRUCTURE CONFIRMED):** zero `.bak/.backup/~/.tmp/.orig/.rej/*old*/*copy*/_v1/_old/deprecated` files tracked; zero CSV/XLSX tracked; zero `.gitignore` violations by tracked files; no stray `migrate_/fix_/debug_/cleanup_` scripts (migration logic lives in library `core/database_migrations.py` + 7 SQL files under `core/migrations/` — LIVE TOOL INPUT read by the CI/predeploy runner).
- **`workers/survey_worker.py`: REMOVED from main** (PR #836). Remaining doc mentions are historical records (matrix row dead-01, C95A, audit-script comment) — SUPERSEDED, not drift requiring action.

---

## Section G — DOC → CODE DRIFT (consolidated claims; verify-before-classify applied)

Classification: DOC DRIFT = contradicts current code · SUPERSEDED = later merged change intentionally replaced it (original preserved) · CURRENT = claim checked out as still true.

| # | Document:line | Claim | Current-code evidence | Class | Owner |
|---|---|---|---|---|---|
| G1 | `AGENTS.md:154` | "single-file Python/Flask application" | Multi-module tree (~400 test files, core/, tools/, workers/); corrected by PR #882 | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G2 | `AGENTS.md:169` | "The repository has no automated tests" | ~400 `test_*.py` executed by CI backend job; corrected by PR #882 | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G3 | `CLAUDE.md:116` | Listed `core/tenant_config.py` as existing unwired module | Deleted by PR #851; corrected by PR #896 | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G4 | `ROADMAP.md:2199,2206,2210-2211` | F13 presented deleted `core/tenant_config.py` as current | Corrected by PR #896 after PR #894 recheck | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G5 | `AI_CONTEXT.md:66` | N18 canary flags named obsolete `*_CUTOVER` identifiers | Corrected to canonical `*_CANONICAL_LEAD_WRITE` identifiers by PR #893 | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G6 | `AI_CONTEXT.md:4` | Briefing freshness/SHA stale | Refreshed through current snapshot by PR #893 | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G7 | `docs/context_librarian/CONSUMPTION_ENFORCEMENT_PLAN.md:9-19` | "implementation still blocked… nothing implemented" | `verify_consumption()` live at `librarian.py:1361`, wired by `__main__.py:217,343`; Phase 1 = PR #490; Phase 3 CI gate remains planned | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G8 | `docs/governance/HORIZON_STATUS_AND_NEXT_STEPS_AUDIT_20260821.md:70-73` | "terminal-turn-result contract remains next" | Assertion holds today (`core/turn_result.py` exists but ROADMAP:69 older entry superseded in-file) | CURRENT | #19 |
| G9 | `ROADMAP.md:69` | Pre-PR-807 "terminal result contract missing" | Superseded by newer entry in same file (:36-62) | SUPERSEDED | #19 |
| G10 | `docs/governance/ARCHITECTURE_DRIFT_MAP.md:14` (row 1, TODO) | Emergency-flag /tmp persistence fix pending | Landed: durable Airtable-backed `evaluate_emergency_stop()` (`feature_flags.py:260-281`); CLAUDE.md:98 "/tmp mechanism no longer exists"; map status column never updated | SUPERSEDED (map row stale) | #19/#24 |
| G11 | `C02_C04_REMEDIATION_1_FINDING_3.md:19` | "not merged / not deployed" | Merged PR #853 (`38a382c`) | SUPERSEDED (original preserved per rule) | #19 |
| G12 | `C02_C04_REMEDIATION_2_FINDINGS_7_8.md:20` | "implemented locally… no merge" | Merged PR #857 (`2b0c08e`) | SUPERSEDED | #19 |
| G13 | `C02_C04_REMEDIATION_3_FINDING_1.md:56` | "no production writes, merge…" | Merged PR #859 (`d70a59f`,`9561ed6`, merge `5f0763f`) — post-dates prior matrix baseline | SUPERSEDED | #19 |
| G14 | `CLAUDE.md:159` worker.py truth-reset claim | "legacy, currently unwired" | Verified: 0 imports; route forwards to run_agent() | CURRENT | — |
| G15 | `CLAUDE.md:125` Approval_Policy_Spec.md absent | "doesn't currently exist in the repo" | Still absent; CLAUDE now states it is absent and not current activation guidance. Historical/dangling refs remain preserved elsewhere | **RESOLVED / DOC DRIFT REMEDIATED** | #19 |
| G16 | `BOSS_CURRENT_STATE.md:3` | Self-banner "⚠️ STALE (09/08/2026)" | Intentional declared-stale archive marker | CURRENT (by design) | — |
| G17 | `docs/audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md:60+` | Cites "ROADMAP.md:241" supersession record | ROADMAP.md:241 content no longer matches citation (now TC10 text) | DOC_DRIFT (stale line-cite inside historical audit — do NOT rewrite body; record only) | #19 |

Notes: `CHANGE_CONTROL_LOG.md` contains no entries marked superseded (term hits are code-behavior names). ARCHITECTURE_DRIFT_MAP rows 2 (messaging facade TODO) valid; rows 3/4/5/8 not cheaply verifiable → UNKNOWN. Prior SSOT files' rows internally consistent except items covered by this pass (G3/G13 + line-cite offsets fixed in matrix addendum below).

---

## Section H — CODE → DOCS GAPS (capabilities/invariants lacking canonical documentation)

| # | Capability | Canonical doc? | Evidence / nearest coverage | Owner |
|---|---|---|---|---|
| H1 | Media processing result contract (`MediaError`/`MediaResult`/`MediaProcessingStatus`, `media_handler.py:48-69`) | **GAP** | Only audit narrative: C02_C04_REMEDIATION_3_FINDING_1.md:37-56 | #20 |
| H2 | WhatsApp ACK vs processing-status behavior | **GAP** (post-fix behavior documented only inside remediation audit) | same doc :41-42; fix = PR #859 | #20 |
| H3 | File upload/reuse architecture (`last_uploaded_file`) | **GAP + dangling citation** | `session_store.py:98` cites `SPEC_File_Context_Reference.md` — file does not exist on main; historical mentions only (F52_STATE_FLOW_MAP.md:45-46, ROADMAP:814) | #20 |
| H4 | GoogleDriveArtifactStore general spec | **PARTIAL** | MPT-scoped `docs/MPT_PHASE_2A_DRIVE_STORAGE.md` exists; design-only gate doc `docs/research/ARTIFACT_FILE_GATEWAY_EXTRACTION_GATE.md`; no store-level spec | #20 |
| H5 | Media Files Airtable table responsibility | **GAP** | One inline comment `airtable_schema.py:67`; passing mentions elsewhere | #20 |
| H6 | Session persistence durability semantics | **GAP** | Research snapshots only (BOSS_OPEN_SOURCE_INFRA_AUDIT "DURABLE/PARTIAL", memory-retrieval arch doc); formally recorded as register item D9 | #20 |
| H7 | Scheduler/process ownership | EXISTS | CLAUDE.md:102 + "Background workers" (:157-160); RUNBOOK log-hints | — |
| H8 | ActionGateway single-write-path invariant | EXISTS (in audit decision) | C05_C07 audit §DECISION + matrix architecture table; thin beyond those two pointers | #20 (optional expansion) |
| H9 | Idempotency mechanisms overview | **GAP** | Mechanisms exist (`guards/idempotency.py`, dispatcher `_DEDUP_FIELDS`, `media_handler.py:140`); docs = one-line listing (CLAUDE.md:105). No dedicated inventory (= missing-artifact M3) | #20 |
| H10 | Context Librarian usage contract | EXISTS | docs/context_librarian/README.md + AGENT_CONSUMPTION_CONTRACT.md wired into AGENTS.md bootstrap | — |

Counts: GAP 5 (H1,H2,H3,H5,H9) · PARTIAL 2 (H4,H6) · EXISTS 3.

---

## Section I — NAMING / ALIAS DRIFT

| # | Item | Names involved / evidence | Canonical (if established) | Risk | Owner |
|---|---|---|---|---|---|
| I1 | Domain variants | Historical inventory `docs/architecture/DOMAIN_CANONICALIZATION_INVENTORY.md` + live reconciliation 20260811 | Normalization code LIVE on main (`domain_utils.py`); wrappers local | LOW (resolved; smoke PASS recorded) | #13 |
| I2 | Owner-ish field constants overlap | `airtable_schema.py`: `OWNER_TENANT="Owner/Tenant"`(:153), `OWNER="Owner"` at :263,:302,:336,:488,:617,:1128 with DIFFERENT per-table semantics (linked Profile record IDs :302/:336 vs Hebrew select :1128), `OWNER_IDS` comma-separated (:591), `OWNERSHIP_PCT` (:615), `NEXT_STEP_OWNER` (:620), `CREATED_BY` (:641) | No single canonical owner field; semantics per-table, documented inline only | MED — audits must never treat "Owner" uniformly | #13/#2 |
| I3 | Provider-specific column reused generically | Historical rows may contain Twilio MessageSid, Meta media id, or TMA pseudo-id in `"Telegram File ID"`; remediation boundary is `media_gateway.py:65-66` and provider-neutral IDs flow from `media_handler.py:574,616,658` | New writes use `Logical Media Key` (`airtable_schema.py:636`; `media_gateway.py:72`) for every provider; `"Telegram File ID"` is compatibility storage only for `source="telegram"`. Legacy non-Telegram values remain read-irrelevant historical data; no live schema migration performed | **CLOSED / STATIC VERIFIED** | #3 Data Contract (routed from #13) |
| I4 | Active FIELD_ALIASES (intentional compatibility) | gateway alias map + permanent `.strip()` hardening (`airtable_schema.py:366-376`, leads_adapter :260-262, audience_intelligence :185-188) | Aliases ARE the sanctioned compat layer (owner decision) | REQUIRED CURRENT COMPATIBILITY | #14 |
| I5 | Hand-copied duplicate field maps (drift-prone) | `dispatcher.py:51-58`, `tma_api.py:1783-1788` duplicate gateway alias knowledge instead of importing it | Gateway map is canonical | MED | #13/#16 |
| I6 | English-schema migration never executed | `docs/governance/MIGRATION_AIRTABLE_ENGLISH_SCHEMA.md` renames + Step-4 compat layer exist on paper only | n/a (plan unexecuted) | UNKNOWN (if executed later, re-check aliases first) | #14/#2 |
| I7 | Flag NAME_DRIFT ×5 (M01 rows) | `EMAIL_INBOUND`, `AUDIENCE_INTELLIGENCE`, `LEARNING_ENGINE` called `FEATURE_*` in old comments/docs; `INTERACTION_INTELLIGENCE` mixed ENV+FF read paths (`scheduler.py:448` vs `interaction_engine.py:489`) | Registry names (feature_flags.py) canonical | LOW-MED | #13 |
| I8 | COST_WATCHDOG dual override names | `COST_WATCHDOG_LIVE` vs direct-env `COST_WATCHDOG_ENABLED` overriding it (`core/cost_watchdog.py:74-79`; M01 READ_PATH_DRIFT/MEDIUM) | Precedence undocumented — also tracked as D8 | MED | #19/#23 |
| I9 | Unregistered flag read path | `ERROR_REPORTING` direct env, absent from registry (`feature_flags.py:661`, `core/error_reporter.py:21,55`) | Registry canonical for flags | LOW | #13 |
| I10 | DEAD_FLAG | `FEATURE_UNIFIED_APPROVAL_MESSAGES` registered, zero runtime consumers (planning-only) | n/a | LOW | #14 |

### Track #13 closure disposition

Track #13 is **CLOSED / CLEAN IN OWNED SCOPE**. The provider-identity naming
issue remains cross-track #3, owner-field overlap remains #2, and
`FEATURE_*` documentation drift remains #20. No #13 rename or migration is
authorized by this closure.

---

## Section J — DEPRECATED COMPATIBILITY retained after migrations

| # | Item | State/evidence | Classification |
|---|---|---|---|
| J1 | `llm_fallback.py` | Load-bearing infrastructure; ONLY dead consumer is unwired `creative_generator.py` | REQUIRED CURRENT COMPATIBILITY |
| J2 | identity fail-open fallback | `resolve_identity()` never returns None (`identity.py:235-284`) vs documented hard-fail rule | DEPRECATION CANDIDATE (= R-C06-8; docs-or-code decision pending) |
| J3 | Approval-state legacy values | `ActionContractStatus.EXECUTED` legacy terminal read-compat ("do not emit for new transitions", `airtable_schema.py:893`); `ProjectedLifecycleStatus.LEGACY` bucket (:795); Approvals.STATUS Hebrew display projection non-authoritative (:744-765) | REQUIRED CURRENT COMPATIBILITY; values = DEPRECATION CANDIDATE once legacy rows age out (= R-C07-6 scope) |
| J4 | Dual conversation-state stores | `memory_store.MemoryStore` process-local 12h TTL (LIVE) vs `session_store.PersistentSessionStore` Airtable-backed (LIVE) — coexist by design, distinct scopes | REQUIRED CURRENT COMPATIBILITY (scopes need documenting → H6) |
| J5 | `memory.ConversationMemory` | Zero importers repo-wide (self-refs only inside `memory.py`) | SUPERSEDED / UNKNOWN CONSUMER (bundled with F1 memory.py row) |
| J6 | Duplicate Media Files writer | `media_handler._save_transcript_to_media_files()` hand-builds fields incl. Status via direct `airtable_create` (`media_handler.py:206-224`) alongside canonical `media_gateway.save_asset()` (`media_gateway.py:58-68`) | DEPRECATION CANDIDATE (consolidate behind gateway module) |
| J7 | Transitional/dormant registered flags | M01 documents DEAD_FLAG + default-off planning-only entries (e.g. FEATURE_UNIFIED_APPROVAL_MESSAGES) | DEPRECATION CANDIDATE (owner flag-hygiene pass; no-deploy boundary respected) |


---

## Section K — SCHEMA / DATA-CONTRACT FOLLOW-UPS (already-surfaced items only; full audits NOT performed here)

| # | Finding | Current state / evidence | Mark | Owner |
|---|---|---|---|---|
| K1 | `TurnEnvelope.turn_id` nullable (`str \| None`) until TurnCoordinator exists; ownership fields caller-supplied | Documented in envelope foundation spec + contract V1 + decision log + multilayer plan (MESSAGE_CONTRACT_ENVELOPE_FOUNDATION_SPEC.md:21; CONTRACT_V1.md:69,177,225-232) | NEEDS_DATA_CONTRACT_AUDIT | #3 |
| K2 | `resolve_identity()` None-assumption mismatch (never returns None vs documented hard-fail) | C05-C07 F8, deferred (= R-C06-8) | NEEDS_DATA_CONTRACT_AUDIT | #3/#15 |
| K3 | Select-option whitespace baked into live schema | LeadOutcome trailing spaces on 7/8 options; renamed trimmed 22/08; read paths keep permanent `.strip().lower()` hardening (`airtable_schema.py:361-380`, `core/adapters/leads_adapter.py:260-262`) | NEEDS_DEDICATED_SCHEMA_AUDIT (verify other tables' option strings) | #2 |
| K4 | Checkbox-absent-means-False contract | EmergencyStopStore `Enabled` checkbox omitted by Airtable when unchecked; readers must default missing→False; duplicate Flag Names undetectable by type system (`airtable_schema.py:1495-1508`) | NEEDS_DATA_CONTRACT_AUDIT | #3 |
| K5 | PR #851 tenant_config deletion residue in docs/comments | Active doc references in CLAUDE/ROADMAP corrected by PR #896; `CURRENT_STATE_MAP.md:197`, CHANGELOG, BUG_AUDIT_LOG, master plan, POST_N15 survey, and `memory_store.py:15` comment remain historical/source-comment evidence outside this scope | **RESOLVED ACTIVE DOC SUBSET; HISTORICAL/CROSS-TRACK RESIDUE PRESERVED** | #19/#20 |
| K6 | Media Files identity columns write-only | `DRIVE_FILE_ID` (:635) and `TELEGRAM_FILE_ID` (:642): sole writers `media_gateway.py:41,48` (+ transcript writer :214 status); ZERO lookup-by-ID readers anywhere; no Drive-file-id retrieval either | NEEDS_DEDICATED_SCHEMA_AUDIT | #2 |
| K7 | LeadSessions persistence | Original F4 gap (lead_draft in-memory only) FIXED (PR #845 `f2030b0`; persist+restore+round-trip self-test `session_store.py:519,693,887-890`). Residual: entire session state is one schema-less `State JSON` blob; keys evolve without versioning | Fixed; residual NEEDS_DATA_CONTRACT_AUDIT | #3 |
| K8 | Structured-result contract complete; FileUploadResult.file_id dual-table overloading | Media pipeline fully structured today (`MediaError/MediaResult` dataclasses; all 3 entry points return MediaResult; rendering centralized :156-160). Overloading CONFIRMED: file_id = Media Files rec ID when type="drive_file" vs Decision Inbox rec ID when "inbox_file" (`session_store.py:102-115`); `_sync_to_db` writes LINKED_MEDIA_FILE only for drive_file to dodge cross-table INVALID_RECORD_ID (:536-540) | Overloading NEEDS_DATA_CONTRACT_AUDIT | #3 |
| K9 | Contract field present only on some paths | `"Status"` hardcoded literal `_MEDIA_FILES_STATUS_FIELD` in media_handler (:200-203, Voice Inbox rows get Status=pending) — ABSENT from `MediaFileFields` constants (:623-647) and absent from media_gateway's AssetRecord mapping → gateway validation blind to the field | NEEDS_DEDICATED_SCHEMA_AUDIT | #2 |
| K10 | Owner-field semantic fragmentation | see I2 (12 constants, per-table semantics inline-commented only) | NEEDS_DEDICATED_SCHEMA_AUDIT | #13/#2 |

---

## Section L — MEDIA / FILE-INGESTION FINDINGS (current-main evidence)

Evidence areas (all path:line verified at this commit):

- **(a) FileUploadResult** — `session_store.py:101-115`: fields type/url/file_id/original_filename/timestamp/conversation_id. Produced at `app.py:5981-5994` (drive_file after Telegram upload), `cmd_decision.py:728-741` + `:805-817` (inbox_file via Decision Inbox). Consumed via get_last_file → attachment-reference handling, pronoun resolution (`app.py:2431-2562`), LINKED_MEDIA_FILE session link (drive_file only).
- **(b) last_uploaded_file lifetime** — RAM LRU (1000) + Airtable Sessions State JSON sync on every set (`session_store.py:228-242,512,686-695,727-733`); durable only if sync succeeded; no TTL of its own.
- **(c) Media Files table** — two writers only (`media_gateway.save_asset` :58-68; transcript writer `media_handler.py:206-224`); **readers: none** (create-only table).
- **(d) Provider IDs** — DRIVE_FILE_ID + TELEGRAM_FILE_ID columns; Twilio MessageSid and Meta message/media ids all land in the Telegram-named column; TMA uploads fabricate ephemeral dedupe pseudo-id sha256(bytes[:1024])[:16] (`media_handler.py:536`). Neutral identity exists ONLY in the disconnected MPT store (`mpt_identity`/`mpt_sha256` appProperties + result_ref JSON, `core/google_drive_artifact_store.py:50,87,111-118`).
- **(e) Ingestion idempotency is process-local** — `guards/idempotency.py:14-41`: in-memory dict + threading.Lock, TTL 300s; restart-unsafe, not shared across gunicorn workers; key recorded BEFORE I/O so a failed upload burns the key and blocks immediate user retry with DUPLICATE.
- **(f) GoogleDriveArtifactStore scope** — MPT mp4 outputs only, gated `MPT_ARTIFACT_STORAGE=google_drive`; resumable upload w/ bounded retries, idempotent-by-identity Drive query, post-upload verification, durable result_ref mapping; uncertain-outcome codes surfaced through adapters. **The Telegram/TMA/WhatsApp ingestion path does NOT use it**: raw single-shot httpx multipart (`drive_adapter.py:144-204`), no retry/verification/appProperties; best-effort Airtable metadata afterwards — failure returns ASSET_SAVE_FAILED retryable=True leaving an orphaned Drive file (`media_handler.py:509-515`).
- **(g) External-tool/GitHub ingestion** — no GitHub-based ingestion exists (only upstream URL constants). External tools persist via SubmitResult/PollResult.result_ref in the jobs repository + ArtifactStore protocol (`core/external_execution_boundary.py:34-52`, `external_execution_repository.py:32,48`); structured xlsx/csv Telegram documents bypass storage entirely (parsed to text, `core/file_ingress_adapter.py`). Agent-facing Drive access is search/read-only.

**Verdict (re-checked at this commit): STILL HOLDS** — no canonical media-handler mechanism currently proves all four:
1. stable logical key — NOT PROVEN (provider-specific/polysemous columns; ephemeral TMA pseudo-id; record-ID overloading);
2. durable Drive mapping — NOT PROVEN for ingestion (one-shot write-after-upload; ASSET_SAVE_FAILED leaves Drive files unmapped; durable mapping only inside MPT-scoped store);
3. cross-process retry safety — ABSENT (in-memory TTL dict);
4. metadata reconciliation — ABSENT (zero read paths against Media Files).

**New since prior consolidation:** PR #859 (commits `6f74a71` separate WhatsApp ACK from processing status, `9561ed6` Twilio adapter failure reporting, `d70a59f` Meta adapter failure reporting; merge `5f0763f`) fixed the false-success ACK finding (C02-C04 Remediation 3, Finding #1). This improves ACK/status honesty but does NOT change any of the four clauses above. Status: MERGED; doc-gap H2 remains.

---

## Section M — UNKNOWN / MISSING AUDIT ARTIFACTS (re-searched at this commit)

| # | Artifact | Result |
|---|---|---|
| M1 | Full original C00/C08 route & entry-point audit body | **STILL ABSENT** (chat-origin; only BUG_AUDIT_LOG.md C00-F1 summary entry preserved) |
| M2 | Full original C02–C04 audit body | **STILL ABSENT** — note: THREE remediation docs now exist under docs/audit/ (#3, #7+#8, and new Remediation-3 Finding #1); unevidenced findings #2,#4,#5,#6,#9,#10 remain UNKNOWN |
| M3 | Dedicated C04 idempotency inventory | **STILL ABSENT** |
| M4 | LeadSessions/session-lifecycle audit | **STILL ABSENT** (= D9) |
| M5 | Long-log/context-growth audit | **STILL ABSENT** (= D10) |
| M6 | Approval_Policy_Spec.md | **STILL ABSENT**; dangling refs at RELEASE_CHECKLIST.md:100, CHANGE_CONTROL_LOG.md:957, BUG_AUDIT_LOG.md:466; AI_CONTEXT itself no longer references it (nuance on CLAUDE.md:125 claim). Similarly-named APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md DOES exist (different doc) |

Never reconstruct these from memory/chat. If needed, re-run fresh audits against current main.

---

## Future-audit cross-reference

| Future audit | Consolidated findings routed here |
|---|---|
| #2 Schema Drift | **AUDIT COMPLETE — DEFERRED LIVE VERIFICATION**; K3, K6, K9, K10, I2, I6 remain separately tracked pending Live evidence |
| #3 Data Contract | **AUDIT COMPLETE — ALL CURRENT CODE GAPS CLOSED / FINDING #2 EXPLICITLY DEFERRED**; #1, #3, #4, #5, #6 CLOSED; #2 remains **DEFERRED — LIVE/SCHEMA CONTRACT DECISION**; I3 **CLOSED / STATIC VERIFIED** |
| #4 Exception Taxonomy follow-up | (none consolidated this pass) |
| #5 Async/Concurrency follow-up | guards/idempotency lock-before-I/O behavior noted in L(e) |
| #6 Scheduler follow-up | R-C06-10 (existing), scheduler lazy-import inventory F3 |
| #7 CLI/Admin Tools | F3 manual CLI list; diagnose_airtable.py no-main-guard note (**SUPERSEDED**, PR #930); benchmark_token_estimate.py — **#7 CLOSED 25/08/2026, see `docs/governance/HORIZON.md`; `benchmark_token_estimate.py`'s own orphan-suspect status remains routed to #21, unaffected by #7's closure** |
| #8 Test Gap | tc8_test_repo_stub/emergency_stop_test_support root placement; test-only-import modules F1 (placement concern only — owned by #12, per Track F 24/08/2026 closure). **#8 itself is CLOSED / STATIC VERIFIED + CI ENFORCED (26/08/2026 remediation)** — #8-1 CLOSED/VERIFIED (evidence adopted from PR #1017's `test_approval_concurrency.py` Test 1+6, no duplicate test) and #8-2 CLOSED/CI ENFORCED (dedicated blocking `pytest` CI step added for `test_phase_4b_1b_durable_lifecycle.py`, matching the Context Librarian pattern). See `BUG_AUDIT_LOG.md` ("Audit #8 — Test Gap — CLOSURE (Combined Fix)") and `docs/governance/HORIZON.md` §CLOSED. The 24/08/2026 "ALREADY CLOSED" and 26/08/2026 "OPEN — CURRENT TEST GAPS" entries in `MAINTENANCE_STATUS_MATRIX.md`/`MAINTENANCE_DEFERRED_REGISTER.md` are both preserved as historical record, not rewritten. |
| #9 Mock Fidelity | **CONSUMED, Audit #9 25/08/2026**: 4 findings (#9-1 HIGH, #9-2 MEDIUM-latent, #9-3/#9-4 LOW) — see `BUG_AUDIT_LOG.md` ("Audit #9 — Mock Fidelity (Phase 1, Read-Only)" and its closure entry) and `docs/governance/HORIZON.md` §CLOSED. #9 itself is **CLOSED / STATIC VERIFIED (25/08/2026)** — all 4 findings remediated (test/test-double changes only, 0 production code changes); CROSS-TRACK → #8 (negative-path Test Gap) stayed open until #8's own 26/08/2026 remediation closed it (see #8 row above) — #9's verdict/findings above are unchanged by that. |
| #10 Dependency Risk | (none consolidated this pass) |
| #11 Security Surface | J2 fail-open context (owner R-C06-8) — **CONSUMED, Audit #11 25/08/2026**: evaluated as ALREADY VERIFIED, not a security fail-open gap (`identity.py:235-284` falls back to minimal-privilege `READONLY`/`LEAD`, not an elevated role); the docs-or-code naming decision itself remains open under R-C06-8, unaffected by this evaluation. #11 itself is **CLOSED / STATIC VERIFIED + CI ENFORCED (25/08/2026)** — #11-1/#11-2/#11-3 all remediated — see `BUG_AUDIT_LOG.md` and `docs/governance/HORIZON.md` §CLOSED. |
| #12 File/Folder Ownership | F1 cluster (worker/knowledge_engine/router/lead_qualifier/profile/creative_generator/tenant_provisioner/memory.py) — **#12 CLOSED 25/08/2026**: 7 of 8 modules removed (see F1 table's "Current disposition" column for per-file commit citations); `tenant_provisioner.py` remains parked by owner decision, not a gap. The #21 → #12 `reports/` provenance handoff is **DEFERRED — OWNER: #12**, with no current runtime gap and an explicit reopen trigger recorded in `MAINTENANCE_DEFERRED_REGISTER.md`. See `docs/governance/HORIZON.md` §CLOSED and `docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md`. |
| #13 Naming Consistency | I1-I3, I5, I7-I10, K10 |
| #14 Deprecated Compatibility | I4, I6, I10, J1-J7 |
| #15 Recovery/Fallback follow-up | L(f) orphaned-Drive-file on ASSET_SAVE_FAILED; burned-idempotency-key retry block L(e) |
| #16 Tool Contract | I5 duplicate maps; K8 result-contract overloading |
| #18 SSOT | G3-G7, G17 doc-authority conflicts; matrix/register are SSOT pointers |
| #19 Docs-to-Code | G1-G7, G15, K5 active subset **resolved**; G17 historical audit drift preserved; I8 cross-routed to #23 |
| #20 Code-to-Docs | H1-H6, H9 (H8 optional expansion) |
| #21 Orphan Artifact | config.json, import_knowledge_base.json, review_diffs.txt review, memory.py, benchmark_token_estimate.py, reports/ provenance gaps — **#21 CLOSED for the identified orphan candidates** (`docs/audit/ORPHAN_ARTIFACT_REMEDIATION_INVENTORY_20260824.md:42`); see F1/F2 tables' "Current disposition" columns for per-item evidence. The `reports/` provenance handoff is **CLOSED / ACKNOWLEDGED** as **DEFERRED — OWNER: #12 File / Folder Ownership**; #21 owns no further work on `reports/`. |
| #22 Performance Smell | (none consolidated this pass) |
| #23 Cost | D8/I8 cost-flag precedence (cross-ref) |
| #24 Architecture Drift | G10 drift-map stale row; drift-map rows 3/4/5/8 UNKNOWN verification |

---

## Counts summary (this pass)

- Ownership debt findings: **15** (F1 ×10 modules incl. corrections, F2 ×4 artifacts, survey_worker removal note)
- Docs→code drift rows: **17** (DOC_DRIFT 7 · SUPERSEDED 5 · CURRENT 5 · notes/UNKNOWN 4 drift-map rows)
- Code→docs gaps: **10** capabilities (GAP 5 · PARTIAL 2 · EXISTS 3)
- Naming/alias drift: **10** rows (covering ~12 sub-findings incl. M01 NAME_DRIFT ×5, DEAD_FLAG ×1, READ_PATH_DRIFT ×2)
- Deprecated compatibility: **7** rows (REQUIRED ×3, DEPRECATION CANDIDATE ×4 incl. SUPERSEDED/UNKNOWN-CONSUMER J5)
- Schema/data-contract follow-ups: **10** (NEEDS_DEDICATED_SCHEMA_AUDIT ×4 · NEEDS_DATA_CONTRACT_AUDIT ×5 · mixed/fixed-with-residual ×2)
- Media/file-ingestion findings: 7 evidence areas + 4-clause verdict (STILL HOLDS) + PR #859 update
- Missing historical artifacts: **6 STILL ABSENT**
