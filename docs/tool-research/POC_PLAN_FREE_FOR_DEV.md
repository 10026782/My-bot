# SCOREBOS — Free-for.dev POC Plans

**Status:** Planning only — no tools installed, no accounts created, no vendors connected, no secrets added, and no SCOREBOS runtime or code changed.  
**Scope:** Four approved candidates only: UptimeRobot, Checkly, Sentry, and Socket.

## Non-negotiable guardrails

- These POCs are diagnostic or development-support experiments, not new SCOREBOS runtime authorities.
- No tool may own business state, approvals, identity/permissions, ActionGateway execution, emergency-stop decisions, or canonical audit history.
- No production secrets may be added to any vendor.
- No production customer, tenant, contact, message, prompt, financial, property, or candidate data may leave SCOREBOS.
- Any account/configuration is Owner-controlled and must be created only after the decision gate below.
- A POC must be reversible without changing business data or requiring a migration.

## Decision status

| Candidate | Decision status | Gate |
|---|---|---|
| UptimeRobot | APPROVE AFTER POLICY | Owner approves public health/heartbeat shape, alert owner, retention, and external monitoring terms. |
| Checkly | APPROVE AFTER POLICY | Owner approves synthetic tenant/test account, read-only endpoints, browser recording policy, and data region/retention. |
| Sentry | APPROVE AFTER POLICY | Owner approves redaction contract, excluded fields, region, retention, and error-volume budget. |
| Socket | APPROVE POC | Owner approves read-only CI scan and warning-only output; no blocking policy in this POC. |

“Approve” here means approve the bounded plan for execution. It does not authorize implementation in this document.

## Shared POC evidence and stop conditions

Each POC must record:

- start/end time and tested version;
- exact configuration and data boundary;
- successful and intentionally failed test result;
- alert/scan evidence with sensitive values redacted;
- time-to-detection or triage result;
- false positives and operational burden;
- whether the tool would remain a static support layer or creates unacceptable lifecycle complexity.

Stop immediately if a tool requests or receives production secrets, business payloads, identity/permission data, approval data, ActionGateway data, or customer/tenant data outside the approved allowlist.

---

## 1. UptimeRobot

**Official URL:** [UptimeRobot](https://uptimerobot.com/)  
**POC classification:** independent external monitoring; not incident authority.

### Exact SCOREBOS gap addressed

SCOREBOS/Render runtime health and internal logs cannot independently prove that a public endpoint is reachable from outside the deployment environment. The POC addresses only:

1. external reachability of one public health endpoint; and
2. whether one scheduler heartbeat is being emitted on time.

It does not address business correctness, Telegram/WhatsApp delivery, approvals, user permissions, or emergency-stop state.

### Exact POC scope

- Configure exactly **one public health monitor** for an existing or Owner-approved public endpoint.
- Configure exactly **one scheduler heartbeat monitor** for an existing or Owner-approved heartbeat URL.
- Use email alerting to one Owner-approved operational inbox only.
- Perform one controlled failure of the health endpoint in a non-production/safe window, or use a reversible test endpoint that returns a failure status.
- Perform one controlled missed-heartbeat test without changing business state.
- Capture alert latency, recovery alert behavior, false positives, and whether the endpoint response exposes data.
- Do not add more monitors, status pages, integrations, webhooks, or incident automation during the POC.

### Data boundary

**Allowed to leave SCOREBOS:**

- public URL/hostname of the health endpoint;
- public URL/hostname of the heartbeat endpoint;
- HTTP status, response timing, and a deliberately minimal fixed response such as `ok`/`heartbeat`;
- no user identifiers, tenant identifiers, request IDs, business identifiers, or response payloads beyond the fixed health marker.

**Forbidden to leave SCOREBOS:**

- API keys, webhook secrets, authentication headers, cookies, signed URLs, or query-string tokens;
- customer, tenant, contact, message, lead, deal, property, candidate, financial, or prompt data;
- ActionGateway/action/approval identifiers;
- internal stack traces, environment variables, infrastructure details, or operational logs;
- any endpoint that performs a write or triggers a business action.

### Setup effort and required configuration

- **Effort:** Low; approximately 30–60 minutes once Owner policy and endpoints exist.
- **Account required:** One Owner-controlled UptimeRobot account; no shared personal account.
- **Configuration required:** one monitor, one heartbeat, one email recipient, named monitor ownership, and documented retention/export expectations.
- **SCOREBOS code changes:** None if suitable existing public health and heartbeat endpoints already exist. If an endpoint must be created or changed, that is a separate implementation request and is outside this plan.
- **Production secrets:** None.

### Rollback path

Delete/deactivate exactly the two monitors and remove the Owner-approved alert recipient. No SCOREBOS data or code changes should need rollback. If a test endpoint was separately introduced, remove it through a separate approved change; do not alter the existing health contract during this POC.

### Success criteria

- Health monitor detects a controlled failure and recovery within the agreed threshold.
- Heartbeat monitor detects one intentionally missed heartbeat and recovery.
- No sensitive value appears in monitor URL, response, alert, or dashboard.
- Monitoring does not trigger a SCOREBOS action, approval, notification workflow, or emergency-stop change.
- Alert ownership and on-call response are explicit.
- The external signal is demonstrably different from Render/internal logs.

### Failure criteria

- Any sensitive data is required or captured.
- A monitor must call an authenticated or write-capable endpoint.
- The health response is too broad and exposes internal/runtime details.
- Alerts are unreliable, unowned, or too delayed for the stated use.
- The monitor encourages treating UptimeRobot as the canonical incident or emergency-stop system.

### Owner decision needed before execution

- Approve the exact two URLs and fixed response contract.
- Approve the alert inbox and retention policy.
- Confirm the health endpoint is safe to expose publicly.
- Confirm whether the heartbeat endpoint already exists; no runtime change is approved by this plan.
- Decide whether a five-minute free-tier cadence is useful enough for the operational objective.

---

## 2. Checkly

**Official URL:** [Checkly](https://www.checklyhq.com/)  
**POC classification:** synthetic API/browser verification; no business writes.

### Exact SCOREBOS gap addressed

Internal tests and uptime probes may miss externally observable contract failures, especially in an authenticated TMA/WebView flow. The POC addresses:

1. one read-only API contract check; and
2. one synthetic TMA smoke path that verifies loading/navigation/read-only display.

It does not test real customer journeys, production business writes, approvals, payments, or message delivery.

### Exact POC scope

- Create one Owner-approved synthetic test account/tenant with no real business data.
- Configure exactly one read-only API check, such as a health/read endpoint that returns a stable contract.
- Configure exactly one browser smoke path for the TMA: open the approved test URL, authenticate with synthetic credentials/token, verify the expected landing surface, navigate to one read-only screen, and assert visible non-sensitive content.
- Use no create/update/delete action, approval callback, file upload, payment, outbound message, or ActionGateway execution.
- Capture only status, timing, pass/fail, and a screenshot/trace if Owner approves that the synthetic screen contains no sensitive data.
- Introduce one safe failure in a non-production target or via a reversible test fixture; do not deliberately break production.

### Data boundary

**Allowed to leave SCOREBOS:**

- public test URL and approved read-only API route;
- synthetic username/credential or short-lived synthetic token created specifically for the POC;
- synthetic tenant ID and synthetic records created for testing, containing no real person or business data;
- fixed UI labels, status codes, timing, and approved screenshots of the synthetic surface;
- redacted browser console/network metadata necessary to debug the smoke path.

**Forbidden to leave SCOREBOS:**

- real user credentials, session cookies, Telegram/WhatsApp tokens, API keys, or production auth artifacts;
- production tenant IDs, customer/contact/lead/deal/property/candidate/financial records;
- message bodies, prompts, files, attachments, approval payloads, ActionGateway identifiers, or internal URLs;
- any write-capable route or test that can mutate canonical state;
- screenshots or traces containing PII, business data, secrets, or authenticated real-user surfaces.

### Setup effort and required configuration

- **Effort:** Medium; approximately 2–4 hours after the synthetic test account and safe read-only route are available.
- **Account required:** One Owner-controlled Checkly account; verify current free-tier limits and data-region/retention terms first.
- **Configuration required:** one API check, one browser check, synthetic credentials, safe test URL, alert recipient, and explicit screenshot/trace retention decision.
- **SCOREBOS code changes:** None if existing read-only routes and a safe TMA test surface exist. Creating a test-only route, test tenant, or fixture is separate implementation work and requires approval; do not modify ActionGateway, identity/permissions, or production runtime for this POC.
- **Production secrets:** None.

### Rollback path

Disable/delete the two checks and revoke the synthetic credential. Delete synthetic test artifacts through the approved test-data process. Remove any local test definition or CI reference if one was created. No production business data should require rollback.

### Success criteria

- API check detects a deliberate safe contract failure and recovery.
- Browser check loads the synthetic TMA path, reaches the read-only screen, and fails clearly when the safe fixture is broken.
- No real business write, approval, message, or ActionGateway execution occurs.
- Screenshots/traces contain only synthetic/non-sensitive content.
- Evidence is more actionable than a plain uptime check: route, browser stage, timing, and failure location are visible.
- Test maintenance remains bounded to one API and one browser path.

### Failure criteria

- A test requires production credentials or real business records.
- The browser path can mutate canonical state or trigger a message/approval.
- Screenshots/traces expose sensitive content or cannot be reliably redacted.
- The free plan/data terms are unsuitable or unverified for the intended data boundary.
- Flaky tests create alert fatigue before a stable baseline is established.

### Owner decision needed before execution

- Approve creation/use of a synthetic tenant and synthetic credentials.
- Approve the exact read-only API route and TMA screen.
- Approve whether screenshots, traces, console logs, or network metadata may be retained externally.
- Confirm the synthetic path cannot reach write-capable routes or ActionGateway actions.
- Approve current Checkly free-plan, region, retention, and security terms.

---

## 3. Sentry

**Official URL:** [Sentry](https://sentry.io/)  
**POC classification:** bounded exception aggregation only.

### Exact SCOREBOS gap addressed

Normal Render/runtime logs provide raw evidence but may not group recurring exceptions, correlate them with releases/environments, or provide a focused triage view. The POC addresses exception grouping and release/environment context for one Flask backend path and one TMA frontend boundary.

It does not replace SCOREBOS logs, audit history, execution evidence, approvals, or incident authority.

### Exact POC scope

- Define and review a redaction contract before any SDK/configuration work.
- Instrument exactly one non-sensitive Flask exception path in a non-production environment, or use a controlled test exception if an existing hook is already available.
- Instrument exactly one TMA frontend error boundary in a non-production/synthetic surface.
- Add only approved tags: environment, release/version, component, and a non-identifying correlation value if Owner approves it.
- Send one controlled exception from each surface.
- Verify grouping, stack trace usefulness, release/environment filtering, alert behavior, and data scrubbing.
- Do not enable performance tracing, session replay, breadcrumbs containing user messages, profiling, attachments, AI features, or broad automatic capture during the POC.

### Redaction contract and exact data boundary

**Allowed to leave SCOREBOS:**

- exception type and stack trace after source paths/arguments are reviewed;
- component name (`backend`/`tma`), environment (`poc`/`staging`), and release identifier;
- coarse non-identifying runtime metadata needed for triage, such as framework version or browser family;
- a generated random POC event ID with no mapping to a person, tenant, action, or business record;
- a fixed synthetic error message used solely to validate grouping.

**Forbidden to leave SCOREBOS:**

- message bodies, prompts, model inputs/outputs, chat transcripts, attachments, files, screenshots of business surfaces, or request/response bodies;
- API keys, access tokens, cookies, auth headers, signed URLs, session IDs, or credentials;
- names, emails, phone numbers, Telegram/WhatsApp IDs, user IDs, tenant IDs, contact/lead/deal/property/candidate IDs;
- Airtable/Google record contents, financial data, approval payloads, ActionGateway data, business memory, or internal URLs;
- query strings, form fields, headers, local storage, Redux/state snapshots, breadcrumbs containing user input, and request bodies;
- source code context beyond the minimum stack trace needed for the approved POC.

### Required redaction configuration

Before any event is sent, Owner/Architecture must approve:

- `before_send`/equivalent event scrubber behavior;
- denied field list covering message, prompt, token, authorization, cookies, request data, user, tenant, business-record, and attachment fields;
- disabled or absent request-body capture, breadcrumbs, replay, profiling, attachments, and broad tracing;
- environment and release tagging scheme using only `poc`/`staging` and an approved release identifier;
- data region, retention, access seats, and deletion behavior;
- an offline/local redaction test fixture proving forbidden values do not survive serialization.

### Setup effort and required configuration

- **Effort:** Medium; approximately 3–6 hours for policy, redaction tests, bounded instrumentation, and review.
- **Account required:** One Owner-controlled Sentry account/project after region and terms are approved.
- **Configuration required:** DSN stored only as a non-production secret, redaction hooks, disabled capture features, environment/release tags, one backend project and one TMA project or equivalent bounded scope.
- **SCOREBOS code changes:** Likely small, non-business instrumentation changes in Flask/TMA error boundaries, but implementation is not authorized by this plan. No ActionGateway, identity/permission, business schema, or runtime execution changes.
- **Production secrets:** No production DSN or secrets. A POC/staging DSN may be used only after Owner approval and secret handling is defined.

### Rollback path

Disable the Sentry projects/DSNs, remove the bounded SDK initialization and instrumentation in a separate approved code change, revoke the POC DSN, request deletion of captured POC events, and remove any non-production secret. Existing SCOREBOS logs remain the diagnostic fallback. No business data migration or replay is involved.

### Success criteria

- Controlled backend and TMA exceptions are grouped correctly.
- Release/environment tags support filtering without identifying a user or tenant.
- Stack traces are useful while all forbidden fields remain absent.
- No message bodies, tokens, prompts, business records, request bodies, breadcrumbs, or replays leave SCOREBOS.
- The tool reduces triage time compared with raw logs without becoming a second audit or incident system.
- Capture volume and retention are predictable within the approved budget.

### Failure criteria

- Any forbidden field appears in an event, tag, breadcrumb, trace, or attachment.
- Redaction cannot be tested or cannot guarantee the stated boundary.
- The SDK captures broad request/user context by default and cannot be disabled.
- The POC requires production secrets/data or creates a new runtime dependency that is hard to remove.
- Grouping/alerting adds no material value over existing logs.

### Owner decision needed before execution

- Approve the complete redaction/excluded-field contract.
- Approve data region, retention, access, and deletion terms.
- Approve non-production instrumentation and the bounded code-change scope.
- Approve environment/release tags and whether any correlation ID is permitted.
- Confirm that no production Sentry project, DSN, data, or secrets are in scope.

---

## 4. Socket

**Official URL:** [Socket](https://socket.dev/)  
**POC classification:** read-only dependency/supply-chain assessment.

### Exact SCOREBOS gap addressed

The SCOREBOS baseline lists runtime tests, deployment controls, and observability but does not establish a dedicated dependency supply-chain risk review. Socket can provide a second signal for suspicious dependency behavior and package risk before code changes are merged.

### Exact POC scope

- Run one read-only scan against the existing dependency manifests/lockfiles in a non-blocking evaluation context.
- Review findings for direct and transitive dependencies, package behavior signals, and false positives.
- Compare a sample of findings against existing dependency/security checks if present.
- Produce an advisory report only.
- **Warning mode first:** no CI failure, no merge block, no automatic remediation, no package upgrades, no firewall enforcement, and no changes to dependency policy.
- Do not grant Socket write access to the repository or package registries.

### Data boundary

**Allowed to leave SCOREBOS:**

- dependency manifest and lockfile contents necessary for package analysis;
- package names, versions, hashes, dependency graph, and public package metadata;
- repository/branch identifier only if Owner approves it;
- scan result identifiers and severity labels.

**Forbidden to leave SCOREBOS:**

- source code, business logic, tests, prompts, configuration secrets, `.env` files, credentials, tokens, private URLs, customer/tenant data, or runtime logs;
- private package contents unless explicitly approved;
- repository write credentials, GitHub tokens, package-registry tokens, or CI secrets;
- automatic source upload, code upload, dependency mutation, or enforcement action.

### Setup effort and required configuration

- **Effort:** Low/Medium; approximately 30–90 minutes for one read-only scan and findings review.
- **Account required:** Owner-controlled Socket account only if required by the current tool; verify plan/access first. A local/CLI scan is preferred if available.
- **Configuration required:** target manifests/lockfiles, read-only scan mode, warning/advisory output, and an artifact destination approved by Owner.
- **SCOREBOS code changes:** None. No runtime, ActionGateway, identity, permission, deployment, or CI policy changes in the POC.
- **Production secrets:** None.

### Rollback path

Delete the advisory scan configuration/artifacts and revoke any read-only token if one was required. Since no dependency files, CI policy, or runtime code changed, rollback is limited to removing the evaluation job/report.

### Success criteria

- A complete read-only dependency scan runs without source/business data exposure.
- Findings are understandable and actionable enough to identify at least whether existing dependencies need review.
- False positives and overlap with existing scanners are documented.
- Scan runs in warning mode only and cannot block CI or alter dependencies.
- No repository write access or secrets are granted.

### Failure criteria

- The tool requires source-code, private package, repository-write, or CI-secret access.
- Findings are too noisy or opaque to support a human review.
- The scan cannot run read-only or cannot be kept non-blocking.
- It duplicates an existing trusted control without material additional signal.
- The free/access terms require a commitment not justified by the POC.

### Owner decision needed before execution

- Approve Socket’s access scope and current privacy/retention terms.
- Approve the exact manifests/lockfiles in scope.
- Confirm warning-only behavior and explicitly defer blocking CI policy.
- Decide who reviews findings and how reports are retained.

---

## Final recommendation

### APPROVE POC

| Tool | Recommendation |
|---|---|
| Socket | Approve a read-only dependency scan in warning mode, with no CI blocking and no write access. |

### APPROVE AFTER POLICY

| Tool | Required policy gate |
|---|---|
| UptimeRobot | Public endpoint contract, alert ownership, heartbeat semantics, and retention. |
| Checkly | Synthetic tenant, read-only route, browser capture policy, and data terms. |
| Sentry | Redaction/excluded fields, region, retention, access, and bounded non-production instrumentation. |

### DEFER

Better Stack, OpenObserve, Bugsink, Algolia, and other audit candidates remain outside this approved POC plan. Their value or architecture fit is not established enough for execution.

### REJECT

Any plan that introduces a second ActionGateway, approval system, identity/permission model, canonical data store, business queue, or external file-processing proxy is rejected. No candidate in this plan may be used to route business data or execute SCOREBOS actions.

## Explicit stop condition

Stop after Owner review of this planning document. Execution requires a separate approval and implementation task. This document itself creates no accounts, connections, configuration, code changes, secrets, or production behavior.
