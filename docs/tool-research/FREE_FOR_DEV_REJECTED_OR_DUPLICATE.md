# SCOREBOS — Rejected, Duplicate, or Deferred Tools

This record prevents rediscovery of attractive but unsuitable options. A rejection here is relative to the current SCOREBOS architecture, not a claim that the product is generally poor.

## Explicitly do not introduce now

| Tool or family | Classification | Reason |
|---|---|---|
| [Trigger.dev](https://trigger.dev/) | ARCHITECTURAL DISTRACTION | Duplicates Turn Coordinator, durable state, scheduling, and AI orchestration; creates a second execution path. |
| [Cloudflare Queues](https://developers.cloudflare.com/queues/) | ARCHITECTURAL DISTRACTION | Adds another queue/runtime boundary around a Render-centered architecture and could bypass ActionGateway semantics. |
| [AnyHook](https://anyhook.net/) | ARCHITECTURAL DISTRACTION | Replayable webhook storage is risky unless every replay re-enters ActionGateway with idempotency and approval enforcement. |
| [Aserto](https://www.aserto.com/) / [Cerbos Hub](https://www.cerbos.dev/) | DUPLICATES EXISTING CAPABILITY | Duplicates Role + Scope + Capability, tenant handling, and authorization contracts. |
| [Novu](https://novu.co/) / [Courier](https://www.courier.com/) / [Knock](https://knock.app/) | DUPLICATES EXISTING CAPABILITY | Duplicates Telegram/WhatsApp/email plans and risks a parallel notification policy. |
| [Algolia](https://www.algolia.com/pricing/build-plan) for canonical data | ARCHITECTURAL DISTRACTION | Useful only as a derived search index; never a business source of truth. No current search-quality gap is established. |
| BaaS/database entries such as Back4App, Backendless, Convex, Nhost | ARCHITECTURAL DISTRACTION | Introduce new data stores and auth/runtime contracts without a confirmed persistence gap. |
| Low-code admin tools and FlutterFlow | DUPLICATES EXISTING CAPABILITY | Do not replace SCOREBOS Mini-App/admin contracts for convenience. Temporary isolated prototypes are the only plausible use. |

## Looked promising but not promoted

| Tool or family | Classification | Reason |
|---|---|---|
| [Better Stack](https://betterstack.com/pricing) | USEFUL POC CANDIDATE, tightly scoped | Strong unified telemetry, but free tier is labeled personal projects, retention is short, and it overlaps multiple existing capabilities. |
| [OpenObserve](https://openobserve.ai/) | USEFUL POC CANDIDATE, deferred | Potentially solves centralized log search/retention, but current gap is not measured and hosted free-tier facts were not confirmed. |
| [Bugsink](https://www.bugsink.com/) / [GlitchTip](https://glitchtip.com/) | POSSIBLE FUTURE OPTION | Sentry-compatible/self-hostable error tracking; keep as alternatives only if Sentry data residency or lock-in fails review. |
| Logtail, Axiom, Logz.io, Logflare, ManageEngine Log360 | DUPLICATES EXISTING CAPABILITY | Same central-log problem as OpenObserve/Better Stack; evaluating all separately creates tool sprawl. |
| Amplitude, PostHog, Umami, Aptabase | POSSIBLE FUTURE OPTION | Could answer a defined TMA/product question, but generic analytics would duplicate runtime/business telemetry and create event-taxonomy cost. |
| CloudAMQP, Ably, EMQX, Novu-style messaging | DUPLICATES / ARCHITECTURAL RISK | No confirmed queue/realtime gap; external message semantics may bypass canonical flows. |
| Auth0, Clerk, Descope, Logto, Ory, SuperTokens, WorkOS | DUPLICATES EXISTING CAPABILITY | Hosted identity may be good for a new product, but replacing or shadowing SCOREBOS identity is not justified. |
| Backendless, ConnectyCube, GetStream | NOT SUITABLE | Add backend/chat/push state already covered by SCOREBOS channels and persistent state. |
| Make, IFTTT, Integrately, Activepieces, YepCode | ARCHITECTURAL DISTRACTION | Generic automation can create ungoverned side effects and bypass ActionGateway/approvals. |
| Cloudflare Workers, Runsite, Val Town, alternative PaaS | NOT SUITABLE | Existing Render/Flask deployment is an explicit baseline; no hosting gap was found. |
| Free databases and object stores from Google/AWS/Azure/Oracle/Cloudflare | NOT SUITABLE | Free capacity is not an architectural requirement; migration or dual-write risk is high. |
| Browser session replay tools such as FullStory, LogRocket, Clarity, OpenReplay | POSSIBLE FUTURE OPTION | Useful only for a defined TMA UX/debugging problem; sensitive authenticated sessions make default capture unsafe. |

## Free-tier or source-status warnings

- Directory free-tier claims are snapshots, not contracts. Recheck before any POC.
- Checkly, OpenObserve, Bugsink, Trigger.dev, Aserto/Cerbos, notification platforms, and several analytics entries had limits or production terms that were not independently confirmed during this audit; they are marked **NEEDS VERIFICATION** in the full audit where relevant.
- Better Stack’s official page currently says “Free for personal projects”; do not assume that means SCOREBOS production/commercial use is permitted.
- Algolia’s Build plan is explicitly for development/experimentation; do not index production business data under that assumption.

## Rejection rule

Any tool that becomes a second business source of truth, permission model, approval system, action executor, or canonical queue must be rejected unless Owner and Architecture explicitly approve a replacement boundary and migration plan. This audit authorizes neither.
