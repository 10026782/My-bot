from core.source_owner_mapping import (
    OwnerMappingSource,
    carried_owner_user_id,
    resolve_furniture_owner_user_id,
    resolve_owner_user_id,
)


MAPPINGS = {
    "whatsapp_destination": {"whatsapp:+972501234567": "eliyahu"},
    "email_recipient": {"leads@boss.co.il": "eliyahu"},
    "voice_destination": {"+97235555555": "eliyahu"},
}


def test_mapped_sources_resolve_canonical_user_id_only():
    assert resolve_owner_user_id(
        OwnerMappingSource.WHATSAPP_DESTINATION,
        "+972501234567",
        mappings=MAPPINGS,
    ) == "eliyahu"
    assert resolve_owner_user_id(
        OwnerMappingSource.EMAIL_RECIPIENT,
        " LEADS@BOSS.CO.IL ",
        mappings=MAPPINGS,
    ) == "eliyahu"
    assert resolve_owner_user_id(
        OwnerMappingSource.VOICE_DESTINATION,
        "tel:+97235555555",
        mappings=MAPPINGS,
    ) == "eliyahu"


def test_unmapped_and_wrong_source_fail_closed():
    assert resolve_owner_user_id(
        OwnerMappingSource.WHATSAPP_DESTINATION,
        "+972500000000",
        mappings=MAPPINGS,
    ) is None
    assert resolve_owner_user_id(
        OwnerMappingSource.EMAIL_RECIPIENT,
        "whatsapp:+972501234567",
        mappings=MAPPINGS,
    ) is None
    assert resolve_owner_user_id(
        OwnerMappingSource.VOICE_DESTINATION,
        "whatsapp:+972501234567",
        mappings=MAPPINGS,
    ) is None


def test_furniture_reuses_whatsapp_mapping_and_memory_requires_carried_owner():
    assert resolve_furniture_owner_user_id(
        "whatsapp:+972501234567",
        mappings=MAPPINGS,
    ) == "eliyahu"
    assert carried_owner_user_id(" owner-1 ") == "owner-1"
    assert carried_owner_user_id("") is None
