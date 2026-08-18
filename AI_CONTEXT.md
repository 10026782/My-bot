# AI CONTEXT

**עודכן:** 18/08/2026 · **origin/main:** `1c3d7fd` (6 PRs merged 17/08: #647–#651, #653 — all non-blocking changes, production verification pending)

> קרא אותי לפני כל דבר אחר. תדרוך תמציתי לא מלא.
> `ROADMAP.md` הוא מקור האמת הקנוני; `CHANGELOG.md`, `main` קודקוד קודמים.
> **"מוזג" ≠ "פרוס" ≠ "מאומת בפרודקשן."** בעל הבית מחזיק את פרטי השדה.

## 1. Executive Summary

- **CORE v1 — COMPLETE / READY TO FREEZE** (קנוני: `docs/audit/CORE_COMPLETION_AUDIT_20260810.md`). ללא שינוי.
- **Context Librarian CI — ירוק** (GitHub Actions verified; PR #651 owner-classification + PR #653 PR-time gate — שניהם ירוקים).
- **Production verifications עדיין פתוחים:** BUG-051-FU (router → Lead capture leakage, PR #647), BUG-164 (demand-fidelity, PR #649), Tool Catalog DB Phase 2 migration (PR #651 code-verified, runtime unverified).
- Bots operational (Telegram + WhatsApp/Twilio). Identity→Router→Context→Agent pipeline. ללא שינוי תפעולי.

## 2. Current System State

**✅ ללא תוספות מ-16/08/2026:**
- ActionGateway/ActionContract lifecycle, CORE v1 stack
- Context Librarian (post-merge + PR-time gates)
- F23 M1/M2 (Marketing Bridge) — ✅ verified in prod
- D1 (domain canonicalization)
- Tool Runtime Snapshot Phase 1

**🟡 Merged, not production-verified (3 items):**
1. **BUG-051-FU (PR #647):** Router now correctly routes `create_contact` intent to Contact flow instead of Lead capture. Catalog matching improved (Hebrew "ה-" normalization + Squoosh synonym). **Tests green, no production canary run yet.**
2. **BUG-164 demand-fidelity (PR #649):** Three free-text `compose_brief()` paths (`creative_review`, `ad_package`, `publishing_plan`) added prompt-level guardrails against factual distortion. **Deterministic path for `creative_ideas` already merged/verified (PR2, `e9d1ca8`). These three remain unverified against live AI output.**
3. **Tool Catalog DB Phase 2 (PR #651):** Phase 1 already live (dict-based snapshot); Phase 2 wires `business_tool_registry.list_tools()` to read from database layer instead. **Code + wiring verified; actual database migration execution in production unconfirmed.**

**🔵 Shadow/gated (no change):**
- TC7-B1, RP4/RP5 evidence shadow
- F52 audit maps

**⏸ Blocked (no change):**
- Formal `TurnCoordinator` class (Layer 2) — zero implementation, de-facto substituted by `router.py`
- BUG-161/BUG-162 (owner decision pending)

## 3. No New Completions Since 16/08/2026

Yesterday's PRs (#647–#651, #653) were all merged; no production canaries run this session.

## 4. Next Priorities (ordered by risk/verification debt)

1. **Enable & verify Lead Capture chain (N02–N04):** `LEAD_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY` all default-off in production. Code complete; no production verification. Enable in Render and test: WhatsApp unknown contact → Airtable Leads create → scoring → memory. Decision needed: all-or-phased activation.
2. **Verify BUG-051-FU production:** Router `create_contact` intent routing (not Lead capture). Merged PR #647; no production canary yet. Send test message, confirm Contact flow executed.
3. **Verify BUG-164 demand-fidelity production:** `compose_brief()` free-text guards (`creative_review`, `ad_package`, `publishing_plan`). Merged PR #649; deterministic path (`creative_ideas`) already verified. Prompt-level guardrails are best-effort, not gates.
4. **TMA Receipt Persistence (C40 gap):** Approval receipts returned but not displayed in Activity Feed. Blocks lead/deal/task completion workflows on Mini App.
5. **Update `ROADMAP.md`/`CHANGELOG.md`:** Both trail behind `1c3d7fd` (15/08 vs 18/08). ROADMAP `עודכן:` missing #647–#653; CHANGELOG "Unreleased" stale since 12/08.

---

**סטטוס-ו-הוכחה שנעשו ידנית:**
- **מוזג (git log):** `1c3d7fd` verified `origin/main` via GitHub API.
- **אומת בקוד:** PR #647/#649/#651/#653 read via `git show`, grep checks. No runtime trace.
- **אומת בפרודקשן:** NONE since yesterday — Context Librarian CI is PASS (governance, not functional).
