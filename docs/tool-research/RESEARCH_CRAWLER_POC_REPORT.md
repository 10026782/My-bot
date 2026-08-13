# SCOREBOS Research Crawler POC Report

## Status

**Design and isolated harness prepared; runtime crawl not executed in this session.** No crawler package was installed, no production secret was used, and no SCOREBOS runtime or canonical data was changed.

## Selected engine

`Crawl4AI FIRST`, because it provides a Python-native local path, browser rendering, Markdown, structured extraction, screenshots, deep crawling and recovery controls without requiring a hosted API key for the local path. Firecrawl is retained as a measured fallback only.

## Files

- `scripts/research_crawler_poc/crawl.py` — isolated bounded runner.
- `scripts/research_crawler_poc/requirements.txt` — optional POC dependency only; not production dependencies.
- `scripts/research_crawler_poc/README.md` — run instructions and safety boundary.
- `docs/tool-research/FIRECRAWL_VS_CRAWL4AI.md` — comparison and decision.
- `docs/tool-research/RESEARCH_CRAWLER_ARCHITECTURE.md` — data flow and controls.

## What was tested

Static review was performed against the current official Firecrawl and Crawl4AI repositories/docs. The executable crawl was intentionally not run because this task did not authorize installing dependencies. The harness performs target validation, bounded crawl configuration, normalized output, hashing and previous/current diff when run in its own environment.

## Expected output and measurements

Each run records source URL, retrieval time, content hash, Markdown excerpt, detected items, verification status, elapsed seconds, output bytes and error state. The first run should use:

- NoSignups
- Free-for.dev
- two approved official tool pages

Success is not a recommendation or approval. It is a pending evidence artifact.

## Dependencies and cost

No production dependency was added. The optional POC dependency is Crawl4AI; its browser setup and resource cost must be measured locally. Do not claim a currency cost until request count, browser time, memory and any optional LLM calls are recorded.

## Remaining unknowns

JS rendering quality, memory/time on Render-like infrastructure, source blocking/terms, normalized diff precision, and the release pin all remain open until the POC is run.

## Gate

Do not integrate either crawler into production. The next smallest step is an owner-approved local run of the isolated harness, followed by a go/no-go decision based on evidence.
