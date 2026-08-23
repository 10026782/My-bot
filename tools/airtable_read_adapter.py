"""Public read boundary for business code that needs Airtable records."""

from __future__ import annotations

from tools.airtable_gateway import at_list_by_formula


def list_records(
    table: str,
    formula: str = "",
    *,
    max_records: int | None = 20,
    fields: list[str] | None = None,
) -> list[dict]:
    """Return raw Airtable records without exposing provider details."""
    return at_list_by_formula(
        table,
        formula,
        max_records,
        fields=fields,
        paginate=not max_records,
    )
