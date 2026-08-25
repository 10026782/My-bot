"""Provider-neutral query intent contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Query:
    operation: str
    arguments: tuple[Any, ...] = ()


def equals(
    field: str,
    value: object,
    *,
    spaced: bool = False,
    case_insensitive: bool = False,
) -> Query:
    return Query("equals", (field, value, spaced, case_insensitive))


def contains(
    field: str,
    value: object,
    *,
    case_sensitive: bool = False,
    case_insensitive: bool = False,
) -> Query:
    return Query("contains", (field, value, case_sensitive, case_insensitive))


def array_contains(field: str, value: object) -> Query:
    return Query("array_contains", (field, value))


def record_id_equals(value: object) -> Query:
    return Query("record_id_equals", (value,))


def before(field: str, value: object) -> Query:
    return Query("before", (field, value))


def after(field: str, value: object) -> Query:
    return Query("after", (field, value))


def date_add(value: object, amount: int, unit: str) -> Query:
    return Query("date_add", (value, amount, unit))


def today() -> Query:
    return Query("today")


def created_time() -> Query:
    return Query("created_time")


def same_day(field: object, value: object) -> Query:
    return Query("same_day", (field, value))


def greater_or_equal(field: str, value: object) -> Query:
    return Query("greater_or_equal", (field, value))


def not_equals(field: str, value: object, *, spaced: bool = False) -> Query:
    return Query("not_equals", (field, value, spaced))


def all_of(*clauses: Query | str) -> Query:
    return Query("all_of", tuple(clause for clause in clauses if clause))


def any_of(*clauses: Query | str) -> Query:
    return Query("any_of", tuple(clause for clause in clauses if clause))


def negate(clause: Query | str) -> Query:
    return Query("negate", (clause,)) if clause else Query("empty")
