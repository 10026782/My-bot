# Target Ownership Matrix

| Intent group | Current owner(s) | Target owner | Transition | Reason/risk |
|---|---|---|---|---|
| task create/update/complete/search | router + Agent/tool paths | `TURN_COORDINATOR` → handler/resolver | typed intent envelope and bounded builder | duplicate Agent/tool decisions |
| lead create/update/search | lead candidate handler, Agent, TMA | `TURN_COORDINATOR` → resolver/handler | preserve capture policy; separate read/write | parallel lead paths and overwrite risk |
| approval status/pending query | Gateway, EventBus, app RAM, TMA projection | `TURN_COORDINATOR` → `RESOLVER`; ActionGateway remains lifecycle authority | read canonical AC first, project queues second | four stores disagree |
| execution status | Gateway/provider/result paths | `RESOLVER` → `ACTION_GATEWAY` | use durable execution/evidence state | tool call is not verified write |
| confirmation/cancellation | app, EventBus, Gateway | `TURN_COORDINATOR` → `ACTION_GATEWAY` | normalize word and resolve exact contract | legacy fallback can bypass lifecycle |
| callbacks | app callback branch + EventBus | `TURN_COORDINATOR` → `RESOLVER` → `ACTION_GATEWAY` | exact contract ID, role, version, claim | callback/text race and direct fallback |
| ambiguous business request | Agent safety-net | `TURN_COORDINATOR` → `AGENT` or clarify | deterministic pre-check first | Agent must not invent action |
| unsupported intent | unknown/Agent fallback | `UNSUPPORTED` | explicit safe response | no invented tool path |

The coordinator owns selection, not execution, approval state, evidence, or
final message composition.
