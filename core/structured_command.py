# core/structured_command.py — Canonical Write Infrastructure, Phase 2 (N18)
#
# Shared mechanics for deterministic "<trigger> | field | field | ..."
# power-user commands (e.g. Lead's "ליד חדש | שם | טלפון | domain | הערה").
# Extracted from core/lead_service.py::parse_structured_command() — the ONLY
# thing generalized here is trigger-matching + delimiter-detection + split;
# field names, order, and validation stay owned by each entity's own
# schema/parsing function. See ROADMAP.md N18: "Parsing mechanics is shared.
# Field semantics belong to the entity schema."

from __future__ import annotations

import re
from typing import Optional


def build_structured_trigger_re(trigger_pattern: str, delimiters: str = "|/") -> re.Pattern:
    """Builds the `^\\s*<trigger>\\s*([delims].*)?$` (DOTALL) regex expected
    by parse_positional_command(). `trigger_pattern` is a raw regex for the
    trigger words only (e.g. r"ליד\\s+חדש\\b") — NOT the whole line."""
    delim_class = re.escape(delimiters)
    return re.compile(rf"^\s*{trigger_pattern}\s*([{delim_class}].*)?$", re.DOTALL)


def parse_positional_command(text: str, trigger_re: re.Pattern) -> Optional[dict]:
    """
    Parses `<trigger>` optionally followed by one delimiter (whichever of
    the delimiters the trigger_re was built with) and delimiter-split field
    values. Delimiter is detected from the match, not hardcoded, so a caller
    can accept e.g. both "|" and "/" without preferring one.

    Returns:
      None              — text doesn't match the trigger at all (caller
                           should fall through to its own non-structured
                           handling, e.g. free-text/NLP capture).
      {"prompt": True}  — trigger matched, no fields after it yet.
      {"parts": [...]}  — trigger matched; parts are the stripped,
                           delimiter-split field values. Caller maps
                           positional parts -> field names and validates —
                           this function has no concept of field semantics.
    """
    if not text:
        return None
    m = trigger_re.match(text.strip())
    if not m:
        return None

    matched = m.group(1) or ""
    if not matched:
        return {"prompt": True}

    delimiter = matched[0]
    rest = matched[1:].strip()
    if not rest:
        return {"prompt": True}

    return {"parts": [p.strip() for p in rest.split(delimiter)]}


def demo() -> None:
    trig = build_structured_trigger_re(r"ליד\s+חדש\b")

    assert parse_positional_command("שלום", trig) is None
    assert parse_positional_command("ליד חדש", trig) == {"prompt": True}
    assert parse_positional_command("ליד חדש   ", trig) == {"prompt": True}
    assert parse_positional_command("ליד חדש משה", trig) is None  # no delimiter -> not this format

    r1 = parse_positional_command("ליד חדש | משה | 0501234567 | recruitment", trig)
    assert r1 == {"parts": ["משה", "0501234567", "recruitment"]}

    r2 = parse_positional_command("ליד חדש/משה/0501234567/recruitment/הערה", trig)
    assert r2 == {"parts": ["משה", "0501234567", "recruitment", "הערה"]}

    # mixed delimiters within one command are NOT re-split — "/" stays part of the value once "|" is the detected delimiter
    r3 = parse_positional_command("ליד חדש | משה/כהן | 0501234567", trig)
    assert r3 == {"parts": ["משה/כהן", "0501234567"]}

    print("core/structured_command.py: all demo() assertions passed")


if __name__ == "__main__":
    demo()
