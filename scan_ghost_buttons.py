#!/usr/bin/env python3
"""
scan_ghost_buttons.py — TMA endpoint coverage audit tool.

סורק tma-frontend/src/ ומוצא כפתורים שמפנים ל-endpoints שלא קיימים
ב-tma_api.py — לפני שמשתמש לוחץ עליהם.

הרצה:
    python3 scan_ghost_buttons.py [> ghost_buttons_report.md]

Classification:
  A ✅  Handler calls an existing backend endpoint
  B 🔕  Navigation-only (state setter / onBack — no API expected)
  C ❌  Handler calls an API but the endpoint is NOT in tma_api.py
  D ⚠️  Handler has fetch call but method+path not deterministic (dynamic)
  E ❓  Handler calls unknown function(s) — couldn't resolve to fetch
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
API_FILE   = ROOT / "tma_api.py"
FRONT_ROOT = ROOT / "tma-frontend" / "src"

# ═══════════════════════════════════════════════════
# Step 1 — build endpoint registry from tma_api.py
# ═══════════════════════════════════════════════════

_ROUTE_RE = re.compile(
    r'@tma_api\.route\(\s*"([^"]+)"\s*,\s*methods\s*=\s*\[([^\]]+)\]',
)

def _flask_to_regex(path: str) -> re.Pattern:
    seg = re.sub(r"<[^>]+>", "[^/]+", re.escape(path))
    return re.compile(f"^{seg}$")

def load_endpoints() -> list[tuple[str, re.Pattern, str]]:
    """Returns list of (METHOD, regex, raw_path)."""
    text = API_FILE.read_text(encoding="utf-8")
    seen: set = set()
    out = []
    for m in _ROUTE_RE.finditer(text):
        path    = m.group(1)
        methods = [x.strip().strip("'\"").upper() for x in m.group(2).split(",")]
        for method in methods:
            if method == "OPTIONS":
                continue
            key = (method, path)
            if key not in seen:
                seen.add(key)
                out.append((method, _flask_to_regex(path), path))
    return out

def endpoint_exists(method: str, path: str, registry: list) -> bool:
    # Strip query params before matching
    clean_path = path.split("?")[0]
    for reg_method, rx, raw_path in registry:
        if reg_method != method:
            continue
        # Forward: endpoint regex matches frontend path
        if rx.match(clean_path):
            return True
        # Reverse: frontend path (which may contain [^/]+ placeholders) matches endpoint raw path
        if "[^/]+" in clean_path:
            try:
                front_rx = re.compile(f"^{clean_path}$")
                if front_rx.match(raw_path):
                    return True
            except re.error:
                pass
    return False

# ═══════════════════════════════════════════════════
# Step 2 — map api.ts exports to their fetch calls
# ═══════════════════════════════════════════════════

_FETCH_RE = re.compile(
    r"""fetch\(\s*(?:
        `\$\{[^}]+\}(/api/[^`]+)` |
        ['"](/api/[^'"]+)['"]\s*|
        BASE\s*\+\s*['"](/api/[^'"]+)['"]
    )\s*(?:,\s*\{[^}]*?method\s*:\s*['"](\w+)['"][^}]*?\})?""",
    re.VERBOSE | re.DOTALL,
)

_NAV_ONLY_RE = re.compile(
    r"""^(?:
        (?:set\w+(?:Open|Close|Selected|State|Mode|View|Id|Tab|Page|Panel|Active|Visible|Show|Hide|Edit|Confirm|Loading|Error|Toast))\s*\(|
        onBack\s*\(|
        setSelected\s*\(|
        setState\s*\(|
        load\s*\(\s*\)|
        loadHub\s*\(\s*\)|
        e\.(?:stopPropagation|preventDefault)\s*\(
    )""",
    re.VERBOSE | re.IGNORECASE,
)

def _normalize_path(path: str) -> str:
    path = re.sub(r"\$\{[^}]+\}", "[^/]+", path)
    path = re.sub(r"encodeURIComponent\([^)]+\)", "[^/]+", path)
    return path

def extract_fetches_from_src(src: str) -> list[tuple[str, str]]:
    """Returns list of (METHOD, normalized_path)."""
    results = []
    for m in _FETCH_RE.finditer(src):
        path   = m.group(1) or m.group(2) or m.group(3) or ""
        method = (m.group(4) or "GET").upper()
        if path:
            results.append((method, _normalize_path(path)))
    return results

def build_apits_function_map(api_ts_src: str) -> dict[str, list[tuple[str, str]]]:
    """Maps exported function names → list of (method, path) fetch calls."""
    fn_map: dict[str, list[tuple[str, str]]] = {}
    fn_re = re.compile(r"""export\s+(?:async\s+)?function\s+(\w+)\s*\(""")
    for m in fn_re.finditer(api_ts_src):
        fname = m.group(1)
        # Walk past the parameter list (track paren depth)
        pos   = m.end()
        depth = 1
        while pos < len(api_ts_src) and depth > 0:
            ch = api_ts_src[pos]
            if   ch == "(": depth += 1
            elif ch == ")": depth -= 1
            pos += 1
        # Walk past the return type annotation (track angle-bracket depth to
        # skip complex generics like Promise<{ ok: boolean }> before finding {)
        angle_depth = 0
        body_start: int | None = None
        while pos < len(api_ts_src):
            ch = api_ts_src[pos]
            if   ch == "<":                      angle_depth += 1
            elif ch == ">" and angle_depth > 0:  angle_depth -= 1
            elif ch == "{" and angle_depth == 0:
                body_start = pos + 1
                break
            pos += 1
        if body_start is None:
            continue
        # Extract body by counting braces
        depth = 1
        for i, ch in enumerate(api_ts_src[body_start:], body_start):
            if   ch == "{": depth += 1
            elif ch == "}": depth -= 1
            if depth == 0:
                body = api_ts_src[body_start:i]
                fetches = extract_fetches_from_src(body)
                if fetches:
                    fn_map[fname] = fetches
                break
    return fn_map

# ═══════════════════════════════════════════════════
# Step 3 — scan component files for onClick handlers
# ═══════════════════════════════════════════════════

# Capture onClick={...} body — handles nested braces up to depth 3
_ONCLICK_SIMPLE_RE = re.compile(
    r"""on(?:Click|Press|Tap)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}""",
    re.DOTALL,
)

def _extract_called_fns(handler: str) -> list[str]:
    """Extract bare function calls from handler text (not state setters)."""
    # Find identifiers followed by (
    candidates = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", handler)
    # Filter out obvious React/JSX/known non-API calls
    ignore = {
        "e", "event", "parseInt", "String", "Number", "Boolean",
        "JSON", "Object", "Array", "Math", "Date", "console",
        "setTimeout", "clearTimeout", "void", "Promise",
        "encodeURIComponent", "decodeURIComponent",
        "stopPropagation", "preventDefault",
        # Built-in array/object methods that appear as foo.map(, foo.filter(, etc.
        "map", "filter", "reduce", "forEach", "find", "some", "every",
        "sort", "flat", "flatMap", "includes", "indexOf", "slice", "splice",
        "push", "pop", "shift", "unshift", "join", "split", "trim",
        "replace", "stringify", "parse", "keys", "values", "entries",
        "assign", "freeze", "round", "floor", "ceil", "max", "min",
        "repeat", "padStart", "padEnd", "startsWith", "endsWith",
    }
    return [c for c in candidates if c not in ignore and not c[0].isupper()]

def _get_label(src: str, onclick_pos: int) -> str:
    """Try to extract button text near the onClick attr."""
    # Look backwards for <button
    search_from = max(0, onclick_pos - 300)
    seg  = src[search_from:onclick_pos + 300]
    # Text nodes between > and < after the button open tag
    m = re.search(r">\s*([^<>{]{1,50}?)\s*(?:<|{)", seg[::-1])
    if m:
        return m.group(1)[::-1].strip()[:40]
    return "(label?)"

def scan_component(
    path: Path,
    registry: list,
    fn_map: dict,
    local_fns: dict,         # functions defined in this file
) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:
        return []

    rel = path.relative_to(FRONT_ROOT)
    results = []

    for m in _ONCLICK_SIMPLE_RE.finditer(src):
        handler = m.group(1).strip()
        lineno  = src[:m.start()].count("\n") + 1
        label   = _get_label(src, m.start())

        # 1. Direct fetch in handler
        direct_fetches = extract_fetches_from_src(handler)

        # 2. Resolve called function names
        called_fns = _extract_called_fns(handler)
        indirect_fetches: list[tuple[str, str]] = []
        resolved_fns: list[str] = []

        for fn in called_fns:
            # Check api.ts map
            if fn in fn_map:
                indirect_fetches += fn_map[fn]
                resolved_fns.append(fn)
            # Check local file functions
            elif fn in local_fns:
                body = local_fns[fn]
                # Recurse one level into local functions
                sub_fetches = extract_fetches_from_src(body)
                if sub_fetches:
                    indirect_fetches += sub_fetches
                    resolved_fns.append(fn)
                else:
                    # local fn with no direct fetch — might call api.ts fn
                    sub_calls = _extract_called_fns(body)
                    for sub_fn in sub_calls:
                        if sub_fn in fn_map:
                            indirect_fetches += fn_map[sub_fn]
                            resolved_fns.append(f"{fn}→{sub_fn}")

        all_fetches = direct_fetches + indirect_fetches

        # Classify
        # Navigation only?
        # Handler is ONLY a setter/onBack call (no real called fn besides nav)
        non_nav_fns = [
            f for f in called_fns
            if not re.match(
                r"^(?:set[A-Z]|load|onBack|e\.|setState|stop|prevent)",
                f,
            )
        ]
        is_nav_only = (
            not all_fetches
            and not non_nav_fns
            and re.match(r"^[()=>\s]*(?:set\w+|onBack|load|e\.)\(", handler)
        )

        if is_nav_only:
            status  = "B 🔕"
            method  = "-"
            api_path = "-"
            results.append({
                "file": str(rel), "line": lineno, "label": label,
                "status": status, "method": method, "path": api_path,
                "detail": "navigation",
            })
            continue

        if all_fetches:
            for method, api_path in all_fetches:
                if endpoint_exists(method, api_path, registry):
                    status = "A ✅"
                else:
                    status = "C ❌"
                results.append({
                    "file": str(rel), "line": lineno, "label": label,
                    "status": status, "method": method, "path": api_path,
                    "detail": ",".join(resolved_fns) or "direct",
                })
        else:
            # Called fns found but none resolved to fetch
            if non_nav_fns:
                status = "E ❓"
            else:
                status = "B 🔕"
            results.append({
                "file": str(rel), "line": lineno, "label": label,
                "status": status, "method": "-", "path": "-",
                "detail": ",".join(non_nav_fns) or "no-call",
            })

    return results


def extract_local_fns(src: str) -> dict[str, str]:
    """Extract non-exported function bodies defined in a component file."""
    fn_map: dict[str, str] = {}
    fn_re = re.compile(
        r"""(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{|const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{""",
    )
    for m in fn_re.finditer(src):
        fname = m.group(1) or m.group(2)
        start = m.end()
        depth = 1
        for i, ch in enumerate(src[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    fn_map[fname] = src[start:i]
                    break
    return fn_map


# ═══════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════

def main() -> None:
    print("# TMA Ghost Button Scan\n")
    print(f"Scanning: `{FRONT_ROOT.relative_to(ROOT)}`  \nAPI file: `tma_api.py`\n")

    registry = load_endpoints()
    print(f"## Backend endpoints found: {len(registry)}\n")
    for method, _, raw in sorted(registry, key=lambda x: x[2]):
        print(f"- `{method} {raw}`")
    print()

    api_ts = FRONT_ROOT / "api.ts"
    api_ts_src = api_ts.read_text(encoding="utf-8") if api_ts.exists() else ""
    fn_map = build_apits_function_map(api_ts_src)

    ts_files = sorted(
        f for f in (
            list(FRONT_ROOT.rglob("*.tsx")) +
            list(FRONT_ROOT.rglob("*.ts")) +
            list(FRONT_ROOT.rglob("*.jsx")) +
            list(FRONT_ROOT.rglob("*.js"))
        )
        if "node_modules" not in str(f) and "dist" not in str(f)
    )

    all_rows: list[dict] = []
    for f in ts_files:
        local_fns = extract_local_fns(f.read_text(encoding="utf-8"))
        all_rows += scan_component(f, registry, fn_map, local_fns)

    if not all_rows:
        print("No onClick handlers found.\n")
        return

    counts: dict[str, int] = {}
    for r in all_rows:
        s = r["status"][0]
        counts[s] = counts.get(s, 0) + 1

    print("## Summary\n")
    print("| Class | Symbol | Count | Meaning |")
    print("|-------|--------|-------|---------|")
    print(f"| A | ✅ | {counts.get('A',0)} | Connected to existing endpoint |")
    print(f"| B | 🔕 | {counts.get('B',0)} | Navigation-only (no API expected) |")
    print(f"| C | ❌ | {counts.get('C',0)} | Calls endpoint NOT found in tma_api.py |")
    print(f"| D | ⚠️  | {counts.get('D',0)} | Dynamic path — could not verify |")
    print(f"| E | ❓ | {counts.get('E',0)} | Unknown function — couldn't resolve to fetch |")
    print()

    critical = [r for r in all_rows if r["status"].startswith("C")]
    unknown  = [r for r in all_rows if r["status"].startswith("E")]

    if critical:
        print(f"## ❌ Endpoint Not Found ({len(critical)})\n")
        print("| File:Line | Label | Method | Path Called | Detail |")
        print("|-----------|-------|--------|-------------|--------|")
        for r in critical:
            print(f"| `{r['file']}:{r['line']}` | {r['label']} | `{r['method']}` | `{r['path']}` | {r['detail']} |")
        print()

    if unknown:
        print(f"## ❓ Could Not Resolve ({len(unknown)}) — manual check\n")
        print("| File:Line | Label | Called fn(s) |")
        print("|-----------|-------|-------------|")
        for r in unknown:
            print(f"| `{r['file']}:{r['line']}` | {r['label']} | `{r['detail']}` |")
        print()

    print(f"## Full Table ({len(all_rows)} handlers)\n")
    print("| File:Line | Label | Status | Method | Path |")
    print("|-----------|-------|--------|--------|------|")
    for r in sorted(all_rows, key=lambda x: (x["file"], x["line"])):
        print(f"| `{r['file']}:{r['line']}` | {r['label']} | {r['status']} | `{r['method']}` | `{r['path']}` |")


if __name__ == "__main__":
    main()
