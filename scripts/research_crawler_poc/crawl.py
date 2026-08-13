"""Bounded Crawl4AI evidence harness; intentionally outside SCOREBOS runtime."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_HOSTS = frozenset({"nosignups.net", "www.nosignups.net", "free-for.dev"})
MAX_MARKDOWN_BYTES = 500_000


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("URL is not an approved HTTPS research target")
    return url


def record(
    url: str,
    markdown: str,
    elapsed_seconds: float,
    previous: dict[str, object] | None = None,
) -> dict[str, object]:
    bounded = markdown.encode("utf-8")[:MAX_MARKDOWN_BYTES].decode("utf-8", "ignore")
    digest = hashlib.sha256(bounded.encode("utf-8")).hexdigest()
    current_hash = f"sha256:{digest}"
    return {
        "source_url": url,
        "source_type": "approved_public_source",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": current_hash,
        "markdown_excerpt": bounded[:4000],
        "detected_items": [],
        "verification_required": True,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "output_bytes": len(bounded.encode("utf-8")),
        "previous_content_hash": (previous or {}).get("content_hash"),
        "meaningful_change": bool(previous and previous.get("content_hash") != current_hash),
    }


async def crawl(url: str, previous: dict[str, object] | None = None) -> dict[str, object]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError as exc:
        raise SystemExit("Install the optional POC requirements in its disposable environment.") from exc

    started = time.perf_counter()
    browser = BrowserConfig(headless=True, java_script_enabled=True)
    config = CrawlerRunConfig(
        word_count_threshold=10,
        page_timeout=30_000,
        screenshot=False,
        pdf=False,
        check_robots_txt=True,
        verbose=False,
    )
    async with AsyncWebCrawler(config=browser) as crawler:
        result = await crawler.arun(url=url, config=config)
    if not result.success:
        raise RuntimeError(result.error_message or "crawl failed")
    return record(url, result.markdown or "", time.perf_counter() - started, previous)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, default=Path("/tmp/scorebos-research-crawler-poc.json"))
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    try:
        url = validate_url(args.url)
        previous = json.loads(args.previous.read_text()) if args.previous else None
        result = asyncio.run(crawl(url, previous))
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"POC rejected/failed safely: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
