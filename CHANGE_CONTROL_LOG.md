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
