"""reconcile_test_fixture.py — deliberately unregistered OFFLINE_RESEARCH_TOOL
fixture, kept permanently for test_reconcile.py's "policy-approved new source
registers and reconciles clean" scenario.

Matches scripts/research_crawler_poc/*, the same directory as the real
crawl.py this policy was written for -- so this proves auto-registration
end-to-end against a real file, real classification, and the real
OFFLINE_RESEARCH_TOOL predicate, without depending on which genuine
repository registration gaps happen to still be open (PR #628 closed every
one that existed when this test was first written). Deliberately left
unregistered in docs/context_librarian/decisions/canonical_boundaries.json so
it stays classifiable as a real new source on every run; the reconciliation
workflow registering it for real via --apply-auto on a future main push is
expected, harmless behavior, not a bug.

No imports, no dispatcher/app.py wiring, no high-risk content -- exists only
to be read as file content by the OFFLINE_RESEARCH_TOOL predicate and the
reconciliation engine's registration/content-hash machinery.
"""
