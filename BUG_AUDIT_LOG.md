# BUG_AUDIT_LOG.md
> כל באג נפתח כאן מרגע הדיווח עד אימות בפרודקשן.

## פורמט רשומה

### BUG-[XXX] — [תיאור קצר]
- **דווח:** [תאריך]
- **דווח על ידי:** 
- **מסך / מודול:** 
- **תיאור:** 
- **Severity:** Critical / High / Medium / Low
- **Root Cause:** 
- **תוקן ב-commit:** 
- **תוקן ב-branch:** 
- **Merged:** כן / לא
- **Deployed:** כן / לא / תאריך
- **Verified בפרודקשן:** כן / לא
- **Verification ראיה:** 
- **סטטוס:** Open / Fixed / Verified / Won't Fix

---

## לוג באגים

### BUG-001 — PersonalMode field names mismatch
- **דווח:** ~17/06/2026
- **Severity:** Medium
- **Root Cause:** field names בקוד לא תאמו ל-live Airtable
- **סטטוס:** Won't Fix — אומת שהקוד כבר נכון

### BUG-002 — /api/game/today shared endpoint
- **דווח:** 17/06/2026
- **Severity:** High — שינוי אחד שובר שני מסכים
- **מסך / מודול:** `tma_api.py` — `GET /api/game/today`, נצרך גם ע"י `BossCheckin.tsx` וגם ע"י `GameScreen.tsx`
- **Root Cause:** BossCheckin ו-GameScreen חלקו endpoint יחיד עם לוגיקת סינון (`Roadmap_Tasks`) שלא הייתה ממוקמת במקום אחד; שינוי בפילטר ל-screen אחד (הסרת owner filter ב-commit `d3243ef`) שינה התנהגות עבור שני הצרכנים בלי בדיקת רגרסיה מפורשת.
- **תוקן ב-commit:** `d3243ef` ("fix(TMA): remove owner filter from game today") ואז `1876842` ("fix(TMA): repair game today task filtering") — תיקון בשני שלבים: הראשון הוציא שגיאה, השני תיקן את הסינון בפועל. בהמשך אוחד ל-helper משותף `_get_active_world_dict()` (commit `a462633`, ראו docstring: "Shared by game_status / game_today / game_checkin so World-lookup logic lives in exactly one place — BOSS_Refactor_Plan.md Stage 0 #2").
- **תוקן ב-branch:** `claude/meta-whatsapp-phase-1-q6pp3e` (לפי תבנית branch naming של שאר commits מאותו טווח תאריכים — לא אומת ישירות מ-`git branch --contains`)
- **Merged:** כן — שלושת ה-commits מופיעים ב-`origin/main`
- **Deployed:** לא ידוע — דרוש בדיקה ידנית (Render)
- **Verified בפרודקשן:** לא
- **Verification ראיה:** אין — לא בוצעה בדיקה ידנית מתועדת בשני המסכים בפרודקשן
- **סטטוס:** Fixed — ממתין ל-Verify

### BUG-003 — Multiple Active Worlds no constraint
- **דווח:** 17/06/2026
- **Severity:** Medium
- **Root Cause:** אין hard constraint ב-Airtable שמבטיח רשומת World יחידה עם `Status=Active`; אם שתי רשומות מסומנות Active, `game_today()` (ב-`max_records=1` הישן) היה מחזיר תוצאה לא צפויה לפי סדר ה-API.
- **תוקן ב-commit:** `a462633` ("feat(TMA): Daily_Checkin write-through for BossCheckin (Stage 0 #2-#4)") — הוסיף את `_get_active_world_dict()` עם הגנה לוגית: אם יותר מ-World אחד מסומן Active, נרשם לוג אזהרה והNumber הנמוך ביותר נבחר באופן דטרמיניסטי (`tma_api.py:2253-2272`, Stage 0 #3 בתיעוד הפנימי). אין constraint אמיתי ב-Airtable עצמו — ההגנה היא קוד בלבד.
- **Merged:** כן
- **Deployed:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** אין
- **סטטוס:** Fixed — ממתין ל-Verify (constraint עצמו ברמת Airtable עדיין לא קיים — ראו AI_CONTEXT.md §8 OPEN RISKS)

### BUG-004 — BossCheckin silent no-op on text tasks
- **דווח:** 17/06/2026
- **Severity:** High — UX שובר אמון
- **Root Cause:** persisted flag לא נכתב ל-Airtable — ה"3 דברים" freeform ritual ב-BossCheckin היה no-op שקט לכל task שלא היה Roadmap task
- **תיקון:** טבלת `Daily_Checkin` חדשה + write-through מיידי
- **תוקן ב-commit:** `a462633` ("feat(TMA): Daily_Checkin write-through for BossCheckin (Stage 0 #2-#4)") — "BossCheckin's freeform 3-things ritual now writes immediately to a dedicated Daily_Checkin table instead of silently no-oping for non-Roadmap tasks (the old persisted-flag bug). One record per day, edited in place with Updated_At/Updated_By, never deleted/recreated." (מתוך commit message המלא)
- **Merged:** כן
- **Deployed:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** אין — לא נמצאה בדיקה ידנית מתועדת ב-TMA החי
- **סטטוס:** Fixed — ממתין ל-Verify

### BUG-005 — /status Telegram handler missing decorator
- **דווח:** 17/06/2026
- **Severity:** Low
- **Root Cause:** `cmd_status` איבד את ה-decorator `@bot.message_handler(commands=["status"])`
- **תוקן ב-commit:** `628d2bb` ("fix: restore /status decorator, remove TEMP DEBUG block from Hub")
- **Merged:** כן
- **Deployed:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא
- **סטטוס:** Fixed ✅ (commit 628d2bb)

### BUG-006 — Hub debug block in production
- **דווח:** 17/06/2026  
- **Severity:** Medium — security / UX
- **Root Cause:** בלוק TEMP DEBUG נשאר ב-Hub בקוד פרודקשן
- **תוקן ב-commit:** `628d2bb` ("fix: restore /status decorator, remove TEMP DEBUG block from Hub") — אותו commit כמו BUG-005
- **Merged:** כן
- **Deployed:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא
- **סטטוס:** Fixed ✅ (commit 628d2bb)

### BUG-007 — CORS 500 on OPTIONS preflight (`_venture_id` parameter mismatch)
- **דווח:** 17/06/2026 — דווח כ-CORS preflight error על `/api/ventures/<id>` (`Exception on /api/ventures/<id> [OPTIONS]`)
- **מסך / מודול:** `tma_api.py` — preflight stubs ל-`/api/approvals/<id>`, `/api/assets/<id>`, `/api/ventures/<id>`, `/api/game/quests/<id>`
- **Severity:** High — חסם כתיבה (PATCH) על כל ארבעת הנתיבים, לא רק Ventures
- **Root Cause:** לא CORS כפי שדווח — הפונקציות `_preflight_approval`/`_preflight_asset`/`_preflight_venture`/`_preflight_game_quest` קיבלו פרמטר עם `_` מוביל (למשל `_venture_id`) שלא תאם לשם המשתנה ב-URL rule (`venture_id`). Flask קורא ל-view עם `venture_id=...` כ-keyword arg, ולכן כל בקשת OPTIONS זרקה `TypeError: ... unexpected keyword argument 'venture_id'` — מטופל כ-Exception, מוחזר כ-500 שבדפדפן נראה כ-CORS preflight failure. אומת ע"י reproduction script עצמאי ב-Flask לפני ואחרי התיקון.
- **תוקן ב-commit:** `7d5cb3a`
- **תוקן ב-branch:** `claude/meta-whatsapp-phase-1-q6pp3e`
- **Merged:** לא — ממתין לאימות ידני לפני merge (לפי הנחיית המשתמש)
- **Deployed:** לא ידוע — דרוש Render deploy
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` עבר; Flask reproduction script אישר 500→204 לאחר התיקון. אין עדיין אימות בפרודקשן החיה.
- **סטטוס:** 🟡 Fixed — ממתין לאימות ידני בפרודקשן (בחירת Domain ב-Venture)

### BUG-008 — Lead Business Outcome 422 (trailing space in Airtable options) — ✅ VERIFIED / CLOSED 09/07/2026
- **דווח:** 17/06/2026 — Airtable PATCH נכשל עם `422 INVALID_MULTIPLE_CHOICE_OPTIONS`, `keys=['Business Outcome', 'status']`; ב-UI רק "סמן כמתאים" עבד, שאר כפתורי הסטטוס הציגו "update failed"
- **מסך / מודול:** `tma_api.py` — `update_lead_status`, `set_lead_outcome`, `patch_lead`; `airtable_schema.py` — קבועי `LeadStatus`/`LeadOutcome` חדשים
- **Severity:** High — חסם את כל כפתורי הסטטוס/תוצאה במסך Lead Detail מלבד אחד
- **Root Cause:** שדה `Leads."Business Outcome"` (singleSelect, `fldVa5wSmAqcKLi86`) כולל trailing space ב-7 מתוך 8 האופציות החיות שלו (`"open "`, `"needs_followup "`, `"meeting_scheduled "`, `"converted "`, `"not_relevant "`, `"lost "`, `"duplicate "` — רק `"archived"` נקי). הקוד שלח ערכים נקיים (ללא רווח), ו-Airtable (עם typecast כבוי) דחה את הכתיבה כניסיון ליצור אופציה חדשה. אומת ישירות מול הסכמה החיה דרך Airtable MCP `get_table_schema` (2026-06-17).
- **תוקן ב-commit:** `7d5cb3a`
- **תוקן ב-branch:** `claude/meta-whatsapp-phase-1-q6pp3e`
- **תיקון:** `LeadOutcome.BY_KEY` ב-`airtable_schema.py` ממפה מפתח נקי קנוני (ללא רווח) לערך המדויק בפועל ב-Airtable; `LeadStatus.ALL` לבדיקת תקינות `status`. שני השדות מאומתים לפני PATCH — אם הערך לא תקין, מוחזר 400 ברור במקום לאפשר ל-Airtable להחזיר 422.
- **Merged:** ✅ כן (מוזג בשלב מוקדם יותר — commit `7d5cb3a`).
- **Deployed:** ✅ כן.
- **Verified בפרודקשן:** ✅ כן — 09/07/2026:
  ```
  PATCH /api/leads/recLQNCnuyfoMMcV4/outcome
  PATCH Airtable /Leads/recLQNCnuyfoMMcV4 → 200 OK
  [AUDIT:gateway] keys=['Business Outcome', 'status'] ok=True
  ```
  אותו זוג שדות בדיוק מהבאג המקורי (`Business Outcome`+`status`), 200 OK, אין 422.
- **Verification ראיה:** `py_compile` עבר; `test_integration.py` 4/4 PASS; `smoke_tests.py` 5/6 PASS (כשל תלוי-סביבה, לא קשור); `npm run build` עבר. + audit-log למעלה, 09/07/2026.
- **סטטוס:** ✅ VERIFIED / CLOSED.

### FLAGGED (not fixed) — `Next Action` field schema drift
- **דווח:** 17/06/2026, תוך כדי חקירת BUG-008
- **מסך / מודול:** `airtable_schema.py` — `LeadFields.NEXT_STEP` ("Next Action")
- **תיאור:** האופציות החיות בפועל (`"Call Back"`, `"Send Details"`, `"Follow Up"`, `"Waiting Response"`, `"Create Deal"`, `"Convert Contact"`, `"Schedule Meeting "` [עם trailing space], `"Closed Won"`, `"Closed Lost"`) שונות מהותית מהערכים שהקוד מתעד (`call_now|call_today|schedule_this_week|...`).
- **למה לא תוקן:** אומת (ע"י מעקב קוד ב-`LeadDetail.tsx`) שהשדה הזה אינו נכתב בפועל מ-Lead Detail screen — `handleCreateTask()` מעדכן רק state מקומי (`updateLoadedData`), לא PATCH אמיתי. ה-drift חבוי (latent) ולא פעיל (active) — לא חלק מהבאג שדווח.
- **סטטוס:** Open — דורש ticket נפרד לפני שמישהו יחבר כתיבה אמיתית לשדה הזה

### BUG-009 — lead_conversion.py בודק את crm_add_contact בלי audit log (MEDIUM)
- **דווח:** 20/06/2026 — סשן "BOSS Security Fix Session"
- **מסך / מודול:** `lead_conversion.py` — `convert_lead_to_contact()`
- **תיאור:** `crm_add_contact()` כותב ל-Airtable ישירות, עוקף את `tools/airtable_gateway.py` — אין audit log, אין tenant scope enforcement. מפר את כלל הארכיטקטורה ב-`CLAUDE.md` ("Never import tool functions... outside of the dispatcher").
- **Severity:** Medium — לא חסם ייצור (owner-only + `LEAD_AUTO_CONVERT=false` כברירת מחדל), אבל בלי audit trail
- **Root Cause:** `lead_conversion.py` נכתב כ"פקודה עצמאית" (owner types explicit command = the approval) ולא עבר דרך ה-dispatcher; לא נדרש audit log באותה נקודה.
- **תיקון:** קריאה ל-`audit_log_airtable()` אחרי הצלחת `crm_add_contact`, עם identity-stub מינימלי (`tenant_id="system", user_id="lead_conversion", role="system"`) — לפונקציה אין identity של קורא בפועל ב-scope. תוקן ה-import path מהמפרט המקורי (`tools.airtable_tools` — לא קיים שם) ל-`tools.airtable_security` (איפה שהפונקציה באמת חיה), ותוקנה חתימת הקריאה לפי הקוד האמיתי (`tool_name, identity, params, result_snippet`) ולא לפי החתימה המשוערת במפרט (`table=, action=, details=`).
- **תוקן ב-commit:** `6e30d37`
- **תוקן ב-branch:** `main` (commit ישיר — ללא branch/PR, לפי הנחיית הסשן)
- **Merged:** כן — `main` עצמו
- **Deployed:** כן — Render hash אומת תואם ל-`59adff7` (כולל commit זה) ע"י המשתמש
- **Verified בפרודקשן:** כן (לפי אישור משתמש על Render deploy hash)
- **Verification ראיה:** `py_compile` עבר; mock test אישר שה-audit log נכתב נכון עם ה-identity stub, ושנכשל בלי לקרוס (non-fatal) כשהקריאה ל-Airtable נכשלת; `grep -n "audit_log_airtable" lead_conversion.py` על `origin/main` מאמת קיום פיזי
- **סטטוס:** Verified

### BUG-010 — tma_api.py substring match על owner_ids (LOW)
- **דווח:** 20/06/2026 — סשן "BOSS Security Fix Session"
- **מסך / מודול:** `tma_api.py` — `_get_project_cards()` (המפרט קרא לה `get_projects()` — שם שגוי, הפונקציה האמיתית אומתה ב-grep לפני התיקון)
- **תיאור:** `identity.user_id not in str(f.get("owner_ids", "") or ""))` היה substring match — `user_id="12"` תאם בטעות ל-`owner_ids="120,455"`, חושף נראות פרויקט למשתמש לא נכון.
- **Severity:** Low — דורש user_id ספציפי שהוא substring של owner_ids אחר; לא ניצול נפוץ, אבל data leak אמיתי
- **Root Cause:** בדיקת string membership גולמית במקום פיצול וניסיון התאמה מדויקת ברשימת מזהים מופרדת בפסיקים
- **תיקון:** `_owner_ids = [x.strip() for x in str(f.get("owner_ids","") or "").split(",")]` + `if identity.user_id not in _owner_ids`
- **תוקן ב-commit:** `59adff7`
- **תוקן ב-branch:** `main` (commit ישיר — ללא branch/PR)
- **Merged:** כן — `main` עצמו
- **Deployed:** כן — Render hash אומת תואם ל-`59adff7` ע"י המשתמש
- **Verified בפרודקשן:** כן (לפי אישור משתמש על Render deploy hash)
- **Verification ראיה:** `py_compile` עבר; unit test אישר ש-`"12"` לא תואם יותר ל-`"120,455"` ושהתאמות מדויקות (`"120"`, `"455"`) עדיין עובדות; `grep -n "_owner_ids" tma_api.py` על `origin/main` מאמת קיום פיזי
- **סטטוס:** Verified

### BUG-011 — app.py: אין תשובה לטלגרם כש-run_agent זורק חריגה
- **דווח:** 22/06/2026
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `app.py` — `_webhook_telegram_impl()` (ענף הודעת טקסט), `webhook_telegram()` (H1 wrapper)
- **תיאור:** ב-`_webhook_telegram_impl()`, הקריאה ל-`run_agent(text, sender_user_id, channel="telegram")` הייתה עטופה ב-`try/finally` בלבד (לא `try/except`) — ה-`finally` רק מנקה את ה-typing thread והודעת ה-thinking, אבל לא בולע את החריגה. אם `run_agent()` זרק exception, הוא המשיך לדלוף עד ל-wrapper `webhook_telegram()` (H1), שמדווח למשתמש-בעלים עם `report_error()` ואז עושה `raise` מחדש (→ Flask 500) — אף תשובה לא נשלחה למשתמש בפועל בצ'אט. הקריאה התואמת ב-`_webhook_whatsapp_impl()` (WhatsApp) סובלת מפער מבני זהה אך לא טופלה כאן — מחוץ לתחום הדיווח שצוין במפורש ("תשובה לטלגרם").
- **Severity:** High — כל חריגה לא-צפויה מתוך `run_agent()` (timeout, שגיאת Anthropic API, באג בכלי) הופכת לחוסר תשובה שקט למשתמש בטלגרם, בלי שום הודעת שגיאה.
- **Root Cause:** N09 (`core/error_reporter.py`, commit `4ac6d24`) הוסיף את ה-wrapper pattern H1/H2/H3 סביב handlers ש-renamed ל-`*_impl` — אבל ה-wrapper רק מדווח+raise, ולא בנה fallback תשובה למשתמש. הפער המבני (`run_agent()` בלי `except` מקומי) קדם ל-N09 בפועל, אבל N09 הוא ה-commit שחישף/מימש את ה-pattern שהמשתמש מתייחס אליו כ"גורם".
- **תיקון:** הוספת `except Exception as e:` סביב הקריאה ל-`run_agent()` ב-`_webhook_telegram_impl()` — קורא ל-`report_error(e, context="run_agent (telegram)")` הקיים (התראת בעלים, ללא שינוי), וקובע `reply` להודעת fallback בעברית ("⚠️ קרתה שגיאה בעיבוד ההודעה. נסה שוב בעוד רגע.") כך שהקריאה הבלתי-מותנית ל-`bot.send_message(reply_chat_id, reply)` שאחרי תמיד שולחת משהו למשתמש.
- **תוקן ב-commit:** `16ee6ae`
- **תוקן ב-branch:** `claude/bug-011-telegram-reply-fix`
- **Merged:** **כן — PR #110, מוזג ל-`main` ב-commit `a4c8f27` (22/06/2026).** תוקן 23/06/2026: המסמך תיעד "לא עדיין" באופן שגוי. אומת ישירות: `gh pr view 110` → `state: MERGED`, `mergedAt: 2026-06-22T23:06:03Z`, `mergedBy: 10026782`; `git merge-base --is-ancestor a4c8f27 main` → מאשר אב-קדמון בפועל.
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — אין עדיין סימולציית webhook עם `run_agent` שזורק חריגה בפועל מול תעבורה חיה; מומלץ לאמת ידנית
- **Verification ראיה:** `py_compile app.py` עבר; `smoke_tests.py` עבר; כל קבצי `test_*.py` + `core/router/test_router.py` עברו ללא רגרסיה. אין עדיין סימולציית webhook עם `run_agent` שזורק חריגה בפועל — מומלץ לאמת ידנית לפני "Verified בפרודקשן". `gh pr view 110` מאשר merge בפועל (לא רק commit message).
- **סטטוס:** 🟡 MERGED TO MAIN (PR #110, `a4c8f27`) — ממתין לאימות פרודקשן

### BUG-014 — BOSS אמר "אני יכול לחפש ב-Drive" בלי לחפש בפועל
- **דווח:** 23/06/2026
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `core/anti_hallucination.py` — `_NO_TOOL_CLAIMS` (gate A32, `sanitize_agent_response`)
- **תיאור:** ה-NO-TOOL-EVIDENCE gate (A32) חסם טענות הצלחה ללא tool evidence עבור Calendar/Gmail/Airtable בלבד — Drive (`search_drive`/`read_drive_file`) לא היה ברשימת `_NO_TOOL_CLAIMS` בכלל, אז כל טענה כמו "אני יכול לחפש ב-Drive" / "מצאתי את הקובץ" עברה ללא חסימה גם כש-`tool_results_log` היה ריק.
- **Severity:** Medium — אותה משפחת בעיה כמו A32 (PR #80) אך מצומצמת ל-Drive בלבד; אין סיכון כתיבה (Drive search הוא read-only), אבל פוגע באמינות תשובות הסוכן.
- **Root Cause:** `_NO_TOOL_CLAIMS` נבנה עם 3 קטגוריות בלבד (calendar/gmail/airtable) בזמן ש-A32 (PR #80) נבנה — Drive (`tools/drive_tools.py`, רשום ב-`tool_registry.py`) לא נכלל מהתחלה, ולא נוסף מאז.
- **תיקון:** נוספה רביעית ל-`_NO_TOOL_CLAIMS` — regex עברי לטענות "אני יכול לחפש ב-Drive" / "חיפשתי ב-Drive" / "מצאתי את הקובץ" / "הקובץ נמצא" / "קראתי/פתחתי את הקובץ", מותנה ב-`frozenset({"search_drive", "read_drive_file"})`. נוספו 2 self-test assertions תואמות (no-tool → blocked, with-tool → passed through).
- **תוקן ב-commit:** `7f7d059`
- **תוקן ב-branch:** `claude/bug-014-drive-evidence-gate`
- **Merged:** **כן — PR #115, מוזג ל-`main` ב-commit `cf0ded7` (23/06/2026, 00:14 UTC).** תוקן 23/06/2026: המסמך תיעד "לא עדיין" באופן שגוי. אומת ישירות: GitHub API `pulls/115` → `state: closed`, `merged_at: 2026-06-23T00:14:49Z`, `merged_by: 10026782`, `merge_commit_sha: cf0ded7`.
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — מומלץ לאמת ידנית
- **Verification ראיה:** `python3 core/anti_hallucination.py` — 33/33 self-tests עוברים (כולל 2 התרחישים החדשים); `python3 test_c53a.py` — 50/50 עובר ללא רגרסיה; `py_compile` נקי. GitHub API מאשר merge בפועל (לא רק commit message).
- **סטטוס:** 🟡 MERGED TO MAIN (PR #115, `cf0ded7`) — ממתין לאימות פרודקשן

### BUG-015 — N07 (schema_governance.py) לא תפס Media Files table שלא קיימת ב-Airtable
- **דווח:** 23/06/2026
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `schema_audit.py` — `TABLE_CLASS_MAP`; `tools/schema_governance.py` (N07) — צרכן של אותו `TABLE_CLASS_MAP`
- **תיאור:** טבלת "Media Files" הוגדרה בקוד (`airtable_schema.py` — `MediaFileFields`, F16) לפני שנוצרה בפועל ב-Airtable live, ו-N07 לא תפס את הפער. הסיבה האמיתית: `MediaFileFields` מעולם לא נוסף ל-`TABLE_CLASS_MAP` ב-`schema_audit.py` (שממנו `tools/schema_governance.py` מייבא), אז N07 פשוט לא בדק את הטבלה הזו בכלל — לא שגיאת severity, אלא חוסר בדיקה מלא. בנפרד, המקרה הקיים של "טבלה חסרה ב-live" ב-`schema_audit.py` (להבדיל מ-N07 עצמו, ששם זה כבר ERROR) טופל כ-`⚠️` warning בלבד, בלי קוד exit נכשל.
- **Severity:** Medium — drift סכמה לא מאותר הוא דפוס כשל חוזר בריפו הזה (ראה BUG-008, N07 עצמו).
- **Root Cause:** `TABLE_CLASS_MAP` ב-`schema_audit.py` לא עודכן כשנוסף `MediaFileFields`/F16 — אין מנגנון שמזהיר אוטומטית על `*Fields` class שלא רשום ב-map.
- **תיקון:** (1) הוספת `schema.Tables.MEDIA_FILES: schema.MediaFileFields` ל-`TABLE_CLASS_MAP`. (2) טבלה חסרה ב-live ב-`schema_audit.py` עכשיו מודפסת כ-`❌` (לא `⚠️`), ו-`run_audit()`/`main()` מחזירים/exit קוד שנכשל (`1`) במקום `None`/הצלחה שקטה — מתאים להתנהגות שכבר הייתה קיימת ב-N07 (`tools/schema_governance.py`) עבור המקרה הזה.
- **תוקן ב-commit:** `949d983`
- **תוקן ב-branch:** `claude/git-audit-roadmap-drift`
- **Merged:** **כן — PR #108, מוזג ל-`main` ב-commit `095b59d` (23/06/2026, 00:21 UTC).** אומת: GitHub API `pulls/108` → `state: closed`, `merged_at: 2026-06-23T00:21:39Z`, `merged_by: 10026782`.
- **Deployed:** לא ידוע — כלי CLI עצמאי, לא חלק מה-pipeline החי, אין deploy אוטומטי
- **Verified בפרודקשן:** N/A — לא נקרא מאף קוד pipeline; טרם הורץ מול live Airtable אמיתי בסביבה הזו
- **Verification ראיה:** `py_compile schema_audit.py tools/schema_governance.py` עבר; `tools/schema_governance.py --self-test` — 6/6 assertions עברו.
- **סטטוס:** 🟡 MERGED TO MAIN (PR #108, `095b59d`) — ממתין להרצה מול live Airtable

### BUG-016 — last_review_date לא מתעדכן → תזכורת אבטחה מציגה 999 ימים תמיד
- **דווח:** 23/06/2026
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `scheduler.py` — `_get_last_review_date()` / `_days_since_review()` / `_job_security_reminder()`
- **תיאור:** `LAST_SECURITY_REVIEW` נקרא רק מ-env var, שהיה אמור להתעדכן ידנית ב-Render אחרי כל review (לפי `docs/governance/SECURITY_CHECKLIST.md`) — בפועל זה לא קרה אף פעם, אז `_days_since_review()` חזר תמיד ל-fallback של 999 ימים, וההתראה השבועית תמיד הציגה "🔴 review מלא נדרש".
- **Severity:** Low — לא משפיע על אבטחה בפועל, אבל מנטרל את כל הערך של תזכורת ה-review (false-positive תמידי).
- **Root Cause:** אין שום קוד שכותב ל-`LAST_SECURITY_REVIEW` — ההסתמכות היחידה הייתה על משתמש שיזכור לערוך env var ב-Render dashboard ידנית, תהליך שלא קרה.
- **תיקון:** נוספה `record_security_review(d=None)` ב-`scheduler.py` שכותבת תאריך review מוצלח לקובץ persistent (`/tmp/security_review.json`), בדומה לתבנית הקיימת ל-emergency flags ב-`feature_flags.py`. `_get_last_review_date()` קוראת מהקובץ הזה קודם, ונופלת ל-env var רק לתאימות לאחור. הודעת התזכורת עודכנה להפנות ל-`record_security_review()` במקום לעריכת env var ב-Render.
- **תוקן ב-commit:** `949d983`
- **תוקן ב-branch:** `claude/git-audit-roadmap-drift`
- **Merged:** **כן — PR #108, מוזג ל-`main` ב-commit `095b59d` (23/06/2026, 00:21 UTC).** אומת: GitHub API `pulls/108` → `state: closed`, `merged_at: 2026-06-23T00:21:39Z`, `merged_by: 10026782`.
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — `record_security_review()` לא נקראה עדיין בפועל אחרי review אמיתי; מומלץ לאמת ידנית בריצה הבאה
- **Verification ראיה:** `py_compile scheduler.py` עבר; הורץ ידנית מקומית: `_days_since_review()` חזר 999 לפני קריאה ל-`record_security_review()`, ו-3 אחריה עם תאריך נתון — מאשר את ה-persistence.
- **סטטוס:** 🟡 MERGED TO MAIN (PR #108, `095b59d`) — ממתין להפעלה ידנית בפועל אחרי review הבא

### BUG-013 — קובץ גדול מהמותר (oversized) ב-Telegram → אין תגובה ולוגים ריקים
- **דווח:** 23/06/2026
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `app.py` — ענפי `voice`/`photo`/`document` ב-handler ה-media של Telegram (לפני הקריאה ל-`media_handler.handle_voice_note`/`handle_file_upload`)
- **תיאור:** סיווג ה-tier לפי גודל (`media_handler._classify_size`, סף 50MB) רץ רק *אחרי* ש-`bot.get_file()`/`bot.download_file()` כבר הורידו את כל הקובץ לזיכרון. בקובץ oversized זה הפעיל הורדה סינכרונית איטית/עתידה-להיכשל בתוך בקשת ה-webhook עצמה, בלי שום log או תשובה למשתמש אם הבקשה נהרגה (timeout/kill) לפני שה-`try/except` הסוגר הספיק לרוץ.
- **Severity:** Medium — חוסר תשובה שקט ומבלבל למשתמש; ללא סיכון אבטחה (read-side בלבד).
- **Root Cause:** טלגרם כבר שולח `file_size` על אובייקט ההודעה (`message.voice.file_size`/`photo.file_size`/`doc.file_size`) בלי צורך בהורדה — אבל ה-handler ב-`app.py` התעלם מזה והוריד את הקובץ קודם, והסתמך על הסיווג שב-`media_handler.py` שרץ רק על bytes שכבר ירדו.
- **תיקון:** בדיקת `_classify_size(file_size)` מול `message.voice.file_size`/`photo.file_size`/`doc.file_size` *לפני* הקריאה ל-`bot.get_file()`/`bot.download_file()`, בשני הענפים (voice ו-photo/document). קובץ oversized נדחה מיידית עם `logger.info(...)` ותשובת `FILE_TOO_LARGE` זהה לזו שהייתה מתקבלת מ-`media_handler.py` — בלי לנסות הורדה בכלל.
- **תוקן ב-commit:** `faf0c88`
- **תוקן ב-branch:** `claude/bug-013-oversized-file-tier-check`
- **Merged:** **כן — PR #117, מוזג ל-`main` ב-commit `aae59c4` (23/06/2026, 00:32 UTC).** אומת: GitHub API `pulls/117` → `state: closed`, `merged_at: 2026-06-23T00:32:16Z`, `merged_by: 10026782`.
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — מומלץ לאמת ידנית עם העלאת קובץ >50MB אמיתי בטלגרם
- **Verification ראיה:** `py_compile app.py` עבר; `media_handler.py` self-test 4/4 עבר; `test_media_layer.py` 33/33 עבר ללא רגרסיה.
- **סטטוס:** 🟡 MERGED TO MAIN (PR #117, `aae59c4`) — ממתין לאימות פרודקשן

### BUG-017 — `session_store._sync_to_db` קרא את חוזה ה-dict של `airtable_add`/`airtable_update` כ-string
- **דווח:** 25/06/2026
- **דווח על ידי:** Claude Code, תוך כדי בניית Decision Hub Stage 0.5/0.6
- **מסך / מודול:** `session_store.py` — `PersistentSessionStore._sync_to_db()`
- **תיאור:** מאז C53-A, `airtable_add()`/`airtable_update()` (ב-`tools/airtable_tools.py`) מחזירים חוזה structured `{"ok": bool, "tool": str, "external_id": str, "evidence": dict, "user_message": str}` — לא string. `_sync_to_db()` עדיין התייחס לערך החזרה כ-string (לוג/בדיקת הצלחה לפי תוכן טקסטואלי), כך שסנכרון session-state ל-Airtable דיווח הצלחה/כשל לא נכון בלי לבדוק את `ok`/`evidence` בפועל.
- **Severity:** Medium — לא גרם לאיבוד דאטה (הכתיבה בפועל ל-Airtable עדיין קרתה), אבל לוגים/דיווח הצלחה היו לא אמינים — בדיוק התבנית ש-A32/anti_hallucination נועד למנוע, רק בשכבת ה-session sync ולא בשכבת ה-agent.
- **Root Cause:** `_sync_to_db()` נכתב לפני שחוזה ה-dict הוצג (C53-A); לא עודכן כשהחוזה השתנה ב-`airtable_tools.py`, ואין בדיקת טיפוס/חוזה ב-call site שתתפוס דריפט כזה אוטומטית.
- **תיקון:** `_sync_to_db()` עודכן לבדוק `result.get("ok")` מהחוזה החדש ולהשתמש ב-`evidence`/`user_message` ללוג, במקום להתייחס לערך כ-string. תוקן **רק** `_sync_to_db` — `_load_from_db` (קורא, לא כותב) נשאר ללא שינוי, כי `airtable_get()` היא פונקציה אחרת שמחזירה string מפורמט ולא את חוזה ה-dict.
- **תוקן ב-commit:** `fdeb039`
- **תוקן ב-branch:** `claude/new-session-be1ckb`
- **Merged:** **כן — PR #147, מוזג ל-`main` ב-commit `483851f`.** אומת: `git fetch origin main` + `git merge-base --is-ancestor origin/claude/new-session-be1ckb origin/main` → exit 0.
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile session_store.py` עבר; `python3 session_store.py` self-test 18/20 עברו (2 כשלים קיימים מראש, mock-import-path bug בלתי תלוי בתיקון זה — `sys.modules["airtable_tools"]` ממוקֶה בעוד הקוד האמיתי עושה `from tools.airtable_tools import ...`); בדיקה ידנית נוספת עם mock נכון על `tools.airtable_tools` אישרה את הלוגיקה המתוקנת.
- **סטטוס:** 🟡 MERGED TO MAIN (PR #147, `483851f`) — ממתין לאימות פרודקשן
### BUG-020 — airtable_schema.py: כמה קבועי טבלה/שדה לא תאמו ל-base החי — ✅ מוזג ל-main (סטטוס עודכן 10/07/2026, doc drift שתוקן)
- **דווח:** 24/06/2026 — אודיט ידני מול "בסיס עיקרי" (`app4bcgoX7t0HUVnm`) דרך Airtable MCP (`list_tables_for_base`), אחרי שהתברר ש-`schema_cache.json` הקיים הוא seed שנוצר מהקוד עצמו ולא snapshot אמיתי מ-Airtable (ראה BUG-021).
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `airtable_schema.py`
- **תיאור:** השוואה שדה-שדה בין `class Tables` / `*Fields` ל-schema החי גילתה: `Tables.LEARNINGS = "למידות ותובנות"` בזמן שהטבלה החיה נקראת `"למידות ותובנות (Learnings & Insights)"`; `class AssetsFields` הגדיר 9 שדות עבריים ("שם הנכס", "סוג"...) לטבלת "Assets (Personal)" שלא קיימת — הטבלה החיה בשם "Assets" נבנתה לנדל"ן עם שדות אנגליים שונים בתכלית (Asset Type, Current Value, Equity, Asset Potential/Risks...); `ProfileFields.NAME = "Name"` בזמן שהשדה החי הוא `"name"` (אות קטנה), ו-`ProfileFields.PROFILE_DATA = "ProfileData"` לא קיים בכלל; `Tables.IMPORTS`/`Tables.TENANTS`/`Tables.DAILY_TASKS` מצביעים לטבלאות שלא קיימות ב-base בכלל. גם התגלתה טבלה חיה חדשה — `TRAFFIC_SOURCES` (BOSS Growth P0) — שלא הייתה מתועדת בקוד בכלל.
- **Severity:** Medium — `Tables.LEARNINGS`/`AssetsFields`/`ProfileFields`/`Tables.IMPORTS`/`Tables.TENANTS`/`Tables.DAILY_TASKS` אומתו כ-**לא נקראים משום קוד חי** (`grep` ברחבי הריפו) — drift תיעודי בלבד, לא באג פעיל. (לעומת BUG-017/018/019 למטה — אלה כן נקראים מקוד חי ונכשלים בפועל.)
- **Root Cause:** `airtable_schema.py` תיעד כוונה/תכנון שלא עודכן אחרי שהטבלאות נבנו/שונו בפועל ב-Airtable.
- **שינוי שבוצע:** עודכן ישירות ב-`airtable_schema.py` (ללא commit בזמן התיעוד המקורי): שם `Tables.LEARNINGS` עודכן; `AssetsFields` הוחלף לחלוטין לשדות האמיתיים; `ProfileFields.NAME` עודכן ל-`"name"` + הערה ש-`PROFILE_DATA` עדיין לא קיים חי; `Tables.IMPORTS`/`Tables.TENANTS`/`Tables.DAILY_TASKS`/`DailyTaskFields`/`DailyTaskStatus` סומנו במפורש כ-DEAD CODE (בדומה לסימון F13); נוסף `class TrafficSourcesFields` לתיעוד הטבלה החדשה.
- **תועד ב-commit:** commit הענף שמוסיף את BUG-020 ואת עדכון `airtable_schema.py`
- **עדכון סטטוס (10/07/2026):** התיקון עצמו **כבר ממוזג בפועל** — הרשומה הזו פשוט לא עודכנה כשזה קרה (doc drift, לא באג בקוד). מאומת ישירות מול `origin/main` עכשיו: `Tables.LEARNINGS = "למידות ותובנות (Learnings & Insights)"` (airtable_schema.py:50), `Tables.TRAFFIC_SOURCES = "TRAFFIC_SOURCES"` (airtable_schema.py:86) — שניהם קיימים בפועל. מתגלה לראשונה דרך merge ענק PR #193 (`97ebe3e`) — אותה תבנית בדיוק כמו BUG-093 (LL-13): commit ספציפי לא ניתן לאיתור מדויק כי הוא הגיע בתוך מיזוג גדול, לא PR ממוקד.
- **Merged:** ✅ כן — קיים ב-`origin/main` (מאומת `git show origin/main:airtable_schema.py`), מקור מדויק (PR/commit) לא ניתן לאיתור מעבר ל-PR #193's merge.
- **Deployed:** לא ידוע — לא אומת מול Render.
- **Verified בפרודקשן:** לא — אימות הקוד עצמו (השמות/הקבועים) בוצע, אבל לא אומת שהתנהגות חיה (כתיבה/קריאה בפועל דרך הקבועים המתוקנים) נבדקה בפרודקשן.
- **Verification ראיה:** השוואה ישירה ל-`list_tables_for_base`/`get_table_schema` החי דרך Airtable MCP, 24/06/2026 (המקור); `git show origin/main:airtable_schema.py` מאשר את הקבועים בקוד היום (10/07/2026).
- **סטטוס:** ✅ ממוזג ל-main — לא מאומת בפרודקשן (behavioral, לא code-existence).

### BUG-017 — inbound_handler.py כותב ל-LeadFields.UPDATED_AT שלא קיים ב-Leads החי — ✅ VERIFIED / CLOSED 09/07/2026
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `inbound_handler.py` — `_update_existing()`, שורות 75-86 (F06, נקרא בפועל ע"י `email_inbound.py`)
- **תיאור:** `_update_existing()` עושה PATCH יחיד ל-Leads עם 3 שדות: `SUMMARY`, `UPDATED_AT`, `EXTERNAL_ID`. `LeadFields.UPDATED_AT = "updated_at"` — שדה שלא קיים בטבלת Leads החיה (אומת דרך Airtable MCP: אין `updated_at`, יש רק `created_at`). Airtable דוחה PATCH עם שדה לא קיים (422) — **כל הבקשה נכשלת**, לא רק השדה החסר, כך שגם `SUMMARY` וגם `EXTERNAL_ID` לא מתעדכנים בפועל כשליד קיים שולח הודעה נכנסת חדשה. ה-`except` הסוגר רק כותב ל-log, אז זה נכשל בשקט.
- **Severity:** High — F06 inbound-lead gate בשימוש בפועל; כל "ליד קיים עונה שוב" לא מתעדכן בכלל ב-production.
- **Root Cause:** הקוד הניח קיומו של שדה `updated_at` שלא נוצר בפועל ב-Airtable.
- **תוקן (09/07/2026) — נרטיב מדויק:** הבאג המקורי (24/06) דיווח כתיבת `UPDATED_AT` בפועל מתוך `inbound_handler.py::_update_existing()`. באימות מול `origin/main` נקי (09/07), נתיב הכתיבה הזה **כבר לא היה קיים בכלל** — `_update_existing()` הנוכחי כותב רק `SUMMARY`+`EXTERNAL_ID` (`git log --all -S "LeadFields.UPDATED_AT" -- inbound_handler.py` לא מחזיר שום commit, כך שאי אפשר לצטט מתי/איך זה הוסר — רק לאשר שהקוד הנוכחי נקי). הסיכון האמיתי שנשאר בקוד הנוכחי היה הרשאה ישנה שנשכחה: `tools/airtable_tools.py::_TABLE_FIELDS["Leads"]` עדיין כלל `"created_at"`/`"updated_at"` ברשימת השדות המותרים — הרשאה מתה (dormant permission), לא bug פעיל, אבל סיכון אמיתי לו יכתוב אליה שוב קוד עתידי. **PR #283 מסיר את הסיכון הנשאר הזה בקוד הנוכחי. הוא לא מוסיף שדה Airtable** (לא מיישם את אופציה (א)/(ב) מהרשומה המקורית — Meta API עדיין לא כולל `updated_at`/`Last Modified Time` ב-Leads).
- **Merged:** ✅ כן — `main` `d3d0fc5` (Merge pull request #283), commit `ba5ad6d` (`fix(leads): remove non-writable timestamps from legacy allowlist`).
- **Deployed:** ✅ כן.
- **Verified בפרודקשן:** ✅ כן — 09/07/2026, ראיית audit-log ישירה:
  ```
  POST /Leads → 200 OK
  [AUDIT:gateway] table=Leads keys=[Name, phone, channel, memory_key, domain, source, status, summary, Score, sender_id, tenant_id]

  PATCH /Leads/recLQNCnuyfoMMcV4 → 200 OK
  [AUDIT:gateway] source=tma op=patch table=Leads keys=['Business Outcome', 'status'] ok=True
  ```
  לא הופיעו `created_at`/`updated_at`/`Created At`/`Updated At`/422 באף אחת מהקריאות — גם create וגם update דרך TMA עוברים נקי.
- **Verification ראיה:** ראה audit-log למעלה + `git show ba5ad6d -- tools/airtable_tools.py`.
- **סטטוס:** ✅ VERIFIED / CLOSED.

### BUG-018 — tma_api.py כותב ל-TaskFields.LEAD_LINK שלא קיים ב-Tasks החי → "צור משימה מליד" נכשל — ✅ CLOSED / PROD VERIFIED 10/07/2026
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `tma_api.py` — POST ל-`Tables.TASKS` ב-flow של "צור משימה מליד" ב-TMA, שורה 1499 (וגם 1513 ב-queue-for-approval path)
- **תיאור:** `task_fields[TaskFields.LEAD_LINK] = [lead_id]` — `TaskFields.LEAD_LINK = "Leads"`, אבל אין שדה linked-record כזה בטבלת "משימות (Tasks)" החיה (אומת דרך Airtable MCP). ה-POST השלם נכשל (500) כי Airtable דוחה שדה לא קיים — "צור משימה מליד" נכשל **בכל קריאה**, גם ל-owner וגם ב-approval flow למנהל.
- **Severity:** High — חוסם תכונה שלמה ב-TMA (יצירת משימה מתוך מסך ליד).
- **Root Cause:** הקוד הניח קיומו של שדה linked-record "Leads" על Tasks שלא נוצר בפועל.
- **תוקן:** כן — תוקן בצד Airtable schema, לא בקוד. לטבלת `"משימות (Tasks)"` נוסף/קיים כעת שדה linked-record בשם `"Leads"` שתואם ל-`TaskFields.LEAD_LINK`.
- **Merged:** N/A — אין שינוי קוד; הקוד הקיים היה נכון ביחס ל-schema הרצוי.
- **Deployed:** N/A — שינוי Airtable schema, לא deploy אפליקטיבי.
- **Verified בפרודקשן:** ✅ כן — 10/07/2026 — **ראיה קשיחה**, לא רק דיווח: POST אמיתי ל-"משימות (Tasks)" החזיר `200 OK`, `record=recbpQzwrmZdxIaDf`, עם שדות `Domain`+`Leads` שניהם נכתבו בהצלחה. `/api/leads/.../task` הצליח קצה-לקצה; `Interaction Log` → `200 OK`.
- **Verification ראיה:** production smoke אמיתי — `record=recbpQzwrmZdxIaDf`, `200 OK`, שדות `Domain`/`Leads` תקינים.
- **סטטוס:** ✅ CLOSED / PROD VERIFIED.

### BUG-019 — crm.py: כמה פונקציות כותבות/מסננות לפי שדות ש-Contacts/Deals/Payments החיים לא מכילים — ✅ CLOSED (10/07/2026)
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `crm.py` — בשימוש בפועל ע"י `scheduler.py`, `payment_reminder.py`, `lead_conversion.py`, `tools/contact_resolver.py`, ו-`tools/dispatcher.py` (`crm_mark_payment_paid`)
- **תיאור (5 תת-בעיות, כולן מאומתות מול schema חי דרך Airtable MCP):**
  - **(a) `crm_find_contact`** (שורות ~126-152): ה-formula משתמש ב-`{Name}`/`{Company}` (אנגלית) אבל השדות החיים הם `שם`/`חברה` (עברית) — החיפוש **לעולם לא מוצא תוצאה**, באף קריאה.
  - **(b) `crm_add_contact` + `crm_list_contacts`** (שורות 116, 172): משתמשים ב-`ContactFields.TYPE = "Type"` — שדה שלא קיים ב-Contacts החי (הקטגוריזציה האמיתית היום היא `Role Category`/`Specialty`).
  - **(c) `crm_add_deal` + `crm_update_deal_status` + `crm_list_deals`** (שורות ~195-273): כותבים/קוראים `DealFields.ADDRESS`/`FUNDING_COST`/`ROI`/`RISK_LEVEL`/`NOTES` — אף אחד מהם לא קיים ב-"עסקאות (Deals)" החי. `crm_add_deal` נכשל ב-422 בכתיבה הראשונה.
  - **(d) `crm_add_payment`** (שורות ~280-308): כותב ל-`PaymentFields.CONTACT="contact_id"` ו-`NOTES="notes"` — שניהם לא קיימים ב-Payments החי.
  - **(e) `crm_upcoming_payments` + `crm_overdue_payments`** (שורות ~311-380): ה-formula משתמש ב-`{סטטוס}`/`{תאריך}` (עברית) על טבלת Payments, אבל השדות החיים הם `status`/`date` (אנגלית) — תוצאה ריקה לתמיד, בלי שגיאה (תזכורות תשלום שלא שולחות כלום).
- **Severity:** High — פוגע בפונקציונליות CRM ליבתית (חיפוש אנשי קשר, יצירת עסקאות, תזכורות תשלום) שבשימוש בפועל.
- **Root Cause:** `crm.py` נכתב מול גרסה ישנה/אנגלית של הסכמה ולא עודכן אחרי שהטבלאות "אנשי קשר (Contacts)"/"עסקאות (Deals)" עברו ל-Hebrew naming ו-Payments צומצם לשדות הנוכחיים.
- **עדכון (10/07/2026) — סגור סופית: re-audit יסודי של המשתמש מול ייצוא CSV חי מ-Airtable, מאומת גם ישירות בקוד:**
  - **(a)/(b) Contacts — ✅ אין באג פעיל.** `crm_find_contact()`/`crm_add_contact()`/`crm_list_contacts()` משתמשים כולם ב-`ContactFields.NAME`/`COMPANY`/`ROLE_CATEGORY` (`"שם"`/`"חברה"`/`"Role Category"`) — תואמים בדיוק לייצוא ה-CSV החי. `ContactFields.TYPE` לא בשימוש בפונקציות אלו יותר.
  - **(e) Payments — ✅ אין באג פעיל במסלול הכתיבה.** `crm_add_payment()` כותב רק `NAME`/`AMOUNT`/`DUE_DATE`/`STATUS`/`DEAL` (`"reference"`/`"amount"`/`"date"`/`"status"`/`"deal_id"`) — תואם לייצוא ה-CSV החי. `crm_upcoming_payments`/`crm_overdue_payments` גם תואמים.
  - **(d) `PaymentFields.CONTACT`/`NOTES` — לא בשימוש בכתיבה בכלל, לא באג.** מאומת: `crm_add_payment()` מקבלת `contact_id`/`notes` כפרמטרים אך אינה כותבת אותם לשום מקום. בבדיקה נוספת: **ל-`crm_add_payment()` אין אף קורא בכל הריפו** (`grep -rn "crm_add_payment(" --include="*.py" .` → 0 hits מחוץ ל-`crm.py` עצמו) — הפונקציה אינה רשומה ב-`tool_registry.py` וגם אין לה `case` ב-`tools/dispatcher.py`, כלומר אינה נגישה ל-Agent כלל דרך לולאת הכלים החיה. אין סיכון live, אין קורא שסובל מאובדן מידע.
  - **(c) Deals — ✅ תוקן, מאומת מול ייצוא CSV חי.** שלושת הפערים שהמשתמש איתר (Address→Adress, Funding Cost %→Funding Cost, ROI %→Roi) תוקנו ב-commit `9b51537` (ישיר, `eli chazan`, PR #289), **וגם RISK_LEVEL ("Risk Level") וגם NOTES ("Notes") אושרו כתואמים ל-live ללא צורך בשינוי** — מאומת ישירות בקוד הנוכחי: `DealFields.ADDRESS="Adress"`, `FUNDING_COST="Funding Cost"`, `ROI="Roi"`, `RISK_LEVEL="Risk Level"`, `NOTES="Notes"`. **חשוב:** גם `crm_add_deal()` אין לו אף קורא בריפו ואינו רשום ב-`tool_registry.py`/`dispatcher.py` — כמו `crm_add_payment()`, אינו נגיש ל-Agent החי. **המשמעות המעשית:** אין דרך "לבדוק ב-POST אמיתי דרך התנהגות משתמש חיה" כפי שהוצע — צריך קריאה ידנית ישירה ל-`crm.crm_add_deal(...)` כדי לאשר 200 OK, לא תרחיש production ארגי.
- **תוקן:** כל 5 תת-הבעיות — סגורות ברמת הקוד. Contacts/Payments לא היו צריכים תיקון (re-verify בלבד). Deals תוקן במלואו ב-`9b51537`.
- **Merged:** ✅ כן — כולל ב-`origin/main` (`9b51537` + מיזוגים קודמים).
- **Deployed:** לא ידוע.
- **Verified בפרודקשן:** ⚠️ חלקי במובן מיוחד — Contacts/Payments בשימוש חי (`crm_find_contact`/`crm_add_contact` דרך `tools/contact_resolver.py`, ראה למעלה) ולא דווחה עדיין בעיה בפועל לאחר התיקון. Deals/`crm_add_payment` **אינם נגישים ל-Agent כלל כרגע** (לא ב-registry/dispatcher) — "אימות בפרודקשן" עליהם לא רלוונטי עד שמישהו יחבר אותם ל-dispatcher; אם וכשזה יקרה, יש לוודא POST אמיתי מצליח לפני חשיפה ל-Agent.
- **Verification ראיה:** `git show 9b51537 -- airtable_schema.py`; קריאה ישירה של `crm.py`/`airtable_schema.py`/`tool_registry.py`/`tools/dispatcher.py` על `origin/main`, 10/07/2026; re-audit מלא של המשתמש מול ייצוא CSV חי מ-Airtable (Contacts/Deals/Payments).
- **סטטוס:** ✅ CLOSED — 5/5 תת-בעיות סגורות. `crm_add_deal`/`crm_add_payment` נשארים unwired (לא רשומים ב-tool_registry/dispatcher) — לא באג, אבל שווה לזכור לפני חיבור עתידי.

### BUG-021 — schema_audit.py: UnboundLocalError במקום fallback ל-cache כשה-live fetch נכשל — ✅ כבר תוקן, לא היה מתועד (סטטוס עודכן 10/07/2026)
- **דווח:** 24/06/2026 — תוך כדי ניסיון להריץ `schema_audit.py` בלי `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` ב-env
- **דווח על ידי:** המשתמש (זוהה ע"י קלוד תוך כדי ביצוע)
- **מסך / מודול:** `schema_audit.py` — `run_audit()`, שורות 48-65
- **תיאור:** אם `sv.refresh_cache()` זורק exception (חסרי credentials), הענף `except` (שורות 53-55) רק מדפיס אזהרה "ממשיך עם cache קיים" אבל **לא בפועל טוען cache** — המשתנה `tables` נשאר לא מוגדר, והקריאה הבאה ל-`tables.get(...)` (שורה 65) קורסת עם `UnboundLocalError`. ה-fallback ל-cache עובד רק אם מריצים עם `--offline` במפורש (`sys.argv`), לא אוטומטית כמו שההודעה מבטיחה.
- **Severity:** Low — הסקריפט עצמו לא בשימוש production, אבל ההודעה המוטעה ("ממשיך עם cache קיים") מטעה את מי שמריץ אותו.
- **Root Cause:** ה-except branch לא קרא בפועל את לוגיקת ה-fallback הקיימת בענף `else` של `live=False`.
- **תוקן:** ✅ כבר תוקן בקוד — הענף `except` (`schema_audit.py:53-61` היום) **כן** טוען `tables` מ-`schema_cache.json` בפועל (`json.loads(cache_path.read_text(...))`) לפני שממשיך לביקורת — בדיוק התיקון שהוצע במקור. לא ניתן לאתר commit ממוקד — מתגלה לראשונה דרך אותו merge ענק PR #193 (`97ebe3e`) כמו BUG-020/BUG-093, אותה תבנית של doc שלא עודכן אחרי שהקוד תוקן.
- **בדיקה (הורצה בפועל, 10/07/2026):** שחזור התרחיש המדויק מהדיווח — `AIRTABLE_API_KEY=""` `AIRTABLE_BASE_ID=""` `python3 -c "import schema_audit; schema_audit.run_audit(live=True)"` — **לא קורס**. פלט אמיתי: `"⚠️ לא ניתן לשלוף schema: AIRTABLE_API_KEY / AIRTABLE_BASE_ID חסרים"` ואז `"ממשיך עם cache קיים (אם יש)"`, ומיד אחריו דוח mismatches מלא ואמיתי מתוך `schema_cache.json` (למשל `Leads: 'updated_at' ב-Airtable אך לא בקוד`, `Assets: 'Asset Potential' בקוד אך לא ב-Airtable`) — מוכיח שה-except branch נכנס בפועל וטען את ה-cache בהצלחה, לא רק שהקוד "נראה" מתוקן.
- **Merged:** ✅ כן — קיים ב-`origin/main` (מאומת ישירות דרך הרצה אמיתית של הקוד).
- **Deployed:** N/A — סקריפט פיתוח, לא production.
- **Verified בפרודקשן:** N/A — סקריפט פיתוח, לא production.
- **Verification ראיה:** הרצה אמיתית מול `origin/main`, 10/07/2026 — ראה "בדיקה" למעלה.
- **סטטוס:** ✅ תוקן, ממוזג — אין exposure חי מלכתחילה (סקריפט dev-only).

### BUG-022 — SPEC_DAILY_CHANGES_AUDIT.md מניח קיומה של reports/daily_changes/ — לא קיימת, לא הייתה קיימת
- **דווח:** 29/06/2026
- **דווח על ידי:** המשתמש, באמצעות `SPEC_DAILY_CHANGES_AUDIT.md` (סשן audit לתיעוד יומי)
- **מסך / מודול:** `reports/daily_changes/` (תיקייה שלמה)
- **תיאור:** ה-SPEC מניח שקיימות תיקיות-תאריך תחת `reports/daily_changes/` עם שינויים מתועדים
  לאימות מול `main`. בבדיקה: התיקייה לא קיימת ב-`main` (`ls reports/daily_changes/` → No such
  file or directory), לא קיימת בשום branch אחר (`phase-3-contacts`, `phase-4-knowledge`,
  `phase-5-marketing`, `test/stale-airtable-gateway`), ולא קיימת אף-פעם בהיסטוריית git
  (`git log --all --diff-filter=A --name-only -- '*daily_changes*'` החזיר 0 תוצאות). זהו
  ❌ MISSING שמיושם על קלט ה-audit עצמו, לא על feature בקוד — הוחל הכלל הרלוונטי מה-SPEC
  באופן רפלקסיבי.
- **Severity:** Low — אין משתמע נזק לפרודקשן; התוצאה היא ש-audit השינויים היומי לא יכול
  להתבצע על קלט שלא קיים, ולא יותר מזה.
- **Root Cause:** ה-SPEC נכתב מול תהליך/מבנה תיקיות מתוכנן או רצוי שלא נוצר בפועל באף סשן קודם —
  אין רישום שהתיקייה אי-פעם הכילה תוכן.
- **תוקן:** התיקייה `reports/daily_changes/` נוצרה (ריקה מתוכן היסטורי, מכילה רק את
  `AUDIT_SUMMARY.md` של audit זה) כדי שסשנים עתידיים יוכלו להתחיל לתעד שינויים יומיים לפיה.
  לא בוצע שום שינוי קוד/ארכיטקטורה.
- **Merged:** ראה commit ה-audit (`docs: daily_changes audit 29/06/2026`)
- **Deployed:** N/A — שינוי תיעוד בלבד
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** `ls`, `git log origin/main --oneline -5`, `git branch -a`,
  `git ls-tree -r <branch> --name-only | grep daily_changes` (לכל branch מרוחק), ו-
  `git log --all --diff-filter=A --name-only -- '*daily_changes*'` — כולם הוצגו ב-
  `reports/daily_changes/AUDIT_SUMMARY.md`.
- **סטטוס:** ✅ נסגר — לא היה באג בקוד, הייתה הנחת-קלט שגויה ב-SPEC; התיקייה נוצרה, אין פעולה נוספת דרושה.

### BUG-023 — "ליד חדש" כתב-דרס Name Primary Field + memory_key lookup לא-אחיד (BUG-NEW-01/02, כבר תוקן)
- **דווח:** 29/06/2026 — התגלה תוך עיבוד `BOSS_Manual_Verification_ChecklIST_UPDATED2.docx` (Part 3 — שרידי שיחת פיתוח שהיו מוטבעים בתוך הקובץ)
- **דווח על ידי:** זוהה ע"י Claude Code תוך grep-אימות מול `main`, לא דווח במפורש ב-checklist עצמו (לא היה לו ID פורמלי — מסומן בקוד כ"BUG-NEW-01"/"BUG-NEW-02")
- **מסך / מודול:** `identity.py::resolve_identity()` (זיהוי משתמש לא-מוכר), `lead_capture.py::capture_inbound_lead()`
- **תיאור:** שני באגים נפרדים שתועדו ותוקנו יחד:
  1. **BUG-NEW-01:** `identity.py` החזיר `display_name="ליד חדש"` לכל מספר לא-מוכר. `lead_capture.py` כתב `LeadFields.NAME = identity.display_name or identity.external_id` — כך שכל ליד חדש קיבל את המחרוזת הליטרלית "ליד חדש" בשדה Name, שהוא ה-**Primary Field** של Airtable (מוצג בכל Linked Record בכל טבלה אחרת) — מה שגרם לתחושה שכל הלידים "מזוהים" באותו שם.
  2. **BUG-NEW-02:** חיפוש כפילות בוצע מול `memory_key` לא-אחיד (`whatsapp:{external_id}` במקום `boss_hq:{external_id}` הקנוני) — יכול היה לגרום ל-false negative בבדיקת "ליד קיים".
  3. **תיקון נלווה (אותו commit):** `lead_capture.py` קרא ל-`airtable_add()` וציפה למחרוזת (`if "✅" in result`), בעוד `airtable_add()` מחזיר `dict` לפי חוזה C53-A — קריסת `TypeError` שקטה שנתפסה ב-`except` כללי.
- **Severity:** High — באג #1 משפיע על Primary Field, מתפשט ויזואלית לכל הטבלאות המקושרות; השתקף בנתוני production אמיתיים (ראו evidence).
- **Root Cause:** `identity.py` ניסה לתת ערך ידידותי-לתצוגה ("ליד חדש") במקום להשאיר את ה-Name לקוד הצרכן (`lead_capture.py`) למלא מה-`external_id` (טלפון). הצימוד הזה לא תועד/נבדק כשנכתב לראשונה.
- **תוקן ב-commit:** `ca1f5a0` ("Apply CXX lead capture and identity fixes") — `display_name=""` (ריק בכוונה, ראה הערה ב-`identity.py:267-273`), `lead_capture.py` עבר ל-`ActionResult`/`ClaimType` (חוזה C53-A מלא, לא בדיקת `"✅" in result`), וחיפוש כפילות מתבסס בלעדית על `identity.memory_key`.
- **Merged:** **כן — מאומת: `git merge-base --is-ancestor ca1f5a0 origin/main` → exit 0** (origin/main = `e735bf7`).
- **Deployed:** לא אומת מהסביבה הזו (אין Render dashboard access).
- **Verified בפרודקשן:** ✅ חלקי — ראיית-לוג אמיתית מתוך `BOSS_Manual_Verification_ChecklIST_UPDATED2.docx` (V1-04, מתוך מייל עם רשימת לידים בפועל) מציגה ליד עם `שם: ליד חדש` ו-`תאריך יצירה: 26/6/2026` ו-`15/6/2026` — **לפני** התיקון (`ca1f5a0` מתאריך 28/06/2026 23:52). כלומר הבאג היה פעיל בפרודקשן והשפיע על רשומות אמיתיות; אין עדיין ראיה ישירה (לוג/screenshot) שליד שנוצר **אחרי** ה-commit מקבל את הטלפון כ-Name כראוי — מומלץ לאמת ב-בדיקה הבאה (LL-01/LF-01 עם ליד טרי).
- **Verification ראיה:** `grep -n "ליד חדש\|display_name" identity.py` → שורות 267-273 (הערת BUG-NEW-01 ROOT CAUSE FIX + `display_name=""`); `git show ca1f5a0 -- identity.py lead_capture.py` מציג את הדיף המלא; checklist evidence מצוטט מעל.
- **Production smoke 09/07/2026:** ליד חדש שנוצר היום לא נשמר בשם "ליד חדש" הליטרלי — `Name='מתעניין במיטות עץ'`, `record=recZBwXryhG7QfgCd`. **תומך בתיקון, אך לא סוגר סופית:** הבדיקה הייתה דרך owner dictation/Telegram, לא flow חיצוני נקי של ליד אמיתי חדש (מספר טלפון חדש שמעולם לא נראה במערכת). **סטטוס: partially verified — לא לסגור כ-Verified מלא עד בדיקה ממספר חיצוני חדש לגמרי.**
- **סטטוס:** 🟡 MERGED TO MAIN (`ca1f5a0`) — 🟡 Partially Verified 09/07/2026 (smoke test דרך owner dictation) — עדיין ממתין לאימות מלא עם ליד **טרי ממספר חיצוני חדש לגמרי**.

### FLAGGED (cleanup candidates, not bugs) — קוד מת ב-airtable_schema.py / קובץ cache מטעה — 3/4 נמחקו 10/07/2026
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **תיאור:** אומת ב-`grep` (0 שימושים מעבר להגדרה עצמה):
  - **✅ נמחק (10/07/2026)** — `class ImportsFields` + `Tables.IMPORTS` — הטבלה "Imports" לא קיימת ב-Airtable החי, ואין קובץ אחר שמשתמש בקבועים האלה.
  - **✅ נמחק (10/07/2026)** — `class TenantsFields` + `Tables.TENANTS` — הטבלה "Tenants" לא קיימת חי; `tenant_provisioner.py` (F08) לא מייבא מ-`airtable_schema` בכלל, אין תלות.
  - **✅ נמחק (10/07/2026)** — `class DailyTaskFields` + `class DailyTaskStatus` + `Tables.DAILY_TASKS` — הטבלה "Daily_Tasks" לא קיימת חי. `tma_api.py:27` **כבר לא** מייבא `DailyTaskFields`/`DailyTaskStatus` (נוקה מוקדם יותר, בנפרד מהמחיקה הזו — grep מאשר 0 שימוש לפני המחיקה). re-grep אחרי המחיקה: `grep -rn "ImportsFields\|TenantsFields\|DailyTaskFields\|DailyTaskStatus\|Tables\.IMPORTS\b\|Tables\.TENANTS\b\|Tables\.DAILY_TASKS\b" --include="*.py" .` → 0 hits. `python3 -m py_compile airtable_schema.py` עבר; `smoke_tests.py`/`test_integration.py` — כולם ירוקים, אפס רגרסיה.
  - **🟡 עדיין פתוח, לא נגעתי** — `schema_cache.json` (root) — מכיל `"fetched_at": "seed-from-schema-py"`, כלומר לא snapshot אמיתי מ-Airtable אלא seed שנוצר מתוך הקוד עצמו. **לא נמחק בסבב הזה** — בניגוד לשלוש המחלקות למעלה (0 תלות אמיתית), הקובץ הזה הוא ה-fallback הפעיל בפועל של `schema_audit.py`'s except branch (BUG-021, כבר מאומת שעובד נכון) — מחיקתו תסיר את רשת הביטחון הזו (גם אם באופן fail-safe: `except FileNotFoundError` קיים ומחזיר `False` בלי קריסה). דורש החלטה נפרדת: למחוק / לרענן עם credentials אמיתיים / להשאיר כפי שהוא.
- **סטטוס:** 🟡 3/4 נסגרו (המחלקות המתות נמחקו). `schema_cache.json` נשאר Open — ממתין להחלטה נפרדת.

---

## פיצ'רים (לא באגים) — מעקב אימות

### FEATURE — Approval Policy: Emergency Window + OTP + Policy Gate (ROADMAP C56)
- **דווח/תוכנן:** 17/06/2026 — לפי `Approval_Policy_Spec.md`
- **מסך / מודול:** `core/emergency_window.py` (phase 1), `core/otp.py` (phase 2), `tma_api.py` — `_queue_tma_write_approval` policy gate (phase 3); טבלת Airtable `Emergency_Window` (`tblyC9hb6INMUCOkR`); `tma-frontend/src/api.ts` — header `X-TMA-Platform`
- **תיאור:** שכבת אישור מדורגת לפי סיכון (Low/Medium/High/Critical) × פלטפורמה (mobile/desktop). Low תמיד מותר; Medium מהטלפון דורש אישור כפול (`confirmed`); High מהטלפון דורש Emergency Window פעיל + OTP; Critical לעולם לא מהטלפון, ודורש OTP בכל מצב — כולל desktop. `web` מסווג כ-mobile (fail-closed — Telegram Web עשוי לרוץ בדפדפן בטלפון). חסר platform header = mobile (fail-closed). Emergency **Window** (חריג מבוקר ל-High) ≠ Emergency **Stop** (C33, מקפיא הכל).
- **תוקן/מומש ב-commits:** `8209d36` (phase 1: טבלה + `emergency_window.py`), `a57fd7f` (phase 2: `otp.py`), `44457dd` (phase 3: policy gate + 3-tuple status + frontend header), `92e4b2b` (CORS `X-TMA-Platform` header + derived RISK_LEVEL write) — **merge commit `4e933b0`**
- **תוקן ב-branch:** `claude/meta-whatsapp-phase-1-q6pp3e`
- **Feature Flag:** `EMERGENCY_WINDOW` — **כבוי כברירת מחדל.** דגל כבוי = התנהגות זהה 100% להיום (כולל 202 קשיח).
- **Merged:** **כן — PR #69, מוזג ל-`main` ב-commit `4e933b0` (17/06/2026).** תוקן 23/06/2026: המסמך הזה תיעד "לא" באופן שגוי במשך 6 ימים. אומת ישירות: `gh pr view 69` → `state: MERGED`, `mergedAt: 2026-06-17T18:56:00Z`, `mergedBy: 10026782`; `git merge-base --is-ancestor 4e933b0 main` → מאשר אב-קדמון בפועל (לא רק PR status).
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main`, כך שמיזוג ל-`main` ככל הנראה הפעיל deploy אוטומטי, אך **לא אומת ידנית** מול Render Dashboard מהסביבה הזו. `EMERGENCY_WINDOW` נשאר כבוי כך שגם אם ה-deploy רץ, אין שינוי התנהגות בפרודקשן.
- **Verified בפרודקשן:** לא — ממתין לאימות ידני לפני הדלקת `EMERGENCY_WINDOW`
- **Verification ראיה:** `py_compile` עבר על `tma_api.py`; `npm run build` עבר; `smoke_tests.py` 5/6 PASS (כשל `anthropic` import תלוי-סביבה, ידוע מראש); מטריצת 12 תרחישים (Low/Medium/High/Critical × mobile/desktop/web + window on/off + OTP) אומתה מול קוד הגייט האמיתי — כולל אימות חוזר ש-`web` נחסם כ-mobile וש-flag off מחזיר 202 זהה. אין עדיין אימות בפרודקשן החיה.
- **סטטוס:** 🟡 MERGED TO MAIN (PR #69, `4e933b0`) — flag off, ממתין לאימות פרודקשן לפני הדלקת `EMERGENCY_WINDOW`
### FEATURE — "/update" Business Memory command (ספק שכינה אותו "C20")
> ⚠️ **שם מתנגש:** ROADMAP.md מיועד ל-C20 = "Scheduler" (קיים, לא קשור). הפיצ'ר הזה תועד כאן בלי ה-ID כדי לא להחריף את הבלבול — לא להשתמש ב-"C20" כהפניה ל-ROADMAP בהקשר הזה.
- **דווח/תוכנן:** 19/06/2026
- **מסך / מודול:** `cmd_update.py` (חדש) — פקודת `/update`/`/עדכון` ל-Telegram; `app.py` — רישום הפקודה; `context.py` — הזרקת "זיכרון עסקי" אחרון ל-system prompt לפי domain
- **תיאור:** owner/manager/partner יכולים לתעד אירוע עסקי דרך inline keyboard (domain → סוג אירוע → טקסט חופשי) שנכתב לטבלת Airtable "Business Memory", ומוזרק חזרה כקונטקסט לסוכן בפניות עתידיות מאותו domain. State TTL 30 דק', `/cancel` נתמך.
- **תוקן/מומש ב-commits:** `5e9816c` (feat), `e82d4ee` (hardening — `m.text=None` guard, `identity.is_owner` ב-permission check, `domain_id or domain` fallback, מיפוי "שיחה"→"Other" במקום "Announcement")
- **תוקן ב-branch:** `claude/c20-business-update-command-sp7h2i` → PR #85 → `main` (commit מיזוג `3887d62`)
- **Feature Flag:** `FEATURE_BUSINESS_UPDATE` — **כבוי כברירת מחדל** (לא רשום ב-`_DEFAULTS`, ברירת המחדל של `is_enabled()` היא off לכל דגל לא רשום)
- **Merged:** כן — `origin/main`
- **Deployed:** לא ידוע — דרוש בדיקה ידנית ב-Render
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` על שלושת הקבצים; `smoke_tests.py`/`test_integration.py` עברו; סימולציה ידנית (mock bot/Airtable) על תשעה תרחישי ספק + 4 תיקוני reviewer. אין אימות בפרודקשן.
- **סטטוס:** 🟡 CODE COMPLETE — flag off, ממתין לאימות פרודקשן

### FEATURE — Origin Lead linking בהמרת ליד→איש קשר (ספק שכינה אותו "C21")
> ⚠️ **שם מתנגש:** ROADMAP.md מיועד ל-C21 = "Daily Digest" (קיים, לא קשור). אותה הערה כמו לעיל — לא להשתמש ב-"C21" כהפניה ל-ROADMAP בהקשר הזה.
- **דווח/תוכנן:** 20/06/2026
- **מסך / מודול:** `airtable_schema.py` — `ContactFields.ORIGIN_LEAD`/`DealFields.ORIGIN_LEAD`; `crm.py` — `crm_add_contact(lead_source_id=...)`; `lead_conversion.py` — `convert_lead_to_contact()` מעביר `lead["id"]`
- **תיאור:** שדה linked-record "Origin Lead" קיים בפרודקשן (`fldGE1seCyCdWJGCO` ב-Contacts, `fldoobGq4PS78C0Em` ב-Deals — אומתו ע"י המשתמש לפני התחלת העבודה). `/convert` כותב כעת `[lead_source_id]` לשדה הזה כדי לשמר עקיבות ליד→איש קשר.
- **תוקן/מומש ב-commit:** `ed172fc`
- **תוקן ב-branch:** `claude/c21-lead-source-linking` → PR #86 → `main` (commit מיזוג `9a7ccc2`)
- **Feature Flag:** N/A — תלוי רק ב-`LEAD_AUTO_CONVERT` הקיים
- **Merged:** כן — `origin/main`
- **Deployed:** לא ידוע — דרוש בדיקה ידנית ב-Render
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` עבר; `smoke_tests.py` עבר; mock test אישר כתיבת `{"Origin Lead": ["recLEAD..."]}` כש-`lead_source_id` מועבר, והיעדר המפתח כשהוא לא מועבר; mock נוסף אישר ש-`convert_lead_to_contact()` מעביר את `lead["id"]` כ-`lead_source_id` בפועל. אין אימות בפרודקשן.
- **סטטוס:** 🟡 CODE COMPLETE — ממתין לאימות פרודקשן

### SPEC-001 — F13 shim signatures לא תאמו את הקוד האמיתי
- **דווח:** 20/06/2026
- **דווח על ידי:** ספק ה-spec (F13 — TenantConfig + Provider Interfaces)
- **מסך / מודול:** `providers/airtable_shim.py`, `providers/twilio_shim.py`
- **תיאור:** ה-spec המקורי הניח קיומן של פונקציות/חתימות שלא קיימות בקוד:
  - `tools/airtable_gateway.py` — אין `gateway_add`/`gateway_update`/`gateway_delete`. הפונקציות האמיתיות הן `airtable_create(table, fields, source=...)` ו-`airtable_patch(table, record_id, fields, source=...)`; אין פונקציית delete בכלל.
  - `tools/airtable_tools.py` — `airtable_get(table, filter_formula="")` מחזיר `str` מפורמט, לא `list[dict]`, ואין לו פרמטר `max_records`.
  - `core/output_gateway.py` — אין `send_via_cog`. נקודת הכניסה האמיתית היא `send_outbound(envelope: OutboundEnvelope)`, ול-`OutboundEnvelope` יש שדה חובה `audience: AudienceClass` בלי default, שדה `recipient` (לא `to`), ואין שדה `media_url` (יש `meta: dict`).
  - `app.py._validate_twilio_signature()` לא מקבל פרמטרים — קוראת את Flask `request` global ישירות, ולא ניתן לעטוף אותה בחתימה `(request_headers, request_body)` בלי לשנות את הפונקציה הקיימת.
- **Severity:** Low — התגלה לפני implementation, לא הגיע לקוד production
- **Root Cause:** ה-spec נכתב מול ארכיטקטורה מתוכננת/רצויה ולא מול שמות הפונקציות/dataclasses בפועל בקוד.
- **תוקן:** ה-shims נכתבו מול החתימות האמיתיות (`airtable_create`/`airtable_patch` + `_resolve_table()` alias resolution + raw REST ל-`get()`; `send_outbound(OutboundEnvelope(...))` עם `audience=AudienceClass.CUSTOMER`, `recipient=`, `meta={"media_url":...}`). שתי פונקציות שאין להן מימוש תואם בקוד הקיים (`delete()`, `validate_inbound()`) נשארו stubs שמצהירים `NotImplementedError` במקום להעמיד פנים שהן עובדות.
- **תוקן ב-commit:** (ראה commit F13 בהמשך)
- **תוקן ב-branch:** `claude/claude-md-docs-u8kbsc`
- **Feature Flag:** N/A — קבצים חדשים בלבד, לא מחוברים ל-pipeline החי
- **Merged:** לא עדיין
- **Deployed:** לא
- **Verified בפרודקשן:** לא — אין צורך, אין caller חי
- **Verification ראיה:** `py_compile` על 6 הקבצים החדשים; `smoke_tests.py` ו-`test_integration.py` עברו ללא רגרסיה; שלוש בדיקות import (`core.tenant_config`, `providers.interfaces`+שלושת ה-shims, `isinstance(...)` מול כל Protocol) עברו.
- **סטטוס:** 🟡 CODE COMPLETE — קבצים חדשים בלבד, לא מחוברים ל-pipeline

### BUG-018 — Mojibake encoding corruption ב-app.py (132 שורות, הודעות live ללקוח)
- **דווח:** 25/06/2026
- **דווח על ידי:** המשתמש, עם שורות דוגמה גיבריש (354/360/365 בדיווח, מספרי שורה זזו מאז)
- **מסך / מודול:** `app.py` — תוכן הקובץ עצמו, לא רינדור טרמינל
- **תיאור:** 132 שורות ב-`app.py` (טקסט עברי קשיח + סימני פיסוק/אמוג'י) היו פגומות פיזית בקובץ המאוחסן — לא תקלת תצוגה. הקובץ עבר round-trip שגוי: bytes מקוריים ב-UTF-8 פוענחו פעם אחת כ-cp1255 (Windows Hebrew), והתוצאה (מחרוזת שגויה) נשמרה שוב כ-UTF-8 — מה שקיבע את השגיאה לתמיד בתוך הקובץ. הפגיעה כיסתה גם מילים בעברית (78 שורות עם תו Geresh ׳ כסימן היכר) וגם סימנים כמו קו מפריד ─/═, חצים →, ואמוג'י (✅❌🪙⏳🎮 וכו', 54 שורות נוספות). חלק גדול מהשורות הן הודעות **live ללקוח**: `/done`, `/quest`, `/coins`, `/convert`, זרימת ה-Approval (כפתורי אישור/ביטול, הודעות תוקף/הצלחה/כשלון), תגובות fallback של הסוכן, ו-Voice IVR fallback.
- **Severity:** High — גיבריש מגיע בפועל למשתמשי production בהודעות תפעוליות שכיחות.
- **Root Cause:** עיבוד היסטורי (לא ידוע מתי/איך) שפיענח את bytes ה-UTF-8 המקוריים כ-cp1255 (כולל fallback ל-raw byte value לתווי בקרה C1 שלא מוגדרים ב-cp1255 הרשמי, למשל 0x9C/0x9D/0x9E/0x9F/0x90/0x8F/0x9A) ולא כ-UTF-8, ואז שמר את התוצאה השגויה כ-UTF-8 תקין — מה שמנע מ-`UnicodeDecodeError` להתגלות בכל קריאה רגילה של הקובץ.
- **תוקן:** שוחזר טקסט מקורי ב-132 השורות באמצעות round-trip הפוך (`line.encode('cp1255', fallback=raw-byte)` ואז `.decode('utf-8')`) — שיטה מאומתת אוטומטית (כל שורה שעברה בהצלחה את ה-round-trip ושינתה תוכן, אומתה ידנית בקריאת diff מלא). BOM של הקובץ נשמר. לא בוצע שינוי בשום שורה אחרת.
- **תוקן ב-commit:** `b5717da` (+ `80ae008` תיקון תיעוד), **merge commit `9f408e7`**
- **תוקן ב-branch:** `claude/new-session-be1ckb`
- **Feature Flag:** N/A — תיקון טקסט בלבד, אין שינוי לוגיקה/זרימה
- **Merged:** כן — PR #154, `9f408e7`, מאומת עצמאית דרך `mcp__github__pull_request_read` (`merged: true`, `merged_by: 10026782`) וגם `git fetch origin main` (`9f408e7` הוא tip של `origin/main`, ה-branch נמחק מה-remote)
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile app.py` עבר; `smoke_tests.py` (2 כשלים קיימים מראש — `flask`/`httpx` חסרים בסביבה, לא קשור); `test_integration.py` 4/4; `session_store.py` self-tests 40/40; `test_c53a.py` 50/50; `git diff --stat` מאשר 132 שורות בלבד שונו; סריקה חוזרת (Geresh + raw C1 control chars) מאשרת 0 שורות פגומות שנותרו; `file app.py` מאשר UTF-8-with-BOM תקין.
- **תיקון משני שנבדק ונדחה:** הדיווח המקורי שיער גם שערבוב `parse_mode="Markdown"`/`"MarkdownV2"` הוא גורם נוסף לגיבריש (שורה ~356). בבדיקה: שורה זו (היחידה שמשתמשת ב-MarkdownV2 בכל הקובץ) מבצעת escape נכון לשני התווים המיוחדים שהיא כוללת (`\!`, `\+`) — לא נמצא באג escaping בפועל. הגיבריש שנראה באותה שורה היה תוצאה של אותה תקלת encoding, לא של parse_mode. לכן **לא** מומלץ מעבר גורף ל-`parse_mode="HTML"` בכל קריאות ה-`send_message` — זה שינוי scope רחב ולא קשור לבאג שדווח, ויחייב המרת כל עיצוב `*bold*`/`_italic_` קיים לתגי HTML.
- **סטטוס:** ✅ מוזג ל-`main` — ממתין לאימות פרודקשן (Render deploy + בדיקה ידנית של הודעה בעברית)

## TEST-GAP-001 — error_reporter.py
**תאריך:** 23/06/2026
**מה חסר:** אין בדיקות ל-`core/error_reporter.py` — PII sanitization, rate limit, Telegram send.
**Piggyback Trigger:** כל שינוי ב-`core/error_reporter.py`

## TEST-GAP-002 — finance_pulse endpoint
**תאריך:** 23/06/2026
**מה חסר:** אין בדיקות ל-`GET /api/finance/pulse` — view=all/active/overdue, domain injection guard.
**Piggyback Trigger:** כל שינוי ב-`finance_pulse()` ב-`tma_api.py`

## TEST-GAP-003 — contact_merge.py
**תאריך:** 23/06/2026
**מה חסר:** אין בדיקות ל-`contact_merge.py` — merge logic, dedup, vCard parsing.
**Piggyback Trigger:** לפני wire לפרודקשן

---

## Session 28-29/06/2026 — Lead Lifecycle Stabilization (BUG-NEW-01 עד BUG-META-01)

### BUG-024 (BUG-NEW-01) — Score ריק בליד חדש
- **תאריך:** 28/06/2026
- **קובץ:** `lead_capture.py`
- **שורש:** `LeadFields.SCORE` לא נכלל ב-`fields` בעת יצירת ליד חדש
- **תיקון:** הוספת `LeadFields.SCORE: 0` ל-allowlist של שדות יצירה
- **Evidence:** Airtable screenshot — Score ריק לפני, Score=0 אחרי
- **Regression:** T02 ב-`anti_hallucination.py`
- **PR:** #169
- **סטטוס:** ✅ תוקן ומוזג

### BUG-025 (BUG-NEW-01b) — Primary Field corruption
- **תאריך:** 28/06/2026
- **קבצים:** `identity.py`, `lead_capture.py`
- **שורש:** `display_name="ליד חדש"` → Name=Primary Field מושחת בכל Linked Record
- **תיקון:** `display_name=""` → `lead_capture` כותב `external_id` (טלפון) כ-Name
- **Evidence:** Airtable — עמודות מציגות "ליד חדש" לפני תיקון
- **Regression:** T01 ב-`anti_hallucination.py`
- **הערה:** ראו גם BUG-023 שתיעד את אותה בעיה מזווית ה-Primary Field. BUG-025 מתמקד ב-display_name fix כחלק מסדרת תיקוני Lead Lifecycle.
- **PR:** #169
- **Production smoke 09/07/2026:** ראה BUG-023 — ליד חדש היום לא הציג "ליד חדש" הליטרלי (`Name='מתעניין במיטות עץ'`), אבל דרך owner dictation, לא מספר חיצוני חדש לגמרי. תומך בתיקון, לא סוגר.
- **סטטוס:** ✅ תוקן | 🟡 Partially Verified 09/07/2026 (smoke test) | ⚠️ אימות מלא עם מספר חיצוני חדש לגמרי — עדיין ממתין

### BUG-026 (BUG-NEW-02) — dict error ב-`airtable_add` return value
- **תאריך:** 28/06/2026
- **קובץ:** `lead_capture.py`
- **שורש:** `airtable_add` עודכן לחוזה C53-A (מחזיר `dict`). `lead_capture` המשיך `re.search`/string
- **Evidence:** `[LeadCapture] capture_inbound_lead error: expected string or bytes-like object, got 'dict'`
- **תיקון:** `ActionResult.from_airtable_add(raw_result)`
- **Regression:** T09 ב-`anti_hallucination.py`
- **PR:** #169
- **סטטוס:** ✅ תוקן ומוזג

### BUG-027 (BUG-NEW-03) — `airtable_security` audit crash על dict
- **תאריך:** 29/06/2026
- **קובץ:** `tools/airtable_security.py` שורה 95
- **שורש:** `result_snippet[:60]` על `dict` → `TypeError: unhashable type: 'slice'`
- **תיקון:** `str(result_snippet)[:60]` + `try/except` — audit לא שובר פעולה עסקית
- **Evidence:** לוג Render: `TypeError: unhashable type: 'slice'`
- **Evidence לתיקון:** 9/9 self-tests
- **PR:** #172
- **סטטוס:** ✅ תוקן ומוזג

### BUG-028 (BUG-NEW-04) — Agent כותב ישירות ל-Leads
- **תאריך:** 29/06/2026
- **קבצים:** `tools/airtable_security.py`, `tools/dispatcher.py`
- **שורש:** אין חסימה — Agent יכול `airtable_add` ישיר ל-Leads, עוקף `capture_inbound_lead`
- **Evidence:** `[Tool] airtable_add | {'table': 'Leads', 'fields': {'Name': 'משה חביב'}}`
- **תיקון:** `enforce_leads_write_gate()` + `LeadsDirectWriteBlocked`
- **מותר:** `lead_capture` | `lead_event` | `lead_scoring` | `crm`
- **חסום:** `agent`
- **Evidence לתיקון:** 6/6 gate tests + 9/9 security tests
- **PR:** #172
- **עדכון 09/07/2026 (policy re-review, ראה BUG-090):** נבדק מחדש אם `enforce_leads_write_gate()` צריך להכליל לטבלאות נוספות (Business Memory/Contacts/Deals), בעקבות עבודה על BUG-081/086/087. **הוכרע לא לגעת:**
  ```
  DECISION (09/07/2026): Leads' structural source-gate (BUG-028) remains
  Leads-specific by design. Other tables rely on requires_approval (tool_registry.py)
  as their write-gate — sufficient given no corruption history exists for them.
  Revisit ONLY if a similar repeated-failure pattern emerges for another table.
  ```
  לא PR, לא שינוי קוד — `tool_registry.py`'s `requires_approval=True` על `airtable_add`/`airtable_update` כבר עוצר ביצוע כל כתיבה יזומת-Agent (לכל טבלה) בתור אישור, ללא תלות ב-table-specific gate.
- **Verified בפרודקשן (09/07/2026):** ✅ כן — ראיית לוג ישירה שה-gate עצר כתיבה אמיתית:
  ```
  [LeadsWriteGate] BLOCKED direct Leads write | tool=airtable_update source=agent table=Leads
  ```
  השאלה המקורית ("האם כתיבה ישירה ל-Leads מה-Agent חסומה?") מאומתת חיובית בפרודקשן. **Follow-up נפתח בנפרד:** BUG-090 — הודעת החסימה למשתמש שגויה עבור `airtable_update` (מציגה `capture_inbound_lead()` שלא רלוונטי לעדכון) + הפרת Single-Speaker בנתיב הכשל — לא פותח מחדש את BUG-028 עצמו (ה-gate עובד נכון), רק את הניסוח/UX.
- **סטטוס:** ✅ תוקן ומוזג, ✅ VERIFIED בפרודקשן — scope Leads-only אושר כמכוון, לא פער (09/07/2026).

### BUG-029 (BUG-NEW-05) — A32: FOUND יכול להצדיק CREATED
- **תאריך:** 28/06/2026
- **קובץ:** `core/anti_hallucination.py`
- **שורש:** CRM pattern אחד קיבל `airtable_add`/`update`/`get`/`search_lead` לכל טענה
- **תיקון:** פיצול ל-3 patterns: יצירה→`add` בלבד | עדכון→`update/add` | חיפוש→`get/search`
- **Evidence:** 33/33 + 9 CXX tests
- **PR:** #171
- **סטטוס:** ✅ תוקן ומוזג

### BUG-030 (BUG-NEW-06) — ליד קיים + נושא חדש לא נשמר
- **תאריך:** 28-29/06/2026
- **קבצים:** `lead_capture.py`, `airtable_schema.py`
- **שורש:** `capture_inbound_lead` על ליד קיים → return FOUND בלבד, אין כתיבה
- **תיקון:** `capture_lead_event()` חדשה — Lead Event מקושר לליד
- **Evidence:** Lead Events table + Link to Lead — אומתו ב-Airtable
- **PR:** #171
- **סטטוס:** ✅ תוקן ומוזג

### BUG-031 (BUG-NEW-07) — Lead payload אובד כשAgent נחסם
- **תאריך:** 29/06/2026
- **קבצים:** `core/lead_buffer.py` (חדש), `tools/dispatcher.py`, `app.py`
- **PR:** #176
- **שורש:** dispatcher חסם ולא שמר. שם/פרטים שAgent חילץ נעלמו.
- **תיקון:** thread-local buffer → `save_blocked_payload` → `recover_blocked_lead_payload`
- **זרימה:** `capture_inbound_lead` → Agent נחסם → save → recover → patch lead → clear
- **Evidence:** 22/22 buffer tests
- **סטטוס:** ✅ תוקן ומוזג

### BUG-032 (BUG-FOUND-01) — ליד קיים הוחזר כ-CREATED עם record_id מזויף
- **תאריך:** 29/06/2026
- **קובץ:** `lead_capture.py`
- **PR:** #170
- **שורש:** `capture_inbound_lead` על ליד קיים החזיר `claim_type=CREATED` + `record_id="existing"` → A32/ClaimGate חשבו שנוצר Lead חדש; אי אפשר לכתוב Lead Event בלי record_id אמיתי
- **תיקון:** ליד קיים → `claim_type=FOUND` + `record_id=rec...` אמיתי + `tool_called=True` + `tool_http_ok=True`
- **חוק:** FOUND cannot justify CREATED
- **סטטוס:** ✅ תוקן ומוזג

### BUG-033 (BUG-META-01) — Metadata patch כשל על שדות לא קיימים
- **תאריך:** 29/06/2026
- **קבצים:** `lead_capture.py`, `airtable_schema.py`
- **PR:** #172
- **שורש:** PATCH ל-`utm_source`/`utm_medium`/`utm_campaign`/`platform` — שדות לא קיימים ב-schema → warning/error צדדי נראה כמו כשל עסקי
- **תיקון:** metadata patch failure = post/update warning בלבד, לא דורס `business_success`
- **חוק:** Lead created/found = `business_success`. metadata patch failed = warning בלבד.
- **סטטוס:** ✅ תוקן ומוזג

---

## Session 30/06/2026 — Decision Hub Quality Gate (BUG-DH-01 עד BUG-DH-05)

### BUG-034 (BUG-DH-01) — `missing_penalty` לא הופחת מה-score
- **תאריך:** 30/06/2026
- **קובץ:** `decision_confidence.py`
- **שורש:** `_MISSING_PENALTY` מוגדר אבל לא חוסר מה-score בפועל
- **תיקון:** `missing_penalty = _MISSING_PENALTY * len(missing)` → מחוסר מה-score; נוסף פרמטר `domain` ל-`calc_confidence(events, conflicts, domain)`
- **Evidence:** score גבוה שגויה כשחסרות ראיות — תוקן
- **סטטוס:** ✅ תוקן ומוזג

### BUG-035 (BUG-DH-02) — `_position_emoji` strings עבריים hard-coded
- **תאריך:** 30/06/2026
- **קובץ:** `cmd_decision.py`
- **שורש:** strings עבריים hard-coded במקום קבועי schema
- **סטטוס:** 🟡 מתועד ב-drift map, לא קריטי — לא תוקן עדיין

### BUG-036 (BUG-DH-03) — formula injection ב-`_resolve_decision_ref` — ✅ תוקן 07/07/2026
- **תאריך:** 30/06/2026 (דווח) → 07/07/2026 (תוקן)
- **קובץ:** `cmd_decision.py`
- **שורש:** `FIND('{ref}', ...)` ללא sanitization על `ref` מגיע מ-user input
- **תיקון (✅ בוצע):** נוסף `tools.airtable_gateway._safe_formula_param()` — helper משותף אחד, `_resolve_decision_ref()` מעביר את `ref` דרכו לפני הכנסה ל-formula. אותו helper משמש גם לתיקון BUG-037 ול-`core/lead_candidate_handler.py::_search_formulas` (שכבר עשה escaping דומה inline — הוחלף במקור המשותף).
- **בדיקה:** `test_bugdh03_04_formula_injection.py` (חדש, 15/15) — כולל בדיקת injection ייעודית ל-`_resolve_decision_ref` (`ref="test' OR 1=1 --"` → כל `'` בקלט נשמר escaped בפורמולה שנבנתה, לא נשאר raw).
- **Merged:** לא — ענף `claude/tool-approval-metadata-mi89lu`, commit `2e9bb57`.
- **Deployed:** לא. **Verified בפרודקשן:** לא.
- **סטטוס:** 🟡 CODE DONE, NOT VERIFIED — עדיין חוסם הפעלת `FEATURE_DECISION_HUB` עד מיזוג+production evidence (עקבי עם הכלל בראש הקובץ; לא לסמן ✅ מלא עד אז).

### BUG-037 (BUG-DH-04) — formula injection ב-`maybe_supersede` — ✅ תוקן 07/07/2026
- **תאריך:** 30/06/2026 (דווח) → 07/07/2026 (תוקן)
- **קובץ:** `decision_pipeline.py`
- **שורש:** Claim Topic (וגם Decision ID) מגיעים ל-formula ללא escaping ויכולים לשבור Airtable formula
- **תיקון (✅ בוצע):** `maybe_supersede()` מעביר גם את `decision_id` וגם את `new_event["Claim Topic"]` דרך `tools.airtable_gateway._safe_formula_param()` לפני בניית ה-`AND(...)` formula. (הבהרה: `decision_ports.py`'s `StoragePort.get()` הוא רק passthrough דק ל-`filterByFormula` — הבנייה עצמה תמיד הייתה ב-`decision_pipeline.py`, לא ב-`decision_ports.py`.)
- **בדיקה:** `test_bugdh03_04_formula_injection.py` (חדש, 15/15) — `maybe_supersede()` עם `decision_id`/Claim Topic זדוניים, מוודא escaping מלא בפורמולה שנבנתה בפועל דרך `StoragePort.get()` מדומה.
- **Merged:** לא — ענף `claude/tool-approval-metadata-mi89lu`, commit `2e9bb57`.
- **Deployed:** לא. **Verified בפרודקשן:** לא.
- **סטטוס:** 🟡 CODE DONE, NOT VERIFIED — עדיין חוסם הפעלת `FEATURE_DECISION_HUB` עד מיזוג+production evidence.

### BUG-038 (BUG-DH-05) — COG מקבל domain ישן (domain drift)
- **תאריך:** 30/06/2026
- **קובץ:** `app.py`
- **שורש:** `_gateway_whatsapp_reply` קיבל `domain_from_channel` (לפני Router) במקום domain שנקבע אחרי Router
- **תיקון:** `make_request_state(domain_from_channel)` → `_req_state.domain` מועדכן אחרי `run_agent`
- **Evidence:** COG לוג הציג `domain=general` במקום domain שזוהה
- **סטטוס:** ✅ תוקן ומוזג (`core/request_state.py`)

---

## Session 30/06/2026 — Approval Gateway Safety (Section 1 bug report)

### BUG-039 (BUG-ROUTER-TEST-WORD-COLLISION) — `בדיקה`/`test` כ-substring מפעיל BOT_STATUS_CHECK
- **תאריך:** 30/06/2026
- **קובץ:** `core/router/intent_router.py`
- **שורש:** חוק BOT_STATUS_CHECK אחד (`r"(בדיקה|test|...)"`) תפס substring — שם טבלה "בדיקה" או הודעה "הוסף לגיליון בדיקה" ניתב ל-BOT_STATUS_CHECK במקום ל-Agent
- **תיקון:** פיצול לשני חוקים: `^(בדיקה|test)\s*[\?!.]*$` (anchor מלא, confidence 0.99) + חוק קשרי נפרד לביטויים כמו `אתה עובד?`
- **PR:** #188
- **סטטוס:** ✅ תוקן ומוזג

### BUG-040 (BUG-V1-A32-SHEETS-FALSE-SUCCESS) — A32 לא חוסם טענת כתיבה ל-Sheets ללא עדות כלי
- **תאריך:** 30/06/2026
- **קובץ:** `core/anti_hallucination.py`
- **שורש:** `_NO_TOOL_CLAIMS` לא כלל pattern ל-`sheets_append` — Agent יכול לכתוב "השורה נוספה לגיליון" ללא קריאת `sheets_append` אמיתית, והתגובה עוברת A32 ללא חסימה
- **תיקון:** הוסף gate ל-`sheets_append` עם patterns: "השורה נוספה", "הוספתי לגליון/שיטס", "נוסף/נוספו ל-Google Sheets", "הנתונים נכתבו לגליון" ועוד. 6 בדיקות חדשות inline.
- **PR:** #188
- **סטטוס:** ✅ תוקן ומוזג

### BUG-041 (BUG-V1-FAKE-APPROVAL-STATE) — Agent יכול לטעון "⏳ ממתינה לאישור" ללא approval אמיתי
- **תאריך:** 30/06/2026
- **קבצים:** `core/anti_hallucination.py`, `app.py`
- **שורש:** A32 לא בדק אם approval אכן הועמד בתור — Agent יכול להחזיר "⏳ ממתינה לאישור הבעלים" גם אם `_queue_approval()` לא רץ בכלל
- **תיקון:** (א) `_queue_approval()` מזריק sentinel `__approval_queued__` ל-`tool_results_log` בכל הרצה. (ב) A32 קיבל pattern חדש: ביטויי approval דורשים עדות `__approval_queued__`. ללא sentinel — תגובה נחסמת.
- **PR:** #188
- **סטטוס:** ✅ תוקן ומוזג
- **עדכון אימות 09/07/2026 — כיסוי מול BUG-086/087:** ✅ סגור בפועל במסלול Agent tool-loop. הטענה הבעייתית היא טקסט שיוצא מה-Agent ונבדק ב-`sanitize_agent_response()` לפני החזרה למשתמש (`app.py:1969-1973`). `_queue_approval()` מזריק עדות `{"tool": "__approval_queued__", "ok": True}` ל-`tool_results_log` רק אחרי queue אמיתי (`app.py:1897-1911`). ב-`core/anti_hallucination.py:235-247` יש pattern מפורש לטענות "ממתינה לאישור" שדורש את ה-sentinel הזה; בלי sentinel התגובה מוחלפת ל-`_NO_TOOL_EVIDENCE_FALLBACK` דרך הלולאה ב-`core/anti_hallucination.py:546-554`. כלומר BUG-086/087 לא צריכים PR נוסף עבור BUG-041.

### BUG-042 (BUG-V1-APPROVAL-REQUEUE-AFTER-CONFIRM) — פעולה שאושרה ניתנת ל-re-queue מיידי
- **תאריך:** 30/06/2026
- **קבצים:** `event_bus.py`, `app.py`
- **שורש:** לאחר אישור ובצוע פעולה, Agent יכול לקבל הודעת follow-up שתגרום לו להוסיף שוב אותה פעולה לתור — ביצוע כפול
- **תיקון:** `ExecutedActionCache` — fingerprint SHA1(chat_id|tool_name|sorted_inputs)[:16] עם TTL 600s. `_queue_approval()` בודק לפני קיבוע; `_handle_approval_callback_impl()` מסמן לאחר dispatch מוצלח.
- **PR:** #188
- **סטטוס:** ✅ תוקן ומוזג

### BUG-043 (BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION) — שני כלים הדורשים אישור באותו תור Agent
- **תאריך:** 30/06/2026
- **קובץ:** `app.py`
- **שורש:** Agent יכול לקרוא לשני כלים עם `requires_approval=True` בתור אחד — שני approval requests נפרדים בו-זמנית, payload של השני יכול "לזהם" את הראשון בזיכרון
- **תיקון:** counter `_mutating_approvals_this_turn` בלולאת tool-use — כלי שני המבקש approval באותו תור מקבל חסימה עם הודעת שגיאה ברורה
- **PR:** #188
- **סטטוס:** ✅ תוקן ומוזג

### BUG-044 (P0-SEND-RECOVERY-HANDLER) — `send_recovery.confirmed` פולט לחלל ריק
- **תאריך:** 30/06/2026
- **קבצים:** `app.py`, `lead_recovery.py`
- **שורש:** `lead_recovery.py:237` קורא `bus.emit("send_recovery.confirmed", ...)` — אין handler רשום ל-event זה ב-`app.py`; `emit()` מחזיר `None` בשקט, הפעולה לא מבוצעת לעולם (P0 — silent data loss)
- **תיקון:** הוסף `_handle_send_recovery_confirmed()` + `bus.subscribe("send_recovery.confirmed", ...)` ב-`app.py` לאחר ה-subscribe הקיים של `send_followup.confirmed`
- **PR:** #188
- **סטטוס:** ✅ תוקן ומוזג

### BUG-045 (C53-EMERGENCY-STOP-NOT-ENFORCED) — `EMERGENCY_STOP_AUTOMATION` לא נאכף ב-followup/scheduler
- **תאריך:** 30/06/2026
- **קבצים:** `followup_engine.py`, `scheduler.py`
- **שורש:** הדגל `EMERGENCY_STOP_AUTOMATION` הוצג ב-TMA UI כאמצעי עצירת אוטומציה, אך לא נבדק בפועל ב-`run_followup_scan()` ולא ב-`_job_followup_scan()`/`_job_payment_reminders()` — הפעלת הדגל לא עצרה כלום
- **תיקון:** `run_followup_scan()` + שני jobs ב-scheduler בודקים `is_enabled("EMERGENCY_STOP_AUTOMATION")` כניסה ראשונה לפני כל עבודה
- **PR:** #189
- **סטטוס:** ✅ תוקן ומוזג

### BUG-046 (C53-THREE-APPROVAL-LISTS) — שלוש רשימות `TOOLS_REQUIRING_APPROVAL` נפרדות
- **תאריך:** 30/06/2026
- **קבצים:** `tool_registry.py`, `event_bus.py`, `tools/dispatcher.py`
- **שורש:** `tool_registry.py`, `event_bus.py`, ו-`tools/dispatcher.py` כל אחד שמר רשימת כלים הדורשים אישור/emergency-stop עצמאית — שינוי ברשימה אחת לא משפיע על האחרות; bypass של Emergency Stop אפשרי
- **תיקון:** `tool_registry.TOOLS_REQUIRING_APPROVAL` (frozenset) הוגדר כמקור יחיד; `event_bus` ו-`dispatcher` מייבאים ממנו
- **PR:** #189
- **סטטוס:** ✅ תוקן ומוזג

## Session 02/07/2026 — C89 Stage 3 Capture Policy + Session Dedup + Ambiguous Phrase Gate

### BUG-047 (BUG-NEW-12) — Session duplication: N existing Sessions rows → POST במקום PATCH
- **תאריך:** 02/07/2026
- **קובץ:** `session_store.py`
- **שורש:** `_find_record_id_in_db` השתמש ב-`re.search(r"rec\w+", raw)` — regex גנרי שיכול לתפוס record ID שמוטמע בתוך State JSON (למשל `recLEAD123`, `recMEDIA456`) במקום את רשומת ה-Session עצמה. כשזה קרה, הבדיקה "יש session קיים?" פספסה, וה-code נפל דרך ל-`airtable_add` → רשומת Session כפולה. תועד live: 14 רשומות כפולות לאותו sender.
- **תיקון:** `_SESSION_RECORD_RE = re.compile(r"•\s*\[?(rec\w+)\]?")` מזהה אך ורק את בולטי הרשומה `• [recXXX]` בפלט `airtable_get`. `_find_best_session_in_db(sender)` סופר את כל ההתאמות, בוחר הראשונה (העדכנית ביותר), ומחזיר `(record_id, found_count, reason)`. `_load_from_db` הוגבל לחלון הרשומה הראשונה בלבד (מונע דליפה בין רשומות כשיש 14). כלל: `found_count > 0` → תמיד PATCH, אף פעם לא POST. לוגים מפורשים: `[SessionStore] lookup sender=... found_count=N selected=recXXX action=reuse_existing|create_new`.
- **בדיקה:** 52/52 (כולל תרחיש 14 רשומות כפולות → PATCH יחיד, אפס POST)
- **PR:** #203
- **סטטוס:** ✅ תוקן ומוזג

### BUG-048 (BUG-IC-01) — ביטויים דו-משמעיים ("סטטוס"/"בדיקות מערכת") מפעילים Agent עם כלים מלאים ללא בקשה מפורשת
- **תאריך:** 02/07/2026
- **קבצים:** `core/router/intent_router.py`, `core/router/router.py`
- **שורש:** משפטים חשופים כמו "סטטוס", "בדיקות מערכת", "מה המצב", "למלא משימות" לא תאמו אף חוק intent קיים (חוק SYSTEM_STATUS דרש מילה שנייה כמו "מערכת/system/בוט/bot" אחרי מילת הסטטוס) — נפלו ל-`Intent.UNKNOWN` → `Handler.AGENT` עם גישה מלאה לכלים. ה-Agent החליט בעצמו אם להריץ בדיקת קישוריות. תועד live: "בדיקות מערכת" הפיק דוח סטטוס Gmail/Calendar/Airtable מלא ללא בקשה מפורשת לבדיקה כזו.
- **תיקון:** `detect_ambiguous_phrase()` חדש ב-`intent_router.py` — מזהה את הביטויים החשופים ומחזיר שאלת הבהרה ספציפית לכל אחד. `router.py` בודק זאת לפני הנפילה ל-`Handler.AGENT` (safety net) כש-intent הוא UNKNOWN; אם נמצא — `Handler.CLARIFY` עם התשובה, ללא קריאה ל-Agent או לכלי כלשהו. חוק חדש נוסף גם ל-SYSTEM_STATUS: מילת פועל מפורשת (בדוק/תבדוק) + יעד (חיבור/gmail/calendar/airtable/מערכת) — כדי שבקשות מפורשות כמו "בדוק חיבורי מערכת" עדיין יגיעו ל-Agent (הוזז מוקדם בטבלת החוקים כדי לנצח את "calendar"→LIST_EVENTS ו"בדוק"→RESEARCH_TOPIC).
- **בדיקה:** 7/7 ביטויים ממוקדים, 29/29 router suite, ללא רגרסיה על intents רגילים
- **PR:** #203
- **סטטוס:** ✅ תוקן ומוזג

### BUG-049 (BUG-CI-SILENT-PASS-DOCUMENT-CONVERTER) — `test_document_converter.py` רץ ב-CI בלי לבצע אף assertion
- **תאריך:** 02/07/2026
- **קובץ:** `test_document_converter.py`
- **שורש:** `ci.yml` מריץ בדיקות דרך `for f in test_*.py; do python "$f"; done` (מוסכמת הפרויקט — script-based, לא pytest). `test_document_converter.py` נכתב כקובץ pytest טהור (6 פונקציות `test_*` עם fixture `tmp_path`, בלי `__main__` guard). כשמורץ כ-`python3 test_document_converter.py` הפונקציות מעולם לא נקראות — הסקריפט מסתיים ב-exit 0 בלי לבצע שום assertion, ו-CI מדווח ✅ שקרי. אומת ישירות: `python3 test_document_converter.py` לפני התיקון → exit 0, אפס פלט. `pytest test_document_converter.py` באותו זמן → 6/6 עובר, מוכיח שהבדיקות עצמן תקינות והבעיה היא רק בהרצה.
- **תיקון:** נוסף `if __name__ == "__main__"` guard בסוף הקובץ. מכיוון שכל 6 הפונקציות תלויות ב-fixture `tmp_path` (אין מקבילה ב-Python רגיל) — לא בוצע auto-collect לפי prefix; כל פונקציה נקראת במפורש עם `tempfile.mkdtemp()` שנארז ב-`Path`. `pytest.importorskip` בשתי הפונקציות (`docx`, `openpyxl`) נתפס בנפרד עם `except pytest.skip.Exception` ומדווח כ-skip ולא כשגיאה. לא נגעו ב-`ci.yml` וב-`document_converter/` עצמו — היקף מצומצם לקובץ הבדיקה בלבד.
- **בדיקה:** `python3 test_document_converter.py` לאחר התיקון → 6/6 רצות בפועל (exit 0, "passed" מודפס לכל אחת). שבירה מכוונת (`assert False` זמני בתוך test אחד) → exit 1 עם traceback אמיתי, מוכיח שה-guard באמת בודק ולא רק מדמה. `pytest test_document_converter.py` נשאר 6/6 ללא רגרסיה. סימולציית לולאת `ci.yml` (`for f in test_*.py; do python "$f" || exit 1; done`) על גרסה נקייה → הצלחה; על גרסה שבורה במכוון → נכשל כצפוי.
- **PR:** ממתין לפתיחה (branch: `fix/ci-silent-pass-document-converter`)
- **Merged:** לא
- **Deployed:** לא רלוונטי (בדיקת CI בלבד, אין נגיעה בלוגיקת production)
- **Verified בפרודקשן:** לא — 🟡 קוד תוקן ואומת מקומית, טרם ממוזג
- **סטטוס:** 🟡 Fixed, awaiting merge

### BUG-050 (BUG-AGENTS-RULE-NOT-FOLLOWED) — כלל "סיום סשן" ב-AGENTS.md לא יושם בפועל
- **תאריך:** 02/07/2026
- **קובץ:** `AGENTS.md` (תצפית תיעודית — אין שינוי קוד)
- **Severity:** Medium
- **שורש:** `AGENTS.md` §"סיום סשן" ("ברירת מחדל: פתח PR לפני סיום. אין צורך באישור. חריג יחיד: המשתמש אמר במפורש 'אל תפתח PR'") היה קיים בקוד **לפני** תחילת הסשן הזה (קומיט `36f2784`, 28/06/2026 — אותו קומיט שהעלה גם את `document_converter/`). בסיום עבודת BUG-049 (CI silent-pass fix) הסוכן דיווח "Not opening a PR since none was requested" — כלומר פעל בניגוד לכלל שהיה כתוב לו במפורש, במקום לפתוח PR כברירת מחדל. אין שום מנגנון שמוודא ש-`AGENTS.md` נקרא/מיושם בפועל בתחילת/סוף סשן — האכיפה תלויה כרגע רק בציות ידני/זיכרון של הסוכן, בדיוק אותו דפוס drift שכבר תועד כמה פעמים בין תיעוד לקוד/התנהגות בפועל בלוג הזה.
- **תיקון:** לא בוצע בסשן זה — במכוון. הפעולה המתקנת המיידית הייתה בקשה מפורשת מהמשתמש לפתוח את ה-PR (ראה BUG-049), לא בניית מנגנון אכיפה. נמנע over-engineering לבעיה חד-פעמית; אם compliance אוטומטי (למשל בדיקת "PR נפתח בסיום סשן" ב-`daily_git_audit.py`/hook) יימצא שווה את המאמץ בעתיד, זה roadmap item נפרד.
- **בדיקה:** לא רלוונטי — תיעוד בלבד, אין קוד לבדוק.
- **PR:** נכלל באותו PR כמו BUG-049 (`fix/ci-silent-pass-document-converter`)
- **Merged:** לא
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** 🟡 Documented, no fix — פתוח כתצפית ל-roadmap עתידי

### BUG-051 (SPEC-1-LCH-ROUTER-BYPASS) — LeadCandidate Handler עקף את כל ה-Router (Identity→Router→Context→Agent)
- **תאריך:** 02/07/2026
- **קבצים:** `app.py`, `core/router/router.py`, `core/router/route_decision.py`, `core/router/capture_router.py` (חדש), `core/lead_candidate_handler.py`
- **Severity:** Medium — לא security-critical (LCH עדיין עובר Gateway/enforce), אבל domain שגוי + Router עוקף = audit trail חסר לכל capture.
- **שורש:** `app.py` שלב "1.45" קרא ל-`core.lead_candidate_handler.handle_lead_candidate()` **לפני** `route_request()` (Identity→Router→Context→Agent) עבור כל sender פנימי — `route_request()` לא רץ בכלל לתורות האלה. `handle_lead_candidate()` קבע domain בעצמו דרך `_detect_domain()` — regex mirror ידני של `domain_router._DOMAIN_RULES` (הערה בקוד: "mirrors domain_router._DOMAIN_RULES"), לא ה-domain_router האמיתי, ולכן לא תמיד תואם למה ש-Router היה קובע (למשל לא רואה `domain_from_channel`). זה **לא** אותו code path כמו BUG-NEW-13 המתועד (`app.py` שורות ~1258, `lead_capture.py`/W0, ל-sender חיצוני מסוג `Role.LEAD`) — זו בעיה מקבילה, קוד נפרד, ב-code path פנימי (owner/staff) שלא היה מתועד כבאג נפרד עד עכשיו.
- **תיקון:** `RouteDecision` קיבל 3 שדות אופציונליים חדשים (`capture_tier`, `capture_reason`, `raw_ref`, כולם default None/""). `core/router/capture_router.py` חדש — עטיפה דקה סביב `core.ingress_classifier.classify_ingress()` הקיים (אין שכתוב לוגיקת tier, אין import ל-airtable/drive/gateway — grep מאמת). `router.py` קורא לו כשלב חדש, גייט על `identity.is_internal` בלבד. `app.py`'s שלב 1.45 הוסר; קריאה חדשה ל-`handle_lead_candidate()` נוספה **אחרי** `route_request()` (אחרי ש-`resolved_route_domain` חושב), עם `domain=resolved_route_domain` — פרמטר אופציונלי חדש שנוסף ל-`handle_lead_candidate()` (ברירת מחדל `""`, נופל חזרה ל-`_detect_domain()` הישן אם לא הועבר — תאימות לאחור מלאה לכל caller אחר).
- **3 סטיות מכוונות מהספק המעודכן, מתועדות כאן במפורש:**
  1. **`capture_tier` הוא observability-בלבד, לא gate.** הספק הציע "אם capture_tier is not None → קורא ל-LCH". נמצא ב-discovery שזה שובר את `_handle_batch_followup()` — רץ בלי-תנאי בתוך `handle_lead_candidate()` *לפני* כל סיווג tier, ולא מייצר tier בעצמו (תגובת follow-up כמו "מה קרה עם השאר?" מסווגת Tier 5 → capture_tier=None → gate כזה היה חוסם אותה). ה-gate האמיתי ל-app.py נשאר `identity.is_internal`, זהה לישן — `capture_tier` משמש רק לצפייה/audit trail על RouteDecision. ראה `test_batch_followup_still_reachable_without_a_tier` ב-`test_capture_router_wiring.py`.
  2. **הוסר ה-gate `intent in {...} and confidence < 0.75`** משלב 4 ב-`router.py`. אם היה נשאר: הודעה מפורשת כמו "תוסיף ליד: משה כהן 0501234567" מזוהה ע"י `intent_router` כ-`CREATE_LEAD` ב-0.95 confidence — התנאי היה False, `capture_tier` נשאר None, ואילו `handle_lead_candidate()` (שרץ בלי תלות ב-intent, רק ב-`is_internal`) עדיין היה כותב אותה כ-Tier 1 בפועל. `RouteDecision` היה "משקר" — מציג "אין capture" בזמן שקרתה כתיבה. ה-gate החדש: `identity.is_internal` בלבד, זהה ל-gate האמיתי של LCH. ראה `test_router_capture_tier_high_confidence_intent_still_fires`.
  3. **`handle_lead_candidate()` קיבל פרמטר חדש (`domain`), לא "חתימה זהה" כפי שהספק ביקש.** בלי זה, DoD #14 (domain נכון לא "general" קבוע) לא היה בר-מימוש בלי לגעת בלוגיקת הכתיבה הפנימית — אין דרך "להזרים" domain מבחוץ בלי איזשהו פרמטר. הפתרון המינימלי: פרמטר יחיד עם default ריק (תאימות מלאה לאחור), שורה אחת שונתה (`domain = domain or _detect_domain(...)`). שאר 813 השורות בקובץ — אפס שינוי (parse/write/preview/confirmation logic זהים ב-100%).
- **בדיקה:** 10/10 `test_capture_router_wiring.py` (חדש) — כולל regression guards ל-3 הסטיות למעלה. 29/29 `core/router/test_router.py` (MockIdentity קיבל `is_internal`/`memory_key` תואמים ל-`identity.Identity`). 4/4 `test_integration.py` (אותו תיקון ל-MockIdentity הנפרד שם — היה שובר שקט: `route_request()` זרק `AttributeError`, נבלע ב-`except Exception` הרחב של `_safe_route()` של הבדיקה עצמה, וגרם ל-3/4 כשלים מדומים לפני שאותר השורש). כל 30 קבצי `test_*.py` בריפו רצים ירוק (`for f in test_*.py; do python "$f"; done`, זהה ל-CI). `smoke_tests.py` 7/7 (אחרי התקנת `flask`/`httpx`/`anthropic`/`telebot` שחסרו בסביבת ה-sandbox — לא רגרסיה, תלות sandbox).
- **PR:** #205 — מוזג (`bcafc39`)
- **Merged:** כן
- **Deployed:** לא ידוע (לא אומת מול Render מהסביבה הזו)
- **Verified בפרודקשן:** לא — 🟡 קוד ממוזג ואומת מקומית (unit-level, אין Airtable/Gateway חי בסביבת ה-sandbox); `FEATURE_AUTO_CAPTURE` עדיין כבוי כברירת מחדל, אין שינוי התנהגות בפרודקשן עד הפעלה מפורשת
- **סטטוס:** ✅ תוקן ומוזג (production verification עדיין פתוח, ראה DoD #14 caveat ב-PR)

### BUG-052 (TESTABILITY-GAP-RUN-AGENT) — run_agent() אינו ניתן לבדיקה מבודדת, אין test_*.py שעובר קצה-לקצה
- **תאריך:** 02/07/2026
- **קובץ:** `app.py` (תצפית תיעודית — אין שינוי קוד)
- **Severity:** Low (documentation, not behavior)
- **שורש:** `run_agent()` ב-`app.py` תלוי ב-Flask/Anthropic/`session_store`/`scheduler` — אין אף `test_*.py` בריפו שעובר דרכו קצה-לקצה. כל "N/N tests pass" שנוגע בזרימת Router→Agent בודק שכבות מתחתיו (unit-level: `route_request()`, `handle_lead_candidate()` ישירות וכו') — לא את השרשרת המלאה מ-`run_agent()` עצמו.
- **תיקון:** לא בוצע — מתועד במכוון כדי ש-PRs עתידיים לא יניחו כיסוי e2e שאין. Roadmap: harness ל-`run_agent()` עם dependency injection/mocking, כשיהיה שווה את המאמץ (לא כרגע — over-engineering לבעיה שלא חוסמת merge).
- **בדיקה:** לא רלוונטי — תיעוד בלבד.
- **PR:** זוהה תוך כדי PR #205 (Capture Policy Stage 3), DoD #14 caveat — לא נפתר שם.
- **Merged:** לא רלוונטי
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** 🟡 Documented, no fix — roadmap item עתידי

### BUG-053 (TEST-BUG-MOCKIDENTITY-MISSING-IS-INTERNAL) — MockIdentity חסר is_internal גרם ל-3 כשלים מזויפים ב-test_integration.py
- **תאריך:** 02/07/2026
- **קובץ:** `test_integration.py`
- **Severity:** Low
- **שורש:** `test_integration.py`'s `MockIdentity` (dataclass נפרד, לא משותף עם `core/router/test_router.py`) חסר `is_internal` — כש-`router.py` (PR #205) התחיל לקרוא ל-`identity.is_internal` בשלב 4 החדש (capture_router), `route_request()` זרק `AttributeError`. השגיאה נבלעה ע"י `except Exception` רחב מדי ב-`_safe_route()` המקומי של הטסט עצמו (מדמה fail-closed fallback), שהחזיר `RouteDecision` ברירת מחדל שגוי — הפיק 3 כשלים (`domain=general` במקום `import`, `restricted must be True` פעמיים) שנראו כמו router regressions אמיתיים עד שאותר השורש.
- **תיקון:** נוסף `is_internal`/`memory_key` כ-`@property` ל-`MockIdentity` ב-`test_integration.py`, תואם ל-`identity.Identity` האמיתי. אותו תיקון הוחל גם ב-`core/router/test_router.py`'s `MockIdentity` הנפרד (אותה בעיה, שני עותקים כפולים של המחלקה).
- **בדיקה:** 4/4 `test_integration.py` אחרי התיקון (היה 1/4 לפני שאותר השורש).
- **PR:** #205 — מוזג (`bcafc39`)
- **Merged:** כן
- **Deployed:** לא רלוונטי (test file בלבד)
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** ✅ תוקן ומוזג

### C89 — Stage 3 Capture Policy: IngressClassification + tiered auto-write (טקסט)
- **תאריך:** 02/07/2026
- **קובץ:** `core/ingress_classifier.py` (חדש), `core/lead_candidate_handler.py`
- **מה נבנה:** `IngressClassification` (הטיפוס הגנרי לצד הקלט, מקביל ל-`ActionContract` בצד הפלט). `classify_ingress()` — נקודת כניסה יחידה, שום מודול לא מסווג קלט בעצמו. Tier 4 gate רץ ראשון: טבלאות/timestamps/WhatsApp export/Airtable IDs/JSON/פלט בוט → לעולם לא auto-write. Tier 1 (ליד בודד ברור) / Tier 2 (batch נקי) / Tier 3 (מעורב) / Tier 5 (ללא סימן — ממשיך ל-agent). `FEATURE_AUTO_CAPTURE` (כבוי כברירת מחדל) שולט על auto-write; אחרת preview + אישור.
- **PR:** #203
- **סטטוס:** ✅ קוד הושלם ומוזג (flag כבוי — ללא שינוי התנהגות בפרודקשן עד הפעלה מפורשת)

### BUG-054 (AGENTS-RULE-REPEAT-MISS) — כלל "סיום סשן" ב-AGENTS.md לא יושם בפעם השנייה
- **תאריך:** 03/07/2026
- **קובץ:** `AGENTS.md` (תצפית תיעודית — אין שינוי קוד)
- **Severity:** Medium — זהה ל-BUG-050, אך זו הפעם השנייה שאותו כלל תיעודי לא נאכף בפועל, כלומר הדפוס עצמו (לא רק המופע) הוא הבעיה.
- **שורש:** זהה במהותו ל-BUG-050: `AGENTS.md` §"סיום סשן" קובע במפורש "ברירת מחדל: פתח PR לפני סיום. אין צורך באישור. חריג יחיד: המשתמש אמר במפורש 'אל תפתח PR'". בסיום עבודת F52 Stage 1 (audit tooling + shadow recorder, ענף `claude/f52-stage1-safe-refactors-cors1j`) הסוכן דיווח "לא פתחתי PR כי לא ביקשת" — שוב, בניגוד ישיר לכלל הכתוב. BUG-050 כבר תיעד את התקרית הראשונה (28-29/06/2026) והחליט במפורש **לא** לבנות מנגנון אכיפה ("נמנע over-engineering לבעיה חד-פעמית"). ההנחה הזו הופרכה עכשיו בפועל: זו לא הייתה בעיה חד-פעמית, אלא כלל מתועד שאינו מאכף את עצמו (self-enforcing) — התלות היחידה הייתה זיכרון/ציות ידני של הסוכן בכל סשן מחדש, בדיוק כפי ש-BUG-050 עצמו ניסח את הסיכון, בלי לפעול לפיו.
- **תיקון:** לא בוצע בסשן זה בקוד. הפעולה המתקנת המיידית הייתה בקשה מפורשת (שוב) מהמשתמש לפתוח PR — ראה PR שנפתח מיד לאחר רישום זה. תיעוד זה עצמו הוא ההסלמה מ"מקרה בודד" (BUG-050) ל"דפוס חוזר" (BUG-054), כפי שהמשתמש ביקש לסמן.
- **המלצה ל-roadmap (לא בוצעה בסשן זה):** אם תקרית שלישית תתרחש, over-engineering-avoidance כבר לא תקף — כדאי גייט אוטומטי (למשל hook/check ב-`daily_git_audit.py` שבודק אם יש commits לא-מוזגים ב-branch נוכחי בלי PR פתוח תואם ב-GitHub, ומזהיר/חוסם דיווח "done").
- **בדיקה:** לא רלוונטי — תיעוד בלבד.
- **PR:** נפתח עבור branch `claude/f52-stage1-safe-refactors-cors1j` בעקבות רישום זה.
- **Merged:** לא
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** 🟡 Documented, no fix — דפוס חוזר, פתוח ל-roadmap אם יקרה פעם שלישית

### BUG-055 (CLAIM-CORRECTION-ACTION-GATEWAY-552) — תיקון claim: "action_gateway.py:552 + 3 נוספים" — 1 מופע מאומת, לא 4
- **תאריך:** 03/07/2026
- **קובץ:** `core/action_gateway.py` (תצפית תיעודית — אין שינוי קוד)
- **Severity:** Low — dormant path, אין השפעת פרודקשן
- **שורש:** בסבב אימות C89/F52 (grep נגד main + כל הענפים הפתוחים) הועלה claim ל"callback auth — action_gateway.py:552 + 3 נוספים". grep ישיר ל-`approver mismatch`/`canonical_user_id != approver` מצא **מופע אחד בלבד** בכל הריפו — `core/action_gateway.py:552`, בתוך `ActionGateway.approve()` (Stage B, `FEATURE_ACTION_GATEWAY` כבוי כברירת מחדל — לא פעיל בפרודקשן). ה-"3 נוספים" הנטענים לא אומתו ב-grep על מצב הריפו הנוכחי — ייתכן שהתייחסו למשהו מחוץ ל-snapshot הזה, או שהיה אי-דיוק בזיכרון/הנחה. בנוסף: הנתיב החי בפרודקשן (`app.py:_handle_approval_callback_impl`, שורה 909) **כבר חוסם קשיח** על אי-התאמת approver (`bot.answer_callback_query(cq.id, "⛔ אין לך הרשאה לאשר פעולה זו")`) — החולשה קיימת רק בנתיב Stage B הרדום.
- **תיקון:** לא בוצע — ולא נדרש SPEC. זו תיקון-תיעוד בלבד (claim correction), לא באג פעיל. אם/כשיופעל `FEATURE_ACTION_GATEWAY`, יש לחזק את הבדיקה ב-`action_gateway.py:552` מ-warning-only ל-hard-block לפני production — לציין כ-follow-up אם/כש-Stage B יוצא מ-dormant.
- **בדיקה:** `grep -rn "approver mismatch\|canonical_user_id != approver" --include="*.py" .` → מופע יחיד, `core/action_gateway.py:552/554`.
- **PR:** לא רלוונטי — docs-only, ישיר ל-main.
- **Merged:** כן (docs commit ישיר)
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי (Stage B לא פעיל)
- **סטטוס:** ✅ Documented — תיקון claim, לא דורש SPEC

### BUG-056 (C89-ROUTER-PREVIEW-HARDENING) — 4 ממצאים מסבב QA ידני על C89/BUG-IC-01
- **תאריך:** 03/07/2026
- **קבצים:** `core/router/intent_router.py`, `core/router/router.py`, `core/router/route_decision.py`, `core/router/capture_router.py`, `core/lead_candidate_handler.py`, `core/action_gateway.py`, `app.py`
- **Severity:** Medium — preview confirmation ואי-חסימת Tier 4 יכולים לגרום ל-user-visible breakage (הבטחת "לשמור?" שלא מתממשת) ול-intent שגוי מתוכן מודבק.
- **שורש (4 ממצאים נפרדים, מאותו סבב QA):**
  1. **BUG-IC-01 coverage gap:** `_AMBIGUOUS_PHRASES` regex `r"^בדיקות?\s*מערכת..."` שם את ה-`?` על ה-ת' הסופית במקום על ה-ו' הפנימית — תופס "בדיקות מערכת" (רבים) אך לא "בדיקת מערכת" (יחיד/סמיכות), כי ההבדל בין הצורות הוא ה-ו', לא ה-ת'.
  2. **C89 preview confirmation dead-end:** `_handle_single_candidate`/`_handle_clean_batch` (Tier 1/2, `FEATURE_AUTO_CAPTURE=false`) שומרים preview ב-`session["pending_lead_preview"]` דרך `_store_pending_preview()` — אבל שום קוד בריפו לא קורא את השדה הזה בחזרה. כש-"כן" מגיע, `app.py`'s confirm-word intercept (שורה ~1362) בודק רק `action_gateway`/`event_bus` — לא `pending_lead_preview` — ומחזיר "אין פעולה שממתינה לאישור". בנוסף, `_store_pending_preview` עושה no-op שקט אם `_ls.get(chat_id)` מחזיר `None` (session חדש).
  3. **C89 Tier 4 לא עוצר routing:** `handle_lead_candidate()` מחזיר `None` עבור `ic.tier >= 4` — זה מונע רק auto-write מ-LCH עצמו, אבל הטקסט הגולמי ממשיך ל-`intent_router`/Agent כרגיל. `core/ingress_classifier.py`'s התיעוד העצמי אומר "Tier 4: NEVER auto-write, preview only" — הקוד מממש רק את החצי הראשון.
  4. **פלט מודבק מפעיל intent שגוי:** תוצאה ישירה של #3 — טקסט מודבק שסווג נכון כ-Tier 4 (`_is_tier4`, למשל `bot_output_block`/`table_separator`) עדיין מגיע ל-`intent_router.detect_intent()`, שמזהה מילות מפתח כמו "הוסף משימה" בכל מקום בטקסט ללא קשר למבנה שמסביב.
  5. **Double classification (cleanup, לא blocker):** `core/router/router.py` קורא ל-`classify_ingress()` (דרך `classify_capture()`) לצורך observability בלבד על `RouteDecision.capture_tier`, ו-`core/lead_candidate_handler.py` קורא לו שוב באופן עצמאי כדי להחליט בפועל — שתי קריאות נפרדות לאותו טקסט, מתועד כ"by design" בשני המקומות אך סותר את התיעוד העצמי של `classify_ingress()` כ"single entry point".
- **תיקון:**
  1. `core/router/intent_router.py`: regex תוקן מ-`^בדיקות?\s*מערכת...` ל-`^בדיקו?ת\s*מערכת...` — ה-`?` עבר מה-ת' הסופית לו' הפנימית, כך ש"בדיקת" (יחיד, ללא ו') ו"בדיקות" (רבים, עם ו') תואמים שניהם.
  2. `core/router/router.py`: תוסף Tier-4 stop-gate ב-step 7 (edge cases) — `capture_ic.tier == 4` → `handler=CLARIFY`, `tool_allowed=False`, הודעה דטרמיניסטית. עוצר Routing *לפני* `Handler.AGENT` ללא קשר לאיזה intent הטקסט המודבק הזעיק (למשל "הוסף משימה" בתוך bot output).
  3. `core/lead_candidate_handler.py`: פונקציה חדשה `_propose_lead_write()` — Tier 1 preview (`auto_write=False`) קורא ל-`action_gateway.propose_action(requires_approval=True, tool_name="airtable_add"/"airtable_update", _source="lead_capture")` במקום `_store_pending_preview()` המת. `_store_pending_preview` (עדיין בשימוש ע"י Tier 2 batch — לא תוקן מעבר לזה, ראה "נשאר פתוח" למטה) עבר מ-`_ls.get()` ל-`_ls.get_or_create()` לתיקון ה-no-op בsession חדש.
  4. `core/action_gateway.py`: מתודה חדשה `route_cancellation_word()` — מבטלת (`status="rejected"`) contracts חיים בתגובה ל"לא".
  5. `app.py`: בלוק `_CONFIRM_WORDS`/`_CANCEL_WORDS` (סעיף 2.55) בודק `action_gateway.find_live_contracts()` **לפני** ה-branch המותנה ב-`FEATURE_ACTION_GATEWAY` — כך ש-contract שנוצר ע"י LCH נפתר תמיד, גם כשהדגל כבוי (ברירת המחדל). "לא" מטופל באותה שכבה עם `route_cancellation_word()` חדש.
  6. Double classification (#5): `core/router/capture_router.py` מקבל `classify_capture_ic()` (קריאת `classify_ingress()` יחידה); `RouteDecision` מקבל שדה חדש `capture_ic`; `router.py` ו-`app.py` מעבירים אותו ל-`handle_lead_candidate(ic=route.capture_ic)`, שמשתמש בו במקום לסווג שוב — מטפל גם ב-Tier-4 gate וגם ב-double-classification בקריאה משותפת אחת.
- **בדיקה:** `core/router/test_router.py` 38/38 + 3 בדיקות Tier-4 ידניות (tool_allowed=False, capture_ic.tier==4, LCH→None). `test_c89_preview_confirmation.py` (חדש) 6/6 — preview, אישור-דרך-Gateway, ביטול, מניעת כפילות (pending + executed), grep סטטי על app.py. כל 34 קובצי `test_*.py` בריפו + `smoke_tests.py` + `test_integration.py` + `core/router/test_router.py` — 0 רגרסיות.
- **נשאר פתוח (לא בסקופ הסשן הזה):** Tier 2 (`_handle_clean_batch`, batch preview) עדיין קורא ל-`_store_pending_preview()` הישן — "לשמור את כולם?" לbatch עדיין לא עובר דרך Gateway; ActionGateway בנוי סביב contract יחיד, לא batch-confirm. דורש עיצוב נפרד (roadmap item עתידי, לא SPEC חדש בסשן זה).
- **PR:** #215 (`fix/c89-router-preview-hardening`).
- **Merged:** כן — `bcfbff2` (מאומת `git log origin/main --oneline`)
- **Deployed:** לא אומת (אין גישת Render dashboard מה-sandbox)
- **Verified בפרודקשן:** לא עדיין
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification

### BUG-057 (LL-14 / AD-ATTRIBUTION-UTM-UNGATED) — _inject_utm רץ ללא גייט FEATURE_ACTION_GATEWAY על כל הודעת WhatsApp נכנסת
- **תאריך:** 03/07/2026
- **קבצים:** `app.py`, `test_ad_attribution_gate.py` (חדש)
- **Severity:** Medium — לא critical (הכתיבה נכשלת בכל מקרה כי השדות לא קיימים ב-schema), אבל ריצה מיותרת + לוגים שקטים על כל הודעה.
- **שורש:** מזוהה בענף `claude/leads-write-gate-verify-aodpud` (PR #184 המקורי, אף פעם לא מוזג בפועל ל-main בתור branch, אותר מחדש בסבב "handle branches one at a time"). `app.py`'s `_webhook_whatsapp_impl()` קרא ל-`ad_attribution._inject_utm()` על **כל** הודעת WhatsApp נכנסת ללא תלות ב-flag `AD_ATTRIBUTION` (רשום ב-`feature_flags.py` אך לא נבדק בקריאה הזו) — כל עוד המודול `ad_attribution` יובא בהצלחה. הכתיבה נכשלת בפועל (שדות `utm_source`/`utm_medium`/`utm_campaign`/`platform` לא קיימים ב-`schema_cache.json`/הטבלה החיה), אך הכשל נבלע ב-`logger.debug` — לא נראה בלוגים בפרודקשן.
- **הערה (renumbering):** הענף המקורי קרא לזה `BUG-040` — מתנגש עם `BUG-040` הקיים כבר ב-main (`BUG-V1-A32-SHEETS-FALSE-SUCCESS`, A32 Sheets false-success). ID collision זה תועד קודם בענפי `determined-fermat-sdrmx3`/`xuxfwv` (verification logs שמעולם לא מוזגו). ממוספר מחדש ל-`BUG-057` כאן, בסבב שבו הקוד בפועל מוזג.
- **תיקון:** `if _inject_utm:` → `if _inject_utm and _flag_enabled("AD_ATTRIBUTION"):`. `logger.debug` → `logger.warning` בבלוק ה-`except` כדי שכשל אמיתי (כשהדגל כן דלוק) יהיה גלוי, לא שקט.
- **בדיקה:** `test_ad_attribution_gate.py` (חדש, 2/2) — מדמה בקשת webhook מלאה (חתימה/idempotency/identity/furniture-funnel/output-gateway מדומים), מוודא ש-`_inject_utm` **לא** נקרא כש-`AD_ATTRIBUTION=False` (ברירת מחדל) ו-**כן** נקרא כש-`AD_ATTRIBUTION=True`.
- **PR:** #216 (`fix/bug057-ad-attribution-utm-gate`).
- **Merged:** לא עדיין
- **Deployed:** לא עדיין
- **Verified בפרודקשן:** לא עדיין
- **סטטוס:** ✅ מוזג ל-main (`320d0b3`) — ממתין ל-production verification

### BUG-058 (TIER2-SILENT-PREVIEW-NO-READER) — Tier 2 batch preview מבטיח אישור קבוצתי שלא קיים
- **תאריך:** 03/07/2026
- **קבצים:** `core/lead_candidate_handler.py`, `test_tier2_silent_preview.py` (חדש)
- **Severity:** Medium — לא critical כרגע (`FEATURE_AUTO_CAPTURE` כבוי, אין auto-write בפרודקשן), אך הטעיה חיה על לידים אמיתיים ברגע שהדגל ידלק.
- **שורש:** אותר בסבב Contract Chain audit על PR #215 (BUG-056) — `pending_lead_preview` (Tier 2, `_store_pending_preview` ב-`core/lead_candidate_handler.py`) נכתב אך **לעולם לא נקרא בחזרה** (grep מלא על הריפו: 0 קוראים, רק 2 writers pass-through ב-`session_store.py` + נקודת הכתיבה עצמה). ההודעה למשתמש ("📋 זיהיתי N לידים: ... לשמור את כולם? ענה *כן* לאישור.") נבנית ב-`_handle_clean_batch()` (לא ב-`_store_pending_preview` עצמה — תיקון ל-Contract Chain המקורי שהניח את המיקום הלא-נכון) ומבטיחה במפורש שאישור "כן" יפעל על הקבוצה. בפועל: "כן" נפתר אך ורק דרך `ActionGateway.route_confirmation_word()`/`route_cancellation_word()` (BUG-056), שאין להם שום ידיעה על `pending_lead_preview` — אם יש contract חי מ-Tier 1 הוא "מנצח" בשתיקה, אחרת המשתמש מקבל "אין פעולה שממתינה לאישור" סתמי, בלי הסבר שה-batch שהוא ראה מעולם לא היה בר-אישור.
- **החלטת עיצוב מפורשת:** לא נבנה resolver ל-Tier 2 בסשן זה (batch-confirm דורש עיצוב נפרד — ActionGateway בנוי סביב contract יחיד, לא batch; ראה BUG-056 "נשאר פתוח"). התיקון היחיד: להפסיק להטעות — אם/כש-resolver ייבנה בעתיד, יש להגדיר precedence מפורש בין Tier-1 contract ל-Tier-2 batch-state *לפני* הבנייה.
- **תיקון:** `_handle_clean_batch()`'s הודעת ה-preview שונתה לתצפית-בלבד: "📋 זיהיתי N לידים אפשריים בקבוצה: ... לא שמרתי אותם ולא נפתחה פעולת אישור קבוצתית. אישור קבוצתי עדיין לא זמין. כדי לשמור ליד, שלח ליד אחד בכל פעם או בקש ממני להכין רשימה לבדיקה." אין "ענה כן"/"לאישור" יותר. `_store_pending_preview()` מקבל docstring מפורש `INTENTIONAL — no resolver yet`. השדה `pending_lead_preview` **נשאר נכתב** (audit/future-design, לא נמחק).
- **בדיקה:** `test_tier2_silent_preview.py` (חדש, 4/4) — הודעת Tier 2 נטולת CTA מטעה, `pending_lead_preview` עדיין נכתב, משתמש עם Tier-2 preview בלבד ש-"כן" → "אין פעולה שממתינה לאישור" (לא false positive), הודעת Tier 1 (שיש לה resolver אמיתי) נשארה ללא שינוי. כל 36 קבצי `test_*.py` + `smoke_tests.py` + `core/router/test_router.py` — 0 רגרסיות.
- **PR:** #217 (`fix/bug058-tier2-silent-preview`).
- **Merged:** כן — `769e171` (מאומת `git log origin/main --oneline`)
- **Deployed:** לא אומת (אין גישת Render dashboard מה-sandbox)
- **Verified בפרודקשן:** לא עדיין
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification
- **עדכון אימות 09/07/2026 — כיסוי מול BUG-086/087:** ✅ סגור כטקסט מטעה, לא דרך anti-hallucination. זה לא Agent claim ולא עובר דרך `sanitize_agent_response()`, אלא הודעה קבועה מ-`core/lead_candidate_handler.py`. הקוד הנוכחי ב-`_handle_clean_batch()` אומר במפורש "לא שמרתי אותם ולא נפתחה פעולת אישור קבוצתית" ו"אישור קבוצתי עדיין לא זמין" (`core/lead_candidate_handler.py:713-724`). `_store_pending_preview()` מתועד כ-`INTENTIONAL — no resolver yet`, ושומר `pending_lead_preview` ל-audit/future-design בלבד (`core/lead_candidate_handler.py:770-794`). לכן BUG-086/087 אינם המנגנון הרלוונטי כאן; ה-resolver הקבוצתי נשאר functional gap נפרד ומכוון, אבל ההבטחה הכוזבת "ענה כן לאישור batch" כבר סגורה.

- **עדכון 10/07/2026 — Tier-2 batch-confirm resolver נבנה בפועל, ה-precedence-decision שנדרש לפני בנייה (ראה למעלה) הוכרע ומומש:**
  - **`session_store.py`:** שלוש מתודות חדשות אחרי `get_active_lead_candidate()` — `set_pending_lead_preview(sender, candidates, raw_text, channel, domain)` (TTL 30 דק', כולל `set_at`), `get_pending_lead_preview(sender)` (מחזיר `None` אם פג תוקף, מנקה + `_sync_to_db()` גם ב-expiry — בשונה מ-`get_active_lead_candidate()` הקיים), `clear_pending_lead_preview(sender)`.
  - **`core/lead_candidate_handler.py`:** `_store_pending_preview()` קיבל פרמטרים חדשים `channel`/`domain` (נשמרים בזמן הכתיבה — ב-app.py section 2.55, נקודת ה-resolve, ה-Router עוד לא רץ ואין `resolved_route_domain` זמין שם). פונקציה חדשה `resolve_pending_lead_preview(identity, chat_id, is_confirm, is_cancel)` — קוראת preview בחזרה, "כן" מפעיל `_handle_batch()` בפועל (כתיבה אמיתית ל-Airtable per lead) עם channel/domain מה-preview עצמו, "לא" מנקה בלי לכתוב. מחזירה `None` אם אין preview/פג תוקף/לא confirm-או-cancel — כך ש-app.py ממשיך לזרימה הרגילה. הודעת ה-preview חזרה להזמין אישור אמיתי ("ענה \"כן\" לשמירת כולם, או \"לא\" לביטול. (בתוקף ל-30 דקות)") — כי הפעם יש resolver אמיתי מאחוריה.
  - **Precedence decision (הקונפליקט שסומן כלא-פתור):** Tier-1 ActionGateway **מנצח תמיד** Tier-2 batch preview כששני המנגנונים חיים בו-זמנית לאותו `chat_id` — לא נבחר סתם, זו המשכיות ישירה של precedent קיים כבר בקוד (BUG-056: "check ActionGateway live contracts FIRST, regardless of FEATURE_ACTION_GATEWAY"). מומש ב-`app.py`'s section 2.55: קריאה ל-`resolve_pending_lead_preview()` נוספה **בתוך** ה-`elif _lower in _CONFIRM_WORDS:`/`elif _lower in _CANCEL_WORDS:` הקיימים, **אחרי** ש-`_gw_cw.find_live_contracts(...)`/`route_cancellation_word(...)` (Tier-1) כבר נבדקו ולא מצאו כלום — לא בנקודת כניסה נפרדת/מוקדמת יותר כפי שהוצע בטיוטת התיקון המקורית. Tier-2 resolver עצמו לא בודק Tier-1 בכלל (במפורש ב-docstring) — ה-ordering guarantee חי כולו ב-caller (`app.py`), לא בתוך `resolve_pending_lead_preview()`.
  - **בדיקה:** `test_tier2_silent_preview.py` נכתב מחדש (9/9) — הודעת Tier-2 מזמינה אישור אמיתי, `pending_lead_preview` נכתב עם `set_at`/`channel`/`domain`, "כן" כותב בפועל דרך `_handle_batch` עם channel/domain מהמאוחסן, "לא" מנקה בלי לכתוב, preview שפג תוקפו נופל דרך (`None`), אין-preview נופל דרך, לא-confirm-ולא-cancel לא צורך את ה-preview, ו-regression guard ל-Tier-1 (הודעת preview המקורית לא השתנתה). `test_c89_preview_confirmation.py`'s בדיקה סטטית (`test_app_py_confirm_word_checks_gateway_before_flag_branch`) עודכנה (חלון חיפוש הורחב מ-1200/3000 ל-3000/5000 תווים — הקוד החדש דחף את `_flag_cw(...)`/`_CANCEL_WORDS` רחוק יותר מה-marker, אך הסדר עצמו — `find_live_contracts` לפני `_flag_cw` — לא השתנה) — 9/9. אפס רגרסיה: `test_action_gateway.py` (37/37), `test_bug070_combined_wording.py` (27/27), `test_bug070_pending_approval_multi.py`, `smoke_tests.py`, `test_integration.py` (4/4), `core/router/test_router.py` (44/44), `test_c53a.py` (50/50), `test_approval_concurrency.py` (14/14), וכל שאר `test_*.py` בריפו (חוץ מ-`test_document_converter.py` — כשל קודם/לא-קשור, משוכפל זהה גם על `main` ללא נגיעה).
  - **PR:** ראה branch/PR של סבב זה (10/07/2026).
  - **Merged:** ממתין ל-push/PR.
  - **סטטוס:** ✅ **BUG-058 סגור במלואו** — התיקון המקורי (טקסט מטעה) + הפתרון המלא (resolver אמיתי, precedence מוכרע ומיושם) שניהם ב-main/ממתינים ל-merge. לא נותר functional gap.

- **עדכון 10/07/2026 — בדיקה חיה בפרודקשן, תוצאה מדויקת: BUG-058 (ה-resolver עצמו) IMPLEMENTED ✅, אך PROD TEST חשף באג נפרד במעלה הזרם:**
  - **מה עבד:** הלוג `[LCH] resolve_pending_lead_preview(confirm): user=boss_hq:eliyahu` הוכיח ש-"כן" נתפס נכון ע"י ה-resolver, `pending_lead_preview` נקרא בחזרה, וה-batch בוצע בפועל (לא נפל ל-"אין פעולה שממתינה לאישור") — **בדיוק ה-gap שה-resolver נועד לסגור נסגר**, מאומת חי, לא רק בטסטים.
  - **מה לא עבד (לא קשור ל-resolver עצמו):** שני הלידים בבאצ' נכתבו לאותה רשומת Airtable בדיוק, עם אותו שם שגוי למועמד השני. שורש: `parse_batch_dictation()` (שורש upstream, קודם ל-resolver, קודם אפילו ל-`_store_pending_preview`) העתיק את שם המועמד הראשון למועמד השני לפני שהם בכלל הגיעו ל-preview — ה-resolver רק העביר הלאה candidates שכבר היו שגויים. ראה **BUG-094** (למטה) לאבחון המלא ולתיקון.
  - **מסקנה מדויקת:** ה-resolver (BUG-058's scope) עצמו לא היה הבאג — הוא רק חשף באג upstream קיים-מראש (BUG-094) שהיה בלתי-נראה כל עוד לא היה resolver שמבצע את ה-batch בפועל. BUG-058 נשאר ✅ סגור לגבי ה-scope שלו (route "כן"/"לא" ל-preview אמיתי); הבטיחות של batch confirm מקצה-לקצה תלויה כעת ב-BUG-094 (תוקן באותו סבב, ראה למטה) — **לפני BUG-094, batch confirm "קיים אך אינו בטוח לשימוש"**; בדיקה חוזרת בפרודקשן אחרי מיזוג BUG-094 חייבת להראות שני `record_id` שונים לשני מועמדים שונים.

### BUG-059 (LEAD-EVENT-DOMAIN-ORDERING-DORMANT-INJECTION) — ענף claude/lead-event-domain-ordering (לא ממוזג) מכיל prompt-injection surface + dual mechanism
- **תאריך:** 03/07/2026
- **קבצים:** תצפית על ענף `claude/lead-event-domain-ordering` (commit `4b80602`) — לא נוגע בקוד ב-main, אין שינוי בסשן זה.
- **Severity:** Medium (לא Critical — הענף לא ממוזג, אין production exposure כרגע).
- **שורש (2 בעיות שחוסמות merge כמו-שהוא):**
  1. **Unsanitized injection ל-system prompt:** `core/lead_candidate.py`'s `_INTRO_PATTERN` (בענף) קולט כל טקסט שתואם `[א-תA-Za-z][א-תA-Za-z\s\'\"]{2,40}` אחרי trigger phrase ("אני "/"שמו "/"שמה "/"ליד חדש:"/"לקוח חדש:") — ללא שום ולידציה שזה שם סביר. `app.py`'s step "1.4.5" (בענף) מזריק את זה גולמי ל-`ctx.system_prompt` דרך `{_cand_name!r}` (Python `repr()` — לא sanitization/escaping אמיתי) בתוך ניסוח ציווי ("חובה... כוון תמיד ל-X, לא לאליהו"). הגייט הוא `if identity.is_internal:` — כלומר לא lead חיצוני יכול להפעיל את זה ישירות על ההודעה שלו, אבל כל טקסט שעובר דרך sender פנימי (כולל העתק-הדבק של הודעת לקוח ע"י עובד) הופך להוראת system-prompt ללא סינון.
  2. **Dual Mechanism:** `session_store.py`'s `active_lead_candidate` (כבר ב-main, מומש עצמאית עם TTL=30 דק') ו-`core/lead_candidate.py` (בענף, אותו רעיון בדיוק) הם שני מימושים נפרדים לאותו קונספט — merge כמו-שהוא ייצור כפילות/סתירה, לא רק redundant code.
- **תיקון:** לא בוצע — הענף לא מוזג, אין production exposure. תיעוד בלבד לקראת merge עתידי כלשהו.
- **חובה לפני merge עתידי של הענף הזה (או כל SPEC חדש שמממש את אותו רעיון):**
  1. Resolve בין שני המנגנונים (`active_lead_candidate` הקיים ב-main מול `core/lead_candidate.py` בענף) — לא לבנות שניים.
  2. Sanitize את ה-capture, או להעביר אותו כ-user-turn content (לא system-prompt עם ניסוח ציווי).
- **בדיקה:** לא רלוונטי — תיעוד בלבד, אין קוד שרץ.
- **PR:** #218 (docs-only, `docs/bug059-lead-event-injection-audit`).
- **Merged:** לא עדיין
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי (הענף המקורי dormant, לא בפרודקשן)
- **סטטוס:** 🟡 Documented, no fix — dormant, לא דחוף

### BUG-060 (AD-ATTRIBUTION-ORDERING) — inject_source_to_incoming_lead רץ לפני route_request — נבדק, לא bug
- **תאריך:** 03/07/2026
- **Severity:** Low (documented, not a bug).
- **הקשר:** Audit 1/4, משפחת "Pre-Router Bypasses" — נבדק בהמשך ל-BUG-057/058/059 שהיו bypasses אמיתיים באותה משפחה.
- **ממצא:** `ad_attribution.py`'s `inject_source_to_incoming_lead()` (קריאה יחידה מ-`app.py:2162`, מאחורי `if _inject_utm and _flag_enabled("AD_ATTRIBUTION")`) רץ **לפני** `route_request()` ב-`_webhook_whatsapp_impl()`. נבדק במלואו:
  1. **עדכון-בלבד:** `record_lead_source()` (הכתיבה היחידה שהפונקציה מפעילה) קוראת `airtable_get` לפי `memory_key`; אם אין רשומה קיימת — `return False`, **אין `airtable_add`/יצירה בשום מסלול**.
  2. **שדות:** רק `utm_source`/`utm_medium`/`utm_campaign`/`platform` (`UTMParams.to_airtable_fields()`) — `grep -n domain ad_attribution.py` → 0 hits, אין נגיעה ב-domain.
  3. **Domain-overlap:** 0 חפיפה עם Router / `capture_router.py` / `lead_candidate_handler.py` — אין race, אין קונפליקט כתיבה.
  4. **furniture_lead_funnel.py:** נבדק בנפרד — 0 hits על `utm_source`/`utm_medium`/`utm_campaign`/attribution; ה-bypass שנמצא שם ב-Audit 1/4 שייך למשפחה אחרת (funnel state machine), לא ל-attribution.
  5. **Gate:** מאחורי `AD_ATTRIBUTION` (`_flag_enabled`), כבוי כברירת מחדל — לא ב-`_DEFAULTS` ב-`feature_flags.py`.
- **החלטה:** אין תיקון — הריצה-לפני-Router היא כוונה מוצהרת (attribution לא אמור להיות תלוי בהחלטת domain/routing), לא bypass. תועד ב-`docs/governance/MODULE_RULES.md` (תוספת לחוק 9 — Input Precedence) כחריג מכוון.
- **תיקון:** לא נדרש.
- **בדיקה:** grep מלא (`domain`, `utm_source`/`utm_medium`/`utm_campaign`, `inject_source_to_incoming_lead`/`_inject_utm`) על הריפו — ראה `docs/governance/MODULE_RULES.md` לפירוט.
- **PR:** אין — עדכון תיעוד בלבד (`docs/governance/MODULE_RULES.md`, `BUG_AUDIT_LOG.md`).
- **Merged:** N/A (docs-only)
- **Deployed:** N/A
- **Verified בפרודקשן:** N/A
- **סטטוס:** ✅ מתועד כחריג מכוון — לא נכנס לתור תיקונים

### BUG-061 (BUG-IC-01B) — ביטויים דו-משמעיים עם prefix טבעי ("אני צריך למלא משימות") לא נתפסו ע"י BUG-IC-01
- **תאריך:** 04/07/2026
- **קבצים:** `core/router/intent_router.py`, `core/router/test_router.py`
- **Severity:** Medium — המשך ישיר ל-BUG-048/BUG-IC-01; אותה חשיפה (Agent עם כלים מלאים) אך רק על ביטויים עם prefix.
- **שורש:** `_AMBIGUOUS_PHRASES` (BUG-048) טיפל רק בביטויים חשופים ("סטטוס", "למלא משימות") עם `^...$` anchoring מלא — כל prefix טבעי ("אני צריך ...", "צריך ...", "רוצה ...", "אפשר ...", "תעזור לי ...") לפני הביטוי הדו-משמעי גרם ל-`pattern.match()` להיכשל, והמשפט נפל ל-`Intent.UNKNOWN` → `Handler.AGENT` עם גישה מלאה לכלים (כולל `airtable_get` על Tasks בפועל, לפי הדיווח החי) ללא בקשת הבהרה.
- **תיקון:** 3 patterns חדשים ב-`_AMBIGUOUS_PHRASES` (status/system-check, system-tests, tasks) שכל אחד תופס prefix אופציונלי `(אני\s+)?(צריך|רוצה|אפשר|תעזור לי)` לפני הביטוי הדו-משמעי המקורי, ומחזיר את אותה שאלת הבהרה כמו הגרסה החשופה.
- **בדיקה:** `core/router/test_router.py` — 6 מקרים חדשים ("אני צריך למלא משימות", "צריך למלא משימות", "תעזור לי למלא משימות", "אני צריך לראות סטטוס", "צריך סטטוס", "אני צריך בדיקות מערכת") → `Intent.UNKNOWN`/`Handler.CLARIFY`. 44/44 עברו.
- **PR:** #220 (`claude/ic-01b-ambiguous-prefix-routing-zp109k`)
- **Merged:** כן — `b76e6d5`, מאומת דרך `mcp__github__pull_request_read` (`merged: true`, `merged_at: 2026-07-04T21:50:30Z`) וגם `git log origin/main`
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `python3 core/router/test_router.py` → 44/44 + 3 בדיקות Tier-4; `python3 -m py_compile core/router/intent_router.py`
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification

### BUG-062 (BUG-C89-APPROVAL-IDENTITY) — פעולה שאושרה ע"י owner מאבדת role וחוזרת ל-readonly ב-dispatch
- **תאריך:** 04/07/2026
- **קבצים:** `core/action_gateway.py`, `core/lead_candidate_handler.py`, `app.py`, `test_action_gateway.py`, `test_c89_preview_confirmation.py`
- **Severity:** High — owner שמאשר פעולה (למשל עדכון ליד) עם "כן" נחסם ע"י ה-dispatcher כאילו היה readonly.
- **שורש:** `ActionGateway.propose_action()` נקרא עם `origin_chat_id=identity.memory_key` (למשל `"boss_hq:eliyahu"`) ולא external_id אמיתי של הערוץ. ב-`approve()`, ה-executor שנבנה ע"י `_make_dispatch_executor` קרא `resolve_identity(contract.origin_channel, contract.origin_chat_id)` → מפתח `"telegram:boss_hq:eliyahu"` שלא קיים ב-registry → נפילה שקטה ל-`Role.READONLY` (הערוץ אינו whatsapp) → `dispatch_tool` חוסם פעולה שאושרה בפועל ע"י ה-owner (`airtable_update` על Leads).
- **תיקון:** `ActionContract` שומר כעת actor identity שנפתרה בזמן ה-propose (`actor_role`/`actor_user_id`/`actor_external_id`/`actor_display_name`/`actor_domain_id`/`actor_allowed_domains`) דרך פרמטר `identity=` חדש (אופציונלי) ב-`propose_action()`. ה-executor ב-`_make_dispatch_executor` בונה `Identity` ישירות מהשדות השמורים על ה-contract במקום `resolve_identity()` מחדש; חוזים ישנים ללא actor שמור נופלים חזרה ל-`resolve_identity()` כמו קודם (backward-compatible). עודכנו קריאות ב-`core/lead_candidate_handler.py` (`_write_one_lead`, `_propose_lead_write`) וב-`app.py`'s `_queue_approval` להעביר `identity=identity`.
- **תוספת UX (C89):** כשמועמד-ליד תואם ליד קיים, ה-preview אומר כעת "מצאתי ליד קיים. לעדכן אותו?" במקום "לשמור?" הגנרי; עדכון ליד קיים תמיד דורש אישור, גם כש-`FEATURE_AUTO_CAPTURE=true` — רק ליד חדש לגמרי נכתב אוטומטית.
- **בדיקה:** `test_action_gateway.py` (37/37, כולל בדיקת רגרסיה חדשה שמאמתת ש-dispatcher מקבל `role=owner` ולא `readonly`, ואומתה ידנית שנכשלת ללא התיקון), `test_c89_preview_confirmation.py` (9/9, כולל 3 בדיקות חדשות ל-UX העדכון), `core/router/test_router.py` (44/44), `test_tier2_silent_preview.py`/`test_stage_b_verification.py`/`test_approval_gate_registry.py` — כולם ירוקים.
- **PR:** #222 (`claude/ic-01b-ambiguous-prefix-routing-zp109k`) — **הערה תפעולית:** ה-commit נדחף במקור לאותו ענף כמו BUG-061 *אחרי* ש-PR #220 כבר מוזג, ולכן לא נכלל בו בפועל בטעות. אותר; הענף אותחל מחדש מ-`main` העדכני (`git rebase origin/main`) ונדחף מחדש (`--force-with-lease`) לפני פתיחת PR #222 נפרד.
- **Merged:** כן — `717465a`, merge commit `57e7cad` (מאומת `git log origin/main --oneline`)
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** ראה בדיקה למעלה; `git merge-base --is-ancestor 717465a origin/main` → הצלחה
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification

### BUG-063 (BUG-SESSIONS-ROOT) — Session lookup נכשל בשקט ומאפשר POST כפול במקום PATCH
- **תאריך:** 04/07/2026 (זוהה ותוקן בענף נפרד `codex/bug-sessions-root` ע"י כלי אחר; נסקר, נבדק עצמאית ומוזג בסבב זה)
- **קבצים:** `session_store.py`, `tools/airtable_tools.py`, `test_session_store_contract.py` (חדש)
- **Severity:** Medium/High — המשך ישיר ל-BUG-047/BUG-NEW-12; באג-שורש שהשאיר את הבעיה חלקית פתוחה.
- **שורש:** `_find_best_session_in_db()` פרסר את הפלט המפורמט-לבני-אדם של `airtable_get()` באמצעות regex (`_SESSION_RECORD_RE`). כל כשל בפרסור/שגיאת רשת/תשובה לא צפויה גרם להחזרת "לא נמצא" (`found_count=0`), ו-`_sync_to_db()` ביצע POST (יצירת רשומה חדשה) גם כשרשומת Session אמיתית כבר קיימת — כפילות שקטה בכל פעם שה-lookup היה flaky, לא רק כשבאמת לא היו רשומות.
- **תיקון:** `tools/airtable_tools.py` מקבל `airtable_get_records()` חדש — reader מובנה (list[dict], לא string), עם pagination מלא ו-`raise` על כשל HTTP/contract (fail-closed, לא "אין רשומות" שקט). `airtable_get()` הישן נשאר עטיפה תואמת-לאחור מעליו (Agent-facing string בלבד). `_sync_to_db()`/`_find_best_session_in_db()` ב-`session_store.py` הוחלפו לקרוא ל-`airtable_get_records()` ומאמתים כל רשומה במבנה (`_validated_records`); POST מותר **רק** כש-`found_count == 0 and reason == "no_records"` — כל מצב אחר (שגיאה, contract mismatch, תוצאה עמומה) חוסם יצירה ומחזיר `False` (fail-closed) במקום POST שקט. נוסף `_normalize_sender()` לאחידות מפתחות sender בין get/get_or_create/delete/sync/lookup.
- **בדיקה:** `python3 session_store.py` — 49/49; `python3 -m pytest test_session_store_contract.py` (חדש) — 4/4 (בחירת רשומה מרובה + נירמול sender, 17 כפילויות → PATCH יחיד ואפס POST, contract-mismatch חוסם POST, pagination). נבדק עצמאית ב-worktree מבודד לפני פתיחת PR: `test_airtable_gateway.py` (25/25), `test_inbound_handler.py` (11/11), `test_furniture_lead_funnel.py` (22/22), `test_c53a.py` (50/50), `py_compile` נקי, `git merge-tree` מול `main` העדכני — אפס קונפליקטים.
- **PR:** #221 (`codex/bug-sessions-root`) — נוצר ונפתח ע"י session זה (הכלי המקורי נחסם ע"י בעיית auth ב-`gh` CLI); הענף/commit זוהו ע"י המשתמש, נבדקו ואומתו עצמאית לפני פתיחת ה-PR.
- **Merged:** כן — `eead2cc`, מאומת דרך `git log origin/main --oneline` (merge commit `1718ce7`)
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** ראה בדיקה למעלה; `git merge-base --is-ancestor eead2cc origin/main` → הצלחה
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification

### BUG-064 (BUG-C89-TIER4-PRECEDENCE) — טבלה/ייצוא/פלט-מערכת לא תמיד גובר על חילוץ ליד
- **תאריך:** 04/07/2026
- **קבצים:** `core/ingress_classifier.py`, `test_c89_tier4_precedence.py` (חדש)
- **Severity:** High — פלט Airtable/CSV/טבלה מודבק סווג כ-Tier 1/2 והגיע ל-Agent/ActionGateway עם `airtable_add`/`airtable_update` בפועל, במקום Tier 4 (preview בלבד, ללא כתיבה).
- **שורש:** `_is_tier4()` (השער היחיד — נצרך גם ע"י `router.py`'s Tier-4 stop-gate וגם ע"י `core/lead_candidate_handler.py`) כיסה רק תת-קבוצה צרה של סמנים (טבלת pipe/tab, timestamp עם `/`, Airtable rec/fld ID של 8+ תווים, JSON block, CSV של 3+ שורות עם 2+ פסיקים, ≥3 שורות עם אימוג'י בוט). לא כוסו: כותרות טבלה ללא separator מפורש (`Name, Phone, City, Status` / `שם, טלפון, עיר, סטטוס`), טבלאות fixed-width עבריות (עמודות מיושרות ברווחים), ופלטי סטטוס/ציון של Airtable (`Status:`, `Score:`, `View in Airtable`, `memory_key`/`@lead`, `owner_dictation`).
- **תיקון:** הורחב `_is_tier4()` היחיד (`core/ingress_classifier.py`) — לא נוסף שער מקביל במקום אחר: `_has_table_header()` (כותרת מופרדת בפסיק/טאב/2+ רווחים עם 2+ מילות-כותרת מוכרות, עברית+אנגלית), `_has_fixed_width_table()` (2+ שורות עם 2+ מקטעי "מילה+2 רווחים+"), `_LITERAL_MARKERS` (רשימת מחרוזות מערכתיות), `_MEMORY_KEY_RE` (פורמט `tenant/phone@lead`), `_SCORE_LIKE_RE` (`NN/100`), timestamp עם נקודות (`[DD.MM.YYYY, HH:MM]`), והורחב זיהוי פלט-בוט (נוספו 📋/🌤️/█, סף הורד מ-3 ל-2 שורות). מילת "airtable" בודדת מוגבלת לדרוש מבנה נוסף (נקודתיים/שורה חדשה/rec ID/memory_key) כדי לא לבלוע פקודת בדיקת-מערכת מפורשת קצרה ("תבדוק עכשיו את Airtable") — regression שנתפס ותוקן מול `core/router/test_router.py` הקיים לפני פתיחת ה-PR.
- **בדיקה:** `test_c89_tier4_precedence.py` (חדש, 13/13) — כל 6 התרחישים הנדרשים (View in Airtable+Status/Score, פלט בוט ✅/📋/🌤️, owner_dictation+memory_key+score, כותרות CSV, טבלה עברית fixed-width, Airtable rec ID) + 3 בקרות שלילה (ליד רגיל, פקודת בדיקת-מערכת מפורשת, batch ליד נקי אמיתי). `test_capture_router_wiring.py` (10/10), `core/router/test_router.py` (44/44) — אפס רגרסיה.
- **PR:** #223 (`claude/ic-01b-ambiguous-prefix-routing-zp109k`)
- **Merged:** כן — `b7d8445`, merge commit `84973b9` (מאומת `git log origin/main --oneline`)
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** ראה בדיקה למעלה; `git merge-base --is-ancestor b7d8445 origin/main` → הצלחה
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification

### BUG-065 (C89-RAW-OBS) — raw_ref תמיד ריק, אין observation על החלטת סיווג
- **תאריך:** 04/07/2026
- **קבצים:** `core/ingress_classifier.py`, `feature_flags.py`, `test_c89_raw_obs.py` (חדש)
- **Severity:** Low/Medium — פער תיעוד/observability, לא bug פונקציונלי (Tier gating עצמו עבד נכון) — `IngressClassification.raw_ref` היה מסומן "future — empty for now" ומעולם לא מולא, ואין תיעוד AgentObservation לאף החלטת סיווג.
- **שורש:** `classify_ingress()` (השער היחיד לכל סיווג קלט) בנה `IngressClassification` עם `raw_ref=""` קבוע בכל אחת מ-7 נקודות ה-return שלו, ומעולם לא קרא ל-`ActionGateway.record_agent_observation()` — אין עקבות ניתנות-לביקורת של מה סווג ולמה.
- **תיקון:** `classify_ingress()` הוסבה לעטיפה דקה סביב הלוגיקה המקורית (שהוזזה, ללא שינוי, ל-`_classify_ingress_core()`); העטיפה מפעילה עבור **כל** קריאה (Tier 1-5, כולל `empty_text`/`source_type` לא נתמך): (1) `_save_raw_capture()` — כותב את הטקסט הגולמי ל-`Tables.DECISION_INBOX` (שדה `RAW_INPUT`) מאחורי flag חדש `FEATURE_RAW_CAPTURE` (כבוי כברירת מחדל, רשום ב-`feature_flags.py`), ותמיד מחזיר reference לא-ריק — ה-record id האמיתי כשה-flag פעיל והכתיבה הצליחה, אחרת fallback מקומי (`local:<uuid>`); כשל בכתיבה/Airtable לעולם לא חוסם את הסיווג. (2) `_record_classification_observation()` — רושם `AgentObservation(kind="capture_classification", text="tier=<n> confidence=<f> reason=<r> raw_ref=<ref>")` דרך ה-API הקיים בלבד של `ActionGateway.record_agent_observation(contract_id=None, ...)` — ללא שום שינוי בליבת ה-Gateway (contract/ledger).
- **בדיקה:** `test_c89_raw_obs.py` (חדש, 14/14) — `raw_ref` לא-ריק ל-Tier 1/4/5 (וגם `empty_text`/`source_type` לא נתמך), observation נרשם לכל קריאה על פני Tier 1/2/4/5 עם `contract_id=None` וצורת טקסט נכונה, והתנהגות flag on/off/כשל-כתיבה. `test_capture_router_wiring.py` (10/10), `core/router/test_router.py` (44/44), `test_c89_tier4_precedence.py` (13/13) — אפס רגרסיה.
- **PR:** #224 (`claude/ic-01b-ambiguous-prefix-routing-zp109k`)
- **Merged:** כן — `68f8c97`, merge commit `cd9576f` (מאומת `git log origin/main --oneline`)
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** ראה בדיקה למעלה; `git merge-base --is-ancestor 68f8c97 origin/main` → הצלחה
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification
- **עדכון (PR #227, `ca207ba`, merge commit `64b477a`):** תיקון היה נכון פונקציונלית, אך `_classify_ingress_core()` עדיין כתב `raw_ref=""` באופן מילולי בכל אחת מ-8 נקודות ה-return הפנימיות שלה (הערך נדרס ע"י ה-wrapper לפני ההחזרה בפועל, אבל grep סטטי על `raw_ref=""` עדיין מצא hits ותועד בטעות כאילו התיקון חסר). `IngressClassification.raw_ref` קיבל ברירת מחדל sentinel פרטי (`__unset__`) במקום `""`, כך שאף return statement פנימי לא צריך להזכיר `raw_ref` בכלל — `classify_ingress()` הוא המקום היחיד שמקצה ערך אמיתי. אומת: `grep -rn 'raw_ref=""' --include="*.py" .` → אפס hits בקוד בפועל (רק במחרוזת הבדיקה עצמה). נוסף guard סטטי (`inspect.getsource`) ל-`test_c89_raw_obs.py` — 15/15. אין שינוי התנהגות.

### BUG-066 (BUG-DAILY-01) — ✅ תוקן — Boss Daily Tasks נתקע ולא ממשיך (אין fail-safe פר-שלב)
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש — תצפית תפעולית ("הריצה מתחילה, אך נעצרת/נתקעת באמצע, בלי מעבר תקין להמשך השלבים")
- **קבצים:** `daily_collector.py`, `scheduler.py`
- **Severity:** High
- **שורש (מאומת בקוד):** `daily_collector.py`'s `collect_daily()` עוטף רק את קריאת ה-LLM+parse ב-try/except (`daily_collector.py:76-100`, `except Exception as e: logger.error(...); return {"items": [], "all_clear": True}`). קריאת ה-history (`memory.get_for_claude(memory_key)`, שורה 62) **לא** עטופה בכלל — חריגה שם מתפשטת ללא טיפול. `format_collector_message()` (שורות 114-135) **גם היא ללא כל try/except**. כלומר מתוך 3 שלבים אמיתיים (fetch history → LLM/parse → format/send), רק אחד מוגן. הרשת היחידה שתופסת כשל בלתי-מוגן היא ה-wrapper החיצוני ב-`scheduler.py:72-87`'s `_job_daily_collector()` — `except Exception as e: logger.error(f"daily_collector error: {e}")` — **בלוק אחד גורף**, לא פר-שלב, כך שהלוג לעולם לא מציין איזה שלב נכשל (fetch/LLM/format/send), ואין log של "התחלת שלב"/"סיום שלב"/"דילוג" בשום מקום. Timeout מפורש קיים רק לקריאת Anthropic (`timeout=30`, `daily_collector.py:80`) — ל-`bot.send_message` (שורות 157-161) אין timeout מוגדר בשום מקום בריפו (מאומת גרפ על `apihelper`). ה-scheduler loop עצמו (`scheduler.py:740-747`) עטוף try/except משלו, כך שחריגה *שנזרקת* לא הורגת את ה-thread לצמיתות — אבל קריאה ש**נתקעת** (hang, לא raise) בכל מקום ללא timeout (במיוחד `send_message`) תחסום את `schedule.run_pending()` הבודד-thread-י הזה ותקפיא כל job אחר שממתין באותו תור, וזה בדיוק המנגנון הריאלי ל"נתקע ולא ממשיך".
- **תיקון:** ✅ בוצע — `daily_collector.py`'s `collect_daily()` פוצל ל-2 שלבים מבודדים בנפרד (fetch history / LLM+parse), כל אחד עם try/except משלו ו-logging מפורש (start/done/error); הפונקציה לעולם לא raise-ת, תמיד מחזירה fallback בטוח. `send_daily_collector()` בודד גם את שלב ה-format ואת שלב ה-send בנפרד, כל אחד עם try/except+logging משלו. `bot.send_message()` מקבל כעת `timeout=15` מפורש (`_SEND_TIMEOUT`) כדי שקריאת רשת תקועה לא תקפיא את ה-scheduler thread הבודד. `scheduler.py`'s `_job_daily_digest`/`_job_daily_collector` קיבלו logging מפורש של start/done/skip/error ברמת ה-job (בנוסף לזה שבתוך `daily_collector.py` עצמו). כאגב תוקנה גם corruption (mojibake) שהתגלתה בשתי שורות טקסט בקובץ (דומה ל-BUG-018) — לא היו קשורות לבאג המקורי אך תוקנו באותה עריכה.
- **בדיקה:** `test_bug066_daily_collector_fail_safe.py` (חדש, 8/8) — כשל בשלב fetch/LLM/JSON-parse/format/send כל אחד בנפרד לא raise-ה, נרשם ב-log, וממשיכה בבטחה; מסלול הצלחה מציג logging של כל גבול-שלב; `timeout` מפורש מאומת בקריאה ל-`bot.send_message`; regression guard ש-`all_clear=True` לא שולח כלום. `test_c86_scheduler_emergency_matrix.py` (2/2) ו-`test_bug067_shabbat_gates_scheduled_digest.py` (3/3) — ירוקים ללא שינוי (אותו registration block ב-`scheduler.py`). `smoke_tests.py` — `build_digest` מחזיר בדיוק אותם 215 תווים (לא נגעתי ב-`daily_digest.py`).
- **PR:** #231
- **Merged:** כן (`aa30695`, merge commit `f2431e1`) — מאומת `git log origin/main --oneline`
- **Deployed:** לא מאומת עדיין (תלוי Render deploy — לא נבדק במסגרת session זה)
- **Verified בפרודקשן:** לא עדיין
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification

### BUG-067 (BUG-DAILY-02) — ✅ תוקן — Daily Digest נשלח בשבת למרות הודעת "Shabbat Mode" — הגייט הוסיף טקסט בלבד, לא חסם שליחה
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש — ראיה חיה: דוח נשלח ב-04/07/2026 (שבת) עם כותרת "שבת — הודעות אוטומטיות מושהות עד מוצ״ש בשעה 20:00 בערך" בראש הדוח עצמו שנשלח
- **קבצים:** `daily_digest.py`, `shabbat_guard.py`, `scheduler.py`
- **Severity:** High — סתירה לוגית ישירה בין ההודעה לבין ההתנהגות בפועל
- **שורש (מאומת בקוד):** `shabbat_guard.py` מספק **שני מנגנונים נפרדים**: (1) `should_send_now(channel)`/`shabbat_safe(job_fn)` (שורות 131-147, 187-201) — gate אמיתי שמדלג על קריאת ה-job לגמרי בזמן שבת/חג ("Job '...' skipped — Shabbat/Holiday"). (2) `shabbat_status_message()` (שורות 173-180) — מחזיר **רק מחרוזת תצוגה**, ללא אפקט חוסם. `daily_digest.py` משתמש **אך ורק** במנגנון השני: `build_digest()` (שורה 301-302) מייבא ומפעיל רק `shabbat_status_message()`, ומצרף אותו כשורת כותרת בראש הדוח (שורות 319-321: `if shabbat: header.append(shabbat)`) — לעולם לא מחזיר early, לעולם לא מבטל את השליחה. `send_daily_digest()` (שורות 341-351) קורא תמיד ל-`bot.send_message(...)` ללא תלות בשבת. גרפ מלא על `daily_digest.py` מאשר: `should_send_now`/`shabbat_safe`/`is_shabbat_now` **אף פעם לא מיובאים או נקראים** בקובץ. **ההוכחה המכרעת שזו לא תקלה נקודתית אלא פער מבני:** ב-`scheduler.py:801-816`, רוב ה-jobs עטופים ב-`shabbat_safe(...)` (למשל שורות 808-816: `followup_scan`, `payment_reminders`, `lead_recovery`, `abandoned_scan`, `audience_report`, `interaction_scan`) — אבל דווקא `_job_daily_digest` (שורה 802) ו-`_job_daily_collector` (שורה 804) **אינם עטופים ב-`shabbat_safe`** בכלל. מאומת ישירות ב-`grep -n "_job_daily_digest\|_job_daily_collector\|shabbat_safe" scheduler.py`.
- **תיקון:** ✅ בוצע — `scheduler.py`'s `_job_daily_digest`/`_job_daily_collector` נעטפו ב-`shabbat_safe(...)` (אותו pattern בדיוק כמו 6 ה-jobs האחרים, אותו סדר קומפוזיציה `shabbat_safe(_automation_guard(fn, name=...))`). 2 שורות שונו ב-`scheduler.py` בלבד — לא נגע ב-`build_digest()`, Airtable queries, scoring, leads, formatting (מאומת: `smoke_tests.py`'s `check_daily_digest` מחזיר בדיוק אותם 215 תווים לפני ואחרי).
- **בדיקה:** `test_bug067_shabbat_gates_scheduled_digest.py` (חדש, 3/3) — שני ה-jobs מדולגים כש-`should_send_now()` מחזיר `False` (gate אמיתי, לא מנוטרל), שניהם עדיין רצים ביום רגיל (regression guard), וכל job אחר (מגודר-שבת כבר קודם / לא-מגודר-שבת בכלל) נשאר בדיוק כמו שהיה (scope guard) — לפי אותו pattern רישום-וקריאה של `test_c86_scheduler_emergency_matrix.py` הקיים (2/2, ירוק ללא שינוי). `shabbat_guard.py`'s self-test הפנימי (19/19) — ירוק, לא נגע במודול עצמו.
- **PR:** #230 (`fix/bug067-shabbat-gate-digest`)
- **Merged:** כן — `b31b880`, merge commit `cfa3205` (מאומת `git log origin/main --oneline`)
- **Deployed:** לא אומת מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** ראה בדיקה למעלה; `git merge-base --is-ancestor b31b880 origin/main` → הצלחה
- **סטטוס:** ✅ מוזג ל-main — ממתין ל-production verification (הרצה אמיתית בשבת קרובה)

### BUG-068 (BUG-DAILY-03) — Daily Digest ארוך מדי, ללא הגבלת אורך/מספר פריטים
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש
- **קבצים:** `daily_digest.py`
- **Severity:** Medium-High (UX)
- **שורש (מאומת בקוד):** `build_digest()` (`daily_digest.py:295-338`) מרכיב 6 סקשנים (`_hot_leads` max_rec=8, `_followups_today` max_rec=15, `_roadmap_tasks_today` max_rec=30, `_open_deals` max_rec=10, `_upcoming_payments` max_rec=10, `_yesterday_changes` — leads max_rec=10 + deals max_rec=5 + completed tasks max_rec=5) ומחבר אותם ב-`"\n".join(...)` (שורות 325-338) **ללא שום cap על אורך כולל, מספר שורות, או בדיקה מול מגבלת ה-4096 תווים של Telegram**. ה-`max_rec` הקיימים מגבילים רק כמה רשומות **נשלפות מ-Airtable**, לא כמה **מוצגות בפועל** בדוח — אין "top N לפי עדיפות והשאר מקופל", אין הפרדה "דורש פעולה" מול "מידע בלבד" (`_roadmap_tasks_today`, שורות 154-166, כן מקבץ לפי P0-P3 אבל מדפיס **כל** משימה תואמת בכל bucket, לא top-N).
- **תיקון:** לא בוצע — תיעוד בלבד לפי בקשת המשתמש.
- **כיוון תיקון מוצע (מהדיווח + החלטת מוצר מוצעת בסוף הדיווח):** מבנה קצר — (1) דורש פעולה היום, (2) חסימות/תקיעות, (3) לידים חמים Top 5, (4) משימות P0/P1 בלבד, (5) סיכום שינויים קצר, (6) קישור/פקודה להרחבה. הגבלת מספר פריטים לכל סקשן; הסתרת פריטים ללא פעולה נדרשת; תקציר עליון ("היום יש X פעולות, Y לידים חמים, Z חסימות").
- **בדיקה:** אין עדיין. בדיקת קבלה מוצעת (מהדיווח): Daily Digest רגיל לא עובר אורך מוגדר מראש; כל סקשן מוגבל במספר פריטים; הפרדה בין "דורש פעולה" ל"מידע בלבד".
- **PR:** אין עדיין
- **Merged:** לא רלוונטי (לא תוקן)
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** 🟡 פתוח — שורש מאומת בקוד, החלטת עיצוב + תיקון לא בוצעו

### BUG-069 (BUG-DAILY-04) — Daily Digest מציג פירוט מלא של משימות שהושלמו במקום ספירה בלבד
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש — ראיה: סקשן "מה השתנה אתמול — משימות שהושלמו (5)" עם פירוט מלא מתחתיו
- **קבצים:** `daily_digest.py`
- **Severity:** Medium
- **שורש (מאומת בקוד):** `_yesterday_changes()`'s completed-tasks בלוק (`daily_digest.py:275-280`) — `if done_recs: lines.append(f"• *משימות שהושלמו ({len(done_recs)}):*"); for r in done_recs: ... lines.append(f"  – {f.get('כותרת המשימה','?')}")`. הכותרת אמנם מציגה ספירה (`len(done_recs)`) אבל **תחתיה מודפס פירוט מלא** של כותרת כל משימה — לא ספירה-בלבד כפי שהדיווח מצפה. אין flag/מצב `compact_daily_digest` בקוד.
- **תיקון:** לא בוצע — תיעוד בלבד לפי בקשת המשתמש.
- **כיוון תיקון מוצע (מהדיווח):** Daily Digest מציג completed tasks כספירה בלבד ("הושלמו אתמול 5 משימות"); פירוט מלא רק ב-Weekly Digest או לפי בקשת owner ("הרחב"); flag/מצב `compact_daily_digest=true`.
- **בדיקה:** אין עדיין. בדיקת קבלה מוצעת (מהדיווח): משימות completed לא מופיעות ברשימת "משימות היום"; בדוח יומי מוצגת רק ספירה; פירוט מופיע רק בדוח שבועי/לפי בקשה.
- **PR:** אין עדיין
- **Merged:** לא רלוונטי (לא תוקן)
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** 🟡 פתוח — שורש מאומת בקוד, תיקון לא בוצע

### BUG-070 (C90-VERIFY-01) — Individual approval targeting: תמיכה חלקית/לא-קיימת ב-3 מנגנוני אישור שונים, לא UX gap אחיד
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש — דרישת "individual approval targeting": כשיש כמה שורות ממתינות, המשתמש צריך לבחור שורה ספציפית חד-משמעית (למשל "כן 1"/"לא 2"/"אשר 3" או כפתורי אישור נפרדים). המשתמש ביקש **וריפיקציה בלבד, ללא תיקון** — לבדוק אם ה-backend כבר תומך בבחירה פרטנית ורק ה-UX חסר, או שה-backend עצמו לא יכול לייצג יותר מפעולה ממתינה אחת.
- **קבצים:** `app.py` (`_pending_approvals`, שורות 78-89, 586-601, 1283-1429), `core/action_gateway.py` (`route_confirmation_word`/`route_disambiguation`/`route_cancellation_word`, שורות 428-524), `event_bus.py` (`PendingActionsStore`, שורות 28-178), `daily_collector.py` (`format_collector_message`, שורה 150)
- **Severity:** Medium — לא חוסם פונקציונליות קיימת, אבל 3 מנגנוני אישור נפרדים בקוד עם רמות בשלות שונות לגמרי, ואחד מהם (`daily_collector`) מבטיח יכולת שלא קיימת בכלל.
- **ממצא (מאומת בקוד, לא הונח בלבד) — 3 מנגנונים נפרדים, לא אחד:**
  1. **`core/action_gateway.py` (tool-call approvals — הנתיב של C89/C90 lead capture):** ה-backend **כבר תומך** בכמה contracts חיים בו-זמנית, כל אחד עם `contract_id` ייחודי (`_ledger._store: dict[str, ActionContract]`, שורה 211). `route_confirmation_word()` (שורה 428): אם יש יותר מ-contract חי אחד, מציג רשימה ממוספרת ושומר `_disambiguation[canonical_user_id] = live` (שורות 439-446). `route_disambiguation()` (שורה 485): מפרסר `_parse_ordinal()` — ספרה בודדת ("1","2") או מילת סדר בעברית ("ראשונה"/"שנייה"/"שלישית"/"רביעית", שורות 469-474) — ומאשר **רק** את ה-contract שנבחר, דוחה את השאר (שורות 507-524). **זה בדיוק המנגנון המבוקש — אבל עם 3 פערים מאומתים:**
     - (א) מפרסר **רק מספר/סדר בודד** ("1", "ראשונה") — **לא** את הפורמט המשולב מהספק ("כן 1", "אשר 3"): `_parse_ordinal("כן 1")` → `"כן 1".isdigit()` = `False`, ולא ב-`_ORDINALS_HE` → מחזיר `None` → הטקסט לא מזוהה כלל כבחירה, נופל הלאה ל-Agent כהודעה רגילה.
     - (ב) **אין יכולת "דחה פריט ספציפי"** — `route_cancellation_word()` (שורה 450) דוחה **את כל ה-contracts החיים יחד** ("לא" = בטל הכל), אין דרך לדחות רק פריט מסוים (אין "לא 2" ב-backend כלל, לא רק ב-UX).
     - (ג) כל המנגנון (`route_disambiguation`/`route_confirmation_word`) מופעל ב-`app.py` רק דרך `core.action_gateway.action_gateway` שנקרא תמיד (שורה 1334) — פעיל גם כש-`FEATURE_ACTION_GATEWAY` כבוי, כל עוד יש contract חי אחד לפחות (BUG-056 fallback, שורה 1368-1375) — כלומר בפועל **חי בפרודקשן**, לא רק מאחורי flag. **מסקנה לסעיף זה: UX gap בלבד לחלק (א), gap אמיתי ב-backend לחלק (ב) — לא רק ניסוח.**
  2. **`app.py`'s `_pending_approvals` (router-level Handler.APPROVAL — הודעות מנותבות ברמת risk כללית, לא tool calls):** `_pending_approvals: dict[str, dict]` (שורה 81) — **מפתח יחיד לכל chat_id, לא רשימה**. `approval_response()` (שורה 590): `_pending_approvals[chat_id] = {...}` — הקצאת dict רגילה, **דורסת בשקט** כל פעולה ממתינה קודמת לאותו chat_id ללא אזהרה, ללא מיזוג, ללא שמירת ההיסטוריה. אין `action_id`/מזהה ייחודי כלל למנגנון הזה. אישור נבדק רק מול `_CONFIRM_WORDS`/`_CANCEL_WORDS` (מילים בודדות בדיוק, שורה 1296/1307) — לא תומך במספור בכלל, גם לא ברמת ה-backend. **מסקנה: זה gap ארכיטקטוני אמיתי, לא רק UX** — אין שום דרך לייצג יותר מפעולה ממתינה אחת per chat_id במנגנון הזה.
  3. **`daily_collector.py`'s `format_collector_message()` (שורה 150):** הטקסט "ענה במספר לאישור שמירה, או 'הכל בסדר' אם כבר טופל" **מבטיח** יכולת תגובה ממוספרת לפריטי המאסף היומי. גרפ מלא על הריפו (`grep -rn "מאסף יומי\|daily_collector"`) לא מוצא **שום handler** — לא ב-`app.py`, לא ב-callback handlers, לא במקום אחר — שמפרסר תגובה ממוספרת מול רשימת הפריטים של המאסף היומי. **מסקנה: gap מלא — אין שום תשתית backend, לא רק חסר parsing; הטקסט אספירציוני בלבד ומטעה משתמשים.**
- **תיקון (חלק 2 מתוך 3 בלבד):** ✅ בוצע ל-gap (2) — `app.py`'s `_pending_approvals` שונה מ-`dict[str, dict]` (רשומה יחידה) ל-`dict[str, dict[str, dict]]` (`chat_id → {approval_id → entry}`), כל entry עם `display_index` (1,2,3...). פונקציות חדשות: `_add_pending_approval()` (מוסיף בלי לדרוס), `_resolve_pending_reply()` (מפענח מספר בטקסט מול display_index, או fallback ל-ממתין יחיד לתאימות לאחור), `_pop_pending_approval()` (מסיר entry ספציפי בלבד), `_pending_clarification_message()` (רשימה ממוספרת כש-2+ ממתינים ואין מספר בתשובה). `run_agent()`'s "2.5 Pending Approval Gate" עודכן לפרש "כן"/"לא" בלי מספר (ממתין יחיד, תאימות לאחור), "כן 2"/"לא 2"/מספר בודד (עם 2+ ממתינים) כבחירה ספציפית, ותשובה דו-משמעית (2+ ממתינים, בלי מספר תואם) כהצגת הרשימה מחדש בלי לנחש. **תיקון בטיחות שנוסף בביקורת קוד (מעבר לפאץ' שסופק):** הענף "מספר בודד = אישור" הוגבל ל-`len(bucket) > 1` בלבד — הפאץ' המקורי טיפל בכל מספר בודד (למשל "1") כאישור מרומז גם כשיש **ממתין יחיד בלבד**, מה שהיה מבצע בפועל פעולה ממתינה (למשל "שלח מייל ללקוח") בתגובה למספר לא-קשור לגמרי (למשל תשובה לשאלה "כמה יחידות?") — אומת ידנית לפני התיקון (`resolve_reply(chat, "1")` → `("confirm", {...})` כשיש ממתין יחיד ולא קשור), ותוקן לפני commit. gaps (1) ו-(3) (ActionGateway reject-by-index + combined-wording, ו-daily_collector) **נשארים פתוחים**, לא נגעו בהם.
- **בדיקה:** `test_bug070_pending_approval_multi.py` (חדש, 9/9) — קורא ישירות לפונקציות האמיתיות (`app._add_pending_approval`/`_resolve_pending_reply`/`_pop_pending_approval`), לא reimplementation: שני ממתינים לא דורסים זה את זה; "כן 2"/"לא 2" מכוונים לפריט הנכון בלי לגעת באחרים; תשובה דו-משמעית לא מנחשת; "כן"/"לא" בלי מספר עדיין עובד עם ממתין יחיד (תאימות לאחור); **מספר בודד לא-קשור עם ממתין יחיד לא מאשר בטעות** (regression guard לתיקון הבטיחות); מספר בודד עם 2+ ממתינים כן מכוון בהצלחה; מספר לא-תואם לא נוגע בכלום; הודעת ההבהרה מציגה את כל הפריטים ממוספרים. אפס רגרסיה: `test_ll13_double_execution.py` (4/4), `test_approval_concurrency.py` (14/14), `test_a32_enforcement.py` (6/6), `test_c53a.py` (50/50), `test_bug066_...`/`test_bug067_...` (8/8, 3/3), `smoke_tests.py` — הכל ירוק.
- **PR:** #234
- **Merged:** כן (`db37225`, merge commit `ef2385b`) — מאומת `git log origin/main --oneline`
- **Deployed:** לא מאומת עדיין
- **Verified בפרודקשן:** לא עדיין
- **סטטוס:** ✅ מוזג ל-main (gap 2/3 בלבד) — ממתין ל-production verification. gaps (1) ו-(3) נשארים 🔴 פתוחים.

- **עדכון 05/07/2026 — gap (1) נסגר (combined wording + reject-by-index):** `core/action_gateway.py` מקבל `_parse_combined()` (מזהה "<מילת אישור/ביטול> <סדרתי>", למשל "כן 1"/"אשר 3"/"מאשר 2"/"לא 2"/"בטל 1") ו-`route_combined_word()` — מיירט לפני ש-`route_disambiguation()`/`_CONFIRM_WORDS`/`_CANCEL_WORDS` מספיקים לרוץ, פועל ישירות מול `find_live_contracts()` (לא תלוי בקיום disambiguation state קודם, ולא בדגל `FEATURE_ACTION_GATEWAY` — אותו עיקרון כמו BUG-056). אישור ממוקד ("כן 1") סוגר siblings אחרים (כמו `route_disambiguation`, §21); דחייה ממוקדת ("לא 2") **חדש** — דוחה רק את הפריט שנבחר, משאיר את שאר הממתינים ללא שינוי (לפני התיקון: `route_cancellation_word()` דחה תמיד את כל ה-contracts יחד — לא הייתה כל דרך backend לדחות פריט בודד, לא רק חסר ניסוח). מחווט ב-`app.py`'s §2.55, ממוקם *לפני* בדיקת ה-disambiguation הרגילה (§4) — קריטי כי אחרת `route_disambiguation()` היה מנקה בטעות `_disambiguation` state על טקסט משולב שהוא לא מזהה (`_parse_ordinal("כן 1")` מחזיר `None`).
  - **בדיקה:** `test_bug070_combined_wording.py` (חדש, 27/27) — פענוח `_parse_combined` (כולל מילות סדר עבריות, טקסט לא-תואם, מספר בודד ללא מילת-מפתח), אישור ממוקד מבצע בדיוק את ה-contract הנבחר וסוגר siblings, דחייה ממוקדת לא נוגעת ב-siblings ולא מבצעת כלום, טווח לא-תקין מוחזר כאזהרה, ממתין יחיד (לא רק 2+) מטופל נכון. אפס רגרסיה: `test_action_gateway.py` (37/37), `test_bug070_pending_approval_multi.py` (9/9), `smoke_tests.py`, `test_integration.py` (4/4), `core/router/test_router.py` (44/44), `test_c53a.py` (50/50), `test_approval_concurrency.py` (14/14), `test_bug066_...`/`test_bug067_...`/`test_c83_...`/`test_c86_...` — כולם ירוקים.
  - **gap (3) (daily_collector) — לא נבנה backend, תוקן רק ניסוח מטעה, לפי החלטת המשתמש המפורשת:** `daily_collector.py`'s `format_collector_message()` הבטיח "ענה במספר לאישור שמירה" בלי שום handler שמפרסר תגובה כזו (אין state/contract שמייצג את פריטי המאסף). הוחלף לניסוח שלא מבטיח יכולת שלא קיימת ("כדי לשמור פריט — עדכן אותו ידנית או שלח לי אותו כליד/משימה בנפרד"). לא נבנה backend/state מלא לפריטי המאסף היומי בסבב הזה — דורש להגדיר קודם מה "שמירה" אומר לכל קטגוריה (cashflow/crm/calendar/task) ואיך זה נכתב ל-Airtable. gap (3) **נשאר פתוח**, רק הטקסט המטעה תוקן (אותו pattern בדיוק כמו התיקון המקורי של BUG-058).
  - **BUG-058's Tier-2 batch-confirm resolver — גם נשאר פתוח במכוון, לא נבנה בסבב זה** (לפי החלטת המשתמש המפורשת) — עדיין דורש עיצוב precedence מול Tier-1 ActionGateway contract לפני קוד, בדיוק כפי שתועד ב-03/07/2026 (ראה BUG-058 למעלה).
  - **PR:** אותו ענף (`claude/bug-070-058-gaps-1i1spl`) — commit נפרד ל-gap(1)+gap(3) מעבר ל-#234 המקורי.
  - **Merged:** ממתין ל-push/PR של סבב זה.
  - **סטטוס (עדכון):** gap (1) — combined wording + reject-by-index — ✅ קוד הושלם, בדיקות עברו, ממתין ל-merge+production verification. gap (2) כבר נסגר קודם (#234). gap (3) — 🟡 רק ניסוח תוקן, backend עדיין לא קיים, נשאר פתוח במכוון.
  - **עדכון אימות 09/07/2026 — כיסוי מול BUG-086/087:** ✅ סגור כטקסט מטעה, לא דרך anti-hallucination. `daily_collector` אינו Agent tool-loop: `scheduler.py` מפעיל `_job_daily_collector()` ומשם `send_daily_collector()` (`scheduler.py:73-90`, `scheduler.py:805-810`), ו-`daily_collector.py` בונה הודעה קבועה ב-`format_collector_message()` ושולח אותה ישירות עם `bot.send_message()` (`daily_collector.py:130-153`, `daily_collector.py:160-190`). לכן BUG-086/087 לא יכולים ולא צריכים לתפוס את ההבטחה הישנה. ההוכחה לסגירה היא שהטקסט הנוכחי כבר לא אומר "ענה במספר לאישור שמירה", אלא "כדי לשמור פריט — עדכן אותו ידנית או שלח לי אותו כליד/משימה בנפרד" (`daily_collector.py:150-152`). ה-backend/state לפריטי המאסף היומי נשאר functional gap נפרד ומכוון.

- **תיקון-טעות שתועדה בסבב קודם (05/07/2026, אחרי בדיקה חיה):** ניתוח קודם (בשיחה, לא הגיע ל-commit) טען ש-`route_disambiguation()` הוא "dead code" בפועל, כי הצרכן שלו (§4, `app.py`) עטוף ב-`FEATURE_ACTION_GATEWAY` בעוד היצרן שלו (`route_confirmation_word()`, populates `self._disambiguation`) רץ ללא תלות בדגל (BUG-056). **המשתמש בדק חי בטלגרם והפריך את הטענה:** כששולחים קודם מילת אישור בודדת ("כן"/"מאשר") ומחכים לרשימה הממוספרת, ואז שולחים מספר/סדר בודד בנפרד — הבחירה **כן** נפתרת נכון. המסקנה המתוקנת: אין כאן באג — הייתה ציפייה שגויה לפרוטוקול (ניסיון לשלוח מספר ישיר בלי לשלוח קודם מילת אישור בודדת שמפעילה את `route_confirmation_word()` ומאכלסת את `_disambiguation`). כלומר: ב-סביבה שנבדקה, `FEATURE_ACTION_GATEWAY` בפועל **פעיל** (אחרת גם הפרוטוקול הדו-שלבי לא היה עובד) — לא מאומת דרך קוד סטטי (ברירת המחדל בקוד היא כבוי, `feature_flags.py:116-118`), אלא רק דרך תצפית חיה. אין תיקון קוד נדרש לממצא הזה.
- **נקודה לתיעוד עתידי (לא באג, לא תוקן):** יש חוסר-אחידות UX אמיתי בין שני מסלולי disambiguation בבוט — מסלול ה-file-upload/ActionGateway דורש פרוטוקול דו-שלבי ("כן"/"מאשר" קודם, ואז מספר בנפרד), בעוד `daily_collector.py`'s `format_collector_message()` (gap 3 למעלה) מבטיח בטקסט יכולת תגובה ישירה במספר בודד ("ענה במספר") שלא קיימת כלל. שני הפרוטוקולים שונים זה מזה ואף אחד מהם לא תומך ב-"כן/מאשר + מספר" משולב באותה הודעה (gap 1 למעלה). ראוי לשקול בעתיד איחוד לחוויה אחת עקבית בין שני המסלולים, כחלק מטיפול בgaps 1 ו-3.

### BUG-071 — WhatsApp file upload עוקף לגמרי את C90 Structured File Capture (ואת כל טיפול media בכלל)
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש — תצפית חיה: קובץ CSV/XLSX שהועלה דרך WhatsApp לא נכנס ל-pipeline של C90 row-level ingress; channel=whatsapp, handler=agent, tool=`read_drive_file`/`search_drive`, result=file not found ב-Drive; אין row parsing, אין ActionGateway row approvals.
- **קבצים:** `app.py` (`_webhook_whatsapp_impl`, שורות 2398-2470; Meta WhatsApp Cloud API handler, משורה 2477; `_is_structured_file`/`_process_structured_file_upload`, שורות 1960-2036; `_handle_telegram_media`, שורה 2039)
- **Severity:** Medium — C90 לא "נשבר" ב-Telegram (עדיין באמצע אימות שם ממילא), אבל התכונה חסרה לגמרי בערוץ WhatsApp; לא רגרסיה, gap שמעולם לא נסגר.
- **שורש (מאומת בקוד):** `_is_structured_file()`/`_process_structured_file_upload()` (C90) מחוברים **אך ורק** דרך `_handle_telegram_media()` (שורה 2381: `_handle_telegram_media(update.message)`, קרוא רק מתוך ה-Telegram document callback). גרפ מלא על `_webhook_whatsapp_impl()` (Twilio, שורות 2398-2470) מראה שהיא קוראת **רק** `request.values.get("Body", "")` — אין קריאה בשום מקום ל-`NumMedia`/`MediaUrl0`/`MediaContentType0` (שדות ה-attachment של Twilio WhatsApp). Meta WhatsApp Cloud API handler (משורה 2477) גם הוא **ללא כל טיפול media/attachment** (מאומת: `grep -n "media\|Media\|document\|attachment\|MediaUrl\|NumMedia"` על הבלוק שלו — אפס hits). המסקנה: זה לא "C90 לא מחובר ל-WhatsApp" בלבד — **אין שום טיפול media/קובץ בשום ערוץ WhatsApp כרגע** (לא רק CSV/XLSX — גם תמונה/קול/מסמך כלשהו). קובץ שמגיע ב-WhatsApp פשוט מתעלם מה-attachment ומעביר את `Body` (ריק/לא-קשור) ל-`run_agent()` כטקסט רגיל — ה-Agent, ללא הקשר לקובץ אמיתי, מנחש ומנסה `read_drive_file`/`search_drive` (הכלים היחידים שיש לו לחיפוש "קובץ" בכלל), ומקבל "not found" כי הקובץ מעולם לא הגיע ל-Drive או לשום מקום אחר בשרת.
- **תיקון:** ✅ בוצע בעלות GitHub issue #235 (BUG-071)
  * `providers/whatsapp_media_adapter.py` — Twilio WhatsApp media extraction (NumMedia, MediaUrl0, MediaContentType0 → בהורדה מ-signed URL; אין צורך ב-Twilio Basic Auth, Twilio מספקת URL מחתומים פומיים)
  * `providers/meta_whatsapp_media_adapter.py` — Meta Cloud API media extraction (image/video/audio/document; media_id → URL fetch דרך Meta Media API עם access_token)
  * `app.py._webhook_whatsapp_impl()` (שורות 2419-2467) — Twilio media handling אחרי dedup, לפני furniture funnel
  * `app.py._normalize_meta_payload()` (שורות 222-256) — Meta media metadata extraction
  * `app.py.webhook_meta_whatsapp()` (שורות 2582-2642) — Meta media handling אחרי dedup, לפני outbound gate
  * שניהם מנתבים דרך `media_handler.handle_voice_note()` (audio) או `handle_file_upload()` (files/images/video)
- **Commit:** `4f64666` ("BUG-071 fix: Unified WhatsApp media support (Twilio + Meta Cloud API)")
- **Branch:** `claude/ic-01b-ambiguous-prefix-routing-zp109k`
- **PR:** זמין לפתיחה עם בקשת המשתמש
- **Merged:** לא עדיין (branch פתוח, ממתין לאישור)
- **Tested:** smoke_tests.py ✅ | test_bug070_pending_approval_multi.py ✅ | test_whatsapp_media.py ✅ (6 tests)
- **Deployed:** לא עדיין
- **Verified בפרודקשן:** לא עדיין (ממתין למיזוג + Render deploy)
- **סטטוס:** 🟡 תוקן בקוד — ממתין ל-merge ו-verification בפרודקשן.

### BUG-072 — לוגים קיימים חושפים sender ID/מספר טלפון גולמי (לא C94) — ✅ תוקן 06/07/2026
- **תאריך:** 05/07/2026 (דווח) → 06/07/2026 (תוקן)
- **דווח על ידי:** המשתמש — נצפה אגב בדיקת production smoke ל-C94 (Telegram+WhatsApp inbound). לא קשור למנגנון הסניטיזציה של C94 עצמו (`type(exc).__name__` בלבד, ראה C94 Stage ב/ג) — זה pre-existing gap בנתיבי לוג אחרים, ישנים יותר.
- **מאומת בקוד (grep, לא רק נטען):** `app.py` — `logger.info(f"[APPROVAL] ... | saved for {chat_id}")` (שורה 677), `logger.info(f"[Approval] ✅ sent to owner {owner_chat_id} | {action_id}")` (844), `logger.info(f"[Approval] queued {action_id} | {tool_name} | user={user_chat_id}")` (853), `logger.warning(f"[C60] set_last_tool_result failed for {chat_id}: {e}")` (900), `logger.debug(f"[Typing] failed for {chat_id}: {e}")` (1241, 1248), `logger.info(f"[PendingApproval] 🚫 cancelled by {chat_id}")` (1477), `logger.warning(f"[Agent] Claude transient error ... for {chat_id}")` (1980), `logger.error(f"[Agent] Timeout for {chat_id}")` (1995). `chat_id`/`user_chat_id`/`owner_chat_id` הם ה-external_id הגולמי (מספר טלפון ל-WhatsApp, user_id ל-Telegram) — לא memory_key/hash.
- **Severity:** Low-Medium — לוגים תפעוליים פנימיים, לא user-facing, אבל אם לוגים אלו מגיעים ל-log aggregator חיצוני/נצפים ע"י מי שלא "צריך לדעת", זו חשיפת PII אמיתית.
- **תיקון (✅ בוצע 06/07/2026):** נוסף `_sanitize_id()` ב-`app.py` — `hashlib.sha256(str(raw_id).encode()).hexdigest()[:8]` (fingerprint קצר, לא הפיך, דטרמיניסטי — אותו קלט תמיד מייצר את אותו fingerprint, כך שאפשר עדיין לקשר שורות לוג של אותו משתמש בלי לחשוף את המזהה עצמו). כל 19 מופעי הלוגינג הגולמי שנמצאו ב-`app.py` (8 מהממצא המקורי + 11 נוספים שנתפסו בסריקה מלאה: `chat_id`/`user_chat_id`/`owner_chat_id`/`sender_user_id`/`identity.user_id`/`approver_identity.user_id` בקבצי approval/media/agent-loop/cost-watchdog) עודכנו לעטוף את הערך ב-`_sanitize_id(...)` לפני הלוג. `role`/`identity.role` **לא** נחשב PII ונשאר גלוי (נחוץ לדיבוג הרשאות).
- **בדיקה:** `test_bug072_log_sanitization.py` (חדש, 7/7) — בדיקת יחידה ל-`_sanitize_id()` (דטרמיניסטי, לא הפיך, מטפל ב-empty/None) + guard סטטי (grep-based, כמו `smoke_tests.py`) שסורק את `app.py` בפועל ומוודא שאין אף `logger.*` עם `{chat_id}`/`{user_chat_id}`/וכו' גולמי שלא עטוף — regression guard נגד הישנות התבנית. אפס רגרסיה: כל 50 קבצי `test_*.py` בריפו ירוקים (`test_document_converter.py` נכשל מסיבה לא-קשורה — חבילת `markdown` חסרה בסביבת ה-sandbox, לא נגעתי במודול `document_converter`).
- **Merged:** ✅ כן — `main` `e1436e9` (Merge pull request #246), commit `54961f1`. מאומת: `git merge-base --is-ancestor 54961f1 origin/main` + `git show origin/main:app.py | grep -c "_sanitize_id("` → 21.
- **סטטוס:** ✅ תוקן ומוזג ל-main — **לא** מאומת עדיין ב-production/Render (deploy hash מול origin/main לא נבדק).

### BUG-073 (ROADMAP-DOC-DRIFT-01) — כמה "חסמים"/PARTIAL ב-ROADMAP.md היו doc drift, לא חסם קוד אמיתי
- **תאריך:** 05/07/2026
- **דווח על ידי:** המשתמש — תצפית שחלק מהחסמים ב-ROADMAP נראים כמו "בלגן תיעודי, לא בהכרח בלגן בקוד".
- **Severity:** Low — תיעוד בלבד, אין קוד שגוי, אבל מטעה לגבי מה באמת חסום.
- **ממצא (מאומת מול הקוד/הקובץ עצמו, לא רק נטען):**
  1. **C91/C92 (Voice/Email capture)** סומנו "חסום על C89" — אבל C89 כבר סגור (`✅ CLOSED/VERIFIED`, 05/07/2026, ראה N13 למעלה) לפי החלטת הבעלים. C91/C92 לא באמת חסומים יותר — פשוט לא התחילו.
  2. **F10 (Lead Memory Wire-up)** תואר כ"בנוי ובדוק, תלוי ב-N02" — אבל N02/N03 (סעיף נפרד באותו קובץ) כבר מיישמים בדיוק את זה: `lead_capture.py` קורא ל-`lead_memory.update()` הן ב-create והן אחרי scoring. F10 היה כפילות תיעודית ל-N02/N03, לא פריט עבודה נפרד.
  3. **F11 (Followup Engine Full Activation)** תואר כ"תשתית קיימת, תלוי ב-N04 MVP" — אבל N04 (MVP) ו-N05-B (טיוטת אישור בטלגרם) כבר מיושמים ומחוברים. F11 כבר לא MVP חסר, לכל היותר הרחבה עתידית אופציונלית.
  4. **בלוק "Audit note - 2026-06-14"** (סוף הקובץ) טען N02-N05 "PARTIAL" — אבל זה תיעוד מ-14/06/2026, לפני שסעיפי N02/N03/N04/N05/N05-B (כולם ✅ מיושם) נבנו. נשאר בקובץ בלי סימון "היסטורי", וסתר ישירות את הסטטוס העדכני יותר באותו מסמך.
  5. **F12/F13** לא היו מסומנים במפורש שהם חוסמים *רק* multi-tenant/SaaS provider-abstraction עתידי — קריאה שטחית הייתה עלולה לפרש אותם כחסם על עבודה שוטפת (לידים/digest/C89-C94/Decision Hub), מה שלא נכון.
- **תיקון:** ✅ בוצע (docs-only, `ROADMAP.md` בלבד) — (1) C91/C92 עודכנו ל"לא חסום על C89" עם הפניה ל-N13; C93 נשאר חסום אך במפורש על צבירת `AgentObservation` data, לא על C89. (2) F09/F10/F11 עודכנו לשקף שה-N-תלויות שלהם כבר מומשו; F10 סומן כהפניה היסטורית ל-N02/N03 (לא סעיף עבודה עצמאי). (3) טבלת "פערים ידועים" עודכנה בהתאם — שורת F10 הוסרה (כפולה), F09/F11 קיבלו ניסוח מעודכן. (4) F12/F13 קיבלו הבהרה מפורשת שהם חוסמים רק multi-tenant/provider-abstraction עתידי. (5) בלוק ה-Audit הישן מ-14/06 סומן במפורש "היסטורי — לפני N02-N05 המיושמים למעלה", לא נמחק (evidence), עם הפניה לסטטוס הנוכחי. Decision Hub (BUG-DH-03/04) ו-N05-C (Meta outbound) **לא שונו** — אלו חסמים אמיתיים שנשארים בתוקף.
- **בדיקה:** `smoke_tests.py` — pass (docs-only, sanity check). אין שינוי קוד.
- **PR:** ראה branch `claude/new-session-bkfd11` (אותו ענף כמו PR #244, docs-only).
- **Merged:** ממתין ל-push/PR של סבב זה.
- **סטטוס:** ✅ תוקן (תיעוד בלבד) — ממתין ל-merge.

### BUG-074 — ActionGateway free-text confirmation מאפשר אישור עצמי ל-tool הדורש requires_approval — ✅ תוקן 06/07/2026
- **תאריך:** 06/07/2026
- **דווח על ידי:** ביקורת אבטחה (`app.py`/`tma_api.py`/`tools/`) — ראה גם GitHub issue המקורי (מכונה "BUG-073" בטיקט; ממוספר כאן BUG-074 כדי לא להתנגש עם BUG-073 (ROADMAP-DOC-DRIFT-01) שכבר תפוס למעלה).
- **קבצים:** `core/action_gateway.py` (`route_confirmation_word` שורה 428, `route_disambiguation` שורה 514, `route_combined_word` שורה 560, `approve` שורה 674), `app.py` (4 call sites בשורות ~1503/1518/1560/1571).
- **Severity:** High בקוד, אך **דורם בפועל תחת ברירת המחדל** — `FEATURE_ACTION_GATEWAY` כבוי כברירת מחדל, אבל מסלול Tier-1 lead-preview (`core/lead_candidate_handler.py._propose_lead_write()`, BUG-056) קורא ל-`route_confirmation_word()` **ללא תלות בדגל** — כלומר הבאג היה **חי בפרודקשן היום** לפחות עבור אישור-עצמי של כתיבת/עדכון ליד (`airtable_add`/`airtable_update`) ע"י owner/partner/manager/employee (כל role שמורשה ע"י `tool_registry.py` להפעיל את הכלי, גם אם הכלי מסומן `requires_approval=True`).
- **ממצא (מאומת בקוד):** `route_confirmation_word()`/`route_disambiguation()`/`route_combined_word()` תמיד קוראות ל-`approve(contract_id, approver=canonical_user_id)` כאשר `canonical_user_id` הוא **בדיוק** הזהות ששולחת את מילת האישור עכשיו (כי `find_live_contracts(canonical_user_id)` מסנן contracts ששייכים לה בלבד) — כלומר זה תמיד "אישור עצמי". הבדיקה היחידה שהייתה קיימת ב-`approve()` (`contract.canonical_user_id != approver and not approver.startswith("owner")`) הייתה **log בלבד** — לא חסמה כלום. משמעות: כל role שמורשה (לפי `tool_registry.py`) להפעיל tool עם `requires_approval=True` (כולל `employee` על `airtable_add`) יכול היה לאשר את הבקשה של עצמו ע"י מילה חופשית ("כן"/"מאשר"), בלי אישור owner אמיתי כלל.
- **תיקון:** `approve()` קיבל פרמטר חדש `approver_role: str` והוא **שער האכיפה היחיד** — פונקציית עזר חדשה `_has_approval_authority(role)` (owner או "actions.approve" בלבד) נבדקת **תמיד** לפני dispatch; חוסר סמכות → `⛔ הפעולה דורשת אישור בעלים.`, ה-contract **נשאר pending** (לא נצרך), לא רק warning. שלוש הפונקציות `route_confirmation_word`/`route_disambiguation`/`route_combined_word` מעבירות את הפרמטר החדש הלאה. `app.py`'s 4 נקודות הקריאה מעבירות `approver_role=identity.role` (הזהות המאומתת בפועל של מי ששולח את ההודעה עכשיו, לא נגזר מ-`canonical_user_id`). זרימת כפתור הטלגרם (`_handle_approval_callback_impl`) **לא שונתה** — כבר הייתה נכונה (בודקת `approver_identity.is_owner or approver_identity.can("actions.approve")` לפני dispatch).
- **תופעת-לוואי שהועלתה כאן (06/07/2026) — נפתרה ע"י החלטת מוצר, ראה BUG-076 למטה:** אחרי התיקון הזה בלבד, זרימת ה-Tier-1 lead-preview (`_propose_lead_write`) לא נתנה דרך ל-manager/partner/employee לאשר בעצמם כתיבת/עדכון ליד דרך "כן" — רק owner יכול היה. הבעלים החליט (06/07/2026): lead capture הוא low-risk ולא אמור לדרוש אישור owner בכלל — זה לא "אישור" (approval) אלא "אישוש" (confirmation) שהמערכת הבינה נכון את הטיוטה. הפתרון (BUG-076): מדיניות `self_confirm` נפרדת מ-`approval`, לא owner-notification.
- **בדיקה:** `test_bug074_approval_authority.py` (חדש, 22/22) — employee/manager לא יכולים לאשר בעצמם tool עם `requires_approval=True` (לא dispatch, contract נשאר pending), owner יכול לאשר את אותו contract, shadow-mode (`FEATURE_ACTION_GATEWAY=false`) לא משתנה (propose_action עדיין לא חוסם), parity מלאה בין נוסחת ה-authorization של זרימת הכפתור לזו של `_has_approval_authority()` על כל role במערכת, guard סטטי ש-`app.py` עדיין מכיל את הבדיקה המקורית של זרימת הכפתור. אפס רגרסיה — כל 7 קבצי הטסט הקיימים שקראו ל-`approve()`/`route_confirmation_word()`/`route_disambiguation()`/`route_combined_word()` עודכנו להעביר `approver_role="owner"` (או `identity.role` כש-identity כבר בסקופ) ועדיין ירוקים במלואם: `test_action_gateway.py` (37/37), `test_stage_b_full_suite.py` (124/124), `test_stage_b_verification.py` (29/29), `test_approval_gate_registry.py` (31/31), `test_bug070_combined_wording.py` (27/27), `test_c89_preview_confirmation.py` (9/9), `test_tier2_silent_preview.py` (4/4). כל 50 קבצי `test_*.py` בריפו הורצו — ירוקים חוץ מ-`test_document_converter.py` (חבילת `markdown` חסרה בסביבה, לא קשור).
- **Merged:** ✅ כן — `main` `e1436e9` (Merge pull request #246), commit `54961f1`. מאומת: `git merge-base --is-ancestor 54961f1 origin/main` + `git show origin/main:core/action_gateway.py | grep -c approver_role` (>0).
- **סטטוס:** ✅ תוקן ומוזג ל-main — **לא** מאומת עדיין ב-production/Render.

### BUG-075 — `/api/tma/upload` יש authentication אבל אין authorization לפי role — ✅ תוקן 06/07/2026
- **תאריך:** 06/07/2026
- **דווח על ידי:** ביקורת אבטחה (`app.py`/`tma_api.py`/`tools/`) — מכונה "BUG-074" בטיקט המקורי; ממוספר כאן BUG-075 בהמשך ל-BUG-074 למעלה.
- **קבצים:** `tma_api.py` (`tma_upload`, שורה 3033).
- **Severity:** Medium — דורם: `FEATURE_MEDIA_UPLOAD` כבוי כברירת מחדל (מחזיר `coming_soon` תמיד), אבל ברגע שיופעל, כל identity מאומתת (כולל `lead`/`guest`/`readonly`) תוכל להעלות קבצים — בניגוד לכל endpoint כתיבה אחר ב-`tma_api.py` שבודק role.
- **ממצא (מאומת בקוד):** בניגוד לכל שאר endpoints הכתיבה ב-`tma_api.py` (כולם בודקים `identity.is_owner` או `identity.role in {OWNER, MANAGER, PARTNER}`), `tma_upload()` היה מסתמך אך ורק על `@require_tma_auth` (מוודא HMAC initData תקין — כלומר *מי* זה, לא *מה מותר לו*) — ללא שום בדיקת role.
- **תיקון:** נוספה בדיקת role זהה למדיניות הקיימת ב-endpoints אחרים: `if identity.role not in {Role.OWNER, Role.MANAGER, Role.PARTNER}: return jsonify({"error": "forbidden"}), 403` — לפני גישה ל-`request.files`. בדיקת ה-flag (`FEATURE_MEDIA_UPLOAD`) נשארה **לפני** בדיקת ה-role (ללא שינוי בהתנהגות כש-flag כבוי).
- **בדיקה:** `test_bug075_tma_upload_role_gate.py` (חדש, 17/17) — flag כבוי מחזיר `coming_soon` לכל role (ללא שינוי); flag דלוק: guest/lead/readonly/employee נחסמים ב-403 עם body בטוח; owner/manager/partner עוברים את שער ה-role (מגיעים ללוגיקת ההעלאה עצמה — לא לצינור Drive/Airtable המלא, שאינו קשור לתיקון ההרשאה הזה). נקרא ישירות דרך `tma_upload.__wrapped__` (מעקף את בדיקת ה-HMAC של `@require_tma_auth`, שלא שונתה ואינה נבדקת כאן) בתוך `Flask.test_request_context`.
- **Merged:** ✅ כן — `main` `e1436e9` (Merge pull request #246), commit `54961f1`. מאומת: `git merge-base --is-ancestor 54961f1 origin/main` + `git show origin/main:tma_api.py` מכיל את בדיקת ה-role (שורה 3042-3044).
- **סטטוס:** ✅ תוקן ומוזג ל-main — **לא** מאומת עדיין ב-production/Render.

### BUG-076 — הפרדת "confirmation" מ-"approval": lead capture בטוח לא צריך אישור owner — ✅ תוקן 06/07/2026
- **תאריך:** 06/07/2026
- **דווח על ידי:** החלטת מוצר של הבעלים, בתגובה לתופעת-הלוואי שתועדה ב-BUG-074 למעלה — lead capture הוא low-risk ולא אמור לדרוש אישור owner.
- **קבצים:** `core/action_gateway.py` (`classify_approval_policy()`, `_lead_safe_fields()`, `_is_internal_role()`, `ActionContract.approval_policy`, `propose_action()`, `approve()`).
- **החלטת מדיניות (לא קוד, נקבעה ע"י הבעלים):** שני מושגים נפרדים — **"confirmation"**: המבקש מאשש שהמערכת הבינה נכון את הטיוטה/preview (סיכון נמוך, self-confirm מותר). **"approval"**: זהות מורשית (owner/"actions.approve") חייבת להסמיך פעולה רגישה (הכלל הקשיח של BUG-074, ללא שינוי). `approve()` **נשאר** שער האכיפה המרכזי לכל הפעולות — ה-carve-out הוא צר ומחושב מרכזית, לא "החלשה" גורפת.
- **תיקון:** `ActionContract` קיבל שדה חדש `approval_policy` (`"approval"` ברירת מחדל, או `"self_confirm"`). `classify_approval_policy(tool_name, tool_inputs)` מחושבת ב-`propose_action()` מתוך ה-payload המנורמל בפועל (לא נסמך על טענת הקורא) ומחזירה `self_confirm` **רק** עבור: `tool_name` ∈ {`airtable_add`, `airtable_update`}, טבלה=`Leads`, ושדות שכולם בתוך allowlist בטוח — `airtable_add` (יצירה): `Name/phone/channel/memory_key/domain/source/status/summary/Score/sender_id` (תואם בדיוק את מה ש-`_write_one_lead()`/`_propose_lead_write()` כבר כותבים ל-ליד חדש — קביעת מצב התחלתי, לא "escalation"). `airtable_update` (עדכון ליד קיים): allowlist **צר בהרבה** — רק `phone/summary/domain` (תואם בדיוק את `_propose_lead_write()`), **בלי** status/score/tier/Owner/Next Action — כל אלו escalation/assignment ונשארים `approval`. כל tool/table/field שלא ברשימה → `approval` (fail-closed). `approve()`: אם `contract.approval_policy == "self_confirm"` — מאושר רק אם המאשר הוא **בדיוק** אותה זהות שביקשה (`approver == contract.canonical_user_id`) **וגם** מחזיק role פנימי (owner/partner/manager/employee) — לא "כל אחד". אחרת (כולל כל מקרה אחר) — הכלל הקשיח של BUG-074 (owner/"actions.approve" בלבד) נשאר בעינה ללא שינוי.
- **תוצאה:** manager/partner/employee יכולים כעת לאשש בעצמם ("כן") טיוטת יצירת/עדכון-בטוח של ליד — בדיוק כמו שכתיבת ליד אוטומטית (`FEATURE_AUTO_CAPTURE`) כבר עושה היום ללא אישור נפרד. כל פעולה אחרת (מחיקה, שדות מוגנים, סטטוס/שיוך, דילס/פיננסים/יוצא/bulk) עדיין דורשת owner/"actions.approve" בדיוק כמו ב-BUG-074.
- **בדיקה:** `test_bug076_lead_confirmation_policy.py` (חדש, 32/32) — matrix של `classify_approval_policy()` (יצירה בטוחה→self_confirm, עדכון בטוח→self_confirm, עדכון סטטוס/Owner/Score→approval, טבלה אחרת→approval, כלי לא-ליד→approval, כלי פיננסי→approval, fields ריק/חסר→approval fail-closed, "airtable_delete" היפותטי על Leads→approval כי הכלי עצמו לא ב-allowlist); employee מאשש בעצמו יצירת ליד בטוחה (1); employee לא יכול לאשש בעצמו פעולה לא-ליד (2); employee לא יכול לאשש בעצמו עדכון סטטוס/שדה מוגן (3, כולל אימות שה-contract מסווג `approval` ולא `self_confirm`); owner עדיין יכול לאשר פעולת approval אמיתית אחרי הכל (4); manager אחר (לא המבקש המקורי) לא יכול "לאשש" preview של מישהו אחר — self_confirm דורש בדיוק אותה זהות, לא כל role פנימי (5). אפס רגרסיה: `test_bug074_approval_authority.py` עודכן לתרחיש שאינו lead-capture (טבלת "Deals" במקום "Leads") כדי להמשיך לבדוק את הכלל הכללי, נשאר 22/22 ירוק. כל 50 קבצי `test_*.py` בריפו ירוקים חוץ מ-`test_document_converter.py` (לא קשור).
- **Merged:** ✅ כן — `main` `e1436e9` (Merge pull request #246), commit `bb4b9ca`. מאומת: `git merge-base --is-ancestor bb4b9ca origin/main` + `git show origin/main:core/action_gateway.py | grep -c "classify_approval_policy\|approval_policy"` → 15.
- **סטטוס:** ✅ תוקן ומוזג ל-main — **לא** מאומת עדיין ב-production/Render.

### BUG-077 — `propose_action()` סומך עיוורת על `requires_approval` שמצהיר הקורא, בלי לאמת מול `tool_registry.py` (עוקף לגמרי את שער האישור) — 🟡 תוקן בקוד במלואו 07/07/2026 (root cause + תסמין), טרם ממוזג
- **תאריך:** 06/07/2026
- **דווח על ידי:** ביקורת C95A (Archive Carry-Forward Gap Discovery), session audit-only — לא בוצע שינוי קוד בזמן הגילוי.
- **Severity:** P0 — כתיבה חיה לטבלת `Leads` ב-Airtable עם אפס שער אישור, במסלול שכבר רץ בפרודקשן (לא תלוי ב-`FEATURE_ACTION_GATEWAY`, אותו דפוס כמו BUG-074/076 — הפגם חי גם כש-shadow-mode פעיל, כי `propose_action()` עצמו מחליט `status` ללא תלות בדגל).
- **קבצים:** `core/action_gateway.py` (`propose_action()` שורות 419-485, `classify_approval_policy()` שורה 99, `ActionContract.requires_approval` שורה 139), `core/lead_candidate_handler.py` (שורות 355-380 ושורות 526-534), `tool_registry.py` (שורות 120-127, 236).
- **ממצא (מאומת בקוד, לא ניחוש):**
  - `tool_registry.py:120-127` מצהיר `airtable_add` כ-`requires_approval=True` גלובלית; `tool_registry.py:236` (`get_tool_meta`) נגיש לכל קורא, אך **לא נקרא בשום מקום** בתוך `core/action_gateway.py`.
  - `propose_action()` (`core/action_gateway.py:419-430`) מקבל `requires_approval: bool` כפרמטר keyword-only חובה, **בלי ברירת מחדל, בלי validation**.
  - בין שורות 442-459 (`normalize_payload`/`compute_business_fingerprint`/בדיקת `existing` ב-ledger) — **אין שום קריאה ל-`tool_registry`/`enforce()`** בטווח הזה.
  - שורה 468: `requires_approval=requires_approval` — pass-through טהור לתוך ה-`ActionContract`, ללא cross-check.
  - שורה 479: `classify_approval_policy(tool_name, normalized)` **כן** רץ fail-closed (BUG-076), אבל זה קורה **אחרי** שה-contract כבר נוצר עם ה-`requires_approval` הגולמי מהקורא — `classify_approval_policy` קובע רק *מי מותר לו לאשש* contract שכבר `pending`; הוא לא קובע אם ה-contract בכלל נכנס למצב `pending`.
  - שורות 482-485 — נקודת ההכרעה היחידה בכל הפונקציה: `if requires_approval: status="pending" else: status="approved"` — כלומר אם הקורא מצהיר `False`, ה-contract נולד **מאושר מיידית**, ו-`classify_approval_policy`/`approve()` אף פעם לא נקראים.
  - `core/lead_candidate_handler.py:361` (מסלול auto-capture/dedup-check) קורא ל-`propose_action(..., requires_approval=False)` על `airtable_add`/`airtable_update` בטבלת `Leads`; `gw_result.ok` (שורות 364-366) נבדק אך ורק כשער כפילות ("duplicate"), **לא** כשער אישור; מיד לאחר מכן (שורות 371-380) מיובאים `airtable_create`/`airtable_patch` והכתיבה בפועל מתבצעת — **אפס שלב אישור**.
  - לעומת זאת, אותו קובץ, `core/lead_candidate_handler.py:526-534` (מסלול דיקטציה) קורא לאותו `propose_action()`, לאותו `tool_name` נומינלית, עם `requires_approval=True` — כלומר שני call sites **באותו קובץ** מצהירים ערכים סותרים לאותו tool, ואף מנגנון לא תופס את הסתירה.
- **Root cause:** `propose_action()` בונה אמון (trust) על ה-`requires_approval` שהקורא מצהיר, במקום לאמת אותו מול `tool_registry.get_tool_meta(tool_name).requires_approval` — בדיוק אותו דפוס שכבר תוקן עבור `classify_approval_policy` ב-BUG-076 ("never trusted from the caller"), אבל שלב pipeline אחד מוקדם מדי — לפני שהתיקון ההוא בכלל מופעל.
- **מיקום תיקון מדויק (לא exploratory):** ב-`core/action_gateway.py`, להוסיף **לפני שורה 468** קריאה ל-`tool_registry.get_tool_meta(tool_name)` ולאמת/לדרוס את `requires_approval` שהתקבל מהקורא מול `.requires_approval` הרשום שם — fail-closed (הרישום `True` גובר על `False` של הקורא, לא להיפך).
- **Scope לתיקון עתידי:** קובץ בודד, אדיטיבי, ללא שינוי Airtable schema/ROADMAP.
- **סטטוס:** 🟡 OPEN — לא תוקן, לא ממוזג. תועד כממצא ביקורת בלבד; ההחלטה אם/מתי לתקן בידי הבעלים.

#### עדכון 06/07/2026 (C83 audit cross-check — לא פותח BUG חדש, זה אותו ממצא)
במהלך סגירת C83 (ROADMAP.md, Single Policy Source) נבדק שוב מסלול `_write_one_lead:354` כדי לוודא שאין חפיפה/סתירה עם הרישום הזה. **תיקון לניסוח ראשוני שגוי שנשקל במהלך אותה בדיקה:** הועלתה השערה שהפגם "לא חי" כי `FEATURE_AUTO_CAPTURE=false` — ההשערה נבדקה בקוד ונמצאה **שגויה**. Tier 1/2 (`_handle_single_candidate`/`_handle_clean_batch`, `core/lead_candidate_handler.py`) אכן נשערים מאחורי `auto_capture`, אבל **Tier 3** (`_handle_mixed_batch`, שורות 615-621 → קריאה ל-`_write_one_lead` בשורה 746) **קורא ללא שום בדיקת flag**. כלומר על כל דיקטציית owner/staff שמניבה batch מעורב-ביטחון (`ic.tier == 3`), `_write_one_lead` — ועמו ה-gap המתואר למעלה — רץ בפרודקשן היום, ללא תלות ב-`FEATURE_AUTO_CAPTURE`. אין שינוי ל-Severity/סטטוס (עדיין 🟡 OPEN, P0) — זו רק הבהרה שמונעת הנחה מוטעית שהדגל מגן על המסלול הזה. ראה גם `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5/§7 ו-ROADMAP.md §C83.

#### תיקון חלקי 06/07/2026 — סוגר את התסמין החי (Tier 3), לא את הפער הארכיטקטוני המקורי
- **מה תוקן:** `core/lead_candidate_handler.py` — פונקציה משותפת חדשה `_should_auto_write(auto_capture, existing_id)` (כתיבה אוטומטית רק ל-lead חדש לגמרי + auto_capture דלוק; עדכון ליד קיים תמיד עובר אישור, עקבי עם BUG-074/076). Tier 1/2 הועברו לשימוש בה (איחוד קוד, ללא שינוי התנהגות). **Tier 3** (`_handle_mixed_batch`) קיבל את השער שחסר לו: כל `high`-confidence candidate נבדק כעת מול `_should_auto_write()` לפני `_write_one_lead()`; אחרת עובר דרך `_propose_lead_write()` בדיוק כמו Tier 1. כותרת הסיכום של ה-batch תוקנה גם היא כדי לא לטעון "X נשמרו" כשבפועל רק נוצר contract ממתין.
- **מה *לא* תוקן (עדיין פתוח, זה הפער המקורי מ-Root Cause למעלה):** `propose_action()` עצמו (`core/action_gateway.py:419-485`) עדיין סומך עיוורת על ה-`requires_approval` שמצהיר כל קורא, ועדיין **לא** קורא ל-`tool_registry.get_tool_meta(tool_name)` כדי לאמת/לדרוס אותו. התיקון הנוכחי סוגר את מסלול הקריאה היחיד שהיה חי בפרודקשן היום (Tier 3), אבל אינו מטפל ב-root cause עצמו — קורא עתידי אחר שיצהיר `requires_approval=False` בטעות על tool שה-registry מסמן `True` עדיין לא ייתפס. ה"מיקום תיקון מדויק" שתועד למעלה (לפני שורה 468 ב-`action_gateway.py`) נשאר scope נפרד, לא בוצע כאן במכוון (SPEC המקורי הגביל את ההיקף לקובץ `lead_candidate_handler.py` בלבד).
- **בדיקה:** `test_bug077_tier3_auto_capture_gate.py` (חדש, 5/5) — מכסה: auto_capture כבוי + lead חדש → אין כתיבה מיידית (contract ממתין); auto_capture דלוק + lead חדש → נכתב מיד (control, ללא רגרסיה); auto_capture דלוק + lead קיים → עדיין עובר אישור (ליבת התיקון); דיוק כותרת הסיכום; guard סטטי על ה-wiring ב-call site. אפס רגרסיה: כל 50+ קבצי `test_*.py` בריפו ירוקים (הורצו במלואם), `smoke_tests.py` ירוק, `python3 -m compileall .` נקי.
- **Merged:** ✅ כן — `main` `cdc41b5` (Merge pull request #250), commit `e1c0ea5`. מאומת: `git merge-base --is-ancestor e1c0ea5 origin/main` (07/07/2026). **תוקן מרישום קודם שגוי שאמר "Merged: לא" אחרי שהמיזוג כבר קרה.**
- **Deployed:** לא נבדק.
- **Verified בפרודקשן:** לא.
- **סטטוס (היסטורי, לפני התיקון המלא למטה):** 🟡 MERGED, NOT PRODUCTION-VERIFIED — התסמין החי (Tier 3) תוקן, נבדק, ומוזג ל-main. ה-root cause הארכיטקטוני נשאר 🟡 OPEN בנפרד.

#### תיקון root cause 07/07/2026 — סוגר את הפער הארכיטקטוני (לא רק את התסמין)
- **SPEC המקורי שהתקבל:** `propose_action()` (`core/action_gateway.py`) צריך לקרוא ל-`tool_registry.get_tool_meta(tool_name)` ולאמת/לדרוס את `requires_approval`. **תיקון עובדתי:** אין פונקציה בשם `get_tool_meta` ב-`tool_registry.py` — האקססור האמיתי הוא `needs_approval(tool_name) -> bool` (`tool_registry.py:234-236`, `meta.requires_approval if meta else False`), כבר מכוסה ב-3 טסטים קיימים (`test_approval_gate_registry.py`, `test_c83_single_policy_source.py`).
- **בעיה שהתגלתה במימוש הראשוני (לפני שנשלח commit):** יישום נאיבי (`if needs_approval(tool_name) and not requires_approval: requires_approval = True`, ללא תנאי נוסף) **שבר 2 טסטים קיימים** (`test_bug077_tier3_auto_capture_gate.py::test_tier3_new_lead_auto_capture_on_writes_immediately`, `test_c89_preview_confirmation.py::test_new_lead_still_auto_writes_with_auto_capture`). שורש ההתנגשות: `_write_one_lead()` (`core/lead_candidate_handler.py:355`) קרא ל-`propose_action()` עם `tool_inputs={"table": "Leads", "name": name, "phone": phone}` — **בלי מפתח `"fields"`** — לעומת `_propose_lead_write()` (התאום הבטוח שלו, Tier 1 preview) שכן עוטף הכל תחת `"fields": {...}`. `classify_approval_policy()` (BUG-076) בודק `tool_inputs.get("fields")` כדי לקבוע `self_confirm` — בלי המפתח, `_write_one_lead()`'s calls **תמיד** קיבלו `approval_policy="approval"`, לעולם לא `self_confirm`, אף שמדובר בדיוק באותו תרחיש בטוח (ליד חדש, שדות allowlisted) ש-`_propose_lead_write()` מטפל בו כ-self_confirm. תיקון naive לפי הרישום הגולמי היה הופך כל כתיבת-ליד אוטומטית (Tier 1/3, `FEATURE_AUTO_CAPTURE=true`) ל-contract "pending" יתום — הכתיבה בפועל עדיין הייתה מתבצעת מיד (ישירות, לא דרך ה-contract), משאירה "בקשת אישור" רדומה שלעולם לא נפתרת. זו לא הייתה "החלטה" חדשה — התיעוד הקיים כבר ב-`_lead_safe_fields()`'s docstring (`core/action_gateway.py:79`) קבע כהנחת-יסוד ש-`_write_one_lead()` "כבר כותב" בדיוק את השדות הבטוחים — הנחה שלא התממשה בפועל עד התיקון הזה.
- **התיקון הסופי (שני קבצים, לא אחד — אושר ע"י הבעלים אחרי שהקונפליקט הוצג):**
  1. `core/action_gateway.py::propose_action()` — `approval_policy` (מ-`classify_approval_policy()`) מחושב **לפני** בדיקת ה-cross-check, ומשמש גם את הבדיקה וגם את שדה ה-contract (לא קריאה כפולה). ה-override מתבצע **רק אם** `approval_policy != APPROVAL_POLICY_SELF_CONFIRM` **וגם** `tool_registry.needs_approval(tool_name)` **וגם** לא `requires_approval` — כך שה-carve-out הבטוח של BUG-076 לא נדרס.
  2. `core/lead_candidate_handler.py::_write_one_lead()` — ה-`tool_inputs` שנשלח ל-`propose_action()` נבנה מחדש לעטוף תחת `"fields"`, זהה בדיוק לשדות שהקטע "Write" בפועל כותב (`LeadFields.NAME/PHONE/CHANNEL/MEMORY_KEY/DOMAIN/SOURCE/STATUS/SUMMARY/SCORE/SENDER_ID` ליצירה; `PHONE/SUMMARY/DOMAIN` לעדכון) — כעת מקבל `self_confirm` נכון, תואם למה ש-`_lead_safe_fields()`'s docstring כבר הניח.
- **בדיקה:** `test_action_gateway.py` — 3 טסטים חדשים (override ל-`sheets_append`, ללא-שינוי כש-caller כבר מצהיר True, ללא-override ל-`airtable_get` שהרישום לא דורש לו אישור). אפס רגרסיה: 2 הטסטים ששברו בגרסה הנאיבית עוברים שוב; כל 50+ קבצי `test_*.py` ירוקים; `smoke_tests.py` ירוק; `python3 -m compileall .` נקי.
- **Merged:** בתהליך — ענף `claude/tool-approval-metadata-mi89lu`.
- **Deployed / Verified בפרודקשן:** לא.
- **סטטוס:** 🟡 CODE DONE, NOT MERGED — root cause **וגם** תסמין Tier 3 סגורים באותו קוד. **לא לסמן ✅ עד מיזוג + production evidence.**

#### תיקון סטטוס 07/07/2026 — מוזג בפועל, הרישום למעלה היה stale
`main` `4ba3002` (Merge pull request #254), commit `07caf9d`. מאומת: `git merge-base --is-ancestor 07caf9d origin/main`. **Deployed/Verified בפרודקשן:** לא נבדק עדיין — הרישום למעלה ("Merged: בתהליך") נכתב לפני שה-PR מוזג ולא עודכן בזמן אמת; זה תיקון-תיעוד בלבד, אין שינוי קוד.

### BUG-078 — `/update` — קובץ מצורף (photo/document) שנשלח באמצע השלב `text` אבד לגמרי מהקשר העדכון העסקי — ✅ תוקן 07/07/2026
- **תאריך:** 07/07/2026
- **דווח על ידי:** session audit — בדיקת זרימת `/update` מול ניתוב ה-webhook ב-`app.py`.
- **קבצים:** `app.py` (`_webhook_telegram_impl`), `cmd_update.py` (`has_pending_file_capture`, `capture_photo_or_document`).
- **Severity:** Medium — `/update` הוא owner/manager/partner-only, לא public-facing, אבל ההתנהגות השבורה בפועל: קובץ שנשלח באמצע האשף אבד לחלוטין, בלי שום הודעת שגיאה למשתמש.
- **ממצא (מאומת בקוד):** `app.py`'s webhook טיפל בהודעות `photo`/`document` ישירות דרך `_handle_telegram_media()` (הזרימה הכללית להעלאת Drive), **לפני** שקרא בכלל ל-`bot.process_new_updates()` — המנגנון היחיד שמפעיל handlers רשומים דרך `@bot.message_handler` (כולל `cmd_update.py`'s `capture_text`). המשמעות: `_pending[uid]` (ה-state הממתין של `/update`) לא נבדק בכלל לפני שהקובץ טופל. משתמש שהתחיל `/update`, בחר domain+entry_type, ואז שלח תמונה/מסמך במקום טקסט חופשי — הקובץ עלה ל-Drive כרשומת מדיה גנרית ללא קשר לתחום/סוג שנבחרו, וה-state הממתין נשאר תקוע עד שפג תוקפו (30 דקות).
- **תיקון:** `cmd_update.py` קיבל `has_pending_file_capture(user_id)`/`capture_photo_or_document(bot, message, get_identity)`. `app.py` בודק את זה **לפני** `_handle_telegram_media` עבור `photo`/`document`; אם יש `/update` ממתין בשלב `text`, הקובץ מנותב לפונקציה החדשה: מעלה ל-Drive (best-effort, דרך `media_handler.handle_file_upload` הקיים) ושומר caption+drive_url ל-Business Memory עם ה-domain/entry_type שכבר נבחרו באשף.
- **בדיקה:** `smoke_tests.py` ירוק, `test_integration.py` 4/4, `core/router/test_router.py` 44/44, טסט ידני ממוקד (mock `bot`+`identity`) מאמת שה-state נצרך נכון ושהרשומה נשמרת עם domain/entry_type נכונים.
- **Merged:** ✅ כן — `main` `194b3da` (Merge pull request #255), commit `32bbb75`. מאומת: `git grep` על `origin/main`.
- **Deployed/Verified בפרודקשן:** ✅ כן — 08/07/2026, ראה תרחיש מאומת ב-BUG-081 למטה (`/update` → נדל"ן → Other → טקסט → נשמר תקין, אין 422). מכסה את זרימת ה-webhook הכללית של `/update`, לא ספציפית את photo/document capture עצמו (התרחיש שנבדק היה טקסט חופשי).
- **סטטוס:** ✅ תוקן, מוזג ל-main, וזרימת `/update` הכללית מאומתת בפרודקשן (ראה הערה למעלה).

### BUG-079 — `/update` — שלב הטקסט החופשי אף פעם לא מגיע ל-`capture_text`, בורח ל-`run_agent` הכללי — ✅ תוקן 07/07/2026
- **תאריך:** 07/07/2026
- **דווח על ידי:** session audit, בהמשך ישיר ל-BUG-078 (אותו שורש: `app.py`'s webhook לא בודק pending `/update` state לפני ניתוב).
- **קבצים:** `app.py` (`_webhook_telegram_impl`), `cmd_update.py` (`has_pending_text_capture`).
- **Severity:** High — פוגע בתרחיש הראשי והצפוי של `/update` (לא רק edge-case קבצים כמו BUG-078). מאז ש-C20 (Business Context Command, `cmd_update.py`) נוסף (commit `5f902f5`), שלב כתיבת הטקסט החופשי **מעולם לא עבד** דרך ה-webhook האמיתי.
- **ממצא (מאומת בקוד):** `app.py` קורא ל-`bot.process_new_updates([update])` (המנגנון היחיד שמפעיל handlers רשומים, כולל `capture_text`) **רק** כש-`text.startswith("/")`. טקסט חופשי (לא slash-command) ממשיך ישר ל-`idempotency.is_duplicate()` ואז ל-`run_agent()` הכללי — `capture_text` אף פעם לא רץ. משתמש שמתחיל `/update`, בוחר domain+type, וכותב את הטקסט המבוקש — הטקסט מטופל כהודעת צ'אט רגילה (עלול להפעיל כלים/תשובה לא-קשורה), וה-state הממתין נשאר תקוע עד TTL.
- **תיקון:** `cmd_update.py` קיבל `has_pending_text_capture(user_id)` — `app.py` בודק אותו מיד אחרי בלוק ה-slash-command ולפני בדיקת ה-idempotency (fail-open בשגיאה — כשל בבדיקה ממשיך לזרימה הרגילה). אם `/update` ממתין בשלב `text`, ה-webhook קורא ל-`bot.process_new_updates()` בעצמו כדי ש-`capture_text` יתפוס את ההודעה.
- **בדיקה:** `smoke_tests.py` ירוק, `test_integration.py` 4/4, `core/router/test_router.py` 44/44, טסט ידני מבודד של `has_pending_text_capture()` על פני מעברי שלב (domain→type→text) מאמת שהיא מחזירה `True` רק בשלב `text` ולא צורכת state (תואם ל-`capture_text`'s own pop).
- **Merged:** ✅ כן — `main` `baa0283` (Merge pull request #256), commit `912b94e`. מאומת: `git grep` על `origin/main`.
- **Deployed/Verified בפרודקשן:** ✅ כן — 08/07/2026: `/update` → נדל"ן → Other → טקסט חופשי → `capture_text` תפס את ההודעה ושמר בהצלחה (ראה תרחיש מלא ב-BUG-081 למטה).
- **סטטוס:** ✅ תוקן, מוזג ל-main, ומאומת בפרודקשן.

### BUG-080 — כתיבת `datetime` מלא (עם שעה/מיקרושניות/offset) לשדות Date-בלבד ב-Airtable → 422 — ✅ תוקן 07/07/2026
- **תאריך:** 07/07/2026
- **דווח על ידי:** אימות field-type metadata חי מול Airtable — Business Memory + כל 4 טבלאות Decision Hub, `datetime_fields: []` בכולן.
- **קבצים:** `cmd_update.py` (`BMF.DATE`), `media_handler.py` (`BMF.DATE`), `cmd_decision.py` (`DecisionEventFields.EVENT_DATE` ×2, `DecisionInboxFields.RECEIVED` ×3) — 7 נקודות כתיבה בסה"כ.
- **Severity:** High — `BusinessMemoryFields.DATE`/`DecisionEventFields.EVENT_DATE`/`DecisionInboxFields.RECEIVED` הם שדות `Date` בלבד (`YYYY-MM-DD`) ב-Airtable בפועל, אבל כל 7 נקודות הכתיבה שלחו `datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()` — מחרוזת מלאה עם שעה/מיקרושניות/offset (למשל `"2026-07-07T17:48:18.520669+03:00"`). אין `typecast=true` בשכבת ה-gateway (`tools/airtable_gateway.py`/`tools/airtable_tools.py`) — Airtable דוחה ערך כזה עם 422 עבור שדה Date-בלבד.
- **תיקון:** שינוי `.isoformat()` ל-`.date().isoformat()` בכל 7 המקומות — מחרוזת `"YYYY-MM-DD"` בלבד, תואמת את טיפוס השדה. נבדק ונשאר ללא שינוי במפורש: 2 מקומות ב-`cmd_decision.py` שהם `FileUploadResult(timestamp=...)` — אובייקט `session_store` בזיכרון, לא שדה Airtable; שימוש read-only אחד ב-`.get(EVENT_DATE, "")` כמפתח מיון; `Created`/`Last Updated` מאושרים כ-Airtable auto-populated (`createdTime`/`lastModifiedTime`), אין נקודת כתיבה ידנית להם ב-`cmd_decision.py` כלל.
- **בדיקה:** `smoke_tests.py` ירוק, `test_integration.py` 4/4, `core/router/test_router.py` 44/44, `test_decision_attention.py` 11/11, `test_core_reasoning.py` 59/59 (משתמשים ב-fixture strings קבועים, לא מושפעים), בדיקה ידנית של הפורמט לפני/אחרי, `grep` מאמת שבדיוק 7 המקומות השתנו ולא יותר.
- **Merged:** ✅ כן — `main` `a8ffa07` (Merge pull request #258), commit `02bc343`. מאומת: `git grep` על `origin/main`.
- **Deployed/Verified בפרודקשן:** ✅ חלקית — 08/07/2026: `cmd_update.py`'s `BMF.DATE` נבדק בפועל (`/update` → נדל"ן → Other → טקסט → נשמר, אין 422). שאר 6 נקודות הכתיבה (`media_handler.py`, `cmd_decision.py` ×5) **לא נבדקו עדיין** בתרחיש הזה.
- **סטטוס:** ✅ תוקן ומוזג ל-main — נקודת הכתיבה של `/update` מאומתת בפרודקשן, שאר הנקודות עדיין ממתינות לאימות.

### BUG-081 — Business Memory `Domain` "ממוחזר" לתוך `Tags` הכללי, בלי אימות מול live options → 422 (תוקן ב-6 שלבים) — ✅ תוקן 07/07/2026, ✅ מאומת בפרודקשן במלואו 08/07/2026 (6/6 domains), ✅ שלב 6 (root cause מבני) 09/07/2026
- **תאריך:** 07/07/2026
- **דווח על ידי:** session audit, בהמשך ל-BUG-080 — נבדק אם domain key גולמי (למשל `"media"`) שנכתב ל-`Tags` הוא בכלל option קיים.
- **קבצים:** `airtable_schema.py` (`BusinessMemoryFields.DOMAIN` — שדה חדש), `cmd_update.py` (`normalize_business_memory_fields`, `_VALID_TAGS`, `_DOMAIN_TO_AIRTABLE`, `_TAG_NORMALIZE`), `media_handler.py` (`_save_transcript_to_memory`).
- **Severity:** High — `BusinessMemoryFields`, בניגוד לכל טבלה אחרת בסכימה (`Leads`/`Tasks`/`Contacts`/`Deals`/`DecisionEventFields`/`MediaFileFields` — לכולן שדה `Domain` ייעודי), לא היה לה שדה `Domain` בכלל. `cmd_update.py`/`media_handler.py` כתבו את מפתח ה-domain הגולמי (למשל `"media"`) ישירות לתוך `Tags` (multipleSelects) — בלי שום ערבות שזה option קיים. אין `typecast=true` בגייטוויי → כל ערך שאינו option קיים נדחה עם 422 `INVALID_MULTIPLE_CHOICE_OPTIONS`.
- **שלב 1 (PR #259):** נוסף `BusinessMemoryFields.DOMAIN = "Domain"`. נוספה `normalize_business_memory_fields(fields, raw_domain_key)` — ממפה domain key → ערך Airtable מאומת (`import`→`Import`, `media`→`media`, `saas`→`SaaS`, `finance`/`general`→`General`, `real_estate`→`"real_estate"` **[שגוי, ראה שלב 2]**) לשדה `Domain` הייעודי; מסננת `Tags` לערכים חוקיים בלבד (`_VALID_TAGS`) כך ש-domain keys שדלפו מוסרים; מנרמלת גם `Event Type`/`Event Date` כ-defense-in-depth. נקראת משני מקומות הכתיבה (`cmd_update.py`, `media_handler.py`) לפני `airtable_create`.
- **שלב 2 (PR #260) — תיקון על בסיס production evidence:** `_DOMAIN_TO_AIRTABLE["real_estate"]` מופה בטעות ל-`"real_estate"` (lowercase) בשלב 1; אושר מול live Airtable ש-2 real-estate options היו קיימים במקור ואחד (ה-lowercase) נמחק בניקוי — Title Case `"Real Estate"` הוא היחיד שנשאר. תוקן ל-`"real_estate": "Real Estate"`.
- **שלב 3 (PR #261, 2 commits) — 422 חי נוסף בפרודקשן אחרי מיזוג שלב 2:** `_VALID_TAGS` עדיין הכיל `"real_estate"` (lowercase) כ-tag עצמאי חוקי — אותו duplicate-cleanup שחל על `Domain` חל גם על `Tags`, אז `domain="real_estate"` עדיין שלח `"real_estate"` (lowercase) ל-`Tags` וקיבל 422 בפרודקשן (`INVALID_MULTIPLE_CHOICE_OPTIONS`, נצפה בלוג). תיקון ראשון (`f367469`): הוסר `"real_estate"` מ-`_VALID_TAGS` — עצר את ה-422 אבל הפיק `Tags` ריק במקום הערך הקנוני. תיקון שני (`7526e60`): נוסף `_TAG_NORMALIZE = {"real_estate": "Real Estate"}` (מיושם על raw tags **לפני** הסינון), ו-`"Real Estate"` (Title Case) נוסף ל-`_VALID_TAGS` — כעת `domain="real_estate"` מפיק `Domain="Real Estate"` **וגם** `Tags=["Real Estate"]`, אף לא ערך lowercase אחד מגיע ל-Airtable.
- **שלב 4 (PR #263) — root cause אמיתי, לא רק normalization:** מאומת מול production logs ש-`_save_to_business_memory` (וגם `media_handler.py::_save_transcript_to_memory`) **תמיד** הזריקו את ה-domain הנבחר ל-`BMF.TAGS` (`BMF.TAGS: [domain]`), בלי קשר אם זה ערך-נושא אמיתי. שלבים 1-3 טיפלו בזה כבעיית נרמול-ערכים (מיפוי/סינון/קנוניזציה של מה שנכנס ל-`Tags`) במקום לתקן את הפגם עצמו: domain לא אמור להגיע ל-`Tags` בכלל. הוסר `BMF.TAGS: [domain]` משני מקומות הכתיבה; הוסר `_TAG_NORMALIZE` לגמרי (לא נדרש יותר — אין יותר domain-value שדולף ל-Tags לתקן). `_VALID_TAGS` נשאר כ-defense-in-depth למקור נושאים עתידי היפותטי, אך אינו רלוונטי לנתיב הנוכחי. גם תוקן `_DOMAIN_TO_AIRTABLE["media"]` (`"media"` lowercase → `"Media"` Title Case), ותוקנה `get_recent_business_context()` לסנן לפי `{Domain}` במקום `{Tags}` (עם `FIND(...)` על `Tags` כ-legacy fallback לרשומות ישנות בלבד).
- **שלב 5 (PR #265) — תיקון סופי, רווח בסוף:** אומת ישירות מול Airtable Meta API (לא צילום מסך) שהאופציות החיות הן `"Real Estate "` ו-`"SaaS "` (עם רווח בסוף), לא המחרוזות הנקיות ששימשו עד כה. `_DOMAIN_TO_AIRTABLE["real_estate"]`/`["saas"]` עודכנו בהתאם; אומת ב-`repr()` שהרווח נשמר בקוד ולא נגזם ע"י עורך/linter.
- **שלב 6 (PR #276, 09/07/2026) — root cause מבני, לא רק עדכון ערך:** תקרית חיה נוספת (רווח בסוף שוב) הובילה לחקירה שגילתה: הסתירה בין PR #265 (טען שהחי כולל רווח) לבין בדיקה חיה חדשה (בלי רווח) נבעה משינוי ידני של המשתמש בבייס לצורך בדיקת PR2 — לא סתירה אמיתית בשלב 5. אבל זה חשף את הבעיה המבנית: `_DOMAIN_TO_AIRTABLE` הוא מילון סטטי שדורש תיקון ידני בכל פעם שהסכימה החיה משתנה (5 תיקונים קודמים לאותו pattern). נוספה `resolve_business_memory_domain()` — בירור חי מול `RuntimeSchemaProvider.get_table_contract("Business Memory")`, case/whitespace-tolerant matching (`_normalize_domain_option`, נרמול גנרי), duplicate-option guard (`{"ok": false, "error": "duplicate option name found: ... (N matching options)"}`), no-match → שגיאה מובנית לא ערך שרירותי. `_DOMAIN_TO_AIRTABLE` נשאר רק כ-fallback אחרון כש-provider לא זמין בכלל. `_save_to_business_memory` שונה מ-`None` גולמי ל-`{ok, record|error}` (אותה משמעת חוזה כמו `PR_RESPONSE_CONTRACT`) — שני ה-callers מציגים הודעת כשל ספציפית במקום לבלוע כשל בשקט. **DoD חדש שלא היה קיים בשלבים 1-5:** rename אופציה חיה → הכתיבה הבאה מסתגלת אוטומטית, בלי תיקון קוד.
- **בדיקה:** `smoke_tests.py` ירוק בכל שלב, `test_integration.py` 4/4, `core/router/test_router.py` 44/44 (שלבים 1/4). בדיקות ידניות ממוקדות בכל שלב, כולל `repr()` על שלב 5. שלב 6: `test_business_memory_domain_lookup.py` (חדש) 24/24 — exact-value live lookup, rename-DoD, duplicate guard, no-match, provider-fallback, `finance→general`, `{ok,...}` contract על כל מסלולי הכשל.
- **Merged:** ✅ כן — `main` `50847b7` (PR #259), `0094a82` (PR #260), `fa08a58` (PR #261), `eaa01fa` (PR #263), `def0a00` (PR #265), `61b1c34` (PR #276, commits `b578e2c`+`17b73b7`). מאומת: `git grep`/`git merge-base --is-ancestor` על `origin/main` בכל שלב.
- **Deployed/Verified בפרודקשן:** ✅ חלקית — 08/07/2026: `/update` נבדק ב-**כל 6** ה-domains ברצף אמיתי (Telegram, Eli↔BOSS) עם המנגנון של **שלבים 1-5** (המילון הסטטי) — `נדל"ן` (real_estate), `SaaS`, `מדיה` (media), `ייבוא` (import), `כללי` (general), `כספים` (finance), כולם → `Other` → טקסט חופשי → נשמר בהצלחה, "📌 Other | <domain>" הוצג נכון בכל אחד, **אין 422** באף אחד. **שלב 6 (הבירור החי) טרם עבר את אותו אימות production מחדש** — המנגנון החדש שונה מהותית (live lookup ולא מילון), צריך ריצה אמיתית משלו לפני שנחשב מאומת.
- **פער ידוע, לא בסקופ:** `weekly_summary.py::_group_by_domain()` ו-`tma_api.py`'s Business Memory listing עדיין קוראים `Tags[0]` כ-domain — ישברו בשקט (default ל-`"general"`/ריק) ברגע שרשומות חדשות ייכתבו עם `Domain` בשדה הייעודי במקום ב-`Tags`. Backlog, piggyback-trigger על הפעלת `FEATURE_WEEKLY_SUMMARY` או שימוש פעיל ב-TMA business memory screen — אף אחד מהשניים לא בשימוש פעיל כרגע.
- **סטטוס:** ✅ תוקן ומוזג ל-main (6 PRs) — **מאומת בפרודקשן, 6/6 domains, עבור מנגנון שלבים 1-5**; שלב 6 (הבירור החי המבני) מוזג אך **טרם מאומת בפרודקשן בפני עצמו**.

### BUG-082 — כשל בפענוח הפניות אנאפוריות ("זה", "הנספח", "הקודם") — נבדק, לא אושר: הופרך בקוד
- **דווח:** 08/07/2026
- **דווח על ידי:** session audit — השוואת סיכום שיחה (`KNOWN_ISSUES.md`, לא קיים בריפו כקובץ) מול `BUG_AUDIT_LOG.md` הקיים, ללא grep מוקדם.
- **grep-אימות שבוצע (התבקש מפורשות לפני קביעת סטטוס):** `grep -n "last_entity\|last_tool_result\|working_memory\|anaphor\|entity_ref" context.py memory_store.py app.py`.
- **ממצא:** ה-hypothesis **מופרך ישירות בקוד**. קיים מנגנון Working-Memory מלא ומחווט: `app.py:955` — `CONTEXT_PRONOUNS` ממפה בדיוק את המילים שדווחו ("זה"→`last_tool_result`, "הנספח"/"הקובץ"/"הקובץ האחרון"→`last_file`, "הקודם"/"ההוא"/"אותו"→`last_tool_result`) לשדה session (`last_tool_result`/`last_uploaded_file`, נשמר ע"י `_capture_last_tool_result()` אחרי כל tool call, `app.py:883`). `resolve_context_pronouns()` (`app.py:966`) מחליף את הכינוי בהתייחסות מפורשת ("הפעולה «...»"/"הקובץ «...»") **לפני** intent detection. מחווט בפועל בתוך `run_agent()` (`app.py:1631`), עם תגובה מפורשת בקוד: `# "תעלה לדסישנס"/"זה הנספח" וכד' — לפני intent detection` — כלומר "זה הנספח" (הדוגמה המדויקת מהדיווח) מתועד כ-use-case שהמנגנון הזה נבנה לטפל בו. זהו הפיצ'ר **C60 Tool Context Awareness** (ראה `AI_CONTEXT.md` היסטורי, PR #152 — מאומת מוזג).
- **מגבלה אמיתית שנותרה (לא הבאג שדווח):** הפתרון עובד רק אם `session["last_tool_result"]`/`["last_uploaded_file"]` מאוכלס בפועל (כלומר יש tool call/קובץ קודם בשיחה) — אם הכינוי מתייחס לישות שיחתית כללית שאינה tool-result/קובץ (למשל עובדה שנאמרה בטקסט חופשי, לא פלט כלי), הוא לא נפתר. זו מגבלת-scope ידועה של C60, לא "חוסר מוחלט ב-Working Memory" כפי שנוסח בדיווח המקורי.
- **Root Cause:** אין — ה-hypothesis שגויה. הדיווח המקורי כנראה נבע מתצפית ישנה/לפני C60, או מ-repro ספציפי שבו `last_tool_result` לא היה מאוכלס (התרחיש הצר שכן פתוח, ראו למעלה).
- **Merged:** לא רלוונטי — אין תיקון קוד, אין באג מאושר.
- **Verification ראיה:** `grep` בוצע, קוד נקרא במלואו (`app.py:883-986, 1631`), מסקנה מבוססת קוד לא ניחוש.
- **סטטוס:** ❌ Won't Fix / Not a Bug — מופרך בקוד. אם רוצים לחקור את המגבלה הצרה (כינוי ללא tool-result קודם), זה backlog item נפרד, לא BUG-082.

### BUG-083 — Decision Inbox חסרה מ-schema drift coverage — הפרמיס המקורי שגוי, אך נמצא פער אמיתי וצר יותר
- **דווח:** 08/07/2026
- **דווח על ידי:** session audit — לא אומת ב-grep מול קוד בפועל בזמן הדיווח.
- **grep-אימות שבוצע (התבקש מפורשות):** `grep -n "DECISION_INBOX\|DecisionInbox" core/router/*.py airtable_schema.py schema_audit.py`.
- **ממצא 1 — הפרמיס המקורי ("לא רשומה ב-Router Table Registry") שגוי:** **אין בכלל "Router Table Registry" בקוד.** `grep` על `core/router/*.py` לכל תבנית table-registry (`TABLE_CLASS_MAP`/`TABLE_REGISTRY`/`Tables\.`) מחזיר **אפס תוצאות**. הראוטר (`core/router/`) מנתב לפי Identity→Intent/Domain/Risk→Handler — אין לו מושג של "טבלת Airtable רשומה", לא ל-Decision Inbox ולא לאף טבלה אחרת. הפרמיס מבלבל בין שכבת הראוטר לשכבת schema governance (קובץ שונה לגמרי).
- **ממצא 2 — פער אמיתי, אך שונה וצר יותר:** `Tables.DECISION_INBOX`/`DecisionInboxFields` **כן** מוגדרים ב-`airtable_schema.py` (שורות 76, 1147+), אבל `schema_audit.py`'s `TABLE_CLASS_MAP` (הרשימה שמשמשת את בדיקת schema-drift מול Airtable החי) **לא כוללת אותם בכלל** — `grep -n "Decision" schema_audit.py` מחזיר אפס תוצאות. אותו דבר חל על `DecisionEventFields`/`DecisionInboxFields` וכל שאר Decision Hub. זו אותה משפחת-פער כמו BUG-015 (Media Files חסרה מ-`TABLE_CLASS_MAP`) — אבל `MEDIA_FILES` **כן** נמצא כיום ב-`TABLE_CLASS_MAP` (שורה 34, כנראה תוקן מאז BUG-015), בעוד Decision Hub מעולם לא נוסף.
- **Root Cause (הפער האמיתי, לא הפרמיס המקורי):** `schema_audit.py`'s `TABLE_CLASS_MAP` נבנה לפני/בלי Decision Hub (C89+ epic) והוא ידני (dict קשיח) — אף אחד לא הוסיף אליו את טבלאות Decision Hub כשהן נוצרו.
- **השפעה בפועל:** `schema_audit.py`/`schema_validator.py`'s coverage לא מזהה drift בשדות Decision Events/Decision Inbox מול Airtable החי — לא חוסם כתיבה (זה תפקיד `airtable_gateway.py`, לא `schema_audit.py`), רק אומר ש-audit ידני נדרש אם רוצים לוודא שאין drift שם.
- **תיקון מוצע (לא בוצע — audit בלבד):** הוספת `schema.Tables.DECISION_EVENTS: schema.DecisionEventFields` ו-`schema.Tables.DECISION_INBOX: schema.DecisionInboxFields` ל-`TABLE_CLASS_MAP` ב-`schema_audit.py`. שינוי קובץ יחיד, אדיטיבי, ללא נגיעה בכתיבה/router.
- **Merged:** לא — לא בוצע קוד בסבב זה (audit בלבד, כמבוקש).
- **Verification ראיה:** `grep` בוצע כמבוקש, שני הממצאים מבוססי קוד.
- **סטטוס:** 🟡 Open, אך **לא** כפי שתואר במקור — "Router Table Registry" לא קיים ולא רלוונטי; הפער האמיתי (Decision Hub חסר מ-`schema_audit.py`'s `TABLE_CLASS_MAP`) הוא low-severity (audit coverage בלבד, לא production write path) ולא בסקופ תיקון בסבב זה.

### BUG-084 — commit+push מצליחים אך PR לא נפתח — נבדק מול הסשן הנוכחי, לא שוחזר
- **דווח:** 08/07/2026
- **דווח על ידי:** session audit — לא אומת מול היסטוריית PRs בפועל בזמן הדיווח.
- **בדיקה שבוצעה:** נבדקה היסטוריית הסשן הנוכחי (PRs #255-#266, 12 PRs) — בכל מקרה שבו `git push` הצליח, נעשה ניסיון מיידי לפתוח PR דרך כלי ה-GitHub. בשני מקרים בסשן הנוכחי כלי ה-`create_pull_request` היה זמנית לא-זמין (MCP server disconnected) — בשני המקרים זה דווח במפורש למשתמש בטקסט, ולא הושאר בשקט; ה-PR נפתח בפועל ברגע שהכלי חזר להיות זמין (`ToolSearch` לאיתור מחדש). כלומר: יש תרחיש אמיתי של "לא נפתח PR מיד אחרי push" — אבל הוא **תוצאה של זמינות כלי חיצוני חולפת, לא של החלטה שקטה לדלג על פתיחת PR**, ותמיד טופל/תוקשר.
- **תואם את הערכת המדווח עצמו:** "בבדיקת כל הרשומות בלוג הקיים — כל ה-PRs שתועדו נפתחו ומוזגו בפועל... ייתכן כשל gh CLI/auth (ראו BUG-063), לא כשל לוגי שיטתי."
- **Root Cause:** אין כשל לוגי מאושר בקוד המוצר או בתהליך — רק תלות בזמינות כלי MCP חיצוני, שמטופלת כבר (retry + תקשור מפורש כשקורה).
- **Merged:** לא רלוונטי — אין קוד מוצר מעורב, אין תיקון.
- **Verification ראיה:** נבדק מול היסטוריית הסשן הנוכחי (12 PRs, כולל 2 מקרי disconnection שטופלו).
- **סטטוס:** ❌ Won't Fix — אין ראיה לכשל שיטתי; מקביל ל-BUG-063 (כשל זמינות כלי, לא באג לוגי). אם יופיע שוב עם ראיה קונקרטית (PR שבאמת לא נפתח בלי תקשור), לפתוח רשומה חדשה עם אותה ראיה.

### BUG-085 — `run_snapshot_archive()` אף פעם לא כותב `Status=Drift Detected`, למרות שה-enum קיים מ-PR3A — 🟡 תוקן בקוד, טרם ממוזג
- **תאריך:** 09/07/2026
- **דווח על ידי:** session audit, בהמשך לעבודה על PR3A/PR3B — תוייג בטעות בשיחה כ-"BUG-082" (מספר זמני, לא ID אמיתי מהלוג; BUG-082 הרשמי הוא נושא נפרד ולא קשור — anaphora resolution, כבר סגור כ-Won't Fix).
- **קבצים:** `tools/schema_snapshot.py` (`run_snapshot_archive`, `_missing_tables` חדשה), `test_schema_snapshot.py`.
- **Severity:** Medium — `SchemaSnapshotStatus.DRIFT_DETECTED` (`airtable_schema.py`) קיים כ-option מאז PR3A, אבל `run_snapshot_archive()` מעולם לא כתב אליו — הפונקציה קבעה רק `OK`/`Error` על בסיס האם פעולת ה-snapshot עצמה (fetch/upload/XLSX conversion) הצליחה, בלי שום השוואה בין הטבלאות שהקוד מכיר (`airtable_schema.Tables`) לבין מה שחי בפועל ב-Meta API. כלומר: אם טבלה נמחקה/שונה שם ב-Airtable החי, ה-snapshot עדיין נכתב כ-`OK` — אין שום איתות.
- **תיקון:** נוספה `_missing_tables(raw_meta)` — משווה `set(airtable_schema.Tables)` מול שמות הטבלאות החיות מה-Meta API response, אותה שיטת חילוץ בדיוק כמו `tools/check_airtable_schema_runtime.py`'s `missing_in_airtable` (לא כפילות לוגית, רק שימוש חוזר בעיקרון). אם יש טבלאות חסרות — הסטטוס הנכתב (גם ביצירת הרשומה וגם בעדכון הסופי) הוא `Drift Detected` במקום `OK`; `Error` (כשל תפעולי — upload/conversion נכשל) עדיין גובר על `Drift Detected` אם שניהם קורים יחד. `Notes` כולל את רשימת הטבלאות החסרות. `apply_retention_policy()` לא שונה (מגן רק על ה-`OK` האחרון, כפי שהיה — שאלת מדיניות נפרדת, לא בסקופ).
- **בדיקה:** `test_schema_snapshot.py` — 34/34 (9 טסטים חדשים: `_missing_tables` ישיר + end-to-end `run_snapshot_archive()` עם כל הרשתות מדומות, גם למקרה "הכל תקין" (עדיין `OK`, regression) וגם למקרה עם טבלה חסרה (`Drift Detected` גם ב-create וגם ב-patch הסופי, `Notes` מזכיר את הטבלה החסרה)). `smoke_tests.py`/`test_integration.py` ירוקים (רק כשל flask קיים-מראש בסביבה, לא קשור).
- **Merged:** ✅ כן — `main` `5dde1eb` (Merge pull request #279), commit `60901c8`. מאומת: `git grep`/`git log origin/main` (`_missing_tables` נמצא ב-`tools/schema_snapshot.py` על `origin/main`).
- **Deployed/Verified בפרודקשן:** לא — `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` כבוי כברירת מחדל, אין נתוני production.
- **סטטוס:** ✅ תוקן ומוזג ל-main — לא מאומת בפרודקשן (flag כבוי).

### BUG-086 — Anti-hallucination: תביעות CREATE בגוף ראשון ("הוספתי") חמקו מה-Gate, ואין safety net גנרי (09/07/2026, 2 PRs)
- **תאריך:** 09/07/2026
- **דווח על ידי:** המשתמש דיווח תקרית חיה (בדיקה על PR #276): הבוט הגיב "✅ הוספתי... 30 רשומות פעילות" בלוג שהראה 3 קריאות `GET Business Memory` (28 רשומות בכל פעם) ואפס קריאות `airtable_add` — מספר עולה עקבי (28→29→30) בלי גזירה מ-tool result אמיתי, מוכיח שה-LLM "ניחש" את המספר מזיכרון-שיחה.
- **קבצים:** `core/anti_hallucination.py` בלבד (שני PRs) | PR #277, #278.
- **Severity:** High — claim-without-evidence כוזב מהמשתמש, על פעולת כתיבה עסקית שלא קרתה בפועל.
- **שלב 1 (PR #277) — root cause ספציפי:** `_NO_TOOL_CLAIMS`'s CRM creation-claim pattern תפס רק צורות גוף שלישי/סביל ("הרשומה נוצרה", "נוסף ל-Airtable") — בדיוק כמו BUG-NEW-09 (שכבר תוקן לצד ה-UPDATE claims), אבל מעולם לא הוחל על ה-CREATE claims. נוסף `הוספתי|שמרתי|רשמתי|תיעדתי` (גוף ראשון) ל-pattern, עם אותו `(?<!לא )(?<!עדיין )` guard, עדיין דורש evidence מ-`airtable_add`.
- **שלב 2 (PR #278) — safety net גנרי, follow-up מאושר מראש:** ההצעה הראשונית ("zero tool_use בכלל → לחסום") נבדקה מול המבנה האמיתי ונמצאה **לא תקפה** — 3 קריאות `airtable_get` (read-only) בתקרית האמיתית היו "מכבות" guard כזה. תוקן ל-`_has_write_tool_evidence()`: דורש tool מ-`_WRITE_ACTION_TOOLS` ספציפית (לא "כל tool"), משולב עם `_AGENT_ACTION_STATUS_PATTERN` (גם הוא הורחב לגוף ראשון, משותף לשני השימושים). רץ תמיד ב-`sanitize_agent_response`, לא רק תחת `FEATURE_ACTION_GATEWAY` — שכבה נוספת מעל ה-patterns הספציפיים, לא תחליף.
- **בדיקה:** `core/anti_hallucination.py` self-tests — 66/66 אחרי שני השלבים (כולל שחזור מדויק של התקרית החיה, regression ש-GET+CREATE אמיתי לא נחסם, `airtable_add ok=False` עדיין נחסם, ופועל לא-ברשימה נתפס גנרית). CXX 9/9. `test_approval_gateway_safety.py`/`test_c53a.py`/`test_stage_b_verification.py` — אפס רגרסיה.
- **Merged:** ✅ כן — `main` `c961f25` (PR #277, commit `369168f`), `ab1aefd` (PR #278, commit `a64d9f3`). מאומת: `git grep _has_write_tool_evidence` על `origin/main`.
- **Deployed/Verified בפרודקשן:** לא עדיין.
- **סטטוס:** ✅ תוקן ומוזג ל-main — לא מאומת בפרודקשן.

### BUG-087 — Fallback messages ב-Restricted/Single-Speaker flows הבטיחו המשך-טיפול שלא קיים (09/07/2026, 2 PRs)
- **תאריך:** 09/07/2026
- **דווח על ידי:** session audit, בהמשך ל-BUG-086 — grep מכוון לחיפוש ניסוחי "יטופל/יישלח בהמשך" בכל הריפו, כדי לבדוק אם יש מקומות נוספים מאותה מחלה (claim-without-evidence) מעבר ל-tool-result claims.
- **קבצים:** `core/anti_hallucination.py`, `app.py`, `test_restricted_tool_fake_forward_message.py` (חדש), `ROADMAP.md` (N15) | PR #280, #281.
- **Severity:** Medium — לא כשל כתיבה, אבל אותו סוג בדיוק של הבטחה כוזבת למשתמש שה-A32/anti-hallucination אמור למנוע: מחרוזות ה-fallback עצמן היו ה-hallucination.
- **שלב 1 (PR #280):** `_SINGLE_SPEAKER_FALLBACK` ("הפעולה התקבלה. תוצאה תישלח בנפרד.") — כשה-Single-Speaker gate מפעיל את זה, שום תהליך המשך לא קורה בפועל. שונה ל-"לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת." — לא מבטיח דבר שלא קורה. תנאי ההפעלה לא שונו.
- **שלב 2 (PR #281):** `app.py:1867` — אותו pattern בדיוק, ב-tool loop של Restricted flow: `"הבקשה התקבלה ותועבר לטיפול."` מוזרק כ-tool_result כוזב ל-Claude כש-`route.tool_allowed=False`. אומת ב-grep ש-`route.notify_owner` (נקבע `True` עבור `Handler.RESTRICTED`) **אף פעם לא נצרך** בשום קוד מחוץ ל-assertions בטסטים — אין מנגנון התראה/העברה אמיתי. שונה ל-"הבקשה נרשמה במערכת." — כן על המצב האמיתי. נפתח `ROADMAP.md` N15 כ-backlog item נפרד (feature, לא bug): להחליט אם לבנות התראה אמיתית לבעלים או להסיר את השדה המת.
- **בדיקה:** PR #280 — `core/anti_hallucination.py` self-tests 70/70 (כולל 4 טסטים חדשים: gate מופעל עם ההודעה החדשה, לא נשבר תנאי הפעלה). PR #281 — `test_restricted_tool_fake_forward_message.py` חדש, מריץ את `app.run_agent()` האמיתי מקצה לקצה (Identity/Router/Context/Anthropic מדומים) — 3/3. הותקן `requirements.txt` המלא בסביבת הבדיקה (היה חסר) לצורך הרצה אמיתית — כל 62 קובצי `test_*.py` + `smoke_tests.py` (כולל Import test) + `test_a32_enforcement.py` (6/6) + `test_stage_b_full_suite.py` (124/124) אומתו ירוקים בפועל, לא רק סטטית.
- **Merged:** ✅ כן — `main` `b9a1ee7` (PR #280, commit `cd20653`), `75cdb45` (PR #281, commit `9065339`). מאומת: `git grep` על `origin/main`.
- **Deployed/Verified בפרודקשן:** לא עדיין.
- **סטטוס:** ✅ תוקן ומוזג ל-main — לא מאומת בפרודקשן. N15 (מדיניות notify_owner) נשאר פתוח ב-`ROADMAP.md`, לא בסקופ התיקון הזה.

### BUG-088 — Audit: Structural vs Enumeration על כל תיקוני היום (09/07/2026) — ✅ Audit בלבד, ללא action items
- **תאריך:** 09/07/2026
- **דווח על ידי:** session audit, ביוזמת המשתמש — בקשה לוודא שכל תיקון היום הוא כלל גנרי (structural) ולא רשימה שצריך לעדכן ידנית לכל מקרה עתידי (enumeration), לפני שממשיכים ל-item הבא.
- **נבדק (6 פריטים, מול קוד ממוזג בפועל, לא זיכרון):**
  1. `resolve_business_memory_domain()` (BUG-081 שלב 6) — **Structural**: live lookup + נרמול גנרי (`.strip().lower()`), לא רשימת תיקונים.
  2. Anti-hallucination generic guard (BUG-086) — **Structural**: `_has_write_tool_evidence()` לפי חברות ב-set, לא per-verb.
  3. `enforce_leads_write_gate` (BUG-028) — **Enumeration, מכוון**: `_LEADS_TABLE_NAMES` hardcoded, Leads-only. אושר כהחלטת מדיניות (ראה עדכון ב-BUG-028 למעלה), לא נגעו.
  4. SelectValueValidation (PR2, SHADOW) — **Structural**: `choices` נשלף רק מ-`RuntimeSchemaProvider.get_table_contract()`, אין רשימה hardcoded מקבילה (`schema_intelligence.py`'s `SCHEMA` dict אומת כ-dead code, לא מחובר).
  5. BUG-085 drift detection — **Structural**: `set(vars(Tables)) - set(live_names)`, גנרי לכל טבלה עתידית.
  6. Duplicate-option/whitespace normalization — **Structural**: `_normalize_domain_option()` גנרי, לא רשימת הוריאציות הידועות ("Real  Estate ", "SaaS   " וכו').
- **תוצאה:** 5/6 structural, 1/6 enumeration מכוון ומתועד. אין action items חדשים — האודיט עצמו הוא התוצר.
- **Merged:** לא רלוונטי — audit בלבד, אין קוד מוצר מעורב.
- **סטטוס:** ✅ הושלם — נבדק ותועד, ללא ממצאים דורשי תיקון.

### BUG-089 — Audit: סריקה רחבה ל"הבטחת המשך כוזבת" ברחבי הקוד, אחרי BUG-086/087 (09/07/2026) — ✅ Audit בלבד, המשפחה סגורה
- **תאריך:** 09/07/2026
- **דווח על ידי:** session audit — אחרי תיקון BUG-086 (anti-hallucination CREATE claims) ו-BUG-087 (fallback messages כוזבות), grep מכוון לחיפוש מופעים נוספים מאותה משפחה (טענת תהליך-המשך/סטטוס שאין מנגנון אמיתי מאחוריה) בכל הריפו, לפני מעבר ל-item הבא.
- **נבדק:** grep רחב על ניסוחי "יטופל/יישלח/יעודכן בהמשך" וכדומה על כל `*.py` (לא test files). 4 מופעים אותרו:
  1. `app.py:1864`/`core/anti_hallucination.py:500`/`:1079` — הערות קוד שמתעדות את המחרוזות **הישנות** שכבר תוקנו (BUG-087) — לא מופע חדש.
  2. `core/adapters/leads_adapter.py:274` (`_phase_label`) — `PHASE_AWAITING: "ממתין לטיפול"` — **לגיטימי**: label שנגזר מ-`phase` field אמיתי בנתונים, לא הבטחה לתהליך שלא קיים.
  3. `core/anti_hallucination.py` (אזור `__approval_queued__` pattern) — זהו ה-detection pattern עצמו (מזהה טענות כוזבות), לא מופע של הבעיה.
  4. `core/learning_engine.py:27` — `"בהמשך"` מופיע רק כמילת מפתח לסיווג טקסט היסטורי (keyword classification), לעולם לא כפלט למשתמש; `FEATURE_LEARNING_ENGINE` כבוי כברירת מחדל ממילא (ראה `core/learning_engine.py`'s תיאור ב-`CLAUDE.md`: אינרטי במכוון).
- **תוצאה:** אין מופע שלישי של המשפחה (מעבר ל-BUG-086/087). המשפחה נחשבת סגורה נכון ל-09/07/2026.
- **Merged:** לא רלוונטי — audit בלבד, אין קוד מוצר מעורב.
- **סטטוס:** ✅ הושלם — נבדק ותועד, אין ממצאים חדשים.

### BUG-090 — LeadsWriteGate: הודעת חסימה שגויה ל-update + הפרת Single-Speaker בנתיב הכשל (09/07/2026) — ✅ תוקן ומוזג
- **תאריך:** 09/07/2026
- **דווח על ידי:** המשתמש — תוייג בטעות בשיחה כ-"BUG-088" (מספר תפוס — BUG-088/089 הם שני ה-Audits מ-PR #282; המספר הפנוי הנכון הוא BUG-090).
- **מסך / מודול:** `tools/airtable_security.py::enforce_leads_write_gate()` (הודעת חסימה), נתיב הכשל אחרי approval (Single-Speaker).
- **תיאור:** אומת בפרודקשן ש-BUG-028's gate עובד נכון (חוסם `airtable_update source=agent table=Leads`) — אבל שני פגמים נלווים נצפו באותה זרימה:
  1. **הודעה שגויה ל-update:** `enforce_leads_write_gate()` מחזירה תמיד את אותה הודעה קבועה — `"❌ כתיבה ישירה ל-Leads חסומה. השתמש ב-capture_inbound_lead() בלבד."` — גם כשה-tool החסום הוא `airtable_update` (עדכון ליד קיים), למרות ש-`capture_inbound_lead()` רלוונטי רק ל-inbound create flow, לא לעדכון ליד קיים. גם דולפת שם פונקציה פנימי למשתמש.
  2. **הפרת Single-Speaker:** נצפה בפרודקשן רצף כמו: "אושר אך נכשל בביצוע... כתיבה ישירה ל-Leads חסומה. השתמש ב-capture_inbound_lead()... לא הצלחתי לבצע את הפעולה... אותה שגיאה שוב" — כלומר המשתמש מקבל כמה הודעות/שכבות (raw exception + ניסוח סוכן נוסף), לא הודעה אחת נקייה.
- **Contract Chain (בוצע, ראה גם דיון בצ'אט):** `grep -n "enforce_leads_write_gate\|כתיבה ישירה ל-Leads חסומה" tools/airtable_security.py` → הודעה אחת קבועה ב-`enforce_leads_write_gate()` (שורות 74-78), לא תלוית `tool_name` למרות ש-`tool_name` כבר מגיע כפרמטר. `grep -n "LeadsWriteGate\|airtable_update.*Leads\|source=agent" tools/dispatcher.py tools/airtable_security.py` → שני call sites נפרדים ב-`dispatcher.py` (`airtable_add`/`airtable_update`), שניהם `except LeadsDirectWriteBlocked as e: return str(e)` — ה-`str(e)` חוזר ישירות כתוצאת ה-tool, ה-agent רואה את זה ועלול לנסח עוד משפט מעליו (מקור ה-duplication).
- **Scope מאושר (מהמשתמש):** תיקון הודעה בלבד ב-`enforce_leads_write_gate()`/`tools/airtable_security.py`. **לא** לבנות `update_existing_lead()` חדש, **לא** לפתוח כתיבות Agent כלליות ל-Leads, **לא** להחליש את ה-gate עצמו — רק המחרוזת משתנה, לפי `tool_name` (create vs update), single-speaker (הודעה אחת נקייה, לא raw exception + ניסוח סוכן נוסף), בלי לחשוף שם פונקציה פנימי.
- **תיקון:** `_leads_write_blocked_message(tool_name)` חדשה ב-`tools/airtable_security.py` — `airtable_update`/`airtable_patch` מקבלים "עדכון ליד קיים דרך הצ׳אט חסום כרגע. לעדכון ליד קיים יש להשתמש במסך הלידים באפליקציה." (אין קישור TMA קונקרטי בקוד היום — הושארה הנחיה כללית, לא הומצא קישור); `airtable_add` מקבל "יצירת ליד חדש ידנית דרך הצ׳אט חסומה כרגע. לידים חדשים נוצרים אוטומטית מהודעות נכנסות." שני המסרים: בלי `capture_inbound_lead()`, בלי שום שם פונקציה פנימי, בלי suffix דיבאג (`tool=`/`source=` — נשאר רק ב-`logger.error` הקיים, לא בהודעה למשתמש). התנהגות ה-gate עצמה (מה שנחסם/מותר) לא שונתה כלל.

**Single-Speaker DoD (פגם 2 בתיאור המקורי) — נסגר בשני PRs לפי תכנון, לא side effect.** ה-DoD המקורי של BUG-090 הגדיר מההתחלה "הודעה אחת בלבד, אין double-report" כדרישה מפורשת — לדרישה הזו שני חצאים, ושניהם היו מתוכננים:
- **החצי המבני (BUG-091/PR #285):** ה-preflight ב-`app.py` מונע יצירת pending approval מלכתחילה עבור כתיבה חסומה — זה מה שמבטל את רצף "אושר אך נכשל בביצוע... אותה שגיאה שוב". יושם יחד עם תיקון ה-privilege escalation כי שניהם נגעו באותו קוד gate, אבל זה סעיף ב-DoD של הבאג הזה, לא בונוס לא-מתוכנן.
- **החצי של תוכן ההודעה (BUG-090/PR #286, כאן):** ההודעה עצמה, כשהיא כן מוצגת, היא משפט נקי אחד — בלי raw exception, בלי שם פונקציה פנימי.

ביחד, #285+#286 סוגרים את דרישת ה-Single-Speaker במלואה. אף PR לבד לא היה מספיק.
- **בדיקה:** `test_bug090_leads_gate_message.py` (18/18 חדש) — gate עדיין חוסם (create+update), הודעת update מפנה למסך הלידים, שני המסרים בלי `capture_inbound_lead()`/שם פונקציה/suffix דיבאג, create≠update, `airtable_patch` מקובץ עם update, regression על טבלאות שאינן Leads/מקורות מורשים/`airtable_get`. עודכנו assertions ב-`test_bug091_source_trust_boundary.py`/`test_bug091_preflight_no_pending_approval.py` (טקסט ההודעה השתנה, לא ההתנהגות). כל 65 קבצי `test_*.py` + `smoke_tests.py` + `test_integration.py` — ירוקים, אפס רגרסיה.
- **Merged:** ✅ כן — `main` `5338fa9` (Merge pull request #286, commit `85c08f9` + docs commit `314f0dd`). מאומת: `git log --oneline origin/main` וגם `git merge-base --is-ancestor` בפועל בסשן זה (09/07/2026).
- **Deployed/Verified בפרודקשן:** ✅ כן — ראיה חיה מהמשתמש (09/07/2026): הודעה אמיתית מ-Eli "עדכן ליד קיים אברהם ברסלר לא רלוונטי" קיבלה בפועל "❌ עדכון ליד קיים דרך הצ׳אט חסום כרגע. לעדכון ליד קיים יש להשתמש במסך הלידים באפליקציה." — התאמה byte-for-byte להודעת ה-update החדשה (`tools/airtable_security.py:84-85`, מאומת ישירות בקוד). מאשר: (א) התיקון פרוס בפרודקשן, (ב) ההודעה הספציפית-ל-update (לא ההודעה הישנה/גנרית) אכן מוצגת למשתמש אמיתי, (ג) אין `capture_inbound_lead()`/suffix דיבאג/הודעה כפולה (Single-Speaker) — משפט אחד נקי, תואם למה שנצפה. **לא ניתן לקבוע מה-screenshot בלבד** אם החסימה הגיעה דרך ה-preflight המאוחר (BUG-091, אמצע tool loop) או ה-short-circuit המוקדם (BUG-092, לפני קריאת Claude) — שניהם מפיקים בדיוק אותו טקסט. לאישור ספציפי של BUG-092 (אפס round-trip ל-Claude) נדרשים לוגים (כמו הראיה מ-20:08:46 שכבר ניתנה ל-BUG-091), לא רק תוכן ההודעה.
- **סטטוס:** ✅ תוקן, ממוזג ל-main, **מאומת בפרודקשן**.

### BUG-091 — `_source` בתוך tool_inputs עוקף את `enforce_leads_write_gate()` — privilege escalation, לא UX (09/07/2026)
- **תאריך:** 09/07/2026
- **דווח על ידי:** המשתמש — תוך כדי בקשת "no backdoor" ל-BUG-090, זיהה שהתשובה ("אין alias bypass") לא ענתה על השאלה האמיתית: שה-Agent בכלל מצליח להציע פעולה אסורה שמגיעה ל-approval לפני שהיא נחסמת.
- **קבצים:** `tools/dispatcher.py` (`dispatch_tool` — פרמטר `trusted_source` חדש), `app.py` (preflight לפני `_queue_approval` + `trusted_source` מפורש בשני call sites), `core/action_gateway.py` (`ActionContract.trusted_source` שדה חדש, `propose_action()`, `_make_dispatch_executor`), `core/lead_candidate_handler.py` (`_propose_lead_write` — `trusted_source="lead_capture"` כפרמטר, לא כ-key ב-dict) | `test_bug091_source_trust_boundary.py` (חדש), `test_bug091_preflight_no_pending_approval.py` (חדש), עדכון fixtures ב-`test_action_gateway.py`/`test_c89_preview_confirmation.py`.
- **Severity:** Critical — **privilege escalation**, לא claim-without-evidence כמו שאר תיקוני היום. `enforce_leads_write_gate("airtable_update", {"table": table}, source=_write_source)` קרא את `_write_source` מ-`inputs.get("_source", "agent")` — ו-`inputs` הוא, בשני מסלולי האישור הקיימים (EventBus הישן דרך `_queue_approval`/`_handle_approval_callback_impl`, וגם `core/action_gateway.py`'s Gateway/ledger — האחרון flag-gated כבוי כברירת מחדל אך latent), **בדיוק** ה-`tool_use.input` שקלוד יצר, נשמר ומוחזר verbatim בזמן האישור. אם קלוד כולל `"_source": "lead_capture"` בתוך ה-JSON של קריאת הכלי, זה עוקף את ה-gate.
- **Root Cause:** `_source` היה key בתוך dict משותף (`tool_inputs`) שגם קוד Python מהימן (`lead_candidate_handler.py`) וגם תוכן שה-LLM שולט בו (raw `tu.input`) יכולים לכתוב אליו — אין שום דרך להבדיל ביניהם ברגע שהם מגיעים ל-`dispatch_tool()`.
- **תיקון (מבני, לא enumeration/validation נוסף):** `_source` הופרד לגמרי מ-`tool_inputs` והפך לפרמטר Python מפורש (`trusted_source`) שרק קוד קורא מהימן יכול להעביר:
  1. `dispatch_tool(name, inputs, identity=None, trusted_source=None)` — `inputs.get("_source", ...)` הוסר לגמרי; `_write_source = trusted_source or "agent"` בשני ה-case blocks (`airtable_add`/`airtable_update`). ברירת מחדל `None`→`"agent"` — fail-closed לכל קורא שלא מעביר במפורש.
  2. `app.py` — **preflight חדש**: לפני `_queue_approval` (לא רק בתוך `dispatch_tool` בזמן ביצוע), אם `tu.name in ("airtable_add","airtable_update")` — `enforce_leads_write_gate(tu.name, {"table": ...}, source="agent")` (מקודד קשיח) נבדק **לפני** יצירת pending approval; אם חסום — `continue` בלי לקרוא ל-`_queue_approval` בכלל. שני קריאות ל-`dispatch_tool` הקיימות (`_handle_approval_callback_impl`, ה-raw tool loop) קיבלו `trusted_source="agent"` מפורש.
  3. `core/action_gateway.py` — שדה חדש `ActionContract.trusted_source: str = "agent"`, פרמטר חדש ל-`propose_action(trusted_source="agent")`, נשמר על ה-contract בזמן ה-propose (לא נגזר מ-`tool_inputs`/`normalized_payload`). `_make_dispatch_executor`'s `_executor()` קורא `contract.trusted_source` (לא `tool_inputs`) ומעביר ל-`dispatch_tool(trusted_source=...)`. **זה תוקן גם כש-`FEATURE_ACTION_GATEWAY` כבוי** — latent vulnerability מאחורי flag כבוי הוא עדיין vulnerability.
  4. `core/lead_candidate_handler.py::_propose_lead_write` — `"_source": "lead_capture"` הוסר לגמרי מ-`tool_inputs` (בשני הענפים, create/update); מועבר עכשיו כ-`trusted_source="lead_capture"` ל-`propose_action()`.
- **בדיקה:** `test_bug091_source_trust_boundary.py` (10/10 חדש) — `inputs["_source"]` מתעלם ממנו לגמרי (spoofed value לא עוקף, גם לא כש-`trusted_source` מועבר בנפרד), ברירת מחדל "agent", `ActionGateway` attack simulation (contract עם `tool_inputs["_source"]="lead_capture"` מזויף אך `trusted_source` לא הועבר → עדיין `trusted_source="agent"` על ה-contract → נחסם ב-execute), ו-regression מלא ל-`lead_capture` הלגיטימי (`trusted_source="lead_capture"` מפורש, אין `_source` key בכלל, עובד תקין). `test_bug091_preflight_no_pending_approval.py` (3/3 חדש) — מריץ את `app.run_agent()` האמיתי מקצה לקצה: Claude מבקש `airtable_update` על Leads → נחסם ב-preflight, ההודעה היא הודעת ה-gate בלבד (לא "⏳ אישור נדרש"), ו-`bus.request_approval()` **אף פעם לא נקרא** — אין pending contract נוצר בכלל. עודכנו 2 fixtures קיימים (`test_action_gateway.py`'s `_fake_dispatch_tool`, `test_c89_preview_confirmation.py`'s assertion `_source`→`trusted_source`) שהיו תלויים בחוזה הישן. כל 64 קבצי `test_*.py` בריפו + `smoke_tests.py` + `test_integration.py` — ירוקים, אפס רגרסיה.
- **Merged:** ✅ כן — `main` `df49b5e` (Merge pull request #285, commit `5f2c90f`). מאומת: `git log --oneline origin/main` וגם `git merge-base --is-ancestor` בפועל בסשן זה (09/07/2026).
- **Deployed/Verified בפרודקשן:** ✅ כן, חלקית — המשתמש דיווח לוגים אמיתיים מפרודקשן (20:08:46) המראים את ה-preflight פועל: `[LeadsWriteGate] BLOCKED direct Leads write | tool=airtable_update source=agent table=Leads` וגם `[Approval] preflight blocked Leads write before queueing: airtable_update` — מוכיח שה-DoD העיקרי (preflight חוסם לפני pending approval) פעיל בפרודקשן. תזמון הפעלה (הרצת ה-preflight מוקדם יותר, לפני סבב Claude מלא) טופל בנפרד ב-BUG-092.
- **סטטוס:** ✅ תוקן, ממוזג ל-main, אומת חלקית בפרודקשן (preflight פועל, ראה למעלה). **DoD מול המשתמש: 7/8 מכוסים בקוד+בדיקות (preflight, אין pending contract, מקור לא-נסמך על תוכן, LeadsWriteGate נשאר fail-closed, TMA/lead_capture האמיתי לא נשברים) — פריט #3 (ההודעה עצמה מפנה ל-TMA/לא מזכירה capture_inbound_lead) שייך במפורש ל-BUG-090, לא לכאן.**

### BUG-092 — BUG-091 preflight נכון אך מאוחר מדי: סבב Claude מלא לפני חסימה ודאית (09/07/2026) — ✅ תוקן ומוזג
- **תאריך:** 09/07/2026
- **דווח על ידי:** המשתמש — לוגים אמיתיים מפרודקשן (20:08:46) הראו את ה-preflight של BUG-091 פועל נכון, אך אחרי: Router כבר זיהה `Intent.UPDATE_LEAD`, Context/Business Memory נטענו, שני סבבי Claude מלאים, חיפוש `airtable_get`, ועדכון Session — רק אז החסימה קרתה. המשתמש ציין 3 חששות: עלות (טוקנים מבוזבזים), UX (המשתמש ממתין ואז נדחה), ותחושת אמינות. כשהוצע תיקון ממוקד-Leads בלבד, המשתמש דחה זאת במפורש: **"למה המיקוד הוא רק על לידס זה אותו באג לכל הטבלאות ולכל הכלים"** — ודרש מנגנון גנרי, לא enumeration פר-intent.
- **קבצים:** `core/router/deterministic_denial.py` (חדש — `ToolHint`, `INTENT_TOOL_HINTS`, `DeterministicDenial`, `check_deterministic_denial()`), `app.py` (import חדש ליד שורה 58, short-circuit חדש מיד אחרי בדיקת `EMERGENCY_STOP_AI` ולפני תחילת ה-Agent Loop) | `test_deterministic_denial.py` (חדש, 18/18).
- **Root Cause:** שתי קטגוריות חסימה ודאיות ב-100% כבר מהרגע ש-`route.intent`/`identity.role` נפתרים, לפני שה-Agent רץ בכלל: (א) שערי מקור בלתי מותנים (`enforce_leads_write_gate` — לא תלוי role/approval/תוכן, רק ב"זה נתיב ה-Agent הגולמי"), ו-(ב) שערי role שה-`tool_registry.py` מחריג לגמרי (למשל `guest`/`readonly` לכל כלי). שתי הקטגוריות היו ידועות מראש, אך המערכת המשיכה בכל מקרה עד ל-preflight הקיים (`app.py`, אמצע לולאת הכלים) — נקודה מאוחרת מדי.
- **תיקון (מבני, גנרי — לא Leads-only, לא enumeration פר-intent):** מנגנון אחד קטן ב-`core/router/deterministic_denial.py`:
  - `check_deterministic_denial(intent, identity)` — פונקציה טהורה, read-only. לא מיישמת מחדש אף לוגיקת אכיפה — קוראת ישירות ל-`tool_registry.check_allowed()` (קטגוריה ב) ול-`enforce_leads_write_gate()` האמיתית (קטגוריה א), ומחזירה `DeterministicDenial` רק כשהתוצאה כבר ודאית. אף פעם לא "מתירה" משהו — מחזירה רק "חוסמת" או `None`.
  - `INTENT_TOOL_HINTS` — טבלת hint קטנה ושמרנית: `Intent.UPDATE_LEAD`→`airtable_update`/Leads, `Intent.CREATE_LEAD`→`airtable_add`/Leads (אותו gate מדויק, אפס לוגיקה חדשה לכל שורה נוספת). Intent בלי רשומה — ממשיך ל-Agent כרגיל, ללא שינוי. **Fail-safe מפורש: hint שגוי/חסר יכול רק לדלג על אופטימיזציה מוקדמת, לעולם לא להעניק גישה ששערי האכיפה המאוחרים (preflight של BUG-091, `dispatch_tool`'s `tool_registry.enforce()`) לא היו תופסים בכל מקרה** — כי אותם שערים עצמם לא שונו כלל.
  - `app.py` — נקודת החדרה מדויקת: מיד אחרי בדיקת `EMERGENCY_STOP_AI` (אותה קונבנציה — early return לפני תחילת בניית ה-context), מותנה ב-`route.tool_allowed` (לא ב-`handler==AGENT`) כדי לא לפגוע בנתיבי RESTRICTED/CLARIFY/APPROVAL/BLOCK הקיימים שכבר חוזרים למעלה או שיש להם מנגנון נפרד משלהם.
  - שיטת עבודה: לפני כתיבת קוד המימוש, נכתב `test_deterministic_denial.py` והורץ **מול המודול שעדיין לא קיים** — נכשל כצפוי (`ModuleNotFoundError`), ורק אז נכתב `core/router/deterministic_denial.py` ו-`app.py`'s השינוי, לפי בקשת המשתמש "תכתוב ותריץ את הבדיקה קודם כתיבת קוד".
- **בדיקה:** `test_deterministic_denial.py` (18/18 חדש) — כולל: הודעת `UPDATE_LEAD`/`CREATE_LEAD` זהה byte-for-byte ל-`_leads_write_blocked_message()` האמיתית; role חסום (`guest`) מזוהה גם כש-`owner` עדיין נחסם ע"י שער המקור (מוכיח שהשער מבוסס-מקור, לא role); intent בלי hint (`CREATE_TASK`/`FIND_LEAD`) מחזיר `None` לכל role (fail-safe/no-over-block); guard מבני — כל `ToolHint` מפנה לכלי אמיתי ב-`tool_registry`; guard רגרסיה — `enforce_leads_write_gate()`/`tool_registry.enforce()` **עדיין זורקים בעצמם**, בלי תלות במודול החדש (מוכיח שהשערים המקוריים לא שונו); ו-4 בדיקות `app.run_agent()` אמיתיות מקצה לקצה (Identity/Router/Anthropic מדומים) — `UPDATE_LEAD`+`manager`/`guest` חוסמים עם **אפס** קריאות ל-Claude (`mock.call_count==0`), `UPDATE_TASK` (בלי hint) ממשיך רגיל עם קריאת Claude אחת (`call_count==1`, אין over-blocking), ו-`UPDATE_LEAD` עם `tool_allowed=False` (restricted) **לא** מופעל ע"י ה-short-circuit (נתיב restricted הקיים נשמר במלואו). הורצו גם מחדש **ללא שינוי**: `test_bug090_leads_gate_message.py` (18/18), `test_bug091_preflight_no_pending_approval.py` (3/3), `test_bug091_source_trust_boundary.py` (10/10), `smoke_tests.py` (7/7), `test_integration.py` (4/4) — כולם ירוקים, אפס רגרסיה. `python3 -m py_compile core/router/deterministic_denial.py app.py` — עבר.
- **Merged:** ✅ כן — `main` `55d7f08` (Merge pull request #287, commit `b519d50`). מאומת: `git fetch origin main` + `git merge-base --is-ancestor b519d50 origin/main` בפועל בסשן זה (09/07/2026).
- **Deployed/Verified בפרודקשן:** ✅ כן — לוגים אמיתיים מהמשתמש (10/07/2026, 00:10:29):
  ```
  [ERROR] tools.airtable_security: [LeadsWriteGate] BLOCKED direct Leads write | tool=airtable_update source=agent table=Leads
  [WARNING] app: [DeterministicDenial] leads_write_gate short-circuited before Agent | intent=update_lead tool=airtable_update role=owner user=7f464269
  ```
  שורת ה-`[DeterministicDenial]` תואמת byte-for-byte ל-`app.py:1761` (`f"[DeterministicDenial] {denial.reason} short-circuited before Agent | "`) — **זו ההוכחה הספציפית ל-BUG-092 שהייתה חסרה בראיית ה-screenshot הקודמת (BUG-090)**: מוכיחה בפועל שה-short-circuit המוקדם (לפני `build_context`/קריאת Claude) הוא זה שחסם, לא ה-preflight המאוחר של BUG-091 (שהיה מדפיס `[Approval] preflight blocked Leads write before queueing`, לא הופיע כאן). גם מוכיח `role=owner` — תואם לבדיקה #3 ב-`test_deterministic_denial.py` (השער מבוסס-מקור, חוסם גם owner).
- **סטטוס:** ✅ תוקן, ממוזג ל-main, **מאומת בפרודקשן** (כולל הוכחת timing ספציפית ל-short-circuit המוקדם, לא רק תוכן ההודעה).

### BUG-093 (LL-13) — אישור כפול (double-tap/redelivery) מבצע פעולה בלתי-הפיכה פעמיים — כבר תוקן, לא היה מתועד בלוג
- **תאריך:** 09/07/2026 — התגלה תוך התאמת טיוטת log שהמשתמש הכין מקומית (Windows path, קובץ מקומי שהכיל conflict markers `<<<<<<< Updated upstream`/`=======`/`>>>>>>> Stashed changes` בין שתי גרסאות מתנגשות). הטיוטה טענה ל-commit `7ccb4a6`/PR #183 — **שניהם לא אומתו**: `7ccb4a6` לא קיים בהיסטוריית git של הריפו הזה בכלל (`git show 7ccb4a6` → `fatal: unknown revision`), ו-`test_ll13_double_execution.py` מתגלה בפועל דרך PR #193 (merge commit `97ebe3e`, מרג' ענק שכלל גם את `BUG_AUDIT_LOG.md`/`SPEC_LL13_Pending_Approval_Unification.md` עצמם) — **לא** PR #183. הטיוטה גם מספרה את זה כ-"BUG-066", שמתנגש עם BUG-066 הקיים כבר בלוג הזה (BUG-DAILY-01). ממוספר כאן מחדש כ-BUG-093 (המספר הפנוי הבא), עם ציטוט רק לעובדות שאומתו ישירות מול `origin/main` בסשן הזה — לא הועתקו commit hash/PR number מהטיוטה.
- **דווח על ידי:** תועד במקור (ללא ID/log entry) יחד עם `SPEC_LL13_Pending_Approval_Unification.md`; זוהה כחסר תיעוד רשמי תוך סבב "התאמת טיוטה מקומית" של המשתמש.
- **מסך / מודול:** `app.py` (`_pending_approvals`, `_pending_approvals_lock`, `_handle_approval_callback_impl`), `event_bus.py` (`PendingActionsStore.pop`).
- **תיאור:** שני מנגנוני approval נפרדים (`_pending_approvals` dict ב-`app.py`, ו-`event_bus.PendingActionsStore`) עשו במקור `get()`/בדיקה ואז `del`/`pop` נפרד — חלון TOCTOU: שני אישורים כמעט-בו-זמניים לאותו מפתח (double-tap בטלגרם, Telegram callback redelivery, "כן" כפול) יכלו שניהם לראות את הרשומה הממתינה לפני שאחד מהם מוחק אותה — פעולה בלתי-הפיכה (למשל `gmail_send_draft`) מתבצעת פעמיים.
- **Severity:** High (סוג הבאג) — אך המנגנון **כבר תוקן ונמצא ב-`origin/main`** כיום; אין exposure חי.
- **תיקון (מאומת ישירות בקוד הנוכחי, לא מהטיוטה):** `app.py:94` — `_pending_approvals_lock = threading.Lock()`; `app.py:672` — `_pending_approvals.pop(chat_id, None)` תחת `with _pending_approvals_lock:` (`app.py:690`, `app.py:1434`). `event_bus.py:69-73` — `PendingActionsStore.pop(action_id)` עוטף `self._store.pop(action_id, None)` תחת `with self._lock:`. `pop()` אטומי יחיד הוא אתר-הקריאה היחיד בשני המנגנונים — אין יותר `get()`+`del` נפרד.
- **בדיקה:** `test_ll13_double_execution.py` (כבר קיים ב-`origin/main`) — הורץ מחדש בפועל בסבב זה (09/07/2026): **4/4 עברו** — אישור מקביל על `_pending_approvals` (ביצוע יחיד בדיוק), אישור שני על רשומה שכבר נצרכה (no-op), `pop()` מקביל על `PendingActionsStore` (מנצח יחיד), `EventBus.confirm()` שנקרא פעמיים (handler רץ פעם אחת בלבד).
- **מה עדיין פתוח (לא בסקופ תיעוד זה):** האיחוד הארכיטקטוני המלא לפי `SPEC_LL13_Pending_Approval_Unification.md` (טבלת `Pending_Approvals` יחידה ב-Airtable שמחליפה את שני המנגנונים הנפרדים) — **לא מומש**. זה תוקן רק ברמת race-condition בכל מנגנון בנפרד, לא איחוד.
- **Merged:** ✅ כן — קיים ב-`origin/main` נכון להיום (מאומת: `git show origin/main:app.py` מכיל `_pending_approvals_lock`, `git show origin/main:event_bus.py` מכיל `pop()` תחת `self._lock`, `git show origin/main:test_ll13_double_execution.py` קיים). מקור מדויק (PR/commit) לא אומת בוודאות — ראה הערה למעלה על אי-דיוק הטיוטה; לא נטען מספר PR ספציפי בלי אימות.
- **Deployed/Verified בפרודקשן:** לא עדיין — אין evidence של double-tap אמיתי בפרודקשן שנבדק לפני/אחרי התיקון.
- **סטטוס:** ✅ תוקן, ממוזג (קיים ב-main) — תיעוד בלבד בוצע כרגע; איחוד ה-store המלא (SPEC_LL13) נשאר פתוח כ-roadmap item נפרד.

### BUG-094 (BATCH-NAME-WINDOW-BLEED) — שני לידים בבאצ' קרובים נכתבים לאותה רשומה, עם שם שגוי
- **תאריך:** 10/07/2026
- **דווח על ידי:** המשתמש — ראיה חיה מפרודקשן: אחרי ש-BUG-058's resolver עבד נכון (`[LCH] resolve_pending_lead_preview(confirm): user=boss_hq:eliyahu` בלוג, ה-batch בוצע), שני הלידים נכתבו לאותה רשומה בדיוק (`recGqXxzRRvEoUIao` הופיע גם ב-"שמרתי" וגם ב-"עדכנתי"), ושני הלידים הוצגו עם אותו שם ("אבי יוספי" גם עבור המועמד השני, למרות ששמו האמיתי היה שונה) — כלומר שם המועמד השני "אבד" ונדרס בשם הראשון עוד לפני הכתיבה.
- **Severity:** High — data corruption אמיתי: ליד שני נמחק בפועל (הרשומה שלו לא נוצרה, הליד הראשון נדרס עם הטלפון/סיכום של השני).
- **קבצים:** `core/lead_candidate_handler.py` (`parse_batch_dictation`, `_at_find_lead`).
- **שורש (מאומת בשחזור ישיר, לא רק נטען) — 2 בעיות שילבו יחד לייצר את התסמין:**
  1. **`parse_batch_dictation()` (BUG-094 עצמו):** בונה חלון טקסט קבוע של ±60 תווים סביב כל מספר טלפון, וקורא ל-`_extract_name(window)`. `_extract_name` תמיד מחזיר את ההתאמה **הראשונה** בחלון (`.search()`/`.finditer()` order) — לא את הקרובה ביותר לטלפון עצמו. כששני בלוקי-ליד קרובים (פחות מ-120 תווים משולבים ביניהם — המקרה הנפוץ ברשימה קצרה כמו "אבי יוספי 050... אלי ישראלי 052..."), החלון של המועמד השני עדיין הכיל את השם של המועמד הראשון, ו-`_extract_name` החזיר את השם הראשון שוב. שוחזר ישירות: `parse_batch_dictation("אבי יוספי 0501112223, אלי ישראלי 0523334445")` החזיר `[{"name": "אבי יוספי", ...}, {"name": "אבי יוספי", ...}]` — שני מועמדים, אותו שם.
  2. **`_at_find_lead()` (BUG-094-B, בעיה נפרדת שהחמירה את התוצאה):** גם עם שמות תקינים, הפונקציה מטפלת ב-3 formulas לפי סדר (`AND(name,phone)` → `phone בלבד` → `SEARCH(name) בלבד`); ה-formula האחרון **לא כולל phone בכלל**. אם ה-formula הראשונים לא מוצאים כלום (ליד חדש אמיתי), אבל ה-formula השלישי מוצא רשומה עם שם דומה/זהה (במקרה הזה — הרשומה שזה עתה נוצרה למועמד הראשון, בגלל הבעיה #1), הקוד הישן היה מחזיר את `records[0]["id"]` **בלי לוודא שה-phone תואם בכלל** — כלומר גם לו השמות היו שונים אך במקרה דומים (שם נפוץ בעברית), התוצאה הייתה זהה: false match על ליד לא-קשור, וכתיבת phone/summary שגויים על גביו.
  3. **`_write_one_lead()`'s domain handling (BUG-094-C, שורש שלישי נפרד — הבעיה השלישית שהמשתמש דיווח עליה, כתובה בהתחלה כ"הערה לא-קשורה" ותוקנה בפועל):** `core/router/domain_router.py` מסווג כל הודעה שמכילה "ליד"/"lead"/"crm" כ-`RouterDomain.CRM` (`domain_router.py:43`, confidence 0.85) — הודעת batch dictation טיפוסית ("ליד חדש: ...") **תמיד** מכילה "ליד", כך ש-`resolved_route_domain` שמגיע ל-`handle_lead_candidate()` יכול להיות `"crm"` באופן לגיטימי. `_write_one_lead()` כתב את זה ישירות ל-`LeadFields.DOMAIN`/`capture_lead_event(domain=...)` — אבל `"crm"` הוא דומיין-מטא של ה-Router (כוונת ניתוב, לא ורטיקל עסקי; `RouterDomain.INTERNAL` הוא אותו סוג בעיה, מתועד במפורש בקוד עצמו כ"הנדסי/מטא — לא דומיין עסקי"), ואינו ערך חוקי בסכמת Airtable החיה (`Lead Events`' `Domain` singleSelect מאפשר רק `real_estate/import/recruiting/general` — מאומת מ-`allowed=[...]` האמיתי שהוחזר מ-Airtable, לא ניחוש). Lead Events נכשל ב-422 בפועל (shadow-state של הvalidation הפנימי שלנו רק רשם אזהרה, לא חסם את הבקשה עצמה מלהישלח ל-Airtable, ש-Airtable עצמו דחה).
- **תיקון:**
  1. `parse_batch_dictation()`: החלון של כל מועמד מוגבל כעת גם לגבולות מספר הטלפון השכן (הקודם/הבא), לא רק ל-±60 תווים קבוע — כך שחלון של מועמד אחד לא יכול לחצות ולכלול שם של מועמד אחר בכלל.
  2. `_at_find_lead()`: כשיש `phone`, רק התאמת phone מדויקת על אחת הרשומות שהוחזרו נחשבת "אותו ליד" — formula שמצא רשומות בלי אף אחת מהן תואמת phone עובר הלאה ל-formula הבא (או `None` בסוף) במקום להחזיר `records[0]` בעיוור. כשאין phone בכלל (הזרימה `needs_phone`) — ההתנהגות המקורית (name-only fallback) נשארה ללא שינוי, כי אין phone לוודא מולו.
  3. `_lead_domain_key(domain)` — פונקציית עזר חדשה, מחליפה 5 מופעים זהים של `domain if (domain and domain != "general") else "general"`: מוסיפה `"crm"`/`"internal"` (`_NON_BUSINESS_DOMAINS`) לרשימת הערכים שנופלים ל-`"general"`, לצד `""` הריק המקורי. דומיינים עסקיים אמיתיים (`real_estate`/`import`/`media`/`saas`/`finance`) לא נגעו — עוברים כרגיל.
- **בדיקה:** `test_bug094_batch_name_bleed.py` (חדש, 25/25) — שחזור מדויק של הטקסט מהפרודקשן (2 שמות נכונים ונפרדים אחרי התיקון), וריאציה עם prefix "ליד חדש:", וריאציה עם 3 מועמדים צמודים (בדיקת שרשור), regression guard לבאצ' מרווח שכבר עבד נכון קודם, regression guard ל-`parse_lead_dictation` (ליד בודד, לא נגעתי בו), 3 בדיקות ל-`_at_find_lead` (name-match עם phone לא-תואם → `None`, phone מדויק תואם → נמצא כרגיל, אין phone בכלל → fallback ל-name-only נשאר כשהיה), ו-6 בדיקות ל-`_lead_domain_key` (crm/internal → general, ריק → general, general → general ללא שינוי, דומיינים עסקיים עוברים ללא שינוי). אפס רגרסיה: `smoke_tests.py`, `core/router/test_router.py` (44/44), כל שאר `test_*.py` (חוץ מ-`test_document_converter.py`, כשל לא-קשור/קודם, זהה גם על `main` נקי).
- **PR:** ראה branch/PR של סבב זה (10/07/2026).
- **Merged:** ממתין ל-push/PR.
- **סטטוס:** ✅ שלושת השורשים (BUG-094 name-window bleed, BUG-094-B phone-blind fallback match, BUG-094-C crm/internal domain leak) תוקנו בקוד, בדיקות עברו — ממתין ל-merge+production verification. **בדיקה חוזרת בפרודקשן חייבת להראות שני `record_id` שונים** (אבי יוספי → `rec...`, אלי ישראלי → `rec...` אחר) וללא 422 על Lead Events, לפני שסוגרים סופית.

- **עדכון 10/07/2026 — הבדיקה החוזרת בפרודקשן (אחרי מיזוג PR #291) בוצעה, וחשפה שורש נוסף, נפרד: BUG-095.**

### BUG-095 (BATCH-MALFORMED-PHONE-BLOCK-BLEED) — טלפון פגום באמצע באצ' עדיין "בולע" את הבלוק השכן
- **תאריך:** 10/07/2026
- **דווח על ידי:** המשתמש — בדיקה חיה בפרודקשן **אחרי** מיזוג BUG-094 (PR #291), ולכן ראיה תקפה לגבי הקוד המתוקן, לא לפני התיקון. לוג אמיתי: 3 לידים הוכתבו ("אבי אבן 0543546354 ...", "משה אבני 05647389 ...", "שמואל גרין 0368028368 ...") אך `IngressClassifier` דיווח `candidates=2` (לא 3), ונוצרו רק 2 רשומות Leads: `reciGIBbVay9NGbSL` בשם "אבי אבן"/0543546354 (✅ נכון) ו-`recXkNgKwUKxLiyT4` בשם **"חדרים משה אבני"**/**0368028368** — שם מטושטש (מילים משורות שונות שהתמזגו) על טלפון שבפועל שייך ל-**שמואל גרין**, לא למשה אבני. גם משה אבני וגם שמואל גרין "אבדו" כזהויות נכונות.
- **Severity:** High — אותה סוג-בעיה כמו BUG-094 (data corruption: ליד אמיתי לא נוצר, טלפון של ליד אחד מיוחס לשם של ליד אחר), אך עם trigger שונה שה-BUG-094 fix לא כיסה.
- **קבצים:** `core/lead_candidate_handler.py` (`parse_batch_dictation`).
- **שורש (מאומת בשחזור מדויק של הטקסט מהלוג, לא ניחוש):** מספר הטלפון האמצעי בהודעה — `05647389` — **פגום** (8 ספרות בלבד, חסרה ספרה אחת) ולכן `_PHONE_RE` (`0\d{1,2}[-\s]?\d{7,8}`, דורש 10-11 ספרות סה"כ) **אף פעם לא זיהה אותו כטלפון בכלל** — מאומת: `_PHONE_RE.finditer()` על הטקסט המלא מחזיר רק 2 התאמות (`0543546354`, `0368028368`), לא 3. תיקון BUG-094 (חלון מוגבל לגבולות הטלפון *השכן שזוהה*) עדיין תקף רק כשיש טלפון שכן שזוהה לחסום מולו — כשאין בכלל התאמת טלפון לבלוק של משה אבני, אין גבול לחסום מולו, וכל הבלוק שלו (כולל שמו) "נבלע" לתוך החלון של המועמד הבא (שמואל גרין), ש-`_extract_name()` על החלון המורחב הזה מצא תוך כדי חצייה של שורה ("...ב4 חדרים\nשמואל...") את הרצף "חדרים משה אבני" (3 מילים עבריות רצופות שחצו ירידת שורה) כ"שם" — בדיוק ה-garbled name שנצפה.
- **תיקון:** `parse_batch_dictation()` נבנה מחדש להפעיל תחילה `_BLOCK_SEP` (regex שהוגדר כבר בקובץ אך מעולם לא נקרא בפועל — dead code) לפיצול הטקסט לבלוקים (שורה חדשה שמתחילה באות עברית / bullet / מספור / שורה ריקה) **לפני** כל חילוץ טלפון/שם. כל בלוק מעובד בנפרד לגמרי דרך `_extract_batch_candidates_from_block()` (פונקציה חדשה, מכילה את אותה לוגיקת windowing per-phone מ-BUG-094 — עדיין נחוצה לתוך בלוק בודד, למשל שורה אחת עם כמה לידים מופרדים בפסיקים) — כך שגבול-בלוק, לא רק מיקום-טלפון, חוסם bleed. אומת: `_BLOCK_SEP.split()` על הטקסט המדויק מהפרודקשן מפצל נכון ל-3 בלוקים נפרדים; כל בלוק מנותח בנפרד ("משה אבני" בלי טלפון תקף → אין candidate מהבלוק שלו, לא מזהם את השכן).
- **נבדק ונדחה כ-false lead בטעות (לא תוקן, לא צריך):** המשתמש בדק גם קלט שונה לגמרי — ייצוא צ'אט WhatsApp מועבר (`[12.9.2023, 14:25] אורי צדוק: ...`, מספר שורות פר-רשומה, שם השולח חוזר בכל header). זוהה בהתחלה כאילו הוא חושף עוד 2-3 בעיות (block-splitting שגוי על שורות המשך בעברית, חילוץ שם השולח במקום שם הליד) — **אך המשתמש תיקן**: `classify_ingress()` על הטקסט הזה מחזיר `tier=4, content_class='table', reason='log_timestamp'` (מנגנון Tier 4 hard-marker הקיים כבר, מ-BUG-064/C89-TIER4-PRECEDENCE) — כלומר קלט כזה **נחסם כבר לפני** ש-`handle_lead_candidate()`/`parse_batch_dictation()` בכלל נקראים; אין exposure בפרודקשן. אומת ישירות: `classify_ingress(text=..., source_type="text")` → `tier=4`. תיעוד בלבד, אין תיקון קוד לזה.
- **בדיקה:** `test_bug094_batch_name_bleed.py` הורחב (31/31, +6 חדשות ל-BUG-095) — שחזור מדויק של הטקסט מהפרודקשן (2 candidates נכונים, לא 3, לא מזוהמים), אימות ש"משה אבני"/"חדרים" לא מופיעים בשום candidate. כל 25 הבדיקות הקיימות של BUG-094/BUG-094-B/BUG-094-C נשארו ירוקות ללא שינוי (regression guard על ה-rewrite ל-block-based parsing). אפס רגרסיה: `smoke_tests.py`, `core/router/test_router.py` (44/44), כל שאר `test_*.py` (חוץ מ-`test_document_converter.py`, כשל לא-קשור/קודם).
- **PR:** ראה branch/PR של סבב זה (10/07/2026).
- **Merged:** ממתין ל-push/PR.
- **סטטוס:** ✅ תוקן בקוד, בדיקות עברו — ממתין ל-merge+production verification. **בדיקה חוזרת בפרודקשן (batch עם 3+ לידים, כולל טלפון פגום מכוון אחד באמצע) חייבת להראות candidates נפרדים נכונים לכל שם/טלפון תקין, ושהבלוק הפגום פשוט מדולג (לא מזהם שכן), לפני שה-batch-confirm flow המלא נחשב מאומת סופית.**

- **🔴 תיקון-טעות קריטי, 10/07/2026 — הסעיף הזה (BUG-095, וגם BUG-094 המקורי למעלה) תוקן ב-קוד מת, לא נגע בפרודקשן בכלל.** `parse_batch_dictation()`/`parse_lead_dictation()` ב-`core/lead_candidate_handler.py` — הפונקציות ש-BUG-094 וה-BUG-095 שלמעלה תיקנו — **אין להן אף קורא חי בכל הריפו** (מאומת: `grep -rn "parse_batch_dictation\|parse_lead_dictation" --include="*.py" .` מחוץ ל-`test_*.py` של הסבב הזה עצמו → אפס hits). `handle_lead_candidate()` (נקודת הכניסה האמיתית) משתמש ב-`ic.candidates` שמגיע מ-`classify_ingress()`, שקורא ל-`core/ingress_classifier.py`'s `_extract_lead_candidates()` — **מימוש כפול ונפרד לגמרי**, עם אותו באג בדיוק (חלון קבוע ±80 תווים, ללא neighbor/block clipping). שוחזר ישירות: הרצת `_extract_lead_candidates()` (המימוש החי) על הטקסט המדויק מהפרודקשן עדיין מחזירה את אותו garbled name/phone שנצפה בלוג — **אחרי** שה-"תיקון" ל-`parse_batch_dictation` כבר היה ב-`main`. כלומר: BUG-094's root ו-BUG-095 המתוארים למעלה **עדיין פתוחים בפועל בפרודקשן** נכון לרגע כתיבת התיקון הזה. `_at_find_lead`/`_lead_domain_key` (BUG-094-B/BUG-094-C) **כן** תיקנו קוד חי — הם נקראים מ-`_write_one_lead()`, שכן משמש דרך `_handle_batch`/`_handle_mixed_batch`/`_handle_single_candidate` בזרימה האמיתית, ללא תלות במקור ה-candidates. **התיקון האמיתי ל-BUG-094/095 נמצא ב-BUG-096 למטה.** לא נמחקו הפונקציות המתות — נשארות מתועדות כ-dead code, החלטה על מחיקה ממתינה לאישור המשתמש.

### BUG-096 (LIVE-PATH-BATCH-BLEED) — התיקון האמיתי ל-BUG-094/095, במקום הנכון בפועל
- **תאריך:** 10/07/2026
- **דווח על ידי:** המשתמש — הציג ניתוח עצמאי מפורט (6 ממצאים ממוספרים) על אותו לוג פרודקשן, שהוביל לגילוי ש-BUG-095 (למעלה) תוקן בקוד מת.
- **Severity:** High — data corruption אמיתי, חי בפרודקשן עד לתיקון הזה (לא BUG-094/095 שכבר "תוקנו" בטעות בקוד מת).
- **קבצים:** `core/ingress_classifier.py` (`_extract_lead_candidates`, פונקציה חדשה `_extract_candidates_from_block`), `core/lead_candidate_handler.py` (`_handle_batch`, `_handle_mixed_batch` — שימוש ב-`raw_text` per-candidate).
- **שורש:** זהה בדיוק ל-BUG-094/095 (חלון קבוע סביב טלפון, ללא גבול-בלוק/טלפון-שכן, `_extract_name_from_window()` מחזיר את ההתאמה הראשונה בחלון לא הקרובה ביותר) — אך במקום הנכון: `core/ingress_classifier.py`'s `_extract_lead_candidates()`, לא ב-`lead_candidate_handler.py`. שוחזר ואומת: `_extract_lead_candidates()` על הטקסט המדויק מהפרודקשן (לפני התיקון הזה) מחזיר `[{"name": "אבי אבן", "phone": "0543546354", ...}, {"name": "חדרים משה אבני", "phone": "0368028368", ...}]` — בדיוק ה-garbled name/phone שנצפו בלוג.
- **ממצא נוסף שהתגלה יחד (BUG-096-B — item 5 בניתוח המשתמש):** `_handle_batch()`/`_handle_mixed_batch()` קראו ל-`_write_one_lead(identity, name, phone, text, channel, domain)` עם `text` = **כל הטקסט של הבאצ' כולו**, זהה לכל מועמד — כלומר Summary/Lead Event/`lead_memory` של כל ליד בבאצ' כללו את הפרטים של *כל* הלידים האחרים בבאצ', לא רק את שלו. מאומת בקוד (לא ניחוש): `core/lead_candidate_handler.py`'s `_handle_batch`/`_handle_mixed_batch`, קריאות `_write_one_lead(..., text, ...)` העבירו את אותו `text` פרמטר-קלט ללא שינוי לכל item בלולאה.
- **תיקון:**
  1. `_extract_lead_candidates()` נבנה מחדש להפעיל `_BLOCK_SEP` (regex חדש, מיובא-בדיוק מהתיקון שכבר תוכנן ל-BUG-095, הפעם במקום הנכון) לפיצול הטקסט לבלוקים **לפני** חילוץ טלפון/שם. כל בלוק מעובד בנפרד לגמרי דרך `_extract_candidates_from_block()` (חדשה) — עדיין עם windowing per-phone *בתוך* בלוק בודד (לשורה עם כמה לידים מופרדים בפסיקים), אבל מוגבל לגבולות הבלוק, לא חוצה.
  2. כל candidate מקבל כעת גם `"raw_text"` — הבלוק המקורי שלו בלבד. `_handle_batch()`/`_handle_mixed_batch()` עודכנו להשתמש ב-`item.get("raw_text") or text` (fallback לטקסט המלא רק אם אין raw_text, לתאימות לאחור) במקום תמיד ב-`text` הגלובלי, כשקוראים ל-`_write_one_lead()`/`_propose_lead_write()`.
- **בדיקה:** `test_bug096_ingress_classifier_batch_bleed.py` (חדש, 24/24) — שחזור מדויק על `_extract_lead_candidates()` (המימוש החי בפועל) ועל `classify_ingress()` מקצה-לקצה (כולל אימות `candidates=2` תואם ללוג האמיתי), 4 regression guards לצורות-קלט שכבר עבדו נכון (comma-separated, prefixed newline, 3-way chained, spaced newline) — מורצות דרך הפונקציה החיה, לא הקוד המת, 2 בדיקות ל-`raw_text` per-block, ובדיקת end-to-end מלאה דרך `handle_lead_candidate()` המוכיחה שכל ליד נכתב עם הטקסט שלו בלבד (לא מזהם משכנים). אפס רגרסיה: `smoke_tests.py`, `core/router/test_router.py` (44/44), `test_bug077_tier3_auto_capture_gate.py`, `test_c89_raw_obs.py`, `test_c89_tier4_precedence.py`, `test_c90_structured_file_capture.py` (כל אלה משתמשים ב-`ingress_classifier`/`_extract_lead_candidates` — נבדקו במפורש), כל שאר `test_*.py` (חוץ מ-`test_document_converter.py`, כשל לא-קשור/קודם).
- **PR:** ראה branch/PR של סבב זה (10/07/2026) — אותו branch כמו BUG-095 (עדיין לא ממוזג).
- **Merged:** ✅ כן — PR #292, מוזג ל-`main` (מאומת: `git log origin/main`).
- **סטטוס:** ✅ תוקן בקוד ומוזג — ממתין ל-production verification. **בדיקה חוזרת בפרודקשן חייבת להראות: (1) candidates נפרדים נכונים ל-3+ לידים כולל טלפון פגום אחד באמצע, (2) Summary/Lead Event של כל ליד מכיל רק את הטקסט שלו, לא של לידים אחרים.**
- **החלטה פתוחה (לא בוצעה, ממתינה למשתמש):** למחוק את `parse_batch_dictation`/`parse_lead_dictation`/`_extract_batch_candidates_from_block` ב-`lead_candidate_handler.py` (קוד מת, 0 קוראים חיים) ואת `test_bug094_batch_name_bleed.py` (בודק קוד מת בלבד) — או להשאיר כתיעוד/reference. לא נמחק בסבב הזה.
- **עדכון 10/07/2026 — בדיקה חיה שנייה בפרודקשן (אחרי מיזוג BUG-096) חשפה שורש נוסף, צר יותר: BUG-097.**

### BUG-097 (NAME-TRAILING-INTENT-VERB) — פועל-כוונה ("מעוניין") נדבק לשם כשהטלפון בסוף הבלוק
- **תאריך:** 10/07/2026
- **דווח על ידי:** המשתמש — בדיקה חיה שנייה בפרודקשן, **אחרי** מיזוג BUG-096 (PR #292). קלט: 3 לידים ("משה אבני מעוניין ב3 חדרים 0546546345" / "אורי כדורי 0768767 4 חדרים" / "אלי חוטי 0768765678 דירת 5 חדרים"). תוצאה: 2 candidates (טלפון של אורי כדורי — `0768767`, 7 ספרות, קצר מדי — נדחה נכון, **ללא זיהום שכן** — BUG-096 עבד כמתוכנן!), אבל המועמד הראשון הוצג כ-"משה אבני מעוניין" במקום "משה אבני".
- **Severity:** Medium — לא data corruption בין שני אנשים (BUG-096 מנע את זה בהצלחה), אבל שם שגוי נכתב בפועל ל-Airtable (Name field מזוהם במילת-כוונה).
- **קבצים:** `core/ingress_classifier.py` (`_NAME_STOP`).
- **שורש (מאומת בשחזור מדויק):** בניגוד לדוגמת BUG-096 (טלפון מייד אחרי השם), כאן הטלפון נמצא **בסוף הבלוק**, אחרי משפט עניין: "משה אבני &nbsp; מעוניין ב3 חדרים 0546546345". `_HEBREW_NAME_RE` (`[א-ת]{2,}(?:\s+[א-ת]{2,})+`) תופס greedy את **כל** הרצף הרציף של מילים עבריות עד למילה הראשונה שאינה עברית-טהורה ("ב3" עוצר את הרצף בגלל הספרה) — כלומר "משה אבני מעוניין" נתפס כמחרוזת אחת. `_extract_name_from_window()` חותך רק מילים-עצירה **מסוף** ההתאמה שנמצאות ב-`_NAME_STOP` — ו"מעוניין" לא היה שם, אז לא נחתך. שוחזר ישירות: `_extract_lead_candidates()` על הטקסט המדויק החזיר `{"name": "משה אבני מעוניין", ...}` לפני התיקון.
- **תיקון:** נוספו לפועלי-כוונה/עניין נפוצים ל-`_NAME_STOP` (`core/ingress_classifier.py`): `מעוניין`/`מעוניינת`/`רוצה`/`רוצים`/`רוצות`/`מחפש`/`מחפשת`/`צריך`/`צריכה`/`מבקש`/`מבקשת` — אותו מנגנון חיתוך-קיים (trailing-word trim), לא regex חדש, לא שינוי מבני.
- **בדיקה:** `test_bug096_ingress_classifier_batch_bleed.py` הורחב (29/29, +5 חדשות ל-BUG-097) — שחזור מדויק של הטקסט מהפרודקשן (שם נכון "משה אבני" בלבד, טלפון נכון, אורי כדורי לא מזהם אף candidate, אלי חוטי לא מושפע). אפס רגרסיה על כל 24 הבדיקות הקיימות של BUG-096 (כולל regression guards לצורות-קלט שכבר עבדו). אפס רגרסיה: `smoke_tests.py`, `core/router/test_router.py` (44/44), כל שאר `test_*.py` (חוץ מ-`test_document_converter.py`, כשל לא-קשור/קודם).
- **PR:** ראה branch/PR של סבב זה (10/07/2026).
- **Merged:** ממתין ל-push/PR.
- **סטטוס:** ✅ תוקן בקוד, בדיקות עברו — ממתין ל-merge+production verification. **בדיקה חוזרת בפרודקשן (batch עם שם+"מעוניין ב..."+טלפון בסוף) חייבת להראות שם נקי, ללא מילת-כוונה.**

### SPEC A1 (ATOMIC-FAIL-CLOSED) — כתיבה חלקית ל-Airtable מדווחת כהצלחה מלאה, בשקט
- **תאריך:** 10/07/2026
- **דווח על ידי:** המשתמש — audit ידני (Contract Chain) שעקב אחרי בדיקת "Preview Integrity" (סעיפים א/ב, אותו סבב): איתור שכל כתיבה ל-Airtable עוברת דרך `tools/airtable_gateway.py`'s `validate_airtable_fields()`, ש-**מתעדת** שדות שנשמטו (`errors` list) אבל **אף פעם לא מחזירה אותם הלאה** — לפי התיעוד העצמי של הפונקציה: *"errors are warnings only (caller logs them)"*. `airtable_patch()`/`airtable_create()` (הקוראות היחידות) רק `logger.warning()`-ות את ה-`errors` ומ המשיכות לכתוב את מה שנשאר — הרשומה נכתבת בהצלחה, `ok=True`/record מוחזר, וההודעה שהמשתמש רואה ("✅ בוצע"/"✅ שמרתי") לא מבחינה בין "כל השדות נכתבו" ל"חלק מהשדות נשמטו בשקט".
- **Severity:** High — לא ספציפי ל-Leads/domain; משפיע על **כל** נתיב כתיבה בקוד (LCH, cmd_update, Agent tool-loop, ActionGateway) כי כולם מתכנסים לאותה נקודת-גבל יחידה.
- **קבצים:** `tools/airtable_gateway.py` (`airtable_patch`, `airtable_create`), `test_airtable_gateway.py`.
- **שורש (מאומת בקוד, לא ניחוש):** `validate_airtable_fields()` (`:80-158`) מחזירה `(clean, errors)`; כל שדה בעייתי (unknown-to-schema, forbidden, sentinel `"none"`, read-only formula, linked-record לא-תקין, invalid select-value ב-enforce mode) מוסר מ-`clean` ומתועד ב-`errors` — אבל `airtable_patch`/`airtable_create` (`:297-410` בגרסה שנבדקה) בדקו רק `if not clean: return False/None` (הכל נשמט) — לא `if dropped:` (**חלק** נשמט). כלומר payload מעורב (שדה אחד תקין + שדה אחד בעייתי) כתב את השדה התקין בהצלחה, דיווח `ok=True`, והשדה הבעייתי נעלם בלי עדות מעבר ל-log.
- **תיקון (SPEC A1 — "השינוי הקטן ביותר", ללא נגיעה ב-`validate_airtable_fields` עצמה):** שתי הפונקציות הציבוריות (`airtable_patch`/`airtable_create`) מחשבות כעת `dropped = set(fields.keys()) - set(clean.keys())` (על `fields` **אחרי** normalize, **לפני** validate — namespace אחיד, לא מול ה-payload המקורי שעשוי לכלול aliases) — אם `dropped` לא ריק, הכתיבה **נחסמת כליל** (fail-closed אטומי: הכל-או-כלום, לא partial write). ה-diff מחושב אצל הקורא, לא אצל ה-validator — `validate_airtable_fields()` עצמה לא שונתה כלל (חתימה, טיפוס החזרה, לוגיקה פנימית — הכל זהה).
- **מקרה קצה קריטי שנבדק ואומת:** coercion (למשל `{"Owner": "recABC123"}` → `["recABC123"]`, שדה linked-record) נשאר תחת **אותו מפתח** ב-`clean` — לכן **לא** נספר כ-`dropped` ולא חוסם כתיבה. אומת ב-T3 (למטה) — זה בדיוק התרחיש שגרסה נאיבית יותר (`if errors: return False`) הייתה שוברת בטעות.
- **בדיקה:** 5 טסטים חדשים נוספו ל-`test_airtable_gateway.py` (T1-T5, בסך הכל 32/32 בקובץ): T1 (שדה לא-מוכר מעורב עם שדה תקין → חסום, אין קריאת httpx), T2 (ערך select לא-תקין ב-enforce mode מעורב עם שדה תקין → חסום, אין httpx), T3 (**הקריטי**: coercion של linked-record מ-string בודד → **הצלחה**, httpx כן נקרא, הערך נשלח כרשימה), T4 (שדה read-only מעורב עם שדה תקין → חסום, אין httpx — `"טמפרטורה"` נבדק ולא `"tier"`, כי `tier` הפך לשדה כתיב ב-2026-06-15 לפי ההערה הקיימת ב-`test_airtable_gateway.py:90`), T5 (payload תקין לגמרי → ללא שינוי התנהגות, הצלחה כרגיל). אפס רגרסיה: `test_select_value_validation.py` (18/18), `smoke_tests.py`, `core/router/test_router.py` (44/44), כל שאר `test_*.py` (חוץ מ-`test_document_converter.py`, כשל לא-קשור/קודם). אומת גם: `grep` מול `origin/main` מראה חתימות הפונקציות (`bool` / `dict | None`) זהות ב-100% — אין שינוי חוזה, רק שינוי התנהגות (fail-closed יותר).
- **PR:** ראה branch/PR של סבב זה (10/07/2026).
- **Merged:** ממתין ל-push/PR.
- **סטטוס:** ✅ תוקן בקוד, בדיקות עברו — ממתין ל-merge+production verification. **A2 (structured error propagation דרך `airtable_tools.py`/`decision_ports.py`/`providers/airtable_shim.py`/`core/reasoning_ports.py`) נשאר עבודה נפרדת, לא כלול כאן** — A1 רק מונע כתיבה חלקית שקטה; לא מוסיף עדיין ערוץ תקשורת ל-*למה* נכשל חזרה למשתמש/לקורא (זה הממצא #5 מ-audit ה-Preview Integrity שנשאר פתוח).
- **עדכון 10/07/2026 — Merged + production-verified (PR #296, `0ed89e2`; PR #297, `4b9ae60`):** `git log origin/main` מאשר את שתי המיזוגים; `git show origin/main:tools/airtable_gateway.py` מאשר `dropped = set(fields.keys()) - set(clean.keys())` קיים בפועל בשתי הפונקציות (`:320`, `:383`) על main. **אימות production חי בוצע** דרך `verify_a1.py` (סקריפט חד-פעמי, נמחק בסבב הזה אחרי השימוש — ר' PR #297) שרץ בפועל ב-Render Shell (10/07/2026):
  - **מאושר לחלוטין:** payload מעורב (שדה תקין + שדה בעייתי) עבור שדה לא-מוכר, linked-record פגום, ושדה read-only/formula — בשלושת המקרים `dropped` יצא לא-ריק וה-`httpx.post`/`httpx.patch` **לא נקראו כלל** (HTTP_BLOCKED), גם ב-CREATE וגם ב-PATCH. זה בדיוק ההתנהגות שה-fix נועד לייצר.
  - **ממצא נוסף (לא ספציפי ל-SPEC A1 עצמה, אך התגלה תוך כדי):** ערך select לא-חוקי לשדה `Leads.status` (`{"Name": "...", "status": "__invalid__"}`) **לא נבדק בכלל** ע"י `validate_airtable_fields()` — לא ב-CREATE טהור/מעורב ולא ב-PATCH מעורב. `errors=[]`, `clean` כולל את הערך הפגום, וקריאת HTTP אמיתית הייתה יוצאת (נמנעה רק ע"י ה-monkey-patch של הסקריפט עצמו, לא ע"י קוד הפרודקשן). **חשוב לדייק:** הריצה לא הבחינה בוודאות בין `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE="off"` לבין `"shadow"` (הסקריפט הדפיס רק את שורת ה-`[AUDIT:gateway]` האחרונה, לא כל שורות ה-log שנתפסו — ייתכן ששורת אזהרת `[SelectValueValidation:SHADOW]` יצאה ולא הוצגה) — אבל בשני המצבים ההתנהגות החיצונית זהה: אין חסימה, ה-HTTP יוצא. המסקנה המעשית זהה בכל מקרה.
  - **למה זה לא "לתקן עכשיו":** לפי הקוד (`tools/airtable_gateway.py:170-184`) ולפי §3.5 ב-`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` (שורת "Airtable Schema Refresh"), `enforce` על value-validation פועל בפועל רק כש-`RuntimeSchemaProvider.get_table_contract(table)["mode"] == "full"` **לאותה טבלה/שדה ספציפית** — זה אומת פעם אחת, בבדיקה מבוקרת, על שדה אחר (`Domain`, טבלה אחרת), ואז הוחזר במפורש ל-`shadow`. **מעולם לא אומת בנפרד עבור `Leads.status`.** הדלקת `enforce` גורף לפני שמאשרים `mode="full"` ל-`Leads` עלולה שלא לחסום כלום בפועל (אם ה-mode עדיין `"name_only"`) ולתת תחושת ביטחון שגויה. **לכן: אין להדליק `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE=enforce` (בפרט לא עבור `Leads`) עד שמאמתים `get_provider().get_table_contract("Leads")["mode"] == "full"` בנפרד** (למשל דרך `tools/check_airtable_schema_runtime.py`). נרשם כתלות מפורשת ב-§3.5 כדי שלא "ייעלם" בין סשנים.
  - **ראיות:** `git log origin/main -3` → `4b9ae60`/`0ed89e2`; transcript מלא של ריצת `verify_a1.py` ב-Render Shell (10/07/2026, זמין בהיסטוריית השיחה); רשומת record אמיתית שנוצרה ונמחקה בהצלחה במהלך הבדיקה (`recvhM9bm3Wbbfkln`, Leads, `CLEANUP: ... -> True`).

### SPEC Preview Content Fix (Sites #3+#4) — preview ריק/גולמי לפני אישור פעולה
- **תאריך:** 10/07/2026
- **דווח על ידי:** המשתמש — SPEC מוכן (`_describe_tool_call`/`approval_response`), מ-audit "Preview Integrity" קודם.
- **קבצים:** `app.py` (`_describe_tool_call`, `_format_field_value` חדש, `_SENSITIVE_FIELD_KEYS` חדש, `approval_response`, `CONFIRMATION_SUFFIX` חדש), `test_preview_content_fix.py` (חדש).
- **Site #3 — `_describe_tool_call()`:** `airtable_add` הציג רק **שמות** שדות בלי ערכים; `airtable_update` לא הציג כלום מעבר ל-`record_id`/`table` — משתמש לא יכול היה לדעת בפועל מה ישתנה לפני אישור. תוקן: שני הענפים מציגים כעת `key: value` לכל שדה, עם `_format_field_value()` שממסך שדות רגישים וחותך ערכים ארוכים מ-80 תווים.
- **Contract Chain (נדרש לפני מימוש, בוצע):**
  1. `grep -n "_describe_tool_call\|_SENSITIVE_FIELD_KEYS" app.py` → קורא יחיד: `_queue_approval()` (`:781`), עם `dict(tu.input)` **גולמי מ-Claude, לפני כל ולידציה** (`app.py:1980`, ליד ההערה "never read from tu.input... which Claude fully controls").
  2. `grep -rn "phone|sender_id|memory_key|tenant_id|token" airtable_schema.py` **וסריקה רחבה יותר** (`ContactFields`, וכן חיפוש שיטתי אחר "טלפון"/"אימייל"/"כתובת" וכו') העלה ממצא לא-צפוי: `ContactFields.PHONE = "טלפון"` ו-`ContactFields.EMAIL = "אימייל"` (טבלת "אנשי קשר (Contacts)") הם שמות שדה **בעברית מלאה** — רשימת ה-`_SENSITIVE_FIELD_KEYS` המקורית (4 מפתחות אנגליים בלבד מה-SPEC הראשוני) הייתה **מפספסת אותם לגמרי**, כלומר טלפון/אימייל של איש קשר היו מוצגים גולמית ב-preview אישור. תוקן: `_SENSITIVE_FIELD_KEYS` כולל כעת גם `"טלפון"`, `"אימייל"`, `"email"` (עקביות), ו-`"external_id"` (אותה קטגוריה של מפתח-פנימי כמו `sender_id`/`memory_key`/`tenant_id`).
  3. `inputs.get("fields", {})` **אינו** מובטח להיות `dict` — מגיע מ-`tu.input` הגולמי (סעיף 1), בלי ולידציה קודמת. נוספה הגנת `isinstance(fields, dict)` בשני הענפים (`airtable_add`/`airtable_update`) כדי שקלט לא-תקני מ-Claude לא יקריס את בניית ה-preview (`.items()` על לא-dict היה מעיף `AttributeError`).
- **⚠️ ממצא רחב יותר, לא תוקן כאן — item בתור:** העובדה שרשימת `_SENSITIVE_FIELD_KEYS` המקורית פספסה שדה עברי לגמרי מרמזת שהבעיה שיטתית, לא חד-פעמית. סריקה מהירה (`grep "^class.*Fields"` + חילוץ קבועים עם תווים עבריים ב-`airtable_schema.py`) העלתה **6 מתוך 38 מחלקות Field עם שמות שדה בעברית, 45 קבועי שדה בעברית בסך הכל**: `ContactFields` (טופל בסבב הזה), `DealFields`, `TaskFields` (`"כותרת המשימה"`), `DeadlineFields` (`"שם המשימה"`, `"סטטוס"`), `LearningFields`, `ApprovalsFields` (`"מזהה הקשר"`/`CONTEXT_ID`, `"נתוני הקשר"`/`CONTEXT_DATA` — עלולים להכיל payload/מזהה פנימי, לא רק תוכן עסקי). **לא נסקר לעומק אילו מתוך ה-45 הם באמת PII/מזהה-פנימי (בניגוד לתוכן עסקי רגיל כמו "שם העסקה"/"סכום")** — סריקה זו רק סופרת breadth, לא assessment. **פעולה נדרשת (רשומה ב-§3.5, לא בוצעה):** audit שיטתי מלא — לעבור על כל 45 השדות, לסווג כל אחד (PII/מזהה-פנימי מול תוכן עסקי לגיטימי), ולעדכן `_SENSITIVE_FIELD_KEYS` בהתאם — כדי לא לגלות עוד שדה חסר בפרודקשן בעתיד, כמו שקרה כאן עם `ContactFields.PHONE`.
- **Site #4 — `approval_response()`:** נוסף `CONFIRMATION_SUFFIX` (הבהרה שהפרטים המדויקים ייקבעו בזמן האישור בפועל) לסוף שתי תבניות ה-preview הקיימות. **לא** נוגע בארכיטקטורת ה-"הרץ שוב" עצמה (Contract Chain מ-10/07/2026 קבע שזו החלטת עיצוב מכוונת — cost/latency + context freshness — לא נפתחה מחדש כאן, לפי scope מפורש ב-SPEC).
- **בדיקה:** `test_preview_content_fix.py` (חדש, 23/23) — ערכי שדה מוצגים, מיסוך "phone"/"טלפון"/"אימייל", חיתוך ערך ארוך, `airtable_update` מציג שדות משתנים (רגרסיה מ-ריק), הגנת non-dict `fields` לא מקריסה, `gmail_send_draft`/`calendar_create_event`/`sheets_append` ללא שינוי, `CONFIRMATION_SUFFIX` מופיע ב-preview, אחסון ה-pending entry (text/domain/channel) ללא שינוי. אפס רגרסיה: `smoke_tests.py`, `core/router/test_router.py` (44/44), `test_a32_enforcement.py` (6/6), `python3 -m py_compile app.py`.
- **PR:** ראה branch/PR של סבב זה (10/07/2026).
- **Merged:** ממתין ל-push/PR.
- **סטטוס:** ✅ תוקן בקוד, בדיקות עברו — ממתין ל-merge+production verification.

### BUG-098 (STALE-FALSE-SUCCESS-VIA-FOLLOWUP-SUBSTRING) — הודעת "✅ בוצע" כוזבת, נשלחה פעמיים ברצף, ליד חדש לא נוצר בכלל
- **תאריך:** 10/07/2026
- **חומרה:** 🔴 **קריטי** — לא רק missed-lead בודד. תגובת הצלחה כוזבת נשלחה **פעמיים ברצף לאותה הודעת משתמש חוזרת**: אלי שלח "צור ליד חדש גיל חביב..." ב-16:24, קיבל `✅ כל הלידים מהרשימה נשמרו בהצלחה: משה אבני מעוניין, אלי חוטי` (batch לא-קשור מוקדם יותר באותו יום), חשד שמשהו לא תקין ושלח שוב — וקיבל **את אותה הודעת "✅" הכוזבת שוב, מילה במילה**. מנקודת מבט המשתמש אין שום איתות שמבחין בין "בוצע בהצלחה" לבין "המערכת חוזרת על עצמה בטעות" — שני המקרים נראים זהים כלפי חוץ. זה מחריף את הסיווג משמעותית מעבר ל"ליד לא נוצר": המשתמש ניסה לתקן בעצמו וקיבל אישור-שווא חוזר, בלי שום דרך לדעת שמשהו נכשל.
- **דווח על ידי:** המשתמש — לוגי פרודקשן (16:23-16:24) + תמלול שיחת Telegram מצורף.
- **קבצים:** `core/lead_candidate_handler.py` (`_handle_batch_followup`, `_FOLLOWUP_WORDS`, `handle_lead_candidate`), `session_store.py` (`_load_from_db`, `_find_best_session_in_db`, `last_lead_candidate_batch` — אין TTL).
- **שורש (מאומת — קוד + רשומת Airtable חיה, לא ניחוש):**
  1. `_FOLLOWUP_WORDS = {"ומה", "השאר", "שאר", ...}` (`core/lead_candidate_handler.py:1041`) נבדק ב-`_handle_batch_followup()` (`:1085-1086`) עם `any(w in lower for w in _FOLLOWUP_WORDS)` — **substring match, לא word-boundary**. אומת בפועל: `"ומה" in "...קומה שלישית...".lower()` → `True`. המילה "קומה" (ק־ו־מ־ה) מכילה את "ומה" (ו־מ־ה) כשלוש אותיותיה האחרונות — ביטוי נדל"ן שכיח לחלוטין ("קומה שלישית", "קומה 2" וכו') מפעיל בטעות branch שנועד רק ל"ומה עם השאר?".
  2. `handle_lead_candidate()` (`:656-666`) קורא ל-`_handle_batch_followup()` **ראשון, לפני** `classify_ingress()`/Tier gating/כל ניסיון לחלץ שם או טלפון מההודעה החדשה. כשהיא מחזירה string, `handle_lead_candidate()` מחזיר אותו מיידית — שום קוד אחר בפונקציה לא רץ.
  3. הפונקציה נקראת מ-`app.py:1773-1789` (שלב "3.6"), **לפני** ה-Router-driven Agent loop (`Handler.AGENT`/`Handler.APPROVAL` dispatch, `:1799+`). כש-`handle_lead_candidate()` מחזירה reply, `run_agent()` חוזר מיד — מסביר את "POST /telegram 200" תוך פחות משנייה מ-`[Route] ... handler=agent`, ואפס לוגי Claude/tool.
  4. `session["last_lead_candidate_batch"]` (`_save_batch_state`, `lead_candidate_handler.py:1047-1071`) נכתב פעם אחת אחרי `_handle_batch()` **ואין לו TTL/flag "resolved"/ניקוי בכלל** — בניגוד ל-`pending_lead_preview` ו-`active_lead_candidate` שיש להם TTL מפורש של 1800 שניות (`session_store.py:264-276, 298-313`). לכן batch summary שנכתב פעם אחת נשאר "חי" ללא הגבלת זמן, וכל הודעה עתידית עם "ומה"/"שאר" כ-substring "צורכת" אותו מחדש.
  5. **אימות ישיר מול Airtable** (Session record `rec3YS5Zcr2FenX7z`, נשלף חי דרך Airtable MCP): `state.last_lead_candidate_batch.per_lead` מכיל בדיוק `["משה אבני מעוניין"→recW8lw2SxrCH9dse, "אלי חוטי"→recwFDw8UoxjnyMyP]`, `original_message_text` זהה מילה-במילה לטקסט הבדיקה של BUG-096/BUG-097 (אותו יום, מוקדם יותר). `createdTime` של הרשומה: 01/07/2026 (9+ ימים), `Updated At`: 10/07/2026 02:09 — רשומה ותיקה שממשיכה להצטבר state, לא רשומה טרייה.
  6. **גיל חביב מאושר כלא-נוצר**: כש-`_handle_batch_followup()` מחזירה reply, שום קוד לא מגיע ל-`classify_ingress()`/`_extract_name`/`_extract_phone`/`_at_find_lead`/`_write_one_lead`/`propose_action` עבור ההודעה החדשה — אין tool attempt (מוצלח או כושל), אין job מקביל, אין retry ממתין. ההודעה נבלעה במלואה לפני שהגיעה לכל קוד שיכול היה ליצור אותו.
- **ממצא נלווה, נפרד — Session selection לא-דטרמיניסטי (לא הגורם הישיר כאן, אבל risk אמיתי):** `_load_from_db`/`_find_best_session_in_db` (`session_store.py:449-451, 480-482`) קוראים ל-`airtable_get_records` **בלי `sort` מפורש** ובוחרים `records[0]` (`logger.warning("...using first")`) — סדר ברירת המחדל של Airtable אינו מובטח כ"החדש ביותר". טבלת Sessions (אומת מול הסכימה החיה) **אין לה שדה Status כלל** — אין דרך לסנן רשומות "done"/"resolved" ברמת ה-formula, וגם `_find_best_session_in_db` לא נעול תחת `_create_lock` (בניגוד ל-`get_or_create`) — פוטנציאל race בין workers. במקרה הזה הרשומה שנבחרה הזדמן שהייתה עדכנית ורלוונטית, כך שזה לא הגורם לתקרית — אבל זה מנגנון-סיכון נפרד שיכול לגרום לתקריות דומות/גרועות יותר.
  **הישנות נוספת, מאומתת (12/07/2026, אותו לוג שאימת BUG-099b.1 בפרודקשן):** `[SessionStore] load sender=7228089151 found_count=18 -- using first: rec3YS5Zcr2FenX7z` — 18(!) רשומות Session לאותו sender, עדיין נבחרת הראשונה בלי sort. **אומת שלא זו הסיבה לתוצאה בבדיקה הזו** (ה-tier=5/no_lead_candidates המקורי היה נכון ללא תלות ב-session שנבחר) — עדיין לא תוקן, לא BUG-ID נפרד, זו אותה בעיה בדיוק שכבר תועדה כאן, פשוט הישנות עם found_count גבוה יותר (18 לעומת פחות קודם) — ראייה נוספת שזה מצטבר ולא נעלם מעצמו.
- **פער נוסף שהתגלה (לא תוקן, רק מתועד):** אין correlation ID עקבי דרך inbound→session→tool→outbound — `update_id`/`message_id` של Telegram לא נרשמים ברמת INFO, כך שלא ניתן להוכיח אוטומטית 1:1 בין webhook ל-outbound reply (רק היקש מטיימינג).
- **בדיקה:** לא נוספה עדיין — **root cause מאומת, קוד לא שונה**. Contract Chain בוצע במלואו (6 סעיפים) לפני כל שינוי קוד, לפי בקשת המשתמש.
- **PR:** #301, ממוזג ל-`main` (commit `165bcee`, מאושר: `git log origin/main`).
- **Merged:** ✅ כן.
- **סטטוס:** ✅ **VERIFIED IN PROD** — קוד ממוזג (`core/lead_candidate_handler.py:1041-1053,1096`, `_FOLLOWUP_WORD_PATTERN` word-boundary regex) **וגם אומת חי בפרודקשן**: הודעות עם "קומה חמישית"/"קומה שנייה" (10/07/2026, 18:10-18:16) **לא** הפעילו יותר את חטיפת ה-batch הישן ("✅ כל הלידים מהרשימה נשמרו... משה אבני...") — המשיכו כראוי ל-Router (`intent=create_lead confidence=0.95`) ואילך. 16/16 טסטים, כולל negative-test (regression מוכח בהסרת התיקון). **המשך החקירה של אותן הודעות חשף שורש נפרד, נרחב יותר — ר' BUG-099 למטה.**

### BUG-099 (LEAD-EXTRACTION-INTEGRITY) — חילוץ שם/טלפון שגוי בדיקטציית ליד של הבעלים, נתונים שגויים נכתבים בפועל ל-Airtable
- **תאריך:** 10/07/2026
- **חומרה:** 🔴 **גבוה** — לא "false success" (כמו BUG-098) אלא כתיבה אמיתית עם נתונים שגויים, **אושרה ובוצעה בהצלחה** דרך ActionGateway. שם ליד אמיתי הופך לתיאור נכס ("חדרים קומה ראשונה") בשדה `Name`.
- **דווח על ידי:** המשתמש — בדיקות production חיות (10/07/2026, 18:10-18:16) אחרי מיזוג BUG-098, כולל production log + רשומת Airtable אמיתית.
- **קבצים:** `core/ingress_classifier.py` (`_extract_name_from_window`, `_HEBREW_NAME_RE`, `_NAME_STOP`, `_candidate_confidence`, `_extract_candidates_from_block`, `_BLOCK_SEP`) — **לא** `core/lead_candidate_handler.py`'s `_extract_name`/`parse_lead_dictation`/`_PREFIXED_NAME_RE`, שהם קוד מת (0 קוראים, מתועד במפורש בדוקסטרינג של `_extract_lead_candidates()` ב-`ingress_classifier.py:267-270` — "אל תתקן שם בטעות שוב", אזהרה שכבר נכתבה בעקבות BUG-096). `core/router/deterministic_denial.py` (`check_deterministic_denial`, קשור לתסמין ה-"blocked" — ר' סעיף נפרד למטה).
- **שורש #1 — חלון חילוץ מעוגן לטלפון, לא לשם (מאומת, שוחזר בקוד חי + ברשומת Airtable אמיתית):**
  `_extract_candidates_from_block()` בונה חלון של **±80 תווים סביב הטלפון בלבד** (`ingress_classifier.py:320-322`), ו-`_extract_name_from_window()` מחזירה את רצף המילים העבריות **הראשון** שנמצא בתוך אותו חלון — בלי שום העדפה בין "נראה כמו שם" ל"נראה כמו תיאור נכס". כשתיאור נכס ארוך יושב בין השם לטלפון, השם פשוט **מחוץ לחלון**. אומת ישירות מול רשומה אמיתית שנוצרה בפרודקשן — `recRvK6hFTNgyj8ag` (Leads, נוצרה 15:10:42 UTC 10/07/2026, דרך Airtable MCP): `Name="חדרים קומה ראשונה"`, `summary="צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים קומה ראשונה   065726763"` — הטקסט המקורי חושף שהמבנה היה בדיוק "שם ... תיאור-נכס-ארוך ... טלפון", ו-`_NAME_STOP` (`ingress_classifier.py:188-207`) **לא כולל אף מילת-תיאור-נכס** (לא "קומה", לא "חדרים", לא סדרות מספר-קומה) — רק ערים/רחובות/פעלי-עניין כבר מכוסים שם.
  **אישור נוסף עם payload סינתטי מקביל** (לפני שהרשומה האמיתית נמצאה): `"צור ליד חדש יעל רייס מעוניינת בדירת 4 חדרים ... קומה ראשונה טלפון 0657267639"` → `candidates=[{"name": "לה מאוד ונוף פתוח לים ומטבח משופץ לגמרי וחניה תת קרקעית צמודה קומה ראשונה", ...}]`, **`tier=1, confidence=1.00`** — כלומר עם `FEATURE_AUTO_CAPTURE=ON` (כבוי כברירת מחדל, `feature_flags.py:53`) זה היה נכתב אוטומטית בלי preview בכלל; גם עם הדגל כבוי (המצב הנוכחי), ה-preview עצמו מציג את השם השגוי למשתמש.
- **שורש #2 — תלות במבנה שורות/סדר, לא רק בתוכן (reproduction מלא, לא השערה):**
  | קלט | תוצאה | הסבר |
  |---|---|---|
  | Multi-line (שם\nטלפון X\nעניין+תיאור) | `candidates=[]`, Tier 5, `no_lead_candidates` | `_BLOCK_SEP` (`:216`) מפצל ב-`\n` ל-3 בלוקים נפרדים — הטלפון מבודד בבלוק שאין בו שום רצף-שם, השם בבלוק אחר בלי טלפון. כל בלוק מעובד בנפרד לגמרי (BUG-096 logic) — אין קרוס-בלוק. |
  | Single-line, תיאור-נכס **לפני** הטלפון (עם/בלי פסיק — לא משנה) | `name="חדרים בקומה חמישית"` | תיאור הנכס נמצא בתוך חלון ±80 סביב הטלפון, השם לא — אותו שורש #1. |
  | Single-line, תיאור-נכס **אחרי** הטלפון | `name` נכון | השם נמצא בתוך החלון, התיאור לא. |
  **תיקון לדיווח המקורי:** הבדיקה שדיווחה שהפסיק הוא הגורם המכריע ל"single-line" (`"...0736637363, מעוניין..."` → שם שגוי) **לא שוחזרה בדיוק כפי שתוארה** — הרצתי `"יוסי יהלום טלפון 0736637363, מעוניין בדירת 4 חדרים בקומה חמישית"` וקיבלתי `name="יוסי יהלום"` (**נכון**). מה שבפועל קובע הוא **הסדר** (תיאור-נכס לפני הטלפון מול אחרי), **לא** נוכחות הפסיק — אומת בהרצה ישירה של 4 וריאציות (עם/בלי פסיק × תיאור-לפני/אחרי), שתי הווריאציות עם תיאור-לפני נכשלות זהה (עם ובלי פסיק), שתי הווריאציות עם תיאור-אחרי מצליחות זהה (עם ובלי פסיק). Multi-line נכשל בדיוק כמדווח (`candidates=[]`).
- **DeterministicDenial — מאומת כשכבת-ניסוח, לא gate נפרד (חשד ל"BUG-100" מבוטל):** `core/router/deterministic_denial.py:54-90`, `check_deterministic_denial()` — מנגנון **קיים-מראש**, לא קשור ל-BUG-099/098, שרץ ב-`app.py:1841-1849` (שלב "5.1", **לפני** Claude נקרא בכלל) עבור `Intent.CREATE_LEAD`/`Intent.UPDATE_LEAD`: קורא ל-`enforce_leads_write_gate("airtable_add", {"table": "Leads"}, source="agent")` בוודאות (`:80-88`) ומחזיר הודעת חסימה ידידותית אם זו הייתה נחסמת בכל מקרה. **דטרמיניסטי לגמרי, לפי תיעוד המודול עצמו** ("מנבא מה שער מאוחר היה עושה... לעולם לא ניחוש"). כשל LCH לחלץ candidate תקין (שורש #1/#2 למעלה) גורם ל-`handle_lead_candidate()` להחזיר `None`, מה שמאפשר להגעה לשלב 5.1 עבור הודעת `create_lead` — **אין שער שני, אין race, אין מנגנון נסתר**: זו אותה `enforce_leads_write_gate()` שכבר תועדה ב-BUG_AUDIT_LOG, רק עם ניסוח ידידותי במקום שגיאה גולמית. אין צורך ב-Contract Chain נפרד לזה.
- **נזק אמיתי שכבר קיים בפרודקשן:** `recRvK6hFTNgyj8ag` (Leads) — `Name="חדרים קומה ראשונה"`, phone="065726763" תקין, **אושר ונכתב בהצלחה** דרך ActionGateway (contract, אושר ע"י הבעלים). דורש תיקון/שחזור ידני — ליד אמיתי (יעל רייס) קיים בפועל תחת שם שגוי. מצטרף לרשומות שכבר תועדו כדורשות ניקוי (audit נפרד, לא בסקופ קוד).
- **תצפית פתוחה, לתיעוד בלבד — לא נחקרה עדיין:** שלוש בדיקות דומות של אותו סוג הודעה הפיקו שלושה ערכי `domain` שונים (`finance`, `general`, `crm`) על פני מספר סבבי בדיקה. ייתכן קשור ל-session state שיורש domain ישן, ייתכן תלוי-regex בזיהוי domain מתוכן ההודעה. עדיפות נמוכה יחסית ל-BUG-099 עצמו — נרשם ב-§3.5 כ-item נפרד.
- **בדיקה:** לא נוספה עדיין — Contract Chain הושלם, מימוש טרם בוצע.
- **PR:** לא נפתח עדיין.
- **Merged:** לא.
- **סטטוס:** 🟡 **BUG-099a קוד+טסטים מוכנים (ממתין ל-PR+production verification), BUG-099b/c טרם התחילו.** תוכנית מימוש מפוצלת (לא כגוש אחד), נרשמת ב-§3.5:
  - **BUG-099a (✅ קוד+טסטים מוכנים):** הרחבת `_NAME_STOP` (`core/ingress_classifier.py:205-217`) עם 24 מילות תיאור-נכס — Contract Chain קצר (5 שורות, `_NAME_STOP` לא משותף עם עותק מת ב-`lead_candidate_handler.py`, מאומת ב-grep), `test_bug099a_name_stop_extension.py` (חדש, 9/9: T1 reproduction מדויק של `recRvK6hFTNgyj8ag` דרך `summary` field, T2, 2 control cases, isolation check; sanity-check מוכיח שהטסטים תופסים רגרסיה — 5/9 נכשלים בלי התיקון). Regression מלא: `test_bug096_ingress_classifier_batch_bleed.py` (29/29), `test_bug098_followup_word_boundary.py` (16/16), `core/router/test_router.py` (44/44), `smoke_tests.py` — כולם ירוקים, כנדרש במפורש (שינוי בקובץ משותף עם BUG-096/097 גם אם "קטן").
  - **BUG-099b — ✅ תוקן בקוד, בדיקות עברו (12/07/2026, ראה רשומה מלאה למטה):** הרחבת חיפוש השם מעבר לחלון ±80-התווים-סביב-הטלפון (למצוא את "יעל רייס" בפועל, לא רק לדחות תיאור-נכס).
  - **BUG-099c — ✅ תוקן בקוד, בדיקות עברו (12/07/2026, ראה רשומה מלאה למטה):** fallback form כש-LCH לא מצליח לחלץ אבל ה-Router בטוח שזו כוונת create_lead — לא reuse של `core/lead_buffer.py` (מחובר לזרימת `capture_inbound_lead` החיצונית, לא ל-LCH כלל, אומת בקוד). מומש כ-clarification (שאלת "מה שם הליד?"), לא fallback-form קלאסי — ראה DoD המלא + BUG-106 (קדם-תנאי) ברשומות הנפרדות.
    **ראיה חיה מדויקת (12/07/2026, 03:51:59, אותו לוג שאימת את BUG-099b.1):** `"צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"` (ללא שם) → כעת (אחרי 099b.1) `LCH` מדלג נכון (`Tier 5 — not a lead dictation, skip`), אבל `Router` עדיין קובע `intent=create_lead confidence=0.95` ומגיע ל-`DeterministicDenial` שמחזיר את הודעת החסימה השגויה-הקשר: `"יצירת ליד חדש ידנית דרך הצ׳אט חסומה כרגע"` — **המערכת הבינה נכון שזו כוונת יצירת-ליד, ורק לא מצאה שם**, אבל התגובה מנוסחת כאילו הבקשה עצמה נדחתה/אסורה (אותו mechanism כמו BUG-090/092), לא כאילו חסר רק פרט אחד.
    **ההתנהגות הרצויה שהוגדרה (לא מומשה עדיין):** כש-`Intent.CREATE_LEAD` בביטחון גבוה + `handle_lead_candidate()` מחזיר `None`/Tier 5 (לא נחסם ע"י gate של-Leads, אלא כי לא זוהה candidate כלל) → הודעת **הבהרה**, לא דחייה: `"זיהיתי בקשה ליצור ליד ואת מספר הטלפון, אבל לא מצאתי שם. מה שם הליד?"` — לא reuse של `DeterministicDenial`'s ניסוח (שמיועד למקרה אחר לגמרי: חסימת source/role, לא "חסר פרט"). דורש להבחין בין שני מצבים ששניהם היום נופלים לאותו branch: (א) הבקשה נחסמה במכוון (gate אמיתי) מול (ב) הבקשה לא הובנה/הושלמה (LCH לא מצא candidate) — ראה גם ההבחנה המקבילה שנשאלה על 099b.1 עצמו (שאלת מחקר #2 שם).

---

## §3.5 — BUG-102/103/104 (Family F: מנגנון קיים אך לא מחובר לחיים)

> רישום ראשוני בלבד (`DOC-20260712-WA0002`). Contract Chain לכל שלושתם כבר בוצע במחקר קודם (`DOC-20260712-WA0001`) — ראה שם לפירוט מלא. מה שנרשם כאן הוא מיפוי המצב + שאלת-ההחלטה הפתוחה לכל אחד, **לא** תיקון. אינם חוסמים ואינם תלויים ב-BUG-101a/b/c — נתיבים מבניים נפרדים לגמרי (אומת). משפחה: Family F ("מנגנון קיים אך לא מחובר") — מצטרפים ל-BUG-058 כמופע רביעי/חמישי/שישי של אותה תבנית.

### BUG-102 — IngressEnvelope: `normalized_text` נבנה ונזרק בנתיב הודעת-טקסט
- **תאריך:** 12/07/2026
- **קבצים:** `core/ingress_envelope.py:113-163` (המבנה), `app.py:1737-1793` (הנתיב שבו זה קורה)
- **שורש (מאומת בקוד):** `build_telegram_envelope`/`build_whatsapp_envelope` נבנים, `envelope.validate()` רץ (`app.py:1745`) — אבל `_safe_route(user_text, ...)` (`app.py:1754`) ו-`handle_lead_candidate(identity, user_text, ...)` (`app.py:1790-1793`) ממשיכים לעבוד על `user_text` המקורי, לא על `envelope.normalized_text`. רק נתיב הקובץ (C90, `app.py:2249-2287`) באמת קורא מה-envelope עצמו.
- **Severity:** Low-Medium — בלתי-מזיק היום (`normalized_text=text` ורבטים, אז הערך זהה בפועל), אבל bug מבני-שקט: שום trim/normalize עתידי ב-`build_telegram_envelope`/`build_whatsapp_envelope` לא ישפיע על הנתיב הזה, אלא אם מישהו יחליף גם את `_safe_route`/`handle_lead_candidate` לקרוא מה-envelope.
- **שאלת החלטה (לא Contract Chain — כבר קיים):** לחבר את `_safe_route`/`handle_lead_candidate` לקרוא מ-`envelope.normalized_text`, או לתעד במפורש ש-C91 מיועד ל-C90 (קבצים) בלבד ולסגור את השאלה?
- **סיכון לתיקון:** בינוני — שינוי בנתיב חי בפרודקשן (Telegram/WhatsApp טקסט), דורש regression מלא.
- **תוקן:** לא — רישום בלבד.
- **PR:** לא נפתח.
- **Merged:** לא.
- **סטטוס:** 🟡 רישום בלבד — ממתין להחלטת תיקון (לחבר / לתעד-כמכוון).

### BUG-103 — EvidenceTrace: נבנה, נרשם, אף פעם לא נשמר
- **תאריך:** 12/07/2026
- **קובץ:** `core/ingress_envelope.py:183-335`
- **שורש (מאומת בקוד):** `record_classification()` נקרא בפועל בייצור (`core/router/capture_router.py:72,79`, `app.py:2260,2277`) — אבל docstring המודול עצמו (`core/ingress_envelope.py:63-74`) מצהיר במפורש "NOT YET DONE — intentional, not forgotten": כל caller בונה Trace, קורא ל-`record_classification()`, עושה `logger.debug()`, והאובייקט יוצא מ-scope. אין Airtable/DB backing store. `latest_trace()`/`next_attempt()` (`:314-335`) מיועדים לעבוד על היסטוריה שכרגע אף פעם לא נשמרת מעבר לקריאה בודדת.
- **Severity:** Low — תשתית audit-trail שלמה-בקוד שלא מייצרת שום דבר ניתן-לשליפה. שונה מ-BUG-102: כאן זו לא "אותה תוצאה במקרה" אלא תכנון מוצהר-חלקי (documented gap בקוד עצמו) שלא הושלם.
- **שאלת החלטה:** האם זה P1 (נדרש ל-observability שכבר התבקש בהצעת "שכבת ההבנה הכללית", סעיף 7) או שיישאר דחוי במכוון עד שהשכבה הרחבה יותר תוחלט?
- **תוקן:** לא — רישום בלבד.
- **PR:** לא נפתח.
- **Merged:** לא.
- **סטטוס:** 🟡 רישום בלבד — ממתין להחלטה (P1 persisted store / דחייה מכוונת).

### BUG-104 — Core Reasoning Activation Program (לשעבר: ReasoningEntity/leads_adapter/decision_adapter לא מחוברים לחיים)
- **תאריך:** 12/07/2026 (נרשם) · 16/07/2026 (שם התוכנית עודכן + Phase 1 החל)
- **שם קנוני של התוכנית:** **Core Reasoning Activation Program**. זהו שם *תוכנית ההפעלה* בלבד — לא שינוי שמות מודולים. `core/reasoning_entity.py`/`core/reasoning_ports.py`/`core/reasoning_engines.py`/`core/adapters/leads_adapter.py` והשם ההיסטורי-טכני **"Core Reasoning Layer" (F22)** נשארים כפי שהם.
- **היררכיית התוכנית:**
  ```
  BUG-104 — Core Reasoning Activation Program
  └── Phase 1 — Leads Read-Only Reasoning Projection
  ```
  **Phase 1 — Leads Read-Only Reasoning Projection:** חיבור ראשון, קריא-בלבד, של Core Reasoning Layer (F22) הקיים למסלול חי — projection בשם `"reasoning"` על `GET /api/leads/<lead_id>` בלבד. אין mutation, אין persistence, אין Decision Hub / chat / Telegram / WhatsApp / approval / ActionGateway. דגל תלת-מצבי עצמאי `FEATURE_CORE_REASONING_LEADS_STATE` (`off`/`shadow`/`on`, ברירת מחדל `off`). ראה `core/leads_reasoning_projection.py` + `test_bug104_leads_reasoning_projection.py`.
- **קבצים:** `core/reasoning_entity.py`, `core/reasoning_engines.py`, `core/adapters/leads_adapter.py`, `core/adapters/decision_adapter.py`
- **שורש (מאומת בקוד):** `leads_adapter.py` (עם `entity_type=ENTITY_LEAD`, `:56,107`) — **אפס קוראים חיצוניים** בכל הריפו מעבר ל-`smoke_tests.py`/`core/reasoning_ports.py` (הגדרת port, לא caller אמיתי). `decision_adapter.py` כן מחובר לחיים (`cmd_decision.py:445`, `append_reasoning_block`) — אבל `FEATURE_DECISION_HUB` = OFF כברירת מחדל (`feature_flags.py:75`), כלומר "חי" רק תיאורטית.
- **חשיבות מיוחדת:** זה הכי קרוב במבנה למה שהצעת "שכבת ההבנה הכללית" מבקשת — `PHASE_COLLECTING`/`PHASE_BLOCKED`/`PHASE_REVIEW`/`PHASE_AWAITING`/`PHASE_DECIDED`/`PHASE_CLOSED` (`core/reasoning_entity.py:34-39`) ≈ RESOLVED/NEEDS_CLARIFICATION/REJECTED שההצעה מגדירה. **לפני שממשיכים בכל דיון על "לבנות Understanding Contract חדש" — זו הבדיקה שקובעת אם צריך לבנות בכלל, או רק לחבר+להדליק flag.**
- **Severity:** Medium — לא באג פעיל (אין נזק תפעולי), אבל relevant-prior-art מהותי שיכול לשנות החלטת ארכיטקטורה רחבה אם יתעלמו ממנו.
- **שאלת החלטה:** נבדק בנפרד מ-102/103 כי התשובה כאן משפיעה על ההחלטה הארכיטקטונית הרחבה ("שכבת הבנה כללית"), לא רק על תיקון-נקודה. נדרשת החלטה: להרחיב/לחבר `leads_adapter.py` ולהדליק `FEATURE_DECISION_HUB` באופן מבוקר, או לבנות מנגנון נפרד ולהשאיר את זה כקוד-מת מתועד.
- **תוקן:** לא — רישום בלבד.
- **PR:** לא נפתח.
- **Merged:** לא.
- **סטטוס:** 🟡 רישום בלבד — ממתין להחלטה ארכיטקטונית רחבה (חלק מדיון "שכבת ההבנה הכללית", עדיין פתוח — ר' הבהרה למטה).

**הבהרה — הדיון על "שכבת ההבנה הכללית" עדיין פתוח:** רישום שלושת ה-BUGים האלה **אינו** החלטה לבנות/לא-לבנות את ההצעה הרחבה (Interaction Envelope + Understanding Contract + PendingAction Store). זו הפרדה מכוונת: קודם ממפים כל מנגנון קיים בנפרד (מה קיים, מה שבור, מה מחובר — ראה `DOC-20260712-WA0001`), ורק אז חוזרים לשאלת הארכיטקטורה השלמה עם עובדות מלאות על כל שלושת המרכיבים.

**תכנית פעולה מעודכנת (12/07/2026):** נרשם רשמית ב-`ROADMAP.md`'s F-section כ-**U1 — Understanding Layer Architecture Decision**, עם קישור חוסם מפורש ל-UX-01 (Unified BOSS Experience — גם נרשם 12/07/2026, ראה ROADMAP.md). סדר התלות הרשמי מעכשיו: ייצוב Pending Approval flow (✅ הושלם — BUG-PENDING-APPROVAL-B) → סגירת ההחלטה הארכיטקטונית כאן (U1) → רק אז UX-01. שתי האופציות שנותרו על השולחן (מ-"שאלת ההחלטה" למעלה) לא השתנו — עדיין ממתינות להחלטת בעלים, לא טכני.

---

### עדכון 17/07/2026 — Phase 1 + Phase 1.1 + TMA Lead Event Bridge: מומשו, מוזגו, **אומתו בפרודקשן end-to-end**

מאז הרישום המקורי למעלה (12/07), התוכנית התקדמה בפועל דרך 3 PRs ממוזגים (ראה `CHANGE_CONTROL_LOG.md` C112/C115/C118 לפירוט מלא של כל אחד):
- **Phase 1** (PR #354/#357, `71f04fb`/`08ad671`) — `GET /api/leads/<lead_id>`'s read-only `"reasoning"` projection, `FEATURE_CORE_REASONING_LEADS_STATE` (off/shadow/on).
- **BUG-104 TMA Lead Event Bridge** (PR #360, `0a0c331`) — `core/lead_event_writer.write_tma_lead_event()`, מחווט ל-`tma_api.py::patch_lead/set_lead_outcome` ול-`tools/approval_actions.py::tma_write()`. סוגר בדיוק את הפער שה-"שורש" למעלה תיאר: לפני ה-bridge, אף כתיבת-ליד מה-TMA לא יצרה Lead Event, כך שה-projection תמיד קרא `events.count=0` — נכון מבחינה טכנית, אך ריק-מדגם, לא ראיה שהמנגנון עובד.

**אימות פרודקשן (דווח ע"י המשתמש, ליד `recI5JAgcGc07DlOa`, דומיין `recruitment`):**

לפני ה-bridge: `events.count = 0` (כל ליד, ללא יוצא מן הכלל — אין Lead Event אחד שנוצר אי-פעם מ-TMA).

אחרי ה-bridge, לאחר `patch_lead`/`set_lead_outcome` אמיתיים על הליד הזה מה-TMA:
```
events.available = true
events.count = 2
engine.degraded = false
errors = []
state = REVIEW
confidence = 0.2
```

שתי רשומות ה-Lead Events שנוצרו, מאומתות ישירות (לא רק דרך ה-projection):

| | Summary | Message | Domain | Channel | Event Type | Lead |
|---|---|---|---|---|---|---|
| אירוע 1 | `TMA lead_patch` | `lead_patch: status='high_confidence'` | `recruitment` | `tma` | `other` | `recI5JAgcGc07DlOa` |
| אירוע 2 | `TMA lead_outcome` | `Business Outcome='meeting_scheduled ', status='active'` | `recruitment` | `tma` | `other` | `recI5JAgcGc07DlOa` |

זה מוכיח את כל השרשרת בפועל, לא רק בקוד: TMA lead update → Lead Event נוצר → Lead link נכון → domain נכון (`recruitment`, מ-`Leads.domain`, לא project_slug) → channel נכון (`tma` הליטרלי, לא `identity.channel`) → BUG-104 קורא את האירועים → מנוע ה-reasoning צורך אותם (state/confidence מחושבים, לא ברירת-מחדל).

**Read path (אומת באותו סבב, PR #365):** פתיחת אותו ליד ביצעה 3 קריאות — `Leads/<id>` + `Interaction Log` + `Lead Events` (האחרונה קיימת כי ל-ליד הזה יש 2 אירועים מקושרים בפועל). זה **לא** סתירה להערכה הקודמת של "2 קריאות ל-ליד ללא אירועים" (ראו PR #365 audit) — אלא אישור: הערכת ה-2 חלה על ליד ריק-אירועים; הליד הזה הוא הראשון שנבדק שבאמת יש לו אירועים, ולכן מפעיל את קריאת ה-Lead Events השלישית, כמתוכנן. סה"כ הזרימה המלאה (Projects Hub → domain → ליד) אומתה ב-7 קריאות (לא 6) — מוסבר ומצופה.

**⚠️ הערה פתוחה, לא אומתה כאן:** הדיווח לא ציין את מצב `FEATURE_CORE_REASONING_LEADS_STATE` בזמן הבדיקה (`shadow` היה מספיק כדי לחשב ולתעד ללוג; רק `on` מצרף `"reasoning"` לתגובת ה-API בפועל). אם הבדיקה בוצעה מול תגובת ה-API עצמה (לא לוג בלבד) — הדגל היה `on` בזמן הבדיקה. יש לוודא מהו מצב הדגל הנוכחי ב-Render **אחרי** הבדיקה (חזרה ל-`off`, נשאר `on`, או `shadow`) לפני כל הצהרת "production activation" — היעדר אימות כזה כאן אינו הצהרה שהדגל פעיל כברירת מחדל.

**הסטטוס הרשמי (17/07/2026):**
- BUG-104 Phase 1 runtime: **VERIFIED IN PROD**
- BUG-104 Phase 1.1 linked-event path: **VERIFIED IN PROD**
- TMA Lead Event Bridge: **VERIFIED IN PROD**
- Active recruitment-domain producer: **VERIFIED IN PROD**
- Domain propagation: **VERIFIED**
- Projects Hub read optimization (PR #365): **VERIFIED IN PROD**

**מה עדיין לא הוכרע:** מצב `FEATURE_CORE_REASONING_LEADS_STATE` הנוכחי בפרודקשן (ראו הערה פתוחה למעלה); ה"החלטה ארכיטקטונית רחבה" המקורית (U1, למעלה) על חיבור `leads_adapter.py`/`FEATURE_DECISION_HUB` **עדיין לא הוכרעה** — האימות הזה מוכיח שהצנרת הטכנית עובדת קצה-לקצה, לא שההחלטה הארכיטקטונית הרחבה נסגרה. השלב הבא המתוכנן: Phase 2A — Current State Policy, כ-Audit+SPEC בלבד, ללא קוד.

---

## BUG-101 (umbrella) — ייבוא ייצוא-WhatsApp: כשל מצטבר בגבולות הודעה — ✅ VERIFIED IN PROD (12/07/2026)

- **תאריך:** 12/07/2026
- **משפחה:** Family A (upstream) — לא הרחבה של BUG-096/097/099b כפי שהונח במקור; זו ההנחה (גבולות-בלוק נכונים) שמתבררת כשגויה על קלט מסוג ייצוא-צ'אט. 099b נשאר חסום עד לאימות פרודקשן של BUG-101 (לא רק merge).
- **ראיה:** באצ' production אמיתי, 5/5 רשומות שגויות. Record IDs: `rec62b86WqBpaWPaG`, `rec0n8JxF4m1wMBOt`, `recxNHP1uzw7ip4N1`, `reczrNXFy5BvwRLme`, `recrzwkBQwdWBv6HW`.
- **Contract Chain:** בוצע ואומת מול `origin/main` (`fdd1a6f`) לפני מימוש — ראה תשובות המחקר בשיחה (3 שאלות grep-anchored).
- **מצב:** מפוצל ל-3 חלקים (a/b/c), כולם ממומשים באותו commit/branch (לא ניתן לתקן חלקית — כל השלושה נכשלים בו-זמנית כדי לשחזר את התסמין המלא).

### BUG-101a — Tier-4 hardening מול תווי כיווניות (RLM/LRM)
- **קובץ:** `core/ingress_classifier.py` — `_is_tier4`/`_TIMESTAMP_RE`
- **שורש (מאומת בהרצה ישירה):** תו RLM/LRM בודד (`‎`/`‏`, artifact נפוץ בהעתקה מטלפון — כמו `"[נייד] ‏ +972 54-211-6211 ‏"` בעדות המקורית) בתוך סוגריים `[DD.MM.YYYY, HH:MM]` **שובר לחלוטין** את `_TIMESTAMP_RE`/`_WHATSAPP_EXPORT_RE` — מאומת: `_is_tier4("[12.9.2023,‏ 14:25]‏ ...")` → `(False, "")` לפני התיקון, בזמן שהגרסה הנקייה (בלי RLM) כן תופסת נכון.
- **תיקון:** `_strip_bidi_controls()` חדשה (`ingress_classifier.py:54-58`) — `re.sub` על `[‎‏‪-‮⁦-⁩]` (LRM/RLM + embedding/override/isolate marks), נקראת **פעם אחת** בתחילת `_classify_ingress_core()`, לפני Tier-4 gate ולפני כל regex אחר — לא תוקן per-regex, כדי שכל השכבות הבאות (Tier-4, `_BLOCK_SEP`, `_extract_lead_candidates`, `_SENDER_LINE_RE`) יראו תמיד את אותו טקסט נקי.
- **בדיקה:** `test_bug101_whatsapp_export_bleed.py` T1-T5 — מתעד את ההתנהגות השבורה של `_is_tier4()` הגולמי (עדיין קיימת בכוונה — הפתרון הוא strip-לפני-קריאה, לא תיקון ה-regex עצמו), ומאמת ש-`classify_ingress()` המלא (שכן עושה strip) תופס Tier 4 נכון גם עם RLM מוטבע.

### BUG-101b — `_BLOCK_SEP` מודע לגבול-הודעה של ייצוא-צ'אט
- **קובץ:** `core/ingress_classifier.py`, שורה ~247 (לפני התיקון)
- **שורש (מאומת בשחזור ישיר):** אף אחד מ-4 התנאים הקיימים לפיצול-בלוק לא זיהה `[תאריך, שעה] שם:` כתחילת הודעה חדשה (לא מתחיל באות עברית, אין שורה ריקה/בולט/מספור לפניה) — כל הבלוק נבלע לתוך הבלוק הקודם. שוחזר: הרצת `_extract_lead_candidates()` הישן על הטקסט המדויק מהפרודקשן החזירה בדיוק את חמשת הפלטים השגויים (`"אורי צדוק"`/0583290628, `"לחזור אחרי החגים"`/0527118045 של דב אטינגר, `"לחזור מיד אחרי החגים"`/0527163148 של אליאב לוי, `"עומד להתקשר"`/0533175204, ושמואל נעלם לגמרי — הטלפון שלו כבר ב-`seen_phones`).
- **תיקון:** `_CHAT_EXPORT_TIMESTAMP`/`_CHAT_EXPORT_HEADER` חדשים (`ingress_classifier.py:232-239`, sub-pattern משותף גם ל-101c) — `_BLOCK_SEP` קיבל אלטרנטיבה חמישית: `\n(?=` + `_CHAT_EXPORT_HEADER` + `)`, המזהה `[DD.MM.YYYY/DD/MM/YYYY, HH:MM(:SS)] שם:` כגבול-בלוק לגיטימי.
- **⚠️ שיתוף תשתית — regression מלא בוצע כנדרש:** אותו קוד ששימש BUG-096/097/098/099a — `test_bug096_ingress_classifier_batch_bleed.py` (29/29), `test_bug097` (כלול באותו קובץ), `test_bug098_followup_word_boundary.py` (16/16), `test_bug099a_name_stop_extension.py` (9/9), `core/router/test_router.py` (44/44), `smoke_tests.py` — כולם ירוקים, אפס רגרסיה.
- **בדיקה:** `test_bug101_whatsapp_export_bleed.py` T6-T8, T12-T17 — הטקסט המלא מהפרודקשן מפיק כעת בלוקים נפרדים נכונים ל-6 ההודעות המקוריות; דב אטינגר/שמואל/ירמיהו ישורון נכתבים עם השם והטלפון הנכונים שלהם; שמואל (שאבד לגמרי בפרודקשן) נשמר כעת נכון בהופעתו הראשונה.

### BUG-101c — `_SENDER_LINE_RE` שרידות לקידומת timestamp
- **קובץ:** `core/ingress_classifier.py`, שורה ~234 (לפני התיקון)
- **שורש (מאומת בהרצה ישירה):** מעוגן ל-`^` (תחילת שורה) בלבד — קידומת `[timestamp] ` לפני שם-השולח שוברת את העיגון לגמרי. אומת: `_SENDER_LINE_RE.search("[12.9.2023, 14:25] אורי צדוק: ...")` → `None`, בזמן ש-`"דני: 050..."` (בלי קידומת) כן נתפס. התוצאה: "אורי צדוק" (כותרת-שולח מצוטטת בתוך ייצוא מועבר) לא הוכר כשורת-שולח ונכתב בפועל כשם-ליד.
- **תיקון:** `_SENDER_LINE_RE` קיבל קידומת אופציונלית (`(?:` + `_CHAT_EXPORT_TIMESTAMP` + `\s*)?`) לפני ה-capture group הקיים של שם+נקודתיים — הפורמט הישן ("דני:", בלי קידומת) ממשיך לעבוד זהה לגמרי.
- **בדיקה:** `test_bug101_whatsapp_export_bleed.py` T9-T11 — "דני: 050..." (רגרסיה על ההתנהגות הקיימת) וגם "[12.9.2023, 14:25] אורי צדוק: ..." (המקרה החדש) שניהם נתפסים נכון; "אורי צדוק" לא מופיע יותר כשם-מועמד באף candidate.

**ממצא צדדי, מפורשות מחוץ ל-scope (לא תוקן כאן):** טלפון בפורמט בינלאומי עם מקפים פנימיים מרובים (`"+972 54-211-6211"`, המספר של אליאב לוי בעדות המקורית) לא תואם את `_PHONE_RE` כלל — המועמד שלו נשמט בשקט (Family C: לא-ברור → השמטה שקטה) במקום להיכתב שגוי. השמטה שקטה בטוחה יותר מזיהום, אבל זהו פער נפרד, לא תוקן ב-101a/b/c ולא בסקופ ה-DoD שהתבקש.

- **PR:** #304 (`claude/table-incorrect-names-6chfvb` → `main`), פתוח 12/07/2026 — **✅ מוזג**.
- **Merged:** ✅ כן — `main` `74193db` (Merge pull request #304). מאומת: `git fetch origin main` + `git merge-base --is-ancestor 74193db origin/main` → exit 0 (12/07/2026).
- **Deployed בפרודקשן:** ✅ כן — `74193db`, 12/07/2026 02:02 (Render deploy hash אושר ע"י המשתמש מול הדשבורד).
- **Verified בפרודקשן — בסיס האימות (מתועד במלואו, לא רק merge status):**
  1. PR #304 מוזג ל-`origin/main`, deploy live מאושר (`74193db`, 12/07/2026 02:02).
  2. **Grep-anchored confirmation על `origin/main` עצמו** (לא worktree מקומי, `git checkout -B ... origin/main` בוצע לפני האימות) — `git show origin/main:core/ingress_classifier.py` מאשר קיום בפועל של `_strip_bidi_controls` (101a), `_CHAT_EXPORT_TIMESTAMP`/`_CHAT_EXPORT_HEADER` ב-`_BLOCK_SEP` (101b) וב-`_SENDER_LINE_RE` (101c) — שלושתם קיימים ומחוברים.
  3. **אימות התנהגות** — `test_bug101_whatsapp_export_bleed.py` (19/19) הורץ מחדש נגד ה-worktree המסונכרן ל-`origin/main`'s `74193db` בדיוק (לא נגד commit מקומי ישן): קריאה ישירה ל-`_extract_lead_candidates()` על הטקסט האמיתי מהתקרית משחזרת נכון — דב אטינגר/שמואל/ירמיהו ישורון נכתבים עם שם+טלפון נכונים; "אורי צדוק"/"אחרי החגים"/"עומד להתקשר" לא מופיעים יותר כשמות-רפאים.
  4. **הערה מפורשת לגבי מה שלא נבדק:** אימות-חי דרך הודעת-צ'אט אמיתית **אינו ישים במבנה הנוכחי** — Tier-4 (טבלה/CSV/export) מיירט טקסט בפורמט הזה תמיד, ללא flag, בכוונה (`BUG-C89-TIER4-PRECEDENCE`). זו לא פרצה באימות אלא עדות שגייט-בטיחות נפרד עובד כמתוכנן — הבדיקה בסעיף 3 (קריאה ישירה לפונקציית החילוץ) היא השקילה התקפה היחידה במבנה הזה.
- **סטטוס:** ✅ **VERIFIED IN PROD** — 101a+101b+101c מוזגים, deploy מאושר, grep-anchored confirmation על `origin/main` עצמו, ואימות התנהגות מלא מול הקוד החי. **099b נפתח כעת** (ראה רשומה נפרדת למטה) — התלות שנקבעה מראש מולאה.

**BUG-105** (פורמט טלפון בין-לאומי עם מקף, נשמט בשקט) נשאר רשום בנפרד, לא דחוף, **לא חלק מהסגירה הזו**.

---

## BUG-105 — פורמט טלפון בין-לאומי עם מקף — נשמט בשקט (לא זוהם)

- **תאריך:** 12/07/2026
- **משפחה:** Family C (קלט לא-חד-משמעי → השמטה שקטה בלי דגל) — אותה משפחה כמו "אורי כדורי" (ראה `LEAD_CAPTURE_QUALITY_AUDIT` הקודם).
- **מקור:** נמצא כפער שיורי, מחוץ ל-scope, תוך כדי מימוש BUG-101a/b/c — מאומת ע"י `test_bug101_whatsapp_export_bleed.py` (הרצה ישירה מראה שאליאב לוי, עם טלפון `"+972 54-211-6211"` בעדות המקורית, לא מופיע כ-candidate כלל אחרי התיקון).
- **קובץ:** `core/ingress_classifier.py` — `_PHONE_RE`
- **שורש:** `_PHONE_RE` (`(?:0\d[-\s]?\d{3}[-\s]?\d{4,5}|0\d{2}[-\s]?\d{7}|[\+]?972[-\s]?\d{8,9})`) מאפשר מפריד יחיד (`[-\s]?`) רק מיד אחרי ה-"972" הבינלאומי — אבל "+972 54-211-6211" ממשיך עם מקפים נוספים בתוך רצף הספרות עצמו (`54-211-6211`), שלא נתפס ע"י `\d{8,9}` (דורש רצף ספרות רציף). התוצאה: הטלפון לא מזוהה בכלל, ה-candidate לא נוצר.
- **Severity:** נמוכה — **אין זיהום** (לא נכתב ערך שגוי לשום שדה), רק אובדן-שקט של מועמד לגיטימי. שונה מהותית מ-BUG-101 (שם נכתב ערך שגוי בפועל לרשומת Airtable אמיתית).
- **תוקן:** לא — רישום בלבד, לא דחוף.
- **PR:** לא נפתח.
- **Merged:** לא.
- **סטטוס:** 🟡 רשום, לא דחוף — ממתין לתעדוף מול שאר התור (099c/102/103/104). **DoD כשמגיעים אליו:** Contract Chain קצר (בידוד, בדומה ל-099a/101a) + regression על `test_bug101_whatsapp_export_bleed.py`'s suite הקיים + test עם הפורמט הספציפי (מקפים פנימיים מרובים בטלפון בינלאומי).

---

## BUG-099b (NAME-WINDOW-SEGMENTATION) — שחזור שם מחוץ ל"ראשון-שנמצא" בתוך החלון, לא רק דחיית תיאור-נכס — ✅ VERIFIED IN PROD (12/07/2026)

- **תאריך:** 12/07/2026
- **תיאום מפורש שבוצע (נדרש לפני מימוש, DoD §1):** אומת מול BUG-096/097/101b — 099b **לא** נוגע ב-±80-חלון-סביב-הטלפון, בגזירת neighbor-phone, או ב-`_BLOCK_SEP` בכלל. השינוי היחיד הוא **איך בוחרים שם בתוך match שכבר תחום נכון** — לכן לא יכול לפתוח מחדש bleed שכבר נסגר. נבדק ישירות (ראה regression למטה): batch עם 2 מועמדים, פועל-כוונה טרails, וגבול-הודעה של ייצוא-צ'אט — כולם עדיין מבודדים נכון.
- **קבצים:** `core/ingress_classifier.py` — `_extract_name_from_window()`
- **שורש (מאומת בשחזור ישיר, לא ניחוש):** `_HEBREW_NAME_RE` מחזיר **רצף רציף אחד** של מילים עבריות (נשבר רק ע"י ספרות/פיסוק — לא ע"י מילות-עצירה). ב-`"צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים..."` הרצף `"צור ליד חדש יעל רייס  מעוניינת בדירת"` הוא match **אחד** (אין ספרה/פיסוק בין "חדש" ל-"יעל"), כש-"ליד"/"חדש" (מילות-עצירה) יושבות **בתוך** אותו match, בין קידומת-הפקודה לשם האמיתי, ו-"מעוניינת" (מילת-עצירה מ-BUG-097) מיד אחריו. הלוגיקה הקודמת (BUG-099a) חתכה מילות-עצירה רק **מהסוף**, ודחתה את כל ה-match אם נותרה מילת-עצירה **בכל מקום** — כך שהרצף כולו (כולל "יעל רייס") נדחה, ולא רק הקטע הבעייתי. שוחזר ישירות: `_extract_lead_candidates()` על `recRvK6hFTNgyj8ag`'s טקסט המקורי החזיר `[]` (0 candidates) לפני התיקון, לא `[{"name": "יעל רייס", ...}]`.
- **שאלת עיצוב (DoD §3) — הוכרעה:** **לא** להרחיב את חלון ה-±80 (מסוכן, עלול להחזיר cross-message bleed — ראה אזהרת ה-handoff). **במקום זאת:** לשנות את אסטרטגיית החיפוש **בתוך** אותו match/חלון — מילות-עצירה עכשיו **מפצלות** את הרצף לסגמנטים (כמו separator, לא רק trim-מהסוף), והסגמנט **הארוך ביותר** נבחר. מבודד את "יעל רייס" מתוך הרצף הגדול יותר, במקום לדחות את כולו.
- **תיקון:** `_extract_name_from_window()` נבנה מחדש — במקום `while words and words[-1] in _NAME_STOP: pop()` + `if any(w in _NAME_STOP...): continue`, מילות הרצף מפוצלות לרשימת סגמנטים בכל מילת-עצירה, והסגמנט עם הכי הרבה מילים נבחר (`max(segments, key=len)`). Trailing-trim הישן (BUG-097) הופך מיותר ומוסר — פיצול-לסגמנטים מפיק את אותה תוצאה למקרה ה-suffix (מילת-עצירה בסוף = סגמנט ריק אחריה, לא נבחר).
- **שני התרחישים הנדרשים (DoD §2/§4), שניהם מאומתים:**
  1. **תיאור-נכס לפני הטלפון** ("יעל רייס", `recRvK6hFTNgyj8ag` המקורי + וריאנט פסיק) — עכשיו מחלץ נכון את השם האמיתי, `classify_ingress` עולה ל-Tier 1 (במקום Tier 5).
  2. **תיאור-נכס אחרי הטלפון** (כבר עבד נכון קודם) — נבדק כ-regression guard, ממשיך לעבוד זהה.
- **עדכון ל-`test_bug099a_name_stop_extension.py`:** T1/T2 שם קודם טענו "falls through to no-candidates (safer than garbage)" — זו הייתה ההתנהגות הבטוחה-אך-לא-שלמה של 099a; עודכנו לטעון על שחזור השם הנכון בפועל (שיפור מכוון, לא רגרסיה) — 9/9 עדיין ירוקים.
- **בדיקה:** `test_bug099b_name_window_segmentation.py` (חדש, 14/14) — שני התרחישים הנדרשים, 3 coordination guards ישירים מול 096 (batch window-bleed)/097 (trailing intent-verb)/101b (chat-export block boundary) שמוכיחים ששום דבר לא נפתח מחדש, ו-3 בדיקות ישירות על לוגיקת הפיצול-לסגמנטים עצמה. **Regression suite מלא כנדרש (עודכן לכלול גם 101, לא רק 096/097/098):** `test_bug096_ingress_classifier_batch_bleed.py` (29/29), `test_bug098_followup_word_boundary.py` (16/16), `test_bug099a_name_stop_extension.py` (9/9, מעודכן), `test_bug101_whatsapp_export_bleed.py` (19/19), `core/router/test_router.py` (44/44), `smoke_tests.py`, כל שאר `test_*.py` בריפו — כולם ירוקים, אפס רגרסיה.
- **PR:** #305 (`claude/table-incorrect-names-6chfvb` → `main`) — **✅ מוזג**.
- **Merged:** ✅ כן — `main` `0c9b611` (Merge pull request #305), commit `c8bd37e`. מאומת: `git merge-base --is-ancestor c8bd37e origin/main` → exit 0.
- **Verified בפרודקשן:** ✅ כן — 5 בדיקות חיות אמיתיות (12/07/2026, 02:54-03:03, לוג Render מצורף): 3/5 מקרי single-lead עם תיאור-נכס לפני הטלפון זוהו נכון (`יעל רייך`/`יוני יהלום`/`משה ישרלי`, כולם עם `tier=1 conf=1.00`), batch עם 2 לידים זוהה נכון (`tier=2 conf=1.00`), ורשומות אמיתיות נכתבו ל-Airtable (`recevhAPRr0UfkX8v`, `recpkphyROxcpZ889`). **חשוב בפועל, לא רק בקוד** — זו הראיה שנדרשה לפני ✅ VERIFIED.
- **ממצא נוסף מאותו סבב בדיקות — ראה BUG-099b.1 למטה:** מקרה 4 (הודעה **ללא שם אמיתי בכלל**) הפיק candidate שגוי (`Name="בקומה"`) — לא regression על 099b עצמו (שני התרחישים שה-DoD דרש עדיין עובדים נכון), אלא פער נפרד שהתגלה באותו סבב: 099b יודע לשחזר שם כשיש שם אמיתי, אבל לא תמיד יודע לזהות בבטחה שאין שם בכלל.
- **סטטוס:** ✅ VERIFIED IN PROD — מוזג, מאומת מול `origin/main`, ומאומת בהתנהגות חיה עם רשומות Airtable אמיתיות. **099c נשאר הפריט הבא בתור** (fallback form כש-LCH נכשל אך ה-Router בטוח שזו כוונת create_lead — "יוסי ארגמן" מהאודיט המקורי הוא הדוגמה החיה לזה).

---

## BUG-099b.1 — כשל-validation: קלט ללא שם אמיתי עדיין הפיק candidate שגוי — ✅ VERIFIED IN PROD (12/07/2026)

- **תאריך:** 12/07/2026
- **מקור:** התגלה תוך כדי בדיקת production חיה ל-BUG-099b (מקרה 4 מתוך 5, ראה למעלה) — לא regression, פער נפרד שנחשף באותו סבב בדיקות.
- **ראיה:** `"צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"` (הודעה **ללא שם אדם בכלל**) → BOSS זיהה `Name="בקומה"` והציע לשמור, במקום להימנע מיצירת candidate.
- **קובץ:** `core/ingress_classifier.py` — `_extract_name_from_window()`
- **שורש (מאומת בשחזור ישיר, כולל את הקידומת "צור ליד חדש" המלאה מהטקסט האמיתי — לא רק המקטע האחרון):** "קומה" (רצפה) נמצא ב-`_NAME_STOP`, אבל "בקומה" ("על/ב-הקומה" — אותה מילה עם מילת-יחס חד-אותית "ב" צמודה בלי רווח) הוא **טוקן שונה לגמרי** ולא הוכר כמילת-עצירה בכלל. ב-match "חדרים בקומה חמישית טלפון" — "חדרים"/"חמישית"/"טלפון" כולם מילות-עצירה ומתפצלים לסגמנטים ריקים משלהם, אבל "בקומה" שרד כסגמנט הלא-ריק היחיד והוחזר כשם. ה-match הראשון ("צור ליד חדש מעוניין בדירת") נכשל בנפרד בבדיקת האורך (`len<4`, "צור" בלבד באורך 3) — כך שההגנה הקיימת לא הייתה מספיקה למקרה הזה.
- **תיקון — שכבה משותפת אחת, לא תיקון נקודתי (עודכן אחרי code-review):** נמצא **call site שני, נפרד**, שהיה נשאר עם הבדיקה הישנה אילו התיקון הראשוני היה נשאר: `_candidate_confidence()`'s "no stop-words" bonus (`if not any(w in _NAME_STOP for w in words):`) — בדיקת membership ישירה **נפרדת** מזו שבלולאת הפיצול-לסגמנטים ב-`_extract_name_from_window()`. תיקון שתי הבדיקות בנפרד היה משאיר סיכון ממשי שמישהו יתקן רק אחת מהן בעתיד. **הפתרון: helper משותף יחיד** — `_is_name_stop_token(token)` (`ingress_classifier.py:265-275`) — בודק התאמה מדויקת וגם, אם הטוקן מתחיל באחת מ-7 מילות-היחס/חיבור החד-אותיות העבריות (ב/ל/כ/מ/ש/ו/ה, `_HEBREW_SINGLE_LETTER_PREFIXES`), את השארית בעצמה. **שני** ה-call sites (הסגמנטציה ו-`_candidate_confidence`) עודכנו לקרוא ל-helper הזה במקום membership ישיר — לא רק אחד מהם.
- **מקרה קצה שנבדק ואומת לא-נפגע:** שם אמיתי המתחיל באחת מ-7 האותיות (בנימין/משה/הלל/שחר, מאומת ישירות בטסט) **לא** נפסל — הבדיקה נכשלת אלא אם השארית שווה בדיוק למילה שכבר קיימת ב-`_NAME_STOP`.
- **מפורשות מחוץ ל-scope (הוכרע מראש, לא ניחוש בדיעבד):** אין recursive prefix stripping, אין טיפול בתחיליות מוערמות (כמו "ובקומה" = ו+ב+קומה — "מהדירה" למשל **לא** מזוהה כמילת-עצירה, כי הסרת קידומת אחת בלבד משאירה "הדירה" שאינה ב-`_NAME_STOP` בעצמה), אין stemming/מנתח מורפולוגי, אין שינוי בחלון ±80-התווים-סביב-הטלפון, ב-`_BLOCK_SEP`, ב-neighbor-phone clipping, או בזרימת ה-clarification/fallback.
- **בדיקה:** `test_bug099b1_no_name_validation.py` (20/20, כולל **mutation check מפורש**: `unittest.mock.patch` על `_is_name_stop_token` להחזרה זמנית ל-membership-ישיר-בלבד מוכיח ש-"בקומה" חוזר כ-candidate שגוי — הוכחה שה-helper הוא load-bearing, לא קוסמטי) — שחזור מדויק של מקרה 4 (0 candidates), `classify_ingress` יורד ל-Tier 5, שני תרחישי הרגרסיה הנדרשים (`בקומה` בתיאור-נכס עם שם אמיתי + `בקומה` בלי שם בכלל), 4 בדיקות ישירות על `_is_name_stop_token()` (כולל בנימין/משה/הלל/שחר + מהדירה), ורגרסיה מלאה על 4 המקרים האחרים מאותו סבב בדיקות (3 single-lead + batch) + שני תרחישי BUG-099b המקוריים. אפס רגרסיה: `test_bug096` (29/29), `test_bug098` (16/16), `test_bug099a` (9/9), `test_bug099b_name_window_segmentation.py` (14/14), `test_bug101` (19/19), `core/router/test_router.py` (44/44), `smoke_tests.py`, כל שאר `test_*.py` בריפו.
- **פער "מאומת"-מול-חי שדווח ונפתר (12/07/2026, לפני פתיחת PR):** דיווח חי הראה `Name="בקומה"` על הטקסט המדויק **אחרי** שהתיקון כבר דווח כ"נבדק ועובר" — נראה כסתירה. **אומת ישירות, לא הונח:** `git worktree` נקי של `origin/main` (`0c9b611`, טרם כלל PR עבור 099b.1) הריץ את הטקסט המדויק והחזיר `candidates=[{"name": "בקומה", ...}]`, `tier=1` — כלומר `origin/main` (וממילא הפריסה בפרודקשן) **מעולם לא כלל את התיקון הזה בכלל**, כי לא נפתח לו PR. אין סתירה בין "קוד מתוקן ונבדק" ל"פרודקשן עדיין שבור" — אלו שני דברים נכונים בו-זמנית: התיקון קיים ועובד ב-branch, אך לא הגיע ל-`main`/Render. אין תיקון-קוד נוסף נדרש כתוצאה מהפער הזה — פער-deploy בלבד, לא באג.
- **PR:** #306 (`claude/table-incorrect-names-6chfvb` → `main`) — **✅ מוזג**.
- **Merged:** ✅ כן — `main` `a04ec47` (Merge pull request #306), commit `4292845`. מאומת: `git fetch origin main` + `git merge-base --is-ancestor a04ec47 origin/main` → exit 0 (12/07/2026).
- **Deployed בפרודקשן:** ✅ כן — `a04ec47`, 12/07/2026 03:49-03:50 (Render deploy hash אושר ע"י המשתמש מול הדשבורד, "Deploy live for a04ec47").
- **Verified בפרודקשן:** ✅ כן — **על הטקסט המדויק, לא גרסה מקוצרת** (לוג Render אמיתי, 03:51:59):
  ```
  [IngressClassifier] tier=5 conf=0.00 class=unknown reason=no_lead_candidates candidates=0 chat=boss_hq:eliyahu
  [LCH] Tier 5 — not a lead dictation (reason=no_lead_candidates), skip
  ```
  `grep-anchored confirmation`: `_is_name_stop_token`/`_HEBREW_SINGLE_LETTER_PREFIXES` מאושרים ב-`origin/main` עצמו (לא רק worktree מקומי). "בקומה" לא נבחר כשם, אין preview מזוהם — בדיוק ה-DoD שנדרש.
- **סטטוס:** ✅ **VERIFIED IN PROD** — merge+deploy+grep-anchored confirmation+אימות התנהגות חי, כולם מאושרים.
- **סטטוס:** 🟡 CODE DONE, NOT VERIFIED — תוקן בקוד, בדיקות עברו, PR #306 פתוח — ממתין ל-merge+production verification. לא לסמן ✅ עד אימות חי בפועל.

---

## Preview gap — single-lead/batch/disambiguation previews לא מאוחדים, חושפים מזהים פנימיים — רשום בלבד, PR נפרד

- **תאריך:** 12/07/2026
- **מקור:** התגלה תוך כדי אותו סבב בדיקות production ל-BUG-099b (מקרה 5) — **לא** קשור ל-BUG-099b/099b.1 מבנית; זה חוב ישן במסלול LCH/ActionGateway preview, לא תוצאה של אף אחד מהם.
- **ראיה:** כש-5 פעולות `airtable_add` הצטברו כ-pending בו-זמנית, הודעת ה-disambiguation הציגה רק:
  ```
  יש כמה פעולות הממתינות לאישור — איזו?
  • 1. airtable_add (id: f52b3269)
  • 2. airtable_add (id: d18f2a1d)
  ...
  ```
  בלי לציין אף שדה עסקי (שם/טלפון) לאיזה ליד כל מספר שייך — המשתמש נאלץ להסתמך על זיכרון/הקשר כדי לדעת ש-"5" הוא יעל ריס. בנוסף, ה-preview הקצר של ליד בודד ("📋 זיהיתי ליד: *שם* (טלפון)") ושל batch שונים בפורמט מזה של רשימת ה-disambiguation — שלושתם לא מאוחדים.
- **Severity:** בינונית — לא corruption/data-loss, אבל UX שמסתמך על ניחוש/זיכרון במקום מידע ברור, ופוטנציאל לאישור-בטעות של הפעולה הלא-נכונה כשיש כמה pending.
- **Scope לפתרון עתידי (PR נפרד, לא כאן):**
  1. לחבר single-lead ו-batch previews לפורמט משותף אחד.
  2. להציג את השדות העסקיים מתוך ה-payload של הפעולה עצמה (לא רק contract id) — גם ברשימת ה-disambiguation, לא רק ב-preview הראשוני.
  3. למסך טלפון (לא להציג גולמי).
  4. לא להציג מזהים פנימיים (contract id / fingerprint) למשתמש.
- **תוקן:** לא — רישום בלבד, לא בסקופ הסבב הזה.
- **PR:** לא נפתח.
- **Merged:** לא.
- **סטטוס:** 🟡 רשום, ממתין ל-PR נפרד. לא חוסם/תלוי ב-BUG-099b/099b.1/099c.

---

## BUG-106 — Session lookup לא-דטרמיניסטי עבור active_lead_candidate (קדם-תנאי ל-BUG-099c) — ✅ VERIFIED IN PROD

- **תאריך:** 12/07/2026
- **הוראה מחייבת שהתקבלה:** BUG-106 ו-BUG-099c מבוצעים באותו branch/PR, ב-commits נפרדים, בסדר מחייב — BUG-106 קודם, BUG-099c רק לאחר שהבדיקה של 106 ירוקה. בוצע בדיוק כך.
- **קבצים:** `session_store.py` — `_select_canonical_session_record()` (חדשה), `_find_best_session_in_db()`, `_load_from_db()`.

### Contract Chain (בוצע לפני כל שינוי קוד, כנדרש)

1. **מי יוצר רשומת Session:** `PersistentSessionStore.get_or_create()` → `_sync_to_db(is_new=True)` → POST רק כש-`_find_best_session_in_db` מחזיר `found_count==0, reason=="no_records"` (fail-closed אחרת, לפי BUG-063).
2. **מי טוען Session:** `.get(sender)` (RAM תחילה, `_load_from_db()` כ-fallback) — קרוא מ-`get_or_create`, `update_step`, `mark_done`, `get_last_file`, `get_last_tool_result`, `get_current_lead_record_id`, `get_active_lead_candidate`, `get_pending_lead_preview`, `delete`.
3. **מי כותב `active_lead_candidate`:** `set_active_lead_candidate()` — 2 קוראים חיים בלבד, שניהם ב-`core/lead_candidate_handler.py` (אחרי כתיבת ליד מוצלחת — bookmark שלאחר-כתיבה, לא state שלפני-החלטה).
4. **מי קורא `active_lead_candidate`:** `get_active_lead_candidate()` — **אפס קוראים חיים** לפני BUG-099c (מאומת ב-grep) — write-only בפועל בקוד הקיים.
5. **למה קיימות 18 רשומות לאותו Sender ID:** לא ניתן לאימות מול Airtable חי מהסביבה הזו, אך ההיסטוריה בקוד מסבירה מנגנון סביר: BUG-063/BUG-SESSIONS-ROOT (מוזג `eead2cc`) תיקן שורש שבו כשל-lookup שקט גרם ל-`found_count=0` גם כשרשומות אמיתיות קיימות, ומפעיל POST-במקום-PATCH בכל lookup רועש. התיקון ההוא מונע כפילויות **חדשות** מאותו מנגנון מכאן ואילך, אך לא מנקה למפרע רשומות שכבר נוצרו. 18 הרשומות תואמות הצטברות היסטורית מהשורש הזה (שכבר תוקן) — לא סימן לבאג חי/מתמשך.
6. **הבדל לפי tenant/channel/context/created-time/status/race/get_or_create חוזר:** **אין שדה tenant בכלל** ב-Sessions (מאומת מול הסכימה). ה-filter formula הוא `{Sender ID}='...'` בלבד — בלי scoping לפי channel/context-type/tenant (Channel/Context Type נשמרים כשדות אך לא בפילטר). **אין שדה Status כלל** (כבר תועד ב-BUG-098). **אין ראיה לרייס חי היום:** הפרודקשן רץ `gunicorn app:app` בלי `--workers`/`--threads` מפורשים (ברירת מחדל: sync worker יחיד, תהליך יחיד) — רייס בין-תהליכי על אותו sender אינו אפשרי מבנית תחת התצורה הזו. `_create_lock` (`threading.Lock()`) הוא per-process, רלוונטי רק תחת ריבוי-workers/instances שאין ראיה שקיימת כאן.
7. **המפתח הקנוני:** מחרוזת `chat_id`/`sender` הגולמית שמועברת מכל caller — מאומת דרך `app.py`'s `run_agent(user_text, chat_id, ...)` → `handle_lead_candidate(identity, user_text, chat_id, ...)` — זהו מספר הטלפון/user_id הגולמי, **לא** `identity.memory_key`. `_normalize_sender()` (`str(sender).strip()`) הוא הנרמול היחיד.
8. **האם ה-query ממוין:** **לא** — `_find_best_session_in_db`/`_load_from_db` קוראים ל-`airtable_get_records(Tables.SESSIONS, filter_formula)` בלי פרמטר `sort` כלל; לפונקציה עצמה אין תמיכת מיון.
9. **האם "using first" תלוי בסדר החזרה של Airtable:** **כן** — בלי sort מפורש, סדר ה-REST API אינו מובטח חוזית כסדר-יצירה או כל סדר יציב אחר לטווח ארוך; `records[0]` הייתה בחירה שרירותית מבחינת ה-API, לא כוונה מודעת מהקוד.
10. **Consumers נוספים ל-lookup:** רק אחד — `test_session_store_contract.py` (ניגש ל-`_find_best_session_in_db` הפרטית ישירות, לבדיקה בלבד). שום קוד production אחר לא קורא לפונקציות הפרטיות האלה.

### תיקון

`_select_canonical_session_record(records)` חדשה — ממיינת לפי `Updated At` יורד (השדה היחיד שהסכימה בפועל מספקת לזיהוי "מי הרשומה העדכנית", בהיעדר שדה Status). מיון **יציב**: רשומות שוות/חסרות `Updated At` (כולל **כל** הרשומות, כשהשדה נעדר מכולן) שומרות על סדרן היחסי המקורי — לא מנוחשות מחדש — כך שכל caller/טסט שמעולם לא מילא `Updated At` ממשיך לבחור `records[0]` בדיוק כמו קודם. שימוש זהה בשני מקומות הבחירה (`_find_best_session_in_db` ו-`_load_from_db`) — אותה רשומה מנצחת בשניהם, בהינתן אותו קלט.

### בדיקה

`test_bug106_session_determinism.py` (חדש, 7/7): 3 בדיקות ישירות על ה-helper (כולל 18 רשומות בלי timestamp → יציבות מלאה, timestamp אמיתי תמיד מנצח ריק/חסר), ו-**ההוכחה המרכזית שנדרשה** — שתי מופעי `PersistentSessionStore` **נפרדים** (מדמים request 1 ו-request 2 אחרי הפעלה-מחדש/cache-miss) בוחרים **אותו Airtable record ID** בדיוק, לא רק "נמצא ערך". רגרסיה: `test_session_store_contract.py` (BUG-063's own suite, 4/4) ירוק ללא שינוי.

- **PR:** #308 (`claude/table-incorrect-names-6chfvb` → `main`).
- **Merged:** ✅ כן — `c1311b8` (`origin/main`), מאומת ב-grep ישיר מול `origin/main` (`_select_canonical_session_record` קיימת ב-`session_store.py`, משמשת בשני call sites).
- **Deployed:** ✅ כן — Render deploy notification עבור `c1311b8` התקבל.
- **Verified בפרודקשן:** ✅ כן — לוג הפרודקשן (אימות BUG-099c, ראו שם) מציג `found_count=18 -- using canonical (most recently updated): rec3YS5Zcr2FenX7z` ברישום ההודעה הראשונה, ואותו `rec3YS5Zcr2FenX7z` שוב ב-PATCH-ים העוקבים (הודעה שנייה + confirm) — הוכחה ישירה שאותה רשומה קנונית נבחרה בעקביות על פני שלוש קריאות נפרדות ל-store, לא רק unit test.
- **סטטוס:** ✅ VERIFIED IN PROD (12/07/2026) — merged + deployed + live evidence, לא רק unit tests/merge/deploy.

---

## BUG-099c — Clarification במקום Denial כשחסר שם ליד — ✅ VERIFIED IN PROD

- **תאריך:** 12/07/2026
- **תלות שמולאה:** BUG-106 (deterministic session selection) — נדרש כקדם-תנאי כי הזרימה חוצה שתי הודעות/requests נפרדות; אם הודעה 1 (שמירה) והודעה 2 (קריאה) יכלו לנחות על שתי רשומות-כפילות שונות, הזרימה הייתה עובדת "לפעמים", לא לפי עיצוב.
- **ראיה (מאותו לוג פרודקשן שאימת BUG-099b.1):** `"צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"` → Router: `intent=create_lead confidence=0.95`; LCH: Tier 5/no_lead_candidates, מדלג נכון (BUG-099b.1); נופל ל-`DeterministicDenial` שמחזיר "יצירת ליד חדש ידנית דרך הצ׳אט חסומה כרגע" — **שגוי**: המערכת הבינה נכון את הכוונה, רק חסר שדה אחד.
- **Scope:** Leads-only. **לא** בונה Understanding Layer כללית — BUG-104 (ReasoningEntity/reasoning_engines) נשאר פתוח כהחלטת ארכיטקטורה נפרדת; מימוש עתידי של BUG-104 יכול לעדכן את הזרימה הזו בלי לפגוע בנכונותה.

### עיצוב שמומש

- **State:** תחת המפתח הקיים `active_lead_candidate` (אין store חדש) — צורה חדשה ונבדלת `{"state": "needs_clarification", "expected_field", "partial_payload", "original_text", "set_at"}`, לעולם לא מתבלבלת עם צורת-הבוקמארק הישנה `{"name", "record_id", "set_at"}` (0 קוראים חיים, ראה BUG-106). כל consumer בודק `state` במפורש. `set_at` משותף בכוונה לשתי הצורות — כך שה-TTL הקיים (1800 שניות) חל זהה על שתיהן בלי שינוי שם.
- **פונקציות חדשות:** `session_store.py::set_lead_clarification()`/`clear_active_lead_candidate()` (החדש — ניקוי מפורש, לא רק אגב בדיקת-פקיעה). `get_active_lead_candidate()`'s TTL-clear תוקן לסנכרן ל-DB (כמו `get_pending_lead_preview` כבר עושה) — לפני זה פקיעה נוקתה רק ב-RAM, ויכלה "לקום לתחייה" מה-DB אחרי restart.
- **`core/lead_candidate_handler.py`:** `_maybe_start_lead_clarification()` (נקודת-כניסה — Tier 5/no_lead_candidates + `Intent.CREATE_LEAD` + טלפון קיים בטקסט → שומר state, מחזיר "זיהיתי בקשה ליצור ליד ואת מספר הטלפון X, אבל לא מצאתי שם. מה שם הליד?"). `_resolve_lead_clarification()` (resolver — נבדק **ראשון** ב-`handle_lead_candidate()`, לפני batch-followup ולפני `classify_ingress()` על ההודעה החדשה) — סדר עדיפויות מחייב: (1) TTL פג, (2) ביטול, (3) פקודה חדשה מפורשת (Intent מה-Router, לא זיהוי מקומי), (4) תשובה תקינה, (5) תשובה לא-ברורה. `_validate_clarification_name()` — reuse של `_HEBREW_NAME_RE`/`_is_name_stop_token` (`core/ingress_classifier.py`, לא לוגיקה חדשה) עם fullmatch (לא segmentation) **וגם** תקרת-מילים (בדיוק 2) — בלעדיה, "נדבר אחר כך" (משפט שיחה אמיתי, בלי אף מילת-עצירה) עבר בטעות כ"שם" תקין (נמצא ותוקן תוך כדי בדיקה עצמית, לפני הרצת הרגרסיה).
- **Reuse, לא duplication:** תשובה תקינה בונה candidate synthetic ומעביר אותו ל-`_handle_single_candidate()` הקיים (פרמטר חדש `clear_clarification: bool`) — **אותו** dedupe (`_at_find_lead`), **אותו** ActionContract (`_propose_lead_write`), **אותו** preview. הטקסט שמועבר ל-preview/summary הוא ה-`original_text` (ההודעה הראשונה, עם הטלפון+תיאור-העניין) — לא תשובת-השם הקצרה — כך שהפרטים מההודעה הראשונה לא אובדים.
- **ניקוי state:** רק אחרי הצלחה בפועל — `clear_clarification=True` מנוקה רק בענף שאחרי `gw_result.ok`/`ok and record_id`, **לא** לפני. כשל ב-`propose_action()` משאיר את ה-state פעיל, בלי אובדן payload ובלי "פעולה חלקית".
- **LL-11 (אילוץ ארכיטקטוני שהתגלה תוך-כדי, נאכף כבר):** Sessions נקרא **פעם אחת** בלבד לכל request (`test_session_snapshot.py`) — `app.py`'s `run_agent()` כבר טוען snapshot יחיד ומעביר אותו הלאה ל-`resolve_context_pronouns`/`_build_tool_context`. גרסה ראשונה של המימוש קראה ל-`get_active_lead_candidate()` (קריאת Sessions נוספת) **בלי תנאי, על כל הודעה** — הפרה ישירה, שנתפסה ע"י הרגרסיה המלאה (`test_session_snapshot.py` נכשל: "Expected 1 Sessions GET, got 2"; `test_capture_router_wiring.py` נכשל גם, כי fake session-store minimal לא מימש את המתודה החדשה). **תוקן:** `handle_lead_candidate()` קיבל פרמטר `session` חדש — ה-snapshot שה-caller כבר טען, מועבר מ-`app.py`'s `_session_snapshot`. `_resolve_lead_clarification()` קורא `active_lead_candidate` **מה-snapshot הזה**, לא קורא ל-`lead_sessions.get()`/`get_active_lead_candidate()` בעצמו — רק במקרה הנדיר שבו יש state ממתין (ולא בכל הודעה) הוא מבצע כתיבה (שממילא קוראת internally, כמו התקדים הקיים ב-`set_active_lead_candidate`).

### Consumer Audit (grep מלא בוצע כנדרש)

`grep -rn "active_lead_candidate\|pending_lead_preview\|lead_sessions\|session_store" --include="*.py" .` — כל writer/reader/clear אותרו (session_store.py's methods עצמן, שני call sites ב-`lead_candidate_handler.py` לבוקמארק הישן, `interaction_engine.py`/`cmd_decision.py` למתודות גנריות אחרות שלא נוגעות ב-`active_lead_candidate` בכלל). אף consumer קיים לא הניח שקיים `name`/שה-candidate תמיד מלא — הבדיקה `cand.get("state") != "needs_clarification": return None` היא ההגנה המפורשת שמונעת בדיוק את זה.

### בדיקה

`test_bug099c_lead_clarification.py` (חדש, 25/25): מסלול-שמח מקצה-לקצה (2 הודעות, preview אחד, payload נכון כולל הטקסט המקורי לא תשובת-השם), ביטול, פקיעת TTL, פקודה-חדשה-מפריעה, תשובה-לא-ברורה (כולל "נדבר אחר כך" — האזהרה שנתפסה תוך-כדי), שם-פסול ("בקומה" עצמו), כשל `propose_action()` (state שורד), 3 תנאי-כניסה (בלי טלפון / intent שגוי / Tier 4 — אף אחד לא מפעיל הבהרה), `session=None` (לא קורס, לא "פותר" בטעות), ביקורת-consumer (בוקמארק ישן לא מתבלבל), ובדיקת LL-11 מפורשת (`handle_lead_candidate()` לא קורא ל-Sessions כשsnapshot כבר סופק). **Regression suite מלא כנדרש:** `test_bug096` (29/29), `test_bug098` (16/16), `test_bug099a` (9/9), `test_bug099b` (14/14), `test_bug099b1` (20/20), `test_bug101` (19/19), `test_bug106` (7/7), `test_session_store_contract.py` (4/4), `core/router/test_router.py` (44/44), `test_capture_router_wiring.py` (10/10), `test_session_snapshot.py` (2/2, LL-11 עצמו), `smoke_tests.py`, כל שאר `test_*.py` בריפו — כולם ירוקים, אפס רגרסיה.

- **PR:** #308 (אותו PR כמו BUG-106, commit נפרד).
- **Merged:** ✅ כן — `c1311b8` (`origin/main`), מאומת ב-grep ישיר: `_maybe_start_lead_clarification`, `_resolve_lead_clarification`, `_validate_clarification_name` קיימים ב-`core/lead_candidate_handler.py`, וקריאת `app.py` כוללת `intent=route.intent, session=_session_snapshot`.
- **Deployed:** ✅ כן — Render deploy notification עבור `c1311b8` התקבל.
- **Verified בפרודקשן — הרצף החי המלא (2 הודעות נפרדות, כנדרש):**
  - הודעה 1 (בלי שם, רק טלפון) → תשובת ההבהרה המדויקת שנדרשת: "זיהיתי בקשה ליצור ליד ואת מספר הטלפון 0501234571, אבל לא מצאתי שם. מה שם הליד?" — session record `rec3YS5Zcr2FenX7z` (מתוך 18 כפילויות, `_select_canonical_session_record` בחר בעקביות).
  - הודעה 2 (נפרדת! רק "יוסי כהן") → preview נכון עם שם+טלפון+הקשר מהודעה 1 (ה-`original_text` נשמר ולא אבד) — אותה `rec3YS5Zcr2FenX7z` שוב ב-PATCH, מוכיח ששתי הקריאות נחתו על אותה רשומת Session (BUG-106 עשה את עבודתו).
  - אישור ("כן") → רשומת Airtable **יחידה** נוצרה: `recpD6csFGrLCpGjT` — אין כפילות.
  - **הוכחת-בונוס לניקוי ה-state:** הודעה עוקבת בלתי-קשורה ("שמואל כהן") **לא** נבלעה כהמשך-הבהרה — מוכיח ש-`clear_active_lead_candidate()` פעל נכון אחרי יצירת ה-ActionContract, ולא נשאר state תקוע.
  - כל הראיות הנ"ל מלוג פרודקשן שהועבר ישירות (לא unit test, לא הסקה).
- **סטטוס:** ✅ VERIFIED IN PROD (12/07/2026) — merged + deployed + live 2-message sequence + session-record consistency + state-clear regression, כל התנאים שנדרשו לפני סימון ✅ מולאו.

---

## BUG-107 — חיפוש Deals עם שם-שדה שגוי → 422 INVALID_FILTER_BY_FORMULA → A32 false MISMATCH — 🔴 נרשם, לא תוקן (registration-only)

- **תאריך:** 12/07/2026
- **מקור:** התגלה אגב אימות-חי של BUG-106/BUG-099c (אותו לוג פרודקשן) — **אינו** תקלה ב-099c; תקלה נפרדת במסלול החיפוש הכללי. **לא לפתוח מחדש PR #308 בגלל זה.**
- **תיאור:** חיפוש בטבלת "עסקאות (Deals)" בונה formula עם שם-שדה שגוי (`SEARCH('שמואל כהן', {שם})` — השדה `שם` כנראה אינו קיים/אינו נכון בטבלת Deals), מה שגורם ל-Airtable להחזיר `422 INVALID_FILTER_BY_FORMULA` חי בפרודקשן. השילוב של השגיאה הזו (Deals) יחד עם שתי תוצאות "0 רשומות" לגיטימיות מ-Leads/Contacts מפעיל אזהרת A32 anti-hallucination שגויה: `MISMATCH` ("agent says 'not found' but tool results contain data") — כלומר שכבת ה-anti-hallucination מפרשת שגיאת-422 (לא "לא נמצא") כאילו יש נתונים שהסוכן התעלם מהם.
- **קבצים לחקירה (טרם נחקרו — Contract Chain טרם בוצע):** מודול החיפוש הכללי שבונה formulas לפי טבלה (ככל הנראה `crm.py`/`airtable_tools.py`/`contact_resolver.py` או שכבת "חיפוש-בכל-הטבלאות"), שם השדה הנכון בטבלת "עסקאות (Deals)" מול `airtable_schema.py`, ו-`core/anti_hallucination.py`'s טיפול ב-tool-error/422 מול "0 records" לגיטימי.
- **השערת שורש (לא מאומתת עדיין):** קרוב לוודאי שם-שדה קשיח (hardcoded) שגוי או לא-מעודכן מול הסכימה בפועל של טבלת Deals — ייתכן קשור לדפוסי drift שכבר תועדו ב-`docs/governance/ARCHITECTURE_DRIFT_MAP.md`. דורש grep+trace לפני כל תיקון (Contract Chain), לא הונח כאן.
- **סטטוס:** 🔴 נרשם בלבד — לא נחקר לעומק, לא תוקן, לא PR. ממתין להנחיה להתחיל Contract Chain.

---

## BUG-108 / BUG-PENDING-APPROVAL-B (PR-0) — Pending ActionGateway approval שורד הודעות-ביניים לא-קשורות (context poisoning) — ✅ VERIFIED IN PROD

- **תאריך רישום:** 12/07/2026. **תאריך מימוש (PR-0):** 12/07/2026.
- **מקור:** התגלה אגב אימות-חי של BUG-106/BUG-099c — **אינה** תקלה ב-099c. נרשם תחילה כפריט-החלטה בלבד (3 אפשרויות), מומש כ-PR-0 לפי handoff נפרד (`PR0_PENDING_APPROVAL_CONTEXT_SAFETY.md`) שבחר באפשרות #3: "כן" אחרי הודעת-ביניים **חייב** להציג מחדש את תיאור הפעולה לפני ביצוע.
- **תרחיש הבאג:** `preview: יצירת ליד יוסי כהן → הודעת ביניים: שמואל כהן → "כן" → יוסי כהן נוצר` — המשתמש התכוון "כן" בהקשר ההודעה האחרונה, אבל ActionGateway אישר את ה-ActionContract הפתוח מההודעה הישנה יותר. לא disambiguation — context poisoning: הפעולה בוצעה עם אישור אמיתי, אבל ההקשר השתנה בינתיים.

### Contract Chain (בוצע לפני כל שינוי קוד, כנדרש ע"י PR-0 doc)

מיפוי גילה **שלושה מנגנוני pending-approval נפרדים ובלתי-תלויים** בקוד, לא אחד:
1. `core/action_gateway.py`'s `ActionContract`/`ExecutionLedger` (מפתח: `canonical_user_id`, **אין TTL בכלל**) — המנגנון החי בפועל לאישור כתיבת-ליד של LCH (`core/lead_candidate_handler.py::_propose_lead_write` קורא ל-`propose_action()` **תמיד**, "regardless of FEATURE_ACTION_GATEWAY" לפי הערת הקוד עצמה). **זה בדיוק המנגנון שמשחזר את התרחיש בדוח.**
2. `app.py`'s `_pending_approvals` dict (מפתח: `chat_id`, TTL=600s) — מזין גם `_handle_approval_callback_impl()` (כפתורי טלגרם) וגם אישור-חופשי-בטקסט עבור בקשות Agent כלליות (`run_agent`'s pending-check block). **אותה תבנית פגיעות בדיוק**, אך לא זה שמשחזר את התרחיש שבדוח.
3. `event_bus.py`'s `PendingActionsStore`/`bus` (מפתח: `chat_id`, TTL=30min) — Stage-A legacy fallback, נדרש רק כש-`FEATURE_ACTION_GATEWAY` כבוי וגם אין live Gateway contract — נדיר בפועל.

ה-Scope שב-PR-0 doc הזכיר `_handle_approval_callback_impl()`/"EventBus" (מנגנונים #2/#3), אך התרחיש המדווח בפועל משחזר במנגנון #1. **הוצג למשתמש במפורש** (AskUserQuestion) — הוחלט: **ActionGateway בלבד (מנגנון #1)** למימוש הזה; מנגנונים #2/#3 יש להם את אותה בעיה שורשית אך נשארים מחוץ ל-scope, לפתיחה כ-follow-up נפרד אם ירצו.

שאר תשובות ה-Contract Chain: `route_confirmation_word()` (single live contract) מאשר ומבצע מיידית ללא שום בדיקת "האם עבר זמן/הודעה מאז ה-preview" — `ActionContract` לא נשא `created_at`-based TTL ולא state של "הופרע". הודעה שאינה כן/לא/disambiguation/combined נופלת פשוט הלאה לזרימת Context Pronoun Resolution/Agent/LCH בלי לגעת ב-Gateway בכלל. כמה contracts pending בו-זמנית אפשריים (disambiguation קיים מטפל). הודעת-ביניים יכולה בהחלט ליצור בעצמה ActionContract חדש (fingerprint שונה → contract נפרד, לא מתמזג).

### תיקון

- **`core/action_gateway.py`:** `ActionContract` קיבל שני שדות בוליאניים חדשים: `context_interrupted`/`reconfirmation_required` (ברירת מחדל `False`) — לא נדרש store חדש. `ExecutionLedger.mark_context_interrupted(canonical_user_id)` (חדש) מסמן כל contract pending של הזהות כ-`context_interrupted=True`, בלי לגעת ב-status/dispatch. `ActionGateway.mark_context_interrupted()` (חדש) — delegate ציבורי. `_describe_contract_for_reconfirmation(contract)` (חדש) — תיאור עסקי קריא: עבור `airtable_add`/`airtable_update` על טבלת Leads מציג שם+טלפון+domain בפועל (לא internal id); עבור כל tool אחר, `"{tool_name} / {table}"` fallback גנרי. `route_confirmation_word()`'s single-live-contract branch: אם `context_interrupted=True` וטרם `reconfirmation_required` — **לא מבצע**, מציג תיאור עסקי + "לאשר אותה? (כן/לא)", מסמן `reconfirmation_required=True`; אם `reconfirmation_required` כבר `True` — מבצע רגיל (`approve()` הקיים, ללא שינוי בלוגיקת ה-dispatch/execute עצמה). `route_cancellation_word`/`route_disambiguation`/`route_combined_word` **לא שונו** — disambiguation הקיים ממשיך בדיוק כפי שהיה (הבדיקה החדשה חלה רק בענף single-contract).
- **`app.py`:** נקודת-חיבור יחידה — אחרי כל בדיקות combined/disambiguation/confirm/cancel (שכולן `return` כשמזוהות), לפני "2.6 Context Pronoun Resolution": `action_gateway.mark_context_interrupted(identity.memory_key)`. רץ בדיוק עבור הודעה שהגיעה לנקודה הזו בלי שנצרכה כ-resolution לאף contract חי — כלומר "הודעת ביניים" לפי ההגדרה של ה-state machine. הודעת ה"כן" עצמה שכן פותרת contract חי חוזרת (`return`) **לפני** השורה הזו, כך שהיא לעולם לא מסמנת את עצמה כהפרעה (DoD #1 שלם).
- **הוחלט במכוון לא לממש** את השדות `last_prompt_message_id`/`last_user_message_sequence` שה-doc הציע: העיצוב שנבחר (סימון פרואקטיבי של כל pending contract בכל הודעה שאינה resolution) משיג את כל ה-DoD בלי לתלות ב-message_id/sequence-counter, שהיו מוסיפים plumbing חוצה-קבצים (LCH+app.py) ללא תועלת התנהגותית נוספת — עקבי עם "מינימלי — state tracking בלבד" שה-doc עצמו דורש.

### בדיקה

`test_pr0_pending_approval_context_safety.py` (חדש, 26/26): DoD #1 (כן ישיר, ללא הודעת ביניים — מבצע מיידית, לא נשבר), #2 (הודעת ביניים → כן → לא מבצע, `reconfirmation_required` הופך `True`), #3/#9 (התיאור המוצג הוא עסקי-קריא — כולל תרחיש Leads מדויק עם שם+טלפון בפועל — ולא internal contract_id בלבד), #4 (כן נוסף אחרי reconfirmation מבצע בדיוק את אותו payload, פעם אחת), #5 (לא אחרי reconfirmation מבטל, לא מבצע), #6 (פעולה חדשה שמגיעה בזמן pending מקבלת contract_id נפרד, לא מתמזגת עם הישן), #7 (2+ contracts pending → disambiguation קיים ממשיך לעבוד בדיוק כפי שהיה, גם כששניהם מסומנים interrupted), #8 (contract שבוצע יוצא מ-`find_live_contracts`, lifecycle לא נפגע). **Regression suite מלא:** `test_action_gateway.py` (41/41), `test_bug070_combined_wording.py` (27/27), `test_bug070_pending_approval_multi.py` (9/9), `test_bug099c_lead_clarification.py` (25/25), `test_bug106_session_determinism.py` (7/7), `smoke_tests.py` (כולם PASS), `python3 -m compileall app.py core/action_gateway.py core/lead_candidate_handler.py` — כולם ירוקים, אפס רגרסיה.

### Scope

תואם למדויק את ה-Scope שהוחלט (ActionGateway בלבד): נגעו רק ב-`core/action_gateway.py` ו-`app.py` (שורה אחת, נקודת-חיבור). לא נגעו: `dispatch`/`execute` logic של ActionGateway (`_execute_contract`/`approve()`'s dispatch נשארו ללא שינוי), `FEATURE_ACTION_GATEWAY` flag, `LeadsWriteGate`, לוגיקת disambiguation הקיימת. מנגנונים #2 (`app.py`'s `_pending_approvals`) ו-#3 (`event_bus.py`) **לא טופלו** — נשארים עם אותה פגיעות שורשית, למי שירצה follow-up נפרד.

- **PR:** #311 (`claude/table-incorrect-names-6chfvb` → `main`) — **הראשון משני PRs**, ראה Follow-up למטה.
- **Merged:** ✅ כן — `233b196` (`origin/main`), מאומת ב-grep ישיר מול `origin/main`: `context_interrupted`/`reconfirmation_required`/`mark_context_interrupted`/`_describe_contract_for_reconfirmation` קיימים ב-`core/action_gateway.py`, וקריאת `app.py` ל-`mark_context_interrupted` קיימת בשורה 1725.
- **Deployed:** דווח ע"י המשתמש (12/07/2026), Render deploy live for `c1311b8`→ בפועל commit `233b196` פעיל.
- **Verified בפרודקשן (הרצף המקורי — preview→כן ישיר, ללא הודעת ביניים):** ✅ עבד כצפוי.
- **⚠️ פער שנתגלה באימות-חי (12/07/2026) — ראה Follow-up:** רצף אמיתי בפרודקשן (`preview: צור ליד מעיין יכ` → `/update` → `בדיקה` → `כן`) **לא** הפעיל reconfirmation — ה-"כן" ביצע מיידית. שורש: ה-hook היחיד (PR #311) חי **בתוך** `run_agent()`, ו-`/update` + תשובת-הטקסט שלו (`capture_text` ב-`cmd_update.py`) עוברים ב-`app.py`'s webhook דרך `bot.process_new_updates()` **בלי לעבור דרך `run_agent()` בכלל** — לכן ה-hook מעולם לא רץ עבורן.

---

## Follow-up ל-BUG-PENDING-APPROVAL-B — Global Ingress Context Gate (PR #311 לא כיסה מסלולים שעוקפים run_agent) — ✅ VERIFIED IN PROD

- **תאריך:** 12/07/2026.
- **מקור:** לוג פרודקשן אמיתי שהמשתמש הדביק, שאמור להוכיח VERIFIED IN PROD — במקום זאת חשף שה-fix של PR #311 לא מספיק.

### שורש (מאומת, לא הונח)

מיפוי מלא של `app.py`'s Telegram/WhatsApp webhooks גילה **מנגנון עקיפה רחב בהרבה מ-`/update` בלבד** — כל אחד מהמסלולים הבאים מדלג לגמרי על `run_agent()`, ולכן על ה-hook היחיד שהיה קיים בתוכו:
1. כל callback_query (כפתורי inline: `upd_domain:`, `upd_type:`, weekly-summary, **וגם** `approve:`/`reject:` ששייכים למנגנון הנפרד `app.py`'s `_pending_approvals`).
2. כל slash command (`/update`, `/status`, `/schema`, `/cancel`, `/convert` וכו').
3. טקסט חופשי שנלכד ע"י wizard מפעיל (`cmd_update.py`'s `capture_text`, מסונן ב-`app.py` דרך `has_pending_text_capture`).
4. קובץ/תמונה שנלכדים ע"י אותו wizard (`capture_photo_or_document`).
5. Decision Hub attachment-reference handling (`FEATURE_DECISION_HUB`, flag-gated).
6. מדיה כללית (voice/photo/document) מחוץ ל-wizard (`_handle_telegram_media`).
7. מדיה ב-WhatsApp (Twilio + Meta Cloud API).

מסלולים #7/#9 מהמיפוי הקודם (dedup/junk filters) **אינם** מסלולי-עקיפה אמיתיים — הודעה כפולה/זבל אינה "פעולה חדשה" ואינה אמורה להפריע לכלום.

### עיצוב שהוחלט (הוראה מפורשת מהמשתמש — "אל תתקן כל bypass point בנפרד")

**לא** תוקן כל אחד מהמסלולים הנ"ל בנפרד. במקום זאת: **קריאה אחת לכל webhook ערוץ**, בגבול משותף — אחרי אימות (signature) + סינון junk/idempotency/duplicate + resolve_identity, לפני כל ניתוב callback/command/wizard/media/Decision Hub/Agent/early-return. ה-hook הישן בתוך `run_agent()` (PR #311) **הוסר לגמרי** — לא נשמרו שני מנגנונים מקבילים.

### תיקון

- **`core/action_gateway.py`:** `ActionGateway.is_own_resolution_event(canonical_user_id, text)` (חדש) — קובע אם טקסט הוא ניסיון-resolution אמיתי (משתמש **באותם** `_CONFIRM_KEYWORDS`/`_CANCEL_KEYWORDS`/`_parse_ordinal`/`_parse_combined` שה-routes עצמם כבר משתמשים בהם, כולל התקדים של BUG-070 שספרה בודדת נחשבת disambiguation רק כש-2+ contracts חיים) — כך שאין סיכון לסטייה בין הבדיקה הזו לבין ההתנהגות האמיתית של `route_confirmation_word`/`route_cancellation_word`/`route_disambiguation`/`route_combined_word`.
- **`app.py`:** hook יחיד חדש — `_apply_ingress_context_gate(identity, event)` + `_IngressEvent` (dataclass: channel/kind/text). קורא ל-`is_own_resolution_event` (רק כש-`kind=="text"`) — אם אמת, לא עושה דבר (המסלול הרגיל יפתור); אחרת, `mark_context_interrupted`.
- **חוברה בכל אחד מ-6 נקודות ה-webhook** (Telegram: callback/text/media; WhatsApp: Twilio + Meta), **בלי** לגעת ב-dispatch/execute logic. ה-hook הישן (`app.py` שורה 1725 מ-PR #311) **הוסר**.

### Fail-closed מפורש — context_integrity_unknown (תיקון לאחר code review)

בסקירה ראשונה, ה-fallback (כשהקריאה הראשית ל-`mark_context_interrupted` נכשלת) פשוט ניסה להפעיל מחדש את אותה סמנטיקה (`context_interrupted=True`) דרך קוד חלופי. code review דרש הבחנה מפורשת: **כשל ב-marking אסור שישאיר contract כאילו ההקשר בטוח, אבל גם אסור שיפיל את ההודעה העסקית הנכנסת** — יש לסמן את ה-integrity כ-"לא-ידוע" (state נבדל, לא מתבלבל עם הפרעה אמיתית), ולאפשר routing להמשיך כרגיל.

- **שדה חדש ל-`ActionContract`:** `context_integrity_unknown: bool = False` — נבדל מ-`context_interrupted` (state שונה, נצפה בנפרד ב-logs/audits).
- `ExecutionLedger.mark_context_integrity_unknown()`/`ActionGateway.mark_context_integrity_unknown()` (חדשים) — מימוש **עצמאי**, כתוב בנפרד מ-`mark_context_interrupted` (לא reuse של אותה לולאה), כדי שבאג ספציפי לזה לא ישבור גם את זה.
- `route_confirmation_word()`'s single-contract gate: `if (contract.context_interrupted or contract.context_integrity_unknown) and not contract.reconfirmation_required:` — שני המצבים נשערים **זהה** (לא מבצע, מציג תיאור עסקי, דורש כן נוסף), אך נשמרים כשדות נפרדים.
- `_apply_ingress_context_gate()`: אם הקריאה הראשית ל-`mark_context_interrupted` זורקת exception — נרשם ERROR ונקרא `mark_context_integrity_unknown` (fallback עצמאי). אם **גם** זה נכשל (כשל כפול) — נרשם CRITICAL, לא בשקט; ההודעה הנכנסת **ממשיכה ל-routing הרגיל בכל מקרה** (ה-try/except בכל אתר-קריאה ב-webhook לא עוצר את הבקשה) — רק אישור מאוחר מושפע.
- נבדק במפורש: `T11` (כשל ראשי → מסומן `context_integrity_unknown`, לא `context_interrupted`), `T12` (מצב "לא-ידוע" חוסם ביצוע ישיר בדיוק כמו הפרעה אמיתית), `T13` (כשל כפול → CRITICAL, אין קריסה, הבקשה חוזרת 200 כרגיל) — ב-`test_pr0_ingress_context_gate.py`.

### שלושה שערים לפני merge (נדרשו במפורש ע"י המשתמש, כל אחד עם בדיקה נפרדת)

1. **הוכחת מיקום גלובלי** (לא רק טענה) — `test_pr0_gates_structural.py`'s Gate 1a-1e: בדיקת AST על `app.py` בפועל, משווה מספרי-שורה, מוכיחה שבכל אחד משלושת ה-webhooks הסדר הוא בדיוק `auth/filter/dedup → identity resolution → gate → routing`, לכל הענפים (callback/text/media בטלגרם; Twilio/Meta ב-WhatsApp) — לא רק שהתנהגות היום נכונה, אלא שהמבנה עצמו אוכף את זה (רגרסיה עתידית שתשבור את הסדר תיכשל ב-CI).
2. **הוכחת reuse אמיתי, לא duplication** — `test_pr0_gates_structural.py`'s Gate 2a-2c: מוטציה על `_CONFIRM_KEYWORDS`/`_parse_combined` המשותפים מוכיחה ש-`is_own_resolution_event` **קורא מאותו מקור** כמו ה-routing האמיתי (לא רשימה מקבילה שיכולה לסטות), הבדל תקדים BUG-070 (ספרה בודדת) נבדק במפורש, וקריאת callback חיצונית (`approve:`/`reject:`, מנגנון נפרד) עדיין מפריעה ל-ActionGateway.
3. **הפרדת שני התיקונים לקומיטים נפרדים** — ראה למטה.

### מבנה קומיטים (PR #312, לפי דרישה מפורשת — לא לבלוע תיקונים בתוך diff הפיצ'ר)

1. `fix(whatsapp): remove local resolve_identity import that shadows the module-level one` + `test_whatsapp_resolve_identity_scoping.py` (חדש, 4/4) — תיקון scoping עצמאי (Python: import מקומי בהמשך הפונקציה הופך את השם ל-local על פני **כל** הפונקציה, כולל לפני שורת ה-import עצמה), תקף גם בלי הפיצ'ר.
2. `fix(telegram-webhook): run idempotency dedup before command/wizard dispatch` + `test_telegram_dedup_ordering.py` (חדש, 8/8) — תיקון סדר עצמאי (dedup רץ אחרי command/wizard dispatch, כך שהודעה כפולה בוצעה פעמיים), תקף גם בלי הפיצ'ר.
3. `feat(action-gateway): global ingress context gate at the webhook boundary` — הפיצ'ר עצמו (מעל שני התיקונים לעיל), עם `test_pr0_ingress_context_gate.py` ו-`test_pr0_gates_structural.py`.

### בדיקה (מלא)

`test_pr0_ingress_context_gate.py` (33/33) — אינטגרציה אמיתית מול Flask test client על `/telegram`, `/whatsapp`, `/webhooks/meta/whatsapp`: כל מחלקת מסלול (slash command, wizard text-capture, callback לא-קשור, callback `approve:`/`reject:`, מדיה כללית, Decision Hub attachment reference, WhatsApp Twilio, Meta WhatsApp) מפריעה; "כן" אמיתי **לא** מפריע לעצמו; הודעה כפולה/inbound זבל **לא** מפריעים (מסוננים לפני ה-gate); fail-closed (כשל בודד → `context_integrity_unknown`; חוסם ביצוע כמו הפרעה אמיתית; כשל כפול → CRITICAL, לא קורס). `test_pr0_gates_structural.py` (39/39) — Gate 1+2 כמתואר למעלה. `test_whatsapp_resolve_identity_scoping.py` (4/4), `test_telegram_dedup_ordering.py` (8/8). **Regression suite מלא (כל `test_*.py` בריפו):** כולם ירוקים, `smoke_tests.py` PASS, `python3 -m compileall app.py core/action_gateway.py cmd_update.py` — אפס רגרסיה.

### Scope

זהה ל-PR #311 (ActionGateway בלבד) — מנגנונים #2 (`_pending_approvals`)/#3 (`event_bus.py`) לא טופלו — נשאר follow-up נפרד אם ירצו.

- **PR:** #312 (`claude/table-incorrect-names-6chfvb` → `main`), 4 קומיטים (3 קוד + docs). #311 כבר merged וסגור — לא ניתן "לעדכן" אותו ישירות ב-GitHub; זהו PR נפרד שמשלים את אותה עבודה, לפי פרוטוקול ה-merged-PR הקיים בריפו.
- **Merged:** ✅ כן — `417cf45` (`origin/main`), CI ירוק (`backend-ci`/`frontend-ci`/Vercel) לפני מיזוג, אין review comments פתוחים. מאומת ב-grep ישיר מול `origin/main` (לא רק merge status): `context_integrity_unknown`/`mark_context_integrity_unknown`/`is_own_resolution_event` ב-`core/action_gateway.py`; `_apply_ingress_context_gate`/`_IngressEvent` בכל 4+ אתרי הקריאה ב-`app.py`; **אפס** מופעים של `from identity import resolve_identity` מקומי (תיקון ה-scoping אומת שנעלם); סדר ה-dedup לפני `text.startswith("/")` אומת ב-`app.py`.
- **Deployed:** ✅ כן — "Deploy live for `417cf45`" (12/07/2026 13:54).
- **Verified בפרודקשן (הגבול עצמו — reconfirmation מופעל):** ✅ כן — לאחר `/cal` ופעולה נוספת, ה-"כן" הראשון **לא** בוצע והציג מחדש את הליד הממתין כנדרש. **זו ההוכחה החיה שה-global ingress gate עובד** — בדיוק התרחיש שהמנגנון הקודם (PR #311) פספס.
- **⚠️ חוסם חדש שנחשף באימות-חי — ראה Follow-up #2 למטה:** ה-"כן" השני (ה-reconfirmation הלגיטימי) נחסם ע"י `guards.idempotency` כ-duplicate של ה-"כן" הראשון — dead end מוחלט (אין דרך לעקוף/לנסות שוב, רק ליצור פעולה מחדש).
- **סטטוס:** ✅ תוקן בקוד, מוזג, ונפרס — הגבול עצמו אומת חי בפרודקשן. חוסם חדש (idempotency key) תוקן ב-Follow-up #2.

---

## Follow-up #2 ל-BUG-PENDING-APPROVAL-B — מפתח ה-idempotency הטלגרמי לא היה event-identity — ✅ VERIFIED IN PROD

- **תאריך:** 12/07/2026.
- **מקור:** אימות-חי בפרודקשן של הגבול הגלובלי (Follow-up #1, למעלה) — הגבול עצמו עבד, אבל חשף חוסם חדש: "כן" לגיטימי נחסם כ-duplicate.

### שורש (מאומת ב-grep ישיר, לא הונח)

`guards/idempotency.py`'s `IdempotencyStore.is_duplicate(channel, sender, content)` מחשב `hash(f"{channel}:{sender}:{content}")` — המימוש עצמו תקין ו**channel-agnostic**. הבעיה הייתה **מה כל caller מעביר בתור `content`**:
- WhatsApp (Twilio, `app.py`): `dedup_key = msg_sid if msg_sid else incoming` — כבר משתמש ב-`MessageSid` הייחודי של Twilio. ✅ תקין.
- Meta WhatsApp (`app.py`): `idempotency.is_duplicate("whatsapp_meta", sender, msg_id)` — כבר משתמש ב-`msg_id` הייחודי של Meta. ✅ תקין.
- **Telegram (`app.py`):** `idempotency.is_duplicate("telegram", sender_user_id, text)` — מעביר את **טקסט ההודעה הגולמי**. ❌ זה הבאג: שתי הודעות טלגרם **נבדלות** (update_id/message_id שונים) יכולות לשאת טקסט זהה לגיטימית — הדוגמה הברורה ביותר: שני "כן" רצופים בזרימת ה-reconfirmation. מיפוי-תוכן (במקום מיפוי-זהות) גרם ל-"כן" השני להיחסם כ"כבר טופל", בלי שום דרך לשלוח אותו מחדש (הטקסט תמיד יהיה "כן").

### תיקון (מינימלי, ממוקד — לא נגע ב-`guards/idempotency.py` עצמו)

`app.py`'s Telegram call site בלבד: `_dedup_event_id = f"{update.update_id}:{update.message.message_id}"` — זהות האירוע של הספק (Telegram), לא הטקסט. `update_id` ייחודי per-bot לפי הבטחת Telegram עצמה (וזו בדיוק הסיבה ההיסטורית ל-idempotency guard — "Telegram retries"); `message_id` נוסף כהגנה-כפולה. ה-scoping לפי chat/sender כבר קיים דרך הפרמטר הקיים `sender_user_id` (הארגומנט השני, ללא שינוי). **סדר הבדיקות לא השתנה** — dedup עדיין רץ **לפני** ה-context gate (לא נחלש, לפי הוראה מפורשת).

### בדיקה

`test_bug_telegram_idempotency_key.py` (חדש, 17/17):
1. אותו `update_id`/`message_id` פעמיים → השנייה נחסמת (רטריי אמיתי של טלגרם עדיין נתפס).
2. `message_id` שונים עם טקסט "כן" זהה → **שתיהן** מעובדות (לא נחסמות).
3. הרצף המלא של reconfirmation — "כן" ראשון (event id שונה, לא נחסם) → לא מבצע, מציג מחדש; "כן" שני (event id שונה נוסף, אותו טקסט, לא נחסם) → מבצע **פעם אחת בדיוק**; חזרה אמיתית על אותו event id של ה-"כן" השני **כן** נחסמת. משלב בדיקה אמיתית של `IdempotencyStore` + state machine אמיתי של `ActionGateway` יחד.

**Regression suite מלא (כל `test_*.py` בריפו כולל `test_telegram_dedup_ordering.py`'s structural check ש-dedup עדיין לפני slash-command/gate):** כולם ירוקים, `smoke_tests.py` PASS, `python3 -m compileall app.py core/action_gateway.py cmd_update.py guards/idempotency.py` — אפס רגרסיה.

### Scope

נגעו רק ב-`app.py` (שורת ה-`content` שמועברת ל-Telegram call site). `guards/idempotency.py` עצמו, WhatsApp/Meta call sites, וסדר הבדיקות (dedup לפני gate) — **לא** שונו.

- **PR:** #313 (`claude/table-incorrect-names-6chfvb` → `main`).
- **Merged:** ✅ כן — `f8ce334` (`origin/main`), מאומת ב-grep ישיר מול `origin/main`: `_dedup_event_id = f"{update.update_id}:{update.message.message_id}"` קיים בשורות 2683-2684 של `app.py`.
- **Deployed:** ✅ כן — "Deploy live for `417cf45`" (הפריסה של #312; #313 עצמו נכלל ב-deploy הבא).
- **Verified בפרודקשן (הבדיקה עצמה — dedup לא חוסם reconfirmation לגיטימי):** ✅ כן — אימות-חי אישר: ה-global ingress gate וה-Telegram event-id dedup **שניהם עובדים כצפוי**. ה-"כן" הראשון (אחרי הפרעה) הציג מחדש נכון; ה-dedup כבר לא חסם את ה-"כן" השני.
- **⚠️ חוסם שלישי שנחשף באימות-חי — ראה Follow-up #3 למטה:** אחרי שה-reconfirmation הוצג פעם ראשונה, הפרעה **שנייה** (wizard `/update` שהשלים פעולה עסקית אחרת) לא אילצה re-display נוסף — ה-"כן" הבא ביצע את הליד הישן **בלי** להציג אותו מחדש.
- **סטטוס:** ✅ תוקן, מוזג, ונפרס — ה-dedup key עצמו אומת חי. חוסם נוסף (סמנטיקת ה-state, לא ה-dedup) תוקן ב-Follow-up #3.

---

## Follow-up #3 ל-BUG-PENDING-APPROVAL-B — בוליאנים לא מספיקים לייצג הפרעות חוזרות; FSM חסום-סיבוב-אחד — ✅ VERIFIED IN PROD

- **תאריך:** 12/07/2026.
- **מקור:** אימות-חי בפרודקשן (Follow-up #2 למעלה) — ה-gate וה-dedup עובדים; חוסם שלישי נחשף: הפרעה **שנייה** אחרי שה-reconfirmation כבר הוצג פעם אחת לא נתפסה.

### שורש (מאומת, לא הונח)

`context_interrupted`/`reconfirmation_required` הבוליאניים (PR #311) מייצגים רק "הופרע פעם אחת / לא" — ברגע ש-`reconfirmation_required=True` נקבע (אחרי ה-re-display הראשון), `route_confirmation_word()`'s תנאי הגישה (`if (context_interrupted or context_integrity_unknown) and not reconfirmation_required`) הופך תמיד ל-`False` (כי `reconfirmation_required` כבר `True`) — ולכן כל "כן" עתידי מבצע **מיידית**, בלי קשר לכמה הפרעות נוספות קרו בינתיים. זה בדיוק התרחיש שקרה בפרודקשן: preview → הפרעה #1 → "כן" (re-display, `reconfirmation_required=True`) → הפרעה #2 (`/update` wizard) → "כן" ביצע ישירות.

### עיצוב שהוחלט (הוראה מפורשת מהמשתמש — לא recursive/infinite, bounded one-shot)

המשתמש הציע תחילה מודל "context generation/version" (increment בכל הפרעה, השוואת version-at-proposal מול version-at-reconfirm) שמאפשר שרשרת בלתי-מוגבלת של re-displays. **באותה הודעה** המשתמש תיקן/הידק את המדיניות במפורש למודל **חסום, לא-רקורסיבי**: אחרי re-display אחד, כל אירוע נוסף (לא "כן"/"לא") **סוגר** את ה-contract לגמרי (SUPERSEDED), לא פותח סיבוב שני. ה-FSM הסופי המחייב:

```
PENDING
  ├─ כן              → EXECUTED
  ├─ לא              → CANCELLED
  └─ הודעה אחרת      → RECONFIRM_REQUIRED

RECONFIRM_REQUIRED (ה-prompt כבר הוצג פעם אחת)
  ├─ כן              → EXECUTED
  ├─ לא              → CANCELLED
  └─ כל דבר אחר      → SUPERSEDED (סופי — לא נפתח מחדש)
```

**הוחלט במכוון לא לממש** context_generation/version counter: המשתמש עצמו הוריד את זה לדרגת "audit-only, optional" באותה הודעה. ה-status הסופי `"superseded"` משיג את אותה ערובת-בטיחות (bounded recovery, לא infinite chain) בלי plumbing נוסף — עקבי עם ההחלטה הקודמת (BUG-108/PR-0) לא לממש `last_prompt_message_id`/`last_user_message_sequence`.

### תיקון

- **`core/action_gateway.py`:** `ExecutionLedger.mark_context_interrupted()`/`mark_context_integrity_unknown()` — לפני שמסמנים `context_interrupted`/`context_integrity_unknown`, בודקים `c.reconfirmation_required`: אם `True` (ה-prompt כבר הוצג) → `c.status = "superseded"` (סופי, לא "pending" יותר — נופל אוטומטית מ-`find_live_by_user`); אם `False` (הפרעה ראשונה) → מתנהג בדיוק כמו קודם. `ExecutionLedger.find_most_recent_by_user()` (חדש) — הקונטרקט האחרון (כל status) לזהות, לצורך הודעה ספציפית. `ActionGateway.describe_no_pending_reason()` (חדש) — כש-`len(live)==0`: אם ה-contract האחרון הוא `"superseded"` → מציג תיאור עסקי + "הפעולה הקודמת בוטלה כי התחלת פעולה אחרת... שלח את הבקשה מחדש"; אחרת — ההודעה הכללית הקיימת (`"אין פעולה שממתינה לאישור."`, ללא שינוי ניסוח — נדרש ע"י `test_c89_preview_confirmation.py`'s assertion קיים). `route_confirmation_word()`'s ענף `len(live)==0` ו-`app.py`'s Stage A fallback (המסלול שבאמת נדרס כש-`FEATURE_ACTION_GATEWAY` כבוי, ברירת המחדל) שניהם עוברים דרך ה-helper המשותף הזה — כדי שההודעה הספציפית תגיע למשתמש בפועל, לא רק ב-Stage B התיאורטי.
- **`compose_status_reply()`'s "executed" branch (שינוי נפרד, לפי בקשה מפורשת "Separately, change...")**: מציג עכשיו את התיאור העסקי הקפוא של ה-contract (`_describe_contract_for_reconfirmation`, אותו helper כמו ה-reconfirmation prompt) במקום `tool_name` גולמי — `"✅ בוצע: יצירת ליד: יוסי כהן, 050-1234567, real_estate | מזהה: recXXX"` במקום `"✅ בוצע: airtable_add | מזהה: recXXX"`. בטוח לעשות reuse כי `approved_payload == executed_payload` (ללא מוטציה בין הצעה לביצוע). tools בלי טבלה ב-payload (למשל `gmail_send_draft`) לא מושפעים — fallback ל-`tool_name` בדיוק כמו קודם.

### בדיקה

`test_bug_reconfirmation_oneshot_fsm.py` (חדש, 27/27):
- **A** (הרגרסיה המדויקת שהמשתמש ביקש): `preview → הפרעה → כן → כן` — "כן" ראשון מציג מחדש, שני מבצע פעם אחת.
- **B** (הרגרסיה השנייה המדויקת): `preview → הפרעה → כן → הפרעה נוספת → כן` — ה-contract נהיה `superseded`; "כן" האחרון **לא מבצע**; ההודעה הספציפית מוצגת (שם הפעולה + "שלח מחדש").
- **C:** הפרעה שלישית אחרי supersede — no-op חסום, אין קריסה, אין דרדור נוסף.
- **D:** "לא" אחרי reconfirmation עדיין מבטל (`status="rejected"`, לא `"superseded"`) — לא נפגע.
- **E:** ה-fallback (`context_integrity_unknown`) מקבל את אותו bounded rule.
- **F:** קבלת-הודעת-ביצוע מציגה תיאור עסקי (שם+טלפון), לא רק `tool_name`; tools בלי טבלה (למשל `gmail_send_draft`) לא מושפעים.

**Regression suite מלא (כל `test_*.py` בריפו כולל `test_c89_preview_confirmation.py`'s pinned "אין פעולה שממתינה לאישור." exact-string assertion):** כולם ירוקים, `smoke_tests.py` PASS, `python3 -m compileall app.py core/action_gateway.py` — אפס רגרסיה.

### Scope

נגעו רק ב-`core/action_gateway.py` (state machine + describe_no_pending_reason + compose_status_reply) ו-`app.py` (שורה אחת — Stage A fallback קורא ל-helper המשותף במקום מחרוזת קשיחה). לא נגעו: global ingress gate (PR #312), Telegram event-id dedup (PR #313), `ActionContract`'s frozen payload semantics, immediate-confirm behavior (DoD #1 מ-PR-0 — עדיין ללא שינוי).

- **PR:** #314 (`claude/table-incorrect-names-6chfvb` → `main`).
- **Merged:** ✅ כן — `0ef5e85` (`origin/main`), מאומת ב-grep ישיר מול `origin/main`: `status = "superseded"` (שני המקומות), `find_most_recent_by_user`, `describe_no_pending_reason`, ו-`compose_status_reply`'s תיאור-עסקי (`label = _describe_contract_for_reconfirmation(...)`) קיימים.
- **Deployed:** ✅ כן (מרומז מהלוג החי למטה — הקוד שהראה את ההתנהגות הנכונה חייב להיות זה שרץ בפרודקשן).
- **Verified בפרודקשן:** ✅ כן — לוג פרודקשן מילולי מלא, 12/07/2026, תואם **בדיוק** (מילה במילה) לעיצוב:
  1. preview: `"📋 זיהיתי ליד: מני מנחם (0567468374)\nלשמור? ענה כן לאישור או לא לביטול."`
  2. הפרעה #1+#2 (`/update` + `מעניין`, לפני כל reconfirmation) — נבלעות כראוי, contract עדיין ניתן-להצלה.
  3. "כן" ראשון → `"יש פעולה קודמת שממתינה לאישור: יצירת ליד: מני מנחם, 0567468374, general.\nלאשר אותה? (כן/לא)"` — **התאמה מדויקת** ל-`_describe_contract_for_reconfirmation`'s הפורמט ול-reconfirmation prompt. **אין** `airtable_add` בוצע.
  4. הפרעה #3 (`/gmail` + "בדוק 5 מיילים אחרונים") **אחרי** שה-reconfirmation כבר הוצג — Agent מגיב כרגיל (Gmail לא מחובר), ה-contract מסומן `superseded` בשקט ברקע.
  5. "כן" השני → `"הפעולה הקודמת בוטלה כי התחלת פעולה אחרת: יצירת ליד: מני מנחם, 0567468374, general.\nכדי לבצע אותה, שלח את הבקשה מחדש."` — **התאמה מדויקת** ל-`describe_no_pending_reason`'s superseded branch. **אין** ביצוע, אין רשומת Airtable.
- **סטטוס:** ✅ VERIFIED IN PROD (12/07/2026) — merged + deployed + רצף חי מדויק עם לוגים אמיתיים, לא unit tests/merge/deploy בלבד.

---

## סיכום BUG-PENDING-APPROVAL-B (PR #311 → #312 → #313 → #314) — ✅ VERIFIED IN PROD, כל השרשרת

כל ארבעת ה-PRs באשכול הזה אומתו חי בפרודקשן, כל אחד בתורו, ולבסוף השרשרת המלאה יחד (12/07/2026):
1. **PR #311** — state fields + reconfirmation logic (`route_confirmation_word`'s single-contract gate).
2. **PR #312** — global ingress context gate (מכסה slash commands/wizard/callbacks/media שעוקפים `run_agent()`).
3. **PR #313** — Telegram idempotency key = event identity (`update_id:message_id`), לא טקסט — כדי ש-"כן" חוזר לא ייחסם.
4. **PR #314** — bounded one-shot FSM (`SUPERSEDED` אחרי הפרעה שנייה) + קבלת-ביצוע עם תיאור עסקי.

---

## BUG-TMA-APPROVAL-TRUTHFULNESS (PR-0C0) — TMA `bulk_approve` סימן אושר בלי לבצע כלום; `_try_bus_action` בלע כל תוצאה בשקט

- **דווח:** 12/07/2026, כחלק מ-Contract Chain רחב לשלושת מנגנוני האישור המקבילים (PR-0B `app.py::_pending_approvals`, PR-0C `event_bus.PendingActionsStore`, ומנגנון רביעי שהתגלה — טבלת Airtable "Approvals" הנצרכת אך ורק ע"י `tma_api.py`).
- **מסך / מודול:** `tma_api.py` — `bulk_approve()` (route `/api/approvals/bulk`), `_try_bus_action()`, `act_on_approval()`.

### Contract Chain מצומצם על טבלת Airtable "Approvals" (כפי שהתבקש לפני המימוש)
- **Writer יחיד בפועל:** `_queue_tma_write_approval()` — כל רשומה נכתבת עם `CONTEXT_TYPE="tma_write"` ו-`CONTEXT_ID=<action name string>` (לעולם לא `event_bus` action_id אמיתי).
- **Status transitions:** מודל 3-מצבים תקין וקיים מראש — `ממתין → מעבד (durable claim ב-Airtable) → אושר | נכשל`, ממומש נכון ב-`act_on_approval()`'s single-item approve path (claim לפני ביצוע, re-read בתוך lock סוגר race).
- **קשר ל-EventBus IDs:** מכיוון ש-`CONTEXT_ID` הוא תמיד שם-פעולה של TMA ולא action_id אמיתי, `_try_bus_action()` מפספס תמיד היום ב-harmless way — **לא קיים היום תרחיש live שבו TMA מאשרת פעולת-כלי (tool-based) עם `.confirmed` subscriber אמיתי דרך הנתיב הזה.** זו תיקון-מסלול לתיקון האודיט הקודם שלי (שהניח בטעות שהתרחיש הזה קורה היום).
- **סדר ביצוע:** בנתיב היחיד (`act_on_approval`) התיקון הקודם (BUG-090-ish 3-state) כבר הבטיח claim-before-execute-before-finalize. **הבאג האמיתי היה ב-`bulk_approve()` בלבד** — נתיב מקביל, נפרד, שמעולם לא קרא ל-`_execute_tma_write()`: הוא כתב `{"סטטוס": "אושר"}` ישירות ל-Airtable בלי ביצוע כלשהו, כלומר "בulk approve" של N רשומות low-risk לא ביצע אף פעולה אחת בפועל — TMA דיווחה ואישרה משהו שמעולם לא רץ.
- **Restart behavior:** אין persistence ל-in-memory event_bus items — restart מוחק pending items שם. `_try_bus_action` על context_id שאבד ב-restart פשוט מחזיר False (miss), לא raise — לא היה תקין קודם (הערך פשוט נבלע ב-`except Exception: pass` ברמת DEBUG).
- **Failure/retry states:** לפני התיקון — אין מסלול retry, כל exception אחרי claim משאיר רשומה תקועה לצמיתות ב-`מעבד`. אחרי התיקון — `_claim_and_execute_approval()` מחזירה רשומה שנתקעה ל-`ממתין` בכל exception לא-צפוי אחרי ה-claim, כדי לאפשר ניסיון חוזר.
- **האם TMA מסמנת אושר לפני ביצוע:** **כן, זה בדיוק הבאג** — רק ב-`bulk_approve()`. הנתיב היחיד היה כבר תקין.

### Root Cause
כפילות קוד: `act_on_approval()` (יחיד) ו-`bulk_approve()` (מרובה) מימשו שתי גרסאות עצמאיות של אותה לוגיקה — האחת claim→execute→finalize מלאה, השנייה PATCH ישיר בלי execute בכלל. אין single source of truth לרצף האישור.

### התיקון (commit על גבי `claude/table-incorrect-names-6chfvb`)
1. **`_try_bus_action()`** — שוכתב להחזיר `bool` אמיתי. `_BUS_MISS_MESSAGES` (frozenset) מבחין בין "אין מה לסנכרן" (המצב הצפוי היום, לפי ה-Contract Chain למעלה) לבין "נמצא אבל event_bus עצמו דיווח כישלון" — כבר לא נבלע בשקט ב-DEBUG.
2. **`_claim_and_execute_approval(approval_id, identity)`** — helper משותף חדש, ממומש פעם אחת: claim (`ממתין→מעבד` בתוך lock, re-read סוגר race) → `_execute_tma_write()` אם יש `tma_write` payload → finalize ל-`אושר` רק על הצלחה, אחרת `נכשל`. Exception לא-צפוי אחרי ה-claim מחזיר את הרשומה ל-`ממתין` (לא משאיר תקוע ב-`מעבד`).
3. **`act_on_approval()`** — נתיב האישור הבודד שוכתב לקרוא ל-helper המשותף במקום ללוגיקה מוטבעת; נתיב הדחייה חושף `bus_synced` בתגובת ה-JSON במקום להשליך אותו.
4. **`bulk_approve()`** — **התיקון המרכזי.** במקום `_at_patch(..., {"סטטוס": "אושר"})` ישיר, כל רשומה low-risk עוברת דרך `_claim_and_execute_approval()`. רשומות high/medium risk ממשיכות לא להיגע בהן (hard rule ללא שינוי). התגובה כוללת עכשיו `approved`/`failed`/`skipped` נפרדים במקום `approved`/`skipped` בלבד — "failed" חדש כדי לחשוף רשומות שנכשלו בביצוע בפועל, לא רק "לא low-risk".

### Tests
`test_pr0c0_tma_approval_truthfulness.py` (חדש, 22 assertions) — מכסה: miss strings מ-event_bus (כולל restart שמאבד in-memory item) → False; sync אמיתי → True; exception מ-event_bus לא מתפשט (נבלע ל-False); `bulk_approve` מבצע `_execute_tma_write` בפועל לפני ספירת "approved"; כשל ביצוע → "failed" ולא "approved" (הבאג המקורי); high/medium risk לא נגעת אף פעם; recovery מ-`מעבד` תקוע ל-`ממתין` אחרי exception לא-צפוי; `bus_synced` נחשף באמת (True/False) בתגובת reject. `test_approval_concurrency.py` הקיים עודכן (4 מקומות) להעביר `return_value=False` מפורש ל-mock של `_try_bus_action` — לפני התיקון `MagicMock()` לא-מוגדר לא נכנס אף פעם ל-JSON response, אחרי התיקון כן (ונכשל serialization בלי הערך המפורש).

כל 22/22 assertions חדשות עברו, כל test_*.py הקיימים (כולל `test_approval_concurrency.py` המעודכן), `smoke_tests.py`, ו-`test_integration.py` עברו full run לאחר השינוי.

- **Severity:** High — "אישור" כוזב על פעולות שלא בוצעו הוא בדיוק אותה מחלקת באג כמו BUG-108/BUG-PENDING-APPROVAL-B, בנתיב אישור נפרד.
- **תוקן ב-commit:** `1d3ed4b` (PR #316, `75fc242` merge commit ל-`main`) — אומת ב-`git show origin/main:tma_api.py \| grep _claim_and_execute_approval` שהקוד קיים בפועל ב-main, לא רק ב-git log.
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** כן — PR #316
- **Deployed:** לא ידוע — דרוש בדיקה ידנית (Render), לא אומת בסבב הזה
- **Verified בפרודקשן:** לא — merge מאומת, production behavior לא נבדק חי
- **סטטוס:** Merged. PR-0C (הגירת event_bus writers ל-ActionGateway) מתחיל כעת.
- **הערה על scope:** זהו PR-0C0 בלבד — hotfix ל-truthfulness. PR-0C (הגירת 6 ה-writers החיים ל-`ActionGateway.propose_action()`, כולל הפיכת טבלת Airtable "Approvals" ל-projection/audit log או הסרתה) ו-PR-0B (הגירת `app.py::_pending_approvals`) עדיין פתוחים ונדרשים לפני תחילת UnderstandingResult/BUG-104A, לפי הנחיית הבעלים המפורשת.

---

## PR-0C — Phase 1/4: ActionGateway adapters for media_save_to_memory/send_followup/send_recovery

- **דווח:** 12/07/2026, כחלק מהגירת PR-0C (event_bus approval writers → ActionGateway) לפי סדר עבודה שהבעלים אישר מפורשות: 4 PRs נפרדים כמו שרשרת BUG-108 (#311-#314) — (1) adapters, ללא שינוי התנהגות; (2) `app.py::_queue_approval` + כפתור טלגרם; (3) 5 ה-writers החיצוניים; (4) TMA + טבלת Airtable Approvals + deprecation ל-`PendingActionsStore`. זהו ה-PR הראשון בשרשרת.
- **Finding מרכזי (grounding לפני מימוש):** `ActionGateway._execute_contract()` יודע לבצע אך ורק דרך `dispatch_tool(tool_name, tool_inputs, contract_id)` — אין נתיב גנרי ל"הרצת callback Python שרירותי". לכן "adapters" ל-`media_save_to_memory`/`send_followup`/`send_recovery` פירושו להפוך כל אחת מהן לכלי dispatcher אמיתי (checklist מלא: `tools/schemas.py`, `tool_registry.py`, `tools/dispatcher.py`), לא רק "לחבר" אותן ל-Gateway.
- **החלטת עיצוב (owner-confirmed via AskUserQuestion):** מסלול "✏️ עריכה" ב-`media_handler.py` (שהיום מדלג על אישור לגמרי — pop + שמירה ישירה של הטקסט הערוך) **לא** ישמר כ-bypass. יטופל בפאזה מאוחרת יותר (לא כאן) כ"הצעה חדשה": ה-contract הישן נשאר, הטקסט הערוך יוצר `propose_action()` חדש עם preview טרי, וההצלה תתבצע רק אחרי "כן" מפורש — לא מתוך העריכה עצמה.

### מה נבנה (Phase 1 — תוסף בלבד, אפס שינוי התנהגות לקוראים קיימים)
1. **`tools/approval_actions.py`** (חדש) — שלוש הפונקציות, מראה 1:1 את הלוגיקה המקורית (`app.py::_handle_send_followup_confirmed`/`_handle_send_recovery_confirmed`, `media_handler.py::_save_transcript_to_memory`), כולל אי-הסימטריה הקיימת בין followup (לא בודק `delivery_success` לפני `followup_count+=1`) ל-recovery (כן בודק, לא מגדיל מונה) — לא תוקן כאן, לא בהיקף ה-migration. מחזירות את חוזה C53-A המובנה (`{ok, tool, external_id, evidence, user_message}`) במקום string גולמי.
2. **`tool_registry.py`** — שלושת הכלים נרשמו: `roles_allowed=_INTERNAL`, `requires_approval=True`, `blocked_by_emergency=True`. שים לב: `blocked_by_emergency=True` הוא תוספת-בטיחות חדשה שלא הייתה קיימת קודם (event_bus.confirm() לא עבר דרך `EMERGENCY_STOP_ALL` בכלל) — לא "no behavior change" טהור, אבל תואם את הכוונה המוצהרת של הדגל ("חוסם את כל כלי הכתיבה/שליחה") ואינו פעיל היום כי אין עדיין caller אמיתי (Phase 2/3).
3. **`tools/dispatcher.py`** — נוסף `case` לכל אחד משלושת הכלים, קורא ל-`tools.approval_actions.*`.
4. **`action_validator.py`** — נוסף `_REQUIRED` entry לכל כלי (שלב-הגנה נפרד מ-tool_registry שכמעט התפספס — `dispatch_tool()` חוסם "כלי לא מוכר" *לפני* ה-match/case אם הכלי לא רשום כאן).
5. **`tools/schemas.py`** — נוספו schemas ל-`_APPROVAL_ACTION_SCHEMAS_HIDDEN` (בדומה ל-`_CRM_SCHEMAS_HIDDEN`) — **במכוון לא** ב-`TOOL_SCHEMAS`, כדי שה-Agent tool_use loop לא יוכל להציע את הפעולות האלה בעצמו; רק קוד Python מהימן (Phase 2/3: `media_handler.py`/`followup_engine.py`/`core/lead_recovery.py`) יוכל לקרוא ל-`ActionGateway.propose_action(trusted_source=...)`.
6. **`core/anti_hallucination.py`** — נוספו `_validate_media_memory_evidence`/`_validate_owner_draft_evidence` ל-`_EVIDENCE_VALIDATORS`. קריטי: מכיוון ש-`requires_approval=True`, שלושת הכלים אוטומטית ב-`_WRITE_ACTION_TOOLS`, ובלי validator `verify_execution()` היה נכשל-סגור על כל ביצוע (fail-closed by design) — זה היה חוסם כל approve() עתידי דרך ה-Gateway.

### Tests
`test_pr0c_action_gateway_adapters.py` (חדש, 34 assertions) — מכסה: לוגיקת כל פונקציה (הצלחה/כישלון, כולל exception מ-`send_outbound`); רישום ב-`tool_registry` + roles; ניתוב ב-`dispatcher`; היעדר מ-`TOOL_SCHEMAS`; `verify_execution` מקבל/דוחה נכון; **מסלול end-to-end מלא**: `ActionGateway.propose_action() → approve() → dispatch_tool() → tools.approval_actions.* → verify_execution()`, contract מסתיים ב-status `"executed"`.

`test_c83_single_policy_source.py` הקיים עודכן (`EXPECTED_APPROVAL_TOOLS` allowlist) — נכשל בצדק אחרי הוספת 3 הכלים ל-registry (regression מכוון, לא שבור).

כל 34/34 assertions חדשות עברו, כל test_*.py הקיימים (כולל השניים המעודכנים), `smoke_tests.py`, ו-`test_integration.py` עברו full run לאחר השינוי.

- **Severity:** N/A — תשתית תוספת, לא תיקון באג. חלק מ-PR-0C.
- **תוקן ב-commit:** `db98d82` (PR #317, `119f053` merge commit ל-`main`) — אומת ב-`git show origin/main:tools/dispatcher.py \| grep approval_actions` שהקוד קיים בפועל ב-main.
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** כן — PR #317
- **Deployed:** לא ידוע — דרוש בדיקה ידנית (Render)
- **Verified בפרודקשן:** לא — אין עדיין caller אמיתי (Phase 2/3 יחברו את 6 ה-writers + כפתור טלגרם + TMA)
- **סטטוס:** Phase 1/4 של PR-0C הושלם ומוזג. Phase 2 (`app.py::_queue_approval` + כפתור טלגרם) — ראה רשומה הבאה.

---

## PR-0C — Phase 2/4: Telegram approve button executes through ActionGateway.approve()

- **דווח:** 12/07/2026, המשך ישיר ל-Phase 1 (adapters, PR #317).

### Finding מרכזי (grounding לפני מימוש)
`app.py::_queue_approval` **כבר** קורא ל-`ActionGateway.propose_action()` היום — בין אם `FEATURE_ACTION_GATEWAY` דלוק (חוסם בפועל אם `propose_action` מחזירה `ok=False`) או כבוי (shadow mode, best-effort, לא חוסם). המשמעות: ה-caller **כבר** "migrated" בחלקו. הפער האמיתי היה במקום אחר — `_handle_approval_callback_impl` (כפתור ✅/❌ בטלגרם) **מעולם לא** קרא ל-`ActionGateway.approve()`; הוא ביצע `dispatch_tool()` ישירות ואז "סנכרן" ידנית את סטטוס ה-contract ב-ledger בדיעבד (בלוק "Stage B sync", מסתמך על fingerprint lookup חוזר) — כפילות מלאה של הלוגיקה ש-`approve()`/`_execute_contract()` כבר מספקים (claim → dispatch → verify_execution → עדכון סטטוס).

### מה השתנה (`app.py::_handle_approval_callback_impl`, ענף approve עם tool_name)
כאשר `FEATURE_ACTION_GATEWAY` דלוק **וגם** נמצא contract חי (`status="pending"`) עבור אותו fingerprint (tenant_id+canonical_user_id+tool_name+normalized_payload — אותו נוסחה בדיוק כבר בשימוש ב-SB-02 pre-check הקיים) — הביצוע עובר עכשיו דרך `gw.approve(contract_id, approver=..., approver_role=...)` במקום `dispatch_tool()` ישיר. אם לא נמצא contract (למשל shadow propose_action נכשל בשקט, או הדגל כבוי) — **נופל חזרה ל-fallback המקורי** (`dispatch_tool()` ישיר) בלי שינוי התנהגות — לעולם לא מצב כשל חדש לעומת היום.

**BUG-074 קריטי:** `approver_role` המועבר ל-`approve()` הוא התפקיד של **המאשר בפועל** (`approver_identity`, שנפתר מ-`cq.from_user.id` בתחילת הפונקציה) — **לא** של `identity` (מבקש הפעולה המקורי, שמשמש רק לביצוע עצמו דרך `contract.actor_role`/`actor_external_id` שכבר הוקפאו ב-`_queue_approval`). זהו בדיוק ההבחנה ש-BUG-074 דורש במפורש בתיעוד הפנימי של `ActionGateway.approve()`. נבדק במפורש ב-test (ראה למטה) עם מבקש=employee (חסר סמכות אישור) ומאשר=owner — ה-contract מבוצע בהצלחה, מה שהיה נכשל אם הקוד היה (בטעות) גוזר את approver_role מה-מבקש.

הבלוקים הקיימים סביב (SB-02 duplicate pre-check, SB-04 status wrap, Stage-B sync, executed_action_cache, cross-channel completion) **לא שונו** — הם ממשיכים לפעול נכון: ה-Stage-B sync block הופך אוטומטית ל-no-op כשמשתמשים בנתיב Gateway (כי ה-contract כבר "executed" בזמן שהבלוק רץ, לא "pending"), וה-SB-04 wrap מדלג על wrapping מחדש כי `result` הוא כבר string (מה ש-`compose_status_reply` כבר בנה בתוך `approve()`).

### Finding נלווה (לא תוקן כאן — מחוץ ל-scope, מתועד להמשך טיפול)
בזמן כתיבת הטסטים התגלה שה-SB-02 duplicate pre-check (`bus.get(action_id)`) **נכשל תמיד** בשקט: `EventBus` (המחלקה החיצונית שנחשפת כ-`bus` singleton) **אין לה מתודת `get()`** — רק ה-`PendingActionsStore` הפנימי כן. הקריאה תמיד זורקת `AttributeError`, נתפסת ע"י ה-`except Exception` הרחב ב-SB-02, ומתועדת רק כ-warning. המשמעות: הגנת ה-duplicate-approval-blocking של SB-02 מעולם לא הייתה פעילה בפועל מאז שנכתבה. זו לא רגרסיה מה-PR הזה (הבאג קדם לו) ולא תוקנה כאן כדי לא לערבב scope — ראוי לבאג נפרד.

### Tests
`test_pr0c_telegram_callback_gateway.py` (חדש, 8 assertions) — מריץ את `app._handle_approval_callback_impl` בפועל (עם `event_bus.bus` ו-`core.action_gateway.action_gateway` אמיתיים, רק `bot`/`resolve_identity`/`dispatch_tool`/דגלים מדומים): (1) דגל כבוי → נתיב legacy, dispatch פעם אחת; (2) דגל דלוק + contract חי → נתיב Gateway, dispatch פעם אחת, contract מסתיים "executed"; (3) **BUG-074 differential** — מבקש=employee, מאשר=owner → מבוצע בהצלחה (מוכיח ש-approver_role הוא של המאשר, לא המבקש); (4) דגל דלוק בלי contract → fallback ל-legacy, dispatch פעם אחת; (5) דגל דלוק + contract חי + ביצוע נכשל → contract מסתיים "failed", dispatch פעם אחת (ללא retry).

כל 8/8 assertions חדשות עברו, כל test_*.py הקיימים, `smoke_tests.py`, ו-`test_integration.py` עברו full run לאחר השינוי.

- **Severity:** N/A — migration, לא תיקון באג. חלק מ-PR-0C.
- **תוקן ב-commit:** `0bca565` (PR #318, ראה סטטוס merge בהמשך)
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** לא עדיין (PR #318 פתוח, CI ירוק, אין review comments)
- **Deployed:** לא
- **Verified בפרודקשן:** לא — `FEATURE_ACTION_GATEWAY` כבוי כברירת מחדל, אין שינוי התנהגות היום עד שהדגל יופעל ויאומת בנפרד
- **סטטוס:** Phase 2/4 של PR-0C הושלם (ממתין ל-merge). Phase 3 — ראה רשומה הבאה.

---

## PR-0C — Phase 3/4: migration של 3 מתוך 5 ה-writers החיצוניים + blocker לשניים הנותרים

- **דווח:** 12/07/2026, המשך ישיר ל-Phase 2 (PR #318).

### Finding מרכזי (grounding לפני מימוש)
מיפוי מדויק של 5 ה-writers החיצוניים חשף שרק 3 מתוכם (media_handler.py, followup_engine.py, core/lead_recovery.py) שולחים payload שמתאים ל-3 ה-adapters שנבנו ב-Phase 1 — **אבל** ה-payload שלהם היה בפורמט "non-tool" (`{transcript, domain, source}` וכו', בלי `tool_name`/`tool_inputs`), מה שגרם ל-`_handle_approval_callback_impl` לנתב אותם דרך ה-ענף הישן `bus.emit(f"{action}.confirmed", ...)` **ולא** דרך ה-tool_name branch שכבר עבר migration ל-ActionGateway ב-Phase 2. כלומר: בניית ה-adapters (Phase 1) והעברת נתיב-הביצוע (Phase 2) לא הספיקו — היה צריך גם לשנות את **צורת ה-payload** בזמן ה-request כדי שהזרימה בפועל תשתמש בהם.

שני writers נוספים (`email_inbound.py`'s `send_email_reply`, `abandoned_lead_worker.py`'s `send_bounce`) **אין להם `.confirmed` subscriber בכלל** — אישור שלהם היום מסתיים תמיד ב-"⚠️ אין handler — הפעולה לא בוצעה." שניהם flag-off (`EMAIL_INBOUND`, `ABANDONED_LEADS`) ולא מאומתים בפרודקשן. **החלטת בעלים (12/07/2026):** לא לגעת בשני אלה ב-PR-0C — להשאיר על המסלול הישן, ו**להוסיף blocker מפורש** שמונע הדלקת הדגלים לפני שהאדפטר המלא (schema+registry+dispatcher+service+tests) קיים.

### מה השתנה
1. **`core/action_gateway.py`** — `ActionGateway.propose_gated()` (helper משותף חדש) עוטף את הרצף shadow/enforced שכבר קיים ב-`app.py::_queue_approval` (דגל דלוק → `propose_action()` חוסם באמת; דגל כבוי → shadow best-effort, אף פעם לא חוסם, בולע exceptions) — כדי שלא כל writer חדש יממש את אותו קוד בעצמו. `_queue_approval` עצמו **לא שונה** (כבר עובד ונבדק ב-Phase 2 המוזג).
2. **`media_handler.py`** — `_send_voice_approval_request()` בונה עכשיו payload עם `tool_name="media_save_to_memory"`+`tool_inputs`, קורא ל-`propose_gated()`. `_handle_memory_confirmed` וההרשמה שלו הוסרו (dead code — לא ניתן להגיע אליהם יותר). `_cb_voice_edit` תוקן לקרוא ל-`domain`/`source` מתוך `payload["tool_inputs"]` במקום מה-payload הישן (top-level) — **תיקון מכני בלבד**, לא redesign. מסלול "✏️ ערוך" עדיין שומר ישירות בלי אישור מחדש — כפי שהוחלט קודם ("Route edit as a new proposal"), redesign זה **עדיין לא מומש**, נשאר open item מפורש (ראה למטה).
3. **`followup_engine.py`** — `request_followup_approval()` בונה payload עם `tool_name="send_followup"`+`tool_inputs`, קורא ל-`propose_gated()`.
4. **`core/lead_recovery.py`** — `request_recovery_approval()` בונה payload עם `tool_name="send_recovery"`+`tool_inputs` (כולל `tier`), קורא ל-`propose_gated()`.
5. **`app.py`** — `_handle_send_followup_confirmed`/`_handle_send_recovery_confirmed` והרשמותיהם הוסרו (dead code אחרי (3)/(4) — לא ניתן להגיע אליהם יותר, כל ה-writers ששלחו אליהם עברו ל-tool_name payload).
6. **`feature_flags.py`** — `is_enabled()` חוסם כעת מבנית הדלקת `EMAIL_INBOUND`/`ABANDONED_LEADS` אם `tool_registry` אין לו entry ל-`send_email_reply`/`send_bounce` בהתאמה (fail-closed, לא רק תיעוד) — ה-blocker המפורש שהבעלים ביקש.

### Open item שלא טופל כאן (מוצהר, לא הוסתר)
מסלול "✏️ ערוך" ב-media_handler.py עדיין שומר ישירות מהעריכה בלי preview/אישור מחדש (כפי שהיה). ה-redesign ל"עריכה = הצעה חדשה" (contract ישן נשאר, טקסט ערוך יוצר propose_action חדש, preview טרי, רק "כן" מבצע) **הוחלט אך לא מומש** — נדרש state-machine נוסף (מעקב pending-edit-proposal, trigger "כן" חדש) שהוא מחוץ ל-scope של "migrate 5 writers". ממתין לפרויקט נפרד.

### Tests
`test_pr0c_writer_migration.py` (חדש, 16 assertions) — מכסה: `propose_gated()` (shadow לא חוסם/בולע exceptions מול enforced חוסם על duplicate); שלושת ה-writers בונים payload עם `tool_name`/`tool_inputs` נכונים; `_cb_voice_edit` קורא נכון מה-nested `tool_inputs`.

**תופעת לוואי חשובה:** בזמן ריצת רגרסיה התגלה ש-`test_c81_recovery_truth.py` (pytest-style, `assert`-based) **אף פעם לא רץ בפועל** תחת ריצת `python3 <file>.py` (הקובץ לא מריץ את הפונקציות שלו בלי `pytest`, ואין footer `if __name__=="__main__"`), וגם לא נכלל ב-allowlist ה-pytest המפורש של `.github/workflows/ci.yml`. הוא נשבר בפועל אחרי הסרת `_handle_send_recovery_confirmed` (2 טסטים קראו לו ישירות) — עודכן לקרוא ל-`tools.approval_actions.send_recovery()` החדש, ואומת ב-`python3 -m pytest`. **לא תוקן כאן**: הוספת הקובץ ל-CI pytest allowlist — מחוץ ל-scope, ראוי לבאג נפרד ("CI blind spot: pytest-style test_*.py files not covered by either CI mechanism").

הרצה מלאה: כל ה-`test_*.py` (הרצת script + הרצת pytest מפורשת על כל הקבצים ה-pytest-style), `smoke_tests.py`, ו-`test_integration.py` — ירוק, פרט ל-flake ידוע וקודם ב-`test_session_store_contract.py::test_raw_records_reader_follows_airtable_pagination` (עובר לבד, נכשל רק כשרץ יחד עם קבצים אחרים — לא קשור לשינוי הזה).

- **Severity:** N/A — migration + blocker חדש, לא תיקון באג. חלק מ-PR-0C.
- **תוקן ב-commit:** `6391328` (PR #319, `570a367` merge commit ל-`main`) — אומת ב-`git show origin/main:app.py \| grep _handle_send_recovery_confirmed` (0 תוצאות, dead code הוסר בפועל).
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** כן — PR #319
- **Deployed:** לא ידוע — דרוש בדיקה ידנית (Render)
- **Verified בפרודקשן:** לא
- **סטטוס:** Phase 3/4 של PR-0C הושלם ומוזג. Phase 4 — ראה רשומות הבאות (פוצל ל-4A/4B לפי החלטת הבעלים).

---

## PR-0C — Phase 4A/4B: durable ActionContracts persistence + resolve Airtable Approvals table role

- **דווח:** 12/07/2026, המשך ישיר ל-Phase 3 (PR #319).

### החלטת הבעלים (מפורשת, custom answer ב-AskUserQuestion)
- **ActionContracts = מקור אמת יחיד וקנוני** (durable, ב-Airtable).
- **Approvals = read-model/projection ל-TMA בלבד** — display-safe fields, לא payloads/fingerprints/secrets פנימיים.
- שדה "Action Contract ID" נוסף ל-Approvals, מקשר לרשומת ActionContracts הקנונית.
- TMA list endpoints ממשיכים לקרוא מ-Approvals (ללא שינוי).
- TMA approve/reject קוראים ל-ActionGateway לפי Action Contract ID — **אסור** לעדכן סטטוס terminal ישירות על Approvals.
- Projection ל-Approvals מתעדכן **אחרי** שינוי סטטוס קנוני ב-ActionContracts (idempotent).
- רשומות Approvals ישנות (legacy) מתנקזות/פגות — **לא** replay אוטומטי.
- מותר לפצל: **4A** (persistence durable) + **4B** (projection + TMA command routing). בוצע בדיוק כך.
- ביצוע TMA כשירותג: route דרך `airtable_add`/`airtable_update` (כלים קיימים, מחוזקים, עם evidence validators) — לא reuse ל-`_execute_tma_write()`.

### Finding מרכזי (grounding לפני מימוש) — Phase 4A
`core/action_gateway.py::_build_airtable_writer()` היה כתוב במלואו מראש (factory שבודק `hasattr(Tables, "ACTION_CONTRACTS")` ובונה writer ל-Airtable), אבל **מעולם לא חובר** — ה-singleton היה hardcoded ל-`airtable_writer=None` ("RAM-only until Airtable table exists"). בנוסף התגלה שהפונקציה שהוא מייבא, `tools.airtable_gateway.at_upsert`, **לא הייתה קיימת בכלל בקוד** — כלומר גם אם היה מחובר, הייתה נכשלת ב-`ImportError` (נבלע ב-`except Exception: return None` הרחב) בכל קריאה. שתי הבעיות תוקנו יחד.

### מה נבנה — Phase 4A
1. **`airtable_schema.py`** — `Tables.ACTION_CONTRACTS = "ActionContracts"` (טבלה חדשה, נוצרה בפועל דרך Airtable MCP בבסיס החי `app4bcgoX7t0HUVnm`, מאומתת בכתיבה/מחיקה של רשומת בדיקה). `ActionContractsFields` — שמות שדות תואמים 1:1 למה ש-`_build_airtable_writer()`'s `_writer()` כבר שולח. `ActionContractStatus` — 8 הערכים בפועל בקוד. כולל כעת spec מלא לשחזור הטבלה בסביבה אחרת (אין עדיין script אוטומטי — פער מוצהר, ראה תיקון למטה).
2. **`tools/airtable_gateway.py`** — `at_upsert(table, fields, match_field, source)` חדש: מחפש רשומה קיימת לפי `{match_field}=value`, `airtable_patch` אם נמצא אחרת `airtable_create`.
3. **`core/action_gateway.py`** — `_build_airtable_writer()` תוקנה לא לבלוע exceptions בשקט (logger.warning נוסף).

### תיקון קריטי לפני merge (code review, לא self-caught)
ה-reviewer עצר את ה-merge וזיהה שהתיאור המקורי של ה-PR **כזב בטעות** בשתי נקודות מהותיות:

1. **"Phase 4A הוא תשתית בלבד, אין caller חי" — לא נכון.** `_queue_approval` (app.py) וכל שלושת ה-writers שהיגרו ב-Phase 3 (media_handler.py, followup_engine.py, core/lead_recovery.py) כבר קוראים ל-`action_gateway.propose_action()`/`propose_gated()` **ללא תנאי** בפרודקשן היום (shadow mode כש-`FEATURE_ACTION_GATEWAY` כבוי). חיבור ה-`airtable_writer` ל-singleton היה גורם לכתיבות אמיתיות ל-Airtable בכל בקשת אישור בפרודקשן **מיד עם ה-merge** — שינוי התנהגות חי, לא "אפס שינוי" כפי שנכתב.
2. **"ActionContracts = מקור אמת קנוני" מוקדם מדי.** `ExecutionLedger` הוא RAM-only לחלוטין — אין נתיב read/recovery (load-by-contract_id אחרי restart, שחזור pending contracts). writer-only אינו הופך טבלה למקור אמת דורבל; Phase 4B לא יכול לנתב TMA לפי contract_id בביטחון בלי הנתיב הזה.

**תיקון שבוצע (באותו commit, לפני merge):**
- **`_ledger_singleton` הוחזר במפורש ל-`airtable_writer=None`** — Phase 4A נשאר תשתית אמיתית (schema+at_upsert+build_writer בנויים ונבדקים), אבל ה-singleton החי **לא מחובר** עד שיהיה נתיב read/recovery, הגנת concurrency, ואימות מחוץ לפרודקשן.
- `_build_airtable_writer()` — exceptions כבר לא נבלעים בשקט לגמרי (logger.warning).
- `at_upsert()` — docstring מתעד במפורש TOCTOU race ידוע (יצירה כפולה בכתיבה מקבילה על אותו contract_id חדש; כתיבה stale יכולה לדרוס סטטוס חדש יותר) — לא תוקן (דורש locking/versioning אמיתי), מתועד כמגבלה חסומה לפני production rollout אמיתי.
- `ActionContractsFields` docstring עודכן להסיר את הניסוח "canonical durable truth" עד ששני הנתיבים (write + read/recovery) קיימים.
- נוסף regression test מפורש: `action_gateway._ledger._airtable_writer is None` — נכשל בקול אם מישהו יחבר את ה-singleton לפני שהעבודה הנדרשת (read/recovery path, concurrency review, אימות מחוץ ל-production) הושלמה.

### Tests — Phase 4A (מעודכן)
`test_pr0c_action_contracts_persistence.py` (15 assertions, לא 14) — מכסה: `at_upsert` create/patch/missing-match-value; `_build_airtable_writer()` מחזירה callable אמיתי; ה-writer שולח שדות נכונים; `ExecutionLedger.save()`/`update_status()` קוראים ל-writer; writer שזורק exception לא מאבד רשומה מה-RAM; **וה-live singleton עדיין לא מחובר** (regression guard חדש).

כל 15/15 assertions עברו, כל test_*.py הקיימים, `smoke_tests.py`, ו-`test_integration.py` עברו full run (אותו flake ידוע וקודם ב-`test_session_store_contract.py`, לא קשור).

### נשאר פתוח לפני שמחברים את ה-singleton בפועל (לא בהיקף ה-PR הזה)
- נתיב read/recovery: load-by-contract_id, שחזור pending contracts אחרי restart, reconciliation.
- הגנת concurrency/version ל-`at_upsert` (TOCTOU race מתועד, לא מתוקן).
- מדדים/observability מבניים לכשלי כתיבה (מעבר ל-log warning בודד).
- script provisioning אוטומטי לסביבות נוספות (staging וכו') — כרגע spec כתוב ב-docstring בלבד, לא script.
- אימות rollout מחוץ ל-production לפני חיבור אמיתי.

- **Severity:** N/A — תשתית. חלק מ-PR-0C. (הכזב בתיאור המקורי תוקן — לא היה fix ל-production bug, אלא תיקון claim לא-מאומת לפני merge).
- **תוקן ב-commit:** `5045439` (PR #320, `c80a821` merge commit ל-`main`) — אומת ב-`git show origin/main:core/action_gateway.py \| grep "airtable_writer=None"`.
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** כן — PR #320
- **Deployed:** לא ידוע — דרוש בדיקה ידנית (Render). טבלת Airtable כן נוצרה בפועל בבסיס החי — verified via MCP.
- **Verified בפרודקשן:** לא רלוונטי — אין שינוי live (singleton לא מחובר)
- **סטטוס:** Phase 4A הושלם ומוזג אחרי תיקון code review. Phase 4B0 — ראה רשומה הבאה.

---

## PR-0C — Phase 4B0: Durable Ledger Recovery (prerequisite ל-Phase 4B)

- **דווח:** 12/07/2026, המשך ישיר להחלטת ה-reviewer ב-Phase 4A: "Phase 4B cannot route TMA commands reliably by contract ID without this [read/recovery path]." הבעלים אישר במפורש להמשיך (לא לעצור), עם spec מדויק.

### דרישת הבעלים (מפורשת, verbatim עיקרי)
"Do not route TMA approve/reject by contract_id while ExecutionLedger remains memory-only. Insert Phase 4B0 — Durable Ledger Recovery before the projection/routing work. Implement an ActionContractRepository... find_by_id() must fall back to the repository, reconstruct the frozen contract, validate tenant/identity/expiry, and hydrate the cache. Approve/reject must use a compare-and-set or version-guarded durable transition so two Render instances cannot both execute the same contract... Fail closed when the durable store is unavailable... Never re-plan from raw text or create a replacement contract as recovery. Add restart, multi-instance race, identity-binding, expiry, repeated-approval, stale-status-regression, and store-outage tests."

### מה נבנה
1. **`core/action_contract_repository.py`** (חדש) — `ActionContractRepository`: `save()` (upsert מלא), `get()` (fail-closed על not-found/store-unreachable/expired — לעולם None, לא fallback ל-fabricate), `guarded_transition()` (verify-read → PATCH → verify-reread; **לא CAS אמיתי** — Airtable REST API אין לו conditional-write primitive, מתועד במפורש כ"מצמצם את חלון המרוץ, לא סוגר אותו לגמרי"), `find_pending_by_canonical_user()`.
2. **`airtable_schema.py`** — 12 שדות חדשים ל-`ActionContractsFields`: `version` (guard ל-optimistic concurrency), שדות זהות מלאים (`actor_role/user_id/display_name/domain_id/external_id/allowed_domains`), `approval_policy`, `trusted_source`, ושלושת דגלי ה-context (`context_interrupted`, `reconfirmation_required`, `context_integrity_unknown`) — כולם נדרשים כדי ש-hydration אחרי restart ישמר את הזהות/מדיניות המקורית, לא רק tool_name/payload. `agent_observations` **לא** נשמר (מוצהר: אינו authoritative, לא נדרש ל-re-execution בטוח).
3. **`tools/airtable_gateway.py`** — `at_get_by_field()` (extracted מ-`at_upsert`), `at_list_by_formula()` (חדש, ל-pending lookup), `AirtableLookupError` (מבחין store-outage מ-not-found).
4. **`core/action_gateway.py`**:
   - `ActionContract.version: int = 1` (שדה חדש).
   - `ExecutionLedger` מקבל `repository` (constructor param חדש). `find_by_id()` נופל בחזרה ל-`repository.get()` על cache miss, מ-hydrate את ה-cache. `save()` קורא גם ל-`repository.save()` אם קיים.
   - `ExecutionLedger.guarded_update_status()` (חדש) — עוטף transition version-guarded כש-repository קיים; **ללא שינוי התנהגות** כש-repository הוא None (fallback להתנהגות המקורית של `update_status`, רק עם בדיקת expected_status נוספת שמתקיימת תמיד במסלול הרציף הקיים).
   - `ActionGateway.approve()` ו-`_execute_contract()` שוכתבו להשתמש ב-`guarded_update_status()` במקום `update_status()` הישן, בדיוק בנקודות שבהן שני Render instances יכולים לרוץ על אותו contract_id (pending→approved, approved→executing→executed/failed).
5. **`_ledger_singleton` נשאר `airtable_writer=None`, ללא `repository`** — **אותה משמעת בדיוק כמו התיקון ב-Phase 4A**: זו עדיין תשתית נבנית ונבדקת, לא activation live. הפעלה בפועל (חיבור ה-repository ל-singleton החי) היא צעד נפרד, מכוון, שידרוש ניטור/staging משלו — לא נכלל כאן.

### Tests
`test_pr0c_action_contract_repository.py` (חדש, 24 assertions) — מכסה במדויק את 7 הקטגוריות שהבעלים דרש: (1) restart recovery; (2) multi-instance race — שתי `ExecutionLedger` נפרדות (ללא cache משותף) חולקות רק את ה-repository, רק אחת מנצחת; (3) identity binding — actor_role/actor_external_id/trusted_source נשמרים במדויק דרך hydration; (4) expiry — contract pending ישן מ-24h לא ניתן לשחזור; (5) repeated approval — ניסיון שני עם expected_version/status ישנים נדחה; (6) stale-status regression — ניסיון "לחזור אחורה" ל-approved על contract שכבר executed נדחה; (7) store outage — כל שלוש הפונקציות (`get`/`find_by_id`/`guarded_transition`) fail-closed (None), לא זורקות, לא ממציאות contract חלופי. **פלוס test #8** — הוכחה end-to-end דרך ה-API הציבורי: שני `ActionGateway` נפרדים (executor + ledger נפרדים, רק repository משותף — מדמה שני Render instances אמיתיים) קוראים ל-`approve()` על אותו contract_id; ה-dispatch executor נקרא **פעם אחת בדיוק**. **test #9** — regression guard: ה-singleton החי עדיין לא מחובר (אותה משמעת כמו Phase 4A).

כל 24/24 assertions חדשות עברו, כל test_*.py הקיימים (כולל test_action_gateway.py 41, test_stage_b_full_suite.py 124, test_bug074_approval_authority.py 22, וכל בדיקות ה-PR-0C הקודמות) עברו full run ללא רגרסיה — `approve()`/`_execute_contract()` שוכתבו אך מתנהגים זהה לגמרי כש-repository=None (המצב היום).

### הודאה מפורשת על מגבלת התכן (לא הוסתרה)
`guarded_transition()` **אינו** CAS אמיתי ברמת מסד נתונים — Airtable REST API אין לו primitive ל-conditional write. המימוש (verify-read → PATCH → verify-reread) מצמצם משמעותית את חלון המרוץ אך אינו סוגר אותו לחלוטין תיאורטית (כתיבה מתחרה שנופלת בדיוק בפער הקטן בין ה-verify-read שלנו ל-PATCH שלנו עדיין יכולה תיאורטית לחמוק, אם כי ה-reread שלנו יזהה וידווח על הקונפליקט בדיעבד). זה מספיק לתעבורת אישורים בקצב אנושי (Render, לא high-throughput), לא מוצג כערובה מתמטית תחת concurrency יריבה.

- **Severity:** N/A — תשתית קריטית לפני Phase 4B. חלק מ-PR-0C.
- **תוקן ב-commit:** (למלא אחרי commit)
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** לא עדיין
- **Deployed:** לא
- **Verified בפרודקשן:** לא רלוונטי — אין שינוי live (singleton עדיין לא מחובר)
- **סטטוס:** Phase 4B0 הושלם. Phase 4B (TMA Approvals projection + routing by contract_id) יכול להתחיל רק אחרי merge כאן, ורק אחרי החלטה נפרדת ומודעת על הפעלת ה-repository ב-singleton החי (לא נכלל אוטומטית ב-4B0 או ב-4B עצמו).

הלוג האחרון (מעלה) מוכיח את **כל השרשרת יחד**, לא רק חתיכה אחת: preview → 2 הפרעות → "כן" (re-display מדויק) → הפרעה שלישית → "כן" (superseded מדויק, אין ביצוע כפול/שגוי). אין פערים פתוחים ידועים בנושא הזה.

---

## PR-0C — Phase 4B0 CORRECTION: guarded_transition() provided NO protection under genuine concurrency, removed from all execution paths

- **דווח:** 12/07/2026, אותו יום כמו הרשומה המקורית למעלה — הבעלים ביקש להראות את המימוש המדויק של `guarded_transition()` ואת בדיקת ה-race, ולאשר אם מדובר ב-CAS אמיתי או ב-read-check-patch.

### מה התגלה (בדיקה עצמית, לא דיווח מהבעלים)
בעקבות מעקב מדויק אחרי הרצף של `guarded_transition()`, התברר שהניסוח המקורי ברשומה למעלה — "מצמצם משמעותית את חלון המרוץ" — **שגוי**. עבור המקרה המדויק שהכי חשוב (שני קוראים קוראים את הרשומה *לפני* שמישהו מהם כותב — למשל webhook כפול, double-tap, או שני Render instances שמטפלים באותה בקשה במקביל): שני הקוראים מחשבים באופן עצמאי את אותו `expected_version+1`/`new_status`, שניהם עושים PATCH, שניהם קוראים מחדש ורואים (version, status) שתואם למה שהם עצמם ציפו לכתוב, ו**שניהם מקבלים success לא-None** — למרות שה-PATCH השני דרס בשקט שדות אחרים של הראשון (למשל `approved_by`). זו לא "צמצום חלון מרוץ" — זו **אפס הגנה** בדיוק במקרה הזה, ושני הקוראים **ימשיכו לביצוע בפועל**. הבדיקות שתויגו כ-"multi-instance race" (test #2, #5, #6, #8 ברשומה המקורית) לא הוכיחו הגנה אמיתית — הן היו סדרתיות (single-threaded script: הקריאה הראשונה רצה עד הסוף לפני שהשנייה מתחילה), ולכן מעולם לא הציבו שני קוראים בחלון הפגיע בפועל.

### הוראת הבעלים המפורשת (verbatim עיקרי)
"Do not only correct the documentation. The current guarded transition cannot provide the safety property Phase 4B requires. Re-scope PR #321 to durable persistence, hydration, identity binding and fail-closed reads only. Remove or clearly disable the non-atomic transition from any execution path, and retract the multi-instance race claim. Keep the live singleton unwired and keep TMA routing blocked. Add a separate Phase 4B0.1 using a genuinely atomic coordination primitive outside Airtable: transactional SQL/CAS, Redis SET-NX with lease and fencing, or a single-consumer execution queue."

### מה שונה בפועל (לא רק תיעוד)
1. **`core/action_contract_repository.py`** — `guarded_transition()` ו-`_TRANSITION_EXTRA_FIELDS` **הוסרו לגמרי** מהקובץ. נשארו רק `save()`, `get()`, `find_pending_by_canonical_user()` וה-serialization helpers — persistence/hydration/fail-closed-reads בלבד, ללא שום מנגנון transition/claim.
2. **`core/action_gateway.py`** — `ExecutionLedger.guarded_update_status()` **הוסרה לגמרי**. `ActionGateway.approve()` ו-`_execute_contract()` הוחזרו לקרוא ל-`update_status()` הרגיל (הישן), בדיוק כמו לפני שכתוב Phase 4B0 — לא נשאר שום קריאה ל-guarded/version-guarded transition בשום מסלול ביצוע חי. `ExecutionLedger.__init__`'s `repository` param ו-`find_by_id()`'s cache-fallback/hydration נשארו (persistence/hydration תקינים, לא מושפעים).
3. **`_ledger_singleton` נשאר `airtable_writer=None`, ללא `repository`** — ללא שינוי, כפי שהבעלים דרש במפורש ("Keep the live singleton unwired").
4. **`test_pr0c_action_contract_repository.py`** — נבנה מחדש: הוסרו הבדיקות שנבנו סביב `guarded_transition`/`guarded_update_status` (התיוג הקודם "multi-instance race" הוסר לגמרי, לא רק נוסח). נשארו: restart recovery, identity binding, expiry, store outage, וregression guard חדש שמוודא במפורש ש-`guarded_transition`/`guarded_update_status` **לא קיימות יותר** בקוד (hasattr checks) — כדי שהמנגנון הלא-בטוח לא יוכל לחזור בשקט. 14/14 assertions עוברות.
5. **`airtable_schema.py`** — תיאור השדה `VERSION` תוקן: מטא-דאטה מתמידה בלבד, **לא** מנגנון concurrency פעיל — אין היום שום קוד שבודק/עושה CAS על הערך הזה.
6. **`tools/airtable_gateway.py`** — docstring של `at_upsert()` תוקן: לא מפנה יותר ל-`guarded_transition()` (שהוסרה); מציין שאין היום פתרון concurrency-safe בקודבייס למעברי סטטוס.

### רגרסיה מלאה
`python3 -m py_compile` על כל הקבצים שהשתנו — נקי. `test_pr0c_action_contract_repository.py` — 14/14. `test_action_gateway.py` — 41/41. `test_stage_b_full_suite.py` — 124/124. `test_bug074_approval_authority.py` — 22/22. `smoke_tests.py` — pass. לולאת `test_*.py` המלאה (כפי ש-CI מריץ) — כולם עברו, ללא כשל אחד. ההחזרה ל-`update_status()` היא **behavior-neutral** בדיוק כפי שהיה צפוי — `guarded_update_status()` בעצמה כבר הייתה fallback ל-`update_status()` הרגיל כש-repository=None (המצב היחיד שהיה live).

### Phase 4B0.1 — טרם החל
דרישת הבעלים למנגנון claim אטומי אמיתי מחוץ ל-Airtable (transactional SQL/CAS, Redis SET-NX עם lease+fencing, או single-consumer execution queue) **טרם נבנתה**. אימות ב-grep מאשר: **אין** תשתית Redis/SQL/transactional-DB חיה בקודבייס הזה כיום (הפגיעה היחידה — `core/tenant_config.py`'s `Literal["airtable", "supabase", "hubspot", "postgres"]` — type hint בלבד, מודול "code-complete... zero imports from any live module" לפי CLAUDE.md). המשמעות: Phase 4B0.1 תדרוש להכניס תשתית חדשה לגמרי או לבחור בגישת single-consumer-queue — החלטה ארכיטקטונית שטרם הועלתה לבעלים עם אפשרויות והשלכות. Phase 4B (TMA routing by contract_id) **נשאר חסום** עד שPhase 4B0.1 תיבנה, עם acceptance test שמסנכרן שני קוראים כך ששניהם קוראים את אותה גרסה pending לפני שמישהו מהם מנסה claim, ומוכיח ש-**בדיוק קורא אחד** מגיע ל-`dispatch_tool()`.

- **Severity:** גבוה — תיקון עצמי של over-claim בתיעוד קודם (הצהרת "מצמצם race" שהייתה שגויה במקרה הכי חשוב).
- **תוקן ב-commit:** (למלא אחרי commit)
- **תוקן ב-branch:** `claude/table-incorrect-names-6chfvb`
- **Merged:** לא עדיין
- **Deployed:** לא
- **Verified בפרודקשן:** לא רלוונטי — אין שינוי live (singleton עדיין לא מחובר, אף לפני ואף אחרי התיקון)

---

## BUG-BATCH-DISCARD — תיקון רגרסיה: בקשה עם כמה משימות (batch) איבדה משימות בשקט

- **דווח:** 15/07/2026, הבעלים — בקשת "צור לי 5 משימות" בהודעה אחת שמרה ואישרה רק את המשימה הראשונה; 4 הנותרות נעלמו בשקט, למרות שהסוכן הבטיח "שלח מאשר כדי להמשיך עם שאר 4 המשימות".
- **מסך / מודול:** `app.py` (לולאת ה-tool-use של ה-Agent), `core/action_gateway.py`.

### תחקור (root cause) — לפני כל תיקון
1. **הקומיט המדויק שהציג את הרגרסיה:** `9ab4af7` (30/06/2026, "fix(approval-gateway): systemic Approval Gateway Safety — Section 1 bugs"), שסגר את **BUG-043 / BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION**. אומת ב-`git log -S` ש-`_mutating_approvals_this_turn` **לא השתנה** מאז — הרגרסיה קדמה לחלוטין לסשן הנוכחי; שום קומיט מהתיקונים האחרונים (Single-Speaker, post-completion-fallthrough, canonical-tool-wiring) לא נגע בלולאה הזו.
2. **הכוונה המקורית (מ-BUG_AUDIT_LOG.md, BUG-043) הייתה מניעת "זיהום payload בזיכרון" בין שתי בקשות אישור באותו תור** — אך זו מעולם לא שוחזרה בפועל: `dict(tu.input)` כבר יצר עותק עצמאי לכל קריאה גם לפני וגם אחרי 9ab4af7, וכל קריאה ל-`_queue_approval()` כבר יצרה `EventBus` item + `ActionContract` עצמאיים משלה. בדיקת הרגרסיה שנוספה אז (`test_no_multi_pending_from_yes_add_now`) בדקה רק את לוגיקת ה-counter בבידוד, מעולם לא שיחזרה זיהום אמיתי — התיקון בלבל "מניעת סיכון תיאורטי בזיכרון משותף" עם "איסור על יותר מפעולה ממתינה אחת בתור", והשליך בשקט כל משימה מעבר לראשונה.
3. **אחסון לפני ואחרי (שני הזמנים):** תמיד N פריטי `EventBus` עצמאיים + N `ActionContract` עצמאיים — מעולם לא אובייקט batch מאוחד.
4. **ניסיון תיקון נאיבי שנבדק ונדחה לפני היישום:** הסרת החסימה בלבד (כל 5 המשימות הופכות מיד ל-`ActionContract` חי) **נבדקה אמפירית ונמצאה גרועה יותר**: (א) ברגע שיש יותר מ-contract חי אחד לאותו canonical_user_id, `route_confirmation_word()` כבר לא מבצע "מאשר" רגיל ישירות — הוא נופל לענף ה-disambiguation (`len(live)>1`), ששובר את זרימת האישור החד-פעולתי שכבר עבדה; (ב) בחירת פריט לפי מספר דרך `route_disambiguation()`/`route_combined_word()` **דוחה במכוון את כל שאר ה-siblings** (§21, קומיט `6752ec0`, "close all other pending contracts... so no residual pending contracts linger") — עיצוב מכוון ל-disambiguation בין פרשנויות חלופיות לבקשה **אחת**, לא לשימור פריטי batch עצמאיים. אומת בהרצה ישירה: אישור פריט #1 מתוך 5 גרם לדחיית 4 ה-siblings האחרים באופן מיידי.

### התיקון בפועל
1. **`event_bus.py`** — `BatchQueueStore` חדש (in-memory, אותה מחלקת נדיפות כמו `PendingActionsStore`) ששומר משימות שנדחו מהתור הראשון לכל `canonical_user_id`, עד שבטוח לקדם את הבאה.
2. **`app.py` — לולאת ה-tool-use**: המשימה הראשונה בתור עדיין עוברת `_queue_approval()` רגיל (contract חי + הודעת Telegram). כל משימה נוספת נכנסת ל-`batch_queue.enqueue()` במקום להיחסם — משומרת באופן עמיד, לא נוצר לה contract חי עדיין.
3. **`app.py` — `_promote_next_batch_item()` (חדש)**: אחרי כל ניסיון resolution (מאשר/ביטול/disambiguation/combined-word/override/callback כפתור), בודק אם אין contract חי לזהות הזו ואם כן מקדם את הפריט הבא מה-queue לכדי contract חי + הודעת Telegram משלו — דרך אותו `_queue_approval()` בדיוק. לעולם לא יותר מ-contract חי אחד בו-זמנית לזהות אחת ב-batch, כך שה-len(live)>1 disambiguation/sibling-reject לא מופעל אף פעם על ידי batch.
4. **לא שונו:** `ActionGateway.approve()`, `reject()`, `_execute_contract()`, Atomic Claims, מנגנון ה-callback הקיים — התיקון כולו בשכבת התור ב-`app.py`/`event_bus.py` בלבד.

### בדיקות
`test_bug_batch_approval_preserved.py` (חדש, 33 assertions) — 5 משימות בתור אחד → כולן נשמרות, contract חי אחד בלבד, הודעת Telegram אחת; אישור-כולם מבצע כל פעולה פעם אחת בדיוק (5 dispatch, ללא כפילות), "מאשר" רגיל מבצע ישירות לכל משימה בתורה (ללא רשימת disambiguation); ביטול/דחייה על הפריט הפעיל אינו פוגע בפריטים הממתינים בתור ומקדם את הבא באופן דטרמיניסטי. `test_approval_gateway_safety.py`'s simulation עודכן לשקף את ההתנהגות המתוקנת (היה נועל בטעות את התנהגות ה-discard הישנה כטקסט-מקור מצופה).

מלוא הרצה: `compileall`, `smoke_tests.py`, `core/router/test_router.py`, וכל 110 קבצי `test_*.py` — ללא רגרסיה.

### תיעוד נפרד, לא נפתר כאן (מחוץ לתחום לפי הוראה מפורשת)
- `app.py`'s `_apply_ingress_context_gate` מסמן `context_interrupted` על **כל** callback נכנס, כולל לחיצת כפתור אישור/ביטול עצמה (`kind="callback"` לעולם לא פטור, בניגוד ל-`kind="text"` דרך `is_own_resolution_event`) — עלול לגרום ל-reconfirmation מיותר על contract לא-קשור שעדיין ממתין, בכל פעם שנלחץ כפתור כלשהו.

- **Severity:** גבוה — אובדן נתונים שקט (משימות שהמשתמש ביקש נעלמות בלי שום הודעת שגיאה גלויה).
- **תוקן ב-commit:** (למלא אחרי commit)
- **תוקן ב-branch:** `claude/single-speaker-fallback-fix`
- **Merged:** לא עדיין
- **Deployed:** לא
- **Verified בפרודקשן:** לא — ממתין למיזוג ופריסה
- **סטטוס:** תוקן ומאומת ב-suite המלא. הפריט הנפרד (ingress context gate) תועד אך לא טופל, בהתאם להוראה מפורשת שלא לחרוג מהיקף המשימה.
- **סטטוס:** re-scope הושלם. Phase 4B0.1 (מנגנון claim אטומי אמיתי) טרם החל — נדרשת החלטת בעלים על תשתית לפני תכנון.

---

## BUG-109 (OVERRIDE-ATOMIC-CLAIM-COLLISION) — קוד override תקף מנסה להפעיל מחדש חוזה שכבר נתבע ב-atomic claim — 🔴 נרשם, לא תוקן (החלטה מפורשת: להשאיר פתוח)

- **תאריך:** 14/07/2026.
- **מקור:** התגלה תוך תיקון `test_stage_b_full_suite.py`'s תאימות ל-executor contract החדש (PR #339/#340, `identity=`/`claim_execution_id=` params). לאחר התיקון, הרצת ה-suite המלאה עם `FEATURE_ATOMIC_CLAIMS=true` (מול PostgreSQL אמיתי, לא mock) עברה מ-25 כשלי kwarg ל-**134/136 assertions עוברות** — שני הכשלים הנותרים **שניהם ב-Req6 בלבד** ("Duplicate requires override code"), ואינם קשורים לתיקון ה-fixture. הבעלים אישר: לא לתקן ולא להסיר את הבדיקות עד לבדיקת השפעות צדדיות.
- **הבדיקות הכושלות בפועל:** `test_stage_b_full_suite.py` שורות 313/316 — "`Req6: correct override code dispatches again`" ו-"`Req6: consumed override code cannot re-execute`" (שתיהן מצפות ל-`len(_dup_dispatched) == 2` אחרי `route_override_word()`, בפועל נשאר `1`).
- **שורש הבעיה (אומת בקוד, לא השערה):** `route_override_word()` (`core/action_gateway.py:1161`) קורא לאותו `_execute_contract()` (`:1301`) שקורא גם `approve()`. תחת `FEATURE_ATOMIC_CLAIMS`, מפתח ה-idempotency נגזר מ-`contract_id`+`approved_by` בלבד (`:1378-1379`) ו-`action_execution_claims.contract_id` הוא `TEXT PRIMARY KEY` יחיד ולא מורכב (`core/migrations/001_action_execution_claims.sql`). `claim_contract_execution()` (`core/atomic_claim_repository.py:142`) עושה `INSERT ... ON CONFLICT DO NOTHING` לא-ממוקד — ברגע שקיימת שורת claim אחת ל-`contract_id`, **כל** ניסיון claim שני (override מאושר או לא) נדחה כ-`already_claimed`, בלי קשר לערך ה-idempotency_key. שינוי נוסחת ה-key בלבד לא היה פותר את זה — ה-primary key עצמו הוא נקודת ההתנגשות המבנית.
- **החלטת הבעלים (verbatim):** "שני הכשלים: Req6 בלבד. סיבה: override מנסה להפעיל מחדש חוזה שכבר נתבע. החלטה: לא לתקן ולא להסיר עד לבדיקת ההשפעות הצדדיות." — כלומר: הבדיקות משאירות כשל אדום במכוון (לא xfail, לא הוסרו, לא הוחלשו), כתיעוד חי לפער אמיתי, עד שהחלטה מודעת תתקבל.
- **כיוון תיקון מוצע (מחקר בלבד — טרם מומש, טרם אושר):** להוסיף מימד "ניסיון ביצוע" ל-claim, ברירת מחדל `''` (ריק) לכל ביצוע רגיל (ללא שינוי התנהגות/idempotency key לנתיב הרגיל), וערך ייחודי (`override_id`, נוצר פעם אחת ב-`_handle_duplicate_executed()`) לביצוע override מאושר בלבד. שינוי סכימה: migration חדש המוסיף עמודות `execution_attempt_id TEXT NOT NULL DEFAULT ''` ו-`parent_execution_id TEXT` (nullable, lineage לשורת ה-claim המקורית), ומחליף את ה-PRIMARY KEY מ-`contract_id` בלבד ל-מורכב `(contract_id, execution_attempt_id)`. מפתח ה-idempotency הרגיל (`contract_id:approver`) נשאר ללא שינוי בייט-לבייט; רק ניסיון override מוסיף seed נוסף (`:override:{override_id}`) — כך retry של אותו override נשאר idempotent, בלי ליצור key חדש בכל ניסיון, ובלי להחליש את הייחודיות הגלובלית של הנתיב הרגיל.
- **קבצים מושפעים (אם/כאשר יאושר תיקון):** `core/action_gateway.py` (`DuplicateOverrideApproval`, `_handle_duplicate_executed`, `route_override_word`, `_execute_contract`), `core/action_gateway_atomic_executor.py`, `core/atomic_claim_repository.py`, migration חדש `core/migrations/002_execution_attempt_id.sql`, `tools/phase_4b_rollout_common.py::fetch_all_claims()` (SELECT columns), `tools/phase_4b_reconciliation.py` (`claims_by_contract` dict-key כרגע `contract_id` בלבד — יקרוס בשקט שתי שורות ל-contract אחד אחרי שינוי סכימה). **אין** שינוי נדרש ב-`tools/approval_actions.py` — `get_claim(contract_id)` שם משתמש בברירת המחדל, ו-`route_override_word` אף פעם לא מגיע מנתיב ה-TMA.
- **סיכונים שזוהו (לא טופלו):** (א) `ActionContractRepository.transition()` עושה no-op שקט על re-persist לאותו status טרמינלי — כלומר החוזה עצמו ב-Airtable **לא** ישקף חזותית שבוצע override; טבלת ה-claims היא מקור האמת הבלעדי לכך. (ב) אם ביצוע ה-override עצמו נכשל בסטטוס שונה מהמקורי, `ALLOWED_CONTRACT_TRANSITIONS` אין לו קשת יוצאת מ-`completed` — נתפס בחן (מחזיר `False`, לא קורס) אך עם הודעה לא ברורה. (ג) `route_override_word()` כרגע לא מעדכן את `contract.approved_by` לפני הביצוע החוזר — ייחוס שגוי לגורם המקורי במקום לגורם שהפעיל את ה-override, אלא אם ייפתר כחלק מהתיקון.
- **השפעה על G1 (Rollout gate):** `test_stage_b_full_suite.py` **אינו** ברשימת `_REQUIRED_REGRESSION_TEST_FILES` של `tools/phase_4b_rollout_readiness.py` — כלומר הפער הזה **אינו** חוסם את G1 היום גם עם `--run-regression-tests`. זהו פער תיעוד/גילוי בפני עצמו: הפער קיים ומתועד כאן, אך אינו נאכף אוטומטית על ידי כלי ה-rollout.
- **Severity:** בינוני-גבוה — לא משפיע על הנתיב הרגיל (אישור כפול עדיין נחסם כראוי, req #1/#6 בדרישות הבעלים), אך override מאושר במפורש **לא מבצע בפועל** תחת `FEATURE_ATOMIC_CLAIMS=true` — פונקציונליות שקטה שנעלמת בלי שגיאה ברורה למשתמש.
- **תוקן ב-commit:** לא — עדיין לא מומש.
- **תוקן ב-branch:** לא רלוונטי.
- **Merged:** לא.
- **Deployed:** לא רלוונטי.
- **Verified בפרודקשן:** לא רלוונטי — אין קוד production שהשתנה.
- **סטטוס:** 🔴 פתוח במכוון. Stage B: 134/136 (2 כשלים, שניהם Req6, מתועדים ומצופים). לא לתקן ולא להסיר את הבדיקות הכושלות עד החלטת בעלים מפורשת אחרי בדיקת השפעות צדדיות (ActionContract lifecycle no-op, ייחוס approved_by, כלי reconciliation/rollout-common שיזדקקו לעדכון אם הסכימה תשתנה).

---

## BUG-110 — Non-canonical `status="converted"` writers (Business Outcome תפוס ב-status) — ✅ תוקן, לא נבדק בפרודקשן

- **תאריך:** 17/07/2026.
- **⚠️ הערת מספור (חשוב לקרוא לפני שמחפשים "BUG-105"):** תיקון זה תויג `BUG-105` בענף/PR/commit message/שם קובץ הבדיקה (`test_bug105_non_canonical_converted_status.py`), **לפני** שהתגלה ש-`BUG-105` כבר תפוס למעלה בקובץ הזה ("פורמט טלפון בין-לאומי עם מקף — נשמט בשקט", 12/07/2026, עדיין 🟡 פתוח, **נושא שונה לגמרי, לא קשור**). לפי החלטת owner מפורשת (17/07/2026), רשומת ה-audit log משתמשת ב-**BUG-110** (המספר הפנוי הבא אחרי BUG-109) כדי לא להתנגש עם הרשומה הקיימת. **שמות הקבצים/ה-PR/ה-commit ב-`main` לא שונו רטרואקטיבית** — מי שמחפש את הקוד יחפש `bug105`/`BUG-105`, מי שמחפש בתיעוד הממשל (`BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md`/`ROADMAP.md`/`CHANGELOG.md`/`AI_CONTEXT.md`) ימצא `BUG-110`.
- **מקור:** נמצא ב-audit של BUG-104 Phase 2A.0 (`docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md` §5/§7B) — מיפוי read/write מלא של שדות Leads חשף שני אתרי כתיבה עצמאיים שכותבים ערך `status` לא-קנוני.
- **שני אתרי הכתיבה (מאומתים בקוד, לא השערה):**
  1. `lead_conversion.py::convert_lead_to_contact()` (שורה 93-96, לפני התיקון) — `_at_patch(Tables.LEADS, lead["id"], {LeadFields.STATUS: "converted", ...})`, דרך ה-gateway (`tma_api._at_patch` → `tools/airtable_gateway.py::airtable_patch`).
  2. `ad_attribution.py::mark_converted()` (שורה 195-196, לפני התיקון) — `airtable_update("Leads", rec_m.group(0), {"status": "converted", ...})` דרך `tools.airtable_tools.airtable_update` — **לא** דרך ה-gateway.
- **שורש הבעיה:** `"converted"` (המחרוזת הליטרלית) **אינה** חברה ב-`LeadStatus.ALL` (`airtable_schema.py`) ואינה אופציית `Leads.status` חיה (הערכים החיים: `waiting_call/active/high_confidence/new/waiting_response/archived/lost/duplicate/not_relevant/done/ליד חדש`, מאומת ב-Airtable MCP). הערך הקנוני ל"הומר" הוא הצמד `status=LeadStatus.DONE` ("done") + `Business Outcome=LeadOutcome.CONVERTED` ("converted " — עם רווח-זנב מובנה ב-Airtable). `tma_api.py::patch_lead` עצמו מוולד מול `LeadStatus.ALL` לפני כתיבה — שני האתרים האלה עוקפים את הוולידציה הזו כי הם לא עוברים דרך אותו endpoint.
- **תוקן:** כן. שני האתרים כותבים עכשיו `status=LeadStatus.DONE` + `Business Outcome=LeadOutcome.CONVERTED`, באמצעות הקבועים הקיימים ב-`airtable_schema.py` — אין אופציית Airtable חדשה, אין rename, אין backfill לנתונים קיימים.
- **חוב טכני שנשאר במכוון, לא תוקן:**
  - `ad_attribution.py::mark_converted()` **עדיין לא** עובר דרך ה-gateway הקנוני (`tools/airtable_gateway.py`) — נבדק והוערך כלא-ישים בסקופ הזה: מעבר היה משנה את חוזה ה-return של הפונקציה (`bool` מהgateway מול `dict` שנבדק היום עם `result.get("ok")`) ושובר את הבדיקה הקיימת `test_response_contract_fixes.py`.
  - `ad_attribution.py::build_attribution_report()` (שורה 326 לפני התיקון) ו-`audience_intelligence.py` (שורה 177) שניהם קוראים `status == "converted"` לצורכי דיווח/סגמנטציה — יימשיכו לקרוא נכון נתונים ישנים (אין backfill) אך **יחסירו** לידים שהומרו **אחרי** התיקון הזה (status="done" חדש לא תואם את ההשוואה הישנה). לא תוקן, מומלץ follow-up נפרד.
  - `lead_conversion.py`'s `lf.get(LeadFields.STATUS,"") == "converted"` (idempotency read-guard, שורה 57) נשאר ללא שינוי — לא באג: הוא OR'd עם `lf.get(LeadFields.CONVERTED_AT,"")` שנכתב תמיד יחד עם status בשני האתרים, כך שזיהוי "הומר כבר" ממשיך לעבוד נכון גם על נתונים ישנים וגם חדשים.
- **בדיקות:** `test_bug105_non_canonical_converted_status.py` (חדש, 10/10 — שם הקובץ לא שונה, ראו הערת מספור למעלה) — מוודא ששני האתרים כותבים `status=LeadStatus.DONE`+`Business Outcome=LeadOutcome.CONVERTED`, לא `"converted"`. `test_response_contract_fixes.py` (19/19, כולל תיקון מכני של מספר-שורה קבוע ב-baseline של ה-scanner שזז ב-1 בגלל import חדש). `test_bug104_leads_reasoning_projection.py`/`test_bug104_phase1_1_contract_hardening.py`/`test_bug104_tma_lead_event_bridge.py`/`test_core_reasoning.py` — ללא שינוי, ירוקים.
- **PR:** #372 (`fa1506e`, merge `b344b02`).
- **Merged:** כן.
- **Verified בפרודקשן:** לא — הכתיבות החדשות (`status=done`+`Business Outcome=converted`) עדיין לא נצפו על ליד אמיתי בפרודקשן.
- **סטטוס:** ✅ קוד תוקן ומאומת בבדיקות, ⚠️ לא verified-in-prod. חוב טכני (gateway migration + read-side `status=="converted"` consumers) מתועד למעלה, לא נחסם ע"י זה.

---

## BUG-111 — פענוח batch של לידים: מילת דומיין/prefix שולח/שורות דחוסות נלכדו כשם ליד מזויף — ✅ VERIFIED IN PROD

- **דווח:** 18/07/2026 — דווח production ישיר: הודעת batch עם 3 מספרי טלפון יצרה ליד אמיתי אחד עם `name="דומיין גיוס"` (או, בסבב השני, `name="לידים חדשים"`) — שם מזויף שנגזר מטקסט הפקודה/הכותרת, לא משם אמיתי.
- **מסך / מודול:** `core/ingress_classifier.py` (`_extract_lead_candidates`/`_extract_candidates_from_block`/`_extract_name_from_window`/`_classify_ingress_core` — הנתיב החי; `core/lead_candidate_handler.py`'s `parse_batch_dictation`/`parse_lead_dictation` הם dead code מאומת, ראו BUG-096) ו-`core/lead_candidate_handler.py` (`_maybe_start_lead_clarification`/`_resolve_lead_clarification`).
- **Severity:** High — יצירת רשומת Lead אמיתית ב-Airtable עם שם שגוי, ואיבוד שקט של מספרי טלפון נוספים ב-batch.

### סבב 1 — PR #386 (`6bb3b61`, follow-up `7b2cd5c`, CI fix `c3499f5`, merge `fc3f51b`)

- **Root Cause (4 סיבות עצמאיות, מאומתות בקוד):**
  1. `_PHONE_RE` לא תאם פורמטים דו-מפרידים (`05X-XXX-XXXX` מקומי, `+972 XX-XXX-XXXX` בין-לאומי) — בלי match לטלפון, גם ה-Tier-5 clarification fallback לא מצא כלום וההודעה נפלה עד ל-Agent tool_use loop, שנחסם ע"י LeadsWriteGate.
  2. `_CHAT_EXPORT_TIMESTAMP` דרש בלוק שנה מלא (`D.M.YYYY`) — חותמת WhatsApp נפוצה בלי שנה (`[D.M, HH:MM]`) הפילה גם את `_BLOCK_SEP` וגם את `_SENDER_LINE_RE`, ואז כותרת ה-batch ו-prefix השולח (`"אורי צדוק:"`) התמזגו לבלוק/חלון אחד ודלפו כ-candidate name.
  3. `_JSON_BLOCK_RE` סיווג כל `"["` מוביל כ-JSON, כולל שורת timestamp קצרה בודדת — Tier 4 שגוי מהסיבה הלא-נכונה.
  4. למילת המפתח `"דומיין"`/מילת הרמז שלה (למשל `"גיוס"`) לא היה טיפול stop-word/extraction — נכתבו כשם הליד במקום להיות מזוהות כהערת ניתוב.
- **תוקן:** שני alternatives חדשים ל-`_PHONE_RE`; שנה אופציונלית ב-`_CHAT_EXPORT_TIMESTAMP`; `_JSON_BLOCK_RE` עם negative lookahead לתאריך קצר; זוג פונקציות חדש `_extract_domain_hint()`/`_strip_domain_hint()` שמסיר את הביטוי **כולו** ("דומיין X") מהחלון לפני חילוץ שם, וחושף `candidate["domain_hint"]`; pattern גיוס חדש ב-`_DOMAIN_PATTERNS`; `_maybe_start_lead_clarification()` מנרמל את הטלפון לפני שמירה/הצגה.
- **Follow-up באותו PR (`7b2cd5c`):** batch עם טלפון-בלבד (ללא שם) קרס לטלפון יחיד (איבוד שקט של 2 מהמספרים) — `_maybe_start_lead_clarification()` נכתב מחדש להשתמש ב-`.finditer()` על **כל** הטלפונים, ומפצל למצב batch-clarification (`expected_field="names"`) כששני טלפונים+ ללא שם קיימים; `_resolve_batch_name_clarification()` חדש פותר אותו לפי סדר שורה-לכל-שם.
- **CI-only follow-up (`c3499f5`):** 9/50 בדיקות נכשלו ב-CI (עברו 100% מקומית) — `session_store.py` נכתב ל-Airtable אמיתי ב-CI, ו-`chat_id`ים ליטרליים גרמו לזליגת מצב ישן בין ריצות CI רצופות. תוקן ע"י `uuid.uuid4().hex[:10]` suffix ל-chat_idים בקובץ הבדיקה — אין שינוי מוצר.
- **בדיקות:** `test_bug111_lead_domain_and_sender_prefix.py` — 50/50.

### סבב 2 — PR #390 (`4635bcd`, merge `ee012c3`), אותו יום

- **מקור:** דגימת production חדשה, **אחרי** תיקון סבב 1, עם טקסט WhatsApp דחוס (בלי שורות חדשות בין הכותרת לחותמות ה-timestamp) — עדיין הפיק ליד אמיתי אחד עם `name="לידים חדשים"`, איבד 2 מספרי טלפון.
- **Root Cause (3 סיבות מצטברות נוספות):**
  1. `_BLOCK_SEP` דרש `\n` לפני **כל** סוג גבול, כולל chat-export header — כותרת שהודבקה ישירות על החותמת הראשונה (אין `\n`) מעולם לא התפצלה לבלוקים.
  2. `_SENDER_LINE_RE` דרש התחלת שורה אמיתית (`^`) גם לצורה עם bracket-timestamp — שם שולח מיד אחרי הודעה קודמת בלי `\n` לא זוהה כשורת שולח.
  3. `_NAME_STOP` הכיל רק את הצורות היחיד `"ליד"`/`"חדש"` (מסבב 1); הצורות הרבים `"לידים"`/`"חדשים"` שמופיעות בכותרת יצירת batch מעולם לא כוסו.
- **תוקן:** `_BLOCK_SEP` קיבל alternative לא-מעוגן (`(?=_CHAT_EXPORT_HEADER)`) שמפצל לפני header בכל מקום, לא רק אחרי `\n`; `_SENDER_LINE_RE` שוכתב כך שהצורה עם bracket-timestamp לא דורשת `^`; `"לידים"`/`"חדשים"` נוספו ל-`_NAME_STOP`. בנוסף — **רשת ביטחון הגנתית חדשה** ב-`_classify_ingress_core()`: אם החילוץ מפיק candidate יחיד אך הטקסט הגולמי מכיל יותר ממספר טלפון אחד, ה-candidate נזרק וההודעה יורדת ל-Tier 5 (בקשת הבהרה) במקום לשמור candidate יחיד עם שם שאולי שגוי.
- **בדיקות:** `test_bug111_followup_compact_text.py` — 29/29 (כולל שתי הדגימות המדויקות מ-production, worst-case header מודבק ישירות על טלפון, ורגרסיה על ליד יחיד אמיתי + batch נקי קיים).
- **Scope confirmed:** שני הסבבים לא נגעו ב-F52/RP5/`ActionGateway`/דגלים.
- **Merged:** כן (PR #386 + PR #390, שניהם).
- **Deployed:** כן.
- **Verified בפרודקשן:** ✅ כן — דגימת production אמיתית: הודעת WhatsApp מסוג batch קומפקטי/דחוס עם 3 מספרי טלפון (`0533968395`, `0533123482`, `0534185481`) **לא** יצרה יותר ליד מזויף בשם "לידים חדשים". BOSS זיהה את **שלושת** המספרים ופנה בבקשת הבהרה לשמות (Tier 5 clarification), במקום ליצור רשומת Lead שגויה ב-Airtable — בדיוק ההתנהגות שה-safety-net החדש בסבב 2 נועד להבטיח.
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED (79 checks סה"כ בין שני קבצי הבדיקה, suite מלא ירוק בשני הסבבים; אומת גם מול תעבורה חיה).

---

## BUG-112 — Telegram approval button המשיך לבצע אחרי ה-TTL המוצהר (10 דקות) — ✅ VERIFIED IN PROD (מנגנון הליבה) + סבב UX נוסף

- **דווח:** 18/07/2026.
- **מסך / מודול:** `app.py` — `_handle_approval_callback_impl()` (נתיב ה-Telegram inline-button), מול `event_bus.py`'s `PendingActionsStore`.
- **Severity:** High — ביצוע כלי אמיתי (כתיבה/פעולה) אחרי שהמשתמש כבר קיבל הודעה מפורשת שהאישור פג תוקף.
- **Root Cause:** כפתור האישור אומר **"פג תוקף בעוד 10 דקות"** — `_PENDING_APPROVAL_TTL` (600 שניות), אותו קבוע שה-gate של אישור טקסט חופשי ברמת ה-router כבר השתמש בו. אבל `_handle_approval_callback_impl()` קרא רק ל-`event_bus.bus.pop()`, שאוכף TTL **נפרד וארוך יותר** של `event_bus.py` עצמו (`PendingActionsStore.PENDING_TTL_MINUTES = 30 דקות`) — אופק ניקוי כללי לכל ה-store, לא קשור למה שהודעת אישור ספציפית מציגה. לחיצה על הכפתור בין דקה 10 ל-30 עדיין ביצעה את הכלי, בסתירה ל-TTL המוצהר.
- **הערת רגרסיה:** ה-`_PENDING_APPROVAL_TTL` הקיים כיסה רק אישורי טקסט ברמת ה-router (בתוך `run_agent()`'s Pending Approval Gate). אישורי Telegram callback דרשו אכיפת אותו TTL **בנפרד**, כי הם עוברים בנתיב קוד שונה לחלוטין (`_handle_approval_callback_impl()`, מונע ע"י `bus.pop()` ולא ה-dict `_pending_approvals`).
- **תוקן:** `_handle_approval_callback_impl()` בודק כעת, מיד אחרי pop מה-bus ולפני כל החלטת dispatch/execute, את חותמת ה-`"created"` של הפריט מול אותו `_PENDING_APPROVAL_TTL`, לכל callback "approve" (עם/בלי כלי). `_reject_stale_telegram_approval()` חדש מטפל בכל מה ש"פג תוקף" חייב לכלול: לא לבצע/dispatch לעולם; לדחות את ה-`ActionGateway` contract התואם אם קיים וניתן לוודא **בפועל** (לא בהנחה); להודיע למאשר בהודעת chat קבועה ("⏰ פג תוקף — הפעולה לא בוצעה"), לא רק פופ-אפ חולף; לערוך את הודעת האישור המקורית כך שלא תיראה עוד ניתנת לפעולה; לעולם לא ליפול ל-legacy dispatch.
- **Scope:** רק `app.py` נגע, פלוס קובץ הבדיקה החדש. אין שינוי לפענוח לידים (BUG-111), F52/`agent_message_formatter`, `FEATURE_UNIFIED_STATUS_FORMATTER`, RP5, או סמנטיקת ביצוע כלים מעבר לחסימת אישור-שפג-תוקף.
- **בדיקות:** `test_bug112_telegram_approval_ttl.py` — 22/22 (ביצוע בתוך TTL עם דגל כבוי/דלוק וגבול 9-דקות; callback שפג תוקף לעולם לא קורא ל-`dispatch_tool`/`ActionGateway.approve()`; ה-contract התואם נדחה בפועל בצורה durable; לחיצה שנייה על כפתור שפג עדיין 0 dispatches; ניסוח ההודעה הקבועה; סעיף רגרסיה שמוכיח ישירות שה-gate של אישור-טקסט ברמת ה-router לא הושפע).
- **תוקן ב-commit:** `f639c33` ("BUG-112: enforce Telegram approval button TTL before execution").
- **תוקן ב-branch:** `claude/bug-112-telegram-approval-ttl`.
- **PR:** #387 (merge `2136a14`).
- **Merged:** כן.
- **Deployed:** כן.
- **Verified בפרודקשן:** ✅ כן — לחיצה אמיתית על כפתור אישור שכבר פג תוקף הציגה:
  ```
  ⏰ פג תוקף
  ...
  ⏰ פג תוקף — הפעולה לא בוצעה
  ```
  הפעולה **לא** בוצעה, וכפתור האישור **נעלם** (עריכת ההודעה המקורית — `_reject_stale_telegram_approval()` הסירה את ה-reply_markup). 0 dispatch, בדיוק ההתנהגות שהתיקון נועד להבטיח.
- **סטטוס (מנגנון ליבה):** ✅ VERIFIED IN PROD / CLOSED.

### סבב 2 — UX follow-up: כפילות ניסוח בין נתיב "פג-תוקף-ידוע" לנתיב "stale/כבר-נצרך" (PR #394)

- **דווח:** 19/07/2026, מדגימת production שנצפתה **לפני** מיזוג PR #394 (הדגימה עצמה היא שהובילה לתיקון).
- **תצפית:** לחיצה חוזרת/כפולה על כפתור אישור שכבר פג תוקף הפיקה **שלושה** ניסוחי "לא בוצע" חופפים-אך-שונים על מה שהמשתמש קורא כאירוע אחד — הלחיצה הראשונה (פריט pending ידוע, פג-תוקף) לעומת לחיצה שנייה (הפריט כבר נצרך — `bus.pop()` מחזיר `None`), שנייה עברה דרך helper גנרי שהפיק ניסוח שלישי, כפול.
- **Root Cause:** שני נתיבי callback שונים באמת: (א) `_reject_stale_telegram_approval()` (BUG-112 המקורי, סבב 1 למעלה) — פריט pending **ידוע** שנמצא אך פג-תוקף. (ב) המקרה הנפרד: `bus.pop()` לא מוצא **כלום** — TTL הפנימי הנפרד של `event_bus.py` (30 דקות) כבר חלף, או שה-callback המדויק כבר נצרך בלחיצה קודמת. נתיב (ב) נותב דרך helper גנרי לא-מותאם (`_notify_stale_or_resolved_callback()`, בנוי במקור עבור "כבר בוצעה"/"כבר בוטלה") במקום קבלת ניסוח עקבי משלו.
- **תוקן:** `_notify_missing_or_expired_callback()` חדש (`app.py`) — ביטוי ליטרלי **אחד**, `"ℹ️ הפעולה כבר פגה או אינה קיימת, ולכן לא בוצעה."`, זהה בפופ-אפ, בהודעת ה-chat הקבועה, ובעריכת ההודעה המקורית. שני אתרי הקריאה שזקוקים לניסוח נפרד מהותית ("כבר בוצעה"/"כבר בוטלה") נשארו על `_notify_stale_or_resolved_callback()` המקורי, ללא שינוי. `_reject_stale_telegram_approval()` (נתיב א', BUG-112 המקורי) לא נגע כלל.
- **Scope:** אין שינוי לסמנטיקת ביצוע (0 dispatch לפני ואחרי, בשני הנתיבים). אין נגיעה ב-F52/RP5, פענוח לידים (BUG-111), או `FEATURE_UNIFIED_STATUS_FORMATTER`.
- **בדיקות:** `test_bug112_telegram_approval_ttl.py` הורחב ל-30/30 (מ-22) — Test8b-8d (לחיצה שנייה מפיקה ניסוח עקבי אחד, שונה בכוונה מהודעת הלחיצה הראשונה); סעיף 4b חדש (Tests 14-18) — callback עצמאי ל-`action_id` שמעולם לא נכנס לתור בכלל, מוכיח 0 dispatch ושלושת הבמות (פופ-אפ/הודעה קבועה/הודעה ערוכה) זהות במדויק.
- **תוקן ב-commit:** `8ac0c93` ("BUG-112 production follow-up: normalize stale/missing-callback UX to one message").
- **תוקן ב-branch:** `claude/bug112-stale-callback-ux-followup`.
- **PR:** #394 (merge `ad4afc9`).
- **Merged:** כן.
- **Deployed:** לא ידוע — דרוש בדיקה ידנית ב-Render.
- **Verified בפרודקשן:** ⚠️ **לא נבדק בנפרד** — זהו **defensive/idempotency cleanup**, לא נדרש לעצם BUG-112 (שכבר VERIFIED IN PROD, ראו סבב 1 למעלה). אין עדיין דגימת "missing/already-consumed callback" מפורשת אחרי ה-deploy הזה. יתרה מכך: דגימת ה-expiry האחרונה שהוכיחה את BUG-112 (סבב 1) גם מסירה את מסלול הלחיצה-הכפולה-הרגילה, כי כפתור האישור **נעלם** מיד אחרי הלחיצה הראשונה — כך שהמקרה שהתיקון הזה מכסה עשוי להיות נדיר יותר בפועל ממה שהדגימה המקורית הראתה.
- **סטטוס:** ✅ קוד תוקן ומאומת בבדיקות, ⚠️ לא verified-in-prod בנפרד. **אין לסמן את PR #394 כ-production-proven עד שתיצפה דגימת missing/stale-callback מפורשת אחרי deploy.**

---

## BUG-113 — A32 לא דיכא פרוזת approval-invite כפולה כשאישור אמיתי כבר נשלח לתור — ✅ VERIFIED IN PROD / CLOSED (שני סבבים)

- **דווח:** 19/07/2026, מדגימת production ישירה (F52 PR6 כבר היה במיזוג ומאומת — זהו ממצא נפרד, לא כשל taxonomy).
- **מסך / מודול:** `core/anti_hallucination.py::sanitize_agent_response()` — שער ה-Single-Speaker של A32.
- **Severity:** Medium — לא כשל ביטחוני (0 dispatch כפול, ה-approval עצמו תקין), אבל שני מסרים סותרים-בפועל למשתמש/בעלים באותו turn.
- **דגימת production (verbatim, לפני התיקון):**
  - הודעת gateway אמיתית: `⏳ בקשת אישור` / `➕ הוסף ל-Tasks...` / `ID: ... | פג תוקף בעוד 10 דקות`.
  - **וגם**, ללא דיכוי, פרוזת agent: `✅ המשימה מוכנה להוספה...` / `➡️ הצעד הבא... שלח מאשר...`.
  - זה גרם ל-`[EvidenceFinalizerShadow] evidence_status=approval_pending response_claim=success mismatch=true`.
- **Root Cause:** שער ה-Single-Speaker הקיים (`_AGENT_ACTION_STATUS_PATTERN`/`_AGENT_PENDING_STATUS_PATTERN`) לא כיסה את הניסוח הזה. `_AGENT_APPROVAL_INVITE_PATTERN` הקיים כן תואם, אבל נבדק **רק** בשער ה-NO-TOOL-EVIDENCE הנפרד, ורק כש**אין** ראיית `__approval_queued__` — ההפך המדויק מהמקרה הזה, שבו אישור אמיתי **כן** נכנס לתור.
- **תוקן:** ענף דיכוי חדש ב-`sanitize_agent_response()` — יורה כש-`_gateway_active` **וגם** `_AGENT_APPROVAL_INVITE_PATTERN` תואם **וגם** קיימת ראיית `__approval_queued__` אמיתית — מדכא ל-`""` (לא פולבק). `_AGENT_APPROVAL_INVITE_PATTERN` הורחב עם alternative `"הצעד הבא ... אשר"`.
- **Scope:** רק A32 (`core/anti_hallucination.py`) נגע. אין שינוי ל-BUG-111, BUG-112 TTL, F52 formatter states, סמנטיקת ביצוע של `ActionGateway`, או דגלי feature.
- **בדיקות:** `test_a32_approval_prose_suppression.py` חדש (18 בדיקות). רגרסיה מלאה ירוקה (70/70 + 27/27 + smoke + compileall).
- **תוקן ב-commit:** `2d86de6` ("Fix A32: suppress approval-invite prose duplicating a queued approval prompt").
- **PR:** #396 (merge `587d1fe`).
- **Merged:** כן.
- **Deployed:** כן.
- **Verified בפרודקשן:** ✅ כן — evidence מדויק מלוגים **אחרי** ה-deploy:
  ```
  [A32] Single-Speaker: agent emitted approval-invite prose after an approval was already queued this turn — suppressing (not replacing with fallback)
  [TurnEnvelope] ownership_signal ... "approval_queued": true, "agent_claimed_approval": false, "reply_owner": "gateway"
  [EvidenceFinalizerShadow] state=shadow evidence_status=approval_pending response_claim=sent_for_approval mismatch=false code=match counts={'classification': 'approval_pending', 'verified_reads': 0, 'verified_writes': 0, 'failed_calls': 0, 'outcome_unknown': 0, 'approvals_pending': 1, 'unverified_effects': 0}
  ```
  הפלט למשתמש הכיל רק את הודעת ה-gateway — ללא הפרוזה הכפולה.
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED.

### סבב 2 (BUG-113-FU) — פערי markdown-emphasis וצורת-זכר, PR #399

- **דווח:** 19/07/2026, מדגימת production חדשה **אחרי** סבב 1 (PR #396) כבר היה במיזוג ומאומת.
- **תצפית:** אותה כפילות (הודעת gateway + פרוזת agent) חזרה, הפעם עם ניסוח שונה: `"⏳ **העדכון ממתין לאישור:**\n...\nשלח **מאשר** כדי לאשר את העדכון."`
- **Root Cause (שני פערים עצמאיים באותו שורש — סבב 1 לא צפה variant markdown/דקדוק):**
  1. `שלח **מאשר**` — Markdown **bold** (שתי כוכביות) — `_AGENT_APPROVAL_INVITE_PATTERN`'s `\*?` תמך רק בכוכבית **אחת** אופציונלית; שתי כוכביות שברו את ה-match לגמרי.
  2. `ממתין` (זכר, ללא סיומת) — `_AGENT_PENDING_STATUS_PATTERN`'s `ממתינ[הת]` דרש סיומת נקבה (ה/ת) חובה; "העדכון" (המילה שה-⏳ מתאר) הוא זכר דקדוקית, אז המודל כתב נכון "ממתין" — אבל הצורה הבודדת הזו מסתיימת ב-nun **סופית** (ן, U+05DF), אות יוניקוד **שונה** מה-נ הרגילה (U+05E0) שבתוך "ממתינה"/"ממתינת" — לא ניתן היה לתקן רק עם סיומת אופציונלית ([הת]?), כי הבסיס "ממתינ" (עם נ רגילה) פשוט לא מופיע בתוך "ממתין" בכלל.
- **תוקן:** `_strip_markdown_emphasis()` חדש — מסיר `*`/`_` מהטקסט **לצורך matching בלבד** (לא מהטקסט שמוצג למשתמש), בלתי-תלוי-בכמות (סוגר את הפתח ל-`***מאשר***`/`_מאשר_`/`__מאשר__` וכו', לא רק "בדיוק שתי כוכביות"). מיושם בארבע נקודות הבדיקה הרלוונטיות ב-`sanitize_agent_response()`. `_AGENT_PENDING_STATUS_PATTERN` תוקן עם אלטרנציה מפורשת `(?:ממתינ[הת]|ממתין)` (לא סיומת אופציונלית) — מכיר בשתי איות שונות באמת, לא איות אחת עם זנב אופציונלי.
- **Scope:** רק A32 (`core/anti_hallucination.py`) נגע. אין שינוי ל-BUG-111, BUG-112, F52, ActionGateway, דגלי feature.
- **בדיקות:** `test_a32_approval_prose_suppression.py` הורחב ל-28/28 (מ-18) — הדגימה המדויקת, כוכבית/כוכביים/שלוש כוכביות/underscore בודד/כפול, רגרסיה שמוכיחה markdown-stripping לא הופך invite מזויף (ללא ראיית אישור) למדוכא בשקט, ורגרסיה שמוכיחה טקסט רגיל עם markdown לא נפגע (matching-only, לא משנה את הטקסט המוצג).
- **תוקן ב-commit:** `72414c3` ("BUG-113 follow-up: fix A32 markdown-emphasis and masculine-form gaps").
- **PR:** #399 (merge `bb4efdb`).
- **Merged:** כן.
- **Deployed:** כן.
- **Verified בפרודקשן:** ✅ כן — דגימת production אחרי ה-deploy (19/07/2026, "עדכן משימת בדיקת pull request 393") הראתה הודעה **יחידה** בלבד (הודעת ה-gateway), עם `[A32] Single-Speaker: ... suppressing` בלוג ו-`ownership_signal.final_reply_nonempty=false` — אין כפילות. (הדגימה הספציפית לא כללה בדיוק את אותו variant markdown-כפול שנצפה במקור, אך מוכיחה שהצינור המתוקן עובד end-to-end בפועל.)
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED.

---

## BUG-114 — ActionContracts context-interrupt call amplification — ✅ VERIFIED IN PROD / CLOSED

- **תאריך רישום:** 19/07/2026.
- **מקור:** נצפה **באותה** דגימת production שסגרה את הענף המדויק של PR #393 (ראו BUG-audit history/`CHANGE_CONTROL_LOG.md` C127) — **נושא נפרד לגמרי**, לא קשור ל-BUG-111/112/113 או PR #393/#399/#400. סומן במפורש בעדכון התיעוד הקודם כ"טרם אובחן" ונחקר עכשיו בנפרד לפי בקשה מפורשת.
- **תסמין:** הודעה נכנסת אחת (`list_tasks`, ללא קשר לאף contract חי) עם 6 `ActionContracts` פתוחים למשתמש הפיקה **19 קריאות Airtable** (`GET pending` ראשוני + 6×(`GET by contract_id` → `PATCH` → `GET by contract_id`)) — לפני שה-agent בכלל התחיל לעבד את ההודעה. `case_c_signal kind=C1 detail=live_contracts=6`, `multi_contract_conflict=true`.
- **מסך / מודול:** `core/action_gateway.py::ExecutionLedger.mark_context_interrupted()` (שורה 558), `ActionGateway.mark_context_interrupted()` (שורה 2030), נקרא מ-`app.py:3920`; `core/action_contract_repository.py::transition()` (שורה 199) — הנתיב שמבצע בפועל את ה-GET→PATCH→GET לכל contract.
- **Root Cause (מאומת בקוד, לא השערה):** `mark_context_interrupted()` נקרא בכל הודעה נכנסת שאינה resolution event (`app.py:3907-3920`), ומסמן מחדש **כל** contract "pending" של המשתמש כ-`context_interrupted=True` — כולל contracts שכבר `context_interrupted=True` מלכתחילה. ה-filter הקיים בודק רק `status == "pending"`, לא `context_interrupted`. ה-shortcut האידמפוטנטי הקיים ב-`transition()` (`action_contract_repository.py:239`) לא עוזר כאן כי הוא יורה רק כש-`updates` **ריק**, ו-`{"context_interrupted": True}` אינו ריק גם כשהערך כבר זהה. כל contract שנשאר "pending" ולא נסגר במפורש ממשיך לספוג GET+PATCH+GET מלא **על כל הודעה בלתי-קשורה עתידית**, ללא הגבלת זמן (אין job מתוזמן/TTL לניקוי contracts pending ישנים — נבדק ב-`scheduler.py`/`core/approval_queue_recovery.py`, לא נמצא).
- **ביקורת מלאה + תשובות לשש השאלות:** `docs/architecture/action-gateway/BUG-114_CONTEXT_INTERRUPT_CALL_AMPLIFICATION_AUDIT.md` (§1–§5 = הביקורת המקורית, §6 = עדכון היישום).
- **תוקן — עם תיקון חשוב מעבר להצעה המקורית:** תנאי filter נוסף ב-list comprehension הקיים של `mark_context_interrupted()`: `and (c.reconfirmation_required or not c.context_interrupted)` — **לא** `and not c.context_interrupted` הפשוט שהוצע בביקורת המקורית. ההבדל קריטי: `test_bug_reconfirmation_oneshot_fsm.py`'s Regression B (preview → הפרעה → כן → הפרעה שנייה → כן) קוראת ל-`mark_context_interrupted()` **פעמיים**; בקריאה השנייה ה-contract כבר `context_interrupted=True` מהקריאה הראשונה — filter נאיבי היה מדלג עליו **גם** כשהוא צריך supersede אמיתי, ושובר רגרסיה קיימת ומאומתת-בפרודקשן (BUG-108/BUG-PENDING-APPROVAL-B). הפער נתפס תוך כדי כתיבת הבדיקות, לא בביקורת עצמה. בדיקת RAM טהורה, ללא קריאת Airtable נוספת. אינו נוגע ב-GET-before-PATCH/GET-after-PATCH של `transition()` עצמו (Q4/Q5 — נחוצים ל-TOCTOU safety, לא מוחלשים).
- **המלצות נוספות שנשארו מחוץ לתיקון הצר (Q5/Q6 — דורשות החלטת owner נפרדת, לא מומשו):** (1) `airtable_patch()` מזניח את גוף תגובת ה-PATCH — שימוש בו במקום GET-readback נפרד יכול לצמצם עוד, אך משנה פונקציה גנרית משותפת; (2) אין TTL/ניקוי מתוזמן ל-`ActionContracts` pending ישנים (בניגוד ל-TTL כפתור הטלגרם של BUG-112) — שאלת מדיניות, לא תיקון מכני.
- **Scope:** לא נוגע ב-BUG-111/112/113, F52, EvidenceFinalizer taxonomy, או סמנטיקת אישור/דחייה/ביצוע.
- **בדיקות:** `test_bug114_context_interrupt_amplification.py` חדש (12/12) — כל 5 התרחישים המתוכננים, כולל Test 3 שמקודד במפורש את רגרסיית ה-reconfirmation_required שנתפסה. `test_bug_reconfirmation_oneshot_fsm.py` (27/27, ללא שינוי) רץ מחדש כהוכחה עצמאית שהתיקון המתוקן לא שובר את ה-FSM הקיים. suite מלא ירוק, `smoke_tests.py`, `compileall`, `git diff --check` — כולם נקיים.
- **תוקן ב-branch:** `claude/audit-action-contracts-call-amplification` (אותו branch כמו הביקורת, PR #402).
- **Merged:** תלוי במיזוג PR #402.
- **Deployed:** כן.
- **Verified בפרודקשן:** ✅ כן — דיווח production מפורש: "BUG-114 / PR #402 — ✅ PRODUCTION VERIFIED for call-amplification reduction. No repeated per-contract re-marking burst observed after already-interrupted contracts." אין יותר תבנית GET→PATCH→GET חוזרת (7×/6× וכו') על contracts שכבר `context_interrupted=True`.
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED.

---

## BUG-115 — "כן" נחטף לתפריט disambiguation גנרי במקום לאשר את תצוגת ה-ליד שהוצגה — 🔴 מבוקר (audit-only), לא תוקן

- **תאריך רישום:** 19/07/2026.
- **מקור:** דגימת production ישירה, **נושא נפרד לגמרי מ-BUG-114** (לפי בקשה מפורשת שלא לערבב) — למרות ששתיהן נובעות בסופו של דבר מאותה עובדה בסיסית: `ActionContracts` pending לא פוקעים לעולם (BUG-114 §2 שאלה 6, נשארה פתוחה במכוון).
- **תסמין (production, verbatim):**
  ```
  Eli: צור ליד חדש לענף גיוס 0548442163 ללא שם כרגע
  BOSS: 📋 זיהיתי ליד: *לענף גיוס* (0548442163)
        לשמור? ענה *כן* לאישור או *לא* לביטול.
  Eli: כן
  BOSS: יש כמה פעולות הממתינות לאישור — איזו?
        • 1. airtable_add (id: 78876ce1)
        ... (8 פריטים, tool_name + id גולמי לכל אחד)
  ```
  6 מתוך 8 ה-ids זהים בדיוק לדגימת ה-production של BUG-114 (`live_contracts=6`); פריט נוסף (`1da79b0b`) מדגימת production נפרדת (סגירת PR #393) שגם היא מעולם לא נפתרה במפורש; הפריט האחרון (`f3834e7c`, לפי סדר הכנסה) כנראה ה-contract שהתצוגה הזו עצמה יצרה.
- **מסך / מודול:** `core/action_gateway.py::ActionGateway.route_confirmation_word()` (שורה 1010, במיוחד ה-branch של `len(live) > 1`, שורות 1054-1061); `core/lead_candidate_handler.py::handle_lead_candidate()`/`_propose_lead_write()` (שורות 1191-1221, 583) — יוצר את ה-contract האמיתי בפועל שהתצוגה מתארת.
- **Root Cause (מאומת בקוד, לא השערה):** תצוגת "📋 זיהיתי ליד..." **היא** contract אמיתי ב-ActionGateway (Tier-1, לפי עיצוב BUG-056 מכוון — לא בלבול Tier-1/Tier-2 כפי שהושערה ראשונית בבקשת החקירה). `route_confirmation_word()` הניח (BUG-056) ש"בדרך כלל יש contract חי אחד — זה שהוצע עכשיו", אבל אין לו שום מנגנון לזהות "לאיזה contract ה-'כן' הזה מתייחס בפועל" — הוא רק סופר: `len(live)==1` מאשר ישירות, `len(live)>1` מציג רשימה גנרית, ללא קשר לרלוונטיות/עדכניות. כש-contracts ישנים ונטושים מצטברים (בדיוק הממצא של BUG-114 §2 שאלה 6), כל "כן" רגיל אחרי תצוגת-ליד טרייה בודדת מתדרדר לתפריט disambiguation דולף-פרטיות במקום לאשר את מה שהוצג הרגע.
- **ממצא נוסף, מאומת ונפרד:** `TurnEnvelope.active_queue_id` (הצעה ב-Phase 0, `core/turn_envelope.py`) **כן** מעדיף `action_gateway` (`priority=3`) על פני `lead_capture` (`priority=5`) — אך זהו מנגנון **תצפית בלבד** (Phase 0, מתועד במפורש כ-"never injects into the agent's prompt/context"), נבנה בנקודת קריאה נפרדת (`app.py` סעיף "1.7") ולא נקרא כלל בנתיב הניתוב האמיתי (`app.py` סעיף "2.55"). לא הגורם לבאג בפועל — שני המנגנונים רק "מסכימים" במקרה. `TurnEnvelope.message_kind` (שנשאל עליו בבקשת החקירה) **אינו קיים כמנגנון פעיל היום** — מתועד במפורש כ-"Phase 4, לא ממומש עדיין".
- **ביקורת מלאה + עיצוב תיקון מוצע:** `docs/architecture/action-gateway/BUG-115_CONFIRMATION_ROUTING_HIJACK_AUDIT.md` (חדש).
- **תיקון מוצע (לא ממומש), שני חלקים עצמאיים:**
  1. **Bookmark "contract שהוצג לאחרונה"** — reuse של דפוס `set_pending_lead_preview`/`get_pending_lead_preview` הקיים ב-`session_store.py` (לא מנגנון אחסון חדש): `_propose_lead_write()` רושם את ה-`contract_id` שהציע; `app.py`'s confirm-word branch בודק bookmark זה **לפני** `find_live_contracts()`'s ספירה גנרית — אם קיים ועדיין pending, מאשר ישירות אותו contract ספציפי, בלי קשר לכמה contracts ישנים אחרים חיים. Fallback מלא להתנהגות הקיימת כשאין bookmark/פג תוקף.
  2. **תוויות אנושיות ל-disambiguation** — שימוש חוזר ב-`_describe_contract_for_reconfirmation()` הקיים (כבר בשימוש שורה אחת מעל, לאותה מטרה בדיוק) במקום `c.tool_name`/`c.contract_id[:8]` הגולמיים.
- **Scope:** לא נוגע ב-BUG-114 (תיקון ה-filter של `mark_context_interrupted()`), F52, EvidenceFinalizer, או סמנטיקת approve/dispatch עצמה — רק "איזה contract 'כן' פותר" ו"איך רשימה מוצגת".
- **בדיקות:** לא נכתבו עדיין — 5 תרחישים מוצעים במסמך הביקורת.
- **Merged:** לא — אין קוד עדיין, רק תיעוד ביקורת.
- **Deployed:** לא רלוונטי.
- **Verified בפרודקשן:** לא רלוונטי — אין עדיין תיקון.
- **סטטוס:** 🔴 מבוקר במלואו, לא תוקן. ממתין להחלטת owner אם לממש את התיקון הצר המוצע.
