# core/emergency_stop.py — PATCH 3B Step 1
#
# Pure core: types, the EmergencyStopStore Protocol, and EmergencyStopManager
# (cache + TTL + precedence). Deliberately contains:
#   - no import of feature_flags
#   - no os.environ reads
#   - no Flask
#   - no scheduler
#   - no Airtable/tools.airtable_gateway
#   - no adapters
#   - no network or file I/O
#
# time.monotonic is used only as the *default* clock value (a pure in-memory
# counter read, not I/O) — always injectable for deterministic tests.
#
# Force-stop (e.g. an env var) is never read here. The manager only knows
# about it through an injected `force_stop_provider(flag_name) -> bool`
# callable — the concrete provider (reading os.environ) is wired in by the
# caller (feature_flags.py), not this module.
#
# Concrete durable storage (Airtable) is a separate adapter implementing
# EmergencyStopStore — nothing here knows Airtable exists.

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal, Optional, Protocol

StoreStatus = Literal["ok", "unavailable", "invalid"]
EffectiveSource = Literal["env", "durable", "cache", "unknown"]

Clock = Callable[[], float]
ForceStopProvider = Callable[[str], bool]


# ══════════════════════════════════════════════════
# Canonical known-flag-name set (Step 2.5 hardening)
# ══════════════════════════════════════════════════
#
# The concrete set of Emergency Stop flag names this system currently
# governs. Defined once, here, so both EmergencyStopManager and any
# EmergencyStopStore adapter (e.g. adapters/airtable_emergency_stop_store.py)
# share one source of truth without an adapter needing to import
# feature_flags.py (still forbidden — see module header above). feature_flags.py
# is expected to import THIS constant once it's wired in (Step 3+), not
# duplicate the literal list.
#
# known_flag_names is never allowed to be empty (see EmergencyStopManager.__init__
# and AirtableEmergencyStopStore.__init__) — an empty set would silently make
# status()'s health snapshot report nothing, and would silently skip the
# adapter's missing-record integrity check entirely. Using this as the
# default means "caller forgot to pass known_flag_names" fails safe (falls
# back to the real 5) instead of failing open (silently accepting an empty
# set as if that were a deliberate, valid choice).
KNOWN_EMERGENCY_STOP_FLAG_NAMES: frozenset[str] = frozenset({
    "EMERGENCY_STOP_ALL",
    "EMERGENCY_STOP_WHATSAPP",
    "EMERGENCY_STOP_EMAIL",
    "EMERGENCY_STOP_AUTOMATION",
    "EMERGENCY_STOP_AI",
})


# ══════════════════════════════════════════════════
# Structured results — no bare bool return anywhere in this module's
# public API. Every answer carries provenance (source/store_status/
# cache_age) so a caller can tell "configured true" apart from
# "we don't actually know" without a second round trip.
# ══════════════════════════════════════════════════

@dataclass(frozen=True)
class FlagRecord:
    """One flag's durable state as read from the store (PATCH 3B Step 6).

    operation_id is the durable record's current Operation ID — the same
    value a caller must pass back as expected_operation_id on a subsequent
    write() to detect a conflicting change (see EmergencyStopStore.write's
    docstring). None when the store never populates it (e.g. a flag that
    was never written yet) — a caller must treat that as "no known
    operation_id to condition a write on", not as an error.
    """
    enabled: bool
    operation_id: Optional[str] = None


@dataclass(frozen=True)
class ReadResult:
    """Outcome of one attempt to read the full durable flag set.

    status:
      "ok"          — flags is populated; the store's answer is trustworthy.
      "unavailable" — transient failure (network/HTTP/timeout). flags is None.
      "invalid"     — the store responded but the data itself is malformed
                       (e.g. duplicate/missing flag records, bad Enabled
                       value) — a data-integrity problem, not a network one.
                       flags is None.

    Only "ok" may ever be used by the manager to replace its cache.
    """
    status: StoreStatus
    flags: Optional[dict[str, FlagRecord]] = None
    error: str = ""


@dataclass(frozen=True)
class WriteResult:
    """Outcome of one attempt to write a single flag's durable state.

    ok:       the write call itself succeeded (no transport/HTTP error).
    verified: a readback after the write confirmed the new state actually
              took effect. A caller must never treat ok=True, verified=False
              as success — the write may not have stuck.
    conflict: True when the store was given an `expected_operation_id` (see
              EmergencyStopStore.write) that did not match the record's
              current Operation ID at write time — i.e. someone else changed
              the flag between the caller's last observation and this write.
              The write was rejected, not attempted.
    """
    ok: bool
    verified: bool
    conflict: bool = False
    error: str = ""


class EmergencyStopStore(Protocol):
    """Port for durable emergency-stop storage. No implementation lives in
    this module — see adapters/airtable_emergency_stop_store.py (Step 2).

    Contract: both methods must NEVER raise. Any underlying failure
    (network, HTTP, parsing) must be caught by the implementation and
    reported as ReadResult(status="unavailable"/"invalid", ...) or
    WriteResult(ok=False, ...) instead. EmergencyStopManager additionally
    guards against a misbehaving implementation that raises anyway (see
    _safe_read), but implementations must not rely on that guard.
    """

    def read(self) -> ReadResult:
        """Read the full current durable flag set in one call."""
        ...

    def write(
        self,
        flag_name: str,
        enabled: bool,
        *,
        operation_id: str,
        updated_by: str,
        source: str,
        reason: str,
        expected_operation_id: Optional[str] = None,
    ) -> WriteResult:
        """Create-or-update a single flag's durable record.

        If expected_operation_id is given, the implementation must read the
        record's current Operation ID first and reject (WriteResult with
        conflict=True, ok=False) rather than write if it doesn't match.
        This narrows — but, in the absence of an atomic compare-and-set
        primitive in Airtable, does not eliminate — the race between a
        caller's last observation and this write (documented TOCTOU,
        matching tools/airtable_gateway.py::at_upsert()'s own disclosure of
        the same limitation).
        """
        ...


# ══════════════════════════════════════════════════
# Evaluation results
# ══════════════════════════════════════════════════

@dataclass(frozen=True)
class FlagEvaluation:
    """The manager's answer for one flag at one point in time.

    operation_id (Step 6): the durable record's Operation ID as of the last
    successful hydrate, when this evaluation came from the cache/durable
    source. None for source="env" (env force-stop never consults the store)
    and source="unknown" (never successfully hydrated) — there is no
    durable record to attribute an operation_id to in either case.
    """
    flag_name: str
    blocked: bool
    source: EffectiveSource
    store_status: Optional[StoreStatus]
    last_hydrated_at: Optional[float]
    cache_age_seconds: Optional[float]
    operation_id: Optional[str] = None
    error: str = ""


@dataclass(frozen=True)
class ManagerStatus:
    """Observability snapshot — for a health endpoint, not for gating logic."""
    store_configured: bool
    store_status: Optional[StoreStatus]
    last_hydrated_at: Optional[float]
    cache_age_seconds: Optional[float]
    flags: dict[str, FlagEvaluation] = field(default_factory=dict)
    error: str = ""


# ══════════════════════════════════════════════════
# Manager
# ══════════════════════════════════════════════════

class EmergencyStopManager:
    """
    Read-path was the only thing implemented in Step 1; write() (durable
    pass-through, Step 3/PATCH 3B) was added once feature_flags.py's
    set_emergency_stop()/clear_emergency_stop() needed something concrete to
    delegate to — see write()'s own docstring for its cache semantics.

    Precedence per evaluate(flag_name):
      1. force_stop_provider(flag_name) is True  -> blocked=True, source="env".
         Always wins; never consults the store or the cache.
      2. Cache holds a value for flag_name:
         - fresh (age <= ttl_seconds since last successful hydrate)
              -> source="durable" (an accurate reflection of durable state).
         - stale (durable hasn't refreshed successfully within ttl_seconds)
              -> source="cache" (last-known-good, serving as a fallback).
         Either way blocked = the cached boolean.
      3. No cached value for flag_name at all (never successfully hydrated,
         or this flag never appeared in a successful read)
              -> source="unknown", blocked=True (fail-closed).

    A stale cache triggers exactly one refresh attempt per staleness window
    even under concurrent callers (single-flight): the first caller to
    notice staleness acquires the manager's lock and performs the refresh
    while holding it; concurrent callers block on the same lock and, once
    it's released, re-check staleness (double-checked) rather than
    refreshing again themselves.

    Thread safety: a single lock guards all cache state (including during
    the store.read() call itself) — reads are not lock-free, but the
    critical section is only ever entered when the cache is actually stale,
    which is bounded by ttl_seconds under normal operation.
    """

    def __init__(
        self,
        store: Optional[EmergencyStopStore] = None,
        *,
        clock: Clock = time.monotonic,
        force_stop_provider: Optional[ForceStopProvider] = None,
        ttl_seconds: float = 7.0,
        known_flag_names: Iterable[str] = KNOWN_EMERGENCY_STOP_FLAG_NAMES,
    ) -> None:
        self._store = store
        self._clock = clock
        self._force_stop_provider = force_stop_provider
        self._ttl_seconds = ttl_seconds
        self._known_flag_names = frozenset(known_flag_names)
        if not self._known_flag_names:
            # Default is always non-empty (KNOWN_EMERGENCY_STOP_FLAG_NAMES) — the
            # only way to land here is an explicit empty override, which is never
            # a valid configuration (see the constant's docstring above).
            raise ValueError(
                "known_flag_names must not be empty — omit the argument to use "
                "KNOWN_EMERGENCY_STOP_FLAG_NAMES, the canonical default."
            )

        self._lock = threading.Lock()
        self._cache: dict[str, FlagRecord] = {}
        self._last_hydrated_at: Optional[float] = None
        self._last_store_status: Optional[StoreStatus] = None
        self._last_error: str = ""

    # ── configuration (still no I/O — just swaps the reference) ──────

    def configure(self, store: EmergencyStopStore) -> None:
        """Inject/replace the store after construction. Does not itself
        trigger a read — the next evaluate()/status() call will (cache
        starts/stays stale until then). Bootstrap timing is the caller's
        responsibility (see Step 2/4 discussion)."""
        with self._lock:
            self._store = store

    # ── public read API ───────────────────────────────────────────────

    def evaluate(self, flag_name: str) -> FlagEvaluation:
        with self._lock:
            self._maybe_refresh_locked()
            return self._evaluate_locked(flag_name)

    def write(
        self,
        flag_name: str,
        enabled: bool,
        *,
        operation_id: str,
        updated_by: str,
        source: str,
        reason: str,
        expected_operation_id: Optional[str] = None,
    ) -> WriteResult:
        """Durable write pass-through to the configured store (Step 3).

        Deliberately does NOT hydrate the cache with (flag_name, enabled) on
        a successful write — only a verified "ok" read() may ever populate
        the cache (see class docstring / _maybe_refresh_locked). Instead, on
        ANY write attempt — success, failure, or conflict — the cache is
        marked stale so the next evaluate()/status() call performs a fresh,
        verified read instead of trusting a value nobody has independently
        confirmed durably stuck.

        The store.write() call itself happens OUTSIDE the manager's lock.
        This is unlike _maybe_refresh_locked()'s deliberate single-flight
        read, where holding the lock across store.read() is the entire
        point (dedupe concurrent refreshes) — serializing every write behind
        the same lock that guards cache reads would instead stall every
        concurrent evaluate()/status() call for as long as the durable write
        takes, which is not a tradeoff single-flight read was ever meant to
        impose on the write path.

        Returns WriteResult(ok=False, verified=False, ...) if no store is
        configured — this method does not raise for that case (evaluate()/
        status() also degrade gracefully rather than raise; write() matches
        that convention rather than being the one method on this class that
        can throw).
        """
        with self._lock:
            store = self._store
        if store is None:
            return WriteResult(ok=False, verified=False, error="no store configured")

        result = self._safe_write(
            store, flag_name, enabled,
            operation_id=operation_id, updated_by=updated_by,
            source=source, reason=reason,
            expected_operation_id=expected_operation_id,
        )

        with self._lock:
            # Force the next read to be fresh regardless of outcome — never
            # keep serving a cached value from before a write we just
            # attempted (and may or may not have actually stuck).
            self._last_hydrated_at = None

        return result

    def status(self) -> ManagerStatus:
        with self._lock:
            self._maybe_refresh_locked()
            flags = {
                name: self._evaluate_locked(name)
                for name in self._known_flag_names
            }
            return ManagerStatus(
                store_configured=self._store is not None,
                store_status=self._last_store_status,
                last_hydrated_at=self._last_hydrated_at,
                cache_age_seconds=self._cache_age_locked(),
                flags=flags,
                error=self._last_error,
            )

    # ── internals (all assume self._lock is already held) ────────────

    def _evaluate_locked(self, flag_name: str) -> FlagEvaluation:
        if self._force_stop_provider is not None and self._force_stop_provider(flag_name):
            return FlagEvaluation(
                flag_name=flag_name,
                blocked=True,
                source="env",
                store_status=self._last_store_status,
                last_hydrated_at=self._last_hydrated_at,
                cache_age_seconds=self._cache_age_locked(),
                error=self._last_error,
            )

        if flag_name in self._cache:
            record = self._cache[flag_name]
            source: EffectiveSource = "cache" if self._is_stale_locked() else "durable"
            return FlagEvaluation(
                flag_name=flag_name,
                blocked=record.enabled,
                source=source,
                store_status=self._last_store_status,
                last_hydrated_at=self._last_hydrated_at,
                cache_age_seconds=self._cache_age_locked(),
                operation_id=record.operation_id,
                error=self._last_error,
            )

        return FlagEvaluation(
            flag_name=flag_name,
            blocked=True,  # fail-closed: never successfully hydrated (or this
                            # flag never appeared in a successful read)
            source="unknown",
            store_status=self._last_store_status,
            last_hydrated_at=self._last_hydrated_at,
            cache_age_seconds=self._cache_age_locked(),
            error=self._last_error,
        )

    def _is_stale_locked(self) -> bool:
        if self._last_hydrated_at is None:
            return True
        return (self._clock() - self._last_hydrated_at) > self._ttl_seconds

    def _cache_age_locked(self) -> Optional[float]:
        if self._last_hydrated_at is None:
            return None
        return self._clock() - self._last_hydrated_at

    def _maybe_refresh_locked(self) -> None:
        if self._store is None:
            return
        if not self._is_stale_locked():
            return
        # Double-checked within the same critical section by construction:
        # any thread that was blocked on self._lock while another thread
        # refreshed will re-run _is_stale_locked() here (via evaluate()/
        # status() calling this again) and, if it's no longer stale, skip
        # straight through without a second store call.
        result = self._safe_read_locked()
        if result.status == "ok":
            self._cache = dict(result.flags or {})
            self._last_hydrated_at = self._clock()
            self._last_store_status = "ok"
            self._last_error = ""
        else:
            # unavailable/invalid — cache and last_hydrated_at untouched
            # (stale-cache fallback); only diagnostics update.
            self._last_store_status = result.status
            self._last_error = result.error

    def _safe_read_locked(self) -> ReadResult:
        """Defensive wrapper: the Protocol contract says implementations
        must never raise, but a manager that trusts that blindly would
        crash the caller's request path on any adapter bug. Converts an
        unexpected exception into status="unavailable" instead."""
        assert self._store is not None
        try:
            return self._store.read()
        except Exception as e:  # noqa: BLE001 — deliberately broad, see docstring
            return ReadResult(status="unavailable", error=f"store.read() raised: {e}")

    @staticmethod
    def _safe_write(
        store: EmergencyStopStore,
        flag_name: str,
        enabled: bool,
        *,
        operation_id: str,
        updated_by: str,
        source: str,
        reason: str,
        expected_operation_id: Optional[str],
    ) -> WriteResult:
        """Defensive wrapper mirroring _safe_read_locked() — the Protocol
        contract says store.write() must never raise, but write() (unlike
        the read path) calls this without holding the lock, so an unguarded
        exception here would propagate straight out of write() to the
        caller. Converts an unexpected exception into a WriteResult
        instead."""
        try:
            return store.write(
                flag_name, enabled,
                operation_id=operation_id, updated_by=updated_by,
                source=source, reason=reason,
                expected_operation_id=expected_operation_id,
            )
        except Exception as e:  # noqa: BLE001 — deliberately broad, see docstring
            return WriteResult(ok=False, verified=False, error=f"store.write() raised: {e}")
