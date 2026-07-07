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
- **Requirement:** `docs/f52/F52_CURRENT_TOOL_MAP.md` §"Safe No-Brainer Refactors" #4, #6, #7.
- **Commit:** `0695b11`, `2ae6b0c`
- **PR:** #207 — מוזג (`22b2f74`)
- **Review על ידי:** —
- **Deploy תאריך:** —
- **Verified בפרודקשן:** לא
- **Verification ראיה:** Pre-implementation gate (§0 of the task SPEC) re-ran the F52 audit greps against the live repo and found the SPEC's claimed baseline did not match reality on either #6 or #7: `cmd_decision.py:806` has no `httpx` call at all (goes through `airtable_create`); `tools/telegram_adapter.py`/`app.py`/`google_tools.py`/`email_inbound.py`/`knowledge_engine.py`/`survey_worker.py` contain none of the `"✅" in result`/`rec\w+` anti-pattern (telegram_adapter.py already uses a structured `ActionResult`/`delivery_success` bool). Corrected baselines were derived by actually running the new scanners against the repo and cross-checking against `docs/f52/F52_BYPASS_MAP.md`. `tools/audit_gateway_bypass.py` (24 known Airtable-bypass call-sites, 2 write/22 read) and `tools/audit_result_parsing.py` (21 known false-success text-parsing occurrences across 12 files) both self-test clean and report 0 new / 0 resolved against their baselines on the current repo. `core/last_tool_result_shadow.py` (RAM-only, TTL-bounded dataclass recorder) wired passively into `tools/dispatcher.py`'s existing `finally:` clause (source=`agent_tool`) and `tma_api.py`'s `_at_patch`/`_at_post` (source=`tma_route`) — manually verified with the flag on vs off that `dispatch_tool()`'s return value is byte-identical either way. `FEATURE_LAST_TOOL_RESULT_SHADOW` confirmed default-off (not in `feature_flags._DEFAULTS`). All 30+ `test_*.py` scripts, `smoke_tests.py`, `test_integration.py`, and `core/router/test_router.py` pass unchanged; `python -m compileall -q .` clean. Zero `app.py` changes. Both new audit scripts added to `.github/workflows/ci.yml` as warning-only steps (`|| true`), matching the existing `schema_governance.py` pattern.
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
- **Docs עודכנו:** `docs/f52/F52_BYPASS_MAP.md`, `BUG_AUDIT_LOG.md`
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
- **תיאור:** 4 מסמכי audit ב-`docs/f52/` שמתעדים את ארכיטקטורת הכלים הקיימת לפני כל refactor: `F52_CURRENT_TOOL_MAP.md` (מפת כלים נוכחית), `F52_CONTRACT_COVERAGE_MAP.md` (כיסוי חוזה C53-A), `F52_BYPASS_MAP.md` (קטגוריות bypass + bypasses בסיכון גבוה), `F52_STATE_FLOW_MAP.md` (מפת זרימת state). Scope guard מפורש בכל 3 ה-PRs: אין שינוי `app.py`, אין refactor, אין שינוי סכמת Airtable.
- ⚠️ **רשומה זו נוספה בדיעבד** — F52 מוזג כבר ב-3 PRs נפרדים בלי שנפתחה רשומת CHANGE_CONTROL_LOG ייעודית בזמן המיזוג (רק עדכון ROADMAP.md חלקי, שגם הוא היה חסר את הקובץ הרביעי — תוקן באותו commit כמו רשומה זו). אותר ע"י audit יומי (סשן `claude/gifted-clarke-ajyjsa`, 26/06/2026).
- **Commit:** `6afc393` (PR #153) / `84762f0` (PR #155) / `4b0f5d3` (PR #156)
- **PR:** #153 (merge `0ffdc7c`), #155 (merge `d57f405`), #156 (merge `64a018b`) — **כל השלושה מוזגו ל-`main`**, אומת עצמאית דרך `git merge-base --is-ancestor` על כל אחד מ-3 ה-commits
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא רלוונטי — מסמכי תיעוד בלבד, אין קוד לפרוס
- **Verified בפרודקשן:** לא רלוונטי — אין קוד/התנהגות לאמת
- **Verification ראיה:** `ls docs/f52/` מאשר קיום 4 הקבצים בפועל על דיסק; `git merge-base --is-ancestor` אישר שלושת ה-commits כ-ancestors של `origin/main`
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
`_AMBIGUOUS_PHRASES` מזהה כעת גם ביטויים דו-משמעיים עם prefix טבעי ("אני צריך למלא משימות", "צריך סטטוס" וכו') ולא רק גרסאות חשופות (BUG-048/BUG-IC-01) — מנתב ל-`Handler.CLARIFY` במקום Agent עם כלים מלאים. 44/44 בדיקות.
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
**Merged:** כן (`32bbb75`, merge commit `194b3da`, PR #255) | **Verified בפרודקשן:** לא עדיין

### C98 — BUG-079: `/update` שלב הטקסט החופשי מגיע ל-`capture_text` במקום לברוח ל-`run_agent` (07/07/2026)
קבצים: `app.py`, `cmd_update.py` | PR #256 | באג: BUG-079
`app.py` קורא ל-`bot.process_new_updates()` (מפעיל `capture_text` ודומיו) רק כש-`text.startswith("/")` — טקסט חופשי במהלך `/update` המשיך ישר ל-`idempotency.is_duplicate()` ואז ל-`run_agent()` הכללי, מבלי ש-`capture_text` ירוץ אף פעם. פוגע בתרחיש הראשי (לא רק edge-case) של `/update` מאז שנוסף. נוסף `cmd_update.has_pending_text_capture()`, נבדק ב-`app.py` מיד אחרי בלוק ה-slash-command ולפני idempotency (fail-open) — אם `/update` ממתין בשלב `text`, ה-webhook קורא ל-`bot.process_new_updates()` בעצמו. smoke/integration (4/4)/router (44/44) ירוקים + טסט ידני מבודד על מעברי שלב.
**Merged:** כן (`912b94e`, merge commit `baa0283`, PR #256) | **Verified בפרודקשן:** לא עדיין

### C99 — חילוץ טקסט ממסמך (docx/csv/xlsx/txt/html) שנשלח באמצע `/update` (07/07/2026)
קבצים: `media_handler.py` (חדש: `extract_text_if_document`), `cmd_update.py` | PR #257
מסמכים שנתפסו ע"י `capture_photo_or_document` (C97) נשמרו רק עם caption+drive_url — התוכן עצמו מעולם לא נקרא, אז docx/csv/xlsx שצורף לעדכון עסקי לא נשא שום מהתוכן שלו ל-Business Memory. `media_handler.extract_text_if_document(file_bytes, mime_type)` עוטף את `document_converter.convert_document()` הקיים (temp-file+ניקוי+טיפול כשלים בפנים — פורמט לא נתמך/כשל המרה מחזירים `None`, לא raise). `capture_photo_or_document` קורא לזה עבור document בלבד, משלב את הטקסט שחולץ ל-`raw_text` לצד caption+drive_url הקיימים. אין שינוי ל-API הציבורי של `document_converter`. smoke/integration (4/4)/router (44/44)/`test_document_converter.py` (6/6) ירוקים + טסטים ידניים (mime לא-נתמך→`None`, txt תקין→טקסט, docx פגום→`None` בלי exception, אין קבצים זמניים שנשארים).
**Merged:** כן (`3d69609`, merge commit `caef337`, PR #257) | **Verified בפרודקשן:** לא עדיין

### C100 — BUG-080: שדות Date-בלבד ב-Airtable מקבלים ערך date בלבד, לא datetime מלא (07/07/2026)
קבצים: `cmd_update.py`, `media_handler.py`, `cmd_decision.py` (7 נקודות כתיבה בסה"כ) | PR #258 | באג: BUG-080
`BusinessMemoryFields.DATE`/`DecisionEventFields.EVENT_DATE`/`DecisionInboxFields.RECEIVED` הם שדות `Date` בלבד ב-Airtable (`datetime_fields: []`, אומת מול live field-type metadata), אבל כל 7 נקודות הכתיבה שלחו `datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()` — מחרוזת עם שעה/מיקרושניות/offset, נדחית ב-422 (אין `typecast=true` בגייטוויי). שונה ל-`.date().isoformat()` בכל 7 המקומות; שלושה מקומות דומים נבדקו ונשארו ללא שינוי במפורש (2×`FileUploadResult(timestamp=...)` — אובייקט session_store בזיכרון לא Airtable, ו-1× שימוש read-only כמפתח מיון). smoke/integration (4/4)/router (44/44)/`test_decision_attention.py` (11/11)/`test_core_reasoning.py` (59/59) ירוקים.
**Merged:** כן (`02bc343`, merge commit `a8ffa07`, PR #258) | **Verified בפרודקשן:** לא עדיין

### C101 — BUG-081: Business Memory `Domain` נכתב לשדה הייעודי, לא "ממוחזר" לתוך `Tags` (07/07/2026, 3 PRs)
קבצים: `airtable_schema.py` (חדש: `BusinessMemoryFields.DOMAIN`), `cmd_update.py` (חדש: `normalize_business_memory_fields`), `media_handler.py` | PR #259, #260, #261 | באג: BUG-081
`BusinessMemoryFields` לא היה לה שדה `Domain` ייעודי (בניגוד לכל טבלה אחרת בסכימה) — `cmd_update.py`/`media_handler.py` כתבו את מפתח ה-domain הגולמי (למשל `"media"`) ישירות ל-`Tags` הכללי, בלי אימות מול live options; אין `typecast=true` → 422 על ערך לא-קיים. **PR #259:** נוסף `BusinessMemoryFields.DOMAIN`; `normalize_business_memory_fields()` ממפה domain→ערך Domain מאומת (`_DOMAIN_TO_AIRTABLE`) ומסננת `Tags` לערכים חוקיים בלבד (`_VALID_TAGS`). **PR #260:** תוקן `_DOMAIN_TO_AIRTABLE["real_estate"]` מ-lowercase (שגוי, נמחק בניקוי ב-Airtable) ל-`"Real Estate"` (Title Case, היחיד שנשאר). **PR #261 (2 commits):** 422 חי נוסף בפרודקשן — `_VALID_TAGS` עדיין הכיל `"real_estate"` lowercase כ-tag עצמאי; תוקן ל-`"Real Estate"` + נוסף `_TAG_NORMALIZE` כדי ש-`domain="real_estate"` יפיק `Domain="Real Estate"` **וגם** `Tags=["Real Estate"]` (לא Tags ריק, לא lowercase בשום מקום). smoke ירוק בכל שלב + integration (4/4)/router (44/44, שלב 1) + טסטים ידניים ממוקדים בכל שלב, מאומתים מול production log (422 בפועל).
**פער ידוע, לא בסקופ:** `weekly_summary.py::_group_by_domain()` ו-`tma_api.py`'s Business Memory listing קוראים `Tags[0]` כ-domain — ישברו בשקט (default general/ריק) עם רשומות חדשות. Backlog, piggyback על הפעלת `FEATURE_WEEKLY_SUMMARY`/שימוש פעיל ב-TMA business memory screen (אף אחד לא פעיל כרגע).
**Merged:** כן (`bd0f32c`/`50847b7`, `42ed90c`/`0094a82`, `f367469`+`7526e60`/`fa08a58`) | **Verified בפרודקשן:** לא עדיין