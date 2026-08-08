"""Bounded, side-effect-free task reference resolution.

TC5 generalized this module's original bounded-resolve implementation into
``core/router/entity_resolvers.py``'s shared framework. ``TaskLookup`` and
``resolve_task`` are re-exported here unchanged so existing callers/tests do
not need to change their import path or observe any behavior difference.
"""

from __future__ import annotations

from core.router.entity_resolvers import TaskLookup, resolve_task

__all__ = ["TaskLookup", "resolve_task"]
