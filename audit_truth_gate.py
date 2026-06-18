#!/usr/bin/env python3
"""
GOV-02 — Audit Truth Gate
MAIN > CANONICAL > LIVE > DOCS
No MAIN = STOP | No LIVE = READ_ONLY | Docs != Live → Live wins

Usage: python audit_truth_gate.py
exit 0 = OK (check audit_gate_state.json for MODE)
exit 1 = STOP — cannot determine main hash
"""
import subprocess, json, sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_CACHE = Path("schema_cache.json")
MAX_CACHE_AGE_HOURS = 24


def get_main_hash() -> str | None:
    try:
        r = subprocess.run(
            ["git", "ls-remote", "origin", "main"],
            capture_output=True, text=True, timeout=10
        )
        parts = r.stdout.strip().split()
        return parts[0][:8] if parts else None
    except Exception:
        return None


def check_schema_cache() -> dict:
    if not SCHEMA_CACHE.exists():
        return {"ok": False, "reason": "schema_cache.json חסר", "source": "MISSING"}
    try:
        data = json.loads(SCHEMA_CACHE.read_text())
        source    = data.get("_source", "UNKNOWN")
        cached_at = data.get("_cached_at")
        base_id   = data.get("_base_id", "UNKNOWN")

        if source != "LIVE":
            return {"ok": False, "reason": f"source={source} (לא LIVE)", "source": source}

        if cached_at:
            age = (datetime.now(timezone.utc).timestamp() -
                   datetime.fromisoformat(cached_at).timestamp()) / 3600
            if age > MAX_CACHE_AGE_HOURS:
                return {"ok": False,
                        "reason": f"cache בן {age:.1f} שעות (מקסימום {MAX_CACHE_AGE_HOURS})",
                        "source": "STALE"}

        return {"ok": True, "source": source, "base_id": base_id, "cached_at": cached_at}
    except Exception as e:
        return {"ok": False, "reason": f"שגיאת parse: {e}", "source": "ERROR"}


def determine_mode(main_hash, schema) -> tuple[str, str]:
    if not main_hash:
        return "STOP", "לא ניתן לקרוא git ls-remote origin main"
    if not schema["ok"]:
        return "READ_ONLY", schema["reason"]
    return "FULL", "main + live schema זמינים"


def main():
    print("=" * 50)
    print("GOV-02 — AUDIT TRUTH GATE")
    print("=" * 50)

    print("\n[1] בודק main hash...")
    main_hash = get_main_hash()
    print(f"    {'✅' if main_hash else '❌'} {main_hash or 'לא זמין'}")

    print("\n[2] בודק schema cache...")
    schema = check_schema_cache()
    icon = '✅' if schema['ok'] else '⚠️ '
    print(f"    {icon} source={schema.get('source')} — {schema.get('reason', 'תקין')}")

    mode, reason = determine_mode(main_hash, schema)

    print(f"\n{'=' * 50}")
    print(f"MODE: {mode}")
    print(f"סיבה: {reason}")
    print(f"{'=' * 50}\n")

    snapshot = {
        "_gate_ts":    datetime.now(timezone.utc).isoformat(),
        "_mode":       mode,
        "_main_hash":  main_hash,
        "_schema_ok":  schema["ok"],
        "_schema_src": schema.get("source"),
        "_reason":     reason
    }
    Path("audit_gate_state.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2)
    )
    print("📄 audit_gate_state.json נכתב.")

    if mode == "STOP":
        print("\n❌ STOP — אסור להריץ audit. דווח למשתמש ועצור.")
        sys.exit(1)

    if mode == "READ_ONLY":
        print("\n⚠️  READ_ONLY — קריאה בלבד. אסור לדווח CRITICAL/MISSING.")
        print("    כל ממצא יסומן: [UNVERIFIED — cache mode]")
        sys.exit(0)

    print("\n✅ FULL — audit רשאי לרוץ.")
    sys.exit(0)


if __name__ == "__main__":
    main()
