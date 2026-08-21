# CHANGE_CONTROL_LOG.md
> נכתב אוטומטית בכל merge ל-main. אל תערוך ידנית.

## פורמט רשומה

### [ID] — [שם השינוי]
- **תאריך:** 
- **סוג:** Feature / Bug Fix / Security / Schema Change / Hotfix
- **Requirement:** [קישור ל-ROADMAP item]
- **Commit:** [hash]
- **PR:** [מספר/קישור]
- **Review על ידי:** 
- **Deploy תאריך:** 
- **Verified בפרודקשן:** כן / לא / לא רלוונטי
- **Verification ראיה:** [מה נבדק, מה התוצאה]
- **Docs עודכנו:** ROADMAP / CURRENT_STATE / AI_CONTEXT / אחר
- **Feature Flag:** [שם / N/A]
- **Rollback plan:** [אם רלוונטי]

---

## לוג שינויים

> נבנה מ-`git log --since="30 days ago"` (~172 commits, `f935c53`→`eebf73b`) + טבלאות ROADMAP.md (Stabilization Sprint, World 2, Sprint 16/06). כל commit hash צוטט ישירות מ-git או מ-ROADMAP — שורות שלא נמצאה להן ראיה ישירה מסומנות "לא ידוע".

### OC-HYGIENE-SESSION-18AUG — Command Center Data Hygiene Audit + Runtime Fixes + Compact UI (session 18-19/08/2026, 6 deliverables, 4 merged + 2 Draft)
- **תאריך:** 18-19/08/2026
- **סוג:** Feature (UI), Bug Fix (3x), Governance (Context Librarian registration), Infrastructure (CI budget)
- **Requirement:** owner-initiated review of Command Center data accuracy + System Health fix + Approvals read-model + UI compaction
- **Merged PRs:**
  - #722 (Data Hygiene Audit, task A) — `76bfa54` — ביקורת מלאה של כל סעיפי Command Center, זיהוי TRUSTED/PARTIAL/STALE/UNSUPPORTED/MISLEADING
  - #727 (System Health Runtime Fix, task B) — `3e10dbc` — תיקון TypeError: system_health() got multiple values for argument 'identity' (decorator collision)
  - #732 (Approvals Read-Model Alignment, task C) — `55ac3db` — הוספת actionable/legacy_read_only fields, TTL-blindness fix ב-projection
  - #741 (Context Librarian budget overflow fix) — `9745578` — הגדלת approval_ux task budget 9520→10200 tokens
- **Draft PRs (green CI):**
  - #738 (Command Center UI Cleanup, task D) — `610809e` (after main sync) — compact dedupe initiatives, expand-on-demand details, hidden unsupported sections (Business Status, Recent Activity)
  - #739 (overall_state semantics, decision 2) — `535ac4d` (after main sync) — unsupported optional sections no longer trigger PARTIAL downgrade
- **Review על ידי:** —
- **Deploy תאריך:** merged PRs (722/727/732/741) deployed with PR #744 merge-into-main sync; draft PRs (738/739) awaiting owner review
- **Verified בפרודקשן:** #722/#727/#732/#741 merged to main, CI green; #738/#739 Draft, CI green after sync with #741 budget fix
- **Verification ראיה:** test_command_center.py 12/12 (all sessions), test_owner_attention.py 26/26 (all sessions), test_owner_development.py 12/12 (#739 session), smoke_tests.py all pass, Context Librarian validate/reconcile-pr CLEAN on all PRs
- **Files שונו:** 
  - PR #722: audit-only, no code changes
  - PR #727: tma_api.py (new `_system_health_payload()` helper), core/owner_attention.py, test_owner_attention.py (+4 tests)
  - PR #732: tma_api.py, core/owner_attention.py, tma-frontend/src/types.ts, tma-frontend/src/components/Approvals.tsx, test_phase_4b2_wiring.py (+1 test), test_owner_attention.py (+2 tests)
  - PR #741: docs/context_librarian/task_profiles/profiles.json (1 line budget bump)
  - PR #738: tma-frontend/src/lib/commandCenterPresentation.ts (new), test files, context_librarian catalog (+1 node)
  - PR #739: core/command_center.py (`_is_unsupported_placeholder()`, `_overall_state()` logic update), test_command_center.py (2 tests updated, 1 new)
- **Docs עודכנו:** BUG_AUDIT_LOG.md (new bugs/fixes), CHANGE_CONTROL_LOG.md (this entry)
- **Feature Flag:** N/A (no new flags)
- **Rollback plan:** each PR independent; revert by PR number if needed. Infrastructure fix (#741) is prerequisite for clean CI on #738/#739.

### BUG-071-LOCATION-MOVE — move WhatsApp media adapters from providers/ to root (structural fix for F12/F13 quarantine)
- **תאריך:** 05/07/2026
- **סוג:** Refactoring (structural only, zero behavior change)
- **Requirement:** BUG-071 (WhatsApp media support) — avoid placing live code under `providers/` folder which is quarantined pending F12/F13 overlap resolution (ROADMAP.md §F13, CLAUDE.md §providers). Root placement aligns with convention of live integrations (`media_handler.py`, `cmd_update.py`).
- **Commit:** (ייקבע לאחר אישור)
- **PR:** (תמתין ל-merge של BUG-071 PR)
- **Review על ידי:** —
- **Deploy תאריך:** סה"כ עם BUG-071
- **Verified בפרודקשן:** לא עדיין (ממתין למיזוג)
- **Verification ראיה:** smoke_tests.py ✅ | test_whatsapp_media.py (6/6) ✅ | test_bug070_pending_approval_multi.py (9/9) ✅
- **Files רזומנו:** providers/whatsapp_media_adapter.py → whatsapp_media_adapter.py; providers/meta_whatsapp_media_adapter.py → meta_whatsapp_media_adapter.py; app.py (3 imports); test_whatsapp_media.py (6 imports)
- **Docs עודכנו:** BUG_AUDIT_LOG.md
- **Feature Flag:** לא רלוונטי
- **Rollback plan:** `git revert` + revert imports

### F52-STAGE1 — Safe Refactors: static audits (#6/#7) + shadow tool-result recorder (#4)
- **תאריך:** 03/07/2026
- **סוג:** Feature (audit tooling, additive-only, zero behavior change)
- **Requirement:** `docs/architecture/f52-unified-approval-runtime/audits/original/F52_CURRENT_TOOL_MAP.md` §"Safe No-Brainer Refactors" #4, #6, #7.
- **Commit:** `0695b11`, `2ae6b0c`
- **PR:** #207 — מוזג (`22b2f74`)
- **Review על ידי:** —
- **Deploy תאריך:** —
- **Verified בפרודקשן:** לא
- **Verification ראיה:** Pre-implementation gate (§0 of the task SPEC) re-ran the F52 audit greps against the live repo and found the SPEC's claimed baseline did not match reality on either #6 or #7: `cmd_decision.py:806` has no `httpx` call at all (goes through `airtable_create`); `tools/telegram_adapter.py`/`app.py`/`google_tools.py`/`email_inbound.py`/`knowledge_engine.py`/`survey_worker.py` contain none of the `"✅" in result`/`rec\w+` anti-pattern (telegram_adapter.py already uses a structured `ActionResult`/`delivery_success` bool). Corrected baselines were derived by actually running the new scanners against the repo and cross-checking against `docs/architecture/f52-unified-approval-runtime/audits/original/F52_BYPASS_MAP.md`. `tools/audit_gateway_bypass.py` (24 known Airtable-bypass call-sites, 2 write/22 read) and `tools/audit_result_parsing.py` (21 known false-success text-parsing occurrences across 12 files) both self-test clean and report 0 new / 0 resolved against their baselines on the current repo. `core/last_tool_result_shadow.py` (RAM-only, TTL-bounded dataclass recorder) wired passively into `tools/dispatcher.py`'s existing `finally:` clause (source=`agent_tool`) and `tma_api.py`'s `_at_patch`/`_at_post` (source=`tma_route`) — manually verified with the flag on vs off that `dispatch_tool()`'s return value is byte-identical either way. `FEATURE_LAST_TOOL_RESULT_SHADOW` confirmed default-off (not in `feature_flags._DEFAULTS`). All 30+ `test_*.py` scripts, `smoke_tests.py`, `test_integration.py`, and `core/router/test_router.py` pass unchanged; `python -m compileall -q .` clean. Zero `app.py` changes. Both new audit scripts added to `.github/workflows/ci.yml` as warning-only steps (`|| true`), matching the existing `schema_governance.py` pattern.
- **Docs עודכנו:** feature_flags.py (registry docstring), CHANGE_CONTROL_LOG (this entry)
- **Feature Flag:** `FEATURE_LAST_TOOL_RESULT_SHADOW` (new, default OFF)
- **Rollback plan:** revert the branch; all three additions (2 audit scripts + shadow recorder module) are new files or additive call-sites behind a default-off flag — no existing behavior depends on them.

### GOV-PLANNING-GATE-CONSOLIDATION — PLANNING_GATE.md: single 8-question gate + Rule 00
- **תאריך:** 03/07/2026
- **סוג:** Docs (governance, no code)
- **Requirement:** user-directed consolidation of `docs/governance/PLANNING_GATE.md`.
- **Commit:** `1cae175` (8-question gate consolidation), plus this session's Rule 00 addition
- **PR:** #208 — מוזג (`f145fd3`)
- **Review על ידי:** —
- **Deploy תאריך:** לא רלוונטי (docs-only)
- **Verified בפרודקשן:** כן — `grep` על `main` מאשר "שערי חובה — 8 שאלות" קיים, "שלוש השאלות"/"בדיקת התנגשות כלים" הישנים נעלמו.
- **Verification ראיה:** `git log -1 --format="%H" main` = `f145fd3ab7e010c226ecc027b3f4d34c181fb9ce` בזמן המיזוג; grep ישיר על הקובץ אחרי sync.
- **Docs עודכנו:** `docs/governance/PLANNING_GATE.md`
- **Feature Flag:** לא רלוונטי
- **Rollback plan:** docs-only, revert trivial אם נדרש.

### F52-BYPASS-GAPFILL-BUG055 — F52_BYPASS_MAP.md gap-fill (cmd_decision.py:700) + BUG-055 claim correction
- **תאריך:** 03/07/2026
- **סוג:** Docs (governance correction, no code)
- **Requirement:** C89/F52 scope-verification thread — items ה (missing bypass-map entry) ו-ג (unverified "+3 more" claim).
- **Commit:** `ce2ea76` — ישיר ל-`main` (docs-only, לפי בקשה מפורשת, ללא PR נפרד)
- **PR:** לא רלוונטי (direct commit)
- **Review על ידי:** —
- **Deploy תאריך:** לא רלוונטי
- **Verified בפרודקשן:** כן
- **Verification ראיה:** `main @ ce2ea76` — `F52_BYPASS_MAP.md:132` מכיל את שורת `cmd_decision.py`; `BUG_AUDIT_LOG.md` מכיל BUG-055.
- **Docs עודכנו:** `docs/architecture/f52-unified-approval-runtime/audits/original/F52_BYPASS_MAP.md`, `BUG_AUDIT_LOG.md`
- **Feature Flag:** לא רלוונטי
- **Rollback plan:** docs-only.

### FIX-DRIVE-SHEETS-MERGE — orphaned branch merge: BUG-DRIVE-READ-UNSUPPORTED-CONVERSION + BUG-SHEETS-SEARCH-STATUS
- **תאריך:** 03/07/2026
- **סוג:** Bug Fix
- **Requirement:** C89/F52 scope-verification table, item א — orphaned unmerged branch `claude/fix-drive-sheets-conversion` predating this session, rebased cleanly onto current `main` and merged.
- **Commit:** `7c846c6` (rebased), merge `fe713d8`
- **PR:** #209 — מוזג
- **Review על ידי:** —
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** כן (merge-level; אין live Airtable/Drive verification מהסביבה הזו)
- **Verification ראיה:** `main @ fe713d82a733d9721697c3f8065b9f26c0368abc` — grep מאשר שתי התיקונים ב-`tools/google_tools.py` (שורות 251, 261). `python3 test_drive_sheets_fixes.py` 3/3.
- **Docs עודכנו:** —
- **Feature Flag:** לא רלוונטי
- **Rollback plan:** revert commit, scope מוגבל ל-`tools/google_tools.py`.

### FIX-UNIFY-LLM-FALLBACK-FLAG — llm_fallback.py reads feature_flags.LLM_FALLBACK
- **תאריך:** 03/07/2026
- **סוג:** Bug Fix (governance drift — two independent flags for one feature)
- **Requirement:** C89/F52 scope-verification table, item ד.
- **Commit:** `f15a435`
- **PR:** #210 — מוזג (`cec461c`)
- **Review על ידי:** —
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** כן
- **Verification ראיה:** `main @ cec461c` — `grep -c "OPENAI_FALLBACK_ENABLED" llm_fallback.py` → 0; `grep -n "is_enabled(\"LLM_FALLBACK\")" llm_fallback.py app.py` → שני sites. Manual check: flag unset → `False`; `set_flag("LLM_FALLBACK", True)` → `True`.
- **Docs עודכנו:** —
- **Feature Flag:** `LLM_FALLBACK` (existing, unified — no new flag)
- **Rollback plan:** revert commit; `call_anthropic_text`'s fallback logic itself untouched.

### FEAT-OUTPUT-GATEWAY-SHADOW-RECORD — passive shadow record in output_gateway._execute_send
- **תאריך:** 03/07/2026
- **סוג:** Feature (F52 #4 follow-up, additive, flag-off)
- **Requirement:** F52 Stage 1 "chokepoint" gap — `send_outbound()` callers (`app.py`, `followup_engine.py`, `payment_reminder.py`, `providers/twilio_shim.py`) never went through `tools/dispatcher.py`, so the shadow recorder had zero visibility into any outbound send.
- **Commit:** `7bf3bd6`
- **PR:** #212 — מוזג (`02c03ac`)
- **Review על ידי:** —
- **Deploy תאריך:** לא רלוונטי (flag-off)
- **Verified בפרודקשן:** כן
- **Verification ראיה:** `main @ 02c03ac` — grep מאשר `_shadow_record_send`/`last_tool_result_shadow` ב-`core/output_gateway.py`. `git diff` על `app.py`/`core/action_gateway.py` בין הbase לbase החדש — ריק (לא נגעו). Manual check: `GatewayResult` זהה bit-for-bit עם/בלי הדגל.
- **Docs עודכנו:** —
- **Feature Flag:** `FEATURE_LAST_TOOL_RESULT_SHADOW` (existing, extended — no new flag)
- **Rollback plan:** revert commit; scope מוגבל ל-`core/output_gateway.py`.

### FEAT-DRIVE-READ-CONVERTER-FALLBACK — drive_read_file falls back to document_converter
- **תאריך:** 03/07/2026
- **סוג:** Feature (wires the previously-dormant `document_converter` package into production for the first time)
- **Requirement:** SPEC 2 (Document Converter) — after 5 rounds of Rule-00-style contract-chain verification against the live repo caught and fixed 5 defects in the original SPEC draft before it reached approval (see `docs/governance/PLANNING_GATE.md` Rule 00 provenance note).
- **Commit:** `e8570a6`
- **PR:** #213 — מוזג (`b9de424`)
- **Review על ידי:** —
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** כן
- **Verification ראיה:** `main @ b9de424` — grep מאשר `_MIME_TO_TYPE`/`convert_document`/`output_path.unlink` ב-`tools/google_tools.py`. `python3 test_google_tools.py` 5/5 (כולל round-trip אמיתי עם `python-docx`, לא מדומה ברמת ה-conversion). `git diff --stat main` מוגבל ל-`tools/google_tools.py` + `test_google_tools.py` בלבד — `document_converter/*`/`drive_adapter.py`/`media_handler.py`/`cmd_decision.py`/`decision_pipeline.py` לא נגועים.
- **Docs עודכנו:** —
- **Feature Flag:** לא רלוונטי (אין flag — תיקון התנהגות תמידי בפונקציה קיימת)
- **Rollback plan:** revert commit; scope מוגבל ל-`tools/google_tools.py` + test חדש.

### BUG-051-CAPTURE-ROUTER — Capture Policy: Router-integrated, LCH moved post-Router
- **תאריך:** 02/07/2026
- **סוג:** Bug Fix (RouteDecision extended additively — 3 new optional fields, no breaking change)
- **Requirement:** ROADMAP.md §C89 update + `BUG_AUDIT_LOG.md` BUG-051. `core.lead_candidate_handler.handle_lead_candidate()` ran before `route_request()` for every internal-sender message (`app.py` old step "1.45") — the Router (Identity→Router→Context→Agent) never executed for those turns, and domain was guessed by an internal regex mirror of `domain_router` instead of the real thing.
- **Commit:** (ייקבע ב-push)
- **PR:** טרם נפתח (branch `feature/capture-policy-stage-3`)
- **Review על ידי:** —
- **Deploy תאריך:** —
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `RouteDecision` gained `capture_tier: int|None`, `capture_reason: str`, `raw_ref: str` (all optional, default None/""). New `core/router/capture_router.py` wraps the existing `core.ingress_classifier.classify_ingress()` (no reimplementation, no airtable/drive/gateway imports — verified by `test_capture_router_wiring.py::test_capture_router_no_infra_imports`). `app.py`'s pre-Router LCH call removed; new call added after `route_request()` returns, passing `domain=resolved_route_domain` into a new optional `domain` param on `handle_lead_candidate()` (default `""`, falls back to the old `_detect_domain()` guess — backward compatible, only 1 line + 1 param changed in an 813-line file). 10/10 new tests, 29/29 `core/router/test_router.py`, 4/4 `test_integration.py`, all 30 repo `test_*.py` scripts green. No live Airtable/Gateway/Render verification (sandbox).
- **Docs עודכנו:** ROADMAP (§C89), BUG_AUDIT_LOG (BUG-051), AI_CONTEXT
- **Feature Flag:** `FEATURE_AUTO_CAPTURE` (unchanged, still off by default — this change only affects *when* LCH runs and what domain it receives, not the flag-gated write-vs-preview behavior itself)
- **Rollback plan:** revert the branch; `RouteDecision`'s 3 new fields and `handle_lead_candidate()`'s new `domain` param are additive/optional, so a partial revert of just `app.py`'s call-site move (restoring the pre-Router short-circuit) would also be safe in isolation if needed.

### F22-WIRE-29062026 — Decision Hub Stage 6: wire decision_adapter as orchestrator fallback
- **תאריך:** 29/06/2026
- **סוג:** Feature (wiring of already-merged F22 code, no new logic added)
- **Requirement:** ROADMAP.md F22 — "Core Reasoning Layer" was merged 28/06/2026 with zero live
  call sites (governance drift documented in GOV-29062026 below). This entry closes that gap for
  `core.adapters.decision_adapter` specifically (`leads_adapter` remains intentionally unwired).
- **Commit:** (ייקבע ב-push לענף `claude/new-session-be1ckb`)
- **PR:** טרם נפתח
- **Review על ידי:** —
- **Deploy תאריך:** —
- **Verified בפרודקשן:** לא
- **Verification ראיה:** המשתמש העלה `cmd_decision_1.py` בטענה ש"11 שורות diff בלבד, השאר
  \r\n". אומת ע"י `diff <(tr -d '\r' < upload) cmd_decision.py` שהטענה שגויה — ההעלאה התבססה
  על גרסה ישנה של `cmd_decision.py`, חסרה Stage 2 (`_format_confidence_block`)/Stage 3
  (`_format_readiness_block`)/`decision_matching` module — לא הוחל verbatim. במקום זאת בוצע
  שינוי ממוקד ב-`_format_decision_card()` (cmd_decision.py:434-449 הנוכחי): קריאה ל-
  `append_reasoning_block()` **רק כש-`FEATURE_DECISION_HUB` כבוי** — `orchestrator_block`
  (F21, Stage 4/5) ו-`reasoning_block` (Stage 6) מציגים את אותו מידע בעיקרם (state, confidence
  bar, צעד הבא, אחראי); הצגת שניהם יחד נמצאה ע"י בדיקת `format_orchestrator_card()` מול
  `DecisionAdapter.from_result()` כיוצרת כפילות ויזואלית, לא ערך מוסף — הוחלט מול המשתמש דרך
  `AskUserQuestion` (אופציה "reasoning_block רק כש-orchestrator מבוטל"). `python3 -m py_compile
  cmd_decision.py` נקי; `test_decision_confidence.py` 28/28; `test_decision_readiness.py` 25/25;
  `smoke_tests.py::check_decision_hub_call_sites` עודכן (`core.adapters.decision_adapter` →
  `expected_wired=True`) ועובר (7/7 entrypoints תואמים).
- **Docs עודכנו:** ROADMAP.md (F22 — עדכון מצב חיווט), smoke_tests.py (manifest entry),
  CHANGE_CONTROL_LOG.md (רשומה זו)
- **Feature Flag:** `FEATURE_DECISION_HUB` — ללא שינוי בדגל עצמו; ה-fallback רץ **רק כשהדגל כבוי**
- **Rollback plan:** הסרת בלוק ה-Stage 6 מ-`cmd_decision.py._format_decision_card()` (try/except
  עצמאי, אין side effect חוץ מהוספת טקסט לכרטיס) + שינוי `expected_wired` בחזרה ל-`False` ב-
  `smoke_tests.py`

---

### GAP-29062026 — Git Diff Gap Report: undocumented merges + Safe Document Converter stale status
- **תאריך:** 29/06/2026
- **סוג:** Documentation / Governance — תיקון תיעוד בלבד, **ללא שינוי התנהגות בפרודקשן**
- **Requirement:** `SPEC_GIT_DIFF_GAP_FINDER.md` — לגלות מה השתנה ב-`main` שלא תועד ב-ROADMAP/AI_CONTEXT/CHANGE_CONTROL_LOG
- **Commit:** (ייקבע ב-push לענף `claude/new-session-be1ckb`)
- **PR:** טרם נפתח
- **Review על ידי:** —
- **Deploy תאריך:** לא רלוונטי (תיעוד בלבד)
- **Verified בפרודקשן:** לא רלוונטי
- **Verification ראיה:** `git log origin/main --since="5 days ago" --diff-filter=A/M --name-only`
  השווה מול ROADMAP/AI_CONTEXT/CHANGE_CONTROL_LOG. נמצאו 2 commits מוזגים ל-`main` ב-29/06/2026
  בלי שום תיעוד:
  - `4e1d7ed` "Wire lead capture evidence into A32" (PR #171) — `_action_result_to_a32_entry()`
    ב-`app.py`, ממירה `ActionResult`/`ClaimType` של lead_capture ל-רשומת A32
    `tool_results_log` (FOUND≠CREATED). קריאה אמיתית מאומתת: `app.py:1124`.
  - `257a5e4` "Fix safe lead metadata patch" (PR #172) — `capture_lead_event()` ב-`lead_capture.py`,
    כותבת ל-`Tables.LEAD_EVENTS` כש-ליד קיים (FOUND) שולח הודעה חדשה; לא דורסת/יוצרת ליד.
    קריאה אמיתית מאומתת: `lead_capture.py:215`.
  שני אלה **מחוברים בפועל** (caller אמיתי) — MISSING_FROM_DOCS, לא EXISTS_UNWIRED/MISSING קוד.
  בנוסף נמצא: ROADMAP.md §"Fxx — Safe Document Converter" היה כתוב "Not merged to main" כש
  בפועל מוזג מ-26/06/2026 (PR #158, `db719ab`) — תוקן ל"מוזג אך לא מחובר" (EXISTS_UNWIRED,
  pattern F20/F22; אפס caller ל-`convert_document()` מעבר ל-`test_document_converter.py`).
  ממצא נוסף תוך כדי בדיקה: `test_document_converter.py` (סגנון `pytest`, בלי `__main__` guard)
  רץ ב-CI דרך `python "$f"` (לא `pytest`) — מבצע 0 assertions בפועל (exit 0) אף שמתועד כ-"6/6
  passing"; אומת ש-6/6 עובר אמיתי רק דרך `python3 -m pytest test_document_converter.py` ישירות.
  לא תוקן בקוד — מחוץ ל-scope (אין שינוי קוד לפי כללי הספק); תועד כממצא פתוח.
  דוח מלא: `reports/gap_report_29jun2026.md`.
- **Docs עודכנו:** ROADMAP.md (entry חדש + תיקון סטטוס Fxx), CHANGE_CONTROL_LOG.md (רשומה זו),
  AI_CONTEXT.md (main pointer, אזכור הממצאים)
- **Feature Flag:** לא רלוונטי — שום flag לא שונה
- **Rollback plan:** לא רלוונטי — אין שינוי קוד התנהגותי, תיעוד בלבד

---

### GOV-29062026 — Governance Repair: F20/Core Reasoning Layer call-site drift
- **תאריך:** 29/06/2026
- **סוג:** Documentation / Governance — תיקון תיעוד וגארד, **ללא שינוי התנהגות בפרודקשן**
- **Requirement:** תיקון סטיית governance ממצא 27/06/2026 (F20 "feature file exists but has zero call sites")
- **Commit:** (ייקבע ב-push לענף `claude/new-session-be1ckb`)
- **PR:** טרם נפתח
- **Review על ידי:** —
- **Deploy תאריך:** לא רלוונטי (תיעוד + smoke test בלבד)
- **Verified בפרודקשן:** לא רלוונטי
- **Verification ראיה:** grep מלא על הריפו אישר ש-`decision_auto_ingestion.py` (F20) ושכבת
  Core Reasoning Layer (`core/reasoning_engines.py`, `reasoning_entity.py`, `reasoning_ports.py`,
  `core/adapters/decision_adapter.py`, `core/adapters/leads_adapter.py` — **לא היו מתועדים
  בכלל לפני זה**) אין להם קריאה מאף entrypoint חי. `decision_attention.py` (F19),
  `decision_orchestrator.py` (F21), ו-`decision_matching.py` כן מחוברים (אומת דרך
  `cmd_decision.py`). נוסף `smoke_tests.py::check_decision_hub_call_sites` (AST-based,
  משווה manifest מוצהר מול גרף import אמיתי מתוך entrypoints חיים בלבד) — עובר.
  `py_compile` נקי; כל סוויטות הבדיקה הרלוונטיות (`test_core_reasoning.py` 59/59,
  `test_decision_orchestrator.py` 13/13, `test_decision_auto_ingestion.py` 18/18,
  `test_decision_attention.py` 11/11, `test_cxx_action_integrity.py` 6/6,
  `test_decision_confidence.py` 28/28, `test_decision_readiness.py` 25/25,
  `test_integration.py` 4/4) עברו, אין רגרסיה. נסיון אימות Airtable חי דרך Airtable MCP
  (`search_bases`/`list_tables_for_base`/`get_table_schema`) נחסם בסשן הזה ("MCP tool call
  requires approval" על כל קריאה) — `schema_cache.json` נשאר `seed-from-schema-py`,
  לא נערך/נמחק (תקדים BUG_AUDIT_LOG FLAGGED).
- **Docs עודכנו:** ROADMAP.md (F20 downgrade note + F22 חדש), AI_CONTEXT.md (§0 חדש,
  main pointer `b289ab6`→`6b20028`), CHANGE_CONTROL_LOG.md (רשומה זו)
- **Feature Flag:** `FEATURE_DECISION_HUB`/`FEATURE_DECISION_AUTO_INGESTION` — נשארים כבויים;
  לא נשנו ולא הוחלט להדליק
- **Rollback plan:** לא רלוונטי — אין שינוי קוד התנהגותי, רק תיעוד + smoke test נוסף

---

### CXX — Action Integrity cleanup and DOC upload reconciliation
- **תאריך:** 29/06/2026
- **סוג:** Bug Fix / File Hygiene / Contract Wiring
- **Requirement:** reconcile `DOC-20260628-WA*.py`, restore the adapters package, and add minimal CXX regression coverage
- **Commit:** `46d470b`
- **PR:** #169 — draft, לא מוזג
- **Deploy תאריך:** לא בוצע
- **Verified בפרודקשן:** לא
- **Verification ראיה:** branch מבוסס `origin/main@ca1f5a0`; mirror מקומי של backend CI עבר: compileall, smoke tests, core imports וכל 19 קובצי `test_*.py`, כולל CXX ‏6/6. GitHub Actions run `28337822793` עבר: backend-ci ו-frontend-ci ירוקים; Vercel preview עבר.
- **Docs עודכנו:** ROADMAP.md, CHANGE_CONTROL_LOG.md
- **Feature Flag:** ללא שינוי
- **Rollback plan:** revert commit/PR; אין שינוי schema או נתונים

---

### Decision Hub Stages 1–6 — consolidated merge ledger
- **תאריך עדכון:** 28/06/2026
- **סוג:** Documentation / status reconciliation בלבד — ללא שינוי קוד או התנהגות
- **Requirement:** ROADMAP.md §N13, §F17–§F21

| Stage | יכולת | PR | Commit / Merge | בדיקות | מצב |
|---|---|---|---|---|---|
| 1 | Trust Layer | #151 | `73f6fe8` / `b289ab6` | 33/33 | מוזג ל-`main`; Production Verified: לא |
| 2 | Smart Trust / Confidence | #157 | `9252b1e` / `78f9bae` | 28/28 | מוזג ל-`main`; Production Verified: לא |
| 3 | Readiness Engine | #159 | `84cfcff` / `50f6351` | 25/25 | מוזג ל-`main`; Production Verified: לא |
| 4 | Attention Engine | #161 | `3e79a03`, `1281dda` / `fb4d041` | 11/11 | מוזג ל-`main`; Production Verified: לא |
| 5 | Auto Ingestion | #162–#164 | `9b97319` / `8f58634`; `bbea097` / `ebf0261`; `22eae2e` / `076fb0c` | 18/18; Confidence 28/28 | מוזג ל-`main`; Production Verified: לא |
| 6 | Lifecycle Orchestrator | #166 | `9011923` / `2c55c59` | 13/13 | מוזג ל-`main`; Production Verified: לא |

- **Verification ראיה:** כל מזהי ה-commit/merge לעיל קיימים בהיסטוריית git; סך בדיקות Decision Hub ‏128/128. עבור Stage 6 בוצעו גם post-merge sync ו-grep פיזי ב-`main` לפי AGENTS.md.
- **Deploy תאריך:** לא אומת ידנית
- **Verified בפרודקשן:** לא — הרשומה מאמתת merge ובדיקות בלבד
- **Feature Flags:** `FEATURE_DECISION_HUB` ו-`FEATURE_DECISION_AUTO_INGESTION` כבויים כברירת מחדל
- **Docs עודכנו:** ROADMAP.md, CHANGE_CONTROL_LOG.md

---

### F21 — Decision Hub Stage 6: Lifecycle Orchestrator
- **תאריך:** 28/06/2026
- **סוג:** Feature — read-only, מאחורי `FEATURE_DECISION_HUB` הכבוי כברירת מחדל
- **Requirement:** Decision Hub Stage 6 lifecycle: `COLLECTING`→`BLOCKED`→`REVIEW`→`AWAITING`→`DECIDED`→`CLOSED`
- **תיאור:** נוסף `decision_orchestrator.py` עם `OrchestratorResult`, ניתוב first-match ו-render ל-Telegram. Stage 6 משתמש ב-`ConfidenceResult` המחושב ב-Stage 2; fallback דטרמיניסטי עם `conflicts=[]`, ללא AI conflict detection חדש. `cmd_decision.py` מעביר readiness עדכני ב-snapshot לא-מוטטיבי ו-fail-open שומר על הכרטיס הבסיסי.
- **Commit:** `9011923`
- **PR:** #166 — מוזג ל-`main` (merge commit `2c55c59`)
- **Review על ידי:** הבעלים; PR נבדק כ-commit אחד/3 קבצים/ללא Markdown לפני המיזוג
- **Deploy תאריך:** לא אומת ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** Stage 6 ‏13/13; Decision Hub ‏128/128; post-merge sync + grep פיזי על `OrchestratorResult`, `orchestrate`, `append_orchestrator_to_card` והחיווט ב-`cmd_decision.py`
- **Docs עודכנו:** ROADMAP.md, CHANGE_CONTROL_LOG.md (ב-PR תיעוד נפרד לאחר המיזוג)
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל
- **Rollback plan:** revert merge commit `2c55c59`; השינוי מבודד ל-3 קבצים ואינו כותב state חדש

### F20 — Decision Hub Stage 5: Auto Ingestion
- **תאריך:** 27/06/2026
- **סוג:** Feature — raw-first Inbox ingestion, מאחורי דגל כבוי
- **Requirement:** Decision Hub Stage 5 Auto Ingestion
- **תיאור:** ניתוב WhatsApp/email/document/voice ל-Decision Inbox בלבד; matcher משותף; missing-evidence penalty ל-confidence. אין כתיבה אוטומטית ל-Decision canonical.
- **Commit:** `9b97319` / `bbea097` / `22eae2e`
- **PR:** #162 (merge `8f58634`) / #163 (merge `ebf0261`) / #164 (merge `076fb0c`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא אומת ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** שלושת ה-commits ancestors של main; grep פיזי; Auto Ingestion ‏18/18 ו-Confidence ‏28/28
- **Docs עודכנו:** ROADMAP.md, CHANGE_CONTROL_LOG.md (נוסף בדיעבד לאחר אימות המיזוגים)
- **Feature Flag:** `FEATURE_DECISION_AUTO_INGESTION` — כבוי כברירת מחדל
- **Rollback plan:** revert merges #162–#164 לפי הסדר ההפוך

### F19 — Decision Hub Stage 4: Attention Engine
- **תאריך:** 27/06/2026
- **סוג:** Feature — read-only priority calculation, מאחורי דגל כבוי
- **Requirement:** Decision Hub Stage 4 Attention Engine
- **תיאור:** `decision_attention.py` + policy נפרד; דירוג דטרמיניסטי של החלטות לפי readiness, deadline, לחץ עם שינוי, שינויי עמדה, חוסר פעילות ומידע חסר. אין sender/writer או פעולה אוטומטית.
- **Commit:** `3e79a03` / `1281dda`
- **PR:** #161 — מוזג ל-`main` (merge commit `fb4d041`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא אומת ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `test_decision_attention.py` ‏11/11; הקבצים והפונקציות קיימים ב-main
- **Docs עודכנו:** ROADMAP.md, CHANGE_CONTROL_LOG.md (נוסף בדיעבד לאחר אימות המיזוג)
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל
- **Rollback plan:** revert PR #161

### F18 — Decision Hub Stage 3: Readiness Engine
- **תאריך:** 26/06/2026
- **סוג:** Feature — אחורה כבוי דגל (`FEATURE_DECISION_HUB`), אפס שינוי התנהגות בפרודקשן
- **Requirement:** SPEC "Decision Hub Stage 3: Readiness Engine" (PLANNING_GATE + SPEC מלא, הועלה ע"י הבעלים) — ROADMAP.md §F18
- **תיאור:** קובץ חדש `decision_readiness.py` — `calc_readiness(decision, events, confidence_result) -> ReadinessResult`, `build_readiness_message(result) -> str`, `detect_escalation(decision, result) -> list[str]`. `ReadinessResult.status` ∈ {READY, NOT_READY, REVIEW}; READY הוא איתות בלבד להכרעה אנושית — אינו מבצע פעולה. מקבל את `ConfidenceResult` המחושב כבר ב-Stage 2 (אין חישוב כפול/קריאת AI Conflict Detection כפולה). 8 חוקי הספק + 3 הספים + 4 תבניות escalation (עו"ד/רו"ח-יועץ פיננסי/עמדת שותף/מסמך תומך) מיושמים כלשונם.
- **SoA (MODULE_RULES):** `DecisionFields.READINESS` ו-`class DecisionReadiness` (READY/NOT_READY) **היו קיימים מראש** ב-`airtable_schema.py` — נבדק לפני כתיבת קוד חדש. הורחב (לא שוכפל) עם ערך `REVIEW` חדש (לא מאומת כאופציית singleSelect חיה ב-Airtable). `detect_missing_evidence()` הקיים מ-Stage 2 נקרא ישירות.
- ⚠️ **1 סטייה מהטקסט המילולי של הספק:** "Stakeholders if available" מופיע ב-Inputs של הספק, אך חתימת `detect_escalation(decision, result)` כפי שהוגדרה במפורש בספק לא מקבלת `events`/stakeholders. escalation של "עמדת שותף" (partner-disagreement) מזוהה לכן רק דרך אות עקיף — קונפליקט פתוח שמופיע ב-`result.blockers` — לא דרך ניתוח Stakeholder records ישיר.
- **Daily Digest hook (ספק §4):** נבדק `daily_digest.py` — אין אזכור Decision Hub, אין נקודת חיבור קיימת. דולג, לפי האופציונליות המפורשת של הספק.
- **Commit:** `84cfcff`
- **PR:** #159 — מוזג ל-`main` (merge commit `50f6351`), אומת עצמאית דרך `mcp__github__pull_request_read` (`merged:true`, `merged_at: 2026-06-26T11:51:28Z`) + `git fetch origin main` + `git merge-base --is-ancestor 84cfcff origin/main`. ענף המקור `claude/new-session-be1ckb` נמחק מה-remote אחרי המיזוג.
- **Review על ידי:** הבעלים (אישור "Yes, implement now" דרך `AskUserQuestion` על ספק מלא; מיזוג בוצע ע"י הבעלים)
- **Deploy תאריך:** לא אומת — אין גישת Render dashboard/egress מה-sandbox; מוזג ל-`main` אך פריסה בפועל ל-Render לא אומתה
- **Verified בפרודקשן:** לא — מוזג ל-`main`, אך דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל ופריסה לא אומתה מה-sandbox
- **Verification ראיה:** `py_compile` נקי על `decision_readiness.py`/`cmd_decision.py`/`airtable_schema.py`/`test_decision_readiness.py`; `test_decision_readiness.py` 25/25 (6 ה-cases מהספק + מקרי גבול); `test_decision_confidence.py` 25/25 ו-`test_decision_trust.py` 33/33 ללא רגרסיה; `smoke_tests.py` — אותם 2 כשלים קיימים מראש (`flask`/`httpx` חסרים בסביבה), אין כשלים חדשים
- **Docs עודכנו:** ROADMAP.md (סעיף F18 חדש + header עודכן + top-of-file entry), CHANGE_CONTROL_LOG.md (רשומה זו, עודכנה בדיעבד עם נתוני המיזוג המאומתים)
- **Feature Flag:** `FEATURE_DECISION_HUB` (כבוי כברירת מחדל)
- **Rollback plan:** מחיקת `decision_readiness.py` + revert ל-3 השינויים ב-`cmd_decision.py`/`airtable_schema.py` — אין כתיבה לשדות Airtable חדשים (רק `Readiness` הקיים), אפס סיכון לנתונים קיימים

### F52 — Tool Architecture Audit Maps (docs-only, 4 קבצי audit)
- **תאריך:** 26/06/2026
- **סוג:** Documentation — audit-only, אין שינוי קוד/התנהגות
- **Requirement:** audit מקדים לפני מימוש F52 (לא תועד בקובץ ROADMAP item נפרד מעבר לסעיף F52 עצמו)
- **תיאור:** 4 מסמכי audit ב-`docs/architecture/f52-unified-approval-runtime/audits/original/` שמתעדים את ארכיטקטורת הכלים הקיימת לפני כל refactor: `F52_CURRENT_TOOL_MAP.md` (מפת כלים נוכחית), `F52_CONTRACT_COVERAGE_MAP.md` (כיסוי חוזה C53-A), `F52_BYPASS_MAP.md` (קטגוריות bypass + bypasses בסיכון גבוה), `F52_STATE_FLOW_MAP.md` (מפת זרימת state). Scope guard מפורש בכל 3 ה-PRs: אין שינוי `app.py`, אין refactor, אין שינוי סכמת Airtable.
- ⚠️ **רשומה זו נוספה בדיעבד** — F52 מוזג כבר ב-3 PRs נפרדים בלי שנפתחה רשומת CHANGE_CONTROL_LOG ייעודית בזמן המיזוג (רק עדכון ROADMAP.md חלקי, שגם הוא היה חסר את הקובץ הרביעי — תוקן באותו commit כמו רשומה זו). אותר ע"י audit יומי (סשן `claude/gifted-clarke-ajyjsa`, 26/06/2026).
- **Commit:** `6afc393` (PR #153) / `84762f0` (PR #155) / `4b0f5d3` (PR #156)
- **PR:** #153 (merge `0ffdc7c`), #155 (merge `d57f405`), #156 (merge `64a018b`) — **כל השלושה מוזגו ל-`main`**, אומת עצמאית דרך `git merge-base --is-ancestor` על כל אחד מ-3 ה-commits
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא רלוונטי — מסמכי תיעוד בלבד, אין קוד לפרוס
- **Verified בפרודקשן:** לא רלוונטי — אין קוד/התנהגות לאמת
- **Verification ראיה:** `ls docs/architecture/f52-unified-approval-runtime/audits/original/` מאשר קיום 4 הקבצים בפועל על דיסק; `git merge-base --is-ancestor` אישר שלושת ה-commits כ-ancestors של `origin/main`
- **Docs עודכנו:** ROADMAP.md (סעיף F52 תוקן — נוסף הקובץ הרביעי החסר + תוקן סטטוס "branch" ל-"מוזג"), CHANGE_CONTROL_LOG.md (רשומה זו, נוספה בדיעבד)
- **Feature Flag:** N/A — תיעוד בלבד
- **Rollback plan:** לא רלוונטי — מחיקת קבצי Markdown בלבד, אפס סיכון קוד

### C60 — Tool Context Awareness (last_tool_result + system-prompt injection + pronoun resolution)
- **תאריך:** 25/06/2026
- **סוג:** Feature — לא flag-gated (additive, לא נוגע בלולאה הקיימת)
- **Requirement:** `SPEC_C59_Tool_Context_Awareness.md` (הועלה ע"י הבעלים, ללא טקסט מלווה; אישור התקבל דרך `AskUserQuestion`: "Yes, implement now")
- ⚠️ **ID collision מתועד (כמו C54→C57):** הספק החיצוני תייג את עצמו "C59" — מתנגש עם C59 הקיים (Decision Hub Stage 1 Trust Layer, PR #151, ראו למעלה). תויג מחדש **C60** בכל מסמכי התיעוד; כותרת הספק עצמו ("SPEC_C59_...") וכל מחרוזות הקוד/log לא שונו.
- **תיאור:** פותר "עיוורון כלים" — הסוכן לא ידע מה כלי קודם עשה בסבב הקודם, מה שגרם ל-intent שגוי (למשל "תעלה לדסישנס" אחרי שקובץ כבר נמצא ב-context). שלושה חלקים: (1) **`session_store.py`** — `last_tool_result` נוסף ל-`_new_session()` + `set_last_tool_result`/`get_last_tool_result` חדשים ב-`PersistentSessionStore`, מסונכרנים ל-`State JSON` (sync/load/delete) בדיוק כמו `last_uploaded_file` הקיים מ-C58. (2) **`app.py`** — `_capture_last_tool_result()` נקרא אחרי כל dispatch אמיתי בלולאת ה-agent (לא על branches חסומים/ממתינים לאישור); `_build_tool_context()` מזריק "🔧 הקשר כלים" ל-`ctx.system_prompt` (TTL 5 דקות לפי timestamp); `resolve_context_pronouns()` מחליף כינויי הצבעה עבריים ("זה"/"הנספח"/"הקודם"/"ההוא"/"אותו") בהתייחסות מפורשת לפני ה-Router (שלב חדש "2.6").
- ⚠️ **3 סטיות מהטקסט המילולי של הספק, כולן מתועדות:**
  1. **חוזה tool_result שגוי בספק** — הספק מניח `tool_result.get("id")`/`("record_id")`/`("url")`/`("drive_url")`; החוזה האמיתי בקוד (C53-A, אומת ב-`test_c53a.py` — `set(r) == {"ok","tool","external_id","evidence","user_message"}`, ללא מפתחות נוספים) הוא `{ok, tool, external_id, evidence, user_message}`. תוקן: `record_id` נשלף מ-`external_id`, `url` נשלף מ-`evidence.get("htmlLink") or evidence.get("url")`.
  2. **`_seconds_ago()` מוזכר ב-§5 אך לא מוגדר בספק** (כמו `_has_keyword_conflict` ב-C59) — מומש inline ב-`_build_tool_context()` כ-diff בין `datetime.now(timezone.utc)` ל-`datetime.fromisoformat(timestamp)`, עטוף ב-try/except ל-timestamps פגומים.
  3. **§6 "Table Registry fix" (4 קבועי Decision Tables)** — אומת מראש דרך §8 PRE-SESSION GATE grep שכל 4 הקבועים (`DECISIONS`/`DECISION_EVENTS`/`DECISION_STAKEHOLDERS`/`DECISION_INBOX`) כבר קיימים ב-`airtable_schema.py` מ-C59 — no-op, לא נוצר שינוי מיותר.
- **Commit:** `2d85b84`
- **PR:** #152 — **מוזג ל-`main`** (merge commit `3e0094b`, אומת עצמאית דרך `git merge-base --is-ancestor 2d85b84 origin/main`; **תיקון post-merge** — תועד בעבר בטעות כ"לא ממוזג", אותר ע"י audit יומי ב-26/06/2026)
- **Review על ידי:** הבעלים (אישור "Yes, implement now" דרך `AskUserQuestion`)
- **Deploy תאריך:** לא ידוע — מיזוג ל-`main` אומת, אך פריסה בפועל ל-Render **לא ניתנת לאימות מתוך sandbox זה** (אין גישת dashboard/egress)
- **Verified בפרודקשן:** לא — §10 פריט 7 בספק עצמו ("העלה קובץ → 'תעלה לדסישנס' → BOSS זוכר ומנתב נכון") עדיין לא אומת בלייב
- **Verification ראיה:** `python3 -m py_compile app.py session_store.py airtable_schema.py` נקי; `python3 session_store.py` → 40/40 self-tests עוברים (4 חדשים ל-C60: set/get round-trip, sync includes field, missing-session→None); `python3 test_c53a.py` → 50/50 (ללא רגרסיה בחוזה C53-A); `python3 test_integration.py` → 4/4; `python3 smoke_tests.py` — 2 כשלים קיימים-מראש (`flask`/`httpx` לא מותקנים בסביבת dev זו), אומת עם `git stash` שהם זהים על main, לא קשור לשינוי; §9 greps כולם תקינים (`set_last_tool_result`/`get_last_tool_result`/`_build_tool_context`/`הקשר כלים`/`resolve_context_pronouns`/4 קבועי Decision tables כולם נמצאים).
- **Docs עודכנו:** ROADMAP.md (C60 חדש + header, תיקון סטטוס מיזוג ל-C58/C59; **תוקן שוב 26/06/2026** לאחר שנמצא ש-PR #152 כבר מוזג), CHANGE_CONTROL_LOG.md (רשומה זו + תיקון PR/Deploy ל-C58/C59; **תוקן שוב 26/06/2026**), AI_CONTEXT.md
- **Feature Flag:** אין — תמיד-פעיל (additive, כמו `last_uploaded_file` ב-C58)
- **Rollback plan:** revert commit `2d85b84` (או ה-merge commit `3e0094b`) — שדה `last_tool_result` חדש ב-State JSON, אין breaking change לצרכנים קיימים; אם injection ל-system prompt גורם לבעיה (גודל/רעש), ניתן להסיר את שורת `ctx.system_prompt += _build_tool_context(chat_id)` בלבד בלי לגעת בשאר הקוד

### F17 — Decision Hub Stage 2: Smart Trust Layer (AI Conflict Detection, Confidence Score, Evidence Graph, Missing Evidence)
- **תאריך:** 25/06/2026
- **סוג:** Feature — flag-gated (`FEATURE_DECISION_HUB`, כבוי כברירת מחדל)
- **Requirement:** SPEC F17 (הועלה ע"י הבעלים, "SPEC ONLY — אין מימוש לפני אישורך"), אושר בכפוף לתנאי מפורש אחד: *"AI Conflict Detection יהיה Lazy + Cached, לא Eager. קליטת Event לא תלויה ב-Claude. בזמן פתיחת Decision או Refresh יבוצע סריקת קונפליקטים מוגבלת, רק לאירועים באותו Claim Topic וברמת Trust של T1 ומעלה"*.
- **תיאור:** שכבת ביטחון על גבי Stage 1 — מסתכלת על Decision שלם (לא Event בודד): האם האירועים התומכים מסכימים, מה חסר, כמה ביטחון לפני חתימה. קובץ חדש `decision_confidence.py`: (1) **AI Conflict Detection** — `detect_conflict_ai(event_a, event_b)` קריאת Claude בודדת (`call_anthropic_text`, prompt JSON-only בעברית) עם `detect_conflicts_ai_lazy(events)` שעוטף אותה במלוא תנאי האישור — מסנן ל-Trust>=T1 + Claim Topic קיים, מקבץ לפי Claim Topic, dedup לפי `_event_pair_hash` (sha256 על זוג IDs ממוין) ב-`_conflict_cache` (process-local), מוגבל ל-`_MAX_AI_COMPARISONS_PER_RUN=5` קריאות Claude חדשות לריצה (פגיעות ב-cache לא נספרות במגבלה). (2) **Evidence Graph** — `evidence_ids`/`evidence_summary` (`build_evidence_summary()` סופר Events לפי Event Type). (3) **Decision Confidence Score** — `calc_confidence(events, conflicts=None)`: ממוצע משוקלל של ציוני Trust (`_TRUST_SCORE`: T0=0.1/T1=0.4/T2=0.7/T3=0.95) מינוס `0.15×len(conflicts)`, clamped [0,1]; `conflicts=None`→מריץ את הסריקה ה-Lazy, `conflicts=[]`→מדלג עליה במפורש (לבדיקות/refresh בלי תקציב Claude). (4) **Missing Evidence Detector** — `detect_missing_evidence(domain, events)`: בדיקת מילת-מפתח פשוטה (לא LLM) מול `REQUIRED_EVIDENCE[domain]`. **מומלא בפועל** את ה-stub `_has_keyword_conflict()` שStage 1 (C59) השאיר פתוח — כאיתות AI מקביל (`DecisionEventTag.CONFLICT`), לא תחליף לבדיקת מילות-המפתח עצמה. מוזרק ל-`_format_decision_card()` ב-`cmd_decision.py` (נקרא מ-`/decision status`, מאחורי הדגל) — חולצה `_list_decision_events()` חדשה מ-`_latest_event()` הקיים כדי לשתף את רשימת ה-Events בין חישוב הכרטיס הישן לחישוב הביטחון החדש; `_persist_confidence()` כותבת best-effort ל-4 שדות חדשים ב-Decisions דרך `airtable_patch()`.
- ⚠️ **3 סטיות מהטקסט המילולי של הספק, כולן מתועדות:**
  1. הספק כתב `core/decision_confidence.py` — נכתב ב-root, לצד `decision_pipeline.py`/`decision_ports.py`/`cmd_decision.py` (שאר מודולי Decision Hub), לעקביות ארכיטקטונית — אין תיקיית `core/` בשימוש לאף מודול Decision Hub קיים.
  2. הספק הגדיר `REQUIRED_EVIDENCE` לפי "decision_type" — קונספט שלא קיים בסכמה בכלל (ל-Decisions יש רק `Domain`, ראו `DecisionDomain`). נמופה על `DecisionDomain` הקיים (`REAL_ESTATE`/`IMPORT`/`PARTNERSHIP`/`RECRUITMENT`/`GENERAL`); `IMPORT` ו-`PARTNERSHIP` משתפים את אותה רשימת ראיות בהיעדר הבחנה ספציפית יותר בספק.
  3. הספק הניח קיומה של פונקציה `get_decision()` — אינה קיימת בקוד. החיווט נעשה ב-`_format_decision_card()` (הנקודה הקיימת היחידה שמרכיבה כרטיס Decision מלא, כבר מאחורי `FEATURE_DECISION_HUB`, נקראת רק מ-`/decision status`).
- **תיקון רגרסיה תוך-כדי-עבודה (לא הגיע ל-commit):** בעת חילוץ `_list_decision_events()`, השלב הביניים הפך בטעות את בדיקת ה-empty-list (`events[0] if not events else max(...)` — היה זורק `IndexError` על Decision בלי Events מקושרים, במקום להחזיר `None`) — אותר ותוקן (`max(events, ...) if events else None`) לפני כתיבת הבדיקות.
- **שדות Airtable חדשים (לא נוצרו עדיין ביד ב-Airtable חי):** `Evidence Ids` (Long text, JSON array), `Evidence Summary` (Long text), `Confidence Score` (Number 0.0-1.0), `Missing Evidence` (Long text, JSON array). `airtable_patch()` משמיט שדות לא-מוכרים בשקט (`schema_cache.json` עדיין לא מכיר אותם) — תצוגת הטלגרם תקינה בכל מקרה (חישוב in-memory ב-`_format_confidence_block()`), הפרסיסטנס הוא best-effort עד שהשדות ייוצרו ו-`schema_audit.py` ירוץ מחדש.
- **Commit:** `9252b1e`
- **PR:** #157 — **מוזג ל-`main`** (merge commit `78f9bae`, `merged: true`, אומת ע"י GitHub MCP `pull_request_read` + `git merge-base --is-ancestor 9252b1e origin/main`, לא רק לפי דיווח המשתמש)
- **Review על ידי:** הבעלים (אישור מפורש בכפוף לתנאי Lazy+Cached, מצוטט לעיל)
- **Deploy תאריך:** לא ידוע — מיזוג ל-`main` אומת, אך פריסה בפועל ל-Render **לא ניתנת לאימות מתוך sandbox זה** (אין גישת dashboard/egress)
- **Verified בפרודקשן:** לא — דגל `FEATURE_DECISION_HUB` כבוי, אפס בדיקה חיה מול Airtable/Render
- **Verification ראיה:** `python3 -m py_compile decision_confidence.py cmd_decision.py airtable_schema.py app.py test_decision_confidence.py` נקי; `python3 test_decision_confidence.py` → 25/25 self-tests עוברים (`detect_conflict_ai` מ-monkeypatch, אפס קריאות רשת/עלות Claude) — מכסה: ממוצע משוקלל/קנס קונפליקטים/clamp/empty-events ב-`calc_confidence`, ספירת Event Type ב-`build_evidence_summary`, תבניות `REQUIRED_EVIDENCE` לכל Domain ב-`detect_missing_evidence`, וכל תנאי השער ב-`detect_conflicts_ai_lazy` (סינון Trust<T1, סינון Claim Topic חסר/שונה, cache hit לא קורא ל-Claude שוב, מגבלת 5 קריאות לריצה, החרגת Events superseded); `python3 test_decision_trust.py` → 33/33 ללא רגרסיה ב-Stage 1; `python3 smoke_tests.py` — אותם 2 כשלים תלויי-סביבה קיימים מראש (`flask`/`httpx` חסרים בסביבת sandbox), אין כשלים חדשים.
- **Docs עודכנו:** ROADMAP.md (F17 חדש + header, עודכן שוב לאחר המיזוג), CHANGE_CONTROL_LOG.md (רשומה זו, שדות Commit/PR/Deploy עודכנו לאחר המיזוג)
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן
- **Rollback plan:** revert commit `9252b1e` (או ה-merge commit `78f9bae`) — דגל כבוי, קובץ חדש + תוספות בלבד לקבצים קיימים (אין מחיקת/שינוי לוגיקה קיימת מעבר לחילוץ `_list_decision_events()` ותיקון ה-`IndexError`), אפס סיכון פונקציונלי מיידי

### C59 — Decision Hub Stage 1: Trust Layer (Authority × Medium × Verify)
- **תאריך:** 25/06/2026
- **סוג:** Feature — flag-gated (`FEATURE_DECISION_HUB`, כבוי כברירת מחדל)
- **Requirement:** `SPEC_Decision_Hub_Stage1_Trust_Rev2.md` (הועלה ע"י הבעלים עם אישור מפורש: "ניתן ליישם ספק" — מהווה את אישור "אליהו" שהספק דרש ב-header שלו; הבעלים גם דיווח על יצירת 3 שדות Airtable: `Claim Topic`/`Claim Topic Source`/`Claim Topic Confidence`)
- **תיאור:** `gate_trust()` ב-`decision_pipeline.py` (היה stub) מומש במלואו — מודל Trust דו-מימדי: `AUTHORITY_SCORE`(מי אמר)×`MEDIUM_SCORE`(איך הגיע), עם medium ceiling (`compute_trust`/`score_to_level`); `extract_claim_topic()` גוזר נושא אוטומטית מ-4 מקורות לפי עדיפות (filename→Event Type→Delta Type→Raw Content keywords) עם ידני כ-fallback, מורחב להחזיר `(topic, source, confidence)` סביב 2 השדות שהבעלים הוסיף מעבר לטקסט המילולי של הספק; `maybe_supersede()` — supersede בטוח (רק אותו Claim Topic + Trust גבוה יותר). Verify-fail על מקור עם authority≥65 → T0 ישיר (לא T1 רך). T1 שקט (`user_flag=None`), T0 עם אזהרה.
- ⚠️ **9 סטיות מהטקסט המילולי של הספק, כולן מכוונות ומתועדות:**
  1. `VerifierPort.verify()` (`decision_ports.py`) מחזיר `dict` (`{"verified": bool, ...}`) — לא object עם `.status` כפי שהספק מניח. שונה ל-`{"status": "ok"/"warn"/"failed"/"hallucination", "reason": ...}`; `gate_trust` קורא עם `.get("status", "ok")`.
  2. `decision["id"]` — `maybe_supersede` בספק קורא ID ישירות מ-`decision`, אבל שתי נקודות הקריאה האמיתיות ב-`cmd_decision.py` מעבירות ל-`run_pipeline` רק את `decision["fields"]`/`decision_record["fields"]` (sub-dict בלי `"id"`) — היה גורם ל-`KeyError`. תוקן: ה-ID מוזרק כ-`event["_decision_id"]` בנקודות הקריאה (`_handle_update_step`/`_link_inbox_to_decision`), ו-`maybe_supersede` קורא משם.
  3. Tags: הספק כותב מחרוזות אנגלית ("potential_conflict"/"low_confidence"/"pressure_high_risk") — אלה לא קיימות כאופציות Multi-Select חיות ב-Airtable (סיכון `INVALID_MULTIPLE_CHOICE_OPTIONS`). נעשה שימוש ב-`DecisionEventTag.CONFLICT`("קונפליקט") הקיים; נוספו 2 קבועים עבריים חדשים (`LOW_CONFIDENCE`="אמינות_נמוכה", `PRESSURE_HIGH_RISK`="לחץ_סיכון_גבוה") **שלא אומתו מול Airtable חי** — בניגוד ל-`Claim Topic Source` שהבעלים אישר במפורש.
  4. `_has_keyword_conflict()` — הספק מפנה לפונקציה זו ב-§5 שלב ו' אך **לא הגדיר את גוף הלוגיקה בכלל** בטקסט הספק. מומשה כ-stub שמחזיר `False` עם תיעוד inline; נתיב ה-"conflict tag" לא פעיל בפועל עד שתוגדר לוגיקה (Stage 1.x/Stage 2 — מתאים ל-§11 "AI Conflict Detection — Stage 2" שכבר מוחרג בספק).
  5. `DecisionSourceReliability` (`airtable_schema.py`) היו חסרים 4 מתוך 10 מפתחות `AUTHORITY_SCORE` — נוספו `DOCUMENT`("מסמך")/`MANUAL`("ידני")/`EMPLOYEE`("עובד")/`UNKNOWN`("לא_ידוע").
  6. `event["Channel"]` לא היה מועבר כלל ל-`gate_trust` לפני התיקון (היה נכתב רק ב-write-time, אחרי שהשער כבר רץ) — תוקן בשתי נקודות הקריאה. `event["Source Reliability"]` **עדיין לא מוזן ע"י שום UI קיים** ב-`/decision update` — `gate_trust` יחזיר תמיד authority=55(ידני) default עד שתיווסף שאלה ייעודית; מחוץ לטקסט המילולי של הספק, לא תוקן בסבב הזה (דגול ל-Stage 1.x).
  7. פלטי ה-Trust Layer (Trust Level/Confidence/Tags/Claim Topic+Source+Confidence/Source Reliability/Supersedes) לא נכתבו ל-Airtable כלל — נוספה `_add_trust_fields()` ב-`cmd_decision.py`, מחוברת לשני נתיבי הכתיבה (`_create_decision_event`/`event_fields` ב-`_link_inbox_to_decision`).
  8. `run_pipeline()` היה מזניח את `user_flag` של שערים שעברו בהצלחה (בנה `GateResult` סינתטי חדש עם `user_flag=None` בסוף) — נוסף `collected_flag` שעוקב על ה-flag האחרון שאינו `None` בכל איטרציה, ומועבר ל-`GateResult` הסינתטי הסופי. בלי התיקון, הודעת "📝 לא זיהיתי נושא" (T2/T3 בלי Claim Topic) לא הייתה מוצגת למשתמש אף פעם.
  9. `_format_pipeline_outcome()` לא טיפל ב-`halted_at == "trust"` (T0/T1) ולא בדק `result.user_flag` בנתיב ההצלחה — נוסף branch מפורש ל-trust + הצמדת `user_flag` (אם קיים) להודעת ההצלחה הגנרית.
- **Commit:** `73f6fe8`
- **PR:** #151 — **מוזג ל-`main`** (`merged: true`, אומת ע"י GitHub MCP `pull_request_read`, לא רק לפי דיווח המשתמש); branch מרוחק `claude/new-session-be1ckb` נמחק בהתאם
- **Review על ידי:** הבעלים (אישור "ניתן ליישם ספק" על ספק שהיה מסומן SPEC ONLY)
- **Deploy תאריך:** לא ידוע — מיזוג ל-`main` אומת, אך פריסה בפועל ל-Render **לא ניתנת לאימות מתוך sandbox זה** (אין גישת dashboard/egress)
- **Verified בפרודקשן:** לא — §10 פריט 11 בספק עצמו ("אירוע T0 אמיתי → user_flag בטלגרם") עדיין לא אומת מול פרודקשן חי
- **Verification ראיה:** `python3 -m py_compile airtable_schema.py decision_ports.py decision_pipeline.py cmd_decision.py test_decision_trust.py` נקי; `python3 test_decision_trust.py` → 33/33 self-tests עוברים (compute_trust edge cases, extract_claim_topic priority order, maybe_supersede same-topic-only, gate_trust T0/T1/T2/T3 branches, run_pipeline user_flag propagation); §9 greps כולם תקינים (`AUTHORITY_SCORE`/`MEDIUM_SCORE`/`compute_trust`/`extract_claim_topic`/`maybe_supersede`/`Claim Topic` נמצאים, `grep -n "trust stub"`→0 matches, `grep -c "SOURCE_TRUST"`→0); `python3 smoke_tests.py`/`python3 test_integration.py` — אין רגרסיה (2 כשלי smoke_tests קיימים-מראש, נבדק עם `git stash` שהם זהים על main, סיבה: `flask`/`httpx` לא מותקנים בסביבת dev זו, לא קשור לשינוי).
- **Docs עודכנו:** ROADMAP.md (N13 הורחב + header), CHANGE_CONTROL_LOG.md (רשומה זו), AI_CONTEXT.md
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן
- **Rollback plan:** revert ה-commit הבא — דגל כבוי כך שאין breaking change בפרודקשן בכל מקרה; אם נדרש rollback חלקי, `gate_trust` חוזר ל-stub הישן (`GateResult(True, "trust stub — stage 1", next_gate="readiness")`)

### C58 — Universal Sessions: Sessions table replaces non-existent LeadSessions
- **תאריך:** 25/06/2026
- **סוג:** Bug Fix (latent 403 on every session write) + Schema Change — לא flag-gated
- **Requirement:** `SPEC_C58_Universal_Sessions.md` (הועלה ע"י הבעלים עם הוראה מפורשת "implement" — מהווה את אישור "אליהו" שהספק דרש ב-header שלו)
- **תיאור:** `Tables.LEAD_SESSIONS` ("LeadSessions") **לא קיימת בפועל ב-Airtable** — כל כתיבה אליה הייתה מחזירה 403 (באג latent, לא תועד קודם ב-`BUG_AUDIT_LOG.md`). הוחלפה ב-`Tables.SESSIONS` (טבלה אמיתית, `tblHLfE24lTkVUhz0`) עם schema גנרי משותף: `class SessionsFields` (`airtable_schema.py`) — `Context Type` (select, ברירת מחדל `"lead"` לתאימות לאחור), `State JSON` (כל ה-state הקיים — domain/step/answers/done/drop_off_step/score/tier/last_uploaded_file — בשדה טקסט יחיד), `Sender ID`/`Channel`/`Created At`/`Updated At`, ו-10 שדות `Linked *` אופציונליים (Lead/Contact/Decision/Deal/Task/Payment/Venture/Media File/Business Memory/Decision Event). `session_store.py`'s `_sync_to_db`/`_load_from_db`/`_delete_from_db` נכתבו מחדש מלא לשימוש ב-Sessions; `_extract_balanced_json()` חדש (brace-depth counting, לא regex naive) מחלץ את ה-JSON המקונן מתוך הפורמט הטקסטואלי שמ-`airtable_get()` מחזיר.
- ⚠️ **4 סטיות מהטקסט המילולי של הספק, כולן מכוונות ומתועדות:**
  1. **`external_id` extraction** — הספק הציע `result.get("id") or result.get("record_id") or result.get("external_id")`; מומש כ-`result.get("external_id", "")` ישירות, לפי חוזה C53-A האמיתי שאומת ב-`tools/airtable_tools.py` (`_tool_result()` מחזיר מפתח `external_id` בלבד).
  2. **`last_uploaded_file` חסר ב-State JSON** — הספק השמיט אותו מה-snippet המוצע, בסתירה לעקרון "State JSON = כל ה-state הקיים. אפס אובדן מידע" שהוא עצמו מצהיר ב-§4. נוסף ל-State JSON וגם `set_last_file()` עודכן לקרוא בפועל ל-`_sync_to_db()` (לפני כן לא היה מסונכרן ל-DB בכלל).
  3. **`LINKED_MEDIA_FILE` table-identity mismatch** — הספק הציע לקשר את `last_uploaded_file.file_id` תמיד; אומת ב-`cmd_decision.py`/`app.py` ש-`type="inbox_file"` שומר record ID מטבלת **Decision Inbox**, ו-`type="drive_file"` שומר record ID מטבלת **Media Files** — שני סוגי record ID שונים. קישור ה-inbox_file record ל-`LINKED_MEDIA_FILE` (שמייעד ל-Media Files) היה גורם ל-`INVALID_RECORD_ID` באירטייבל. תוקן: הקישור מתבצע רק כש-`type == "drive_file"`.
  4. **`_delete_from_db` מאבד state** — הספק הציע להחליף את כל ה-`State JSON` ב-`{"done": True, "deleted": True}` בלבד, מוחק domain/step/answers/score/tier. תוקן: `_delete_from_db` מקבל גם את `session` המלא ובונה tombstone ששומר את כל השדות הקיימים + `done`/`deleted=True`.
  - בנוסף תוקן באג קדם-קיים (לא קשור ל-C58, התגלה תוך כדי הוספת בדיקות): ה-mock ב-`_run_tests()` רשם `sys.modules["airtable_tools"]` במקום `sys.modules["tools.airtable_tools"]` (הנתיב האמיתי שממנו `session_store.py` מייבא) — `ImportError` נתפס בשקט ב-`_sync_to_db`/`_load_from_db`, כך שכל בדיקות ה-DB-sync "עברו" מבלי לבדוק דבר (כפי שתועד גם ב-N13 לעיל: "18/20, 2 כשלים קיימים מראש" — אלה היו אותם 2 כשלים, לא קשורים-בטעות לתיקון).
- **Commit:** `84f2ef3`
- **PR:** #150 — **מוזג ל-`main`** (`merged: true`, אומת ע"י GitHub MCP `pull_request_read`, לא רק לפי דיווח המשתמש); branch מרוחק `claude/new-session-be1ckb` נמחק בהתאם
- **Review על ידי:** הבעלים (הוראת "implement" על הספק שהיה מסומן SPEC ONLY)
- **Deploy תאריך:** לא ידוע — מיזוג ל-`main` אומת, אך פריסה בפועל ל-Render **לא ניתנת לאימות מתוך sandbox זה** (אין גישת dashboard/egress)
- **Verified בפרודקשן:** לא — סעיף 7 בספק עצמו (item 5, "session חדש → רשומה נוצרת ב-Sessions ב-Airtable") עדיין לא אומת מול Airtable חי
- **Verification ראיה:** `python3 -m py_compile session_store.py airtable_schema.py app.py cmd_decision.py` נקי; `python3 session_store.py` → 36/36 self-tests עוברים (כולל 11 בדיקות חדשות ל-C58: `_extract_balanced_json` עם JSON מקונן, `context_type` ברירת מחדל, מבנה `State JSON` ב-`_sync_to_db`, gating נכון בין drive_file/inbox_file, round-trip מלא של `_load_from_db` מול מחרוזת מזויפת בפורמט האמיתי של `airtable_get()`); spec §6 greps כולם תקינים (`grep -c "LeadSessions" session_store*.py` → 0, `class SessionsFields`/`Tables.SESSIONS`/`State JSON`/`context_type` כולם נמצאים)
- **Docs עודכנו:** ROADMAP.md (C58 חדש + header), CHANGE_CONTROL_LOG.md (רשומה זו), AI_CONTEXT.md
- **Feature Flag:** אין — תשתית sessions תמיד-פעילה (לא אופציונלית), כמו `session_store.py` הקודם
- **Rollback plan:** revert ה-commit הבא — `Tables.LEAD_SESSIONS` עדיין קיים בקוד (deprecated, לא נמחק) כך שאין breaking change בממשק; הסיכון העיקרי הוא ש-`Tables.SESSIONS`/שדות `SessionsFields` לא תואמים 1:1 לשמות השדות האמיתיים ב-Airtable (לא אומת ישירות מול ה-base, רק לפי הספק) — אם כתיבה ראשונה בפרודקשן תיכשל, יש לבדוק שמות שדות מול schema חי לפני כל דבר אחר

### C57 — Agent Tool Awareness: suppress premature text_block alongside tool_use (PR #149)
- **תאריך:** 25/06/2026
- **סוג:** Bug Fix (UX-level, behavior change — לא flag-gated)
- **Requirement:** `SPEC_C54_Agent_Tool_Awareness.md` (הועלה ע"י הבעלים, אושר במלואו: "Yes, both changes")
- **תיאור:** Claude מחזיר לעיתים `text_block` ו-`tool_use` באותה API response. ה-text נכתב לפני שהמודל ראה את תוצאת הכלי — אם הוא נשלח למשתמש (כמו "לא הבנתי מה לעלות") לפני שהכלי רץ בפועל, נוצרת תשובה סותרת/מבלבלת ב-turn אחד בלבד, גם כשהכלי בפועל הצליח. תיקון בשתי שכבות: (1) **`app.py`** (אחרי חילוץ `tool_uses`/`text_blocks` בלולאת ה-agent) — אם שניהם קיימים באותה תשובה, `text_blocks` מאופס ל-`[]` ונכתב `logger.info("[C54] Suppressed premature text_block alongside tool_use: ...")`; הלולאה ממשיכה, הכלי רץ, והתשובה האמיתית מגיעה ב-turn הבא עם תוצאת הכלי. (2) **`core_knowledge.py`** — כלל 7 חדש בבלוק `_NEVER_FAKE_CONTROL`: "כשאתה מפעיל כלי, אל תכלול טקסט הסבר או שאלת הבהרה באותה תשובה. הפעל את הכלי. קבל את התוצאה. ענה למשתמש רק אחרי שיש לך תוצאה." השכבה הראשונה (קוד) מגנה על מה שהשנייה (prompt) לא תפסה.
- ⚠️ **ID collision מתועד:** הספק החיצוני תייג את התיקון "C54" — מתנגש עם C54 הקיים ב-`ROADMAP.md` (Business Memory /update command, PR #85). תויג מחדש **C57** בכל מסמכי התיעוד (ROADMAP/CHANGE_CONTROL); `logger.info` בקוד עצמו וה-docstring ב-`core_knowledge.py` נשארו עם תג `[C54]`/הערת "C54" כפי שנכתבו, כדי לא לגעת בלוג production string ללא צורך תפעולי — ה-mapping מתועד כאן.
- **Commit:** `cc6142b`
- **PR:** #149 — https://github.com/10026782/My-bot/pull/149 — **מוזג ל-`main` ב-commit `1d08402`**
- **Review על ידי:** הבעלים (אישר את שני השינויים במפורש לפני כתיבת קוד, per SPEC ONLY gate)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — ממתין לראות `[C54] Suppressed premature text_block` ב-Render logs (ראו §8 של הספק המקורי); אם לא מופיע תוך שבוע מה-deploy, סימן ש-prompt rule בלבד הספיק.
- **Verification ראיה:** `git fetch origin main` + `git merge-base --is-ancestor cc6142b origin/main` → exit 0; `python3 -m py_compile app.py core_knowledge.py` נקי.
- **Docs עודכנו:** ROADMAP.md (C57 חדש + header), CHANGE_CONTROL_LOG.md (רשומה זו)
- **Feature Flag:** אין — שינוי קוד תמיד-פעיל בלולאת ה-agent, לא flag-gated (תיקון התנהגות בסיסי, לא פיצ'ר)
- **Rollback plan:** revert PR #149 — מחזיר התנהגות קודמת (text+tool_use לעיתים נשלחים יחד); אין סיכון דאטה, רק UX

### N13 — Decision Hub Stage 0.5/0.6 + BUG-017/BUG-B + MODULE_RULES 7-10/12 (PR #147)
- **תאריך:** 25/06/2026
- **סוג:** Feature (flag off) + Bug Fix + Docs
- **Requirement:** ROADMAP.md N13 (נוסף באותו commit — Decision Hub לא היה מתועד ב-ROADMAP לפני כן)
- **תיאור:** `cmd_decision.py`/`app.py` — Stage 0.5 (File/Voice Precedence Routing: `decision_context_active()`, `route_file_to_decision_inbox()`, מוטמע ב-`_handle_telegram_media` עם fail-safe exception handling) ו-Stage 0.6 (File Context Reference: `FileUploadResult`/`set_last_file`/`get_last_file` ב-`session_store.py`, וזיהוי "זה הנספח" דרך `is_attachment_reference()`/`handle_attachment_reference()`, ממוקם ב-`_webhook_telegram_impl` הטלגרם-ספציפי ולא ב-`run_agent()` המשותף-לכל-הערוצים — תיקון ארכיטקטוני שנעשה תוך כדי הבנייה). תוקנו: BUG-017 (`session_store._sync_to_db` קרא חוזה dict כ-string) ו-BUG-B (LeadSessions תחת schema governance, additive). `docs/governance/MODULE_RULES.md` קיבל חוקים 7 (Ports), 8 (Tool↔Gate), 9 (Input Precedence), 10 (Raw-First), 12 (Domain-Agnostic Core — ממוספר 12 לא 11 כדי לא להתנגש עם חוק 11 הקיים, כתיב שמות שדות). נוסף `docs/governance/PLANNING_GATE.md`. נוסף `archive/BOSS_MASTER_PLAN_One_Road.md` (ARCHIVE, לא מקור אמת — ראו הערת מקור בראש הקובץ).
- **Commit:** `a6483c8` (MODULE_RULES 7-10 + BUG-B), `fdeb039` (BUG-017), `4ac2a05` (Stage 0.5), `e0f0111` (Stage 0.6)
- **PR:** #147 — https://github.com/10026782/My-bot/pull/147 — **מוזג ל-`main` ב-commit `483851f`**
- **Review על ידי:** הבעלים (אישר מיזוג מפורשות אחרי שאי-מיזוג קודם זוהה ותוקן)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — `FEATURE_DECISION_HUB` כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן
- **Verification ראיה:** `git fetch origin main` + `git merge-base --is-ancestor origin/claude/new-session-be1ckb origin/main` → exit 0 (מאומת PR ממוזג בפועל, לא רק לפי הצהרה); `py_compile` נקי על `app.py`/`cmd_decision.py`/`session_store.py`; `session_store.py` self-test 18/20 (2 כשלים קיימים מראש, מתועדים, לא קשורים לשינוי)
- **Docs עודכנו:** ROADMAP.md (N13 חדש), AI_CONTEXT.md, BUG_AUDIT_LOG.md (BUG-017), MODULE_RULES.md, PLANNING_GATE.md (חדש), archive/BOSS_MASTER_PLAN_One_Road.md (חדש)
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל
- **Rollback plan:** revert PR #147 — דגל כבוי, אפס סיכון פונקציונלי מיידי בפרודקשן

### N08 / N09 / N11 — ROADMAP status drift correction (docs-only)
- **תאריך:** 22/06/2026
- **סוג:** Docs-only correction, אפס שינוי קוד
- **Requirement:** התגלה בתחילת מימוש N11 (`pre_session_gate.sh` + `git checkout -b claude/n11-finance-pulse`) — לפני כתיבת קוד, נקרא `tma_api.py`/`airtable_schema.py` כדי לאמת שמות שדות לפי הנחיית המשתמש ("שמות שדות חייבים להתאים ל-live Airtable"), ונמצא ש-`finance_pulse()` כבר עובר דרך `SCREEN_CONFIGS["finance_pulse"]` + `_build_formula(entity="Payment")` — כל היקף N11 כבר ממומש ומאוחד. בדיקה נוספת (grep על `main`) חשפה שגם N08 ו-N09 — שהושלמו ומוזגו **בתוך הסשן הזה עצמו** (PR #103/#104) — נשארו מתויגים `🔲 PLANNED` ב-`ROADMAP.md`.
- **תיאור:** `ROADMAP.md` — שלוש רשומות (N08/N09/N11) עודכנו מ-`🔲 PLANNED` ל-`✅ הושלם` עם commit hash + PR, header (שורה 3) עודכן ל-`main` HEAD נכון (`24237e6`). `AI_CONTEXT.md` — Executive Summary, "חסום", "Next Priorities" item 3, ושלוש רשומות חדשות ב-"Completed Since Last Update" (PR #103/#104 + הערת התיקון עצמו). `CHANGELOG.md` — רשומת Unreleased חדשה. אפס שינוי ב-`tma_api.py`/`core/error_reporter.py`/`.github/workflows/ci.yml` עצמם — כולם נכונים כבר.
- **Commit:** (ראו commit log על `claude/n11-finance-pulse`)
- **PR:** טרם נפתח
- **Review על ידי:** —
- **Deploy תאריך:** N/A — docs-only
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** `git log --oneline --merges main | grep -i "n08\|n09"` אישר PR #103 (`abf4835`)/PR #104 (`24237e6`) על `main`; `grep -n "report_error\|error_reporter" app.py` אישר 3 קריאות חיות; `ls .github/workflows/ci.yml` אישר קיום; `grep -n "_build_formula\|entity.*Payment" tma_api.py` אישר wiring N11 (PR #77, `f7d7e4f`/`daab73e`, מאומת `git merge-base --is-ancestor f7d7e4f main`).
- **Docs עודכנו:** ROADMAP.md, AI_CONTEXT.md, CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה)
- **Feature Flag:** ללא שינוי
- **Rollback plan:** revert — docs-only, אפס סיכון

### C22 (spec ID, לא ROADMAP) — Weekly Business Summary
- **תאריך:** 22/06/2026
- **סוג:** Feature
- **Requirement:** spec חיצוני "C22 — Weekly Business Summary" (⚠️ ID זה מתנגש עם ROADMAP.md's C22 הקיים — "feature_flags is_enabled() alias", לא קשור; אותו דפוס תועד עבור C20/C21)
- **Commit:** `c4527b7`
- **PR:** #94 (`claude/weekly-business-summary-4crnek`)
- **Review על ידי:** Claude Code (session), אושר ע"י המשתמש
- **Deploy תאריך:** 22/06/2026 — Render (אישור משתמש)
- **Verified בפרודקשן:** לא ידוע — המשתמש אישר deploy ל-`d91a9df`, לא אומת עצמאית מסביבת Claude (אין גישת Dashboard/egress)
- **Verification ראיה:** `py_compile` נקי; `smoke_tests.py`/`test_integration.py`/`core/router/test_router.py` עוברים; תרחישי A/B/C/D מהספק נבדקו ידנית עם mock data
- **Docs עודכנו:** AI_CONTEXT.md, CHANGELOG.md, feature_flags.py (רישום הדגל), CHANGE_CONTROL_LOG.md (זה)
- **Feature Flag:** `FEATURE_WEEKLY_SUMMARY` — כבוי כברירת מחדל
- **Rollback plan:** `FEATURE_WEEKLY_SUMMARY=false` (ברירת מחדל); try/except ב-scheduler בולע כל כשל; המערכת עולה רגיל גם בלי `weekly_summary.py`

### C25–C40 — Stabilization Sprint (07/06/2026)
- **תאריך:** 07/06/2026
- **סוג:** Bug Fix (batch — 16 פריטים, C25–C40)
- **Requirement:** ROADMAP.md "Stabilization Sprint — 07/06/2026"
- **Commit:** מפתחות עיקריים: `0744ce9` (C37, payment_reminder self-test), `4e5d00d` (C40, Golden Path Approval Gate על branch `origin/approval-gate`, supersedes local `f3172ba`); שאר ה-IDs (C25–C36, C38, C39) — commit ייחודי לכל אחד לא תועד ב-ROADMAP בנפרד, רק שם הקובץ ששונה.
- **PR:** לא ידוע — דרוש בדיקה ידנית (ROADMAP לא מצטט מספרי PR לטווח זה)
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין ראיה מתועדת מעבר לתיאור "מה תוקן" בטבלת ROADMAP
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A (חלק נוגע ב-EMERGENCY_STOP persistence — C33)
- **Rollback plan:** לא תועד

### C40 — Golden Path Approval Gate
- **תאריך:** 07/06/2026
- **סוג:** Security
- **Requirement:** ROADMAP.md C40 — "TMA write endpoints now require approval before Airtable writes"
- **Commit:** `4e5d00d` (origin/approval-gate; supersedes local `f3172ba` per ROADMAP)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### W0 — WhatsApp Lead Capture
- **תאריך:** 08/06/2026
- **סוג:** Feature
- **Requirement:** ROADMAP.md "World 2 — Lead Flow Sprint", N01 prerequisite
- **Commit:** `2b861bd`
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `LEAD_CAPTURE`
- **Rollback plan:** לא תועד

### W1 / W1b — Airtable Schema Fix (N01)
- **תאריך:** 08/06/2026
- **סוג:** Schema Change
- **Requirement:** ROADMAP.md N01 ("✅ הושלם — W1 לעיל")
- **Commit:** W1 = `f095036`; W1b (Score/Next Followup case fix) = `a6b471c`
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md, `schema_cache.json`
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### W2 — Airtable Gateway, single write path
- **תאריך:** 08/06/2026 (refactor המשך: `f964070` ,`b43357e`)
- **סוג:** Feature / Security (consolidates write-path enforcement)
- **Requirement:** ROADMAP.md W2 — "tools/airtable_gateway.py: normalize→validate→audit→httpx"
- **Commit:** `b43357e` (refactor: single write path), `f964070` (gateway bonus fix — Owner multipleRecordLinks coercion)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** "22-test regression suite" מוזכר ב-ROADMAP — קובץ הטסטים (`test_airtable_gateway.py`) קיים בריפו, **לא הורץ בפועל בסשן האודיט הזה**
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### N02 / N03 — Lead Scoring + Lead Memory Wire-up
- **תאריך:** לא ידוע מדויק (לפני 17/06/2026, אחרי W2)
- **סוג:** Feature
- **Requirement:** ROADMAP.md N02/N03 — "✅ מיושם" (קוד), אך flags כבויים בפרודקשן
- **Commit:** `4d1130a` (consolidation, lead_scoring.py הוסר), `02f7e75` (N04-A/B wiring — lead_memory.update בעת create + אחרי scoring)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא — flags `LEAD_SCORING`/`LEAD_MEMORY` כבויים ברירת מחדל (ראה BOSS_CURRENT_STATE.md citations: `lead_capture.py:32,90,96,130,134-138`)
- **Verification ראיה:** אין אימות production; קוד בלבד
- **Docs עודכנו:** ROADMAP.md, BOSS_CURRENT_STATE.md
- **Feature Flag:** `LEAD_SCORING`, `LEAD_MEMORY` (שניהם כבויים ברירת מחדל)
- **Rollback plan:** N/A — flags כבר כבויים, אין expose בפרודקשן

### N04 — Followup Activation
- **תאריך:** לא ידוע מדויק
- **סוג:** Feature
- **Requirement:** ROADMAP.md N04 — "✅ scheduler מחובר (flag כבוי)"
- **Commit:** `02f7e75` (N04-A/B — lead_memory.all_active תיקון)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא — ROADMAP מצהיר במפורש "המתנה לפני הפעלה: לאמת ב-Render env עם הודעת WhatsApp אמיתית + LEAD_CAPTURE=true"
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `FOLLOWUP_AUTOMATION` (כבוי ברירת מחדל)
- **Rollback plan:** N/A — flag כבוי

### N05-B — send_followup.confirmed handler
- **תאריך:** לא ידוע מדויק
- **סוג:** Feature
- **Requirement:** ROADMAP.md N05-B — "✅ מיושם"
- **Commit:** `643f929`
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין; ROADMAP מציין "אין שליחה יוצאת לליד — Meta outbound blocked עד N05-C"
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `FOLLOWUP_AUTOMATION`
- **Rollback plan:** לא תועד

### N05 — Daily Digest שדרוג (Score+Tier wiring)
- **תאריך:** 17/06/2026 (`5490943`, ממוזג ל-main דרך `422c280`)
- **סוג:** Feature
- **Requirement:** ROADMAP.md N05 — "✅ מיושם", תלוי ב-N02
- **Commit:** `5490943` ("N05: wire real Score + computed tier into daily digest")
- **PR:** לא ידוע מספר — ממוזג ל-main כ-`422c280` ("Merge claude/meta-whatsapp-phase-1-q6pp3e: N05 Daily Digest Score+tier wiring")
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A (קורא Score, לא כתיבה)
- **Rollback plan:** לא תועד

### N06 — Ventures Screen (TMA)
- **תאריך:** 17/06/2026
- **סוג:** Feature
- **Requirement:** ROADMAP.md N06 — "✅ מיושם", תלוי ב-N05; החלטה ארכיטקטונית 17/06/2026 (Ventures = טבלה נפרדת)
- **Commit:** `eebf73b` ("N06: add Ventures Screen (TMA) — strategic pre-lead/pre-deal pipeline")
- **PR:** #67 (ממוזג ל-main ב-`7313b2e3`, "Merge pull request #67: N06 — Ventures Screen (TMA)")
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע — שדות הקוד תואמים 1:1 לסכמה חיה של טבלת Ventures (אומת ע"י Airtable MCP, 17/06/2026), אך לא בוצעה בדיקה ידנית במסך TMA החי
- **Verification ראיה:** Airtable MCP schema dump — התאמה מלאה בין `VentureFields`/`tma_api.py` לסכמה חיה
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### Sprint 16/06/2026 — C41–C51
- **תאריך:** 16/06/2026
- **סוג:** Feature / Bug Fix (batch — 11 פריטים)
- **Requirement:** ROADMAP.md "Sprint 16/06/2026"
- **Commit:** ראו פירוט: C45=PR #59, C46=PR #61, C47=PR #62, C48=PR #63, C49=PR #60, C51=branch `furniture-funnel-clean` (`test_approval_concurrency.py`); C41–C44, C50 — אין PR מצוטט ב-ROADMAP
- **PR:** #59, #60, #61, #62, #63 (פירוט לפי שורה למעלה)
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `LLM_FALLBACK` (C41/C42, כבוי ברירת מחדל — `feature_flags.py:40`)
- **Rollback plan:** לא תועד

### Stage 0 — BOSS Refactor Plan bug fixes (BUG-001–006)
- **תאריך:** 16–17/06/2026
- **סוג:** Bug Fix
- **Requirement:** `BOSS_Refactor_Plan.md` Stage 0; פירוט מלא ב-`BUG_AUDIT_LOG.md`
- **Commit:** `628d2bb` (BUG-005/006), `a462633` (BUG-003/004, ומשפיע גם על BUG-002), `d3243ef`+`1876842` (BUG-002)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא — ראו `BUG_AUDIT_LOG.md`, כל הפריטים "Fixed — ממתין ל-Verify" מעבר ל-BUG-005/006 שמסומנים "Fixed ✅" בקוד בלבד (לא verified-בפרודקשן)
- **Verification ראיה:** אין בדיקה ידנית מתועדת בפרודקשן
- **Docs עודכנו:** `BOSS_Refactor_Plan.md`, `BUG_AUDIT_LOG.md` (קובץ זה)
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### Security fixes — אצווה מרוכזת (07–16/06/2026)
- **תאריך:** טווח 07–16/06/2026
- **סוג:** Security
- **Requirement:** לא ידוע — אין רשומת ROADMAP מאוחדת; כל commit מתעד את עצמו
- **Commit:** `9384f89` (Batch 1 — permission/schema hardening), `aca037b` (fail-closed router + strip public /health), `63966dd` (remove DEV_MODE dead code + worker impersonation fix), `e76c247` (7 audit findings — app.py/tma_api.py/dispatcher), `eb1f42b` (2 HIGH — formula injection + approval TOCTOU), `2bae2e6` (3 MEDIUM findings), `126e34c` (2 HIGH — 3-state approval claim + concurrency lock), `f6281a5` (webhook fail-closed + bus._pending private access), `badfb84` (webhook moved from /<TOKEN> to /telegram), `3a4dbc5`/`ef05dcf` (READ_ONLY_FIELDS[Leads] expansion), `9e609cb` (block 5 non-existent/formula fields)
- **PR:** לא ידוע — דרוש בדיקה ידנית
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין ראיה production; `SECURITY_CHECKLIST.md` מסומן ARCHIVED מ-2026-06-14 ולא מתעד ולידציה לאחר מכן
- **Docs עודכנו:** `docs/governance/SECURITY_CHECKLIST.md` (חלקית, לפני 14/06)
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### Schema fix — tier writable singleSelect
- **תאריך:** לא ידוע מדויק
- **סוג:** Schema Change
- **Requirement:** ROADMAP.md "Known Issues / Tech Debt" (רשומה זו **מיושנת** — ראו AI_CONTEXT.md §8 OPEN RISKS)
- **Commit:** `3d8ab50` ("fix: tier is now writable singleSelect — unblock in READ_ONLY_FIELDS, remove dangerous alias, update tests")
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** כן — סכמה חיה (Airtable MCP, 17/06/2026) מאשרת ששדה `tier` קיים כ-`singleSelect` (`fld4eC2mEYrviL3oP`) בטבלת Leads, תואם להחלטת הקוד
- **Verification ראיה:** Airtable MCP `list_tables_for_base` schema dump, 17/06/2026
- **Docs עודכנו:** **לא** — ROADMAP.md "Known Issues" עדיין מתאר את `tier` כ"לא קיים... החלטה נדרשת" (drift מתועד)
- **Feature Flag:** N/A
- **Rollback plan:** N/A

### C52 — Customer Output Gateway (COG)
- **תאריך:** 18/06/2026 (מוזג)
- **סוג:** Feature
- **Requirement:** ROADMAP.md "Sprint 16/06/2026" → C52
- **Commit:** ראו ROADMAP.md C52 row
- **PR:** #70
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md (בזמן ה-PR); תיעוד זה (CHANGE_CONTROL_LOG) — retroactively, 19/06/2026
- **Feature Flag:** Financial Gate ב-shadow mode (לא חוסם, ESCALATE בלבד)
- **Rollback plan:** לא תועד

### C53 — Screen Filter Gateway
- **תאריך:** 18/06/2026 (מוזג)
- **סוג:** Feature
- **Requirement:** ROADMAP.md "Sprint 18/06/2026" → C53
- **Commit:** `5b07088` (תוכן), `96559d2` (docs)
- **PR:** #75
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא — `py_compile`/`smoke_tests.py`/`test_integration.py` עברו לפני merge, אך production לא אומת
- **Verification ראיה:** ראו AI_CONTEXT.md §2 LAST VERIFIED
- **Docs עודכנו:** ROADMAP.md, AI_CONTEXT.md (תוקן 19/06/2026 — היה מתועד כ-"לא ממוזג", drift תוקן)
- **Feature Flag:** N/A (additive, default behavior נשמר)
- **Rollback plan:** לא תועד

### O4 — Finance Pulse: English schema + Screen Filter Gateway wiring
- **תאריך:** 18/06/2026 (מוזג)
- **סוג:** Feature / Schema Change
- **Requirement:** לא ידוע — אין רשומת ROADMAP מקורית מצוטטת; נוסף ל-ROADMAP.md retroactively ב-19/06/2026
- **Commit:** `f7d7e4f` (migration + wiring), `daab73e` (ExpenseFields.STATUS lowercase fix)
- **PR:** #77
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** "Verified against the live Airtable base via MCP" (commit message `f7d7e4f`) — סכמה אומתה, התנהגות בפרודקשן לא
- **Docs עודכנו:** CHANGELOG.md (בזמן ה-PR); ROADMAP.md/AI_CONTEXT.md — retroactively, 19/06/2026 (drift)
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### C53-A — Structured tool results + verify_execution dict contract
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Feature / Hardening
- **Requirement:** ROADMAP.md "Sprint 19/06/2026" → C53-A; קשור ל-audit item "C53 approval/action truth"
- **Commit:** `ffa3afc`, `3a34529`
- **PR:** #79
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` exit 0 (6 קבצים), `smoke_tests.py` 6/6 PASS, `test_integration.py` 4/4 PASS — כל הריצות מקומיות, לא בפרודקשן
- **Docs עודכנו:** ROADMAP.md, AI_CONTEXT.md, CHANGE_CONTROL_LOG.md (זה) — 19/06/2026
- **Feature Flag:** N/A (משנה contract פנימי של tool results; אין flag — כל tools שהשתנו פעילים תמיד)
- **Rollback plan:** לא תועד — revert PR #79 מ-`main` אם מתגלה רגרסיה בפרודקשן

### A32 / C53-A Hotfix — identity-based NO-TOOL-EVIDENCE enforcement + app.py crash fix
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Bug Fix (P0 — production regression) + Hardening
- **Requirement:** התגלה ב-audit ממוקד על "C53 approval/action truth" (מבוקש על ידי הבעלים, 19/06/2026)
- **תיאור הבאג:** PR #79 שינה 5 tools (`airtable_add`/`airtable_update`/`gmail_draft`/`gmail_send_draft`/`calendar_create_event`) להחזיר `dict` structured במקום `str`, אבל **לא נגע ב-`app.py`** (לפי commit message `3a34529` — "Complete the C53-A contract on tools missing from cherry-pick" מצטט רק `google_tools.py`/`airtable_tools.py`/`rate_limiter.py`). שני מקומות ב-`app.py` עדיין הניחו `str`:
  1. Main tool loop — `result[:80]` על dict → `KeyError: slice(...)` בכל קריאה ישירה (לא דרך approval) ל-4 מתוך 5 הכלים. נתפס ע"י ה-`except Exception` הגלובלי ב-`run_agent()` → המשתמש מקבל "משהו השתבש" גנרי, אבל אין כתיבה מאומתת ל-Airtable/Calendar/Gmail בפועל בתגובה למודל.
  2. Approval callback (`_handle_approval_callback`) — לא קרא ל-`verify_execution()` בכלל; דיווח "✅ הפעולה בוצעה" למשתמש ללא תלות ב-`result["ok"]` — בדיוק כשל "approval truth" שה-audit חיפש.
- **תיקון:** נוסף helper `_tool_user_message()` ב-`app.py`; שני המקומות עכשיו קוראים ל-`verify_execution()`/מחלצים `user_message` לפני logging/slicing/שליחה למשתמש. אם `ok=False` — מדווח כשל בפועל, לא הצלחה כוזבת. בנוסף, חוּזק A32's NO-TOOL-EVIDENCE gate (`core/anti_hallucination.py`): קודם התאמת evidence הייתה מבוססת ניחוש keywords בטקסט התגובה (פספסה קטגוריית Airtable כליל וניסוח "טיוטה נשמרה" ב-Gmail); עכשיו evidence נבדק לפי tool identity (`tool_results_log` נושא שם tool אמיתי + סטטוס `ok` מ-`app.py`) מול סט כלים נדרשים מפורש per-claim-category. כלי שנכשל בעצמו לא נחשב evidence. `_SAFE_FALLBACK` הוחלף ב-`_NO_TOOL_EVIDENCE_FALLBACK` ספציפי יותר. נוסף `test_a32_enforcement.py` שמריץ את `app.run_agent()` קצה-לקצה (Identity/Router/Context/Anthropic מדומים).
- **Commit:** `42dd137` (תוכן), `b34c59f` (docs drift fix)
- **PR:** #80 — **ממוזג ל-`main`** (merge commit `7496628`)
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע — נבדק מקומית בלבד
- **Verification ראיה:** שכפול מדויק של ה-crash (`KeyError: slice(None, 80, None)`) על dict לפני התיקון; `py_compile` exit 0; `core/anti_hallucination.py` self-tests 31/31; `test_c53a.py` 50/50; `test_integration.py` 4/4; `smoke_tests.py` 6/6; `test_a32_enforcement.py` 6/6 — כל הריצות מקומיות
- **Docs עודכנו:** AI_CONTEXT.md (PR #81, `56f3ce9`), CHANGE_CONTROL_LOG.md (זה), ROADMAP.md — 19/06/2026, retroactively (drift תוקן)
- **Feature Flag:** N/A
- **Rollback plan:** revert PR #80 מ-`main` אם מתגלה רגרסיה בפרודקשן (שינוי מבודד ב-`app.py`/`core/anti_hallucination.py`)

### Calendar schema restoration + A32 negative-claim gate
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Bug Fix (P0 — production regression) + Hardening
- **Requirement:** התגלה מתוך transcript פרודקשן (הבעלים) שהראה את הסוכן "ממציא" בדיקת קלנדר ודרישת אימייל לא קיימת
- **תיאור הבאג:** commit `9384f89` (14/06/2026, "permission/schema hardening") הסיר 5 schemas מ-`tools/schemas.py` — בהן `calendar_create_event` — מכיוון ש-`GOOGLE_REFRESH_TOKEN` לא היה מוגדר בזמנו. ה-OAuth כבר חי בפרודקשן (אומת מלוגים אמיתיים — `gmail_draft` הצליח), אבל ה-schema לא הוחזר. תוצאה: הסוכן לא יכול היה לקרוא ל-`calendar_create_event` בכלל (לא משנה role/registry/dispatcher), ופיצה על זה ב"המצאת" צ'קים/דרישות לא קיימות (כמו "אני צריך את האימייל שלך" — לפונקציה אין בכלל פרמטר email). בנוסף, A32 (`core/anti_hallucination.py`) הגן רק על הצלחות מומצאות, לא כשלים מומצאים — הסוכן יכל לדווח "הפגישה לא נשמרה" בלי שום קריאת tool בפועל.
- **תיקון:** (1) הוחזרו 5 schemas ל-`tools/schemas.py` (`search_drive`, `read_drive_file`, `calendar_create_event`, `gmail_send_draft`, `gmail_read`). (2) הורחב `_NO_TOOL_CLAIMS` הקיים ב-A32 לתפוס ניסוח עתיד-קרוב ("יוצר את הפגישה"/"קובע את האירוע") וגם וריאנט "קלנדר" (לא רק "ביומן"). (3) נוסף gate סימטרי חדש — `_NEGATIVE_NO_TOOL_CLAIMS` + `_has_negative_evidence()` — שתופס דיווחי כשל מומצאים. שונה מ-gate ההצלחה: `ok=False` *כן* נחשב evidence תקין (קריאה אמיתית שנכשלה מצדיקה דיווח כשל), בניגוד ל-gate ההצלחה שדורש `ok=True`.
- **Commit:** `aa06c4c`, `4712416`, `ab7c1b4`, `870d874`
- **PR:** #82 — **ממוזג ל-`main`**
- **Review על ידי:** הבעלים (אישור מפורש "yes" להחזרת schemas, ואישור מפורש לבניית negative-claim gate)
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render
- **Verified בפרודקשן:** לא — נבדק מקומית בלבד; ראו PR #83 למטה לאימות חלקי בפרודקשן (calendar+gmail_read אומתו דרך לוגים אחרי deploy)
- **Verification ראיה:** `py_compile` exit 0; `smoke_tests.py` PASS; `test_integration.py` 4/4; `core/router/test_router.py` 29/29; `test_a32_enforcement.py` 6/6; `test_c53a.py` 50/50; טסט inline ייעודי אימת שכשל אמיתי (`ok=False`) ממשיך לעבור דרך ה-gate החדש בלי לדרוס אותו ב-fallback
- **Docs עודכנו:** CHANGE_CONTROL_LOG.md (זה), ROADMAP.md — 19/06/2026
- **Feature Flag:** N/A
- **Rollback plan:** revert PR #82 מ-`main` אם מתגלה רגרסיה — שינוי מבודד ב-`tools/schemas.py`/`core/anti_hallucination.py`

### Drive error reporting fix + daily_digest Payments English-schema fix
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Bug Fix
- **Requirement:** התגלה מבדיקת פרודקשן ידנית של הבעלים אחרי deploy של PR #82 (לוגים: calendar ✅, gmail_read ✅, drive ❌)
- **תיאור הבאג (1 — Drive):** `drive_search()`/`drive_read_file()` ב-`tools/google_tools.py` קראו ל-`r.json().get("files", [])` בלי לבדוק `r.status_code`. לוג פרודקשן הציג `403 Forbidden` מ-Drive API, אבל הקוד דיווח "לא נמצא כלום בדרייב" — כישלון הרשאות דיווח כ"לא קיים". הסיבה הסבירה ביותר ל-403: ל-`GOOGLE_REFRESH_TOKEN` אין Drive scope (תיקון credential, לא קוד — מחוץ לטווח PR זה).
- **תיאור הבאג (2 — Daily Digest):** `daily_digest.py`'s `_upcoming_payments()` חיפש טבלה `"תשלומים (Payments)"` עם שדות עבריים (`סכום`/`תאריך`/`סטטוס`/`אסמכתא`, ערך `'התקבל'`). אומת מול ה-Airtable **החי** (base `app4bcgoX7t0HUVnm`, table `tbl027IEVotG1cy46`) שהטבלה/השדות כבר `Payments`/`reference`/`amount`/`date`/`status` (ערך `'received'`) — `airtable_schema.py`'s `PaymentFields`/`PaymentStatus` כבר תיקנו את זה, אבל `daily_digest.py` מעולם לא עבר לקבועים החדשים. תוצאה: סקציית התשלומים בדוח הבוקר החזירה אפס רשומות תמיד.
- **תיקון:** (1) שלושת קריאות ה-Drive API ב-`google_tools.py` בודקות `status_code` ומחזירות שגיאה מפורשת. (2) `daily_digest.py` עבר לייבא ולהשתמש ב-`Tables.PAYMENTS`/`PaymentFields`/`PaymentStatus` מ-`airtable_schema.py` במקום literals עבריים.
- **Commit:** `86087e6` (Drive), `acf676f` (Daily Digest)
- **PR:** #83 — **ממוזג ל-`main`** (merge commit `7df22c3`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render
- **Verified בפרודקשן:** לא — נבדק מקומית בלבד
- **Verification ראיה:** `py_compile` exit 0; `smoke_tests.py` PASS; `test_integration.py` 4/4; `core/router/test_router.py` 29/29; שדות/ערכים אומתו ישירות מול live schema דרך Airtable MCP (`get_table_schema`)
- **Docs עודכנו:** CHANGE_CONTROL_LOG.md (זה), ROADMAP.md — 19/06/2026; PR #83 comment תיעד 8 קבצים נוספים עם drift דומה (`tma_api.py`, `tools/airtable_tools.py`, `schema_intelligence.py` ועוד) — **לא תוקנו**, מחוץ לטווח הסשן
- **Feature Flag:** N/A
- **Rollback plan:** revert PR #83 מ-`main` אם מתגלה רגרסיה — שינוי מבודד ב-`tools/google_tools.py`/`daily_digest.py`

### F16 Media Layer — Batch א/ב/ג (STT provider fix, Drive upload contract, Airtable metadata gateway)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Feature (new, flag-gated — קוד לא מחובר ל-pipeline החי עדיין)
- **Requirement:** F16_MEDIA_LAYER_SPEC.md (ספק חיצוני), batches א/ב/ג, מבוקש ע"י הבעלים בסדר קפדני
- **תיאור הבאג:** הספק המקורי כינה את הפיצ'ר "F12" ואז "F09" — שניהם תפוסים ב-ROADMAP.md (F12=Model Provider Adapter, F09=Lead Qualifier Wire-up). תוקן ל-F16. בנוסף, `voice_stt_adapter.py`'s self-test ו-`drive_adapter.py`'s self-test שניהם השתמשו ב-`unittest.mock.patch("module_name.fn", ...)` כדי למנוע קריאות רשת אמיתיות בזמן `python3 module_name.py` — דפוס שנכשל בשתיקה: הרצה ישירה של סקריפט יוצרת `__main__` כ-namespace הרץ, אבל `patch("module_name.fn")` מבצע `import module_name` טרי שיוצר עותק מודול שני, נפרד, ב-`sys.modules` — ה-patch פוגע בעותק הלא-רץ. תוצאה: `voice_stt_adapter.py` ביצע קריאת רשת אמיתית ל-`api.openai.com` (נחסם ע"י sandbox allowlist), ו-`drive_adapter.py` החזיר תוצאות שגויות/None כי לא היה OAuth מוגדר בסביבת הבדיקה.
- **תיקון:** Batch א — `voice_stt_adapter.py` נכתב מחדש: OpenAI Whisper כ-PRIMARY חי (`OPENAI_API_KEY` קיים), Groq כ-stub מוער לא מחובר; קודי שגיאה `OVERSIZED`/`STT_FAILED` (הוסר `EMPTY_AUDIO` — לא בספק). Batch ב — `drive_adapter.py` נכתב מחדש: `upload_file(file_bytes, filename, mime_type, parent_folder_id)` עם `parent_folder_id` חובה (אין default), ניקוי temp file תמיד ב-`finally`, `_safe_filename` מנקה רק תווים אסורים ל-Drive (עברית native). Batch ג — `media_gateway.py` נמצא תואם 100% לספק כבר מהבנייה המקורית, אפס שינוי קוד. שני באגי ה-self-test תוקנו ע"י החלפת `patch("module.fn")` ב-`patch.object(sys.modules[__name__], "fn")` בשני הקבצים. `test_media_layer.py` עודכן בשני סבבים נפרדים (לפי הוראה מפורשת לאחר כל batch) להתאים לקונטרקט החדש — 33/33 עוברים.
- **Commit:** `9485431` (Batch א + test round 1), `33a560c`/`d073b1f` (Batch ב + test round 2), Batch ג (media_gateway.py ללא שינוי קוד, נכלל ב-PR #97)
- **PR:** #96 (Batch א), #97 (Batch ב+ג) — **שניהם ממוזגים ל-`main`** (merge commit `8f9c648`)
- **Review על ידי:** הבעלים (אישר כל batch בנפרד, כולל שני amend+force-push מפורשים ל-`test_media_layer.py`)
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render (קוד לא מחובר ל-pipeline החי — אין סיכון production מעצם המיזוג)
- **Verified בפרודקשן:** N/A — אין feature flag פעיל, הקוד לא נקרא מאף מקום חי עדיין (Batch ד-ז עדיין לא בנו את ה-hooks)
- **Verification ראיה:** מוזג אומת בפועל דרך `git fetch origin main` + grep על תוכן הקבצים שמוזגו ב-`origin/main` (`OVERSIZED`/`STT_FAILED` ב-`voice_stt_adapter.py`, `parent_folder_id` בחתימת `upload_file`/`_upload_to_drive` ב-`drive_adapter.py`) — לא הסתמכות על git log/PR status בלבד, לפי AGENTS.md POST-MERGE VERIFICATION. self-tests עברו (34/34 → 33/33 לאחר הסרת assertion אחת, צפוי).
- **Docs עודכנו:** ROADMAP.md (נוסף F16, עודכן header), CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` — עדיין לא קיימים ב-`feature_flags.py`; יתווספו ב-Batch ה כשה-hooks ל-`app.py` נבנים
- **Rollback plan:** revert PR #96/#97 מ-`main` אם נדרש — שינוי מבודד בשלושה קבצים עצמאיים (`voice_stt_adapter.py`, `drive_adapter.py`, `media_gateway.py` ללא שינוי), אפס import מקוד פעיל אחר

### F16 Media Layer — Batch ד (`media_handler.py` bug fix)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Bug fix (קוד היה כבר קיים ב-`main` מ-commit `ee4d2ed` קודם, לא נכתב מאפס)
- **Requirement:** F16_MEDIA_LAYER_SPEC.md סעיף 4, מבוקש ע"י הבעלים. בתחילת המימוש התגלה ש-`media_handler.py` **כבר קיים** ב-`main` (מ-`ee4d2ed`, לפני מאמץ הבאצ'ים), עם שמות פונקציות שונים מהספק (`handle_voice_note()`/`handle_file_upload()`/`handle_tma_upload()` במקום `handle_telegram_media()`) וכבר מחובר ל-`app.py`/`tma_api.py`. הוצג למשתמש כקונפליקט (`AskUserQuestion`) — הוכרע: לשמור שמות קיימים, לתקן internals בלבד, לא לגעת ב-`app.py`/`tma_api.py`.
- **תיאור הבאג:** (1) `upload_file()` נקרא עם `domain=domain` — kwarg שלא קיים בחתימה האמיתית של `drive_adapter.upload_file(file_bytes, filename, mime_type, parent_folder_id)` (תוקנה ב-Batch ב) — `TypeError` מובטח בכל הפעלה אמיתית, לא התגלה ע"י `test_media_layer.py` הקיים כי 33 ה-assertions שלו בודקים רק short-circuits (oversized/duplicate), לא את ה-success path. (2) כשל כתיבה ל-Airtable לאחר Drive upload מוצלח הוחזר כ-`MediaResult(ok=True, asset_id="")` בשקט — ללא דרך לצרכן לזהות כשל.
- **תיקון:** נוסף `_resolve_drive_folder(domain)` המשתמש ב-`drive_adapter._get_upload_folder(domain)` לפני קריאה ל-`upload_file()`. נוסף בדיקת `if not asset_id` עם קוד שגיאה `ASSET_SAVE_FAILED`; כשל resolve מחזיר `DRIVE_FAILED`. הודעות שגיאה תורגמו לעברית. נוספו 4 self-test scenarios חדשים (`media_handler.py`'s `__main__`) שמכסים את ה-success path שחשף את הבאג. שמות פונקציות/`_idem_store`/קודי שגיאה קיימים (`FILE_TOO_LARGE`/`DUPLICATE`) לא שונו — `test_media_layer.py` תלוי בהם במדויק.
- **Commit:** `0fcf81b`
- **PR:** #98 — **מוזג ל-`main`** (merge commit `8dd3bca`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render (flag כבוי — אין סיכון production)
- **Verified בפרודקשן:** N/A — `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` כבויים
- **Verification ראיה:** `git fetch origin main` + grep על `_get_upload_folder`/`DRIVE_FAILED`/`ASSET_SAVE_FAILED` ב-`origin/main:media_handler.py` — תואם. `test_media_layer.py` 33/33 עוברים גם לפני וגם אחרי התיקון.
- **Docs עודכנו:** ROADMAP.md, CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` — כבויים כברירת מחדל (לא השתנה)
- **Rollback plan:** revert PR #98 מ-`main` — שינוי מבודד ל-`media_handler.py` בלבד

### F16 Media Layer — Batches ה/ו/ז (app.py hooks, tma_api.py endpoint, airtable_schema.py — gap-fill)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Feature gap-fill (רוב הקוד כבר היה קיים ומחובר; לא מימוש מאפס)
- **Requirement:** F16_MEDIA_LAYER_SPEC.md, מבוקש ע"י הבעלים לפתוח `claude/f16-final` ולממש שלושה batches.
- **תיאור הממצא:** לפני מימוש, אומת ש-Batch ה (`_handle_telegram_media()` ב-`app.py`) ו-Batch ו (`/api/tma/upload` ב-`tma_api.py`) **כבר מחוברים** ל-pipeline החי מאז `ee4d2ed` — לא רק קוד עומד, אלא בפועל נקראים מה-webhook/route. Batch ז (`Tables.MEDIA_FILES`/`MediaFileFields` ב-`airtable_schema.py`) כבר קיים ומלא, מכסה את כל השדות ש-`media_gateway.py` כותב. נמצאו 2 gaps אמיתיים בלבד.
- **תיקון:** `app.py` — נוסף `bot.send_chat_action()` (typing/upload_document) לפני עיבוד voice/photo/document ב-`_handle_telegram_media()`. `tma_api.py`/`media_handler.py` — נוסף קליטת `linked_lead_id` מה-multipart form ב-`/api/tma/upload`, מועבר ל-`handle_tma_upload()` → `handle_file_upload()`. `domain` נשאר נגזר מה-identity המאומת בכוונה (לא משדה form של הלקוח) — מנע tenant scope הנקבע ע"י הלקוח. `airtable_schema.py` — אפס שינוי (כבר שלם).
- **Commit:** `32c6629`
- **PR:** #99 — **מוזג ל-`main`** (merge commit `4924030`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render (flag כבוי — אין סיכון production)
- **Verified בפרודקשן:** N/A — `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` כבויים
- **Verification ראיה:** `git fetch origin main` + grep על `send_chat_action.*upload_document`, `linked_lead_id` ב-`origin/main:app.py`/`tma_api.py`/`media_handler.py` — תואם. `test_media_layer.py` 33/33, `media_handler.py` self-test 4/4, `smoke_tests.py` עובר.
- **Docs עודכנו:** ROADMAP.md, CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` — כבויים כברירת מחדל (לא השתנה). **F16 Media Layer הושלם במלואו (כל 7 batches) — כבוי בפרודקשן עד הדלקה מפורשת + יצירת טבלת "Media Files" ב-Airtable.**
- **Rollback plan:** revert PR #99 מ-`main` — שינוי מבודד בשלושה קבצים, 17 שורות בלבד

### F16 Media Layer — Docs correction (ROADMAP/AI_CONTEXT/CHANGELOG/CHANGE_CONTROL_LOG)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Docs-only correction, אפס שינוי קוד
- **Requirement:** בקשת הבעלים — אחרי שאומת ש-PR #99 כבר מוזג ל-`main` (`pull_request_read`, merged_by=10026782, לא ע"י Claude), עדכון `ROADMAP.md`/`AI_CONTEXT.md` לשקף ש-F16 הושלם במלואו, כולל commit hash + תאריך, ב-PR נפרד קטן.
- **תיאור:** `ROADMAP.md` — header (שורה 3) + סעיף F16 (שורות 412-424) עודכנו לשקף סטטוס אמיתי per-batch (לא "תכנון", אלא "✅ מוזג"/"✅ קיים מהבנייה המקורית" לפי המקרה), כולל תיקון הטענה השגויה על feature flags (הם קיימים ב-`feature_flags.py`, כבויים כברירת מחדל — אומת ב-grep). `AI_CONTEXT.md` — header, Executive Summary, סעיף "חלקי", שתי רשומות חדשות ב-"Completed Since Last Update" (PR #98/#99), "Next Priorities" item 0. `CHANGELOG.md` — תוקן ה-Unreleased entry הקיים. `CHANGE_CONTROL_LOG.md` — שתי רשומות חדשות נוספו (append-only, היסטוריה לא נערכה).
- **Commit:** `1ad9919`
- **PR:** #100 — **מוזג ל-`main`** (merge commit `de5765b`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** N/A — docs-only, אין קוד רץ
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** `git fetch origin main` + grep אחרי כל הטענות המתוקנות ב-4 הקבצים על `origin/main` — אומת שאין יותר טענות "לא מומש"/"עדיין לא בנוי" שמתייחסות ל-F16/Batch ד/ה/ו/ז. `git diff --stat` אומת diff מוגבל ל-4 קבצי docs בלבד (61 insertions/18 deletions).
- **Docs עודכנו:** זה עצמו הוא ה-docs update
- **Feature Flag:** ללא שינוי
- **Rollback plan:** revert PR #100 — docs-only, אפס סיכון

### N07 — Schema Governance script (`tools/schema_governance.py`)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** New feature, קובץ יחיד חדש (קוד שלם מאפס)
- **Requirement:** ROADMAP.md N07 (עדיפות גבוהה), מבוקש ע"י הבעלים. מניע: BUG-008 (`Leads."Business Outcome"` trailing space שהתגלה ad-hoc).
- **תיאור:** `tools/schema_governance.py` — סקריפט standalone, READ ONLY לחלוטין. שולף live schema מ-Airtable Metadata API (`GET /meta/bases/{baseId}/tables`, httpx, Bearer auth מ-env). משווה מול `airtable_schema.py` (import, לא parse) דרך `TABLE_CLASS_MAP`/`_class_values` **קיימים** מ-`schema_audit.py` (יובאו, לא שוכפלו — נמנע מיפוי כפול שיכול לסחוף). מזהה 5 סוגי drift: שדה בקוד חסר ב-live (whitespace-tolerant match, נמנע double-report) → ERROR; שדה ב-live שלא בקוד → WARNING; trailing/leading spaces בשם שדה → WARNING; trailing/leading spaces ב-`singleSelect`/`multipleSelects` choice names → WARNING; שינוי סוג שדה → ERROR (מול ריצה קודמת שנשמרה ב-`schema_drift_report.json` בעצמו — baseline זמני, כי `airtable_schema.py` לא מכיל מטא-דאטה של סוגים בכלל). מדפיס דוח עברית ל-console, שומר `schema_drift_report.json` (נוסף ל-`.gitignore` — לא מתווסף ל-git), exit 1 אם יש ERROR ≥1 אחרת 0. self-test (`--self-test`) עם mock schema, אפס קריאות רשת. אינו נוגע ב-`schema_cache.json` (בבעלות `schema_validator.py`).
- **החלטות תכנון שתועדו במפורש (לא הוסתרו):** (1) baseline זמני לבדיקת סוג שדה (לא קוד) — כי אין מטא-דאטה של סוג ב-`airtable_schema.py`. (2) הוצא מהיקף: "select options חסרות/כפולות" — הופיע רק בטיוטה לא-פורמלית, לא ברשימה הממוספרת הסופית. (3) נמצא ניגוד בין הדוגמה החזותית בספק (`Assets."Purchase Cost"` כ-WARNING) לכלל הסיווג המספרי המפורש (שדה חסר מ-live=ERROR) — הוכרע ללכת לפי הכלל המספרי כסמכותי, הדוגמה החזותית רק עיצובית.
- **Commit:** `cbe9363`
- **PR:** #101 — **מוזג ל-`main`** (merge commit `e465eff`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** N/A — כלי CLI עצמאי, לא חלק מה-pipeline החי, אין deploy
- **Verified בפרודקשן:** N/A — לא נקרא מאף קוד pipeline; טרם הורץ פעם ראשונה מול live Airtable אמיתי (אין credentials בסביבת ה-sandbox)
- **Verification ראיה:** `git fetch origin main` + grep על תוכן `tools/schema_governance.py` ו-`.gitignore` ב-`origin/main` ישירות — תואם. `python3 -m py_compile` עבר. `--self-test`: 6/6 assertions עברו. `smoke_tests.py` עבר במלואו.
- **Docs עודכנו:** ROADMAP.md (N07 → ✅ הושלם), CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** ללא — כלי CLI עצמאי, לא flag-gated
- **Rollback plan:** revert PR #101 — קובץ יחיד חדש + שורה אחת ב-`.gitignore`, אפס import מקוד פעיל אחר, אפס סיכון

### C56 — Approval Policy: Emergency Window + OTP + Policy Gate (docs correction)
- **תאריך:** 23/06/2026 (תיקון תיעוד; הקוד עצמו מוזג כבר ב-17/06/2026)
- **סוג:** Docs correction
- **Requirement:** לא היה ב-ROADMAP.md בכלל לפני תיקון זה; `BUG_AUDIT_LOG.md` תיעד "Merged: לא" בזמן שהקוד היה כבר מוזג. התגלה בעת בדיקת ענפי `claude/*` לא ממוזגים לקראת ניקוי — `claude/meta-whatsapp-phase-1-q6pp3e` (הענף שממנו עלה PR #69) המשיך להצטבר commits **אחרי** שה-PR שלו עצמו מוזג, כולל ניסיון תיקון תיעוד דומה שעצמו לא הגיע ל-`main`.
- **Commit (קוד, לא docs):** `8209d36`, `a57fd7f`, `44457dd`, `92e4b2b` — **merge commit `4e933b0`**
- **PR:** #69 — https://github.com/10026782/My-bot/pull/69
- **Review על ידי:** 10026782 (owner — `mergedBy` ב-GitHub API)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `gh pr view 69 --json state,mergedAt,mergedBy,mergeCommit` → `{"state":"MERGED","mergedAt":"2026-06-17T18:56:00Z","mergedBy":"10026782","mergeCommit":"4e933b0536c03e270f7e4547e7c1d6a0a232b09e"}`; `git merge-base --is-ancestor 4e933b0 main` → exit 0 (אב-קדמון בפועל, לא רק PR API). מטריצת 12 התרחישים (Low/Medium/High/Critical × mobile/desktop/web × window/OTP) שאומתה בזמן הבנייה המקורית (17/06/2026) לא הורצה חזרה בתיקון תיעוד זה — אין שינוי קוד.
- **Docs עודכנו:** ROADMAP.md (נוסף C56, לא היה קיים), AI_CONTEXT.md, BUG_AUDIT_LOG.md, RELEASE_CHECKLIST.md
- **Feature Flag:** `EMERGENCY_WINDOW` — כבוי כברירת מחדל; ללא שינוי בתיקון תיעוד זה
- **Rollback plan:** revert — docs-only, אפס סיכון פונקציונלי

### N12 — Daily Git Audit scheduler wiring
- **תאריך:** 23/06/2026
- **סוג:** New feature (flag off) + docs salvage
- **Requirement:** ROADMAP.md N12; חולץ מ-2 ענפים לא ממוזגים לפני מחיקתם במהלך ניקוי ענפי `claude/*`
- **תיאור:** `daily_git_audit.py` חובר ל-`scheduler.py` (`_job_daily_git_audit`, `GIT_AUDIT_TIME` env var, ברירת מחדל `06:45`). נוספו ל-`daily_git_audit.py`: `check_unmerged_vs_roadmap()`, `check_duplicate_schemas()`, `check_recent_commits()`, `check_cors_env_drift()`. תוקן bug ב-precedence שהיה בענף המקורי: בדק `BOSS_CURRENT_STATE.md` לפני `ROADMAP.md` — הפוך מהכרזת `ROADMAP.md` כ"מקור האמת היחיד, כל מסמך תכנון אחר הוא ARCHIVE". `_CANONICAL_DOC_PRIORITY` סודר מחדש: `ROADMAP.md` ראשון.
- **Commit:** `c26c5e1`
- **PR:** #108 — **מוזג ל-`main`**
- **Review על ידי:** הבעלים
- **Deploy תאריך:** N/A — דגל כבוי, אין שינוי התנהגות בפרודקשן
- **Verified בפרודקשן:** N/A — `GIT_AUDIT_SCHEDULER=off`
- **Verification ראיה:** `py_compile` נקי; פונקציות הבדיקה הורצו ידנית מול הריפו והחזירו ממצאים תקינים (כולל גילוי אמיתי של ענף תקוע אחד); `smoke_tests.py` ללא רגרסיה (אותם 2 כשלים תלויי-סביבה כמו על `main`)
- **Docs עודכנו:** ROADMAP.md (N12 חדש), AI_CONTEXT.md, CHANGELOG.md
- **Feature Flag:** `GIT_AUDIT_SCHEDULER` — כבוי כברירת מחדל
- **Rollback plan:** revert PR #108 — דגל כבוי, אפס סיכון פונקציונלי מיידי

### Docs salvage — `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md`
- **תאריך:** 23/06/2026
- **סוג:** Docs-only, commit ישיר ל-`main` (לא PR — אישור משתמש מפורש)
- **Requirement:** נמצא תוך כדי ניקוי ענפי `claude/*` — מסמך audit ארכיטקטוני (257 שורות, ללא קוד) שהתקיים רק בענף `claude/spec-c52-implementation-uqmu1g`, שלא מוזג מעולם
- **תיאור:** מסמך audit מלא של 4 מנגנוני approval + 2 kill switches, risk matrix, gap analysis, ומפרט test harness ל-C53 (test categories A-J). נכתב 17/06/2026 מול הקוד של אותו יום. נוסף הערת provenance בראש המסמך + הערה ב-`CLAUDE.md` (מבדיל מ-`Approval_Policy_Spec.md` החסר — מסמך אחר)
- **Commit:** `783a680`
- **PR:** ללא — commit ישיר ל-`main`
- **Review על ידי:** הבעלים (אישר במפורש "לשמור כקובץ ב-main, לא PR")
- **Deploy תאריך:** N/A — docs-only
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** תוכן הקובץ זהה ל-blob המקורי בענף שנמחק (`git show <branch>:<path>` לפני המחיקה); `git diff --stat` אומת diff מוגבל ל-2 קבצים (`APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` חדש + שורה אחת ב-`CLAUDE.md`)
- **Docs עודכנו:** זה עצמו + `CLAUDE.md`
- **Feature Flag:** אין — docs-only
- **Rollback plan:** revert commit `783a680` — docs-only, אפס סיכון

### C68 — BUG-NEW-01/01b/02: Lead Capture Fixes (28/06/2026)
קבצים: `lead_capture.py`, `identity.py` | Score=0 + display_name fix + dict contract | PR #169

### C69 — CXX Action Integrity (28/06/2026)
קבצים: `core/action_result.py` (חדש), `core/request_context.py` (חדש), `core/claim_gate.py` (חדש)
Evidence: 16/16 + 33/33 tests | PR #169

### C70 — BUG-FOUND-01: FOUND fix + real record_id (29/06/2026)
קובץ: `lead_capture.py` | `claim_type=FOUND` + record_id אמיתי | PR #170

### C71 — A32 CRM pattern split + Lead evidence (29/06/2026)
קובץ: `core/anti_hallucination.py` | FOUND≠CREATED, 3 patterns + `lead_capture_result`→`tool_results_log` | PR #171

### C72 — BUG-NEW-03: airtable_security audit fix (29/06/2026)
קובץ: `tools/airtable_security.py` | `str(result)[:60]` + `try/except` | PR #172

### C73 — BUG-NEW-04: Leads Write Gate (29/06/2026)
קבצים: `tools/airtable_security.py`, `tools/dispatcher.py`
Evidence: 6/6 gate tests + 9/9 security tests | PR #172

### C74 — N-LEAD-EVENT + domain-keyed memory_key + metadata fix (29/06/2026)
קבצים: `lead_capture.py`, `airtable_schema.py`
Lead Events + `capture_lead_event()` + `memory_key=boss_hq:+972:domain` + metadata warning only | PR #172

### C75 — BUG-NEW-07: Lead Buffer (29/06/2026)
קבצים: `core/lead_buffer.py` (חדש), `tools/dispatcher.py`, `app.py`
Evidence: 22/22 buffer tests | PR #176

### C76 — BUG-DH-01: missing_penalty fix + domain param (30/06/2026)
קובץ: `decision_confidence.py` | `missing_penalty` מחוסר בפועל + `calc_confidence(domain=)` פרמטר חדש
הערה: הוסט מ-C75 (SPEC_DECISION_HUB_SESSION_DOC) למניעת collision עם C75 של Lead Buffer.

### C77 — BUG-DH-05: domain drift fix via request_state (30/06/2026)
קבצים: `core/request_state.py` (חדש), `app.py` | `RequestState.domain` מועדכן אחרי Router

### C78 — Stage 6: Decision Orchestrator (30/06/2026)
קובץ: `decision_orchestrator.py` (חדש)
Lifecycle: `COLLECTING→BLOCKED→REVIEW→AWAITING→DECIDED→CLOSED` | `precomputed_confidence`

### C79 — Core Reasoning Layer (30/06/2026)
קבצים חדשים: `core/reasoning_entity.py`, `core/reasoning_ports.py`, `core/reasoning_engines.py`, `core/request_state.py`, `core/adapters/decision_adapter.py`, `core/adapters/leads_adapter.py`
טסטים: `test_core_reasoning.py` (59), `test_core_reasoning_integration.py` (58+2 xfail) | `conftest.py` (חדש)
ספקים: `SPEC_Core_Reasoning_Layer.md`, `SPEC_Stakeholder_Pressure_Pattern.md` (v2)

### C80 — CI: pytest steps + conftest (30/06/2026)
קובץ: `.github/workflows/ci.yml` | +2 שלבים (pytest collect + pytest core reasoning), 7 test files

### C81 — Approval Gateway Safety — Section 1 bugs (30/06/2026)
קבצים: `core/router/intent_router.py`, `core/anti_hallucination.py`, `event_bus.py`, `app.py`, `test_approval_gateway_safety.py` (חדש)
PR: #188 | באגים: BUG-039..BUG-044 | 25/25 בדיקות חדשות + 40/40 A32 self-tests
- **BUG-039** router word-collision: `בדיקה`/`test` כ-anchor בלבד (לא substring)
- **BUG-040** A32 Sheets: gate חדש ל-`sheets_append` — חוסם false-success claims
- **BUG-041** A32 fake-approval: `__approval_queued__` sentinel נדרש לביטויי "⏳ ממתינה לאישור"
- **BUG-042** ExecutedActionCache: fingerprint SHA1 TTL-600s מונע re-queue אחרי אישור
- **BUG-043** `_mutating_approvals_this_turn`: חוסם כלי שני הדורש אישור באותו תור Agent
- **BUG-044** `send_recovery.confirmed` handler: subscribe חסר ב-`app.py` — P0 silent data loss

### C82 — C53 Infrastructure: single source of truth + EMERGENCY_STOP_AUTOMATION (30/06/2026)
קבצים: `tool_registry.py`, `event_bus.py`, `tools/dispatcher.py`, `followup_engine.py`, `scheduler.py`
PR: #189 | באגים: BUG-045, BUG-046
- **BUG-045** `EMERGENCY_STOP_AUTOMATION` לא נאכף ב-`run_followup_scan()` ו-scheduler jobs
- **BUG-046** `TOOLS_REQUIRING_APPROVAL` — מקור אחד ב-`tool_registry` (frozenset), `event_bus`/`dispatcher` מייבאים ממנו

### BUG-018 — Mojibake/encoding corruption ב-`app.py` (132 שורות)
- **תאריך:** 25/06/2026
- **סוג:** Bug fix, קובץ קיים (`app.py` בלבד)
- **Requirement:** דווח ע"י המשתמש (לא ב-ROADMAP.md) — ג'יבריש בהודעות בוט בעברית. ראה `BUG_AUDIT_LOG.md` BUG-018 לפירוט מלא.
- **תיאור:** טקסט עברי וסימבולים ב-`app.py` עברו בעבר decode שגוי דרך codepage `cp1255` (Windows Hebrew) במקום UTF-8, ונשמרו בחזרה כ-UTF-8 — corruption קבוע בקובץ עצמו (לא בעיית runtime/parse_mode). אותר ותוקן באמצעות hybrid codec (cp1255 + raw-byte fallback ל-12 בתי-קוד שלא מוגדרים ב-cp1255, שעברו דרך identity passthrough בקורפציה המקורית): round-trip `hybrid_encode(line).decode('utf-8')` משמש כגלאי corruption גנרי בטוח (false-positive נמוך מאוד על טקסט תקין). אותרו ותוקנו 132 שורות (78 עם אותיות עבריות + 54 נוספות symbols/emoji/box-drawing ללא עברית, שנמצאו רק בסקאן הגנרי השני). UTF-8 BOM של הקובץ נשמר. בנוסף נבדקה טענת המשתמש על ערבוב `Markdown`/`MarkdownV2` (parse_mode) כגורם — **נשללה**: נקודת ה-`MarkdownV2` היחידה בקובץ (שורה ~356, `cmd_done`) מבצעת escape נכון (`\!`, `\+`); הג'יבריש שהמשתמש ראה היה ה-mojibake, לא בעיית escaping. הצעת המשתמש למעבר גורף ל-`parse_mode="HTML"` בכל קריאות `send_message` **לא בוצעה** — הוחלט שהיא out-of-scope (לא נדרשת לתיקון הבאג בפועל, ותדרוש המרת כל עיצוב `*bold*`/`_italic_` הקיים ל-HTML tags ב-~10 call sites) — לא הוסתר, מתועד גם ב-`BUG_AUDIT_LOG.md`.
- **Commit:** `b5717da` (+ `80ae008` תיקון תיעוד) — **merge commit `9f408e7`**
- **PR:** #154 — **מוזג ל-`main`**, מאומת עצמאית דרך `mcp__github__pull_request_read` (`merged: true`) וגם `git fetch origin main` (`9f408e7` הוא tip של `origin/main`, ה-branch `claude/new-session-be1ckb` נמחק מה-remote לאחר המיזוג)
- **Review על ידי:** 10026782 (owner — `merged_by` ב-GitHub API)
- **Deploy תאריך:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `python3 -m py_compile app.py` עבר; `python3 smoke_tests.py` — 2 כשלים תלויי-סביבה קיימים מראש (`flask`/`httpx` חסרים בסביבת sandbox, לא קשור לשינוי); `python3 test_integration.py` 4/4; `python3 session_store.py` 40/40; `python3 test_c53a.py` 50/50; `git diff --stat app.py` → `1 file changed, 132 insertions(+), 132 deletions(-)`; כל 132 השינויים נסקרו ידנית שורה-שורה ב-diff המלא; סקאן חזרה (round-trip) על הקובץ המתוקן אישר 0 שורות corruption שיוריות; `file app.py` אישר פורמט UTF-8 with BOM ללא שינוי.
- **Docs עודכנו:** `BUG_AUDIT_LOG.md` (BUG-018), `CHANGE_CONTROL_LOG.md` (זה)
- **Feature Flag:** N/A — תיקון טקסט סטטי, ללא flag
- **Rollback plan:** revert commit — שינוי טקסט בלבד ב-קובץ קיים, ללא שינוי לוגיקה, סיכון נמוך

## 30/06/2026 — ניקוי ענפים לא-ממוזגים — בוצע
**הקשר:** המשך לרשומת "סקירת ענפים לא-ממוזגים" — לאחר סקירת diff מלאה פר-ענף.

**נמחקו (11):**
claude/gifted-clarke-qoj3mz, 10026782-patch-1, f21-decision-orchestrator,
furniture-funnel-clean, test/stale-airtable-gateway, cursor/dev-environment-setup-5fb2,
bot.boss, phase-5-marketing, phase-4-knowledge, phase-3-contacts,
cursor/phase-1-stability-5fb2

**הערה:** 9 נמחקו בפועל, 2 (test/stale-airtable-gateway, phase-3-contacts) כבר לא היו קיימים ב-remote בעת הביצוע.

**נשמרו במכוון:**
- fix/c53-approval-hardening — ממתין לספק מיזוג ממוקד (3 פערים זוהו: recovery subscriber חסר, EMERGENCY_STOP_AUTOMATION לא נאכף ב-scheduler, PendingActionsStore לא thread-safe — טעון אימות מחדש מול main הנוכחי)
- cursor/guards-file-audit-report-1742 — ממתין להעברת ממצאים תקפים ל-BUG_AUDIT_LOG.md עם אימות מחודש

**אימות:** git ls-remote מול GitHub אישר שכל 11 השמות אינם קיימים ב-remote, אין PR פתוח על אף אחד מהם. main וענפי עבודה פעילים (fix/c53-approval-hardening, cursor/guards-file-audit-report-1742, claude/leads-write-gate-verify-aodpud) נשמרו.

**סטטוס:** ✅ הושלם — ראה משימות המשך פתוחות לעיל

## 01/07/2026 — סקירת fix/c53-approval-hardening — הוחלט לא למזג
סקירת diff מלאה מול `main=d16fc96`.
אין cherry-pick מהענף. הממצאים הוסבו ל-8 משימות חדשות (`C81-FU`, `C82-FU`, `C83`–`C88`; ראה ROADMAP).
הענף ימחק לאחר רישום המשימות.

## 02/07/2026 — PR #203 מוזג: C89 Stage 3 Capture Policy + BUG-NEW-12 + BUG-IC-01
**ענף:** `claude/session-duplication-claimgate-gnkfiy` (נמחק לאחר מיזוג)
**Merge commit:** `bb81e6c` (לאחר `c9e020d`, PR #202)

**מה נכלל:**
1. **C89 — Stage 3 Capture Policy:** `core/ingress_classifier.py` (חדש) — `IngressClassification` + `classify_ingress()` כנקודת כניסה יחידה לסיווג קלט טקסט; 5 tiers (SIMPLE_CAPTURE/CLEAN_BATCH/MIXED_BATCH/EXPORT-TABLE/UNKNOWN). `core/lead_candidate_handler.py` מחווט דרך המסווג לפני כל פרסור. `FEATURE_AUTO_CAPTURE` (כבוי כברירת מחדל) — ללא שינוי התנהגות בפרודקשן עד הפעלה מפורשת.
2. **BUG-NEW-12 (session_store.py):** `_find_record_id_in_db` תוקן — regex גנרי (`rec\w+`) הוחלף ב-`_SESSION_RECORD_RE` הממוקד לבולטי רשומה (`• [recXXX]`) בלבד, מונע POST כפול כשקיימות מספר רשומות Session לאותו sender. ראה BUG-047 ב-BUG_AUDIT_LOG.md.
3. **BUG-IC-01 (core/router/):** ביטויים חשופים ("סטטוס", "בדיקות מערכת") מנותבים כעת ל-`Handler.CLARIFY` במקום נפילה שקטה ל-Agent עם כלים מלאים. ראה BUG-048 ב-BUG_AUDIT_LOG.md.

**בדיקות:** smoke_tests, test_a32_enforcement (6/6), test_integration (4/4), session_store.py (52/52), core/router/test_router.py (29/29), test_approval_gateway_safety.py (25/25) — כולן ירוקות לפני מיזוג.

**Rollback plan:** revert merge commit `bb81e6c` — שלושת הפיצ'רים עצמאיים זה מזה בקוד (אין תלות הדדית), אך מוזגו יחד ב-PR אחד; revert חוזר את כולם יחד.

**סטטוס:** ✅ מוזג ל-main

### C83 — BUG-IC-01B: prefixed ambiguous phrase routing (04/07/2026)
קבצים: `core/router/intent_router.py`, `core/router/test_router.py` | PR #220 | באג: BUG-061
`_AMBIGUOUS_PHRASES` מזהה כעת גם ביטויים דו-משמעיים עם prefix טבעי ("אני צריך למלא משימות", "צריך סטטוס" וכו') ולא רק גרסאות ~~~~~~ (BUG-048/BUG-IC-01) — מנתב ל-`Handler.CLARIFY` במקום Agent עם כלים מלאים. 44/44 בדיקות.
**Merged:** כן (`b76e6d5`) | **Verified בפרודקשן:** לא עדיין

### C84 — BUG-SESSIONS-ROOT: fail-closed על Session lookup מובנה (04/07/2026)
קבצים: `session_store.py`, `tools/airtable_tools.py` (חדש: `airtable_get_records`), `test_session_store_contract.py` (חדש) | PR #221 | באג: BUG-063
Session lookup עבר מ-regex-parsing על string מפורמט ל-reader מובנה (list[dict], paginated, fail-closed על שגיאות/contract mismatch). POST (יצירת Session חדש) מותר רק אחרי lookup שמאשש בבירור 0 רשומות — כל מצב אחר חוסם POST במקום ליצור כפילות שקטה (המשך ל-BUG-047/BUG-NEW-12). 49 internal + 4 pytest. נבדק ונפתח PR ע"י session נפרד מזה שכתב את הקוד המקורי.
**Merged:** כן (`eead2cc`) | **Verified בפרודקשן:** לא עדיין

### C85 — BUG-C89-APPROVAL-IDENTITY: actor identity נשמרת דרך אישור (04/07/2026)
קבצים: `core/action_gateway.py`, `core/lead_candidate_handler.py`, `app.py`, `test_action_gateway.py`, `test_c89_preview_confirmation.py` | PR #222 | באג: BUG-062
`ActionContract` שומר actor identity (role/external_id/tenant/user/domain) שנפתרה בזמן ה-`propose_action()`; ה-executor ב-`approve()` משתמש בה ישירות במקום `resolve_identity()` מחדש על `origin_chat_id` שיכול להיות `identity.memory_key` ולא channel external_id אמיתי — תיקן owner שאיבד role וחזר ל-`readonly` בביצוע אחרי אישור. גם: preview של עדכון-ליד-קיים אומר "מצאתי ליד קיים. לעדכן אותו?" ולא "לשמור?" הגנרי, ותמיד דורש אישור גם עם `FEATURE_AUTO_CAPTURE=true`. 37+9+44 בדיקות ירוקות.
**הערה:** ה-commit נדחף במקור לענף של PR #220 *אחרי* שזה כבר מוזג — לא נכלל בו. הענף אותחל מחדש מ-`main` (`git rebase` + `--force-with-lease`) לפני פתיחת PR #222 נפרד.
**Merged:** כן (`717465a`) | **Verified בפרודקשן:** לא עדיין

### C86 — BUG-C89-TIER4-PRECEDENCE: hard markers מורחבים לגילוי טבלה/ייצוא (04/07/2026)
קבצים: `core/ingress_classifier.py`, `test_c89_tier4_precedence.py` (חדש) | PR #223 | באג: BUG-064
`_is_tier4()` (השער היחיד, נצרך ע"י `router.py` וע"י `lead_candidate_handler.py`) הורחב: כותרות טבלה ללא separator מפורש (עברית+אנגלית), טבלאות fixed-width, סמנים מילוליים (`Status:`/`Score:`/`View in Airtable`/`memory_key`/`@lead`/`owner_dictation`), timestamp עם נקודות, ופלט-בוט מורחב (📋/🌤️/█, סף 3→2). מילת "airtable" בודדת מוגבלת למבנה נוסף כדי לא לשבור פקודת בדיקת-מערכת מפורשת ("תבדוק עכשיו את Airtable") — regression שנתפס ותוקן לפני פתיחת ה-PR. 13/13 בדיקות חדשות + אפס רגרסיה (`test_capture_router_wiring.py` 10/10, `core/router/test_router.py` 44/44).
**Merged:** כן (`b7d8445`) | **Verified בפרודקשן:** לא עדיין

### C87 — C89-RAW-OBS: raw capture + classification observation (04/07/2026)
קבצים: `core/ingress_classifier.py`, `feature_flags.py` (חדש flag: `FEATURE_RAW_CAPTURE`), `test_c89_raw_obs.py` (חדש) | PR #224 | באג: BUG-065
`classify_ingress()` הוסבה לעטיפה סביב הלוגיקה המקורית (`_classify_ingress_core`, ללא שינוי): לכל קריאה (Tier 1-5) נשמר `raw_ref` לא-ריק (Decision Inbox record id כש-`FEATURE_RAW_CAPTURE` פעיל, אחרת fallback מקומי) ונרשם `AgentObservation(kind="capture_classification")` דרך ה-API הקיים בלבד של `ActionGateway.record_agent_observation(contract_id=None, ...)` — ללא שינוי בליבת ה-Gateway. 14/14 בדיקות חדשות + אפס רגרסיה.
**Merged:** כן (`68f8c97`) | **Verified בפרודקשן:** לא עדיין
**עדכון (PR #227, `ca207ba`):** `raw_ref` קיבל ברירת מחדל sentinel (`__unset__`) במקום `""`, כך שאף return statement פנימי לא כותב `raw_ref=""` יותר — `grep -rn 'raw_ref=""'` מחזיר אפס hits בקוד. אין שינוי התנהגות, רק hardening נגד false-negative של audit מבוסס-grep. 15/15 (מ-14/14). **Merged:** כן (`64b477a`).

### C88 — C90: Structured File Capture — file upload כ-ingress source adapter (05/07/2026)
קבצים: `core/file_ingress_adapter.py` (חדש), `core/ingress_classifier.py`, `app.py`, `feature_flags.py` (חדש flag: `FEATURE_STRUCTURED_FILE_CAPTURE`), `test_c90_structured_file_capture.py` (חדש, 37/37) | PR #228
עיקרון: קובץ שמועלה הוא **ingress source adapter בלבד** — לא capture pipeline חדש, לא classifier חדש, לא write path חדש. `core/file_ingress_adapter.py` מפרסר xlsx/csv (openpyxl/`csv`) לשורות; שורה ריקה לגמרי מדולגת (אין מידע), שורה פגומה (ragged וכו') לא נעלמת בשקט — מוחזרת כטקסט raw מסומן. `core/ingress_classifier.py`'s `_classify_ingress_core()` מטפל ב-`source_type="file"` **באותה בדיוק לוגיקה** כמו `"text"` — בלי special-casing, כך ששורה עם שם+טלפון ברור יכולה להיות Tier1 לגיטימי (לא נכפה Tier4 גורף). `app.py`'s `_process_structured_file_upload()` מריץ כל שורה, אחת בכל פעם, דרך `handle_lead_candidate()` הקיים — כל שורה יוצרת AgentObservation+raw_ref נפרדים, ו-Tier1-3 יוצרים ActionGateway contract נפרד הדורש אישור פרטני (אין "אישור קבוצתי"). מגבלת בטיחות `_MAX_FILE_ROWS_PROCESSED=200` מדווחת במפורש (לא dropping שקט). גייט: `identity.is_internal` + `FEATURE_STRUCTURED_FILE_CAPTURE` (כבוי כברירת מחדל) + סיומת/mime xlsx/csv בלבד — קובץ שאינו xlsx/csv או שולח חיצוני נופלים לזרימה הקיימת (FEATURE_MEDIA_UPLOAD) ללא שינוי.
**באג שנתפס לפני מיזוג:** גרסה ראשונה של `_row_to_text()` השתמשה במפריד `" | "` — התנגש עם `_TABLE_RE` הקיים (Tier4 hard marker ל-2+ שדות pipe-separated), וכפה Tier4 שגוי על כל שורה עם 3+ עמודות מאוכלסות (מקרה טיפוסי לגמרי, למשל Name/Phone/City). תוקן ל-`", "` (לא מתנגש עם אף hard marker קיים) לפני שנפתח PR. נלכד ע"י regression test ייעודי, לא ע"י ביקורת חיצונית.
**Merged:** כן (`f585d9d`, merge commit `004fbf9`) — מאומת `git log origin/main --oneline` | **Verified בפרודקשן:** לא רלוונטי עדיין (flag כבוי כברירת מחדל)

### C91 — BUG-067: Shabbat gate ל-daily_digest/daily_collector (05/07/2026)
קבצים: `scheduler.py`, `test_bug067_shabbat_gates_scheduled_digest.py` (חדש) | PR #230 | באג: BUG-067
`daily_digest.py` הציג רק banner טקסטואלי ("שבת — הודעות מושהות") מבלי לחסום בפועל את השליחה. `_job_daily_digest`/`_job_daily_collector` נעטפו ב-`shabbat_safe(...)` — אותו pattern בדיוק כמו 6 jobs אחרים ב-`scheduler.py`. 2 שורות שונו, ללא נגיעה בתוכן/formatting/Airtable queries. 3/3 בדיקות חדשות.
**Merged:** כן (`b31b880`, merge commit `cfa3205`) | **Verified בפרודקשן:** לא עדיין

### C92 — BUG-066: fail-safe פר-שלב ל-Daily Tasks (05/07/2026)
קבצים: `daily_collector.py`, `scheduler.py`, `test_bug066_daily_collector_fail_safe.py` (חדש) | PR #231 | באג: BUG-066
`collect_daily()`/`send_daily_collector()` פוצלו לשלבים מבודדים (fetch history / LLM+parse / format / send) עם try/except+logging (start/done/error) נפרד לכל שלב — הפונקציות לעולם לא raise-ות, תמיד fallback בטוח. `bot.send_message()` מקבל `timeout=15` מפורש כדי שקריאת רשת תקועה לא תקפיא את ה-scheduler thread הבודד. `scheduler.py`'s job wrappers קיבלו logging מפורש ברמת ה-job. תוקנה גם corruption/mojibake בשתי שורות טקסט בקובץ (לא קשור לבאג עצמו). 8/8 בדיקות חדשות + אפס רגרסיה.
**Merged:** כן (`aa30695`, merge commit `f2431e1`) — מאומת `git log origin/main --oneline` | **Verified בפרודקשן:** לא עדיין

### C93 — BUG-070 (gap 2/3): multi-pending support ב-`_pending_approvals` (05/07/2026)
קבצים: `app.py`, `test_bug070_pending_approval_multi.py` (חדש) | באג: BUG-070
`_pending_approvals` שונה מ-רשומה יחידה per chat_id ל-`dict[chat_id][approval_id] → entry` עם `display_index`; פונקציות חדשות `_add_pending_approval`/`_resolve_pending_reply`/`_pop_pending_approval`/`_pending_clarification_message`. תומך כעת ב-"כן 2"/"לא 2"/מספר בודד לבחירת פריט ספציפי מתוך כמה ממתינים, ובתאימות לאחור מלאה ל-"כן"/"לא" בלי מספר כשיש ממתין יחיד. **תיקון בטיחות שנוסף בביקורת קוד לפני commit** (מעבר לפאץ' שהתקבל): מספר בודד ("1") מטופל כאישור מרומז **רק כש-2+ פריטים ממתינים** — בפאץ' המקורי מספר בודד כזה היה מאשר גם ממתין יחיד, מה שהיה מבצע פעולה אמיתית (למשל שליחת מייל) בתגובה למספר לא-קשור בשיחה (כמות, מחיר וכו'); אומת ותוקן לפני מיזוג. 9/9 בדיקות חדשות (כולל regression guard ייעודי לתיקון הבטיחות) + אפס רגרסיה על `test_ll13_double_execution.py`/`test_approval_concurrency.py`/`test_a32_enforcement.py`/`test_c53a.py`/`smoke_tests.py`. **gaps 1 ו-3 מ-BUG-070 (ActionGateway reject-by-index + combined wording, ו-daily_collector) נשארים פתוחים — לא נכללו בסקופ זה.**
**Merged:** לא עדיין

### C97 — BUG-078: `/update` תופס קובץ מצורף (photo/document) במקום לאבד אותו (07/07/2026)
קבצים: `app.py`, `cmd_update.py` | PR #255 | באג: BUG-078
`app.py`'s webhook ניתב הודעות photo/document ישירות ל-`_handle_telegram_media()` (זרימת Drive הכללית) לפני שקרא בכלל ל-`bot.process_new_updates()` — `/update`'s pending state (`_pending[uid]`) לא נבדק, וקובץ שנשלח באמצע האשף אבד לגמרי מהקשר העדכון העסקי. נוספו `cmd_update.has_pending_file_capture()`/`capture_photo_or_document()`, נבדקים ב-`app.py` לפני `_handle_telegram_media` — קובץ נתפס, מועלה ל-Drive (best-effort), ונשמר ל-Business Memory עם ה-domain/entry_type שכבר נבחרו באשף. smoke/integration (4/4)/router (44/44) ירוקים + טסט ידני ממוקד.
**Merged:** כן (`32bbb75`, merge commit `194b3da`, PR #255) | **Verified בפרודקשן:** ✅ כן — 08/07/2026, זרימת `/update` הכללית נבדקה קצה-לקצה (ראה C101)

### C98 — BUG-079: `/update` שלב הטקסט החופשי מגיע ל-`capture_text` במקום לברוח ל-`run_agent` (07/07/2026)
קבצים: `app.py`, `cmd_update.py` | PR #256 | באג: BUG-079
`app.py` קורא ל-`bot.process_new_updates()` (מפעיל `capture_text` ודומיו) רק כש-`text.startswith("/")` — טקסט חופשי במהלך `/update` המשיך ישר ל-`idempotency.is_duplicate()` ואז ל-`run_agent()` הכללי, מבלי ש-`capture_text` ירוץ אף פעם. פוגע בתרחיש הראשי (לא רק edge-case) של `/update` מאז שנוסף. נוסף `cmd_update.has_pending_text_capture()`, נבדק ב-`app.py` מיד אחרי בלוק ה-slash-command ולפני idempotency (fail-open) — אם `/update` ממתין בשלב `text`, ה-webhook קורא ל-`bot.process_new_updates()` בעצמו. smoke/integration (4/4)/router (44/44) ירוקים + טסט ידני מבודד על מעברי שלב.
**Merged:** כן (`912b94e`, merge commit `baa0283`, PR #256) | **Verified בפרודקשן:** ✅ כן — 08/07/2026, `/update` → נדל"ן → Other → טקסט → `capture_text` תפס ונשמר בהצלחה (ראה C101)

### C99 — חילוץ טקסט ממסמך (docx/csv/xlsx/txt/html) שנשלח באמצע `/update` (07/07/2026)
קבצים: `media_handler.py` (חדש: `extract_text_if_document`), `cmd_update.py` | PR #257
מסמכים שנתפסו ע"י `capture_photo_or_document` (C97) נשמרו רק עם caption+drive_url — התוכן עצמו מעולם לא נקרא, אז docx/csv/xlsx שצורף לעדכון עסקי לא נשא שום מהתוכן שלו ל-Business Memory. `media_handler.extract_text_if_document(file_bytes, mime_type)` עוטף את `document_converter.convert_document()` הקיים (temp-file+ניקוי+טיפול כשלים בפנים — פורמט לא נתמך/כשל המרה מחזירים `None`, לא raise). `capture_photo_or_document` קורא לזה עבור document בלבד, משלב את הטקסט שחולץ ל-`raw_text` לצד caption+drive_url הקיימים. אין שינוי ל-API הציבורי של `document_converter`. smoke/integration (4/4)/router (44/44)/`test_document_converter.py` (6/6) ירוקים + טסטים ידניים (mime לא-נתמך→`None`, txt תקין→טקסט, docx פגום→`None` בלי exception, אין קבצים זמניים שנשארים).
**Merged:** כן (`3d69609`, merge commit `caef337`, PR #257) | **Verified בפרודקשן:** לא עדיין

### C100 — BUG-080: שדות Date-בלבד ב-Airtable מקבלים ערך date בלבד, לא datetime מלא (07/07/2026)
קבצים: `cmd_update.py`, `media_handler.py`, `cmd_decision.py` (7 נקודות כתיבה בסה"כ) | PR #258 | באג: BUG-080
`BusinessMemoryFields.DATE`/`DecisionEventFields.EVENT_DATE`/`DecisionInboxFields.RECEIVED` הם שדות `Date` בלבד ב-Airtable (`datetime_fields: []`, אומת מול live field-type metadata), אבל כל 7 נקודות הכתיבה שלחו `datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()` — מחרוזת עם שעה/מיקרושניות/offset, נדחית ב-422 (אין `typecast=true` בגייטוויי). שונה ל-`.date().isoformat()` בכל 7 המקומות; שלושה מקומות דומים נבדקו ונשארו ללא שינוי במפורש (2×`FileUploadResult(timestamp=...)` — אובייקט session_store בזיכרון לא Airtable, ו-1× שימוש read-only כמפתח מיון). smoke/integration (4/4)/router (44/44)/`test_decision_attention.py` (11/11)/`test_core_reasoning.py` (59/59) ירוקים.
**Merged:** כן (`02bc343`, merge commit `a8ffa07`, PR #258) | **Verified בפרודקשן:** ✅ חלקית — 08/07/2026, `cmd_update.py`'s `BMF.DATE` נבדק (ראה C101); שאר 6 נקודות הכתיבה עדיין לא

### C101 — BUG-081: Business Memory `Domain` נכתב לשדה הייעודי, לא "ממוחזר" לתוך `Tags` (07-08/07/2026, 5 PRs)
קבצים: `airtable_schema.py` (חדש: `BusinessMemoryFields.DOMAIN`), `cmd_update.py` (חדש: `normalize_business_memory_fields`), `media_handler.py` | PR #259, #260, #261, #263, #265 | באג: BUG-081
`BusinessMemoryFields` לא היה לה שדה `Domain` ייעודי (בניגוד לכל טבלה אחרת בסכימה) — `cmd_update.py`/`media_handler.py` כתבו את מפתח ה-domain הגולמי (למשל `"media"`) ישירות ל-`Tags` הכללי, בלי אימות מול live options; אין `typecast=true` → 422 על ערך לא-קיים. **PR #259:** נוסף `BusinessMemoryFields.DOMAIN`; `normalize_business_memory_fields()` ממפה domain→ערך Domain מאומת (`_DOMAIN_TO_AIRTABLE`) ומסננת `Tags` לערכים חוקיים בלבד (`_VALID_TAGS`). **PR #260:** תוקן `_DOMAIN_TO_AIRTABLE["real_estate"]` מ-lowercase (שגוי, נמחק בניקוי ב-Airtable) ל-`"Real Estate"` (Title Case, היחיד שנשאר). **PR #261 (2 commits):** 422 חי נוסף בפרודקשן — `_VALID_TAGS` עדיין הכיל `"real_estate"` lowercase כ-tag עצמאי; תוקן ל-`"Real Estate"` + נוסף `_TAG_NORMALIZE` כדי ש-`domain="real_estate"` יפיק `Domain="Real Estate"` **וגם** `Tags=["Real Estate"]`. **PR #263 — root cause אמיתי:** מאומת מול production logs ש-domain תמיד הוזרק ל-`Tags` (`BMF.TAGS: [domain]`) בשני מקומות הכתיבה — זה עצמו הפגם, לא רק ניסוח הערך. הוסר `BMF.TAGS: [domain]` לגמרי; הוסר `_TAG_NORMALIZE` (לא נדרש יותר); `_DOMAIN_TO_AIRTABLE["media"]` תוקן ל-`"Media"`; `get_recent_business_context()` עברה לסנן לפי `{Domain}` (עם `Tags` כ-legacy fallback בלבד). **PR #265:** אומת מול Airtable Meta API ש-`"Real Estate "`/`"SaaS "` (עם רווח בסוף) הם האופציות החיות, לא המחרוזות הנקיות — תוקן, אומת ב-`repr()` שהרווח נשמר בקוד.
**פער ידוע, לא בסקופ:** `weekly_summary.py::_group_by_domain()` ו-`tma_api.py`'s Business Memory listing קוראים `Tags[0]` כ-domain — ישברו בשקט (default general/ריק) עם רשומות חדשות. Backlog, piggyback על הפעלת `FEATURE_WEEKLY_SUMMARY`/שימוש פעיל ב-TMA business memory screen (אף אחד לא פעיל כרגע).
**Merged:** כן (`bd0f32c`/`50847b7`, `42ed90c`/`0094a82`, `f367469`+`7526e60`/`fa08a58`, `8c720f4`+`69354c3`/`eaa01fa`, `8e6072e`/`def0a00`) | **Verified בפרודקשן:** ✅ כן — 08/07/2026, `/update` נבדק ב-**כל 6** ה-domains (real_estate/SaaS/media/import/general/finance) → Other → טקסט → נשמר תקין בכולם, "📌 Other | <domain>" מוצג נכון, אין 422 באף אחד. **המשך: ראה C102 (שלב 6, 09/07/2026) — הבירור החי מחליף את המילון הסטטי שהעבודה הזו תיקנה 5 פעמים.**

### C102 — BUG-081 שלב 6: Domain live-lookup מחליף את `_DOMAIN_TO_AIRTABLE` הסטטי (09/07/2026)
קבצים: `cmd_update.py` (`resolve_business_memory_domain`, `_normalize_domain_option` חדשות), `test_business_memory_domain_lookup.py` (חדש) | PR #276 (2 commits) | באג: BUG-081 (שלב 6)
תקרית חיה נוספת (רווח בסוף) הובילה לחקירה שגילתה סתירה בין PR #265 (טען שהחי כולל רווח) לבין בדיקה חיה חדשה — התבררה כתוצאה של שינוי ידני של המשתמש בבייס לצורך בדיקת PR2, לא סתירה אמיתית. אבל זה חשף את הבעיה המבנית: `_DOMAIN_TO_AIRTABLE` מילון סטטי שדרש 5 תיקונים ידניים קודמים בכל פעם שהסכימה החיה השתנתה. `resolve_business_memory_domain()` מבררת מול `RuntimeSchemaProvider.get_table_contract("Business Memory")` בכל קריאה, case/whitespace-tolerant, duplicate-option guard מובנה (`{"ok": false, "error": "duplicate option name found: ... (N matching options)"}`), no-match → שגיאה מובנית לא ערך שרירותי. `_DOMAIN_TO_AIRTABLE` נשאר fallback אחרון בלבד. `_save_to_business_memory` שונה מ-`None` גולמי ל-`{ok, record|error}` (אותה משמעת חוזה כמו `PR_RESPONSE_CONTRACT`). 24/24 בדיקות חדשות (`test_business_memory_domain_lookup.py`), כולל DoD: rename אופציה חיה → הכתיבה הבאה מסתגלת אוטומטית בלי תיקון קוד.
**Merged:** כן (`b578e2c`+`17b73b7`, merge commit `61b1c34`, PR #276) | **Verified בפרודקשן:** לא עדיין — מנגנון שונה מהותית מהמילון שאומת ב-C101, דורש אימות production משלו.

### C103 — BUG-086: Anti-hallucination — תביעות CREATE בגוף ראשון חמקו מה-Gate + safety net גנרי (09/07/2026, 2 PRs)
קבצים: `core/anti_hallucination.py` בלבד | PR #277, #278 | באג: BUG-086
תקרית חיה: "✅ הוספתי... 30 רשומות פעילות" עם 3 קריאות `airtable_get` (read-only) ואפס `airtable_add` בלוג — מספר עולה (28→29→30) בלי גזירה מ-tool result, מוכיח ניחוש. **שלב 1 (PR #277):** `_NO_TOOL_CLAIMS`'s CRM creation pattern תפס רק גוף שלישי/סביל — נוסף `הוספתי|שמרתי|רשמתי|תיעדתי` (גוף ראשון), symmetric ל-UPDATE claims שכבר תוקנו ב-BUG-NEW-09. **שלב 2 (PR #278):** הצעת עיצוב ראשונית ("zero tool_use בכלל") נבדקה מול המבנה האמיתי ונמצאה לא-תקפה מראש (3 GET-ים היו "מכבים" אותה) — תוקן ל-`_has_write_tool_evidence()` הדורש tool מ-`_WRITE_ACTION_TOOLS` ספציפית, לא "כל tool". רץ תמיד ב-`sanitize_agent_response`, לא רק תחת `FEATURE_ACTION_GATEWAY`. 66/66 self-tests אחרי שני השלבים (כולל שחזור מדויק של התקרית, regression שה-flow הרגיל לא נשבר).
**Merged:** כן (`369168f`, merge commit `c961f25`, PR #277; `a64d9f3`, merge commit `ab1aefd`, PR #278) | **Verified בפרודקשן:** לא עדיין

### C104 — BUG-087: Fallback messages כוזבות ב-Restricted/Single-Speaker flows (09/07/2026, 2 PRs)
קבצים: `core/anti_hallucination.py`, `app.py`, `test_restricted_tool_fake_forward_message.py` (חדש), `ROADMAP.md` (N15) | PR #280, #281 | באג: BUG-087
אותה מחלת claim-without-evidence שתוקנה ב-BUG-086, הפעם ב-fallback copy עצמו. **שלב 1 (PR #280):** `_SINGLE_SPEAKER_FALLBACK` ("הפעולה התקבלה. תוצאה תישלח בנפרד.") — אין queue/pending אמיתי מאחוריו. שונה ל-"לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת." **שלב 2 (PR #281):** `app.py:1867`'s `"הבקשה התקבלה ותועבר לטיפול."` (tool_result כוזב ב-Restricted flow) — אומת ב-grep ש-`route.notify_owner` (נקבע `True` ל-`Handler.RESTRICTED`) אף פעם לא נצרך בשום קוד. שונה ל-"הבקשה נרשמה במערכת." נפתח `ROADMAP.md` N15 (backlog נפרד: להחליט אם לבנות התראה אמיתית או להסיר את השדה המת). הותקן `requirements.txt` המלא בסביבת הבדיקה (חסר עד כה) לצורך אימות אמיתי — כל 62 `test_*.py` + `smoke_tests.py` (כולל Import) + `test_a32_enforcement.py`/`test_stage_b_full_suite.py` אומתו ירוקים בפועל.
**Merged:** כן (`cd20653`, merge commit `b9a1ee7`, PR #280; `9065339`, merge commit `75cdb45`, PR #281) | **Verified בפרודקשן:** לא עדיין

### C105 — BUG-085: `run_snapshot_archive()` אף פעם לא כותב `Status=Drift Detected` (09/07/2026)
קבצים: `tools/schema_snapshot.py` (`_missing_tables` חדשה), `test_schema_snapshot.py` | PR #279 | באג: BUG-085
`SchemaSnapshotStatus.DRIFT_DETECTED` קיים כ-enum מאז PR3A אך מעולם לא נכתב בקוד — `run_snapshot_archive()` קבעה רק `OK`/`Error` לפי הצלחת פעולת ה-snapshot עצמה, בלי השוואה בין `airtable_schema.Tables` לטבלאות החיות. נוספה `_missing_tables(raw_meta)` — `set(vars(Tables)) - set(live_names)`, אותה שיטת חילוץ כמו `tools/check_airtable_schema_runtime.py`'s `missing_in_airtable` (שימוש חוזר, לא כפילות). טבלה חסרה → `Drift Detected` בכתיבה הראשונית ובפאץ' הסופי גם יחד; `Error` (כשל תפעולי) עדיין גובר. `apply_retention_policy()` לא שונה. 34/34 בדיקות (9 חדשות: `_missing_tables` ישיר + `run_snapshot_archive()` מקצה-לקצה עם כל הרשתות מדומות, גם למקרה "הכל תקין" (עדיין `OK`, regression) וגם עם טבלה חסרה). **תוייג בטעות בשיחה כ-"BUG-082" (מספר זמני, לא ID אמיתי) — BUG-082 הרשמי בלוג הוא נושא נפרד שכבר סגור (anaphora resolution, Won't Fix).**
**Merged:** כן (`60901c8`, merge commit `5dde1eb`, PR #279) | **Verified בפרודקשן:** לא — `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` כבוי כברירת מחדל

### C106 — BUG-091: `_source` בתוך tool_inputs עוקף את `enforce_leads_write_gate()` (09/07/2026)
קבצים: `tools/dispatcher.py`, `app.py`, `core/action_gateway.py`, `core/lead_candidate_handler.py`, `test_bug091_source_trust_boundary.py` (חדש), `test_bug091_preflight_no_pending_approval.py` (חדש) | PR #285 | באג: BUG-091
Privilege escalation, לא UX: `source` ל-`enforce_leads_write_gate()` נגזר מ-`inputs.get("_source", "agent")` — `inputs` הוא `tool_use.input` שקלוד שולט בו במלואו ונשמר verbatim בזמן אישור (גם ב-EventBus הפעיל וגם ב-`ActionGateway` ה-flag-gated). `"_source":"lead_capture"` מזויף בתוך קריאת כלי היה עוקף את השער. תוקן במבנה: `_source` הוסר לגמרי מ-`tool_inputs`, הוחלף בפרמטר Python מפורש `trusted_source` (`dispatch_tool(..., trusted_source=None)`, ברירת מחדל fail-closed ל-`"agent"`) שרק קוד מהימן (`lead_candidate_handler.py`) יכול להעביר. נוסף preflight חדש ב-`app.py` שחוסם *לפני* `_queue_approval` (לא רק בזמן ביצוע), כדי שכתיבה חסומה לעולם לא תיהפך ל-pending approval. תוקן גם ב-`core/action_gateway.py` (`ActionContract.trusted_source`) למרות ש-`FEATURE_ACTION_GATEWAY` כבוי כברירת מחדל — latent vulnerability מאחורי flag כבוי עדיין vulnerability. 10/10 + 3/3 בדיקות חדשות, כולל attack simulation מלאה.
**Merged:** כן (`5f2c90f`, merge commit `df49b5e`, PR #285) | **Verified בפרודקשן:** ✅ כן, חלקית — 09/07/2026, לוגים אמיתיים (20:08:46) מראים את ה-preflight חוסם לפני pending approval. תזמון ההפעלה (מוקדם משמעותית) טופל ב-C108/BUG-092.

### C107 — BUG-090: LeadsWriteGate — הודעת חסימה נכונה לפי create/update, Single-Speaker (09/07/2026)
קבצים: `tools/airtable_security.py` (`_leads_write_blocked_message` חדשה), `test_bug090_leads_gate_message.py` (חדש) | PR #286 | באג: BUG-090
`enforce_leads_write_gate()` החזירה תמיד אותה הודעה קבועה ("...capture_inbound_lead() בלבד") גם ל-`airtable_update` (עדכון ליד קיים) — לא רלוונטי, ודולפת שם פונקציה פנימי. תוקנה הודעה נפרדת לפי `tool_name`: update מפנה למסך הלידים באפליקציה, create מסביר שלידים נוצרים אוטומטית — בלי שם פונקציה, בלי suffix דיבאג. חצי שני של דרישת Single-Speaker המקורית (החצי המבני נסגר יחד עם C106/BUG-091 באותו PR chain — לא side effect, שני חצאים מתוכננים מההתחלה). 18/18 בדיקות חדשות; אפס שינוי בהתנהגות החסימה עצמה.
**Merged:** כן (`85c08f9`+`314f0dd`, merge commit `5338fa9`, PR #286) | **Verified בפרודקשן:** ✅ כן (09/07/2026) — הודעת update אמיתית ממשתמש חי ("עדכן ליד קיים אברהם ברסלר לא רלוונטי") קיבלה טקסט זהה byte-for-byte להודעה המתוקנת, ראה BUG_AUDIT_LOG.md לפירוט

### C108 — BUG-092: Deterministic Denial Short-Circuit — חוסך סבב Claude מיותר לחסימות ודאיות (09/07/2026)
קבצים: `core/router/deterministic_denial.py` (חדש), `app.py`, `test_deterministic_denial.py` (חדש) | PR #287 | באג: BUG-092
לוגים אמיתיים מפרודקשן הראו את ה-preflight של BUG-091 חוסם נכון אך מאוחר מדי — אחרי Router+Context+שני סבבי Claude+`airtable_get`. המשתמש דחה תיקון ממוקד-Leads בלבד ("אותו באג לכל הטבלאות ולכל הכלים"), ודרש מנגנון גנרי. `check_deterministic_denial(intent, identity)` חדש מריץ, מיד אחרי בדיקת `EMERGENCY_STOP_AI` ולפני תחילת ה-Agent Loop, חיזוי read-only של שתי קטגוריות חסימה ודאיות: (א) שערי מקור בלתי מותנים (קורא ל-`enforce_leads_write_gate()` האמיתית), (ב) שערי role שה-registry מחריג לגמרי (קורא ל-`tool_registry.check_allowed()` האמיתי) — אף לוגיקה לא שוכפלה. `INTENT_TOOL_HINTS` שמרנית: רק `UPDATE_LEAD`/`CREATE_LEAD` ביום הראשון. Fail-safe מפורש: hint שגוי/חסר מדלג רק על אופטימיזציה, לעולם לא מעניק גישה. נכתב ע"פ בקשת המשתמש: הבדיקה (`test_deterministic_denial.py`) נכתבה והורצה **לפני** קוד המימוש (נכשלה כצפוי, `ModuleNotFoundError`), רק אז נכתב המימוש. 18/18 בדיקות חדשות (כולל byte-equal על הודעות ה-gate האמיתיות, zero-Claude-round-trip proof, ו-guard רגרסיה שהשערים המקוריים עדיין זורקים בעצמם). `test_bug090_leads_gate_message.py`/`test_bug091_*` (2 קבצים)/`smoke_tests.py`/`test_integration.py` הורצו מחדש ללא שינוי — כולם ירוקים.
**Merged:** כן (`b519d50`, merge commit `55d7f08`, PR #287) | **Verified בפרודקשן:** ✅ כן (10/07/2026) — לוג `[DeterministicDenial] leads_write_gate short-circuited before Agent | intent=update_lead tool=airtable_update role=owner` תואם byte-for-byte ל-`app.py:1761`, ללא לוג preflight מאוחר מקביל — מוכיח את ה-timing המוקדם בפועל, ראה BUG_AUDIT_LOG.md

### C109 — BUG-093 (LL-13): תיעוד רטרואקטיבי — אישור כפול (double-execution) כבר תוקן ב-main, לא היה מתועד בלוג
קבצים: `app.py` (`_pending_approvals_lock`), `event_bus.py` (`PendingActionsStore.pop`), `test_ll13_double_execution.py` (כבר קיים) | מקור מדויק (PR/commit) לא אומת בוודאות | באג: BUG-093
המשתמש שלח טיוטת log מקומית (Windows, `My-bot-main.worktrees/BUG_AUDIT_LOG.md`) עם git conflict markers לא-פתורים בין שתי גרסאות. הצד "Stashed" תיעד תיקון LL-13 (double-tap/redelivery מבצע פעולה בלתי-הפיכה פעמיים) שציטט `commit 7ccb4a6`/PR #183 — נבדק ישירות ונמצא לא-קיים בהיסטוריית git של הריפו (`git show 7ccb4a6` → `unknown revision`). המנגנון עצמו כן קיים ופעיל ב-`origin/main` (`_pending_approvals_lock` ב-`app.py`, `pop()` תחת `self._lock` ב-`event_bus.py`, `test_ll13_double_execution.py` קיים ורץ 4/4 ירוק בפועל בסבב זה) — התיקון האמיתי מתגלה לראשונה דרך merge ענק של PR #193 (`97ebe3e`), לא PR #183 הנטען. נוסף לכך, הטיוטה מספרה את זה "BUG-066" שמתנגש עם BUG-066 האמיתי הכבר-קיים בלוג (BUG-DAILY-01). נרשם כ-BUG-093 (המספר הפנוי הבא) עם ציטוט עובדות מאומתות בלבד — לא הועתק commit hash/PR number לא-מאומת מהטיוטה. איחוד ה-store המלא לפי `SPEC_LL13_Pending_Approval_Unification.md` (טבלת Airtable יחידה) נשאר לא-ממומש, roadmap item נפרד.
**Merged:** כן (קיים ב-`origin/main`, מקור מדויק לא אומת) | **Verified בפרודקשן:** לא עדיין

### C110 — Phase 4B0.1C: Atomic Claims wiring bypass + structured Dispatcher Outcome contract (13/07/2026, 2 PRs)
קבצים: `core/action_gateway.py`, `core/action_gateway_atomic_executor.py`, `core/dispatcher_outcome.py` (חדש), `test_phase_4b0_wiring_regression.py` (חדש), `test_phase_4b0_integration_result_classification.py` (חדש) | PR #325 (ממשיך PR #324) | Staging: `FEATURE_ATOMIC_CLAIMS`
בדיקת production smoke גילתה שכל ארבעת מסלולי האישור (`route_confirmation_word`/`route_disambiguation`/`route_combined_word`/`route_override_word`) התכנסו ל-`_execute_contract()` שקרא ל-`self._tool_executor` ישירות, עוקף לגמרי את רכישת ה-atomic claim — כשה-flag דלוק, אושרו ובוצעו contracts בלי שום שורה נוצרה ב-`action_execution_claims`. תוקן בנקודת ההתכנסות המשותפת, לא בכל route בנפרד. אימות staging בפועל אחרי התיקון הראשוני חשף שני פגמים קריטיים נוספים: (א) **אובדן זהות** — `identity=None` הועבר ל-`execute_with_atomic_claim`, ה-dispatcher קיבל tenant/user לא ידועים; (ב) **סיווג שגוי** — מחרוזת חסימה של ה-dispatcher (`❌ גישה נחסמה`) נבדקה רק לפי exception, לא לפי תוכן, ונרשמה כ-claim מושלם (completed) על אף שנחסמה. תוקן: `_execute_contract` משחזר `Identity` **אך ורק** מהשדות הקפואים והבלתי-ניתנים-לשינוי ב-`ActionContract` (`tenant_id`/`actor_user_id`/`actor_role`/`actor_external_id`) — שדה חסר = fail-closed מיידי, `contract.status="failed"`, בלי fallback חלקי. הוחלף parsing מבוסס-אימוג'י/מחרוזת ב-`DispatcherOutcome` חדש — dataclass קפוא עם `result` מפורש ∈ `{completed, failed, outcome_unknown}`; ה-executor האטומי מסווג לפי `outcome.result`, לעולם לא לפי טקסט `user_message` (תצוגה בלבד). `outcome_unknown` (timeout/כשל תקשורת אחרי שהבקשה אולי כבר נשלחה) נרשם ככזה ולעולם לא retried אוטומטית. 26 בדיקות (11 wiring regression + 15 integration result-classification) ירוקות, כולל: זהות משתמרת דרך ה-wrapper האטומי; חסימת הרשאה → dispatcher נקרא פעם אחת, provider אפס פעמים, claim נכשל; הצלחה מפורשת עם עדות → claim הושלם; תוצאה מעורפלת → claim `outcome_unknown`.
**Merged:** כן (`9584b73`→`4fa5595`, merge commit `2a563e9`, PR #325) | **Verified בפרודקשן:** לא — Production נשאר `FEATURE_ATOMIC_CLAIMS=false` לאורך כל העבודה; אימות staging — ראה C111

### C111 — P0: `unhashable type: 'Identity'` ב-atomic-claims execution wrapper + סיווג DispatcherOutcome אמיתי (13/07/2026)
קבצים: `core/action_gateway.py` (`_make_dispatch_executor`), `core/action_gateway_atomic_executor.py`, `test_p0_unhashable_identity_atomic_wrapper.py` (חדש) | PR #326 | Staging: `FEATURE_ATOMIC_CLAIMS`
בדיקת smoke אמיתית מול PostgreSQL אמיתי (אחרי C110) הפילה `TypeError: unhashable type: 'Identity'` — ה-atomic gate עצמו פעל נכון וכשל-סגור (claim נרכש, הביצוע זרק exception לפני עדות מה-provider, ה-claim עבר ל-failed, המשתמש קיבל תשובת כשל), אבל ה-provider עצמו מעולם לא הופעל. Production הוחזר ל-`FEATURE_ATOMIC_CLAIMS=false` לפני התיקון. **Root cause מאומת ב-traceback מלא:** `execute_with_atomic_claim()` קרא ל-`executor_fn(tool_name, tool_inputs, identity)` **פוזיציונלית** — ל-executor האמיתי בפרודקשן (`_make_dispatch_executor`'s `_executor`) יש חתימה `(tool_name, tool_inputs, contract_id, identity=None)`; המקום השלישי הפוזיציוני הוא `contract_id`, לא `identity`. אובייקט ה-`Identity` המשוחזר נקשר בשקט ל-`contract_id`, ואז `ExecutionLedger.find_by_id()` ניסה `self._store.get(contract_id)` — `dict.get()` על מפתח לא-hashable (`Identity` הוא `@dataclass` בלי `frozen=True`, אז `__hash__=None` במפורש — **לא שונה** כדי "לשתוק" את השגיאה, בכוונה). הוכח שהמסלול הישן (flag כבוי) קורא ב-keyword (`contract_id=contract.contract_id`) ומעולם לא נתקל בבעיה. **תיקון:** שלושת קריאות ה-`executor_fn` ב-`execute_with_atomic_claim` עברו ל-keyword (`contract_id=contract_id, identity=identity`); `_executor` קיבל פרמטר `identity=` מפורש — כשסופק (מסלול אטומי, כבר עבר fail-closed validation ב-C110) נעשה בו שימוש ישיר (tenant/user/role/channel/external_id משתמרים), כשלא סופק (מסלול legacy) ההתנהגות זהה בית-לבית למה שהייתה. **פער סמוי שני שנתגלה ותוקן באותו סבב:** `dispatch_tool()` מעולם לא החזיר בפועל `DispatcherOutcome` (רק test mocks עשו זאת) — כך שגם אחרי תיקון הזהות, כל ביצוע אמיתי היה נתקל ב-"Dispatcher outcome type mismatch" ולעולם לא מגיע ל-`completed`. `execute_with_atomic_claim` מסווג כעת תוצאה גולמית (לא-`DispatcherOutcome`) דרך `verify_execution` — אותו מסווג מבוסס-עדות שה-legacy path כבר סומך עליו — כך שכתיבה מוצלחת אמיתית מגיעה בפועל ל-`completed`. בדיקת רגרסיה (`test_p0_unhashable_identity_atomic_wrapper.py`, 18 בדיקות) מפעילה את ה-executor **האמיתי** (לא mock עם חתימה נוחה) דרך `_execute_contract → execute_with_atomic_claim → dispatch_tool → airtable_update`; אומת מול קוד טרום-התיקון (`git stash`) שהיא נכשלת בדיוק עם `unhashable type: 'Identity'`.
**Merged:** כן (`38d90dc`, merge commit `b962773`, PR #326) | **Verified בפרודקשן:** לא (Production נשאר `FEATURE_ATOMIC_CLAIMS=false`) | **Verified ב-staging:** ✅ כן (13/07/2026) — לוג staging חי, contract=`785b09d1-24e9-44ba-81d5-4b16afe9b013`: `Claim acquired (execution ownership acquired)` → `using pre-resolved identity from atomic wrapper: tenant=boss_hq user=eliyahu role=owner external_id=7228089151` (שורת הלוג המדויקת שנוספה בתיקון זה — מוכיחה שהקוד החדש הוא זה שרץ בפועל) → `airtable_add` אמיתי (`record=recfQuL3n4bmUfeEf`) → `Execution succeeded (explicit)` → claim `outcome=completed` → `route_confirmation_word` החזיר תשובת הצלחה למשתמש. אין אף אחת מהודעות ה-fallback (`PostgreSQL not configured`/`psycopg2 not installed`) בלוג — מוכיח שהתביעה עברה דרך `atomic_claim_repository` האמיתי, לא stub. עדיין נדרש לפני הפעלה בפרודקשן: staged rollout plan (5%→25%→100%) ותקופת תצפית.

### C112 — BUG-104 P1-A/B/C re-audit: Lead Events lookup by record ID, live-schema normalize, honest readiness (16/07/2026)
קבצים: `core/leads_reasoning_projection.py`, `tma_api.py`, `test_bug104_leads_reasoning_projection.py` | PR #354 | באג: BUG-104
תיקון עצמאי-re-audit (verdict: FIX_REQUIRED), ללא שינוי scope. **P1-A:** ה-formula הישן `FIND(lead_id, ARRAYJOIN({Lead}))` התאים ל-*ערך התצוגה* של הרשומה המקושרת, לא ל-record ID — תוקן: הנקודת-קצה קוראת את מזהי reverse-link `Lead Events` שכבר על ה-snapshot הטעון, ורק כשקיימים מריצה שאילתה אחת על טבלת Lead Events עצמה: `OR(RECORD_ID()='rec1',...)`. reverse-link ריק → `[]` ללא קריאה; כשל קריאה אמיתי → `EVENTS_UNAVAILABLE`. **P1-B:** `_normalize_lead_snapshot()` (חדשה) ממפה שדות live lowercase (`phone/status/tier/source/channel/domain/created_at/updated_at/notes/summary/Score`) לשמות ה-CamelCase ש-`LeadsAdapter` מצפה להם, לפני הרצת ה-adapter, בלי לשנות את הרשומה המקורית; domain מפורש גובר עכשיו על ניחוש-מילות-מפתח. תוצאה: `status=lost` הפסיק ליפול ל-`OPEN`, `domain=real_estate` הפסיק לקרוס ל-`general`, `channel=email` הפסיק לקרוס ל-`whatsapp`. **P1-C:** readiness הפכה למצב-אמת מפורש (`{status: unknown|unavailable, reason}`), לעולם לא עותק של `phase` הlifecycle. Suite נכתב מחדש — 102 assertions, כולל סעיף Flask test-client אמיתי (401/403/404, off/shadow/on, קדימות בדיקת-domain של partner לפני reasoning, כשל-קריאה→honest unavailable).
**Merged:** כן (`71f04fb`, merge commit `07d6115`, PR #354) | **Verified בפרודקשן:** לא — `FEATURE_CORE_REASONING_LEADS_STATE` נשאר `off`, אין קורא production

### C113 — PR-RP0: Runtime Reliability & Permission Hardening — מסמכי תכנון (16/07/2026)
קבצים: `RUNTIME_RELIABILITY_AND_PERMISSION_HARDENING_SPEC.md` (חדש), `BOSS_PRODUCTION_RUNTIME_MAP.md` (חדש) | PR #355
Docs בלבד — אין שינוי קוד. נפתח ב-`--force` על `pre_session_gate.sh` (מאושר במפורש ע"י המשתמש), פותח את סדרת PR-RP0→RP4 (Runtime Reliability & Permission Hardening).
**Merged:** כן (`4efb61b`, merge commit `8a317a4`, PR #355) | **Verified בפרודקשן:** לא רלוונטי — docs בלבד

### C114 — PR-RP1: אכיפת invariants מבניים על tool_registry.py (16/07/2026)
קבצים: `tool_registry.py`, `tools/schemas.py`, `test_tool_registry_invariants.py` (חדש) | PR #356
`tool_registry.py` מקבל `validate_tool_invariants()`/`ToolRegistryInvariantError` — בדיקת מבנה ה-registry עצמו (לא runtime dispatch), **תמיד-פעילה, לא flag-gated**: כל tool רשום עומד בכללי מבנה קבועים (roles_allowed לא ריק, tenant_scoped/requires_approval/high_risk/read_only מוגדרים כ-bool, וכו'). 120 בדיקות חדשות.
**Merged:** כן (`b29fbcb`, merge commit `3fa6c47`, PR #356) | **Verified בפרודקשן:** ✅ כן — תמיד-פעיל, מקומי בלבד, לא נוגע ב-runtime dispatch

### C115 — BUG-104 Phase 1.1: Lead Reasoning Contract Hardening — status vocabulary + linkage (16/07/2026)
קבצים: `core/adapters/leads_adapter.py`, `tma_api.py`, `test_bug104_leads_reasoning_projection.py`, `test_bug104_phase1_1_contract_hardening.py` (חדש) | PR #357 | באג: BUG-104
שני תיקונים על בסיס audit מתוקן (PASS_WITH_CORRECTIONS). (1) **Status vocabulary mismatch:** `LeadsAdapter._normalise_status()` החזירה אוצר-מילים מקביל (`"OPEN"`/`"DECIDED_YES"`/...) שמעולם לא התאים לערכים הליטרליים ש-`DecisionStatus` מגדיר (`"Open"`/`"Decided Yes"`/...) — הערכים שמנועי Attention/Orchestrator המשותפים באמת משווים מולם. תוקן להחזיר את ערכי `DecisionStatus` הליטרליים עצמם — אותו סיווג (איזה raw status → איזה bucket), רק הערכים המוחזרים תוקנו. אומת בהרצה אמיתית (לא stub): lead פתוח לא ב-`closed_statuses`, `converted`/`lost`/`cancelled` (כולל עברית) ממופים נכון, Attention/Orchestrator באמת נכנסים לענפים הצפויים. (2) **Lead Events linkage:** אימות דו-כיווני חדש — השדה `Lead` של האירוע *עצמו* חייב להכיל את `lead_id` הנוכחי, לא רק reverse-link-reachable מה-Lead snapshot; אין קריאת Airtable נוספת (סינון על התוצאות שכבר נטענו). אין שינוי לחוזה הציבורי (`PROJECTION_VERSION` נשאר 1, `events` נשאר `{available, count}`). 57 בדיקות חדשות (`test_bug104_phase1_1_contract_hardening.py`), 102/102 בדיקות הprojection הקיימות עדיין ירוקות (2 שתוקנו בכוונה לשקף את התיקון: `DECIDED_NO` הפך לקבוע `DecisionStatus.DECIDED_NO`, fixtures קיבלו שדה `Lead` תואם). `test_core_reasoning.py` **לא** שונה — ה-stub הפנימי שלו מקרה בטעות את אותו באג-ישן, ותועד כממצא נפרד, לא תוקן (הוראה מפורשת).
**Merged:** כן (`08ad671`, merge commit `bfe284b`, PR #357) | **Verified בפרודקשן:** לא — `FEATURE_CORE_REASONING_LEADS_STATE` נשאר `off`

### C116 — PR-RP2: Shadow diagnostics לזמינות כלים per-role (17/07/2026)
קבצים: `tool_registry.py`, `context.py`, `feature_flags.py`, `test_tool_availability_shadow.py` (חדש) | PR #358 | Flag: `FEATURE_TOOL_AVAILABILITY_FILTER`
דיאגנוסטיקת shadow — לכל role, אילו כלים מותרים לפי ה-registry אך "לא-זמינים" מקומית (למשל תלות חסרה) נרשמים ללוג בלבד; `FEATURE_TOOL_AVAILABILITY_FILTER=shadow` (three-state off/shadow/enforce, ברירת מחדל `off`). אין שינוי ל-schema שנחשף ל-Agent בשלב הזה. 194 שורות בדיקות חדשות.
**Merged:** כן (`1b17337`, merge commit `461acf0`, PR #358) | **Verified בפרודקשן:** לא — flag `off`, shadow logging לא נצפה עדיין

### C117 — PR-RP3: Enforce — סינון schemas בפועל לכלים לא-זמינים (17/07/2026)
קבצים: `context.py`, `feature_flags.py`, `test_tool_availability_shadow.py` | PR #359 | Flag: `FEATURE_TOOL_AVAILABILITY_FILTER`
מרחיב את C116 — כש-`FEATURE_TOOL_AVAILABILITY_FILTER=enforce`, schemas של כלים role-allowed אך לא-זמינים מקומית מוסתרים בפועל מה-Agent (לא רק ברירת מחדל היה diagnostic-only ב-RP2, ראו תיקון-ניסוח בהערת המודול: "enforce" כעת אכן חוסם חשיפת schema, לא diagnostic-only כפי שתועד קודם). **ברירת מחדל נשארת `off`**.
**Merged:** כן (`59eafd1`, merge commit `f8577fe`, PR #359) | **Verified בפרודקשן:** לא — `off` בפרודקשן

### C118 — BUG-104 TMA Lead Event Bridge: כתיבות ליד מה-TMA נכתבות גם ל-Lead Events (17/07/2026)
קבצים: `core/lead_event_writer.py` (חדש), `tma_api.py`, `tools/approval_actions.py`, `test_bug104_tma_lead_event_bridge.py` (חדש) | PR #360 | באג: BUG-104
Root cause (אומת ב-grep, לא השערה): אף אחד משלושת נתיבי כתיבת-ליד מה-TMA (`update_lead_status` — תמיד דרך אישור; `patch_lead`/`set_lead_outcome` — owner מיידי, manager דרך אישור) מעולם לא קרא ל-`capture_lead_event()` או כתב ל-`Tables.LEAD_EVENTS` — טבלת הראיה של פרויקציית BUG-104 מעולם לא אוכלסה ע"י זרימת ה-CRM הראשית (TMA), רק ע"י הודעות inbound. תוקן במינימום: `write_tma_lead_event(lead_id, action, applied_fields, lead_domain=None)` חדש — best-effort, לעולם לא מרים exception, לעולם לא הופך כתיבת-ליד מוצלחת לכישלון, נקרא **רק** אחרי שהכתיבה הראשית הצליחה. **לא** תלוי ב-`LEAD_CAPTURE` (שנשאר כבוי כברירת מחדל) ו**לא** משתמש ב-`capture_lead_event()` (מיועד ל-inbound chat — junk filtering + event_type-from-message-text לא רלוונטיים לשינוי-שדה מובנה). Channel הוא ליטרל `"tma"` (לא `identity.channel`, שמתפענח כ-`"telegram"` לכל identity שעבר אימות TMA — `require_tma_auth` קורא ל-`resolve_identity("telegram", ...)`). Domain: נקרא מה-`Leads.domain` של הרשומה עצמה (לא project_slug/ProjectsHub), עובר `strip().lower()`, מאומת מול allowlist (`real_estate/saas/import/recruitment/general/media/crm`, מאומת מול live schema+כל 92 רשומות Leads קיימות) — לא קיים/לא מוכר → `general`; **אין** מיפוי project_slug→domain (נבדק ונדחה — הערכים הגולמיים כבר תואמים את ה-enum). Event Type תמיד `LeadEventType.OTHER` (הערכים המוצעים `lead_patch`/`outcome_change`/וכו' לא קיימים ב-schema החי; לא נוסף schema חדש). חובר ב-2 נקודות: `tma_api.py::patch_lead/set_lead_outcome` (אחרי `_at_patch` מוצלח) ו-`tools/approval_actions.py::tma_write()` (אחרי `patch` מוצלח, רק כש-`table=="Leads"` — לא Tasks/ProjectsHub/Contacts). 46 בדיקות חדשות, כולל שהאירוע החדש עובר את שער ה-linkage הקיים מ-C115. אין שינוי סכימה, אין backfill, אין Phase 2A, אין דגל חדש, אין שינוי response contract.
**Merged:** כן (`0a0c331`, merge commit `ba579f2`, PR #360, rebased מ-`e2fc370` על `origin/main f8577fe` ואומת remote==local לפני push) | **Verified בפרודקשן:** לא — `FEATURE_CORE_REASONING_LEADS_STATE` נשאר `off`, גם ה-bridge עצמו לא-flag-gated אך תוצריו (Lead Events חדשים) עדיין לא נצפו live

### C119 — TMA: הסתרה זמנית של כרטיס domain="saas" מ-Projects Hub (17/07/2026)
קבצים: `tma_api.py` (`_get_project_cards`) | PR #361
בקשת בעלים: להסתיר זמנית את כרטיס ה-Project (`ProjectsHub` slug=`boss-saas`, domain=`saas`, מאומת ב-Airtable MCP) ממסך Projects Hub, בלי למחוק את הרשומה ובלי לשנות `slug`/`domain`. תוקן בשכבת ה-display בלבד: `_get_project_cards()` מדלג על כל רשומת ProjectsHub ש-`domain == "saas"` לפני בניית ה-card — יחיד נקודת-קריאה של הפונקציה הזו (`GET /api/projects`), לא משפיע על `get_project_dashboard`/`get_leads` (מסכים אחרים). אומת פונקציונלית: כרטיס `boss-saas` מוחסר, שלושת הכרטיסים האחרים (`furniture-import`/`recruitment`/`blueview`) חוזרים ללא שינוי. נפתח ב-`--force` על `pre_session_gate.sh` (3 ענפים לא-ממוזגים לא-קשורים באותה עת, מאושר במפורש).
**Merged:** כן (`bee46b5`, merge commit `749001f`, PR #361) | **Verified בפרודקשן:** לא עדיין נבדק live לאחר deploy

### C120 — PR-RP4: Evidence Finalizer — shadow mode (17/07/2026)
קבצים: `core/turn_evidence.py` (חדש), `app.py`, `feature_flags.py`, `test_turn_evidence_shadow.py` (חדש) | PR #362 | Flag: `FEATURE_EVIDENCE_FINALIZER`
`core/turn_evidence.py` חדש — evidence finalizer עבור תור-agent, three-state `FEATURE_EVIDENCE_FINALIZER` (off/shadow/enforce, ברירת מחדל `off`). גם "enforce" נשאר comparison-only בשלב הזה (עד RP5) — אין effect על ה-response האמיתי.
**Merged:** כן (`3a3edbe`, merge commit `96cf643`, PR #362) | **Verified בפרודקשן:** לא רלוונטי — shadow-only, `off`

### C121 — Governance docs sync: תיקון מצב הפעילות #354–#364 (17/07/2026)
קבצים: `AI_CONTEXT.md`, `ROADMAP.md`, `CHANGELOG.md`, `CHANGE_CONTROL_LOG.md` | PRs #363–#364 | Docs בלבד
PR #363 (`28d4f09`, merge `60991c1`) רענן את ה-daily briefing ב-`AI_CONTEXT.md` בלבד. בניגוד לטענה בדוח שהודבק לאחר מכן, merge זה לא כלל draft או תיקון ל-`ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md`. הפער נשאר פתוח עד PR #364 (`1d31aab`, merge `80fdfae`), שהוסיף בפועל את רשומות #354–#362 לשלושת מסמכי הממשל ועדכן את תאריך ה-ROADMAP. עדכון המשך זה מיישר גם את `AI_CONTEXT.md` עם המצב לאחר המיזוג ורושם את #363–#364 עצמם.
**גבול סקופ מפורש:** לא בוצע backfill היסטורי. `CHANGELOG.md` עדיין חסר itemization נפרד ל-#348–#353 (PA-01), וקובץ זה עדיין חסר C-records עבור #327–#353 אחרי C111. הפערים מסומנים; הם אינם מוצגים כעבודה שכבר הושלמה.
**Merged:** PR #363 כן (`60991c1`); PR #364 כן (`80fdfae`) | **Verified בפרודקשן:** לא רלוונטי — docs בלבד

**הערת גבולות (17/07/2026):** הרשומות C112–C120 מתעדות את #354–#362, ו-C121 מתעדת את סנכרון מסמכי הממשל עבור #363–#364. **פער קודם ורחב יותר נשאר פתוח במכוון**: קובץ זה לא תועד כלל בין PR #326 (C111) ל-PR #354 — כלומר PRs #327 עד #353 (הכוללים את סאגת PA-01 ותיקוני approval-callback שכבר מתועדים חלקית ב-`CHANGELOG.md`) עדיין אין להם רשומת C כאן. לא בוצע להם backfill בסבב הזה.

### C122 — BUG-104 Phase 2A.0: Leads Schema Cleanup & Canonicalization SPEC (17/07/2026)
קבצים: `docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md` (חדש) | PR #370 | באג: BUG-104
Audit + SPEC בלבד — אין קוד/schema/frontend. אינוונטר סכמת Leads חי (39 שדות, Airtable MCP `get_table_schema`/`list_records_for_table`, 17/07/2026) + ערכים חיים על כל 92 הרשומות + מפת read/write מלאה בקוד (file:line) לכל אחד מ-16 השדות הרלוונטיים. ממצאים מרכזיים: (1) 5 מימושי tier/temperature עצמאיים ולא-מתואמים בקוד (`lead_capture.py`×2, `furniture_lead_funnel.py`, `daily_digest.py`, `score_display.py`), אף אחד לא "מקור אמת"; (2) שני אתרי כתיבה עצמאיים כותבים `status="converted"` לא-קנוני (`lead_conversion.py`, `ad_attribution.py`) — עוקפים את הוולידציה של `tma_api.py::patch_lead` — שורש-הבעיה שתוקן ב-C124/PR #372; (3) שלוש הצהרות תיעוד סותרות לגבי `tier` (writable/לא-קיים/formula-read-only) — המציאות: singleSelect אמיתי, 100% ריק (0/92, מאומת ישירות); (4) `Domain category`/`Domain risk assessment`/`Domain summary` הם misapplied Airtable AI feature — `Domain summary` הוא שדה `aiText` שמפרש את `domain` הפנימי (`"general"`/`"saas"`/וכו') כאילו הוא שם-דומיין-אינטרנט, 0 references בקוד. מודל קנוני מוצע: `status`/`Business Outcome`/`Score`/`domain` כקנוניים, 6 שדות formula כ-display-only, `tier`+3 שדות Domain* כמועמדי-ניקוי עתידי (אחרי החלטת owner).
**Merged:** כן (`8b4d51e`, merge `a4d04c0`, PR #370) | **Verified בפרודקשן:** לא רלוונטי — docs בלבד

### C123 — BUG-104 Phase 2A.1: Current State Policy SPEC (17/07/2026)
קבצים: `docs/architecture/bug-104/PHASE_2A1_CURRENT_STATE_POLICY_SPEC.md` (חדש) | PR #371 | באג: BUG-104
Audit + SPEC בלבד — אין קוד. תלוי ב-C122/PR #370 (הרביעייה הקנונית כבסיס). §0 מתעד עובדתית (לא מניח) את שרשרת הקוד המלאה שקובעת `state`/`phase` ל-Lead היום (`core/leads_reasoning_projection.py`→`LeadsAdapter`→`core/reasoning_engines.py`→`decision_orchestrator.py`), עם ממצא מרכזי: **`Business Outcome` לא נקרא באף שלב בשרשרת הזו כיום** — שינוי ב-Business Outcome בלי שינוי מקביל ב-status לא ישנה את ה-state המוקרן בכלל. גם: מתוך 10 ערכי status חיים, רק `new`/`lost` ממופים בכוונה ב-`LeadsAdapter._normalise_status()` — שאר השמונה (כולל `done`, הערך הקנוני ל"הומר" לפי `tma_api.py::_OUTCOME_STATUS_MAP`) נופלים לברירת מחדל `OPEN`. מגדיר מדיניות precedence מוצעת (Business Outcome terminal גובר על status; Score/tier/Next Action/Next Followup לא קובעים state; Lead Events מעלים confidence בלבד) + 4 דוגמאות expected-output מול ה-as-is המתועד + תוכנית יישום עתידית + 4 שאלות פתוחות (שמות enum ל-state, מיפוי terminal-administrative, `status=done` בלי Business Outcome, תזמון תיקון שני כותבי ה-`"converted"` הלא-קנוניים).
**Merged:** כן (`fde5c51`, merge `7894bd0`, PR #371) | **Verified בפרודקשן:** לא רלוונטי — docs בלבד. **קוד runtime של Phase 2A טרם התחיל.**

### C124 — BUG-110: תיקון non-canonical status="converted" writers (17/07/2026)
קבצים: `lead_conversion.py`, `ad_attribution.py`, `test_response_contract_fixes.py`, `test_bug105_non_canonical_converted_status.py` (חדש) | PR #372 | באג: BUG-110 (ראו הערת מספור למטה)
תיקון ישיר על בסיס ממצא C122/Phase 2A.0: `lead_conversion.py::convert_lead_to_contact()` (`_at_patch`, דרך ה-gateway) ו-`ad_attribution.py::mark_converted()` (`tools.airtable_tools.airtable_update`, **לא** דרך ה-gateway) כתבו `status="converted"` — ערך שאינו קיים ב-`LeadStatus.ALL`/לא אופציית `Leads.status` חיה, ועוקף את הוולידציה הקיימת ב-`tma_api.py::patch_lead`. תוקן: שני האתרים כותבים כעת `status=LeadStatus.DONE` + `Business Outcome=LeadOutcome.CONVERTED` (הקבועים הקיימים ב-`airtable_schema.py`, כולל הרווח-הזנב המובנה ב-Airtable) — אין שדה/אופציה חדשה, אין backfill. **`ad_attribution.py` נשאר במכוון על `tools.airtable_tools.airtable_update`** — מעבר ל-gateway היה משנה את חוזה ה-return של הפונקציה (`bool` מול `dict` עם `result.get("ok")`) ושובר את `test_response_contract_fixes.py` הקיים; חוב טכני מתועד, לא תוקן בסבב הזה. גם תוקן: `test_response_contract_fixes.py`'s baseline (`_LEGITIMATE_AIRTABLE_GET_ENTRIES`) — מספר שורה קבוע-בקוד זז ב-1 בגלל import חדש, לא שינוי התנהגות. `build_attribution_report()` (`ad_attribution.py`) ו-`audience_intelligence.py` עדיין קוראים `status=="converted"` לדיווח/סגמנטציה — יימצאו ונשארו לא-מתוקנים במפורש (יחסירו לידים שהומרו אחרי התיקון, אין backfill). 10 בדיקות חדשות (`test_bug105_non_canonical_converted_status.py`), 19/19 `test_response_contract_fixes.py`, 102+57+46+59 בדיקות BUG-104/Core Reasoning ללא שינוי.
**הערת מספור:** התיקון תויג `BUG-105` בקוד/PR title/commit message/שם קובץ הבדיקה **לפני** שהתגלה ש-`BUG-105` כבר תפוס ב-`BUG_AUDIT_LOG.md` (פורמט טלפון בין-לאומי עם מקף, 12/07/2026, לא קשור, עדיין פתוח/לא-תוקן). לפי החלטת owner מפורשת, התיעוד (כאן, ב-`BUG_AUDIT_LOG.md`, וב-`AI_CONTEXT.md`/`ROADMAP.md`/`CHANGELOG.md`) משתמש ב-**BUG-110** (המספר הפנוי הבא אחרי BUG-109); שמות הקבצים/ה-PR/ה-commit **לא** שונו רטרואקטיבית ב-`main`.
**Merged:** כן (`fa1506e`, merge `b344b02`, PR #372) | **Verified בפרודקשן:** לא — הכתיבות החדשות (`status=done`+`Business Outcome=converted`) עדיין לא נצפו על ליד אמיתי בפרודקשן

**הערת גבולות (19/07/2026):** רשומות C125–C130 למטה מתעדות **PR #391–#396 בלבד** (הסבב הנוכחי, ממוקד runtime evidence). PR #373–#390 **עדיין לא backfilled** בקובץ הזה — פער נפרד, גדול יותר, שמסומן במפורש ולא נסגר בסבב הזה (ראו `ROADMAP.md`/`AI_CONTEXT.md` לתיאור המצב העדכני שלהם דרך `CHANGELOG.md`/`BUG_AUDIT_LOG.md` שכן סונכרנו). כל רשומה למטה מאומתת מול `main` (`git log`/`git cat-file -e`) לפני כתיבה.

### C125 — Governance docs sync: BUG_AUDIT_LOG.md/CHANGELOG.md ל-PR #385–#390 (19/07/2026)
קבצים: `BUG_AUDIT_LOG.md`, `CHANGELOG.md` | PR #391 | Docs בלבד
הוסיף רשומות עבור עבודה ממוזגת שעדיין לא השתקפה באף אחד משני יומני הממשל: BUG-111 (שני הסבבים), BUG-112 (#387), F52 PR4 (#385) ו-PR5 (#389), וסנכרון AI_CONTEXT (#388).
**Merged:** כן (`8b4e444`, merge `5cfb5ad`, PR #391) | **Verified בפרודקשן:** לא רלוונטי — docs בלבד

### C126 — F52 PR6: approval_pending prompt דרך unified formatter shadow + תיקון EvidenceFinalizer/ownership (19/07/2026)
קבצים: `core/action_gateway.py`, `core/turn_evidence.py`, `app.py`, `test_f52_pr6_pending_shadow.py` (חדש) | PR #392
שלושה ממצאים אמיתיים על נתיב ה-approval_pending: (1) `_queue_approval_detailed_impl()` שלח hardcoded text בעקיפין ל-`bot.send_message()` בלי מעורבות formatter כלל — ה-shadow לא ראה; (2) `core.turn_evidence._classify_response_claim()` קרא דיכוי תקין של A32 כ-`response_claim=empty` (false mismatch); (3) `build_ownership_signal()` לא סימן `reply_owner="gateway"` כשה-agent דוכא. תוקנו שלושתם ללא שינוי בהתנהגות בפועל. 50 בדיקות חדשות.
**Runtime evidence:** לוגי production מציגים `[UnifiedStatusFormatterShadow] outcome=pending mapped_state=approval_pending` — shadow רץ בפועל, למרות ש-`FEATURE_UNIFIED_STATUS_FORMATTER`'s ברירת מחדל בקוד היא `off` (אין להסיק מ-ברירת-מחדל ש-shadow לא רץ — ראו כלל התהליך ב-`AI_CONTEXT.md`).
**Merged:** כן (`38c2820`, merge `90e7e23`, PR #392) | **Verified בפרודקשן:** ✅ כן — runtime shadow evidence כנ"ל

### C127 — F52 PR6 follow-up: הרחבת taxonomy ל-turns מעורבים (read+approval_pending) (19/07/2026)
קבצים: `core/turn_evidence.py`, `test_f52_pr6_pending_shadow.py` | PR #393
turn שמבצע גם read מאומת וגם מעלה approval מסווג `evidence_status="mixed"` (לא `"approval_pending"`) — עדיין false mismatch. `compare_shadow_final_status()` הורחב: `"sent_for_approval"` תואם גם ל-`"mixed"` כשה-non-success היחיד הוא `approvals_pending`. 5 בדיקות הגנה נוספות (55 סה"כ).
**Runtime evidence — ✅ הענף המדויק נלכד (עדכון 19/07/2026):** נצפתה דגימה סמוכה (`evidence_status=mixed verified_reads=1 approvals_pending=1 response_claim=mixed mismatch=false`) שמוכיחה ש-turns מעורבים מתנהגים נקי, **וגם** דגימה מאוחרת יותר (אותו יום) על הענף המדויק עצמו: `evidence_status=mixed response_claim=sent_for_approval mismatch=false verified_reads=1 approvals_pending=1` — turn שביצע `airtable_get` (בדיקת סטטוס משימה) ואז `airtable_update` requires_approval באותו turn. שני הענפים כעת מאומתים.
**Merged:** כן (`53eb19d`, merge `440234f`, PR #393) | **Verified בפרודקשן:** ✅ כן (עדכון 19/07/2026) — שני הענפים נלכדו, ראו הערת runtime evidence למעלה

### C128 — BUG-112 (סבב 2): נרמול UX לניסוח stale/missing-callback אחיד (19/07/2026)
קבצים: `app.py`, `test_bug112_telegram_approval_ttl.py` | PR #394 | באג: BUG-112
לחיצה כפולה על כפתור שפג תוקף הפיקה שלושה ניסוחים חופפים-אך-שונים. `_notify_missing_or_expired_callback()` חדש מאחד לביטוי יחיד בכל שלוש הבמות. אין שינוי לסמנטיקת ביצוע. 8 בדיקות חדשות (30 סה"כ). **הבחנה חשובה:** זהו defensive/idempotency cleanup לנתיב **שונה** מ-BUG-112 המקורי (שכבר VERIFIED IN PROD — ראו `BUG_AUDIT_LOG.md`) — אין לסמן PR זה כ-production-proven בנפרד עד שתיצפה דגימת missing/stale-callback מפורשת.
**Merged:** כן (`8ac0c93`, merge `ad4afc9`, PR #394) | **Verified בפרודקשן:** לא — merged/tests green בלבד, defensive cleanup טרם נבדק live

### C129 — AI_CONTEXT daily briefing: PR #388–#393 (19/07/2026)
קבצים: `AI_CONTEXT.md` | PR #395
מרענן את מסמך ה-briefing עבור PR #388–#393. מסמן `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` כמפגרים אחרי `main`.
**Merged:** כן (`951b1b2`, merge `51405ae`, PR #395) | **Verified בפרודקשן:** לא רלוונטי — docs בלבד

### C130 — BUG-113: A32 מדכא פרוזת approval-invite כפולה כשאישור אמיתי כבר בתור (19/07/2026)
קבצים: `core/anti_hallucination.py`, `test_a32_approval_prose_suppression.py` (חדש) | PR #396 | באג: BUG-113
שער ה-Single-Speaker הקיים לא כיסה פרוזת approval-invite ("✅ מוכנה להוספה... שלח מאשר כדי לאשר") כשאישור אמיתי כבר נכנס לתור — `_AGENT_APPROVAL_INVITE_PATTERN` הקיים נבדק רק בשער הנפרד למקרה **ההפוך** (אין ראיה). ענף דיכוי חדש, גדור ב-`_gateway_active` וראיית `__approval_queued__` אמיתית. 18 בדיקות חדשות.
**Runtime evidence:** לוגי production **אחרי** ה-deploy מציגים את שלושתם יחד — לוג הדיכוי, `ownership_signal` עם `reply_owner=gateway`/`agent_claimed_approval=false`, ו-`EvidenceFinalizerShadow` עם `response_claim=sent_for_approval mismatch=false`. הפלט למשתמש הכיל רק את הודעת ה-gateway.
**Merged:** כן (`2d86de6`, merge `587d1fe`, PR #396) | **Verified בפרודקשן:** ✅ כן — evidence מדויק מלוגים אחרי deploy, ראו `BUG_AUDIT_LOG.md`'s BUG-113. **סגור.**

### C131 — BUG-113 (סבב 2/FU): תיקון פערי markdown-emphasis וצורת-זכר ב-A32 (19/07/2026)
קבצים: `core/anti_hallucination.py`, `test_a32_approval_prose_suppression.py` | PR #399 | באג: BUG-113
דגימת production חדשה **אחרי** C130/PR #396 עדיין הראתה כפילות, עם ניסוח שונה: `שלח **מאשר**` (bold markdown, שתי כוכביות — ה-`\*?` המקורי תמך רק בכוכבית אחת) ו-`⏳ ...ממתין לאישור` (זכר בלי סיומת — `ממתין` מסתיים ב-nun **סופית** ן, אות יוניקוד שונה מה-נ הרגילה בתוך "ממתינה"/"ממתינת", כך שסיומת אופציונלית לא הספיקה). תוקן: `_strip_markdown_emphasis()` חדש (מסיר `*`/`_` ל-matching בלבד, בלתי-תלוי-בכמות — סוגר גם `***מאשר***`/`_מאשר_`), ואלטרנציה מפורשת `(?:ממתינ[הת]|ממתין)` במקום סיומת אופציונלית. 10 בדיקות חדשות (28 סה"כ בקובץ).
**Merged:** כן (`72414c3`, merge `bb4efdb`, PR #399) | **Verified בפרודקשן:** ✅ כן — דגימת production אחרי ה-deploy (19/07/2026) הראתה הודעה יחידה, אין כפילות. ראו `BUG_AUDIT_LOG.md`'s BUG-113 (סבב 2). **סגור.**

### C132 — TurnOwnershipShadow: אינווריאנט shadow חדש לזליגת agent ב-turn בבעלות gateway (19/07/2026)
קבצים: `core/turn_envelope.py`, `test_turn_envelope.py` | PR #400
תצפית טהורה, לא flag-gated, ללא שינוי התנהגות: כש-`approval_queued=true` ו-`reply_owner="gateway"` (כלומר A32 היה אמור לדכא את טקסט ה-agent לגמרי) אך `final_reply` עדיין לא ריק, נרשם `[TurnOwnershipShadow] violation=agent_spoke_in_gateway_owned_approval_turn` + `pattern_class` (approval_invite/pending_status/action_status/unknown, מחושב מול `core/anti_hallucination.py`'s patterns הקיימים, כולל `_strip_markdown_emphasis` מ-C131). `OwnershipSignal` קיבל שני שדות חדשים (`final_reply_nonempty` ב-routine log, `leaked_pattern_class` רק ב-WARNING line). אין נגיעה ב-`app.py` (הפרמטרים הדרושים כבר עברו לפני כן), ActionGateway, או EvidenceFinalizer taxonomy. 25 בדיקות חדשות (95 סה"כ בקובץ).
**Merged:** כן (`c31c219`, merge `8bdd504`, PR #400) | **Verified בפרודקשן:** ✅ כן — דגימת production 19/07/2026 (סגירת #393, ראו C127) הראתה `final_reply_nonempty=false` ואין violation, מאמת שהאינווריאנט מזהה נכון גם את המקרה התקין (no false positive), לא רק את מקרה הדליפה.

### C133 — BUG-114: ביקורת (audit-only) ל-ActionContracts context-interrupt call amplification (19/07/2026)
קבצים: `docs/architecture/action-gateway/BUG-114_CONTEXT_INTERRUPT_CALL_AMPLIFICATION_AUDIT.md` (חדש) | באג: BUG-114 | Docs בלבד
נחקר בנפרד מ-BUG-111/112/113/PR #393/#399/#400, לפי בקשה מפורשת שלא לערבב. דגימת production אחת (הודעה בלתי-קשורה, 6 contracts pending) הפיקה 19 קריאות Airtable. Root cause מאומת בקוד: `ExecutionLedger.mark_context_interrupted()` (`core/action_gateway.py:558`) מסמן מחדש **כל** contract "pending" של המשתמש, כולל כאלה שכבר `context_interrupted=True` — ה-filter לא בודק את השדה הזה, וה-shortcut האידמפוטנטי הקיים ב-`transition()` לא עוזר כי `updates` לא ריק גם כשהערך לא באמת השתנה. תיקון צר מוצע (לא ממומש): תנאי `and not c.context_interrupted` נוסף — בדיקת RAM טהורה, אפס I/O נוסף, לא נוגע ב-GET-before/GET-after PATCH של `transition()` עצמו (TOCTOU safety, לא מוחלש). שתי המלצות נוספות (reuse PATCH response body במקום readback נפרד; מדיניות TTL/ניקוי ל-contracts pending ישנים) מסומנות במפורש כמחוץ לתיקון הצר, ממתינות להחלטת owner נפרדת. אין קוד runtime שהשתנה.
**Merged:** כן (docs בלבד) | **Verified בפרודקשן:** לא רלוונטי — audit בלבד, אין תיקון עדיין

### C134 — BUG-114: יישום התיקון הצר ל-context-interrupt amplification (19/07/2026)
קבצים: `core/action_gateway.py`, `test_bug114_context_interrupt_amplification.py` (חדש) | באג: BUG-114
מימוש התיקון המוצע ב-C133, **אך עם תיקון על התיקון**: ההצעה המקורית (`and not c.context_interrupted` פשוט) הייתה שוברת רגרסיה קיימת — `test_bug_reconfirmation_oneshot_fsm.py`'s Regression B קוראת ל-`mark_context_interrupted()` פעמיים על אותו contract; בקריאה השנייה ה-contract כבר `context_interrupted=True` מהקריאה הראשונה, אז filter נאיבי היה מדלג עליו **גם כשצריך supersede אמיתי** (BUG-108/BUG-PENDING-APPROVAL-B, כבר VERIFIED IN PROD). נתפס תוך כדי כתיבת הבדיקות, לא בביקורת המקורית. התנאי שיושם בפועל: `and (c.reconfirmation_required or not c.context_interrupted)` — contracts עם `reconfirmation_required=True` **לעולם לא** מדולגים, ללא קשר לערך `context_interrupted` הנוכחי שלהם. 12 בדיקות חדשות (5 התרחישים המתוכננים, כולל Test 3 שמקודד במפורש את הרגרסיה שנתפסה); `test_bug_reconfirmation_oneshot_fsm.py` (27/27) רץ מחדש כהוכחה עצמאית. Suite מלא ירוק, smoke/compileall/diff-check נקיים. אינו נוגע ב-GET-before/GET-after PATCH של `transition()` (TOCTOU/readback, Q4/Q5 — לא מוחלשים), F52, EvidenceFinalizer, או BUG-111/112/113.
**Merged:** תלוי במיזוג PR #402 (`claude/audit-action-contracts-call-amplification`) | **Verified בפרודקשן:** לא — התיקון טרם נצפה מפחית קריאות אמיתיות

### C135 — BUG-114: אימות production (19/07/2026)
קבצים: `BUG_AUDIT_LOG.md`, `AI_CONTEXT.md`, `ROADMAP.md` | באג: BUG-114 | Docs בלבד
דיווח production מפורש: "BUG-114 / PR #402 — ✅ PRODUCTION VERIFIED for call-amplification reduction. No repeated per-contract re-marking burst observed after already-interrupted contracts." סוגר את BUG-114 במלואו — קוד (C134) ואימות live כאחד.
**Merged:** כן (docs בלבד) | **Verified בפרודקשן:** ✅ כן

### C136 — BUG-115: ביקורת (audit-only) ל-"כן" שנחטף לתפריט disambiguation גנרי (19/07/2026)
קבצים: `docs/architecture/action-gateway/BUG-115_CONFIRMATION_ROUTING_HIJACK_AUDIT.md` (חדש) | באג: BUG-115 | Docs בלבד
נחקר בנפרד מ-BUG-114 לפי בקשה מפורשת, למרות שיתוף שורש-משותף (contracts pending לא פוקעים לעולם — BUG-114 §2 שאלה 6). דגימת production: תצוגת "📋 זיהיתי ליד..." (contract Tier-1 אמיתי, לפי עיצוב BUG-056 מכוון — לא בלבול Tier-1/Tier-2) ואחריה "כן" נותב ל-disambiguation גנרי של 8 contracts ישנים ולא-קשורים, עם tool_name/id גולמיים גלויים למשתמש. Root cause מאומת בקוד: `route_confirmation_word()` (`core/action_gateway.py:1010`) מניח contract חי יחיד (הנחת BUG-056) וסופר בלבד — `len(live)>1` תמיד מציג רשימה גנרית, ללא זיהוי "לאיזה contract ה-'כן' מתייחס בפועל". ממצא משני מאומת: `TurnEnvelope.active_queue_id` אכן מעדיף `action_gateway` (priority=3) על `lead_capture` (priority=5), אך זהו מנגנון תצפית-בלבד (Phase 0) שלא נקרא כלל בנתיב הניתוב האמיתי — לא הגורם בפועל. `message_kind` אינו קיים כמנגנון פעיל (Phase 4, לא ממומש). תיקון מוצע (לא ממומש), שני חלקים: (1) bookmark "contract שהוצג לאחרונה" בדפוס `set_pending_lead_preview` הקיים, נבדק לפני ספירת `find_live_contracts()`; (2) שימוש חוזר ב-`_describe_contract_for_reconfirmation()` הקיים במקום tool_name/id גולמיים ברשימת disambiguation. אין קוד runtime שהשתנה.
**Merged:** כן (docs בלבד) | **Verified בפרודקשן:** לא רלוונטי — audit בלבד, אין תיקון עדיין

### C137 — BUG-115: יישום התיקון הצר ל-confirmation routing hijack (19/07/2026)
קבצים: `session_store.py`, `core/lead_candidate_handler.py`, `app.py`, `core/action_gateway.py`, `test_bug115_confirmation_routing_bookmark.py` (חדש) | באג: BUG-115
מימוש שני החלקים המוצעים ב-C136. (1) Bookmark: שלוש מתודות חדשות ב-`session_store.py` (`set/get/clear_last_prompted_contract`, TTL 600 שניות — תואם `_PENDING_APPROVAL_TTL`, לא 1800 כמו בוקמארקים אחרים בקובץ), נרשם ב-`_handle_single_candidate()` (lead preview) וב-`app.py`'s `_queue_approval_detailed_impl()` (אחרי `owner_notified` מוכח). `route_confirmation_word()` בודק אותו לפני ספירת contracts. **תיקון מדויק מעבר להצעה:** לוגיקת reconfirmation חולצה ל-`_resolve_single_contract()` משותפת (בוקמארק לעולם לא עוקף בטיחות BUG-PENDING-APPROVAL-B); בוקמארק **נשמר** (לא מנוקה) במקרה "צריך reconfirmation" — נקודה שנתפסה תוך כדי כתיבת בדיקות. (2) תוויות אנושיות: **ניסיון ראשון שבר בדיקה קיימת** — הרחבת ה-fallback הכללי ישירות בתוך `_describe_contract_for_reconfirmation()` המשותף שינתה בשקט גם את הודעת "✅ בוצע" ב-`_compose_status_reply_legacy()`, ששוברת את `test_stage_b_full_suite.py`'s DoD20 (מסתמכת על `tool_name` גולמי שם). תוקן: פונקציה חדשה נפרדת `_describe_contract_for_disambiguation()`, נקראת רק מלולאת ה-disambiguation; הפונקציה המשותפת המקורית לא נגעה כלל. 22 בדיקות חדשות. `test_bug114_context_interrupt_amplification.py` (12/12) ו-`test_bug_reconfirmation_oneshot_fsm.py` (27/27) רצו מחדש כהוכחה. Suite מלא (כולל `test_stage_b_full_suite.py` 128/128 אחרי התיקון), smoke, compileall, diff-check — כולם נקיים.
**Merged:** ✅ כן — `main` `4ce2fae` (Merge pull request #403) | **Verified בפרודקשן:** לא — התיקון טרם נצפה מול תעבורה חיה

### C138 — BUG-116: ביקורת + תיקון — `_AIRTABLE_ID_RE` ב-Tier-4 gate תופס מילים אנגליות רגילות (19/07/2026)
קבצים: `core/ingress_classifier.py`, `test_bug116_airtable_id_word_false_positive.py` (חדש), `docs/architecture/ingress-classifier/BUG-116_AIRTABLE_ID_REGEX_WORD_FALSE_POSITIVE.md` (חדש) | באג: BUG-116
נחקר בנפרד לגמרי מ-BUG-114/BUG-115 — שגיאת Tier-4 ingress-classification, לא ActionGateway/ActionContract. דגימת production: "צור ליד חדש לדומיין recruitment... יהודה גרוס 0533968395" (משפט ליד תקין לגמרי, שם+טלפון אמיתיים) סווג כ-`tier=4 reason=airtable_id` וחסם לגמרי לפני חילוץ מועמדים — חזר זהה על 3 ניסיונות. Root cause מאומת בהרצה ישירה: `_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)[A-Za-z0-9]{8,}\b")` ללא גבול עליון/דרישת-צורה — `recruitment` = `rec`+`ruitment` (8 אותיות) תואם במקרה. ניסיון ראשון (גבול אורך מדויק כמו רגקסי-ID אמיתיים אחרים בקוד) נדחה — היה שובר את `test_c89_tier4_precedence.py`'s fixture הקיים (`recABC1234567890`, זנב של 13 תווים בלבד, לא 14). תוקן עם lookahead הדורש ספרה אחת לפחות בתוך הרצף: `(?=[A-Za-z0-9]*\d)` — אומת תכנותית מול כל fixture ID אמיתי/מזויף בסוויטה (כולם מכילים ספרה, ID אמיתי הוא base62 אקראי; מילה אנגלית לעולם לא). מחוץ לסקופ במפורש: `core/agent_message_formatter.py`'s רגקס נפרד לצנזור פלט (פרופיל-סיכון שונה, לא נגעו). 15 בדיקות חדשות; `test_c89_tier4_precedence.py` (13/13) ללא רגרסיה. Full regression sweep: 138/138 קבצי `test_*.py`, exit 0. smoke/compileall/diff-check נקיים.
**Merged:** ✅ כן — `main` `0ef018f` (Merge pull request #404) | **Verified בפרודקשן:** לא (בזמן המיזוג) — ראה C139 לאימות

### C139 — BUG-116: אימות production (19/07/2026)
קבצים: `BUG_AUDIT_LOG.md` | באג: BUG-116 | Docs בלבד
דגימת production ישירה מיד אחרי מיזוג PR #404: "צור ליד חדש domain recruitment... יונתן כהן - 0534820022" (ניסוח שונה מהדגימה המקורית — `domain recruitment` באנגלית בלי `לדומיין`/מקף, מוודא שהתיקון כללי) → `📋 זיהיתי ליד: יונתן כהן (0534820022)` נכון, לא "📄 זה נראה כמו טבלה" כמו קודם; "כן" → `✅ בוצע: יצירת ליד... מזהה: recNhWVHDd9Noeql1`. סוגר את BUG-116 במלואו. **הערה:** אותה דגימה עקבית עם BUG-115 (bookmark) עובד גם כן (אין disambiguation hijack), אך **לא מספיקה** לסמן את BUG-115 כ-verified — חסרה ראייה של `live_contracts>1` באותו רגע כדי להבדיל מהמסלול הקודם (`len(live)==1`, לא-קשור-לבאג). BUG-115 נשאר "לא נבדק בפרודקשן".
**Merged:** כן (docs בלבד) | **Verified בפרודקשן:** ✅ כן (BUG-116 בלבד)

### C140 — BUG-115: אימות production (19/07/2026)
קבצים: `BUG_AUDIT_LOG.md` | באג: BUG-115 | Docs בלבד
דגימת production עם הראייה שהייתה חסרה ב-C139: `[TurnEnvelope] case_c_signal kind=C1 detail=live_contracts=10` (10 contracts pending בו-זמנית, כולל ה-9 הישנים מהדגימה הקודמת) — "כן" על ליד טרי שהוצג הרגע נפתר ישירות מול ה-contract הנכון (`4c7b539b-3df4-4116-8caa-80b6b7c84843`, ליד "יצחק גלבר") ללא תפריט disambiguation: `Dispatch airtable_add → POST /Leads 200 OK → executed: external_id=rec34IdTmCFVbRABo` → `route_confirmation_word()` → `"✅ בוצע: יצירת ליד: יצחק גלבר, 0527696084, general"`. סוגר את BUG-115 במלואו — התנאי `live_contracts>1` המפורש (שנדרש כדי להבחין מהמסלול הקודם `len(live)==1`) עכשיו מסופק. **הערה מפורשת (התבקשה):** הדגימה F52 executed-shadow נקייה (`outcome=executed mapped_state=success`, כל דגלי ה-leak `False`) — **לא** נספרת כדגימת RP5/EvidenceFinalizer בהיעדר שורת `EvidenceFinalizerShadow` תואמת לאותו turn; סטטוס RP5 לא עודכן.
**Merged:** כן (docs בלבד) | **Verified בפרודקשן:** ✅ כן

### C141 — BUG-117: ביקורת + תיקון — Tier-2 batch lead-preview נחטף לאותה disambiguation שBUG-115 תיקן עבור Tier-1 (19/07/2026)
קבצים: `app.py`, `core/lead_candidate_handler.py`, `test_c89_preview_confirmation.py` (עודכן), `test_bug117_batch_preview_precedence.py` (חדש), `docs/architecture/action-gateway/BUG-117_BATCH_PREVIEW_PRECEDENCE_HIJACK.md` (חדש) | באג: BUG-117
נחקר בנפרד מ-BUG-115 (שורש-תרומה משותף — contracts pending לא פוקעים לעולם, BUG-114 §2 שאלה 6 — אבל מנגנון קוד שונה לגמרי). דגימת production: batch preview ("📋 זיהיתי 2 לידים אפשריים בקבוצה... כן לשמירת כולם") ואחריה "כן" נותב ל-"יש כמה פעולות הממתינות לאישור" (9 contracts ישנים) במקום לאשר את שני הלידים. Root cause מאומת בקוד: `app.py:2632`'s `_CONFIRM_WORDS` בדק Tier-1 (`find_live_contracts()`) תמיד ראשון וללא-תנאי, לפני שהגיע בכלל לבדיקת Tier-2 (`resolve_pending_lead_preview()`) — הנחת "Tier 1 מנצח תמיד" (`core/lead_candidate_handler.py:1415-1419`, BUG-058 docstring) שכבר נשברה עבור Tier-1-מול-Tier-1 (BUG-115) מעולם לא תוקנה עבור Tier-1-מול-Tier-2; בוקמארק BUG-115 לא מכסה batch כי אין לו ActionContract. תוקן עם פונקציה חדשה `should_prefer_batch_preview()` המשווה recency בין `pending_lead_preview`'s `set_at` (TTL 1800s קיים) ל-`last_prompted_contract`'s `set_at` (TTL 600s קיים) — מי שטרי יותר מנצח; נקראת ב-`app.py` **לפני** ה-gate הבלתי-מותנה של Tier-1. שני מנגנוני ה-TTL הקיימים לא שונו. נדרש הרחבת חלון-תווים בבדיקה המבנית הקיימת (`test_app_py_confirm_word_checks_gateway_before_flag_branch`, 3000→5000/5000→6500) — האינווריאנט עצמו לא השתנה, רק המרחק ממנו לסמן. 11 בדיקות חדשות (`test_bug117_batch_preview_precedence.py`); `test_c89_preview_confirmation.py` (9/9) ו-`test_bug115_confirmation_routing_bookmark.py` (22/22) רצו מחדש ללא רגרסיה. Full regression sweep: 140/140 קבצי `test_*.py`, exit 0. smoke/compileall/diff-check נקיים. מחוץ לסקופ במפורש: `_CANCEL_WORDS`/`route_cancellation_word()` (התנהגות שונה ומורכבת יותר, נושא נפרד).
**Merged:** לא עדיין (branch `claude/action-status-shadow-verification-m1m0ow`) | **Verified בפרודקשן:** לא — התיקון טרם נצפה מול תעבורה חיה

### C142 — BUG-117: אימות production (19/07/2026)
קבצים: `BUG_AUDIT_LOG.md` | באג: BUG-117 | Docs בלבד
דגימת production ישירה: batch dictation ("צור לידים חדשים ענף גיוס... בניימין אסולין... אהרון שמחה") נכנס עם `[TurnEnvelope] case_c_signal kind=C1 detail=live_contracts=9` (9 contracts ישנים pending), `[IngressClassifier] tier=2 ... reason=clean_batch_2_items candidates=2`. תצוגת batch הוצגה נכון ("📋 זיהיתי 2 לידים אפשריים בקבוצה..."), ואחרי "כן" שני הלידים אושרו ונכתבו בפועל: `✅ שמרתי את בניימין אסולין (0533123482) | recoLSXsLQNKQG6Gy`, `✅ שמרתי את אהרון שמחה (0548421060) | recgwDYidGrTc9KEU` — ללא תפריט disambiguation, למרות 9 contracts ישנים pending. **הערת דיוק:** שורת `live_contracts=9` נלכדה ל-turn של ה-batch dictation עצמו, לא ל-turn של "כן" בפני עצמו (אין TurnEnvelope נפרד להודעת "כן" בדגימה) — אך שתי הודעות רצופות באותה שיחה, ותצוגת batch (Tier-2) לא יוצרת/מסירה ActionContracts, כך שאין סיבה טכנית למספר הישן להשתנות ביניהן. סוגר את BUG-117 במלואו.
**Merged:** כן (docs בלבד) | **Verified בפרודקשן:** ✅ כן

### C143 — C84: TMA Approvals TTL + freshness check (19/07/2026)
קבצים: `tma_api.py`, `test_c84_tma_approval_ttl.py` (חדש), `test_approval_concurrency.py`, `test_phase_4b2_wiring.py`, `test_pr0c0_tma_approval_truthfulness.py`, `ROADMAP.md` | ROADMAP: C84
**בעיה (ROADMAP C84, 🟡 גבוה):** רשומת Approvals `PENDING` ב-TMA יכולה להישאר actionable ללא הגבלת זמן — בניגוד לכפתור טלגרם (BUG-112), שאוכף `_PENDING_APPROVAL_TTL=600s` עצמאית מיד לפני dispatch, ל-`tma_api.py`'s `_claim_and_execute_approval()` (הנקודה היחידה ש-`act_on_approval()` וגם `bulk_approve()` עוברות דרכה לביצוע) לא הייתה שום בדיקת freshness.

**תיקון, וסטייה מכוונת מהצעת ה-ROADMAP:** ה-ROADMAP המקורי הציע להוסיף שדה `expires_at` חדש לרשומת Approvals. במקום זאת נעשה שימוש ב-`ActionContract.created_at` הקיים (שדה חובה ב-dataclass, קיים על כל contract אמיתי) — כי `ApprovalsFields`'s docstring מתעד במפורש ש-Approvals הוא "non-authoritative TMA display projection" של ActionContracts, אז ה-contract הקנוני הוא מקור האמת ל"כמה זמן זה באמת קיים", לא שדה חדש שדורש יצירה ידנית ב-Airtable + resync של `schema_cache.json` (כמו ש-`inbound_handler.py`'s F06 דרש בזמנו). זה גם נמנע לגמרי מנגיעה ב-`tools/airtable_gateway.py`.

`_TMA_APPROVAL_TTL_SECONDS = 24 * 60 * 60` (24 שעות) — קבוע חדש, מכוון, שונה בכוונה מ-BUG-112's 600 שניות: כפתור טלגרם הוא push notification שנבדק תוך דקות; שורת Approvals ב-TMA נסקרת א-סינכרונית מדשבורד, אולי פעם ביום — 600 שניות היה מפוקע אותה לפני שהבעלים אפילו פותח את המסך.

**מיקום האכיפה:** בדיקה יחידה בתוך `_claim_and_execute_approval()`, מיד אחרי `contract = _gw.find_contract(contract_id)` ולפני `_gw.approve(...)` — אחרי בדיקות ה-scope/canonical-contract הקיימות, כך שלעולם לא עוקפת בדיקת הרשאה אמיתית. contract שחצה את החלון: (1) נדחה דרך `_gw.reject(contract_id, rejected_by="ttl_expired")`, (2) הדחייה מאומתת (re-fetch + בדיקת `status=="rejected"`, לא מונחת כמובן מאליו — מראה `_reject_stale_telegram_approval()`'s pattern הקיים), (3) Approvals projection מסונכרן (`_sync_approval_projection_status`) כדי ש-TMA UI לא ימשיך להראות "ממתין" שקרי, (4) מוחזר `{"ok": False, "status_code": 410, "error": "approval expired — submit a new request"}`. `bulk_approve()` מקבל את זה בחינם — הוא כבר קורא ל-`_claim_and_execute_approval()` per-item, אז contract שפג תוקפו נופל ל-bucket "failed" הקיים (לא bucket חדש), ופריטים אחרים ב-batch לא מושפעים.

**עדכון test doubles:** `_FakeContract` בשלושה קבצי test קיימים (`test_approval_concurrency.py`, `test_phase_4b2_wiring.py`, `test_pr0c0_tma_approval_truthfulness.py`) לא כלל `created_at` בכלל — הבדיקה החדשה הייתה גורמת ל-`AttributeError` בכל טסט קיים שמגיע עד `_gw.approve()` (למשל Test 3/4 ב-`test_pr0c0_tma_approval_truthfulness.py`). תוקן עם פרמטר `created_at: float | None = None` שברירת המחדל שלו `time.time()` ("עכשיו") — כל בדיקה קיימת ממשיכה לעבור בלי שינוי בהתנהגות, בדיוק כמו הרחבת ה-fixture שכבר נעשתה פעמיים קודם באותה סיבה (BUG-058/BUG-117).

**Fail-closed על created_at חסר/לא תקין (תוקן בסבב review פנימי):** הבדיקה הראשונית עשתה `time.time() - contract.created_at` בלי אימות — `created_at` חסר/`None`/לא-מספרי היה מעלה `TypeError` לא-נתפס במקום דחייה נקייה. **בכוונה ההפך מבדיקת ה-TTL של BUG-112 בטלגרם**, ששם timestamp פגום כ"טרי" ("not treated as stale") — סביר לכפתור push-notification בודד, לא סביר לאישור TMA שיכול גם להתבצע דרך `bulk_approve()`. תוקן: `created_at` שאינו `int`/`float` תקין (לא `bool`, לא `<= 0`) מטופל כ-"לא ניתן לאימות" ⇒ נדחה כמו contract שפג תוקפו (fail closed), לא מתבצע לעולם.

**בדיקות:** `test_c84_tma_approval_ttl.py` (44 checks חדשים) — contract טרי מתבצע כרגיל (baseline), contract שפג תוקפו לעולם לא מגיע ל-`approve()` ומסתיים `rejected`/`410`, גבול מדויק (age כמעט-אבל-לא-מעל TTL עדיין מתבצע — הבדיקה היא `>` קשיח, לא `>=`), סנכרון ה-projection ל-Approvals אחרי דחיית TTL, `bulk_approve()` עם שני contracts (אחד פג, אחד טרי) — הפג נופל ל-failed בלי לגעת בכלל בגורם ה-fresh, ו-6 תרחישי fail-closed על `created_at` פגום (`None`/מחרוזת ריקה/מחרוזת לא-מספרית/שלילי/אפס/`bool`) — כולם נדחים, אף אחד לא מתבצע. Full `test_*.py` sweep + `smoke_tests.py` + `compileall` נקיים.

**לא נוגע:** RP5/F52/EvidenceFinalizer/UnifiedStatusFormatter, סמנטיקת אישורים (approval_policy/authority checks), לוגיקת lifecycle של `ActionGateway.approve()`/`reject()` עצמם (רק נקרא נכון, לא שונה), מסלול הכפתור בטלגרם (BUG-112, נפרד לגמרי), שום שינוי סכמה ב-Airtable.
**Merged:** לא עדיין (branch `claude/c84-tma-approval-ttl`) | **Verified בפרודקשן:** לא — קוד+tests בלבד, טרם deployed

### C144 — C81-FU/C82-FU: ניקוי ROADMAP (docs-only audit) + תיקון CI-silent-pass ב-test_c81_recovery_truth.py (19/07/2026)
קבצים: `ROADMAP.md`, `test_c81_recovery_truth.py` | ROADMAP: C81-FU, C82-FU
**רקע:** שני הסעיפים סומנו 🔴 דחוף ב-ROADMAP.md מאז שנכתבו, אך לא נבדקו מול קוד `main` בפועל בשום עדכון תיעוד קודם — פער בין "מה שהתיעוד אומר" ל-"מה שבאמת קיים", בדיוק סוג הפער ש-AGENTS.md's protokol אימות-אחרי-מיזוג נועד למנוע.

**C81-FU (Recovery: אמת משלוח לפני סימון הושלם) — אומת ✅ פתור.** `tools/approval_actions.py::send_recovery()` (מתועד כ-"C53 FIX-1" בעצמו) כבר מחזיר `ok=False` אלא אם `owner_delivery.delivery_success` אומת, ומעולם לא כותב ל-`recovery_count` (בכוונה — הבדל מפורש מ-`send_followup()`, ש**כן** מעדכן `followup_count` תמיד). גרפ אישר: אין אף קריאה ל-`lead_memory.update(..., recovery_count=...)` בכל הריפו מחוץ ל-`lead_memory.py`/`core/lead_recovery.py` עצמם. `test_c81_recovery_truth.py` (4 בדיקות: `test_owner_draft_delivery_does_not_complete_customer_recovery`, `test_unverified_owner_draft_is_reported_and_does_not_complete_recovery`, `test_telegram_adapter_returns_verified_delivery`, `test_telegram_adapter_rejects_unverified_api_response`) מכסה את זה במדויק.

**ממצא צדדי אמיתי, לא קשור ל-C81 עצמו:** לקובץ ה-test חסר היה בלוק `if __name__ == "__main__":` — `python3 test_c81_recovery_truth.py` (הקונבנציה המתועדת ב-CLAUDE.md להרצת כל test_*.py בריפו הזה, ומה ש-`ci.yml`'s "Run test_*.py scripts" step בפועל מריץ) ייבא את המודול, הגדיר את פונקציות ה-test, ויצא עם `exit 0` **בלי להריץ אף assertion** — אותה משפחת באג בדיוק כמו BUG-049/CI-SILENT-PASS-DOCUMENT-CONVERTER (`test_document_converter.py`, שכבר תוקן פעם אחת). תוקן עם אותו pattern: `if __name__ == "__main__": import pytest; raise SystemExit(pytest.main([__file__, "-q"]))`. אומת: `python3 -m pytest test_c81_recovery_truth.py -v` כבר עבר 4/4 גם לפני התיקון (הקוד עצמו תקין ומאומת) — הפער היה רק בנתיב ההרצה הישיר/CI, לא בנכונות הבדיקות עצמן.

**C82-FU (EMERGENCY_STOP_AUTOMATION: gate מרכזי) — אומת ✅ פתור, מעבר לציפייה המקורית.** `scheduler.py::_automation_guard()` עוטף כיום **כל** רישום `.do(...)` בקובץ ללא יוצא מן הכלל — אומת עם `grep -n "\.do(" scheduler.py | grep -v _automation_guard` שמחזיר 0 שורות (23 jobs רשומים, כולם עטופים). `test_c86_scheduler_emergency_matrix.py::test_emergency_stop_matrix_blocks_every_registered_scheduler_job` מכסה זאת במפורש ורץ תקין (יש לו `__main__`, `python3 test_c86_scheduler_emergency_matrix.py` מריץ 2/2 בפועל).

**לא נוגע:** RP5, F52, C84, שום קוד production מלבד ה-`__main__` block החדש (שאין לו השפעת התנהגות — רק מפעיל assertions שכבר היו נכונות).
**Merged:** לא עדיין (branch `claude/c81-c82-roadmap-docs-cleanup`) | **Verified בפרודקשן:** לא רלוונטי — docs-only audit + תיקון test harness, אין שינוי קוד production

### C145 — RP5: staging-only fault-injection mechanism — עותק-תיעודי בלבד (הקוד לא ממוזג ל-main) (19-20/07/2026)
קבצים בפועל (על branch `claude/rp5-staging-fault-injection-v4akit`, PR #407, **לא** ב-`main`): `core/rp5_fault_injection.py` (חדש), `tools/dispatcher.py`, `app.py`, `feature_flags.py`, `.env.example`, `test_rp5_fault_injection.py`, `test_rp5_marker_stripping.py` | קשור: RP5/F52 (שניהם נשארים shadow-only, לא נוגע ב-taxonomy)
**רקע:** מנגנון צר, **staging-only**, מייצר דגימות RP5/F52 אמיתיות מונעות-בוט דרך שרשרת ה-runtime המלאה (Router → IngressClassifier → Lead handler → ActionGateway → A32 → EvidenceFinalizer → rendering), בלי לשנות התנהגות בפרודקשן. הפעלה מותנית בארבעה שערי בטיחות קשיחים: `APP_ENV=="staging"`, `RP5_FAULT_INJECTION_ENABLED=true`, המשתמש הקנוני ב-`RP5_FAULT_ALLOWLIST`, ומרקר מפורש `[rp5-test:<scenario>]` בהודעה — כישלון כל שער אחד משחזר בדיוק את מסלול הפרודקשן הקיים. שבעה תרחישים נתמכים: `google-401`/`write-403`/`write-validation-400`/`write-timeout`/`tool-empty-response`/`tool-malformed-response`/`connection-reset`.
**נקודת הזרקה יחידה** ב-`tools/dispatcher.py::dispatch_tool()`, אחרי שערי identity/role/action_validator, לפני הפעלת הכלי האמיתי. מצב per-turn ב-`contextvars.ContextVar` (stack, ראו C146). לוג מובנה `[RP5FaultInjection] scenario=... user=... provider=... op=... tool=...`.
**זהו רישום תיעודי בלבד על `main`** — הענף עצמו נשאר סגור/staging-only ולא יתמזג לעולם (החלטה מפורשת). הרישום כאן קיים כדי שהראיה/הקונטקסט לא יאבדו כשהענף יימחק (ראו C146/C147 להמשך, ו-`BUG_AUDIT_LOG.md`'s BUG-118/BUG-119 לממצאי-צד שהתגלו תוך כדי אימות).
**Merged:** לא, ולא יתמזג בכוונה — staging-only | **Verified ב-staging:** ✅ כן, ראו C147

### C146 — RP5: תיקון integration — marker לא הוסר לפני ניתוב/סיווג, nested-turn clobber (19/07/2026)
קבצים: `core/rp5_fault_injection.py`, `app.py`, `test_rp5_marker_stripping.py` (חדש) | קשור: RP5 (staging-only, branch `claude/rp5-staging-fault-injection-v4akit`)
**בעיה (דגימת staging חיה):** לאחר יצירת ActionContract ממתין, "מאשר [rp5-test:write-403]" **לא** זוהה כאישור בכלל — `core/action_gateway.py::is_own_resolution_event()` (נקרא לפני `run_agent()`, ב-ingress-context-gate של `app.py`'s webhook handler) וגם `app.py`'s `_CONFIRM_WORDS` בודקים exact-match מול המחרוזת השלמה, שה-marker הנספח שובר. התוצאה: ה-contract סומן `context_interrupted`, ההודעה נפלה ל-Agent הכללי, ואף `[RP5FaultInjection]`/dispatch_tool לא הופעלו.

**תיקון, שני חלקים ב-`core/rp5_fault_injection.py`:** (1) `begin_turn()` מחזיר כעת את הטקסט אחרי הסרת ה-marker, בנוסף להפעלת ה-fault ממקור הטקסט הגולמי — `app.py`'s `_run_agent_impl` משבץ מחדש את `user_text` לתוצאה, כך שכל צרכן בהמשך אותו turn (אישור, lead capture, בניית payload) רואה טקסט נקי. (2) פונקציה חדשה `clean_text_for_routing()` (stateless, ללא הפעלת turn state) עבור ה-ingress gate ב-Telegram webhook handler, שרץ **לפני** `run_agent()`/`begin_turn()`.

**הגנת-עומק נלווית (nested-turn clobber):** ה-contextvar per-turn הוסב ממשתנה יחיד ל-stack — קריאה מקוננת ל-`run_agent()` (הrretry של Stage-A pending-approval, קיים בקוד) הייתה מוחקת את מצב ה-fault של ה-turn החיצוני ברגע שהפנימית מסתיימת (ערך יחיד משותף), מאפשרת כתיבה אמיתית "בשקט" גם כשה-marker היה תקף. push/pop משחזר את המצב שהיה פעיל לפני הקריאה המקוננת.

**בדיקות:** `test_rp5_marker_stripping.py` (11 חדשות) — marker מוסר בדיוק ל-מילת אישור; טקסט גולמי אינו תואם (מוכיח שהבאג היה קיים); `clean_text_for_routing()` תואם את `begin_turn()`; `is_own_resolution_event()` מזהה את הטקסט הנקי, לא הגולמי; זרימה אמיתית propose→"מאשר [rp5-test:write-403]"→`route_confirmation_word()`→`dispatch_tool()` אמיתי מאשרת את ה-contract אך חוסמת כתיבה אמיתית, עם הוכחה ש-`airtable_add` האמיתי אף פעם לא נקרא; marker לא מגיע ל-`normalized_payload`; production/disabled/לא-ברשימה נשארים byte-identical; stack מקונן מאומת ישירות. `test_rp5_fault_injection.py` (31/31) + כל `test_*.py` הקיימים ללא רגרסיה.

**מוגבל במפורש ל-Telegram** — `_webhook_whatsapp_impl()` עדיין מעביר טקסט גולמי ל-ingress gate; כל תרחיש RP5 עם אישור חייב לרוץ בטלגרם עד הרחבה נפרדת ל-WhatsApp.

**לא נוגע:** RP5/F52 taxonomy, EvidenceFinalizer, UnifiedStatusFormatter, סמנטיקת approve/reject/dispatch של ActionGateway.
**Merged:** לא — staging-only, `claude/rp5-staging-fault-injection-v4akit`, לא ממוזג בכוונה | **Verified בפרודקשן:** לא רלוונטי (staging-only) — ראו C147 לאימות staging

### C147 — RP5: אימות staging (smoke test, 19/07/2026) + BUG-119 side finding (20/07/2026)
קבצים: `BUG_AUDIT_LOG.md` | Docs בלבד | קשור: C146
דגימת staging ישירה (Render, `RP5_FAULT_INJECTION_ENABLED=true`) — שני smoke tests, שניהם PASS:
- **Smoke 1 (עם marker):** "מאשר [rp5-test:write-403]" → `[RP5FaultInjection] scenario=write-403` הופעל **לפני** `airtable_add` → הביצוע נכשל במפורש → **אין** POST אמיתי ל-Tasks → אין הצלחת ביצוע.
- **Smoke 2 (בלי marker):** אישור רגיל → **אין** שורת `[RP5FaultInjection]` → ביצוע רגיל: `Dispatch airtable_add` → `POST Tasks 200` → הביצוע הצליח → `ActionGateway` ביצע → `claim outcome=completed`.

מאמת ב-staging חי, קצה-לקצה, ארבעה היבטים בו-זמנית: הפעלת marker, הסרת-marker/ניתוב-אישור (C146), חסימת כתיבה תחת marker, והתנהגות אינרטית לחלוטין בלי marker (byte-identical למסלול הרגיל).

**ממצא-צד 1 (BUG-118, רשום בנפרד, לא חוסם):** תגובת ההצלחה של המסלול הישן ב-`route_confirmation_word()` עדיין מדליפה tool_name/Airtable record_id גולמיים בטקסט — במעקב תחת F52 soak, **אינו** חוסם ל-PR #407.

**ממצא-צד 2 (BUG-119, רשום בנפרד, לא חוסם, לא תוקן, 20/07/2026):** turn חמישי באותה שיחת בדיקה ("😊", נטול כל tool call) קיבל claim הצלחה שהזכיר במפורש את המשימה ש-write-403 חסם turn קודם באותה שיחה — דריסה פעילה של כישלון מתועד, לא הזיה גנרית. Contract Chain אומת בקוד ישיר: `core/anti_hallucination.py`'s `_AGENT_ACTION_STATUS_PATTERN` (ה-"generic structural safety net" שאמור לתפוס בדיוק את זה) מכסה רק צורת-יחיד לשישה מתוך שבעה פעלי-השלמה, חסרה צורת ריבוי (נוצרו/בוצעו/נשלחו/נשמרו/עודכנו/הושלמו — "שתי המשימות **נוצרו**" נפל בדיוק בפער הזה). **לא קשור ל-RP5/F52 taxonomy** — פער כללי ב-A32, יחול זהה בפרודקשן תחת אותו ניסוח (סיכום עם 2+ פריטים). פרטים מלאים + הצעת תרחיש-רגרסיה (cell2b) ב-`BUG_AUDIT_LOG.md`.

**Merged:** לא (docs בלבד, staging-only) | **Verified ב-staging:** ✅ כן — שני smoke tests, כל ההיבטים הנדרשים | **Verified בפרודקשן:** לא רלוונטי — הענף אינו נוגע ב-production, נשאר פתוח/לא ממוזג בכוונה

### C148 — BUG-110 residual: תיקון read-side stale `status=="converted"` (20/07/2026)
קבצים: `ad_attribution.py`, `audience_intelligence.py` | קשור: BUG-110 (PR #372, merged), ROADMAP

**רקע:** BUG-110 (17/07/2026) תיקן את שני אתרי הכתיבה (`lead_conversion.py`, `ad_attribution.py::mark_converted()`) לכתוב `status=LeadStatus.DONE`+`Business Outcome=LeadOutcome.CONVERTED` במקום הליטרל הלא-קנוני `status="converted"`, אבל השאיר במפורש כחוב טכני שני צרכני-קריאה שהמשיכו לבדוק את הליטרל הישן: `ad_attribution.py::build_attribution_report()` ו-`audience_intelligence.py::_parse_records()`. התוצאה: לידים שהומרו **אחרי** תיקון BUG-110 (status="done", לא "converted") הוחסרו בשקט מדוחות attribution ומסגמנטציית "champion"/היקבצות converted — לא קריסה, תוצאה שגויה שקטה.

**תוקן:** שני הצרכנים בודקים עכשיו `l.get("outcome") == LeadOutcome.CONVERTED` (קבוע קנוני מ-`airtable_schema.py`, לא ליטרל "converted " עם הרווח-זנב המובנה) **בנוסף** ל-`status=="converted"` הישן — OR, לא replace, כי אין backfill לנתונים ישנים. `_load_leads_with_timeframe()` ב-`ad_attribution.py` הורחב לשלוף גם את שדה `Business Outcome` (דרך `LeadFields.OUTCOME`), שלא נשלף קודם בכלל. שני הקבצים מייבאים את `LeadOutcome`/`LeadFields` lazy עם `except ImportError` fallback — עקבי עם הסגנון הקיים בכל שאר הפונקציות בשני הקבצים (`mark_converted`, `record_lead_source`, `_load_leads_with_timeframe`).

**במפורש לא נוגע:** `ad_attribution.py::mark_converted()`'s gateway migration — הסעיף השני שBUG-110 השאיר כחוב טכני נשאר בכוונה לא-ממומש (היה שובר את חוזה ה-`bool` return מול `test_response_contract_fixes.py`, כפי שכבר הוערך ותועד ב-BUG-110 עצמו).

**בדיקות:** אין קובץ test ייעודי לשתי הפונקציות הנוגעות (`build_attribution_report`/`_parse_records`) — לא היה קיים כזה גם לפני התיקון. אומת ידנית עם תרחיש inline (ליד legacy עם `status="converted"` + ליד post-fix עם `status="done"`+`outcome=converted` — שניהם נספרים). `test_bug105_non_canonical_converted_status.py` (10/10) ו-`test_response_contract_fixes.py` (19/19) רצו ללא רגרסיה — מוודאים ש-`mark_converted()`/`lead_conversion.py` עצמם לא נגעו. Full `test_*.py` sweep (כולל 12 קבצים שדרשו התקנת `pytest` בסביבה) + `smoke_tests.py` + `test_integration.py` + `core/router/test_router.py` + `compileall` — כולם נקיים, ללא רגרסיה.

**Merged:** לא עדיין (branch `claude/n15-owner-decision-p73c3k`, commit `e6efa3a`) | **Verified בפרודקשן:** לא רלוונטי עדיין — טרם מוזג ל-`main`.

### C149 — Day-3 flag pre-activation prep: FEATURE_WEEKLY_SUMMARY bug fix + FEATURE_LAST_TOOL_RESULT_SHADOW tests (20/07/2026)
קבצים: `weekly_summary.py`, `core/output_gateway.py`, `test_weekly_summary_domain_grouping.py` (חדש), `test_last_tool_result_shadow.py` (חדש) | קשור: פריטי 10/11 ב"תכנית 3-4 הימים"

**FEATURE_WEEKLY_SUMMARY (פריט 10):** `_group_by_domain()` קיבץ לפי `Tags[0]`, אבל `cmd_update.py::_save_to_business_memory()` לעולם לא כותב domain ל-Tags (ראו cmd_update.py:343-349) — domain נכתב רק לשדה `Domain` הייעודי, כערך Airtable קריא-אנוש ("Real Estate", לא "real_estate"). כל רשומה קובצה בשקט לפי tag אמיתי לא-קשור, או נפלה ל-"general" (Tags ריק). תוקן: קריאה מ-`BusinessMemoryFields.DOMAIN` + נרמול ("Real Estate"→"real_estate") להתאמה למפתחות `_DOMAIN_LABELS`. `test_weekly_summary_domain_grouping.py` חדש (11 בדיקות).

**FEATURE_LAST_TOOL_RESULT_SHADOW (פריט 11):** הוסף קובץ test ייעודי (לא היה קיים) המכסה את המחסן עצמו (bounded, TTL eviction, לעולם לא זורק) ואת שלוש נקודות הקריאה האמיתיות (`tools/dispatcher.py`'s `dispatch_tool()` finally-block, `tma_api.py::_shadow_record_tma()`, `core/output_gateway.py::_shadow_record_send()`) — כבוי כברירת מחדל ⇒ אפס קריאות, וגם אם `record()` עצמו זורק, ה-return value/control flow של הקורא לא מושפעים. `test_last_tool_result_shadow.py` חדש (23 בדיקות) — תפס באג אמיתי (זעיר) תוך כדי כתיבה: `_shadow_record_send()` שיבץ את ה-enum `envelope.channel` ישירות למחרוזת האבחון (`f"{envelope.channel}"` → `"OutputChannel.TWILIO_WHATSAPP"` במקום `"twilio_whatsapp"`, כי `OutputChannel(str, Enum)` לא דורס `__str__`). תוקן עם `.value`. מחרוזת אבחון בלבד, אין השפעת control-flow.

**פריטים 7-9** (`FEATURE_CORE_REASONING_LEADS_STATE`, `GIT_AUDIT_SCHEDULER`, `FEATURE_TOOL_AVAILABILITY_FILTER`) — קוד מוכן מסבבים קודמים; ההפעלה עצמה היא שינוי env var ב-Render, לא שינוי קוד — נשאר להחלטת/ביצוע הבעלים.

**בדיקות:** Full `test_*.py` sweep + `smoke_tests.py` + `test_integration.py` + `core/router/test_router.py` + `compileall` — כולם נקיים.

**Merged:** לא עדיין (branch `claude/n15-owner-decision-p73c3k`, commit `23c1a35`) | **Verified בפרודקשן:** לא רלוונטי עדיין — טרם מוזג.

### C150 — Post-N15 Work Survey: דוח מלא + תיקון 3 פריטי drift ב-ROADMAP (20/07/2026)
קבצים: `docs/audit/POST_N15_WORK_SURVEY_20260720.md` (חדש), `ROADMAP.md` | Docs בלבד, אין שינוי קוד production

**רקע:** לקראת תכנית עבודה למספר ימים נוספים (אחרי סבב N15/BUG-110/Day-3-flags/BUG-120/BUG-121) — "כל דבר שאפשר לחזק/להשלים/לשפר, מחוץ ל-RP5/F52/כל דבר חסום". הופעלו 4 סוכני חקירה מקבילים (Explore, read-only): סקירת ROADMAP.md, סקירת BUG_AUDIT_LOG.md, סקירת feature_flags.py למועמדי הפעלה בטוחים, וסקירת חוב טכני/governance drift כללי. לכל הסוכנים ניתנה הנחיה מפורשת להוציא RP5, F52/`FEATURE_UNIFIED_STATUS_FORMATTER`, `FEATURE_ACTION_GATEWAY`, `FEATURE_PA01_ENFORCEMENT_STATE` (enforce), `FEATURE_DECISION_HUB`, `FEATURE_AUTO_CAPTURE`, `MULTITENANT` מהתוצאות.

**הדוח המלא** (לא מקוצר, כדי שאף פרט לא ילך לאיבוד) נשמר ב-`docs/audit/POST_N15_WORK_SURVEY_20260720.md` — כולל: פריטי ROADMAP פתוחים (C85/C87/C88/C91/C92/N10/U1/F06/F09/F14/F15/BUG-072/ועוד), באגים פתוחים מ-BUG_AUDIT_LOG (מקובצים לפי "דורש merge"/"דורש החלטת owner"/"מתועד בלבד"/"אומת חלקית"), 7 מועמדי flag-activation בטוחים, וחוב טכני/governance drift (כולל P0 אמיתי: `EMERGENCY_STOP_*` flags נשמרים ב-`/tmp` בלבד ומתאפסים בשקט ב-restart), ותכנית מוצעת ל-5 ימים.

**3 פריטי drift שנמצאו ותוקנו ב-ROADMAP.md עצמו** (הקובץ טען דבר-אחד, המציאות אחר — נמצא תוך כדי הצלבה מול עבודה מאומתת מהשבוע):
1. **C84** — סומן "טרם ממוזג ל-main"; בפועל כבר merged (`c5c5a97`, PR #408) — אומת בסבב BUG-110 קודם השבוע (`git merge-base --is-ancestor`).
2. **C86** — סומן "planned, not started"; בפועל `test_c86_scheduler_emergency_matrix.py::test_emergency_stop_matrix_blocks_every_registered_scheduler_job` כבר קיים ועובר — תועד בעדכון C82-FU (19/07/2026) **באותו קובץ עצמו**, סתירה פנימית שלא נתפסה.
3. **טבלת "Known Issues"** — טענה ש-`/status` Telegram decorator הוסר ב-PR #55; בפועל קיים ורשום (`app.py:401`, תואם ל-BUG-005 הסגור). עבדנו על `/status` ישירות השבוע (BUG-120/BUG-121, כולל תיקון באג נוסף בו).

כל שלושת הפריטים סומנו ✅ סגור/מתוקן בגוף ה-ROADMAP במקום התוכן המיושן.

**לא נוגע:** שום קוד production, שום flag, שום PR קיים. זהו סבב תיעוד+חקירה בלבד — התכנית המוצעת בדוח עדיין לא בוצעה.
**Merged:** לא עדיין (branch `claude/n15-owner-decision-p73c3k`) | **Verified בפרודקשן:** לא רלוונטי — docs-only.

### C151 — Truth Reset: אימות ישיר מול origin/main לכל פריט בתכנית העבודה (20/07/2026)
קבצים: `BUG_AUDIT_LOG.md`, `ROADMAP.md` | Docs בלבד, אין שינוי קוד production | קשור: C150 (הדוח המקורי)

**רקע:** לפני תחילת ביצוע התכנית מ-C150, הבעלים דרש שכל פריט בתכנית יאומת ישירות מול `origin/main` (commit, merge status, tests, deploy, production verification) — לא לפי מה ש-BUG_AUDIT_LOG/ROADMAP טוענים. כל פריט נבדק בפועל: `git merge-base --is-ancestor`, grep ישיר על `origin/main`, והרצת הטסט הרלוונטי על העץ הנוכחי.

**ממצא מרכזי: 6 פריטים שתועדו כ"לא ממוזג"/"ממתין" התבררו כ-stale — כבר merged ופעילים ב-`main`:**

1. **BUG-072** — כבר merged (`e1436e9`/`54961f1`), 7/7 tests. תיעוד היה כבר נכון (רק production verification נותרה) — אין שינוי בהערכה.
2. **BUG-058** — `resolve_pending_lead_preview`/`set_pending_lead_preview`/`get_pending_lead_preview`/`clear_pending_lead_preview` קיימים ב-`main`, מחוברים ב-`app.py` **ללא flag gate**. `test_tier2_silent_preview.py` — 9/9. הרשומה תיעדה גם production verification אמיתי מ-10/07/2026 (ראיית לוג `[LCH] resolve_pending_lead_preview(confirm)`), אבל השורה "Merged: ממתין ל-push/PR" באותה רשומה בדיוק סתרה את זה. תוקן.
3. **BUG-071** — `whatsapp_media_adapter.py`/`meta_whatsapp_media_adapter.py` בשורש (הועברו מ-`providers/` ב-commit `76128ba`), מחוברים ב-`_webhook_whatsapp_impl()` (מסומן בהערת קוד `BUG-071 FIX`). `test_whatsapp_media.py` — 6/6. הרשומה טענה "Merged: לא עדיין" בטעות. תוקן.
4. **BUG-BATCH-DISCARD** — `BatchQueueStore`/`_promote_next_batch_item()` קיימים ומחוברים (5 call sites). `test_bug_batch_approval_preserved.py` — 33/33. נכנס ל-`main` ב-`ba579f2` (17/07). הרשומה כללה גם שורת "תוקן ב-commit: (למלא אחרי commit)" placeholder שלא מולא מעולם, ושורת "סטטוס" שהעתיקה תוכן ממנגנון אחר (atomic-claim, לא קשור). תוקן.
5. **BUG-007** — `_preflight_venture(venture_id=None)` וכו' כבר תואמים לשמות ה-URL rule (אין mismatch). אומת עם Flask test client אמיתי — 204 על כל 4 הנתיבים (`/api/approvals/<id>`, `/api/assets/<id>`, `/api/ventures/<id>`, `/api/game/quests/<id>`). הרשומה טענה "Merged: לא — ממתין לאימות ידני". תוקן.
6. **BUG-049** — `test_document_converter.py`'s `if __name__ == "__main__":` guard קיים; `python3 test_document_converter.py` מדפיס "6 passed, 0 skipped" בפועל (לא exit 0 שקט). הרשומה טענה "Merged: לא". תוקן. (BUG-050, אותו PR, עודכן בהתאם.)

**פריטים נוספים שנבדקו ונמצאו מדויקים (ללא שינוי):** C85 (אין test כזה — פתוח באמת), C88 (עדיין fail-open ב-staging — פתוח באמת), F14/F15 (אין קוד כזה — פתוח באמת), BUG-105 (עדיין לא תוקן — פתוח באמת), BUG-118 ("Preview-gap") — הבהרה חשובה: הרוב כבר תוקן (רשימת disambiguation דרך `_describe_contract_for_disambiguation()`, "executed" branch דרך `_describe_contract_for_reconfirmation()`) — **רק** `route_confirmation_word()`'s legacy success reply עדיין דולף `tool_name`/`record_id` גולמיים; זה ה-scope המדויק היחיד שנותר תחת "Preview-gap", לא כל שלוש התצוגות כפי שהדוח המקורי (C150) ניסח בטעות ברוחב-יתר.

**פריטי drift נוספים שנתפסו ותוקנו:** כפילות של טעות ה-`/status` decorator בטבלת "פערים ידועים" השנייה ב-ROADMAP (שורה נפרדת מזו שתוקנה ב-C150). תווית "חסום על C81-FU–C83" ב-**C87** — שלושתם (C81-FU/C82-FU/C83) כבר ✅ סגורים; C87 לא-חסום יותר טכנית, ממתין רק להחלטת owner.

**השפעה על התכנית:** יום 2 המקורי ("merge BUG-071/BATCH-DISCARD/BUG-007/BUG-049") כמעט ריק בפועל — כל הפריטים כבר ב-`main`. מה שנותר הוא production verification, לא merge. התכנית עברה ארגון-מחדש מלא ל-patch-stack לפי workstreams (ולא ימים/רשימת-באגים) — ראה תגובת session.

**Merged:** לא עדיין (branch `claude/n15-owner-decision-p73c3k`) | **Verified בפרודקשן:** לא רלוונטי — docs-only, verification עצמה בוצעה מול `origin/main` ישירות (git+grep+test runs), לא בפרודקשן.

### C152 — BUG-122: Pending approval queue pollution מדכא פעולות חדשות מפורשות (20/07/2026)
קבצים: `app.py`, `test_bug122_pending_queue_ux.py` (חדש) | קשור: BUG-122 (`BUG_AUDIT_LOG.md`), PA-01 (`core/router/risk_router.py::intent_requires_contract_for_success`, נעשה בו שימוש חוזר, לא כפילות)

**רקע:** דווח ע"י המשתמש (מתויג בשיחה כ-"BUG-121", אך `main` כבר החזיק BUG-120/121 בלתי-קשורים באותו רגע — נרשם כ-BUG-122 ב-`BUG_AUDIT_LOG.md` כדי למנוע התנגשות מספור, ראו הערה שם). דגימת staging: 5 `ActionContracts` חיים (`status="pending"`) קיימים לזהות; הבעלים שולח בקשת `create_task` חדשה וחד-משמעית; ה-Router מזהה בביטחון (`confidence=0.95`), אך המשתמש מקבל fallback גנרי ("לא הצלחתי לבצע את הפעולה") במקום פעולה חדשה או שאלת-resolution לתור.

**Contract Chain:** אומת ישירות (לא הונח) ש-`TurnEnvelope` תצפיתי-בלבד, ש-`find_live_by_user()` כבר מסנן נכון לפי `status=="pending"`, ושששער מילות-האישור הדטרמיניסטי לא יירט את ההודעה. המנגנון האמיתי: `sanitize_agent_response()`'s Single-Speaker gate מחליף טקסט חופשי שנראה action/pending-status-shaped ב-`_SINGLE_SPEAKER_FALLBACK` גם כשלא נוסה שום דבר בפועל — מטעה כשה-Router כבר זיהה intent הדורש contract.

**תוקן:** מיד אחרי `sanitize_agent_response()` ב-`run_agent()` — כש-(1) `final_reply==_SINGLE_SPEAKER_FALLBACK`, (2) `tool_calls_made==0`, (3) אין `__approval_queued__` בתור הזה, (4) `intent_requires_contract_for_success(route.intent)` אמת, (5) יש contract חי אחד לפחות — התשובה מוחלפת בהודעת queue-resolution מפורשת (מונה בקשות ממתינות, מכוונת ל-"מאשר"/"בטל" או ניסוח מפורש). לוגינג: `pending_gate_decision=ask_queue_resolution`/`bypass_new_action`, `live_contracts_count`, `stale_contracts_count` (קבוע חדש `_LIVE_CONTRACT_STALE_SECONDS=24h`, תצפיתי בלבד — אין auto-expiry).

**Scope decision מדווחת (לא הוחלטה בשקט):** לא נוספה לוגינג `pending_gate_decision=intercept_confirmation` לכל אחד מהענפים המפוזרים של מילות-אישור/disambiguation הקיימים — risk/effort לא-מוצדק לתיקון הזה; הענף עצמו כן נבדק ואומת שהוא ממשיך לעבוד נכון (test (a)).

**בדיקות:** `test_bug122_pending_queue_ux.py` חדש, 8/8 — (a) מילת-אישור עם contract חי אחד עדיין מגיעה ל-`approve()` (regression lock); (b) `create_task` חדש + 5 contracts חיים + 0 tool calls → הודעת queue-resolution, לא fallback; (c) `find_live_by_user()` לא סופר contracts שאינם pending; (d) ללא contracts חיים, ההתנהגות הקיימת לא משתנה (scope containment). Full `test_*.py` sweep (כל קובץ) + `compileall -q .` — נקיים.

**היקף:** `app.py` בלבד. אין נגיעה ב-RP5/F52 taxonomy, ב-PA-01 flag/state, או בביצוע האישור עצמו.

**Merged:** ✅ `main` דרך PR #420 (commit `46efea0`) | **Verified בפרודקשן:** לא עדיין — ממתין לבדיקת המשתמש בטלגרם/WhatsApp חי.

### C153 — BUG-123: הודעת בקשת-אישור חושפת placeholder שבור ומזהים טכניים גולמיים (20/07/2026)
קבצים: `app.py`, `event_bus.py`, `test_preview_content_fix.py` (עודכן), `test_bug123_approval_rendering_fail_closed.py` (חדש) | קשור: BUG-123 (`BUG_AUDIT_LOG.md`), BUG-118 (נתיב-קוד נפרד, לא נסגר)

**רקע:** באותה תצפית staging של C151 — הודעת בקשת-אישור הוצגה כ-`⏳ בקשת אישור\n➕ הוסף ל-?:\nID: eeefa1d6 | פג תוקף בעוד 10 דקות`. המשתמש הבהיר במפורש: שכפול ה-ID לא היה תקלת מערכת (הודבק ידנית פעמיים בשאלה עצמה) — לא לטפל בזה כבאג. הבעיות האמיתיות: placeholder שבור ("הוסף ל-?:"), מזהה טכני גלוי (contract ID), ותוצאה — המשתמש לא יכול להבין מה הוא מאשר.

**שורש:** `app.py::_describe_tool_call()`'s `inputs.get("table", "?")` (ואנלוגי בכלים אחרים) — כשל מידע עסקי הוביל ל-placeholder גולמי במקום כישלון-סגור. נמצאו גם (מעבר לדוגמה המקורית, תחת אותה מדיניות): `record_id` גולמי בענף `airtable_update`, ו-`action_id` גולמי ב-`_legacy_pending_text` — אף אחד מהם לא נדרש בפועל ל-routing (callback_data/display-index כבר עושים זאת).

**תוקן:** `_describe_tool_call()` נכתב מחדש — נכשל-סגור עם `_APPROVAL_DESCRIPTION_FALLBACK` בכל שדה עסקי חסר/ריק; `record_id`/`draft_id` הוסרו מהטקסט הגלוי. `_legacy_pending_text` — הוסר `"ID: {action_id}"`, נשארה שורת פקיעת התוקף. `event_bus.py::_default_label()` נכתב מחדש באותה מדיניות (`_DEFAULT_LABEL_FALLBACK`). מזהים טכניים נשארים רק ב-`callback_data`/לוגים.

**בדיקות:** `test_preview_content_fix.py` עודכן (2 בדיקות ישנות שציפו לחשיפת record_id/draft_id הוחלפו לצפות לאי-חשיפה) — 23/23. `test_bug123_approval_rendering_fail_closed.py` חדש — 20/20 (fail-closed לכל כלי, אי-חשיפת מזהים, אנלוגיה ב-`event_bus`, בדיקת מקור סטטית ל-`_legacy_pending_text`). Full `test_*.py` sweep + `compileall -q .` — נקיים.

**היקף:** רינדור הודעת-אישור בלבד. אין נגיעה ב-RP5/F52, בביצוע האישור עצמו, או ב-BUG-118 (נתיב נפרד, לא נסגר על ידי זה).

**Merged:** ✅ `main` דרך PR #420 (commit `46efea0`) | **Verified בפרודקשן:** לא עדיין — ממתין לבדיקת המשתמש בטלגרם/WhatsApp חי.

### C154 — BUG-124: מילת-הצבעה נפוצה ("זה") הופכת הודעה רגילה לחסימת Tier-4 כוזבת (20/07/2026)
קבצים: `app.py`, `test_bug124_context_pronoun_table_false_positive.py` (חדש) | קשור: BUG-124 (`BUG_AUDIT_LOG.md`)

**רקע:** דגימת staging חיה — "כמה זה 5 כפול 7" (שאלת חשבון רגילה) נחסמה כ-`📄 זה נראה כמו טבלה`, אחרי שנוסה שחזור ישיר של `_TABLE_RE` מול הטקסט הגולמי ולא נמצאה התאמה. חיפוש אחר כל שינוי ל-`user_text` לפני הניתוב איתר את `resolve_context_pronouns()` (C60) — עושה `text.replace("זה", f"הפעולה «{last_tool_result_summary}»")` סאב-סטרינג גולמי, וה-summary (טקסט `_tool_user_message()` אמיתי) מכיל לרוב `" | "` בפורמט הסטנדרטי של הריפו — הצבה כזו מזריקה 2+ pipes להודעה תמימה, ו-`_TABLE_RE` (Tier-4) קורא את זה כטבלה. אושש עצמאית: הודעות בלי "זה" עברו רגיל.

**תוקן (גרסה ראשונית):** `resolve_context_pronouns()` מסנן את תוכן-ההצבה (`|`→`·`, `\t`→רווח, תווי-קופסה יוניקוד מוסרים) דרך `_sanitize_for_free_text()` חדשה, בשתי נקודות-ההצבה המשותפות — חל אוטומטית על **כל 7** מילות `CONTEXT_PRONOUNS`, לא רק "זה" (אומת עם `אותו`/`ההוא`/`הקודם`). `_TABLE_RE` עצמו לא שונה.

**Scope decision (נשאלה מהמשתמש):** תוקנה רק חסימת ה-Tier-4 השגויה; הבעיה הסמנטית העמוקה יותר (ההצבה עדיין קורית במופעים לא-הצבעתיים של המילים האלה, למשל "אני מכיר אותו") נשארת פתוחה בכוונה — המשתמש בחר scope צר.

**המשך (אותו יום, אותו ענף) — לבקשת הבעלים לתחקר היקף/נזק אמיתי:** אומת ש-`core/router/router.py`'s BUG-056 Tier-4 stop-gate חוסם **כל** הודעה מכל משתמש פנימי בכל ערוץ (טלגרם+WhatsApp, שניהם דרך `run_agent()`) ללא תלות ב-intent — כלומר החשיפה היא לכל פקודה עסקית, לא רק שאלות חשבון. יותר חשוב: `core/ingress_classifier._is_tier4()` יש לו 7 מחלקות טריגר עצמאיות; התיקון הראשוני כיסה רק את מחלקת ה-pipe/tab/box-char. אומת בפועל ש-`_AIRTABLE_ID_RE` (מחלקה נפרדת) עדיין נתפס **אחרי** התיקון הראשוני עבור summaries אמיתיים מ-`airtable_add`/`airtable_update`/`tma_write` (3 מתוך 4 הכלים ב-`_MEMORABLE_TOOLS`) — כולם מטביעים record_id גולמי (`recXXXXXXX`) בהודעת ההצלחה. **תוקן עכשיו נכון:** נוספה `_safe_context_quote()` — בודקת את המובאה המסונכרנת מול ה-`_is_tier4()` **האמיתי** לפני ההצבה, ונופלת ל-fallback גנרי ("הפעולה האחרונה שביצעת") רק כשהמובאה הייתה חוסמת כשלעצמה. עמיד מפני טריגרים עתידיים ב-`_is_tier4()`, לא רק הרשימה הידועה היום. שום מידע לא אבד — ה-LLM מקבל record_id/url/tool מלאים בנפרד דרך `_build_tool_context()` (system prompt).

**בדיקות:** `test_bug124_context_pronoun_table_false_positive.py`, 28/28 (18 מקוריות + 10 חדשות: 3 תרחישי record_id אמיתיים מול ה-`_is_tier4()` האמיתי, sanity ש-summary בטוח עדיין מצוטט במלואו, 3 יחידה ל-`_safe_context_quote()`). Full `test_*.py` sweep + `compileall -q .` + `smoke_tests.py` — נקיים.

**היקף:** `app.py::resolve_context_pronouns()`/`_sanitize_for_free_text()`/`_safe_context_quote()` בלבד. אין נגיעה ב-`_is_tier4()`/`_AIRTABLE_ID_RE`/ingress_classifier עצמם.

**Merged:** ✅ `main` דרך PR #422 (commit `5262327`) | **Verified בפרודקשן:** לא עדיין — ממתין לבדיקת המשתמש בטלגרם/WhatsApp חי.

### C155 — N16: ביטול N12 — Git Audit הופרד מהבוט העסקי (21/07/2026)
קבצים: `scheduler.py`, `daily_git_audit.py`, `feature_flags.py`, `.env.example`, `test_c86_scheduler_emergency_matrix.py`, `ROADMAP.md` | קשור: N12 (בוטל, ראה למעלה), PR #108 (`c26c5e1`, המקור)

**רקע:** המשתמש קיבל הודעת טלגרם "🚫 AUDIT ABORTED (GOV-02 STOP)" מהבוט העסקי ותהה למה כלי audit של repo שולח דרך הבוט. חקירה חשפה ש-N12 (PR #108) חיבר את `daily_git_audit.py` (כלי GOV-02) ל-`scheduler.py` **של הבוט העסקי עצמו** — ריצה יומית ב-06:45 (מאחורי דגל `GIT_AUDIT_SCHEDULER`, כבוי כברירת מחדל), עם שליחה ישירה דרך `TELEGRAM_TOKEN`/`ELIYAHU_CHAT_ID` של הבוט. כלומר תהליך ה-Python של הבוט ב-Render קרא Git מהעותק הפרוס אליו ושלח את התוצאה בטלגרם — למרות שקיים כבר Claude Code Routine נפרד ("Road map false positive check") שעושה בדיוק את אותה עבודה (audit קריאת-ריפו + התראה) דרך תשתית אחרת לגמרי. **לא בעיית ניסוח — כפילות ארכיטקטונית אמיתית**, ועדות ישירה שהדגל בכל זאת הודלק/הורץ ידנית בסביבה עם פרטי הטלגרם (אחרת ההודעה לא הייתה מגיעה).

**החלטת בעלים:** git audit הוא אחריות בלעדית של Claude Code Routine (קורא את הריפו, מריץ GOV-02, שולח push/email). הבוט העסקי לא אמור להיות קשור לריפו/Git בשום צורה — ממשיך לשלוח רק digest והתראות עסקיות.

**תוקן:**
1. `scheduler.py` — `_job_daily_git_audit`, `git_audit_time`, ורישום ה-`schedule.every().day.at(...)` שלו **הוסרו לגמרי** (לא הושארו flag-gated — flag-off לבדו כבר לא מנע את ההודעה שהתקבלה בפועל, אז זה לא תיקון מספיק). גם הוסר מ-startup log line.
2. `daily_git_audit.py` — `_send_telegram()` הוסרה כליל, שני call sites (GOV-02 STOP abort + דוח סופי) הוחלפו ב-`print()` בלבד. `import os` הוסר (לא נשאר שימוש). docstring עודכן לתעד במפורש: repo tool בלבד, ריצה/התראה באחריות Routine, אין קשר ל-app.py/scheduler.py/TELEGRAM_TOKEN.
3. `feature_flags.py` — דגל `GIT_AUDIT_SCHEDULER` הוסר מהרישום (0 call sites נותרו). `.env.example` — `GIT_AUDIT_TIME` הוסר.
4. `test_c86_scheduler_emergency_matrix.py`'s `SCHEDULER_JOB_NAMES` עודכן (הוסר `_job_daily_git_audit`).
5. `ROADMAP.md` — N12 סומן בוטל עם הפניה לעדכון, N16 (חדש) מתעד את התיקון, changelog בראש הקובץ עודכן.

**לא נגע (במפורש):** `audit_truth_gate.py` (GOV-02) — נשאר read-only tool בריפו בדיוק כפי שהיה, זמין ל-Routine להריץ ישירות. שום Routine קונפיגורציה (Claude Code Remote) לא שונה — זו תשתית מחוץ לריפו.

**בדיקות:** Full `test_*.py` sweep + `smoke_tests.py` + `compileall -q .`. `python -c "import daily_git_audit"` ו-`python3 daily_git_audit.py` (ללא `TELEGRAM_TOKEN`) — מדפיס דוח, לא נכשל.

**היקף:** תיקון ארכיטקטוני — הסרת חיבור, לא פיצ'ר חדש. אין שינוי ל-GOV-02 עצמו, לשאר משימות ה-scheduler, או ל-Routine.

**Merged:** ✅ `main` דרך PR #424 (commit `99981fb`). **Verified בפרודקשן:** לא עדיין — אין דרך פעילה לבדוק "ההודעה הבאה לא תגיע" מלבד המתנה; אין שגיאת GOV-02 חדשה שדווחה מאז.

### C156 — PATCH 3B Steps 2–4: Airtable adapter + feature_flags hook + preflight/predeploy — ✅ Production Verified (21/07/2026)
קבצים: `adapters/airtable_emergency_stop_store.py`, `core/emergency_stop.py`, `core/emergency_stop_preflight.py`, `core/predeploy.py`, `feature_flags.py`, `tools/airtable_gateway.py`, `airtable_schema.py`, + 7 קבצי test | קשור: PATCH 3B Step 1 (PR #421), Emergency Stop persistence (Truth Reset P0 finding, C150)

**מה נמזג:** PR #425 (`claude/n15-owner-decision-p73c3k` → `main`, commit `3ce949e`) — Steps 2 (adapter), 2.5 (contract hardening), 3 (feature_flags configure hook, ללא wiring), 4 (preflight read-only CLI + predeploy wrapper, טרם Render Pre-Deploy Command). כל השלבים תועדו בפירוט בהודעות ה-commit של הענף עצמו; ראה גם ROADMAP.md's PATCH 3B section.

**אימות production אמיתי (21/07/2026, לא רק tests):** הבעלים יצר את הטבלה `Emergency Stop Flags` ב-Airtable (`app4bcgoX7t0HUVnm`, `tblBba3rkkFcj4uuv`) עם 7 השדות הנדרשים בטיפוסים הנכונים; חמש הרשומות (`EMERGENCY_STOP_ALL`/`WHATSAPP`/`EMAIL`/`AUTOMATION`/`AI`, כולן `Enabled=false`) נזרעו — ישירות דרך Airtable MCP, בהיעדר גישת httpx ישירה לבסיס הפרודקשן מסביבת הפיתוח, ואומתו בחזרה (`list_records_for_table`: 5 רשומות, שמות ייחודיים, ללא "Enabled" key — תואם למוסכמת ה-checkbox-omission ש-`_parse_records()` מטפלת בה). לאחר מכן הבעלים הריץ בעצמו, ישירות על שירות ה-Render החי (commit `3ce949e`, אותו commit שמוזג ל-`main`):
```
$ python -m core.emergency_stop_preflight
... GET https://api.airtable.com/v0/meta/bases/app4bcgoX7t0HUVnm/tables "HTTP/1.1 200 OK"
... GET .../Emergency%20Stop%20Flags?filterByFormula=TRUE%28%29&maxRecords=100 "HTTP/1.1 200 OK"
[emergency_stop_preflight] ok — schema valid, all 5 canonical flags present
preflight_exit=0

$ python -m core.predeploy
[core.database_migrations] Migration succeeded: 001_action_execution_claims.sql
[predeploy] database migrations: OK
... (same two live Airtable calls as above) ...
[emergency_stop_preflight] ok — schema valid, all 5 canonical flags present
[predeploy] emergency stop preflight: OK
[predeploy] all predeploy checks passed
predeploy_exit=0
```
שני הריצות היו כנגד `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` אמיתיים של Render — לא mock. `python -m core.predeploy` גם אימת בפועל שהוא לא שינה את סמנטיקת `python -m core.database_migrations` (המיגרציה הקיימת `001_action_execution_claims.sql` רצה והצליחה בדיוק כפי שהייתה מריצה עצמאית).

**המשמעות:** שלושת התנאים שהוגדרו מראש להחלפת Render Pre-Deploy Command (`python -m core.database_migrations` → `python -m core.predeploy`) מולאו: (1) הטבלה נוצרה, (2) חמש הרשומות נזרעו לפי מצב production תצפיתי (אין אף EMERGENCY_STOP_* env var פעיל ב-Render), (3) הרצה ידנית מוצלחת אומתה — כולל דרך אותו commit שרץ בפרודקשן, לא רק מקומית. **ה-Pre-Deploy Command עצמו טרם הוחלף** (זו פעולת Render dashboard בלעדית, מחוץ לריפו) — זו החלטת הבעלים הבאה, לא נעשתה כאן.

**עדיין inert:** כל הקוד הזה עדיין לא מחובר ל-`app.py`/`scheduler.py`/`tma_api.py`/`cost_monitor.py` — `configure_emergency_stop_manager()` עדיין ללא production caller. אימות ה-preflight/predeploy הוא production-verified במובן ש**הקוד עצמו** רץ בהצלחה מול Airtable חי — לא ש-EMERGENCY_STOP_* flags כבר נשלטים בפועל דרך הבסיס הזה (זה Step 5, טרם בוצע).

**Merged:** ✅ `main` דרך PR #425 (commit `3ce949e`). **Verified בפרודקשן:** ✅ — preflight + predeploy הורצו בהצלחה על שירות Render החי, כולל קריאות Airtable אמיתיות (200 OK), exit 0 לשניהם.

### C157 — BUG-125: `_MUTATION_SUCCESS` מסווג ✅ בודד כתביעת-הצלחה, גם ללא evidence (21/07/2026)
קבצים: `core/turn_evidence.py`, `test_turn_evidence_shadow.py` (עודכן), `test_a32_approval_prose_suppression.py` (עודכן) | קשור: BUG-125 (`BUG_AUDIT_LOG.md`), BUG-119 (אותה משפחה — תביעת-הצלחה כוזבת — שורש שונה)

**רקע:** RP5 shadow test matrix, תא 1.3 — "5 כפול 5"→"25 ✅"/"4 ועוד 4"→"8 ✅", verdict צפוי `match (OK)`. בפועל: `evidence_status=no_evidence response_claim=success mismatch=true`. שורש: `_MUTATION_SUCCESS` כלל `✅` כאלטרנטיבה עצמאית ללא תלות בפועל-השלמה — כל תשובה עובדתית עם ✅ דקורטיבי מסווגת "success".

**תוקן:** הוסר `✅` הבודד מהרשימה; success דורש כעת פועל/ביטוי-השלמה אמיתי. תוך כדי בדיקת רגרסיה נגד `test_generic_success_fallback_without_evidence_is_shadow_mismatch` הקיים התגלה פגם עצמאי נוסף: פעלים המסתיימים באות סופית (ם/ן) לא תואמים כ-substring את הטיית הנקבה/רבים שלהם (`"הושלם" not in "הושלמה"`, אומת ישירות) — נוספו הצורות המפורשות (`הושלמה`/`הושלמו`/`עודכנה`/`עודכנו`) + משפחת מחיקה חדשה (`מחקתי`/`נמחק`/`נמחקה`/`נמחקו`). פעלים שמסתיימים באות לא-סופית (`נוצר`/`נשלח`/`נשמר`) כבר מכסים הטיות כ-substring, לא שונו.

**בדיקה קיימת עודכנה:** `test_a32_approval_prose_suppression.py`'s Test 4 ציפה ש-`PROD_TEXT` הלא-מדוכא ("✅ המשימה מוכנה להוספה...") יסווג "success"; אחרי התיקון מתקבל "neutral" (נכון יותר — הזמנה-לאשר, לא תביעת-השלמה). `mismatch=True` עדיין מתקיים (neutral לא תואם approval_pending) — הצורך בדיכוי A32 עדיין אמיתי, רק reason שונה. Assertions עודכנו בגלוי, לא הוסתרו.

**בדיקות:** `test_turn_evidence_shadow.py` — 13 חדשות (26/26): ✅ בודד→neutral, ✅+פועל→success, צורות נקבה/רבים/מחיקה→success. `test_a32_approval_prose_suppression.py` — 28/28 (עודכן). Full `test_*.py` sweep + `compileall -q .` + `smoke_tests.py` — נקיים.

**היקף:** `core/turn_evidence.py::_MUTATION_SUCCESS`/`_classify_response_claim()` בלבד. אין שינוי ב-F52 rendering, בהתנהגות approval/runtime, או הפעלת אכיפה (`FEATURE_EVIDENCE_FINALIZER` נשאר `off`). `_FAILURE`/`_PENDING`/`_UNKNOWN` לא נבדקו — מחוץ לסקופ, לא הונח שהם תקינים.

**Merged:** ✅ `main` דרך PR #428 (commit `0047804`) | **Verified בפרודקשן:** לא עדיין. הרצה חוזרת של RP5 matrix תא 1.3 נדרשת לאימות (`no_evidence`/`neutral`/`mismatch=false`).

### C158 — BUG-127A: Ingress Context Gate — primary+fallback נכשלים יחד על RAM cache תקוע (21/07/2026)
קבצים: `core/action_gateway.py`, `test_bug127a_stale_lifecycle_version_retry.py` (חדש) | קשור: BUG-127A (`BUG_AUDIT_LOG.md`), רשום גם BUG-127B/BUG-127C (docs-only, לא תוקנו כאן)

**רקע (safety-critical, סומן `[CRITICAL]` בלוג המקורי):** כל הודעה נכנסת קוראת ל-`ExecutionLedger.mark_context_interrupted()`, ובכשל ל-fallback `mark_context_integrity_unknown()`. שניהם נכשלו יחד, פעמיים ברצף, על אותם 4 contracts חיים: `ActionContractTransitionConflictError: stale lifecycle state: expected=pending/v1 actual=pending/v2` — ואז `[CRITICAL] ... fallback ALSO failed ... pending contracts may be silently stale-approvable`.

**שורש (אומת בקוד):** `ExecutionLedger.update_status()` קורא `expected_version` מה-RAM cache **לפני** הקריאה ל-`repository.transition()`, ש-**כן** שולף מחדש מ-Airtable אך בכשל רק `raise`ת — לא מחזירה את ה-truth העדכני לקורא. `update_status()` מרענן את ה-cache **רק בהצלחה** — כך שסטייה חד-פעמית בין RAM ל-durable נשארת **לצמיתות**, וכל קריאה עתידית לאותו contract נכשלת זהה. שני מנגנוני הבטיחות (primary+fallback) קוראים מ-**אותו** RAM cache תקוע — לכן נכשלים יחד, לא כ-fallback אמיתי לסוג-הכשל הזה.

**תוקן:** `_refresh_stale_contract_cache()` חדש — בכשל `ActionContractTransitionConflictError`, שולף truth עדכני (`repository.get()`), מעדכן את ה-RAM cache, ומנסה **פעם אחת** מחדש עם ה-version המתוקן. `expected_status`/`require_status` (דרישת הקורא האמיתית) **לא** משתנים — סטייה אמיתית של status עדיין נכשלת/מחזירה False כראוי (fail-closed נשמר).

**בדיקות:** `test_bug127a_stale_lifecycle_version_retry.py` (10/10) — self-healing על סטיית-version טהורה, fail-closed נשמר על סטיית-status אמיתית, ה-fallback מקבל את אותו תיקון, ריענון-שנכשל לא לולאה אינסופית, ledger ללא repository לא מושפע. `test_action_gateway.py` (43/43), `test_pr0c_action_contract_repository.py` (14/14), `test_pr0_ingress_context_gate.py` (33/33) — ללא רגרסיה. Full `test_*.py` sweep + `compileall -q .` + `smoke_tests.py` — נקיים.

**היקף:** `core/action_gateway.py::ExecutionLedger.update_status()` בלבד. אין נגיעה ב-`action_contract_repository.py::transition()` עצמו, ב-CAS semantics של `require_status`, או בלוגיקת approve()/reject()/execute() מעבר לתועלת המשותפת. BUG-127B/BUG-127C (נרשמו יחד, לא תוקנו כאן) נשארים פתוחים במפורש.

**Merged:** לא עדיין (branch `claude/bug127-ingress-gate-stale-version-and-tool-relevance`) | **Verified בפרודקשן:** לא רלוונטי עדיין — טרם מוזג/נבדק ב-staging.

### C159 — PATCH 3B Step 5 + Step 5.1: `app.py` bootstrap/injection, explicit runtime startup, single-worker pin (21/07/2026)
קבצים: `core/emergency_stop_bootstrap.py` (חדש), `app.py`, `gunicorn.conf.py` (חדש), `health_monitor.py`, `test_emergency_stop_bootstrap.py` (חדש), `test_app_startup_sequence.py` (חדש), `test_health_monitor_emergency_stop.py` (חדש) | קשור: PATCH 3B Steps 2–4 (C156)

**מה נמזג:** PR #427 (`claude/n15-owner-decision-p73c3k` → `main`, commit `7765a46`). `bootstrap_emergency_stop()` — הפונקציה היחידה שבונה `AirtableEmergencyStopStore`+`EmergencyStopManager`, מזריקה דרך `configure_emergency_stop_manager()`, ומבצעת hydration סינכרוני אחד לפני שהאפליקציה מסומנת מוכנה. עדיין **dual-path** בסיום השלב — אין production caller ל-`evaluate_emergency_stop()`/`set_emergency_stop()`, `is_enabled()`/`set_flag()` ממשיכים כרגיל.

**שלושת ה-blockers שהבעלים דחה בסבב הראשון (PR #427 גרסה ראשונה) ותוקנו לפני מיזוג:**
1. **טענת "אין I/O בזמן import" הייתה שגויה בפועל** — `import app` ביצע קריאת Airtable אמיתית, כי ה-bootstrap ישב ברמת המודול. תוקן: `app.run_startup_sequence()` חדש מכיל את שני הדברים היחידים שמבצעים I/O/thread (bootstrap, אז `start_scheduler()`); כל שאר `app.py` (routes, handlers) נשאר ברמת מודול טהורה. `gunicorn.conf.py` (חדש, נטען אוטומטית ע"י gunicorn ללא `-c`) קורא ל-`run_startup_sequence()` מ-`post_worker_init` — ה-hook המתועד של gunicorn ל"אחרי שה-worker קם, לא side-effect של import". אומת עם subprocess שחוסם `httpx.get/post/patch/delete` גלובלית לפני `import app` — עובר נקי, אפס קריאות.
2. **סדר ה-startup לא היה מובטח מבנית** — bootstrap ו-scheduler-start היו שני בלוקים נפרדים ברמת מודול, עם bootstrap דווקא **אחרי** scheduler. תוקן: `run_startup_sequence()` יחיד עם סדר קריאה פנימי טעון-משמעות (bootstrap קודם, ללא-תנאי, ואז scheduler) — אומת עם רשימת `call_order` אמיתית בטסט ועם timestamps אמיתיים מריצת `gunicorn app:app` חיה.
3. **הכלת exceptions רחבה מדי** — היה גם `try/except` פנימי סביב `configure_emergency_stop_manager()`, גם catch-all חיצוני בסוף `bootstrap_emergency_stop()`, גם `try/except` נוסף ב-`app.py` סביב כל הקריאה — כך שגם באג אמיתי הפך בשקט ל-"configured=False" מתועד, ולא חסם את ה-scheduler. תוקן: הוסרו כל שלושת ה-catch-all-ים; רק שני תוצאות **מתועדות** (`store_status="unavailable"`/`"invalid"`, שכבר מטופלות פנימית ע"י ה-adapter/manager) לא זורקות — כל שגיאה בלתי-צפויה (bug בקונסטרוקטור, `configure_emergency_stop_manager()` עצמה זורקת) מתפשטת דרך `bootstrap_emergency_stop()` ← `run_startup_sequence()` ללא-נתפסת, וחוסמת את ה-scheduler.

**Step 5.1 (P0, אותו PR, follow-up commit `67d79d5` לפני המיזוג הסופי):**
1. **סיכון scheduler כפול תחת מספר workers** — `post_worker_init` רץ פעם אחת **לכל worker**, אבל בדיקת "האם thread בשם scheduler כבר רץ" ב-`run_startup_sequence()` היא process-local בלבד — יותר מ-worker אחד היה מריץ scheduler עצמאי משלו, N שכפולים של כל job מתוזמן. תוקן: `gunicorn.conf.py` ננעל ל-`workers = 1` עם הערה מפורשת שאוסרת העלאה עד שיהיה distributed scheduler/leader lock. **אומת אמפירית, לא רק נכתב בקוד:** מכיוון ש-gunicorn's ברירת המחדל שלו עצמו היא גם 1 worker, "ראיתי worker אחד" לא היה מוכיח שה-config נקרא בפועל — הוגדר זמנית `workers = 3`, gunicorn אמיתי עלה עם 3 workers בדיוק, ואז revert + `git diff` נקי.
2. **`store_status` בלתי-צפוי טופל בסלחנות מדי** — ענף `else` ישן ב-`bootstrap_emergency_stop()` היה רושם ללוג ערך לא-צפוי וממשיך כרגיל לעבר ה-scheduler. תוקן: `_require_valid_store_status()` חדש זורק `RuntimeError` על כל ערך מחוץ ל-`{"ok","unavailable","invalid"}` (כולל `None`), גם בענף idempotent-skip; `configured=True` בלי `manager_status` תקין נחשב גם הוא הפרת-חוזה שזורקת.

**בדיקות:** `test_emergency_stop_bootstrap.py` (38), `test_app_startup_sequence.py` (24, כולל proof מבני על `gunicorn.conf.py`'s `workers==1`), `test_health_monitor_emergency_stop.py` (12) — כולם ירוקים. Full sweep + smoke + compileall נקיים.

**Merged:** ✅ `main` דרך PR #427 (commit `7765a46`) | **Verified בפרודקשן:** ✅ — ראה C161 (Step 6) לאימות המשולב של כל ה-stack כולל bootstrap ordering בלוגים חיים.

### C160 — PATCH 3B Step 6 prerequisite: הסרת Airtable production credentials מ-unit CI (21/07/2026)
קבצים: `.github/workflows/ci.yml`, `test_ci_no_airtable_secrets.py` (חדש) | קשור: C159 (Step 5), נמצא תוך כדי אימות Step 5

**הרקע — לא תיאורטי, נתפס בפועל:** תוך כדי אימות production של Step 5, `backend-ci` נכשל על 3 assertions ב-`test_emergency_stop_bootstrap.py`. שורש: assertions שבודקות `evaluate_emergency_stop()`/`get_emergency_stop_status()` רצו **מחוץ** ל-`with patch(at_list_by_formula)` שלהן — וכיוון ש-`EmergencyStopManager` מנסה refresh אמיתי בכל קריאה כשה-cache מעולם לא hydrated בהצלחה (by design, כדי להתאושש מ-outage), הקריאות הבלתי-ממוסקות פגעו ב-`at_list_by_formula` **האמיתית**. מקומית זה "עבד במקרה" (מפתח מזויף → קריאה אמיתית נכשלת → נראה כמו "unavailable", תואם לציפייה) — אבל ב-CI, עם `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` **אמיתיים**, הקריאה הבלתי-ממוסקת הצליחה בפועל מול טבלת `Emergency Stop Flags` **החיה בפרודקשן** (קריאה בלבד, `at_list_by_formula` היא list/search — לא כתיבה), ודרסה בשקט את המצב המדומה.

**תוקן (שני שכבות):** (1) תיקון הבאג הספציפי — כל ה-assertions הועברו לתוך ה-`with patch(...)` הרלוונטי, בשלושה מקומות ב-`test_emergency_stop_bootstrap.py` וב-`test_app_startup_sequence.py`. (2) **הגנת עומק** — גם אחרי תיקון הבאג הספציפי, unit CI לא אמור להחזיק credentials אמיתיים בכלל: `ci.yml`'s `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` הוחלפו בערכי placeholder קבועים (`"fake-ci-key-not-real"`/`"appFAKE00000000000"`, לא `secrets.*`), ונוסף שלב שחוסם גישה ל-`api.airtable.com` דרך `/etc/hosts` **לפני** כל שלב שמריץ קוד טסט — כל באג test-isolation עתידי ייכשל מהר וברעש במקום לגעת בפרודקשן בשקט. אם אי-פעם יידרש טסט אינטגרציה חי מול Airtable, מקומו ב-job נפרד עם secret נפרד מול בסיס CI-only — לא ה-job הזה, לעולם לא production (`conftest.py` כבר מגדיר markers `airtable`/`live`/`integration` שמוחרגים מ-CI כל הזמן).

**בדיקות:** `test_ci_no_airtable_secrets.py` (חדש, 8/8) — מוכיח structurally שאין `secrets.AIRTABLE_*`, שה-placeholder-ים קיימים, ושהחסימה קודמת לשלבי הטסטים. Full sweep (160 קבצים) + smoke + router + compileall נקיים.

**Merged:** ✅ `main` (PR #432) | **Verified בפרודקשן:** לא רלוונטי — שינוי CI-only, אין נגיעה ב-runtime.

### C161 — PATCH 3B Step 6: atomic cutover — `is_enabled()`/`set_flag()` + `tma_api.py` stop/clear + `cost_monitor.py` (21/07/2026)
קבצים: `feature_flags.py`, `core/emergency_stop.py`, `adapters/airtable_emergency_stop_store.py`, `core/emergency_stop_bootstrap.py`, `cost_monitor.py`, `tma_api.py`, `emergency_stop_test_support.py` (חדש), `test_feature_flags_cutover.py` (חדש) + 8 קבצי test קיימים עודכנו | קשור: C159 (Step 5), C160 (prerequisite)

**מה נמזג:** PR #433 (`main`, commit `e6922e2`). זהו ה-cutover האטומי שהושלם ל-PATCH 3B — 5 הדגלים הקנוניים עוברים מהמנגנון הישן (in-process/`/tmp`) לדביק במלואו (Airtable, קריאה **וכתיבה**).

**`feature_flags.py`:** `is_enabled()` עבור 5 השמות מפנה ל-`evaluate_emergency_stop().blocked`; `EmergencyStopNotConfigured` נתפס ומתורגם ל-`True` (fail-closed, לא נופל בחזרה ל-`_RUNTIME`/env — היה יוצר שני מקורות-אמת). `set_flag()` עבור אותם 5 שמות זורק `EmergencyStopLegacyWriteBlocked` חדש במקום לכתוב ל-`_RUNTIME`. מנגנון `/tmp/emergency_flags.json` (`_PERSISTENT_FLAG_NAMES`/`_PERSIST_PATH`/`_load_persistent`/`_save_persistent`) **הוסר לחלוטין** — היה קיים אך ורק עבור 5 השמות האלה. `_env_force_stop_provider()` חדש — קורא `os.environ` ישירות (לא `is_enabled()`, שהיה יוצר מעגליות אחרי ה-cutover); רק המחרוזת המדויקת `"true"` כופה עצירה, `false`/חסר לעולם לא מבטלים עצירה durable; מוזרק ל-`EmergencyStopManager` ב-`core/emergency_stop_bootstrap.py`. `set_emergency_stop()`/`clear_emergency_stop()` מקבלים עכשיו `source` מפורש (במקום מחרוזת קבועה בקוד).

**`core/emergency_stop.py` + adapter:** `FlagRecord(enabled, operation_id)` חדש מחליף `bool` פשוט ב-`ReadResult.flags`/cache המנג'ר. `FlagEvaluation` מקבל `operation_id` — מאפשר לצרכן לגלות אותו דרך מסלול הקריאה בלבד (`GET /api/health`), בלי lookup בצד.

**`tma_api.py`:** `GET /api/health` — `emergency_flags` נקרא עכשיו דרך `get_emergency_stop_status()` (מנג'ר בלבד, אין קריאת Airtable ישירה כאן), כל 5 הדגלים (לא רק 4 — AI היה חסר) כ-`{enabled, operation_id}`. `POST /api/health/emergency` (stop) — `set_emergency_stop()`, `source="tma_owner_stop"`, `operation_id` נוצר server-side ומוחזר, הצלחה מותנית ב-`ok+verified` בלבד. `POST /api/health/emergency/clear` (חדש) — `clear_emergency_stop()`, `source="tma_owner_clear"`, `expected_operation_id` חובה (400 חסר), 409 על stale, הצלחה רק ב-`ok+verified`, תשובה כוללת `still_blocked_by_env`.

**`cost_monitor.py`:** `_trigger_daily_stop()` עבר ל-`set_emergency_stop(source="cost_watchdog")`; כתיבה שלא `ok+verified` מחזירה `_daily_stopped=False` (retry ב-`check_thresholds()` הבא) ולא מדווחת לבעלים "AI נעצר" על כתיבה שלא נדבקה בפועל.

**Callers:** 6 קריאי-קריאה (`tools/dispatcher.py`, `core/output_gateway.py`, `scheduler.py` פי-3, `followup_engine.py`, `health_monitor.py`) נשארו **ללא שינוי טקסטואלי** — `is_enabled()` עצמו הוא נקודת ההפניה. סריקה מבנית חדשה (AST, לא grep) מוכיחה שאף `set_flag()` קריאה בקוד production — literal או dynamic — לא כותבת שם emergency; זהו בדיוק דפוס הבאג שהיה ב-`tma_api.py`'s `f"EMERGENCY_{action.upper()}"` הישן.

**בדיקות:** `test_feature_flags_cutover.py` (חדש, 60) — סריקה מבנית, `_env_force_stop_provider()` ייעודי, durable-survives-restart, set→status→clear round-trip כולל conflict, dispatcher/scheduler integration דרך המנג'ר האמיתי, cost_monitor retry, ו-Flask test client אמיתי ל-`tma_api.py` (400/409/`ok+verified`/`clear_ai` end-to-end). 15 קבצי test קיימים תוקנו לברירת-מחדל ה-fail-closed החדשה (`is_enabled()` בלי מנג'ר מוגדר → `True`, שבר טסטים שלא ציפו לזה — `emergency_stop_test_support.py` חדש, לא `test_*.py` כדי ש-CI לא ינסה להריץ אותו כטסט עצמאי). Full sweep (161 קבצים) + smoke + router + compileall נקיים.

**✅ Production Verified ע"י הבעלים ישירות (21/07/2026, לא רק tests):** `Render HEAD = e6922e2`, `COST_WATCHDOG_LIVE=false`, `/health` מחזיר `status=ok`, `python -m core.predeploy` עבר (migration 001 + preflight, שני קריאות Airtable אמיתיות 200), `WEB_CONCURRENCY=1`. לוג bootstrap אישר: `bootstrap hydration OK — source=durable, 5 flags loaded` → `configured=True store_status=ok flags_loaded=5` → `Scheduler thread started` → `Scheduler OK` (הוכחה ישירה שה-scheduler לא מתחיל לפני שמצב החירום ידוע). `stop_email` דרך ה-TMA → HTTP 200 → **נשאר פעיל אחרי restart אמיתי של Render** (ההוכחה שה-durable persistence עובד — לא restart מוחק, בניגוד למנגנון הישן) → `clear` עם `operation_id` הנוכחי → רשומת Airtable: `Enabled=false`, `Operation ID` חדש, `Source=render_shell_smoke_clear` → TMA חזר ל"כל המערכות תקינות". שני בדיקות השלמה (409 עם operation_id שגוי, STOP ALL חוסם פעולה guarded) לא בוצעו עדיין ע"י הבעלים בפרודקשן — **לא נחשבות ממצא שמטיל ספק** במה שכבר אומת, ראה גם C162 לאימות ה-409 בפועל (frontend+backend מקומי, לא production, אך אותו קוד).

**Merged:** ✅ `main` (PR #433, commit `e6922e2`) | **Verified בפרודקשן:** ✅ — stop, durable persistence, restart survival, clear, ו-bootstrap ordering כולם אומתו ישירות מול Render החי.

### C162 — TMA frontend: Emergency Stop UI ל-Step 6 (Stop AI, Clear buttons, 409 handling) (21/07/2026)
קבצים: `tma-frontend/src/types.ts`, `tma-frontend/src/api.ts`, `tma-frontend/src/components/SystemHealth.tsx`, `tma-frontend/src/components/BossDigest.tsx` | קשור: C161 (Step 6 backend)

**רקע:** בעקבות אימות הפרודקשן של Step 6 (C161), הבעלים ביקש תיקון frontend-בלבד — לא לפתוח מחדש את ה-backend. ה-frontend הישן הציג טקסט שגוי ("לביטול: הפעל מחדש את השרת ב-Render") שאימות ה-production של C161 הפריך ישירות (הדגל **נשאר** פעיל אחרי restart אמיתי), וחסר לו UI ל-`clear`/`stop_ai` שה-backend כבר תומך בהם מ-Step 6.

**תוקן:** `types.ts`'s `emergency_flags` עבר מ-`Record<string, boolean>` ל-`Record<string, {enabled, operation_id}>`, תואם ל-`GET /api/health` החדש. `api.ts` — `emergencyClear()` חדש, זורק `EmergencyClearConflictError` ייעודי על HTTP 409. `SystemHealth.tsx` — כפתור "עצור AI" נוסף לרשימת ה-stop; כל דגל פעיל מציג כפתור Clear משלו (אותו דפוס confirm-לפני-ביצוע כמו Stop) שקורא את ה-`operation_id` ישירות מ-payload הבריאות שכבר נשלף ושולח אותו כ-`expected_operation_id`; 409 מרענן את מצב הבריאות ומציג "המצב השתנה מאז טעינת המסך. רענן ונסה שוב." במקום שגיאה גולמית; הטקסט השגוי על restart **הוסר**. `BossDigest.tsx` עודכן לאותו שינוי טיפוס (`flagState.enabled` במקום ערך בוליאני גולמי). אין קריאה ישירה ל-Airtable מה-frontend — כל פעולה עדיין דרך `tma_api.py` בלבד.

**אומת בדפדפן אמיתי (Chromium דרך Playwright), לא רק build:** backend Flask מקומי חד-פעמי (blueprint `tma_api` בלבד, auth + `EmergencyStopManager` מזויפים, אפס קריאת רשת אמיתית) + Vite entry מינימלי שמרכיב את `SystemHealth` ישירות. נבדק בפועל: מצב דגל-פעיל ראשוני מרונדר נכון; Stop AI מקצה-לקצה (כתיבה durable → refetch → מוצג פעיל עם כפתור Clear); Clear מקצה-לקצה (כתיבה durable → refetch → בריא, `operation_id` חדש נוצר server-side); **קונפליקט 409 מקצה-לקצה** — `clear` חיצוני (out-of-band, מדמה "מישהו אחר כבר ניקה") משנה את ה-`operation_id` הדביק, ואז ה-UI עם ה-id המיושן שלו נדחה בדיוק עם ההודעה המתוכננת. כל קבצי ה-harness הזמניים הוסרו לפני commit — לא חלק מה-diff.

**בדיקות:** `npm run build` (`tsc && vite build`) נקי. אין קובץ backend שנגע.

**Merged:** ✅ `main` (PR #436) | **✅ Verified בפרודקשן ע"י הבעלים ישירות (21/07/2026, לא רק tests/local harness):** `stop_email` דרך ה-TMA החי → "🚨 חירום פעיל" עם כפתור "✅ בטל עצירת Email" מוצג נכון → לחיצה → "✅ כל המערכות תקינות" (תמונות מסך). **בהמשך אישר הבעלים במפורש** שכל 5 כפתורי ה-Stop וה-Clear המתאימים נבדקו ועובדים בפרודקשן, **כולל Stop All** — ואספק ראיה ישירה: פלט אמיתי של `_notify_owner()` מ-Telegram production עבור AI/Automation/WhatsApp/ALL (Email תועד קודם עם תמונות מסך), תואם מילה-במילה לתבנית שנכתבה ב-`tma_api.py`:
```
🚨 EMERGENCY STOP
🛑 STOP AI — קריאות Claude API הופסקו
על ידי: אליהו חזן
Flag: EMERGENCY_STOP_AI=True (נשמר ב-Airtable, שורד restart)
⚠️ לביטול: לחצן הביטול ב-TMA.

✅ CLEAR AI
על ידי: אליהו חזן
Flag: EMERGENCY_STOP_AI=False (נשמר ב-Airtable)
```
(ואותה תבנית בדיוק, עם אותו `על ידי: אליהו חזן`, גם עבור Automation/WhatsApp/ALL — 4 round-trips נוספים). היעדר `⚠️ עדיין חסום ע"י env force-stop` בכל הודעות ה-CLEAR מוכיח גם ש-`still_blocked_by_env=False` בכל המקרים — אין env override פעיל שדרס את ה-clear. זו לא רק "הכפתור עבד" — זו הוכחה ש-`set_emergency_stop()`/`clear_emergency_stop()` רצו בפועל עם `source="tma_owner_stop"`/`"tma_owner_clear"`, כתבו ל-Airtable, ו-`identity.display_name` נפתר נכון מ-TMA auth אמיתי. שני תרחישים ספציפיים יותר נשארים לא-מאומתים במפורש (לא ממצא, רק גבול-דיוק): 409 עם `operation_id` שגוי בפרודקשן החי עצמו (רק ב-harness מקומי, לא production), ושפעולה guarded אמיתית אכן נחסמת **בזמן** ש-Stop All פעיל (לעומת רק "הכפתור עצמו מבצע round-trip").

### C163 — Cost Telemetry Reliability PR1: כתיבה אמיתית ל-`AI_Usage_Daily` + upsert-by-Date (21/07/2026)
קבצים: `app.py`, `core/cost_watchdog.py`, `schema_cache.json`, `docs/PHASE_4B0_MIGRATIONS_CLI.md`, `docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md`, `docs/operations/DEPLOYMENT.md`, `test_ai_usage_daily_schema.py` (חדש), `test_cost_watchdog_airtable_write.py` (חדש) | קשור: פוצל מ-#434 (נסגר בלי מיזוג — בנוי על `main` ישן, התנגש עם `EmergencyStopLegacyWriteBlocked` של PATCH 3B Step 6/C161)

**רקע — לא תיאורטי, נתפס בפועל:** `AI_Usage_Daily` הכילה רשומה אחת בלבד אי-פעם, עם ערכי אפס, למרות שהלוגים הראו הצלחה יומיומית. שורש כפול: (1) השדה החי היה `"﻿Date"` (BOM-prefixed) בעוד הקוד שלח `"Date"` פשוט — כל POST קיבל 422 `UNKNOWN_FIELD_NAME`; (2) `_write_airtable_row()` רשם "שורה יומית נכתבה ל-Airtable" **ללא בדיקה** של ערך ההחזרה של `airtable_create()` — שמחזירה `None` (לא exception) על תגובה שאינה 2xx — כך שההצלחה נטענה גם כשהכתיבה נכשלה בפועל, שבועות ברציפות.

**מה תוקן:** תיקון ה-BOM בוצע **ידנית ע"י הבעלים** ב-Airtable (`Date_tmp` swap) — לא תיקון קוד. בקוד: `_write_airtable_row()` מחזירה `bool` עכשיו ו-`daily_watchdog()` בודקת את זה ומתעדת מפורשות כשהפרויקציה לא נשמרה. נוסף upsert: חיפוש-לפי-Date לפני כתיבה (`at_get_by_field` בגרסה הזו — **הוחלף בהמשך ב-C164**, כי הוא סבל מבאג נפרד), `airtable_patch()` אם קיים, `airtable_create()` אם לא; כשל-lookup (שגיאת רשת/HTTP, לא "לא נמצא" אמיתי) מסרב לכתוב עיוור במקום לנחש ולשכפל.

**היקף שתוקן אחרי review (`ce24605`):** גרסה ראשונה של ה-PR הוסיפה 4 שדות-עלות placeholder (`total_cost_usd` וכו') ל-`schema_cache.json`, נכתבים כ-`0`. הוסר לגמרי — כתיבת `0` לערך שלא נמדד היא עצמה לא-אמינה (לא ניתן להבחין מ"נמדד, אפס אמיתי"), ושם ב-`schema_cache.json` הוא רק ניחוש מקומי, לא הוכחה שהשדה קיים בטבלה החיה. ה-PR כותב/מאמת רק את 5 השדות המאומתים בטבלה החיה (`Date`, `claude_sonnet`, `claude_haiku`, `whatsapp_conversation`, `total_units`).

**Concurrency, מתועד במפורש:** ה-upsert (lookup-then-create-or-patch) הוא **סדרתי best-effort, לא אטומי** — יש חלון TOCTOU אמיתי בין ה-lookup ל-`create`/`patch`. שני ריצות מקבילות של `daily_watchdog()` לאותו `Date` עלולות לשכפל. מקובל היום רק כי ה-scheduler קורא לג'וב הזה אחד-אחד (`WEB_CONCURRENCY=1`).

**Docs:** תוקנו טענות-ישנות ש-Render's Pre-Deploy Command הוא `python -m core.database_migrations`; הערך האמיתי הוא `python -m core.predeploy` (מריץ migrations, ואז Emergency Stop preflight).

**בדיקות:** `test_ai_usage_daily_schema.py` (10 assertions — 5-שדות בלבד, round-trip validation), `test_cost_watchdog_airtable_write.py` (13 assertions — create/patch/failure/lookup-failure). Full `test_*.py` sweep + `smoke_tests.py` + `test_integration.py` + `core/router/test_router.py` + `compileall -q .` — נקיים.

**Merged:** ✅ `main` (PR #435, head commit `ce24605`) | **Verified בפרודקשן:** ❌ — ראה C164: smoke פרודקשן על ה-PR הזה עצמו **נכשל** (upsert לא עבד, שכפל שורות), מה שהוביל ל-hotfix מיידי.

### C164 — Hotfix: lookup ל-`AI_Usage_Daily` עבר מהשוואת-טקסט ל-`DATETIME_FORMAT` (21/07/2026)
קבצים: `core/cost_watchdog.py`, `test_cost_watchdog_airtable_write.py`, `tools/smoke_ai_usage_daily_upsert.py` (חדש) | קשור: C163 (#435), נתפס ע"י smoke פרודקשן אמיתי על #435

**רקע — לא תיאורטי, נתפס בפועל ע"י המשתמש:** smoke ישיר על #435 הממוזג: הרצת `_write_airtable_row()` פעמיים לאותו תאריך הפיקה **שתי** שורות (במקום create→patch); חזרה על הריצה הפיקה **ארבע** שורות סה"כ (11/22/3/36 ו-44/55/6/105, כל אחד משוכפל). כל קריאה נפלה ל-ענף ה-create — patch מעולם לא קרה.

**שורש:** `at_get_by_field(table, "Date", date_str)` בנה `{Date}='YYYY-MM-DD'` — השוואת-טקסט מול שדה מסוג **DATE**, לא טקסט. השוואה כזו **לעולם לא תואמת** שדה date-typed, כך שה-lookup תמיד החזיר "לא נמצא", וכל קריאה נפלה ל-`airtable_create()`.

**תוקן:** lookup עבר ל-`at_list_by_formula()` עם `DATETIME_FORMAT({Date}, 'YYYY-MM-DD')='<date>'` (ממיר את שדה ה-date לטקסט בצד Airtable לפני ההשוואה). `max_records=2` (לא 1), עם שלושה ענפים מפורשים: 0 התאמות → create; 1 התאמה → patch; 2+ התאמות → **סירוב מוחלט**, לוג שגיאת-שלמות-נתונים (כנראה שורות שהבאג הזה עצמו כבר יצר בפרודקשן) — לא ניחוש איזו שורה סמכותית. `date.fromisoformat()` מאמת את `date_str` לפני כל קריאת Airtable. לוגי הצלחה כוללים עכשיו `branch=create|patch`, תאריך, `record_id`, `source=cost_watchdog`.

**חדש:** `tools/smoke_ai_usage_daily_upsert.py` — סקריפט smoke ידני מול Airtable **חי** (לא חלק מלולאת ה-CI, כי הוא כותב לבסיס האמיתי) — בדיוק סוג הבדיקה שטסט ממוסק לא יכול לבצע structurally (הבאג המקורי היה ש-Airtable לא תואם את הפורמולה כפי שהקוד הניח, וזה רק ניתן להוכחה ע"י קריאת API אמיתית).

**בדיקות:** `test_cost_watchdog_airtable_write.py` נכתב מחדש מול `at_list_by_formula` (30 assertions: צורת הפורמולה, 0/1/2+ התאמות, כשל-lookup, תאריך פגום, שני נתיבי כשל-אמיתי). Full sweep + smoke + integration + router + compileall — נקיים.

**Merged:** ✅ `main` (PR #437, head commit `952ddc1`) | **Verified בפרודקשן:** 🟡 חלקי — הבאג עצמו אומת בפרודקשן ישירות (הראיה של המשתמש, ראה "רקע" למעלה); ה-**תיקון** לא אושר במפורש כ-`✅ SMOKE PASSED` באותו סבב (ה-checklist דרש הרצת `tools/smoke_ai_usage_daily_upsert.py` מול הבסיס החי לפני מיזוג — ראה C165 להמשך התיקון של הסקריפט עצמו).

### C165 — Hotfix-followup: תיקון סקריפט ה-smoke עצמו (`total_units` double-count + full assertions) (21/07/2026)
קבצים: `core/cost_watchdog.py`, `tools/smoke_ai_usage_daily_upsert.py` | קשור: C164 (#437)

**רקע:** review-המשך על #437 הממוזג תפס שני באגים **בסקריפט ה-smoke עצמו** (לא בליבת ה-hotfix, שאושרה נכונה וללא שינוי כאן):

1. **`total_units` double-count.** הסקריפט שלח `total_units` כחלק מ-`counts` ל-`_write_airtable_row()` — אבל הפונקציה מחשבת `total_units` בעצמה כ-`sum(counts.values())`. כלומר `counts={claude_sonnet:11, claude_haiku:22, whatsapp_conversation:3, total_units:36}` → נשמר `total_units=72`, לא 36. תוקן: הסקריפט שולח רק את 3 השדות האמיתיים, `_write_airtable_row()` מחשב את `total_units`.
2. **הסקריפט רק הדפיס לוגים — לא אישר כלום.** נכתב מחדש כאימות מבוסס-assertions מלא: pre-check שהתאריך-יעד ריק (אחרת עוצר, כדי לא לכתוב לתוך תאריך עם נתונים אמיתיים); כתיבה #1 → מוודא בדיוק שורה אחת, לוכד `record_id`; כתיבה #2 (ערכים שונים) → מוודא עדיין שורה אחת בדיוק, לוכד `record_id` שני; מוודא ששני ה-`record_id` זהים (patch, לא שכפול); מוודא שערכי השדות הסופיים תואמים בדיוק לכתיבה #2 (`total_units=105`).
3. **ולידציית תאריך קנונית.** `date.fromisoformat()` מקבל פורמטים לא-קנוניים (למשל `"20260721"` עובר בלי `ValueError`). נוסף `parsed.isoformat() == date_str` — רק `YYYY-MM-DD` מילולי מתקבל.
4. **דיוק ניסוח לוג.** לוג שכפול-שורות טען מספר מדויק ("%d שורות תואמות") אך ה-lookup חסום ל-`max_records=2` — נוסח מחדש ל"לפחות 2 שורות תואמות... הספירה האמיתית עשויה להיות גבוהה יותר".

**בדיקות:** `test_cost_watchdog_airtable_write.py` — 30/30 ללא שינוי נדרש (assertion בודקת substring "duplicate", לא ניסוח מדויק). Dry-run מול Airtable מדומה (mocked) לאימות שרשרת ה-assertions מקצה-לקצה. Full sweep + smoke + integration + router + compileall — נקיים.

**Merged:** ✅ `main` (PR #438, head commit `fb6f8b9`) | **Verified בפרודקשן:** 🟡 לא אושר במפורש בסבב הזה עם `✅ SMOKE PASSED` מוצג — ראה גבול-דיוק תחת "עדכון סבב זה" ב-`AI_CONTEXT.md`.

### C166 — Cost Telemetry Reliability PR2: `usage_events` PostgreSQL, shadow only (21/07/2026)
קבצים: `core/usage_telemetry.py` (חדש), `core/model_pricing.py` (חדש), `core/migrations/002_usage_events.sql` (חדש), `app.py`, `llm_fallback.py`, `interaction_engine.py`, `voice_stt_adapter.py`, `providers/anthropic_shim.py`, `.env.example`, `CLAUDE.md`, `test_model_pricing.py` (חדש), `test_usage_telemetry.py` (חדש) | קשור: C163-C165 (PR1 + hotfixes), נבנה על-גבי `main` אחרי #438

**מה זה:** נקודת-רישום דביקה (PostgreSQL) יחידה לכל קריאת AI בתשלום — provider/service/model-generic (לא Anthropic-token-shaped), כך שטקסט OpenAI ו-Whisper STT נכנסים בלי special-casing. **Shadow בלבד לגבי ה-trigger:** `cost_monitor.py` (ה-`EMERGENCY_STOP_AI` trigger החי, האקומולטורים והמחירון שלו) **לא נגעו**; `core/cost_watchdog.py`'s ה-jsonl `daily_watchdog()` הקיים **לא נגע**; `COST_WATCHDOG_LIVE` נשאר `false`; `cost_monitor.record_call()`/`core.cost_watchdog.log_usage()` הקיימים **לא נגעו** — זהו נתיב-רישום שני, מקביל, נוסף בלבד.

**תיקוני-review שהוחלו לפני מיזוג (לא regression — נתפסו בטיוטה):**
- `get_usage_window()` משתמש בחיבור/cursor **אחד** לכל הפעולה — לא "לבדוק זמינות עם חיבור אחד, לשחרר, לפתוח שני לשאילתה האמיתית".
- סטטוס תלת-מצבי `"ok"|"unavailable"|"error"` — שאילתה שזורקת exception מדווחת כ-`"error"`, אף פעם לא מקופלת בשקט לתוצאה ריקה/מאופסת (בדיוק הבלבול שגרם לבאג המקורי של `AI_Usage_Daily` — "השאילתה נכשלה" מול "אירע שימוש-אפס אמיתי").
- כל except שנוגע בחיבור קורא `conn.rollback()` לפני `release_conn(conn)`.

**תיקונים נוספים מסבב-review שני, לפני שה-PR הזה עצמו מוזג:**
- **A.** `app.py::run_agent`'s `except Exception: pass` גולמי סביב `record_llm_usage()` הוחלף בלוג ERROR (`exc_info=True`) — עדיין לא-fatal, אף פעם לא שקט.
- **B.** dedup של `usage_events` עבר מ-`UNIQUE(request_id)` ל-`UNIQUE(provider, request_id)` (וה-`ON CONFLICT` בהתאם) — constraint גולמי על `request_id` מניח שכל מרחב-ID של כל provider זר למרחבים של providers אחרים, לא מובטח.
- **C.** `providers/anthropic_shim.py::AnthropicLLMProvider.generate()` (F13, קריאת `client.messages.create()` ישירה, ללא caller חי — אומת ב-grep) הוכשר עם אותו חוזה `record_llm_usage()` כמו שאר 6 נקודות-הקריאה, על עיקרון (לא להסתמך על "לא בשימוש כרגע" שיישאר נכון).

**נחווט ל-6 נקודות-קריאה אמיתיות + shim מת אחד:** `app.py::run_agent` (Anthropic), `llm_fallback.py::call_anthropic_text`/`call_openai_text` (Anthropic + OpenAI fallback, עם `fallback_from` ל-traceability, ללא double-record), `interaction_engine.py::analyze_interaction` (Anthropic), `voice_stt_adapter.py::_transcribe_openai` (OpenAI Whisper — **לא shadow טהור**, ראה סעיף הבא), `providers/anthropic_shim.py` (shim מת). `creative_generator.py` לא נזקק לשינוי — כבר קורא ל-`call_anthropic_text()`.

**חריגה מתועדת מ"shadow בלבד" — `voice_stt_adapter.py`:** כדי לקבל `duration_seconds` אמיתי (לא ניחוש), `_transcribe_openai()` מבקש עכשיו `response_format="verbose_json"` מ-OpenAI — **שינוי אמיתי לפרמטר קריאת ה-API החי**, לא no-op. חתימת ההחזרה עברה מ-`(text, language)` ל-`(text, language, duration)`; caller יחיד + mock ה-self-test עודכנו בהתאם. התנהגות התמלול עצמה (טקסט, טיפול שגיאות) לא השתנתה, אבל זו לא no-op — צוין כאן במפורש, כפי שצוין ב-PR description אחרי תיקון-ניסוח.

**E/F (smoke/production validation אמיתיים) — לא בוצעו בזמן בניית ה-PR:** נכתב במפורש ב-PR description שאין credentials חיים (Airtable/Postgres/OpenAI) בסביבה שבנתה את ה-PR — לא הועמד claim מזויף. ראה "עדכון סבב זה" ב-`AI_CONTEXT.md` להמשך: המשתמש דיווח (לא Claude) שביצע אימות פרודקשן ישיר בעצמו לאחר המיזוג.

**בדיקות:** `test_model_pricing.py` (11 assertions), `test_usage_telemetry.py` (30 assertions — חיבור יחיד, סטטוס תלת-מצבי, rollback, צורת `ON CONFLICT (provider, request_id)`). Full sweep + smoke + integration + router + compileall — נקיים, הורץ שוב אחרי rebase על `main` שאחרי מיזוג #438.

**Merged:** ✅ `main` (PR #439, head commit `6d4a26e`) | **✅ Verified בפרודקשן — מדווח ע"י המשתמש ישירות (לא נבדק עצמאית ע"י Claude, אין credentials חיים בסביבה זו):** `usage_events table: WORKING`; `Anthropic run_agent recording: VERIFIED`; `OpenAI Whisper recording: VERIFIED`; `runtime model matching pricing table: VERIFIED` (כלומר לא נפל ל-fail-safe ה-`$5/$25`); `exact pricing, not fallback estimate: VERIFIED`; `COST_WATCHDOG_LIVE=false: VERIFIED` (ה-trigger החי לא הושפע). **גבול-דיוק, לא ממצא:** נקודות ה-checklist E (smoke STT מלא לפני-מיזוג) ו-F (מספר הימים של השוואה מול חיוב-ספק אמיתי) לא בוצעו/לא הושלמו — **PR3 (trigger cutover) נשאר חסום במפורש**, לפי הנחיית המשתמש, עד שכמה ימי נתונים ייבדקו מול חיוב פרודקשן אמיתי.

### C167 — BUG-133: test_bug104_tma_lead_event_bridge.py mock-isolation fix (21/07/2026)
קבצים: `test_bug104_tma_lead_event_bridge.py` | באג: BUG-133

> **הערת מספור:** נרשם במקור כ"C163"/"BUG-131" לפני שנודע ש-C163/BUG-131 כבר נתפסו (Cost Telemetry saga, session מקביל). שונה ל-C167/BUG-133 (הבאים הפנויים) בזמן rebase על `main`.

**בעיה:** נחשף ע"י הבעלים דרך בדיקה ידנית ב-TMA/Airtable (לא CI, לא code review) — 310 מתוך 705 רשומות (43%) ב-Interaction Log הפרודקשן שייכות ל-`"recLEAD001"`, fixture ID לא-תקין (10 תווים, לא 17) מתוך קובץ הטסט הזה. חלוקה מדויקת 155/155 בין `lead_outcome`/`lead_patch`, פרוסה על 07-16 עד 07-21.

**Root cause:** `tma_api.py:34` בונד את `_gw_create` ל-`airtable_gateway.airtable_create` **פעם אחת בזמן import**. הקובץ מנסה למקק כתיבות דרך `airtable_gateway.airtable_create = _counting_create` — זה דורס רק את ה-attribute על מודול `airtable_gateway`, לא את `tma_api._gw_create` הכבר-bound. `_audit()` (הנקרא מ-`set_lead_outcome`/`patch_lead` אחרי PATCH מדומה-מוצלח) המשיך לקרוא לפונקציה **האמיתית** → POST אמיתי, שקט, ל-Interaction Log הפרודקשן בכל הרצת "success case". אותה משפחת-באג בדיוק כמו BUG-128, מנגנון שונה (מיקוק היעד הלא-נכון, לא בריחה מ-`with patch()` scope).

**תוקן:** `tma_api._gw_create = _counting_create` נוסף ישירות (עם restore ב-`finally`), + `tma_api._at_list` (ממצא משני נלווה — GET-lead timeline lookup, read-only, לא כתב נתונים אך גם ברח מה-mock, נצפה `403 Forbidden` בזמן ריצה). `_counting_create` עודכן לעקוב אחרי כתיבות ל-`Tables.INTERACTION_LOG` בנפרד, עם 4 assertions חדשות שמוכיחות ש-`_audit()` נתפס ע"י ה-mock.

**בדיקות:** 50/50 (היה 46/46) — 4 assertions חדשות (BUG-133 regression), ואין יותר `403 Forbidden`/קריאת-רשת אמיתית בפלט. Full `test_*.py` sweep + `smoke_tests.py` + `compileall -q .` נקיים, ללא רגרסיה.

**ניקוי:** 310 הרשומות המזוהמות הקיימות (`recLEAD001:*`) נמחקו ישירות מ-Airtable, מאושר במפורש ע"י הבעלים (לא חלק מהתיקון בקוד — ניקוי חד-פעמי).

**לא נוגע:** שני קבצי test-BUG-104 נוספים (`test_bug104_leads_reasoning_projection.py`/`test_bug104_phase1_1_contract_hardening.py`) — נבדקו, לא קוראים ל-Flask test client ל-write endpoints, אין סיכון. `core/lead_event_writer.py`/`tools/approval_actions.py::tma_write()` — import דחוי תקין משני הצדדים, לא נגועים. שום קוד production.

**Merged:** ⏳ טרם — branch `claude/bug131-test-isolation-interaction-log-leak`.
**Verified בפרודקשן:** ⏳ לא רלוונטי עדיין — תיקון test-isolation בלבד, אין שינוי קוד production. הוכחה שהקובץ לא ימשיך לזהם תגיע מהרצת test sweep הבאה אחרי merge.

### C168 — BUG-129, BUG-135: `_NAME_STOP` הרחבה — ציטוט-עצמי ופקודות-מחיקה הפיקו שם ליד מזויף (22/07/2026)
קבצים: `core/ingress_classifier.py`, `test_bug135_command_verb_name_stop.py` (חדש) | באגים: BUG-129, BUG-135

**בעיה:** הבעלים דיווח ששני באגים נפרדים חוסמים בדיקות RP5. **BUG-129** (נרשם קודם, ראה `BUG_AUDIT_LOG.md`): הדבקת התבנית העצמית של הבוט (`"📋 זיהיתי ליד: *X* (phone)"`) חילצה `"זיהיתי"` במקום השם האמיתי. **BUG-135** (חדש): `"תמחק איש קשר 0536272637"` זוהתה כליד בשם *תמחק איש קשר* — אין שם אמיתי בטקסט כלל. שתי דוגמאות production נוספות (`"תוסיף איש קשר בדיקה טלפון X"` → `איש קשר בדיקה`, `"תעדכן טלפון של ביבי נתניהו..."` → `ביבי נתניהו`) כבר עבדו נכון ומשמשות כ-regression baseline.

**Root cause (משותף לשני הבאגים, תסמינים נפרדים):** `_extract_name_from_window()` חוזרת על המאץ' הראשון של `_HEBREW_NAME_RE` שעובר ולידציה — לא ממשיכה למאץ' הבא גם כשקיים שם אמיתי אחריו (BUG-129). "זיהיתי"/"תמחק"/"מחק"/"הסר" לא היו ב-`_NAME_STOP`, כך שנשארו כחלק מהסגמנט שנבחר כ"שם". אין ל-`ingress_classifier.py` טיפול ייעודי ל-delete-intent (`Intent.DELETE_TASK` היחיד שקיים ב-router מכסה רק משימות, לא contacts/leads) — טקסט מחיקה נופל לאותה חילוץ גנרית כמו יצירה/עדכון (BUG-135).

**תוקן:** `_NAME_STOP` + "זיהיתי" (BUG-129) ו-3 פעלי-מחיקה "תמחק"/"מחק"/"הסר" (BUG-135, תואם לקבוצת הפעלים של `Intent.DELETE_TASK` ב-`core/router/intent_router.py`). זה לבדו השאיר "איש קשר" (ה-role-noun השורד) כמועמד שקרי — נבדק במפורש מול הבעלים (AskUserQuestion) שההתנהגות הקיימת של `"איש קשר בדיקה"` (עם מילה נוספת) **לא** אמורה להשתנות, אז "איש"/"קשר" **לא** נוספו כ-stop-words גורפים. במקום זה: `_GENERIC_NAME_PHRASES = {"איש קשר"}` — reject רק על ה-phrase המדויק, בלי מילה נוספת שורדת לצידו.

**Out of scope:** התיקון הזה משנה **רק** את חילוץ-השם. הוא **לא** משנה create-vs-update routing ולא resolution של רשומה קיימת — BUG-130 (עדכון-שדה לליד קיים מנותב כיצירת ליד חדש) **נשאר פתוח**, לא נוגע בפאץ' הזה.

**בדיקות:** `test_bug135_command_verb_name_stop.py` (10 assertions חדש — T1/T2 ל-BUG-129, T3/T4/T6 ל-BUG-135, T5/T7/T8 regression ל-`תעדכן`/"איש קשר בדיקה"). Full sweep (`test_*.py` — 166 קבצים, `smoke_tests.py`, `test_integration.py`, `python3 -m compileall -q .`) — נקי. שני כשלים קיימים-מראש ב-sweep (`test_bug_canonical_tool_wiring.py`, `test_pa01_phantom_approval_enforcement.py`) אומתו כקיימים גם על `main` לפני התיקון הזה (git stash + הרצה) — לא רגרסיה מהשינוי הזה.

**Merged:** ✅ כן — commit `9285106`, PR #444 (`3f69b1d`). **תיקון-סטטוס (23/07/2026):** השורה הזו אמרה בטעות "טרם ממוזג" — אומת ישירות מול `git merge-base --is-ancestor` ש-`9285106` הוא ancestor של `main`. תיקון-תיעוד בלבד, אין שינוי קוד.
**Verified בפרודקשן:** ⏳ לא עדיין — קוד ממוזג, לא אומת מול תעבורת production/staging בפועל.

### C169 — PR #449: warm-cache TTL consistency, sibling-rejection disclosure, pending-approval query routing (23/07/2026)
קבצים: `core/action_gateway.py`, `app.py`, `test_staging_23jul_findings.py` (חדש), `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` (חדש) | קשור: staging findings 23/07/2026, TurnCoordinator Phase 0 (observation only, לא נוגע)

**בעיה:** סבב בדיקות ידניות ב-`my-bot-approval-staging` (Telegram, `boss_hq:eliyahu@owner`) לצורך בחינת החוזה הקפוא של TurnCoordinator העלה 7 ממצאים בקוד הקיים — כולם קיימים תחת `policy_snapshot_version: phase0-static-v1`, לא תוצר של Shadow Decision.

**תוקן (קוד+tests):**
1. `ExecutionLedger.find_live_by_user()` — אכף `_is_expired()`/`CONTRACT_PENDING_TTL_SECONDS` רק במסלול cold-cache (repository recovery), לא במסלול warm-cache. עקבי עכשיו בשני המסלולים. **שם מדויק בכוונה — "warm-cache TTL consistency fix", לא "TTL enforcement fix":** לא נוגע בשאלת-המדיניות של חלון-הזמן עצמו (24h, שהוגדר במקור ל-TMA). אומת מול ActionContracts export אמיתי מהבעלים: 3 מ-6 siblings שנדחו היו בני 27-38 שעות (היו נחסמים ע"י התיקון), אבל ה-contract שבפועל בוצע (`7fed5be6`, "איש קשר דני לוי") היה בן 14.65 שעות — בתוך ה-24h, לא היה נחסם. אזהרת-גיל (`⚠️ ממתין מ-N שעות`, סף שעה) נוספה כמיטיגציה משלימה.
2. `route_disambiguation()`/`route_combined_word()` — גילוי-מפורש כשבחירה ממוקדת דוחה siblings אחרים; הספירה מבוססת על `reject()`'s confirmed-success return, לא הנחה מראש (אומת בבדיקת רגרסיה שמדמה כשל-דחייה חלקי).
3. `ActionGateway.describe_pending_queue()` חדש — עונה על שאלות "מה ממתין לאישור" מ-`ActionContracts` ישירות, במקום שהסוכן הכללי ינחש טבלה (`Tasks`, בפועל). התשובה מציינת במפורש שהיא מכסה `ActionContracts` בלבד — לא `_pending_approvals`/`event_bus.pending` (מנגנוני legacy נפרדים שעדיין קיימים). לוג הקריאה נכתב עם שדות מובנים בלבד (`pending_count`/`scope`/`result_code`) — לא טקסט-משתמש/תוכן-תשובה גולמי (RP5/TurnCoordinator-Shadow sampling hygiene).

**תועד בכוונה, לא מומש** (דורש הכרעת-owner או אישור-חוזה TurnCoordinator, כדי לא לבנות מנגנון מקביל): §21 sibling-reject semantics (Finding #2); `DESTRUCTIVE_ENTITY_CLARIFICATION`/§3.2 בחוזה (Finding #6); Finding #7 (חדש) — "תוסיף איש קשר X" תמיד יוצר Lead, למרות ש-`intent_router.py` כבר מזהה `Intent.CREATE_CONTACT` נכון — `lead_candidate_handler.py` לא קורא לסיווג הזה. אימות-ריאלי לתרחיש 7 המילולי בחוזה הקפוא.

**Manual action items:** רשומת `recK8RdYkdDmTGdob` (Leads) — לא זבל, בקשה לגיטימית שבוצעה באיחור; דורשת אישור-owner. הכרעת-owner על חלון-ה-TTL הרלוונטי לזרימות אינטראקטיביות.

**בדיקות:** `test_staging_23jul_findings.py` (33 assertions חדש). Full regression (`test_action_gateway.py`/`test_bug_batch_approval_preserved.py`/`test_bug115_confirmation_routing_bookmark.py`/`test_bug117_batch_preview_precedence.py`/`test_bug070_combined_wording.py`/`test_bug070_pending_approval_multi.py`/`test_pr0c_action_contract_repository.py`/`test_pr0c_action_contracts_persistence.py`/`test_stage_b_full_suite.py`/`test_c89_preview_confirmation.py`/`test_bug114_context_interrupt_amplification.py`/`test_bug135_command_verb_name_stop.py`) + `smoke_tests.py` + `test_integration.py` + `compileall -q .` — נקי.

**Cross-Layer Impact Matrix מלא:** `docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` (כנדרש ע"י `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — נגיעה ישירה בשכבה 4, בעקיפין בשכבה 2/3).

**Post-merge:** `claude/rp5-staging-fault-injection-v4akit` (ענף deploy staging, בכוונה לעולם לא ממוזג ל-`main`) עבר rebase על `main` (כולל PR זה) והועלה מחדש (force-push) — staging מריץ עכשיו את התיקון.

**Merged:** ✅ כן — PR #449, commit `e2d25af` (merge), `a787203`+`eab7ba5` (תוכן).
**Verified בפרודקשן:** ⏳ לא עדיין — ממתין לדגימת staging אמיתית אחרי ה-rebase למעלה.

### C170/C171 — PR #456/#457: BUG-141..146 documentation + BUG-141 dispatch-order fix (24/07/2026)
קבצים: `BUG_AUDIT_LOG.md`, `app.py`, `test_bug141_pending_query_dispatch_order.py` (חדש) | קשור: staging findings 24/07/2026 (AG-01/CB-01/CB-02)

**PR #456 (תיעוד בלבד):** נרשמו BUG-141 (AG-01), BUG-142 (Sessions stale linked-lead sync), BUG-143 (CB-02A `resolve_canonical_tool` payload mismatch), BUG-144 (CB-02B reject לא סוגר `ActionContracts.status`), BUG-145 (הודעות כפולות approve/reject) — כולם documented-only. BUG-146 מוזג לתוך BUG-122's `bypass_new_action` scope decision (אותו קוד/מנגנון, ראיות CB-01/CB-02 מצטברות). נוסף ממצא תכנוני ללא מספר BUG: "Cost Telemetry Coverage and Per-Turn Attribution".

**PR #457 (תיקון קוד, BUG-141 בלבד):** `_PENDING_QUERY_RE` נבדק כעת ב-`if` עצמאי לפני `if "?" in _stripped:` (במקום `elif` אחרי כל שרשרת ה-if/elif) — שאלת "מה ממתין כרגע לאישור?" כבר לא נחסמת ע"י ה-`"?"` הכללי. אין שינוי ב-regex, אין נגיעה ב-BUG-142/143/144/145/122/Cost Telemetry. 15 בדיקות חדשות (`test_bug141_pending_query_dispatch_order.py`), full sweep 166/169 (3 כשלים קדם-קיימים לא-קשורים: `test_document_converter.py`, `test_google_tools.py` — `docx` חסר, `test_phase_4b0_1a_atomic_claims.py` — קידוד Windows).

**✅ Verified בפרודקשן (24/07/2026, `my-bot-jqz2`, אחרי deploy `c12a19b`):** "מה ממתין לאישור" → `"אין פעולה שממתינה לאישור.\n\n(הבדיקה מכסה את מערכת ActionContracts בלבד...)"`.

**✅ Verified ב-staging (24/07/2026, `my-bot-approval-staging`, אחרי deploy ידני ל-branch המרובייז `claude/rp5-staging-fault-injection-v4akit`):** אותה שאלה בדיוק, לוג מלא — `describe_pending_queue()` נקרא, 2 קריאות Airtable GET (`ActionContracts`), **ואין שום `POST api.anthropic.com`** — ה-Agent לא נקרא כלל. פירוט מלא ב-`BUG_AUDIT_LOG.md`'s BUG-141.

**תצפית עלות (24/07/2026, מהבעלים) — חלקית מאומתת:** "הלוגים נקיים... אני בטוח שגם העלות ירדה." מאומת: turn של שאלת-pending-queue לא מפעיל LLM כלל (0 קריאות Anthropic בלוג, לעומת tool-loop מלא לפני התיקון) — ירידת-עלות מבנית אמיתית לדפוס-השאלה הזה. **לא אומת:** ירידת עלות שעתית/יומית כוללת בפועל — דורש בדיקת `cost_monitor`/`usage_events` totals, לא רק תצפית איכותית. קשור ל-"Cost Telemetry Coverage and Per-Turn Attribution" (`BUG_AUDIT_LOG.md`, ללא מספר BUG) — אין עדיין breakdown פר-turn שהיה מאפשר לכמת את זה במדויק.

**Merged:** ✅ כן — #456 commit `585a6f6`, #457 commit `c12a19b`.
**Verified בפרודקשן:** ✅ כן (24/07/2026) — ראו evidence למעלה. **Verified ב-staging:** ✅ כן (24/07/2026).

### C172 — תיעוד-בלבד: דוח בדיקות Post-Merge (תרחישים 1–5) על BUG-143/144/145 + BUG-147 חדש (25/07/2026)
קבצים: `BUG_AUDIT_LOG.md` | קשור: BUG-143 (CB-02A), BUG-144 (CB-02B), BUG-145 (הודעות כפולות), BUG-147 (חדש)

**מקור:** דוח בדיקות ידניות של הבעלים ("PM460-POSTMERGE", תרחישים 1–5) על מסלול ה-Approve/Reject של `ActionContract`/`ActionGateway`. סיכום הבעלים: NO-GO למסלול Approve בפרודקשן.

**נרשם (תיעוד-בלבד, ללא שינוי קוד):**
1. **BUG-143** — עדכון ראיות: מופע רביעי חי (`contract_id=aa74244a-...`, "PM460-POSTMERGE-CANONICAL") של אותו payload-shape mismatch הרשום.
2. **BUG-144** — עדכון ראיות **סותר לכאורה**: הדוח מציג תרחישי-דחייה (2, 4) שבהם ה-`ActionContract` הקנוני כן עבר `rejected` כראוי. קריאת קוד ישירה מאשרת ש-`app.py:2409-2449` (כפתור-דחייה inline) **עדיין** לא קורא ל-`ActionGateway.reject()` — הפער הרשום נשאר בעינו שם. נמצא מסלול-דחייה שני, נפרד (מילות-ביטול חופשיות → `route_confirmation_word`/`route_cancellation_word` → `self.reject()`), שכן עובד נכון — סביר שהדוח תרגל את המסלול הזה ולא את הכפתור. **לא הוכרע** — נדרש בירור עם הבעלים אילו פעולות בדיוק בוצעו לפני שינוי סטטוס BUG-144.
3. **BUG-145** — עדכון ראיות: כפל-ההודעות המתועד (עד כה רק בענף הצלחה) נצפה עכשיו גם בענף **כישלון-ביצוע** (`contract_id=81528313-...`, "PM460-POSTMERGE-CB-APPROVE") — אותו root cause (`app.py:2385-2400`), scope מורחב.
4. **BUG-147 (חדש)** — `tools/dispatcher.py`'s `case "airtable_add"` מחזיר `str(e)` גולמי (לא מבנה `{ok,...}`) בשני מסלולי-חסימה (`LeadsDirectWriteBlocked`, שורה 261; `TenantScopeViolation`, שורה 319) — משחזר עצמאית את התסמין "expected structured result dict; got plain string" שהדוח דיווח עליו בתרחיש 5. לא אומת שזו בהכרח נקודת ההפעלה המדויקת של הדגימה הספציפית מהדוח.

**שיטה:** אין ריצת-בדיקות/reproduction עצמאית בסבב הזה — כל הממצאים מבוססים על (א) הדוח שהבעלים סיפק, (ב) קריאת קוד ישירה לאימות/הרחבת root cause. שום contract לא אושר/נדחה, שום קוד לא שונה.

**Cross-Layer Authority Contract gate:** לא רלוונטי לסבב הזה — תיעוד-בלבד, אין קוד runtime. יידרש לפני כל PR מימוש עתידי ל-BUG-143/145/147 (נגיעה ישירה ב-`ActionContract`/`ActionGateway`, שכבה 4).

**Merged:** ✅ כן — commit ישירות ל-`claude/telegram-task-approval-audit-il29sj`.
**Verified בפרודקשן:** לא רלוונטי (אין שינוי קוד).

### C173 — PR #469: BUG-147 root-cause fix (Patch A) (26/07/2026)
קבצים: `tools/dispatcher.py`, `test_bug147_dispatcher_structured_error_shape.py` (חדש) | קשור: BUG-147

**PR #469 (`claude/bug147-dispatcher-structured-error`, commit `3b111f6`, ממוזג `e946225`):** תוקן ב-audit קודם ש-BUG-147's root cause שנרשם ב-C172 היה שגוי — השורש האמיתי הוא `dispatch_tool()`'s gate הכללי אחרי `action_validator.validate_action()`, שהחזיר `validation.reason` גולמי (בלי "❌") ל-structured write tools. תיקון: tools ב-`core.anti_hallucination._EVIDENCE_VALIDATORS` (כולל `airtable_add`) מקבלים `{ok: False, tool, user_message}` במקום מחרוזת. PR ממוקד קוד+test בלבד, ללא נגיעה ב-`app.py`/`core/action_gateway.py` (מאומת: BUG-143/144/145 לא כפולים בדיף). נוצר על ענף טרי מ-`origin/main`, לא נבנה מעל branch קודם — ראה `docs/architecture/action-gateway/PM460_POSTMERGE_MINIMAL_PATCH_GATE.md` להיקף המקורי.

**בדיקות:** `test_bug147_dispatcher_structured_error_shape.py` (10/10, חדש) — 3 קבוצות בדיקה: ActionBlocked מוחזר כ-structured failure; `core.action_gateway._make_dispatch_executor()`'s tool_executor boundary (הפונקציה האמיתית ש-ActionGateway קורא לה בפרודקשן, לא מוקית) מקבל dict לא מחרוזת; `verify_execution()` לעולם לא מסווג ככשל-חסום כהצלחה. Full sweep 170/170, `smoke_tests.py` ירוק.

**✅ Verified ב-staging (26/07/2026):** `claude/rp5-staging-fault-injection-v4akit` עבר rebase מעל `main` (כולל PR #469, ו-PR #460/#461/#467 שכבר תועדו) והועלה מחדש (force-push, commit `da7a8ab`). `PM460-RETEST-APPROVE` (סבב הבדיקה החוזרת של הבעלים) אישר במפורש: "BUG-147 לא חזר... לא הופיעה השגיאה expected structured result dict".

**Merged:** ✅ כן — PR #469 commit `3b111f6`, ממוזג `e946225`.
**Verified בפרודקשן:** ⏳ לא עדיין — קוד ממוזג ל-`main`, נבדק רק ב-staging. **Verified ב-staging:** ✅ כן (26/07/2026).

### C174 — PR #470: BUG-149 fix — action-resolution context events + deterministic multi-mutation guard (26/07/2026)
קבצים: `app.py`, `core/action_gateway.py`, `core/action_resolution_event.py` (חדש), `core/action_resolution_projection.py` (חדש), `core_knowledge.py`, `memory_store.py`, `test_bug149_action_resolution_projection.py` (חדש), `test_bug149_multi_mutation_guard.py` (חדש), `test_pa01_phantom_approval_enforcement.py` | קשור: BUG-149, BUG-122 (superseded ל-multi-mutation case)

**מקור:** סבב הבדיקה החוזרת השני של הבעלים (אחרי deploy PR #469 + rebase staging), תרחיש 5 — payload ישן/כבר-נדחה בוצע במקום הבקשה הנוכחית. פירוט מלא ב-BUG_AUDIT_LOG.md's BUG-149.

**PR #470 (`claude/bug149-action-resolution-context`, commit `ceb9148`, ממוזג `59e74be`):** תוכנן ואושר דרך סבב-תכנון ייעודי הכולל Cross-Layer Impact Matrix מלא (`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`) לפני מימוש, per **10 תיקוני-עיצוב** שנדרשו ואושרו במפורש: (1) אירועי-context נפרדים לחלוטין מהיסטוריית שיחה רגילה, לא הודעת user/assistant סינתטית; (2) idempotency דטרמיניסטי (`contract_id+outcome+version`); (3) כשל-הזרקה לא-חוסם ל-lifecycle הדורש, לוג WARNING ללא payload רגיש; (4) תיעוד מפורש ש-`memory_store` הוא process-local/non-durable, לא מקור-אמת; (5) ה-pre-scan סופר רק tool_use מוטטים, ומחסום את **כל** התגובה (0 contracts/dispatch/executor/pending-event) על 2+ — לא שומר ראשון/אחרון; (6) כשל-projection לעולם לא משנה את ה-lifecycle הדורש, אבל השער הדטרמיניסטי ממשיך להגן גם אם ה-projection שבור לגמרי; (7) 7 סוגי-בדיקות דטרמיניסטיות ספציפיות; (8) סקירת כל terminal outcomes וזיהוי נקודת-הפליטה המוסמכת לכל אחד (גילוי: `expired`/`cancelled` אינם קיימים כ-status אמיתי בקוד היום, לא כלולים); (9) Cross-Layer Matrix מעודכן — שכבה 4 הופכת ל-producer מוסמך של אירועי-lifecycle גלויים-למודל, מתועד כגבול-אירוע חדש ולא "ללא השפעה"; (10) הנחיית system-prompt כ-defense-in-depth.

**בדיקות:** `test_bug149_action_resolution_projection.py` (23, חדש) + `test_bug149_multi_mutation_guard.py` (15, חדש). שני test blocks ב-`test_pa01_phantom_approval_enforcement.py` (R3 integration, P1-B/R3-real) הניחו את התנהגות-BUG-122 הישנה ("הראשון מנצח" בתגובה עם 2 mutating tool_use) — עודכנו לשקף את ההתנהגות החדשה (אפס contracts). Full sweep 172/172, `smoke_tests.py` ירוק.

**🟡 Staging rebase בוצע, טרם verified (26/07/2026):** `claude/rp5-staging-fault-injection-v4akit` עבר rebase נוסף מעל `main` (כולל PR #470, commit `59e74be`) והועלה מחדש (force-push, commit `67c595d`). Rebase נקי לחלוטין — 0 קונפליקטים (RP5 hooks ו-BUG-149 נוגעים באזורים שונים ב-`app.py`). שימור מלא של RP5-only hooks (`core/rp5_fault_injection.py`, hook ב-`tools/dispatcher.py`, `run_agent()`→`_run_agent_impl()` wrapper) ואי-שחזור מכוון של commit-ה-PM460 העצמאי הישן. Full sweep על הענף המרובייז: 175/175 ירוק. **טרם בוצע deploy ידני + re-run של תרחיש 5 נגד ה-commit הזה ספציפית** — נדרש לפני שניתן לקבוע "VERIFIED IN STAGING" במלואו לפי "כלל ברזל".

**Merged:** ✅ כן — PR #470 commit `ceb9148`, ממוזג `59e74be`.
**Verified בפרודקשן:** ⏳ לא עדיין — לא נפרס. **Verified ב-staging:** 🟡 קוד מרובייז ומוכן, retest חי טרם בוצע.

### C175 — PR #471: Single-Speaker Approval UX Base (27/07/2026)
קבצים: `app.py`, `core/action_gateway.py`, `feature_flags.py`, `.env.example`, `test_pr1_single_speaker_approval_ux.py` (חדש), מספר `test_*.py` קיימים | קשור: BUG-144, BUG-145, BUG-118, F52 Unified Approval Runtime

**PR #471 (`5e2c244` + תיקון CI `dadf851`, ממוזג `c64da20`):** `ApprovalLifecycleResult` כתוצאת UX קנונית חדשה למחזור-חיי אישור, מאחורי `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` (כבוי כברירת מחדל בקוד וב-`.env.example`). כש-מופעל, Gateway הוא בעל-התשובה במסלולי approval וה-Agent נעצר לאחר בחירת בעלות. Telegram ו-WhatsApp ממפים אותו lifecycle state לאותה משמעות. BUG-144 (callback reject לא סגר את ה-`ActionContract` הקנוני) ו-BUG-145 (שתי הודעות סופיות סותרות לאותו callback) מיושמים. BUG-118 (חשיפת tool_name/UUID/record ID) נסגר ברמת-קוד ע"י redaction בלתי-מותנה — **פעיל גם כשהדגל כבוי**. `ActionContracts` נשאר מקור-האמת היחיד; לא נוסף state ל-Sessions/store חלופי. callback payload מקסימלי שנבדק: 53/64 bytes, ללא truncation.

**D-011 (drift מ-D-010, לא נפתר ב-PR הזה):** `ApprovalLifecycleResult` הוא renderer מקביל ל-`GatewayReply`/`compose_status_reply()`, לא הרחבה שלו כפי ש-D-010 דרש — תועד ב-`DECISION_LOG.md` ע"י audit נפרד של Context Librarian (27/07), נפתר בהמשך ע"י D-012/PR #480 (ראה C177 למטה).

**בדיקות:** `test_pr1_single_speaker_approval_ux.py` (11, חדש). callback approve/reject, דחייה טקסטואלית, repeated completion/rejection, pending/no-pending, cross-chat delivery מכוסים ברגרסיות. `backend-ci`/`frontend-ci` עברו לאחר תיקון-CI ששימר owner-only denial ו-legacy rejection rendering כשהדגל כבוי.

**🟡 Production Verification Plan בוצע חלקית (27/07/2026):** `docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md` — 6 טענות נבדקו נגד staging (אחרי rebase) ו-production. תוצאה מעורבת: claim 1 (דגל פעיל) VERIFIED; claim 2 (הודעה סופית יחידה) PARTIALLY_VERIFIED (Telegram/owner-role/staging בלבד); claim 3 (callback עם contract_id מדויק) VERIFIED; **claim 4 (אין חשיפת מזהים) FALSIFIED** — `_describe_contract_for_reconfirmation()` עדיין חשף שם-טבלה גולמי במסלול ה-reconfirmation, מסלול **שונה** ממה ש-BUG-118 תיקן — נסגר בהמשך ע"י PR #479 (ראה C176 למטה); claim 5 PARTIALLY_VERIFIED; claim 6 VERIFIED.

**Merged:** ✅ כן — PR #471, commit `c64da20`.
**Verified בפרודקשן:** ⏳ לא — `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false` בפרודקשן נכון ל-28/07/2026. **Verified ב-staging:** 🟡 חלקית, ראו לעיל.

### C176 — PR #479: תיקון wording עסקי, redaction שם-טבלה ב-Airtable (28/07/2026)
קבצים: `app.py`, `core/action_gateway.py`, `core/agent_message_formatter.py`, מספר `test_*.py` | קשור: PR #471 claim 4 (FALSIFIED), F52

**PR #479 (`claude/approval-ux-wording-patch`, ממוזג `e663818`):** סוגר את הפער שנמצא ב-C175/claim 4 — `_describe_contract_for_reconfirmation()` (`core/action_gateway.py`) כבר לא כולל שם-טבלה גולמי ב-fallback הכללי של `airtable_add`/`airtable_update`; רק fallback אמיתי של כלי-שאינו-Airtable עדיין מציין את שם הכלי (אין שם-טבלה לחשוף שם מלכתחילה). אומת ישירות מול `main` הנוכחי (לא רק מהכותרת) — הפונקציה בפועל תואמת את התיקון המתואר.

**Merged:** ✅ כן — PR #479, commit `e663818`.
**Verified בפרודקשן:** לא רלוונטי לתיקון-wording זה בפני עצמו — כפוף לאותה מדיניות rollout כמו PR #471.

### C177 — PR #480: D-012, קיבוע MessageContract Envelope V1 לתכנון (28/07/2026)
קבצים: `docs/architecture/f52-unified-approval-runtime/decisions/DECISION_LOG.md`, `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` (חדש), `rollout/MESSAGE_CONTRACT_ENVELOPE_MIGRATION_PLAN.md` (חדש) | קשור: D-010, D-011 (נסגר), F52

**Cross-Layer Authority Contract gate:** רלוונטי — מסמך Planning Gate הנוגע ב-approvals/execution presentation (שכבה 3/RP5 guard), פותח בהפניה מפורשת ל-`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` ומכיל Cross-Layer Impact Matrix מלא ב-§0.1 של המסמך עצמו.

**PR #480 (`claude/message-contract-foundation-quarmf`, ממוזג `11e58df`):** תיעוד-בלבד, אין קוד runtime. D-012 (owner-approved) סוגר את D-011 בדרך של **פיוס, לא מחיקה**: `MessageContract` מאושר כקלט הקנוני היחיד ל-formatter הסופי (`core/agent_message_formatter.py::format_agent_message()`); `ApprovalLifecycleResult`/`GatewayReply`/`ActionFact` נשארים חוזי-fact/result פנימיים תקפים, מגיעים ל-formatter רק דרך adapters. `turn_id` אופציונלי (`None` כברירת מחדל, לעולם לא מסונתז מ-`chat_id`/session/`contract_id`). rollout מתוכנן כ-3 PR נפרדים (PR A/B/C), לעולם לא משולבים.

**Merged:** ✅ כן — PR #480, commit `11e58df`.
**Verified בפרודקשן:** לא רלוונטי — תיעוד-תכנון בלבד, implementation לא מאושר.

### C178 — PR #488/#489/#491: Context Librarian Consumption Enforcement — תכנון + audit-remediation + preflight PR2 (28–29/07/2026)
קבצים: ראו `ROADMAP.md`'s N17 section לרשימה המלאה | קשור: N17, F52 (PR2 preflight). **הערה:**
PR #490 (בטווח המספרים בין אלה) **אינו** חלק מהרשומה הזו — הוא Phase 1 implementation אמיתי,
מתועד בנפרד תחת C179 למטה.

תיעוד-תכנון בלבד, ללא קוד runtime, עבור שלושה PR: **#488** (`CONSUMPTION_ENFORCEMENT_PLAN.md`, תכנון Phase 1, `abf2804`), **#489** (audit עצמאי של Codex — provenance/`FEATURE_AUTO_CAPTURE`/path-validation fixes, `20914f2`), **#491** (`PR2_DETERMINISTIC_APPROVAL_COST_CUTS_PREFLIGHT.md`, `12e2a45`). מתועד במלואו, כולל Cross-Layer Impact Matrix ו-owner decisions, ב-`ROADMAP.md`'s N17 section (items 8–9) — לא משוכפל כאן כדי למנוע היסטוריה כפולה. `core/action_gateway.py`/`app.py` לא שונו ב-PR-ים האלה.

**Merged:** ✅ כן — כל השלושה, מספרי commit לעיל.
**Verified בפרודקשן:** לא רלוונטי — תיעוד/תכנון בלבד.

### C179 — PR #490: Context Librarian Consumption Enforcement, Phase 1 implementation (29/07/2026)
קבצים: `tools/context_librarian/librarian.py`, `tools/context_librarian/__main__.py`, `test_context_librarian.py`, `docs/context_librarian/task_profiles/profiles.json` | קשור: N17 item 10, C178

**Cross-Layer Authority Contract gate:** לא רלוונטי — dev tooling בלבד (`tools/context_librarian/`), ללא production imports, ללא נגיעה בשכבות 1–4.

**PR #490 (ממוזג `7ee5c5b`):** מיישם בדיוק את סעיפים 5.1–5.3+5.5 מהתכנית המאושרת (C178/PR #488): `consumption_checklist()` + סעיף `## Consumption Checklist` חדש בכל bundle; `verify_consumption()` + תת-פקודת CLI `verify-consumption` — fail-closed, מחשב `unreviewed_sources` בעצמו, מוודא identity ברמת top-level+per-item (כולל `production_claim`), דוחה waiver מאושר-עצמית ו-item_id מזויף/כפול/לא-מוכר. שדה אופציונלי `required_for_conclusion`. חמישה profiles קיבלו עדכון `maximum_approximate_token_budget` (מספר בלבד) כדי להכיל את הסעיף החדש. **סקירה עצמאית לפני מיזוג** מצאה ותיקנה 4 פערים אמיתיים ב-`verify_consumption()` המקורי (path/item_id לא-מקושרים, `production_claim` ניתן-לעקיפה, `required_sources` לא-מאומת, item_id לא-מוכר/כפול מתקבל).

**בדיקות:** 35 חדשות (112/112 בסה"כ), `validate`/`smoke_tests.py` נקיים.

**Phase 3 (CI blocking gate + hard-must ב-`AGENT_CONSUMPTION_CONTRACT.md`) במפורש לא מיושם** — ממתין לשימוש ראשון אמיתי ב-Phase 1 לפי סדר ה-rollout של התכנית עצמה.

**Merged:** ✅ כן — PR #490, commit `7ee5c5b`, אומת ב-grep ישיר על `origin/main`.
**Verified בפרודקשן:** לא רלוונטי — dev tooling, לא production runtime.

### C180 — PR #492: PR2 — Deterministic Approval Cost Cuts, implementation (29/07/2026)
קבצים: `app.py`, `core/action_gateway.py`, `core/action_contract_repository.py`, `core/approval_turn_metrics.py` (חדש), `feature_flags.py`, `.env.example`, `test_pr2_deterministic_approval_cost_cuts.py` (חדש), `docs/architecture/f52-unified-approval-runtime/audits/PR2_IMPLEMENTATION_CROSS_LAYER_IMPACT_MATRIX.md` (חדש) | קשור: PR #491 (C178), N17 items 8–10 (C179), F52

**Cross-Layer Authority Contract gate:** רלוונטי — נוגע ישירות בשכבה 4 (Durable Atomic Approval) ובעקיפין בשכבה 2 (TurnCoordinator's de-facto owners, `router.py`/`lead_candidate_handler.py`). Cross-Layer Impact Matrix מלא נכתב, נסקר שכבה-שכבה עם ה-owner, ותועד ב-`PR2_IMPLEMENTATION_CROSS_LAYER_IMPACT_MATRIX.md`.

**PR #492 (`codex/pr2-deterministic-approval-cost-cuts`, ממוזג `db51afc`):** `_resolve_pr2_deterministic_approval()` פותר callback-free approve/reject/pending-query/`יצרת?` לפני Lead Capture, Session, Router, Business Memory, או Agent — snapshot קנוני יחיד של `ActionContracts` שכבר מוקם בתחילת `run_agent`. דקדוק מעוגן חדש (`fullmatch`/lookahead בלבד, לעולם לא substring). דגל חדש `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, כבוי כברירת מחדל, מורכב עם `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` כך ש-PR2 לעולם לא משנה בעלות-תשובה עצמאית. `route_confirmation_word()`/`route_cancellation_word()` קיבלו פרמטרים keyword-only עם ברירת-מחדל משמרת-התנהגות — כל נקודות-הקריאה הישנות לא מעבירות אותם, כך שההתנהגות הישנה (כולל ביטול-כל-האצווה ב-reject עם מספר contracts) נשמרת מבנית ללא תלות בדגל. `find_recent_terminal_by_user(max_age_seconds=...)` מגביל replay ל-24h (`_LIVE_CONTRACT_STALE_SECONDS`), בכוונה לא ל-alias של `find_most_recent_by_user()` הבלתי-מוגבל. `core/approval_turn_metrics.py` חדש — מטריקות request-local (contextvars), observability בלבד.

**תהליך הריויו (ראה `ROADMAP.md` N17 item 11 לפירוט מלא):** נבנה מ-reading pack שנבנה ידנית (לא דרך ה-CLI של C179), נבדק ע"י Claude (3 סטיות מאילוצים מחייבים נמצאו ותוקנו לפני commit), עלה כ-PR, ואז CodeRabbit מצא **7 באגים אמיתיים נוספים** — כולל אחד שביטל בשקט את ה-24h bound עצמו (`recent_terminal or find_most_recent_by_user()` נופל להיסטוריה בלתי-מוגבלת כש-`recent_terminal` הוא `None` מפורש, לא "לא נמסר") — תוקן עם sentinel מפורש (`_TERMINAL_LOOKUP_UNSET`). כל 10 הממצאים תוקנו ואומתו מחדש עצמאית (הרצת טסטים בפועל, לא רק קריאת דוח) לפני המיזוג.

**בדיקות:** `test_pr2_deterministic_approval_cost_cuts.py` (חדש, כולל exact-boundary test עם שעון מבוקר). 10 סוויטות רגרסיה קיימות (confirmation/cancellation/pending-queue/callback/session/PA-01/F52-status/reconfirmation) + `smoke_tests.py` — כולן ירוקות, ללא רגרסיה.

**Merged:** ✅ כן — PR #492, commit `db51afc`, אומת ב-grep ישיר על `origin/main`.
**Verified בפרודקשן:** ⏳ לא עדיין — `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`/`FEATURE_SINGLE_SPEAKER_APPROVAL_UX` שניהם כבויים כברירת מחדל; אין claim ל-staging/production verification.

### C181 — PR #494: PR Hotfix A — Tasks positional canonicalization + confirmation replay guard (29/07/2026)
קבצים: `app.py`, `core/action_gateway.py`, `test_bug_canonical_tool_wiring.py`, `test_pa01_phantom_approval_enforcement.py`, `test_pr2_deterministic_approval_cost_cuts.py`, `docs/architecture/f52-unified-approval-runtime/audits/PR_HOTFIX_A_CROSS_LAYER_IMPACT_MATRIX.md` (חדש) | קשור: PR #492 (C180), staging acceptance audit של PR2

**מקור:** תרחיש staging אמיתי (29/07/2026) שנתפס תוך כדי audit קבלה ל-PR2 — root-caused מלוגי Render בפועל + רשומות `ActionContracts` בבסיס Airtable הראשי, מתואם turn-by-turn.

**PR #494 (`claude/pr2-staging-acceptance-audit-7n9f2p`, ממוזג `186832a`):** שלושה תיקונים ממוקדים. (1) `_sheets_payload_to_airtable()` תמך רק בערך positional אחד ל-Tasks (כותרת) — payload אמיתי עם 2 ערכים (כותרת+תאריך יעד) גרם ל-`CanonicalizationError` שהרג את כל ה-turn בלי ליצור contract; הורחב ל-1 או 2 ערכים. (2) הכשל הזה עדיין נספר נגד תקציב ה-mutation של BUG-122, וחסם ניסיון-חוזר לגיטימי (tool אחר) באותו turn — `_queue_approval_detailed()` תופס `CanonicalizationError` בנפרד (`terminal_outcome=APPROVAL_QUEUE_NEVER_ATTEMPTED`), וה-tool loop לא סופר את זה. (3) `_resolve_pr2_deterministic_approval()`'s בענפי "כן"/"אשר"/"לא"/"דוחה"/"מבטל" עם ללא live contract השתמשו ב-`find_recent_terminal_by_user()` (בהתחלה 24h, בתיקון-ביניים צומצם ל-10 דק') — עדיין שיחזר contract לא-קשור בן ~20 שניות בלבד. תוקן סופית: recency אינה correlation בשום חלון — הענפים האלה לא קוראים ל-`find_recent_terminal_by_user()` כלל יותר; "יצרת?" (שאילתת סטטוס מפורשת) נשאר ב-24h ללא שינוי.

**CI correction (באותו PR, לפני מיזוג):** ה-push הראשון נכשל ב-`backend-ci` — `test_pa01_phantom_approval_enforcement.py` 106/108. שורש: ה-handler החדש ל-`CanonicalizationError` החזיר את שם הכלי הגולמי (טרום-קנוניזציה) במקום לחשב מחדש את השם הקנוני, בניגוד ל-handler הגנרי הסמוך שכבר עושה זאת. אומת כרגרסיה אמיתית (לא קיימת ב-`origin/main`) ע"י הרצת אותו קובץ טסט מול worktree מבודד. תוקן; assertion אחד (P1-2) עודכן לצפות ל-`APPROVAL_QUEUE_NEVER_ATTEMPTED` המדויק יותר במקום ה-`APPROVAL_QUEUE_ORPHANED` הישן.

**Cross-Layer Authority Contract gate:** מלא — `PR_HOTFIX_A_CROSS_LAYER_IMPACT_MATRIX.md` נכתב אחרי המיזוג (4 שכבות × 9 שדות, proof-of-non-impact לשכבות 1/3, וסעיף RP5 guard — ממצא: `CanonicalizationError` מסווג כעת `record_verification("failed",...)` במקום `record_unverified_effect()` ב-`core/turn_evidence.py`'s shadow classification — מדויק יותר, לא רגרסיה; `core/turn_evidence.py` עצמו לא עושה pattern-match על מחרוזות `terminal_outcome`, מאומת ב-grep).

**בדיקות (לפני המיזוג):** 175/175 `test_*.py`, `smoke_tests.py`, `test_integration.py`, `core/router/test_router.py` (44/44), `py_compile` — כולם ירוקים.

**CodeRabbit (סבב נוסף, לא תוקן ב-PR זה):** ממצא actionable אחד — מסלול cancel ישן (`app.py:3391`, BUG-056, פעיל כברירת מחדל כש-PR2 כבוי) עדיין לא מעביר `recent_terminal=None`, אותה מחלקת-באג בדיוק. Nitpick אחד — ולידציית פורמט תאריך-יעד חסרה. שניהם נדחו במכוון לפר הבא, יחד עם Router regex ל"תייצר", אכיפת Single-Speaker בפועל (`is_gateway_owned_leak` היום log-only), והסתרת `sheets_append`/`drive_*` מרשימת הכלים כברירת מחדל.

**✅ Verified ב-staging (29/07/2026, `my-bot-jqz2.onrender.com`, contract `a428e48b-3b57-473a-b647-e8225e08d3b6`, 14:25–14:29):** נבדק ידנית ע"י הבעלים עם `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`/`FEATURE_SINGLE_SPEAKER_APPROVAL_UX` מופעלים ידנית. **חשוב — זו לא שחזור מדויק של האירוע המקורי, אלא רצף קרוב-אך-שונה, ומתועד ככזה:**

- **הרצף המקורי (29/07/2026 10:49–10:53, המתועד ב-C181's root cause למעלה):** `CanonicalizationError` → **אף `ActionContract` לא נוצר בכלל** → אין live contract, אין גם terminal contract חדש → "כן" בלי live contract חייב לא לשחזר contract ישן/לא-קשור. זה מה שתיקון #1+#3 נועדו למנוע.
- **הרצף שנבדק עכשיו (14:25–14:29):** בקשת "צור משימה לא באיירטאבל" → ה-Agent בחר `calendar_create_event` (לא `airtable_add`/`sheets_append` — לא אותו קוד-נתיב של תיקון #1 בכלל) → `ActionContract` **כן נוצר** (`a428e48b`, status=pending) → אושר ע"י הבעלים → **הביצוע עצמו נכשל** (`❌ חסרים פרטי Google OAuth` — סביבה בלי OAuth מוגדר, לא קשור לקוד) → status סופי = `failed`. בקשת "כן" הבאה, בלי live contract (כי `failed` הוא terminal, לא live), החזירה נכון "אין פעולה שממתינה לאישור" — **לא שחזרה את ה-contract הכושל**.

מה שהרצף הזה **כן** מאמת: אינווריאנט תיקון #3 (bare "כן" בלי live contract לעולם לא משחזר terminal contract, יהיה מקור הכשל אשר יהיה — `CanonicalizationError`/`failed`/כל דבר אחר) — זה בדיוק ההתנהגות שנבדקה, בנתיב-כשל **שונה** מהמקורי אבל תחת אותו contract שנבדק (`build_approval_lifecycle_result(canonical_state="no_contract")`). מה שהרצף הזה **לא** מאמת עצמאית: תיקון #1 הספציפי (positional canonicalization ל-Tasks עם 2 ערכים) — לא נצפה `CanonicalizationError` ברצף הזה כי ה-Agent כלל לא בחר `sheets_append`/`airtable_add` הפעם.

**תוספת (30/07/2026) — אימות חי נוסף, שלושת הדגלים (`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`/`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`/`FEATURE_ACTION_GATEWAY`) פעילים בפרודקשן:** בקשה אמיתית — "צור משימה באיירטאבל: להתקשר לספק, עד יום חמישי" — יצרה `ActionContract` (`tool=airtable_add`, `table=Tasks`, `status=pending`) עם כותרת ותאריך יעד נכונים, **ללא `CanonicalizationError`**. המסלול העסקי המלא (זיהוי כוונה → יצירת contract → אישור/ביטול) עבר קצה-לקצה בפרודקשן בפעם הראשונה. **הפער שנשאר פתוח, זהה במהותו לזה שתועד ב-29/07:** ה-Agent בחר `airtable_add` ישירות ולא `sheets_append`, כך שתיקון #1 הספציפי (`_sheets_payload_to_airtable()`'s תמיכת 1-או-2-ערכים positional) עדיין לא נצפה חי בנתיב-הקוד המדויק שלו — נשאר מאומת בבדיקת יחידה בלבד. פירוט מלא: `BUG_AUDIT_LOG.md` BUG-151 (תוספת 30/07/2026).

**ממצא נלווה (לא מתוקן, לא באחריות PR זה):** לאחר ביטול המשימה בסבב הבדיקה הזה, בקשה חדשה דומה נעצרה פעם אחת ע"י ה-Agent ורק בשליחה חוזרת נוצר כרטיס אישור. נרשם בנפרד — ראו `BUG_AUDIT_LOG.md` BUG-152 (חדש, 🔴 לא root-caused).

**Merged:** ✅ כן — PR #494, commit `186832a`, אומת ב-grep ישיר על `origin/main` (`APPROVAL_QUEUE_NEVER_ATTEMPTED`, `len(row_data) not in (1, 2)`).
**Verified בפרודקשן:** חלקי — עודכן 30/07/2026. תיקון #3 (guard ה-replay) ✅ אומת בפרודקשן (ראו BUG-151 תוספת, וגם C183 למטה). **היכולת העסקית הכללית** (יצירת Tasks עם תאריך יעד, קצה-לקצה) ✅ אומתה בפרודקשן 30/07/2026 (תוספת למעלה) — **אך זו לא** אימות של תיקון #1 (הממיר) או תיקון #2 (חריגת mutation-budget), ששניהם דורשים `CanonicalizationError` בפועל כדי להיבדק, וזה לא קרה בסבב הזה. **הפער היחיד שנשאר:** הממיר `_sheets_payload_to_airtable()`'s תמיכת 1-או-2-ערכים positional (תיקון #1 בבידוד המדויק) לא נצפה חי — ה-Agent לא בחר `sheets_append` באף אחד משני סבבי הבדיקה (29/07, 30/07). נשאר מאומת בבדיקת יחידה בלבד עד שתרחיש חי יגרום ל-Agent לבחור `sheets_append` בפועל.

### C182 — PR #496: Hotfix B — legacy cancel-word replay guard + due-date validation (29/07/2026)
קבצים: `app.py`, `core/action_gateway.py`, `test_*.py` (רגרסיה) | קשור: PR #494 (C181), staging acceptance audit של PR2

**PR #496 (ממוזג `3dcf0ab`):** שני תיקונים שנדחו במכוון מ-PR #494 (C181) לפר נפרד. (1) ממצא CodeRabbit — מסלול cancel ישן (`app.py:3391`, BUG-056) השאיר את `recent_terminal` בברירת-המחדל שלו, שנופל ל-`find_most_recent_by_user()` הבלתי-מוגבל — אותה מחלקת-באג בדיוק ש-BUG-151/PR #494 תיקן לענפי הרזולבר הדטרמיניסטי של PR2. תוקן: `recent_terminal=None` מועבר במפורש. (2) nitpick — ולידציית פורמט תאריך-יעד חסרה ב-`_sheets_payload_to_airtable()`.

**הערה חשובה, זוהתה 30/07/2026 בעת סבב אימות חי:** המסלול הישן ב-`app.py:3391` נגיש **רק** כש-`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` ו/או `FEATURE_ACTION_GATEWAY` כבויים — `_resolve_pr2_deterministic_approval()` (`app.py:2858-2860`) מיירט כל מילת אישור/ביטול חופשית *לפני* המסלול הישן כששני הדגלים דלוקים, כפי שהם היום בפרודקשן. כלומר התיקון הזה הוא **fallback רדום** במצב הדגלים הנוכחי — אינו ניתן לאימות חי במובן משמעותי בלי לכבות דגל זמנית.

**בדיקות:** `test_bug056_legacy_cancel_replay_guard.py` (חדש) — מכסה ישירות את נקודת-הקריאה הזו. Full sweep ירוק.

**Merged:** ✅ כן — PR #496, commit `3dcf0ab`, אומת ב-grep ישיר על `origin/main`.
**Verified בפרודקשן:** לא רלוונטי כרגע — המסלול רדום כל עוד `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`/`FEATURE_ACTION_GATEWAY` דלוקים (מצב נוכחי, אומת ע"י הבעלים 30/07/2026). **Verified by test:** ✅ כן.

### C183 — PR #497: Hotfix E — shared replay-policy correction (29/07/2026), ✅ Verified בפרודקשן (30/07/2026)
קבצים: `core/action_gateway.py`, `app.py`, `test_hotfix_e_shared_replay_policy.py` (חדש) | קשור: PR #494 (C181), PR #496 (C182)

**PR #497 (ממוזג `7dd64a1`):** `describe_no_pending_reason()` הצטמצם ל-אחריות יחידה — תשובת no-pending קנונית, אפס שאילתת ledger. `describe_superseded_reason()` (חדש, צר) שימר את BUG-PENDING-APPROVAL-B's "הפעולה הקודמת בוטלה כי התחלת פעולה אחרת" — נקרא מפורשות ע"י שני קוראים (Stage A fallback, `route_confirmation_word()`), עם fallback ל-`describe_no_pending_reason()`. שלושת הקוראים (`route_confirmation_word()`, `describe_pending_queue()`, Stage A fallback) עברו audit מלא לפני commit, כולל דוח "Return before commit" בן 7 סעיפים לפי דרישת הבעלים.

**CodeRabbit (באותו PR, לפני מיזוג):** מצא ותיקן ממצא Major אמיתי — `describe_superseded_reason()` עצמו היה ללא הגבלת-גיל (unbounded), אותה מחלקת-באג בדיוק ש-Hotfix E כולו נועד לבטל, רק ממוקדת בסטטוס אחד. תוקן: `_SUPERSEDED_REASON_MAX_AGE_SECONDS = 24h`.

**בדיקות:** `test_hotfix_e_shared_replay_policy.py` — 56/56. Full sweep ירוק.

**Merged:** ✅ כן — PR #497, commit `7dd64a1`, אומת ב-grep ישיר על `origin/main`.
**✅ Verified בפרודקשן (30/07/2026):** הבעלים שלח "כן" בלי live contract — תשובה: "אין פעולה שממתינה לאישור" (המחרוזת הקנונית המדויקת), עם הוכחות לוג: `contract_reads=1`, `agent_calls=0`, `deterministic=True`, `action=discard_no_promotion`. מאמת ישירות את הפירוק ל-`describe_no_pending_reason()` ההיסטוריה-עיוורת — אין שחזור של contract ישן/לא-קשור.

### C184 — PR #498 + PR #499: Hotfix C — "תייצר" verb recognition for CREATE_TASK, ✅ Verified בפרודקשן (30/07/2026)
קבצים: `core/router/intent_router.py`, `test_hotfix_c_create_task_verb.py` (חדש) | קשור: staging acceptance audit של PR2 ("פתוח לפר הבא" ב-C181)

**PR #498 (ממוזג `850a575`):** הוסיף את הפועל "תייצר" לקבוצת הפעלים של כלל ה-CREATE_TASK ב-`intent_router.py` — "תייצר משימה..." היה נופל ל-`Intent.UNKNOWN` קודם. שינוי מכוון (regex יחיד + הערה), ללא הרחבת נטיות נוספות, ללא נגיעה ב-CREATE_EVENT/CREATE_LEAD/tool exposure/ActionGateway.

**PR #499 (ממוזג `b872e46`, follow-up לממצאי CodeRabbit על PR #498 שהגיעו אחרי המיזוג):** שני תיקונים — (1) תרגום ההערה החדשה לעברית (מוסכמת המאגר). (2) ממצא Functional Correctness אמיתי — "תייצר" ללא `\b` תפס גם נטיות ארוכות יותר ("תייצרי") בניגוד ל"exact verb only" שהתגובה טענה. תוקן: `\b` סביב "תייצר" בלבד (לא סביב שאר ארבעת הפעלים בקבוצה — שומר על ההתנהגות הקיימת שלהם ללא שינוי).

**בדיקות:** `test_hotfix_c_create_task_verb.py` — 12/12 (11 + בדיקת ה-`\b`). `core/router/test_router.py` — 44/44 (רגרסיה). Full sweep ירוק שני הפעמים.

**Merged:** ✅ כן — PR #498 (`850a575`) + PR #499 (`b872e46`), שניהם אומתו ב-grep ישיר על `origin/main`.
**✅ Verified בפרודקשן (30/07/2026):** הבעלים שלח "תייצר משימה לבדוק את הדוח החודשי" — לוג הראה `intent=create_task confidence=0.95` דרך הכלל `(פתח|צור|\bתייצר\b|הוסף|תוסיף).*(משימ|טאסק|task)` (מוודא שהגרסה הפרוסה היא זו של PR #499, עם ה-`\b`, לא רק PR #498), ונוצר `ActionContract` תקין (`tool=airtable_add`, `table=Tasks`, `status=pending`).

---

## Core Program Status Update — 10/08/2026

Deploy gap closure and runtime verification for TC8/TC9/Track D/RP5.

### C185 — PR #585: TC8 durable turn-state, ✅ DEPLOYED (03:56 UTC 10/08/2026)
**Merged:** ✅ כן — PR #585, commit `a945ee7`, אומת ב-grep ישיר על `origin/main`.
**Deployed:** ✅ כן — Render event log, auto-deploy (08:32–03:56 UTC 10/08/2026), live for `a945ee7` (TC8) confirmed 03:56 UTC.
**WIRED:** ✅ כן — מחובר ב-4 נקודות בקוד (approve/reject/cancel text & callback) ב-`app.py:3110/3134/3350/3372/4127/4143/4230/4248`, no feature flag. `_tc8_claim_contract()` / `_tc8_finish_contract()` קרויות unconditionally.
**Runtime Verified:** ❌ לא עדיין — DEPLOYED כן, אך אין ייצוא Render log עדכני לאחר ה-deployment (חלון ה-09/08 audit קדם לפריסה). צריך ייצוא Render טרי שמראה בפועל `[TC8]` מסגים/סטייג'ינג אחרי 03:56.

### C186 — PR #588: TC9 MessageContract wiring, ✅ DEPLOYED (08:32 UTC 10/08/2026)
**Merged:** ✅ כן — PR #588, commit `cec3f83`, אומת ב-grep ישיר על `origin/main`.
**Deployed:** ✅ כן — Render event log, auto-deploy (rollback+redeploy 03:58→08:32 UTC 10/08/2026), live for `cec3f83` confirmed 08:32 UTC.
**WIRED:** ✅ כן — `_message_contract_for_fact()` בנוי unconditionally ב-`ActionGateway.compose_status_reply()` (~3483). טקסט ה-user קשור לנקודות output-gate בעבור `FEATURE_UNIFIED_STATUS_FORMATTER` (כבוי). `GatewayReply.contract` שדה קיים, כרגע אין קוראים downstream.
**Runtime Verified:** ❌ לא עדיין — DEPLOYED כן (08:32), אך אין ייצוא Render log עדכני שמראה בפועל בנייה/מזגי TC9 אחרי ה-deployment.

### C187 — PR #580: Track D observability (RuntimeSchemaProvider/IngressEnvelope), MERGED + WIRED (DEPLOYED verification pending)
**Merged:** ✅ כן — PR #580, commit `f38c5e4` (09/08/2026), אומת ב-grep על `origin/main`.
**WIRED:** ✅ כן — `_log_result()` static method ב-`core/runtime_schema_provider.py` emits `[RuntimeSchemaProvider] result table=... source=... mode=...` unconditionally לכל 4 sources (live/cached/snapshot/seed). `[IngressEnvelope]` marker emitted ב-2 בנייה נקודות ב-`app.py:3631`. Code-tested ✅ (`test_runtime_schema_provider.py`).
**Deployed:** ❌ לא עדיין — PR merged to `main` אבל commit שלו לא נכנס עדיין לפריסה אחת שהיא "live". הפריסה אחרונה (`08:32`) היא `cec3f83` (TC9), שקודם ל-`f38c5e4`.
**Runtime Verified:** ❌ לא עדיין — צריך deploy + ייצוא Render log שיראה את הסימנים החדשים בפועל.

### C188 — PR #579: TC7/RP5 execution-shadow wiring, MERGED + WIRED, RUNTIME VERIFIED shadow (09/08/2026 audit)
**Merged:** ✅ כן — PR #579 (supersedes #576), commit `2603b44`, אומת ב-grep על `origin/main`.
**WIRED:** ✅ כן — `project_evidence_result()` קרוי מ-`_persist_execution_status()` ב-`core/action_gateway.py`, gated by `get_evidence_finalizer_state() in ("shadow","enforce")`. `FEATURE_EVIDENCE_FINALIZER` code default OFF.
**Deployed:** ✅ כן — Render live per `RUNTIME_CAPABILITY_AUDIT_20260809.md` (09/08/2026 evidence from Production/Staging logs, spanning 2026-08-02–09/08). Log entries `[EvidenceFinalizerShadow] state=shadow` observed בפרודקשן ובסטייג'ינג.
**Runtime Verified:** ✅ SHADOW VERIFIED — ראיות log אמיתיות שצפו בשני environments. זו RP4 shadow-comparison logging (לא claim-authorization enforcement). **Blocker for RP5 enforcement:** לא "להדליק shadow" (כבר בפעולה עם ראיות production אמיתיות), אלא לאסוף דוגמאות sufficient מ-B2/B3 classification states כדי להרשות החלטת enforcement — מעבר מ-shadow-only לשינוי `final_reply` בפועל. דורש ניטור operator מתמשך + אישור ממצא לפני שPR יישום RP5 יוכל להתחיל.

### C189 — PA-01 Task Deterministic Paths (UPDATE_TASK/COMPLETE_TASK), clarification & status correction
**Builders/Registry/Wiring Status:** קוד ממשי קיים וכן ממוזג (PR #564/#565/#567 core/router/): `build_update_task_proposal()` / `build_complete_task_proposal()` קיימים ב-`core/router/task_builders.py`; `prepare_task_proposal()` integration ב-`core/router/task_integration.py`; `TASK_OWNERSHIP` registry ב-`core/turn_coordinator_runtime.py` + `gateway_call()` wiring; `_queue_deterministic_task_update()` ב-`app.py:1045` + קריאה אמיתית `app.py:4369`.
**Merged:** ✅ כן — (כל הקוד) יחידים, אומתו ב-grep על `origin/main`.
**Gap הנשאר (לא "אין קוד"):** Router.py line 248–254 קובע `Handler.TOOL` רק עבור `Intent.CREATE_TASK` (דטרמיניסטי). עבור `Intent.UPDATE_TASK`/`COMPLETE_TASK` אין כלל-קלאסיפיקציה דומה ב-router — שום מקום לא משדרג להם `Handler.TOOL`, כך שהעצמה המחוברת ב-`app.py:4369` לעולם לא מגיעה מ-route החי. `RUNTIME_CAPABILITY_AUDIT_20260809.md` מאשר: Staging UPDATE_TASK observed with `handler=agent` (לא TOOL); COMPLETE_TASK אין ראיות חדשות.
**Required Fix:** הוסף כלל-דטרמיניסטי ב-`core/router/router.py` (מקביל ל-CREATE_TASK במקום 254) שקובע `Handler.TOOL` עבור UPDATE_TASK/COMPLETE_TASK — תלוי על התנאים (intent match + role/domain gates + capable-this-turn check).

---

## Gap Summary (10/08/2026 close)

**Closed:**
- TC8 DEPLOYED ✅ (Render 03:56, 10/08)
- TC9 DEPLOYED ✅ (Render 08:32, 10/08)
- RP5 RUNTIME VERIFIED shadow ✅ (09/08 audit with production evidence)

**Still Open:**
- TC8/TC9/Track D RUNTIME VERIFIED (need fresh Render export post-deploy)
- RP5 enforcement/RP5 full (not just shadow) — blocked on sufficient production sample accumulation across B2/B3 classification states + owner authorization before enforcement implementation PR
- PA-01 UPDATE/COMPLETE handler routing (router.py gap)
- F52 PR1/PR4/PR5/PR6/Lane-A Cross-Layer Impact Matrix compliance (structural gap)


### C190 — Canonical CORE Completion Audit (10/08/2026)
The final CORE Completion Audit is canonicalized at
`docs/audit/CORE_COMPLETION_AUDIT_20260810.md`, based on main
`134148e42e1c15975858b58f5c22c3a512846129`.

**Final verdict:** CORE COMPLETION AUDIT — PASS WITH NON-BLOCKING DEFERRED ITEMS;
CORE v1 — COMPLETE; CORE v1 — READY TO FREEZE. Freeze remains an
owner/governance decision. This entry supersedes earlier current-status
snapshots where their deployment or PA-01/TC8/TC9/Track D wording predates the
final audit; those entries remain historical evidence.

### C191 — PR #598: D1 canonical `recruitment` domain across adapters, MERGED + WIRED (11/08/2026)
Business Memory adapter now emits live lowercase `recruitment`; legacy
`Recruitment` reads remain accepted for backward compatibility. Wired through
routing, identity, weekly summary, and Lead Event writing (11 files,
+327/-14). Qualifies as consequential: changes a canonical value across
multiple subsystems (routing/identity/memory/lead-event authority
boundaries), not a routine UX/cosmetic change. **Merged:** ✅ yes, ancestor of
`origin/main`. **Deployed/Runtime Verified:** not independently checked by
this entry — PR body cites live read-only Airtable verification
(`Marketing Demand.Domain`, `TRAFFIC_SOURCES.Suitable Domains`, `Business
Memory.Domain` all show `recruitment`) plus 4 test suites (10/24/50/50 pass).

### C192 — PR #623: BUG-164 PR1 Authority/Foundation, MERGED, NOT WIRED (14/08/2026)
Adds `marketing_fact_authority.py` (`ProtectedFact`), `marketing_creative_templates.py`
(closed template registry), `marketing_creative_renderer.py`
(`CreativeProposal`) — new authority/rendering modules for the BUG-164 fix
line. Qualifies as consequential: establishes a new canonical-contract
pattern for marketing creative content. **Merged:** ✅ yes (3 commits:
`f8c6332`, `4210acf`, `1066762`). **Wired:** ❌ no — verified by direct grep,
zero callers outside test files; `cmd_marketing.py::_create_demand_and_generate_ideas()`
(the actual BUG-164 code path) is untouched. Foundation existence ≠ live fix;
see `BUG_AUDIT_LOG.md::BUG-164`.

### C193 — PR #634/#638: Context Librarian Reconciliation engine + CI baseline unblock, MERGED + WIRED, CI CURRENTLY RED (14/08/2026)
PR #634 (`feat/context-librarian-reconciliation`) adds a new, separate GitHub
Actions workflow (`context-librarian-reconcile.yml`, distinct from the
pre-existing in-`ci.yml` "Context Librarian authoritative post-merge
reconciliation" step) plus crash-recovery idempotency for its maintenance-PR
flow. PR #638 (`ci/baseline-unblock`) pins a freshness-state fixture.
Qualifies as consequential: new governance/CI automation touching the
Context Librarian catalog-freshness gate. **Merged:** ✅ yes, both ancestors
of `origin/main`. **Wired:** ✅ yes, runs on every push to main. **Current
state (verified against `origin/main` @ `904ce13b`):** both the "CI"
workflow and the new "Context Librarian Reconciliation" workflow are
**currently failing** at the exact integration-cut commit — **not caused by
PR #634/#638 themselves**; root-caused to 5 sources unregistered in the
catalog, all introduced by C192 (PR #623) and the tool-runtime-snapshot work
(PR #640) — see `docs/audit/CORE_COMPLETION_AUDIT_20260810.md` addendum and
`AI_CONTEXT.md` §1/§2/§4 for the exact list. Fix is catalog registration, an
owner decision, not a code change — out of scope for this documentation-only
documentation-only pass.

### C194 — MY-WORK-1: Owner linked-record root-cause fix (My Work + Lead Detail), PARTIALLY MERGED (20/08/2026)
Root cause of the My Work screen always showing zero tasks: `Tasks.Owner` /
`Leads.Owner` are `multipleRecordLinks` fields pointing at a `Profile`
team-roster table (verified via Airtable MCP, 19/08/2026), not plain text as
every prior read/write site assumed — compounded by a case mismatch
(`Profile.name` = `"Eliyahu"` vs. `identity.user_id` = `"eliyahu"`) that
would have broken even a naive string filter. Live Airtable check at
discovery time: 0 of 121 Tasks and 0 Leads had `Owner` populated.

**Merged:**
- **PR #766** (branch `my-work-1d`, cherry-pick of `f6d0aff` after PR #760
  was merged mid-session without this fix) — read-path fix
  (`_resolve_profile_record_id()` + linked-record-aware
  `_process_owner_tasks()`) and write-path fix (`create_lead_task()`
  defaults a new task's Owner to the creator's resolved Profile record when
  the source Lead has none). Merge commit `df107a4`.
- **PR #770** (branch `my-work-1e`) — unowned-task fallback: a Task with no
  Owner link at all now defaults to the requesting (sole) owner in the My
  Work read path, instead of requiring a backfill of the 121 pre-existing
  Owner-less Task records. Owner-approved policy (20/08/2026): unowned
  records default to the sole owner unless/until an explicit other owner
  exists. Merge commit `f647586`, mergedAt `2026-08-20T00:04:25Z`.
  **Runtime verified:** production My Work screen went from 0 immediate/0
  upcoming to 19 immediate + 77 upcoming real tasks after this deploy —
  confirmed by the owner directly against the live TMA screen.

**Open, not yet merged:**
- **PR #788** (branch `my-work-1f`) — resolves `Leads.Owner` linked-record
  IDs to a display name in `GET /api/leads/<id>` (previously returned raw
  `recXXX` IDs; the frontend already defended against this with a generic
  placeholder, so this was a display-quality bug, not a crash). Latent —
  0 Leads currently have `Owner` set in production, so not yet visible to
  any user. See `BUG_AUDIT_LOG.md::BUG-166`.

**Consequential because:** corrects a canonical field-type/contract
assumption (Owner treated as plain text) that silently broke a live
production feature end-to-end, plus establishes an explicit, owner-approved
default-ownership policy for unowned records — not a routine UX/cosmetic
change.

### C195 — Governance/Horizon refresh against `origin/main` `6a0ba6a` (21/08/2026)

Documentation-only governance reconciliation for the owner's requested Track D
workstream. Updates `AI_CONTEXT.md`, `ROADMAP.md`, and
`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` to reflect that main advanced
materially beyond the older 16/08–20/08 planning snapshots.

**Status changes recorded:**
- H6 Command Center is no longer `PLANNED`: owner read API/UI, owner attention,
  owner development projection, and registry projection are merged; the remaining
  gate is deployed-SHA/runtime verification plus the known `system_health`
  attention-source hygiene issue.
- H1/N18 Canonical Write Infrastructure is active: Lead is now the first
  consumer of shared write primitives, not a separate one-off Lead system.
- H4 Media/Gateway progressed through staging-gated MPT, Media Probe POC,
  Artifact Contract v1, StoredArtifact MIME, Gateway readiness, and fail-closed
  gateway canary harness; still not production-activated.

**Scope boundary:** Governance files only. No runtime, UI, media, API, schema,
or test implementation files changed. This preserves the four-agent split where
Track D owns status/decision documents and other tracks own verification,
Command Center runtime/UI, and Media/Gateway implementation.
