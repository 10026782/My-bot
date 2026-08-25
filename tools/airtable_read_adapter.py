"""Public read boundary for business code that needs Airtable records."""

from __future__ import annotations

import httpx

from core.query_contract import Query
from tools.airtable_gateway import AirtableLookupError
from tools.airtable_gateway import at_get_record
from tools.airtable_gateway import at_list_by_formula
from tools.airtable_gateway import at_list_page
from tools.airtable_gateway import escape_formula_value


def _field_ref(field: str) -> str:
    return "{" + str(field) + "}"


def render_query(query: Query | str) -> str:
    """Translate provider-neutral intent at the Airtable boundary only."""
    if isinstance(query, str):
        return query
    if not isinstance(query, Query):
        raise TypeError(f"unsupported query type: {type(query).__name__}")

    op, args = query.operation, query.arguments
    if op == "empty":
        return ""
    if op == "equals":
        field, value, spaced, case_insensitive = args
        if case_insensitive:
            return f"LOWER({_field_ref(field)})=LOWER('{escape_formula_value(value)}')"
        separator = " = " if spaced else "="
        return f"{_field_ref(field)}{separator}'{escape_formula_value(value)}'"
    if op == "not_equals":
        field, value, spaced = args
        separator = " != " if spaced else "!="
        return f"{_field_ref(field)}{separator}'{escape_formula_value(value)}'"
    if op == "contains":
        field, value, case_sensitive, case_insensitive = args
        escaped = escape_formula_value(value)
        if case_insensitive:
            return f"FIND(LOWER('{escaped}'), LOWER({_field_ref(field)}))"
        function = "FIND" if case_sensitive else "SEARCH"
        return f"{function}('{escaped}', {_field_ref(field)})"
    if op == "array_contains":
        field, value = args
        return f"FIND('{escape_formula_value(value)}', ARRAYJOIN({_field_ref(field)}))"
    if op == "record_id_equals":
        return f"RECORD_ID()='{escape_formula_value(args[0])}'"
    if op in {"before", "after"}:
        field, value = args
        return f"IS_{op.upper()}({_field_ref(field)}, '{escape_formula_value(value)}')"
    if op == "greater_or_equal":
        field, value = args
        return f"{_field_ref(field)}>={escape_formula_value(value)}"
    if op in {"all_of", "any_of"}:
        parts = [render_query(part) for part in args if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        function = "AND" if op == "all_of" else "OR"
        return f"{function}({', '.join(parts)})"
    if op == "negate":
        rendered = render_query(args[0])
        return f"NOT({rendered})" if rendered else ""
    raise ValueError(f"unsupported query operation: {op}")


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

    def as_http_status_error(self) -> httpx.HTTPStatusError:
        """Recreate the legacy httpx error for callers that expose it."""
        if self.status_code is None:
            raise ValueError("AirtableReadError has no HTTP status")
        request = httpx.Request("GET", self.response_url or "https://provider.invalid/records")
        response = httpx.Response(
            self.status_code,
            text=self.response_text,
            request=request,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return exc
        raise ValueError(f"status {self.status_code} is not an HTTP error")


def list_records(
    table: str,
    formula: Query | str = "",
    *,
    max_records: int | str | None = 20,
    limit: int | str | None = None,
    fields: list[str] | None = None,
    sort: list[dict[str, str]] | None = None,
    paginate: bool | None = None,
    timeout: float = 10,
) -> list[dict]:
    """Return raw records; ``limit`` is the provider-neutral result cap."""
    try:
        formula = render_query(formula)
        if limit is not None:
            max_records = limit
        return at_list_by_formula(
            table,
            formula,
            max_records,
            fields=fields,
            sort=sort,
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


def list_records_page(
    table: str,
    formula: Query | str = "",
    *,
    page_size: int | None = None,
    offset: str = "",
    max_records: int | str | None = None,
    fields: list[str] | None = None,
    timeout: float = 10,
) -> tuple[list[dict], str | None]:
    """Return one raw Airtable page and its next offset."""
    try:
        formula = render_query(formula)
        return at_list_page(
            table,
            formula,
            page_size=page_size,
            offset=offset,
            max_records=max_records,
            fields=fields,
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


def get_record(table: str, record_id: str, *, timeout: float = 10) -> dict:
    """Return one raw Airtable record without exposing provider details."""
    try:
        return at_get_record(table, record_id, timeout=timeout)
    except AirtableLookupError as exc:
        raise AirtableReadError(
            str(exc),
            cause=exc.cause,
            status_code=exc.status_code,
            response_text=exc.response_text,
            response_url=exc.response_url,
            response_reason=exc.response_reason,
        ) from exc


def get_record_fields(table: str, record_id: str, *, timeout: float = 10) -> dict:
    """Return one record's business fields, without exposing the raw envelope."""
    return get_record(table, record_id, timeout=timeout).get("fields", {})
