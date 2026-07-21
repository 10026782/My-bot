#!/usr/bin/env python3
"""
test_ci_no_airtable_secrets.py — PATCH 3B Step 6 prerequisite

Structural proof that .github/workflows/ci.yml's backend-ci job:
  1. does NOT source AIRTABLE_API_KEY/AIRTABLE_BASE_ID from real secrets,
  2. DOES set fixed fake placeholder values instead,
  3. blocks network egress to api.airtable.com before any step that runs
     test code, as defense-in-depth against the exact class of bug fixed
     in commit 1967dd4 (a test-isolation leak that let mocked assertions
     run outside their patch context and silently hit production Airtable).

Reads the workflow file directly rather than parsing YAML — a plain text
scan is enough to prove the properties above and needs no new dependency.
"""

from __future__ import annotations

import sys

CI_PATH = ".github/workflows/ci.yml"

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


with open(CI_PATH, encoding="utf-8") as f:
    ci_text = f.read()

chk(
    "ci.yml does not source AIRTABLE_API_KEY from secrets",
    "secrets.AIRTABLE_API_KEY" not in ci_text,
)
chk(
    "ci.yml does not source AIRTABLE_BASE_ID from secrets",
    "secrets.AIRTABLE_BASE_ID" not in ci_text,
)
chk(
    "ci.yml sets a fixed fake AIRTABLE_API_KEY placeholder",
    'AIRTABLE_API_KEY: "fake-ci-key-not-real"' in ci_text,
)
chk(
    "ci.yml sets a fixed fake AIRTABLE_BASE_ID placeholder",
    'AIRTABLE_BASE_ID: "appFAKE00000000000"' in ci_text,
)
chk(
    "ci.yml blocks api.airtable.com via /etc/hosts",
    "api.airtable.com" in ci_text and "/etc/hosts" in ci_text,
)

# Ordering: the network-block step must appear before the step that runs
# every test_*.py script — otherwise a real Airtable call could slip
# through before the block is in place.
block_idx = ci_text.find("Block network egress to Airtable")
run_tests_idx = ci_text.find("Run test_*.py scripts")
smoke_idx = ci_text.find("Smoke tests")

chk(
    "network-block step exists",
    block_idx != -1,
)
chk(
    "network-block step runs before the test_*.py loop",
    block_idx != -1 and run_tests_idx != -1 and block_idx < run_tests_idx,
)
chk(
    "network-block step runs before smoke_tests.py",
    block_idx != -1 and smoke_idx != -1 and block_idx < smoke_idx,
)

# Other real secrets (Anthropic/Telegram/OpenAI/Google) are explicitly out
# of scope for this fix — not touched, not asserted against here. Airtable
# was the specific incident; broadening scope to the other services was
# never asked for.

print(f"\n{'='*40}")
print(f"CI Airtable secret removal: {passed} passed, {failed} failed")

if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
