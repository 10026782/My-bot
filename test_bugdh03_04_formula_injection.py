# test_bugdh03_04_formula_injection.py — BUG-DH-03/04: Airtable filterByFormula
# injection via unescaped user-controlled text.
#
# Airtable formula strings use ' as the field-literal delimiter. Any code
# that interpolates raw user text into filterByFormula with an f-string
# lets a value containing "'" break out of the string literal and inject
# arbitrary formula logic (e.g. ref="x' OR 1=1 --" widening a lookup to
# match unrelated records, or blocking the AND(...) conditions entirely).
#
# tools.airtable_gateway.escape_formula_value() is now the single sanctioned
# way to interpolate such text; three call sites are retrofitted to use it:
#   - cmd_decision.py::_resolve_decision_ref            (ref)
#   - decision_pipeline.py::maybe_supersede              (decision_id, Claim Topic)
#   - core/lead_service.py::_search_formulas             (name, phone — already
#     escaped inline before this fix; switched to the shared helper so there
#     is exactly one escaping implementation in the codebase, not two. Moved
#     here from core/lead_candidate_handler.py by the Phase 1 canonical Lead
#     creation service — core.lead_candidate_handler.find_existing_lead is
#     now a thin re-export of core.lead_service.find_existing_lead.)

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

from tools.airtable_gateway import escape_formula_value
import cmd_decision
import decision_pipeline
import core.lead_service as lead_service

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# 1. escape_formula_value() — unit level
# ══════════════════════════════════════════════════
print("\n── 1. escape_formula_value() unit tests ──")

chk("single quote escaped", escape_formula_value("O'Brien") == "O\\'Brien")
chk("no quotes -> unchanged", escape_formula_value("Dana Levi") == "Dana Levi")
chk("multiple quotes all escaped",
    escape_formula_value("a'b'c") == "a\\'b\\'c")
chk("empty string -> empty string", escape_formula_value("") == "")


# ══════════════════════════════════════════════════
# 2. cmd_decision.py::_resolve_decision_ref — injection blocked
# ══════════════════════════════════════════════════
print("\n── 2. _resolve_decision_ref() injection blocked ──")

captured_formula = {}


def _fake_at_list(table, formula=""):
    captured_formula["formula"] = formula
    return []


with patch.object(cmd_decision, "_at_get_record", return_value=None), \
     patch.object(cmd_decision, "_at_list", side_effect=_fake_at_list):
    injected_ref = "test' OR 1=1 --"
    cmd_decision._resolve_decision_ref(injected_ref)

built = captured_formula.get("formula", "")
chk("the injected quote was backslash-escaped in the built formula",
    "\\'" in built)
chk("no unescaped quote remains from the raw injected ref (every ' in the "
    "payload is preceded by a backslash)",
    injected_ref.replace("'", "\\'") in built)
chk("formula still references the DecisionFields.TITLE field",
    "{" in built and "}" in built)


# ══════════════════════════════════════════════════
# 3. decision_pipeline.py::maybe_supersede — injection blocked
# ══════════════════════════════════════════════════
print("\n── 3. maybe_supersede() injection blocked ──")


class _FakeStorage:
    def __init__(self):
        self.captured_formula = None

    def get(self, table, filter_formula=""):
        self.captured_formula = filter_formula
        return []

    def add(self, table, fields, source): return None
    def update(self, table, record_id, fields, source): return True


class _FakePorts:
    def __init__(self, storage):
        self.storage = storage
        self.contacts = None
        self.verifier = None
        self.approver = None


storage = _FakeStorage()
ports = _FakePorts(storage)

malicious_decision_id = "rec123' OR 1=1 --"
malicious_topic = "budget' OR {Status}!='' --"
new_event = {
    "_decision_id": "rec_holder",  # unused directly by maybe_supersede's formula build
    "Claim Topic": malicious_topic,
    "Trust Level": "T2",
}
decision_pipeline.maybe_supersede(
    {**new_event, "_decision_id": malicious_decision_id},
    decision={"id": "recSOMEDECISION0001"},
    ports=ports,
)

built2 = storage.captured_formula or ""
chk("maybe_supersede built a formula (storage.get was called)", built2 != "")
chk("decision_id: every quote in the raw payload was backslash-escaped",
    malicious_decision_id.replace("'", "\\'") in built2)
chk("Claim Topic: every quote in the raw payload was backslash-escaped",
    malicious_topic.replace("'", "\\'") in built2)


# ══════════════════════════════════════════════════
# 4. core/lead_service.py::_search_formulas — no regression
# ══════════════════════════════════════════════════
print("\n── 4. _search_formulas() no regression ──")

formulas_plain = lead_service._search_formulas("Dana Levi", "0501234567")
chk("still returns 3 formulas for name+phone (AND, phone-only, name-only)",
    len(formulas_plain) == 3)
chk("phone-only formula present", any("{phone}='0501234567'" in f for f in formulas_plain))
chk("name-search formula present", any("SEARCH('Dana Levi', {Name})" in f for f in formulas_plain))

formulas_no_phone = lead_service._search_formulas("Dana Levi", "")
chk("no phone -> only the name-search formula", formulas_no_phone == ["SEARCH('Dana Levi', {Name})"])

formulas_injection = lead_service._search_formulas("O'Brien' OR 1=1 --", "050")
chk("name with quote is escaped, not left raw",
    all("O\\'Brien\\' OR 1=1 --" in f for f in formulas_injection if "SEARCH" in f))


print("\n" + "=" * 50)
print(f"BUG-DH-03/04 formula injection tests: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
