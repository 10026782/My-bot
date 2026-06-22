# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-22
**עודכן על ידי:** Claude Code — session update (git-verified against `origin/main` HEAD `8f9c648`)

> מקור אמת לתוכן הזה: `ROADMAP.md` + `BOSS_CURRENT_STATE.md` + `CHANGELOG.md` + git log. `CANONICAL_STATE.md` לא קיים בריפו — לא נסמכתי עליו.

---

## 1. Executive Summary
- `main` עומד על `8f9c648` (PR #96+#97) — **מתקדם מעבר ל-`d91a9df`** שאליו AI_CONTEXT הקודם הפנה. PR #96/#97 הוסיפו F16 Media Layer Batches א/ב/ג (STT, Drive upload, Airtable metadata gateway — ראו §3). קוד חדש, **לא מחובר ל-pipeline החי** (Batches ד-ז עדיין לא בנויים — אין hooks ב-`app.py`/`tma_api.py`, אין feature flag).
- Pipeline הליבה (Identity → Router → Context → Agent) ושער ה-Approval תקינים ופעילים.
- כל פיצ'רי הצמיחה (Lead Scoring/Memory/Followup/Email Inbound) — **קוד מוכן, דגלים כבויים כברירת מחדל**, לא אומתו בתעבורה אמיתית בפרודקשן.
- מצב Render בפרודקשן: המשתמש אישר שדיפלוי בוצע ל-`d91a9df` (Render dashboard) — **לא אומת באופן עצמאי מהסביבה הזו** (אין גישת Dashboard/egress ל-Claude).
- Screen Filter Gateway (C53) ו-Finance Pulse (O4) מוזגו ל-main ופעילים בקוד; `raw_formula` של Finance Pulse עדיין סטטי (לא דינמי לפי תאריך).
- אין CI/CD ואין Monitoring אוטומטי — כל verification היום הוא ידני.

## 2. Current System State

**עובד (Operational):**
Identity/Router/Context/Agent core; `tool_registry`+`dispatcher` enforcement; Approval flow (3-state, fail-closed, `verify_execution()` נבדק לפני דיווח הצלחה — תוקן ב-PR #80); Airtable single-write-path gateway (`tools/airtable_gateway.py`); Daily Digest; Payment Reminder; Twilio signature validation; TMA auth+CORS; Screen Filter Gateway (`SCREEN_CONFIGS`); Finance Pulse (קורא Payments/Expenses חיים); A32 anti-hallucination evidence gate (חוזק ב-PR #80 — בודק tool identity+ok, לא keyword guessing).

**חלקי (Partial — קוד קיים, לא מאומת/לא פעיל):**
Lead Scoring (`LEAD_SCORING=off`), Lead Memory (`LEAD_MEMORY=off`), Followup Automation (`FOLLOWUP_AUTOMATION=off`) — שרשרת תלויה אחת בשנייה, כולן code-complete. WhatsApp outbound = honest stub (חסום ב-Meta Cloud API). Google integrations (OAuth נדרש). Approval Policy Emergency Window/OTP — code-complete, `EMERGENCY_WINDOW=off`. F16 Media Layer Batches א/ב/ג (`voice_stt_adapter.py`/`drive_adapter.py`/`media_gateway.py`) — code-complete, **אפס import מקוד חי** (אין עדיין `media_handler.py`/`app.py` hooks/`tma_api.py` endpoint — Batch ד-ז).

**חסום (Blocked):**
F05 WhatsApp Production — מחכה לאישור Meta. N08 CI/CD, N09 Monitoring, N07 Schema Governance script — מתוכננים, לא מומשו. TMA: Activity Feed / Assets / Personal Mode — stub כן (`coming_soon`).

## 3. Completed Since Last Update

**PR #96/#97 (22/06/2026) — `claude/f16-media-layer`, מוזגים ל-`main` כ-`8f9c648`:**
- F16 Media Layer, Batches א/ב/ג. ⚠️ ID collision כפול: הספק החיצוני קרא לפיצ'ר "F12" (תפוס — Model Provider Adapter) ואז "F09" (תפוס — Lead Qualifier Wire-up); תוקן ל-F16 ב-ROADMAP.md, באותו דפוס שתועד עבור C20/C21/F14/F15.
- **Batch א — `voice_stt_adapter.py` (PR #96):** STT provider תוקן ל-OpenAI Whisper כ-PRIMARY חי (`OPENAI_API_KEY` קיים בסביבה) — הספק המקורי הניח Groq, תוקן מול הסביבה האמיתית; Groq נשאר רק כ-stub מוער ("Phase 2"), לא מחובר ל-`transcribe()`. קודי שגיאה תוקנו ל-`OVERSIZED`/`STT_FAILED` (`EMPTY_AUDIO` הוסר — לא קיים בספק).
- **Batch ב — `drive_adapter.py` (PR #97):** `upload_file(file_bytes, filename, mime_type, parent_folder_id)` — `parent_folder_id` חובה ללא default; temp file מנוקה תמיד ב-`finally`; `_safe_filename` מנקה רק תווים אסורים ל-Drive (עברית native, אין נורמליזציה נוספת).
- **Batch ג — `media_gateway.py` (PR #97):** נמצא תואם 100% לספק כבר מהבנייה המקורית — אפס שינוי קוד, רק וידוא.
- **באג self-test חוזר (תוקן פעמיים, שורש זהה):** `voice_stt_adapter.py` ו-`drive_adapter.py` השתמשו ב-`unittest.mock.patch("module.fn", ...)` בתוך ה-self-test שלהם; הרצה ישירה (`python3 module.py`) יוצרת `__main__` נפרד מ-`sys.modules["module"]` — ה-patch פוגע בעותק הלא-רץ, אז קריאות רשת אמיתיות יצאו בפועל בזמן בדיקה. תוקן: `patch.object(sys.modules[__name__], "fn", ...)` בשני הקבצים.
- `test_media_layer.py` עודכן בשני סבבים נפרדים (אחרי כל batch, לפי הוראה מפורשת) — שמות error code, פרמטר `parent_folder_id` חדש, assertions שהוסרו. 33/33 עוברים.
- Verified: PR #96/#97 אומתו ממוזגים בפועל דרך `git fetch origin main` + grep על תוכן הקבצים ב-`origin/main` (לא git log/PR status בלבד, לפי AGENTS.md POST-MERGE VERIFICATION) — `OVERSIZED`/`STT_FAILED` נמצאו ב-`voice_stt_adapter.py`, `parent_folder_id` נמצא בחתימת `upload_file`/`_upload_to_drive` ב-`drive_adapter.py`. **קוד מוזג, לא מחובר ל-pipeline החי, לא אומת בפרודקשן** (אין feature flag, אין caller חי).
- Batches ד (`media_handler.py`), ה (`app.py` hooks), ו (`tma_api.py` endpoint), ז (`airtable_schema.py` verification) — עדיין לא מומשו.

**PR #94 (22/06/2026) — `claude/weekly-business-summary-4crnek`, מוזג ל-`main` כ-`d91a9df`:**
- C22 Weekly Business Summary (`weekly_summary.py`) — שולף Business Memory מ-7 ימים אחרונים, מקבץ לפי domain, שולח סיכום שבועי לטלגרם (ראשון 08:30 דרך `scheduler.py`) + כפתור להעברת רשומות `Event Type=Learning` ("רעיון") ל-ROADMAP. Read-only לחלוטין. דגל `FEATURE_WEEKLY_SUMMARY` כבוי כברירת מחדל — נוסף לרשימת `feature_flags.py`.
- תוקנו שני באגים בספק המקורי לעומת הסכמה האמיתית: `_DOMAIN_LABELS` כלל domain לא קיים ("recruitment") וחיסר `media`/`saas` (תוקן להתאים ל-`real_estate/import/media/saas/finance/general` מ-`cmd_update.py`); `_IDEA_TYPES` כלל ערך `"Idea"` שלא קיים ב-`BusinessMemoryFields.EVENT_TYPE` — תוקן ל-`"Learning"` (הערך האמיתי היחיד למיפוי "רעיון").
- **תיקון נוסף ב-`app.py` (webhook):** לפני התיקון, *כל* `callback_query` נוטה ל-`_handle_approval_callback` ללא תנאי — כל `callback_data` שלא מתחיל ב-`approve:`/`reject:` נפל ל-`else` שמחזיר "פעולה לא מוכרת" ולא עשה דבר. זה הפך את `register_weekly_callbacks` (וגם את `cmd_update.py`'s `upd_domain:`/`upd_type:` הקיימים מ-PR #85/86!) ל-dead code בפועל — הכפתורים מעולם לא עבדו דרך ה-webhook. תוקן: `callback_query` עם `data` שלא מתחיל ב-`approve:`/`reject:` מנותב כעת דרך `bot.process_new_updates([update])` (כמו slash commands), כדי שה-`@bot.callback_query_handler` הרשומים בפועל יופעלו.
- ⚠️ ID collision: ה-spec החיצוני קרא לפיצ'ר "C22", אך ROADMAP.md's C22 הקיים הוא "feature_flags — is_enabled() alias" (Contract Fix, לא קשור) — אותו דפוס שתועד כבר עבור C20/C21 (PR #85/86). אין שינוי ב-ROADMAP.md בסשן הזה; ה-ID `C22` בהקשר הזה (Weekly Summary) מתייחס רק ל-spec החיצוני/למסמכי השינוי הזה, לא ל-ROADMAP.
- Verified: `py_compile` נקי; `smoke_tests.py`/`test_integration.py`/`core/router/test_router.py` עוברים; תרחישי A/B/C/D מהספק (flag off, Business Memory ריק, רשומות מקובצות, כפתורי Idea) נבדקו ידנית עם mock data. דיפלוי ל-Render על `d91a9df` אושר ע"י המשתמש — לא אומת עצמאית מהסביבה הזו.

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
0. **F16 Media Layer Batches ד-ז** (`media_handler.py`, `app.py` hooks, `tma_api.py` endpoint, `airtable_schema.py` verification) — Batches א/ב/ג מוזגים אבל הקוד "תלוי באוויר" עד שה-handler/hooks מחברים אותו ל-pipeline החי; ללא flag פעיל אין שום סיכון production מהמיזוג הנוכחי.
1. **לתעד את PR #80 / A32 fix** ב-`CHANGE_CONTROL_LOG.md` + `ROADMAP.md` עם commit hash — אותו דפוס drift שכבר תועד עבור C25-C40 חוזר על עצמו (תיעוד מפגר אחרי main).
2. **N07 — Schema Governance script**: עדיפות גבוהה ברודמאפ; drift בסכמת Airtable מתגלה כרגע ad-hoc per-bug, לא שיטתי.
3. **N11 — Finance Pulse dynamic formula**: `raw_formula` עדיין סטטי; + לסגור 2 הפערים הידועים (`PaymentFields.CONTACT/NOTES` מצביעים על שדות שלא קיימים; case-mismatch ב-`_build_formula()`).
4. **לאמת מצב Render בפועל מול `main` HEAD (`7496628`)** — לא ניתן מהסביבה הזו (egress חסום); סיכון High שתועד כבר ב-גרסה קודמת.
5. **החלטה על הדלקת N02-N04** (Lead Scoring/Memory/Followup) — קוד מוכן ושלם, אך אפס תעבורת ייצור אמיתית אומתה עד כה.
