from unittest.mock import patch

import tma_api
from airtable_schema import MarketingCreativesFields as MCF, MarketingDemandFields as MDF, MarketingDemandStage as Stage


class Identity:
    def __init__(self, allowed):
        self.allowed = allowed

    def can_access_domain(self, domain):
        return domain in self.allowed


def test_tma_marketing_uses_orchestrator_and_filters_domains():
    records = [
        {"id": "internal-1", "fields": {MDF.NAME: "Visible", MDF.DOMAIN: "real_estate", MDF.CURRENT_STAGE: Stage.INTAKE}},
        {"id": "internal-2", "fields": {MDF.NAME: "Hidden", MDF.DOMAIN: "import", MDF.CURRENT_STAGE: Stage.INTAKE}},
    ]
    with patch("marketing_gateway.list_demands", return_value=records), patch("marketing_gateway.get_creative"):
        result = tma_api._marketing_status_payload(Identity(["real_estate"]))
    assert result["count"] == 1
    assert result["demands"][0]["title"] == "Visible"
    assert "internal-1" not in str(result)


def test_tma_marketing_inconsistent_state_is_fail_closed():
    demand = {"id": "internal-1", "fields": {MDF.NAME: "Mixed", MDF.DOMAIN: "real_estate", MDF.CURRENT_STAGE: Stage.IDEAS_GENERATED, MDF.CREATIVES: ["c1", "c2"]}}
    creatives = {
        "c1": {MCF.SELECTION_STATUS: "Pending Review"},
        "c2": {MCF.SELECTION_STATUS: "Pending Review"},
    }
    with patch("marketing_gateway.list_demands", return_value=[demand]), patch(
        "marketing_gateway.get_creative", side_effect=lambda cid: creatives[cid]
    ):
        result = tma_api._marketing_status_payload(Identity(["real_estate"]))
    assert result["demands"][0]["consistency_state"] == "inconsistent"
    assert "מצב לא עקבי" in result["demands"][0]["next_action"]


if __name__ == "__main__":
    test_tma_marketing_uses_orchestrator_and_filters_domains()
    test_tma_marketing_inconsistent_state_is_fail_closed()
    print("test_tma_marketing_status.py: 2/2 passed")
