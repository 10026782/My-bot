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

### C52 — Approval Policy: Emergency Window + OTP + Policy Gate
- **תאריך:** 17/06/2026
- **סוג:** Security
- **Requirement:** ROADMAP.md C52 (Sprint 16/06/2026); `Approval_Policy_Spec.md`
- **Commit:** `8209d36` (phase 1 — Emergency_Window table + `core/emergency_window.py`), `a57fd7f` (phase 2 — `core/otp.py`), `44457dd` (phase 3 — policy gate ב-`_queue_tma_write_approval`), `ce111bb` (`web`→mobile fail-closed fix + doc updates), `92e4b2b` (CORS `X-TMA-Platform` header + derived RISK_LEVEL write) — **merge commit `4e933b0`**
- **PR:** #69 — https://github.com/10026782/My-bot/pull/69
- **Review על ידי:** 10026782 (owner — `merged_by` ב-GitHub API)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` נקי; `npm run build` עבר; `smoke_tests.py` 5/6 PASS (כשל `anthropic` import תלוי-סביבה); מטריצת 12 תרחישים (Low/Medium/High/Critical × mobile/desktop/web × window/OTP) אומתה מול קוד הגייט האמיתי; CORS preflight מאומת מחזיר `X-TMA-Platform`; כתיבת RISK_LEVEL מאומתת מול live Airtable choices. GitHub API `pull_request_read` מאשר `merged: true`, `merged_at: 2026-06-17T18:56:00Z`; `git fetch origin main` מאשר `origin/main` על `4e933b0`. אין אימות פרודקשן חי.
- **Docs עודכנו:** ROADMAP / AI_CONTEXT / BUG_AUDIT_LOG / RELEASE_CHECKLIST
- **Feature Flag:** `EMERGENCY_WINDOW` — כבוי כברירת מחדל; מיזוג ל-`main` אינו משנה התנהגות בפרודקשן כל עוד הדגל כבוי
- **Rollback plan:** revert ל-merge commit `4e933b0` על `main`; אין סיכון פונקציונלי מיידי כי הדגל כבוי
