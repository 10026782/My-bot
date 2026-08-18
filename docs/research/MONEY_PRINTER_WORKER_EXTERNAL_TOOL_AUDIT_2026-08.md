# Money Printer / Worker External Tool Audit — 2026-08

> This is a research/procurement catalog, not a BOSS source of truth for implementation or runtime status. No implementation, installation, or provider connection happened as part of this audit.

Base: `origin/main` at `2de5a81dc10cbe8f80c8efbd7195ae68d8bc8bba` (fetched 2026-08-18).

## A. Executive Summary

1. "Money Printer" is **not** a built pipeline in this repo — it's referenced twice in prior research docs as an aspirational loop (signal → lead → research/enrichment → prioritization → action → follow-up → outcome → revenue attribution → learning). No file defines it end-to-end.
2. The closest existing pieces are `lead_capture.py`, `lead_qualifier.py`/`score_display.py`, `core/lead_recovery.py`/`abandoned_lead_worker.py`, `followup_engine.py`, `ad_attribution.py`, `audience_intelligence.py`, `core/learning_engine.py` — most behind flags that default off or are intentionally inert.
3. `worker.py` is small and complete: a Render-cron deadline nudger over Airtable Tasks + Telegram, plus a 3h in-process recheck thread. It has zero observability today — no exception tracking, no "did the cron actually fire" heartbeat.
4. The single biggest, cheapest, most defensible finding across every source: BOSS already writes to Postgres `usage_events` (shadow-only, nothing reads it) and has no heartbeat on its own cron trigger. Both gaps have free-tier, non-authority, read-only fixes.
5. The single biggest capability gap in the Money Printer loop — a "research/enrichment" stage for inbound leads — has **no good external-tool fix**. public-apis has no Israeli business-registry/address-validation API at all; awesome-llm-apps has a strong *pattern* to imitate, not a tool to install.
6. n8n and Dify were re-confirmed (not reopened) at their existing verdicts with fresh license/README checks; no new evidence surfaced.
7. Nothing found contradicts the four locked verdicts (Supabase, MCP, Ollama, Hermes runtime) — none of the five sources referenced them in a way that changes the prior audit.
8. Every real candidate below is a read-only evidence/observability layer or an offline research pattern — none imply giving an external tool mutation authority over Airtable/business data.
9. Two internal-pattern findings (research/enrichment stage shape, impact-based prioritization filter) are more valuable to Money Printer than any tool found — they're free, and they're what's actually missing.
10. `awesome-selfhosted`'s "real task queue" candidates (Cronicle, Dagu, Airflow) are explicitly *not* needed yet — current worker volume (2 cron fires/day + a 3h thread) doesn't justify any of them; Dagu is the one worth remembering if that ever changes.
11. Free-for-dev has no evidence of a Postgres cost reduction below the existing $14/month Render baseline — this reconfirms `KEEP RENDER` rather than reopening it.
12. License/commercial risk is low across the top candidates (Apache-2.0, MIT, BSD-3, AGPL-3 for Metabase); n8n/Dify remain the only source-license-restricted items and stay reference-only.
13. Nothing here is ready to implement without its own scoped review (read-only DB role for Metabase, SDK init points for Sentry, ping placement in `worker.py` for healthchecks.io) — this audit identifies candidates, it does not approve wiring them in.

## B. Top Candidates

| Candidate | Source | Build Saving | Cost Saving | New Capability | Worker Fit | Money Printer Value | Risk | Verdict |
|---|---|---|---|---|---|---|---|---|
| healthchecks.io | free-for-dev / awesome-selfhosted | High — replaces custom cron-heartbeat logic | $0 free tier | Detects a silently-dead `worker.py` cron trigger (nothing does today) | 5 | 1 | Low — receive-only ping | DEEP AUDIT / PRODUCTION CANDIDATE |
| Sentry (or GlitchTip) | free-for-dev / awesome-selfhosted | High — replaces building error tracking | $0 free/staging tier | Real exception visibility for `worker.py`/`scheduler.py` (currently local logs only) | 4 | 2 | Low — SDK is passive, no mutation authority | PRODUCTION CANDIDATE (Sentry) / STAGING CANDIDATE (GlitchTip) |
| Metabase | awesome-selfhosted | High — dashboards for free vs. building UI | $0 marginal (existing Postgres) | Read-only dashboard on `usage_events`, which nothing currently reads | 3 | 2 | Low if DB role is read-only only | DEEP AUDIT |
| Axiom | free-for-dev | Medium — replaces ad hoc log shipping | $0 free tier (0.5TB/mo) | Structured, searchable job logs for scheduler/worker | 4 | 1 | Low — ingest-only | PRODUCTION CANDIDATE |
| Research/enrichment pipeline shape (awesome-llm-apps) | INTERNAL PATTERN | Medium — saves pipeline-design time | none | The missing "research/enrichment" stage shape for Money Printer, output-only until approval | 3 | 5 | Medium if ever wired to auto-send — must stay draft-only through existing approval flow | ADAPT |
| Impact-based noise filtering (awesome-llm-apps) | INTERNAL PATTERN | Low — small, reusable filter idea | none | Generalizes `score_display.py`'s threshold-surfacing to any worker job | 4 | 4 | None — pure read/rank logic | LEARN |
| OpenCage | public-apis | Low | Paid past trial ($50/mo @10k/day) | Address sanity check on lead intake, better than Nominatim for Israel but unverified | 2 | 2 | Low — read-only geocode lookup | SPIKE CANDIDATE |
| Numverify | public-apis | Low | Very low free volume (100/mo) | Israeli mobile (05x) validation, accuracy unconfirmed | 2 | 2 | Low, but PII (phone) flows through a third party | SPIKE CANDIDATE |
| Dagu | awesome-selfhosted | None now | $0, but real ops cost if adopted | Only relevant if worker.py's cron/thread approach hits a real scaling wall | 3 (future) | 0 | Medium if ever wired to touch Airtable directly instead of via dispatcher | FUTURE |
| n8n | n8n-io/n8n | None at current scale | Unknown, real ops cost (Redis+Postgres for queue mode) | None justified — YAGNI at 2 cron jobs/day | 1 | 0 | Medium — Sustainable Use License restricts hosting/redistribution; would need to stay strictly internal | NO USE |

## C. Best Patterns from awesome-llm-apps

1. **Scout→Rank→Deliver split w/ dry-run default** (`always_on_hn_briefing_agent`, `release_radar_agent`) — collect/score/render/send/schedule as separate steps, delivery gated behind an explicit flag. Direct template for any new `worker.py` job beyond deadline-nudges. Worker Fit 5, MP Value 3. **LEARN.**
2. **Impact-based noise filtering** (`release_radar_agent/ranker.py`) — only escalate on a real signal (security/breaking/deprecation), not every item. Same shape as Money Printer's prioritization stage; generalizes `score_display.py`'s tiering beyond leads. Worker Fit 4, MP Value 4. **LEARN.**
3. **Deterministic-vs-agentic separation** (`devpulse_ai`) — dedup/normalize as plain code, reserve LLM calls for judgment steps. Validates BOSS's existing dispatcher/registry split rather than adding capability. Worker Fit 3, MP Value 3. **LEARN.**
4. **4-stage lead research pipeline, output-only** (`ai_email_gtm_outreach_agent`) — discover → identify contacts → research/personalize → draft, no auto-send. This is the closest real-world shape to Money Printer's missing "research/enrichment" stage. Must stay draft-only through `Handler.APPROVAL`. Worker Fit 3, MP Value 5. **ADAPT.**
5. **Sequential enrichment+synthesis, artifacts-only** (`ai_sales_intelligence_agent_team`) — multi-stage research → synthesis → formatted report, no system writes. Maps to account/competitor intel rather than raw lead enrichment. Worker Fit 2, MP Value 3. **LEARN.**
6. **Tiered evaluator system** (`agent_skills/evals`) — automated CI tiers plus a human-graded behavioral tier, documented catching a real regression. Useful for validating any new worker job before shipping, not Money-Printer-specific. Worker Fit 3, MP Value 2. **LEARN.**
7. **Self-improving skills via eval feedback** (`agent_skills/self-improving-agent-skills`) — same shape as `core/learning_engine.py`'s eventual activation. Too early to act on; `learning_engine.py` is deliberately dormant pending data. Worker Fit 2, MP Value 2. **FUTURE SPIKE.**
8. **Hash-chained audit log** (`trust_gated_agent_team`) — tamper-evident action record; the *trust-gating* half of this pattern (agents gating their own execution) is explicitly incompatible with BOSS's governance model and must not be adapted. Only the hash-chaining idea is safely reusable for `event_bus.py`. Worker Fit 1, MP Value 1. **IGNORE** (hash-chain idea alone: LEARN).

No pattern here referenced MCP, Ollama, Hermes, or Supabase — no new evidence against the locked verdicts.

## D. Best Self-hosted Candidates

| Name | License | Self-host reqs | Verdict |
|---|---|---|---|
| Healthchecks | BSD-3-Clause | Docker/Python, own DB | DEEP AUDIT |
| Metabase | AGPL-3.0 | Docker/Java, own metadata DB + read access to a data source | DEEP AUDIT |
| Dagu | GPL-3.0 | Single Go binary, no DB | FUTURE |
| Cronicle | MIT | Nodejs, own persistent storage | FUTURE (heavier than Dagu, not preferred) |
| MeiliSearch | MIT | Rust/Docker, own data volume | FUTURE (only if a real lead-search/RAG need appears) |
| ntfy / Apprise | Apache-2.0 / MIT | Go or Python | REJECT — Telegram already is BOSS's alert channel |
| Paperless-ngx | GPL-3.0 | Docker, Postgres+Redis+storage volume | REJECT — no OCR/document-ingestion need exists today |
| Apache Airflow | Apache-2.0 | Multi-process cluster (scheduler/webserver/workers/metadata DB) | REJECT — the anti-pattern example; wildly oversized for 2 cron jobs/day |

## E. Best APIs

| API | Auth | Free tier | Israel fit | Verdict |
|---|---|---|---|---|
| Nominatim (OSM) | None | Free, 1 req/sec cap, no commercial bulk use | Weak — inconsistent outside major cities | CATALOG |
| OpenCage | apiKey | Trial only, 2,500/day | Better than Nominatim but unverified for Israel | SPIKE CANDIDATE |
| Numverify | apiKey | 100/month | Israeli mobile (05x) accuracy unconfirmed | SPIKE CANDIDATE |
| Hunter | apiKey | 50 credits/month | Weak — most BOSS leads are Hebrew-only SMBs without a company domain | CATALOG |
| VATlayer | apiKey | 100/month | **EU-only** — irrelevant to Israeli ח.פ/עוסק מורשה | IGNORE (core), CATALOG (only if `import`-domain EU-supplier validation becomes a real roadmap item) |
| Binlist | None | Free | No current BOSS use case | IGNORE |
| SEC EDGAR / FRED | None / apiKey | Free | US-scoped, irrelevant to Israeli SMB leads | IGNORE |

**No Israeli business-registry, company-lookup, or address-validation API exists anywhere in public-apis.** This is the actual capability gap Money Printer's research/enrichment stage needs most, and it needs a separate, targeted search (gov.il / commercial Israeli data vendors), not another pass over public-apis.

## F. Best Free/Low-cost Infrastructure

| Service | Free Limit | After Limit | Verdict |
|---|---|---|---|
| healthchecks.io | 20 checks | Hard stop, existing checks keep working | PRODUCTION CANDIDATE |
| Sentry | 5,000 errors/mo, 1 user | Events dropped past quota, no silent auto-bill | PRODUCTION CANDIDATE |
| Axiom | 0.5TB logs, 30-day retention | Ingestion throttled | PRODUCTION CANDIDATE |
| Better Stack | 10 monitors, 3-min interval | Hard stop adding monitors | PRODUCTION CANDIDATE (pairs with healthchecks.io, doesn't replace it — confirms liveness, not job completion) |
| UptimeRobot | 50 monitors, 5-min interval | Hard stop adding monitors | DEV/STAGING ONLY — redundant with Better Stack, pick one |
| GlitchTip | 1,000 events/mo hosted, unlimited self-hosted | Events dropped past quota | STAGING CANDIDATE |
| Grafana Cloud | 3 users, Loki 50GB/14d, Prometheus 10k series/14d | Hard stop per cap | REJECT for now — overkill for a single Flask app + one worker |
| Neon (Postgres) | 0.5GB storage, autosuspend after 5min idle | Autosuspend degrades latency | REJECT — reconfirms KEEP RENDER, autosuspend incompatible with an always-on bot, no saving found |

## G. n8n Verdict

**NO USE.** License reconfirmed unchanged (Sustainable Use License v1.0 — internal use permitted, commercial redistribution/hosting-for-customers barred; Enterprise-marked files need a separate paid license). Production-grade use requires Redis + Postgres + separate worker processes — real infra for a problem BOSS doesn't have. `worker.py` and `scheduler.py` are two cron jobs a day; standing up n8n for that is over-buying. This confirms, and extends to the non-core case, the prior "IGNORE for core" verdict. Revisit only if internal automation surface grows enough that many one-off scripts become worse than operating n8n, and legal reviews the license fit.

## H. Dify Learnings

**LEARN-ONLY, unchanged.** License reconfirmed (modified Apache-2.0: multi-tenant restriction without authorization, frontend logo/copyright preservation in `web/`). Concrete patterns reviewed: prompt versioning/A/B testing (REFERENCE ONLY — low priority), provider abstraction (IGNORE — BOSS already has `providers/interfaces.py`, unwired; finishing that is not new work to import), RAG/dataset pipeline concept (LEARN, deferred until a real research/enrichment stage needs document RAG), LLMOps tracing/eval logging shape (LEARN — the one plausibly cheap near-term win, as a structured trace schema feeding `core/learning_engine.py` once it activates), visual workflow builder UX (IGNORE — conflicts with BOSS's code-reviewed Intent→Policy→ActionGateway contract; a user-built graph is exactly the wrong shape for a governed mutation path).

## I. Explicit Rejections

- **Neon (Postgres)** — autosuspend incompatible with an always-on bot; no cost saving over existing $14/month Render baseline. Reconfirms `KEEP RENDER`, does not reopen it.
- **ntfy / Apprise** — Telegram direct to the owner already is BOSS's alert channel; a notification relay duplicates a channel that already works.
- **Paperless-ngx** — no OCR/scanned-document ingestion path exists anywhere in BOSS today; heaviest infra ask reviewed (DB+Redis+storage) for a non-existent need.
- **Apache Airflow** — production Airflow needs a multi-process cluster costing more than BOSS's entire infra bill to run two cron jobs a day.
- **Grafana Cloud** — real setup cost (PromQL/LogQL dashboards, alert rules) exceeds the value at BOSS's current single-app, single-worker scale.
- **VATlayer, Binlist, SEC EDGAR, FRED** — wrong country/domain for Israeli SMB leads; no plausible BOSS use case.
- **Cronicle** — needs its own persistent stateful service and job-runner UI for the same job Dagu (a static binary) does with a smaller attack surface; prefer Dagu if this category is ever revisited.
- **Trust-gating pattern** (awesome-llm-apps `trust_gated_agent_team`) — the "agent's own trust score gates its execution" idea is directly incompatible with BOSS's governance model (no external tool/agent gates its own authority). Only the unrelated hash-chaining idea survives as a LEARN.

## J. Cost-reduction Opportunities

None found with real, proven savings. Free-for-dev's Postgres options (Neon) don't beat the existing $14/month Render baseline once autosuspend/storage caps are accounted for. This is a negative result, not a gap — it closes out "is there a cheaper DB" rather than reopening Supabase/KEEP RENDER. The closest thing to a cost-saving finding is avoided *future* build cost: healthchecks.io/Sentry/Axiom/Metabase are all free-tier substitutes for infrastructure BOSS would otherwise have to build from scratch to get the same visibility.

## K. Worker Opportunities

The concrete, real gap: `worker.py` has zero observability. Nothing today would notice if the Render Cron trigger silently stopped firing, and job exceptions go only to local logs. healthchecks.io (a ping at job start/end) and Sentry/GlitchTip (SDK init in `worker.py`/`scheduler.py`) are the two highest-value, lowest-effort additions found in this entire audit — both are additive, read/receive-only, and sit outside the `Intent → ActionGateway → dispatcher` mutation path entirely, so neither requires the governance review a new tool/provider integration would. If worker volume ever genuinely outgrows the current cron+thread model, Dagu (not Cronicle or Airflow) is the most defensible next step, provided every step still calls BOSS's dispatcher rather than touching Airtable directly.

## L. Money Printer Opportunities

The biggest, most honest finding: Money Printer's weakest stage — research/enrichment on inbound leads — has no good external-tool fix. public-apis has no Israeli business-registry or reliable Israeli address/phone validation; OpenCage and Numverify are only worth a timeboxed spike, not a commitment. What *does* move the needle is free: the awesome-llm-apps 4-stage research pipeline pattern (discover→contacts→research→draft, output-only through approval) is the closest real match to the missing stage, and the impact-based noise-filtering pattern generalizes `score_display.py`'s tiering to any future worker/prioritization job. Both are internal-pattern adoptions, not installs. Separately, Metabase pointed read-only at the existing (already-collected, currently-unread) `usage_events` table is the cheapest path to any revenue/spend visibility for the "outcome → revenue attribution" end of the loop — it doesn't build new data collection, it just reads what already exists.

---

## Top 5 External Candidates

1. **healthchecks.io** — why: closes the one real, verified gap (no detection of a silently-dead `worker.py` cron trigger). Expected value: high, near-zero effort. Integration effort: one HTTP ping at job start/end. Major risk: none — receive-only, no mutation authority. Next step: a scoped spike adding the ping behind a flag, reviewed like any other worker change.
2. **Sentry (or GlitchTip for staging)** — why: `worker.py`/`scheduler.py` currently fail silently to local logs only. Expected value: high — real exception visibility, industry-standard tooling. Integration effort: SDK init in two files. Major risk: low — passive capture, verify free-tier ToS for the eventual production volume. Next step: staging-first GlitchTip/Sentry trial before any production SDK init.
3. **Metabase, read-only against existing Postgres** — why: `usage_events` is already collected and shadow-only; this is the cheapest path to spend/usage visibility that exists. Expected value: medium-high, near-zero marginal infra cost. Integration effort: a dedicated read-only DB role plus Metabase deploy. Major risk: must never be given write access — that would create a second view outside the ActionGateway boundary. Next step: DEEP AUDIT scoping the read-only role and hosting footprint.
4. **Axiom** — why: no structured/searchable job logging exists today. Expected value: medium — meaningfully better than local stdout for `scheduler.py`/`worker.py` debugging. Integration effort: log shipping config, no code path changes. Major risk: low, portability of dashboards/queries (APL) is the only lock-in concern. Next step: staging trial alongside the Sentry spike.
5. **OpenCage or Numverify (enrichment spike, not commitment)** — why: the only candidates that touch Money Printer's actual weakest stage (lead research/enrichment), even though neither is proven for Israeli data. Expected value: unproven — genuinely needs testing against real historical lead data first. Integration effort: a single read-only, non-approval-required dispatcher tool case. Major risk: PII (phone/address) flowing through a third party — needs a data-sensitivity review before any spike. Next step: a timeboxed accuracy test against real (anonymized) Israeli lead addresses/phones before deciding whether to pursue either further.

## Top 5 Internal Patterns

(To adopt in BOSS's own code — not to install, not external dependencies.)

1. **4-stage research/enrichment pipeline shape** (discover → identify contacts → research/personalize → draft, output-only) — the closest existing template for Money Printer's missing research/enrichment stage. Must terminate in a draft routed through `Handler.APPROVAL`, never auto-send.
2. **Impact-based noise filtering** — only escalate when a real signal fires, not every item. Generalizes `score_display.py`'s tiering logic into a reusable filter any future worker job (or Money Printer prioritization step) can use.
3. **Scout→Rank→Deliver split with an explicit dry-run gate** — a clean four-step scaffold (collect/score/render/send-behind-a-flag) for any new job added to `worker.py` beyond today's single deadline-nudge purpose.
4. **Deterministic-vs-agentic separation as an explicit design rule** — codify what BOSS's dispatcher/registry split already enforces in practice: dedup/normalize/write stays plain code, LLM calls are reserved for judgment steps only. Not new capability — worth writing down so it doesn't erode over time.
5. **Structured LLMOps trace/eval logging shape** (from Dify) — a log schema around LLM calls (input, output, verification result) that would give `core/learning_engine.py` real data to activate on once its dormancy period ends. Cheap to design now, doesn't require deploying anything.

## Required Classification

| Item | Classification |
|---|---|
| healthchecks.io | INFRA SERVICE |
| Sentry / GlitchTip | INFRA SERVICE |
| Axiom | INFRA SERVICE |
| Metabase | EXTERNAL TOOL |
| Better Stack / UptimeRobot | INFRA SERVICE |
| Dagu | EXTERNAL TOOL (FUTURE) |
| Cronicle, Airflow, Paperless-ngx, ntfy, Apprise | REJECT |
| OpenCage | EXTERNAL API |
| Numverify | EXTERNAL API |
| Hunter, VATlayer, Binlist, SEC EDGAR, FRED, Nominatim | EXTERNAL API (CATALOG or IGNORE, see §E) |
| n8n | REFERENCE ONLY |
| Dify | REFERENCE ONLY |
| Research/enrichment pipeline shape | INTERNAL PATTERN |
| Impact-based noise filtering | INTERNAL PATTERN |
| Scout→Rank→Deliver split | INTERNAL PATTERN |
| Deterministic-vs-agentic separation | INTERNAL PATTERN |
| LLMOps trace/eval logging shape | INTERNAL PATTERN |
| Trust-gating (agent self-authorization) | REJECT |
| Hash-chained audit log idea | INTERNAL PATTERN |

## Verification Boundary

This audit is external-source research plus grounding checks against current `origin/main` (file existence, flag defaults, module sizes). No provider was connected, no dependency was installed, no code or database changed. It does not claim any candidate is deployed, wired, or approved for implementation.
