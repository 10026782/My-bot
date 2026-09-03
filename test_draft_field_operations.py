from core.draft_fields import FieldMetadata, FieldOperationError, clear_field, move_field, set_field, swap_fields
from core.lead_service import LEAD_FIELD_METADATA, new_empty_draft, set_draft_field


def test_lead_set_uses_existing_draft_and_normalizes_phone():
    draft = new_empty_draft("telegram")
    assert set_draft_field(draft, "phone", "050-1234567") == (True, "")
    assert draft["phone"] == "0501234567"


def test_operations_are_atomic_and_key_based():
    fields = {
        "a": FieldMetadata("a", "A", compatible_field_type="text"),
        "b": FieldMetadata("b", "B", compatible_field_type="text"),
        "number": FieldMetadata("number", "Number", choices=("1", "2")),
    }
    draft = {"a": "left", "b": "right", "number": "1"}
    swap_fields(draft, "a", "b", fields)
    assert draft["a"] == "right" and draft["b"] == "left"
    before = dict(draft)
    try:
        move_field(draft, "a", "number", fields)
    except FieldOperationError:
        pass
    else:
        raise AssertionError("incompatible move must fail")
    assert draft == before
    try:
        swap_fields(draft, "a", "number", fields)
    except FieldOperationError:
        pass
    else:
        raise AssertionError("incompatible swap must fail")
    assert draft == before
    clear_field(draft, "number", fields)
    assert draft["number"] == ""
    set_field(draft, "number", "2", fields)
    assert draft["number"] == "2"


def test_lead_metadata_is_user_facing_and_choice_ready():
    assert LEAD_FIELD_METADATA["domain"].input_type == "single_select"
    assert LEAD_FIELD_METADATA["domain"].choice_options()
    assert all("field_key" not in option for option in LEAD_FIELD_METADATA["domain"].choice_options())


if __name__ == "__main__":
    test_lead_set_uses_existing_draft_and_normalizes_phone()
    test_operations_are_atomic_and_key_based()
    test_lead_metadata_is_user_facing_and_choice_ready()
    print("test_draft_field_operations.py: 3 passed")
