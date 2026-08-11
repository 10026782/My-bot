# Domain Canonicalization — D1 inventory

Status: D1 code foundation implemented; live Airtable migration is not performed.

## Decision

`recruitment` is a first-class business domain. It is present in the existing
Leads/Lead Events contracts, ProjectsHub schema notes, lead detection and
normalization code, prompts, tenant provisioning, and focused regression tests.
It must not be silently mapped to `general`.

The canonical business vocabulary is:

`real_estate`, `import`, `media`, `saas`, `finance`, `recruitment`, `general`.

`crm` and `internal` are routing namespaces. `partnership` is a Decision Hub
value with different semantics. Neither is added to the business vocabulary.

## Inventory

| Location / field | Storage and values observed | Writers/readers | Classification |
|---|---|---|---|
| `identity.py::Domain` | Python constants; six values before D1 | identity, permissions, context callers | canonical; extended with `recruitment` |
| `core/router/route_decision.py::RouterDomain` | routing strings; includes `crm`, `internal` | router/risk/domain routers | routing superset; explicit adapter |
| `airtable_schema.py::VentureFields.DOMAIN` / `VentureDomain` | title-case values including `Recruitment` | Venture readers/writers | legacy storage; `venture_legacy` adapter |
| `airtable_schema.py::LeadFields.DOMAIN` | documented lower-case strings; text field | lead creation, TMA, reasoning | canonical storage target; compatible reads |
| `airtable_schema.py::LeadEventFields.DOMAIN` | documentation contains legacy `recruiting` wording | Lead Event writer/readers | schema-drift surface; shared adapter at writer |
| `airtable_schema.py::BusinessMemoryFields.DOMAIN` | select field; exact live options still require live read | `cmd_update.py`, `weekly_summary.py` | dynamic storage adapter |
| `airtable_schema.py::DecisionDomain` | Hebrew Decision values, including partnership | Decision command/adapters | different semantics; keep separate |
| `ProjectsHubFields.DOMAIN` | lower-case documentation includes recruitment | TMA project/lead filtering | canonical target |
| `AssetsFields.DOMAIN` / `MediaFileFields.DOMAIN` | domain metadata fields | asset/media gateways | canonical target; legacy reads via adapter |
| `SessionsFields.DOMAIN` / lead session state | string session context | `session_store.py` | legacy runtime storage; not Marketing state |
| Interaction Log | domain-like metadata in consumers, no dedicated canonical field | `tma_api.py` and readers | separate interaction semantics; no D1 migration |

## Local normalizer classification

- `core/lead_event_writer._normalize_domain`: **REPLACE** — shared
  normalizer, preserving the writer's explicit `general` fallback.
- `weekly_summary._normalize_domain_key`: **REPLACE** — shared normalizer,
  preserving the read-only `general` fallback.
- `cmd_update._normalize_domain_option`: **KEEP FOR DIFFERENT SEMANTICS** —
  matches Airtable option labels from live schema; it is not domain resolution.
- `tma_api._normalize_task_domain`: **KEEP FOR DIFFERENT SEMANTICS** — maps
  to the Tasks table's exact legacy option vocabulary.
- ingress phrase maps: **WRAP** at storage boundaries; phrase detection is
  routing/input semantics, while stored values remain canonical.

## Live migration gate

No Airtable mutation was attempted. The next step is a read-only live schema
and record preview covering every listed field, counts, dependent views,
formulas/lookups, and the exact legacy-to-canonical map. Only after that
preview and compatibility verification may Phase B migration be considered.
