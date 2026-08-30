# Public Renderer / MessageContract Registry

New public renderer symbols and new entry paths into the semantic
`MessageContract`/formatter require an exact row here. Each row names the
surface owner and the architecture decision that approved the path. A row is
review metadata; it does not itself wire or activate a runtime surface.

| Path | Kind | Symbol | Surface owner | Architecture decision |
| --- | --- | --- | --- | --- |
| `core/lead_service.py` | `public_renderer` | `build_lead_draft_message_contract` | f52_lead_draft | `D-012/R4` |
| `core/lead_service.py` | `contract_import` | `message_contract` | f52_lead_draft | `D-012/R4` |
| `core/lead_service.py` | `contract_entry` | `message_contract` | f52_lead_draft | `D-012/R4` |
| `core/lead_service.py` | `public_renderer` | `render_lead_draft_message` | f52_lead_draft | `D-012/R4` |
| `tools/whatsapp_adapter.py` | `contract_entry` | `message_contract` | f52_whatsapp_r7 | `D-012/R7.1` |
