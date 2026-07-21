#!/usr/bin/env python3
"""
test_predeploy.py — PATCH 3B Step 4

Tests core/predeploy.py's migrations-then-preflight wrapper. Both stages
are mocked at their source modules (core.database_migrations.run_migrations,
core.emergency_stop_preflight.run_preflight) — no real Postgres or Airtable
I/O. python -m core.database_migrations itself is untouched by this file
(and by core/predeploy.py) — this only tests the new wrapper.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

# ══════════════════════════════════════════════════════════════════
# 0. Importing core.predeploy / core.emergency_stop_preflight does no I/O
# ══════════════════════════════════════════════════════════════════

_pre_import_modules = set(sys.modules)
import core.predeploy  # noqa: E402
import core.emergency_stop_preflight  # noqa: E402
_new_modules_from_import = set(sys.modules) - _pre_import_modules

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


print("\n── import-time I/O boundary ──────────")

chk(
    "importing core.predeploy/.emergency_stop_preflight does not pull in the adapter",
    "adapters.airtable_emergency_stop_store" not in _new_modules_from_import,
)
chk(
    "importing core.predeploy/.emergency_stop_preflight does not pull in the gateway",
    "tools.airtable_gateway" not in _new_modules_from_import,
)
chk(
    "importing core.predeploy/.emergency_stop_preflight does not pull in feature_flags",
    "feature_flags" not in _new_modules_from_import,
)


# ══════════════════════════════════════════════════════════════════
# 1. migrations success + preflight success -> exit 0
# ══════════════════════════════════════════════════════════════════
print("\n── both stages succeed ────────────────")

with patch("core.database_migrations.run_migrations", return_value=True) as m_mig, \
     patch("core.emergency_stop_preflight.run_preflight", return_value=0) as m_pre:
    code = core.predeploy.main()
    chk("both succeed -> exit 0", code == 0)
    chk("migrations was called exactly once", m_mig.call_count == 1)
    chk("preflight was called exactly once", m_pre.call_count == 1)


# ══════════════════════════════════════════════════════════════════
# 2. migrations failure -> preflight is never called
# ══════════════════════════════════════════════════════════════════
print("\n── migrations failure short-circuits ──")

with patch("core.database_migrations.run_migrations", return_value=False), \
     patch("core.emergency_stop_preflight.run_preflight") as m_pre:
    code = core.predeploy.main()
    chk("migrations failure -> non-zero exit", code != 0)
    chk("migrations failure -> preflight NEVER called", m_pre.call_count == 0)


# ══════════════════════════════════════════════════════════════════
# 3. migrations success + preflight failure -> non-zero, code preserved
# ══════════════════════════════════════════════════════════════════
print("\n── preflight failure -> non-zero ──────")

with patch("core.database_migrations.run_migrations", return_value=True), \
     patch("core.emergency_stop_preflight.run_preflight", return_value=3):
    code = core.predeploy.main()
    chk("preflight invalid (3) -> predeploy exits non-zero", code != 0)
    chk("preflight's specific exit code is preserved, not collapsed to a generic 1", code == 3)

with patch("core.database_migrations.run_migrations", return_value=True), \
     patch("core.emergency_stop_preflight.run_preflight", return_value=2):
    code = core.predeploy.main()
    chk("preflight unavailable (2) -> predeploy exits non-zero, code preserved", code == 2)


# ══════════════════════════════════════════════════════════════════
# 4. exception in either stage -> non-zero, never silently OK
# ══════════════════════════════════════════════════════════════════
print("\n── exception in a stage -> non-zero ───")

with patch("core.database_migrations.run_migrations", side_effect=RuntimeError("db bug")), \
     patch("core.emergency_stop_preflight.run_preflight") as m_pre:
    code = core.predeploy.main()
    chk("migrations raising -> non-zero exit (not silently OK)", code != 0)
    chk("migrations raising -> preflight never called", m_pre.call_count == 0)

with patch("core.database_migrations.run_migrations", return_value=True), \
     patch("core.emergency_stop_preflight.run_preflight", side_effect=RuntimeError("preflight bug")):
    code = core.predeploy.main()
    chk("preflight raising -> non-zero exit (not silently OK)", code != 0)


print(f"\n{'='*40}")
print(f"core/predeploy.py tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
