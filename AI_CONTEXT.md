# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-20
**עודכן על ידי:** Claude Code — session update (git-verified against `origin/main` HEAD `59adff7`)

> מקור אמת לתוכן הזה: `ROADMAP.md` + `BOSS_CURRENT_STATE.md` + `CHANGELOG.md` + git log. `CANONICAL_STATE.md` לא קיים בריפו — לא נסמכתי עליו.

---

## 1. Executive Summary
- `main` עומד על `7496628` (PR #80) — **מתקדם מעבר ל-`be65801`** שאליו כל שלושת מסמכי המקור (ROADMAP/CURRENT_STATE/AI_CONTEXT הקודם) עדיין הפנו. PR #80 כולל תיקון **crash אמיתי** ב-`app.py` (ראו §3).
- Pipeline הליבה (Identity → Router → Context → Agent) ושער ה-Approval תקינים ופעילים.
- כל פיצ'רי הצמיחה (Lead Scoring/Memory/Followup/Email Inbound) — **קוד מוכן, דגלים כבויים כברירת מחדל**, לא אומתו בתעבורה אמיתית בפרודקשן.
- מצב Render בפרודקשן (deploy hash, `/health`, webhook) **לא ניתן לאימות מהסביבה הזו** — אין גישת Dashboard/egress.
- Screen Filter Gateway (C53) ו-Finance Pulse (O4) מוזגו ל-main ופעילים בקוד; `raw_formula` של Finance Pulse עדיין סטטי (לא דינמי לפי תאריך).
- אין CI/CD ואין Monitoring אוטומטי — כל verification היום הוא ידני.

## 2. Current System State

**עובד (Operational):**
Identity/Router/Context/Agent core; `tool_registry`+`dispatcher` enforcement; Approval flow (3-state, fail-closed, `verify_execution()` נבדק לפני דיווח הצלחה — תוקן ב-PR #80); Airtable single-write-path gateway (`tools/airtable_gateway.py`); Daily Digest; Payment Reminder; Twilio signature validation; TMA auth+CORS; Screen Filter Gateway (`SCREEN_CONFIGS`); Finance Pulse (קורא Payments/Expenses חיים); A32 anti-hallucination evidence gate (חוזק ב-PR #80 — בודק tool identity+ok, לא keyword guessing).

**חלקי (Partial — קוד קיים, לא מאומת/לא פעיל):**
Lead Scoring (`LEAD_SCORING=off`), Lead Memory (`LEAD_MEMORY=off`), Followup Automation (`FOLLOWUP_AUTOMATION=off`) — שרשרת תלויה אחת בשנייה, כולן code-complete. WhatsApp outbound = honest stub (חסום ב-Meta Cloud API). Google integrations (OAuth נדרש). Approval Policy Emergency Window/OTP — code-complete, `EMERGENCY_WINDOW=off`.

**חסום (Blocked):**
F05 WhatsApp Production — מחכה לאישור Meta. N08 CI/CD, N09 Monitoring, N07 Schema Governance script — מתוכננים, לא מומשו. TMA: Activity Feed / Assets / Personal Mode — stub כן (`coming_soon`).

## 3. Completed Since Last Update

**Security Fix Session (20/06/2026) — commits ישירים ל-`main`, ללא branch/PR (לפי הנחיית סשן מפורשת):**
- `6e30d37` — Audit log ל-`lead_conversion.py`'s `crm_add_contact()` bypass (MEDIUM, ראו `BUG_AUDIT_LOG.md` BUG-009). תוקן ע"י Claude לעומת הספק: import path ל-`tools.airtable_security` (לא `tools.airtable_tools`) + חתימת קריאה אמיתית, לא המשוערת.
- `59adff7` — תיקון substring match על `owner_ids` ב-`tma_api.py` `_get_project_cards()` (LOW, ראו BUG-010). באג אומת בקוד אמיתי — שם הפונקציה בספק (`get_projects()`) היה שגוי.
- שני התיקונים: `py_compile` נקי, `smoke_tests.py`/`test_integration.py`/`core/router/test_router.py`/`test_airtable_gateway.py`/`test_identity_smoke.py` עברו, אומתו ב-grep על `origin/main` (לא רק git log), ו-Render deploy hash אומת תואם ל-`59adff7` ע"י המשתמש. **Verified בפרודקשן.**

**PR #85/#86 (19-20/06/2026) — `claude/c20-business-update-command-sp7h2i` ו-`claude/c21-lead-source-linking`, מוזגו ל-`main`:**
- `/update` Business Memory command (`cmd_update.py`) — owner/manager/partner מתעדים אירוע עסקי דרך Telegram inline keyboard, נכתב ל-Airtable, מוזרק חזרה כקונטקסט per-domain ב-`context.py`. דגל `FEATURE_BUSINESS_UPDATE` כבוי כברירת מחדל. ⚠️ ה-spec ID החיצוני "C20" מתנגש עם ROADMAP.md's C20 הקיים (Scheduler) — ראו פירוט מלא ב-`BUG_AUDIT_LOG.md`.
- Origin Lead linking — `/convert` כותב כעת קישור ל-ליד המקור (`ContactFields.ORIGIN_LEAD`/`DealFields.ORIGIN_LEAD`, שדות שאומתו בפרודקשן Airtable). ⚠️ spec ID "C21" מתנגש עם ROADMAP.md's C21 הקיים (Daily Digest) — אותה הערה.
- `GOVERNANCE_RULES.md` נוסף (Rules 13-18) + הפניה מ-`AGENTS.md`.
- שניהם code-complete, לא מאומתים בפרודקשן עדיין (ראו `BUG_AUDIT_LOG.md` לפרטי verification).

**PR #80 (commit `42dd137`, merged ל-main כ-`7496628`):**
- **תיקון crash**: PR #79 הכניס תשובות tool כ-dict מבני (`{ok, tool, external_id, evidence, user_message}`), אבל שני הצרכנים ב-`app.py` לא עודכנו — קריאה ישירה (לא דרך approval) ל-`airtable_add`/`update`, `gmail_draft`, או `calendar_create_event` קרסה עם `KeyError` על `result[:80]` (string slicing על dict), נבלעה ע"י `except Exception` גנרי, והמשתמש קיבל "קרה משהו לא צפוי" בלי שום אישור שהפעולה בוצעה.
- **Approval callback**: לא קרא ל-`verify_execution()` בכלל — `gmail_send_draft` דרך אישור דיווח "אושר וביצע" גם כשהכלי בפועל נכשל. תוקן.
- **A32 hardening**: שער NO-TOOL-EVIDENCE עבר מ-keyword guessing בטקסט התשובה לבדיקה לפי tool identity + `ok` status מ-`tool_results_log`. נוסף `test_a32_enforcement.py` — מריץ `run_agent()` end-to-end (Identity/Router/Context/Anthropic מדומים), 6/6 עובר.
- Verified בקומיט: `py_compile` נקי; `core/anti_hallucination.py` self-tests 31/31; `test_c53a.py` 50/50; `test_integration.py` 4/4; `smoke_tests.py` עובר; `test_a32_enforcement.py` 6/6.

**מהסשן הקודם (PR #75/#77/#79, מוזגים ל-`be65801`):** Screen Filter Gateway (C53), Finance Pulse English-schema migration + wiring (O4), structured tool-result contract (C53-A — שהרגרסיה שלו תוקנה כרגע ב-PR #80 לעיל).

## 4. Next Priorities
1. **לתעד את PR #80 / A32 fix** ב-`CHANGE_CONTROL_LOG.md` + `ROADMAP.md` עם commit hash — אותו דפוס drift שכבר תועד עבור C25-C40 חוזר על עצמו (תיעוד מפגר אחרי main).
2. **N07 — Schema Governance script**: עדיפות גבוהה ברודמאפ; drift בסכמת Airtable מתגלה כרגע ad-hoc per-bug, לא שיטתי.
3. **N11 — Finance Pulse dynamic formula**: `raw_formula` עדיין סטטי; + לסגור 2 הפערים הידועים (`PaymentFields.CONTACT/NOTES` מצביעים על שדות שלא קיימים; case-mismatch ב-`_build_formula()`).
4. **לאמת מצב Render בפועל מול `main` HEAD (`7496628`)** — לא ניתן מהסביבה הזו (egress חסום); סיכון High שתועד כבר ב-גרסה קודמת.
5. **החלטה על הדלקת N02-N04** (Lead Scoring/Memory/Followup) — קוד מוכן ושלם, אך אפס תעבורת ייצור אמיתית אומתה עד כה.
