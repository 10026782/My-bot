# SCOREBOS Research Crawler Architecture

## Boundary

The crawler is an evidence-ingestion component, not a SCOREBOS action tool.

```text
approved source manifest
        ↓
isolated bounded crawler
        ↓
clean Markdown + metadata
        ↓
deterministic normalizer and hashes
        ↓
pending research record
        ↓
human/agent verification
        ↓
existing canonical tool registry
```

The crawler cannot approve a tool, publish a recommendation, modify canonical business data, bypass verification, execute business actions, or create an approval path. Markdown files and crawler output are evidence, not a new source of truth.

## Minimal POC

Default engine: Crawl4AI in a local isolated environment. Source set:

- `https://nosignups.net/`
- `https://free-for.dev/`
- two official tool pages selected before the run

The POC accepts only exact HTTPS hostnames in a checked-in source manifest. It has a page limit, timeout, output-size limit and no cookies, credentials, arbitrary JavaScript, hooks, proxy rotation or authenticated sessions.

Normalized source record:

```json
{
  "source_url": "https://example.org/page",
  "source_type": "approved_public_source",
  "retrieved_at": "2026-08-13T00:00:00Z",
  "content_hash": "sha256:...",
  "markdown_excerpt": "...",
  "detected_items": [],
  "verification_required": true
}
```

Candidate records are always pending:

```json
{
  "tool_name": "",
  "official_url": "",
  "free_status_claim": "",
  "signup_claim": "",
  "privacy_claim": "",
  "evidence_urls": [],
  "confidence": "",
  "verification_status": "pending"
}
```

## Change detection

Use the smallest deterministic chain:

1. Canonicalize URL, title, headings and extracted text.
2. Remove known volatile fields such as retrieval timestamp and navigation boilerplate.
3. Compute whole-page SHA-256 and per-section SHA-256 values.
4. Compare the previous snapshot with the current snapshot.
5. Create a pending change record only for changed sections.
6. Use an LLM, if ever approved, only on the changed excerpt and never as the comparator or publisher.

This avoids sending entire unchanged pages to an LLM.

## Data flow and retention

POC outputs go to a local temporary directory outside the repository by default. Keep only normalized evidence and hashes for the test. Do not store cookies, authorization headers, downloaded binaries, private pages or raw pages containing secrets.

## Security controls

Treat every URL and every scraped character as hostile data.

| Threat | Required control |
|---|---|
| SSRF/private network | Exact HTTPS hostname allowlist; resolve and reject private/link-local/loopback addresses; re-check redirects; no `file:`, `data:`, `javascript:` or localhost targets |
| Arbitrary user URLs | No user-supplied URLs in POC; source manifest only |
| Credentials/cookies | No secrets, cookies, authenticated sessions or browser profiles |
| Redirects | Allow only redirects whose final host remains approved |
| Downloaded files | Disable downloads; reject non-HTML/PDF unless explicitly approved and size-limited |
| Prompt injection | Scraped content is data in a quoted evidence field; never concatenate it into agent instructions or tool definitions |
| Large pages/resource exhaustion | Page count, byte, timeout, concurrency and browser limits; terminate on budget breach |
| Hooks/JS execution | No Crawl4AI hooks or request-supplied JS in the POC |
| Network abuse | Respect robots/terms where applicable; low fixed concurrency and per-domain delay |
| Canonical state mutation | No imports from runtime registry/action modules; output is pending JSON only |

## Operational shape

The POC is a one-shot CLI, not a service. A future scheduled job may invoke it externally, but scheduling, storage, queue ownership and verification remain SCOREBOS-owned decisions. Do not add a Render service until a measured workload proves a local job is insufficient.

## Acceptance checks

The isolated POC should prove: JS-capable fetch, clean Markdown, bounded multi-source crawl, controlled diff, pending verification record, rejection of unapproved targets, safe failure for unreachable sources, and timing/output-size measurements. It must not write the canonical registry.

## Next smallest step

Run the isolated POC once with the four approved public sources, record timings and failures, and decide whether Crawl4AI actually needs a Firecrawl fallback. No production dependency or service should be added before that evidence exists.
