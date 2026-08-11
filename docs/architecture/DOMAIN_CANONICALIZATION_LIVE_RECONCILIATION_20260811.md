# D1 live Airtable reconciliation — 2026-08-11

Base inspected: `app4bcgoX7t0HUVnm`.

Status: **LIVE SCHEMA/DATA VERIFIED** for read-only inspection. Mutation is
blocked because the connected Airtable update-field operation rejects select
option updates; no live writes were performed.

## Canonical business domain

`real_estate`, `import`, `media`, `saas`, `finance`, `recruitment`, `general`.

`crm` and `internal` remain Router-only namespaces. Decisions remain a
separate Decision Hub taxonomy.

## Live inventory

| Table / field | Live type and options | Record values / count | Classification |
|---|---|---|---|
| Projects.Domain | singleSelect: General, Saas, Real Estate␠, Import, Recruitment | 0 | legacy storage; no records |
| Loans.Domain | singleSelect: Finance | 0 | incomplete/legacy; no records |
| Contacts.Domain | singleSelect: SaaS␠, General, Real Estate␠, ␠Recruitment␠, Import | empty 421 | legacy storage; no values to migrate |
| Deals.Domain | singleSelect: Real Estate␠, General, SaaS, Recruitment, Import | empty 2 | legacy storage; no values to migrate |
| Tasks.Domain | singleSelect: Real Estate, Income Properties, Recruitment, Import, Saas | empty 119, Recruitment 2 | legacy task vocabulary; preserve |
| Expenses.domain | singleSelect: ␠General, Real Estate␠, SaaS␠, Recruitment␠, Import | empty 1 | legacy storage; no values to migrate |
| Payments.domain | singleSelect: ␠General, SaaS␠, Real Estate␠, Recruitment␠, Import | empty 1 | legacy storage; no values to migrate |
| Learnings.domain | singleSelect: General, Real Estate␠, SaaS␠, Recruitment, Import | empty 1 | legacy storage; no values to migrate |
| Leads.domain | singleLineText | recruitment 19, general 3 | canonical business domain |
| Leads.Domain category | singleSelect classification | empty 22 | different semantics; untouched |
| Leads.Domain risk assessment | singleSelect classification | empty 22 | different semantics; untouched |
| Leads.Domain summary | aiText from Leads.domain | empty/stale 22 | different semantics; untouched |
| ProjectsHub.domain | singleSelect: saas, real_estate, import, recruitment, finance, general | import 1, finance 1, recruitment 1, saas 1, real_estate 1 | canonical business domain |
| Assets.Domain | singleSelect: Finance, Personal | Personal 7, empty 2 | different asset classification; untouched |
| Business Memory.Domain | singleSelect: General, Real Estate␠, Saas, Import, Media, Finance | empty 34 | legacy storage; add Recruitment option when write capability exists |
| Interaction Log.Domain | singleSelect: ␠General, ␠SaaS␠, Real Estate␠, Recruitment␠, Import | empty 385 | legacy storage; no values to migrate |
| Ventures.Domain | singleSelect: Real Estate, Import, SaaS, Recruitment, General | Import 1, Recruitment 1, General 1 | legacy storage; adapter required |
| Lead Events.Domain | singleSelect: real_estate, import, recruiting, general, saas, recruitment, media, crm | general 39, recruitment 14, real_estate 8 | canonical records; `recruiting` and `crm` remain legacy options |
| Media Files.Domain | singleLineText | general 9, empty 1 | canonicalized on writes; keep free text |
| Marketing Demand.Domain | singleSelect: real_estate, import, media, saas, finance, general | 0 | canonical; add recruitment option |
| TRAFFIC_SOURCES.Suitable Domains | multipleSelects: real_estate, import, media, saas, finance, general | 0 | canonical business-domain eligibility; add recruitment |
| Decisions.Domain | singleSelect: ייבוא, גיוס, שותפות, כללי, media | 0 | different Decision Hub taxonomy; untouched |

Additional domain-shaped fields `email_domain`, `actor_domain_id`, and
`actor_allowed_domains` are not business-domain fields and were not migrated.

## Required mutation preview

| Field | Current | Records affected | Proposed change | Rollback |
|---|---|---:|---|---|
| Marketing Demand.Domain | six canonical choices | 0 | add `recruitment` | restore six-choice list |
| TRAFFIC_SOURCES.Suitable Domains | six canonical choices | 0 | add `recruitment` | restore six-choice list |
| Business Memory.Domain | six legacy display choices | 0 | add `Recruitment` legacy storage choice | restore six-choice list |

No records require rewriting. Lead Events `recruiting` remains a read-compatible
legacy option because its record count is zero and removing it would shorten the
compatibility window without benefit.

## Compatibility and exceptions

- `domain_utils.py` accepts canonical and observed aliases and provides explicit
  `business_memory_legacy`, `venture_legacy`, and `decision_legacy` adapters.
- Marketing code files named in the brief (`marketing_gateway.py`,
  `marketing_domain_profiles.py`, `marketing_brief_composer.py`, and
  `cmd_marketing.py`) are absent from this worktree, so M1 code compatibility
  could not be runtime-checked here.
- No table, field, field type, unrelated option, or Decision vocabulary was
  changed.
