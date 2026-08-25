"""
Regression test — Audit #11 (#11-3) blocking guard,
tools/audit_formula_escaping_boundary.py.

Proves the guard's classification on synthetic in-memory source snippets
(not the live repo scan, which is exercised separately by CI running the
guard itself): unescaped interpolation is rejected, the sanctioned
two-step/inline escape patterns are accepted, canonical query-renderer
output is accepted, and ordinary log/message strings that merely echo the
"{field}='...'" shape are not incorrectly rejected.
"""

import sys

from tools.audit_formula_escaping_boundary import scan_text


def _paths(findings):
    return sorted(f"{f.path}|{f.scope}" for f in findings)


def run():
    results = []

    # 1. Classic unescaped interpolation — must be rejected.
    unsafe_direct = scan_text("synthetic/unsafe_direct.py", """
from airtable_schema import LeadFields, Tables

def _find_by_external_id(external_id: str):
    raw = get(Tables.LEADS, f"{{{LeadFields.EXTERNAL_ID}}}='{external_id}'")
    return raw
""")
    results.append(("unsafe direct interpolation rejected", len(unsafe_direct) == 1))

    # 2. Sanctioned two-step pattern (safe_x = escape_formula_value(x); f"...{safe_x}...")
    #    — the exact shape Audit #11's remediation applies — must be accepted.
    safe_two_step = scan_text("synthetic/safe_two_step.py", """
from airtable_schema import LeadFields, Tables
from tools.airtable_gateway import escape_formula_value

def _find_by_external_id(external_id: str):
    safe_external_id = escape_formula_value(external_id)
    raw = get(Tables.LEADS, f"{{{LeadFields.EXTERNAL_ID}}}='{safe_external_id}'")
    return raw
""")
    results.append(("sanctioned two-step escape_formula_value() accepted", len(safe_two_step) == 0))

    # 3. Sanctioned inline call pattern (f"...='{escape_formula_value(x)}'") — must be accepted.
    safe_inline = scan_text("synthetic/safe_inline.py", """
from airtable_schema import MediaFileFields, Tables
from tools.airtable_gateway import escape_formula_value

def lookup(logical_media_key: str):
    formula = f"{{{MediaFileFields.LOGICAL_MEDIA_KEY}}}='{escape_formula_value(logical_media_key)}'"
    return formula
""")
    results.append(("sanctioned inline escape_formula_value() call accepted", len(safe_inline) == 0))

    # 4. Canonical query-renderer output (render_query()'s own internal literal
    #    construction, escaping via escape_formula_value before quoting) — accepted.
    safe_renderer = scan_text("synthetic/safe_renderer.py", """
from tools.airtable_gateway import escape_formula_value

def _field_ref(field):
    return "{" + field + "}"

def render_equals(field, value):
    return f"{_field_ref(field)}='{escape_formula_value(value)}'"
""")
    results.append(("canonical query-renderer output accepted", len(safe_renderer) == 0))

    # 5. Static/constant literal formulas (e.g. a PascalCase enum-attribute
    #    comparison, no runtime variable at all) — must not be rejected.
    safe_static = scan_text("synthetic/safe_static.py", """
from airtable_schema import Tables, WorldsFields
from enum import Enum

class WorldStatus(Enum):
    ACTIVE = "active"

def load_active_world():
    worlds = _at_list(Tables.WORLDS, f"{{{WorldsFields.STATUS}}}='{WorldStatus.ACTIVE}'", max_records=1)
    return worlds
""")
    results.append(("static/constant enum-attribute formula not rejected", len(safe_static) == 0))

    # 6. A log message that merely echoes the "{field}='...'" shape must not
    #    be mistaken for real formula construction.
    safe_log = scan_text("synthetic/safe_log.py", """
import logging
logger = logging.getLogger(__name__)

def resolve(field, val, rec_id):
    logger.info(f"airtable: resolved {field}='{val}' -> {rec_id}")
""")
    results.append(("log message resembling formula shape not rejected", len(safe_log) == 0))

    print("\n=== Audit #11 (#11-3) Formula Escaping Boundary — Regression ===")
    failures = []
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            failures.append(name)

    if failures:
        print(f"\n❌ FAILED: {', '.join(failures)}")
    else:
        print("\n✅ all formula-escaping boundary checks passed")
    return not failures


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
