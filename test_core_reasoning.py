# test_core_reasoning.py — Core Reasoning Layer test suite
#
# רץ ללא חיבור ל-Airtable, ללא Claude API, ללא Render.
# כל dependency חיצוני מוחלף ב-fake בתוך הקובץ הזה.
#
# הרצה:
#   python -m pytest test_core_reasoning.py -v
#   python test_core_reasoning.py          (בלי pytest)
#
# מבנה:
#   Section A — reasoning_entity.py  (dataclasses, אפס לוגיקה)
#   Section B — reasoning_ports.py   (null impls, port contracts)
#   Section C — DecisionAdapter      (to_entity, from_result, domain_rules)
#   Section D — LeadsAdapter         (to_entity, status normalisation, domain)
#   Section E — reasoning_engines    (run() integration, graceful degradation)
#   Section F — edge cases           (empty input, missing fields, errors)

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# Test doubles — כל מה שהמערכת הקיימת מספקת, מוחלף כאן ב-stub
# ══════════════════════════════════════════════════════════════════════════════

def _install_stubs():
    """
    Install minimal module stubs so core/ imports don't fail in the test
    environment (no Airtable, no Claude, no Render).
    Must be called before any core import.
    """
    # airtable_schema stubs
    at = types.ModuleType("airtable_schema")
    at.DecisionFields = type("DF", (), {
        "TITLE": "Title", "STATUS": "Status", "DOMAIN": "Domain",
        "READINESS": "Readiness", "LAST_UPDATED": "Last Updated",
        "CREATED": "Created", "DEADLINE": "Deadline",
        "MISSING_INFO": "Missing Info", "DESCRIPTION": "Description",
        "URGENCY": "Urgency", "ESTIMATED_EXPOSURE": "Estimated Exposure",
    })()
    at.DecisionStatus = type("DS", (), {
        "OPEN": "OPEN", "PENDING_INPUT": "PENDING_INPUT",
        "DECIDED_YES": "DECIDED_YES", "DECIDED_NO": "DECIDED_NO",
        "CANCELLED": "CANCELLED",
    })()
    at.DecisionStakeholderFields = type("SF", (), {
        "ROLE": "Role", "CONTACT": "Contact",
        "POSITION": "Position", "POSITION_DETAILS": "Position Details",
    })()
    at.DecisionStakeholderRole = type("SR", (), {"OWNER": "Owner"})()
    at.DecisionDomain = type("DD", (), {
        "REAL_ESTATE": "real_estate", "IMPORT": "import",
        "PARTNERSHIP": "partnership", "RECRUITMENT": "recruitment",
        "GENERAL": "general",
    })()
    at.DecisionEventFields = type("EF", (), {
        "STATUS": "Status", "TRUST_LEVEL": "Trust Level",
        "AI_SUMMARY": "AI Summary", "RAW_CONTENT": "Raw Content",
        "CLAIM_TOPIC": "Claim Topic", "EVENT_TYPE": "Event Type",
        "EVENT_DATE": "Event Date", "DELTA_TYPE": "Delta Type",
        "TAGS": "Tags",
    })()
    at.DecisionEventStatus = type("ES", (), {"SUPERSEDED": "Superseded", "ACTIVE": "Active"})()
    at.DecisionTrustLevel = type("TL", (), {
        "T0": "T0", "T1": "T1", "T2": "T2", "T3": "T3",
    })()
    at.DecisionSourceReliability = type("SRC", (), {
        "CONTRACT": "contract", "LAWYER": "lawyer", "ACCOUNTANT": "accountant",
        "DOCUMENT": "document", "PARTNER": "partner", "CLIENT": "client",
        "MANUAL": "manual", "EMPLOYEE": "employee", "RUMOR": "rumor",
        "UNKNOWN": "unknown",
    })()
    at.DecisionEventChannel = type("CH", (), {
        "DOCUMENT": "document", "EMAIL": "email", "WHATSAPP": "whatsapp",
        "TELEGRAM": "telegram", "VOICE": "voice", "MANUAL": "manual",
    })()
    at.DecisionEventTag = type("TAG", (), {
        "LOW_CONFIDENCE": "low_confidence", "PARTIAL_TRANSCRIPT": "partial_transcript",
        "VAGUE": "vague", "PRESSURE_ONLY": "pressure_only",
        "MISSING_CONTEXT": "missing_context", "CONFLICT": "conflict",
        "PRESSURE_HIGH_RISK": "pressure_high_risk",
    })()
    at.DecisionClaimTopicSource = type("TOPIC_SRC", (), {
        "FILENAME": "filename", "EVENT_TYPE": "event_type",
        "AUTO": "auto", "KEYWORD": "keyword",
    })()
    at.DecisionExposureType = type("EXP", (), {
        "FINANCIAL": "financial", "LEGAL": "legal",
    })()
    at.DecisionDeltaType = type("DDT", (), {
        "PRESSURE": "pressure", "POSITION_SHIFT": "position_shift",
    })()
    at.DecisionStakeholderPosition = type("DSP", (), {})()
    at.Tables = type("T", (), {"DECISION_INBOX": "Decision Inbox"})()
    at.DecisionInboxChannel = type("DIC", (), {
        "WHATSAPP": "WhatsApp", "EMAIL": "Email", "VOICE": "Voice",
        "DOCUMENT": "Document", "MANUAL": "Manual",
    })()
    at.DecisionInboxFields = type("DIF", (), {
        "RAW_INPUT": "Raw Input", "CHANNEL": "Channel",
        "RECEIVED": "Received", "STATUS": "Status",
        "TENANT_ID": "Tenant ID", "ATTACHMENT": "Attachment",
        "SUGGESTED_DECISION": "Suggested Decision",
        "MATCH_CONFIDENCE": "Match Confidence",
    })()
    at.DecisionInboxStatus = type("DIS", (), {"PENDING": "Pending"})()
    sys.modules["airtable_schema"] = at

    # decision_pipeline stub
    dp = types.ModuleType("decision_pipeline")
    dp.SRC = at.DecisionSourceReliability
    dp.CH  = at.DecisionEventChannel
    dp.TL  = at.DecisionTrustLevel

    def compute_trust(authority, medium, verify_status):
        if verify_status in ("hallucination", "failed"):
            return "T0", 10
        scores = {"contract": 90, "lawyer": 88, "document": 80,
                  "client": 60, "manual": 55, "unknown": 25}
        a = scores.get(authority, 55)
        if a >= 80:   return "T3", a
        if a >= 55:   return "T2", a
        if a >= 30:   return "T1", a
        return "T0", a

    dp.compute_trust = compute_trust
    dp._trust_rank = lambda lvl: {"T0": 0, "T1": 1, "T2": 2, "T3": 3}.get(lvl, 0)
    sys.modules["decision_pipeline"] = dp

    # decision_confidence stub
    dc = types.ModuleType("decision_confidence")

    class _ConfResult:
        def __init__(self, score=0.5, missing=None, conflicting=None):
            self.score = score
            self.missing = missing or []
            self.conflicting = conflicting or []
            self.supporting = []

    def calc_confidence(events, conflicts=None, domain=None):
        if not events:
            return _ConfResult(score=0.0, missing=["אין אירועים מקושרים"])
        base = 0.6
        return _ConfResult(score=base, missing=[])

    dc.calc_confidence = calc_confidence
    dc.detect_missing_evidence = lambda domain, events: []
    sys.modules["decision_confidence"] = dc

    # decision_attention stub
    da = types.ModuleType("decision_attention")
    da.PRIORITY_HIGH   = "HIGH"
    da.PRIORITY_MEDIUM = "MEDIUM"
    da.PRIORITY_LOW    = "LOW"
    da.PRIORITY_NONE   = "NONE"

    class _AttItem:
        def __init__(self, priority, reasons=()):
            self.priority = priority
            self.score = 0
            self.reasons = tuple(reasons)

    def calc_priority(decision, events=None, now=None, require_feature_flag=True):
        fields = decision.get("fields", decision)
        readiness = fields.get("Readiness", fields.get("readiness", ""))
        if readiness in ("NOT_READY", "Not Ready"):
            return _AttItem("HIGH", ("Readiness = NOT_READY",))
        return _AttItem("NONE")

    da.calc_priority = calc_priority
    sys.modules["decision_attention"] = da

    # decision_orchestrator stub
    do = types.ModuleType("decision_orchestrator")

    class _OrcResult:
        def __init__(self, phase, next_step, blockers, awaiting_owner, after_resolution):
            self.phase = phase
            self.next_step = next_step
            self.blockers = blockers
            self.awaiting_owner = awaiting_owner
            self.after_resolution = after_resolution

    class _NS:
        def __init__(self, action, responsible, detail=""):
            self.action = action
            self.responsible = responsible
            self.detail = detail

    def orchestrate(decision, events=None, stakeholders=None,
                    precomputed_confidence=None, require_feature_flag=True):
        fields = decision.get("fields", decision)
        status = fields.get("Status", "")
        readiness = fields.get("Readiness", "")

        if status in ("DECIDED_YES", "DECIDED_NO"):
            return _OrcResult("DECIDED", _NS("ארכב", "system"), [], False, "")
        if status == "CANCELLED":
            return _OrcResult("CLOSED", _NS("ארכב", "system"), [], False, "")
        if readiness in ("NOT_READY", "Not Ready"):
            return _OrcResult(
                "BLOCKED",
                _NS("השג מסמך תומך", "הצוות", "חסר מידע"),
                ["חסר מידע"],
                False,
                "המערכת תסמן REVIEW.",
            )
        return _OrcResult(
            "COLLECTING",
            _NS("הוסף ראיות", "הצוות"),
            [], False, "",
        )

    do.orchestrate = orchestrate
    sys.modules["decision_orchestrator"] = do

    # feature_flags stub — always enabled for tests
    ff = types.ModuleType("feature_flags")
    ff.is_enabled = lambda name: True
    sys.modules["feature_flags"] = ff

    # tools.contact_resolver has no heavy deps by itself, but `import
    # tools.contact_resolver` would run tools/__init__.py first, which
    # eagerly imports tools.dispatcher -> tools.airtable_tools ->
    # airtable_schema.TABLE_ALIASES, none of which exist in this stubbed
    # environment. Load the file directly instead, bypassing tools/__init__.py.
    _cr_path = os.path.join(os.path.dirname(__file__), "tools", "contact_resolver.py")
    _cr_spec = importlib.util.spec_from_file_location("tools.contact_resolver", _cr_path)
    _real_contact_resolver = importlib.util.module_from_spec(_cr_spec)
    sys.modules["tools.contact_resolver"] = _real_contact_resolver  # needed by dataclass() before exec
    _cr_spec.loader.exec_module(_real_contact_resolver)

    # tools.airtable_gateway stub
    tools = types.ModuleType("tools")
    ag = types.ModuleType("tools.airtable_gateway")
    ag.airtable_search = lambda *a, **kw: []
    ag.airtable_create = lambda *a, **kw: None
    ag.airtable_patch  = lambda *a, **kw: None
    tools.contact_resolver = _real_contact_resolver
    sys.modules["tools"] = tools
    sys.modules["tools.airtable_gateway"] = ag
    sys.modules["tools.contact_resolver"] = _real_contact_resolver


_STUBBED_MODULE_NAMES = (
    "airtable_schema", "decision_pipeline", "decision_confidence",
    "decision_attention", "decision_orchestrator", "feature_flags",
    "tools", "tools.airtable_gateway", "tools.contact_resolver",
)
_ORIGINAL_MODULES: dict = {}


def setUpModule():
    """Install the stubs only once this module's own tests are about to run
    (not at collection time) — core.reasoning_entity/ports/engines/adapters
    import decision_pipeline/decision_confidence/decision_attention/
    decision_orchestrator/feature_flags/tools.airtable_gateway lazily inside
    function bodies, so the stubs aren't needed for the module-level imports
    below. Deferring keeps this file from permanently clobbering
    sys.modules["decision_orchestrator"] (etc.) for other test files that
    share this pytest process, e.g. test_decision_orchestrator.py's
    unittest.mock.patch("decision_orchestrator....", ...) calls."""
    for name in _STUBBED_MODULE_NAMES:
        _ORIGINAL_MODULES[name] = sys.modules.get(name)
    _install_stubs()


def tearDownModule():
    """Restore the real modules after this file's tests finish."""
    for name, original in _ORIGINAL_MODULES.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


# ── Now import core (no stubs needed — see setUpModule above) ───────────────
from core.reasoning_entity import (   # noqa: E402
    ENTITY_DECISION, ENTITY_LEAD,
    PHASE_BLOCKED, PHASE_COLLECTING, PHASE_DECIDED, PHASE_CLOSED, PHASE_REVIEW,
    PRIORITY_HIGH, PRIORITY_NONE,
    TRUST_T2, TRUST_T3,
    NextStep, ReasoningAdapter, ReasoningEntity, ReasoningResult,
)
from core.reasoning_ports import ReasoningPorts, _NullStorage, _NullVerifier, _ProductionContacts
from core.reasoning_engines import run
from core.adapters.decision_adapter import DecisionAdapter, append_reasoning_block as decision_block
from core.adapters.leads_adapter import LeadsAdapter, append_reasoning_block as leads_block


# ══════════════════════════════════════════════════════════════════════════════
# Shared fakes
# ══════════════════════════════════════════════════════════════════════════════

class FakeVerifier:
    def __init__(self, status="ok"):
        self._status = status
    def verify(self, text, source):
        return {"status": self._status}


def _fake_ports(**overrides):
    return ReasoningPorts(
        verifier=overrides.get("verifier", FakeVerifier()),
        storage=overrides.get("storage", _NullStorage()),
    )


def _decision_record(status="OPEN", readiness="", domain="general", title="Test Decision"):
    return {
        "id": "rec_test_001",
        "fields": {
            "Title": title,
            "Status": status,
            "Domain": domain,
            "Readiness": readiness,
        }
    }


def _lead_record(status="NEW", score=50, source="whatsapp"):
    return {
        "id": "rec_lead_001",
        "fields": {
            "Name": "Israel Israeli",
            "Status": status,
            "Score": score,
            "Source Channel": source,
            "Last Message": "מעוניין לשמוע פרטים",
        }
    }


def _entity(status="OPEN", readiness="", domain="general", events=None, metadata=None):
    m = {"title": "Test", "readiness": readiness}
    if metadata:
        m.update(metadata)
    return ReasoningEntity(
        entity_type=ENTITY_DECISION,
        entity_id="rec_test_001",
        domain=domain,
        status=status,
        raw_input="חתמנו על החוזה",
        events=events or [],
        metadata=m,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Section A — reasoning_entity.py
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningEntity(unittest.TestCase):

    def test_entity_constructs_with_required_fields(self):
        e = ReasoningEntity(
            entity_type=ENTITY_DECISION,
            entity_id="rec001",
            domain="general",
            status="OPEN",
            raw_input="test",
        )
        self.assertEqual(e.entity_type, ENTITY_DECISION)
        self.assertEqual(e.events, [])
        self.assertEqual(e.evidence, [])
        self.assertEqual(e.metadata, {})
        self.assertIsNone(e.owner)

    def test_result_as_dict_contains_all_keys(self):
        r = ReasoningResult(
            entity_type=ENTITY_DECISION,
            entity_id="rec001",
            phase=PHASE_COLLECTING,
            trust_level=TRUST_T2,
            confidence_score=0.55,
            attention_priority=PRIORITY_NONE,
            next_step=NextStep("action", "person", "detail"),
        )
        d = r.as_dict()
        for key in ("entity_type", "entity_id", "phase", "trust_level",
                    "confidence_score", "attention_priority", "next_step",
                    "blockers", "awaiting_owner", "after_resolution",
                    "conflict_count", "errors"):
            self.assertIn(key, d, f"Missing key: {key}")

    def test_nextstep_is_frozen(self):
        ns = NextStep("action", "person")
        with self.assertRaises(Exception):
            ns.action = "changed"   # type: ignore

    def test_adapter_base_raises_not_implemented(self):
        a = ReasoningAdapter()
        with self.assertRaises(NotImplementedError):
            a.to_entity({})
        with self.assertRaises(NotImplementedError):
            a.from_result(None)   # type: ignore

    def test_domain_rules_returns_dict(self):
        a = ReasoningAdapter()
        self.assertIsInstance(a.domain_rules(), dict)


# ══════════════════════════════════════════════════════════════════════════════
# Section B — reasoning_ports.py
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningPorts(unittest.TestCase):

    def test_null_storage_returns_empty_list(self):
        s = _NullStorage()
        self.assertEqual(s.get("SomeTable", ""), [])

    def test_null_storage_create_returns_none(self):
        s = _NullStorage()
        self.assertIsNone(s.create("SomeTable", {}))

    def test_null_verifier_returns_ok(self):
        v = _NullVerifier()
        result = v.verify("any text", "manual")
        self.assertEqual(result["status"], "ok")

    def test_ports_defaults_are_null_impls(self):
        ports = ReasoningPorts()
        # Should not raise
        self.assertEqual(ports.storage.get("T", ""), [])
        self.assertEqual(ports.verifier.verify("", ""), {"status": "ok"})

    def test_ports_accepts_custom_verifier(self):
        fake = FakeVerifier(status="warn")
        ports = ReasoningPorts(verifier=fake)
        self.assertEqual(ports.verifier.verify("x", "y")["status"], "warn")

    def test_production_contacts_delegates_to_contact_resolver(self):
        # Regression: _ProductionContacts previously imported a
        # contact_resolver.find_or_create_contact that never existed anywhere
        # in the repo, always raised ImportError, and silently swallowed it
        # into a fabricated {"status": "found", "matches": []}. It must now
        # call the real tools/contact_resolver.py::resolve(), same as
        # decision_ports.py's working _ContactResolverAdapter.
        from tools.contact_resolver import ResolveStatus, ContactMatch, ResolveResult
        match = ContactMatch(record_id="rec1", name="Dana", email="", phone="", contact_type="", company="", score=0.9)
        fake_result = ResolveResult(status=ResolveStatus.FOUND_ONE, query="Dana", matches=[match], message="")
        with patch("tools.contact_resolver.resolve", return_value=fake_result) as mock_resolve:
            out = _ProductionContacts().find_or_create("Dana")
        mock_resolve.assert_called_once_with("Dana")
        self.assertEqual(out["status"], "found_one")
        self.assertEqual(out["contact"], match)

    def test_production_contacts_fails_soft_to_not_found(self):
        with patch("tools.contact_resolver.resolve", side_effect=RuntimeError("boom")):
            out = _ProductionContacts().find_or_create("Dana")
        self.assertEqual(out, {"status": "not_found", "matches": []})


# ══════════════════════════════════════════════════════════════════════════════
# Section C — DecisionAdapter
# ══════════════════════════════════════════════════════════════════════════════

class TestDecisionAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = DecisionAdapter()

    def test_entity_type_is_decision(self):
        self.assertEqual(self.adapter.entity_type, ENTITY_DECISION)

    def test_to_entity_maps_basic_fields(self):
        record = _decision_record(status="OPEN", domain="real_estate", title="Blue View")
        entity = self.adapter.to_entity(record)
        self.assertEqual(entity.entity_type, ENTITY_DECISION)
        self.assertEqual(entity.entity_id, "rec_test_001")
        self.assertEqual(entity.domain, "real_estate")
        self.assertEqual(entity.status, "OPEN")
        self.assertEqual(entity.metadata["title"], "Blue View")

    def test_to_entity_extracts_owner_from_stakeholders(self):
        stakeholders = [{
            "id": "rec_sh_001",
            "fields": {
                "Role": "Owner",
                "Contact": ["Eliyahu"],
                "Position": "",
            }
        }]
        entity = self.adapter.to_entity(
            _decision_record(), stakeholders=stakeholders
        )
        self.assertEqual(entity.owner, "Eliyahu")

    def test_to_entity_no_owner_when_no_stakeholders(self):
        entity = self.adapter.to_entity(_decision_record())
        self.assertIsNone(entity.owner)

    def test_to_entity_raw_input_from_last_event(self):
        events = [
            {"id": "ev1", "fields": {"Raw Content": "first"}},
            {"id": "ev2", "fields": {"Raw Content": "second"}},
        ]
        entity = self.adapter.to_entity(_decision_record(), events=events)
        self.assertEqual(entity.raw_input, "second")

    def test_to_entity_raw_input_fallback_to_title(self):
        entity = self.adapter.to_entity(_decision_record(title="Fallback Title"))
        self.assertIn("Fallback", entity.raw_input)

    def test_domain_rules_returns_expected_thresholds(self):
        rules = self.adapter.domain_rules()
        self.assertIn("confidence_ready_threshold", rules)
        self.assertIn("confidence_decide_threshold", rules)
        self.assertGreater(rules["confidence_decide_threshold"],
                           rules["confidence_ready_threshold"])

    def test_from_result_returns_empty_for_decided(self):
        result = ReasoningResult(
            entity_type=ENTITY_DECISION, entity_id="r",
            phase=PHASE_DECIDED, trust_level=TRUST_T2,
            confidence_score=0.9, attention_priority=PRIORITY_NONE,
        )
        self.assertEqual(self.adapter.from_result(result), "")

    def test_from_result_returns_empty_for_closed(self):
        result = ReasoningResult(
            entity_type=ENTITY_DECISION, entity_id="r",
            phase=PHASE_CLOSED, trust_level=TRUST_T2,
            confidence_score=0.0, attention_priority=PRIORITY_NONE,
        )
        self.assertEqual(self.adapter.from_result(result), "")

    def test_from_result_contains_next_step(self):
        result = ReasoningResult(
            entity_type=ENTITY_DECISION, entity_id="r",
            phase=PHASE_BLOCKED, trust_level=TRUST_T2,
            confidence_score=0.3, attention_priority=PRIORITY_HIGH,
            next_step=NextStep("השג חוזה", "הצוות", "חסר חוזה"),
            blockers=["חסר חוזה"],
        )
        rendered = self.adapter.from_result(result)
        self.assertIn("השג חוזה", rendered)
        self.assertIn("הצוות", rendered)
        self.assertIn("חסר חוזה", rendered)

    def test_from_result_shows_confidence_bar(self):
        result = ReasoningResult(
            entity_type=ENTITY_DECISION, entity_id="r",
            phase=PHASE_COLLECTING, trust_level=TRUST_T2,
            confidence_score=0.7, attention_priority=PRIORITY_NONE,
            next_step=NextStep("הוסף ראיות", "הצוות"),
        )
        rendered = self.adapter.from_result(result)
        self.assertIn("70%", rendered)
        self.assertIn("█", rendered)


# ══════════════════════════════════════════════════════════════════════════════
# Section D — LeadsAdapter
# ══════════════════════════════════════════════════════════════════════════════

class TestLeadsAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = LeadsAdapter()

    def test_entity_type_is_lead(self):
        self.assertEqual(self.adapter.entity_type, ENTITY_LEAD)

    def test_to_entity_maps_basic_fields(self):
        entity = self.adapter.to_entity(_lead_record(status="HOT", score=75))
        self.assertEqual(entity.entity_type, ENTITY_LEAD)
        self.assertEqual(entity.entity_id, "rec_lead_001")
        self.assertEqual(entity.metadata["lead_score"], 75)

    def test_status_normalisation_hot(self):
        entity = self.adapter.to_entity(_lead_record(status="HOT"))
        self.assertEqual(entity.status, "OPEN")

    def test_status_normalisation_converted(self):
        entity = self.adapter.to_entity(_lead_record(status="converted"))
        self.assertEqual(entity.status, "DECIDED_YES")

    def test_status_normalisation_lost(self):
        entity = self.adapter.to_entity(_lead_record(status="lost"))
        self.assertEqual(entity.status, "DECIDED_NO")

    def test_status_normalisation_hebrew_hot(self):
        record = _lead_record()
        record["fields"]["Status"] = "חם"
        entity = self.adapter.to_entity(record)
        self.assertEqual(entity.status, "OPEN")

    def test_domain_inferred_from_source_real_estate(self):
        record = _lead_record()
        record["fields"]["Source"] = "נדל\"ן"
        entity = self.adapter.to_entity(record)
        self.assertEqual(entity.domain, "real_estate")

    def test_domain_inferred_from_source_import(self):
        record = _lead_record()
        record["fields"]["Source"] = "יבוא"
        entity = self.adapter.to_entity(record)
        self.assertEqual(entity.domain, "import")

    def test_domain_defaults_to_general(self):
        entity = self.adapter.to_entity(_lead_record())
        self.assertEqual(entity.domain, "general")

    def test_source_reliability_whatsapp(self):
        entity = self.adapter.to_entity(_lead_record(source="whatsapp"))
        self.assertEqual(entity.metadata["source_reliability"], "client")

    def test_domain_rules_inactive_days_shorter_than_decision(self):
        lead_rules     = LeadsAdapter().domain_rules()
        decision_rules = DecisionAdapter().domain_rules()
        self.assertLess(
            lead_rules["inactive_days"],
            decision_rules["inactive_days"],
            "Leads should have shorter inactivity window than Decisions",
        )

    def test_domain_rules_confidence_threshold_lower_than_decision(self):
        lead_rules     = LeadsAdapter().domain_rules()
        decision_rules = DecisionAdapter().domain_rules()
        self.assertLess(
            lead_rules["confidence_ready_threshold"],
            decision_rules["confidence_ready_threshold"],
            "Leads should have lower confidence threshold than Decisions",
        )

    def test_from_result_contains_phase_label(self):
        result = ReasoningResult(
            entity_type=ENTITY_LEAD, entity_id="r",
            phase=PHASE_BLOCKED, trust_level=TRUST_T2,
            confidence_score=0.3, attention_priority=PRIORITY_NONE,
            next_step=NextStep("פנה ללקוח", "סוכן"),
        )
        rendered = self.adapter.from_result(result)
        self.assertIn("חסום", rendered)
        self.assertIn("פנה ללקוח", rendered)


# ══════════════════════════════════════════════════════════════════════════════
# Section E — reasoning_engines.run() integration
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningEngines(unittest.TestCase):

    def _run(self, **kwargs):
        entity = _entity(**kwargs)
        return run(entity, ports=_fake_ports(), require_feature_flag=False)

    def test_run_returns_reasoning_result(self):
        result = self._run()
        self.assertIsInstance(result, ReasoningResult)

    def test_run_entity_type_preserved(self):
        result = self._run()
        self.assertEqual(result.entity_type, ENTITY_DECISION)

    def test_run_entity_id_preserved(self):
        result = self._run()
        self.assertEqual(result.entity_id, "rec_test_001")

    def test_run_not_ready_gives_blocked_phase(self):
        result = self._run(status="OPEN", readiness="NOT_READY")
        self.assertEqual(result.phase, PHASE_BLOCKED)

    def test_run_decided_yes_gives_decided_phase(self):
        result = self._run(status="DECIDED_YES")
        self.assertEqual(result.phase, PHASE_DECIDED)

    def test_run_decided_no_gives_decided_phase(self):
        result = self._run(status="DECIDED_NO")
        self.assertEqual(result.phase, PHASE_DECIDED)

    def test_run_cancelled_gives_closed_phase(self):
        result = self._run(status="CANCELLED")
        self.assertEqual(result.phase, PHASE_CLOSED)

    def test_run_open_no_events_gives_zero_confidence(self):
        result = self._run(events=[])
        self.assertEqual(result.confidence_score, 0.0)

    def test_run_with_events_gives_nonzero_confidence(self):
        events = [{"id": "ev1", "fields": {"Trust Level": "T2", "Status": "Active"}}]
        result = self._run(events=events)
        self.assertGreater(result.confidence_score, 0.0)

    def test_run_not_ready_attention_is_high(self):
        result = self._run(readiness="NOT_READY")
        self.assertEqual(result.attention_priority, PRIORITY_HIGH)

    def test_run_no_errors_on_clean_input(self):
        result = self._run()
        self.assertEqual(result.errors, [], f"Unexpected errors: {result.errors}")

    def test_run_returns_next_step(self):
        result = self._run(status="OPEN", readiness="NOT_READY")
        self.assertIsNotNone(result.next_step)
        self.assertIsInstance(result.next_step, NextStep)
        self.assertTrue(result.next_step.action)
        self.assertTrue(result.next_step.responsible)

    def test_trust_level_t3_for_contract_source(self):
        entity = _entity(metadata={
            "title": "Test",
            "readiness": "",
            "source_reliability": "contract",
            "channel": "document",
        })
        result = run(entity, ports=_fake_ports(), require_feature_flag=False)
        self.assertEqual(result.trust_level, TRUST_T3)

    def test_trust_level_t0_for_hallucination(self):
        entity = _entity(metadata={
            "title": "Test",
            "readiness": "",
            "source_reliability": "contract",
            "channel": "document",
        })
        ports = _fake_ports(verifier=FakeVerifier(status="hallucination"))
        result = run(entity, ports=ports, require_feature_flag=False)
        self.assertEqual(result.trust_level, "T0")

    def test_precomputed_confidence_is_used(self):
        class _FakeConfResult:
            score = 0.99
            missing = []
            conflicting = ["ev_a", "ev_b"]
        result = run(
            _entity(),
            ports=_fake_ports(),
            precomputed_confidence=_FakeConfResult(),
            require_feature_flag=False,
        )
        self.assertEqual(result.confidence_score, 0.99)
        self.assertEqual(result.conflict_count, 2)

    def test_feature_flag_off_returns_disabled_result(self):
        result = run(_entity(), ports=_fake_ports(), require_feature_flag=True)
        # feature_flags stub has is_enabled=True, so this should still work.
        # To simulate flag OFF, patch the stub.
        import feature_flags as ff
        original = ff.is_enabled
        ff.is_enabled = lambda name: False
        try:
            result = run(_entity(), ports=_fake_ports(), require_feature_flag=True)
            self.assertIn("feature_flag_off", result.errors)
        finally:
            ff.is_enabled = original


# ══════════════════════════════════════════════════════════════════════════════
# Section F — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):

    def test_entity_with_empty_raw_input(self):
        entity = ReasoningEntity(
            entity_type=ENTITY_DECISION, entity_id="r",
            domain="general", status="OPEN", raw_input="",
        )
        result = run(entity, ports=_fake_ports(), require_feature_flag=False)
        self.assertIsNotNone(result)
        self.assertEqual(result.errors, [])

    def test_entity_with_unknown_status(self):
        result = run(
            _entity(status="UNKNOWN_STATUS"),
            ports=_fake_ports(),
            require_feature_flag=False,
        )
        self.assertIsNotNone(result)
        # Should not crash — phase defaults to COLLECTING
        self.assertIn(result.phase, (PHASE_COLLECTING, PHASE_BLOCKED, PHASE_REVIEW))

    def test_decision_adapter_to_entity_missing_fields(self):
        adapter = DecisionAdapter()
        # Record with only id — all fields missing
        entity = adapter.to_entity({"id": "rec_bare"})
        self.assertEqual(entity.entity_id, "rec_bare")
        self.assertEqual(entity.domain, "general")   # fallback
        self.assertEqual(entity.status, "")

    def test_leads_adapter_to_entity_invalid_score(self):
        adapter = LeadsAdapter()
        record = _lead_record()
        record["fields"]["Score"] = "not_a_number"
        entity = adapter.to_entity(record)
        self.assertEqual(entity.metadata["lead_score"], 0)

    def test_append_reasoning_block_decision_returns_string(self):
        block = decision_block(
            _decision_record(readiness="NOT_READY"),
            events=[],
            stakeholders=[],
        )
        self.assertIsInstance(block, str)

    def test_append_reasoning_block_leads_returns_string(self):
        block = leads_block(_lead_record(), events=[])
        self.assertIsInstance(block, str)

    def test_decision_adapter_from_result_no_next_step(self):
        adapter = DecisionAdapter()
        result = ReasoningResult(
            entity_type=ENTITY_DECISION, entity_id="r",
            phase=PHASE_COLLECTING, trust_level=TRUST_T2,
            confidence_score=0.5, attention_priority=PRIORITY_NONE,
            next_step=None,
        )
        # Should not raise even with next_step=None
        rendered = adapter.from_result(result)
        self.assertIsInstance(rendered, str)

    def test_result_as_dict_next_step_none(self):
        result = ReasoningResult(
            entity_type=ENTITY_DECISION, entity_id="r",
            phase=PHASE_COLLECTING, trust_level=TRUST_T2,
            confidence_score=0.5, attention_priority=PRIORITY_NONE,
        )
        d = result.as_dict()
        self.assertIsNone(d["next_step"])

    def test_leads_adapter_from_result_with_errors_does_not_raise(self):
        adapter = LeadsAdapter()
        result = ReasoningResult(
            entity_type=ENTITY_LEAD, entity_id="r",
            phase=PHASE_COLLECTING, trust_level=TRUST_T2,
            confidence_score=0.3, attention_priority=PRIORITY_NONE,
            next_step=NextStep("action", "person"),
            errors=["confidence_engine: something went wrong"],
        )
        # Should not raise — just logs warning
        rendered = adapter.from_result(result)
        self.assertIsInstance(rendered, str)


# ══════════════════════════════════════════════════════════════════════════════
# Runner (plain python, no pytest required)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in (
        TestReasoningEntity,
        TestReasoningPorts,
        TestDecisionAdapter,
        TestLeadsAdapter,
        TestReasoningEngines,
        TestEdgeCases,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
