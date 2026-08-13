# SCOREBOS Developer / Operator Toolbox

Date: 13/08/2026  
Scope: direct-use tooling from the NoSignups audit. No installs, integrations, extensions, or SCOREBOS changes are authorized by this document.

## Policy baseline

- Production data is **not allowed** in any hosted browser utility.
- Use synthetic fixtures or redacted exports by default.
- “Local/browser processing verified” below means the current vendor/project documentation was re-checked. It is not an independent penetration test or a guarantee that every browser asset is offline.
- ShareClean and Metadata Remover were specifically re-verified. SQLChef and csv.repair were previously uncertain; SQLChef still has no stable primary URL surfaced by the review, so its local-processing claim remains unverified.
- Sanitization is a last check, not a security boundary. Review the output manually before sharing.
- No tool may become a SCOREBOS source of truth, approval path, identity system, execution path, or production observability store.

## 1. Approved Direct-Use Tools

These are bookmark/use-now tools. Direct use is sufficient; no integration is justified.

### CyberChef

- **Approved use case:** Decode or encode redacted webhook fragments, inspect hashes, parse test payloads, and transform synthetic evidence during debugging.
- **Prohibited use case:** Pasting live tokens, credentials, customer records, or using a recipe as a production security control.
- **Privacy/data handling rule:** Use synthetic or already-redacted input; verify the recipe does not invoke external services.
- **Production data allowed:** No.
- **Redacted/synthetic only:** Yes.
- **Local/browser processing verified:** Browser tool and open-source project are verified; individual recipes and browser network behavior still require operator judgment.
- **Bookmark or POC:** Bookmark only.
- **Integration justified:** No.

### Screenshot Studio

- **Approved use case:** Create UX/debug evidence from synthetic screens or redacted screenshots, including device/browser framing.
- **Prohibited use case:** Treating a polished screenshot as responsive/accessibility testing, or sharing screenshots containing IDs, names, phone numbers, URLs, or tokens.
- **Privacy/data handling rule:** Redact before upload/use and inspect the exported image for hidden context.
- **Production data allowed:** No.
- **Redacted/synthetic only:** Yes.
- **Local/browser processing verified:** Browser-based operation is verified from the current feature page; no independent no-upload guarantee was established.
- **Bookmark or POC:** Bookmark only.
- **Integration justified:** No.

### Squoosh

- **Approved use case:** Compress documentation images, UX evidence, and synthetic media fixtures while checking text remains legible.
- **Prohibited use case:** Compressing evidence until details disappear, or using it for confidential customer media without approval.
- **Privacy/data handling rule:** Prefer synthetic/redacted images; the project says processing is local but documents Google Analytics collection of basic visitor/size data.
- **Production data allowed:** No.
- **Redacted/synthetic only:** Yes.
- **Local/browser processing verified:** Yes, project documentation says images do not leave the device; analytics still exists.
- **Bookmark or POC:** Bookmark only.
- **Integration justified:** No.

## 2. Approved With Data Restrictions

These remain direct-use utilities, but their data rules are strict.

### Hoppscotch

- **Approved use case:** Manually inspect safe staging HTTP/webhook requests, headers, status codes, and responses; use only read-only or idempotent test requests.
- **Prohibited use case:** Sending production mutations, storing production credentials in collections, bypassing SCOREBOS approvals, or treating a request collection as a test/source-of-truth system.
- **Privacy/data handling rule:** Use fake credentials, synthetic payloads, and redacted responses. Prefer local-first use; do not sync secrets to cloud workspaces.
- **Production data allowed:** No by default; only an explicitly approved read-only diagnostic request with scrubbed output would be an exception.
- **Redacted/synthetic only:** Yes for normal use.
- **Local/browser processing verified:** Browser, desktop, CLI, and self-host options are verified from current official documentation; request destination still controls data exposure.
- **Bookmark or POC:** Bookmark now; optional POC only for repeatable staging smoke tests.
- **Integration justified:** Not now. A CLI POC is justified only if manual replay cannot cover a documented, stable smoke-test gap.

### ShareClean

- **Approved use case:** Run locally on logs, stack traces, curl output, URLs, headers, and config snippets before sharing them in tickets, GitHub, Slack, or AI tools.
- **Prohibited use case:** Treating redaction as complete, replacing secret scanning/DLP, or uploading raw logs to the browser playground.
- **Privacy/data handling rule:** Use the CLI, never overwrite the input, inspect the cleaned output, and add SCOREBOS-specific custom patterns when needed. The current package page says no account, API key, network calls, or telemetry.
- **Production data allowed:** Yes only as a local input to the CLI, subject to SCOREBOS access policy; never send the raw input to a hosted playground.
- **Redacted/synthetic only:** Required for anything leaving the workstation; the cleaned output still requires review.
- **Local/browser processing verified:** CLI local processing is verified from current PyPI documentation. The browser playground is for fake text only.
- **Bookmark or POC:** Bookmark the package page; no POC needed.
- **Integration justified:** No. Existing runtime redaction remains authoritative; ShareClean is a pre-sharing safety pass.

### Log Voyager

- **Approved use case:** Inspect large, already-authorized log exports locally; search, filter, and inspect JSON/error patterns.
- **Prohibited use case:** Uploading live logs to an unapproved service, retaining logs in browser history, or declaring an incident resolved from visual inspection alone.
- **Privacy/data handling rule:** Prefer sanitized exports; delete downloads and browser-local history after use.
- **Production data allowed:** Yes only for an approved local export with least-privilege access; no hosted transfer.
- **Redacted/synthetic only:** Required before sharing or screenshotting results.
- **Local/browser processing verified:** The current site states local processing; independent source-code/security verification was not performed.
- **Bookmark or POC:** Bookmark only.
- **Integration justified:** No; `scripts/render_log_export.py` and existing regression evidence remain canonical.

### Metadata Remover

- **Approved use case:** Remove GPS, camera/device, author, document, PDF, and related metadata from files before external sharing.
- **Prohibited use case:** Assuming metadata removal anonymizes content, removes visible sensitive text, or is safe for every file format without checking the result.
- **Privacy/data handling rule:** Verify the browser Network panel shows no file upload for the chosen operation; inspect before/after metadata and preserve the original separately.
- **Production data allowed:** Yes only for an explicitly approved local/browser cleanup of a file already authorized for sharing; never treat the cleaned file as automatically safe.
- **Redacted/synthetic only:** Required for routine testing; production files require owner approval.
- **Local/browser processing verified:** Current page explicitly states no signup, no upload, and in-browser WebAssembly/JavaScript processing. This is a vendor claim, not independent assurance.
- **Bookmark or POC:** Bookmark only.
- **Integration justified:** No. Do not insert an implicit scrubber into SCOREBOS ingestion or file storage.

### SQLChef

- **Approved use case:** Ad-hoc SQL exploration of redacted CSV, JSON, or Parquet exports if the correct tool URL and behavior are independently confirmed.
- **Prohibited use case:** Querying live Airtable/Drive data, importing remote production URLs, or treating a browser query as an authoritative report.
- **Privacy/data handling rule:** Local copies only; disable/avoid URL imports and sharing until the actual implementation is verified.
- **Production data allowed:** No.
- **Redacted/synthetic only:** Yes.
- **Local/browser processing verified:** No. The NoSignups crawl described DuckDB-WASM behavior, but did not expose a stable primary URL; current review could not verify the exact SQLChef deployment.
- **Bookmark or POC:** Do not bookmark a guessed URL; keep as a research note until resolved.
- **Integration justified:** No.

### csv.repair

- **Approved use case:** Repair a disposable, redacted CSV export and compare the result against the original before manual import review.
- **Prohibited use case:** Editing the canonical Airtable export in place, importing repaired rows without review, or assuming automatic repair preserves every value.
- **Privacy/data handling rule:** Use a copy; prefer synthetic/redacted data; validate row counts, headers, delimiters, quoting, and encoding after repair.
- **Production data allowed:** No by default.
- **Redacted/synthetic only:** Yes.
- **Local/browser processing verified:** The current site confirms browser loading, editing, SQL, diagnostics, and repair, but local-only/no-upload behavior was not independently established.
- **Bookmark or POC:** Bookmark only for disposable files; no POC.
- **Integration justified:** No; `scripts/classify_contacts_for_airtable.py` remains the controlled SCOREBOS path.

### JSON Crack

- **Approved use case:** Visualize redacted JSON/YAML/XML/CSV payloads to understand nesting and field relationships.
- **Prohibited use case:** Pasting production records, tokens, or internal identifiers into hosted visualization or embedding it as a user-facing SCOREBOS payload viewer.
- **Privacy/data handling rule:** Use synthetic fixtures; remove IDs and personal data before visualization.
- **Production data allowed:** No.
- **Redacted/synthetic only:** Yes.
- **Local/browser processing verified:** Browser visualization is verified; hosted processing/storage behavior for every mode is not independently verified.
- **Bookmark or POC:** Bookmark only.
- **Integration justified:** No; Python snapshots and existing evidence structures remain canonical.

## 3. Optional POC

### Hoppscotch CLI — staging smoke-test POC only

This is the only candidate that may justify a POC. Proceed only when a concrete manual-testing gap is documented.

- Scope: one or two staging-safe, read-only/idempotent requests.
- Inputs: fake credentials, synthetic payloads, no customer data.
- Success condition: reproducible request/response checks that complement—not replace—the existing regression/staging scripts.
- Failure condition: production credentials, mutation execution, cloud secret sync, a new result store, or divergence from canonical evidence.
- Decision: do not integrate unless the POC proves material repeatability or operator-time savings.

## 4. Do Not Integrate

Do not integrate any listed tool into SCOREBOS now. Direct use is sufficient, and integration would risk parallel behavior or data authority.

- No API client integration: Hoppscotch must not become a second execution or approval path.
- No runtime log integration: Log Voyager must not become log retention, alerting, or incident authority.
- No runtime redaction integration: ShareClean and Metadata Remover must not silently alter raw ingress, evidence, or stored files.
- No data-source integration: SQLChef, csv.repair, and JSON Crack must not read/write Airtable, Drive, or production data directly.
- No media pipeline integration: Squoosh and Screenshot Studio are presentation/content utilities, not product workflows.
- No browser extensions, accounts, cloud collections, hosted uploads, or new vendor dependencies.

## Compact operator table

| Tool | Use For | Safe Data | Forbidden Data | Integration |
|---|---|---|---|---|
| Hoppscotch | Staging HTTP/webhook inspection | Synthetic payloads, fake creds, redacted responses | Production mutations, live credentials, customer payloads | None; optional staging POC |
| ShareClean | Pre-sharing log/config sanitization | Local logs; output reviewed before sharing | Raw logs in browser playground; assumption of perfect redaction | None |
| Log Voyager | Local large-log triage | Approved local exports, preferably sanitized | Unapproved hosted uploads, retained raw screenshots | None |
| CyberChef | Redacted encoding/decoding | Synthetic/redacted strings | Secrets, credentials, customer data | None |
| Screenshot Studio | UX/debug evidence | Synthetic/redacted screenshots | Tokens, IDs, PII, unreviewed production screens | None |
| Metadata Remover | File metadata cleanup before sharing | Approved files, preferably redacted | Unreviewed sensitive files; assumption of anonymization | None |
| SQLChef | Ad-hoc file queries | Synthetic/redacted CSV/JSON/Parquet | Live exports, remote production URLs | None; behavior still unverified |
| csv.repair | Disposable CSV repair | Copies of synthetic/redacted exports | Canonical exports, unreviewed imports | None |
| JSON Crack | Payload-shape visualization | Synthetic/redacted JSON/YAML/XML/CSV | Production records, tokens, internal IDs | None |
| Squoosh | Image compression | Synthetic/redacted media and fixtures | Confidential media without approval; unreadable evidence | None |

## Re-verification notes and sources

- [ShareClean current package documentation](https://pypi.org/project/shareclean/) — local CLI, no network calls/telemetry, browser playground for fake text.
- [Metadata Remover current page](https://vaulternal.com/metadata-remover/) — no signup, local WebAssembly/JavaScript processing, no-upload claim, Network-panel verification guidance.
- [Hoppscotch documentation](https://docs.hoppscotch.io/) — browser, desktop, CLI, self-hosting, and API testing capabilities.
- [Log Voyager](https://www.logvoyager.cc/) — local-processing claim and large-log workflow.
- [CyberChef](https://gchq.github.io/CyberChef/) — browser transformation workbench.
- [Screenshot Studio features](https://www.screenshot-studio.com/features) — browser screenshot editor and no-signup claim.
- [Squoosh](https://squoosh.app/) and [Squoosh source](https://github.com/GoogleChromeLabs/squoosh) — local processing and analytics note.
- [csv.repair](https://www.csv.repair/) — current CSV editor/query/diagnostic/repair workflow.
- [JSON Crack docs](https://jsoncrack.com/docs) — visualization and widget capabilities.
- [NoSignups catalog](https://nosignups.net/) — source catalog and candidate classification context.
