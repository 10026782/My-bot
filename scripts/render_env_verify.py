#!/usr/bin/env python3
"""Read a small, safe Render environment summary without printing secrets."""

from __future__ import annotations

import argparse
import os
import re
import sys

import requests


RENDER_API_BASE = "https://api.render.com/v1"
FLAG_KEYS = (
    "FEATURE_ACTION_GATEWAY",
    "FEATURE_ACTION_CONTRACT_PERSISTENCE",
    "FEATURE_ATOMIC_CLAIMS",
)
PRESENCE_ONLY_KEYS = ("DATABASE_URL",)


def safe_summary(entries: list[dict]) -> list[str]:
    """Render only allowlisted flag booleans and secret presence."""
    values = {
        str(item.get("envVar", {}).get("key", "")): item.get("envVar", {}).get("value")
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("envVar"), dict)
    }
    lines = []
    for key in FLAG_KEYS:
        value = str(values.get(key, "")).strip().lower()
        lines.append(f"{key}={value if value in {'true', 'false'} else ('ABSENT' if not value else 'SET_NON_BOOLEAN')}")
    for key in PRESENCE_ONLY_KEYS:
        lines.append(f"{key}={'PRESENT' if values.get(key) else 'ABSENT'}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a redacted Render environment summary.")
    parser.add_argument("--service-id", required=True)
    parser.add_argument("--api-key-env", default="RENDER_API_KEY")
    args = parser.parse_args()
    if not re.fullmatch(r"srv-[A-Za-z0-9]+", args.service_id):
        parser.error("service id must have the form srv-...")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"{args.api_key_env}: NOT SET", file=sys.stderr)
        return 2
    try:
        response = requests.get(
            f"{RENDER_API_BASE}/services/{args.service_id}/env-vars",
            headers={"Authorization": f"Bearer {api_key}"}, timeout=30,
        )
        response.raise_for_status()
        entries = response.json()
    except (requests.RequestException, ValueError):
        print("Render environment query failed; no response body is printed.", file=sys.stderr)
        return 1
    if not isinstance(entries, list):
        print("Render environment response was invalid; no response body is printed.", file=sys.stderr)
        return 1
    print("\n".join(safe_summary(entries)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
