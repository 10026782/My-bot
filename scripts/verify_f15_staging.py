#!/usr/bin/env python3
"""Bounded, staging-only F15 runtime verifier.

This script performs one disposable CRM create/update pass per supported entity,
captures canonical gateway audit events, and deletes only record IDs returned by
those creates. It never retries a write and never guesses an ID after an
uncertain provider result.

Required environment:
  F15_STAGING_NON_PRODUCTION=true
  F15_STAGING_ENVIRONMENT=staging
  AIRTABLE_API_KEY=<staging key>
  AIRTABLE_BASE_ID=<staging base>
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import uuid
from datetime import date, timedelta, timezone, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"f15-{stamp}-{uuid.uuid4().hex[:10]}"


def _preflight() -> list[str]:
    errors = []
    if os.environ.get("F15_STAGING_NON_PRODUCTION", "").lower() != "true":
        errors.append("F15_STAGING_NON_PRODUCTION=true is required")
    if os.environ.get("F15_STAGING_ENVIRONMENT", "").lower() != "staging":
        errors.append("F15_STAGING_ENVIRONMENT=staging is required")
    if not os.environ.get("AIRTABLE_API_KEY"):
        errors.append("AIRTABLE_API_KEY is missing")
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    expected_base = os.environ.get("F15_STAGING_BASE_ID", base_id)
    if not base_id or base_id != expected_base:
        errors.append("AIRTABLE_BASE_ID does not match F15_STAGING_BASE_ID")
    for key in ("FLASK_ENV", "APP_ENV", "ENVIRONMENT"):
        if os.environ.get(key, "").lower() == "production":
            errors.append(f"{key}=production is forbidden")
    return errors


class _GatewayAudit(logging.Handler):
    _pattern = re.compile(
        r"source=(?P<source>\S+) op=(?P<op>\S+) table=(?P<table>.*?) "
        r"record=(?P<record>\S+) keys=.* ok=(?P<ok>True|False)$"
    )

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.events: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if "[AUDIT:gateway]" not in message:
            return
        match = self._pattern.search(message)
        if match:
            event = match.groupdict()
            event["ok"] = event["ok"] == "True"
            self.events.append(event)


def _record_id(result) -> str:
    return str(getattr(result, "record_id", "") or "")


def _text_record_id(result: str) -> str:
    match = re.search(r"ID:\s*`([^`]+)`", result or "")
    return match.group(1) if match else ""


def _operation(run: dict, operation: str, table: str, **values) -> dict:
    item = {"operation": operation, "table": table, **values}
    run["operations"].append(item)
    return item


def _gate(run: dict, gate_id: str, passed: bool, evidence: str) -> None:
    run["gates"].append({"gate": gate_id, "status": "PASS" if passed else "FAIL", "evidence": evidence})


def _audit_for(handler: _GatewayAudit, start: int, *, op: str, table: str) -> list[dict]:
    return [
        event for event in handler.events[start:]
        if event["source"] == "crm" and event["op"] == op and event["table"] == table
    ]


def _fetch_by_id(at_list_by_formula, table: str, record_id: str) -> dict | None:
    safe_id = record_id.replace("'", "\\'")
    records = at_list_by_formula(table, f"RECORD_ID()='{safe_id}'", max_records=2)
    return records[0] if len(records) == 1 else None


def _assert_unique(at_list_by_formula, table: str, field: str, value: str) -> int:
    safe = value.replace("'", "\\'")
    return len(at_list_by_formula(table, f"{{{field}}}='{safe}'", max_records=10))


def _cleanup(run: dict, airtable_delete) -> None:
    for item in run["created_records"]:
        try:
            ok = airtable_delete(item["table"], item["record_id"], source="f15_staging_verifier")
            item["cleanup"] = "PASS" if ok else "FAIL"
        except Exception as exc:  # cleanup evidence must survive one failure
            item["cleanup"] = "FAIL"
            item["cleanup_error"] = f"{type(exc).__name__}: {exc}"
    _gate(
        run,
        "cleanup_owned_records",
        all(r.get("cleanup") == "PASS" for r in run["created_records"]),
        json.dumps(run["created_records"], ensure_ascii=False) if run["created_records"] else "no records created",
    )


def verify() -> dict:
    run = {
        "run_id": _run_id(),
        "environment": "staging",
        "operations": [],
        "created_records": [],
        "gates": [],
    }
    preflight_errors = _preflight()
    _gate(run, "staging_preflight", not preflight_errors, "; ".join(preflight_errors) or "explicit non-production staging configuration present")
    if preflight_errors:
        run["verdict"] = "F15 — STAGING VERIFICATION FAILED"
        return run

    from airtable_schema import ContactFields, DealFields, PaymentFields, Tables
    import crm
    from tools import airtable_gateway

    audit = _GatewayAudit()
    gateway_logger = logging.getLogger("tools.airtable_gateway")
    old_level = gateway_logger.level
    gateway_logger.setLevel(logging.INFO)
    gateway_logger.addHandler(audit)
    try:
        # Read-only table reachability preflight through the canonical gateway.
        for table in (Tables.CONTACTS, Tables.DEALS, Tables.PAYMENTS):
            airtable_gateway.at_list_by_formula(table, "FALSE()", max_records=1)
        _gate(run, "gateway_table_preflight", True, "Contacts, Deals, Payments reachable through gateway reads")

        # Contact create + duplicate check + update. crm_add_contact delegates to
        # find_or_create_contact, which is the F14 deduplication authority.
        phone_suffix = str(uuid.uuid4().int % 1_000_000).zfill(6)
        phone = f"+972599{phone_suffix}"
        name = f"F15 staging {run['run_id']}"
        if _assert_unique(airtable_gateway.at_list_by_formula, Tables.CONTACTS, ContactFields.PHONE, phone):
            raise RuntimeError("unique Contact phone was already present before the run")
        audit_start = len(audit.events)
        contact_result = crm.crm_add_contact(name=name, phone=phone, notes=run["run_id"])
        contact_id = _record_id(contact_result)
        contact_create_audit = _audit_for(audit, audit_start, op="create", table=Tables.CONTACTS)
        contact_op = _operation(run, "contact_create", Tables.CONTACTS, record_id=contact_id, result=repr(contact_result), gateway_result=contact_create_audit)
        _gate(run, "contact_create_id", bool(contact_id), f"result={contact_op['result']}")
        _gate(run, "contact_create_gateway", len(contact_create_audit) == 1 and contact_create_audit[0]["ok"] and contact_create_audit[0]["record"] == contact_id, json.dumps(contact_create_audit, ensure_ascii=False))
        if contact_id:
            run["created_records"].append({"entity": "Contact", "table": Tables.CONTACTS, "record_id": contact_id})
            duplicate_count = _assert_unique(airtable_gateway.at_list_by_formula, Tables.CONTACTS, ContactFields.PHONE, phone)
            duplicate_result = crm.crm_add_contact(name=name, phone=phone, notes=run["run_id"])
            duplicate_op = _operation(run, "contact_duplicate_check", Tables.CONTACTS, record_id=_record_id(duplicate_result), result=repr(duplicate_result), duplicate_count=duplicate_count)
            _gate(run, "contact_gate_no_duplicate", duplicate_count == 1 and getattr(duplicate_result, "status", "") == "existing" and len(_audit_for(audit, audit_start, op="create", table=Tables.CONTACTS)) == 1, json.dumps(duplicate_op, ensure_ascii=False))

            audit_start = len(audit.events)
            update_result = crm.crm_update_last_contact(contact_id)
            update_audit = _audit_for(audit, audit_start, op="patch", table=Tables.CONTACTS)
            updated = _fetch_by_id(airtable_gateway.at_list_by_formula, Tables.CONTACTS, contact_id)
            update_op = _operation(run, "contact_update", Tables.CONTACTS, record_id=contact_id, result=update_result, gateway_result=update_audit, record_after_update=updated)
            _gate(run, "contact_update_same_id", len(update_audit) == 1 and update_audit[0]["ok"] and update_audit[0]["record"] == contact_id, json.dumps(update_op, ensure_ascii=False, default=str))

        # Deal and Payment paths are current CRM APIs; both use the same shims.
        deal_name = f"F15 staging deal {run['run_id']}"
        if _assert_unique(airtable_gateway.at_list_by_formula, Tables.DEALS, DealFields.NAME, deal_name):
            raise RuntimeError("unique Deal name was already present before the run")
        deal_result = crm.crm_add_deal(deal_name, "F15 staging", 1, 1)
        deal_id = _text_record_id(deal_result)
        deal_audit = _audit_for(audit, audit_start, op="create", table=Tables.DEALS)
        _operation(run, "deal_create", Tables.DEALS, record_id=deal_id, result=deal_result, gateway_result=deal_audit)
        _gate(run, "deal_create_gateway", bool(deal_id) and len(deal_audit) == 1 and deal_audit[0]["ok"] and deal_audit[0]["record"] == deal_id, json.dumps(deal_audit, ensure_ascii=False))
        if deal_id:
            run["created_records"].append({"entity": "Deal", "table": Tables.DEALS, "record_id": deal_id})
            audit_start = len(audit.events)
            deal_update_result = crm.crm_update_deal_status(deal_id, "Active", run["run_id"])
            deal_update_audit = _audit_for(audit, audit_start, op="patch", table=Tables.DEALS)
            deal_after = _fetch_by_id(airtable_gateway.at_list_by_formula, Tables.DEALS, deal_id)
            _operation(run, "deal_update", Tables.DEALS, record_id=deal_id, result=deal_update_result, gateway_result=deal_update_audit, record_after_update=deal_after)
            _gate(run, "deal_update_same_id", len(deal_update_audit) == 1 and deal_update_audit[0]["ok"] and deal_update_audit[0]["record"] == deal_id and (deal_after or {}).get("fields", {}).get(DealFields.STATUS) == "Active", json.dumps(deal_update_audit, ensure_ascii=False))

        payment_name = f"F15 staging payment {run['run_id']}"
        if _assert_unique(airtable_gateway.at_list_by_formula, Tables.PAYMENTS, PaymentFields.NAME, payment_name):
            raise RuntimeError("unique Payment reference was already present before the run")
        payment_result = crm.crm_add_payment(payment_name, 1, (date.today() + timedelta(days=7)).isoformat())
        payment_id = _text_record_id(payment_result)
        payment_audit = _audit_for(audit, audit_start, op="create", table=Tables.PAYMENTS)
        _operation(run, "payment_create", Tables.PAYMENTS, record_id=payment_id, result=payment_result, gateway_result=payment_audit)
        _gate(run, "payment_create_gateway", bool(payment_id) and len(payment_audit) == 1 and payment_audit[0]["ok"] and payment_audit[0]["record"] == payment_id, json.dumps(payment_audit, ensure_ascii=False))
        if payment_id:
            run["created_records"].append({"entity": "Payment", "table": Tables.PAYMENTS, "record_id": payment_id})
            audit_start = len(audit.events)
            payment_update_result = crm.crm_mark_payment_paid(payment_id)
            payment_update_audit = _audit_for(audit, audit_start, op="patch", table=Tables.PAYMENTS)
            payment_after = _fetch_by_id(airtable_gateway.at_list_by_formula, Tables.PAYMENTS, payment_id)
            _operation(run, "payment_update", Tables.PAYMENTS, record_id=payment_id, result=payment_update_result, gateway_result=payment_update_audit, record_after_update=payment_after)
            _gate(run, "payment_update_same_id", len(payment_update_audit) == 1 and payment_update_audit[0]["ok"] and payment_update_audit[0]["record"] == payment_id, json.dumps(payment_update_audit, ensure_ascii=False))

        source = (REPO_ROOT / "crm.py").read_text(encoding="utf-8")
        direct_http_write = re.search(r"\bhttpx\.(post|patch)\s*\(", source)
        _gate(run, "crm_static_no_direct_http_writes", direct_http_write is None, "crm.py contains no direct httpx.post()/httpx.patch()")
        _gate(run, "f14_gate_path", bool(contact_id) and any(op["operation"] == "contact_duplicate_check" for op in run["operations"]), "Contact create and duplicate check used crm_add_contact/find_or_create_contact")
    except Exception as exc:
        run["exception"] = f"{type(exc).__name__}: {exc}"
        _gate(run, "runtime_execution", False, run["exception"])
    finally:
        _cleanup(run, airtable_gateway.airtable_delete)
        gateway_logger.removeHandler(audit)
        gateway_logger.setLevel(old_level)

    run["verdict"] = "F15 — COMPLETE AND STAGING VERIFIED" if all(g["status"] == "PASS" for g in run["gates"]) else "F15 — STAGING VERIFICATION FAILED"
    return run


def main() -> int:
    report = verify()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(report["verdict"])
    return 0 if report["verdict"] == "F15 — COMPLETE AND STAGING VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

