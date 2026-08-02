# Resolver Map

| Resolver | Lookup source | Scope/bound | 0 matches | 1 match | Multiple | Cold cache/durable | Agent fallback |
|---|---|---|---|---|---|---|---|
| tasks | canonical task provider/adapter | tenant + requester/domain; bounded limit | clarify/no-op | return stable ref | numbered choices | durable read; cache is optional | No for known action |
| leads | lead adapter/provider | tenant + identity/domain; bounded limit | clarify/create only if intent says create | stable lead ref | disambiguate | durable read | Only semantic ambiguity |
| contacts | contact resolver/provider | tenant + identity; bounded limit | no match | stable contact ref | disambiguate | durable read | No for mutation |
| deals | CRM adapter | tenant + domain; bounded limit | no match | stable deal ref | disambiguate | durable read | Conditional read-only synthesis |
| ActionContracts | `ActionContractRepository` | tenant + canonical contract ID/user | terminal/not found | lifecycle snapshot | never pick silently | durable source | No |
| session references | session store | identity/chat scope + TTL | expired/absent | continuation | disambiguate | durable only where existing contract says so | No authorization |
| callback references | callback payload → exact AC ID, legacy pointer only as migration | identity + role + contract state | stale/invalid | resolve exact contract | reject ambiguous | durable AC first | No |

Every resolver returns a typed result with `match_count`, stable IDs hidden from
UX, source version, and freshness. Full-table scans and unbounded `_store`
searches are not acceptable in the target path.
