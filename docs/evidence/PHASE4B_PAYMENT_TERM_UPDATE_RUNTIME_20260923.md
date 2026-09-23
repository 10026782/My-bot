# BusinessDraft Phase 4B — Payment Term generic-update runtime evidence

- Observed: 23/09/2026, Asia/Jerusalem, live Render production (`my-bot-jqz2.onrender.com`).
- Deployed SHA: `507e12b3` (PR #1262 merge commit).
- Method: real Telegram owner session ("תעדכן ב-Airtable את שדה ההערות בתנאי
  התשלום שיצרנו עכשיו ל-'בדיקת קנוני 4B'" — a free-text request naming
  Airtable directly, deliberately phrased to give the model room to choose
  the generic `airtable_update` tool rather than a structured command),
  independently confirmed by reading the live records directly via the
  Airtable MCP connector — not from application logs, not from a chat
  transcript.

## Direct record evidence

**The `ActionContracts` record itself** (`recexXeX1nxC070vv`'s sibling
`reci6FsaG6lKhcYSS`, read live from the base):
```
contract_id: dd086c5e-ba35-4d80-b9cc-2904daabce00
tool_name: crm_update_payment_term
normalized_payload: {"notes": "בדיקת קנוני 4B", "record_id": "recZ6IkYGDOucA8Cl"}
status: completed
```
`tool_name` is the dedicated tool, never `airtable_update`; `normalized_payload`
is the canonical primitive kwarg shape, never `{"table": "Payment Terms",
"fields": {...}}` — this is the exact invariant Phase 4B's canonicalization
promises, read directly from the persisted contract, not inferred from a log
line.

**The Payment Terms record itself** (`recZ6IkYGDOucA8Cl`, read live from the
base): `Notes = "בדיקת קנוני 4B"`, linked `Deal = TEST-4B-DELETE-ME`
(`recFi9Vpdxv2DTuIg`) — the write landed correctly on the real field.

## A live-found, now-fixed messaging bug (unrelated to the write itself)

At the time of this test the completion/pending-approval text for
`crm_update_payment_term` fell through to a generic fallback ("הפעולה
המבוקשת" / "לא הצלחתי להכין תיאור ברור...") — `_safe_contract_business_
description()` and `app._describe_tool_call()` had no branch for
`crm_update_payment_term`/`crm_update_payment` at all. The underlying write
was correct throughout, as the record evidence above shows; only the
user-facing text was wrong. Fixed in this same PR (commit `207019c3`), with
regression coverage; re-verified locally against the exact live payload:
```
_describe_tool_call("crm_update_payment_term",
  {"record_id": "recZ6IkYGDOucA8Cl", "notes": "בדיקת קנוני 4B"})
-> "✏️ עדכון תנאי תשלום: בדיקת קנוני 4B"
```

## Scope of this evidence

Confirms **RUNTIME_VERIFIED** for: Payment Term generic `airtable_update` →
`crm_update_payment_term` canonicalization, canonical payload shape, and a
correct live write — in production, on deployed SHA `507e12b3`. (The
messaging-text fix itself is not yet independently runtime-verified — it has
not been redeployed since being written; only unit-tested.)

Still open: Deal generic CREATE, Payment Term generic CREATE, Payment generic
CREATE/UPDATE, the legacy-Payment fail-closed block, and role-authorization
denial for a generic call on these tables.
