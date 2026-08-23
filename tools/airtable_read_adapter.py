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
        response_url: str = "",
        response_reason: str = "",
    ):
        super().__init__(message)
        self.cause = cause
        self.status_code = status_code
        self.response_text = response_text
        self.response_url = response_url
        self.response_reason = response_reason


def list_records(
    table: str,
    formula: str = "",
    *,
    max_records: int | str | None = 20,
    fields: list[str] | None = None,
    paginate: bool | None = None,
    timeout: float = 10,
) -> list[dict]:
    """Return raw Airtable records without exposing provider details."""
    try:
        return at_list_by_formula(
            table,
            formula,
            max_records,
            fields=fields,
            paginate=not max_records if paginate is None else paginate,
            timeout=timeout,
        )
    except AirtableLookupError as exc:
        raise AirtableReadError(
            str(exc),
            cause=exc.cause,
            status_code=exc.status_code,
            response_text=exc.response_text,
            response_url=exc.response_url,
            response_reason=exc.response_reason,
        ) from exc
