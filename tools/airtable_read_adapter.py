"""Public read boundary for business code that needs Airtable records."""

from __future__ import annotations

from tools.airtable_gateway import at_list_by_formula
from tools.airtable_gateway import AirtableLookupError


class AirtableReadError(RuntimeError):
    """Read failure with provider details retained for legacy callers."""

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
        status_code: int | None = None,
        response_text: str = "",
    ):
        super().__init__(message)
        self.cause = cause
        self.status_code = status_code
        self.response_text = response_text


def list_records(
    table: str,
    formula: str = "",
    *,
    max_records: int | str | None = 20,
    fields: list[str] | None = None,
) -> list[dict]:
    """Return raw Airtable records without exposing provider details."""
    try:
        return at_list_by_formula(
            table,
            formula,
            max_records,
            fields=fields,
            paginate=not max_records,
        )
    except AirtableLookupError as exc:
        raise AirtableReadError(
            str(exc),
            cause=exc.cause,
            status_code=exc.status_code,
            response_text=exc.response_text,
        ) from exc
