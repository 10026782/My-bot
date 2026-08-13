# SCOREBOS — Firecrawl vs Crawl4AI

## Decision

**CRAWL4AI FIRST** for a bounded, self-hosted research-ingestion POC.

Firecrawl remains a **fallback POC candidate** for difficult public sites where Crawl4AI cannot reliably extract the required evidence. Do not introduce the fallback until a measured failure case exists.

The crawler is not a business tool and is not an approval or publication path:

`approved sources → crawler → clean content → candidate → research queue → verification → canonical tool registry`

The crawler must never approve, publish, execute, or write canonical SCOREBOS state.

## Evidence convention

- **OBSERVED** — stated in current official repository or documentation.
- **INFERRED** — engineering conclusion from those capabilities and SCOREBOS constraints.
- **NEEDS VERIFICATION** — must be tested in the isolated POC or confirmed against the selected release.

## Comparison

| Dimension | Firecrawl | Crawl4AI | Status / SCOREBOS reading |
|---|---|---|---|
| License | AGPL-3.0 for the main project; SDKs/some UI are MIT | Apache 2.0 with attribution requirement from v0.5 | OBSERVED; legal review still needed before distribution |
| Maturity/activity | Large active open-source project with cloud product and SDKs | Large active project; current docs advertise 50k+ stars and frequent releases | OBSERVED; exact operational maturity is not proof of reliability |
| Python fit | Python SDK, but service/API-first ergonomics | Native Python package and async API | OBSERVED; Crawl4AI fits the existing backend better |
| API key/account | Cloud use requires signup/API key | Local package and Docker path advertise zero keys | OBSERVED |
| Self-hosting | Supported, but Compose includes API, workers, PostgreSQL, Redis and RabbitMQ concerns | Supported through pip or Docker; server has auth/loopback hardening | OBSERVED; both need isolation before exposure |
| Hosted option | First-party cloud | Cloud is described as closed beta / upcoming | OBSERVED; hosted Crawl4AI is not a current assumption |
| JS/browser support | Playwright plus fallback; actions can click, scroll, write, wait | Playwright browser, wait conditions, shadow DOM flattening and browser config | OBSERVED; both cover dynamic public pages |
| Sessions/auth | Supports complex navigation/auth claims and interaction | Supports cookies, headers, sessions, CDP and identity configuration | OBSERVED; **NEEDS VERIFICATION** for SCOREBOS; authenticated crawling is out of this POC |
| Markdown | Native clean Markdown output | Native Markdown output and filters | OBSERVED |
| Structured extraction | JSON/schema extraction and extract endpoint | CSS/XPath/LLM extraction strategies and schema support | OBSERVED; deterministic extraction preferred |
| Crawl/map | Crawl jobs, batch scrape and Map endpoint | BFS/DFS deep crawl, URL discovery and prefetch | OBSERVED |
| Screenshots/PDF | Scrape formats include screenshots and media/PDF parsing | Screenshot, PDF and MHTML capture | OBSERVED |
| Cache/retry | API/service manages orchestration, retries and rate limits; exact cache semantics are **NEEDS VERIFICATION** | Cache modes, retry controls, proxy fallback and crash recovery/resume state | OBSERVED; exact default tuning is **NEEDS VERIFICATION** |
| Proxies/rate limits | Rotating proxies and rate limits are advertised | Proxy configuration/rotation and retry support | OBSERVED; not enabled for the POC |
| Observability/recovery | Hosted/job model; self-host persistence and monitoring are deployment responsibilities | Docker dashboard/monitoring plus crawl state callbacks/resume | OBSERVED; production SLO evidence is **NEEDS VERIFICATION** |
| Security model | Self-host guide warns default API is unauthenticated and dependencies need private networking | Recent Docker releases add auth, loopback defaults and request-boundary hardening; library users must validate URLs | OBSERVED; neither is safe for arbitrary URLs by default |
| Resources/deployment | Higher footprint: service graph and queues; hosted path is simpler but vendor-dependent | Browser runtime is heavy but single-process POC is simpler; Docker adds operational surface | INFERRED |
| Render fit | Likely poor as an embedded web process; possible only as separately managed worker/service | Likely suitable for a bounded worker/container, subject to Chromium RAM/time limits | INFERRED; benchmark required |
| Maintenance burden | Higher self-host burden; lower application code burden | Lower initial code burden; browser/dependency upgrades remain SCOREBOS responsibility | INFERRED |
| Vendor lock-in | Higher when using cloud API and credits | Lower for local Python/HTML/Markdown pipeline | INFERRED |
| Small-scale cost | Cloud credits/API fees, or significant self-host compute | Mostly compute/storage; optional LLM cost only for filtered changes | INFERRED; measure before budget claim |

Sources: [Firecrawl README](https://github.com/firecrawl/firecrawl/blob/main/README.md), [Firecrawl self-hosting](https://github.com/firecrawl/firecrawl/blob/main/SELF_HOST.md), [Firecrawl crawl](https://docs.firecrawl.dev/features/crawl), [Firecrawl map](https://docs.firecrawl.dev/features/map), [Crawl4AI README](https://github.com/unclecode/crawl4ai), [Crawl4AI configuration](https://docs.crawl4ai.com/core/browser-crawler-config/), [Crawl4AI changelog/security hardening](https://github.com/unclecode/crawl4ai/blob/main/CHANGELOG.md).

## Fit matrix

Scores are 1 (poor) to 5 (strong). They are decision input, not the decision itself.

| Criterion | Firecrawl | Crawl4AI | Explanation |
|---|---:|---:|---|
| Setup simplicity | 4 hosted / 2 self-host | 4 | Crawl4AI is one Python dependency for the POC; browsers still add setup work |
| Python fit | 4 | 5 | Crawl4AI is Python-native; Firecrawl is SDK/API-native |
| Control | 3 | 5 | Local browser/configuration gives more control |
| Reliability | 4 hosted | 3 | Firecrawl manages more service concerns; Crawl4AI needs local operations proof |
| Dynamic-site coverage | 4 | 4 | Both use browser automation; site-specific testing decides |
| Extraction quality | 4 | 4 | Both provide clean Markdown and structured paths |
| Structured output | 5 | 4 | Firecrawl’s extract/schema workflow is more turnkey |
| Self-hosting | 3 | 4 | Both self-host; Firecrawl’s service graph is heavier |
| Operational burden | 2 self-host / 4 hosted | 3 | Firecrawl self-hosting has more moving parts |
| Security | 3 | 3 | Both require URL allowlists, isolation and content handling |
| Cost | 3 | 4 | Crawl4AI avoids hosted credits at small scale; compute is still real |
| Vendor independence | 2 | 5 | Firecrawl cloud creates provider/credit dependence |
| Scheduled research | 4 | 4 | Both can support bounded jobs; scheduler is SCOREBOS-owned later |
| Agent-driven research | 5 | 4 | Firecrawl has stronger agent-facing hosted APIs; this is out of POC scope |

## Use-case fit

| Use case | Preferred path | Reason |
|---|---|---|
| A. Tool directory monitoring | Crawl4AI | Scheduled, allowlisted, deterministic snapshots and section hashes are enough |
| B. Official tool verification | Crawl4AI first; Firecrawl fallback | Keep evidence local; use fallback only after measured extraction failure |
| C. UX reference collection | Crawl4AI for public snapshots | Screenshots are useful evidence, but never replace authenticated UX inspection |
| D. Bounded business research | Crawl4AI | Local control and no provider lock-in fit a small approved source list |

## Recommendation boundary

Use Crawl4AI as the default controlled crawler for public, approved, bounded sources. Do not use its LLM extraction, hooks, proxies or authenticated sessions in the first POC.

Consider Firecrawl only when all are true:

1. the source is public and approved;
2. Crawl4AI fails a documented extraction test;
3. the extra API/provider data path is accepted by the owner;
4. the result remains a pending evidence record;
5. the secret and network boundary are isolated from SCOREBOS runtime.

## Cost-control conclusion

For 20 sources, one crawl/day, the first implementation should use one bounded request per source, URL/domain allowlists, normalized section hashes and local snapshots. Send only changed sections to later review. Do not use an LLM for unchanged pages. The POC must measure browser time, peak memory if available, output bytes and failures; no credible currency estimate is claimed before that run.

## Unknowns to close in POC

- JS rendering success and timing on the selected four sources.
- Chromium memory and CPU on the intended Render-like environment.
- Actual change-detection precision after boilerplate normalization.
- Crawl4AI release pin and browser compatibility.
- Firecrawl cloud credit usage and self-host recovery behavior.
- Whether any source blocks automated access or has terms that prohibit the test.

## Decision

`CRAWL4AI FIRST` — local isolated POC only. No production integration, persistent crawler service, arbitrary URL input, authenticated crawling, automatic approval or canonical registry write.
