# Deterministic Routing Map

1. Normalize ingress and identity scope.
2. Preserve the existing classifier result and confidence.
3. Resolve lifecycle-first signals: exact callback, confirmation,
   cancellation, stale/expired/terminal/duplicate references.
4. Resolve explicit entity references with bounded identity-scoped lookups.
5. Select a canonical builder for complete structured mutations.
6. Route read-only known status/search requests to deterministic handlers.
7. Admit Agent only under the policy in `AGENT_ADMISSION_POLICY.md`.
8. Return `UNSUPPORTED` when no supported owner exists.

| Input condition | Owner | Agent | Required result |
|---|---|---:|---|
| Exact callback reference | Resolver → ActionGateway | No | lifecycle result, one speaker |
| Bare confirmation/cancellation | Resolver → ActionGateway | No | pending/ambiguous/terminal response |
| Structured create task | Deterministic handler | No | canonical proposal/result |
| Known entity update | Resolver → deterministic handler | No after one match | 0/1/multiple-match outcome |
| Known status/search | Resolver/read handler | No | source-backed status |
| Complete but semantically ambiguous request | Coordinator → clarify/Agent | Conditional | no mutation before clarification |
| Unsupported or forbidden action | Unsupported/block | No | explicit no-op response |

The routing result should carry `intent`, `owner`, `resolver_result`,
`canonical_action`, `approval_policy`, `evidence_requirement`, and
`reply_policy`. It must not carry an inferred completion claim.
