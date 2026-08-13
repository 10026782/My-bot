# SCOREBOS — Free-for.dev Shortlist

Research-only shortlist. No POC, account, integration, or configuration is authorized by this document. Priority is a ranking aid, not an automatic decision.

## Ranked shortlist

| Rank | Tool | Classification | Category | Priority | Why it made the list |
|---:|---|---|---|---:|---|
| 1 | [UptimeRobot](https://uptimerobot.com/) | HIGH-VALUE GAP CLOSER | External monitoring | 10 | Independent public endpoint and heartbeat checks; commercial free plan, low effort. |
| 2 | [Checkly](https://www.checklyhq.com/) | USEFUL POC CANDIDATE | Synthetic API/browser testing | 7 | Tests real API/TMA behavior rather than only process health. Free-tier facts need verification. |
| 3 | [Socket](https://socket.dev/) | HIGH-VALUE GAP CLOSER | Supply-chain security | 7 | Adds a capability not listed in the SCOREBOS baseline; low-friction CI evaluation. |
| 4 | [Sentry](https://sentry.io/) | USEFUL POC CANDIDATE | Error tracking | 5 | Exception grouping/release context materially differs from normal logs. |
| 5 | [Better Stack](https://betterstack.com/pricing) | USEFUL POC CANDIDATE | Unified telemetry/monitoring | 3 | Broad capability, but personal-project free plan and major overlap reduce fit. |
| 6 | [OpenObserve](https://openobserve.ai/) | USEFUL POC CANDIDATE | Centralized logs | 2 | Could improve Render log search/retention; only if that gap is measured. Free facts need verification. |
| 7 | [Bugsink](https://www.bugsink.com/) | POSSIBLE FUTURE OPTION | Error tracking | — | Self-host/Sentry-compatible escape hatch if data residency or lock-in becomes decisive. |

## Top three POCs now — after Owner approval

### 1. UptimeRobot: independent availability

POC scope: one public health endpoint and one scheduler heartbeat. Success means a down endpoint produces an alert with acceptable latency and no sensitive data is exposed. It does not own incident response or emergency-stop state.

### 2. Checkly: synthetic TMA/API behavior

POC scope: one read-only API check and one synthetic-tenant TMA smoke test. Success means detection of a deliberate safe failure and useful evidence (status, timing, screenshot/trace as allowed). Verify the current free plan and hosted-data terms first.

### 3. Sentry: bounded exception triage

POC scope: one redacted Flask exception stream and one redacted TMA error boundary. Success means grouped issues, release/environment context, and actionable alerts without message bodies, tokens, or business records leaving approved boundaries.

## Candidate that deserves a parallel security POC

Socket is not in the top three operational POCs because it addresses the software supply chain rather than runtime behavior. It is still a high-value, low-complexity candidate for a read-only CI evaluation after Owner defines warn/fail policy.

## Do not promote based on free tier alone

Better Stack, OpenObserve, and Sentry each need data-redaction, retention, region, and ownership decisions. Free quota is not evidence of production fit.
