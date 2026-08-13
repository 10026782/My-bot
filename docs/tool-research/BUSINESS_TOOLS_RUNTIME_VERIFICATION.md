# SCOREBOS — Business Tools Runtime Verification + Dogfooding

**Date:** 2026-08-13  
**Scope:** bounded local verification and dogfooding. No external tools were opened with data, no production data was used, and no new architecture was added.

## 1. Current Main SHA

Current merged `main` was inspected at:

`c3fe74357caf41e71c7f55ea9da7a1a082e8240a`

The following were confirmed directly on `main`:

| Item | Status |
|---|---|
| `business_tool_registry.py` | MERGED |
| `app.run_agent()` recommendation hook | WIRED |
| Approved business records | MERGED |
| Operator/infrastructure class separation | MERGED |
| Verification-status filtering | MERGED |
| Privacy guidance and restrictions | MERGED |
| Tool-combination strategy and toolbox documents | MERGED |
| Deployment | Not evidenced in this task |
| Production runtime verification | Not evidenced in this task |

`DEPLOYED` and `RUNTIME VERIFIED` are therefore not claimed.

## 2. Capability Status

The external catalog is a frozen, read-only tuple of `BusinessTool` records. It contains 13 business records, including approved-with-restrictions entries, plus separate operator and deferred infrastructure records.

Normal matching is eligible only for enabled `business` records whose status is `verified` or `approved_with_restrictions`. Operator records (`Hoppscotch`, `Log Voyager`) and infrastructure candidates (`UptimeRobot`, `Checkly`, `Sentry`, `Socket`) are not in the normal business result set.

## 3. Real Execution Path

The verified code path is:

`incoming user message → app.run_agent() → resolve_identity() → maybe_recommend(user_text) → find_recommended_tools() → eligibility filter + deterministic ranking → format_recommendation() → returned message`

Details:

- **Entry point:** `app.run_agent()`.
- **Identity/auth:** `resolve_identity(channel, chat_id)` runs before discovery.
- **Matcher:** `business_tool_registry.maybe_recommend()`.
- **Eligibility:** `list_tools()` defaults to `tool_class="business"`; matching excludes disabled records and any status outside `verified`/`approved_with_restrictions`.
- **Ranking:** task aliases score 3 points per match; capabilities/categories score 1; ties preserve registry order; at most three results are returned.
- **Formatting:** name, description/use, privacy level and direct URL; restricted tools receive an explicit non-sensitive/approved-data caution.
- **Fallback:** if no recommendation is produced, execution continues into the existing contract/router/agent path. Import or matcher errors are caught and also fall through.
- **Metadata:** when a recommendation is returned, `_out_meta["source_module"]` is set to `business_tool_registry`.

The path is read-only. It does not upload files, execute an external tool, write canonical state, create ActionContracts, bypass approval, or create a second action path.

## 4. Regression Matrix

### Positive matches

| Input | Expected canonical record | Result |
|---|---|---|
| `אני צריך לאחד כמה קבצי PDF` | BentoPDF (`bentopdf`) | PASS |
| `יש לי CSV שלא נפתח` | csv.repair (`csv-repair`) | PASS |
| `אני צריך להקטין תמונה לפני שליחה` | Squoosh (`squoosh`) | PASS |
| `אני רוצה ליצור גרף מהנתונים` | RAWGraphs (`rawgraphs`) | PASS |
| `יש לי JSON מסובך שאני רוצה להבין` | JSON Crack (`json-crack`) | PASS; restriction preserved |

### Required safety/isolation tests

| Test | Result |
|---|---|
| Unrelated task request not intercepted | PASS |
| Unrelated marketing request not intercepted | PASS |
| Operator tools hidden | PASS |
| Infrastructure candidates hidden | PASS |
| Deferred/verify-first records hidden | PASS |
| Unknown task does not invent a tool | PASS |
| Ranking deterministic | PASS |

## 5. Owner Dogfooding Results

All inputs were synthetic/redacted examples. Each passed with the expected first match, a direct-use URL, and an applicable privacy level.

| User request | Matched tool | Why it matched | Quality | False positive? | Miss? | Owner likely use? | Privacy warning |
|---|---|---|---|---|---|---|---|
| לחבר כמה מסמכי PDF לפני שליחה | BentoPDF | PDF merge alias | Good | No | No | Yes | Clear |
| איך לדחוס PDF גדול? | BentoPDF | PDF compression alias | Good | No | No | Yes | Clear |
| הקובץ CSV לא נפתח באקסל | csv.repair | CSV failure/opening aliases | Good | No | No | Yes | Clear |
| תקטין לי תמונה לוואטסאפ | Squoosh | image/WhatsApp alias | Good | No | No | Yes | Clear |
| תרשים מהנתונים של הקמפיין | RAWGraphs | chart/data aliases | Good | No | No | Yes | Clear |
| JSON מסובך, איך להבין את המבנה? | JSON Crack | JSON understanding aliases | Good | No | No | Yes | Clear/restricted |
| להציג JSON של בדיקות בלי לחשוף פרטים | JSON Crack | JSON visualization + caution | Good | No | No | Yes | Clear/restricted |
| לכווץ לוגו SVG | SVGOMG | SVG/logo aliases | Good | No | No | Yes | Clear |
| לשאול שאלה על CSV ו-JSON | SQL for Files | file-query aliases | Good | No | No | Yes | Clear |
| לנקות לוג לפני שליחה לתמיכה | ShareClean | log-sanitization aliases | Good | No | No | Yes | Clear/restricted |

## 6. False Positives

After the bounded alias fixes, the following existing SCOREBOS-style requests all returned no business-tool recommendation:

- create/update/complete task;
- list tasks;
- marketing request;
- lead/contact/deal request;
- generic business question;
- project/status request;
- infrastructure/operator phrases such as `monitor endpoint`, `test api`, `track error`, `scan dependencies`.

False positives in the final matrix: **0**.

## 7. Misses

The initial dogfooding pass found five narrow misses:

1. `הקובץ CSV לא נפתח באקסל` was not recognized by the intent gate.
2. `תקטין לי תמונה לוואטסאפ` lacked a matching image alias.
3. `צריך לכווץ לוגו SVG` lacked a matching SVG alias.
4. `אני רוצה לשאול שאלה על CSV ו-JSON` lacked the SQL-for-Files Hebrew phrase.
5. `צריך לנקות לוג לפני שליחה לתמיכה` lacked the ShareClean Hebrew phrase.

These are local, uncommitted fixes at the time of this report. They are not part of the current merged `main` SHA above.

Final dogfooding misses after the local fixes: **0**.

## 8. Exact Fixes Made

Local bounded changes only:

- Added two concrete Squoosh aliases for WhatsApp image reduction.
- Added one concrete SVGOMG alias for logo compression.
- Added one concrete SQL for Files Hebrew phrase.
- Added one concrete ShareClean Hebrew phrase.
- Changed `maybe_recommend()` to reuse deterministic matches when a real match exists even if the wording lacks one of the broad intent markers. No-match messages still return `None`.
- Added regression assertions for the new phrases.

No LLM classifier, new service, schema, screen, database, crawler, ActionGateway path or authorization change was introduced.

## 9. Test Results

Local command:

`python3 -m pytest -q test_business_tool_registry.py test_tool_registry_invariants.py test_tool_availability_shadow.py`

Result: **27 passed**.

Additional dogfooding matrix result:

- 10 positive owner scenarios: PASS
- 9 non-hijack scenarios: PASS
- 4 infrastructure isolation scenarios: PASS
- 2 unknown-need scenarios: PASS
- deterministic ranking repeated 10 times: PASS
- `py_compile`/production deployment: not run or claimed for this documentation-only verification

## 10. Runtime Verification Status

The recommendation path is **locally verified in isolation and by static inspection of the merged source**, not production-runtime verified.

| Term | Status |
|---|---|
| MERGED | Yes — `main` SHA above |
| WIRED | Yes — hook present in `app.run_agent()` |
| DEPLOYED | Unknown/not evidenced |
| RUNTIME VERIFIED | No production evidence available |
| LOCAL VERIFIED | Yes for registry/matcher path and regression matrix |

The local fixes in Section 8 remain `Implemented but not yet verified` until merged and then re-run against the resulting `main`.

## 11. Mini-App Decision

`NO MINI-APP NEED YET`

Evidence: 10 direct-use owner scenarios succeeded through the bot recommendation path. The test set demonstrates task lookup value, not a need to browse categories or maintain a second surface. No browsing demand was observed in this bounded task.

## 12. Crawler Decision

`NO FRESHNESS PAIN YET`

Evidence: this task found matching/wording gaps, not stale-source or maintenance failures. The existing crawler remains a POC-only plan; no crawl, schedule or vendor integration is justified by this run.

## 13. Next Smallest Step

Review and merge the five bounded matcher fixes, then rerun this same local matrix against the resulting `main`. Do not add a Mini-App or crawler until browsing demand or freshness pain is measured.

## VERDICT

### BUSINESS TOOL PATH

`PASS WITH FIXES`

### RUNTIME STATUS

`MERGED / WIRED / DEPLOYED NOT EVIDENCED / RUNTIME VERIFIED NOT EVIDENCED`

### MATCHING QUALITY

`NEEDS EXPANSION`

### FALSE POSITIVES

`0`

### MISSES

`0 after bounded local fixes; 5 before fixes`

### MINI-APP

`NO MINI-APP NEED YET`

### CRAWLER

`NO FRESHNESS PAIN YET`

### NEXT SMALLEST STEP

Merge the five bounded alias/intent fixes and rerun the existing 27-test suite plus the dogfooding matrix.
