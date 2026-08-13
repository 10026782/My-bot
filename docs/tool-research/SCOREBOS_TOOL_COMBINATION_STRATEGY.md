# SCOREBOS — Tool Capability Combination Strategy

**Date:** 2026-08-13  
**Scope:** strategy research only. No tools were installed, connected, scheduled, or added to SCOREBOS.

## 1. Current Capability Inventory

| Capability | Current state | Evidence and boundary |
|---|---|---|
| Internal execution registry | IMPLEMENTED | `tool_registry.py` owns internal tool roles, availability, approval and emergency blocking. It is not an external-tool catalog. |
| External Business Tool Registry | MERGED BUT NOT RUNTIME VERIFIED | `business_tool_registry.py` is a read-only, code-seeded catalog with deterministic matching, privacy guidance, verification status and business/operator/infrastructure classes. |
| Bot recommendation path | MERGED BUT NOT RUNTIME VERIFIED | `app.run_agent()` checks the external catalog after identity resolution and returns a recommendation without upload, execution, approval or a second action path. |
| Verification statuses | IMPLEMENTED | Normal-user matching accepts only `verified` and `approved_with_restrictions`; deferred/verify-first records are excluded. |
| Privacy and class separation | IMPLEMENTED | Business tools, operator tools and infrastructure candidates are distinct; operator/infrastructure records are not normal-user recommendations. |
| Crawl4AI research crawler | POC ONLY | Isolated harness and architecture exist; runtime crawl was not executed and no package was installed. |
| Firecrawl comparison | DOCUMENTED / PLANNED | Crawl4AI is the default POC path; Firecrawl is a measured fallback only after a real failure case. |
| Source allowlist/change detection | DOCUMENTED / PLANNED | Exact HTTPS allowlist, bounded crawl, normalized content, hashes and pending verification records are specified. |
| Verification queue | DOCUMENTED / PLANNED | Candidate output is always pending and cannot approve or publish registry state. |
| UptimeRobot | DEFERRED | External reachability POC candidate; no account, monitor or runtime dependency. |
| Checkly | DEFERRED | Synthetic API/browser testing POC candidate; no account or production checks. |
| Sentry | DEFERRED | Redacted exception-triage POC candidate; no SDK or telemetry path. |
| Socket | DEFERRED | Read-only dependency/supply-chain scan candidate; no CI policy or blocking gate. |
| Operator toolbox | DOCUMENTED / PLANNED | Hoppscotch, CyberChef, Log Voyager and related utilities are direct-use guidance, not SCOREBOS runtime dependencies. |
| User-facing toolbox | IMPLEMENTED | Approved Business Toolbox research feeds the curated catalog; direct links remain the execution surface. |

The important architectural fact is that SCOREBOS has one internal execution registry and one external recommendation catalog. They must not be merged, duplicated in TMA, or replaced by a crawler or vendor.

## 2. Real User Jobs

### Job A — “I need a tool for this”

`user need → external Business Tool Registry → deterministic match → recommendation + direct link`

This is the only combination with present runtime value. SCOREBOS recommends; the user opens and operates the external tool. No file proxy, upload, execution or approval is added.

### Job B — “We do not have a tool for this yet”

Current behavior should remain a normal answer or a bounded “I do not have an approved tool for that” response. A research request path is not required now. Adding one would create intake, queue, status and review behavior before usage proves the need.

### Job C — Keep known tools current

Potential flow:

`approved source manifest → Crawl4AI → deterministic diff → pending evidence → human/agent verification → registry update`

The crawler must never approve, publish, execute or write canonical business state directly.

### Job D — SCOREBOS operational reliability

These are independent concerns:

- UptimeRobot answers “is a public endpoint reachable?”
- Checkly answers “does a synthetic API/browser flow behave correctly?”
- Sentry answers “which redacted exceptions are recurring?”
- Socket answers “did dependency risk change?”

None is a business-tool recommendation and none should be bundled automatically.

### Job E — Operator assistance

Operators can use Hoppscotch, CyberChef and Log Voyager directly with synthetic/redacted data. Direct use is sufficient; importing these tools into the bot would create credential, data-retention and support obligations.

## 3. Architecture Combinations

### Option 1 — MINIMAL TOOL DISCOVERY

`Business Tool Registry → bot recommendation → external link`

No crawler, mini-app, automation or infrastructure dependency. This reuses the merged path and gives immediate user/owner value with the smallest rollback surface.

### Option 2 — TOOL DISCOVERY + MINI-APP

`canonical Business Tool Registry → bot + read-only Mini-App list`

The screen could improve browsing and category discovery, but it adds a second surface, navigation/UX work and another runtime read path. It is worthwhile only after bot usage demonstrates browsing demand.

### Option 3 — RESEARCH-ASSISTED TOOLBOX

`approved sources → Crawl4AI → deterministic change detection → verification queue → registry`

This adds freshness and reduces manual rechecking, but requires scheduling, retention, failure handling and owner review. It is a later workflow, not a runtime user feature.

### Option 4 — SMART GAP DISCOVERY

`user need → registry lookup → research request → crawler/research agent → pending candidate → verification`

This could expose unmet demand, but creates an intake and approval lifecycle around low-volume unknowns. It is not justified until repeated unmatched requests are measured.

### Option 5 — TOOLBOX + OPS STACK

Keep the Business Tool Registry separate and evaluate UptimeRobot, Checkly, Sentry and Socket independently. Each closes a different gap; a bundle would obscure data boundaries and make rollback harder.

### Option 6 — HYBRID CRAWLER

`Crawl4AI default → Firecrawl fallback`

The fallback is justified only by measured Crawl4AI failures on an approved public source. Until then it adds a vendor, credentials/cost or a heavier service path without evidence of benefit.

## 4. Comparison Matrix

Scores are 1–5. For effort, complexity, risk, cost and maintenance, 5 means more burden. For value and fit, 5 means stronger.

| Option | Immediate user value | Owner value | Business value | Eng. effort | Runtime complexity | New deps / infra | Security / privacy impact | Maintenance | Cost / lock-in | Fit | Failure modes | Rollback | Runtime verification | 30 days | 6 months |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---:|---:|
| 1. Minimal discovery | 5 | 5 | 4 | 1 | 1 | none | low; links only | 1 | 1 / 1 | 5 | stale/manual catalog, bad match | easy | verify merged path + regression | 5 | 4 |
| 2. Discovery + Mini-App | 4 | 4 | 4 | 3 | 2 | UI surface | medium; extra exposure surface | 3 | 2 / 1 | 4 | catalog drift, unused screen | moderate | bot + screen parity tests | 3 | 5 if browsing demand appears |
| 3. Research-assisted | 2 | 5 | 4 | 4 | 3 | crawler + scheduler + review | high; URL/content handling | 4 | 3 / 2 | 3 | crawl failure, false candidate, stale queue | moderate | isolated crawl and queue evidence | 2 | 5 if freshness pain is real |
| 4. Smart gap discovery | 2 | 4 | 3 | 5 | 4 | intake/research workflow | high; user text becomes research input | 5 | 3 / 2 | 2 | noise, duplicate approvals, scope creep | hard | end-to-end queue/approval evidence | 1 | 3 only with measured demand |
| 5. Toolbox + ops stack | 2 | 5 | 4 | 4 | 2 | each vendor separate | high; telemetry/monitoring data | 4 | 3–5 / 2–5 | 3 | noisy alerts, leaked payloads, overlap | medium | one bounded POC per tool | 3 | 4 if a measured ops gap exists |
| 6. Hybrid crawler | 2 | 3 | 3 | 5 | 4 | two crawler paths/vendor | high; two trust/deployment paths | 5 | 4 / 4 | 2 | divergent extraction, fallback ambiguity | hard | failure benchmark first | 1 | 3 only after repeated failures |

Option 1 wins now because it is already merged, read-only, reversible and useful without a new source of truth. Options 3–6 are not rejected forever; they are rejected as default next steps without a trigger.

## 5. Combination and Synergy Analysis

| Combination | Effect | Decision |
|---|---|---|
| Registry + bot | Converts a curated catalog into an immediate answer and preserves direct-use simplicity. | `1 + 1 > 2`; use now. |
| Registry + Mini-App | Adds browsing and category discovery from the same source. | Useful only after observed browsing demand; do later. |
| Registry + crawler | Reduces stale-link/manual-review burden. | Real synergy, but only when freshness is a demonstrated cost. |
| Crawler + verification | Turns extraction into reviewable evidence instead of automatic approval. | Required safety boundary for any future crawler. |
| Crawler + AI | Can reduce triage effort but adds cost and false positives. | Do not add until deterministic diff volume justifies it. |
| UptimeRobot + Sentry | Availability and exception visibility are complementary. | Potentially useful, but separate POCs and separate data boundaries. |
| Checkly + UptimeRobot | Synthetic behavior plus reachability can find different failures. | Consider only after a public endpoint and safe synthetic tenant exist. |
| Socket + GitHub | Dependency scan can strengthen review without entering runtime. | Good isolated CI POC; warning-only initially. |
| All monitoring vendors together | Overlapping alerts, more secrets and no single clear owner. | `1 + 1 = unnecessary complexity`; reject. |
| External utilities + bot execution | Removes the direct-use boundary and creates credential/approval/data paths. | Reject. |

## 6. Recommended Now — Bundle A

Use **MINIMAL TOOL DISCOVERY**:

1. Keep `business_tool_registry.py` as the single external catalog.
2. Keep `tool_registry.py` as the separate internal execution/permission registry.
3. Let the bot recommend only eligible business records and show privacy guidance plus a direct URL.
4. Keep operator and infrastructure classes hidden from normal business matching.
5. Verify the merged path with the existing regression matrix and a small set of owner scenarios.

This is one bounded cycle and requires no new integration, account, secret, database, schedule or source of truth.

## 7. Recommended Next — Bundle B

Add a read-only Mini-App/toolbox surface only after both conditions hold:

- the merged bot path is runtime-verified; and
- the owner has repeated tool discovery requests or explicitly wants browsing/categories.

The Mini-App must read the same `business_tool_registry.py` source. It must not become a second catalog, upload surface, execution path, identity model or approval system.

After that, consider the crawler only when manual re-verification of approved sources is a recurring maintenance burden. The crawler remains isolated and produces pending evidence only.

## 8. Future / Conditional — Bundle C

- `repeated stale-link/privacy changes → bounded Crawl4AI refresh POC`
- `Crawl4AI fails on an approved JS-heavy source → measure Firecrawl fallback`
- `public endpoint incidents not detected externally → UptimeRobot POC`
- `synthetic flow regressions escape unit tests → Checkly POC`
- `repeated production triage without grouping → redacted Sentry POC`
- `dependency-risk review gap → Socket warning-only CI POC`
- `high unmatched-request volume with a clear owner review process → gap-discovery intake design`
- `repeated browsing demand → Mini-App read-only catalog`

Every item requires an explicit Owner decision before credentials, external providers, scheduling, production topology or runtime changes.

## 9. Explicit Rejections

- **Crawler automatically approving tools:** false positives would pollute the only external catalog and bypass verification.
- **Multiple tool registries:** duplicates identity and creates drift between execution policy and recommendations.
- **Separate bot/TMA catalogs:** creates parallel source-of-truth maintenance; both should read one external catalog if a TMA surface is later approved.
- **Unrestricted arbitrary-URL crawling:** creates SSRF, content-injection, terms and data-exfiltration risk; use an exact HTTPS allowlist.
- **External tools executing from normal conversation:** creates credentials, uploads, action paths and approval ambiguity; direct links are sufficient.
- **Large marketplace or research-request workflow now:** speculative product surface and lifecycle burden without measured demand.
- **Combining UptimeRobot, Checkly, Sentry and Socket at once:** each has a distinct question; bundling creates noisy, expensive operations.
- **Firecrawl as a standing second crawler:** no evidence yet that Crawl4AI fails the approved workload.
- **Any vendor as business source of truth, approval authority or audit history:** violates SCOREBOS architecture boundaries.

## 10. Smallest Implementation Sequence

1. Verify `main` contains the Business Tool Registry, bot hook, crawler documents and approved catalog.
2. Run the existing registry/invariant tests and the regression matrix:
   - `אני צריך לאחד PDF` → BentoPDF;
   - `יש לי CSV שבור` → csv.repair;
   - ordinary unrelated request → normal router/no recommendation;
   - operator/infrastructure request → no normal-user result;
   - deferred/verify-first record → never presented as approved.
3. Run a few real owner scenarios with redacted or synthetic inputs and record false positives/misses.
4. Fix only confirmed matching or wording gaps in the existing catalog.
5. If browsing demand is demonstrated, design the smallest read-only Mini-App view against the same source.
6. If freshness becomes a measured burden, run the isolated Crawl4AI POC; compare evidence before considering any schedule.
7. Evaluate infrastructure candidates one at a time, beginning with the gap that has the clearest evidence.

## 11. Owner Decision Gates

The following are `OWNER DECISION REQUIRED` and are not implemented by this research:

| Change | Why the Owner must decide |
|---|---|
| Mini-App surface | New user-facing surface and maintenance commitment. |
| Scheduled production crawler | New production topology, external requests, retention and review workload. |
| Firecrawl fallback | New provider, credentials/cost, legal/data-handling terms and operational path. |
| UptimeRobot / Checkly / Sentry / Socket POC | External accounts, data boundaries, retention and alert/CI ownership. |
| Any canonical schema, ActionGateway, authorization or persistence change | Cross-layer authority and lifecycle impact. |
| Any new secret, database/table, vendor integration or production monitor | Security, privacy, cost and rollback authority. |

Until a gate is approved, the correct implementation is the existing direct-use recommendation path and the documented POCs remain plans only.
