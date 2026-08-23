import airtable_schema as schema
from schema_audit import TABLE_CLASS_MAP
from tools.schema_governance import find_unregistered_field_classes


VERIFIED_MAPPINGS = {
    schema.Tables.ACTION_CONTRACTS: schema.ActionContractsFields,
    schema.Tables.DAILY_CHECKIN: schema.DailyCheckinFields,
    schema.Tables.EMERGENCY_STOP_FLAGS: schema.EmergencyStopFlagFields,
    schema.Tables.EXTERNAL_EXECUTION_JOBS: schema.ExternalExecutionJobFields,
    schema.Tables.LEAD_EVENTS: schema.LeadEventFields,
    schema.Tables.MARKETING_DEMAND: schema.MarketingDemandFields,
    schema.Tables.MARKETING_PUBLICATIONS: schema.MarketingPublicationFields,
    schema.Tables.SESSIONS: schema.SessionsFields,
}


def test_verified_classes_are_registered_without_collisions():
    assert len(TABLE_CLASS_MAP) == len(set(TABLE_CLASS_MAP))
    assert len(TABLE_CLASS_MAP.values()) == len(set(TABLE_CLASS_MAP.values()))
    for table_name, fields_class in VERIFIED_MAPPINGS.items():
        assert TABLE_CLASS_MAP[table_name] is fields_class


def test_verified_classes_are_not_unregistered():
    unregistered = {finding["table"] for finding in find_unregistered_field_classes()}
    assert not unregistered.intersection(cls.__name__ for cls in VERIFIED_MAPPINGS.values())


if __name__ == "__main__":
    test_verified_classes_are_registered_without_collisions()
    test_verified_classes_are_not_unregistered()
    print("✅ schema governance tests passed")
