# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-23
**עודכן על ידי:** Claude Code — session update (git-verified against `origin/main` HEAD `d1c48a1`)

> מקור אמת לתוכן הזה: `ROADMAP.md` + `BOSS_CURRENT_STATE.md` + `CHANGELOG.md` + git log. `CANONICAL_STATE.md` לא קיים בריפו — לא נסמכתי עליו.

---

## 1. Executive Summary
- `main` עומד על `e465eff` (PR #96/#97/#98/#99/#100/#101) — **F16 Media Layer הושלם במלואו** (כל 7 batches, א-ז). PR #96/#97 הוסיפו Batches א/ב/ג (STT, Drive upload, Airtable metadata gateway); PR #98 תיקן באג חוסם ב-Batch ד (`media_handler.py` — חתימת `upload_file()` שגויה + כשל Airtable מוחזר כ-`ok=True` בשקט); PR #99 גילה וסגר שני gaps קטנים ב-Batches ה/ו (`app.py`/`tma_api.py` היו **כבר מחוברים** ל-pipeline החי מאז commit `ee4d2ed` המקורי, לפני כל מאמץ הבאצ'ים — `send_chat_action` חסר ו-`linked_lead_id` לא עבר ב-TMA upload). Batch ז (`airtable_schema.py`) היה קיים ומלא מהבנייה המקורית. הקוד רץ במלואו, **אך כבוי בפרודקשן** מאחורי `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` (שני דגלים כבויים כברירת מחדל) — ⚠️ טבלת "Media Files" עצמה חייבת להיווצר ידנית ב-Airtable לפני כל הדלקה.
- Pipeline הליבה (Identity → Router → Context → Agent) ושער ה-Approval תקינים ופעילים.
- כל פיצ'רי הצמיחה (Lead Scoring/Memory/Followup/Email Inbound) — **קוד מוכן, דגלים כבויים כברירת מחדל**, לא אומתו בתעבורה אמיתית בפרודקשן.
- מצב Render בפרודקשן: המשתמש אישר שדיפלוי בוצע ל-`d91a9df` (Render dashboard) — **לא אומת באופן עצמאי מהסביבה הזו** (אין גישת Dashboard/egress ל-Claude).
- Screen Filter Gateway (C53) ו-Finance Pulse (O4) מוזגו ל-main ופעילים בקוד; `GET /api/finance/pulse` מחובר ל-`_build_formula()` עם `entity="Payment"` (`N11`, PR #77 — תועד כ-PLANNED ב-ROADMAP בטעות עד הסשן הזה, תוקן). סיווג overdue/pending לפי תאריך נשאר ב-Python (לא ב-`raw_formula`) — החלטת עיצוב, לא bug.
- **N07 (Schema Governance) הושלם** — `tools/schema_governance.py` (PR #101) קיים ב-main, standalone read-only drift detector מול Airtable Metadata API; עדיין לא רץ אוטומטית (אין CI בריפו), הרצה היא manual.
- **N08 (CI/CD) הושלם** (PR #103, `abf4835`) — `.github/workflows/ci.yml` רץ על כל PR. **N09 (Monitoring/Alerting) הושלם** (PR #104, `4ac6d24`) — `core/error_reporter.py` שולח התראות Telegram על שגיאות פרודקשן.
- **C56 (Approval Policy: Emergency Window + OTP + Policy Gate) מוזג ל-`main`** — `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` תיעדו "Merged: לא" וה-ROADMAP לא הזכיר את הפיצ'ר בכלל, אבל `gh pr view 69` מאשר `state: MERGED`, `mergedAt: 2026-06-17T18:56:00Z`, `mergeCommit: 4e933b0`; `git merge-base --is-ancestor 4e933b0 main` מאשר שזה אב-קדמון של `main` בפועל. תוקן בשלושת המסמכים (PR #112). `EMERGENCY_WINDOW` flag נשאר כבוי — אין שינוי התנהגות בפרודקשן.
- **ניקוי ענפי `claude/*` ישנים (סשן 23/06/2026)** — audit מלא של 37 ענפים (29+8) לא ממוזגים מול `main`, לפי ancestry+diff+content (לא תאריך/שם בלבד). **34 נמחקו**: ממוזגים בפועל (אב-קדמון של `main`), זהים-תוכן (אפס diff מהותי), orphan history, או collision שנפתר כבר בעבר לטובת גרסה אחרת (למשל `claude/claude-md-docs-u8kbsc` — קונפליקט classifier שנפתר כבר לטובת `codex/contact-import-classifier`). שני ענפים הכילו עבודה אמיתית שחולצה לפני המחיקה: **N12** למטה (`claude/lucid-franklin-0os9ma`+`claude/tender-hypatia-h5n0d3`, PR #108) ותיקון C56 לעיל (`claude/meta-whatsapp-phase-1-q6pp3e`, PR #112).
- **`APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` שוחזר** — מסמך audit ארכיטקטוני של מערכת ה-approval (4 מנגנונים + 2 kill switches, risk matrix, מפרט test harness ל-C53), 257 שורות, ללא קוד, מענף `claude/spec-c52-implementation-uqmu1g` שלא מוזג מעולם. נכתב 17/06/2026, נשמר ישירות ל-`main` (commit `783a680`, ללא PR — אישור משתמש מפורש) לפני שהענף נמחק. **טענות ה-file:line בו לא אומתו מחדש** מול הקוד הנוכחי.
- **BUG-014 תוקן** (PR #115) — `core/anti_hallucination.py`'s `_NO_TOOL_CLAIMS` (שער A32) לא כלל Drive בכלל; BOSS יכול היה להגיד "אני יכול לחפש ב-Drive"/"מצאתי קובץ" בלי שום קריאת `search_drive`/`read_drive_file`. נוספה קטגוריה רביעית ל-gate; 33/33 self-tests עוברים (היה 31/31).
- **תיקון תיעוד ל-BUG-011** (PR #116) — `BUG_AUDIT_LOG.md` תיעד "Merged: לא עדיין" עבור PR #110, אבל `gh pr view 110` מאשר `MERGED`, `mergeCommit: a4c8f27`, ו-`git merge-base --is-ancestor` מאשר אב-קדמון בפועל. תוקן, ללא שינוי קוד.

## 2. Current System State

**עובד (Operational):**
Identity/Router/Context/Agent core; `tool_registry`+`dispatcher` enforcement; Approval flow (3-state, fail-closed, `verify_execution()` נבדק לפני דיווח הצלחה — תוקן ב-PR #80); Airtable single-write-path gateway (`tools/airtable_gateway.py`); Daily Digest; Payment Reminder; Twilio signature validation; TMA auth+CORS; Screen Filter Gateway (`SCREEN_CONFIGS`); Finance Pulse (קורא Payments/Expenses חיים); A32 anti-hallucination evidence gate (חוזק ב-PR #80 — בודק tool identity+ok, לא keyword guessing).

**חלקי (Partial — קוד קיים, לא מאומת/לא פעיל):**
Lead Scoring (`LEAD_SCORING=off`), Lead Memory (`LEAD_MEMORY=off`), Followup Automation (`FOLLOWUP_AUTOMATION=off`) — שרשרת תלויה אחת בשנייה, כולן code-complete. WhatsApp outbound = honest stub (חסום ב-Meta Cloud API). Google integrations (OAuth נדרש). Approval Policy Emergency Window/OTP — code-complete, `EMERGENCY_WINDOW=off`. F16 Media Layer (כל 7 batches, `voice_stt_adapter.py`/`drive_adapter.py`/`media_gateway.py`/`media_handler.py`/`app.py` hooks/`tma_api.py` endpoint/`airtable_schema.py`) — code-complete **ומחובר ל-pipeline החי**, אך `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` כבויים כברירת מחדל — לא אומת בתעבורה אמיתית בפרודקשן. N12 Daily Git Audit scheduler job — code-complete ומחובר ל-`scheduler.py`, `GIT_AUDIT_SCHEDULER=off` (נשאר manual-only).

**חסום (Blocked):**
F05 WhatsApp Production — מחכה לאישור Meta. TMA: Activity Feed / Assets / Personal Mode — stub כן (`coming_soon`).

## 3. Completed Since Last Update

**סשן 23/06/2026 — ניקוי ענפי `claude/*` + 4 PRs:**
- **PR #108 (`claude/git-audit-roadmap-drift`, merge `c26c5e1`):** N12 — `daily_git_audit.py` חובר ל-`scheduler.py` (flag `GIT_AUDIT_SCHEDULER`, כבוי כברירת מחדל), נוספו `check_unmerged_vs_roadmap()`/`check_duplicate_schemas()`/`check_recent_commits()`/`check_cors_env_drift()`. חולץ מ-2 ענפים לא ממוזגים (`claude/lucid-franklin-0os9ma`, `claude/tender-hypatia-h5n0d3`) לפני מחיקתם; תוקן בדרך גם bug ב-precedence (הקוד המקורי בדק `BOSS_CURRENT_STATE.md` לפני `ROADMAP.md` — הפוך מהכרזת `ROADMAP.md` כמקור האמת היחיד).
- **PR #112 (`claude/approval-policy-docs-correction`, merge `a226e9d`):** ראו C56 לעיל — תיקון תיעוד PR #69.
- **commit `783a680` (ישיר ל-`main`, ללא PR — אישור משתמש מפורש):** שחזור `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` מענף `claude/spec-c52-implementation-uqmu1g` לפני מחיקתו.
- **PR #115 (`claude/bug-014-drive-evidence-gate`, merge `cf0ded7`):** BUG-014 — Drive נוסף ל-NO-TOOL-EVIDENCE gate (`core/anti_hallucination.py`).
- **PR #116 (`claude/bug-011-docs-correction`, merge `d1c48a1`):** תיקון תיעוד BUG-011 (PR #110 תועד "לא ממוזג" בטעות).
- **ניקוי ענפים:** 34 ענפי `claude/*` נמחקו (מתוך audit של 37) — ראו `ROADMAP.md` ל-summary, ללא קוד שאבד שלא חולץ קודם.

**PR #96/#97 (22/06/2026) — `claude/f16-media-layer`, מוזגים ל-`main` כ-`8f9c648`:**
- F16 Media Layer, Batches א/ב/ג. ⚠️ ID collision כפול: הספק החיצוני קרא לפיצ'ר "F12" (תפוס — Model Provider Adapter) ואז "F09" (תפוס — Lead Qualifier Wire-up); תוקן ל-F16 ב-ROADMAP.md, באותו דפוס שתועד עבור C20/C21/F14/F15.
- **Batch א — `voice_stt_adapter.py` (PR #96):** STT provider תוקן ל-OpenAI Whisper כ-PRIMARY חי (`OPENAI_API_KEY` קיים בסביבה) — הספק המקורי הניח Groq, תוקן מול הסביבה האמיתית; Groq נשאר רק כ-stub מוער ("Phase 2"), לא מחובר ל-`transcribe()`. קודי שגיאה תוקנו ל-`OVERSIZED`/`STT_FAILED` (`EMPTY_AUDIO` הוסר — לא קיים בספק).
- **Batch ב — `drive_adapter.py` (PR #97):** `upload_file(file_bytes, filename, mime_type, parent_folder_id)` — `parent_folder_id` חובה ללא default; temp file מנוקה תמיד ב-`finally`; `_safe_filename` מנקה רק תווים אסורים ל-Drive (עברית native, אין נורמליזציה נוספת).
- **Batch ג — `media_gateway.py` (PR #97):** נמצא תואם 100% לספק כבר מהבנייה המקורית — אפס שינוי קוד, רק וידוא.
- **באג self-test חוזר (תוקן פעמיים, שורש זהה):** `voice_stt_adapter.py` ו-`drive_adapter.py` השתמשו ב-`unittest.mock.patch("module.fn", ...)` בתוך ה-self-test שלהם; הרצה ישירה (`python3 module.py`) יוצרת `__main__` נפרד מ-`sys.modules["module"]` — ה-patch פוגע בעותק הלא-רץ, אז קריאות רשת אמיתיות יצאו בפועל בזמן בדיקה. תוקן: `patch.object(sys.modules[__name__], "fn", ...)` בשני הקבצים.
- `test_media_layer.py` עודכן בשני סבבים נפרדים (אחרי כל batch, לפי הוראה מפורשת) — שמות error code, פרמטר `parent_folder_id` חדש, assertions שהוסרו. 33/33 עוברים.
- Verified: PR #96/#97 אומתו ממוזגים בפועל דרך `git fetch origin main` + grep על תוכן הקבצים ב-`origin/main` (לא git log/PR status בלבד, לפי AGENTS.md POST-MERGE VERIFICATION) — `OVERSIZED`/`STT_FAILED` נמצאו ב-`voice_stt_adapter.py`, `parent_folder_id` נמצא בחתימת `upload_file`/`_upload_to_drive` ב-`drive_adapter.py`.

**PR #98 (22/06/2026) — `claude/f16-batch-d`, מוזג ל-`main` כ-`8dd3bca`:**
- F16 Batch ד — `media_handler.py`. במהלך המימוש התגלה שהקובץ **כבר קיים על `main`** מ-commit `ee4d2ed` קודם (לפני כל מאמץ הבאצ'ים), עם שמות פונקציות שונים מהספק (`handle_voice_note()`/`handle_file_upload()`/`handle_tma_upload()` במקום `handle_telegram_media()`) ו-2 באגים אמיתיים. המשתמש הכריע: לשמור שמות קיימים, לתקן רק internals, לא לגעת ב-`app.py`/`tma_api.py`.
- תוקן: (1) `upload_file()` נקרא עם `domain=domain` — kwarg שלא קיים בחתימה האמיתית של `drive_adapter.upload_file()` (`parent_folder_id` חובה) — `TypeError` מובטח עם flag דלוק; נוסף `_resolve_drive_folder()` שמשתמש ב-`drive_adapter._get_upload_folder(domain)`. (2) כשל כתיבה ל-Airtable לאחר Drive upload מוצלח הוחזר כ-`ok=True` בשקט — נוסף בדיקה + קוד שגיאה `ASSET_SAVE_FAILED`. קוד שגיאה חדש נוסף גם ל-resolve כשל: `DRIVE_FAILED`.
- הודעות שגיאה תורגמו לעברית; הוספו 4 self-test scenarios חדשים ב-`media_handler.py`'s `__main__` (large-tier success, voice+memory-keyword approval, `DRIVE_FAILED`, `ASSET_SAVE_FAILED`) — התרחיש שחשף את הבאג המקורי לא היה מכוסה ב-`test_media_layer.py` הקיים. 33/33 עוברים גם לפני וגם אחרי התיקון (regression-safe).
- Verified: `git fetch origin main` + grep על `_get_upload_folder`/`DRIVE_FAILED`/`ASSET_SAVE_FAILED` ב-`origin/main:media_handler.py` — תואם.

**PR #99 (22/06/2026) — `claude/f16-final`, מוזג ל-`main` כ-`4924030`:**
- F16 Batches ה/ו/ז — לפני מימוש, אומת ש-Batches ה (`app.py` hooks) ו-ו (`tma_api.py` `/api/tma/upload`) **כבר מחוברים** ל-pipeline החי מאז `ee4d2ed` (לא רק קוד עומד — `_handle_telegram_media()` כבר נקרא מ-webhook על voice/photo/document, ה-endpoint כבר קורא ל-`handle_tma_upload()`), ו-Batch ז (`Tables.MEDIA_FILES`/`MediaFileFields` ב-`airtable_schema.py`) כבר קיים ומלא. תוקנו רק 2 gaps אמיתיים: `send_chat_action` חסר לפני עיבוד ב-`app.py` (typing/upload_document); `linked_lead_id` לא התקבל מה-multipart form ב-`tma_api.py` ולא עבר ל-`handle_tma_upload()`/`handle_file_upload()`. `domain` נשאר נגזר מה-identity המאומת בכוונה (לא משדה form) — מנע client-controlled tenant scope.
- Verified: `git fetch origin main` + grep על `send_chat_action.*upload_document`, `linked_lead_id` ב-`origin/main:app.py`/`tma_api.py`/`media_handler.py` — תואם. `test_media_layer.py` 33/33, `media_handler.py` self-test 4/4, `smoke_tests.py` עובר.
- **F16 Media Layer — הושלם במלואו (כל 7 batches), כבוי בפרודקשן מאחורי flags.**

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

**PR #100 (22/06/2026) — `claude/f16-docs-final`, מוזג ל-`main` כ-`de5765b`:** עדכון docs-only — תיקון `ROADMAP.md`/`AI_CONTEXT.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` לשקף ש-F16 הושלם במלואו (PR #99 כבר מוזג בפועל ע"י בעל הריפו לפני שניסיתי למזג בעצמי — אומת דרך `pull_request_read`, לא דרך הצהרה).

**PR #101 (22/06/2026) — `claude/n07-schema-governance`, מוזג ל-`main` כ-`e465eff`:** N07 — `tools/schema_governance.py`. סקריפט standalone, קובץ יחיד, READ ONLY לחלוטין: שולף live schema מ-Airtable Metadata API, משווה ל-`airtable_schema.py` (import, לא parse) דרך `TABLE_CLASS_MAP`/`_class_values` הקיימים מ-`schema_audit.py` (לא שוכפל מיפוי שני). מזהה 5 סוגי drift: שדה חסר ב-live (whitespace-tolerant match) → ERROR; שדה ב-live שלא בקוד → WARNING; trailing/leading spaces בשם שדה → WARNING; trailing/leading spaces ב-select options → WARNING; שינוי סוג שדה → ERROR (מול ריצה קודמת שנשמרה, כי `airtable_schema.py` לא מכיל מטא-דאטה של סוגים — baseline זמני, לא קוד). מדפיס דוח עברית, שומר `schema_drift_report.json` (ב-`.gitignore`, לא ב-git), exit 1 אם יש ERROR. self-test (`--self-test`, ללא רשת) כלול. מניע: BUG-008 (`Leads."Business Outcome"` trailing space שהתגלה ad-hoc).

**PR #103 (22/06/2026) — `claude/n08-ci-cd`, מוזג ל-`main` כ-`abf4835`:** N08 — `.github/workflows/ci.yml`. מריץ `smoke_tests.py`/`test_integration.py` + `npm run build` (frontend, skip חינני אם `tma-frontend/package.json` חסר) על כל PR. Secrets ממופים נכון (`TELEGRAM_TOKEN` וכו').

**PR #104 (22/06/2026) — `claude/n09-monitoring`, מוזג ל-`main` כ-`24237e6`:** N09 — `core/error_reporter.py`. `report_error(error, context, level)` שולח התראת Telegram על שגיאות פרודקשן בלבד (`RENDER=="true"` + `ERROR_REPORTING`), rate-limited (10/שעה), בלי payload/תוכן הודעות (context = שם פונקציה בלבד, traceback גולמי). מחובר ב-3 נקודות ב-`app.py`: `_handle_approval_callback`, `webhook_telegram`, `webhook_whatsapp`.

**Docs correction (סשן זה) — N08/N09/N11:** שלושתם תועדו כ-`🔲 PLANNED` ב-`ROADMAP.md` אף שהיו ממוזגים ל-`main` (N08/N09 מהסשן הזה עצמו; N11 מ-PR #77, סשן קודם). תוקן ב-`ROADMAP.md`/`AI_CONTEXT.md` (זה) אחרי grep ישיר על `main` שאישר את הקוד החי בכל שלושתם (לא הוסתמך על git log/PR status בלבד — POST-MERGE VERIFICATION לפי `AGENTS.md`).

## 4. Next Priorities
0. **F16 Media Layer — הדלקת flags** (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`) — קוד שלם ומחובר (כל 7 batches), אך טבלת "Media Files" חייבת להיווצר ידנית ב-Airtable לפני כל הדלקה; אפס תעבורת ייצור אומתה עד כה.
1. **לתעד את PR #80 / A32 fix** ב-`CHANGE_CONTROL_LOG.md` + `ROADMAP.md` עם commit hash — אותו דפוס drift שכבר תועד עבור C25-C40 חוזר על עצמו (תיעוד מפגר אחרי main).
2. **להריץ את N07 (`tools/schema_governance.py`) מול live Airtable** — קוד הושלם ומוזג, עדיין לא הורץ פעם ראשונה מול הסכמה האמיתית (אין credentials בסביבת sandbox זו); כל עוד לא רץ, BUG-008-style drift עדיין לא מתגלה בפועל.
3. **N11 — הושלם** (raw_formula נשאר סטטי בכוונה, ראו §1). פער שנותר פתוח, **מחוץ להיקף N11** (`crm.py`, לא `tma_api.py`): `PaymentFields.CONTACT`/`NOTES` (`contact_id`/`notes`) מצביעים על שדות שלא קיימים ב-`Payments` החי — `crm.py`'s `create_payment()` יכשל אם יקרא עם `contact_id`/`notes` (ראו `CHANGELOG.md` Unreleased).
4. **לאמת מצב Render בפועל מול `main` HEAD (`7496628`)** — לא ניתן מהסביבה הזו (egress חסום); סיכון High שתועד כבר ב-גרסה קודמת.
5. **החלטה על הדלקת N02-N04** (Lead Scoring/Memory/Followup) — קוד מוכן ושלם, אך אפס תעבורת ייצור אמיתית אומתה עד כה.
