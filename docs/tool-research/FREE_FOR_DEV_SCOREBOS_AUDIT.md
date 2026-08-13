# SCOREBOS — Free-for.dev Tool Opportunity Audit

**Research date:** 2026-08-13  
**Scope:** research and classification only. No vendors were installed, connected, configured, or trialed.

## Executive conclusion

Free-for.dev is useful as a discovery source, but most entries duplicate capabilities SCOREBOS already has or would introduce a second system of record. The strongest opportunities are deliberately narrow support services:

1. **UptimeRobot** for an independent external availability signal.
2. **Checkly** for synthetic API/browser checks, especially TMA/WebView flows.
3. **Sentry** for exception aggregation and release-aware stack traces.

**OpenObserve** and **Socket** are credible secondary POC candidates, but only after Owner review of data boundaries and the actual gap. **Better Stack** is attractive technically, but its free plan is described as for personal projects and it overlaps with logs, incidents, error tracking, and uptime; it is therefore a narrowly scoped POC candidate, not a platform recommendation.

The repository contained no SCOREBOS source or documentation beyond metadata at audit time. Existing-capability comparisons therefore use the supplied SCOREBOS context, not inferred absence from this checkout.

## Method and source notes

The primary directory was [free-for.dev](https://free-for.dev/), whose maintained source describes itself as an opinionated list of free as-a-service offerings and explicitly excludes self-hosted-only software. I screened entries in the 16 requested categories and followed official product/pricing/documentation pages for the serious candidates. Directory claims that could not be confirmed from an official current page are marked **NEEDS VERIFICATION** rather than silently corrected.

**Screening count:** 16 categories reviewed; 126 directory entries screened; 15 serious candidates examined in detail; 7 shortlisted as `HIGH-VALUE GAP CLOSER` or `USEFUL POC CANDIDATE`.

## Capability baseline used for comparison

SCOREBOS is assumed to already cover Telegram/WhatsApp interaction, Flask/Render runtime, Airtable and Google APIs, identity and role/scope/tenant handling, approvals, ActionGateway, Turn Coordinator, persistent state, runtime observability, feature flags, emergency stop, logs, marketing workflows, business memory, TMA/Mini-App, and AI orchestration.

External tools may provide telemetry, independent probes, or development diagnostics. They must not own canonical business state, approvals, permissions, action execution, or emergency-stop decisions.

## Category review

| Category | Entries screened | Finding |
|---|---:|---|
| Logging / Observability | 8 | Potential gap is centralized, searchable, longer-lived evidence outside Render; do not replace existing logs by default. |
| Error Tracking | 11 | Exception aggregation is materially different from ordinary logs; a narrow POC is justified. |
| Audit Trail / Activity History | 3 | External activity-log products risk becoming a second governance record; retain canonical audit history in SCOREBOS. |
| Monitoring / Uptime / Alerts | 12 | Independent external probes are a likely gap because internal health cannot prove external reachability. |
| Databases / Storage | 8 | No confirmed migration gap; existing Airtable/Google/state contracts make most BaaS/DB entries distractions. |
| Queues / Workers / Scheduling | 7 | Existing Turn Coordinator/scheduler architecture means no replacement candidate is justified. |
| Authentication / Authorization | 12 | Existing Role + Scope + Capability model makes hosted identity/authorization duplication high risk. |
| Search / Indexing | 4 | Algolia is a possible retrieval POC only after Business Memory search requirements are defined. |
| Analytics / Product Analytics | 10 | Product telemetry could help TMA usage questions, but it duplicates existing runtime/business analytics unless the question is explicitly defined. |
| AI / LLM Infrastructure | 8 | The directory contains many model/agent layers; SCOREBOS already has orchestration. No replacement is justified. |
| Low-Code / Admin / Internal Tools | 6 | Useful for temporary prototypes, not a Mini-App or admin-system replacement. |
| Notifications / Messaging / Email | 8 | Existing Telegram/WhatsApp and email plans cover the core need; providers add routing complexity. |
| Webhooks / Automation / Integrations | 6 | Durable relay is interesting, but must not bypass ActionGateway or approval checks. |
| Backups / Recovery | 4 | No tool in the screened set was a confirmed fit for canonical Airtable/Google/business recovery. |
| Security / Secrets / API Protection | 8 | Socket is a useful dependency/supply-chain check; hosted secrets/WAF entries overlap deployment boundaries or require Owner policy. |
| Testing / Browser / Mobile Debugging | 9 | Synthetic API/browser testing is a likely gap for authenticated TMA/WebView behavior. |

## Serious candidates

### 1. UptimeRobot

| Field | Assessment |
|---|---|
| Tool / category | [UptimeRobot](https://uptimerobot.com/) — Monitoring / uptime / alerts |
| Free-tier summary | Official help says 50 monitors, 5-minute checks, status pages, HTTP/keyword/ping/port/heartbeat monitoring, commercial use allowed, and no card required. |
| Problem solved | Independent checks of public Flask/Render endpoints and heartbeat endpoints, with downtime alerts outside the Render process. |
| SCOREBOS gap addressed | External availability and deadman/heartbeat evidence; internal logs cannot prove that Telegram-facing or public endpoints are reachable from outside. |
| Existing overlap | Render health checks, runtime observability, logs, emergency stop. It supplements them; it must not become incident authority. |
| Integration complexity | Low |
| Vendor lock-in | Low |
| Self-hostable / API | No / Yes, API and integrations are available; verify exact free-plan access before POC. |
| Production suitability | Good for low-frequency external checks; 5-minute detection is not real-time and free plan has limited seats/integrations. |
| Data sensitivity | Keep probes to public health/heartbeat endpoints; never put tokens, customer data, or business payloads in URLs or response bodies. |
| Main benefit | Independent signal with low implementation and operational cost. |
| Main risk | False confidence if health endpoint only says “process alive”; alert fatigue and free-tier limitations. |
| Classification | **HIGH-VALUE GAP CLOSER** |
| Priority | Impact 4 + Urgency 4 + Free-tier usefulness 5 − Effort 1 − Risk 2 = **10** |
| Recommended next step | Owner-approved POC with one public health check and one scheduler heartbeat; define alert ownership and evidence retention first. |

### 2. Checkly

| Field | Assessment |
|---|---|
| Tool / category | [Checkly](https://www.checklyhq.com/) — Testing / synthetic monitoring |
| Free-tier summary | The directory lists a free plan with one user, 10k API/network runs, and 1.5k browser runs. The official pricing page was not machine-readable during this audit: **NEEDS VERIFICATION**. |
| Problem solved | Repeatable API and real-browser checks for login, TMA/WebView loading, authenticated navigation, and critical read-only flows. |
| SCOREBOS gap addressed | External behavioral verification; uptime checks alone cannot detect a broken authenticated UI or webhook contract. |
| Existing overlap | Existing tests, runtime logs, TMA/Mini-App, and feature flags. It should test contracts, not implement them. |
| Integration complexity | Medium |
| Vendor lock-in | Medium |
| Self-hostable / API | No / Yes, API/CLI workflow is advertised; verify current plan and data-region terms. |
| Production suitability | Good for synthetic checks if test accounts and safe fixtures exist; browser minutes/one-user limits may constrain coverage. |
| Data sensitivity | Test accounts, session cookies, tokens, customer-like data, screenshots, and traces may leave approved boundaries. Use synthetic tenants only. |
| Main benefit | Finds regressions in external and browser behavior before users report them. |
| Main risk | A hosted browser may capture sensitive state; tests can mutate business data if not designed read-only. |
| Classification | **USEFUL POC CANDIDATE** |
| Priority | Impact 5 + Urgency 4 + Free-tier usefulness 4 − Effort 3 − Risk 3 = **7** |
| Recommended next step | Verify pricing/security/API facts, then design two read-only tests: public health and a synthetic TMA smoke path. |

### 3. Sentry

| Field | Assessment |
|---|---|
| Tool / category | [Sentry](https://sentry.io/) — Error tracking |
| Free-tier summary | The directory lists 5,000 errors/month and one user. Official material confirms a free Developer plan, SDKs for 100+ languages/frameworks, and US/EU data locations; exact current quota should be confirmed at signup. |
| Problem solved | Aggregates exceptions, groups stack traces, adds tags/releases, and separates recurring defects from raw logs. |
| SCOREBOS gap addressed | Likely gap in exception triage and release correlation, especially Flask backend and TMA frontend failures. |
| Existing overlap | Runtime observability and logs. Sentry must be diagnostic telemetry only, not audit history or action evidence. |
| Integration complexity | Medium |
| Vendor lock-in | Medium |
| Self-hostable / API | Yes, self-hosted option exists / Yes |
| Production suitability | Good for a bounded error stream; free quota, one-user access, retention, and attachments need confirmation. |
| Data sensitivity | Scrub PII, tokens, message contents, Airtable records, prompts, and business payloads. Select EU/US region deliberately. |
| Main benefit | Faster debugging through grouping, stack traces, breadcrumbs, release/environment context, and alerts. |
| Main risk | Accidental exfiltration of sensitive conversational/business data and another operational inbox. |
| Classification | **USEFUL POC CANDIDATE** |
| Priority | Impact 4 + Urgency 3 + Free-tier usefulness 4 − Effort 3 − Risk 3 = **5** |
| Recommended next step | Owner review of telemetry redaction and region; if approved, instrument one non-sensitive Flask error path and one TMA error boundary. |

### 4. Better Stack

| Field | Assessment |
|---|---|
| Tool / category | [Better Stack](https://betterstack.com/pricing) — Monitoring / logs / error tracking |
| Free-tier summary | Official pricing currently shows free-for-personal-projects: 10 monitors/heartbeats, 1 status page, 100k exceptions/month, 5,000 replays, 3 GB logs and traces retained 3 days, and 30 GB metrics. |
| Problem solved | A unified external monitor/status/telemetry surface with SQL-like log querying and alerting. |
| SCOREBOS gap addressed | Potentially reduces fragmented diagnostic tooling and adds independent uptime/status. |
| Existing overlap | Strong overlap with runtime observability, logs, alerts, error tracking, and incident workflows. |
| Integration complexity | Medium |
| Vendor lock-in | Medium |
| Self-hostable / API | No / Yes, REST/API and webhooks are listed. |
| Production suitability | Free plan’s personal-project wording makes production/commercial suitability **NEEDS VERIFICATION**; 3-day retention is weak for governance evidence. |
| Data sensitivity | Centralizes logs, traces, exceptions, replays, and potentially user data. Scrub aggressively; do not send business payloads. |
| Main benefit | One diagnostic view with external monitoring and broad free quotas. |
| Main risk | Platform sprawl and overlap; free-plan eligibility/retention may fail SCOREBOS requirements. |
| Classification | **USEFUL POC CANDIDATE** |
| Priority | Impact 3 + Urgency 3 + Free-tier usefulness 4 − Effort 3 − Risk 4 = **3** |
| Recommended next step | Do not adopt as a platform. Only compare against Sentry + UptimeRobot in a redacted telemetry POC after Owner review. |

### 5. OpenObserve

| Field | Assessment |
|---|---|
| Tool / category | [OpenObserve](https://openobserve.ai/) — Logging / observability |
| Free-tier summary | The directory lists 200 GB ingestion/month and 15-day retention; current hosted-plan details were not independently confirmed in this pass: **NEEDS VERIFICATION**. |
| Problem solved | Centralized structured logs, traces, dashboards, and search, with an open-source/self-hostable path. |
| SCOREBOS gap addressed | Longer-lived, queryable diagnostic logs beyond ephemeral Render visibility, if that gap is confirmed. |
| Existing overlap | Runtime observability, logs, and execution evidence. It must not replace canonical SCOREBOS audit records. |
| Integration complexity | Medium/High |
| Vendor lock-in | Low/Medium |
| Self-hostable / API | Yes / Yes |
| Production suitability | Potentially good if self-hosted or the hosted plan meets retention/security needs; free-tier facts are **NEEDS VERIFICATION**. |
| Data sensitivity | Logs can contain chat content, identifiers, tokens, prompt data, and business records. Use a redaction contract and retention policy. |
| Main benefit | OpenTelemetry-compatible central diagnostics with lower lock-in than a closed observability suite. |
| Main risk | Operating another stateful service defeats the “reduce complexity” goal; hosted data boundary remains unresolved. |
| Classification | **USEFUL POC CANDIDATE** |
| Priority | Impact 4 + Urgency 2 + Free-tier usefulness 4 − Effort 4 − Risk 4 = **2** |
| Recommended next step | First measure Render log search/retention pain. If material, compare hosted vs self-hosted cost and operating burden before any POC. |

### 6. Socket

| Field | Assessment |
|---|---|
| Tool / category | [Socket](https://socket.dev/) — Security / dependency and supply-chain scanning |
| Free-tier summary | The directory describes a free app and firewall CLI for individual developers, small teams, and open source, detecting 70+ supply-chain risk indicators. Current commercial limits should be confirmed. |
| Problem solved | Flags malicious or suspicious dependency behavior and supply-chain risk in pull requests/CI. |
| SCOREBOS gap addressed | No listed SCOREBOS capability explicitly covers dependency/supply-chain scanning; this is a likely engineering-security gap. |
| Existing overlap | General tests, logs, and deployment controls, but not dependency-intent analysis. |
| Integration complexity | Low/Medium |
| Vendor lock-in | Low |
| Self-hostable / API | Unknown / Yes, CLI/API integrations are advertised; verify. |
| Production suitability | Good as a CI gate or advisory scanner; not a runtime protection system. |
| Data sensitivity | Source/package metadata and manifests leave the repository boundary; review organization and retention terms. |
| Main benefit | Low-friction early warning for compromised or risky dependencies. |
| Main risk | False positives, policy noise, or assuming it replaces vulnerability scanning and code review. |
| Classification | **HIGH-VALUE GAP CLOSER** |
| Priority | Impact 4 + Urgency 3 + Free-tier usefulness 4 − Effort 2 − Risk 2 = **7** |
| Recommended next step | Owner-approved read-only CI evaluation on the existing dependency set; define fail vs warn policy before enforcement. |

### 7. Algolia

| Field | Assessment |
|---|---|
| Tool / category | [Algolia](https://www.algolia.com/pricing/build-plan) — Search / indexing |
| Free-tier summary | Official Build plan lists 1M records and 10k search requests/month, intended for development/experimentation; Grow includes a smaller production free allowance. |
| Problem solved | Fast typo-tolerant keyword search, suggestions, ranking, and index-backed retrieval. |
| SCOREBOS gap addressed | Could support Business Memory/contact/project/lead retrieval if current Airtable/search behavior is demonstrably inadequate. |
| Existing overlap | Business Memory, Airtable/business data, and AI orchestration. Index must remain a derived read model, never canonical state. |
| Integration complexity | High |
| Vendor lock-in | High |
| Self-hostable / API | No / Yes |
| Production suitability | Good search service, but Build is development-oriented and data synchronization/quotas need design. |
| Data sensitivity | Indexing contacts, deals, prompts, or tenant data creates a second external copy and needs tenant isolation, deletion, and redaction controls. |
| Main benefit | Better retrieval UX without building a search engine. |
| Main risk | Duplicate business data, stale indexes, deletion/tenant leakage, and cost expansion beyond the free tier. |
| Classification | **POSSIBLE FUTURE OPTION** |
| Recommended next step | Define search quality and scale requirements first; run offline relevance tests against a sanitized export before considering a hosted index. |

### 8. Bugsink

| Field | Assessment |
|---|---|
| Tool / category | [Bugsink](https://www.bugsink.com/) — Error tracking |
| Free-tier summary | Directory entry: Sentry-SDK-compatible, up to 5,000 errors/month, unlimited when self-hosted. Current plan and hosted data terms are **NEEDS VERIFICATION**. |
| Problem solved | Exception aggregation with a potentially lower-lock-in/self-hosted route. |
| SCOREBOS gap addressed | Same bounded error-triage gap as Sentry. |
| Existing overlap | Runtime observability and logs. |
| Integration complexity | Medium |
| Vendor lock-in | Low/Medium due to SDK compatibility and self-hosting. |
| Self-hostable / API | Yes / Unknown |
| Production suitability | Potentially suitable if self-hosted operations are acceptable; hosted facts need verification. |
| Data sensitivity | Same exception payload, PII, token, and prompt risks as Sentry. |
| Main benefit | Error tracking with an escape hatch. |
| Main risk | Smaller ecosystem and new operational burden if self-hosted. |
| Classification | **POSSIBLE FUTURE OPTION** |
| Recommended next step | Compare with Sentry only if data residency or self-hosting is a decision driver. |

### 9. AnyHook

| Field | Assessment |
|---|---|
| Tool / category | [AnyHook](https://anyhook.net/) — Webhooks / integration delivery |
| Free-tier summary | Directory and official site describe inbound relay, storage-before-delivery, automatic retries, logs/replay, 3,000 events/month, 3 retries, and 3-day retention. |
| Problem solved | Buffers inbound webhook events when SCOREBOS is unavailable and provides replay. |
| SCOREBOS gap addressed | Possible delivery durability for external webhooks, but only if existing ingress lacks persistence/retry evidence. |
| Existing overlap | ActionGateway, canonical action execution, approvals, persistent state, and logs. |
| Integration complexity | Medium |
| Vendor lock-in | Medium |
| Self-hostable / API | Unknown / Yes, API creation is advertised. |
| Production suitability | Useful as a relay only; 3-day retention and unclear security/tenant controls are limiting. |
| Data sensitivity | Webhook payloads may contain payment, identity, customer, or business data. External storage is high-risk. |
| Main benefit | Simple store-and-forward behavior. |
| Main risk | Creates a replay/integration path that can bypass canonical validation, idempotency, approvals, or emergency stop. |
| Classification | **ARCHITECTURAL DISTRACTION** |
| Recommended next step | Do not POC unless Architecture explicitly defines it as an ingress buffer that forwards only into ActionGateway with idempotency and approval enforcement. |

### 10. Aserto / Cerbos Hub

| Field | Assessment |
|---|---|
| Tool / category | [Aserto](https://www.aserto.com/) / [Cerbos Hub](https://www.cerbos.dev/) — Authorization |
| Free-tier summary | Directory lists fine-grained authorization free tiers, with Aserto at 1,000 MAUs/100 authorizers and Cerbos Hub at 100 monthly active principals. Current limits are **NEEDS VERIFICATION**. |
| Problem solved | External policy decision point and authorization-policy management. |
| SCOREBOS gap addressed | None confirmed; SCOREBOS already has Role + Scope + Capability and tenant handling. |
| Existing overlap | Directly duplicates identity/authorization and approval boundaries. |
| Integration complexity | High |
| Vendor lock-in | Medium/High |
| Self-hostable / API | Aserto: Unknown/Yes; Cerbos: Yes/Yes |
| Production suitability | Technically credible, but not justified without a policy-scale or compliance gap. |
| Data sensitivity | Identity, tenant, role, capability, and authorization context would cross a new boundary. |
| Main benefit | Possible policy testing/centralization later. |
| Main risk | Split-brain permissions and accidental authorization bypass. |
| Classification | **DUPLICATES EXISTING CAPABILITY** |
| Recommended next step | Do not introduce; revisit only through an Architecture decision to replace, not shadow, the canonical model. |

### 11. Trigger.dev

| Field | Assessment |
|---|---|
| Tool / category | [Trigger.dev](https://trigger.dev/) — Queues / workers / scheduling / AI jobs |
| Free-tier summary | Directory lists $5 monthly compute credits, 20 concurrent runs, unlimited tasks, 5 team members, 10 schedules, and 1-day logs. Current limits are **NEEDS VERIFICATION**. |
| Problem solved | Durable background jobs, retries, schedules, and realtime task state. |
| SCOREBOS gap addressed | None confirmed; SCOREBOS already has a Turn Coordinator, persistent state, scheduler, and AI orchestration. |
| Existing overlap | Directly overlaps runtime execution, scheduling, retries, and orchestration. |
| Integration complexity | High |
| Vendor lock-in | High |
| Self-hostable / API | Yes / Yes |
| Production suitability | Strong product, but adding it would create a parallel runtime path. |
| Data sensitivity | Job payloads, prompts, tokens, and business actions would cross a new runtime boundary. |
| Main benefit | Faster job-platform prototyping. |
| Main risk | Duplicate execution authority and inconsistent state/approval semantics. |
| Classification | **ARCHITECTURAL DISTRACTION** |
| Recommended next step | Do not introduce for convenience. Address any scheduler gap inside existing SCOREBOS contracts. |

### 12. Novu / Courier / Knock

| Field | Assessment |
|---|---|
| Tool / category | [Novu](https://novu.co/) / [Courier](https://www.courier.com/) / [Knock](https://knock.app/) — Notifications |
| Free-tier summary | Directory lists approximately 30k, 10k, and 10k notifications/messages per month respectively; exact current limits are **NEEDS VERIFICATION**. |
| Problem solved | Multi-channel templates and notification routing. |
| SCOREBOS gap addressed | None confirmed; Telegram/WhatsApp interaction and email plans already exist. |
| Existing overlap | Marketing workflows, messaging, approvals, and user-facing notification policy. |
| Integration complexity | Medium/High |
| Vendor lock-in | Medium/High |
| Self-hostable / API | Novu: Yes/Yes; Courier/Knock: Unknown/Yes |
| Production suitability | Potentially useful for a standalone product, but not justified for current SCOREBOS channels. |
| Data sensitivity | Contact details, message content, tenant routing, and approval-sensitive notifications. |
| Main benefit | Template management across many channels. |
| Main risk | Parallel delivery policy and messages sent outside canonical action/approval flow. |
| Classification | **DUPLICATES EXISTING CAPABILITY** |
| Recommended next step | Do not introduce unless a specific channel/template/volume gap is documented. |

### 13. Cloudflare Queues

| Field | Assessment |
|---|---|
| Tool / category | [Cloudflare Queues](https://developers.cloudflare.com/queues/) — Queues / workers |
| Free-tier summary | Directory lists 1M operations/month. Current plan details and account eligibility should be verified. |
| Problem solved | Managed message buffering and asynchronous delivery. |
| SCOREBOS gap addressed | None confirmed; persistent state and coordinator already exist. |
| Existing overlap | Turn Coordinator, workers, ActionGateway, and deployment architecture. |
| Integration complexity | High |
| Vendor lock-in | High |
| Self-hostable / API | No / Yes |
| Production suitability | Good as Cloudflare-native infrastructure, but poor fit for a Render-centered runtime without a clear boundary. |
| Data sensitivity | Queue payloads may carry business actions and secrets. |
| Main benefit | Durable buffering at scale. |
| Main risk | Second runtime and message semantics; can bypass approvals/idempotency. |
| Classification | **ARCHITECTURAL DISTRACTION** |
| Recommended next step | No POC without an Architecture decision defining queue ownership and ActionGateway-only consumption. |

### 14. PostHog / Amplitude

| Field | Assessment |
|---|---|
| Tool / category | [PostHog](https://posthog.com/pricing) / [Amplitude](https://amplitude.com/pricing) — Product analytics |
| Free-tier summary | The directory lists Amplitude at 1M monthly events and PostHog as a free product-analytics option; current plans and limits are **NEEDS VERIFICATION**. |
| Problem solved | Funnels, feature usage, retention, and product behavior analysis. |
| SCOREBOS gap addressed | Possible TMA adoption/UX measurement gap, not a backend observability gap. |
| Existing overlap | Runtime observability, marketing workflows, business analytics, and feature flags. |
| Integration complexity | Medium |
| Vendor lock-in | Medium |
| Self-hostable / API | PostHog: Yes/Yes; Amplitude: No/Yes |
| Production suitability | Good only with a defined product question and privacy model. |
| Data sensitivity | User identifiers, sessions, tenant activity, and interaction events require consent/redaction. |
| Main benefit | Product decisions from behavioral evidence. |
| Main risk | Event-taxonomy sprawl and tracking sensitive business actions. |
| Classification | **POSSIBLE FUTURE OPTION** |
| Recommended next step | Define one TMA funnel and event contract first; do not add generic tracking. |

### 15. Logz.io / Logtail / Axiom

| Field | Assessment |
|---|---|
| Tool / category | [Logtail/Better Stack](https://betterstack.com/logtail) / [Axiom](https://axiom.co/) / [Logz.io](https://logz.io/) — Logs |
| Free-tier summary | Directory entries advertise small free log volumes or short retention; current limits vary and are **NEEDS VERIFICATION**. |
| Problem solved | Central log aggregation and search. |
| SCOREBOS gap addressed | Only if Render/runtime log search and retention are inadequate. |
| Existing overlap | Runtime observability and logs. |
| Integration complexity | Medium |
| Vendor lock-in | Medium |
| Self-hostable / API | Varies / Yes |
| Production suitability | Depends on retention, export, redaction, and plan limits. |
| Data sensitivity | High: logs can contain all SCOREBOS context if structured logging is careless. |
| Main benefit | Searchable diagnostics. |
| Main risk | Tool duplication and data leakage. |
| Classification | **DUPLICATES EXISTING CAPABILITY** |
| Recommended next step | Do not evaluate separately; compare only as part of the OpenObserve/Better Stack telemetry decision. |

## Architecture guardrails for any future POC

- External tools receive diagnostics or probes, not canonical business state.
- Action execution remains exclusively behind ActionGateway.
- Approval, emergency-stop, identity, tenant, and capability checks remain in SCOREBOS.
- Any derived index or replay buffer needs idempotency, tenant isolation, deletion behavior, retention, and an explicit source-of-truth declaration.
- Test accounts and synthetic data only; no production customer payloads in browser recordings or error breadcrumbs.
- POC success must be measured against a named problem: detection time, triage time, false-positive rate, coverage, or search relevance.

## Gaps with no good current candidate

1. **Canonical business-data backup and recovery.** The directory has storage/database options, but none inspected provides a clearly suitable, policy-safe backup/restore path for Airtable, Google data, business memory, runtime configuration, and tenant boundaries together.
2. **Governance-grade action evidence.** External audit-log products can store activity, but they cannot safely replace SCOREBOS’s canonical action/approval history. The gap, if any, should be addressed in SCOREBOS contracts, not outsourced as a parallel record.
3. **End-to-end WhatsApp/Telegram delivery assurance.** Uptime tools can check endpoints and heartbeats, but they cannot prove provider-side delivery, user receipt, or semantic correctness without a carefully designed synthetic test harness.

## Owner / Architecture decisions required before any POC

- Whether business and conversational data may be sent to a hosted telemetry vendor, and which region is allowed.
- Whether SCOREBOS needs one narrow monitor/error tool or intentionally accepts a unified observability platform.
- Whether a synthetic test account/tenant can be created and what actions are permitted.
- The retention and deletion policy for logs, screenshots, traces, errors, and heartbeat history.
- Whether Socket may run in CI and whether findings fail builds or only warn.
- Any proposal involving AnyHook, Cloudflare Queues, Trigger.dev, Aserto/Cerbos, notifications vendors, or search indexing requires Architecture review because it can create a parallel execution, permission, messaging, or data path.

## Source register

- [free-for.dev directory](https://free-for.dev/) and [maintained source repository](https://github.com/ripienaar/free-for-dev)
- [UptimeRobot free plan](https://help.uptimerobot.com/en/articles/11604710-who-should-use-uptimerobot-s-free-plan) and [pricing](https://uptimerobot.com/pricing/)
- [Better Stack pricing](https://betterstack.com/pricing)
- [Sentry pricing](https://sentry.io/pricing/) and [data-region announcement](https://sentry.io/changelog/data-storage-location-in-germany-is-generally-available/)
- [Algolia Build plan](https://www.algolia.com/pricing/build-plan)
- [Checkly](https://www.checklyhq.com/)
- [OpenObserve](https://openobserve.ai/)
- [Bugsink](https://www.bugsink.com/)
- [Socket](https://socket.dev/)
- [AnyHook](https://anyhook.net/)
- [Cloudflare Queues](https://developers.cloudflare.com/queues/)
- [Trigger.dev](https://trigger.dev/)
- [Aserto](https://www.aserto.com/) and [Cerbos](https://www.cerbos.dev/)
- [Novu](https://novu.co/), [Courier](https://www.courier.com/), and [Knock](https://knock.app/)
- [PostHog](https://posthog.com/pricing) and [Amplitude](https://amplitude.com/pricing)
