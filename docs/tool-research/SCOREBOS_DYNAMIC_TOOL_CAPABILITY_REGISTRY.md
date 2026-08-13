# SCOREBOS Dynamic Tool Capability Registry

**Status:** Architecture proposal only  
**Date:** 2026-08-14  
**Scope:** Discovery, research, verification, classification, and read-only runtime recommendations. This document does not create a database, crawler, account, integration, or execution path.

## 1. Current-state problem

business_tool_registry.py is currently the canonical read-only catalog for curated external recommendations. It combines identity, user-facing aliases, capability hints, research state, privacy policy, verification, owner decisions, and runtime eligibility in one Python record. That is safe for the current seed but awkward when:

- a tool gains or loses a capability;
- multiple tools implement one capability;
- a native SCOREBOS implementation replaces an external tool;
- a crawler reports changed URL, privacy, signup, or free-tier facts;
- operator, infrastructure, crawler, worker, and business classes must coexist without leaking into normal recommendations.

tool_registry.py is the separate internal execution and permission registry. It owns internal tool roles, availability, approval, and execution policy. It must remain separate from the external catalog.

The target is one canonical external catalog. Bot and any future Mini-App must consume the same published runtime view. Research output, crawler output, Markdown, Airtable, and vendor APIs are evidence or editorial surfaces, not runtime truth.

## 2. Canonical data model

The smallest useful model has four durable entities and one generated view:

    Tool 1 ---< ToolCapability >--- 1 Capability
    Tool 1 ---< ToolEvidence
    Tool 1 ---< ToolDecisionHistory
    Tool 1 ---< ToolReplacement (optional relation)

Tool is stable identity and policy. Capability is a normalized need/action. ToolCapability is the many-to-many relation and carries fit, status, and notes specific to that pairing. Evidence is append-only pending material. Decision history records owner decisions; it is not runtime configuration.

The canonical store must expose an immutable, validated runtime snapshot. The application fails closed if the snapshot is missing, malformed, stale beyond policy, or contains an unknown enum/value.

No user request, crawler result, or model output may directly publish a runtime-visible tool.

### Stable identifiers

- tool_id: lowercase stable slug; never derived from display name at runtime.
- capability_id: normalized lowercase slug such as pdf_merge.
- tool_capability_id: deterministic pair key such as bentopdf:pdf_merge.
- Display names and task wording are not identifiers.
- Renaming a tool changes name, not tool_id.
- Replacing a URL does not create a new tool unless the owner decides it is a different service.

## 3. Tool schema

Conceptual record:

    {
      "tool_id": "bentopdf",
      "name": "BentoPDF",
      "canonical_url": "https://bentopdf.com/",
      "tool_class": "business",
      "tags": ["documents", "pdf"],
      "execution_mode": "GUIDED_EXTERNAL",
      "agent_mode": "NO_AGENT",
      "lifecycle_status": "APPROVED",
      "priority": 50,
      "decision": "KEEP_EXTERNAL",
      "privacy_class": "COPY_ONLY",
      "enabled": true,
      "source": "manual_research",
      "verification_status": "VERIFIED",
      "last_verified_at": "2026-08-13T00:00:00Z",
      "next_verification_at": "2026-11-13T00:00:00Z",
      "verification_source": "docs/tool-research/NOSIGNUPS_BUSINESS_TOOLBOX.md",
      "owner_notes": "Direct-use link; no SCOREBOS upload path.",
      "next_trigger": "Recheck URL and privacy behavior if reported changed.",
      "created_at": "2026-08-13T00:00:00Z",
      "updated_at": "2026-08-14T00:00:00Z"
    }

Required fields:

| Field | Rule |
|---|---|
| tool_id | Stable unique slug |
| name | Human display name |
| canonical_url | HTTPS canonical landing URL |
| tool_class | Extensible class: business, operator, infrastructure_candidate, research_crawler, worker_candidate, internal |
| tags | Normalized tag set; no category columns |
| execution_mode | One approved execution mode |
| agent_mode | One approved agent mode |
| lifecycle_status | Current lifecycle state |
| priority | Owner-set ordering value, never approval |
| decision | Owner architectural decision |
| privacy_class | Bounded handling rule |
| enabled | Runtime gate, subject to all other gates |
| source | Provenance of canonical record |
| verification_status | Current evidence status |
| last_verified_at | Last accepted verification timestamp |
| next_verification_at | Freshness deadline |
| verification_source | URL/document/test evidence reference |
| owner_notes | Human context, never authorization |
| next_trigger | Event that reopens research |
| created_at, updated_at | Audit timestamps |

Optional fields may include replacement_tool_id, deprecation_reason, privacy_notes, and verification_version. These do not change the semantic contract.

## 4. Capability schema

    {
      "capability_id": "pdf_merge",
      "name": "PDF merge",
      "description": "Combine multiple PDF files into one output.",
      "tags": ["documents", "pdf"],
      "lifecycle_status": "VERIFIED",
      "source": "owner_seed",
      "created_at": "2026-08-13T00:00:00Z",
      "updated_at": "2026-08-14T00:00:00Z"
    }

Store one canonical action, not every Hebrew or English wording variation. Wording aliases belong in a matcher/read model. A capability may exist before any tool is approved. It is not executable by itself: resolution always selects an eligible implementation and execution mode.

Adding pdf_merge, csv_repair, image_resize, api_testing, or uptime_monitoring is a data change, not a schema change.

## 5. Tool-Capability relation

    {
      "tool_capability_id": "bentopdf:pdf_merge",
      "tool_id": "bentopdf",
      "capability_id": "pdf_merge",
      "fit": "PRIMARY",
      "execution_mode": "GUIDED_EXTERNAL",
      "agent_mode": "NO_AGENT",
      "lifecycle_status": "APPROVED",
      "verification_status": "VERIFIED",
      "priority": 50,
      "enabled": true,
      "notes": "Direct browser use; copy-only privacy rule.",
      "last_verified_at": "2026-08-13T00:00:00Z"
    }

Relationship-level state is required because a tool may be verified for one capability but unverified for another. It also lets a native implementation supersede an external candidate without changing user intent matching.

Normal-user eligibility requires all of:

    tool.enabled
    relation.enabled
    tool.lifecycle_status == APPROVED
    relation.lifecycle_status == APPROVED
    tool.verification_status == VERIFIED
    relation.verification_status == VERIFIED
    tool.decision != REJECT
    tool.execution_mode not in {OPERATOR_ONLY, POC_ONLY}

Restrictions are represented by APPROVED plus privacy/owner restrictions, not by inventing another lifecycle enum.

## 6. Category/tag model

Categories are tags, not columns:

    tags: ["documents", "pdf", "privacy-reviewed"]

Tags are normalized slugs. A tag may attach to a Tool, Capability, or relation. New tags do not require migration. A controlled tag registry may document meaning, owner, and deprecation, but it is metadata, not a second catalog.

Runtime authority uses explicit fields. Tags are for grouping and search; a tag must never grant approval, access, or execution permission.

Adding accessibility, webhook, or media is a data change. A genuinely new semantic contract, such as a new approval boundary, requires architecture review and a schema/version change.

## 7. Lifecycle/status model

| Status | Meaning | Runtime visible? |
|---|---|---|
| DISCOVERED | Mentioned by a source or owner; not researched | No |
| RESEARCHING | Evidence gathering is active | No |
| VERIFIED | Evidence is current; owner approval is separate | No |
| APPROVED | Owner-approved for declared scope | Yes if all gates pass |
| DEFERRED | Intentionally postponed; preserve reason | No |
| REJECTED | Explicitly rejected | No |
| DEPRECATED | Known but no longer recommended | No |

Normal transition:

    DISCOVERED -> RESEARCHING -> VERIFIED -> APPROVED
          \-> DEFERRED
          \-> REJECTED
    APPROVED -> DEPRECATED
    APPROVED -> RESEARCHING   (material change)

When now exceeds next_verification_at, the record is stale and must not be presented as current approval. Runtime excludes it unless a separately approved stale policy exists; this design recommends exclusion.

## 8. Execution and agent modes

Execution modes:

- GUIDED_EXTERNAL: SCOREBOS explains and links; the user operates the external tool.
- NATIVE: SCOREBOS-owned local/native implementation.
- INTEGRATED: approved SCOREBOS integration with explicit authority, secrets, error, and approval design.
- OPERATOR_ONLY: internal operator use; never normal business recommendation.
- POC_ONLY: evaluation only; never runtime-visible.

Agent modes:

- NO_AGENT: bounded explanation only.
- OPTIONAL_AGENT: one bounded offer of help that does not execute the tool.
- AGENT_REQUIRED: only when an approved SCOREBOS-owned flow explicitly requires agent participation.

Current external records are mainly GUIDED_EXTERNAL. Operator and infrastructure candidates are OPERATOR_ONLY or POC_ONLY. No external tool is promoted to INTEGRATED by this design.

## 9. Runtime consumption architecture

| Option | Strength | Risk | Verdict |
|---|---|---|---|
| Code remains canonical | Simple, reviewable, already fail-closed | Editorial changes require deploy; relationships become awkward | Keep as transition seed |
| Database/Airtable canonical | Easy editing and querying | New authority, runtime dependency, privacy/approval coupling, parallel catalog risk | Reject now |
| Dynamic canonical store plus generated snapshot | Supports relationships/history while runtime stays immutable and fail-closed | Requires validation and generation workflow | Recommended |

Recommended flow:

    approved research sources
            \↓
    candidate/evidence records
            \↓
    owner review and decision
            \↓
    canonical dynamic store
            \↓
    schema validation and deterministic generation
            \↓
    versioned read-only runtime snapshot
            \↓
    business_tool_registry resolver
            \↓
    bot and future Mini-App use the same snapshot

The dynamic store is canonical editorial state. The snapshot is a derived, versioned read model, never edited directly. It must include source revision/hash and generation time. Invalid generation fails; no candidate fallback is allowed. If no valid snapshot exists, the resolver returns no recommendation.

tool_registry.py remains the internal execution/permission authority. This registry must not import or mutate ActionContracts, approval state, identities, Airtable records, or execution evidence.

### Capability resolution

    Need -> capability_id -> eligible ToolCapability relations
         -> ranked current execution mode -> recommendation or native route

Example:

    "איחוד PDF" -> pdf_merge
                 -> bentopdf:pdf_merge [GUIDED_EXTERNAL, APPROVED]
                 -> BentoPDF direct-use recommendation

After internalization:

    "איחוד PDF" -> pdf_merge
                 -> score eligible implementations
                 -> SCOREBOS native route [NATIVE]

Intent matching targets capability_id. Tool-name matching remains a compatibility path for direct references, not the canonical need model.

## 10. Update and verification flow

    Discovery -> Candidate -> Research -> Verification
             -> Owner/approved decision -> Canonical Registry -> Runtime snapshot

Research agents and crawlers may create candidates and append evidence. They may not set APPROVED, enable runtime use, or publish a snapshot.

Verification evidence includes source URL, retrieval time, content hash or test reference, observed claims, and reviewer. Owner approval is explicit and scoped to tool, capability, privacy/data constraints, execution mode, and freshness window.

Snapshot generation rejects unknown enum values, missing URLs, invalid relations, stale approvals, duplicate IDs, and approved records without verification evidence.

Re-open research when the URL, redirect target, privacy/upload/telemetry/signup/retention conditions, free-tier claim, availability, or deprecation status changes; when an owner reports a mismatch; or when next_verification_at is reached.

Example pending crawler evidence:

    {
      "evidence_id": "evidence-2026-08-14-bentopdf",
      "tool_id": "bentopdf",
      "observed_at": "2026-08-14T10:00:00Z",
      "source_url": "https://bentopdf.com/",
      "claim_type": "privacy_behavior",
      "observed_value": "needs manual verification",
      "content_hash": "sha256:...",
      "verification_status": "PENDING",
      "proposed_changes": ["privacy_class"],
      "reviewer": null
    }

Pending evidence never changes runtime behavior. A changed URL or privacy condition causes exclusion or owner re-review, not automatic publication.

## 11. Migration of current tools

| Current field | Target |
|---|---|
| tool_id, name, url | Tool identity |
| tool_class | Tool tool_class |
| categories, domain_tags | Tool tags |
| capabilities | Capability records plus relations |
| tasks | Capability matcher aliases/read model |
| verification_status, last_verified_at, source | Verification/provenance |
| enabled | Tool enabled gate |
| privacy_level, allowed_data, forbidden_data | Privacy class/policy and notes |
| free_status, signup_required, local_processing | Evidence attributes and notes |
| short_description, when_to_use, when_not_to_use | User-facing description and policy notes |
| playbook | Capability-specific guidance |
| status=deferred | DEFERRED lifecycle |
| status=approved_with_restrictions | APPROVED plus restrictions |

Seed inventory and preservation mapping:

| Existing record/class | Target class | Lifecycle / decision | Execution |
|---|---|---|---|
| BentoPDF, VERT, Squoosh, PairDrop, RAWGraphs | business | APPROVED / KEEP_EXTERNAL | GUIDED_EXTERNAL |
| csv.repair, SQL for Files, CyberChef, SVGOMG, Mr. Data Converter | business | APPROVED / KEEP_EXTERNAL | GUIDED_EXTERNAL |
| JSON Crack, Metadata Remover, ShareClean | business | APPROVED / KEEP_EXTERNAL, restrictions preserved | GUIDED_EXTERNAL |
| Hoppscotch, Log Voyager | operator | APPROVED with restrictions / KEEP_EXTERNAL | OPERATOR_ONLY |
| UptimeRobot, Checkly, Sentry, Socket | infrastructure_candidate | DEFERRED / INTEGRATE_LATER | POC_ONLY |
| Crawl4AI | research_crawler | DEFERRED / KEEP_EXTERNAL for isolated POC | POC_ONLY |
| Firecrawl | research_crawler | DEFERRED / INTEGRATE_LATER after measured Crawl4AI failure | POC_ONLY |
| Worker/orchestration candidates | worker_candidate | DEFERRED / INTEGRATE_LATER | POC_ONLY |

The last row preserves the deferred worker/orchestration research class without promoting unverified names. Exact candidates remain in research documents until an owner approves a seed record.

Internal tool_registry.py records are not migrated into this external catalog. They retain internal permission and approval authority. If an internal implementation later serves a user capability, it gets an explicit relation to the shared Capability; its permission record is not duplicated.

## 12. Example records and extensibility

One capability can have multiple implementations:

    bentopdf:pdf_merge       GUIDED_EXTERNAL  APPROVED   KEEP_EXTERNAL
    scorebos-pdf-merge:pdf_merge
                               NATIVE          RESEARCHING INTERNALIZE

Only the approved relation is eligible today. Adding the native candidate does not change user intent matching.

A new tool, capability, category, or tool class is a record/tag/value addition. No schema column is needed. Only a genuinely new semantic contract, such as a new approval boundary, requires schema/version review.

## 13. Owner decision gates

Owner approval is required for:

- choosing the dynamic store technology and access/retention boundary;
- changing GUIDED_EXTERNAL to INTEGRATED or NATIVE;
- enabling operator, infrastructure, crawler, or worker candidates;
- approving production data, credentials, uploads, telemetry, or vendor retention;
- changing privacy class, canonical URL, replacement, or freshness interval;
- publishing a snapshot after candidate evidence changes;
- adding a Mini-App consumer;
- introducing a scheduled crawler, queue, database, Airtable workflow, or external provider.

Research-only candidates and pending evidence need no publication gate as long as they cannot enter runtime resolution.

## 14. Smallest implementation sequence

1. Freeze enums, IDs, eligibility predicate, snapshot version, and fail-closed behavior in a decision document.
2. Convert the existing business_tool_registry.py seed into Tool, Capability, and ToolCapability records in a checked-in canonical format.
3. Generate and validate one deterministic read-only snapshot; keep matching behavior unchanged.
4. Keep tool_registry.py as the internal execution registry and keep bot/Mini-App on the same snapshot.
5. Add pending evidence separately; require explicit owner verification before regeneration.
6. Measure maintenance pain before choosing a dynamic store/editorial surface. Do not add Airtable, a database, crawler scheduling, or a vendor for convenience.
7. Migrate one capability end to end: pdf_merge with BentoPDF, then csv_repair.
8. Test normal matching, operator/infrastructure isolation, stale exclusion, unknown enum rejection, and identical bot/Mini-App snapshot reads.

## Final verdict

### CANONICAL SOURCE

**A canonical dynamic Tool/Capability store with a generated, validated, read-only runtime snapshot.**

business_tool_registry.py remains the safe transition seed until the snapshot path is implemented and verified.

### WHY

1. Supports many-to-many capabilities and future native implementations without rewriting intent matching.
2. Keeps editorial history, evidence, freshness, and owner decisions out of the runtime process.
3. Avoids making Airtable, a crawler, a vendor, or a Mini-App a parallel source of truth.
4. Provides deterministic, immutable, fail-closed runtime behavior.
5. Preserves separation between external recommendations and internal execution/approval authority.

### CURRENT REGISTRY MIGRATION

Extract BusinessTool records into Tool records; split capabilities into normalized Capability records; split tasks into capability matcher aliases; create one ToolCapability relation per supported capability; map status, privacy, class, verification, and decision fields as above; generate the first snapshot; then switch business_tool_registry.py to a read-only snapshot adapter. Do not migrate internal tool_registry.py records into the external catalog.

### RUNTIME MODEL

user need -> capability_id -> eligible ToolCapability relations -> ranked current execution mode -> one shared read-only snapshot consumed by bot and future Mini-App

Unknown, stale, unverified, rejected, deferred, operator-only, or POC-only records resolve to no user-facing recommendation.
