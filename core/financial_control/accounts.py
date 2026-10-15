"""FCC financial accounts — pure, read-only read model (D1 step 5). No I/O, no writes, NOT wired to any route or screen.

Facts vs estimates (FAMILY_WEALTH_ACCOUNTS_SPEC §5):
* a balance is a dated ``balance_snapshot`` event; the account value is its latest valid (not superseded) snapshot;
* the consolidated value is the sum of those snapshots only — deposits / withdrawals / fees / transfers NEVER change it;
* the movements after the snapshot are reported separately and give a clearly marked ESTIMATE, never added to the fact;
* a transfer is one event (Account -> Counter Account): it nets to zero across accounts and is never a deposit or a withdrawal;
* an account without a snapshot has no value (None, never 0) and is counted, not silently dropped.
Free-text ``Notes`` / ``Tax Notes`` are deliberately not part of the output.
"""

from __future__ import annotations

from datetime import date

from airtable_schema import FinAccountFields as AF
from airtable_schema import FinEventFields as EF
from core.financial_control import calc

DEPOSIT, WITHDRAWAL, FEE, TRANSFER, SNAPSHOT = "deposit", "withdrawal", "fee", "transfer", "balance_snapshot"
ACCOUNT_KINDS = (DEPOSIT, WITHDRAWAL, FEE, TRANSFER, SNAPSHOT)      # deliberately NOT in calc.EVENT_KINDS
DEFAULT_VERIFICATION = "self_reported"


def _sel(value):
    return value.get("name") if isinstance(value, dict) else value


def _ids(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [v for v in value if isinstance(v, str)] if isinstance(value, (list, tuple)) else []


def _event(record: dict) -> dict | None:
    """A well-formed account event, else None (malformed rows are skipped, never guessed)."""
    f = (record or {}).get("fields") or {}
    kind = _sel(f.get(EF.KIND))
    amount, day = calc._num(f.get(EF.AMOUNT)), calc._d(f.get(EF.OCCURRED_AT))
    accounts = _ids(f.get(EF.ACCOUNT))
    if kind not in ACCOUNT_KINDS or amount is None or day is None or len(accounts) != 1 or f.get(EF.SUPERSEDED_BY):
        return None
    if amount < 0 or (kind != SNAPSHOT and amount == 0):            # amounts are positive; the Kind carries the direction
        return None
    counter = _ids(f.get(EF.COUNTER_ACCOUNT))
    if kind == TRANSFER and (len(counter) != 1 or counter[0] == accounts[0]):
        return None
    return {"id": (record or {}).get("id"), "kind": kind, "amount": amount, "day": day, "account": accounts[0],
            "counter": counter[0] if kind == TRANSFER else None,
            "verification": _sel(f.get(EF.VERIFICATION)) or DEFAULT_VERIFICATION}


def _signed_effect(ev: dict, account_id: str) -> float:
    if ev["kind"] == DEPOSIT:
        return ev["amount"]
    if ev["kind"] in (WITHDRAWAL, FEE):
        return -ev["amount"]
    if ev["kind"] == TRANSFER:
        return -ev["amount"] if ev["account"] == account_id else ev["amount"]
    return 0.0


def _owned(fields: dict, owner_id: str | None, owner_field: str) -> bool:
    return owner_id is None or owner_id in _ids((fields or {}).get(owner_field))


def accounts_overview(accounts: list[dict], events: list[dict], today: date, owner_id: str | None = None) -> dict:
    """Read model over owner-scoped rows. ``owner_id`` (Profile record id) is defence in depth on top of the access policy:
    when given, accounts and events of anyone else are ignored even if the caller passed them in."""
    mine = [a for a in accounts or [] if _owned((a or {}).get("fields"), owner_id, AF.FINANCIAL_OWNER)]
    known = {a.get("id") for a in mine if a.get("id")}
    evs, skipped = [], 0
    for rec in events or []:
        if not _owned((rec or {}).get("fields"), owner_id, EF.FINANCIAL_OWNER):
            continue
        kind = _sel(((rec or {}).get("fields") or {}).get(EF.KIND))
        if kind not in ACCOUNT_KINDS:
            continue                                                 # goal events and unknown kinds are none of our business
        ev = _event(rec)
        if ev is None or ev["account"] not in known or (ev["counter"] and ev["counter"] not in known):
            skipped += 1
            continue
        evs.append(ev)
    rows = []
    for acc in mine:
        aid, f = acc.get("id"), acc.get("fields") or {}
        mine_evs = [e for e in evs if aid in (e["account"], e["counter"])]
        snaps = sorted((e for e in mine_evs if e["kind"] == SNAPSHOT and e["account"] == aid and e["day"] <= today),
                       key=lambda e: (e["day"], str(e["id"])))
        last = snaps[-1] if snaps else None
        after = [e for e in mine_evs if e["kind"] != SNAPSHOT and last and last["day"] < e["day"] <= today]   # same-day: ambiguous, excluded
        moved = round(sum(_signed_effect(e, aid) for e in after), 2) if last else None
        rows.append({
            "id": aid, "name": f.get(AF.NAME) or None, "account_type": _sel(f.get(AF.ACCOUNT_TYPE)),
            "institution": f.get(AF.INSTITUTION) or None, "holder_names": f.get(AF.HOLDER_NAMES) or None,
            "status": _sel(f.get(AF.STATUS)), "liquidity": _sel(f.get(AF.LIQUIDITY)),
            "liquid_from": f.get(AF.LIQUID_FROM) or None, "tax_treatment": _sel(f.get(AF.TAX_TREATMENT)),
            "management_fee_pct": calc._num(f.get(AF.MANAGEMENT_FEE)),
            "balance": None if last is None else {
                "value": last["amount"], "as_of": last["day"].isoformat(), "verification": last["verification"],
                "estimate": {"value": round(last["amount"] + moved, 2), "movements_since": moved, "movement_count": len(after),
                             "label": "estimate"},
            },
        })
    active = [r for r in rows if r["status"] != "closed"]
    with_value = [r for r in active if r["balance"]]
    totals = {
        "consolidated_value": round(sum(r["balance"]["value"] for r in with_value), 2) if with_value else None,
        "estimated_value": round(sum(r["balance"]["estimate"]["value"] for r in with_value), 2) if with_value else None,
        "accounts_with_value": len(with_value),
        "accounts_without_snapshot": len(active) - len(with_value),
        "closed_accounts": len(rows) - len(active),
        "oldest_snapshot": min((r["balance"]["as_of"] for r in with_value), default=None),
        "all_self_reported": all(r["balance"]["verification"] == DEFAULT_VERIFICATION for r in with_value) if with_value else None,
    }
    return {"accounts": rows, "totals": totals, "skipped_events": skipped, "as_of": today.isoformat()}
