"""בדיקות רגרסיה — LEAD-TO-DEAL-ORIGIN-LINK (02/09/2026).

הרקע: ל-`crm_create_deal` יש שני מסלולים — Agent (ה-LLM בוחר את הכלי,
יכול לספק `origin_lead_id`) ודטרמיניסטי (`core.router.router.
parse_deterministic_create_deal` → `app._queue_deterministic_create_deal`,
agent_calls=0). המסלול הדטרמיניסטי מעולם לא קיבל דרך לספק `origin_lead_id`
— אין שום פקודה/טריגר דטרמיניסטי שיוצר עסקה מקושרת לליד. הכתיבה עצמה
(`commercial_crm.create_deal`), ה-schema וה-dispatcher כבר תמכו ב-
`origin_lead_id` נכון — זה חור ב-inlet, לא writer שבור.

הבדיקות כאן מוכיחות:
1. `app._queue_deterministic_create_deal()` מכניס `origin_lead_id` ל-payload
   כשסופק, ולא משנה כלום כשלא סופק (no regression למסלול הטקסטואלי הקיים).
2. `lead_conversion.resolve_lead_for_deal()` — ה-resolve-only step שמזין את
   `/dealfromlead` — מטפל נכון בכל מקרי הקצה: flag כבוי, query חסר, 0/כמה
   לידים תואמים, ליד בלי שם, domain לא מוכר/ריק, ומקרה ההצלחה.

pytest-native (assert, not a print/chk scaffold that never raises) — this
file's bare `def test_*()` functions match CI's auto-detect regex
(`^def test_`) and are routed through `python -m pytest`, so a helper that
only prints on failure would silently report every test as passed
regardless of outcome (exactly the class of gap
docs/audit/CI_TEST_HARNESS_FALSE_PASS_20260830.md documents for other
files) — real asserts are required here.
"""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-lead-deal-link-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:lead-deal-link-test")
os.environ.setdefault("AIRTABLE_API_KEY", "patLeadDealLinkTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLeadDealLinkTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
from identity import Identity, Role  # noqa: E402


def _owner_identity() -> Identity:
    return Identity(
        user_id="owner1", role=Role.OWNER, display_name="owner1",
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id="owner1",
    )


# ══════════════════════════════════════════════════════════════════
# 1. _queue_deterministic_create_deal() — origin_lead_id plumbing
# ══════════════════════════════════════════════════════════════════

def test_origin_lead_id_included_when_provided():
    identity = _owner_identity()
    captured = {}

    def _fake_queue_approval_detailed(tool_name, tool_inputs, *a, **kw):
        captured["tool_inputs"] = dict(tool_inputs)
        return {
            "message": "queued", "contract_id": "c1", "ok": True,
            "terminal_outcome": None, "action_tool": tool_name,
            "created_this_turn": True, "owner_notified": False,
        }

    with patch.object(app, "_queue_approval_detailed", side_effect=_fake_queue_approval_detailed), \
         patch.object(app, "enforce", return_value=None):
        app._queue_deterministic_create_deal(
            "עסקה עם ליד", "import", "chat1", "telegram", "text", identity,
            origin_lead_id="recLead123",
        )

    assert captured["tool_inputs"].get("origin_lead_id") == "recLead123"
    assert captured["tool_inputs"]["name"] == "עסקה עם ליד"
    assert captured["tool_inputs"]["domain"] == "import"


def test_origin_lead_id_absent_when_not_provided_no_regression():
    """The existing free-text trigger ("צור עסקה בשם X בתחום Y") never
    passes origin_lead_id — its payload shape must stay byte-for-byte the
    same as before this change."""
    identity = _owner_identity()
    captured = {}

    def _fake_queue_approval_detailed(tool_name, tool_inputs, *a, **kw):
        captured["tool_inputs"] = dict(tool_inputs)
        return {
            "message": "queued", "contract_id": "c1", "ok": True,
            "terminal_outcome": None, "action_tool": tool_name,
            "created_this_turn": True, "owner_notified": False,
        }

    with patch.object(app, "_queue_approval_detailed", side_effect=_fake_queue_approval_detailed), \
         patch.object(app, "enforce", return_value=None):
        app._queue_deterministic_create_deal(
            "עסקה בלי ליד", "general", "chat1", "telegram", "text", identity,
        )

    assert "origin_lead_id" not in captured["tool_inputs"]
    assert set(captured["tool_inputs"].keys()) == {"name", "domain", "owner_id"}


# ══════════════════════════════════════════════════════════════════
# 2. lead_conversion.resolve_lead_for_deal()
# ══════════════════════════════════════════════════════════════════

def _lead_record(rec_id: str, name: str, domain: str) -> dict:
    from airtable_schema import LeadFields
    return {"id": rec_id, "fields": {LeadFields.NAME: name, LeadFields.DOMAIN: domain}}


def test_flag_off_blocks_with_clear_message():
    import lead_conversion
    with patch("lead_conversion.is_enabled", return_value=False):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("דני")
    assert not name and not domain and not lead_id
    assert "LEAD_TO_DEAL" in err


def test_missing_query_is_rejected():
    import lead_conversion
    with patch("lead_conversion.is_enabled", return_value=True):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("")
    assert not name and err


def test_no_matching_lead():
    import lead_conversion
    with patch("lead_conversion.is_enabled", return_value=True), \
         patch("tma_api._at_list", return_value=[]):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("לא קיים")
    assert not name
    assert "לא קיים" in err


def test_multiple_matching_leads():
    import lead_conversion
    leads = [_lead_record("rec1", "דני כהן", "import"), _lead_record("rec2", "דני לוי", "import")]
    with patch("lead_conversion.is_enabled", return_value=True), \
         patch("tma_api._at_list", return_value=leads):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("דני")
    assert not name
    assert "דני כהן" in err and "דני לוי" in err


def test_lead_with_no_name_is_rejected():
    import lead_conversion
    lead = _lead_record("rec1", "", "import")
    with patch("lead_conversion.is_enabled", return_value=True), \
         patch("tma_api._at_list", return_value=[lead]):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("050-1234567")
    assert not name and not domain and err


def test_lead_with_unrecognized_domain_fails_to_clarify_not_guess():
    """Same principle as core/router/router.py's DeterministicDealParse:
    an unrecognized domain word fails closed instead of writing a guessed
    or raw value."""
    import lead_conversion
    lead = _lead_record("rec1", "דני כהן", "משהו-לא-קיים")
    with patch("lead_conversion.is_enabled", return_value=True), \
         patch("tma_api._at_list", return_value=[lead]):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("דני")
    assert not name and not domain and err


def test_lead_with_empty_domain_fails_to_clarify():
    import lead_conversion
    lead = _lead_record("rec1", "דני כהן", "")
    with patch("lead_conversion.is_enabled", return_value=True), \
         patch("tma_api._at_list", return_value=[lead]):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("דני")
    assert not domain and err


def test_happy_path_returns_name_domain_lead_id():
    import lead_conversion
    lead = _lead_record("recLeadABC", "דני כהן", "import")
    with patch("lead_conversion.is_enabled", return_value=True), \
         patch("tma_api._at_list", return_value=[lead]):
        name, domain, lead_id, err = lead_conversion.resolve_lead_for_deal("דני")
    assert err == ""
    assert name == "דני כהן"
    assert domain == "import"
    assert lead_id == "recLeadABC"


def test_happy_path_reuses_shared_lookup_with_convert_lead_to_contact():
    """resolve_lead_for_deal() and convert_lead_to_contact() must use the
    SAME lead-lookup helper — a hand-duplicated second lookup is exactly
    the kind of drift this session's guard work exists to prevent."""
    import inspect
    import lead_conversion
    src_convert = inspect.getsource(lead_conversion.convert_lead_to_contact)
    src_deal = inspect.getsource(lead_conversion.resolve_lead_for_deal)
    assert "_resolve_single_lead_by_query(" in src_convert
    assert "_resolve_single_lead_by_query(" in src_deal
