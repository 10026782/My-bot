# BusinessDraft Phase 4B — Deal generic-update runtime evidence

- Observed: 23/09/2026, Asia/Jerusalem, live Render production (`my-bot-jqz2.onrender.com`).
- Deployed SHA: `507e12b3` (PR #1262 merge commit).
- Method: real Telegram owner session, read directly from Render application logs
  (not a staging harness, not a mock). No record was created for this evidence
  capture beyond the one real Deal update described below.
- Trigger: `_handle_deal_enrichment_reply()`'s `_finish()` (app.py) — the
  post-Deal-creation optional-enrichment loop, which has always called the
  generic `airtable_update` tool on the `עסקאות (Deals)` table directly from
  Python (never a model tool_use decision). This is the exact code path
  `PHASE4B_SHARED_COMMERCIAL_GENERIC_BYPASS_PENDING` named as open for Deal.

## What the logs show, in call order

1. **Canonicalization before proposal** — `ActionGateway.propose_action()` is
   invoked with `tool_name=crm_update_deal` (not `airtable_update`), status
   `pending`, before any ActionContract exists:
   ```
   propose_action: contract=6f11e377-ace3-49ee-8a41-5da78bef9aaf
   fingerprint=36ce498bd719 tool=crm_update_deal ... status=pending
   ```
2. **Canonical primitive payload stored, not the generic envelope** — the
   approved contract's `payload_keys` are `commercial_crm.update_deal()`'s
   own kwarg names, never `table`/`fields`:
   ```
   approved: ... tool=crm_update_deal
   payload_keys=['business_deal_type', 'commercial_status', 'currency',
   'engagement_duration', 'estimated_value_basis', 'estimated_value_notes',
   'estimated_value_range', 'record_id', 'relationship_role']
   ```
3. **Dispatch reached the dedicated `crm_update_deal` case directly** — never
   the `airtable_update` → `_CRM_TABLE_ROUTING` compatibility redirect:
   ```
   Dispatch] crm_update_deal | tenant=boss_hq user=eliyahu |
   inputs={'business_deal_type': 'מכירה', 'commercial_status': 'prospect', ...}
   ```
4. **Golden Writer performed the real write**, translating canonical kwargs
   back to live Airtable column names:
   ```
   op=patch table=עסקאות (Deals) record=recFi9Vpdxv2DTuIg
   keys=['סוג העסקה העסקי', 'אופי הקשר העסקי', 'משך ההתקשרות', 'Currency',
   'Commercial Status', 'אופן הערכת שווי', 'טווח שווי משוער', 'הערות לשווי משוער']
   ok=True
   ```
5. **Verified end to end**:
   ```
   executed: ... tool=crm_update_deal external_id=recFi9Vpdxv2DTuIg
   [core.turn_evidence] evidence_status=verified_write_success verified_writes=1
   [app] [Approval] ✅ confirmed 6cc7c5d5 | crm_update_deal
   ```
6. **The user-facing approval text was business-readable**, e.g. "עדכון פרטי
   עסקה: • סוג עסקה: מכירה • סטטוס מסחרי: פוטנציאלית ..." — no raw tool name,
   no `record_id`, no raw `rec...` id anywhere in it (matches the Deal UX
   parity fix in commit `77bd5ce1`).
7. **No Agent/LLM tool-use turn occurred for this write** — the same log
   sequence includes `agent_calls=0` on the `[DealEnrichment]` summary line:
   ```
   [DealEnrichment] agent_calls=0 action_tool=crm_update_deal
   created_this_turn=True reply_owner=gateway
   ```
   (The unrelated `source=agent` string appearing in `tools.airtable_security`
   audit lines is a hardcoded literal in `tools/dispatcher.py`'s
   `crm_update_deal` case — `commercial_crm.update_deal(..., source="agent")`
   — pre-existing, unrelated audit metadata, not an LLM-loop indicator.)

## Scope of this evidence

Confirms **RUNTIME_VERIFIED** for: Deal generic `airtable_update` →
`crm_update_deal` canonicalization, canonical payload/fingerprint shape,
dispatcher routing to the dedicated writer, and UX parity — in live production,
on deployed SHA `507e12b3`.

Does **not** cover (still `STATIC_VERIFIED` only, per
`test_business_draft_phase4b_generic_bypass.py`'s 223 checks against the same
shared `core/commercial_generic_canonicalization.py` module): Deal generic
CREATE, Payment Term generic CREATE/UPDATE, Payment generic CREATE/UPDATE, the
legacy-Payment-shape fail-closed block, and role-authorization denial for a
generic call on these tables.
