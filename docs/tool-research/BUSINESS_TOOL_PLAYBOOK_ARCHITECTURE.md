# SCOREBOS Business Tool Playbook Architecture

## Decision

The existing `BusinessTool` registry remains the single source of truth. Each
record now carries a `ToolPlaybook` with deterministic purpose, prerequisites,
steps, output, privacy guidance, mistakes, and agent policy.

The runtime path is:

`need or tool name → deterministic registry match → playbook formatter → optional assistance offer`

The formatter presents the tool name as the Markdown link. It does not show a
raw URL, image preview, or call the model. `optional_agent` only offers help;
it does not invoke an agent automatically.

## Coverage

Thirteen normal business tools have playbooks. Current classifications:

| Agent mode | Count |
|---|---:|
| `NO_AGENT` | 9 |
| `OPTIONAL_AGENT` | 4 |
| `AGENT_REQUIRED` | 0 |

All remain `GUIDED_EXTERNAL_TOOL`; none is integrated or made an execution
path for SCOREBOS. No production data upload, secrets, ActionGateway change,
permission change, database, or Mini-App was added.

## Examples

| Need | Tool | Playbook | Agent decision |
|---|---|---|---|
| איחוד PDF | BentoPDF | upload copies, merge, verify, download | `NO_AGENT` |
| CSV שלא נפתח | csv.repair | inspect, repair, reopen and verify | `NO_AGENT` |
| הקטנת תמונה | Squoosh | load copy, choose quality, compare, download | `NO_AGENT` |
| יצירת גרף | RAWGraphs | load redacted export, map columns, export | `OPTIONAL_AGENT` |
| הבנת JSON | JSON Crack | paste redacted JSON and inspect tree | `OPTIONAL_AGENT` |

## Verification

The registry tests cover deterministic need matching, direct tool lookup,
clean link output, no preview URL, restricted-data warnings, hidden operator
tools, unknown-need non-invention, and optional assistance being offered
without an agent call. The pure registry path itself contains no model client
or external execution call, so the zero-agent guarantee is structural.

## Future decisions

Keep all current tools external. Consider internalization later only for
privacy-sensitive, repeatedly used transformations such as image metadata
removal or CSV repair, and only after measured demand and a security review.
No future API integration is justified by this task.

## Remaining gaps

Playbook wording is deterministic and intentionally compact. Production
verification still needs live checks for direct tool-name lookup and the
rendered Markdown behavior in the deployed Telegram path.
