# Media / Marketing Enablement — Audit (post PR #595)

Date: 10/08/2026
Status: AUDIT ONLY — no code/schema changes made yet, see stop condition at bottom.

## Context

PR #595 (`pa01-task-routing`) is merged and CORE is marked complete on `main` (current branch: `docs/core-final-integration-gate-report`, clean, up to date with origin). The next workstream is enabling a **manual** marketing loop — demand → 3 creative ideas → human selection → ad package → Drive/Airtable storage → channel selection → manual publish → results tracked — without redesigning CORE, without a parallel CRM, and without any auto-publishing.

This document is **audit only**, produced by reading the actual repo (`/home/elichazan/My-bot`), not by trusting prior planning docs. Every claim below is grep/read-verified against current code, and the two Airtable tables in question were re-confirmed live via Airtable MCP during this audit. Where a planning doc disagreed with code, code wins and the doc is flagged stale.

---

## A. Current-state matrix

| # | Capability | Status | Evidence | Runtime status | Gap |
|---|---|---|---|---|---|
| 1 | Media upload to Drive | PARTIAL | `drive_adapter.py` (`upload_file`, `_upload_to_drive`, `get_or_create_folder`, `_get_upload_folder`) — real Drive REST upload, domain/month folder convention under `GOOGLE_DRIVE_FOLDER_ID` root | Called only from `media_handler.py`'s Telegram/TMA intake paths, gated by `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` (both default OFF). **Not** an agent tool — no dispatcher/registry entry. Agent-callable Drive tools (`search_drive`, `read_drive_file`, `tools/dispatcher.py:186-189`) are read-only; no agent-callable upload exists | Upload mechanism exists and is reusable; nothing calls it for *outbound* marketing assets |
| 2 | Media metadata persistence | PARTIAL | `media_gateway.py` — `AssetRecord` dataclass + `save_asset()`, writes via `airtable_create(Tables.MEDIA_FILES, ...)` (single-gateway write, correct pattern) | Only called from `media_handler.py`'s inbound flows | Clean, reusable function; needs new fields + a new caller for outbound marketing assets |
| 3 | `Media Files` Airtable table integration | DONE (confirmed live 10/08/2026) | `airtable_schema.py:67` `Tables.MEDIA_FILES = "Media Files"`; `airtable_schema.py:597-618` `MediaFileFields`. **Verified live via Airtable MCP `list_tables_for_base` (base `app4bcgoX7t0HUVnm`) during this audit**: table `tbl6AFKkPZVN5qdCt` exists with 17 fields — the 12 code-defined fields (Name, File Type, Mime Type, Drive URL, Drive File ID, Domain, Source, Raw Transcript, Transcript, Size Bytes, Created By, Telegram File ID, Linked Lead) match live field names **exactly**, including the `NORMALIZED_TRANSCRIPT = "Transcript"` naming, plus 4 extra live-only link fields (Linked Decision, Linked Decision Event, Linked Contact, Sessions) unused by current code | Code-complete, flag-gated OFF (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`), but the table itself is confirmed live and schema-correct — `schema_cache.json`'s stale seed and BUG-015 (23/06/2026) are both superseded by this direct check | None — this item is resolved, safe to extend directly |
| 4 | Link between Airtable records and Drive files | DONE (pattern) | `MediaFileFields.DRIVE_URL` / `DRIVE_FILE_ID` on `Media Files`; same linked-record pattern via `LINKED_LEAD` (array of record ids) already used for lead↔asset linking | Wired within the F16 path | Pattern is proven and directly reusable for Demand↔Asset and Creative↔Drive-prompt links |
| 5 | Marketing demand representation | MISSING | No table/module represents "work type + location + experience level" demand anywhere in code. Closest structural analog is `VentureFields` (`airtable_schema.py:242-259`: NAME, STAGE, DOMAIN, NEXT_ACTION, OWNER, NOTES) — a *different* concept (pre-deal opportunity eval), not demand intake | — | New small table needed; reuse the Venture/Lead field-naming convention (`Stage`, `Next Action`, `Status`), not the Ventures table itself |
| 6 | Creative concept storage | MISSING | `creative_generator.py` generates copy text (5 Hebrew templates) but persists nothing — no Airtable write anywhere in the file (confirmed by grep) | Not wired anywhere — zero callers in the whole repo | Storage layer entirely absent; generation logic exists but is orphaned code (matches CLAUDE.md's own "not currently imported" list) |
| 7 | Selected creative / approval state | MISSING (pattern exists elsewhere) | `ApprovalStatus` enum (`airtable_schema.py:660-665`: ממתין/מעבד/אושר/נדחה/נכשל) exists for the unrelated tool-execution approval flow (`Approvals` table) | Not applicable to creative review | No creative-specific approval table/field exists; the *string-constant pattern* is reusable, the `Approvals` table itself should not be repurposed (different lifecycle: tool-execution vs. content review) |
| 8 | Marketing asset representation | MISSING (extend #2/#3) | Nothing distinguishes an "outbound ad asset" from an "inbound uploaded file" today — `Media Files` schema has no Platform/Creative-Concept/Approval/Publish-status fields | — | Extend `MediaFileFields` + `AssetRecord`, don't create a parallel table |
| 9 | Distribution channel registry | PARTIAL (unused live table, re-confirmed 10/08/2026) | `Tables.TRAFFIC_SOURCES` (`airtable_schema.py:82`) + `TrafficSourcesFields` (`airtable_schema.py:1293-1311`). **Re-verified live via Airtable MCP during this audit**: table `tblwMww5e9yZWeCXg` exists with 12 fields (Source Name, Source Type, Audience, Contact, Reach, Leads, Deals, Revenue, Cost, Status, Notes, ROI formula) matching code exactly, description confirms "channel-level traffic source attribution" | Zero code reads/writes it anywhere — pure unused schema definition, confirmed still true | Table already exists live and already covers Channel Name→Source Name, Audience Type→Audience. Needs new fields (URL/reference, Location, Professional Category, Free/Paid, Suitable Work Types, Posting Rules, Last Published At, Quality Notes), not a new table |
| 10 | Manual publication tracking | MISSING | No table/module tracks "published asset X to channel Y with source code Z, N responses." `Interaction Log` table exists but is documented as "automatic log — agent/system interactions" (`airtable_schema.py` Tables comment), a different shape/purpose | — | New small table needed (thin — 8 fields, all scalar/link, no logic) |
| 11 | Source / attribution tracking | PARTIAL | `ad_attribution.py` (588 lines) — `UTMParams`, `parse_utm()`, `record_lead_source()`, writes `utm_source`/`utm_medium`/`utm_campaign`/`platform` directly onto `Leads` (raw literals, not through `LeadFields` constants, deliberate per `ROADMAP.md:307`). Wired at `app.py:6172-6183` on the WhatsApp inbound path only, gated by `AD_ATTRIBUTION` flag (default OFF) | Runtime-wired but off by default; unverified end-to-end per `BOSS_Marketing_Execution_Map.md`'s own admission | Existing mechanism is the right one to extend for "Source Code" on Manual Publication records — don't build a second attribution system |
| 12 | `Next Action` / workflow-stage visibility | DONE (as a pattern) | `LeadFields.NEXT_STEP = "Next Action"` (`airtable_schema.py:329`), `VentureFields.NEXT_ACTION`/`STAGE` (`airtable_schema.py:251,245`), rendered in `score_display.py:74` | Live, established convention across Leads and Ventures | No gap — reuse this exact field-naming convention (`Current Stage`, `Next Action`, `Status`) for the new Demand/Creative tables, don't invent new vocabulary |
| 13 | Prompt-library storage and access | MISSING | `grep -rni "prompt_library\|prompt library"` across all `.py`/`.md`: **zero hits anywhere**, code or docs | — | Pure absence. Smallest fix: a Drive folder (`marketing/prompt-library/`) referenced by URL from Airtable — no new table, no new code required for storage itself |
| 14 | Existing flags required to enable Media Layer safely | DONE | `FEATURE_VOICE_NOTES`, `FEATURE_MEDIA_UPLOAD` (`feature_flags.py:75-76`), both default OFF, checked at `app.py:5629`, `app.py:5672`, `tma_api.py:3944`, `cmd_update.py:283` | Flags exist and gate correctly | None — this workstream needs its own new flag(s) for the marketing-specific write paths (writing outbound assets/creatives), following the same default-OFF convention |

---

## B. Reuse map — use unchanged or lightly extend, do not rebuild

| Existing thing | File | Reuse as-is for |
|---|---|---|
| `media_gateway.save_asset(AssetRecord)` + `airtable_create()` gateway | `media_gateway.py` | The single write path for any new Marketing Asset record — same function, extended `AssetRecord`/`MediaFileFields` |
| `drive_adapter.get_or_create_folder(name, parent_id)` | `drive_adapter.py:80` | Building the marketing Drive folder tree — it's already generic (not F16-specific), takes any name/parent |
| `drive_adapter._upload_to_drive` / `upload_file` | `drive_adapter.py:144,190` | The actual file-bytes-to-Drive call for ad assets |
| `Tables.TRAFFIC_SOURCES` + `TrafficSourcesFields` | `airtable_schema.py:82,1293-1311` | The Distribution Channel record — table already live, extend fields, don't create a new one |
| `Tables.MEDIA_FILES` + `MediaFileFields` | `airtable_schema.py:67,597-618` | The Marketing Asset record — extend, don't duplicate |
| `ad_attribution.py` UTM/source mechanism | `ad_attribution.py` | Source Code on Manual Publication records — same mechanism, don't build a second attribution system |
| `Next Action` / `Stage` / `Status` field-naming convention | `LeadFields`, `VentureFields` (`airtable_schema.py`) | Field names on the new Demand table |
| `feature_flags.py` default-OFF pattern + `is_enabled()` | `feature_flags.py` | Any new flags this workstream needs |
| Linked-record pattern (`LINKED_LEAD` as array field) | `airtable_schema.py:MediaFileFields` | Demand↔Creative, Demand↔Asset, Asset↔Publication links |

---

## C. Exact confirmed gaps (proven against current state, not docs)

1. **No agent/marketing-facing Drive upload path.** `upload_file()` exists and works but is only called from F16's inbound Telegram/TMA handlers.
2. ~~`Media Files` table's live existence unconfirmed~~ — **RESOLVED during this audit**: confirmed live via Airtable MCP, schema matches code exactly (see row 3 above). No longer a gap.
3. **No Demand table/record exists anywhere** (work type / location / experience level).
4. **No Creative record exists anywhere** — `creative_generator.py` generates but never persists, and has zero callers.
5. **No creative approval/selection state exists** — no field, no table.
6. **`Media Files` has no marketing-specific fields** (Platform, Creative Concept, Approval Status, Ready To Publish, Published Status, linked Demand).
7. **`TRAFFIC_SOURCES` exists live but is completely unwired** (zero code readers/writers) and lacks the fields this workflow needs (URL, Location, Professional Category, Free/Paid, Suitable Work Types, Posting Rules, Last Published At, Quality Notes).
8. **No Manual Publication record exists.**
9. **No Prompt Library storage exists** — not even a documented convention.
10. **`AD_ATTRIBUTION` flag is off by default and its own execution-map doc admits the write path is unverified end-to-end** — relevant if Source Code on publications is meant to reuse this mechanism.

Everything else requested (folder conventions, linking pattern, field-naming convention, write gateway, flag pattern) already exists and works — this is a genuinely small remaining gap, consistent with the task's framing.

---

## D. Ownership map — what this workstream would own

- **Airtable (existing base, no new base):**
  - Extend `Media Files` (fields only) — owned jointly with F16, additive only.
  - Extend `TRAFFIC_SOURCES` (fields only) — currently unowned by any code, this workstream becomes its first owner.
  - New table: `Marketing Demand` (6 fields, per spec below).
  - New table: `Marketing Creatives` (8 fields, per spec below).
  - New table: `Marketing Publications` (8 fields, per spec below).
- **Drive:** a new root subfolder (e.g. `marketing/`) alongside the existing F16 domain folders under `GOOGLE_DRIVE_FOLDER_ID`, with children: `prompt-library/`, `active/`, `approved/`, `published/`, `archive/`.
- **Repository files this workstream would touch:**
  - `airtable_schema.py` — new `Tables.*` constants + new `*Fields` classes for the 3 new tables; extend `MediaFileFields`/`TrafficSourcesFields`.
  - `media_gateway.py` — extend `AssetRecord` with the new optional fields (mirrors the existing `linked_lead_id`-style optional-field pattern).
  - New thin module (e.g. `marketing_gateway.py`) for Demand/Creative/Publication record writes — same shape as `media_gateway.py`, going through `airtable_gateway.airtable_create`/`airtable_update`. Ponytail note: don't build this until the "extend media_gateway" path is proven insufficient — a single gateway module covering all 3 new tables is enough, no per-table modules.
  - `feature_flags.py` — one new flag (e.g. `MARKETING_ENABLEMENT`), default OFF, following the existing docstring-registry convention.
  - No changes to `app.py` core pipeline, `tool_registry.py` role model, `dispatcher.py` routing, or CORE modules — this is additive schema + a small gateway module, consistent with "do not redesign CORE."

---

## E. Smallest implementation plan (ordered, gaps only)

**1. No-code configuration**
   - None identified beyond Airtable/Drive setup below.

**2. Airtable changes**
   1. ~~Verify `Media Files` exists live~~ — done during this audit (base `app4bcgoX7t0HUVnm`, table `tbl6AFKkPZVN5qdCt`, confirmed).
   2. Add marketing fields to `Media Files`: `Linked Demand` (link), `Platform`, `Creative Concept`, `Approval Status`, `Ready To Publish`, `Published Status`.
   3. Add fields to `TRAFFIC_SOURCES` (table `tblwMww5e9yZWeCXg`, confirmed live): `URL`, `Location`, `Professional Category`, `Free/Paid`, `Suitable Work Types`, `Posting Rules`, `Last Published At`, `Quality Notes`.
   4. Create `Marketing Demand` table: Work Type, Location, Experience Level, Current Stage, Next Action, Status.
   5. Create `Marketing Creatives` table: Linked Demand, Creative Idea 1/2/3, Reviewer Notes, Selected Creative, Creative Status, Prompt/Drive Link.
   6. Create `Marketing Publications` table: Demand, Asset, Channel, Published At, Source Code, Responses, Qualified Responses, Notes.

**3. Drive setup**
   1. Create `marketing/` folder under the existing `GOOGLE_DRIVE_FOLDER_ID` root.
   2. Create children: `prompt-library/`, `active/`, `approved/`, `published/`, `archive/`.
   3. No file duplication — Airtable records reference Drive URLs, files stay in Drive only (matches existing F16 convention exactly).

**4. Repository/documentation changes**
   1. Add the new `Tables.*` / `*Fields` constants to `airtable_schema.py` (matches steps in §2).
   2. Register the new flag in `feature_flags.py`.
   3. Note the new tables/flag in `ROADMAP.md` under a new entry (next available ID is F23 — F16 through F22 are taken).

**5. Actual code changes**
   1. Extend `AssetRecord`/`_asset_to_fields()` in `media_gateway.py` with the new optional marketing fields (same optional-field pattern already used for `linked_lead_id`/`raw_transcript`).
   2. New `marketing_gateway.py`: thin write functions for Demand/Creative/Publication records, mirroring `media_gateway.py`'s shape exactly (dataclass → fields dict → single `airtable_create`/`airtable_update` call). No dispatcher/registry wiring needed — this is a direct-call module like `cmd_update.py`/`media_handler.py`, not an agent tool, since creation/selection/publishing are explicitly manual, human-triggered actions, not agent-autonomous ones.
   3. A minimal entry point for a human to trigger record creation (Telegram command, TMA screen, or direct Airtable data entry) — **not specified by the requirements above; needs a decision before this step, see below.**

Everything in §5 is small and additive; nothing here touches CORE, the router, the dispatcher, or tool registry.

---

## Stop condition — proposed first vertical slice

**One demand → three creative ideas stored → one selected → one ad asset stored in Drive/Airtable → one manual publication recorded.**

What must exist for that slice to work, in order:
1. ~~Confirmed live `Media Files` table~~ — done during this audit.
2. `Marketing Demand`, `Marketing Creatives`, `Marketing Publications` tables created in Airtable (§E.2.4-6).
3. `Media Files` extended with the marketing fields (§E.2.2).
4. `marketing_gateway.py` with three functions: create-demand, save-creative-ideas, record-publication — reusing `media_gateway.save_asset` unchanged for the asset itself.
5. The `marketing/` Drive folder tree (§E.3).
6. One new default-OFF flag gating the write paths.
7. A human-facing entry point to trigger these writes — **open question, not yet decided** (user deferred this to a follow-up planning pass): is this a new Telegram command (like `cmd_update.py`'s `/update`), a TMA screen, or direct Airtable data entry with code only handling the Drive upload + Media Files/Publication linkage? This determines whether §E.5 needs one more small file or zero.

No code should be written until the human-entry-point question above is answered — that is now the only remaining blocker.
