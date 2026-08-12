# test_cmd_marketing_status.py — F23 BOSS Marketing Bridge (M2)
#
# Standalone script, run directly: python3 test_cmd_marketing_status.py
# (no pytest harness in this repo — see CLAUDE.md's Tests section). Covers
# the authorization/domain-filtering behavior of cmd_marketing.py's
# /marketing_status + mkt_status: callback support functions, which
# marketing_orchestrator's own tests don't touch (that module is pure and
# never sees an identity). Mocks marketing_gateway so no real Airtable I/O
# happens.

from unittest.mock import patch

from airtable_schema import MarketingDemandFields as MDF, MarketingDemandStage as Stage
from cmd_marketing import _authorized_demand_list, _get_next_action_card


class _FakeIdentity:
    """Minimal stand-in for identity.Identity — only the method these
    functions actually call."""

    def __init__(self, role: str, allowed_domains: list[str] | None = None):
        self.role = role
        self.allowed_domains = allowed_domains or []

    def can_access_domain(self, domain: str) -> bool:
        if self.role == "owner":
            return True
        if self.role == "partner":
            return domain in self.allowed_domains
        return True


_MIXED_DOMAIN_RECORDS = [
    {"id": "recA", "fields": {MDF.DOMAIN: "real_estate", MDF.NAME: "A"}},
    {"id": "recB", "fields": {MDF.DOMAIN: "import", MDF.NAME: "B"}},
    {"id": "recC", "fields": {MDF.DOMAIN: "real_estate", MDF.NAME: "C"}},
]


def test_partner_sees_only_allowed_domain():
    identity = _FakeIdentity("partner", allowed_domains=["real_estate"])
    with patch("marketing_gateway.list_demands", return_value=_MIXED_DOMAIN_RECORDS):
        result = _authorized_demand_list(identity)
    assert {r["id"] for r in result} == {"recA", "recC"}


def test_owner_sees_all_domains():
    identity = _FakeIdentity("owner")
    with patch("marketing_gateway.list_demands", return_value=_MIXED_DOMAIN_RECORDS):
        result = _authorized_demand_list(identity)
    assert {r["id"] for r in result} == {"recA", "recB", "recC"}


def test_next_action_card_forged_id_returns_generic_error():
    identity = _FakeIdentity("owner")
    with patch("marketing_gateway.get_demand", return_value=None):
        result = _get_next_action_card("rec_does_not_exist", identity)
    assert result["ok"] is False
    assert result["error"] == "הדרישה לא נמצאה"


def test_next_action_card_unauthorized_domain_returns_same_generic_error():
    identity = _FakeIdentity("partner", allowed_domains=["real_estate"])
    demand = {MDF.NAME: "t", MDF.DOMAIN: "import", MDF.CURRENT_STAGE: Stage.INTAKE, MDF.STATUS: "Active"}
    with patch("marketing_gateway.get_demand", return_value=demand):
        result = _get_next_action_card("recSomeone Elses Demand".replace(" ", ""), identity)
    assert result["ok"] is False
    # Same message as the forged/missing-id case — no enumeration signal.
    assert result["error"] == "הדרישה לא נמצאה"


def test_next_action_card_authorized_returns_text():
    identity = _FakeIdentity("owner")
    demand = {
        MDF.NAME: "t", MDF.DOMAIN: "real_estate",
        MDF.CURRENT_STAGE: Stage.INTAKE, MDF.STATUS: "Active",
    }
    with patch("marketing_gateway.get_demand", return_value=demand):
        result = _get_next_action_card("recAuthorized", identity)
    assert result["ok"] is True
    assert "צעד הבא" in result["text"]
    assert result["keyboard"] is None


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"test_cmd_marketing_status.py: {len(tests)}/{len(tests)} passed")
