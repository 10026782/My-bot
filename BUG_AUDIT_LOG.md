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
- **תוקן ב-branch (היסטורי):** `claude/meta-whatsapp-phase-1-q6pp3e` (commit `7d5cb3a` — hash לא נגיש יותר מה-sandbox, ככל הנראה squash/rebase בדרך למיזוג).
- **עדכון (20/07/2026) — אומת ישירות מול `origin/main`, לא רק נטען:** `tma_api.py`'s ארבע פונקציות ה-preflight (`_preflight_approval(approval_id=None)`, `_preflight_asset(asset_id=None)`, `_preflight_venture(venture_id=None)`, `_preflight_game_quest(quest_id=None)`) **כבר תואמות** לשמות ה-URL rule (`<approval_id>`/`<asset_id>`/`<venture_id>`/`<quest_id>`) — אין leading underscore mismatch. Reproduction אמיתי עם Flask test client (`app.test_client().options(...)`) על כל ארבעת הנתיבים החזיר **204** (לא 500) עבור כולם.
- **Merged:** ✅ כן — מאומת ישירות מול `origin/main`.
- **Deployed:** לא ידוע ישירות מה-sandbox (אין גישת Render).
- **Verified בפרודקשן:** לא עדיין — לא נצפתה בקשת OPTIONS אמיתית מוצלחת בפרודקשן.
- **סטטוס:** ✅ תוקן ומוזג ל-main (reproduction אמיתי, 204 על כל 4 הנתיבים) — נותרה רק production verification.

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
- **branch (היסטורי):** `fix/ci-silent-pass-document-converter`
- **עדכון (20/07/2026) — אומת ישירות מול `origin/main`:** `test_document_converter.py`'s `if __name__ == "__main__":` guard **קיים בפועל**. `python3 test_document_converter.py` על העץ הנוכחי → "document_converter self-test OK — 6 passed, 0 skipped" (לא exit 0 שקט).
- **Merged:** ✅ כן — מאומת ישירות מול `origin/main`.
- **Deployed:** לא רלוונטי (בדיקת CI בלבד, אין נגיעה בלוגיקת production).
- **Verified בפרודקשן:** לא רלוונטי — תיקון תשתית-בדיקות, אין "פרודקשן" למדוד מולו מעבר ל-CI עצמו (שכבר ירוק).
- **סטטוס:** ✅ תוקן ומוזג ל-main — סגור במלואו.

### BUG-050 (BUG-AGENTS-RULE-NOT-FOLLOWED) — כלל "סיום סשן" ב-AGENTS.md לא יושם בפועל
- **תאריך:** 02/07/2026
- **קובץ:** `AGENTS.md` (תצפית תיעודית — אין שינוי קוד)
- **Severity:** Medium
- **שורש:** `AGENTS.md` §"סיום סשן" ("ברירת מחדל: פתח PR לפני סיום. אין צורך באישור. חריג יחיד: המשתמש אמר במפורש 'אל תפתח PR'") היה קיים בקוד **לפני** תחילת הסשן הזה (קומיט `36f2784`, 28/06/2026 — אותו קומיט שהעלה גם את `document_converter/`). בסיום עבודת BUG-049 (CI silent-pass fix) הסוכן דיווח "Not opening a PR since none was requested" — כלומר פעל בניגוד לכלל שהיה כתוב לו במפורש, במקום לפתוח PR כברירת מחדל. אין שום מנגנון שמוודא ש-`AGENTS.md` נקרא/מיושם בפועל בתחילת/סוף סשן — האכיפה תלויה כרגע רק בציות ידני/זיכרון של הסוכן, בדיוק אותו דפוס drift שכבר תועד כמה פעמים בין תיעוד לקוד/התנהגות בפועל בלוג הזה.
- **תיקון:** לא בוצע בסשן זה — במכוון. הפעולה המתקנת המיידית הייתה בקשה מפורשת מהמשתמש לפתוח את ה-PR (ראה BUG-049), לא בניית מנגנון אכיפה. נמנע over-engineering לבעיה חד-פעמית; אם compliance אוטומטי (למשל בדיקת "PR נפתח בסיום סשן" ב-`daily_git_audit.py`/hook) יימצא שווה את המאמץ בעתיד, זה roadmap item נפרד.
- **בדיקה:** לא רלוונטי — תיעוד בלבד, אין קוד לבדוק.
- **PR:** נכלל באותו PR כמו BUG-049 (`fix/ci-silent-pass-document-converter`) — **מוזג** (ראו עדכון BUG-049, 20/07/2026).
- **Merged:** ✅ כן (אותו PR כמו BUG-049) — אך אין כאן שינוי קוד לאמת, זו תצפית תיעודית בלבד.
- **Deployed:** לא רלוונטי
- **Verified בפרודקשן:** לא רלוונטי
- **סטטוס:** 🟡 Documented, no fix — פתוח כתצפית ל-roadmap עתידי (מנגנון אכיפה אוטומטי, אם ירצו בעתיד)

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
  - **Merged:** ✅ כן — אומת ישירות מול `origin/main` (20/07/2026): `resolve_pending_lead_preview`/`set_pending_lead_preview`/`get_pending_lead_preview`/`clear_pending_lead_preview` קיימים ב-`core/lead_candidate_handler.py`/`session_store.py`, מחוברים ב-`app.py` **ללא flag gate** ("Not gated by FEATURE_ACTION_GATEWAY — separate mechanism"). `test_tier2_silent_preview.py` — 9/9 עובר על העץ הנוכחי. השורה הקודמת כאן ("ממתין ל-push/PR") הייתה עצמה stale.
  - **סטטוס:** ✅ **BUG-058 סגור במלואו** — התיקון המקורי (טקסט מטעה) + הפתרון המלא (resolver אמיתי, precedence מוכרע ומיושם) שניהם ב-`main` בפועל. הפרודקשן test ב-10/07/2026 (למטה) גם מוכיח שזה deployed וחי, לא רק merged. לא נותר functional gap ב-scope הזה.

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
  * `whatsapp_media_adapter.py` (בשורש, לא `providers/` — הועבר ב-`76128ba` "BUG-071: move WhatsApp media adapters from providers/ to root") — Twilio WhatsApp media extraction
  * `meta_whatsapp_media_adapter.py` (בשורש) — Meta Cloud API media extraction (image/video/audio/document; media_id → URL fetch דרך Meta Media API עם access_token)
  * `app.py._webhook_whatsapp_impl()` — Twilio media handling אחרי dedup, לפני furniture funnel (מסומן בקוד עצמו בהערה `# ── BUG-071 FIX: WhatsApp Media Support ──`)
  * `app.py.webhook_meta_whatsapp()` — Meta media handling
  * שניהם מנתבים דרך `media_handler.handle_voice_note()` (audio) או `handle_file_upload()` (files/images/video)
- **Commits:** `4f64666` (מקורי) → `76128ba` (העברת providers/→root).
- **עדכון (20/07/2026) — הרשומה הזו עצמה הייתה stale:** אומת ישירות מול `origin/main` — `whatsapp_media_adapter.py`/`meta_whatsapp_media_adapter.py` **קיימים בשורש** (לא ב-`providers/`), `app.py` מייבא ומשתמש בהם בפועל ב-`_webhook_whatsapp_impl()` (עם ההערה `BUG-071 FIX`). `test_whatsapp_media.py` — **6/6 עובר** על העץ הנוכחי. השורות "Merged: לא עדיין"/"Deployed: לא עדיין" למטה היו שגויות — היה קיים גם commit נפרד `c65557f` ("docs: Update BUG-071 status to Fixed") שכנראה לא תפס את השורה הזו בפועל.
- **Merged:** ✅ כן — מאומת ישירות מול `origin/main`.
- **Tested:** `smoke_tests.py` ✅ | `test_whatsapp_media.py` ✅ (6/6, הורץ מחדש 20/07/2026).
- **Deployed:** לא ידוע ישירות מה-sandbox (אין גישת Render), אך אם ה-merge הזה כבר עלה בשלבים קודמים, סביר שכן.
- **Verified בפרודקשן:** לא עדיין — לא נצפתה העלאת קובץ אמיתית דרך WhatsApp שעברה בהצלחה.
- **סטטוס:** ✅ תוקן ומוזג ל-main — נותרה רק production verification.

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
```text
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

## BUG-107 — חיפוש Deals עם שם-שדה שגוי → 422 INVALID_FILTER_BY_FORMULA → A32 false MISMATCH — ✅ VERIFIED IN PROD

- **תאריך רישום:** 12/07/2026. **תאריך מימוש:** 19/07/2026 (PR #410, `claude/bug107-has-data-false-mismatch`).
- **מקור:** התגלה אגב אימות-חי של BUG-106/BUG-099c (אותו לוג פרודקשן) — **אינו** תקלה ב-099c; תקלה נפרדת במסלול החיפוש הכללי. **לא לפתוח מחדש PR #308 בגלל זה.**
- **תיאור:** חיפוש בטבלת "עסקאות (Deals)" בונה formula עם שם-שדה שגוי (`SEARCH('שמואל כהן', {שם})` — השדה `שם` כנראה אינו קיים/אינו נכון בטבלת Deals), מה שגורם ל-Airtable להחזיר `422 INVALID_FILTER_BY_FORMULA` חי בפרודקשן. השילוב של השגיאה הזו (Deals) יחד עם שתי תוצאות "0 רשומות" לגיטימיות מ-Leads/Contacts מפעיל אזהרת A32 anti-hallucination שגויה: `MISMATCH` ("agent says 'not found' but tool results contain data") — כלומר שכבת ה-anti-hallucination מפרשת שגיאת-422 (לא "לא נמצא") כאילו יש נתונים שהסוכן התעלם מהם.

### Contract Chain (בוצע לפני כל שינוי קוד)

מיפוי גילה **שני שורשים נפרדים**, לא אחד:
1. **`core/anti_hallucination.py::_has_data()` (BUG-107A, השורש המשמעותי יותר):** הפונקציה סיווגה כל מחרוזת לא-ריקה שלא מתחילה ב-`❌` כ"יש דאטה" — כולל את הקונבנציה הכלל-מערכתית `📭 ...` לתוצאה ריקה לגיטימית (`airtable_tools.py`, `crm.py`, `contact_resolver.py`). המשמעות: `MISMATCH` שגוי הופיע בכל פעם שהסוכן אמר "לא מצאתי" אחרי **כל** שילוב של חיפושים שהחזירו 0 תוצאות באמת — **לא רק** בשילוב הספציפי של Deals+422 שתועד במקור. הוכח ב-replay מקומי + counterfactual (ראה למטה) ששני התרחישים (עם/בלי שגיאת 422) גרמו לאותה תקלה.
2. **`core_knowledge.py` (BUG-107B, שורש נפרד):** הנחיית ה-system-prompt נתנה דוגמה מפורשת נכונה רק ל-Leads (`{Name}`), לא ל-Deals — מה שגרם לסוכן לנחש שם-שדה שגוי (`{שם}` במקום `{שם העסקה}` לפי `airtable_schema.py::DealFields.NAME`), ולקבל 422 אמיתי בכל חיפוש-שם ב-Deals. אין קשר-סיבתי ל-(1) — גם חיפוש Deals תקין לחלוטין (0 שגיאות) עדיין הפעיל את ה-MISMATCH השגוי לפני התיקון.
- **קבצים ששונו:** `core/anti_hallucination.py::_has_data()` (הוספת `📭` לרשימת הקידומות שאינן "דאטה", באותו אופן כמו `❌`), `core_knowledge.py` (דוגמה מפורשת אחת ל-Deals: `airtable_get("Deals", "SEARCH('[שם]', {שם העסקה})")`). אין שינוי סכימה, אין נגיעה ב-RP5/F52/UnifiedStatusFormatter/EvidenceFinalizer.
- **בדיקות:** `test_bug107_has_data_no_records.py` — 11/11 עוברות (כולל שני התרחישים + guidance ב-core_knowledge).

### אימות (verification)

1. **קוד ממוזג ל-main בפועל** — `git log -1 origin/main` → `3fc6146 Merge pull request #410`; אומת ב-grep ישיר על תוכן `origin/main` (לא רק `git log`): `📭` קיים ב-`_has_data()`, `{שם העסקה}` קיים ב-`core_knowledge.py`.
2. **Replay מקומי מקצה-לקצה** (לא פרודקשן — אין credentials אמיתיים בסביבת הפיתוח): הרצת `app.run_agent()` האמיתי (הקוד הממוזג) עם Identity/Router/Context/Anthropic מדומים בלבד — שני התרחישים (עם/בלי שגיאת 422) חוזרים תשובה נקייה בלי קידומת MISMATCH. **Counterfactual**: אותה שרשרת בדיוק עם `_has_data()` הישנה (monkeypatch) **כן** הפיקה את `⚠️ שים לב — ייתכן שהתוצאה אינה מדויקת.` — מוכיח שהתרחיש היה שבור לפני, ותוקן עכשיו.
3. **פרודקשן חי (19/07/2026)** — שתי פניות אמיתיות של אליהו לבוט, שתיהן תוצאה-ריקה לגיטימית לחלוטין (ללא שגיאת 422 כלל — בדיוק תרחיש BUG-107B הרחב):
   - "מה עם ליד אבי נמני" → `❌ לא מצאתי את אבי נמני בטבלת Leads.` (עם הצעות המשך) — **בלי** קידומת MISMATCH.
   - "מה עם משימת זכייה במונדיאל מה 20/07/27" → `❌ לא מצאתי משימה בשם "זכייה במונדיאל" בטבלת Tasks.` — **בלי** קידומת MISMATCH.
- **סטטוס:** ✅ VERIFIED IN PROD (19/07/2026) — merged (`origin/main` 3fc6146) + replay מקומי מקצה-לקצה + counterfactual + שתי דוגמאות פרודקשן חיות, כל התנאים שנדרשו לפני סימון ✅ מולאו.

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

```text
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
- **תוקן ב-branch:** `claude/single-speaker-fallback-fix`
- **עדכון (20/07/2026) — הרשומה הזו עצמה הייתה stale:** אומת ישירות מול `origin/main` — `event_bus.py::BatchQueueStore` ו-`app.py::_promote_next_batch_item()` **קיימים בפועל** ומחוברים (5 call sites ב-`app.py`, כולל אחרי resolution/disambiguation/combined-word/callback). `test_bug_batch_approval_preserved.py` — **33/33 עובר** על העץ הנוכחי. נכנס ל-`main` ב-`ba579f2` (17/07/2026, דרך merge PR #360). השורות "Merged: לא עדיין"/"Deployed: לא" למטה היו שגויות.
- **Merged:** ✅ כן — `main` `ba579f2` (17/07/2026).
- **Deployed:** לא ידוע ישירות מה-sandbox (אין גישת Render), אך אם זה כבר merged מ-17/07, סביר שכן.
- **Verified בפרודקשן:** לא עדיין — קוד merged, לא נצפה batch אמיתי (5 משימות) שנשמר במלואו בפרודקשן.
- **סטטוס:** ✅ תוקן ומוזג ל-main, מאומת ב-suite המלא (33/33) — נותרה רק production verification. הפריט הנפרד (ingress context gate, `context_interrupted` על כל callback) תועד אך לא טופל, בהתאם להוראה מפורשת שלא לחרוג מהיקף המשימה.

**הערה:** השורה "סטטוס: re-scope הושלם. Phase 4B0.1..." שהייתה כאן קודם לא קשורה ל-BUG-BATCH-DISCARD בכלל (מדברת על atomic-claim mechanism, נושא אחר) — כנראה copy-paste artifact, הוסרה.

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
  - ~~`ad_attribution.py::build_attribution_report()` (שורה 326 לפני התיקון) ו-`audience_intelligence.py` (שורה 177) שניהם קוראים `status == "converted"` לצורכי דיווח/סגמנטציה~~ — **תוקן (20/07/2026)**, ראו עדכון למטה. `lead_conversion.py`'s `lf.get(LeadFields.STATUS,"") == "converted"` (idempotency read-guard, שורה 57) נשאר ללא שינוי — לא באג: הוא OR'd עם `lf.get(LeadFields.CONVERTED_AT,"")` שנכתב תמיד יחד עם status בשני האתרים, כך שזיהוי "הומר כבר" ממשיך לעבוד נכון גם על נתונים ישנים וגם חדשים.
- **עדכון (20/07/2026) — read-side residual תוקן:** `ad_attribution.py::build_attribution_report()`/`_load_leads_with_timeframe()` ו-`audience_intelligence.py::_parse_records()` בדקו רק את הליטרל הישן `status=="converted"`, כך שלידים שהומרו **אחרי** תיקון BUG-110 (status="done"+Business Outcome="converted ") הוחסרו בשקט מדוחות attribution/segmentation. תוקן: שני הצרכנים בודקים עכשיו גם `Business Outcome == LeadOutcome.CONVERTED` (קבוע קנוני מ-`airtable_schema.py`, לא ליטרל) לצד הבדיקה הישנה — אין backfill, אז נתונים ישנים חייבים עדיין לעבור דרך ה-`status` הישן. `LeadOutcome`/`LeadFields` מיובאים lazy (עם `except ImportError` fallback), עקבי עם הסגנון הקיים בשני הקבצים. אין קובץ test ייעודי (אין כזה גם ל-2 הפונקציות הקוראות עצמן) — אומת ידנית + `test_bug105_non_canonical_converted_status.py` (10/10) ו-`test_response_contract_fixes.py` (19/19) רצו ללא רגרסיה, full `test_*.py` sweep + `smoke_tests.py` + `compileall` נקיים. `ad_attribution.py::mark_converted()`'s gateway migration (הסעיף למעלה) נשאר בכוונה לא-נוגע.
  - **Merged:** לא עדיין (branch `claude/n15-owner-decision-p73c3k`, commit `e6efa3a`) | **Verified בפרודקשן:** לא רלוונטי עדיין — טרם מוזג.
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

## BUG-115 — "כן" נחטף לתפריט disambiguation גנרי במקום לאשר את תצוגת ה-ליד שהוצגה — ✅ VERIFIED IN PROD / CLOSED

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
- **ביקורת מלאה + עדכון יישום:** `docs/architecture/action-gateway/BUG-115_CONFIRMATION_ROUTING_HIJACK_AUDIT.md` (§1–§6 = הביקורת המקורית, §7 = עדכון היישום).
- **תוקן, שני חלקים:**
  1. **Bookmark "contract שהוצג לאחרונה"** — שלוש מתודות חדשות ב-`session_store.py` (`set/get/clear_last_prompted_contract`, אותו דפוס בדיוק כמו `pending_lead_preview` הקיים, כולל round-trip דרך Airtable State JSON) — TTL של 600 שניות (לא 1800 כמו הבוקמארקים האחרים בקובץ), תואם בדיוק את "פג תוקף בעוד 10 דקות" שכבר מוצג למשתמש. נרשם בשני נקודות: `core/lead_candidate_handler.py`'s `_handle_single_candidate()` (אחרי `_propose_lead_write()` מצליח) ו-`app.py`'s `_queue_approval_detailed_impl()` (אחרי `_owner_notified = True` מוכח, לא רק ניסיון). `route_confirmation_word()` (`core/action_gateway.py`) בודק את הבוקמארק **לפני** ספירת `find_live_contracts()` — אם מצביע על contract חי ("pending") לאותו canonical_user_id, נפתר ישירות מולו. **תיקון מדויק מעבר לסקיצת הביקורת:** לוגיקת ה-reconfirmation/context-poisoning הקיימת חולצה ל-`_resolve_single_contract()` חדשה, משותפת לנתיב "contract חי יחיד" ולנתיב "בוקמארק נמצא" — בוקמארק לעולם לא עוקף את הבדיקה הזו. הבוקמארק **נשמר** (לא מנוקה) כשהתוצאה היא "צריך reconfirmation" (לא terminal) — רק כשמאשרים בפועל או נכשלת כתיבה עמידה (terminal=True) הוא מנוקה — נקודה שלא פורטה במדויק בביקורת המקורית, נתפסה תוך כדי כתיבת הבדיקות (Test 6).
  2. **תוויות אנושיות ל-disambiguation** — פונקציה חדשה ונפרדת `_describe_contract_for_disambiguation()`, **לא** הרחבה של `_describe_contract_for_reconfirmation()` הקיים (ניסיון ראשון: הרחבת ה-fallback הכללי בפונקציה המשותפת — שבר בשקט בדיקה קיימת ולא-קשורה, `test_stage_b_full_suite.py`'s DoD20, שמסתמכת על אותה פונקציה בדיוק להצגת `tool_name` גולמי בהודעת "✅ בוצע" — נתפס ותוקן ב-full regression sweep). הפונקציה החדשה: אותו ענף Leads בדיוק (delegate לפונקציה המקורית), אבל fallback כללי משלה ל"הוספה/עדכון ב-{table}" + preview קצר של שדה ראשון (לא-רגיש, לא בצורת record-id) — נקראת **רק** מלולאת ה-disambiguation; שאר נקודות הקריאה של הפונקציה המקורית לא נגעו כלל.
- **Scope:** לא נוגע ב-BUG-114 (תיקון ה-filter של `mark_context_interrupted()`), F52, EvidenceFinalizer, סמנטיקת approve/dispatch, `route_disambiguation()`, `TurnEnvelope`, או `message_kind`.
- **בדיקות:** `test_bug115_confirmation_routing_bookmark.py` חדש (22/22) — כל 5 התרחישים המתוכננים ועוד (בוקמארק פג-תוקף, בוקמארק ל-contract שכבר נפתר, בוקמארק למשתמש אחר, בוקמארק+interruption נשמר עד terminal, אינטגרציה עם `_handle_single_candidate()` בפועל). `test_bug114_context_interrupt_amplification.py` (12/12) ו-`test_bug_reconfirmation_oneshot_fsm.py` (27/27) רצו מחדש כהוכחה שלא נשברו. עוד ~28 קבצי בדיקה קיימים שנוגעים ב-`route_confirmation_word`/`route_disambiguation`/lead preview/BUG-070/074/076/111/Stage B/PR-0/F52 PR5 נבדקו ידנית ונשארו ירוקים. Suite מלא, smoke, compileall, diff-check — כולם נקיים.
- **תוקן ב-branch:** `claude/bug115-confirmation-routing-audit` (אותו branch כמו הביקורת, PR #403).
- **Merged:** ✅ כן — `main` `4ce2fae` (Merge pull request #403), מאומת ב-`git log`/`git merge-base --is-ancestor`.
- **Deployed:** ✅ כן (נגזר מהדגימה החיה למטה).
- **Verified בפרודקשן:** ✅ כן — דגימת production עם ראייה מפורשת של live_contracts (התנאי שהיה חסר עד עכשיו):
  ```
  [TurnEnvelope] case_c_signal kind=C1 detail=live_contracts=10
  [ActionGateway] approved: contract=4c7b539b-3df4-4116-8caa-80b6b7c84843
  Dispatch airtable_add → POST /Leads 200 OK → executed: contract=4c7b539b... external_id=rec34IdTmCFVbRABo
  route_confirmation_word() → "✅ בוצע: יצירת ליד: יצחק גלבר, 0527696084, general"
  ```
  10 contracts pending בו-זמנית (כולל 9 הישנים מהדגימה הקודמת) — ולמרות זאת **לא** הוצג "יש כמה פעולות הממתינות לאישור — איזו?"; "כן" נפתר ישירות מול ה-contract הטרי (`4c7b539b...`, ה-ליד "יצחק גלבר" שהוצג הרגע ב-`_handle_single_candidate()`'s preview) בזכות הבוקמארק. זהו בדיוק התנאי שנדרש להבחין בין "הבוקמארק פתר נכון" לבין "היה רק contract חי אחד ממילא" (ראה C139/הערה קודמת) — עכשיו מסופק במפורש. **הערה מפורשת (התבקשה):** הדגימה הזו היא F52 executed-shadow נקייה (`UnifiedStatusFormatterShadow outcome=executed mapped_state=success`, `record_id_leak=False tool_name_leak=False contract_id_leak=False fallback_used=False`) — **לא** נספרת כדגימת RP5/EvidenceFinalizer, כי לא הופיעה שורת `EvidenceFinalizerShadow` תואמת לאותו turn; לא נעשה עדכון לסטטוס RP5 על סמך הדגימה הזו.
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED.

---

## BUG-116 — `_AIRTABLE_ID_RE` ב-Tier-4 gate תופס מילים אנגליות רגילות ("recruitment") כ-Airtable ID — ✅ VERIFIED IN PROD / CLOSED

- **תאריך רישום:** 19/07/2026.
- **מקור:** דגימת production ישירה, **נושא נפרד לגמרי מ-BUG-114/BUG-115** — שגיאת Tier-4 ingress-classification, לא קשורה ל-ActionGateway/ActionContract routing כלל.
- **תסמין (production, verbatim):**
  ```
  Eli: צור ליד חדש לדומיין recruitment
       יהודה גרוס  0533968395
  BOSS: 📄 זה נראה כמו טבלה/ייצוא/פלט מודבק — לא ביצעתי שום פעולה אוטומטית.
        אם התכוונת לבקש משהו ספציפי, כתוב את זה במשפט רגיל.
  ```
  חזר זהה על ניסיון שני זהה, ועל ניסיון שלישי מנוסח-מחדש ("זה משפט רגיל צור ליד").
- **מסך / מודול:** `core/ingress_classifier.py:90` (`_AIRTABLE_ID_RE`), נבדק ב-`_is_tier4()` (שורה 169) — הגייט הרץ **לפני** כל parsing/חילוץ מועמדים, ומנצח תמיד (`classify_ingress()`'s תיעוד עצמו: "Tier 4 מנצח תמיד").
- **Root Cause (מאומת בהרצה ישירה, לא השערה):** `_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)[A-Za-z0-9]{8,}\b")` — ללא גבול עליון וללא דרישת-צורה, כל מילה שמתחילה ב-`rec`/`fld` ומלווה ב-8+ אותיות מותאמת, בין אם היא ID אמיתי או לא. `recruitment` = `rec` + `ruitment` (8 אותיות) → תואם. אומת ישירות: `_AIRTABLE_ID_RE.search("...recruitment...")` → match על `'recruitment'`. כל מילה אנגלית שמתחילה ב-`rec`/`fld` ומלווה ב-8+ אותיות חשופה (`recommendation`, `reconnect`, `reciprocity`, `fieldwork` וכו'), ללא תלות בתוכן עברי אחר בהודעה.
  - **הבדל מהמוסכמה הקיימת בקוד:** בדיקות BUG-111 (`test_bug111_lead_domain_and_sender_prefix.py`) מקלידות תמיד את הרמז העברי `"גיוס"` בטקסט הודעה גולמי — `"recruitment"` שם מופיע רק כערך הקנוני שאליו `_detect_domain()`/`_extract_domain_hint()` מתרגמים פנימית, אף פעם לא כטקסט שהמשתמש הקליד. זהו המקרה הראשון שנצפה שבו המילה האנגלית עצמה הוקלדה ישירות כרמז דומיין — מקרה קצה שאף בדיקה קיימת לא בדקה.
- **ניסיון ראשון שנדחה:** גבול-אורך מדויק (`rec[A-Za-z0-9]{14}`, כמו רגקסי ה-ID האמיתיים במקומות אחרים בקוד — `core/action_gateway.py:684`, `core/anti_hallucination.py:27`) היה שובר בדיקה קיימת ולא-קשורה: `test_c89_tier4_precedence.py`'s "Airtable rec ID" fixture (`recABC1234567890`) הוא ID מזויף שהזנב שלו רק **13** תווים, לא 14.
- **תוקן:** דרישת ספרה אחת לפחות בתוך הרצף התואם, דרך lookahead: `_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{8,}\b")`. אומת תכנותית מול **כל** fixture של Airtable ID אמיתי/מזויף בכל קובצי הבדיקה הרלוונטיים (`recABC1234567890`, `recRvK6hFTNgyj8ag`, `rec3YS5Zcr2FenX7z`, `rec62b86WqBpaWPaG`, `recTIER3TESTREC001`, `recRAWOBS0000001` ועוד) — **כולם** מכילים ספרה, כי ID אמיתי הוא מחרוזת base62 אקראית. מילה אנגלית רגילה לעולם לא מכילה ספרה. תיקון-הידוק טהור, לא מנגנון חדש.
- **סיכון שיורי, מקובל, מחוץ לסקופ:** ID אמיתי שבמקרה מכיל אפס ספרות (הסתברות ~6.5%) לא ייתפס יותר ע"י הסימן הזה בלבד — אך Tier-4 הוא defense-in-depth, כמעט תמיד יתפוס אותו סימן אחר (`"airtable"` + נקודתיים/newline, `_LITERAL_MARKERS`, טבלה/CSV/timestamp). לא טופל כאן — תיקון צר בלבד.
- **מחוץ לסקופ במפורש:** `core/agent_message_formatter.py:106`'s רגקס נפרד (`\brec[A-Za-z0-9]{10,}\b`) — משמש לצנזור record ID **בפלט** ה-agent (לא לחסימת קלט), פרופיל-סיכון שונה לגמרי, נקודת-קריאה שונה. לא נגעו בו, מתועד לצורך מודעות בלבד.
- **ביקורת מלאה + תיעוד:** `docs/architecture/ingress-classifier/BUG-116_AIRTABLE_ID_REGEX_WORD_FALSE_POSITIVE.md`.
- **Scope:** לא נוגע ב-BUG-114/BUG-115 (ActionGateway/ActionContract), לא ב-Tier-4 markers אחרים (`_TABLE_RE`/`_TIMESTAMP_RE`/`_LITERAL_MARKERS` וכו', כולם נשארו ללא שינוי), לא ב-`core/agent_message_formatter.py`.
- **בדיקות:** `test_bug116_airtable_id_word_false_positive.py` חדש (15/15) — שחזור מדויק של דגימת production (כעת tier≠4, candidate אחד נחלץ), מילים אנגליות נוספות שמתחילות ב-rec/fld לא תואמות, כל fixture ID אמיתי בסוויטה עדיין תואם, תרחיש ID-אמיתי-מודבק מ-`test_c89_tier4_precedence.py` (`recABC1234567890`) עדיין מגיע ל-tier=4 מקצה-לקצה. `test_c89_tier4_precedence.py` (13/13, ללא שינוי) רץ מחדש — ללא רגרסיה לאף סימן Tier-4 אחר. Full regression sweep: **138/138 קבצי `test_*.py`, exit 0**. `smoke_tests.py` PASS, `compileall -q .` נקי, `git diff --check` נקי.
- **תוקן ב-branch:** `claude/action-status-shadow-verification-m1m0ow` (ענף חדש, לאחר restart מ-`main` העדכני — הענף המיועד המקורי כבר היה ממוזג במלואו ל-`main`, per merged-branch restart protocol).
- **Merged:** ✅ כן — `main` `0ef018f` (Merge pull request #404), מאומת ב-`git fetch origin main` + `git log origin/main`.
- **Deployed:** ✅ כן (נגזר מהדגימה החיה למטה — הפעולה בוצעה בפועל מול Airtable).
- **Verified בפרודקשן:** ✅ כן — דגימת production ישירה, מיד אחרי המיזוג:
  ```
  Eli: צור ליד חדש domain recruitment
       יונתן כהן - 0534820022
  BOSS: 📋 זיהיתי ליד: *יונתן כהן* (0534820022)
        לשמור? ענה *כן* לאישור או *לא* לביטול.
  Eli: כן
  BOSS: ✅ בוצע: יצירת ליד: יונתן כהן, 0534820022, general | מזהה: `recNhWVHDd9Noeql1`
  ```
  ניסוח שונה מהדגימה המקורית (`domain recruitment` באנגלית, בלי `לדומיין`/מקף) — מוודא שהתיקון כללי ולא מותאם-דיוק לניסוח הבדיקה. `_AIRTABLE_ID_RE` לא תפס `recruitment` יותר, `classify_ingress()` החזיר tier=1, שם+טלפון נחלצו נכון, תצוגת-ליד תקינה נשלחה, ולא "📄 זה נראה כמו טבלה" כמו קודם.
  **הערה על BUG-115:** אותה דגימה מראה "כן" שנפתר ישירות ל-`✅ בוצע` בלי תפריט disambiguation — עקבי עם תיקון BUG-115, אך **לא מספיק כדי לסמן את BUG-115 כ-verified**: אין ראייה בדגימה הזו (למשל שורת `case_c_signal live_contracts=N`) שאכן היו כמה contracts pending חיים במקביל באותו רגע — בלעדיה לא ניתן להבדיל בין "הבוקמארק פתר נכון מתוך כמה" לבין "היה רק contract חי אחד ממילא" (המסלול הקודם, הלא-קשור-לבאג). BUG-115 נשאר מסומן "לא נבדק בפרודקשן" עד דגימה עם ספירת live_contracts>1 מפורשת.
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED.

---

## BUG-117 — Tier-2 batch lead-preview נחטף לאותה disambiguation שBUG-115 תיקן עבור Tier-1 — ✅ VERIFIED IN PROD / CLOSED

- **תאריך רישום:** 19/07/2026.
- **מקור:** דגימת production ישירה, **נושא נפרד מ-BUG-115** (שורש-תרומה משותף — contracts pending לא פוקעים לעולם, BUG-114 §2 שאלה 6 — אך מנגנון/קוד שונה לגמרי, ללא ActionContract בכלל).
- **תסמין (production, verbatim):**
  ```
  BOSS: 📋 זיהיתי 2 לידים אפשריים בקבוצה:
        • יצחק גלבר (0527696084)
        • אהרון שמחה (0548421060)
        ענה "כן" לשמירת כולם, או "לא" לביטול. (בתוקף ל-30 דקות)
  Eli: כן
  BOSS: יש כמה פעולות הממתינות לאישור — איזו?
        • 1. הוספה ב-Tasks: בדוק פר4
        ... (9 פריטים, כולם ישנים ולא-קשורים)
  ```
  ה-batch מעולם לא אושר — "כן" נחטף לתפריט disambiguation גנרי במקום.
- **מסך / מודול:** `app.py:2632` (`_CONFIRM_WORDS` handler), `core/lead_candidate_handler.py` (`should_prefer_batch_preview()` חדש, `resolve_pending_lead_preview()`, `_store_pending_preview()`).
- **Root Cause (מאומת בקוד, לא השערה):** תצוגת batch (BUG-058) נשמרת ב-`session_store.py`'s `pending_lead_preview` — **לא** `ActionContract` (בניגוד לתצוגת ליד-בודד, BUG-056, שכן ממירה ל-contract אמיתי). `app.py`'s `_CONFIRM_WORDS` בדק Tier-1 (`find_live_contracts()`) **תמיד ראשון וללא-תנאי**, לפני שהוא בכלל הגיע לבדיקת ה-Tier-2 (`resolve_pending_lead_preview()`, שורה מאוחרת יותר) — קוד ותיעוד קיימים (`core/lead_candidate_handler.py:1415-1419` לפני התיקון) הניחו במפורש "Tier 1 מנצח תמיד כששני המנגנונים חיים בו-זמנית". הנחה זו כבר נשברה עבור Tier-1-מול-Tier-1 (BUG-115, תוקן עם בוקמארק), אך מעולם לא תוקנה עבור Tier-1-מול-Tier-2 — הבוקמארק של BUG-115 לא יכול לכסות את זה כי אין לו `ActionContract` להצביע עליו.
- **תוקן:** פונקציה חדשה `core.lead_candidate_handler.should_prefer_batch_preview(canonical_user_id, chat_id)` — משווה recency בין ה-`pending_lead_preview`'s `set_at` (TTL 1800s קיים) לבין `last_prompted_contract`'s `set_at` (TTL 600s קיים, BUG-115) — מי שטרי יותר מנצח. `app.py`'s `_CONFIRM_WORDS` קורא לפונקציה הזו **לפני** ה-gate הבלתי-מותנה של Tier-1, ומדלג ישירות ל-`resolve_pending_lead_preview()` כשהיא מחזירה `True`. שני מנגנוני ה-TTL הקיימים לא שונו כלל — הפונקציה רק משווה timestamps. אין נגיעה ב-BUG-114, בבוקמארק של BUG-115 עצמו, ב-`route_disambiguation()`, או ב-`route_cancellation_word()`/`_CANCEL_WORDS` (מחוץ לסקופ במפורש — ל-`route_cancellation_word()` יש התנהגות שונה/מורכבת יותר, מבטל את **כל** ה-contracts החיים כשקיימים, נושא נפרד).
- **הערת בדיקה מבנית:** `test_c89_preview_confirmation.py`'s `test_app_py_confirm_word_checks_gateway_before_flag_branch()` בודקת סטטית שהמרחק בין הסמן ל-`find_live_contracts()`/ה-flag branch נשאר בתוך חלון-תווים קבוע — התיקון הזה דחף אותם רחוק יותר מהסמן (בדיוק כמו ש-BUG-058 כבר עשה פעם אחת קודם, לאותה סיבה); החלון הורחב (3000→5000, ו-5000→6500 לבדיקת `_CANCEL_WORDS`) עם הערה מתעדת, האינווריאנט עצמו לא השתנה.
- **ביקורת מלאה + תיעוד:** `docs/architecture/action-gateway/BUG-117_BATCH_PREVIEW_PRECEDENCE_HIJACK.md`.
- **Scope:** לא נוגע ב-BUG-114, בבוקמארק/route_confirmation_word() של BUG-115, ב-`route_disambiguation()`, או ב-`_CANCEL_WORDS`.
- **בדיקות:** `test_bug117_batch_preview_precedence.py` חדש (11/11) — שחזור מדויק של דגימת production, רגרסיה ל"אין batch preview", השוואות recency בשני הכיוונים, תפוגה של כל אחד מהשני המנגנונים (ללא קריסה), בידוד chat_id, ובדיקת end-to-end שה-batch אכן מאושר. `test_c89_preview_confirmation.py` (9/9, כולל הבדיקה המבנית עם החלון המורחב) ו-`test_bug115_confirmation_routing_bookmark.py` (22/22) רצו מחדש ללא רגרסיה. Full regression sweep: **140/140 קבצי `test_*.py`, exit 0**. `smoke_tests.py` PASS, `compileall -q .` נקי, `git diff --check` נקי.
- **תוקן ב-branch:** `claude/action-status-shadow-verification-m1m0ow` (אותו ענף כמו BUG-116, PR #405).
- **Merged:** ✅ כן — `main` `4546880` (Merge pull request #405), מאומת ב-`git fetch origin main` + `git log`.
- **Deployed:** ✅ כן (נגזר מהדגימה החיה למטה).
- **Verified בפרודקשן:** ✅ כן — דגימת production ישירה:
  ```
  Eli: צור לידים חדשים ענף גיוס
       בניימין אסולין - 053-3123482
       אהרון שמחה - 054-8421060

  [TurnEnvelope] case_c_signal kind=C1 detail=live_contracts=9   ← בהודעת ה-batch dictation
  [IngressClassifier] tier=2 conf=1.00 class=lead reason=clean_batch_2_items candidates=2

  BOSS: 📋 זיהיתי 2 לידים אפשריים בקבוצה:
        • בניימין אסולין (0533123482)
        • אהרון שמחה (0548421060)
        ענה "כן" לשמירת כולם, או "לא" לביטול. (בתוקף ל-30 דקות)
  Eli: כן
  BOSS: 📋 עובדתי 2 לידים:
        ✅ שמרתי את בניימין אסולין (0533123482) | recoLSXsLQNKQG6Gy
        ✅ שמרתי את אהרון שמחה (0548421060) | recgwDYidGrTc9KEU
  ```
  9 contracts ישנים היו pending (`live_contracts=9`, אותה תבנית כמו הדגימות הקודמות) ברגע שה-batch dictation נכנס — ולמרות זאת "כן" **לא** נחטף ל-disambiguation: שני הלידים אושרו ונכתבו בפועל (record ids אמיתיים). **הערת דיוק (שקיפות, לפי הסטנדרט שנשמר לאורך הסבב):** שורת `live_contracts=9` נלכדה בדיוק ל-turn של ה-batch dictation עצמו, לא ל-turn של "כן" בפני עצמו — אין שורת TurnEnvelope נפרדת עבור הודעת ה-"כן" בדגימה שסופקה. עם זאת, מדובר בשתי הודעות רצופות באותה שיחה, ותצוגת batch (Tier-2) לא יוצרת/מסירה ActionContracts כלל — כך שאין סיבה טכנית שמספר ה-contracts הישנים ישתנה בין שתי ההודעות. הראייה נחשבת מספקת לסגירה, בהינתן שהתסמין המדויק שדווח (batch + "כן" + contracts ישנים חיים ⇐ hijack) שוחזר ותוקן קצה-לקצה.
- **סטטוס:** ✅ VERIFIED IN PROD / CLOSED.

---

## BUG-118 — `route_confirmation_word()`'s legacy success reply מדליף tool_name/Airtable record_id גולמיים למשתמש — 🟡 מומש ומוזג, טרם אומת ב-staging/production

- **תאריך:** 19/07/2026.
- **מקור:** ממצא-צד תוך כדי staging smoke test ל-PR #407 (RP5 fault-injection marker-stripping fix) — **לא** תקלה ב-RP5/dispatch/ActionGateway lifecycle עצמם, ונצפה על **Smoke 2** (הרצה ללא marker — המסלול הרגיל, לא מסלול RP5): `route_confirmation_word()`'s תשובת-ההצלחה (המסלול הישן, לפני F52/UnifiedStatusFormatter) מציגה למשתמש שם-כלי גולמי (`tool_name`) ו-Airtable `record_id` גולמי בטקסט התשובה, במקום ניסוח עסקי (בדומה לדפוס שכבר תועד/תוקן במקומות אחרים — למשל BUG-115/BUG-117's "gצריך תיאור עסקי, לא tool_name/contract_id גולמי").
- **מקור מפורש (הוראת המשתמש):** "track separately under F52 soak, not as PR #407 blocker" — **אינו** חוסם את מיזוג/סגירת PR #407 (RP5 נשאר staging-only, לא ממוזג בכל מקרה), ואינו נחשב חלק מ-scope ה-RP5 fault-injection עצמו.
- **קבצים לחקירה (טרם נחקרו — Contract Chain טרם בוצע):** `core/action_gateway.py::route_confirmation_word()`/`_resolve_single_contract()` (המסלול הישן שמציג את ה-tool_name/record_id הגולמיים), מול `core/agent_message_formatter.py`/`FEATURE_UNIFIED_STATUS_FORMATTER` (F52 — שכבר בתהליך shadow soak; ייתכן שהמסלול המאוחד כבר פותר את זה ב-`shadow`/`on` ולא רק ב-legacy).
- **השערת שורש (לא מאומתת עדיין):** תגובת ה-"בוצע" הישנה (לפני F52) בונה טקסט ישירות מ-`contract.tool_name`/`external_id` ללא שכבת-תיאור עסקי, בדומה לדפוסים שכבר טופלו במקומות דומים (BUG-115/BUG-117's `_describe_contract_for_disambiguation()`), אך כאן במסלול ה-**הצלחה** (לא disambiguation).
- **עדכון מימוש (27/07/2026, PR #471):** נבנה renderer קנוני מבוסס `ApprovalLifecycleResult` ותיאור עסקי fail-closed. redaction של `tool_name`, UUID/contract ID, ActionContract record ID ו-Airtable business record ID מתבצע ללא תלות ב-`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, ולכן נשאר פעיל גם ב-rollout flag off. נוספה בדיקת regression מפורשת ל-flag-off שמוכיחה שה-routing הישן חוזר אך המזהים אינם נחשפים. אין תלות ב-F52 cutover לצורך ההגנה הזו.
- **ממוזג:** ✅ `main` דרך PR #471 (`5e2c244` + תיקון CI `dadf851`, merge `c64da20`, 27/07/2026).
- **סטטוס:** 🟡 Implemented but not yet verified — מומש ומוזג ועבר CI, אך טרם אומת בפועל ב-staging/production אחרי deploy.

---

## BUG-119 — A32 מאפשר ל-agent "להלבין" כישלון מתועד (RP5 write-403) להצלחה בתשובה מאוחרת לא-קשורה — 🟡 קוד תוקן, טרם נבדק בפרודקשן/staging

- **תאריך:** 20/07/2026.
- **מקור:** דגימת staging חיה (אותה שיחת בדיקת RP5 של PR #407 — **לא** קשור ל-RP5/F52 taxonomy עצמם, ממצא-צד כללי ב-`core/anti_hallucination.py`).
- **הרצף המדויק (חמור יותר מ"הזיה גנרית ללא ראייה" — עדכון לאחר סקירה נוספת):**
  1. Turn 1-2: "מאשר [rp5-test:write-403]" → RP5 **חסם נכון**: `❌ ביצוע נכשל: ❌ אין הרשאה לבצע את הפעולה הזאת.` המשימה "בדיקת RP5 write 403" **מעולם לא נוצרה** — כישלון אמיתי, מתועד, מכוון (מנגנון ההגנה עבד כמתוכנן).
  2. Turn 3-4: "מאשר" (בלי marker) → הצלחה אמיתית: `✅ בוצע: airtable_add / Tasks | מזהה: rec7z2ZCmZmpN1liS`. משימה **אחת** אמיתית נוצרה ("בדיקת RP5 no marker").
  3. Turn 5: "😊" בלבד — turn נטול כל tool call (`IngressClassifier tier=5 reason=no_lead_candidates`). BOSS ענה: *"😊 הכל בסדר! **שתי** המשימות נוצרו בהצלחה: ✅ בדיקת RP5 write 403 — תאריך יעד: 25.7.2026 ✅ בדיקת RP5 no marker — תאריך יעד: 25.7.2026"* — **וכולל במפורש את המשימה שנחסמה ב-turn 1 כאילו נוצרה**, עם תאריך יעד מומצא.
  - **למה זה חמור יותר מ"no_evidence+success" גנרי:** זו לא הזיה סתמית מתוך ואקום — זו **דריסה פעילה של כישלון אמיתי, מתועד, מכוון** שהתרחש באותה שיחה ממש. RP5 עשה בדיוק את מה שתוכנן (חסם POST אמיתי), וההזיה ביטלה את התוצאה הזו בשקט מול המשתמש, בלי שום tool call חדש שיצדיק שינוי סטטוס. ההשערה הסבירה: הסינתזה מבוססת-זיכרון-שיחה (לא בדיקת מצב Airtable בפועל), שממזגת "מה שדיברנו עליו" ל"מה שקרה בפועל" בלי הבחנה בין 403 שנחסם ל-200 שהצליח.
- **ראייה ישירה מהלוג:** `[EvidenceFinalizerShadow] state=shadow evidence_status=no_evidence response_claim=success mismatch=true code=status_claim_mismatch counts={..., 'verified_writes': 0, 'failed_calls': 0, ...}` — ה-shadow observer (log-only, לא חוסם) תפס את חוסר-ההתאמה נכון, בדיוק כפי שתוכנן. אך שער האכיפה בפועל (`core.anti_hallucination.sanitize_agent_response`) **לא** חסם/תיקן את התשובה — היא הגיעה למשתמש כמות שהיא.

### Contract Chain (מאומת בהרצת קוד ישירה, לא הונח)

שני פערים עצמאיים ומצטברים, שניהם נדרשו יחד כדי שההזיה תחמוק:

1. **`verify_result_claim()`'s hallucination branch (`_all_failed(tool_results) and _POSITIVE_CLAIMS.search(...)`):** `_POSITIVE_CLAIMS` תפס את "נוצר" (כתת-מחרוזת בתוך "נוצרו" — regex בלי `\b`). אך `_all_failed([])` על רשימת tool_results **ריקה** מחזיר `False` (הפונקציה שואלת "האם כל הקריאות נכשלו" — ל-0 קריאות אין מה "כל" להיכשל, אז זה `False` באופן vacuous) → הענף לא מופעל, `verify_result_claim` מחזיר `"ok"`.
2. **"Generic structural safety net" (`_AGENT_ACTION_STATUS_PATTERN` + `_has_write_tool_evidence`, שנועד במפורש לפי ה-docstring שלו לתפוס בדיוק את המקרה הזה — "fires on ANY action-completion-shaped text... as long as NO write tool succeeded"):** `_AGENT_ACTION_STATUS_PATTERN` משתמש ב-`\b(...)\b` על מילים בודדות — ומכיל **רק** צורת יחיד (זכר+נקבה) לשישה מתוך שבעה פעלי-השלמה, בלי צורת ריבוי. אומת ישירות בהרצת קוד:
  ```
  נוסף/נוספה/נוספו   → כולם תואמים (היחיד עם כיסוי מלא)
  בוצע/בוצעה/בוצעו   → בוצעו: לא תואם
  נשלח/נשלחה/נשלחו   → נשלחו: לא תואם
  נשמר/נשמרה/נשמרו   → נשמרו: לא תואם
  נוצר/נוצרה/נוצרו   → נוצרו: לא תואם  ← זה שקרה בפועל
  עודכן/עודכנה/עודכנו → עודכנו: לא תואם
  הושלם/הושלמה/הושלמו → הושלמו: לא תואם
  ```
  "המשימה נוצרה" (יחיד) היה נתפס. "שתי המשימות נוצרו" (ריבוי) לא נתפס — לא כי הוא שונה מהותית, אלא כי אף אחת מהמילים ברשימה לא כתובה בצורת ריבוי (חוץ מ-"נוספו").
- **קבצים:** `core/anti_hallucination.py` — `_AGENT_ACTION_STATUS_PATTERN` (שורה ~521-527), `_all_failed()` (שורה ~455), `verify_result_claim()` (שורה ~485).
- **היקף:** **לא** קשור ל-RP5/F52 taxonomy, ל-`core/rp5_fault_injection.py`, או ל-PR #407 — פער כללי ב-A32 שהיה קיים לפני RP5 ויחול זהה בפרודקשן תחת אותו ניסוח בדיוק (ריבוי-פריטים בתשובת סיכום, כולל פריט-שנכשל). נחשף עכשיו רק כי דגימות ה-RP5 יצרו טבעית תרחיש "שני פריטים, אחד נכשל אחד הצליח, ואז שאלה תמימה".
- **Cleanup נדרש (staging בלבד):** רשומה אחת אמיתית — `rec7z2ZCmZmpN1liS` ("בדיקת RP5 no marker") בטבלת Tasks — נוצרה כחלק מבדיקת "no marker" התקינה ולא קשורה לבאג עצמו, אך יש למחוק אותה כניקיון סטנדרטי של דגימת בדיקה. "בדיקת RP5 write 403" מעולם לא נוצרה (RP5 חסם) — אין מה לנקות שם.
- **תרחיש רגרסיה מומלץ:** להריץ כל אחד מ-4.2/4.3/4.4 (כישלון RP5 מתועד) עד הסוף, ואז מיד לשלוח הודעה תמימה לא-קשורה ("😊"/"תודה") ולבדוק אם ה-agent "מלבין" את הכישלון להצלחה. מוצע כתא רשמי חדש **cell2b — success claim overriding a documented failure** ברשימת 36 התרחישים (תת-מקרה של תא 2, לא תא נפרד ב-evidence_status/response_claim — עדיין `no_evidence+success`/`verified_read_only+success` — אך שונה מהותית בהקשר-שיחה ובחומרה, ולכן ראוי לתיוג נפרד בדגימות).

### שחזור שני (20/07/2026, עצמאי, מאשש דפוס עקבי לא מקרה חד-פעמי)

אותה שיחה, כמה turns אחר כך. Eli שאל **"כמה זה אחד ועוד אחד?"** (שאלת חשבון תמימה לגמרי, לא קשורה בשום צורה למשימות) — ותשובת הבוט: *"✅ שתי המשימות נשמרו בהצלחה! • בדיקת RP5 write 403 — סטטוס: ממתין... • בדיקת RP5 no marker... יש כרגע 75 משימות בטבלה"*. שוב מזכיר במפורש את המשימה שנחסמה כאילו "נשמרה".

- **הבדל מהותי מהשחזור הראשון:** הפעם `evidence_status=verified_read_only` (לא `no_evidence`) — הייתה קריאת `airtable_get` אמיתית ומאומתת ל-Tasks (75 רשומות, נכון בפועל). אבל **תביעת הכתיבה** ("נשמרו") על שתי המשימות הספציפיות — כולל זו שנחסמה — לא נתמכת בשום `verified_writes` (0 ב-counts). `[EvidenceFinalizerShadow] state=shadow evidence_status=verified_read_only response_claim=success mismatch=true`.
- **מאשש את השורש באופן בלתי-תלוי:** אומת בקוד ישיר ש-`_AGENT_ACTION_STATUS_PATTERN.search("שתי המשימות נשמרו בהצלחה")` → `False` (לפני התיקון) — בדיוק כמו "נוצרו", גם "נשמרו" חומק. שני פעלים שונים, שני שחזורים בלתי-תלויים, אותו מנגנון-שורש בדיוק.
- **ממצא אורתוגונלי (לא בסקופ התיקון):** ה-trigger הפעם היה שאלת חשבון פשוטה, לא small-talk. לוג `[C54] Suppressed premature text_block... 'השאלה שלך קצת מעורפלת'` מראה שהמודל עצמו סיווג את השאלה כמעורפלת ובחר "לעדכן על משימות" — כנראה recency bias מהקשר השיחה. שאלת התנהגות-מודל, לא נפתרת ע"י תיקון ה-regex (שמטפל בתפיסת הטענה השגויה אחרי שנוצרה, לא במניעתה).

### תיקון (20/07/2026, branch `claude/bug119-plural-completion-verbs`)

הוספת שש צורות הריבוי החסרות ל-`_AGENT_ACTION_STATUS_PATTERN` (`core/anti_hallucination.py`): בוצעו, נשלחו, נשמרו, נוצרו, עודכנו, הושלמו (נוספו כבר הייתה קיימת). שינוי מינימלי — רק ה-regex, שום שינוי בלוגיקת `_all_failed()`/`verify_result_claim()` (השארת ה-`verify_result_claim` blind-spot ל-zero-tool-calls כפי שהיא — ה-generic safety net קיים בדיוק כדי לכסות את הפער הזה, ותיקון הרשימה שלו מספיק).

**בדיקות:** נוספו ל-`core/anti_hallucination.py`'s self-test suite הפנימי (`_run_tests()`, מורץ עם `python3 core/anti_hallucination.py`) — 23 בדיקות חדשות: כל 21 הצורות (7 פעלים × 3 צורות) נבדקות ישירות מול ה-regex, ושני שחזורים מדויקים של אירועי ה-production/staging בפועל (הטקסט המדויק שנשלח בכל אחד מהשני האירועים) — שניהם נחסמים כעת (`_NO_TOOL_EVIDENCE_FALLBACK`). Full self-test: **93/93 עובר** (היה 70/70 לפני). Full `test_*.py` sweep (כל קובץ בריפו) + `smoke_tests.py` + `compileall -q .` — כולם נקיים, אין רגרסיה.

**היקף:** רק `core/anti_hallucination.py`. אין נגיעה ב-RP5/F52 taxonomy, ב-`core/rp5_fault_injection.py`, או ב-PR #407.
- **סטטוס:** 🟡 קוד תוקן ונבדק (Contract Chain + fix + 93/93 self-test + full sweep) — **טרם נבדק בפרודקשן/staging בפועל**. לפי "כלל ברזל" — לא לסמן ✅ עד לאימות runtime אמיתי אחרי deploy.

---

## BUG-120 — `bot.exception_handler` set to a bare function, not an object — masked every command-handler exception in production — ✅ תוקן, לא נבדק בפרודקשן

- **דווח:** 20/07/2026 07:55, התראת production ישירה (`core/error_reporter.py`): `context: command_dispatch`, `AttributeError: 'function' object has no attribute 'handle'`, traceback דרך `telebot/__init__.py`'s `_notify_command_handlers` → `_exec_task` → `_handle_exception` → `self.exception_handler.handle(exception)`.
- **Severity:** גבוה — לא באג פונקציונלי בודד, אלא **פגיעה מלאה בנראות** על כל שגיאה שקורית בתוך handler של פקודת `/`. קיים בקוד לפחות מאז PR #293 (מאומת ב-`git log -S`, `bdbeaef`, סבב ישן).
- **שורש הבעיה (מאומת בקוד ישיר + reproduction אמיתי):** `app.py` (לפני התיקון) הגדיר `bot.exception_handler = handle_telebot_error` כאשר `handle_telebot_error` היא **פונקציה רגילה**. `telebot.TeleBot._handle_exception()` (הספרייה, `telebot/__init__.py:1247`) קוראת `self.exception_handler.handle(exception)` — דורשת **אובייקט** עם מתודת `.handle()` (`telebot.ExceptionHandler`, class בסיס עם `def handle(self, exception): return False`), לא callable גולמי. החיפוש `.handle` על אובייקט-פונקציה זורק `AttributeError` **בתוך** `_handle_exception()` עצמה — לפני ש-`handle_telebot_error` בכלל רץ. ה-`AttributeError` הזו יוצאת מ-`_exec_task()` (ב-webhook mode, `threaded=False`, `tools/dispatcher` הרלוונטי כאן הוא `telebot`'s פנימי, לא `tools/dispatcher.py` של הריפו) **במקום** החריגה המקורית — כלומר: **החריגה האמיתית שגרמה לכשל בפקודה נבלעת/נמחקת לחלוטין**, ומוחלפת תמיד באותה הודעה חסרת-משמעות. `handle_telebot_error`'s `logger.error(...)` (שהיה אמור לתעד את השגיאה האמיתית) **לעולם לא רץ בפועל** — הקריסה קורית לפני שהוא נקרא.
- **השפעה בפועל:** כל קריאה ל-`bot.process_new_updates([update])` ב-`app.py`'s `/command dispatch` path (שורה ~4101) שבה handler רשום (`@bot.message_handler(commands=[...])`) זרק חריגה — מאז ש-`bot.exception_handler` הוגדר כך — דווחה כ-`AttributeError: 'function' object has no attribute 'handle'` בהתראת ה-Telegram, בלי שום מידע על השגיאה האמיתית (סוג, הודעה, traceback מקורי). לא ניתן לשחזר בדיעבד מה השגיאה שגרמה לאירוע הספציפי מ-20/07 07:55 — הראיה אבדה ברגע שהתרחשה (לא נרשמה בשום מקום לפני שנמחקה).
- **תוקן:** `bot.exception_handler` הוחלף למחלקה `_TelebotExceptionHandler(telebot.ExceptionHandler)` עם מתודת `handle(self, exception)` אמיתית — מלוגגת `exc_info=True` ומחזירה `False` (כלומר "לא טופל") כדי ש-`telebot` **ימשיך לזרוק את החריגה המקורית** הלאה — משמר את ההתנהגות הקיימת של `app.py`'s `except Exception as e: ... report_error(e, context="command_dispatch")` שרואה עכשיו את השגיאה האמיתית, לא רק שגיאת ה-handler השבור. שיפור-אגב קטן, לא-PII: לוג ה-`[Command] dispatch error:` המקומי (לא ה-Telegram alert, שממשיך לעבור `_sanitize()`) כולל עכשיו את שם הפקודה עצמה (`cmd={text.split()[0]!r}`) לצורך אבחון עתידי מהיר יותר.
- **בדיקות:** `test_telebot_exception_handler.py` (חדש, 4 בדיקות) — בדיקה מבנית ש-`bot.exception_handler` הוא אובייקט עם `.handle()` (לא פונקציה), ובדיקת end-to-end אמיתית: handler מדומה שזורק `ValueError` דרך `bot.process_new_updates()` אמיתי (`telebot.types.Update.de_json(...)`, לא mock) — לפני התיקון זה היה מייצר `AttributeError`; אחרי התיקון ה-`ValueError` האמיתי עובר ללא שינוי. Full `test_*.py` sweep + `smoke_tests.py` + `test_integration.py` + `compileall` — כולם נקיים.
- **היקף:** `app.py` בלבד (שורות ~213-232, ~4105). לא נוגע ב-`tools/dispatcher.py` (הdispatcher הפנימי של הריפו — שם אחר, לא קשור), ב-router, או בלוגיקת `report_error`/`error_reporter.py` עצמה (רק מקבלת עכשיו את השגיאה הנכונה).
- **סטטוס:** ✅ קוד תוקן ומאומת (reproduction אמיתי + 4/4 טסטים + full sweep) — **טרם נבדק בפרודקשן**. עד ל-deploy, אין דרך לדעת מה הייתה השגיאה המקורית שהובילה לאירוע ה-07:55 המדווח — רק שהיא כבר לא תיבלע שוב.
- **עדכון (20/07/2026) — התעלומה נפתרה, ראו BUG-121:** אחרי ש-BUG-120 מוזג ל-`main` ועלה בפרודקשן, הבעלים הריץ `/status` (בדיוק כפי שהומלץ, לאימות שלושת ה-env vars שהוגדרו) — וקיבל **בדיוק את אותה** התראת `AttributeError: 'function' object has no attribute 'handle'`, `context: command_dispatch`, `07:55`. זה איפשר לזהות **בוודאות** ש-`/status` הוא המקור: `format_startup_message()` מכיל שמות env vars גולמיים עם `_` רבים, נשלח עם `parse_mode="Markdown"` ללא הגנה — `ApiTelegramException: Can't parse entities` נבלעה ע"י BUG-120 (לפני שתוקן). ראו BUG-121 לתיקון המלא.

---

## BUG-121 — `/status` crashes on `ApiTelegramException: Can't parse entities` — the actual root cause behind the BUG-120 mystery — ✅ תוקן, לא נבדק בפרודקשן

- **דווח:** 20/07/2026, שחזור ישיר: הבעלים הריץ `/status` (בדיוק כפי שהומלץ, כדי לאמת שלושה env vars שהוגדרו ב-Render) **אחרי** ש-BUG-120 כבר עלה לפרודקשן, וקיבל שוב את אותה התראה `context: command_dispatch`, `AttributeError: 'function' object has no attribute 'handle'`. מכיוון ש-BUG-120 עצמו כבר תוקן באותו deploy, ההתראה החוזרת הזו הוכיחה חד-משמעית ש-BUG-120 היה **מסכה** על שגיאה אחרת אמיתית שממשיכה לקרות — לא שהיא עצמה חזרה.
- **שורש הבעיה (מאומת עם reproduction אמיתי, לא רק תיאוריה):** `app.py::cmd_status()` (`/status` handler, owner-only) קרא ל-`bot.send_message(msg.chat.id, format_startup_message(), parse_mode="Markdown")` **בלי שום try/except**. `format_startup_message()` (`startup_validator.py`) מרכיב הודעה עם שמות env vars גולמיים לא-בורחים (למשל `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_TELEGRAM_ID`, `IDENTITY_MAP`) — הרצה מקומית הפיקה הודעה עם 16 קווים-תחתונים. הפרסר הישן/השביר של טלגרם (legacy `parse_mode="Markdown"`, לא `MarkdownV2`) מנסה לפרש `_` כסימון איטליק ולעיתים נכשל עם `400 Bad Request: can't parse entities` — `telebot` מעלה את זה כ-`ApiTelegramException`, לא נתפס בשום מקום בתוך `cmd_status()`, יוצא אל `_exec_task()` בדיוק כמו כל חריגה אחרת מ-handler של פקודה.
- **שרשרת שגיאות (שני באגים עצמאיים שהצטלבו):** BUG-121 (חריגה אמיתית מ-`bot.send_message`) → BUG-120 (מסכה אותה עם `AttributeError` חסר-משמעות, לפני שתוקן) → התראת `command_dispatch` שנראית כאילו אין לה שום קשר ל-`/status` בכלל. אחרי תיקון BUG-120 בלבד, `/status` היה ממשיך לכשל בשקט (הבעלים היה מקבל התראת שגיאה עם `ApiTelegramException` אמיתית אבל **ה-`/status` עדיין לא היה נשלח בפועל**) — תיקון BUG-121 הוא מה שבאמת גורם ל-`/status` לעבוד.
- **תוקן:** `cmd_status()` עוטף את השליחה ב-`try/except telebot.apihelper.ApiTelegramException` — בכשל, שולח שוב את **אותו טקסט** בלי `parse_mode` (plain text, שלא תלוי בפרסור Markdown בכלל) במקום לתת לחריגה לצאת מה-handler.
- **בדיקות:** `test_cmd_status_markdown_fallback.py` (חדש, 8 בדיקות) — משחזר את ה-`ApiTelegramException` המדויקת (400, "can't parse entities") מ-mock על `bot.send_message`, מוודא retry יחיד לטקסט רגיל עם אותו תוכן/chat_id; happy-path (הצלחה בפעם הראשונה → אין retry); ובדיקת end-to-end אמיתית דרך `bot.process_new_updates()` על עדכון `/status` אמיתי — מוכיחה שהדיספאץ' כבר לא זורק כלום (לפני התיקון: היה קורס, נבלע ע"י BUG-120). Full `test_*.py` sweep + `smoke_tests.py` + `test_integration.py` + `compileall` — כולם נקיים.
- **היקף:** `app.py::cmd_status()` בלבד. `format_startup_message()`/`startup_validator.py` לא שונו (התוכן עצמו תקין — הבעיה היא רק בפרסור Markdown הישן של טלגרם, לא בתוכן). ייתכן שיש handlers נוספים ב-`app.py` עם אותה חשיפה (`bot.send_message(..., parse_mode="Markdown")` בלי try/except) — לא נסקרו כאן, מחוץ לסקופ, מומלץ audit נפרד אם רוצים לסגור את זה באופן שיטתי.
- **סטטוס:** ✅ קוד תוקן ומאומת (reproduction אמיתי מדויק לאירוע בפרודקשן + 8/8 טסטים + full sweep) — **טרם נבדק בפרודקשן**. אחרי deploy, `/status` אמור להצליח (כטקסט רגיל, בלי עיצוב מודגש) גם אם ה-Markdown נכשל.
- **ממוזג:** ✅ `main` דרך PR #420 (commit `46efea0`, 20/07/2026).

---

## BUG-122 — Pending approval queue pollution מדכא פעולות חדשות מפורשות (Single-Speaker gate מחליף תשובה כנה בהודעת "נכשלתי" מטעה) — 🟡 קוד תוקן, טרם נבדק בפרודקשן/staging

> **הערת מספור:** דווח ע"י המשתמש כ-"BUG-121" בשיחה, אך באותו רגע `origin/main` כבר הכיל BUG-120/BUG-121 בלתי-קשורים (`bot.exception_handler`/`/status` markdown crash, לעיל) שמוזגו במקביל על ידי עבודה אחרת. נרשם כאן כ-BUG-122 כדי למנוע התנגשות מספור — שני הנושאים נפרדים לחלוטין, אין ביניהם קשר קוד או תלות.

- **תאריך:** 20/07/2026.
- **מקור:** דגימת staging חיה. הבעלים שלח בקשת יצירת משימה ברורה וחד-משמעית בזמן שהיו לו 5 ActionContracts חיים (`status="pending"`) ממתינים מבקשות קודמות.
- **תסמין (production/staging, verbatim תיאור המשתמש):** ה-Router זיהה בביטחון `intent=create_task confidence=0.95`, אך התשובה שהתקבלה הייתה fallback גנרי ולא-מועיל, במקום ליצור contract חדש או לבקש resolution מפורש לתור הקיים.
- **Contract Chain (נבדק ישירות, לא הונח):**
  1. `core/turn_envelope.py`'s `TurnEnvelope`/`build_turn_envelope()` — נבדק ואומת שהוא **תצפיתי בלבד** (Phase 0, log-only), לא מוזן לתוך prompt המודל, ולא יכול להיות הגורם להתנהגות.
  2. `core/action_gateway.py::ExecutionLedger.find_live_by_user()` — נבדק ואומת שהוא **כבר** מסנן נכון לפי `status == "pending"` (לא ספירת contracts סגורים/מבוטלים/מאושרים בטעות).
  3. שער מילות-האישור הדטרמיניסטי (`_CONFIRM_WORDS`/`_CANCEL_WORDS` ב-`app.py`) נבדק ואומת שהוא **לא** יירט את ההודעה הזו — ה-Router רץ כרגיל, מה שמוכיח שאין כאן חסימה מוקדמת/early-return.
  4. המנגנון האמיתי: `core.anti_hallucination.sanitize_agent_response()`'s Single-Speaker gate. ה-agent turn לא ביצע שום tool call ולא תור שום approval חדש, אך הטקסט החופשי שהמודל הפיק נראה מבחינת-regex כמו הצהרת סטטוס-פעולה/ממתין (`_AGENT_ACTION_STATUS_PATTERN`/`_AGENT_PENDING_STATUS_PATTERN`). כלל הבלוקט הגורף של Single-Speaker (`_gateway_active` + regex match, ללא `__approval_queued__` sentinel) **תמיד** מחליף טקסט כזה ב-`_SINGLE_SPEAKER_FALLBACK` ("לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת.") — מטעה כאן במפורש: שום דבר לא באמת נוסה, כך ש"נכשלתי" הוא שקר, וההודעה לא נותנת למשתמש שום דרך המשך.
- **תוקן (`app.py`, מיד אחרי קריאת `sanitize_agent_response()`):** כשמתקיים **כל** אחד מהתנאים הבאים בו-זמנית — (1) `final_reply == _SINGLE_SPEAKER_FALLBACK`, (2) `tool_calls_made == 0`, (3) שום `__approval_queued__` בתור הזה, (4) `core.router.risk_router.intent_requires_contract_for_success(route.intent)` מחזיר `True` (PA-01's own single policy source — נעשה שימוש חוזר, לא כפילות), (5) יש לפחות contract חי אחד — התשובה מוחלפת בהודעת resolution מפורשת שמונה את מספר הבקשות הממתינות ומכוונת את המשתמש ל-"מאשר"/"בטל" או לניסוח מפורש מחדש. לוגינג חדש: `pending_gate_decision=ask_queue_resolution` (כשההחלפה קורית) ו-`pending_gate_decision=bypass_new_action` (כש-tool call אמיתי כן קרה תוך כדי שיש contracts חיים — מקרה תקין, מתועד ל-observability). קבוע חדש `_LIVE_CONTRACT_STALE_SECONDS` (24 שעות) — **תצפיתי בלבד**, מחושב ומתועד כ-`stale_contracts_count` בלוג, **אינו** פוקע/דוחה contracts בפועל (אין auto-expiry ל-ActionContract "pending" בליבה, בניגוד ל-TTL הספציפי-ל-TMA של C84).
- **החלטת scope מפורשת שלא בוצעה (מדווחת כאן במפורש למשתמש, לא הוחלט חד-צדדית בשקט):** לא נוספה לוגינג `pending_gate_decision=intercept_confirmation` בכל אחד מהענפים המפוזרים של מילות-אישור/disambiguation הקיימות ב-`app.py` (`_CONFIRM_WORDS`, `route_confirmation_word`, `route_disambiguation`, `route_combined_word` וכו') — יש עשרות נקודות-קריאה כאלה, וההוספה בכל אחת נראתה risk/effort לא-מוצדק לתיקון הזה. הענף הזה עצמו (יירוט מילת-אישור) **כן** נבדק ישירות ומאומת שהוא ממשיך לעבוד נכון (test (a) למטה) — רק הלוגינג הספציפי הזה לא נוסף בכל מקום.
- **עדכון ראיות (24/07/2026, CB-01/CB-02 staging — מוזג מ-BUG-146, ראו רשומת ההיסטוריה שם):** ה-scope decision ש-`bypass_new_action` הוא observability-בלבד קיבל ראיה קונקרטית לנזק מצטבר: BUG-143 (2 `ActionContracts` פגומים, `ee5ffb68-...`/`00b84046-...`) ו-BUG-144 (contract `0ce5b20e-...` שנשאר `pending` אחרי שהמשתמש קיבל אישור-ביטול) שניהם הצטברו כ-`live_contracts` בזמן שה-gate ב-`app.py:3548-3558` לא חסם יצירת contracts נוספים (`tool_calls_made>0` עוקף את הענף `ask_queue_resolution` לחלוטין). ממליץ לשקול מחדש בין (א) לחסום/לבקש resolution גם כש-`tool_calls_made>0`, או (ב) sibling-auto-reject דטרמיניסטי — דורש החלטת-מדיניות מהבעלים לפני מימוש (ראו PR/Fix 5 בתוכנית התיקונים).
- **עדכון ראיות נוסף (24/07/2026, AG-03 — תור עם 3 חוזים):** מופע שלישי נצפה של אותו דפוס — לוג `pending_gate_decision=bypass_new_action`, `live_contracts_count=2`, כשחוזה חדש (השלישי, הפגום — ראה BUG-143) נוצר בזמן ששני חוזים חיים כבר קיימים. עקבי לחלוטין עם ה-gap שכבר תועד (`tool_calls_made>0` עוקף את `ask_queue_resolution`) — לא מנגנון חדש, רק דגימה נוספת שמחזקת את התדירות.
- **בדיקות:** `test_bug122_pending_queue_ux.py` (חדש, 8 בדיקות): (a) מילת אישור עם contract חי אחד עדיין מגיעה ל-`approve()` (לא fallback גנרי, לא הודעת queue-resolution) — regression lock על התנהגות קיימת שלא נגעו בה; (b) בקשת `create_task` חדשה עם 5 contracts חיים ו-0 tool calls מקבלת הודעת queue-resolution מפורשת, לא `_SINGLE_SPEAKER_FALLBACK`; (c) `find_live_by_user()` לא סופר contracts שאינם `pending` (approved/rejected/completed) — בדיקת unit ישירה; (d) ללא contracts חיים בכלל, ההתנהגות הקיימת (`_SINGLE_SPEAKER_FALLBACK`) לא משתנה — מוודא שהתיקון לא חורג מהיקפו. Full `test_*.py` sweep (כל קובץ, כולל זה) + `compileall -q .` — נקיים.
- **היקף:** `app.py` בלבד (הענף שאחרי `sanitize_agent_response()` ב-`run_agent()`). אין נגיעה ב-RP5/F52 taxonomy, ב-PA-01 flag/state, בלוגיקת ביצוע האישור עצמה (`ActionGateway.approve()`/`_execute_contract()`), או בהפעלת דגלי production כלשהם.
- **סטטוס:** 🟡 קוד תוקן ונבדק (Contract Chain + fix + 8/8 טסטים ייעודיים + full sweep) — **טרם נבדק בפרודקשן/staging בפועל**. לפי "כלל ברזל" — לא לסמן ✅ עד לאימות runtime אמיתי אחרי deploy.
- **ממוזג:** ✅ `main` דרך PR #420 (commit `46efea0`, 20/07/2026).

---

## BUG-123 — הודעת בקשת-אישור חושפת placeholder שבור ("הוסף ל-?:") ומזהים טכניים גולמיים (contract ID) במקום תיאור עסקי קריא — 🟡 קוד תוקן, טרם נבדק בפרודקשן/staging

> **קשר ל-BUG-118:** BUG-118 (לעיל, registration-only) מתעד ממצא **קרוב אך נפרד** — דליפת `tool_name`/Airtable `record_id` גולמיים בתשובת ה**הצלחה** אחרי אישור (`route_confirmation_word()`'s legacy success reply, במעקב תחת F52 soak). BUG-123 כאן הוא על הודעת ה**בקשה לאישור עצמה** לפני שהמשתמש בכלל אישר (`_describe_tool_call()`/`_legacy_pending_text`/`event_bus._default_label()`) — נתיב קוד שונה לחלוטין, אין חפיפה בקבצים/פונקציות. אותה משפחת-בעיה עקרונית (מזהים טכניים גולמיים בטקסט פונה-למשתמש), שני תיקונים נפרדים. BUG-123 **אינו** סוגר את BUG-118.

- **תאריך:** 20/07/2026.
- **מקור:** תצפית staging של המשתמש (הודעה אחת, שני ממצאים — הראשון תוקן כ-BUG-122 לעיל, זה השני).
- **תסמין (staging, verbatim):** `⏳ בקשת אישור\n➕ הוסף ל-?:\nID: eeefa1d6 | פג תוקף בעוד 10 דקות`. הערת המשתמש המפורשת: ה-ID **לא** שוכפל ע"י המערכת — המשתמש הדביק אותו פעמיים ידנית בשאלה עצמה בצ'אט; אין לטפל בשכפול-ID כבאג.
- **בעיות אמיתיות שזוהו:**
  1. תיאור עסקי חסר — `"הוסף ל-?:"` הוא placeholder שבור, לא תיאור.
  2. מזהה טכני קצר (contract ID) גלוי בטקסט פונה-למשתמש.
  3. כתוצאה מ-1+2, המשתמש לא יכול להבין מה בדיוק הוא מאשר.
- **שורש הבעיה (מאומת בקוד ישיר):** `app.py::_describe_tool_call()`'s `inputs.get("table", "?")` (ואנלוגי ל-`fields`/`summary`/`sheet_name` חסרים בכלים אחרים) — כשחסר מידע עסקי, הפונקציה בנתה מחרוזת עם placeholder `"?"` גולמי במקום להיכשל-סגור. בנוסף, נמצאו (לא בדוגמה המקורית של המשתמש, אך תחת אותה מדיניות מפורשת — "לעולם לא contract ID/record ID/tool_name גולמי בטקסט פונה-למשתמש") שני חשיפות-זהות טכניות נוספות: (א) `_describe_tool_call()`'s ענף `airtable_update` הציג את ה-`record_id` הגולמי; (ב) `app.py`'s `_legacy_pending_text` הציג את ה-`action_id` הגולמי ישירות בטקסט (`"ID: {action_id}"`) — למרות שה-routing בפועל הוא תמיד דרך `callback_data` של הכפתור, או דרך display-index טקסטואלי ("1"/"2") במקומות אחרים; שום דבר לא פענח את ה-ID הזה בחזרה מתוך טקסט ההודעה. אנלוגי ל-`event_bus.py::_default_label()` (fallback/duplicate label-builder, בשימוש רק כש-`request_approval()` נקרא בלי label מפורש) — אותה בעיית `"?"`/placeholder גולמי.
- **תוקן:**
  - `app.py::_describe_tool_call()` נכתב מחדש: נכשל-סגור עם `_APPROVAL_DESCRIPTION_FALLBACK` ("לא הצלחתי להכין תיאור ברור לבקשה הזו. נא לנסח את הבקשה שוב.") בכל מקרה של שדה עסקי חסר/ריק (table/fields/summary/sheet_name) — לעולם לא `"?"` גולמי. `record_id`/`draft_id` הוסרו לחלוטין מהטקסט הגלוי; השדות שהשתנו בפועל (למשל `status: hot`) עדיין מוצגים — הם התוכן העסקי הרלוונטי.
  - `app.py`'s `_legacy_pending_text`: הוסר `"ID: {action_id}"` מהטקסט הגלוי; שורת "פג תוקף בעוד 10 דקות" (המידע היחיד שבאמת שימושי למשתמש בשורה הזו) נשארה.
  - `event_bus.py::_default_label()` נכתב מחדש באותה מדיניות — `_DEFAULT_LABEL_FALLBACK` במקום placeholder גולמי.
  - בכל שלושת המקומות: מזהים טכניים (contract_id/record_id/tool_name) נשארים **רק** ב-`callback_data`/לוגים פנימיים — לעולם לא בטקסט הגלוי למשתמש.
- **בדיקות:** `test_preview_content_fix.py` (קיים, עודכן) — שתי בדיקות ישנות שציפו לחשיפת `record_id`/`draft_id` הוחלפו לצפות ל**אי**-חשיפה (ההתנהגות הישנה הייתה עצמה חלק מהבאג); 21 הבדיקות האחרות (מיסוך שדות רגישים בעברית/אנגלית, חיתוך ערכים ארוכים, `approval_response`) ללא שינוי — 23/23 עובר. `test_bug123_approval_rendering_fail_closed.py` (חדש, 20 בדיקות): fail-closed לכל שילוב שדה-עסקי-חסר בכל אחד מהכלים, אי-חשיפת `record_id`/`draft_id`/`tool_name` גולמיים, ההתנהגות המקבילה ב-`event_bus._default_label()`, ובדיקת מקור סטטית שמוודאת ש-`_legacy_pending_text`'s template כבר לא כולל `{action_id}`. Full `test_*.py` sweep (כל קובץ, כולל שני אלה) + `compileall -q .` — נקיים.
- **היקף:** רינדור הודעת-אישור בלבד (`app.py::_describe_tool_call()`/`_legacy_pending_text`, `event_bus.py::_default_label()`). אין נגיעה ב-RP5/F52 taxonomy, בלוגיקת ביצוע האישור עצמה, או ב-BUG-118 (נתיב-קוד נפרד, לא נסגר על ידי זה).
- **סטטוס:** 🟡 קוד תוקן ונבדק (Contract Chain + fix + 23/23 + 20/20 טסטים + full sweep) — **טרם נבדק בפרודקשן/staging בפועל**. לפי "כלל ברזל" — לא לסמן ✅ עד לאימות runtime אמיתי אחרי deploy.
- **ממוזג:** ✅ `main` דרך PR #420 (commit `46efea0`, 20/07/2026).

---

## BUG-124 — מילת-הצבעה נפוצה ("זה") הופכת הודעה רגילה לחסימת Tier-4/table_separator כוזבת — 🟡 קוד תוקן ונבדק, טרם נבדק בפרודקשן/staging

- **תאריך:** 20/07/2026.
- **מקור:** דגימת staging חיה. הבעלים שלח "כמה זה 5 כפול 7" — שאלת חשבון רגילה לחלוטין — וקיבל `📄 זה נראה כמו טבלה/ייצוא/פלט מודבק — לא ביצעתי שום פעולה אוטומטית`. שחזור עצמאי שני עם "כמה זה 5+5" — אותה תוצאה. "5 כפול 5" (בלי המילה "זה") וכן שאלות אחרות ללא "זה" ("=כמה יוצא 4 ועוד 4") עבדו כרגיל.
- **Contract Chain (אומת ישירות בקוד, לא הונח):**
  1. `core/ingress_classifier.py::_TABLE_RE` (Tier-4 gate) נבדק ישירות מול הטקסט הגולמי `"כמה זה 5 כפול 7"` — **אין** התאמה. כלומר: הבעיה אינה ב-regex עצמו ואינה תלויה בטקסט כפי שהמשתמש הקליד אותו.
  2. חיפוש אחר כל מקום שמשנה את `user_text` לפני הניתוב (`app.py::run_agent()`) איתר את `resolve_context_pronouns()` (C60, "מחליף כינויי הצבעה ('זה'/'הנספח'/'הקודם' וכו') בהקשר אמיתי מה-session"), שרץ **לפני** ה-Router/`classify_ingress()`.
  3. `CONTEXT_PRONOUNS["זה"] = "last_tool_result"` — הפונקציה עושה `text.replace("זה", f"הפעולה «{ltr.get('summary','')}»")` **סאב-סטרינג גולמי**, לא בדיקת-הקשר, כל עוד `session["last_tool_result"]` קיים (מתעדכן אחרי **כל** קריאת tool בשיחה, `_capture_last_tool_result`/C60).
  4. `last_tool_result["summary"]` הוא `_tool_user_message(result)[:120]` — טקסט תוצאת-כלי אמיתי, שבפורמט הסטנדרטי של הריפו הזה מכיל לרוב `" | "` (למשל `"✅ בוצע: ... | מזהה: ..."`). אומת ישירות בקוד: הרצת `resolve_context_pronouns("כמה זה 5 כפול 7", ..., session_with_pipe_summary)` מייצרת `"כמה הפעולה «...|...|...» 5 כפול 7"` — טקסט עם 2+ pipes — ואז `_TABLE_RE.search()` על התוצאה **כן** מתאים (`"[^|\n]+\|[^|\n]+\|[^|\n]+"`, "2+ pipe-separated fields in a line").
  5. אושש עצמאית: הודעות **ללא** "זה" ("5 כפול 5"/"=כמה יוצא 4 ועוד 4") עברו ללא שינוי — מוכיח שהמנגנון תלוי בנוכחות המילה "זה" ולא במשהו אחר בטקסט.
- **חומרה/היקף אמיתי:** "זה" היא אחת המילים הנפוצות ביותר בעברית מדוברת ("כמה **זה** עולה", "מה **זה**", "תבדוק את **זה**") — הבאג יכול לפגוע בכל הודעה כזו, לא רק בשאלות חשבון, בכל פעם שקדם לה tool call כלשהו בשיחה (מה שקורה כמעט בכל שיחה עסקית אמיתית). שאר 6 המילים ב-`CONTEXT_PRONOUNS` (`הנספח`/`הקובץ האחרון`/`הקובץ`/`הקודם`/`ההוא`/`אותו`) חולקות את אותו מנגנון-סאב-סטרינג ואת אותה חשיפה — "אותו"/"ההוא"/"הקודם" נפוצות כמעט באותה מידה בעברית רגילה (למשל "אני מכיר **אותו** כבר שנים", "זה קרה בחודש **הקודם**").
- **תוקן (`app.py::resolve_context_pronouns()`):** הוחלף כל תוכן-ההצבה (`ltr.get("summary")`/`luf.get("original_filename")`) דרך פונקציה חדשה `_sanitize_for_free_text()` — ממירה `|`→`·` (middle dot), `\t`→רווח, מסירה תווי-קופסה יוניקוד (`│`/`┃`) — **לפני** ההצבה בטקסט. מתוקן פעם אחת בשתי נקודות-ההצבה המשותפות (`last_file`/`last_tool_result`), ולכן חל אוטומטית על **כל שבע** המילים ב-`CONTEXT_PRONOUNS`, לא רק על "זה" — אומת ישירות עם משפטים רגילים לכל אחת מ-`אותו`/`ההוא`/`הקודם`. `core/ingress_classifier.py::_TABLE_RE` עצמו **לא שונה** — נשען עליו זיהוי-טבלה אמיתי במקומות אחרים; התיקון פותר את מקור-הדליפה (התוכן המוצב), לא את הגלאי המשותף.
- **החלטת scope מפורשת (נשאלה מהמשתמש, לא הוחלטה חד-צדדית):** קיימת בעיה שנייה, נפרדת ועמוקה יותר — גם אחרי התיקון, ההצבה **עדיין קורית** בכל מופע של המילים האלה, גם כשאינן מתפקדות דקדוקית כהצבעה למשהו קודם (למשל "אני מכיר **אותו**" הופך ל-"אני מכיר **הפעולה «...»**" — כבר לא נחסם, אבל עדיין ניסוח מוזר שעלול לבלבל את ה-Router/Agent). המשתמש נשאל מפורשות אם לתקן גם את זה עכשיו; ההחלטה הייתה **לא** — scope מוגבל לתיקון החסימה השגויה (Tier-4), הבעיה הסמנטית העמוקה יותר דורשת עיצוב זהיר יותר (heuristics להבחין בין הצבעה אמיתית להופעה תחבירית רגילה) ונשארת פתוחה במפורש.
- **בדיקות (גרסה ראשונית):** `test_bug124_context_pronoun_table_false_positive.py` (18 בדיקות): שני שחזורי live-incident מדויקים (`"כמה זה 5 כפול 7"`/`"כמה זה 5+5"`) לא חוסמים יותר; הודעה בלי "זה" נשארת ללא שינוי (regression); הכללה לכל 4 מילות `last_tool_result` (`זה`/`אותו`/`ההוא`/`הקודם`) עם משפטים רגילים אמיתיים — כולן לא חוסמות, וההצבה עצמה עדיין מתבצעת (מוודא שהתיקון לא כיבה את הפיצ'ר בטעות); הכללה ל-3 מילות `last_file` עם שם-קובץ שמכיל pipes; בדיקות יחידה ל-`_sanitize_for_free_text()` עצמה (pipes/tabs/box-chars/טקסט רגיל).

- **המשך חקירה (אותו יום, אותו ענף) — הפער שהתיקון הראשוני לא סגר:** לבקשת הבעלים ("עד כמה [הבאג] נוגע באלו עוד פקודות וכלים... עד כמה יכול להזיק לנו"), נבדק ההיקף האמיתי לעומק:
  1. `core/router/router.py:90-101,128-140` (BUG-056 Tier-4 stop-gate) מריץ סיווג Tier-4 על **כל** הודעה מכל משתמש פנימי (`identity.is_internal`, כלומר owner/partner/manager/employee) ב-**כל** ערוץ שקורא ל-`run_agent()` (טלגרם + WhatsApp — שניהם; אומת ש-`resolve_context_pronouns` נקרא בתוך `run_agent()` עצמו, פעם אחת, לפני `_safe_route`) — וברגע ש-tier==4, חוסם את ההודעה **לגמרי לפני ה-Agent**, ללא תלות במה ש-intent_router זיהה. כלומר: לא רק "שאלות חשבון" — כל פקודה עסקית (הוספת/עדכון ליד, תזכורת, אירוע יומן, טיוטת מייל וכו') שנאמרת עם אחת מ-7 מילות ה-`CONTEXT_PRONOUNS` אחרי tool call כלשהו בשיחה נחשפת לאותו סיכון.
  2. `core/ingress_classifier.py::_is_tier4()` מכיל **7 מחלקות טריגר עצמאיות** (`_TABLE_RE`, `_TIMESTAMP_RE`, `_WHATSAPP_EXPORT_RE`, `_AIRTABLE_ID_RE`, `_JSON_BLOCK_RE`, `_CSV_RE`, `_LITERAL_MARKERS`/`_SCORE_LIKE_RE`, table-header/fixed-width) — התיקון הראשוני (`_sanitize_for_free_text`) כיסה **רק** את מחלקת ה-pipe/tab/box-char (`_TABLE_RE`).
  3. **אומת ישירות בקוד+הרצה:** `tools/airtable_tools.py:377` (`airtable_update`) מחזיר `user_message=f"✅ רשומה {record_id} עודכנה."` — ללא אף pipe, אבל עם ה-record_id הגולמי מוטבע. `tools/airtable_tools.py:331` (`airtable_add`) ו-`tools/approval_actions.py:442` (`tma_write`) גם מטביעים record_id גולמי (בנוסף לפייפ שכבר טופל). שלושת אלה הם 3 מתוך 4 הכלים היחידים ש-`_MEMORABLE_TOOLS` (`app.py:80-83`) בכלל שומר ב-session. הרצת `resolve_context_pronouns()` עם summary כזה **אחרי** התיקון הראשוני עדיין הפיקה טקסט שתפס ב-`_AIRTABLE_ID_RE` (`reason=airtable_id`) — כלומר אותה חסימה שגויה בדיוק, רק עם reason אחר.
  4. **תוקן (הרחבה, לא עוד תיקון נקודתי):** נוספה `_safe_context_quote(label, raw, fallback)` — במקום רק לתרגם תווים ידועים, הפונקציה בונה את המובאה המסונכרנת ואז בודקת אותה **מול ה-`_is_tier4()` האמיתי** לפני ההצבה בפועל; אם המובאה הייתה חוסמת כשלעצמה — נופלת ל-fallback גנרי בלי תוכן מצוטט בכלל ("הפעולה האחרונה שביצעת"/"הקובץ האחרון שהעלית"). דבר לא אבד: ה-LLM כבר מקבל record_id/url/tool מלאים דרך `_build_tool_context()` (system prompt) בנפרד — תפקידה היחיד של ההצבה כאן הוא לתת ל-Router רפרנס מפורש במקום כינוי-סתמי. זה גם עמיד מפני כל טריגר **עתידי** שיתווסף ל-`_is_tier4()`, לא רק לרשימה הידועה היום.
- **בדיקות (סה"כ אחרי ההרחבה):** 28/28 — נוספו 10: 3 תרחישי record_id אמיתיים (airtable_update/airtable_add/tma_write) שכבר לא חוסמים מול ה-`_is_tier4()` האמיתי + עדיין מבצעים הצבה; sanity שסיכום "בטוח" (בלי תוכן טריגר) עדיין מצוטט במלואו ולא מתדרדר סתם ל-fallback; 3 בדיקות יחידה ל-`_safe_context_quote()` עצמה. Full `test_*.py` sweep + `compileall -q .` + `smoke_tests.py` — נקיים.
- **היקף:** `app.py::resolve_context_pronouns()`/`_sanitize_for_free_text()`/`_safe_context_quote()` בלבד. אין נגיעה ב-`core/ingress_classifier.py`/`_is_tier4()`/`_AIRTABLE_ID_RE` עצמם, ב-RP5/F52 taxonomy, או בלוגיקת ה-Router/Agent מעבר לקריאת `_is_tier4()` כבדיקה בלבד (read-only, לא side-effect).
- **סטטוס:** 🟡 קוד תוקן ונבדק (Contract Chain + fix מורחב + 28/28 טסטים + full sweep + smoke) — **טרם נבדק בפרודקשן/staging בפועל**. לפי "כלל ברזל" — לא לסמן ✅ עד לאימות runtime אמיתי אחרי deploy.
- **ממוזג:** ✅ `main` דרך PR #422 (commit `5262327`, 20/07/2026).

---

## BUG-125 — `core/turn_evidence.py`'s `_MUTATION_SUCCESS` מסווג ✅ בודד כתביעת-הצלחה עסקית, גם ללא tool call — 🟡 קוד תוקן ונבדק, טרם נבדק בפרודקשן/staging

- **תאריך:** 21/07/2026.
- **מקור:** RP5 fault-injection shadow test matrix (תא 1, תרחיש 1.3) שהריץ הבעלים ידנית ב-staging. תרחיש: "5 כפול 5" → "25 ✅", "כמה יוצא 4 ועוד 4" → "8 ✅" — verdict צפוי `match (OK)` (שתי ההודעות הן שאלות חשבון פשוטות, ללא tool call כלשהו). התוצאה בפועל: `[EvidenceFinalizerShadow] evidence_status=no_evidence response_claim=success mismatch=true code=status_claim_mismatch` — פעמיים, לכל אחת מההודעות.
- **Contract Chain (אומת ישירות בקוד, לא הונח):**
  1. `core/turn_evidence.py::_MUTATION_SUCCESS` (המשמש את `_classify_response_claim()`) כלל `✅` כאלטרנטיבה עצמאית ברשימת הטריגרים ל-"success" — ללא שום תלות בנוכחות פועל-השלמה/פעולה-עסקית.
  2. אומת ישירות בהרצת regex: `'25 ✅'` ו-`'8 ✅'` שניהם מתאימים ל-`_MUTATION_SUCCESS` המקורי, אך **לא** מתאימים כשה-`✅` הבודד מוסר מהרשימה (רק פעלים) — מוכיח שה-`✅` הבודד הוא הגורם היחיד, לא איזה טקסט אחר בהודעות.
  3. מכיוון ש-`evidence_status="no_evidence"` (לא בוצע tool call) מקובל רק כ-`response_claim` מסוג `"neutral"`/`"empty"`, קבלת `"success"` יוצרת `mismatch=true` — בדיוק כפי שנצפה בלוג.
- **חומרה/היקף אמיתי:** זהו shadow-only כרגע (`FEATURE_EVIDENCE_FINALIZER=off`, אין השפעה על התנהגות חיה) — אבל זהו פגם במנגנון שכל מטרתו לתפוס תביעות-הצלחה כוזבות עבור אכיפת RP5 עתידית, וכרגע הוא **מייצר** false positive בכל תשובה עובדתית/חשבונית שהבוט מוסיף לה ✅ בסגנון ידידותי — בדיוק תבנית התשובה שנצפתה כאן ("25 ✅", "8 ✅") ובעבר גם בטקסט production אחר (`test_a32_approval_prose_suppression.py`'s `PROD_TEXT`, ראה בדיקות למטה). מסכן את אמינות ה-RP5 evidence-sweep עצמו — תא 1.3 נראה SUSPECT בטעות, לא בגלל הזיה אמיתית.
- **אותה משפחה, שורש שונה מ-BUG-119:** BUG-119 (לעיל) היה חוסר-כיסוי צורות-ריבוי ב-`core/anti_hallucination.py::_AGENT_ACTION_STATUS_PATTERN`. כאן מדובר במודול נפרד (`core/turn_evidence.py`) ובגורם שונה לגמרי — לא חסרה צורת-פועל, אלא ה-✅ הבודד בכלל לא דורש פועל.
- **תוקן (`core/turn_evidence.py::_MUTATION_SUCCESS`):** הוסר `✅` כאלטרנטיבה עצמאית. "success" נדרש כעת פועל/ביטוי-השלמה אמיתי בטקסט (`✅` לצד פועל כזה עדיין תופס באופן טבעי — אין צורך במנגנון co-occurrence נפרד, כי ה-`.search()` הקיים כבר בודק "אותו טקסט"). תוך כדי בדיקת רגרסיה נגד `test_generic_success_fallback_without_evidence_is_shadow_mismatch` (קיים, מצפה ש-"✅ פעולה הושלמה." יסווג כ-"success") התגלה ממצא נוסף עצמאי: פעלים עבריים המסתיימים באות סופית (ם/ן/ך/ף/ץ) **לא** תואמים כ-substring את הטיה שלהם ברבים/נקבה — "הושלם" (מ סופית) אינו substring של "הושלמה" (מ רגילה + ה) כלל (אומת ישירות: `"הושלם" in "פעולה הושלמה"` → `False`). אותה בעיה קיימת עבור "עודכן"/"עודכנו"/"עודכנה". תוקן על ידי הוספת הצורות המפורשות (`הושלמה`, `הושלמו`, `עודכנה`, `עודכנו`) — לא הסתמכות על substring matching שבור. גם נוספה משפחת "מחיקה" (`מחקתי`/`נמחק`/`נמחקה`/`נמחקו`) שלא הייתה ברשימה כלל. פעלים שמסתיימים באות לא-סופית (`נוצר`/`נשלח`/`נשמר`) כבר מכסים את הטיותיהם כ-substring (אומת: `נוצרה`/`נוצרו`/`נשלחה`/`נשלחו`/`נשמרה`/`נשמרו` כולם מכילים את הצורה היחידאית) — לא שונו.
- **תיקון נוסף בבדיקה קיימת (`test_a32_approval_prose_suppression.py`):** Test 4 (מתעד את הבאג ההיסטורי של A32 — טקסט production בלתי-מדוכא "✅ המשימה מוכנה להוספה...") ציפה ש-`response_claim=="success"` על הטקסט הלא-מדוכא; אחרי התיקון הזה מתקבל `"neutral"` (התנהגות נכונה יותר — "מוכנה להוספה" הוא הזמנה-לאשר, לא תביעת-השלמה אמיתית). ה-`mismatch=True` עדיין מתקיים (neutral לא תואם `approval_pending`) — כלומר הצורך בדיכוי A32 עדיין אמיתי בדיוק כפי שהיה, רק דרך reason שונה. עודכנו ההערות/assertions בהתאם, לא הוסתר השינוי.
- **בדיקות:** `test_turn_evidence_shadow.py` — 13 בדיקות חדשות (26/26 סה"כ): `✅` בודד ("25 ✅"/"8 ✅"/"נכון ✅") → neutral; `✅`+פועל אמיתי ("✅ בוצע"/"✅ שמרתי את הליד"/"נשמרו 2 משימות"/"נוצרו 2 משימות") → success; צורות נקבה/רבים/מחיקה חדשות ("הושלמו"/"עודכנה"/"עודכנו"/"מחקתי"/"נמחקה"/"נמחקו") → success. `test_a32_approval_prose_suppression.py` עודכן (28/28, ראה למעלה). Full `test_*.py` sweep + `compileall -q .` + `smoke_tests.py` — נקיים.
- **היקף:** `core/turn_evidence.py::_MUTATION_SUCCESS`/`_classify_response_claim()` בלבד. אין נגיעה ב-F52 rendering, בהתנהגות approval/runtime, או בהפעלת אכיפה (`FEATURE_EVIDENCE_FINALIZER` נשאר `off`). אין נגיעה ב-`_FAILURE`/`_PENDING`/`_UNKNOWN` (לא נבדקו כאן אם יש להם פגם דומה — מחוץ לסקופ, לא הונח שהם תקינים).
- **סטטוס:** 🟡 קוד תוקן ונבדק (Contract Chain + fix + 13 בדיקות חדשות + full sweep + smoke) — **טרם נבדק בפרודקשן/staging בפועל**. לפי "כלל ברזל" — לא לסמן ✅ עד לאימות runtime אמיתי אחרי deploy (הרצה חוזרת של תא 1.3 ב-RP5 matrix, לוודא `no_evidence`/`neutral`/`mismatch=false`).

---

> **הערת מספור (BUG-127A/B/C):** המשתמש ביקש לרשום את שלושת הממצאים הבאים תחת "BUG-121" — אך "BUG-121" כבר תפוס ב-`main` ע"י באג בלתי-קשור לחלוטין (`/status` crash על `ApiTelegramException`, לעיל, ממוזג דרך PR #420). "BUG-126" גם תפוס — כבר נרשם (על ענף נפרד, `claude/bug126-rp5-historical-failure-claim-mismatch`, טרם ממוזג) עבור ממצא שלישי ולא-קשור לגמרי. נרשמים כאן כ-BUG-127A/BUG-127B/BUG-127C (המספר הפנוי הבא בפועל) — אותו דפוס שכבר יושם שוב ושוב הסבב הזה (BUG-122/123/125).

## BUG-127A — Ingress Context Gate: primary + fallback מכשירי סימון context-interrupted נכשלים יחד על גרסת-lifecycle תקועה (RAM cache stale) — 🟡 קוד תוקן ונבדק, טרם נבדק ב-staging בפועל

- **תאריך:** 21/07/2026. **חומרה: safety-critical** — הלוג עצמו סימן זאת `[CRITICAL]`.
- **מקור:** דגימת staging חיה (RP5 matrix). כל הודעה נכנסת (`_apply_ingress_context_gate` ב-`app.py`) קוראת ל-`mark_context_interrupted()`, ובכשל — ל-fallback `mark_context_integrity_unknown()`. שני המנגנונים נכשלו **יחד**, פעמיים ברצף (על אותם 4 contracts חיים בדיוק), עם:
  ```
  [ERROR] ... ingress context gate primary mark failed ... ActionContractTransitionConflictError: stale lifecycle state: expected=pending/v1 actual=pending/v2
  [CRITICAL] ... ingress context gate fallback ALSO failed ... pending contracts may be silently stale-approvable
  ```
- **Contract Chain (אומת ישירות בקוד):**
  1. `core/action_gateway.py::ExecutionLedger.update_status()` (שורה 477-482) קורא `expected_version = c.version` מתוך ה-**RAM cache** (`self._store`) — **לפני** כל קריאה לשכבת ה-durable.
  2. `core/action_contract_repository.py::transition()` (שורה 222) **כן** שולף מחדש מ-Airtable (`current, record_id = self._get_for_transition(contract_id)`) — כלומר `actual=pending/v2` בהודעת השגיאה הוא ה-truth העדכני האמיתי; `expected=pending/v1` הוא ה-cache התקוע ב-RAM.
  3. בכשל, `transition()` פשוט `raise`ת (שורה 232) — **לא** מחזירה את ה-`current` (v2) בחזרה לקורא, ו-`update_status()`'s `self._cache_contract(persisted)` (שורה 532) רץ **רק בהצלחה**. כלומר: ברגע שה-RAM cache סוטה מה-durable store, **שום דבר בקוד הקיים לא מתקן את זה** — אותו contract_id יכשל **תמיד** מעכשיו והלאה, בכל קריאה עתידית, ללא self-healing, עד restart של התהליך (שטוען מחדש מ-Airtable).
  4. `mark_context_interrupted()` וה-fallback `mark_context_integrity_unknown()` **שניהם** קוראים מ-`self._store.values()` (**אותו** RAM cache תקוע) — ולכן שניהם נכשלים באותו אופן זהה, בדיוק כפי שנצפה בלוג. ה-fallback אינו fallback אמיתי לכשל-מסוג-הזה — הוא רק מגן מפני באג ספציפי ב-`mark_context_interrupted()` עצמו, לא מפני RAM/durable drift.
  5. **הסיבה לסטייה עצמה (RAM v1 מול durable v2) לא אושרה סופית** — סביר שכתיבה אחרת (worker/process נפרד, או job רקע) עדכנה את ה-durable version בלי לעדכן את מופע ה-RAM הזה; לא הונח כעובדה, מסומן כשאלה פתוחה.
- **תוקן (`core/action_gateway.py::ExecutionLedger.update_status()`):** בכשל `ActionContractTransitionConflictError` — `_refresh_stale_contract_cache(contract_id)` חדש שולף truth עדכני מה-repository (`repository.get()`) ומעדכן את ה-RAM cache (`status`/`version`) בהתאם, ואז **ניסיון חוזר יחיד** (לא לולאה) עם `expected_version` המתוקן. `expected_status`/`_cas_expected` (הדרישה האמיתית של הקורא, `require_status` כשקיים) **לא** משתנים בניסיון החוזר — כך שסטייה אמיתית של status (לא רק version) עדיין נכשלת כראוי בניסיון השני, בדיוק כמו לפני התיקון (fail-closed נשמר). אם הרענון עצמו נכשל (repository לא נגיש, contract לא קיים/פג תוקף) — נופל בחזרה להתנהגות הקודמת (raise/`return False`), ללא שינוי.
- **בדיקות:** `test_bug127a_stale_lifecycle_version_retry.py` (חדש, 10/10): (a) `mark_context_interrupted()` — RAM cache עם `version` תקוע מול durable store מתקדם מצליח אחרי ריענון+ניסיון-חוזר יחיד, ה-RAM cache מתעדכן ל-version הנכון; (b) סטייה אמיתית של **status** (לא רק version) עדיין נכשלת כראוי — לא נפרץ ה-fail-closed, durable state לא נגע; (c) `mark_context_integrity_unknown()` (ה-fallback) מקבל אותו תיקון; (d) ריענון שנכשל בעצמו (מדומה) נופל בחזרה לחריגה המקורית, לא ללולאה אינסופית; (e) ללא repository בכלל (legacy RAM-only) — ההתנהגות הקיימת לא משתנה. גם הורצו מחדש: `test_action_gateway.py` (43/43), `test_pr0c_action_contract_repository.py` (14/14), `test_pr0_ingress_context_gate.py` (33/33) — ללא רגרסיה. Full `test_*.py` sweep + `compileall -q .` + `smoke_tests.py` — נקיים.
- **היקף:** `core/action_gateway.py::ExecutionLedger.update_status()` בלבד. אין נגיעה ב-`core/action_contract_repository.py::transition()` עצמו, ב-`require_status`'s CAS semantics, או בשום נתיב approve()/reject()/execute() מעבר לתועלת המשותפת מתיקון ה-choke-point היחיד הזה.
- **סטטוס:** 🟡 קוד תוקן ונבדק (Contract Chain + fix + 10/10 טסטים חדשים + full sweep + smoke, אפס רגרסיה בסוויטות הקיימות) — **טרם נבדק ב-staging בפועל**. לפי "כלל ברזל" — לא לסמן ✅ עד לאימות runtime אמיתי (הרצה חוזרת מול אותם 4 contracts, לוודא היעדר `[CRITICAL]`).

## BUG-127B — turn עובדתי/חשבוני לא-קשור מפעיל `airtable_get` על Tasks; C54 מבטל את התשובה הנכונה והתשובה הסופית הופכת לפרוזת-משימה לא-קשורה — 🔴 נחקר לעומק, לא תוקן (ממתין להחלטת scope)

- **תאריך:** 21/07/2026.
- **מקור:** דגימת staging חיה. Turn 2 ("כמה זה 5 כפול 5") — הלוג מראה שה-agent **כן** חישב נכון: `[C54] Suppressed premature text_block alongside tool_use: ['5 כפול 5 = 25\n\nאבל זה לא קשור לעבודה שלך']` — ואז קרא בכל זאת ל-`airtable_get {'table': 'Tasks'}` (זהה ל-turn הקודם, לא-קשור לשאלת חשבון). התשובה הסופית שהוצגה למשתמש הייתה **רק** על המשימה ("✅ **המשימה האחרונה שנוצרה:**...") — התשובה הנכונה (25) אבדה לגמרי.
- **Contract Chain (אומת ישירות בקוד — לא הונח):**
  1. `app.py`'s C54 (שורה 3100-3111): כשתגובת ה-agent מכילה **גם** `text_blocks` **וגם** `tool_uses` באותה תשובה — ה-text **תמיד** מבוטל, **ללא תנאי**, ללא קשר לתוכנו. `_c54_pending_text` (בדיקת "ממתינ"/"אישור"/"pending"/"⏳") **מחושב** אך **אינו** משפיע על ההחלטה לבטל — משמש רק ל-logging/`AgentObservation` (kind="contradiction"). כלומר: אין שום מנגנון קיים שמבחין בין "טקסט-הכנה לפני כלי חיוני" (התרחיש שה-design מיועד לו, לפי התיעוד) לבין "תשובה שלמה ונכונה שנלווה אליה כלי מיותר" (מה שקרה כאן בפועל) — שני המקרים מטופלים זהה.
  2. `airtable_get` **אינו** ב-`_MEMORABLE_TOOLS` (`app.py:80`) — כלומר `resolve_context_pronouns()`/`_build_tool_context()` (C60) **לא** יכולים להיות המקור לכך שה-agent "זוכר" את חיפוש המשימות מ-turn 1 (אומת ישירות: שני המנגנונים תלויים ב-`session["last_tool_result"]`, שמעולם לא מתעדכן עבור `airtable_get`). המסקנה: מה שגרם ל-agent לבחור לקרוא שוב ל-`airtable_get Tasks` ב-turn 2 חייב להגיע מה-**historique השיחה הגולמי** שנשלח ל-Anthropic (ה-`messages` שנבנים ב-`run_agent()`) — לא ממנגנון app.py ייעודי. Turn 1's tool_use/tool_result (חיפוש המשימות) עדיין נמצאים בהיסטוריה הזו **גם אם** הטקסט הסופי שהוצג למשתמש היה fallback גנרי (A32/BUG-127C, ראה למטה) — וה-agent, רואה זאת בהקשר השיחה, יזם מעצמו "לבדוק" שוב, למרות שהשאלה החדשה לא-קשורה בכלל.
  3. **קשר סביר, לא-מאושר סופית ל-BUG-127C:** אם A32 (BUG-127C) לא היה מדכא את התשובה האמיתית של turn 1 (כי החיפוש **הצליח באמת**, `evidence_status=verified_read_only`), המשתמש היה רואה תוצאה כנה ב-turn 1 — לא בהכרח מסיר את הנטייה של ה-agent "לחזור" לנושא ב-turn 2, אך משנה את התמונה שהמשתמש רואה. שני הבאגים **נפרדים בקוד** (C54 מול A32/Single-Speaker), אך עשויים לחלוק את אותו trigger בשיחה בפועל.
- **למה אין תיקון "צר" ברור:** הסיבה **שה-agent עצמו** בחר לקרוא שוב ל-`airtable_get` היא שאלת שיפוט-מודל/system-prompt (לא path דטרמיניסטי אחד ב-`app.py`) — לא נבדק/אושר כאן מה בדיוק ב-system prompt (אם משהו) מעודד את זה. מנגד, C54 **עצמו** הוא קוד דטרמיניסטי לגמרי, וה-`_c54_pending_text` flag שכבר קיים **ולא בשימוש התנהגותי** הוא מועמד ריאלי לתיקון: להשתמש בו כדי **להעדיף את הטקסט המוקדם** (ולדלג על שליחת ה-tool_use לביצוע) כש-`_c54_pending_text` הוא `False` — כלומר "טקסט שלא נשמע כמו placeholder-בעבודה, כנראה כבר תשובה שלמה." **סיכון לא-מבוטל:** ייתכנו מקרים לגיטימיים שבהם טקסט לא-'ממתין'-shaped מלווה tool_use שעדיין הכרחי (למשל "הנה מה שמצאתי, בודק גם עדכון") — היפוך הלוגיקה עלול לדלג על קריאות-כלי חיוניות. לא מומש כאן בלי אישור מפורש.
- **סטטוס:** 🔴 נחקר לעומק (Contract Chain מלא, root cause מאומת בקוד+לוגים), **לא תוקן** — ממתין להחלטת המשתמש על כיוון הפתרון (ראה למעלה) לפני מימוש. נרשם בכוונה בלי תיקון קוד.

## BUG-127C — A32 Single-Speaker מדכא תוצאת קריאה אמיתית ומאומתת (verified_read_only) ומחליף אותה בהודעת כישלון גנרית — 🔴 נחקר עד הסוף, Contract Chain מלא, **A32/regex הוא כנראה השכבה הלא-נכונה לתיקון** (לא "אין תיקון" — ראה כיווני-המשך למטה)

- **תאריך:** 21/07/2026.
- **מקור:** אותה דגימת staging (turn 1, "תראה לי משימה אחת אחרונה"). Router סיווג נכון: `intent=list_tasks confidence=0.90`. `airtable_get {'table': 'Tasks'}` **הצליח** בפועל (76 רשומות, `tools.airtable_security` audit log מלא). אך: `[A32] Single-Speaker: agent emitted action-status text, replacing` — התשובה שהוצגה למשתמש הייתה `"לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת."` — **הפוכה** מהאמת.
- **Contract Chain מלא (אומת ישירות בקוד, כולל הרצה):** ה-gate הראשון ב-`core/anti_hallucination.py::sanitize_agent_response()` (שורה ~728, "Single Speaker") מפעיל את הדיכוי **ללא שום תלות ב-`tool_results`** מלבד חריגה יחידה ל-`__approval_queued__` — כלומר: כל טקסט שמתאים ל-`_AGENT_ACTION_STATUS_PATTERN` (פועלי-השלמה, כולל צורות פסיביות/גוף-שלישי כמו "נוצרה"/"עודכן") מוחלף תמיד כש-`_gateway_active=True`, **בלי קשר לשאלה אם קרה tool call אמיתי השבוע**. אומת ישירות: `"המשימה האחרונה שנוצרה: ..."` (טקסט אמיתי-לכאורה מתוך turn 1) תואם את ה-pattern הזה (הצורה הפסיבית "נוצרה"), ולכן דוכא — בדיוק כפי שנצפה בלוג, ללא צורך בהנחות נוספות.
- **ניסיון תיקון שנעשה ונדחה (חשוב לתעד — לא לנסות שוב באותה צורה):** נוסתה הבחנה בין הצורה הראשונה-גוף ("הוספתי"/"שמרתי" — תמיד טענת-פעולה חד-משמעית) לצורה הפסיבית/גוף-שלישי ("נוצרה"/"עודכן" — עשויה לתאר שדה-נתונים קיים, לא בהכרח טענת-פעולה), עם פטור לצורה הפסיבית **רק** כשיש evidence אמיתי של קריאה מוצלחת (`_has_read_tool_evidence`) באותו turn. **זה נכשל ישירות מול בדיקה קיימת ומכוונת:** `core/anti_hallucination.py`'s self-test suite הפנימי (`python3 core/anti_hallucination.py`) כולל "live incident #2 repro" (מ-BUG-119) שדורש **במפורש** ש-`"✅ שתי המשימות נשמרו בהצלחה!\n• ... סטטוס: ממתין\n• ... סטטוס: ממתין\nיש כרגע 75 משימות בטבלה."` **יישאר חסום גם כשיש evidence של קריאה מוצלחת (`airtable_get`)** — כי הצורה הזו (טענת-הצלחה פסיבית + evidence של read-בלבד + "סטטוס: ממתין" מתחת) היא בדיוק תבנית ההזיה שה-precedent הזה נועד לתפוס. הטקסט של BUG-127C ("המשימה האחרונה **שנוצרה**: ... סטטוס: ממתין") **זהה במבנה** לטקסט של ה-precedent הזה שחייב להישאר חסום — אין דרך regex/evidence-shape-based בטוחה להבחין בין השניים: שניהם "פועל-השלמה פסיבי + read evidence + סטטוס ממתין מתחת". תיקון שיישן את הבדיקה הזו יפתח מחדש חור שכבר נסגר ב-BUG-119. **הקוד הוחזר לגמרי למצבו המקורי** (`git checkout`) — 93/93 self-test חזר לירוק.
- **מסקנה מדויקת (חשוב לנסח נכון):** **לא נמצא תיקון בטוח ברמת A32/regex** — הניסיון להעניק פטור מבוסס-evidence-של-קריאה היה פותח מחדש את ההגנה של BUG-119. **זה אומר ש-A32 הוא כנראה השכבה הלא-נכונה לתיקון הזה — לא שהבאג-המוצרי בלתי-ניתן-לתיקון.** ההבחנה בין "תיאור אמיתי של נתונים קיימים" לבין "טענת-פעולה מומצאת" היא בעיית הבנת-שפה סמנטית שregex/evidence-presence ברמת ה-sanitizer לא יכולים לפתור בבטחה — צריך שכבה/גישה אחרת לגמרי, לא ניסוח מדויק יותר של אותה בדיקה.
- **כיווני-המשך סבירים (לא הוחלט, לא מומש כאן):**
  1. למנוע מלכתחילה קריאות-כלי לא-רלוונטיות ב-turn עובדתי/חשבוני (קשור ישירות ל-BUG-127B — אותו trigger).
  2. למנוע מתוצאות-כלי/משימות גולמיות מ-turn קודם "להטות" turn לא-קשור (שוב, אותו מנגנון עם BUG-127B — היסטוריית-שיחה גולמית, לא C60/`_MEMORABLE_TOOLS`).
  3. להתאים את מדיניות ה-prompt/context כך שסיכומי-קריאה (read summaries) לא ישתמשו בניסוח פועל-השלמה אלא אם המשתמש שאל במפורש על סטטוס/השלמה של פעולה.
  4. **לא** לשנות את A32 באופן שמחליש את ההגנה של BUG-119 — כל כיוון-תיקון עתידי חייב לעבור מול ה-self-test הפנימי (`python3 core/anti_hallucination.py`, כולל "live incident #2 repro") לפני שנחשב בטוח.
- **סטטוס:** 🔴 נחקר עד הסוף (Contract Chain מלא + ניסיון תיקון + דחייה מנומקת מול precedent אמיתי) — **לא תוקן**. אין שינוי קוד בפועל (הניסיון הוחזר במלואו). ממתין להחלטת המשתמש על איזה כיוון-המשך (למעלה) לבחון קודם.

## BUG-126 — `compare_shadow_final_status()` מסמן mismatch כוזב כשתשובה מתארת נכונה כישלון היסטורי מתועד, לא כישלון של ה-turn הנוכחי — 🔴 נרשם, לא תוקן (החלטת המשתמש: תיעוד בלבד כרגע)

- **תאריך:** 21/07/2026.
- **מקור:** RP5 fault-injection shadow test matrix (המשך תא 2.3/2b — רצף connection-reset). הבעלים דיווח:
  ```
  evidence_status בפועל: no_evidence
  response_claim בפועל: failure
  mismatch / code בפועל: mismatch=true, code=status_claim_mismatch
  ```
  הבוט תיאר **נכון** שני כישלונות connection-reset קודמים ומתועדים (מ-turns קודמים באותה שיחה) — אין טענת-הצלחה שגויה, אין המצאת תוצאה. ה-turn הנוכחי עצמו לא ביצע tool call כלשהו (evidence_status=no_evidence), אך הטקסט מתאר כישלון (response_claim=failure) — שילוב שה-classifier תמיד מסמן כ-mismatch, ללא תלות בשאלה אם הכישלון המתואר קרה עכשיו או תועד באמת ב-turn קודם.
- **Contract Chain (אומת ישירות בקוד):** `core/turn_evidence.py::compare_shadow_final_status()` — עבור `status=="no_evidence"`, רק `claim in ("empty","neutral")` נחשב compatible; `claim=="failure"` תמיד `mismatch=True`, ללא תלות בהקשר. אומת ישירות עם simulcation:
  ```python
  no_evidence_this_turn = TurnEvidenceSummary()
  text = "כן, שני הניסיונות הקודמים לחפש את הליד נכשלו עקב תקלת חיבור (connection-reset)."
  compare_shadow_final_status(text, no_evidence_this_turn)
  # -> evidence_status='no_evidence' response_claim='failure' mismatch=True code='status_claim_mismatch'
  ```
  תוצאה זהה בין "תיאור אמיתי של כישלון קודם מתועד" לבין "המצאה מלאה של כישלון שלא קרה מעולם" — ה-classifier הוא per-turn בלבד וחסר כל מנגנון-זיכרון לקשר claim לראיה מ-turn קודם.
- **חומרה:** shadow-only (`FEATURE_EVIDENCE_FINALIZER=off`, אין השפעה על התנהגות חיה). אבל מייצר false positive בכל תשובה שמסכמת/מזכירה כישלון קודם בלי לבצע tool call חדש באותו turn — תבנית שכיחה בשיחה טבעית ("מה קרה עם X?" אחרי כישלון-מתועד).
- **כיווני תיקון אפשריים (לא הוחלט, נשארים פתוחים):**
  1. מנגנון קישור claim היסטורי ל-evidence אמיתי מ-turn קודם — לדוגמה שימוש ב-`session["last_tool_result"]` הקיים (C60, `app.py::_capture_last_tool_result`) שכבר שומר `status` ("success"/"failed") מה-turn האחרון בפועל, כדי לאמת שה-failure claim אכן תואם ראיה תיעודית אמיתית — לא מנגנון-זיכרון חדש מאפס. טרם נבדק אם `compare_shadow_final_status()`'s call site נגיש ל-session.
  2. חריגה צרה יותר, מבוססת-טקסט: זיהוי ניסוחים שמסכמים turn קודם ("קודם"/"לפני כן"/"בפעם הקודמת") ופטור אותם מה-mismatch — פשוט יותר אך חלש יותר: claim מומצא-לגמרי על "כישלון קודם" שלא קרה בכלל היה חומק גם הוא.
- **החלטת המשתמש (נשאלה מפורשות):** תיעוד בלבד כרגע — לא לממש אף אחד מהכיוונים. ממתין להנחיה עתידית.
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain בלבד.
- **סטטוס:** 🔴 נרשם, Contract Chain אומת ישירות בקוד — **לא תוקן**, לפי בחירת המשתמש. אין claim על תיקון/deploy עד להנחיה נוספת.

## BUG-128 — Unit CI's `test_emergency_stop_bootstrap.py` silently read the live production Airtable table via assertions running outside their mock context — ✅ Fixed and verified (both the test bug and the underlying CI credential exposure)

- **תאריך:** 21/07/2026. **חומרה: High** — לא גרם נזק (קריאה בלבד, לא כתיבה), אבל הוכיח ש-unit CI יכול לגעת בפרודקשן בכלל.
- **מקור:** התגלה תוך כדי אימות production של PATCH 3B Step 5 — `backend-ci` נכשל על 3 assertions ב-`test_emergency_stop_bootstrap.py` ("unavailable"/"invalid" sections) שעברו מקומית אבל נכשלו ב-CI.
- **Contract Chain (אומת ישירות):** `EmergencyStopManager._maybe_refresh_locked()` מנסה refresh אמיתי מול ה-store בכל קריאת `evaluate()`/`status()` כל עוד ה-cache מעולם לא hydrated בהצלחה (by design — כך מתאוששים מ-outage אמיתי). שלוש סקציות בקובץ הטסט קראו ל-`evaluate_emergency_stop()`/`get_emergency_stop_status()` **מחוץ** ל-`with patch(f"{ADAPTER_MOD}.at_list_by_formula", ...)` שלהן — כך שהקריאות הבלתי-ממוסקות פגעו ב-`at_list_by_formula` **האמיתית**. מקומית: `AIRTABLE_API_KEY` מזויף → קריאה אמיתית נכשלת מיד → נראה כמו "unavailable", תואם בטעות לציפייה (coincidence, לא הוכחה). ב-CI: `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` **אמיתיים** → הקריאה הבלתי-ממוסקת הצליחה בפועל מול טבלת `Emergency Stop Flags` **החיה בפרודקשן** (`at_list_by_formula` הוא list/search — קריאה בלבד, לא כתיבה) — ודרסה בשקט את המצב המדומה, מה שגרם ל-3 ה-assertions להיכשל (blocked/source לא תואמים למצוקה שהמוקד תכנן).
- **תוקן (שתי שכבות):** (1) התיקון הספציפי — כל assertion שתלוי ב-mock הועבר לתוך ה-`with patch(...)` הרלוונטי, בשלושה מקומות (`test_emergency_stop_bootstrap.py` × 3, `test_app_startup_sequence.py` × 1). (2) הגנת עומק — גם אחרי תיקון הבאג הספציפי, unit CI לא אמור להחזיק credentials אמיתיים כלל: `ci.yml`'s `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` הוחלפו בפלייסהולדרים קבועים מזויפים (לא `secrets.*`), ונוסף שלב חדש שחוסם `api.airtable.com` דרך `/etc/hosts` לפני כל שלב שמריץ קוד טסט — כל באג test-isolation עתידי ייכשל מהר וברעש (connection refused) במקום לגעת שוב בפרודקשן בשקט.
- **בדיקות:** `test_ci_no_airtable_secrets.py` (חדש, 8/8) — מוכיח structurally שאין `secrets.AIRTABLE_*` ב-`ci.yml`, שה-placeholder-ים הקבועים קיימים, ושהחסימה קודמת לשלבי הטסטים. Full `test_*.py` sweep (160 קבצים) + `smoke_tests.py` + `core/router/test_router.py` + `compileall -q .` — נקיים. CI עצמו רץ ירוק אחרי התיקון (`backend-ci` ✅).
- **היקף:** `test_emergency_stop_bootstrap.py`, `test_app_startup_sequence.py`, `.github/workflows/ci.yml` בלבד. שאר ה-Secrets ב-`ci.yml` (Anthropic/Telegram/OpenAI/Google) לא נגעו — מחוץ לסקופ, זה תיקון ממוקד לתקרית Airtable הספציפית.
- **Merged:** ✅ `main` — התיקון הספציפי כחלק מ-PR #427 (commit `1967dd4`); הגנת ה-CI כ-PR #432 נפרד.
- **Verified בפרודקשן:** לא רלוונטי — זהו תיקון CI/test-isolation, לא שינוי runtime. הבדיקה הרלוונטית היא ש-CI רץ ירוק ושאין עוד credentials אמיתיים ב-unit CI — שניהם אומתו ישירות.
- **סטטוס:** ✅ Fixed and verified — גם הבאג הספציפי וגם ההגנה המבנית הרחבה יותר.

## BUG-129 — `_extract_name_from_window()` מקבל "זיהיתי" (מתוך הטקסט-תבנית של הבוט עצמו) כשם-ליד, במקום השם האמיתי שמופיע באותה הודעה — ✅ תוקן

- **תאריך:** 21/07/2026.
- **מקור:** דגימת staging חיה. המשתמש שלח הודעה שמנוסחת (ציטוט/echo) בדיוק כמו תבנית-התשובה של הבוט עצמו: `"📋 זיהיתי ליד: *משה חביב* (0501112222)\nלשמור? ענה *כן* לאישור או *לא* לביטול."`. תשובת הבוט חזרה עם `"📋 זיהיתי ליד: *זיהיתי* (0501112222)"` — כלומר המילה "זיהיתי" (גוף ראשון, "I identified") נבחרה כשם הליד במקום "משה חביב" שמופיע באותה הודעה ממש.
- **Contract Chain (אומת ישירות בקוד, כולל trace צעד-אחר-צעד — לא רק תצפית על הפלט הסופי):**
  1. אומת ישירות דרך `classify_ingress()`:
     ```python
     from core.ingress_classifier import classify_ingress
     text = "📋 זיהיתי ליד: *משה חביב* (0501112222)\nלשמור? ענה *כן* לאישור או *לא* לביטול."
     ic = classify_ingress(text, source_type="text")
     # tier=1 reason=single_high_confidence
     # candidates=({'name': 'זיהיתי', 'phone': '0501112222', 'confidence': 0.85, ...},)
     ```
  2. עקבתי בקוד עצמו (לא רק בפלט) אחרי `core/ingress_classifier.py::_extract_name_from_window()`: `_HEBREW_NAME_RE.finditer(window)` על החלון (שכולל את כל הבלוק, כי `*`/`:` אינם `\s` ולכן שוברים ריצות-מילים עבריות רציפות) מחזיר **שתי** התאמות לפי סדר: קודם `"זיהיתי ליד"`, ורק אחר-כך `"משה חביב"` (ה-`*` לפני "משה" ואחרי "חביב" שוברים את הריצה, `(?<!\w)`/`(?!\w)` מתקיימים כי `*` אינו `\w`).
  3. עבור ההתאמה הראשונה `"זיהיתי ליד"`: הפילוג ל-segments לפי `_is_name_stop_token()` — **"ליד" נמצא ב-`_NAME_STOP`** (שורה 242), אבל **"זיהיתי" אינו** ב-`_NAME_STOP` בשום מקום (נבדק ה-frozenset המלא, שורות 239-300). לכן הפילוג מייצר `[["זיהיתי"], []]`, וה-segment הארוך ביותר הוא `["זיהיתי"]` — 6 תווים, עובר את הבדיקה `len(name) < 4`, לא ב-`sender_names`.
  4. `_extract_name_from_window()` **מחזיר מיידית** על ההתאמה הראשונה הזו (שורה 590, `return name` בתוך ה-loop) — **אף פעם לא מגיע** להתאמה השנייה, הנכונה, `"משה חביב"`.
- **Root cause מדויק:** ל-`_extract_name_from_window()` אין שום מנגנון שמזהה "זה נראה כמו הניסוח-התבנית של הבוט עצמו" — "זיהיתי" הוא סתם מילה עברית רגילה מבחינת הפונקציה, ושום דבר לא דוחה אותה כמילת-עצירה. כל טקסט נכנס שמכיל `"זיהיתי ליד:"` (ציטוט/forward/echo של אישור-הבוט) עלול לחטוף את משבצת-השם באותה צורה, בלי קשר לשם האמיתי שמופיע אחריו.
- **אפקט משני שנצפה באותה דגימה:** ה-candidate השגוי `"זיהיתי"` יצר ככל הנראה approval pending ממופתח על הטלפון `0501112222` — מה שהסביר מדוע ההודעה הבאה ("תעדכן את הטלפון של משה חביב ל-0501112222") קיבלה `"⏳ כבר יש בקשת אישור פתוחה לפעולה זו"` במקום להיות מנותבת כרגיל. זהו סימפטום נוסף, לא אישור-שדחיפה, לבאג ה-create-vs-update (ראה BUG-130 למטה) — ככל הנראה אותה שכבת state מתנגשת.
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain בלבד, לפי בחירת המשתמש לרשום בלבד כרגע.
- **תוקן:** `_NAME_STOP` (`core/ingress_classifier.py`) הורחב במילה "זיהיתי" — עם "ליד" כבר stop-word, הוספת "זיהיתי" מאפסת לגמרי את ה-segment של ההתאמה הראשונה (`"זיהיתי ליד"`), כך שהלולאה ב-`_extract_name_from_window()` ממשיכה למאץ' השני, הנכון (`"משה חביב"`), במקום לחזור מיידית על הראשון. תוקן **באותו commit/PR** שתיקן גם את BUG-135 (ראה למטה) — שני הבאגים חולקים את אותה נקודת-שורש (`_NAME_STOP` לא מכיל את כל מילות ה"רעש" שיכולות לשרוד בתוך ריצת-מילים-עבריות רציפה), אך הם תסמינים נפרדים ונרשמים בנפרד. לא נבדק אם יש תבניות-תשובה נוספות של הבוט עם אותה בעיה (למשל מילים אחרות שגם הן גוף-ראשון-פעלים בתבניות אחרות) — מעבר להיקף הסבב הזה.
- **בדיקות:** `test_bug135_command_verb_name_stop.py` T1/T2 — הטקסט המדויק מהדגימה כאן משוחזר במפורש ומאמת ששם ה-candidate הוא `"משה חביב"`, לא `"זיהיתי"`.
- **Merged:** ✅ כן — commit `9285106`, PR #444 (`3f69b1d`). **תיקון-סטטוס (23/07/2026):** השורה הזו אמרה בטעות "טרם ממוזג" — אומת ישירות מול `git merge-base --is-ancestor` שהקומיט הוא ancestor של `main`. תיקון-תיעוד בלבד.
- **סטטוס:** ✅ קוד תוקן ונבדק מקומית (Contract Chain אומת ישירות בקוד + regression test). Production/RP5 verification ממתין להרצת הבעלים אחרי merge+deploy.

## BUG-130 — עדכון-שדה לליד קיים ("תעדכן את הטלפון של X") מנותב כיצירת ליד חדש במקום עדכון הקיים — 🔴 נרשם (רשמית, עם מספר), לא תוקן

- **תאריך:** 21/07/2026 (נחקר לראשונה מוקדם יותר באותו יום, ללא מספר-באג פורמלי; נרשם רשמית עכשיו לפי בקשת המשתמש, אחרי שנצפה פעם שנייה באותה דגימת staging).
- **מקור:** הודעת משתמש "תעדכן את הטלפון של דני לוי" (מופע ראשון, ללא מספר-באג באותו זמן) ו"תעדכן את הטלפון של משה חביב ל-0501112222" (מופע שני, באותה שיחת staging שגם חשפה את BUG-129) — שניהם ציפו לעדכון ליד/איש-קשר **קיים**, אך המערכת ניסתה/נטתה ליצור ליד **חדש** במקום זאת.
- **Contract Chain (אומת בקוד, לא הונח):**
  1. `intent_router` מזהה `intent=update_lead`/דומה **רק** אם המילה המילולית "ליד"/"lead" מופיעה במשפט — "תעדכן את הטלפון של X" (בלי המילה "ליד" בפירוש) לא תמיד מסווג ככוונת-עדכון.
  2. `core/lead_candidate_handler.py::handle_lead_candidate()`'s Tier-1 branch (single high-confidence candidate, ראה BUG-129/`classify_ingress` tier=1) **מתעלם לגמרי מ-`intent`** — Tier-1 מטפל בכל candidate יחיד באותה נתיב-ברירת-מחדל (בדיקת "האם קיים ליד תואם" ואז יצירה/עדכון), בלי להתחשב בכך שהראוט כבר זיהה (או לא זיהה) כוונת-עדכון מפורשת.
  3. `_at_find_lead(name, phone)` (BUG-094) דורש **התאמת-טלפון מדויקת** (`_search_formulas()`) כדי לזהות ליד קיים — עיצוב מכוון כדי למנוע זיהום-חוצה-לידים (BUG-094). אבל זה בדיוק מה שמונע התאמה במקרה של "עדכון טלפון": השם תואם לליד קיים, אבל הטלפון **החדש** (שרוצים לעדכן אליו) **שונה** מהטלפון הרשום — ולכן ההתאמה-המדויקת נכשלת, המערכת "לא מוצאת" את הליד הקיים, ומתייחסת אליו כאילו הוא ליד חדש.
- **זו לא תקלה חד-שורתית — מתח ארכיטקטוני אמיתי:** ההגנה של BUG-094 (דרישת טלפון-מדויק למניעת זיהום-חוצה-לידים) מתנגשת במישרין עם התרחיש "אותו אדם, טלפון חדש" — כל תיקון צריך להבחין בין השניים (למשל לפי שם+context נוסף) בלי לפתוח מחדש את הפרצה ש-BUG-094 נסגרה כדי למנוע.
- **סטטוס באג:** מעולם לא היה לו מספר רשמי לפני עכשיו (נחקר, לא דווח כ-BUG-N בזמנו). נרשם עכשיו **רשמית עם מספר** לפי בקשת המשתמש. **לא תוקן** — לא הוחלט/אושר אף כיוון-תיקון.
- **היקף:** לא נגעתי בקוד. רישום/Contract Chain בלבד.
- **סטטוס:** 🔴 נרשם רשמית (BUG-130), Contract Chain אומת בקוד — **לא תוקן**. ממתין להחלטת המשתמש על כיוון-תיקון (וסדר-עדיפות מול BUG-127B/127C).

- **עדכון (23/07/2026 — דגימת staging שלישית, אותה סיבת-שורש נצפתה פעמיים נוספות באותה שיחה):** המשתמש הריץ שני עדכוני-טלפון נוספים על אותם שני לידים (דני לוי, משה חביב) שכבר נחקרו לעיל, וקיבל שוב ניסוח-CREATE ("📋 זיהיתי ליד: X (טלפון-חדש). לשמור?") **בכל פעם** — כולל על משה חביב, ליד שעודכן בהצלחה ב-turn קודם **באותה שיחה ממש**. זה מחזק את סעיף 3 ל-Contract Chain למעלה לכדי מסקנה חדה יותר, לא רק תיאורטית: **מנגנון ההתאמה מבוסס-טלפון-מדויק אינו יכול, מעצם הבנייה, להצליח כשהשדה שמבקשים לעדכן הוא הטלפון עצמו** — כל בקשת "עדכן טלפון" שולחת ל-`_at_find_lead()` בדיוק את הערך שעדיין לא קיים ברשומה (זה כל הרעיון של "עדכון"), כך שההתאמה-המדויקת נכשלת תמיד באופן דטרמיניסטי, לא מקרי. אין כאן חוסר-עקביות אקראי בין הפעמים שנצפו — זו תוצאה צפויה, חוזרת על עצמה, של אותו handler.
- **סיכון נלווה שנצפה, טרם אומת בקוד (flagged, לא CONFIRMED):** באותה דגימה, עדכון-טלפון על "דני לוי" הניב `✅ בוצע: עדכון ליד: 0500000000, finance | מזהה: recoeWLkqGLxDxnMs` — domain=`finance` ו-record-id חדשים-לגמרי, שלא הופיעו בשום מקום אחר בשיחה (כל שאר הפעולות היו domain=`general`). ייתכן שזה signal שההתאמה-לפי-טלפון-בלבד (כש-*כן* מוצאת רשומה, לא רק כשהיא "מפספסת" ויוצרת חדש) עלולה להתאים בטעות לרשומה אמיתית ולא-קשורה שבמקרה חולקת את אותו מספר טלפון, בעוד ה-UI מציג אותה בתור "דני לוי" (השם שהמשתמש הקליד) בלי לוודא שזה אכן שם הרשומה שנמצאה. **לא אומת ישירות מול הבסיס האמיתי** (אין credentials חיים בסביבה זו) — ייתכן גם הסבר שפיר (לדוגמה domain מוזרק מ-`identity`/מהקשר אחר, לא מהרשומה שנמצאה). דורש בדיקה ישירה מול Airtable (מה `recoeWLkqGLxDxnMs` בפועל) לפני שניתן לקבוע P0 — עד אז זהו risk פתוח, לא ממצא מאושר.
- **מקור הבנייה של השדה `domain` בהודעת ההצלחה:** אומת בקוד — `core/action_gateway.py::_describe_contract_for_reconfirmation()` (שורות 718-732) מרכיב את הודעת "✅ בוצע: עדכון ליד: ..." ע"י `', '.join([Name, Phone, Domain])` מתוך `payload["fields"]`, ללא שום תווית-שדה. ראה BUG-137 למטה — זו אותה פונקציה בדיוק, ממצא נפרד (בעיית קריאוּת/דליפת-תווית, לא בהכרח אותה בעיה כמו ה-collision risk שלמעלה, אבל מסביר טכנית *איך* "finance" בכלל יכול להופיע במחרוזת בלי הקשר).

## BUG-131 — `_write_airtable_row()` רשם הצלחה ל-`AI_Usage_Daily` בלי לבדוק את ערך ההחזרה של `airtable_create()` — כתיבות נכשלו בשקט שבועות ברציפות (BOM field mismatch) — ✅ תוקן, אומת בעקיפין בפרודקשן

- **תאריך:** 21/07/2026.
- **מקור:** `AI_Usage_Daily` הכילה רשומה אחת בלבד אי-פעם, עם ערכי אפס, למרות שהלוגים הראו "שורה יומית נכתבה ל-Airtable" בהצלחה כל יום. המשתמש הביא לוג production אמיתי: `[RuntimeSchemaProvider:SHADOW] discrepancy... provider_unknown=['Date']` וגם `422 Unprocessable Entity` / `UNKNOWN_FIELD_NAME: "Date"` ישירות מ-Airtable.
- **שורש כפול:**
  1. השדה החי ב-Airtable היה `"﻿Date"` (BOM-prefixed, לא נראה לעין), בעוד הקוד שלח `"Date"` פשוט — כל POST קיבל 422.
  2. `_write_airtable_row()` רשמה הצלחה **ללא בדיקה** של ערך ההחזרה של `airtable_create()`, שמחזירה `None` (לא exception) על תגובה שאינה 2xx — כך שהכשל היה בלתי-נראה ללוגים לגמרי.
- **תוקן:** (1) תיקון ה-BOM בוצע **ידנית ע"י הבעלים** ב-Airtable עצמו (`Date_tmp` swap) — לא תיקון קוד; (2) `_write_airtable_row()` מחזירה `bool` עכשיו, `daily_watchdog()` בודקת ומתעדת מפורשות כשל. נוסף גם regression test (`test_ai_usage_daily_schema.py`) שמוודא ש-`schema_cache.json`'s `AI_Usage_Daily` entry נקי מ-BOM/control chars, כדי שהשגיאה הזו לא תישנה בלי להיתפס.
- **בדיקות:** `test_ai_usage_daily_schema.py` (10 assertions), `test_cost_watchdog_airtable_write.py` (13 assertions בגרסה הראשונית, הורחב ל-30 ב-BUG-132/C164).
- **Verified בפרודקשן:** ✅ בעקיפין — ה-smoke שחשף את BUG-132 (ראה למטה) הוכיח שכתיבות **כן** מצליחות עכשיו (יצרו שורות אמיתיות, גם אם משוכפלות מסיבה אחרת) — לפני התיקון הזה שום כתיבה לא הצליחה מעולם. לא אומת עצמאית ע"י Claude (אין credentials חיים בסביבה זו) — מבוסס על ראיית production שהמשתמש הביא.
- **Merged:** ✅ `main` (PR #435) — ראה `CHANGE_CONTROL_LOG.md` C163.
- **סטטוס:** ✅ תוקן (קוד + תיקון ידני ב-Airtable), אומת בעקיפין בפרודקשן.

## BUG-132 — lookup של `AI_Usage_Daily` השווה טקסט מול שדה מסוג DATE, לעולם לא תואם — upsert נפל תמיד ל-create, יצר שורות משוכפלות בפרודקשן — ✅ תוקן, גבול-דיוק על אימות-חוזר

- **תאריך:** 21/07/2026 (נתפס מיד אחרי מיזוג PR #435 — ראה BUG-131 לעיל — ע"י smoke ישיר שהמשתמש הריץ בעצמו מול הבסיס החי).
- **מקור:** דיווח production מפורש מהמשתמש: הרצת `_write_airtable_row()` פעמיים לאותו תאריך הפיקה **שתי** שורות (במקום create→patch); חזרה נוספת הפיקה **ארבע** שורות סה"כ (עם ערכי `11/22/3/36` ו-`44/55/6/105`, כל אחד כפול). כל קריאה נפלה ל-ענף ה-create — patch מעולם לא קרה.
- **שורש:** `at_get_by_field(table, "Date", date_str)` בנה פורמולת השוואת-טקסט `{Date}='YYYY-MM-DD'` מול שדה `Date` מסוג **DATE** (לא טקסט) ב-Airtable. השוואת טקסט מול שדה date-typed לעולם לא תואמת — ה-lookup תמיד החזיר "לא נמצא", כל קריאה נפלה ל-`airtable_create()`.
- **תוקן:** lookup עבר ל-`at_list_by_formula()` עם `DATETIME_FORMAT({Date}, 'YYYY-MM-DD')='<date>'`, `max_records=2`, עם 0/1/2+ handling מפורש (2+ = סירוב מוחלט + לוג שגיאת-שלמות-נתונים, לא ניחוש). `date.fromisoformat()` מאמת את הקלט לפני כל קריאה. לוגי הצלחה כוללים `branch=create|patch`, תאריך, `record_id`.
- **בדיקות:** `test_cost_watchdog_airtable_write.py` נכתב מחדש (30 assertions). Full sweep נקי.
- **Verified בפרודקשן:** 🟡 חלקי — עצם הבאג אומת ישירות בפרודקשן (ראיית המשתמש למעלה). ה**תיקון** לא אושר במפורש בסבב הזה עם פלט `✅ SMOKE PASSED` מוצג (ה-checklist דרש הרצת `tools/smoke_ai_usage_daily_upsert.py` מול הבסיס החי לפני מיזוג #437/#438) — אין ברשותי אישור מפורש שזה בוצע. אין לראות בכך ממצא של "עדיין שבור" — רק גבול-דיוק על מה שאומת במפורש מול מה שרק נדרש ע"י ה-checklist.
- **Merged:** ✅ `main` (PR #437, המשך תיקון ב-#438) — ראה `CHANGE_CONTROL_LOG.md` C164/C165.
- **סטטוס:** ✅ קוד תוקן ונבדק (unit-level), הבאג המקורי אומת ונסגר בפרודקשן — אימות-חוזר מפורש של ה-fix הספציפי (smoke PASSED) לא תועד בסבב הזה.

## BUG-133 — `test_bug104_tma_lead_event_bridge.py` פרץ את גבול ה-mock שלו וכתב 310 רשומות אמיתיות ל-Interaction Log הפרודקשן (43% מהטבלה כולה) — ✅ תוקן ומאומת

> **הערת מספור:** נרשם במקור כ"BUG-131" על branch נפרד לפני שנודע שמספר זה כבר נתפס (במקביל, session אחר) ע"י באג `AI_Usage_Daily` BOM שכבר מוזג ל-main. שונה ל-BUG-133 (הבא הפנוי אחרי BUG-132) בזמן rebase על `main` — אין קשר תוכני בין הבאגים, רק התנגשות מספור.

- **תאריך:** 21/07/2026. **חומרה: High** — לא כתיבה ל-Leads עצמו (שם ה-mock עבד נכון), אבל זיהום מתמשך וממשי של טבלת אודיט פרודקשן, אותה משפחת-באג בדיוק כמו BUG-128 (unit test חוצה את גבול ה-mock שלו לפרודקשן) — מקור/מנגנון שונה לגמרי, קובץ שונה.
- **מקור:** הבעלים בדק בעצמו את מסך ה-TMA (ראה גם הבדיקה הנפרדת של C84/TTL באותה שיחה) ושם לב לנפח חריג בטבלת Interaction Log ("איך נהיו 450 תיעודים היום?"). בדיקה ישירה מול Airtable החי (דרך Airtable MCP, לא הונחה) גילתה: 705 רשומות סה"כ בטבלה, **310 מתוכן (43%!)** מתייחסות ל-`"recLEAD001"` — מזהה שאפילו לא בפורמט Airtable תקין (10 תווים, לא 17) — פיזור על פני 07-16 עד 07-21 (2026), חלוקה מדויקת **155/155** בין `[TMA] lead_outcome` ל-`[TMA] lead_patch`.
- **Contract Chain (אומת ישירות בקוד, לא הונח):**
  1. `"recLEAD001"` הוא ה-fixture ID של `test_bug104_tma_lead_event_bridge.py` (וגם שני קבצי test נוספים של BUG-104 — נבדקו ונמצאו **תקינים**, לא קוראים ל-endpoints אמיתיים דרך Flask test client, ראו סעיף "לא נוגע" למטה).
  2. הקובץ הבעייתי, section 2 ("tma_api owner-immediate path"), קורא בפועל ל-`/api/leads/<id>` PATCH ול-`/api/leads/<id>/outcome` POST דרך Flask test client אמיתי, ומדמה (`tma_api._at_patch = _fake_at_patch`) את כתיבת ה-Leads בהצלחה.
  3. `set_lead_outcome()`/`patch_lead()` (`tma_api.py:1757`/`1805`) קוראים אז ל-`_audit(...)` → `_at_post(Tables.INTERACTION_LOG, ...)` → `_gw_create(...)`.
  4. `tma_api.py:34`: `from tools.airtable_gateway import airtable_create as _gw_create` — bind **חד-פעמי** בזמן import. הטסט מנסה למקק את זה עם `airtable_gateway.airtable_create = _counting_create` (שורה 238 בקובץ המקורי) — אבל זה רק דורס את ה-attribute על מודול `airtable_gateway`, **לא** את `tma_api._gw_create` שכבר bound לפונקציה האמיתית. טעות mocking קלאסית בפייתון ("מיקוק היעד הלא-נכון") — שונה מ-BUG-128 (שם קוד ברח מ-`with patch()` scope), אך אותה תוצאה: כל "success case" בקובץ ביצע **POST אמיתי, שקט, לפרודקשן** ל-Interaction Log.
  5. **אומת גם למה `core/lead_event_writer.py` (בקטע 1 של אותו קובץ) *כן* ממוקק נכון:** שם ה-import הוא `from tools.airtable_gateway import airtable_create` **בתוך** הפונקציה (import דחוי, נטען מחדש בכל קריאה) — מסתכל על ה-attribute הנוכחי של `airtable_gateway` בזמן קריאה, ולכן דריסת ה-attribute עובדת נכון שם. `tools/approval_actions.py::tma_write()` (קטע 3 של אותו קובץ) עושה אותו import דחוי — גם מבודד כראוי, לא נגוע.
  6. **ממצא משני, אותו קובץ, אותה סיבת-שורש:** GET `/api/leads/<id>` בונה "timeline" מ-Interaction Log דרך `tma_api._at_list()` (`tma_api.py:1582`) — פונקציה ישירה, אין gateway indirection. גם זו לא ממוקקת בקובץ הטסט — נצפה `_at_list(Interaction Log) error: 403 Forbidden` בהרצה בפועל (קריאת רשת אמיתית שנכשלה, לא כתיבה — read-only, `_at_list` מחזיר `[]` על כל שגיאה, אז אין השפעת-נתונים, רק "leak" של קריאת-רשת בלתי-מכוונת).
- **תוקן:** `test_bug104_tma_lead_event_bridge.py` — נוסף `tma_api._gw_create = _counting_create` (ישירות, לא דרך `airtable_gateway`) עם restore ב-`finally`, ו-`tma_api._at_list = lambda *a, **kw: []` לאותה סיבה (הממצא המשני). `_counting_create` עודכן לעקוב גם אחרי כתיבות ל-`Tables.INTERACTION_LOG` (`_interaction_log_writes`), עם 4 assertions חדשות שמוכיחות structurally שכתיבת האודיט נתפסת ע"י ה-mock ולא בורחת לרשת אמיתית (בדיוק אותו סוג הוכחה מבנית כמו `test_ci_no_airtable_secrets.py` ב-BUG-128).
- **בדיקות:** `test_bug104_tma_lead_event_bridge.py` — 50/50 (היה 46/46 לפני 4 ה-assertions החדשות), אין עוד `403 Forbidden`/קריאת-רשת בפלט ההרצה. Full `test_*.py` sweep (כל קובץ בריפו) + `smoke_tests.py` + `compileall -q .` — נקיים, ללא רגרסיה.
- **לא נוגע:** `test_bug104_leads_reasoning_projection.py`/`test_bug104_phase1_1_contract_hardening.py` (נבדקו ישירות — לא קוראים ל-Flask test client ל-write endpoints, משתמשים ב-`recLEAD001` רק כ-fixture dict סטטי, ללא סיכון). `tools/approval_actions.py::tma_write()` עצמו (import דחוי תקין, לא נגוע). שום קוד production — התיקון כולו בקובץ טסט אחד.
- **ניקוי הנתונים הקיימים:** 310 הרשומות המזויפות שכבר נכתבו ל-Interaction Log (`recLEAD001:*`) נמחקו ישירות מ-Airtable (לא ע"י קוד — פעולת ניקוי חד-פעמית, מאושרת מפורשות ע"י הבעלים). ראו לוג המחיקה למטה.
- **Merged:** ✅ כן — commit `d565cae`, PR #442. **תיקון-סטטוס (23/07/2026):** השורה הזו אמרה בטעות "טרם ממוזג" — אומת ישירות מול `git merge-base --is-ancestor` שהקומיט הוא ancestor של `main`. תיקון-תיעוד בלבד.
- **סטטוס:** ✅ Fixed — קוד + tests מאומתים מקומית (50/50 + full sweep נקי). Production verification (הבעלים בודק שהקובץ לא ממשיך לזהם) ממתין להרצה עתידית של ה-test sweep אחרי merge.

## BUG-134 — TTL הגנרי של `ActionContractRepository` (24h) עלול ליירט contract לפני שהלוגיקה הספציפית של C84 (reject + סנכרון Approvals projection) מספיקה לרוץ — 🔴 נרשם, לא תוקן

- **תאריך:** 21/07/2026.
- **מקור:** הבעלים ביקש לאמת את C84 (TMA Approvals TTL, ראה `CHANGE_CONTROL_LOG.md` C143) ע"י יצירת ActionContract-בדיקה נקי וחיכה 24 שעות. הביא לוג production אמיתי:
  ```
  [ActionContractRepository] get(1d255ed2-c837-414b-b4fa-e0fc4d6319aa) — pending contract expired (created_at=1784578007.9891315)
  ```
  בהתחלה נראה כאילו זה מאמת את C84 (24h TTL אכן פג) — אבל trace מדויק בקוד גילה שזה **מנגנון אחר**, לא C84 עצמו.
- **Contract Chain (אומת ישירות בקוד):**
  1. `core/action_contract_repository.py:84`: `CONTRACT_PENDING_TTL_SECONDS = 24 * 3600` — TTL **גנרי**, שונה ומוקדם יותר מ-`tma_api.py`'s `_TMA_APPROVAL_TTL_SECONDS` הספציפי ל-C84 (גם 24h, אך לוגיקה שונה לגמרי). `ActionContractRepository.get()` (שורות 300-321): אם `contract.status=="pending"` וגם `_is_expired(contract)` — **מחזיר `None`** (מתנהג כ"לא נמצא", לוג ה-`"pending contract expired"` שהמשתמש הביא).
  2. `tma_api.py`'s `_claim_and_execute_approval()` קורא ל-`_gw.find_contract(contract_id)` → `ExecutionLedger.find_by_id()` (`core/action_gateway.py:432`) → cache hit מחזיר מייד מה-RAM (**לא בודק תפוגה בכלל**), cache miss נופל ל-`repository.get()` (המנגנון הגנרי שלעיל). הלוג שהמשתמש הביא **מוכיח cache miss קרה** (אחרת השורה הזו לא הייתה נרשמת כלל) — כנראה מ-restart/redeploy כלשהו בחלון 24 השעות.
  3. כשה-repository מחזיר `None`, `_claim_and_execute_approval()` (`tma_api.py:2753-2759`) נכנס לענף **`404 "canonical ActionContract not found — orphaned projection row"`** — **לא** לענף הספציפי של C84 (`tma_api.py:2775-2829`) שעושה `_gw.reject(contract_id, rejected_by="ttl_expired")` + `_sync_approval_projection_status()` + `410 "approval expired — submit a new request"`.
  4. **המשמעות:** כש-TTL הגנרי מיירט ראשון (cache miss + פג-תוקף), לוגיקת ה-reject/sync הספציפית של C84 **אף פעם לא רצה** — ה-Approvals row ב-Airtable עלול להישאר `status=pending` שקרי לנצח (אף אחד לא כתב אליו `rejected`), גם כשה-contract עצמו "נעלם" מבחינת ה-backend. זה בדיוק ההפך ממה ש-C84 תוכנן לפתור ("TMA UI לא ימשיך להראות 'ממתין' שקרי").
- **לא אומת (עדיין):** האם ה-Approvals record הספציפי בדוגמה הזו אכן נשאר `pending` ב-Airtable/TMA UI בפועל — המשתמש עדיין לא בדק/דיווח את זה במפורש (רק את הלוג). לא לראות בזה "מאומת ב-100%", רק Contract Chain מלא שמסביר למה זה **סביר**.
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain בלבד, לפי בקשת המשתמש לרשום בלבד כרגע.
- **כיוון תיקון אפשרי (לא הוחלט, לא מומש כאן):** ה-404 "orphaned projection row" branch יכול לבדוק אם ה-Approvals projection type-appropriate ולנסות reject+sync גם שם (לא רק בענף ה-410 הספציפי) — או: לתאם בין שני ה-TTLs (24h זהים במקרה, אך מנגנונים נפרדים) כך שהגנרי לעולם לא יקדים את הספציפי. דורש בדיקה זהירה מול BUG-127A (אותו סוג conflict/cache-miss territory).
- **סטטוס:** 🔴 נרשם, Contract Chain אומת ישירות בקוד — **לא תוקן**. ממתין להחלטת המשתמש על עדיפות/כיוון-תיקון.
- **עדכון (24/07/2026) — סוגר את ה"לא אומת" למעלה, עם ראיה ישירה מ-Airtable:** נשלף ישירות מטבלת `Approvals` (Airtable MCP, בסיס `app4bcgoX7t0HUVnm`) — רשומה `recyoMWRE2Lv8Fzvk` (`action_contract_id=1d255ed2-c837-414b-b4fa-e0fc4d6319aa`, בדיוק ה-contract מהדוגמה המקורית למעלה) **עדיין `projected_lifecycle_status=pending`/`ממתין`, נוצרה 20/07/2026** — 4 ימים תקועה, בדיוק כפי שהתיאוריה חזתה. שתי רשומות `Approvals` נוספות באותה טבלה (סה"כ 4 רשומות בטבלה כולה) גם הן `pending` תקוע: `recnFF6VCBVcR8apL` (contract `92291037-0060-47fe-bf3f-67ca4d7ff87d`, נוצרה 19/07 — 5 ימים) ו-`rec9VBFoLUoEX71bD` (נוצרה 09/07 — שבועיים). כל השלוש חסרות `action_contract_id` תואם ב-`ActionContracts` הפעילה (backend), ומאומתות בנפרד כ-404/409 בלוגי production אמיתיים מאותו יום (09:42-09:46 UTC, ראה `RP5_LOG_OBSERVATION_23JUL2026.md` §6 להפניה המלאה) כשה-TMA ניסה לפעול עליהן: `POST /api/approvals/recyoMWRE2Lv8Fzvk` → 404, `POST /api/approvals/recnFF6VCBVcR8apL` → 409, `POST /api/approvals/rec9VBFoLUoEX71bD` → 409. **מסקנה: הבאג לא רק "סביר" — הוא מאומת עם ראיה ישירה, תקוע, ממושך (4-14 ימים), ולא מטופל.**

## BUG-135 — `core/ingress_classifier.py`: פקודות מחיקה ("תמחק איש קשר <phone>", אין שם אמיתי בטקסט) הפיקו שם ליד מזויף — ✅ תוקן

- **תאריך:** 22/07/2026.
- **מקור:** דווח ע"י הבעלים כחוסם בדיקות RP5, לצד BUG-129 (ציטוט-עצמי — ראה שם, תוקן באותו PR, נרשם בנפרד). `"תמחק איש קשר 0536272637"` (וריאציות `מחק`/`הסר`) — אין שם אמיתי בטקסט כלל, אך זוהתה כליד בשם *תמחק איש קשר* (0536272637).
- **Root Cause (אומת ישירות בקוד):** למודול הזה **אין** טיפול ייעודי לכוונת-מחיקה (ה-intent היחיד שקיים בכלל ל-delete הוא `Intent.DELETE_TASK` ב-`core/router/intent_router.py`, שום דבר ל-contacts/leads) — כך שטקסט מחיקה נופל לאותה חילוץ שם+טלפון גנרית כמו יצירה/עדכון. "תמחק"/"מחק"/"הסר" לא היו stop-words כלל ב-`_NAME_STOP`, אז הפועל שרד כחלק מ"השם" שנבחר ע"י הסגמנטציה.
- **תוקן:** `_NAME_STOP` הורחב בקבוצת פעלי-המחיקה "תמחק"/"מחק"/"הסר" (מראה קבוצת פעלי ה-DELETE_TASK הקיימת ב-router). זה לבדו עדיין השאיר "איש קשר" (השורד ≥4 תווים, ללא הפועל) כמועמד שקרי — "איש"/"קשר" **לא** הפכו ל-stop-words גורפים בכוונה (המשתמש אישר לשמר את ההתנהגות הקיימת: `"תוסיף איש קשר בדיקה טלפון X"` חייבת להמשיך לחלץ `"איש קשר בדיקה"` verbatim, ראה AskUserQuestion בסבב הזה). נוסף `_GENERIC_NAME_PHRASES = frozenset({"איש קשר"})` — reject רק על ה-phrase המדויק כשהוא כל מה ששרד, לא כשמילה נוספת (כמו "בדיקה") שורדת לצידו.
- **Out of scope:** התיקון הזה משנה **רק** את חילוץ-השם. הוא **לא** משנה create-vs-update routing ולא resolution של רשומה קיימת — BUG-130 (עדכון-שדה לליד קיים מנותב כיצירת ליד חדש) **נשאר פתוח, לא נוגע**. גם אין כאן intent/handler אמיתי ל-"מחיקת איש קשר" — הפקודה עדיין לא תבוצע בפועל בשום מסלול, רק לא תיצור עוד candidate-שם שקרי.
- **בדיקות:** `test_bug135_command_verb_name_stop.py` (10 assertions, T3/T4/T6 רלוונטיים ל-BUG-135 הזה, T1/T2 ל-BUG-129, T5/T7/T8 regression). Full sweep (`test_*.py` — 166 קבצים, `smoke_tests.py`, `test_integration.py`, `compileall -q .`) — נקי, ללא רגרסיה (כולל `test_bug099b1_no_name_validation.py`/`test_bug099a/b/c`, `test_bug096/098/101/111/116` — כל טסטי ה-ingress_classifier הקיימים). שני קבצים כושלים ב-full sweep (`test_bug_canonical_tool_wiring.py`, `test_pa01_phantom_approval_enforcement.py`) אומתו כקיימים גם על `main` לפני התיקון (`git stash` + הרצה) — לא רגרסיה.
- **Verified בפרודקשן:** 🟡 לא עדיין — תוקן ונבדק מקומית (unit-level, full sweep). אימות מול production/RP5 בפועל ממתין להרצת הבעלים אחרי merge+deploy.
- **Merged:** ✅ כן — commit `9285106`, PR #444 (`3f69b1d`). **תיקון-סטטוס (23/07/2026):** השורה הזו אמרה בטעות "טרם ממוזג" — אומת ישירות מול `git merge-base --is-ancestor` שהקומיט הוא ancestor של `main`. תיקון-תיעוד בלבד.
- **סטטוס:** ✅ קוד תוקן ונבדק מקומית. Production verification ממתין.

## BUG-136 — "בצע שוב `<קוד>`" נופל ל-Agent (ומקבל תשובה מומצאת) כשהמשתמש שולח בדיוק את הפורמט שהבוט עצמו הציע, עטוף ב-markdown bold — 🔴 נרשם, לא תוקן

- **תאריך:** 23/07/2026.
- **מקור:** דגימת staging חיה. אחרי "⚠️ פעולה זו כבר בוצעה לאחרונה... שלח: *בצע שוב 645324*", המשתמש שלח קודם `בצע שוב 655324` (טעות-הקלדה, ללא markdown) וקיבל כראוי `"קוד שגוי. נסה שוב..."`. בניסיון הבא שלח בדיוק את הקוד הנכון, עטוף כפי שהבוט עצמו שלח אותו — `*בצע שוב 645324*` — וקיבל: `"❌ לא מצאתי פעולה עם מזהה \"645324\". אני לא שומר מזהים של פעולות קודמות בשיחה."` — טענה כוזבת (המערכת **כן** שומרת state כזה, ראה `route_override_word()` למטה) ולא תגובת-מערכת אמיתית של מנגנון ה-override בכלל.
- **Contract Chain (אומת ישירות בקוד):**
  1. `core/action_gateway.py:1114`: `f"אם אתה בטוח שזו חזרה מכוונת — שלח: *בצע שוב {code}*"` — הבוט **עצמו** מנחה את המשתמש לשלוח את הקוד עטוף ב-`*...*` (Telegram bold markdown).
  2. `app.py:2757`: `_override_match = re.match(r"^בצע\s+שוב\s+(\d{4,8})$", _stripped)` — regex **מעוגן** (`^...$`) שדורש שההודעה השלמה תהיה בדיוק "בצע שוב <ספרות>", ללא שום תו נוסף. `_stripped = user_text.strip()` (שורה 2753) מסיר רק whitespace — **לא** מסיר `*`/markdown אחר.
  3. תוצאה: הודעה `"*בצע שוב 645324*"` (בדיוק מה שהבוט הציע והמשתמש העתיק/שלח) **לא תואמת** את ה-regex בגלל ה-`*` המובילים/סוגרים — היירוט ב-2.55 לא מופעל בכלל, ואין נפילה-חלופית ל-`route_override_word()` בשום מקום אחר בקובץ.
  4. אומת ש-`route_override_word()` (`core/action_gateway.py:1712-1747`) **לעולם לא** מפיק את הטקסט שנצפה — ארבע תגובות האפשריות היחידות שלה הן: `"אין override פתוח עבורך..."` / `"קוד האתגר פג..."` / `"קוד שגוי. נסה שוב..."` / `"✅ override אושר..."`. גם `grep` גורף על "לא מצאתי פעולה עם מזהה"/"אני לא שומר מזהים" בכל הריפו מחזיר **0 תוצאות** — המשפט הזה אינו string קבוע בשום מקום בקוד. המסקנה: ההודעה שנצפתה הופקה ע"י ה-Agent (Claude) עצמו כטקסט-חופשי, אחרי שההודעה "נפלה" מעבר לכל המיירטים הדטרמיניסטיים (2.55 ואילך) ישירות ל-`run_agent()` — ה-Agent, שאין לו שום כלי/הקשר למושג "קוד override", אלתר הסבר סביר-להישמע אך שגוי לחלוטין ("אני לא שומר מזהים") — למעשה hallucination על state שהמערכת דווקא כן שומרת (ה-override עצמו, `gw._overrides`), רק שההודעה הספציפית הזו מעולם לא הגיעה לשם.
  5. `test_action_gateway.py`'s DoD15/§17 (שורות 160-208) בודקות את `route_override_word()`/regex-extraction ישירות על מחרוזת נקייה (`re.search(r"בצע שוב (\d+)", ...)` על הטקסט שה-gateway עצמו הפיק) — **אין** טסט קיים ששולח את הטקסט המדויק שמשתמש-אמיתי היה שולח (כולל ה-`*` שהבוט עצמו כלל בהצעה), כך שהפער הזה לא נתפס קודם.
- **חומרה:** UX/אמינות — לא security. אבל: (א) המשתמש עוקב **בדיוק** אחרי ההנחיה של הבוט עצמו ונענה בכישלון; (ב) התשובה שמתקבלת (מהסוכן) היא הצהרה שגויה על יכולות המערכת ("אני לא שומר מזהים") — בדיוק סוג ה-claim-בלי-evidence שה-anti_hallucination/A32 gate אמור לתפוס בפעולות-כתיבה, אך כאן זו תשובת-מידע חופשית שלא עוברת דרך אותו gate כלל.
- **כיווני תיקון אפשריים (לא הוחלט, לא מומש כאן):** (1) לנקות markdown-wrapping (`*`/`_`/backticks) מ-`_stripped` לפני ה-`re.match` ב-app.py:2757, באופן סימטרי למה שכבר קורה במקומות אחרים בקובץ ל-bare-digit disambiguation; (2) להרפות את העיגון ל-`re.search` במקום `re.match(^...$)` כדי לתפוס גם טקסט עטוף; (3) שני אלה צריכים לעבור דרך שער ה-Cross-Layer Authority Contract (נוגע ל-F52/Approval layer) לפני מימוש — לא מומש בסבב הזה.
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain בלבד.
- **סטטוס:** 🔴 נרשם, Contract Chain אומת ישירות בקוד — **לא תוקן**. ממתין להחלטת המשתמש על עדיפות/כיוון-תיקון.

## BUG-137 — הודעת "✅ בוצע: עדכון ליד" מרכיבה domain פנימי (למשל "finance") לתוך המחרוזת בלי שום תווית, לצד הטלפון — נראה כמו token מבלבל/דולף — 🔴 נרשם, לא תוקן

- **תאריך:** 23/07/2026.
- **מקור:** דגימת staging חיה. `"✅ בוצע: עדכון ליד: 0500000000, finance | מזהה: recoeWLkqGLxDxnMs"` — "finance" מופיע כפריט שני ברשימה מופרדת-פסיקים, בלי הקשר/תווית, ונראה כמו ערך שדה-פנימי שדלף לטקסט-משתמש (ראו גם ההערה תחת BUG-130 למעלה, אותו ציטוט בדיוק).
- **Contract Chain (אומת ישירות בקוד):** `core/action_gateway.py::_describe_contract_for_reconfirmation()` (שורות 708-732), המשמשת גם את הודעת "✅ בוצע: {label}" (לפי ה-docstring של הפונקציה עצמה, שורות 709-717 — נסמכת ע"י `test_stage_b_full_suite.py`'s DoD20): עבור `tool_name in ("airtable_add", "airtable_update")` על טבלת ה-Leads, בונה `parts = [Name, Phone, Domain]` מתוך `payload["fields"]`, מסננת ריקים, ומחזירה `f"{verb}: {', '.join(parts)}"` — **ללא שום תווית לכל שדה**. כשה-update payload מכיל רק שדה טלפון (המקרה השכיח בתרחיש "עדכן טלפון ל-X" — Name לרוב לא נשלח מחדש), ה-Domain (אם קיים ב-payload) נשאר כפריט השני היחיד ברשימה, ומוצג צמוד לטלפון בלי שום סימון שזהו תג-דומיין ולא חלק מזהות האיש.
- **חומרה:** קריאוּת/UX — לא הודלף מזהה טכני-פנימי אמיתי (record_id/tool_name, כמו BUG-118), אבל "finance" נקרא כמו token שרירותי/באג למשתמש שלא יודע שזה שדה domain, ופוגע באמינות ("✅ בוצע") כשההודעה עצמה נראית שבורה.
- **לא אומת:** האם ה-Domain שהופיע בפועל ("finance") הגיע מהרשומה שנמצאה, מ-`identity.domain_id`, או ממקור אחר — תלוי בנתיב ה-caller שבונה את ה-payload עבור `airtable_update`, לא נבדק כאן. ראו גם ההערה תחת BUG-130 על סיכון-collision אפשרי (טרם אושר) שאותה תופעה עשויה להיות גם סימפטום שלו.
- **כיוון תיקון אפשרי (לא הוחלט, לא מומש כאן):** להוסיף תוויות לכל חלק (`f"טלפון: {phone}"`, `f"תחום: {domain}"` וכו') במקום join גולמי, או להשמיט Domain מהתצוגה-למשתמש לגמרי (הוא רלוונטי-פנימי, לא זהות-מזהה). דורש בדיקה זהירה מול DoD20 הקיים (`test_stage_b_full_suite.py`) שכבר תלוי בפורמט הנוכחי, ומול שער ה-Cross-Layer Authority Contract (F52/Approval layer).
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain בלבד.
- **סטטוס:** 🔴 נרשם, Contract Chain אומת ישירות בקוד — **לא תוקן**. ממתין להחלטת המשתמש על עדיפות/כיוון-תיקון.
- **עדכון (24/07/2026) — הישנות אמיתית נוספת + רמז חלקי למקור ה-Domain (סעיף "לא אומת" למעלה):** נשלף ישירות מ-`ActionContracts` (Airtable MCP) — contract נוסף על **אותה רשומה בדיוק** (`recoeWLkqGLxDxnMs`), נוצר 23/07/2026 19:20:35 UTC: `normalized_payload = {"fields": {"phone": "0500000000", "summary": "תעדכן את הליד דני לוי למספר 0500000000", "domain": "finance"}, ...}`. הודעת המשתמש המקורית לא מזכירה domain בכלל — כלומר `"domain": "finance"` הוזרק ל-payload באופן עצמאי, לא מטקסט המשתמש. הרשומה הקיימת ב-`Leads` (`recoeWLkqGLxDxnMs`) עצמה מחזיקה `domain="finance"` באופן קבוע (שדה אמיתי על הרשומה, נבדק ישירות) — **רמז חזק (לא הוכחה מלאה) שמקור ה-Domain הוא ה-domain הקיים של הרשומה שנמצאה ב-match, לא `identity.domain_id`** — נשאר לאמת מול הקוד עצמו (path שבונה את ה-`airtable_update` payload) לפני קביעה סופית.

## BUG-138 — כפתור אישור טלגרם (inline keyboard) לא נעלם אחרי לחיצה/אישור — `edit_message_text()` בכל 6 נקודות-הסיום ב-`_handle_approval_callback_impl()` לא מנקה `reply_markup` — 🔴 נרשם, לא תוקן (השערה — טרם אומת מול התנהגות Telegram API בפועל)

- **תאריך:** 23/07/2026.
- **מקור:** דיווח הבעלים על בקשת אישור חיה ("➕ הוסף ל-Tasks: הכנת מודעה ופרסום בפייסבוק ובוואטסאפ", TTL 10 דק') — "הכפתור לא נסגר גם אחרי האישור".
- **Contract Chain (אומת בקוד — הקריאות עצמן, לא ה-side-effect ב-Telegram):** `grep` גורף על `bot.edit_message_text(` בתוך `app.py` מראה **שש** נקודות-קריאה בתוך/סביב `_handle_approval_callback_impl()`/`_notify_stale_or_resolved_callback()`/`_reject_stale_telegram_approval()` — שורות 1851, 1930, 1979, 2279, 2397, 2435 (מכסות: stale/resolved, TTL-expired, missing/expired-callback, אושר-אך-נכשל-בביצוע, **אושר ובוצע בהצלחה (המקרה שדווח)**, ונדחה) — **אף אחת מהן לא מעבירה `reply_markup=None`** (או ריק) ל-`edit_message_text()`. בקובץ הזה עצמו יש גם קריאות נפרדות ל-`bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)` (שורות 1858, 1937, 1985) — אך כל אחת מהן נמצאת **רק בתוך ה-`except` block** של קריאת ה-`edit_message_text` המקבילה, כלומר מנקה את המקלדת **רק אם `edit_message_text` נכשל/זרק חריגה** — לא כ-fallback-תמיד. במקרה השכיח (הקריאה מצליחה, כמו בתרחיש שדווח) אף אחד מהם לא נקרא בכלל, וה-inline keyboard המקורי (✅/❌) נשאר מצורף להודעה שהטקסט שלה כבר עודכן ל-"✅ אושר ובוצע".
- **טרם אומת:** האם `editMessageText` ב-Telegram Bot API (וב-`telebot`/pyTelegramBotAPI שהמודול הזה עוטף) שומר בפועל על ה-reply_markup הקיים כשהפרמטר לא מועבר כלל, לעומת מנקה אותו אוטומטית. אין credentials/גישת-רשת חיה בסביבה הזו לאמת מול Telegram בפועל — ההשערה מבוססת על התנהגות ידועה/מתועדת של ה-API הזה (edit-text אינו מוחק reply_markup קיים אלא אם התבקש מפורשות), אבל **לא אומתה כאן ישירות**. אם ההשערה נכונה — הבאג הוא סיסטמי לכל שש הנקודות, לא רק ל"אושר ובוצע"; אם היא שגויה — יש לחפש הסבר אחר (למשל race עם `answer_callback_query`, cache צד-לקוח של Telegram, או handler כפול).
- **חומרה:** UX — לא security. משתמש שרואה כפתור פעיל אחרי אישור עלול ללחוץ שוב; מסלול "כבר בוצעה"/duplicate-guard (`_eac`/BUG-DUPLICATE) כבר קיים ואמור למנוע ביצוע-כפול בפועל, כך שהסיכון כאן הוא בלבול/אי-אמון ב-UI, לא כפל-כתיבה אמיתי (טרם אומת גם זה).
- **כיוון תיקון אפשרי (לא הוחלט, לא מומש כאן):** להעביר `reply_markup=None` (או `types.InlineKeyboardMarkup()` ריק, לפי מה ש-telebot דורש בפועל) בכל שש קריאות ה-`edit_message_text` ב-`_handle_approval_callback_impl`/`_notify_stale_or_resolved_callback`/`_reject_stale_telegram_approval`, במקום להסתמך על `except`-fallback שרץ רק בכישלון. נוגע ב-Durable Atomic Approval layer (`app.py`'s handler הישיר, גם אם לא ב-`core/action_gateway.py` עצמו) — לבדוק מול שער ה-Cross-Layer Authority Contract לפני מימוש.
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain חלקי (הקריאות אומתו, ה-side-effect בפועל לא) בלבד.
- **סטטוס:** 🔴 נרשם, השערה מבוססת-קוד — **לא אומת מול Telegram/לוגים בפועל, לא תוקן**. דורש בדיקת לוגים/רפרודוקציה (ראו handoff בשיחה) לפני קביעת root cause סופי.
- **עדכון (24/07/2026) — זוהה ה-batch המדויק שבו התרחש הדיווח המקורי, מ-Airtable אמיתי:** `ActionContracts` (Airtable MCP) מראה 4 contracts על טבלת `Tasks`, כולם `airtable_add`, נוצרו 23/07/2026 13:17:07–13:19:20 UTC, כולם `status=completed`: "לקבוע נסיעה לצפון...", "להכין 3 מודעות...", "לפנות לתיווך...", ו-`recE0N2reMAt6TVe7`: **"להכין מודעה ולפרסם בפייסבוק ובוואטסאפ"** — ציטוט מדויק של הדוגמה בדיווח המקורי למעלה ("➕ הוסף ל-Tasks: הכנת מודעה ופרסום בפייסבוק ובוואטסאפ"). זהו אותו batch-approval flow בן-4-המשימות שמתועד גם כ-Findings #8/#9 (scenarios 26/27) ב-`docs/architecture/action-gateway/STAGING_23JUL_TTL_DISAMBIGUATION_AUDIT.md` — כלומר תלונת BUG-138 (הכפתור לא נעלם) קרתה **בתוך** אותו session/batch ש-#8/#9 מתעדים (Tier-2 preview שורד + הודעות בסדר הפוך). לא בהכרח אותו root cause — לא אומת קשר סיבתי — אבל אותו session בדיוק, זמנית וממצא-תוכן. עדיין לא אומת מול Telegram API עצמו (הפער המקורי נשאר פתוח).

## BUG-139 — RP5 Evidence Finalizer: `response_claim=failure`/`mixed` כשאין שום tool call בתור כלל (`evidence_status=no_evidence`) — 🔴 נרשם, לא תוקן (מאומת מלוגי production/staging אמיתיים, root cause בקוד עדיין לא אותר)

- **תאריך:** נתוני לוגים מ-23/07/2026, נרשם 24/07/2026.
- **מקור:** ניתוח לוגי Render בפועל (read-only export, `scripts/render_log_export.py`) מול שירות staging `my-bot-approval-staging` (`srv-d99uq63eo5us73967cj0`), marker `[EvidenceFinalizerShadow]`, חלון 24 שעות (`2026-07-22T20:54Z → 2026-07-23T20:54Z`). פירוט מלא + כל ה-timestamps: `RP5_LOG_OBSERVATION_23JUL2026.md` §1-2.
- **ממצא מאומת (מלוגים אמיתיים, לא היפותזה):** מתוך 15 דגימות `[EvidenceFinalizerShadow]` אמיתיות שנאספו באותו יום, 7 (47%) הן `mismatch=true` (`code=status_claim_mismatch`, תפוקה ישירה של `core/turn_evidence.py`'s comparison logic עצמו — לא מוסק). מתוכן **5 חוזרות על אותה תבנית מדויקת: `evidence_status=no_evidence` (אפס קריאות tool בתור כלל) יחד עם `response_claim=failure`** — טקסט-התשובה של הבוט טוען שמשהו נכשל, כשה-evidence layer לא מצא שום tool call בתור בכלל. נצפה בשני sessions נפרדים באותו יום: `13:10:39Z`, `13:10:55Z`, `13:15:25Z` (cluster אחד), ו-`19:21:38Z`, `19:22:06Z` (cluster שני, ~6 שעות מאוחר יותר). דגימה שישית קרובה (`13:16:06Z`) היא אותה תבנית עם `response_claim=mixed` במקום `failure`.
- **נשלל כארטיפקט של RP5 fault-injection (אומת ישירות, לא הונח):** marker `[RP5FaultInjection]` (הלוג הייעודי ש-`core/rp5_fault_injection.py` כותב בכל פעם שהוא בפועל מיירט tool call, ענף `claude/rp5-staging-fault-injection-v4akit`) הוחזר עם **0 תוצאות** באותו חלון-זמן/שירות. גם מבנית זה לא יכול להיות ההסבר: ה-helper מיירט קריאת-tool קיימת בלבד ולכן לא יכול לגרום ל-`evidence_status=no_evidence` (שמשמעותו אפס קריאות tool קרו בתור בכלל — אין מה ליירט).
- **טרם אומת (root cause בקוד):** מהיכן מגיע `response_claim=failure`/`mixed` כשאין שום `tool_use` בתור — נדרש grep/read על `core/turn_evidence.py`'s classification logic (גזירת `response_claim` מטקסט-התשובה הסופי של המודל) כדי לקבוע אם זו טעות זיהוי-claim מטקסט חופשי (למשל מילת-מפתח כמו "לא הצלחתי"/"תקלה" בתשובה שאינה קשורה לביצוע tool בפועל — למשל בקשה לא ברורה מהמשתמש), התנהגות לגיטימית שפשוט לא מסווגת נכון (דיווח-אי-הבנה מתפרש כ-`failure` במקום כקטגוריה נפרדת), או משהו אחר. לא בוצעה קריאת קוד ל-`core/turn_evidence.py` בסבב הזה מעבר לאישור שהמנגנון עצמו קיים ותקין (ראו `RP5_PREFLIGHT_BLOCKER.md`); טקסט-התשובה בפועל של 5 הדגימות לא נשמר ב-log line (רק metadata/counts), כך שאימות נוסף עשוי לדרוש גישה ל-raw conversation אם עדיין נגישה.
- **חומרה:** תלוי root cause. אם מדובר בטעות סיווג אמיתית (המודל "מדווח כישלון" כשלא נוסה שום דבר) — UX חמור: משתמש עלול לחשוב שפעולה נכשלה כשלמעשה שום דבר לא נוסה. אם מדובר בהתנהגות לגיטימית שפשוט לא מסווגת נכון (למשל "לא הבנתי" מתפרש כ-`failure`) — עדיין באג בקטגוריזציה של RP5, אבל פחות מטעה בפועל למשתמש עצמו (הטקסט שהמשתמש רואה עדיין נכון; רק ה-shadow classification שגוי, ו-shadow לא משפיע על `final_reply` כרגע ממילא).
- **היקף:** לא נגעתי בקוד. ממצא מבוסס-לוגים בלבד.
- **סטטוס:** 🔴 נרשם, מאומת מלוגי production/staging אמיתיים (לא היפותזה) — **לא תוקן, root cause בקוד עדיין לא אותר**. דורש קריאת `core/turn_evidence.py`'s `response_claim` derivation logic + השוואה לטקסט-התשובה בפועל של הדגימות שנמצאו.

## BUG-140 — בקשה מפורשת ל"ליד חדש" (שם+טלפון שונים) מיוצרת כ-`airtable_update` נגד ליד קיים ולא-קשור, ככל הנראה עקב collision-לפי-טלפון — 🔴 נרשם, לא תוקן (מאומת ישירות מ-Airtable, contract עדיין `pending`)

- **תאריך:** נתוני 23/07/2026, נרשם 24/07/2026.
- **מקור:** ניתוח משולב לוגים+Airtable (Airtable MCP, בסיס `app4bcgoX7t0HUVnm`, טבלת `ActionContracts`) על אותו session שמתועד ב-`RP5_LOG_OBSERVATION_23JUL2026.md`/`docs/architecture/turn-coordinator/LOG_OBSERVATION_23JUL2026.md`.
- **ממצא מאומת (מ-Airtable ישירות, לא היפותזה):** contract `0e8a155c-9a6c-4c8e-acc3-b7ff448df752` (נוצר 23/07/2026 19:26:06 UTC, `tool_name=airtable_update`, `status=pending` — **עדיין ממתין נכון לרגע האיסוף**) — payload: `{"phone": "0521234567", "summary": "רגע, תוסיף גם ליד חדש בשם דנה כהן 0521234567"}`, `record_id: recLwJhPNh4EDbw56`. הודעת המשתמש מבקשת במפורש **הוספת ליד חדש** בשם "דנה כהן" — אך ה-contract שנוצר הוא `airtable_update` (לא `airtable_add`) נגד רשומה קיימת. נשלפה הרשומה `recLwJhPNh4EDbw56` ישירות: `Name="ישראל כהן"`, `phone="0521234567"`, נוצרה 2026-07-10, `summary="צור ליד: ישראל כהן, טלפון 0521234567, מעוניין בדירת 4 חדרים"` — **אדם אחר לגמרי, ליד לא-קשור** (דירת 4 חדרים, לא קשור לכל מה שדנה כהן ביקשה), ששיתף אותו מספר טלפון בדיוק.
- **השערת root cause (לא אומתה בקוד עדיין):** ככל הנראה סיכון-collision-לפי-טלפון-בלבד שכבר תועד כלא-מאושר תחת BUG-130 ("סיכון collision-לפי-טלפון-בלבד (רשומה לא-קשורה עם domain שונה) נצפה גם הוא, לא אומת ישירות") — עכשיו יש לו מופע קונקרטי: dedup/match-לוגיקה שמזהה ליד קיים לפי טלפון בלבד (בלי לבדוק שם) הפכה "הוסף ליד חדש" ל-"עדכן ליד קיים", נגד רשומה של אדם שונה לגמרי.
- **חומרה:** גבוה יותר מ-BUG-130's המקרה הרגיל — לא רק ניתוב שגוי, אלא **סיכון לדריסת נתונים אמיתיים** של ליד לא-קשור (ישראל כהן, דירת 4 חדרים) אם ה-contract הזה ייאושר. ה-contract עדיין `pending` נכון לרגע כתיבת הרשומה הזו — **טרם אושר, טרם גרם נזק בפועל**.
- **לא אומת:** קוד ה-matching/dedup המדויק (`contact_resolver.py`? `lead_candidate_handler.py`?) שהוביל להחלטה הזו — לא נקרא בסבב הזה, רק תוצאת ה-Airtable data עצמה.
- **היקף:** לא נגעתי בקוד, לא באישרתי/דחיתי את ה-contract. ממצא מבוסס-Airtable בלבד.
- **סטטוס:** 🔴 נרשם, מאומת ישירות מ-Airtable — **contract עדיין pending, לא אושר, לא תוקן**. מומלץ: הבעלים ישקול לדחות את ה-contract הזה ידנית (למנוע דריסה בטעות) לפני שממשיכים לחקור root cause.

---

## BUG-141 (AG-01) — שאלת pending-queue טבעית עם "?" עוקפת את `describe_pending_queue()` הדטרמיניסטי ונופלת ל-Agent — ✅ VERIFIED IN PROD + STAGING

- **תאריך:** 24/07/2026.
- **מקור:** בדיקת staging יזומה (AG-01). הודעת משתמש: `"מה ממתין כרגע לאישור?"`.
- **Expected:** ניתוב דטרמיניסטי ל-`ActionGateway.describe_pending_queue()`, תשובה מבוססת `ActionContracts` בלבד.
- **Actual:** ההודעה נפלה ל-Agent, שביצע `airtable_get` על `Tasks`/`Deals`/`Payments`, קיבל `422` על חלק מהקריאות (Deals/Payments), ו-A32 (`sanitize_agent_response`) החליף את התשובה הסופית ב-`"לא הצלחתי לבצע את הפעולה. נסה שוב או נסח אחרת."`. `EvidenceFinalizerShadow` תיעד evidence מעורב: 3 קריאות מאומתות + 2 כשלונות.
- **Contract Chain (אומת ישירות, לא הונח):**
  1. `_PENDING_QUERY_RE` (`app.py:194-198`) **כן** תואם את הטקסט — אומת ישירות: alt 3 (`(?:מה|אילו|איזה|רשימת).{0,15}(?:ממתי\w*|מחכ\w*)`) תואם "מה"…"ממתין", ו-alt 1 תואם באופן עצמאי גם כן. **לא בעיית regex.**
  2. Deploy: אומת ישירות מול Render API (`/v1/services/srv-d99uq63eo5us73967cj0/deploys`) — ה-deploy החי כרגע (`dep-d9h0krnlk1mc738qasu0`, commit `40116da9`) **מכיל** את `_PENDING_QUERY_RE`/`describe_pending_queue()` (אומת עם `git show 40116da9:app.py`, שורות 199/3038-3052 בקומיט הזה; `git merge-base --is-ancestor eab7ba5 40116da9` → כן). **לא בעיית deploy.**
  3. **שורש אמיתי — branch-ordering ב-`app.py`:** בתוך `if pending_entry is None:` (`app.py:2752`) קיימת שרשרת `if/elif/elif/elif` יחידה: `if "?" in _stripped:` (`app.py:2803`) → `elif _lower in _CONFIRM_WORDS:` (`2824`) → `elif _lower in _CANCEL_WORDS:` (`2927`) → `elif _PENDING_QUERY_RE.search(_stripped):` (`2957`). מכיוון שהטקסט מכיל `"?"`, ה-branch הראשון (`2803`) תמיד תופס אותו קודם, ו-`_PENDING_QUERY_RE` **לעולם לא נבדק** — ללא תלות אם היה מתאים. בתוך ה-branch של `"?"`, הבדיקה היחידה (`_STATUS_QUERY_PATTERNS`, `app.py:2807-2811`) מכסה רק פעלי-השלמה בעבר (`נוספה`/`בוצע`/`הצליח`/`נשלח` וכו') — "ממתין" (הווה) לא ברשימה, ה-`any(...)` מחזיר `False`, ו-`pass` (`2823`) נופל ל-Agent.
- **Test gap מאומת:** `test_staging_23jul_findings.py:233-247` (הבדיקה שליוותה את הפיצ'ר) בודקת רק `app._PENDING_QUERY_RE.search(text)` ישירות — **לא** בודקת את סדר ה-dispatch האמיתי, ואף אחת מ-4 הדוגמאות החיוביות לא מסתיימת ב-`"?"`. הרגרסיה הזו הייתה בלתי-ניתנת-לגילוי ע"י הבדיקה הקיימת.
- **צורת תיקון מוצעת (לא בוצע קוד):** להזיז את בדיקת `_PENDING_QUERY_RE.search(_stripped)` **לפני** ה-`if "?" in _stripped:` בשרשרת (למשל בדיקה נפרדת מיד אחרי `route_combined_word`/לפני `§4 disambiguation`, לא כ-branch באותה שרשרת), כך שלא משנה אם הטקסט מכיל `"?"` — או, לחלופין, להוסיף את הבדיקה כ-branch ראשון *בתוך* ה-`if "?" in _stripped:` עצמו (לפני `_STATUS_QUERY_PATTERNS`), כדי לשמור על המבנה הקיים אך לתת לה עדיפות. יש להוסיף גם test חדש שמכסה במפורש שאלת pending-queue **עם** `"?"` בסוף — לא רק בלעדיו — כדי לסגור את פער-הבדיקה שאיפשר את הרגרסיה הזו.
- **היקף:** לא נגעתי בקוד. ממצא מבוסס git+Render API+קריאת קוד ישירה.
- **תוקן:** `app.py` — `_PENDING_QUERY_RE.search(_stripped)` נבדק כעת ב-`if` עצמאי מיד לפני `if "?" in _stripped:` (לא כ-`elif` בסוף השרשרת) — שאלה עם `"?"` בסוף כבר לא נחסמת ע"י ה-branch הכללי. אין שינוי ב-regex עצמו. `elif` הישן (הפך בלתי-נגיש) הוסר. PR #457, commit `9d156d9`, ממוזג ל-`main` (`c12a19b`). 15 בדיקות חדשות (`test_bug141_pending_query_dispatch_order.py`) — מוכיחות דרך נתיב ה-dispatch האמיתי (לא רק `.search()` ישיר) ש-`describe_pending_queue()` נקרא, Agent/`dispatch_tool` לעולם לא נקראים לשאלת pending-queue, "?" ובלעדיו מתנהגים זהה. Full sweep 166/169 (3 כשלים קדם-קיימים לא-קשורים).
- **✅ Verified בפרודקשן (24/07/2026):** אחרי deploy ל-`my-bot-jqz2` (`c12a19b`) — "מה ממתין לאישור" → `"אין פעולה שממתינה לאישור.\n\n(הבדיקה מכסה את מערכת ActionContracts בלבד — לא תורי אישור legacy נוספים.)"`, בדיוק ה-reply הדטרמיניסטי המצופה מ-`describe_pending_queue()`.
- **✅ Verified ב-staging (24/07/2026):** אחרי deploy ידני של ה-owner ל-branch `claude/rp5-staging-fault-injection-v4akit` (מרובייז מעל `main` כולל התיקון הזה) על `my-bot-approval-staging`. דגימה חיה מלאה:
  ```
  Eli: מה ממתין כרגע לאישור?
  BOSS: אין פעולה שממתינה לאישור.
  (הבדיקה מכסה את מערכת ActionContracts בלבד — לא תורי אישור legacy נוספים.)

  [identity] Resolved: boss_hq/eliyahu@owner [telegram:general]
  [httpx] GET .../ActionContracts?filterByFormula=...canonical_user_id...pending... "200 OK"
  [core.turn_envelope] [TurnEnvelope] user=b2320d31 {"turn_mode": "free_agent", "queue_count": 0, ...}
  [app] [ActionGateway] describe_pending_queue: user=boss_hq:eliyahu pending_count=0 scope=action_contracts result_code=empty
  "POST /telegram HTTP/1.1" 200 0
  ```
  כל דרישות ה-fix מאומתות בו-זמנית: `describe_pending_queue()` נקרא (`[ActionGateway] describe_pending_queue`), Airtable `ActionContracts` הוא מקור-האמת היחיד (2 קריאות GET, לא tool-loop כללי), **ואין שום `POST api.anthropic.com` בלוג** — ה-Agent לא נקרא כלל לשאלה הזו (בניגוד לתסמין המקורי, ששלח `airtable_get` ל-Tasks/Deals/Payments + קריאת LLM מלאה).
- **תצפית עלות (24/07/2026, מהבעלים) — חלקית מאומתת, לא הוכחה מלאה:** הבעלים דיווח "הלוגים נקיים פתאום ואני בטוח שגם העלות ירדה". מה שכן מאומת ישירות מהלוג לעיל: ה-turn הספציפי הזה (שאלת pending-queue) לא מפעיל שום קריאת Anthropic — ירידת-עלות מבנית אמיתית **לדפוס-השאלה הזה בלבד** (לפני התיקון: tool-loop מלא + קריאת LLM על כל שאלה כזו; אחרי: 2 קריאות Airtable GET בלבד, אפס LLM). **לא אומת:** ירידת עלות כוללת/שעתית בפועל — דורש בדיקת `cost_monitor`'s hourly/daily totals בפועל (או `usage_events`) לפני קביעה כזו, לא רק תצפית איכותית על "לוגים נקיים". ראו גם הממצא התכנוני "Cost Telemetry Coverage and Per-Turn Attribution" למטה — עדיין אין breakdown פר-turn/source שהיה מאפשר לכמת את הירידה הזו במדויק.
- **✅ AG-03 — הרחבת אימות ל-multiple pending contracts (24/07/2026, staging):** בדיקה ייעודית עם תור של 3 `ActionContracts` חיים — `describe_pending_queue()` הציג ספירה נכונה (3), ומספר כל פעולה דטרמיניסטית (1/2/3), ללא נפילה ל-Agent. **סוגר את שלושת תרחישי-הליבה של BUG-141: תור ריק, חוזה יחיד, מספר חוזים — שלושתם מאומתים ב-staging בפועל.** **לא נבדק עדיין:** בחירה ממוקדת לפי מספר (למשל שליחת "2" כדי לאשר/לדחות פעולה ספציפית מתוך הרשימה הממוספרת) — פריט פתוח, לא כשל, סתם לא נבדק בסבב הזה. **תסמין נלווה שהתגלה (לא ב-BUG-141 עצמו):** החוזה השלישי בתור היה פגום (ראה BUG-143's עדכון-ראיות) והוצג עם label גנרי "airtable_add" במקום תיאור עסקי — `describe_pending_queue()` עצמו התנהג נכון (לא נפל ל-Agent, ספר נכון), אבל התוכן שהוא הציג היה חלקית לא-קריא בגלל BUG-143.
- **סטטוס:** ✅ VERIFIED IN PROD + STAGING (24/07/2026), כולל multi-contract queue (AG-03). קוד תוקן, נבדק (unit+integration, 15/15 + full sweep), ומאומת runtime בשתי סביבות נפרדות עם evidence מלוגים אמיתיים. תצפית-העלות הכוללת (לא רק לדפוס-שאלה בודד) נשארת לא-מאומתת. בחירה ממוספרת מתוך תור מרובה — לא נבדקה.

---

## BUG-142 — Linked-record ישן וsale (`current_lead_record_id`) ב-`Sessions.State JSON` תוקע לצמיתות את ה-sync של אותו sender — 🔴 נרשם, לא תוקן (מאומת ישירות מ-Airtable)

- **תאריך:** 24/07/2026.
- **מקור:** תלונת PATCH כשל: `Sessions/rec3YS5Zcr2FenX7z` נכשל עם `ROW_DOES_NOT_EXIST` על linked record `rec1XZQnIOSiE1Ig5`.
- **ממצא מאומת מ-Airtable:**
  - `rec1XZQnIOSiE1Ig5` **לא קיים** בטבלת `Leads` (שאילתה ישירה על ה-record ID — 0 תוצאות) — עקבי עם המחיקה הידנית של טבלת ה-Leads שהמשתמש ביצע במהלך הסשן ("לידס מחקתי הכל") ואת השחזור החלקי שאחריה ("שחזרתי את טבלת הלידס").
  - `Sessions/rec3YS5Zcr2FenX7z`'s שדה `Linked Lead` (linked-record אמיתי, `fldaGbWJUeUtPZa64`) **ריק כרגע** — Airtable מנקה אוטומטית שדות `multipleRecordLinks` כשהרשומה המקושרת נמחקת. אבל שדה `State JSON` (טקסט חופשי, `fld0ebfybGzlb5XFg`) עדיין מכיל `"current_lead_record_id": "rec1XZQnIOSiE1Ig5"` ו-`"active_lead_candidate": {"record_id": "rec1XZQnIOSiE1Ig5", ...}` — Airtable לא יודע שהטקסט החופשי מכיל רפרנס למשהו שנמחק, אז הוא לא מנקה שם.
  - **אימות שדות נוסף (24/07/2026, שאילתת Airtable ישירה עם מיפוי field-ID→name מאומת דרך `get_table_schema`, לא הונח מהקשר):** `Channel` (`fld900OKlGM8dS3Zl`) `= "whatsapp"` — ערך מפורש בשדה עצמו, מאשר את הסיווג הקיים בדוח. `Sender ID` (`fldyCswBwX333LIxG`) `= "7228089151"` — תואם. `Context Type` (`fldOhFqtt4JfK3Uw8`, singleSelect) `= "lead"` — לא צוין בדיווח המקורי, מוסבר מדוע `active_lead_candidate`/`current_lead_record_id` קיימים ב-state של סשן זה. לא משנה את שורש הבעיה.
- **שורש (אומת בקוד ישיר):**
  1. `session_store.py:648` — `_load_from_db()` משחזר `current_lead_record_id` ישירות מתוך ה-`State JSON` בלי שום בדיקת-קיום מול Airtable.
  2. `session_store.py:491-493` — `_sync_to_db()` בונה מחדש `fields[SF.LINKED_LEAD] = [_linked_lead]` מאותו ערך לא-מאומת, בכל כתיבה עתידית.
  3. `tools/airtable_tools.py:366-369` — `airtable_update()` שולח `State JSON` + `Linked Lead` (וכל שדה אחר שהשתנה) יחד ב-PATCH אחד, אטומי, דרך `airtable_patch()`. Airtable דוחה את ה-PATCH **כולו** על ID לא-תקף — לא רק את השדה הבעייתי.
- **השפעה:** ברגע ש-`current_lead_record_id` מצביע על ליד שנמחק, **כל** קריאת `_sync_to_db()` עתידית עבור אותו session record נכשלת כולה — לא רק ה-linked field, אלא גם `State JSON` עצמו (step/answers/last_tool_result וכו') מפסיק להישמר עבור אותו sender, עד שהערך המיושן ינוקה.
- **צורת תיקון מוצעת (לא בוצע קוד):** לפני בניית `fields[SF.LINKED_LEAD]` ב-`_sync_to_db()`, לאמת שה-`record_id` עדיין קיים (למשל `airtable_get_records`/`GET` ממוקד), ואם לא — לא לשלוח את `Linked Lead` בכלל, ולסמן/לנקות את הערך המיושן בתוך ה-state (`current_lead_record_id=""`/`active_lead_candidate=None`) כדי שלא ינסה שוב בכל כתיבה עתידית. חלופה זולה יותר: לתפוס ספציפית שגיאת `ROW_DOES_NOT_EXIST`/`INVALID_RECORD_ID` ב-`airtable_update()`/`_sync_to_db()` ולנסות שוב פעם אחת בלי שדה ה-linked record.
- **היקף:** לא נגעתי בקוד. ממצא מבוסס Airtable+קריאת קוד ישירה.
- **סטטוס:** 🔴 נרשם, root cause מאומת עד השורה, לא תוקן.

---

## BUG-143 (CB-02A) — `resolve_canonical_tool()` מחליף `sheets_append`→`airtable_add` בלי להמיר payload, יוצר ActionContract פגום — ✅ תוקן (PR #461, ממוזג `main`)

- **תאריך:** 24/07/2026.
- **מקור:** בדיקת CB-02 (שלב A — malformed sample), חוזרת פעמיים.
- **ממצא מאומת מ-Airtable (`ActionContracts`, בסיס `app4bcgoX7t0HUVnm`):**
  - `ee5ffb68-7a10-475d-bc7b-3dfa1f01fa38` (`recaj8Mme0Vasu7PH`, נוצר 24/07 00:27:56Z) — `tool_name=airtable_add`, `normalized_payload={"row_data": ["CB02 — בדוק כפתור אישור", "ממתין", "2026-07-25", "בדיקה מחר"], "sheet_name": "Tasks"}`, `status=pending`.
  - `00b84046-8fe6-408b-be55-f0c69ecf009b` (`recFc4x9JGCDVPRQ6`, נוצר 24/07 00:38:43Z) — אותו דפוס בדיוק: `tool_name=airtable_add` עם `row_data`/`sheet_name` (צורת Sheets), `status=pending`.
  - שני ה-payloads הם צורת `sheets_append` (`row_data`/`sheet_name`, ראה `action_validator.py:22`) — לא צורת `airtable_add` התקנית (`table`/`fields`).
- **שורש (אומת בקוד ישיר):** `core/action_gateway.py::resolve_canonical_tool()` (שורות 314-338) — כשה-hint המקורי הוא `sheets_append` וללא בקשת-Sheets מפורשת בטקסט המשתמש, הפונקציה **מחזירה** `tool_name` חדש (`airtable_add`, שורה 336) אבל **אף פעם לא נוגעת ב-`tool_inputs`**. הקריאה היחידה למקום הזה (`app.py:1104`, `_queue_approval_detailed_impl()`) משתמשת בערך המוחזר בתור `tool_name` החדש, אבל ממשיכה עם אותו `tool_inputs` המקורי (עדיין בצורת Sheets) הלאה ליצירת ה-fingerprint/contract.
- **השפעה:** נוצר `ActionContract` שנראה כמו פעולת Airtable תקנית (`tool_name=airtable_add`) אך ה-payload שלו לא מכיל `table`/`fields` תקינים — אם ה-contract הזה יאושר, הביצוע בפועל (`dispatch_tool`/`airtable_add`) צפוי להיכשל או להתנהג לא-צפוי (payload לא תואם schema). **אומת: אף אחד משני ה-contracts לא אושר עדיין** — טבלת `Tasks` נבדקה ישירות ולא מכילה "CB02 — בדוק כפתור אישור" או "CB-22" — אין נזק נתונים בפועל עדיין.
- **צורת תיקון מוצעת (לא בוצע קוד):** אם `resolve_canonical_tool()` משנה tool_name, היא (או הקורא ב-`app.py:1104`) חייבת גם להמיר את ה-payload לסכמה של הכלי החדש (Sheets `row_data`/`sheet_name` → Airtable `table`/`fields`). אם ההמרה לא ניתנת לביצוע בוודאות (מיפוי עמודות לא ידוע) — עדיף **לא** ליצור ActionContract בכלל, ולהחזיר בקשת-הבהרה/כישלון-סגור למשתמש, במקום ליצור contract "תקין-למראה" עם payload שבור.
- **עדכון ראיות (24/07/2026, AG-03 — pending-queue עם 3 חוזים):** בדיקת `describe_pending_queue()` על תור עם 3 `ActionContracts` חיים חשפה תסמין נוסף מאותו שורש: החוזה השלישי (מופע נוסף של הבאג הזה — `tool_name=airtable_add`, canonical tool הוחלף מ-`sheets_append`, שדה הטבלה ריק) הוצג בתור עם label גנרי "airtable_add" בלבד — כי `_describe_contract_for_disambiguation()` (המשמשת את `describe_pending_queue()`) לא הצליחה לבנות תיאור עסקי קריא מ-payload פגום, ונפלה חזרה לשם ה-tool הגולמי. כלומר הבאג לא רק מסכן ביצוע שגוי (כפי שתועד למעלה) — הוא גם פוגע ב-**קריאוּת התור עצמו** למשתמש שמנסה לבדוק מה ממתין (BUG-141's `describe_pending_queue()`).
- **היקף:** לא נגעתי בקוד, לא אישרתי/דחיתי אף contract. ממצא מבוסס Airtable+קריאת קוד ישירה.
- **סטטוס:** 🔴 נרשם, root cause מאומת עד השורה, לא תוקן. שלושת ה-contracts עדיין `pending` — ראו המלצת ניקוי ידנית.
- **עדכון ראיות (25/07/2026, דוח בדיקות Post-Merge של הבעלים, תרחיש 3 — "PM460-POSTMERGE-CANONICAL"):** מופע רביעי (חי, `pending`) של אותו דפוס בדיוק — `contract_id=aa74244a-4658-45dd-9c21-4e1467e204a3`, `tool_name=airtable_add`, payload בצורת Sheets (`{"row_data": [...], "sheet_name": "Tasks"}` — לא `table`/`fields`). הדוח מציין במפורש שהמערכת "לא נעצרה לפני יצירת ActionContract לא תקין" — עקבי עם ה-root cause הרשום למעלה (`resolve_canonical_tool()` מחליף שם-tool בלי להמיר payload). **לא אומת ישירות על ידי (Claude) מול Airtable/קוד בסבב הזה** — מבוסס על דוח הבדיקות שהבעלים סיפק; רישום-בלבד, לא ריצת-קוד עצמאית.
- **✅ תוקן (26/07/2026, PR #461 `codex/pm460-drive-fail-closed`, `70093f0`, ממוזג `719bb86`):** `_sheets_payload_to_airtable()` (`core/action_gateway.py`) — המרה אמיתית של payload בצורת Sheets ל-`table`/`fields`, כולל field-allowlist (`FIELD_MAP`) וטבלה-קנונית (`TABLE_ALIASES`), עם `CanonicalizationError` (fail-closed) כשההמרה לא בטוחה. נקרא מ-`resolve_canonical_call()`, שמחליף כעת את הקריאה הישירה ל-`resolve_canonical_tool()` שתועדה כשורש-הבעיה כאן. **מאומת ב-git log/diff ישירות מול `main`** (לא רק PR status). **לא אומת מול production/staging traffic חי בסבב התיקון עצמו** — אימות-staging חי הגיע מאוחר יותר (ראו PM460-RETEST-CANONICAL, תרחיש 3 בסבב הבדיקה החוזרת של הבעלים ב-26/07/2026: contract נוצר עם payload קנוני מלא — `table`/`fields`, ללא `sheet_name`/`row_data` — ✅ PASS, ראו BUG-149 למטה לפרטי הסבב המלא). שלושת ה-contracts הפגומים הקיימים בזמן התיקון (`ee5ffb68`/`00b84046`/`aa74244a`) נותרו `pending` — התיקון אינו רטרואקטיבי, נדרש ניקוי ידני נפרד אם עדיין רלוונטי.
- **סטטוס מעודכן:** ✅ תוקן ומאומת חי ב-staging (PR #461 + PM460-RETEST-CANONICAL, 26/07/2026).

---

## BUG-144 (CB-02B) — כפתור דחייה בטלגרם לא סוגר את `ActionContracts.status` — מקור-האמת נשאר `pending` אחרי שהמשתמש קיבל אישור-ביטול — 🟡 שני מסלולי-תיקון עצמאיים (PR #460 + PR #471) — ראה סטטוס מפורט למטה

- **תאריך:** 24/07/2026.
- **מקור:** בדיקת CB-02 (שלב B — clean reject sample). הודעת משתמש: `"תוסיף משימה לראות מה קורה עם אוטומציית הלוגים מחר"`.
- **Expected:** ActionContract תקין, כפתור דחייה, לחיצה → אין כתיבה ל-Tasks, `ActionContracts.status=rejected`.
- **Actual:** הכפתור עבד ברמת Telegram UI, המשתמש קיבל `"🚫 בוטל"` (popup) ואז הודעה נוספת "🚫 הפעולה בוטלה: {label}" — אך `ActionContracts` הראה עדיין `pending`.
- **ממצא מאומת מ-Airtable:** `0ce5b20e-33ea-4fe5-aeca-3d3911debe0c` (`recCKbg1fH2HaXwo5`, נוצר 24/07 00:39:30Z, `tool_name=airtable_add`, payload תקין — `{"table": "Tasks", "fields": {"כותרת המשימה": "לראות מה קורה עם אוטומציית הלוגים", "סטטוס": "ממתין", "תאריך יעד": "2026-07-25"}}`) — `status=pending`, **לא** `rejected`, למרות שהמשתמש לחץ דחייה וקיבל אישור-ביטול. `Tasks` נבדק ישירות — לא נוצרה שורה, כך שאין נזק-נתונים, אבל מקור-האמת (`ActionContracts`) לא סונכרן.
- **שורש (אומת בקוד ישיר):** `app.py:2409-2449` (`elif action == "reject":` ב-`_handle_approval_callback_impl()`) — התגובה הזו כבר מתועדת בהערת קוד קיימת (`app.py:2409-2421`, מפנה ל-`docs/architecture/f52-unified-approval-runtime/PR5_REJECTION_CANCELLATION_SHADOW.md`): ה-branch הזה קורא רק ל-`bus.pop(action_id)` (`2422`, event_bus בלבד) ובונה טקסט-ביטול ידנית — **הוא אף פעם לא קורא ל-`ActionGateway.reject(contract_id)`** (`core/action_gateway.py:1298`) או לכל lifecycle transition שקול. ה-`ActionContract` המתאים ב-Airtable נשאר `pending` כי שום דבר לא סימן אותו `rejected`.
- **השפעה:** המשתמש חושב שהפעולה בוטלה (מקבל שתי הודעות אישור-ביטול), אבל מקור-האמת (`ActionContracts`) עדיין חי — גורם ל-`live_contracts`/`find_live_by_user()` לגדול ולזהם דגימות עתידיות (BUG-122's `multi_contract_conflict`, RP5 sampling).
- **צורת תיקון מוצעת (לא בוצע קוד):** ה-`reject` callback חייב לקרוא ל-`ActionGateway.reject(contract_id)` (או ל-lifecycle transition שקול) לפני/יחד עם בניית הטקסט למשתמש — לא להסתפק ב-`event_bus.pop()`. יש למצוא את ה-contract המתאים לפי fingerprint (כמו שנעשה כבר בענף ה-approve, `app.py:2159-2187`) לפני הודעת "בוטל".
- **היקף:** לא נגעתי בקוד. ממצא מבוסס Airtable+קריאת קוד ישירה.
- **סטטוס:** 🔴 נרשם, root cause מאומת עד השורה (כולל הערת-קוד קיימת שכבר מתעדת את הפער כ"ידוע"), לא תוקן. Contract עדיין `pending` — ראו המלצת ניקוי ידנית.
- **עדכון ראיות (25/07/2026, דוח בדיקות Post-Merge של הבעלים, תרחישים 2/4 — לכאורה סותר, דורש בירור):** דוח הבדיקות מדווח **PASS**/**PASS חלקי** על שני תרחישי-דחייה — `contract_id=96ab2a59-4ab1-453f-b56f-b7bdeefbad00` (תרחיש 4, "callback הדחייה") עבר בפועל ל-`rejected` (`version: 2`), ו-`PM460-POSTMERGE-122-B` (תרחיש 2) לא יצר רשומת Task בטבלת היעד. זה **נראה סותר** את הסטטוס הרשום למעלה. **קריאת קוד ישירה בסבב הזה מאשרת שה-gap התיעודי עדיין קיים במדויק** ב-`app.py:2409-2449` (`elif action == "reject":` ב-`_handle_approval_callback_impl()` — הענף הזה עדיין רק קורא `bus.pop(action_id)`, אף פעם לא `ActionGateway.reject()`; הערת-הקוד הקיימת שם עדיין מתעדת את זה כפער ידוע, ללא שינוי). **אבל** נמצא בקוד מסלול-דחייה **שני**, נפרד לגמרי — מילות-ביטול בשפה חופשית (`_CANCEL_WORDS`, `app.py:176`) המנותבות דרך `core/action_gateway.py`'s `route_confirmation_word()`/`route_cancellation_word()`, אשר **כן** קוראות ל-`self.reject(contract.contract_id, ...)` (למשל `core/action_gateway.py:1690`, `1607`, `1517`) — מסלול הזה מעדכן את ה-`ActionContract` הקנוני נכון. **מסקנה זהירה, לא סופית:** ייתכן שדוח ה-Post-Merge בפועל תרגל את מסלול מילת-הביטול בשפה חופשית (שכבר עובד נכון) ולא את כפתור-הדחייה של Telegram (`_handle_approval_callback_impl`, שעדיין שבור) — הדוח לא מפרט אילו לחיצות/מילים בדיוק שימשו. **דורש בירור מפורש לפני שינוי סטטוס BUG-144:** אם הבדיקה בפועל לחצה על כפתור inline, זו ראיה חדשה שסותרת את הרישום למעלה וצריכה חקירה נפרדת; אם היא הקלידה מילת-ביטול חופשית, הדוח פשוט אימת מסלול-דחייה *אחר* מזה שה-BUG הזה מתעד, וסטטוס BUG-144 (כפתור inline) נשאר ללא שינוי. לא אומת ישירות מול Airtable/לוגים אמיתיים על ידי (Claude) בסבב הזה.
- **✅ תוקן (26/07/2026, PR #460 `codex/july24-sampling-blockers`, `006506d`, ממוזג `0c06f4c`) — הבירור שהתבקש למעלה נפתר:** שיכתוב ענף ה-reject ב-`_handle_approval_callback_impl()` — מוצא כעת את ה-contract הקנוני לפי fingerprint ו**קורא בפועל ל-`ActionGateway.reject(contract_id, rejected_by=...)`**, כולל בדיקת-transition (`_reject_after.status == "rejected"`) לפני שהמשתמש מקבל אישור-ביטול. **מאומת ב-git log/diff ישירות מול `main`.** הבירור שנדרש למעלה נפתר בפועל, לא רק בהשערה: **PM460-RETEST-REJECT** (סבב הבדיקה החוזרת של הבעלים ב-staging, 26/07/2026, אחרי deploy) לחץ במפורש על כפתור-הדחייה של Telegram (לא מילת-ביטול חופשית) — לוג מלא: `PATCH ActionContracts ... keys=['status','version'] ok=True`, `[ActionGateway] rejected: contract=c11c69b4...`, הודעת סיום **אחת** בלבד ("🚫 הפעולה בוטלה: ..."), וחיפוש בטבלת Tasks לא מצא רשומה שנוצרה — ✅ PASS מלא, כולל אישור ש-BUG-145's כפל-ההודעות גם נסגר לענף הזה (ראו BUG-145 למטה).
- **עדכון מימוש (27/07/2026, PR #471, `5e2c244` + תיקון CI `dadf851`, merge `c64da20`) — מסלול-תיקון עצמאי שני, מאוחר יותר, תחת `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` (כבוי כברירת-מחדל):** callback reject מקושר כעת ל-ActionContract המדויק דרך correlation קנוני וקורא ל-`reject_with_lifecycle_result()` במקום להסתפק ב-`event_bus.pop()`. בדיקות callback hardening מאמתות מעבר durable ל-`rejected`, replay ללא שינוי lifecycle, ואפס dispatch. `ActionContracts` נשאר מקור האמת היחיד; לא נוסף state ל-Sessions או correlation store. payloads נכשלים במפורש מעל 64 bytes ואינם מקצרים contract ID. מסלול זה נפרד מהשיכתוב הבלתי-מותנה של PR #460 שכבר תועד ואומת למעלה.
- **סטטוס מעודכן:** ✅ תוקן ומאומת חי ב-staging דרך כפתור ה-inline עצמו (PR #460 + PM460-RETEST-REJECT, 26/07/2026) — לא רק מסלול מילת-הביטול החופשית. **בנוסף**, PR #471 (27/07/2026) מימש מסלול-תיקון שני, עצמאי, תחת flag נפרד (`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, כבוי כברירת-מחדל) — 🟡 מומש ומוזג ל-`main`, עבר CI, אך טרם אומת בפועל ב-staging/production תחת ה-flag הזה.

---

## BUG-145 (CB-01 + CB-02B) — Approval/rejection callback שולח שתי הודעות סופיות למשתמש על אותה פעולה — 🟡 שני מסלולי-תיקון עצמאיים (PR #460 + PR #471) — ראה סטטוס מפורט למטה

- **תאריך:** 24/07/2026.
- **מקור:** CB-01 (approve) — שתי הודעות הצלחה על אותה פעולה. CB-02B (reject) — "🚫 בוטל" ואז הודעת ביטול נוספת עם פירוט הפעולה.
- **שורש (אומת בקוד ישיר, שני הענפים ב-`_handle_approval_callback_impl()`):**
  - **Approve:** `app.py:2385-2400` — `bot.send_message(origin_chat_id, user_notify_text)` (`2388`, הודעת צ'אט חדשה: "✅ הפעולה בוצעה:\n{result}") **וגם** `bot.edit_message_text(f"✅ אושר ובוצע\n{item['label']}", ...)` (`2397-2400`, עריכת ההודעה המקורית) — כשה-`origin_chat_id` זהה לצ'אט של הכפתור (המקרה השכיח), המשתמש רואה שתי בועות-הצלחה נפרדות (בנוסף ל-popup `answer_callback_query`, `2403`, שהוא ephemeral ולא נספר כ"הודעה" בהיסטוריה).
  - **Reject:** `app.py:2426-2442` — `bot.send_message(user_chat_id, f"🚫 הפעולה בוטלה: {item['label']}")` (`2430`) **וגם** `bot.edit_message_text("🚫 *בוטל*", ...)` (`2436-2439`) — אותו דפוס כפול בדיוק.
- **השפעה:** המשתמש מקבל הודעות כפולות (ולפעמים נראות כסותרות, למשל אם אחת מהן נכשלת/מתעכבת) על כל פעולת approve/reject.
- **צורת תיקון מוצעת (לא בוצע קוד):** לקבוע exactly-one final user-facing message לכל turn של approve/reject בבעלות ה-gateway — למשל, לוותר על `bot.send_message()` הנפרד ולהסתפק בעריכת ההודעה המקורית (`edit_message_text`) כערוץ הסופי היחיד, כשמדובר באותו chat; לשמור על `send_message` נפרד רק כש-`origin_chat_id != cq.message.chat.id` (ערוץ אחר לגמרי מזה שבו נלחץ הכפתור).
- **עדכון ראיות (24/07/2026, AG-03 — תור עם 3 חוזים, החוזה השלישי פגום/BUG-143):** בתור ה-approval turn של החוזה הפגום, נצפה `agent_spoke_in_gateway_owned_approval_turn` (סימן turn-ownership) יחד עם RP5 evidence `approval_pending` + user-facing text שמכיל טענת-כישלון, ו-`status_claim_mismatch` (RP5/F52 shadow). **הערת-זהירות:** זה כנראה אותה משפחת-תופעה (יותר מ"קול" אחד סמכותי למשתמש באותו turn של אישור) — אבל דרך מנגנון שונה (Agent מדבר בתוך turn שאמור להיות בבעלות ה-gateway, מזוהה ע"י RP5/turn-ownership shadow) מזה שכבר תועד למעלה (`send_message`+`edit_message_text` כפולים ב-`_handle_approval_callback_impl()`). **לא אומת** שזה אותו code path בדיוק — ייתכן שמדובר בסימפטום נוסף/נפרד שרק במקרה שייך לאותה קטגוריה. דורש קריאת קוד נפרדת (`core/turn_envelope.py`'s ownership signal + RP5's `status_claim_mismatch` classification) לפני שקובעים אם זה תיקון-אחד או שניים.
- **היקף:** לא נגעתי בקוד. ממצא מבוסס תצפית משתמש ישירה + קריאת קוד לאימות.
- **סטטוס:** 🔴 נרשם, root cause מאומת עד השורה בשני הענפים המקוריים, לא תוקן. תופעה נוספת (agent-spoke-in-gateway-turn) נצפתה ב-AG-03, קשר מדויק ל-root cause הקיים טרם אומת.
- **עדכון ראיות (25/07/2026, דוח בדיקות Post-Merge של הבעלים, תרחיש 5 — "PM460-POSTMERGE-CB-APPROVE"):** מרחיב את ה-scope הרשום — עד כה תועד כפל-הודעות רק בענף **הצלחה**; הדוח מדווח כפל זהה גם בענף **כישלון-ביצוע**: `contract_id=81528313-9168-4820-bd9d-1ff1810e931b` עבר `approved`→`failed` (`version: 3`, `approved_by: boss_hq:eliyahu`), ואותה הודעת-כישלון נשלחה למשתמש **פעמיים**. עקבי עם ה-root cause הרשום למעלה (`app.py:2385-2400`): הענף שולח דרך `bot.send_message()`+`bot.edit_message_text()` ללא הבחנה בין success/failure ב-`result` — כך שהכפילות משוכפלת בדיוק גם כש-`result` מכיל טקסט-כישלון. **לא אומת ישירות מול לוגים/Airtable על ידי (Claude) בסבב הזה** — מבוסס על דוח הבעלים בלבד.
- **✅ תוקן (26/07/2026, PR #460, `006506d`/`0c06f4c`):** helper אחיד להודעה-סופית-יחידה (`_deliver_callback_final()`, `app.py`) — משווה `origin_chat_id` מול `cq.message.chat.id`: אם זהים, `edit_message_text()` הוא הערוץ היחיד; אם שונים, `send_message()` נפרד לצ'אט המקורי. מיושם **בשני הענפים** (approve success/failure **וגם** reject) — מקיף יותר מהתיקון שתוכנן במקור לענף approve בלבד, כולל את ה-failure-branch שהורחב בממצא-ה-25/07 מיד למעלה. **מאומת חי ב-staging:** PM460-RETEST-REJECT (26/07/2026) קיבל הודעת סיום **אחת** בלבד — ✅ PASS.
- **עדכון מימוש (27/07/2026, PR #471, `5e2c244` + תיקון CI `dadf851`, merge `c64da20`) — מסלול-תיקון עצמאי שני, מאוחר יותר, תחת `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` (כבוי כברירת-מחדל):** callback acknowledgment מוגדר non-final. באותו chat, ההודעה המקורית נערכת והיא המשטח הסופי היחיד; ב-cross-chat נשמרת הודעת requester יחידה וה-keyboard של approver בלבד מוסר. `ApprovalLifecycleResult.final_response_count=1` ו-Gateway ownership מונעים fallback/retry/action-status/duplicate success של Agent לאחר handoff. בדיקות approve/reject/replay/stale/cross-chat מאמתות surface סופי יחיד. **טרם אומת בפועל ב-staging/production תחת ה-flag הזה** (עבר CI בלבד).
- **סטטוס מעודכן:** ✅ תוקן ומאומת חי ב-staging תחת המסלול הבלתי-מותנה (PR #460 + PM460-RETEST-REJECT, 26/07/2026), כולל ענף reject. **בנוסף**, PR #471 (27/07/2026) מימש מסלול-תיקון שני, עצמאי, תחת flag נפרד — 🟡 מומש ומוזג, עבר CI, טרם אומת בפועל תחת ה-flag.

---

## BUG-146 — `bypass_new_action` enforcement gap — ⚪ Merged into BUG-122 (24/07/2026)

> **Merged into BUG-122 — evidence expansion, not a separate defect.**
>
> נשמר כאן כרשומת היסטוריה בלבד. המנגנון (`app.py:3548-3558`), הראיות (CB-01/CB-02, contracts `ee5ffb68-...`/`00b84046-...`/`0ce5b20e-...`) והצעת התיקון הועברו במלואן לסעיף **"עדכון ראיות (24/07/2026, CB-01/CB-02 staging)"** בתוך BUG-122 לעיל. הסיבה: אותו קובץ/שורה בדיוק, אותו מנגנון (`bypass_new_action`, כבר מתועד ב-BUG-122 כ-"מקרה תקין, מתועד ל-observability"), אותה הצעת-תיקון — אין אחריות/שכבת-קוד/expected-behavior נפרדים מהותית שמצדיקים מספר-באג עצמאי. המספור (BUG-146) נשאר תפוס ולא נמחק; אין לפתוח PR/fix תחת המספר הזה — הפניה ל-BUG-122.
- **תאריך מיזוג:** 24/07/2026.
- **סטטוס:** ⚪ Merged into BUG-122 — evidence expansion, not a separate defect.

---

## BUG-147 — `dispatch_tool`'s `airtable_add` case returns a plain string on blocked/violation paths instead of the structured `{ok, ...}` contract — ✅ תוקן (PR #469, ממוזג `main`)

- **תאריך:** 25/07/2026.
- **מקור:** דוח בדיקות Post-Merge של הבעלים, תרחיש 5 ("PM460-POSTMERGE-CB-APPROVE") — `contract_id=81528313-9168-4820-bd9d-1ff1810e931b` אושר (`approved`) אך הביצוע נכשל עם `airtable_add: expected structured result dict with ok=true; got plain string`, ולא נוצרה רשומת Task.
- **שורש (אומת בקוד ישיר בסבב הזה — root cause עצמאי, לא רק אימות-דוח):**
  - `tools/airtable_tools.py:319-339` (`airtable_add()`) עצמה **כן** מחזירה תמיד dict מובנה (`_tool_result(ok=..., tool="airtable_add", ...)`, C53a contract) — לא זו נקודת הכשל.
  - אבל `tools/dispatcher.py`'s `case "airtable_add":` (שורות 241-323) מכיל שני מסלולי-חסימה שמחזירים **מחרוזת רגילה** במקום ה-contract המובנה: שורה 261 (`return str(e)` כש-`LeadsDirectWriteBlocked` נזרקת מ-`enforce_leads_write_gate`) ושורה 319 (`return str(e)` כש-`TenantScopeViolation` נזרקת מ-`enforce_tenant_scope`). שני המחרוזות האלה **לא** מתחילות ב-"❌" (הן ה-`__str__` הגולמי של האקספשן).
  - `core/anti_hallucination.py:400-436` (`verify_execution`, פנימי ל-`ActionGateway.approve`/`_execute_contract`) בודק: אם התוצאה `dict` — נתיב תקין; אחרת (מחרוזת) — אם היא מתחילה ב-"❌" מסווגת כ-`failed` עם הטקסט כסיבה (תקין); אבל אם היא **לא** מתחילה ב-"❌" וה-tool רשום כ-write/validator (`airtable_add` הוא), השורה 428-431 מייצרת בדיוק את ההודעה שנצפתה בדוח: `f"{tool_name}: expected structured result dict with ok=true; got plain string"`.
  - כלומר: אם `dispatch_tool("airtable_add", ...)` נכנס לאחד משני המסלולים החוסמים האלה, ה-contract-shape שנשבר גורם לסיווג-כישלון "עמום" (הודעה גנרית) במקום סיבת-החסימה האמיתית (Leads-direct-write / tenant-scope), ושובר את ה-`{ok, data/error}` uniform contract שה-`ActionGateway` דורש מכל executor.
- **הבהרה חשובה — לא אומת שזו בהכרח נקודת ההפעלה המדויקת של תרחיש 5 עצמו:** לא נצפו לוגים/traces אמיתיים של אותה הרצה (`81528313-...`) בסבב הזה כדי לקבוע איזה משני המסלולים (או מסלול שלישי לא-ידוע) בפועל הופעל. ייתכן גם שזו תוצאה נוספת/שונה של BUG-143 (payload שעדיין לא-קנוני מגיע לביצוע וגורם ל-`KeyError`) — אך אותו מסלול (`core/action_gateway.py:1996-2015`, ה-`except Exception as exc: return f"❌ ביצוע נכשל: {exc}"`) **כן** מתחיל ב-"❌" ולכן לא היה מייצר את ההודעה "expected structured result dict" הספציפית — מה שמחזק (לא מוכיח) שהחסימה של דיספצ'ר (261/319) קרובה יותר לשורש בפועל.
- **השפעה:** כל executor ב-`tools/dispatcher.py` שמחזיר מחרוזת-שגיאה גולמית (לא-"❌"-prefixed) על נתיב-חסימה, במקום ה-contract המובנה, גורם ל-false/generic failure classification ב-`verify_execution()` — מסתיר את סיבת-הכישלון האמיתית מהמשתמש/מהתחזוקה, ובסופו נופל תחת "NO-GO" recommendation לפי דוח הבעלים.
- **צורת תיקון מוצעת (לא בוצע קוד):** כל branch חוסם ב-`dispatch_tool`'s `case "airtable_add"`/`"airtable_update"` (ואולי tools נוספים) צריך להחזיר את אותו `{ok: False, tool, error, user_message}` shape במקום `str(e)` גולמי — לא רק כדי לתקן את הדוח הזה אלא כדי לסגור את הפער העקרוני שדוח הבעלים מצביע עליו ("כל executor חייב להחזיר מבנה אחיד").
- **היקף:** קריאת קוד בלבד (`tools/dispatcher.py`, `tools/airtable_tools.py`, `core/anti_hallucination.py`, `core/action_gateway.py`) — לא בוצע שינוי קוד, לא אושר/נדחה contract.
- **סטטוס:** 🔴 נרשם, root cause סביר ומאומת חלקית (שני code paths קונקרטיים שמשחזרים את התסמין), לא תוקן. הקישור המדויק לתרחיש 5 הספציפי מהדוח לא אומת מול לוגים אמיתיים.
- **✅ תוקן (26/07/2026, PR #469 "Patch A", ענף `claude/bug147-dispatcher-structured-error`, commit `3b111f6`, ממוזג `e946225`) — root cause שנרשם למעלה התברר כשגוי, שורש אמיתי אחר נמצא:** בדיקה מדוקדקת יותר גילתה ש-`_leads_write_blocked_message()`/`TenantScopeViolation`'s ההודעה **כבר** מתחילות ב-"❌" — כלומר שני המסלולים החשודים למעלה (שורות 261/319) **כן** סווגו נכון ע"י `verify_execution()`, ולא היו התסמין בפועל. השורש האמיתי: `dispatch_tool()`'s gate הכללי מיד אחרי `action_validator.validate_action()` (לפני ה-`case` הספציפי לכל tool) מחזיר `validation.reason` גולמי (בלי "❌") לכל structured write tool — בדיוק מה ש-payload בצורת BUG-143 (חסר `table`/`fields`) מייצר. **תיקון:** tools ב-`core.anti_hallucination._EVIDENCE_VALIDATORS` (כולל `airtable_add`) מקבלים כעת `{ok: False, tool, user_message}` במקום מחרוזת גולמית על הנתיב הזה; שני המסלולים המקוריים בהשערה (`LeadsDirectWriteBlocked`/`TenantScopeViolation`) גם עודכנו לאותה צורה, לעקביות (לא כי היו שבורים). **PR ממוקד קוד+test בלבד** — `tools/dispatcher.py` + `test_bug147_dispatcher_structured_error_shape.py` (10/10 assertions), ללא נגיעה ב-`app.py`/`core/action_gateway.py`. **מאומת ב-git log/diff ישירות מול `main`** — 170/170 full sweep ירוק בזמן המיזוג. **מאומת חי ב-staging:** PM460-RETEST-APPROVE (26/07/2026, סבב הבדיקה החוזרת) — "BUG-147 לא חזר... לא הופיעה השגיאה expected structured result dict" — ✅ PASS (התוצאה שכן נכשלה בתרחיש הזה הייתה בעיה נפרדת לגמרי, ראו BUG-149 למטה).
- **סטטוס מעודכן:** ✅ תוקן ומאומת חי ב-staging (PR #469 + PM460-RETEST-APPROVE, 26/07/2026), עם root-cause writeup מתוקן מהרישום המקורי.

---

## BUG-149 — Multi-mutation turns replay a stale, already-resolved earlier proposal instead of the current request; the real request is silently dropped — ✅ תוקן (PR #470, ממוזג `main`)

- **תאריך:** 26/07/2026.
- **מקור:** דוח בדיקות Post-Merge של הבעלים (סבב שני, אחרי deploy PR #469 + rebase staging), תרחיש 5 — "PM460-RETEST-APPROVE". הבקשה שנשלחה בפועל: "צור משימה PM460-RETEST-APPROVE...", אך המערכת יצרה `ActionContract` חדש (`contract_id=733e2e5a-...`) עם ה-payload של תרחיש 3 הקודם ("PM460-RETEST-CANONICAL", שכבר נדחה כ-`rejected` ב-contract נפרד `938dca44-...`) — לא עם ה-payload של הבקשה הנוכחית. ה-contract השגוי אושר וביצע בהצלחה (`record_id=recN4Fofh8SNEaT5p`), כך שהמשתמש קיבל "✅ בוצע" על משימה שלא ביקש, בעוד הבקשה האמיתית שלו לא בוצעה בכלל וגם לא הודיעה על עצמה בבירור.
- **שורש (אומת בקוד ישיר בסבב הזה):**
  1. `memory.add()` (`app.py`) שומר רק טקסט גולמי (הודעת המשתמש + תשובת ה-Agent) — **לעולם לא** את תוצאת האישור/הדחייה בפועל. approve()/reject() (`core/action_gateway.py`) דטרמיניסטיים לחלוטין ואף פעם לא קוראים מחדש ל-Agent — ה-Agent פשוט **אף פעם לא לומד** מה קרה להצעה קודמת שהוא הציע.
  2. בשיחת-בדיקה עם 3 בקשות "צור משימה" רצופות (תרחישים 3/4/5) בתוך אותו חלון TTL של 12 שעות, ה-history שחוזר ל-Claude מכיל את כל 3 הבקשות כטקסט גולמי, בלי שום סימן שהראשונות כבר טופלו — Claude, "זוכר" 3 בקשות פתוחות-לכאורה, מנסה ליצור את כולן מחדש באותו turn ("אני יוצר את שלוש המשימות ב-Airtable").
  3. שער BUG-122 הקיים (`app.py`, `_mutating_approvals_this_turn>=1`) שומר רק את tool_use ה**ראשון** של turn עם כמה mutating tool_use ומחסום את השאר — כשה-tool_use הראשון הוא דווקא ה-payload הישן (לפי סדר-הופעה בהיסטוריית השיחה), הוא זה שמנצח, וה-payload האמיתי (השלישי בסדר) נחסם בהודעה גנרית "לשלוח מחדש".
- **תיקון (שתי שכבות, per עיצוב מאושר עם Cross-Layer Impact Matrix מלא):**
  1. `core/action_resolution_event.py`/`core/action_resolution_projection.py` (חדשים) — `ActionGateway` (שכבה 4) פולט `ActionResolutionEvent` דטרמיניסטי מ-`reject()` ומהצומת היחיד `_persist_execution_status()` (מכסה `completed`/`executed`/`failed`/`outcome_unknown` באחידות; `approved` **אינו** נחשב terminal בכוונה). `ActionGateway` עצמו **לא** מייבא `memory_store` ישירות — הזרקת-תלות (`resolution_sink`, אותו דפוס כמו `tool_executor`) לאדפטר חיצוני, שנקשר פעם אחת ב-`app.py`'s `run_startup_sequence()`. אידמפוטנטי (`contract_id+outcome+version`). כשל בהזרקה: `WARNING`, ללא payload רגיש, לעולם לא משפיע על ה-transition הדורש (מאומת ב-test עם sink שזורק). האירועים נשמרים בערוץ נפרד וחדש ב-`memory_store.py` (`add_context_event()`/`get_context_events_for_claude()`) — **לא** מוזרקים להיסטוריית user/assistant הרגילה — ומוזרקים ל-system prompt (`app.py`'s `_build_action_resolution_context()`) כ-context מסומן-במפורש. Process-local, לא-דורש, מתועד ככזה — `ActionContract`/`ExecutionLedger` נשארים מקור-האמת הדורש היחיד.
  2. שער דטרמיניסטי חדש `MULTI_MUTATION_CONTEXT_MISMATCH` (`app.py`, לפני ה-loop הקיים על tool_use): אם תגובת-מודל אחת מכילה 2+ tool_use בעלי `requires_approval=True`, **אף אחד** מהם לא מבוצע — אפס `ActionContract`, אפס קריאות ל-`dispatch_tool`/`tool_executor`/`propose_action`/`event_bus`, tool_result כשל אחיד לכולם, הודעה למשתמש שדבר לא נשמר ושצריך לשלוח מחדש בקשה אחת. **לא** שומר את הראשון ולא את האחרון — זו רשת-הביטחון הדטרמיניסטית בפועל; שכבה 1 (context events) היא מיטיגציה נוספת מעליה, לא תחליף לה.
  3. הנחיה חד-שורתית ב-system prompt (`core_knowledge.py`) — "התייחס רק להודעה האחרונה של המשתמש כהוראה הפעילה של הסבב הזה."
- **Cross-Layer Impact Matrix:** מולא במלואו לפני מימוש (שכבה 4 נוגעת ישירות; שכבה 2 נוגעת בעקיפין — שכבה 4 הופכת למקור מוסמך לאירועי-lifecycle גלויים-למודל, מתועד כגבול-אירוע חדש, לא "ללא השפעה"; שכבות 1/3 לא נוגעות). ראו commit message/PR #470 לפירוט המלא.
- **בדיקות:** `test_bug149_action_resolution_projection.py` (23 assertions — schema, נקודות-פליטה, אידמפוטנטיות, sink-failure non-blocking, הוכחת ניתוב-זהות) + `test_bug149_multi_mutation_guard.py` (15 assertions — CANONICAL→REJECT→APPROVE יוצר אפס contracts לא את הראשון, `propose_action`/`dispatch_tool`/`event_bus`/executor כולם מאומתים כ-0 קריאות בנפרד, mutation יחיד + reads עדיין עובר נורמלי). שני test blocks קיימים ב-`test_pa01_phantom_approval_enforcement.py` שהניחו את התנהגות-BUG-122 הישנה ("הראשון מנצח") עודכנו לשקף את ההתנהגות החדשה המאושרת. **170/170 (170 file לפני, 172 אחרי הוספת 2 test files חדשים) → 172/172 full sweep ירוק**, `smoke_tests.py` ירוק.
- **מאומת ב-git log/diff ישירות מול `main`** (`ceb9148`, ממוזג `59e74be` דרך PR #470) — לא נבדק מול production/staging traffic אמיתי עדיין בזמן המיזוג עצמו.
- **🟡 Staging rebase בוצע, טרם verified (26/07/2026):** `claude/rp5-staging-fault-injection-v4akit` עבר rebase נוסף מעל `main` הכולל את PR #470 (commit `67c595d`, force-push) — כולל שימור מלא של RP5-only hooks (`core/rp5_fault_injection.py`, `tools/dispatcher.py`'s fault-injection hook, `run_agent()`→`_run_agent_impl()` wrapper) ואי-שחזור מכוון של commit-ה-PM460 העצמאי הישן של הענף. Full sweep על הענף המרובייז: 175/175 ירוק (172 + 3 בדיקות RP5-ספציפיות). זהו rebase+test evidence בלבד — **לא** staging-traffic verification. **אימות-staging חי בפועל של BUG-149 עצמו (סבב retest שלישי, אחרי ה-deploy הזה) טרם בוצע** — נדרש deploy ידני של ה-owner ואז re-run של תרחיש 5 לפני שניתן לסמן "VERIFIED IN STAGING" במלואו, לפי "כלל ברזל".
- **סטטוס מעודכן:** ✅ קוד תוקן, ממוזג ל-`main` (PR #470), staging מרובייז ומוכן ל-deploy — טרם אומת מול תעבורת staging אמיתית לאחר ה-deploy הזה ספציפית.

---

> **הערת redaction (BUG-148, BUG-150):** בעקבות security review על PR #477, מזהים תפעוליים גולמיים (Render service ID, contract UUIDs, Airtable record IDs, event-bus action_id, טלגרם handle של הבעלים) הוחלפו כאן ב-aliases יציבים (`RENDER_SERVICE_STAGING`, `CONTRACT_4`, `AIRTABLE_RECORD_3`, `ACTION_ID_3`, `NOTIFY_ID_1`, `FINGERPRINT_1`, `TELEGRAM_CHAT_ID_1`, `TELEGRAM_OWNER_HANDLE`) — אותם aliases בדיוק כמו ב-`SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md`, כך ש-`CONTRACT_4`/`AIRTABLE_RECORD_3` שם ופה מתייחסים לאותה ישות אמיתית. שמות tool (למשל `airtable_add`) לא הוחלפו — הם קבועי קוד פומביים ממילא, וזה בדיוק הממצא של BUG-148. **מגבלה ידועה:** ה-redaction חל על תוכן הקובץ הנוכחי בלבד; הערכים הגולמיים כבר נדחפו להיסטוריית ה-git של הענף הזה בקומיטים קודמים — שכתוב היסטוריה (force-push) לא בוצע כאן ללא אישור מפורש של הבעלים. המיפוי alias↔ערך אמיתי והראיות הגולמיות שמורים אך ורק בקובץ מקומי, git-ignored, שלא שורד מעבר לסשן sandbox זה — הבעלים צריך להחליט היכן לשמר את הראיות הגולמיות לטווח ארוך אם יידרש שחזור.

## BUG-148 — `_describe_contract_for_reconfirmation()` דולפת `tool_name` גולמי ו-Airtable record ID ישירות למשתמש בהודעת reconfirmation ובטקסט-סטטוס legacy — 🔴 נרשם, לא תוקן

- **תאריך:** 27/07/2026.
- **מקור:** בדיקה חיה על staging (`RENDER_SERVICE_STAGING`), לפני שהענף רובייס מול `main` (ראו `docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md` Claim 4). ציטוט מדויק מטלגרם אמיתי: `"יש פעולה קודמת שממתינה לאישור: airtable_add / Tasks. לאשר אותה? (כן/לא)"` וכן `"✅ בוצע: airtable_add / Tasks | מזהה: AIRTABLE_RECORD_3"` (וכנ"ל עבור `AIRTABLE_RECORD_1`, `AIRTABLE_RECORD_2`) — שם ה-tool הגולמי (`airtable_add`) ומזהה הרשומה הגולמי ב-Airtable (`rec...`) מופיעים ישירות בטקסט למשתמש.
- **Contract Chain (אומת ישירות בקוד, כולל על `main`):** `core/action_gateway.py::_describe_contract_for_reconfirmation()` (שורות 821-847), המשמשת גם את פרומפט ה-reconfirmation של `route_confirmation_word()` וגם את טקסט הסטטוס הישן `"✅ בוצע: {label}"` (לפי ה-docstring של הפונקציה עצמה — נסמכת ע"י `test_stage_b_full_suite.py`'s DoD20). עבור כל `tool_name`/`table` שאינו המקרה המיוחד של Leads-capture, הפונקציה מחזירה **`f"{contract.tool_name} / {table}"` גולמי** — ללא שום redaction. זהו fallback **מכוון**, לא תקלה: ה-docstring קובע במפורש "Unchanged by BUG-115... Generalizing this shared function's fallback instead of adding a separate one was tried first and reverted — it silently changed that unrelated, already-tested behavior too." כלומר ניסיון קודם לתקן את זה כבר בוטל בגלל תלות של DoD20 בפורמט הגולמי.
  זהו נתיב **שונה** מזה ש-BUG-118 תיקן (`_safe_contract_business_description()`/`build_approval_lifecycle_result()`, PR #471) — הפונקציה הדולפת קיימת גם **לפני** וגם **אחרי** PR #471, ללא שינוי (`git show <pre-#471-commit>:core/action_gateway.py` מול `main` — זהה byte-for-byte).
- **חומרה:** זהו דליפת מזהה טכני-פנימי אמיתי (raw tool_name + Airtable record ID) — בדיוק סוג הדליפה ש-BUG-118 טוען לסגור "באופן בלתי-מותנה" (`CHANGELOG.md`'s PR #471 entry: "unconditionally removes raw tool names, contract UUIDs, ActionContract record IDs and Airtable business record IDs, including while the rollout flag is off"). הטענה הזו **אינה נכונה** עבור נתיב ה-reconfirmation/legacy-status — סתירה ישירה, לא רק פער-כיסוי.
- **לא אומת:** האם התרחיש (reconfirmation על contract קיים-ותקוע) קורה גם ב-production בפועל — לא נבדק שם ישירות (ה-3 בדיקות שנעשו ב-production לא נתקלו בתרחיש reconfirmation), אבל הקוד זהה, כך שסביר מאוד שאותה דליפה תשוחזר שם אם יקרה אותו תרחיש.
- **כיוון תיקון אפשרי (לא הוחלט, לא מומש כאן):** להעביר את `_describe_contract_for_reconfirmation()`'s ה-fallback דרך `_safe_contract_business_description()` (או `_redact_approval_identifiers()`/`_remove_raw_approval_tool_name()`, שכבר קיימות ומטפלות בדיוק בזה) — דורש קודם לעדכן/לתאם עם `test_stage_b_full_suite.py`'s DoD20 שתלוי כרגע בפורמט הגולמי (ראו ה-docstring שמזהיר מפני זה במפורש).
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain אומתו ישירות בקוד וב-transcript אמיתי.
- **סטטוס:** 🔴 נרשם, Contract Chain אומת ישירות בקוד (כולל אישור זהות בין staging הישן ל-`main`) — **לא תוקן**. ממתין להחלטת הבעלים על עדיפות מול DoD20.

---

## BUG-150 — אישור תקף בן שניות דווח כ"פג/לא קיים" מיד לאחר יצירתו, ונשאר תקוע `pending` כ-14 שעות בלי שאף מנגנון ידע להתריע — 🔴 נרשם, לא תוקן

- **תאריך:** 27/07/2026.
- **מקור:** לוגים אמיתיים מ-staging (`RENDER_SERVICE_STAGING`) + תיאור חי מהבעלים, שניהם מסופקים ישירות ע"י הבעלים — לא נמשכו ע"י sandbox זה (אין לו גישת Render).
- **מה שהבעלים חווה בפועל (בזמן אמת, לא שחזור):** ביקש ליצור משימה ("צור משימה באיירטאבל לפרסם בפייסבוק את המיטות והגיוס"). ה-Agent שאל שאלת הבהרה חופשית (האם "הגיוס" משימה נפרדת או חלק מ"המיטות") — טקסט חופשי בלבד, ללא tool call, ללא contract. הבעלים ענה "משימה אחת". התשובה הזו יצרה בהצלחה `ActionContract` וכפתורי אישור/דחייה אמיתיים נשלחו. **הבעלים ניסה לאשר כמעט מיד** (תוך פחות מדקה) וקיבל: `"ℹ️ הפעולה כבר פגה או אינה קיימת, ולכן לא בוצעה."` — נראה כאילו הפעולה כולה נכשלה/לא קיימת.
- **הרצף המלא בלוגים (מאומת, timestamps אמיתיים):**
  ```text
  2026-07-27 10:33:36 [INFO] core.router.router: [Route] ... intent=create_task ... handler=agent
  2026-07-27 10:33:40 [INFO] core.turn_envelope: [TurnEnvelope] ownership_signal ...
    "tool_use_emitted": false, "reply_owner": "agent", "final_reply_nonempty": true
    # ↑ שאלת ההבהרה — טקסט בלבד, שום contract עדיין
  2026-07-27 10:34:17 [INFO] core.router.router: [Route] ... intent=unknown ... handler=agent
    # ↑ "משימה אחת" — ה-Router לא זיהה אותה כפקודה, נפלה ל-Agent בכל זאת
  2026-07-27 10:34:20 [INFO] core.action_gateway: [ActionGateway] propose_action:
    contract=CONTRACT_4 fingerprint=FINGERPRINT_1
    tool=airtable_add table=Tasks provider=airtable channel=telegram
    status=pending user=TELEGRAM_OWNER_HANDLE
  2026-07-27 10:34:20 [INFO] event_bus: 📥 Pending action registered: ACTION_ID_3 | airtable_add | chat=TELEGRAM_CHAT_ID_1
  2026-07-27 10:34:20 [INFO] app: [Approval] ✅ sent to owner NOTIFY_ID_1 | ACTION_ID_3
  2026-07-27 10:34:20 [INFO] core.turn_envelope: [TurnEnvelope] ownership_signal ...
    "approval_queued": true, "reply_owner": "gateway", "final_reply_nonempty": false
  2026-07-27 10:34:41 [INFO] httpx: HTTP Request: GET .../Emergency%20Stop%20Flags... "200 OK"
    # ↑ ההעדפה: זו התחלת event נכנס חדש (כל handler מתחיל בבדיקת Emergency Stop Flags) —
    # 21 שניות בלבד אחרי שהכפתורים נשלחו, תואם לזמן שלקח לבעלים ללחוץ אשר.
  # --- שום שורת log נוספת (INFO/WARNING) אחרי זה, עד routine UptimeRobot pings ואז
  #     event אמיתי הבא ב-10:44:43 — פער של כ-10 דקות ---
  ```
  `10:34:20`/`10:34:41` הם זמן מקומי (ישראל, UTC+3) = `07:34:20Z`/`07:34:41Z` — תואם במדויק את ה-`contract_id` שכבר תועד ב-`docs/architecture/f52-unified-approval-runtime/rollout/SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md`'s Claim 2.
- **ההוכחה שהאישור מעולם לא נפתר בפועל בניסיון של הבעלים:** אותו מסמך verification plan מתעד שה-contract `CONTRACT_4` בוצע בפועל (עם `external_id=AIRTABLE_RECORD_3` אמיתי) רק ב-`21:40:10Z` — **על ידי session נפרד**, כ-11 שעות אחרי ניסיון הבעלים. מעבר lifecycle מ-`pending` ל-`completed` לא יכול לעבור דרך "בוטל" — כלומר הלחיצה של הבעלים ב-`10:34:41` **לא שינתה את סטטוס ה-contract בכלל**. הוא נשאר `pending`, בלתי-פתור, כשהבעלים קיבל הודעה שגויה שאומרת שאין יותר מה לאשר.
- **למה אין שום שורת log בין `10:34:41` ל-`10:44:43`, אומת בקוד:** `_notify_missing_or_expired_callback()` (`app.py:2079-2090`) — הפונקציה היחידה שמייצרת את הטקסט המדויק הזה — **לא קוראת ל-`logger.info`/`logger.warning` בכלל בנתיב ההצלחה שלה**, רק ל-Telegram API ישירות (`bot.answer_callback_query`/`bot.send_message`/`bot.edit_message_text`). כלומר אם זה הנתיב שרץ, השקט בלוגים הוא **צפוי**, לא ראיה לתקיעה/hang — אבל זה בעצמו ממצא-משנה: הנתיב הזה בלתי-נראה לחלוטין לצורך אבחון עתידי.
- **מנגנון ה-miss עצמו — לא סופי, שתי השערות מבוססות-קוד בלבד:** `event_bus.py`'s `PendingActionsStore` הוא RAM-בלבד (`self._store: dict`), ללא backing חיצוני. שקלתי ונשללה השערת ריבוי-workers: `gunicorn.conf.py` נועל `workers=1`, **מאומת אמפירית** (הרצת `workers=3` אמיתית הראתה 3 workers בפועל, ואז revert) ו**מאומת בפרודקשן** (`WEB_CONCURRENCY=1`, `CHANGE_CONTROL_LOG.md` C159-162) — אין בידוד RAM בין-תהליכי אפשרי כאן מבנית. שתי השערות שנותרות פתוחות:
  1. **Restart/redeploy של staging בדיוק בחלון `10:34:20`-`10:34:41`** — `PendingActionsStore` הוא RAM-בלבד; restart מוחק אותו לגמרי בלי קשר ל-TTL.
  2. **Telegram webhook retry/race** — אם התגובה הראשונה הייתה איטית, Telegram יכול לשלוח שוב את אותו update; שני invocations חופפים של ה-approve handler יכולים להסביר גם את ההודעה השגויה שהבעלים ראה (ה-invocation השני, שמצא שאין מה ל-pop) וגם למה ה-contract נשאר תקוע `pending` (ה-invocation הראשון, החבוי, אולי pop-אה את ה-item ואז נכשל/נעצר באמצע הביצוע בלי לעדכן status).
  אף אחת מהשתיים לא אושרה — דורש בדיקת deploy/restart history של Render לאותו staging service בחלון הזמן המדויק, שרק session עם גישת Render יכול למשוך.
- **Contract Chain (TTL, מאומת ישירות בקוד):** `core/action_gateway.py`'s `find_live_by_user()` (שורות 575-613) מתעד ש-`CONTRACT_PENDING_TTL_SECONDS` הוא 24 שעות במכוון — לא רלוונטי כהסבר ל-miss אחרי 21 שניות, אבל כן מסביר למה שום דבר לא ניקה את ה-contract התקוע באופן אוטומטי במשך 14 השעות שאחרי. גריפ מקיף אחר מנגנון תזכורת יזום (`scheduler.py`, `feature_flags.py`, `core/action_gateway.py`, `app.py`) **לא העלה שום job/flag reminder/nudge לאישורים תלויים**, בניגוד ל-`payment_reminder.py`'s `PAYMENT_REMINDERS` המקביל. ה-mitigation היחיד הקיים (`_format_pending_age_suffix()`, PR #449) פסיבי בלבד — מוצג רק כשמסתכלים על רשימת disambiguation מרובת-פריטים, לא דוחף שום דבר.
- **חומרה:** זה לא "אף אחד לא הזכיר" — הבעלים **ניסה באופן פעיל** לפתור את זה תוך דקה, קיבל מידע שקרי שהפעולה לא קיימת, והפעולה נשארה תקועה בלי שום דרך לדעת זאת עד שסשן נפרד גילה את זה 11 שעות אחר כך. זה חמור משמעותית מפער-תזכורת גרידא.
- **לא אומת (במקור):** מנגנון ה-miss המדויק (restart מול race — שתי ההשערות לעיל); האם זה משוחזר ב-production; האם זה קורה שוב בתדירות כלשהי.
- **כיוון תיקון אפשרי (לא הוחלט, לא מומש כאן):** (1) לזהות ולסגור את מנגנון ה-miss המדויק ברגע שיש evidence — לא ניתן לתקן root cause לא-מאומת; (2) להוסיף `logger.warning` ל-`_notify_missing_or_expired_callback()` כדי שהמקרה הבא יהיה נראה בלוגים; (3) job מתוזמן שמתריע יזומה כש-pending contract עובר סף גיל קצר בהרבה מ-24 שעות — דורש החלטת בעלים על סף/UX.
- **היקף:** לא נגעתי בקוד. ממצא + Contract Chain אומתו ישירות בקוד; הלוגים והתיאור החי סופקו ישירות ע"י הבעלים, לא נמשכו עצמאית מ-Render בסשן הזה.

- **עדכון (27/07/2026, סשן עם גישת Render) — מנגנון ה-miss נחקר ישירות:**

  1. **השערה #1 (restart/redeploy בחלון) — נשללה בוודאות.** `GET /v1/services/{id}/events` (Render API) מראה פער נקי, ללא שום `deploy_started`/`deploy_ended`/`build_started`/`build_ended`/`server_restarted`, מ-`2026-07-26T15:01:41Z` ועד `2026-07-27T21:15:54Z` — כ-6 שעות **לפני** החלון וכ-13 שעות **אחריו**, ללא אירוע יחיד. אומת גם ישירות מול deploy history: commit `67c595d5a128541dc4b29db1482e1eb236289016` היה `live` ברציפות דרך כל התקרית.

  2. **תיקון קריטי לעוגן-הזמן שהתיעוד המקורי הסתמך עליו:** השורה `07:34:41Z [INFO] httpx: GET .../Emergency Stop Flags...` **אינה** קשורה בפועל ללחיצת הבעלים — זו הרצה שגרתית של `scheduler.py`'s `_job_interaction_scan()` (D06, "כל 15 דקות" לפי ה-docstring שלה, `scheduler.py:433-437`). הוכחה: אותו זוג-שורות מדויק (GET ל-Emergency Stop Flags ואחריו `[D06] interaction intelligence disabled by env`, `scheduler.py:437`) חוזר ב-`07:04:35Z`, `07:19:40Z`, `07:34:41Z`, `07:49:46Z` — כל 15 דקות בדיוק, ללא שום קשר לפעילות אישורים. כלומר **אין בידינו יותר את התזמון המדויק** של לחיצת הבעלים — רק את ההערכה שלו עצמו ("ניסה לאשר כמעט מיד", תוך פחות מדקה).

  3. **סריקת לוגים מלאה ולא-מסוננת של השעה כולה (`07:00:00Z`-`08:00:00Z`, כל type=app log) לא מעלה שום עקבה** — לא רק להיעדר-הלוג הידוע כבר של `_notify_missing_or_expired_callback()`'s success path, אלא **גם** להיעדר כל עקבה חלופית: קריאה מוצלחת ל-`EventBus.confirm()` הייתה מייצרת `"✅ Confirmed and executed: {action_id} | {action}"` (`event_bus.py:317`, בקוד שהיה live באותו רגע) — שורה כזו **לא קיימת** בשום מקום בשעה כולה. אם ה-item אכן נצרך ע"י משהו, גם הצריכה עצמה בלתי-נראית.

  4. **שלושה מנגנוני-miss נוספים (מעבר לשתי ההשערות המקוריות) נבדקו ונשללו ישירות מהקוד שהיה live בפועל** (`git show 67c595d5a1:event_bus.py`/`scheduler.py`/`gunicorn.conf.py`):
     - **פקיעת TTL:** `PENDING_TTL_MINUTES = 30` (`event_bus.py:26`) — הרבה מעבר לחלון של כ-דקה; ופקיעה-ב-pop מייצרת שורת log ייעודית משלה (`"⏰ Pending action expired at pop"`, `event_bus.py:78`) שלא הופיעה.
     - **פינוי לפי קיבולת (LRU/max-size):** לא קיים — `PendingActionsStore._store` הוא `dict` לא-חסום ללא מגבלת גודל.
     - **job הניקוי המתוזמן** (`_job_cleanup_pending`, כל `CLEANUP_INTERVAL_MIN`=360 דק' כברירת מחדל, `scheduler.py:20-25,813`): שומר על בדיקת TTL תקינה ומייצר `"🧹 Cleaned N expired pending actions"` (`event_bus.py:178`) כשהוא בפועל מנקה משהו — שורה כזו לא הופיעה בשעה כולה.
     - **race בין-thread-י בתוך התהליך:** `gunicorn.conf.py` נועל `workers = 1` **וללא** override ל-`threads`/`worker_class` — כלומר worker סינכרוני ברירת-מחדל, single-threaded לגמרי. שני invocations חופפים באותו RAM אינם אפשריים מבנית תחת התצורה הזו.
  5. **`getWebhookInfo`** (Telegram Bot API, נבדק בפועל עם ה-token האמיתי של staging) מראה `last_error_date=None`/`pending_update_count=0` — אך זה **לא-קונקלוסיבי** לחלון ההיסטורי: Telegram שומר רק את השגיאה **האחרונה**, ומאז החלון עברו עשרות deploys/בדיקות נוספות שהיו יכולות לדרוס כל שגיאה קודמת.
- **לא אומת (עדכני):** לאחר שלילת חמשת המנגנונים לעיל (restart, TTL, קיבולת, cleanup job, race בין-thread-י), ה**השערה היחידה שנותרה סבירה בעיני exclusion היא Telegram webhook retry/duplicate delivery** (השערה #2 המקורית) — אך היא נותרת בלתי-ניתנת-לאישור מה-sandbox הזה: `GET /v1/logs` של Render חושף רק `type=app` לשירות הזה; `type=request` (ונסיונות `type` אחרים) מחזיר תגובה ריקה (`{"hasMore":false,"logs":null}`) ולא שגיאה — כלומר אין access-log/HTTP-level log stream נפרד חשוף ב-API הזה לאימות ישיר של POST כפול. אישור סופי ידרוש שחזור-חי מבוקר עם diagnostic זמני (לוג ל-`update.update_id` הגולמי של כל POST נכנס, בדומה לדפוס ה-temp-diagnostic-reviewed-and-reverted ששימש לאימות Claim 3 במסמך ה-verification plan) — לא בוצע כאן ללא אישור בעלים מפורש.
- **סטטוס:** 🔴 נרשם, Contract Chain אומת ישירות בקוד, evidence חי ומתוארך קיים. **חמישה מנגנוני-miss אפשריים נבדקו ונשללו ישירות מהקוד/מ-Render API בפועל (restart, פקיעת TTL, פינוי-קיבולת, cleanup job, race בין-thread-י)** — נותרה השערה אחת בלבד (Telegram webhook retry/duplicate), בלתי-מאושרת אך הסבירה היחידה שנותרה. עוגן-הזמן `07:34:41Z` המקורי תוקן — אינו קשור בפועל לתקרית. **לא תוקן, root cause הסופי (אישור Telegram-side) עדיין פתוח**, ממתין להחלטת בעלים על שחזור-חי מבוקר אם רוצים סגירה מלאה.

---

## ממצא תכנוני (ללא מספר BUG) — Cost Telemetry Coverage and Per-Turn Attribution

> ממצא-תשתית (coverage gap במדידת עלות), לא regression בהתנהגות קיימת ולא סיווג-באג — נשאר ללא מספור עד להחלטה על תוכנית מימוש. נפרד לחלוטין מ-BUG-141 ומ-PR של approval callbacks (BUG-144/145/122).

- **תאריך:** 24/07/2026.
- **מקור:** Cost Watchdog הפיק את התראת-ה-runtime החיה הראשונה שלו לאחר תיקון השבוע (`⚠️ Cost Alert — עלות שעה: $0.78 עברה את הסף $0.25`).
- **Positive finding (runtime PASS):** `cost_monitor.py`'s `check_thresholds()`/`_send_hourly_alert()` מאומתים כעובדים כמתוכנן — אוספים עלות, משווים לסף, מפיקים התראה למשתמש, **לא** עוצרים מיד את השירות (`_trigger_daily_stop()` נפרד לגמרי, לא הופעל). `COST_HOURLY_LIMIT` ברירת המחדל הוא `$5.0` (`cost_monitor.py:27`) — הסף `$0.25` שנצפה מרמז על override מכוון ב-staging (סף נמוך לבדיקת המנגנון עצמו).
- **Risk finding (amplification, לא מכומת עדיין ברמת הודעה בודדת):** `cost_monitor.record_call()` — הפונקציה היחידה שמזינה את ה-live accumulator שהפיק את ההתראה — נקראת ממקום יחיד בכל הריפו: `app.py:3174`, בתוך ה-`while True:` tool-loop של `run_agent()` (עד `MAX_TOOL_TURNS=3`, `app.py:77`). מכאן שני ממצאים מאומתים:
  1. turn יחיד יכול להפיק עד 3 קריאות Claude נפרדות ומתומחרות-במלואן, כולן נספרות לאותו hourly bucket ללא קיבוץ לפי turn.
  2. `daily_collector.py` (`llm_fallback.call_anthropic_text`) ו-`interaction_engine.py:232` (`record_llm_usage()` ישיר) **לא** קוראים ל-`cost_monitor.record_call()` בכלל (אומת בגריפ, 0 תוצאות) — עלותם מגיעה רק ל-`core/usage_telemetry.py`'s `usage_events`, שהוא **shadow-only** במפורש (nothing reads from it yet). מסקנה: התראת ה-`$0.78` היא 100% עלות `run_agent()` (Daily Collector נשלל כתורם להתראה הזו ספציפית), אך אותה סיבה הופכת את Daily Collector לבלתי-נראה גם ל-daily Emergency Stop.
  3. `caller` (`app.py:3178`) מועבר ל-`record_call()` אך מגיע רק ל-`logger.debug()` — `_hourly_cost`/`_daily_cost` הם float גלובלי בודד ללא breakdown לפי source/model/turn.
- **אין לקבוע** ש-TurnCoordinator לבדו יפתור את בעיית העלות — הוא עשוי לצמצם כפילות-turn וניתוב שגוי, אך אינו מודד או מתקן context loading (Business Memory), retries, או עלות scheduler/collector tools.
- **Fix shape עתידי בלבד (הצעה, ללא מימוש):**
  1. correlation ID (`turn_id`/`job_id`) משותף לכל קריאות ה-LLM/tools של אותו turn/job.
  2. accumulator משותף לכל מסלולי LLM (כיום שלושה מסלולי רישום נפרדים ב-`run_agent()` בלבד, ומסלול חלקי דרך `llm_fallback.py`).
  3. breakdown לפי source/model/turn ב-`cost_monitor.py`'s ה-accumulator החי (לא רק ב-`usage_telemetry`'s shadow table).
  4. מדדי `llm_calls_per_turn`/`tool_calls_per_turn`/`cost_per_turn` (הבסיס `tool_calls_made` כבר קיים מקומית ב-`run_agent()`).
  5. התראה עם top-3 turns/jobs יקרים בחלון (דורש buckets פר-turn, לא קיימים כיום).
  6. guard נגד מספר חריג של LLM/tool calls באותו turn (`MAX_TOOL_TURNS=3` הוא תקרה טכנית קיימת, לא אות-חריגה נפרד).
  7. הפרדת עלות Staging sampling מתעבורה אורגנית (אין תיוג `source`/`meta` שמבדיל כיום — כל תעבורת בדיקות staging נספרת זהה ל-production).
- **היקף:** לא נגעתי בקוד. ממצא מבוסס קריאת קוד ישירה (`cost_monitor.py`, `core/usage_telemetry.py`, `app.py`, `daily_collector.py`, `llm_fallback.py`, `interaction_engine.py`).
- **סטטוס:** ממצא תכנוני, ללא מספר BUG. ממתין להחלטה אם למספר כבאג רשמי או להשאיר כתוכנית-תשתית עד לעיצוב מימוש.

---

## BUG-151 — "כן" בלי live contract שיחזר `ActionContract` לא-קשור/ישן ("הפעולה כבר הושלמה"); `CanonicalizationError` ב-`sheets_append`→`airtable_add` ל-Tasks הרג turn בלי ליצור contract — ✅ תוקן

- **תאריך:** 29/07/2026.
- **מקור:** תרחיש staging אמיתי, נתפס תוך כדי audit קבלה ל-PR2 (`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`) — root-caused מלוגי Render בפועל (`my-bot-jqz2.onrender.com`) + רשומות `ActionContracts` בבסיס Airtable הראשי (`app4bcgoX7t0HUVnm`), מתואם turn-by-turn (timestamps מדויקים, contract IDs אמיתיים).
- **הרצף שנתפס בפועל:** בקשת "צור משימה באיירטאבל" נכשלה פעמיים (10:49, 10:53) — `sheets_append` נבחר ע"י ה-Agent (למרות בקשה מפורשת ל-Airtable), `resolve_canonical_tool()` ניסה להמיר ל-`airtable_add` כראוי, אבל `_sheets_payload_to_airtable()` תמך רק בערך positional אחד (כותרת) — payload בפועל כלל 2 (כותרת+תאריך יעד) → `CanonicalizationError: no explicit positional converter for Airtable table 'Tasks'` בשתי הפעמים, **לפני** כל ניסיון persistence — אף `ActionContract` לא נוצר. המשתמש ענה "כן" לשאלת-המשך חופשית של ה-Agent (לא של ה-Gateway) — בלי live contract, `_resolve_pr2_deterministic_approval()` נפל ל-`find_recent_terminal_by_user()` (24h) ומצא contract **לא-קשור לחלוטין**: ליד שהושלם ~4 שעות קודם. השיב "הפעולה כבר הושלמה" — הודעה מטעה שלא קשורה לבקשה בכלל, ואף task לא נוצר.
- **שני מנגנוני-שורש, לא אחד:** (1) `_sheets_payload_to_airtable()`'s positional converter צר מדי (1 ערך בלבד ל-Tasks). (2) `_resolve_pr2_deterministic_approval()`'s bare-confirm-word branch משתמש ב-recency (`find_recent_terminal_by_user`) כאילו זו correlation — recency **אינה** correlation, בשום חלון (נבדק גם עם חלון-ביניים של 10 דקות — עדיין היה משחזר: contract לא-קשור בתרחיש-אימות נפרד היה בן ~20 שניות בלבד).
- **תיקון (PR #494, `claude/pr2-staging-acceptance-audit-7n9f2p`, ממוזג `186832a` — פירוט מלא ב-`CHANGE_CONTROL_LOG.md` C181):**
  1. `_sheets_payload_to_airtable()` תומך עכשיו ב-1 או 2 ערכים positional ל-Tasks.
  2. `_queue_approval_detailed()` תופס `CanonicalizationError` בנפרד (`terminal_outcome=APPROVAL_QUEUE_NEVER_ATTEMPTED`) — לא נספר נגד תקציב ה-mutation של BUG-122, כדי שניסיון-חוזר לגיטימי (tool אחר) לא ייחסם בטעות.
  3. `_resolve_pr2_deterministic_approval()`'s בענפי "כן"/"אשר"/"לא"/"דוחה"/"מבטל" בלי live contract לא קוראים ל-`find_recent_terminal_by_user()` כלל יותר — תמיד תשובת no-pending קנונית, אפס mutation, אפס קריאת Agent. "יצרת?" (שאילתת סטטוס מפורשת) נשאר ב-24h ללא שינוי — ההבחנה: שאלת-סטטוס יזומה שונה מהותית מתגובת-אישור סתמית.
- **בדיקות:** `test_bug_canonical_tool_wiring.py`, `test_pr2_deterministic_approval_cost_cuts.py` (כולל שחזור-אירוע מלא + sweep גילאים 5s/20s/9min), `test_pa01_phantom_approval_enforcement.py` — כולם ירוקים. Full sweep 175/175 + `smoke_tests.py`/`test_integration.py`/`core/router/test_router.py` (44/44) + `py_compile`.
- **✅ Verified ב-staging (29/07/2026, `my-bot-jqz2.onrender.com`, contract `a428e48b-3b57-473a-b647-e8225e08d3b6`, 14:25–14:29) — עם הסתייגות מדויקת, לא claim גורף:** רצף-אימות **קרוב אך שונה** מהאירוע המקורי — `ActionContract` **כן נוצר** הפעם (בקשה נפרדת שבחרה `calendar_create_event`, לא `sheets_append`/`airtable_add` — לא אותו נתיב-קוד בדיוק של תיקון #1), אושר, **הביצוע עצמו נכשל** (`❌ חסרים פרטי Google OAuth` — פער-סביבה, לא קוד) → status סופי `failed`. "כן" הבא, בלי live contract (כי `failed` הוא terminal), החזיר נכון "אין פעולה שממתינה לאישור" — **לא שחזר את ה-contract הכושל**. זה מאמת את אינווריאנט תיקון #3 (bare "כן" בלי live contract לעולם לא משחזר terminal contract, יהיה מקור-הכשל אשר יהיה) בנתיב-כשל **שונה** מהמקורי. **לא מאמת עצמאית** את תיקון #1 הספציפי (positional canonicalization) — נדרש תרחיש שבאמת יגרום ל-`CanonicalizationError` (Agent בוחר `sheets_append` עם payload רב-ערכי) כדי לסגור את הפער הזה.
- **פתוח לפר הבא (לא מהמחלקה הזו של הבאג, זוהו באותו audit):** Router regex ל-"תייצר" (create_task intent); אכיפת Single-Speaker בפועל (`is_gateway_owned_leak` היום log-only ב-`core/turn_envelope.py`, לא מדכא בפועל); הסתרת `sheets_append`/`drive_*` מרשימת הכלים כברירת מחדל; מסלול cancel ישן (`app.py:3391`, BUG-056) שעדיין לא מעביר `recent_terminal=None` — ממצא CodeRabbit, אותה מחלקת-באג בדיוק, פעיל כברירת מחדל כש-PR2 כבוי; ולידציית פורמט תאריך-יעד ב-`_sheets_payload_to_airtable`.
- **תוספת (30/07/2026) — אימות חי בפרודקשן, `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`/`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`/`FEATURE_ACTION_GATEWAY` שלושתם `true`:** הבעלים הריץ בקשה אמיתית — "צור משימה באיירטאבל: להתקשר לספק, עד יום חמישי" — נוצר `ActionContract` (`tool=airtable_add`, `table=Tasks`, `status=pending`) עם כותרת ותאריך יעד נכונים, **ללא `CanonicalizationError`**. המסלול העסקי (יצירת משימה עם תאריך יעד) עבר מקצה לקצה. **הסתייגות מדויקת, כמו בסבב 29/07:** ה-Agent בחר הפעם `airtable_add` ישירות, לא `sheets_append` — כך שהממיר הספציפי `_sheets_payload_to_airtable()`'s תמיכת 1-או-2-ערכים positional (תיקון #1) **עדיין לא נבדק חי בנתיב-הקוד המדויק שלו**; נשאר מאומת בבדיקת יחידה בלבד (`test_bug_canonical_tool_wiring.py`). ראו `CHANGE_CONTROL_LOG.md` C181 (תוספת) לפירוט המלא.
- **סטטוס:** ✅ תוקן ומאומת ב-staging (עם ההסתייגות המדויקת לעיל). **Verified בפרודקשן:** חלקי — תיקון #3 (guard ה-replay) אומת חי בנפרד (29/07, ראה למעלה). ה-**יכולת העסקית הכללית** (יצירת Tasks עם תאריך יעד, קצה-לקצה) אומתה חי 30/07/2026 — אך זו **לא** אימות של תיקון #1 (הממיר) או תיקון #2 (חריגת mutation-budget), ששניהם דורשים `CanonicalizationError` בפועל כדי להיבדק, וזה לא קרה. הממיר הספציפי `sheets_append→airtable_add` (תיקון #1 בבידוד) עדיין לא נצפה חי.

---

## BUG-152 — בקשה חוזרת/דומה נעצרה פעם אחת ע"י ה-Agent ונוצר כרטיס אישור רק בשליחה חוזרת — 🔴 נרשם, לא תוקן

- **תאריך:** 30/07/2026.
- **מקור:** נצפה תוך כדי סבב אימות חי ל-PR2 (Test 2, ראו BUG-151 תוספת 30/07/2026 למעלה) — לא תרחיש מבודד/משוחזר, נצפה כתופעת-לוואי של בדיקה אחרת. **לא root-caused עדיין.**
- **הרצף שנצפה:** לאחר ביטול משימה שנוצרה בבדיקת BUG-151 (Test 2), הבעלים שלח בקשה חדשה דומה (יצירת משימה נוספת). הבקשה **נעצרה פעם אחת** ע"י ה-Agent — לא נוצר כרטיס אישור, לא הוחזרה שגיאה מפורשת (לפי דיווח הבעלים; לא אומת מול לוג Render בפועל). רק לאחר **שליחה חוזרת** של אותה בקשה (או דומה) נוצר כרטיס אישור תקין.
- **השערות שורש אפשריות, אף אחת לא אומתה:**
  1. השפעת היסטוריית-שיחה על החלטת ה-Agent — ייתכן שהביטול הטרי (contract שזה עתה נדחה/בוטל) גרם למודל "להסס"/לפרש את הבקשה החדשה כהמשך של הביטול, לא כבקשה עצמאית.
  2. שער דדופ/fingerprint (`executed_action_cache`, BUG-122 mutation budget, או `MULTI_MUTATION_CONTEXT_MISMATCH` מ-BUG-149) חסם בטעות ניסיון לגיטימי שנראה דומה מדי לפעולה שזה עתה טופלה.
  3. Race/timing גרידא (Session state עוד לא התעדכן מהביטול הקודם כש-turn הבא התחיל).
- **היקף:** לא נגעתי בקוד. תיעוד בלבד לפי בקשת הבעלים — "מומלץ לתעד זאת כממצא נפרד".
- **דרוש כדי לתקדם:** שחזור מבוקר (לוג Render מלא של שני ה-turns — הביטול והבקשה החדשה שנעצרה — לא רק דיווח מסוכם), כדי לקבוע אם מדובר בהתנהגות #1/#2/#3 לעיל או במשהו אחר לגמרי.
- **סטטוס:** 🔴 נרשם, לא תוקן, לא root-caused. אין מספר PR/commit משויך.

---

## BUG-153 — בקשת create חדשה אחרי rejection נחסמת

- **דווח:** 3 באוגוסט 2026
- **סביבה:** Staging — `my-bot-approval-staging`, בסיס `בסיס עיקרי`
- **מסך / מודול:** `core/action_gateway.py` — `propose_action()`, rejected replay guard, lookup לפי business_action_fingerprint
- **הרצף שנצפה:** לאחר שהמשתמש ביטל (דחה) פעולה, שליחה חדשה ומפורשת של אותה בקשה (בקשת "create" חדשה ומפורשת מהמשתמש) נחסמה שוב ושוב.
  - תשובת הבוט: "יצירת המשימה כבר בוטלה"
  - לוג: `[ActionGateway] propose blocked: business action already rejected contract=665a3d2d-acf8-45f9-af0e-84abc1d03b75`
  - בהמשך: `[DeterministicCreateTask] created_this_turn=False reply_owner=None`
- **Severity:** גבוהה
- **Root Cause:** `ActionGateway` משתמש ב-`business_action_fingerprint` של ה-contract שנדחה כדי לחסום כל ניסיון עתידי זהה. אין הבחנה בין:
  - replay אוטונומי (צריך להישאר חסום)
  - turn חדש שמכיל בקשת create מפורשת מהמשתמש (צריך ליצור contract חדש)
- **דרישת תיקון:** יש לשמר את אותו fingerprint, אך להוסיף הבחנה בין autonomous replay לבין explicit new user request. בקשת משתמש חדשה ומפורשת צריכה ליצור contract חדש (`ActionContract.status = pending`), בעוד ה-contract הישן נשאר terminal (`status = rejected`).
- **קריטריוני סגירה:**
  - contract שנדחה נשאר ב-status `rejected`
  - בקשת create חדשה ומפורשת יוצרת `ActionContract` חדש בstatus `pending`
  - autonomous replay עדיין חסום
  - אותו fingerprint נשמר (לא משתנה כדי לעקוף את ההגנה)
- **חשוב — קונפליקט עם תיעוד קיים, נמצא ב-04/08/2026:** `docs/architecture/
  action-gateway/DETERMINISTIC_TASK_ROUTING_AND_REPLAY_POLICY_20260802.md`
  (מוזג עם PR #546 עצמו) קובע במפורש שה-blocking **מכוון** ("must not weaken
  fingerprint deduplication"), ושפתיחה-מחדש דורשת "a separately approved
  reconfirmation policy" שמעולם לא עוצבה. הועלה ל-owner (04/08/2026) —
  ההחלטה: **לעצב policy כזו** (לא Won't-Fix, לא רק לתעד).
- **עיצוב + תיקון (04/08/2026):** ראה
  `docs/architecture/action-gateway/BUG-153_CREATE_TASK_EXPLICIT_RECONFIRMATION_POLICY_20260804.md`
  ל-Cross-Layer Impact Matrix מלא. תמצית: ערך `trusted_source` חדש
  (`"deterministic_create_task"`) מוגדר ב-`_queue_deterministic_create_task()`
  בלבד (Python קוד מהימן, לעולם לא מ-tool_inputs/טקסט משתמש) — `propose_action()`'s
  ה-rejected-branch מבחין בין `trusted_source == "deterministic_create_task"`
  (מותר, פותח contract חדש; ה-contract הישן נשאר `rejected` ללא שינוי) לבין
  כל trusted_source אחר, **כולל `"agent"`** (autonomous replay — ממשיך
  להיחסם ללא תנאי, בדיוק כמו היום). בטוח כי: (1) idempotency guard קיים
  כבר במעלה הזרימה (`app.py:5247`) מסנן webhook redelivery לפני
  `route_request()`; (2) המסלול הדטרמיניסטי לא יכול "להחליט" לבד לחזור על
  עצמו (regex על טקסט נכנס של ה-turn הנוכחי בלבד, לא Agent tool_use loop);
  (3) ה-fingerprint עצמו לא משתנה. `_queue_deterministic_task_update()`
  (UPDATE_TASK/COMPLETE_TASK) **לא** כלול ב-carve-out — scope מוצהר,
  create_task בלבד.
- **בדיקות:** `test_bug153_create_task_reconfirmation_after_rejection.py`
  (חדש, 11/11 — כולל regression מפורש ש-`trusted_source="agent"` ו-כל
  trusted_source אחר נשארים חסומים), `test_create_task_deterministic_route.py`
  (13/13, ללא שינוי), `test_bug_canonical_tool_wiring.py` (52/52, ללא שינוי),
  `test_bug091_source_trust_boundary.py` (10/10, ללא שינוי),
  `core/router/test_router.py` (44/44, ללא שינוי), `smoke_tests.py`,
  `test_integration.py` (4/4) — כולם ירוקים.
- **Merged:** ✅ כן — PR #550, מוזג ל-`origin/main` (`e26de4a`) (עודכן
  07/08/2026 — אומת: `git merge-base --is-ancestor e26de4a origin/main`)
- **Deployed:** ✅ כן — Render: "Deploy live for `44fe0fb`" (07/08/2026,
  11:34); `e26de4a` הוא ancestor מאומת (`git merge-base --is-ancestor
  e26de4a 44fe0fb`)
- **Verified בפרודקשן (07/08/2026 14:22-14:23, owner, `my-bot-approval-
  staging` Render logs):** ✅ **כן.** נשלח "צור משימה בדיקת 156 עד
  12-08-26 בשעה 14:54" בטלגרם, נדחה (14:23:17), ואז נשלחה **אותה בקשה
  בדיוק** שוב (14:23:23). הלוג מצטט במפורש:
  ```
  [ActionGateway] BUG-153 reconfirmation מפורש: פותח contract חדש לבקשת
  create_task דטרמיניסטית ש-fingerprint שלה תואם contract שנדחה=
  2b5a0c55-62db-43c4-9faf-a9222c03638a fingerprint=26195bce6309
  user=boss_hq:eliyahu.
  ```
  contract חדש (`47d6b0b7-0571-4e3f-b7ea-aeee6a6164bb`) נפתח מיד
  (`status=pending`), בעוד ה-contract הישן (`2b5a0c55-...`) נשאר
  `rejected` — בדיוק ההתנהגות שהתיקון מבטיח: explicit reconfirmation
  נפתח, autonomous replay עדיין נחסם.
- **אימות עצמאי שני (07/08/2026 13:58):** אותה תופעה שוחזרה בתרחיש נפרד —
  `contract=389acb7a-df6f-43b6-afdf-d0a9ed547bbd` נדחה (13:58:21),
  אותה בקשה נשלחה שוב, `fingerprint=ef2894380762` — אותו לוג "BUG-153
  reconfirmation מפורש", contract חדש `35fae4fe-cc0e-4d42-9600-
  5297406a505a` נפתח. שני מופעים עצמאיים, שני fingerprints שונים.
- **סטטוס:** ✅ **VERIFIED IN PROD** — merged (`e26de4a`→`44fe0fb`) +
  deployed (Render, 07/08/2026 11:34) + production-verified (owner,
  שני מופעים עצמאיים: 07/08/2026 13:58 ו-14:23, לוגים אמיתיים מצוטטים
  למעלה)

---

## BUG-154 — ניסוח "ל־תאריך" מפיל את parser

- **דווח:** 3 באוגוסט 2026
- **סביבה:** Staging — `my-bot-approval-staging`, בסיס `בסיס עיקרי`
- **מסך / מודול:** `core/router/router.py`, פונקציה `parse_deterministic_create_task()`
- **קלט ששיחזר את הבאג:**
  ```text
  צור משימה לבדוק את אימות 546 המעודכן, ל־5/8/26 בשעה 10:30
  ```
- **הרצף שנצפה:**
  - התנהגות צפויה: parsing דטרמיניסטי תקין, `intent=create_task`, `handler=tool`, CanonicalActionProposal תקין, ActionContract בstatus `pending`
  - התנהגות בפועל: Parser קרס עם `AttributeError: 'NoneType' object has no attribute 'start'`
  - Stack trace: `parse_deterministic_create_task` → `if date_marker.start() > date_match.start():`
- **Root Cause:** `date_marker` הוא תוצאה של `re.search(r"\bעד\b", body)` —
  מחפש את מילת-הסימון "עד" בלבד, לא "ל־". הקלט משתמש ב-"ל־" כמסמן-תאריך
  במקום "עד", ולכן `date_marker` הוא `None`, בעוד `date_match` (שמזהה את
  צורת התאריך `5/8/26` עצמה, ללא תלות ב-marker) כן נמצא. `parse_
  deterministic_create_task()` קורא ל-`date_marker.start()` בלי לבדוק
  קודם שהוא לא `None`.
- **Fallback לאחר ההקרסה:** המערכת עברה ל-fallback: `intent=unknown`, `handler=approval`, `confidence=0.00`, rule='fallback'. מציגה approval כללי ללא details:
  ```text
  הפרטים המדויקים ייקבעו כשאכין את הפעולה בפועל
  ```
  זה אינו CanonicalActionProposal תקין.
- **Severity:** גבוהה
- **דרישת תיקון:**
  - להגן על שימוש ב-`date_marker.start()` עם בדיקת None
  - לתמוך ב-"ל־5/8/26" ובגרסאות Unicode דומות
  - במקרה parse failure יש להחזיר clarification בלבד, לא generic approval
  - זה fail-closed requirement: create_task צריך להיות בטוח או clarification, לעולם לא fallback approval לא-בטוח
- **קריטריוני סגירה:**
  - "ל־5/8/26" עובר parse תקין ללא exception
  - אין AttributeError
  - אין generic approval fallback
  - parse failure אמיתי מחזיר clarification בלבד
- **תוקן (04/08/2026):** `date_marker` נבדק כעת גם מול `None` בלי exception,
  ונוסף מסמן חלופי — "ל" + מקף עברי/hyphen/en-dash/em-dash, נבדק **רק** צמוד
  (עם רווח אופציונלי) ממש לפני `date_match.start()` עצמו, לא חיפוש גלובלי
  (ש"ל" הוא אות עברית נפוצה מדי). אם לא נמצא שום marker — `uncertain=True`
  (fail-closed, clarification), לא crash. ראה
  `docs/architecture/action-gateway/BUG-154_CREATE_TASK_DATE_MARKER_PARSER_CRASH_FIX_20260804.md`
  ל-Cross-Layer Impact Matrix.
- **בדיקות:** `test_bug154_date_marker_prefix_parser.py` (חדש, 15/15 —
  כולל שחזור מדויק של ה-crash [נכשל על הקוד הישן], גרסאות Unicode
  ל-hyphen/en-dash/em-dash, regression ל-"עד" הקיים, ו-fail-closed
  ל-date-shaped-token-בלי-marker), `core/router/test_router.py` (44/44,
  ללא שינוי), `test_create_task_deterministic_route.py` (13/13, ללא
  שינוי), `smoke_tests.py`, `test_integration.py` (4/4) — כולם ירוקים.
- **Merged:** ✅ כן — PR #550, מוזג ל-`origin/main` (`e26de4a`) (עודכן
  07/08/2026)
- **Deployed:** ✅ כן — Render: "Deploy live for `44fe0fb`" (07/08/2026,
  11:34); `e26de4a` הוא ancestor מאומת.
- **Verified בפרודקשן (07/08/2026 13:59, owner, `my-bot-approval-staging`
  Render logs):** ✅ **כן.** נשלח "צור משימה בדיקת 154 ל־12/8/26" — בדיוק
  הצורה שגרמה במקור ל-`AttributeError` (מרקר "ל־" בלי "עד", עם תבנית
  תאריך `12/8/26`). הלוג: `intent=create_task risk=needs_approval
  handler=tool`, ActionContract חדש נוצר (`56e0a99a-ff29-41f7-a1a2-
  026bcfa336de`, `status=pending`), ו-`[DeterministicCreateTask]
  agent_calls=0 created_this_turn=True reply_owner=gateway` — אין
  exception, אין נפילה ל-fallback כללי.
- **סטטוס:** ✅ **VERIFIED IN PROD** — merged (`e26de4a`→`44fe0fb`) +
  deployed (Render, 07/08/2026 11:34) + production-verified (owner,
  07/08/2026 13:59, לוג אמיתי מצוטט למעלה)

---

## BUG-155 — TTL expiry אינו סוגר את ה־ActionContract

- **דווח:** 3 באוגוסט 2026
- **סביבה:** Staging — `my-bot-approval-staging`, בסיס `בסיס עיקרי`
- **מסך / מודול:** TTL callback handler, ActionContract lifecycle transition
- **הרצף שנצפה:**
  - התנהגות צפויה: כאשר approval פג תוקף:
    - המשתמש מקבל הודעת expiry
    - ה-ActionContract עובר למצב terminal כגון `expired`
    - הוא אינו נספר כ-live contract
    - הוא אינו חוסם פעולות חדשות
    - לא ניתן לאשר אותו מאוחר יותר
  - התנהגות בפועל:
    - המשתמש קיבל: `פג תוקף — הפעולה לא בוצעה`
    - לוג: `[Approval] TTL-expired Telegram callback: action_id=513fbb08 tool=airtable_add — not executed`
    - אבל ה-contract נשאר חי (`pending`)
    - `pending_gate_decision=block_new_action` ו-`live_contracts_count=1`
    - בקשה חדשה נחסמה: `יש לך כרגע 1 בקשות הממתינות לאישור`
    - לאחר מכן ה-contract הישן חזר ל-reconfirmation ובסופו בוצע
    - אותו contract (ID: 71443fe1-0f94-44a3-986e-54b506f0759d) עבר: `approved` → `Claim acquired` → `Execution succeeded` → `outcome=completed`
- **Root Cause:** מסלול expiry משפיע על callback או UI בלבד, אך אינו מבצע transition מלא של ה-ActionContract למצב terminal. סתירה:
  - למשתמש נאמר שהפעולה אינה זמינה
  - backend ממשיך להתייחס אליה כ-pending
- **Severity:** קריטית או גבוהה מאוד
- **אזורים חשודים:**
  - TTL callback handler
  - ActionContract lifecycle transition
  - pending contract query בתוך live contracts
  - live contract count calculation
  - pending lock cleanup
- **דרישת תיקון:** ב-TTL expiry יש לבצע transition אטומי: `pending → expired`, ולוודא:
  - removal מ-live contracts collection
  - cleanup של pending lock
  - אי־אפשרות reconfirmation
  - callback נוסף אינו מבצע פעולה
- **קריטריוני סגירה:**
  - expiry מעביר contract ל-terminal status
  - ה-contract שפג נעדר מ-`find_live_contracts()` (contract-scoped — הספירה
    הכוללת של live contracts יורדת בדיוק באחד, לא נדרשת ל-0 גלובלית; ל-
    identity יכולים להיות live contracts אחרים, לא-קשורים, שלא אמורים
    להיפגע)
  - בקשה חדשה אינה נחסמת
  - approval מאוחר אינו אפשרי
  - callback כפול אינו מבצע
- **Root Cause המדויק (אומת בקוד, 04/08/2026):** `_reject_stale_telegram_approval()`
  (`app.py:2223`) זיהה את ה-contract לדחייה ע"י **חישוב מחדש** של
  `business_action_fingerprint` מתוך `payload.get("tool_inputs", {})` בלבד —
  אבל `propose_action()` מחשב את ה-fingerprint המקורי מתוך `fingerprint_payload`
  (למשל `task_parse.business_identity()` הכולל `due_time`) כשהוא מועבר בנפרד
  מ-`tool_inputs`/`task_fields` (payload הכתיבה, ללא `due_time` — ראה BUG-156).
  לכל משימה עם שעה, ה-fingerprint המחושב-מחדש שונה מהאמיתי, `find_by_fingerprint()`
  מחזיר `None`, `reject()` לעולם לא נקרא — אך הקוד ממשיך כרגיל ומודיע "פג תוקף".
  `payload["contract_id"]` כבר נשמר על אותו payload (`app.py:1612`) ומעולם לא
  נעשה בו שימוש בנתיב הזה.
- **תוקן ב-commit:** ממתין ל-commit (עבודה בענף `claude/pr-546-turn-coordinator-bugs-jhdrtl`)
- **תיקון:** `_reject_stale_telegram_approval()` משתמש כעת ב-`payload.get("contract_id")`
  ל-lookup ישיר דרך `find_by_id()`, במקום recompute של fingerprint. הlookup
  הישן (fingerprint recompute) נשמר כ-fallback רק לפריטים ללא contract_id שמור.
  **לא הוצג status חדש ("expired")** — `reject(rejected_by="ttl_expired")` הקיים
  כבר מעביר למצב terminal `"rejected"` הנתמך במלואו (מספיק לכל קריטריוני הסגירה).
  ראה `docs/architecture/action-gateway/BUG-155_TTL_EXPIRY_CONTRACT_LOOKUP_FIX_20260804.md`
  ל-Cross-Layer Impact Matrix מלא (נדרש לפי `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`).
- **בדיקות:** `test_bug155_ttl_expiry_contract_id_lookup.py` (חדש — משחזר את
  התרחיש המדויק, נכשל על הקוד הישן [3/5], עובר על הקוד המתוקן [5/5]),
  `test_bug112_telegram_approval_ttl.py` (30/30, ללא שינוי), `test_bug_stale_callback_ux.py`
  (10/10, ללא שינוי), `smoke_tests.py`, `test_integration.py` (4/4) — כולם ירוקים.
- **Merged:** ✅ כן — PR #550, מוזג ל-`origin/main` (`e26de4a`) (עודכן
  07/08/2026)
- **Deployed:** ✅ כן (עקיף) — Render: "Deploy live for `44fe0fb`"
  (07/08/2026, 11:34); `e26de4a` הוא ancestor מאומת.
- **⚠️ תיקון תיוג-ראיות (07/08/2026, אחרי דוח closure של ה-owner):** דוח
  ה-closure שהעביר ה-owner ל-#546 ייחס ל-BUG-155 את הלוג של 13:24
  (`contract=ab02671f...`, `Pending action expired at pop`, `BUG-158 שוחזר
  contract pending אחרי פקיעת item ב-EventBus`) — אבל זו **אותה ראיה
  בדיוק** שכבר תועדה תחת BUG-158 למעלה (אותו contract ID, אותו timestamp).
  הלוג המצוטט מכיל את המחרוזת המילולית "BUG-158" כי הוא נוצר ע"י
  `_recover_pending_item_from_contract()` — הפונקציה ש-BUG-158 (לא
  BUG-155) הוסיף. **זו אינה בדיקה של המנגנון של BUG-155** —
  `_reject_stale_telegram_approval()` (`app.py:2223`, ה-contract_id-lookup
  שמחליף recompute-fingerprint שגוי) — אלא של המנגנון הנפרד לגמרי
  שמטפל ב-`bus.pop()` שמחזיר `None` אחרי פקיעת ה-TTL הפנימי של
  EventBus (~30 דק'). שני המנגנונים מטפלים בתסמין דומה ("כפתור/פעולה
  שפג" + contract עדיין pending) אך דרך code paths נפרדים לגמרי, עם
  triggers נפרדים (`TTL-expired Telegram callback` בלוג עבור BUG-155,
  לעומת `Pending action expired at pop` עבור BUG-158). **לכן BUG-155
  נשאר לא-מאומת-ישירות** — דורש תרחיש נפרד: משימה עם `due_time`
  (כדי להפעיל את ה-fingerprint-recompute שהיה שגוי), שה-Telegram inline
  button שלה פג בחלון ה-10-30-דקות הספציפי (log line `TTL-expired
  Telegram callback`), לא חלון ה-30-דקות של EventBus.
- **Verified בפרודקשן (07/08/2026 15:03, owner, `my-bot-approval-staging`
  Render logs) — התרחיש הנכון הפעם:** ✅ **כן.** לחיצת ✅ (approve, לא
  ❌) יותר מ-10 דקות אחרי יצירת המשימה — בדיוק התנאי ב-`app.py:2680`
  (`if _age_seconds > _PENDING_APPROVAL_TTL`) שקורא בפועל ל-
  `_reject_stale_telegram_approval()`. הלוג:
  ```
  [ActionGateway] rejected: contract=123fc26c-412e-4415-9637-ff3d4bd54728
  tool=airtable_add by=ttl_expired
  [Approval] TTL-expired Telegram callback: action_id=f090cc12
  tool=airtable_add — not executed
  ```
  **אומת בקוד (07/08/2026):** `rejected_by="ttl_expired"` מופיע במקום
  **יחיד** בכל הריפו (`app.py:2317`) — בתוך הענף שמשתמש ב-
  `stored_contract_id` ל-`find_by_id()` ישיר (השורות 2295-2307,
  ה-branch שהתיקון של BUG-155 הוסיף), **לא** בענף ה-fallback של
  fingerprint-recompute (שמופעל רק `if not stored_contract_id`). כלומר
  הלוג הזה לא יכול להיווצר אלא דרך הנתיב המתוקן בדיוק. ה-contract
  אכן נמצא (`status=pending` לפני), עבר `reject()`, ואומת שוב כ-
  `rejected` — לא נשאר תקוע `pending` כמו בהתנהגות המקורית של הבאג.
- **סטטוס:** ✅ **VERIFIED IN PROD** — merged (`e26de4a`→`44fe0fb`) +
  deployed (Render, 07/08/2026 11:34) + production-verified (owner,
  07/08/2026 15:03, לוג אמיתי מצוטט למעלה, אומת מול הקוד כתואם לנתיב
  המתוקן ולא ל-fallback)

---

## BUG-156 — השעה משתתפת בזהות אך אינה נשמרת בכתיבה

- **דווח:** 3 באוגוסט 2026
- **סביבה:** Staging — `my-bot-approval-staging`, בסיס `בסיס עיקרי`
- **מסך / מודול:** canonical create-task payload, mapping ל-Airtable fields, schema של `משימות (Tasks)`
- **קלט:**
  ```text
  צור משימה לבדוק את אימות 546 המעודכן עד 5/8/26 בשעה 10:30
  ```
- **מה אומת:**
  - שינוי שעה משנה fingerprint
  - 19:00 → fingerprint=3e79afbdc541...
  - 20:00 → fingerprint=76e5eb2f8e74...
  - כלומר, השעה היא חלק מהזהות העסקית (`business_action_fingerprint`)
- **מה נכתב בפועל:**
  - הרשומה שנוצרה: recJHmybGqfR3tq3G
  - בטבלת `משימות (Tasks)`:
    - כותרת המשימה: `לבדוק את אימות 546 המעודכן`
    - תאריך יעד: `2026-08-05`
  - **לא נשמרה שעה**
- **Proof סכמה:**
  - השדה `תאריך יעד` הוא מסוג `date` (לא `dateTime`)
- **Root Cause:** המערכת משתמשת בשעה לצורך:
  - canonical identity
  - fingerprint
  - duplicate detection
  - אבל payload הכתיבה מכיל רק: כותרת המשימה ותאריך יעד
  - לכן השעה אובדת
- **Severity:** בינונית עד גבוהה
- **דרישת תיקון:** צריך להחליט חוזית על אחת משתי אפשרויות:

  **אפשרות א — השעה היא חלק מהמשימה:**
  - להפוך את השדה ל-`dateTime`, או
  - להוסיף שדה שעה נפרד
  - לוודא שה-write payload שומר את השעה

  **אפשרות ב — השעה אינה נתמכת:**
  - לא לכלול אותה ב-fingerprint
  - להחזיר clarification או הודעה מפורשת שהשעה אינה נשמרת
  - לא לאשר payload שמבטיח יותר ממה שנכתב
- **השפעה:**
  - שתי משימות זהות באותו תאריך ובשעות שונות מקבלות identities שונות
  - לאחר execution שתיהן עלולות להיכתב באופן זהה ב-Airtable
  - המידע שאושר אינו נשמר במלואו
  - completion עלול להציג הצלחה אף שחלק מהבקשה לא נשמר
- **קריטריוני סגירה:**
  - שעה נשמרת בפועל בAirtable, או
  - נדחית מפורשות עם clarification/cancel
  - payload מאושר וה-write payload עקביים
  - fingerprint אינו מכיל מידע שאובד בכתיבה
- **החלטת owner (04/08/2026, AskUserQuestion):** אפשרות ב — "stop promising
  the time." קוד-בלבד, ללא נגיעה בסכמת Airtable החיה.
- **תוקן (04/08/2026):** `DeterministicTaskParse.business_identity()`
  (`core/router/router.py`) כבר לא כולל `due_time` ב-fields — שתי בקשות
  זהות בכותרת+תאריך, שונות רק בשעה, מייצרות כעת את אותו fingerprint
  (במקום fingerprints שונים). `due_time` עדיין מנותח ומאומת (שעה פגומה
  עדיין fail-closes ל-clarification) — רק לא חלק מהזהות. בנוסף,
  `_queue_deterministic_create_task()` בונה הודעה מפורשת ("⚠️ שים לב: השעה
  שצוינה ({HH:MM}) לא תישמר ברשומה — רק התאריך יישמר") ומעביר אותה דרך
  פרמטר חדש `extra_note` ב-`_queue_approval_detailed()`/`_queue_approval_
  detailed_impl()` — מוצגת הן ל-owner (בהודעת ה-pending עם כפתורי אישור),
  הן לקורא לא-owner (בתשובה המוחזרת). ראה
  `docs/architecture/action-gateway/BUG-156_DUE_TIME_FINGERPRINT_VS_PERSISTENCE_FIX_20260804.md`
  ל-Cross-Layer Impact Matrix.
- **בדיקות:** `test_bug156_due_time_note_and_fingerprint_exclusion.py`
  (חדש, 8/8 — כולל אימות שהזהות זהה עבור שעות שונות, ושה-note מכיל את
  השעה המדויקת ומילת "לא תישמר"), `test_create_task_deterministic_route.py`
  (13/13 — אחד עודכן במכוון לשקף את ההתנהגות החדשה),
  `test_business_action_fingerprint_normalization.py` (8/8, ללא שינוי),
  `test_bug155_ttl_expiry_contract_id_lookup.py` (5/5, ללא שינוי),
  `test_bug153_create_task_reconfirmation_after_rejection.py` (11/11, ללא
  שינוי), `core/router/test_router.py` (44/44, ללא שינוי), `smoke_tests.py`,
  `test_integration.py` (4/4) — כולם ירוקים.
- **Merged:** ✅ כן — PR #550, commit `4337abe`, מוזג ל-`origin/main`
  (`e26de4a`) (עודכן 07/08/2026 — אומת: `git merge-base --is-ancestor
  4337abe origin/main`)
- **Deployed:** ✅ כן — Render: "Deploy live for `44fe0fb`" (07/08/2026,
  11:34); `4337abe` הוא ancestor מאומת (`git merge-base --is-ancestor
  4337abe 44fe0fb`)
- **Verified בפרודקשן (07/08/2026 14:22, owner, `my-bot-approval-staging`
  Render logs):** ✅ **כן.** נשלח "צור משימה בדיקת 156 עד 12-08-26 בשעה
  14:54" בטלגרם. הבוט החזיר בפועל:
  ```
  יש משימה שממתינה לאישור: בדיקת 156

  ⚠️ שים לב: השעה שצוינה (14:54) לא תישמר ברשומה — רק התאריך יישמר.
  ```
  ניסוח מדויק, זהה ל-`extra_note` שנבנה ב-`app.py:995` — מוכיח שה-warning
  המפורש (אפשרות ב שה-owner בחר) אכן מוצג בפרודקשן במקום להבטיח בשקט
  שמירת שעה שלא נשמרת.
- **סטטוס:** ✅ **VERIFIED IN PROD** — merged (`4337abe`→`44fe0fb`) +
  deployed (Render, 07/08/2026 11:34) + production-verified (owner,
  07/08/2026 14:22, לוג אמיתי מצוטט למעלה)

---

## בדיקה חסרה — כשל בשליחת הודעת pending ראשונה + suppression fallback

- **דווח:** 3 באוגוסט 2026
- **סביבה:** Staging — `my-bot-approval-staging`
- **מטרת הבדיקה:** לוודא כי אם שליחת הודעת ה-pending הראשונה נכשלת (network error, rate limit, טעות בשרת Telegram וכו'):
  - `duplicate_reply_suppressed=true` אינו מעלים גם את הודעת ה-fallback
  - המשתמש מקבל הודעה ציבורית אחת
  - לא מתקבלות אפס תשובות
  - לא מתקבלות שתי תשובות
- **הסדר הנבדק:** בעלים שולח בקשה → ActionContract נוצר → שליחת הודעת pending ראשונה נכשלת (via fault injection) → fallback notification משדר (חיוור/ייזום) → owner_notification_sent מתעדכן
- **דרוש:** Fault injection זמני ב-staging:
  ```bash
  export STAGING_FAIL_FIRST_APPROVAL_NOTIFICATION=true
  ```
  ה-fault צריך להפיל רק את ניסיון השליחה הראשון, בלי לפגוע ב:
  - יצירת ActionContract
  - routing
  - gateway
  - fallback send
- **תוצאה צפויה:**
  ```text
  owner_notification_sent=false
  duplicate_reply_suppressed=false
  final_responses=1
  ```
  או לוג שקול
- **נסגר (04/08/2026) — ללא צורך ב-`STAGING_FAIL_FIRST_APPROVAL_NOTIFICATION`
  או קוד production חדש:** `app._queue_approval_detailed_impl()`'s `bot.send_message(
  owner_chat_id, ...)` כבר עטוף ב-try/except ("BOSS NEVER FAKES" block) שמבצע,
  על כשל: ביטול מאומת של ה-EventBus pending item (`_cancel_and_verify_pending()`)
  וביטול מאומת (revoke) של ה-ActionContract שזה עתה נוצר
  (`_revoke_and_verify_contract()`) — שני helpers קיימים ונבדקים בנפרד
  ב-`core/approval_queue_recovery.py` — ומחזיר dict מובנה עם `ok=False`,
  ללא מפתח `owner_notified` (falsy), הודעת שגיאה יחידה. נבדק ישירות עם
  `bot.send_message` שמדומה לזרוק exception (ללא fault-injection env var
  ייעודי — mocking סטנדרטי ב-unit test מספיק) על event_bus/ActionGateway
  אמיתיים.
- **בדיקות:** `test_first_pending_notification_failure_suppression.py`
  (חדש, 11/11) — מאמת: `send_message` נקרא בדיוק פעם אחת (אין retry
  שקט/loop), `ok=False`, `owner_notified` falsy, `terminal_outcome=
  APPROVAL_QUEUE_ERROR`, הודעה ציבורית **אחת** לא-ריקה מוחזרת,
  `created_this_turn=False`, אין `ActionContract` חי שנשאר, אין
  `EventBus` pending item שנשאר — כל הקריטריונים שהתבקשו (`owner_notification_
  sent=false`, `duplicate_reply_suppressed=false`, `final_responses=1`)
  מתקיימים. Regression מוודא ששליחה תקינה (לא-נכשלת) עדיין מדווחת
  `owner_notified=True` ונשלחת פעם אחת בלבד. `smoke_tests.py`,
  `test_integration.py`, `test_bug112_telegram_approval_ttl.py` (30/30),
  `test_bug_stale_callback_ux.py` (10/10) — כולם ירוקים, לא נגעתי בקוד
  production כלל.
- **סטטוס:** ✅ בדיקה נוספה ואומתה — הקוד הקיים כבר עומד בכל הדרישות,
  ללא צורך בתיקון. **Merged:** ✅ כן — PR #550, מוזג ל-`origin/main`
  (`e26de4a`) (עודכן 07/08/2026, אומת: `test_first_pending_notification_
  failure_suppression.py` קיים ב-`origin/main`). **Deployed:** ✅ כן
  (עקיף) — Render: "Deploy live for `44fe0fb`" (07/08/2026, 11:34);
  `e26de4a` הוא ancestor מאומת. **Verified בפרודקשן:** לא (אין קוד
  production שהשתנה כאן מלכתחילה — לא רלוונטי).

---

## BUG-157 — propose_action() אינו אטומי סביב fingerprint lookup+save (concurrency)

- **דווח:** 04/08/2026, ע"י ביקורת CodeRabbit על PR #550 (לא תרחיש production
  שנצפה בפועל)
- **סביבה:** לא רלוונטי — ממצא סטטי מבוסס-קוד, לא production incident
- **מסך / מודול:** `core/action_gateway.py::ActionGateway.propose_action()`
  (שורות 1498-1526 בזמן הביקורת)
- **תיאור:** `propose_action()` מבצע `find_by_fingerprint()` ואז `save()`
  כשני צעדים נפרדים, ללא atomic uniqueness constraint ברמת ה-DB.
  תיאורטית, שתי בקשות **מקבילות באמת** עם אותו fingerprint עסקי יכולות
  כל אחת ליצור contract pending משלה לאותה זהות עסקית.
- **Root Cause:** תבנית check-then-act לא-אטומית ב-`propose_action()` —
  קיימת עבור **כל** יצירת contract חדש, לא רק ל-carve-out החדש של BUG-153.
  `ActionContractRepository` לא מספק שום compare-and-set/unique-constraint
  ברמת האחסון.
- **אומת (04/08/2026):** זה **לא** תרחיש שדווח מ-production — אומת סטטית
  מקריאת קוד בלבד. `gunicorn.conf.py` נועל `workers = 1` ללא override
  ל-`threads`/`worker_class` — Flask מטפל בבקשה אחת בזמן נתון בתוך אותו
  worker, בסינכרון מלא. **תיקון להערכה הקודמת (05/08/2026):** ה-workers=1
  שולל ריבוי **processes**, אך **לא** שולל ריבוי **threads** בתוך אותו
  process — `scheduler.py:844` (`threading.Thread(target=_run_scheduler,
  daemon=True, name="scheduler")`) מריץ thread נפרד לגמרי, שרץ **בו-זמנית**
  עם ה-thread הראשי שמטפל בבקשות webhook. `core/lead_recovery.py:257`
  ו-`followup_engine.py:212` שניהם קוראים ל-`propose_gated()` (→
  `propose_action()`) **מה-scheduler thread**. כלומר שתי thread אמיתיות
  יכולות לקרוא ל-`propose_action()` בו-זמנית תחת ה-deployment הנוכחי —
  הסיכון **אינו** רק latent, הוא נגיש כבר היום (גם אם נדיר בפועל, תלוי
  תזמון scheduler מול webhook).
- **Severity:** גבוהה (לפי CodeRabbit — "Major") — נגיש בפועל (לא רק latent).
- **החלטת owner (04/08/2026, AskUserQuestion):** להשאיר ל-PR נפרד — לא
  לתקן בתוך PR #550 (בג-פיקס ממוקד). דורש עיצוב עצמאי + Cross-Layer Impact
  Matrix מלא לפי `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` (נוגע ישירות
  בשכבה 4 — Durable Atomic Approval).
- **תגובה ב-PR #550:** https://github.com/10026782/My-bot/pull/550#issuecomment-5189294142
- **תוקן (05/08/2026):** CAS (compare-and-set) אטומי חדש על אינדקס
  `_by_fingerprint` הקיים ב-RAM, תחת `ExecutionLedger._lock` הקיים —
  `claim_fingerprint_cas(fingerprint, expected_contract_id)`/
  `release_fingerprint_claim(fingerprint)` חדשים. `propose_action()`
  עוטף את רצף lookup→status-branch-checks (ללא שינוי בהתנהגות)→claim
  בלולאת retry חסומה (5 ניסיונות) — אם ה-claim נכשל (race הפסיד), חוזר
  ל-lookup טרי שרואה את מה שה-thread המנצח שמר, ומחזיר תגובת dedup נכונה
  במקום כפילות. ללא שינוי בהתנהגות תחת single-caller (המקרה הנפוץ) — הclaim
  תמיד מצליח בניסיון הראשון. ראו
  `docs/architecture/action-gateway/BUG-157_ATOMIC_FINGERPRINT_CLAIM_20260805.md`
  ל-Cross-Layer Impact Matrix מלא.
- **בדיקות:** `test_bug157_atomic_fingerprint_claim.py` (חדש, 18/18) —
  כולל race אמיתי עם 8 threads בו-זמנית (barrier), אימות דטרמיניסטי
  (interleave ידני של check-then-act, מוכיח שהקוד הישן יצר 2 contracts
  לאותו fingerprint ב-100% מהריצות, לעומת הקוד המתוקן שחוסם duplicate
  ב-100% מהריצות), 5 קריאות `propose_action()` מקבילות אמיתיות (5/5
  הצליחו לחזור, 1 בלבד ok=True, contract חי אחד בלבד לbecome N),
  ו-regression ל-single-caller (ללא race, ללא שינוי התנהגות).
  `test_action_gateway.py` (43/43, ללא שינוי), `test_business_action_
  fingerprint_normalization.py` (8/8, ללא שינוי), `test_bug153` (16/16),
  `test_bug155` (5/5), `test_bug156` (11/11), `test_pr0c_action_gateway_
  adapters.py` (34/34), `test_phase_4b_1a_durable_proposals.py` (11/11),
  `test_phase_4b_1a_lookup_correctness.py`, `core/router/test_router.py`
  (44/44), `smoke_tests.py`, `test_integration.py` (4/4) — כולם ירוקים.
- **Merged:** ✅ כן — PR #552, commit `c5dbe86` על `origin/main` (אומת
  05/08/2026: `git merge-base --is-ancestor f75f095 origin/main` → YES)
- **Deployed:** ✅ כן (עקיף) — Render: "Deploy live for `44fe0fb`"
  (07/08/2026, 11:34); `c5dbe86` הוא ancestor מאומת
  (`git merge-base --is-ancestor c5dbe86 44fe0fb`)
- **Verified בפרודקשן:** לא — תרחיש ה-race המקביל הספציפי (שני threads
  על אותו fingerprint) לא נבדק ישירות בפרודקשן; הבדיקה שבוצעה (07/08
  13:24) עברה במסלול BUG-158/EventBus-recovery, לא במסלול claim-race הזה
- **סטטוס:** 🟡 מוזג ל-`main` (PR #552) + deployed (עקיף/ancestor) —
  **production verification ישיר לתרחיש ה-race עדיין לא בוצע**

### המשך (05/08/2026) — סבב ביקורת שני של CodeRabbit: המתנה ל-claim משתחרר

לאחר מיזוג PR #552, CodeRabbit העלה בסבב ביקורת שני על אותו PR (שכבר
נסגר עם המיזוג) ממצא Major נוסף שלא הספיק להיכלל: ה-retry loop
המקורי היה "הפסד claim → lookup טרי מייד", ללא שום המתנה לשחרור
claim מתחרה. תחת `FEATURE_ACTION_CONTRACT_PERSISTENCE=on` (כתיבה
עמידה אמיתית, latency לא-טריוויאלי ב-`save()`), מפסיד יכול היה למצות
את כל 5 ניסיונות ה-retry בזמן שהמנצח עדיין באמצע כתיבה ל-repository,
ולקבל `failure_code="persistence_lookup_failed"` שגוי ("עומס גבוה")
במקום את תגובת ה-dedup הנכונה מול ה-contract שהמנצח בפועל יצר.

- **תוקן (05/08/2026, המשך, PR נפרד חדש — לא #552 שנסגר):**
  `ExecutionLedger.__init__` מקבל `self._claim_released_condition =
  threading.Condition(self._lock)` (Condition על אותו lock קיים).
  `claim_fingerprint_cas()` מקבל פרמטר חדש `wait_timeout: float = 0.0`
  (ברירת מחדל שומרת התנהגות זהה אם לא מועבר) — אם ה-claim הפסיד
  **ספציפית** כי claim מתחרה בתהליך (לא כי המצב כבר סופי ושונה),
  ממתין (עם timeout) ל-`notify_all()` מ-`release_fingerprint_claim()`/
  `_cache_contract()` לפני שהוא בודק שוב. `propose_action()` מחשב
  `_CLAIM_TOTAL_WAIT_BUDGET_SECONDS = 2.0` כתקציב-המתנה **כולל** על
  פני כל 5 הניסיונות (לא per-attempt), ומעביר את הזמן שנותר לכל
  ניסיון. בתנאי ללא-race — ההמתנה לעולם לא מופעלת בפועל.
- **בדיקות:** `test_bug157_atomic_fingerprint_claim.py` הורחב ל-24/24
  (מ-18/18) — section 6 חדשה מדמה `save()` איטי (delay מלאכותי 0.5s
  על ה-instance) עם 2 threads מקבילים על אותו fingerprint, מוודאת:
  שתי הקריאות חוזרות (אין תקיעה), המפסיד מקבל dedup נכון מול
  ה-contract_id של המנצח (**לא** `persistence_lookup_failed`), והזמן
  הכולל חסום ע"י ה-delay היחיד של המנצח ולא מוכפל ע"י retries.
  regression מלא ירוק: `test_action_gateway.py` (43/43),
  `test_business_action_fingerprint_normalization.py` (8/8),
  `test_bug153` (16/16), `test_bug155` (5/5), `test_bug156` (11/11),
  `test_first_pending_notification_failure_suppression.py` (14/14),
  `core/router/test_router.py` (44/44), `smoke_tests.py`,
  `test_integration.py` (4/4).
- **Merged:** ✅ כן (עודכן 07/08/2026, שוב) — כלול ב-PR #555, מוזג
  ל-`origin/main` (`bf9b670`) יחד עם ה"המשך שני" למטה (אותו PR, אותו
  branch) — ראו את בלוק ה-"סטטוס" המעודכן בסוף "המשך שני" למטה, שהוא
  הסטטוס הסופי המדויק של כל PR #555.
- **Deployed:** ✅ כן (עקיף) — Render: "Deploy live for `44fe0fb`"
  (07/08/2026, 11:34); `bf9b670` הוא ancestor מאומת
  (`git merge-base --is-ancestor bf9b670 44fe0fb`)
- **Verified בפרודקשן:** לא — תרחיש ההמתנה-לשחרור-claim הספציפי לא נבדק
  ישירות בפרודקשן; הבדיקה שבוצעה (07/08 13:24) עברה במסלול
  BUG-158/EventBus-recovery

### המשך שני (07/08/2026) — CodeRabbit על PR #555: bounded claim-ownership token

ביקורת CodeRabbit על PR #555 עצמו העלתה ממצא Major/Heavy-lift נוסף:
`_cache_contract()` היה משחרר כל claim על fingerprint **ללא בדיקת בעלות** —
כולל כשנקרא מנתיב **read-path בלבד** (`find_by_id()`/`find_by_fingerprint()`/
`find_live_by_user()` שמחממים cache מה-repository, לא caller שבאמת claim-ם).
תרחיש קונקרטי: שתי הצעות `deterministic_create_task` שקוראות במקביל
fingerprint עם contract קיים שנדחה ("rejected", carve-out של BUG-153) —
caller A זוכה ב-claim; caller B, שרק *קורא* (cold-cache hydration) את אותו
contract שנדחה, היה בעבר משחרר בטעות את ה-claim של A ע"י `_cache_contract()`
הישן; caller B יכול היה אז לזכות ב-claim בעצמו; שני callers היו יכולים
לשמור contract חלופי לאותו fingerprint — בדיוק ה-duplicate ש-BUG-157 המקורי
נועד לסגור.

- **תוקן (07/08/2026):** `claim_fingerprint_cas()` מחזיר עכשיו **token
  אטום** (`str`, לא `bool`) במקום פשוט `True`. `release_fingerprint_claim(
  fingerprint, token)` ו-`_cache_contract(contract, *, claim_token=None)`
  משחררים claim **רק אם ה-token תואם בדיוק**. קריאות read-path-בלבד
  (4 call sites: `find_by_id()`, `find_by_fingerprint()`,
  `find_live_by_user()`, `update_status()`) משאירות `claim_token=None`
  במפורש — לעולם לא יכולות לשחרר claim של מישהו אחר. `propose_action()`
  מעביר את ה-token שקיבל מ-`claim_fingerprint_cas()` ל-`save()` ול-
  `release_fingerprint_claim()` בנתיב הכשל.
- **בדיקות:** `test_bug157_atomic_fingerprint_claim.py` הורחב ל-**34/34**
  (מ-24/24) — section 2b חדשה (cache-warm לא גונב claim פעיל), section 7
  חדשה (שחזור מדויק של התרחיש שהעלה CodeRabbit: cold-cache re-hydration
  של contract שנדחה תוך כדי claim פעיל — מוכיח contract יחיד נשמר, לא
  שניים). גם תוקן: sections 1/2/3 עודכנו ל-API החדש (token במקום bool),
  section 6 קיבל daemon threads + bounded join (לא unbounded `.join()` —
  תיקון נוסף של CodeRabbit, מונע תלייה שקטה של הטסט אם regression יחזור).
  regression מלא ירוק: `test_action_gateway.py` (43/43),
  `test_business_action_fingerprint_normalization.py` (8/8), `test_bug153`
  (16/16), `test_bug155` (5/5), `test_bug156` (11/11),
  `test_first_pending_notification_failure_suppression.py` (14/14),
  `test_pr0c_action_gateway_adapters.py` (34/34),
  `test_phase_4b_1a_durable_proposals.py` (11/11),
  `test_phase_4b_1a_lookup_correctness.py`,
  `test_p0_unhashable_identity_atomic_wrapper.py` (18/18),
  `test_pr0c_action_contracts_persistence.py` (16/16),
  `core/router/test_router.py` (44/44), `smoke_tests.py`,
  `test_integration.py` (4/4) — כולם ירוקים.
- **Merged:** ✅ כן — PR #555, מוזג ל-`origin/main` (`bf9b670`), 07/08/2026
- **Deployed:** ✅ כן (עקיף) — Render: "Deploy live for `44fe0fb`"
  (07/08/2026, 11:34); `bf9b670` הוא ancestor מאומת
  (`git merge-base --is-ancestor bf9b670 44fe0fb`)
- **Verified בפרודקשן:** לא — תרחיש ה-claim-ownership token הספציפי
  (cold-cache re-hydration תוך כדי claim פעיל) לא נבדק ישירות בפרודקשן;
  הבדיקה שבוצעה (07/08 13:24) עברה במסלול BUG-158/EventBus-recovery
- **סטטוס:** 🟡 מוזג ל-`main` (PR #555) + deployed (עקיף/ancestor) —
  **production verification ישיר לתרחיש ה-claim-ownership עדיין לא בוצע**

---

## BUG-158 — כפתור אישור/ביטול שפג ב-EventBus מדווח "לא זמין" גם כש-ActionContract עדיין pending

- **דווח:** 05-07/08/2026, ע"י owner — בדיקה ידנית על `my-bot-approval-staging`
  (Render), נותח לוגים מלאים + צילומי מסך Telegram מול הקוד ב-`main`
- **סביבה:** Staging — `my-bot-approval-staging`
- **מסך / מודול:** `app.py::_handle_approval_callback_impl()`
  (`action=="approve"`, שורה ~2538; `action=="reject"`, שורה ~2923)
- **תיאור:** לחיצה על כפתור טלגרם (✅/❌) לאחר שה-item המתאים ב-`event_bus.py`'s
  `PendingActionsStore` כבר פג (TTL הפנימי של EventBus, ~30 דקות — נפרד
  לגמרי מ-24h TTL של ה-`ActionContract` עצמו, `CONTRACT_PENDING_TTL_SECONDS`
  ב-`core/action_contract_repository.py:84`) מחזירה למשתמש "ℹ️ הפעולה כבר
  אינה זמינה, ולכן לא בוצעה" — ניסוח שמשתמע ממנו שאין יותר שום פעולה קיימת.
  בפועל, ה-`ActionContract` יכול להישאר pending וחי לגמרי, ולחזור מאוחר
  יותר (reconfirmation, או "מאשר"/"כן" בטקסט) — מה שהמשתמש כבר האמין
  שבוטל/לא קיים מבצע בפועל.
- **Root Cause (אומת בקוד, 07/08/2026):** שני ה-branches (`approve`,
  `reject`) קוראים ל-`bus.pop(action_id)`; אם מחזיר `None` (item פג ב-TTL
  הפנימי של EventBus) — שניהם קוראים מיד ל-`_notify_missing_or_expired_
  callback()` ומחזירים, **בלי לבדוק את מצב ה-`ActionContract`**. זה סותר
  קוד קיים **באותה פונקציה, מוקדם יותר** (שורות ~2519-2536): בדיקה מבוססת
  `callback_contract_id` (מוטמע ב-callback_data של הכפתור עצמו, עצמאי
  מ-EventBus) שכבר קיימת — אך רק חוסמת כשה-contract כבר terminal; כשהוא
  עדיין pending, נופלת דרך על הנחה שה-`bus.pop()` יטפל בזה כרגיל. ההנחה
  שוברת בדיוק כש-`bus.pop()` נכשל.
- **Severity:** גבוהה — "שקר תפעולי" למשתמש (owner: "המשתמש חושב שהפעולה
  איננה קיימת, בעוד שהמערכת עדיין מחזיקה אותה חיה")
- **המדיניות שנבחרה (owner, 07/08/2026):** "רק הכפתור פג, הפעולה עדיין
  pending" (לא "פקיעת הכפתור מבטלת גם את הפעולה") — ה-`ActionContract`
  (24h TTL, מכוון) הוא מקור האמת; אין הצדקה לבטל פעולה אמיתית רק כי
  עותק-cache פנימי (EventBus, 30 דק') פג.
- **תוקן (07/08/2026):** פונקציית עזר חדשה `app._recover_pending_item_
  from_contract(contract_id)` — משחזרת מבנה `item` זהה-בצורתו ל-item רגיל
  של `bus.pop()`, ישירות מתוך ה-`ActionContract` (`tool_name`,
  `normalized_payload`, `origin_channel`, `origin_chat_id`,
  `canonical_user_id`) — שדות סמכותיים קיימים על ה-contract, לא צריך
  עותק EventBus כדי לדעת אותם. מחזירה `None` אם ה-contract לא נמצא או
  כבר לא pending — במקרה הזה ההתנהגות הקיימת (`_notify_missing_or_
  expired_callback`) ממשיכה ללא שינוי. בשני ה-branches, כש-`bus.pop()`
  מחזיר `None`: מנסה את `_recover_pending_item_from_contract()` לפני
  שהוא נכנע ל"אינה זמינה". שאר הקוד הקיים רץ ללא שינוי — reuse מלא של
  `approve_with_lifecycle_result()`/`reject_with_lifecycle_result()`.
  ראה `docs/architecture/action-gateway/
  BUG-158_APPROVAL_CANCELLATION_EXPIRY_CANONICALIZATION_20260807.md`
  ל-Cross-Layer Impact Matrix מלא.
- **בדיקות:** `test_bug158_approval_callback_eventbus_ttl_recovery.py`
  (חדש, 11/11) — approve משוחזר ומבוצע, reject משוחזר ומבטל, baseline
  (item קיים) ללא שינוי, contract שכבר terminal לא "קם לתחייה" ע"י
  השחזור, ו-callback ישן ללא contract_id עדיין נופל ל"אינה זמינה"
  (fallback ללא שינוי). regression מלא ירוק: `test_bug112_telegram_
  approval_ttl.py` (30/30), `test_bug153` (16/16), `test_bug155` (5/5),
  `test_bug156` (11/11), `test_first_pending_notification_failure_
  suppression.py` (14/14), `test_pa01_phantom_approval_enforcement.py`
  (108/108), `test_pending_contract_read_amplification.py` (6/6),
  `test_bug_approval_callback_hardening.py` (39/39),
  `test_bug_batch_approval_preserved.py` (13/13),
  `test_bug122_pending_queue_ux.py` (8/8),
  `test_approval_gateway_safety.py` (27/27), `smoke_tests.py`,
  `test_integration.py` (4/4) — כולם ירוקים.
- **מיפוי TTL לפני מיזוג (07/08/2026, לבקשת owner):** נבדקו כל קבועי
  ה-TTL הקשורים לאישור בקוד (`event_bus.py`, `app.py`, `tma_api.py`,
  `core/otp.py`, `core/emergency_window.py`, WhatsApp, `voice_adapter.py`)
  — טבלה מלאה ב-`docs/architecture/action-gateway/
  BUG-158_APPROVAL_CANCELLATION_EXPIRY_CANONICALIZATION_20260807.md`.
  **תוצאה: `event_bus.py::PENDING_TTL_MINUTES` (30 דק') היה הפער היחיד**
  — בדיוק מה שתוקן כאן. TMA כבר תואם 24h בכוונה; שאר המנגנונים לא
  קשורים לאותה מחלקת באג. **מסקנת closure:** state קצר-חיים של
  transport/UI לעולם אסור לו לדרוס או לדווח בטעות את מצב ה-ActionContract
  החי — בכל פקיעת cache/event, ה-resolution חייב לחזור ל-`contract_id`
  ול-lifecycle של ה-ActionContract עצמו.
- **Merged:** ✅ כן — PR #556, מוזג ל-`origin/main` (`00ad6f1`), 07/08/2026
- **Deployed:** ✅ כן — Render: "Deploy live for `44fe0fb`" (07/08/2026,
  11:34), `00ad6f1` הוא ancestor מאומת של `44fe0fb`
  (`git merge-base --is-ancestor 00ad6f1 44fe0fb`)
- **Verified בפרודקשן (07/08/2026, 13:24, owner):** ✅ **כן — תרחיש מדויק
  שוחזר בפרודקשן בפועל.** Contract נוצר ב-11:54, עדיין pending ב-13:24
  (90 דקות — מעל ה-TTL הפנימי של EventBus, 30 דקות). Owner לחץ על כפתור
  *בטל* הישן. לוג Render בפועל:
  ```text
  [INFO] event_bus: ⏰ Pending action expired at pop: 44325224
  [INFO] app: [Approval] BUG-158 שוחזר contract pending אחרי פקיעת item
  ב-EventBus: contract=ab02671f-c7e0-4987-ab30-887b5a829fa8 tool=airtable_add
  [INFO] core.action_gateway: [ActionGateway] rejected:
  contract=ab02671f-c7e0-4987-ab30-887b5a829fa8 tool=airtable_add by=boss_hq:eliyahu
  [INFO] app: 🚫 Rejected: 44325224 | ➕ יצירת משימה: • כותרת המשימה: ...
  ```
  `_recover_pending_item_from_contract()` אכן הופעל, מצא את ה-contract
  עדיין pending, וביצע דחייה אמיתית ומאומתת — **לא** "ℹ️ הפעולה כבר אינה
  זמינה" הכוזב שהיה קורה לפני התיקון.
- **סטטוס:** ✅ **VERIFIED IN PROD** — merged (`00ad6f1`→`44fe0fb`) +
  deployed (Render, 07/08/2026 11:34) + production-verified (owner,
  07/08/2026 13:24, לוג אמיתי מצוטט למעלה)

---

## BUG-159 — הפרסר הדטרמיניסטי של create_task לא מזהה "משימת" (סמיכות) ו-הוסף/תוסיף

- **דווח:** 07/08/2026, ע"י owner — בדיקת staging ידנית, ניתוח מדויק מול
  הקוד (`core/router/router.py`)
- **סביבה:** Staging — `my-bot-approval-staging`
- **מסך / מודול:** `core/router/router.py:26-28`
  (`_STRUCTURED_CREATE_TASK_RE`)
- **תיאור:** "צור משימה בדיקת באג 153" (משימה, צורת יסוד) עבר במסלול
  הדטרמיניסטי (`risk=needs_approval handler=tool`), בעוד "צור משימ**ת**
  בדיקת באג 155" (צורת סמיכות, ניסוח עברי טבעי לגמרי) נפל דרך ל-Agent
  loop הכללי (`risk=normal handler=agent`, קריאת Claude אמיתית). בנוסף,
  "הוסף"/"תוסיף" — פעלים ש-`detect_intent()` כבר מזהה כ-create_task ברמת
  ה-intent — לא נתמכו בפרסר הדטרמיניסטי כלל, גם עם "משימה" תקנית.
- **Root Cause (אומת בקוד):** `_STRUCTURED_CREATE_TASK_RE = re.compile(
  r"^\s*(?:צור|תיצור)\s+משימה\s*:?\s*(?P<title>.+?)\s*$")` — דרש בדיוק
  "משימה" ורק "צור"/"תיצור". "משימת" לא תואם `fullmatch()` →
  `DeterministicTaskParse()` ברירת מחדל (`matched=False`) — לא `certain`
  וגם לא `uncertain` במפורש → נופל ל-`detect_risk()` הגנרי.
- **Severity:** בינונית-גבוהה — ניסוח עברי טבעי (לא שגיאת קלט) קובע
  routing/מדיניות אישור שונה; BUG-153's `trusted_source=
  "deterministic_create_task"` carve-out לא חל על הניסוחים שנפלו דרך.
- **תוקן (07/08/2026):** `_STRUCTURED_CREATE_TASK_RE = re.compile(
  r"^\s*(?:צור|תיצור|הוסף|תוסיף)\s+משימ(?:ה|ת)\s*:?\s*(?P<title>.+?)\s*$")`
  — owner אישר `משימ(?:ה|ת)` (מצומצם) ודחה `\bמשימ\w?` (רחב מדי, עלול
  לתפוס צורות לא רצויות). שאר `parse_deterministic_create_task()`
  (תאריך/שעה/title extraction, BUG-154/156) ללא שינוי. ראה
  `docs/architecture/action-gateway/
  BUG-159_CREATE_TASK_NOUN_FORM_PARSER_GAP_20260807.md` ל-Cross-Layer
  Impact Matrix מלא.
- **בדיקות:** `test_bug159_create_task_noun_form_and_verbs.py` (חדש,
  **52/52**) — כל 6 הניסוחים מקריטריוני הסגירה של ה-owner (`צור משימה`/
  `צור משימת`/`צור משימת בדיקה`/`תיצור משימת בדיקה`/`הוסף משימת בדיקה`/
  `תוסיף משימת בדיקה`) מגיעים ל-`intent=create_task, risk=needs_approval,
  handler=tool`; `business_identity()` שקול (fingerprint) בין כל
  הניסוחים לתוכן זהה; "משימות" (רבים, לא נתמך) **לא** תואם — מוכיח
  שהתיקון מצומצם ולא `\w+` רחב; section 6 — `app._queue_
  deterministic_create_task()` נקרא ישירות עם ארגומנטים מפורסרים
  (composition-level proof); **section 7 (CodeRabbit, 07/08/2026)**
  — end-to-end אמיתי דרך `app.run_agent()` עצמו (נקודת הכניסה
  האמיתית שה-webhook קורא לה עם טקסט גולמי) — `app.client.messages.
  create` מוחלף ב-mock שזורק `AssertionError` אם נקרא בכלל, מוכיח
  `agent_calls=0` **בפועל, לא רק מלוג** — יחד עם contract חי יחיד,
  `trusted_source` נכון, ו-title נכון, דרך השרשרת המלאה `run_agent()`
  → `route_request()` → `_queue_deterministic_create_task()`.
  regression מלא ירוק: `core/router/test_router.py` (44/44),
  `test_bug153` (16/16), `test_bug154` (20/20), `test_bug155` (5/5),
  `test_bug156` (11/11), `smoke_tests.py`, `test_integration.py`
  (4/4).
- **Merged:** ✅ כן — PR #557, מוזג ל-`origin/main` (`44fe0fb`), 07/08/2026
  (אומת: `git merge-base --is-ancestor 44fe0fb origin/main`)
- **Deployed:** ✅ כן — Render: "Deploy live for `44fe0fb`: Merge pull
  request #557 ... fix(BUG-159)" (07/08/2026, 11:34) — commit ה-PR עצמו,
  לא רק ancestor
- **Verified בפרודקשן (07/08/2026, owner):** ✅ **כן.** נשלח בפועל בטלגרם:
  "צור משימ**ת** בדיקת באג 159" (צורת סמיכות — בדיוק הפער שתוקן, לא
  "משימה"). תגובת הבוט: "יש משימה שממתינה לאישור: בדיקת באג 159" — תבנית
  התגובה הדטרמיניסטית המדויקת (לא תגובת Agent חופשית), מוכיחה שהניסוח
  הגיע למסלול המהיר ולא ל-Agent loop. (מבוסס על צורת התגובה בפועל —
  לא צוטט כאן לוג גולמי ייעודי לשורה הזו, בשונה מ-BUG-158 למעלה.)
- **סטטוס:** ✅ **VERIFIED IN PROD** — merged (`44fe0fb`) + deployed
  (Render, 07/08/2026 11:34) + production-verified (owner, 07/08/2026,
  ניסוח "משימת" הגיע לתגובה הדטרמיניסטית הנכונה)

---

## BUG-160 — מרכאה לא מאוזנת עוקפת את המסלול הדטרמיניסטי של create_task — ✅ תוקן ומאומת (טרם deployed/verified בפרודקשן)

- **דווח:** 07/08/2026, ע"י owner — נחשף תוך כדי אימות production של #546
- **סביבה:** Production — `my-bot-approval-staging` (Render)
- **מסך / מודול:** `core/router/router.py` —
  `_normalize_create_task_input()` + `_STRUCTURED_CREATE_TASK_RE.fullmatch()`
- **קלט:**
  ```text
  "צור משימה בדיקת PR546 עד תאריך 12-08-26 בשעה 14:54
  ```
  (מרכאה פותחת (`"`) בלבד — אין מרכאה סוגרת בסוף ההודעה)
- **התנהגות בפועל (מהלוג):**
  ```text
  wrapper_stripped=False
  intent=create_task
  risk=normal
  handler=agent
  ```
  ואז קריאת Anthropic אמיתית (`POST https://api.anthropic.com/v1/messages`).
- **Root Cause (אומת בקוד, 07/08/2026):**
  `_normalize_create_task_input()` (`core/router/router.py:76-95`) מסיר
  זוג-מרכאות **רק אם שניהם קיימים** —
  `value.startswith(opening) and value.endswith(closing)` (שורות 82-84).
  מרכאה פותחת בלי מרכאה סוגרת תואמת לא מקיימת את התנאי, ולכן **לעולם
  לא מוסרת** — נשארת כחלק מהמחרוזת. `_STRUCTURED_CREATE_TASK_RE.fullmatch()`
  (שורה 100) דורש שהמחרוזת המנורמלת תתחיל (אחרי `\s*`) ישירות באחד
  הפעלים (`צור`/`תיצור`/`הוסף`/`תוסיף`) — מרכאה תקועה בתחילת המחרוזת
  שוברת את ה-`fullmatch` לגמרי. `parse_deterministic_create_task()`
  מחזיר `DeterministicTaskParse()` המחדל (`matched=False`) — לא
  `.certain` ולא `.uncertain` — כך ש-`route_request()` נופל דרך לניתוב
  הכללי מבוסס-`intent_router.py` (`Handler.AGENT`), בדיוק כמו הפער
  המקורי שתועד ב-BUG-159, אך כאן הסיבה היא פיסוק לא-מאוזן ולא צורת
  פועל/שם-עצם חסרה.
- **Severity:** גבוהה — bypass שקט של המסלול הדטרמיניסטי: `agent_calls>0`
  במקום `0`, סמנטיקת approval שונה (Agent tool-use loop, לא
  `queue_task_request()` הקנוני), ו-`trusted_source="agent"` (לא
  `"deterministic_create_task"`) — כלומר גם ה-carve-out של BUG-153
  לא בהכרח יחול אם הבקשה הזו תידחה ותישלח שוב במרכאות.
- **קריטריוני סגירה:**
  - מרכאה פותחת בלי סוגרת תואמת (וההפך) אינה מפילה את הבקשה מהמסלול
    הדטרמיניסטי — או שהיא מנוקה (strip חד-צדדי בטוח), או שה-clarify
    fail-closed המפורש (התבנית הקיימת ל-`uncertain`) מופעל במקום נפילה
    שקטה ל-Agent
  - `agent_calls=0` נשמר לכל קלט שהיה עובר כ-`.certain` אלמלא הפיסוק
    הבלתי-תקין
  - אין regression לניקוי הקיים של מרכאות מאוזנות/prefix של "Eli:"/">"
- **תוקן (07/08/2026):** נוסף מקרה שלישי, צר, ללולאת ה-strip הקיימת
  והחסומה של `_normalize_create_task_input()`: מרכאה/סוגר פותח שהתו-
  הסוגר התואם שלו **לא מופיע בשום מקום אחר במחרוזת** — מוסר רק תו-הפתיחה
  הבודד (לא מניחים שקיימת סגירה איפשהו ומורידים גם אותה). מקרה עמום
  (התו-הסוגר כן מופיע, רק לא בדיוק בסוף) נשאר **במכוון** לא-מטופל — אין
  stripping חדש למקרה לא-חד-משמעי, בהתאם לקריטריון-הסגירה השני
  ("clarify fail-closed" נשמר כברירת-מחדל לכל מה שלא-ודאי). אופציית-
  הסגירה שנבחרה היא (a) מהקריטריונים למעלה — strip חד-צדדי בטוח, לא (b).
- **Cross-Layer Impact Matrix:** מולא ב-`docs/architecture/action-gateway/
  BUG-160_161_162_163_TURN_COORDINATOR_FALLBACK_AUTHORITY_PLANNING_GATE_
  20260807.md` (נכתב יחד עם BUG-161/162/163 לפי בקשת ה-owner — "שכחתי את
  באג 160 בתוך הלייר"). שכבה 2 (TurnCoordinator) touched directly; שכבות
  1/3/4 not touched (grep=0 מאומת בכל שלושתן).
- **בדיקות:** `test_bug160_unbalanced_quote_create_task.py` (חדש, 15/15
  — כולל התרחיש המדויק מהלוג, ה-due_date שמנותח נכון, כל ה-stripping
  הקיים ללא regression, והמקרה העמום שנשאר במכוון unmatched) +
  `core/router/test_router.py` (44/44) + `test_bug153_create_task_
  reconfirmation_after_rejection.py` (16/16) + `test_bug159_create_
  task_noun_form_and_verbs.py` (52/52) + `test_hotfix_c_create_task_
  verb.py` (12/12) — כולם ללא regression, ו-`smoke_tests.py` (PASS).
- **סטטוס:** ✅ CODE DONE, מאומת מקומית (טסט חדש + regression מלא על כל
  סוויטות ה-create_task). **לא** נדחף/נפרס עדיין — לא VERIFIED IN PROD
  עד push+deploy+אימות production בפועל, לפי כלל הברזל.

---

## BUG-161 — reconfirmation מפורש לא עקבי בין המסלול הדטרמיניסטי למסלול Agent

- **דווח:** 07/08/2026, ע"י owner — המשך ישיר לתרחיש BUG-160 (נפילה
  ל-Agent גרמה לחשיפת הפער הזה)
- **סביבה:** Production — `my-bot-approval-staging`
- **הרצף שנצפה:** אחרי ש-BUG-160 הפיל בקשת create_task למסלול Agent,
  ה-Agent (לא ה-gateway הדטרמיניסטי) ניסה להציע את הפעולה מול contract
  שכבר נדחה בעבר. תשובת ה-Agent למשתמש:
  ```text
  אם אתה רוצה ליצור משימה זו בכל זאת — אנא אשר זאת בבירור.
  ```
  המשתמש כתב `מאשר` — תגובה: `אין פעולה שממתינה לאישור` (אין contract
  pending שממתין ל-callback הזה בפועל). המשתמש כתב אז במפורש `צור
  משימה ... למרות שנדחתה בעבר` — ה-Agent ניסה tool-use, וה-Gateway חסם:
  ```text
  [ActionGateway] propose blocked: business action already rejected
  ```
- **Root Cause (עקבי עם התיעוד הקיים, לא נדרש grep נוסף לאישור):**
  BUG-153's carve-out (`BUG-153_CREATE_TASK_EXPLICIT_RECONFIRMATION_POLICY_20260804.md`)
  מוגדר **במפורש ובכוונה** בהיקף צר: רק `trusted_source ==
  "deterministic_create_task"` — ערך שנקבע **רק** בתוך
  `_queue_deterministic_create_task()` (קוד מהימן, לא tool_inputs/טקסט
  משתמש). "**כולל `\"agent\"`** (autonomous replay — ממשיך להיחסם ללא
  תנאי, בדיוק כמו היום)" — כלומר ה-Gateway חוסם את ה-Agent path **לפי
  עיצוב**, לא כתקלה. הפער האמיתי הוא **UX/policy**, לא Gateway logic:
  ה-Agent מציע למשתמש אפשרות ("אשר בבירור") שה-runtime מבנית לא יכול
  לספק — אין נתיב שממיר "מאשר"/"בכל זאת" שנאמר ל-Agent לבקשת
  `deterministic_create_task` חדשה עם ה-trusted_source הנכון.
- **Severity:** גבוהה — הבטחה שקרית למשתמש מפי ה-Agent (הזמנה לפעולה
  שהמערכת חוסמת בהמשך), לא רק חוסר-נוחות
- **קריטריוני סגירה (טרם הוחלט — דורש הכרעת owner):**
  - אפשרות א: Agent אסור לו להציע "אשר בבירור" למשתמש כשה-contract
    האחרון הרלוונטי הוא `rejected` — יכוון את המשתמש לנסח בקשת create
    חדשה מפורשת (המסלול הדטרמיניסטי, אם BUG-160 ייסגר, יתפוס את זה
    ישירות)
  - אפשרות ב: להרחיב את carve-out של BUG-153 כך שגם path מסוים
    שמקורו ב-Agent (עם אימות דומה ל-`trusted_source`) יוכל לפתוח
    reconfirmation — משנה scope שכבר הוחלט במפורש כצר בכוונה, דורש
    Cross-Layer Impact Matrix חדש לפני כל שינוי קוד
  - בכל מקרה: אין הבטחה מ-Agent שה-runtime לא יכול לקיים
- **תלות:** קשור ישירות ל-BUG-160 — אם BUG-160 ייסגר (מרכאות לא-מאוזנות
  לא מפילות ל-Agent), חלק ניכר מהחשיפה בפועל לתרחיש הזה קטן, אך הפער
  העקרוני (Agent path אינו תומך reconfirmation) נשאר קיים לכל נפילה
  אחרת ל-Agent.
- **החלטת owner (07/08/2026) — אפשרות א' אושרה, אפשרות ב' נדחתה
  במפורש:**
  > BUG-161 policy decision: do not expand Agent reconfirmation.
  > create_task reconfirmation remains owned by the Turn Coordinator /
  > deterministic ActionGateway path. Agent must not promise or
  > simulate reconfirmation. If a create_task request reaches Agent
  > due to fallback, it must defer/route back to the canonical
  > coordinator path or return a truthful non-approval response.

  ותוספת עברית מה-owner, המרחיבה את העיקרון גם ל-BUG-162 (ראו שם):
  "אנחנו רוצים במסגרת Turn Coordinator לצמצם את סמכויות הסוכן, לא
  להרחיב — רק צריך לוודא שלא יובטחו הבטחות שאין בהן ממש, ולא תילקח
  בעלות שלא כדין, גם עם fallback-ים שונים."

  **המשמעות המעשית לתיקון (טרם מומש — Cross-Layer Impact Matrix נדרש
  לפני קוד):** ה-carve-out של BUG-153 **נשאר בהיקפו הצר הנוכחי**
  (`trusted_source == "deterministic_create_task"` בלבד) — **לא**
  יורחב ל-Agent. במקום זאת, כשבקשת `create_task` מגיעה ל-Agent path
  (בין אם דרך BUG-160 או fallback אחר כלשהו), ה-Agent צריך לזהות
  מצב כזה ו: (1) להפנות/להחזיר את המשתמש למסלול הקנוני (route back
  ל-`route_request()`/`queue_task_request()`), **או** (2) להחזיר
  תשובה אמיתית שאין אישור ממתין — **לא** לנסח הזמנה ל"אשר בבירור" ולא
  לדמות reconfirmation semantics שה-runtime לא תומך בהם בפועל.
- **Cross-Layer Impact Matrix הושלם (07/08/2026):**
  `docs/architecture/action-gateway/BUG-160_161_162_163_TURN_COORDINATOR_
  FALLBACK_AUTHORITY_PLANNING_GATE_20260807.md` — נכתב יחד עם BUG-162/163
  לפי בקשת ה-owner ("כאן ממילא פותחים אותה אז אל תשכח את שלושתם"). שכבה 2
  (TurnCoordinator) touched directly; שכבה 4 (Durable Atomic Approval)
  touched indirectly (תלות סמנטית חדשה, לא code coupling — מתועדת
  במפורש); שכבות 1/3 not touched (grep=0 מאומת). RP5 guard: applies=yes,
  מנגנון-קיים בלבד (STATIC_MANIFEST honesty rules, לא classifier חדש).
- **מומש חלקית (07/08/2026) — רק החלק שאינו תלוי ב-BUG-162:** נוסף כלל-
  כנות חדש ב-`core_knowledge.py`'s `STATIC_MANIFEST` (אותו בלוק "חוקי
  כנות" שכבר מכיל את הכלל הקיים על אישור-Telegram-בלבד): מניעה **מראש**
  של Agent מלהציע "אשר בבירור"/reconfirmation בטקסט חופשי לפעולה שכבר
  נדחתה. **למה ברמת prompt ולא regex/classifier:** ה"הבטחה" היא טקסט
  חופשי לפני כל tool_use — בדיוק קטגוריית-הבעיה שכבר נחקרה ונדחתה
  ב-BUG-126/BUG-127C ("A32/regex הוא כנראה השכבה הלא-נכונה"). ה-backstop
  הדטרמיניסטי הקיים (`core/action_gateway.py:1622-1643`, חוסם
  `trusted_source != "deterministic_create_task"` נגד fingerprint שנדחה)
  **לא שונה** — אומת ישירות שהוא עדיין אמיתי ולא-ממציא
  ("יצירת המשימה כבר בוטלה", `reply_owner=gateway`).
- **המגבלה שנשארת (למה עדיין 🟡, לא ✅):** `reply_owner=gateway` על
  תוצאת ה-block הזו הוא **shadow-בלבד** (זהה ל-BUG-162) — אין אכיפה
  שמונעת מה-Agent "לדבר" סביב תוצאת tool_use גם אחרי שכלל-הכנות מנסה
  למנוע את ההבטחה **מראש**. סגירה מלאה של BUG-161 תלויה במנגנון-
  enforcement של BUG-162.
- **בדיקות:** `test_bug161_agent_no_reconfirmation_promise.py` (חדש,
  7/7) — מאמת מיקום/ניסוח הכלל בפרומפט **וגם** את תקינות ה-Gateway
  backstop (`build_approval_lifecycle_result`) שהכלל נשען עליו, כ-cross-
  layer test מפורש בין שכבה 2 לשכבה 4.
- **סטטוס:** 🟡 CODE DONE (חלקית — מניעה ברמת prompt בלבד), **לא**
  VERIFIED — תלוי בהכרעת-enforcement של BUG-162 לסגירה מלאה. לא נדחף/
  נפרס עדיין.

---

## BUG-162 — הפרת turn-ownership: Agent מדבר ב-turn שבבעלות ה-gateway

- **דווח:** 07/08/2026, ע"י owner — נצפה באותו flow של BUG-160/161
- **סביבה:** Production — `my-bot-approval-staging`
- **מסך / מודול:** `core/turn_envelope.py` — `TurnOwnershipShadow`
  (`OwnershipSignal.is_gateway_owned_leak`, שורה ~559)
- **הרצף שנצפה:** באותו turn שבו ה-Agent ניסה להציע reconfirmation
  (ראו BUG-161), נרשם:
  ```text
  [TurnOwnershipShadow] violation=agent_spoke_in_gateway_owned_approval_turn
  ```
- **הבהרה חשובה (אומת בקוד, 07/08/2026):** זהו סיגנל **shadow-בלבד**
  — התיעוד הקיים ב-`core/turn_envelope.py` (שורות 362-367, הפונקציה
  `_classify_agent_leak_pattern()`) קובע במפורש: "purely observational,
  never used to suppress/alter text". כלומר המנגנון **זיהה נכון** את
  ההפרה (זו הוכחה שה-monitoring עובד), אך שום דבר לא חסם את ה-leak
  עצמו בפועל — ה-Agent שלח את התשובה למשתמש כרגיל.
- **Root Cause:** אותה שרשרת שגרמה ל-BUG-160/161 — נפילה למסלול Agent
  עבור בקשה שה-`reply_owner` הרשמי שלה אמור להיות `gateway` (לפי
  ה-invariant של `turn_envelope.py`) גורמת ל-Agent "לדבר" ב-turn
  שאינו בבעלותו. ה-shadow signal קיים כדי **לזהות** בדיוק את המקרה
  הזה, ועשה זאת נכון — הפער הוא שאין enforcement, רק תיעוד.
- **Severity:** בינונית-גבוהה — לא נזק ישיר בפני עצמו (התשובה שנשלחה
  לא בהכרח שגויה תוכנית — ראו BUG-161), אלא **הפרת invariant ארכיטקטוני
  מתועד** (`reply_owner=gateway` אמור להבטיח קול סמכותי יחיד לתשובת
  approval) שכרגע לא נאכף, רק נצפה.
- **קריטריוני סגירה:**
  - להחליט (owner) האם `TurnOwnershipShadow` צריך לעבור מ-shadow
    ל-enforce עבור התבנית הזו הספציפית (חסימת/דיכוי תשובת Agent כש-
    `reply_owner=gateway` כבר נקבע), בדומה למודל shadow→enforce
    שקיים כבר בפייצ'רים אחרים בריפו (ראו `FEATURE_AIRTABLE_RUNTIME_
    SCHEMA_PROVIDER_STATE`, `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE`)
  - אם מוחלט על enforce: להגדיר מה קורה בפועל כשה-Agent "רוצה לדבר"
    ב-turn כזה — clarify? silence? redirect לגייטווי?
  - Cross-Layer Impact Matrix מלא נדרש לפני כל שינוי enforcement
    (נוגע ישירות ל-TurnCoordinator/reply-ownership contract לפי
    `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`)
- **תלות:** אותו trigger כמו BUG-160/161 — סגירת BUG-160 מצמצמת את
  התדירות בפועל אך לא סוגרת את הפער העקרוני ב-enforcement.
- **החלטת owner (07/08/2026) — כיוון מדיניות ניתן, מנגנון enforcement
  ספציפי עדיין לא הוכרע:** אותה החלטה שנרשמה תחת BUG-161 מרחיבה
  במפורש גם לכאן: "אנחנו רוצים במסגרת Turn Coordinator לצמצם את
  סמכויות הסוכן, לא להרחיב — רק צריך לוודא שלא יובטחו הבטחות שאין
  בהן ממש, ולא תילקח בעלות שלא כדין, גם עם fallback-ים שונים." זה
  קובע **כיוון ברור** (Agent אסור לו "לקחת בעלות" ב-turn שאמור
  להיות `reply_owner=gateway`, בשום fallback) — אך **לא** מכריע עדיין
  את שאלת ה-enforcement הקונקרטית מה"קריטריוני סגירה" למעלה (מה
  בדיוק קורה כש-Agent "רוצה לדבר" ב-turn כזה: silence? clarify?
  redirect אוטומטי לגייטווי?). זו עדיין החלטת ארכיטקטורה נפרדת,
  ספציפית, שדורשת Cross-Layer Impact Matrix משלה לפני מימוש —
  ה-direction אינו תחליף למנגנון.
- **Cross-Layer Impact Matrix (planning-level, 07/08/2026):** מולא יחד
  עם BUG-161/163 ב-`docs/architecture/action-gateway/BUG-161_162_163_
  TURN_COORDINATOR_FALLBACK_AUTHORITY_PLANNING_GATE_20260807.md` — אך
  **אין קוד runtime** שנכתב עבור BUG-162 עצמו בסבב הזה. חשוב: מטריצה
  מלאה מסירה את חסם "אין מטריצה" (`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
  §6), **אינה** תחליף להחלטת-owner המפורשת שעדיין חסרה (מנגנון ה-
  enforcement הקונקרטי) — נשאר `PLANNING BLOCKED` על הסעיף הזה בלבד.
- **החלטת enforcement קונקרטית (owner, 07/08/2026, verbatim):**
  > "Single final speaker: Gateway. Agent may produce internal
  > reasoning/tool intent, but never a competing final response.
  > Clarification is an explicit Coordinator-owned message kind rendered
  > by Gateway, not an Agent-owned reply."

  זו הכרעה חד-משמעית לטובת **redirect אוטומטי לגייטווי** מבין שלוש
  האופציות שהוצגו — לא silence גנרי ולא clarify גנרי: Agent מותר לו
  reasoning/tool-calls פנימיים, אך **אף פעם** לא תשובה סופית מתחרה;
  clarification עצמו הופך לסוג-הודעה שבבעלות ה-Coordinator/Gateway,
  לא ניסוח חופשי של Agent.

- **ממצא קריטי (אומת בקוד, 07/08/2026) — המנגנון הזה כבר קיים, בנוי
  ונבדק, פשוט כבוי:** `app.py:4437-4494` ("PR1 single-speaker boundary",
  קומנט מפורש בקוד) מיישם **בדיוק** את מה שההחלטה מתארת: כש-`tool_
  results_log` מכיל רשומת `__approval_queued__` עם `reply_owner==
  "gateway"` (מאומת שזה קורה **גם** במסלול ה-block/rejected, לא רק
  בהצלחה — `_queue_approval_detailed_impl()` שורה 1821 קורא
  `_lifecycle_result = action_gateway.lifecycle_result(_contract_id)`
  ומגדיר `"reply_owner": _lifecycle_result.reply_owner`, ו-
  `build_approval_lifecycle_result()` קובע `reply_owner="gateway"`
  **ללא תנאי** על כל ה-canonical_state branches, כולל `rejected`) —
  ה-turn מסתיים מיד עם `_lifecycle.safe_user_message` (או `""` אם כבר
  נשלח דרך side-channel), **בלי לקרוא ל-Agent שוב בכלל**. זה בדיוק
  "Agent... never a competing final response".
  **אבל:** כל המנגנון הזה נעול מאחורי `FEATURE_SINGLE_SPEAKER_APPROVAL_
  UX` — **כבוי כברירת מחדל** (`feature_flags.py:217-218`,
  `os.environ.get("FEATURE_SINGLE_SPEAKER_APPROVAL_UX", "false")`),
  ומתועד כ-"PR1 response-routing cutover" — כלומר rollout מדורג שטרם
  הופעל, לא קוד חדש שצריך להיכתב. יש כיסוי-טסטים קיים ב-7 קבצי טסט
  (`test_bug112_telegram_approval_ttl.py`, `test_bug155_ttl_expiry_
  contract_id_lookup.py`, `test_bug_approval_callback_hardening.py`,
  `test_bug_stale_callback_ux.py`, `test_f52_pr6_pending_shadow.py`,
  `test_hotfix_e_shared_replay_policy.py`, `test_pr2_deterministic_
  approval_cost_cuts.py`).
- **מגבלה חשובה שגם הפעלת הדגל לא סוגרת:** המנגנון הזה תלוי בכך
  שנוצרה **רשומת** `__approval_queued__` באותו turn — כלומר, הוא פועל
  רק **אחרי** שה-Agent בפועל ניסה tool_use שהגיע ל-Gateway (המקרה השני
  בתרחיש BUG-161 שנצפה). את המקרה **הראשון** (Agent מבטיח "אשר בבירור"
  **מראש**, בלי לנסות tool_use כלל — turn ריק מ-tool_results) המנגנון
  הזה **לא** יכול לתפוס מבנית, כי אין תוצאת-Gateway להעדיף על פני טקסט
  ה-Agent. זה נשאר מטופל רק ע"י כלל-הכנות ב-`STATIC_MANIFEST` שכבר
  נוסף ב-BUG-161 (מניעה ברמת prompt, לא אכיפה מבנית) — "Clarification
  is an explicit Coordinator-owned message kind" (חלק ב' של ההחלטה)
  מכסה תיאורטית גם את המקרה הזה, אך מימושו דורש שינוי גדול יותר
  (Agent לא מייצר טקסט חופשי לקריאה-לbהבהרה כלל — סוג-הודעה נפרד
  שה-Coordinator עצמו בונה) שלא מומש בסבב הזה — נשאר סעיף פתוח.
- **החלטת owner על אופן ההפעלה (07/08/2026):** נשאלה מפורשות בין שלוש
  אופציות (שינוי דיפולט בקוד / השארה כבוי כרגע / הפעלה ידנית ב-Render
  env) — **נבחרה האופציה השלישית**: ה-owner יפעיל את
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` **ידנית ב-Render environment**
  (staging/production), **לא** דרך שינוי הדיפולט ב-`feature_flags.py`.
  **שום קוד לא שונה** בעקבות ההחלטה הזו — הדיפולט ב-`feature_flags.py`
  נשאר `"false"` במכוון, כפי שהוא, כדי שסביבות ללא env var מפורש
  (למשל CI/טסטים מקומיים) לא ישתנו. הפעלה בפועל = פעולת-owner ב-Render
  dashboard, מחוץ להיקף session זה — **אין claim על deploy/activation
  בפועל עד שה-owner יאשר שה-env var אכן הוגדר וש-behavior אומת
  ב-production**, לפי כלל הברזל.
- **⚠️ תיקון-מסקנה קריטי (07/08/2026, אחרי צילום-מסך אמיתי מ-Render מה-owner):**
  ה-owner הראה בפועל ש-`FEATURE_SINGLE_SPEAKER_APPROVAL_UX` **כבר `true`**
  ב-environment (לא כבוי כפי שהונח למעלה) — **ובכל זאת** נצפה ה-violation
  המקורי. זו סתירה ישירה למסקנה הקודמת ("ממתין רק להפעלת flag") — המסקנה
  ההיא הייתה **שגויה**, לא רק לא-שלמה. נחקר מחדש מאפס במקום לנחש.
- **Root Cause האמיתי (אומת בקוד, 07/08/2026):** `app.py::
  _queue_approval_detailed_impl()` — הבלוק ל-`failure_code ==
  "existing_pending_blocks_agent"` (שורות ~1504-1520) קובע במפורש
  `"reply_owner": "gateway"` ו-`"lifecycle_result"` בתוצאה שהוא מחזיר. אבל
  הבלוק **הגנרי** מיד אחריו (שורות ~1521-1532 לפני התיקון) — שהוא **זה
  שבפועל מטפל** ב-block של BUG-153 ("business action already rejected"),
  ובכל דחיית-dedup/pending/approved/executing/completed אחרת שנמצאת
  ע"י `propose_action()` — **לא הגדיר את שני השדות האלה בכלל**. כתוצאה:
  ה-lookup ב-tool-use loop (`_gateway_owned = next((entry for entry in
  reversed(tool_results_log) if entry.get("tool")=="__approval_queued__"
  and entry.get("reply_owner")=="gateway"), None)`) **לעולם לא מצא
  התאמה** לתרחיש הזה — **ללא קשר בכלל** לערך של
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`. הדגל לא היה הבעיה; ה-signal
  שהמנגנון מחפש פשוט לא הופק במקום הנכון.
- **תוקן (07/08/2026):** הבלוק הגנרי בונה עכשיו `ApprovalLifecycleResult`
  אמיתי (`build_approval_lifecycle_result()`, אותו מנגנון בדיוק כמו הבלוק
  השכן) בכל פעם שיש `contract_id` — ומסמן `reply_owner="gateway"` +
  `lifecycle_result`, בדיוק כמו הבלוק השכן. הגנתי: אם `find_contract()`
  לא מוצא רשומה (לא אמור לקרות בפועל — אותה קריאה סינכרונית שהחזירה
  את ה-id לפני רגע), נשאר בהתנהגות הישנה (לא מסמן reply_owner) במקום
  לתאר "no_contract" לא-נכון על contract שכן קיים. **תוכן ההודעה
  (`safe_user_message`) לא השתנה** — התיקון רק מוסיף את ה-signal
  החסר, לא משנה מה נאמר למשתמש.
- **בדיקות (חדש, הורחב ל-exhaustive; הורחב שוב ב-code review, 07/08/2026):**
  `test_bug162_gateway_reply_owner_on_generic_block.py` (**57/57**) — לא רק
  תרחיש BUG-153 בודד: enumeration ממצה על **7 ערכי `existing.status`**
  שמגיעים ל-branch הגנרי (pending/completed/executed/rejected/approved/
  executing/outcome_unknown — "executed" נוסף ב-code review כי
  `_handle_duplicate_executed()` מקבץ אותו יחד עם "completed" ולא היה
  מכוסה קודם), כל אחד נבדק בנפרד עבור `reply_owner=="gateway"` +
  `lifecycle_result` מאוכלס + תוכן-הודעה אמיתי ולא-ממציא + (תוספת code
  review) קישור מפורש ל-contract_id שנזרע ול-canonical_state הספציפי
  לסטטוס, לא רק "lifecycle_result לא None". **Regression מלא**:
  `test_bug153_...py` (16/16), `test_bug161_...py` (7/7), ו-10 קבצי טסט נוספים שמפעילים
  `_queue_approval_detailed` (`test_bug115`, `test_bug155`, `test_bug156`,
  `test_bug_batch_approval_preserved`, `test_bug_canonical_tool_wiring`,
  `test_create_task_deterministic_route`, `test_first_pending_
  notification_failure_suppression`, `test_pa01_phantom_approval_
  enforcement`, `test_f52_pr6_pending_shadow`, `test_f52_status_reply_
  reconciliation`) — כולם ירוקים, ללא regression.
- **Closure Audit מלא (07/08/2026, בעקבות בקשת ה-owner "איך קרתה תקלה כזו
  ואיך נמנעים מלחזור עליה"):** `docs/architecture/action-gateway/BUG-162_
  SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md`. תמצית:
  1. **מיפוי exit-path מלא** — כל 11 ה-return branches של
     `_queue_approval_detailed_impl()` נבדקו ידנית מול ה-contract
     (`reply_owner` נדרש כש-יש contract אמיתי וסופי; לא נדרש כש-אין
     contract/מצב לא-מאומת). **רק branch אחד (הגנרי) היה שגוי** — שאר
     ה-10 היו נכונים-בעיצוב מלכתחילה. התיקון סוגר את כל הפער בפונקציה
     הזו, לא רק מופע יחיד.
  2. **למה זה קרה למרות ה-DoD:** `TURN_COORDINATOR_PROPOSAL_V2.md`'s
     Gate C דורש במפורש regression-coverage מלא ל-"reply ownership"
     — אבל חל פורמלית רק על Phase 3 ("Reply Ownership"), שלפי
     `docs/architecture/turn-coordinator/README.md` **מעולם לא נפתח
     רשמית** ("Phase 1 not started"). PR #471 שלח מימוש-מקדים,
     לא-רשמי, של אותו מנגנון עצמו לפרודקשן — בלי לעבור מול ה-DoD
     שנכתב בשבילו, כי הוא לא נקרא רשמית "Phase 3". `docs/context_
     librarian/layers/turn_coordinator.json`'s notes תיעדו את הפער
     הזה בכנות מראש ("a conditional... not a general reply_owner claim
     mechanism") — אבל אף Gate לא חייב שקוד-מקדים כזה יעבור מול ה-DoD
     של המטרה שהוא בפועל משרת. **זה פער תהליכי, לא רק טכני.**
  3. **ראיה שזה נחזה מראש:** `docs/architecture/f52-unified-approval-
     runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md` (נכתב
     ~15/07/2026, 3 שבועות לפני הדיווח), Finding 3, כבר קבע במפורש
     שהמנגנון-אז-הקיים הוא "stopgap"/"suppression patch, not a
     reply_owner field" — וש-Phase 3 הוא ה-generalization הנדרש.
     המסמך לא יכול היה לחזות שגם ה-generalization עצמו (PR #471)
     ייצא לא-שלם.
  4. **Duplicate authority — ממצא פתוח, לא תוקן (לפי הנחיה מפורשת):**
     שני מנגנונים עצמאיים מחשבים "האם ה-turn שייך ל-gateway" —
     מנגנון-האכיפה (`_gateway_owned`, דורש `reply_owner=="gateway"`)
     ומנגנון ה-shadow-observation (`_approval_queued_this_turn`, דורש
     רק נוכחות `__approval_queued__`, לא בודק `reply_owner` בכלל). זו
     בדיוק הסיבה שה-shadow log תפס את ההפרה נכון בזמן שהאכיפה נכשלה —
     שני מקורות-אמת נפרדים, יכולים להתפצל. **מתועד, לא מומש** —
     איחוד לשני המקורות דורש Cross-Layer Impact Matrix משלו אם/כש-owner
     יחליט לטפל בזה.
- **⚠️ סיווג מתוקן (07/08/2026, אחרי איתור TC6):** התיקון ב-`app.py` הוא
  **interim tactical patch, לא מימוש TC6** ("explicit reply ownership",
  Workstream 2 — `docs/architecture/turn-coordinator-full/GAP_ANALYSIS.md`,
  עדיין `NEXT_IMPLEMENTATION`). אומת ישירות בקוד: `ActionGateway.approval_
  status()`/`execution_status()` (WS2's projection methods) **כן קיימות**
  (`core/action_gateway.py:3366,3379`) **אך תוצאתן נזרקת בפועל** בשתי
  נקודות-הקריאה (`core/action_gateway.py:3459,3486` — נקראות בלי `=`) —
  `build_approval_lifecycle_result()` (המנגנון הישן, בדיוק איפה שהבאג חי)
  הוא עדיין מה שמייצר את הטקסט בפועל לכל מקרה. ה-patch תוקן **בתוך**
  המנגנון הישן הזה — לא ביצע cutover ל-WS2's projections, ולא סוגר את
  TC6. תועד גם ש-ה-patch נכתב כעריכה ישירה ל-`app.py` **מחוץ** לתהליך
  ה-WS2 agent-prompt/Librarian-bundle/integrator-review (`app.py` מוגדר
  "Integrator only" ב-`PARALLEL_IMPLEMENTATION_WORKSTREAMS.md`'s file
  ownership map) — נרשם במפורש ב-`turn-coordinator-full/DECISION_LOG.md`
  entry 14 כדי שמימוש TC6 העתידי ימצא את זה בכוונה, לא כסחיפה לא-מוסברת,
  ויסקור/יאחד או יחליף אותו במפורש.
- **Single source of truth (07/08/2026):** התגלה תוך כדי החקירה ש-
  `docs/architecture/turn-coordinator/` (המעודכן שוטף) ו-`docs/
  architecture/turn-coordinator-full/` (תוכנית ה-WS1/WS2/WS3, TC1-TC10)
  הן שתי תיקיות **נפרדות** שתיארו אותה תוכנית, בלי הפניה הדדית — עד
  עכשיו. תוקן: שני ה-README's מפנים זה לזה במפורש (`turn-coordinator/
  README.md` קנוני לסטטוס-מיזוג נוכחי; `turn-coordinator-full/` קנוני
  לפירוק-המשימות TC1-TC10 ולבעלות-פערים).
  **⚠️ תיקון (07/08/2026, אחרי CI):** ניסיון לעדכן גם את
  `docs/context_librarian/layers/turn_coordinator.json`'s
  `canonical_docs` (להוסיף את `turn-coordinator-full/`) **נדחה בחזרה
  (revert מלא)** — גילינו ש-catalog הזה מכויל בצמצוד קיצוני מול תקציבי
  token/document-count מרובים ושונים (`test_context_librarian.py`,
  `test_pilot_preflight.py`), וגם תוספת מינימלית (2 קבצים, טקסט מקוצר)
  שברה 5 טסטים שונים בסוויטה המלאה (לא רק את הטסט שנכשל ב-CI תחילה).
  **מקור-האמת היחיד ל-Turn Coordinator נשען כרגע רק על הפניה בין שני
  ה-README's עצמם** (רמת התיעוד) — **לא** על הקטלוג האוטומטי של
  ה-Librarian, שנשאר כפי שהיה (ללא `turn-coordinator-full/`). זה פער
  שנשאר פתוח במפורש: bundle עתידי עדיין עלול לפספס את `turn-coordinator-
  full/` אם לא ייקרא ה-README הראשי ידנית. תיקון קטלוג עתידי (אם ירצה
  ה-owner) דורש עבודה נפרדת, ממוקדת, על תקציבי-הטוקן/מסמכים של כל
  ה-profile queries הרלוונטיים — לא side-fix אגבי כמו שנוסה כאן.
- **סטטוס:** 🟡→ קרוב יותר ל-סגירה אמיתית: **root cause אמיתי אותר,
  interim patch תוקן ונבדק בקוד, closure audit מלא בוצע, TC6 סומן נכון
  כ-NEXT_IMPLEMENTATION (לא Done, לא נסגר ע"י ה-patch)** (לא רק "ממתין
  להפעלת flag" — זו הייתה מסקנה שגויה שתוקנה כאן; ולא רק "תוקן מקרה
  אחד" — כל 11 exit-paths אומתו). נותר: (1) אימות-production חוזר
  לתרחיש BUG-161/162 המקורי אחרי push+deploy (2) מימוש נפרד ל-
  "Clarification כסוג-הודעה של Coordinator" עבור התרחיש-הראשון (Agent
  מבטיח מראש, בלי tool_use כלל) — עדיין לא מכוסה (3) duplicate-authority
  finding — מתועד, לא מומש, ממתין להחלטת owner אם/מתי לטפל (4) **TC6
  עצמו** — המימוש הפורמלי, כשיגיע בתורו ב-WS2, צריך לסקור/לאחד את ה-
  interim patch הזה, לא להשאיר side-patch נפרד לצמיתות. **לא claim
  "✅ Fixed" עד אימות production**, לפי כלל הברזל.

---

## אימות Turn Coordinator E2E (07/08/2026) — שילוב BUG-160/161/162 לתוך התוכנית, ותיקון מסגור

- **מקור:** דוח E2E מסודר + דוח באגים (12 ממצאים, BUG-TC-01 עד BUG-TC-12) שסיפק
  ה-owner, מבדיקות ידניות ב-`my-bot-approval-staging` על תרחישי Update/Complete
  task. הבקשה: לשלב את BUG-160/161/162 בתוך תיקון Turn Coordinator, ולתעד את
  12 הממצאים.
- **מתודולוגיה (כלל ברזל):** הדוח **לא** הועתק כמות שהוא. כל ממצא נבדק ישירות
  מול הקוד החי לפני תיעוד — בדומה לבדיקה שנעשתה ל-BUG-153 עד 162. התוצאה: רוב
  הממצאים (8 מתוך 12) הם **לא** באגים חדשים אלא אישוש-ייצור לפער שכבר מתועד
  בפירוט ב-Planning Gate קיים; שני ממצאים נוספים כבר מתועדים כבאגים קיימים
  (BUG-126/BUG-127C); ממצא אחד הוא חדש ואמיתי (נרשם כ-BUG-163); ואחד הוא פער
  testability, לא באג.

### ממצא 1 (TC-01, TC-03, TC-04, TC-05, TC-08, TC-09, TC-10, TC-11) — לא באגים חדשים: אישוש-production ל-`PA-01_PLANNING_GATE.md` הקיים

- **Root Cause מדויק (אומת בקוד ישירות, 07/08/2026):** קיים כבר infrastructure
  דטרמיניסטי מלא ל-update/complete task — `core/router/task_resolvers.py`
  (`resolve_task()`, 0/1/multiple matches ללא בחירה שקטה),
  `core/router/task_builders.py`, `core/turn_coordinator_runtime.py`
  (`queue_task_request()`, `TASK_OWNERSHIP` registry הכולל את שני ה-intent-ים
  עם `resolver_required=True`), ו-`app.py:1046-1079`
  (`_queue_deterministic_task_update()`, כולל `enforce("airtable_update", ...)`
  ו-קריאה ל-`queue_task_request()`). כל זה **מחובר בפועל** ב-`app.py:3955-3958`:
  ```python
  if route.handler == Handler.TOOL and route.intent in {"update_task", "complete_task"}:
      return _queue_deterministic_task_update(...)
  ```
  אבל: `core/router/router.py:234-239` — הבלוק היחיד שקובע `Handler.TOOL`
  באופן דטרמיניסטי — כתוב **רק** עבור `Intent.CREATE_TASK`
  (`if intent == Intent.CREATE_TASK and _create_task_parse.certain and ...`).
  **אין בלוק מקביל ל-`UPDATE_TASK`/`COMPLETE_TASK`** — למרות
  ש-`core/router/risk_router.py`'s `_CONTRACT_REQUIRED_INTENT_TO_TOOL`
  (שורות 57-60) **כבר** מגדיר את שניהם כ-contract-required
  (`airtable_update`), ולמרות ש-`docs/architecture/turn-coordinator/
  PA-01_PLANNING_GATE.md`'s טבלת §3.5/§3.6 (שורות 224-225) **כבר** קובעת
  `UPDATE_TASK`/`COMPLETE_TASK` = contract-required = Yes, "Same reasoning as
  `CREATE_TASK`". התוצאה: כל בקשת update/complete מגיעה תמיד ל-`Handler.AGENT`
  (ברירת המחדל של `detect_risk()` ל-`_NORMAL_INTENTS`), ה-resolver/gateway
  הדטרמיניסטי **לעולם לא מופעל בפועל היום**, וההתנהגות נופלת כולה לשיקול-דעת
  חופשי של ה-Agent — בדיוק ההתנהגות שתועדה ב-12 הבדיקות של הדוח (resolution
  לא-עקבי, "multiple matches" בלי verified read, שאילתות Airtable לא-אחידות
  בין הרצה להרצה, ownership שנשאר agent).
- **קריטי:** `PA-01_PLANNING_GATE.md` **כבר קיים**, כותרת מפורשת "Phantom
  Approval Prompt Structural Enforcement", Status header: **"PLANNING ONLY. No
  code written, no branch opened, no implementation started."** (Baseline
  `main` `f2f7093`, 15/07/2026) — ומתאר במפורש את אותו הפער: אילו intent-ים
  מגיעים ל-`Handler.AGENT` למרות שהם contract-required, כולל `UPDATE_TASK`/
  `COMPLETE_TASK` בשמם. הסטטוס הזה **תואם** את מה שנמצא בקריאה ישירה של
  `router.py` היום — אין סתירה בין המסמך לקוד.
- **מסקנה — תיקון מסגור, לא תיוג-מחדש:** 8 מתוך 12 הממצאים בדוח (TC-01, 03,
  04, 05, 08, 09, 10, 11) הם **לא** באגים חדשים שדורשים מספרי BUG נפרדים —
  הם **ראיית-production חיה ומאומתת** לכך שהפער ש-PA-01 קיים כדי לסגור הוא
  אמיתי וגורם היום להתנהגות בלתי-דטרמיניסטית בפרודקשן, לא רק סיכון תיאורטי.
  ה-no-op/already-satisfied UX (TC-08) וה-A32 fallback הגס (TC-09) והאי-עקביות
  ב-resolver query (TC-10) — כולם תוצרי-לוואי של אותה נפילה ל-`Handler.AGENT`,
  לא שורשים נפרדים: כש-`Handler.TOOL` יתחיל להיקבע גם ל-update/complete,
  `resolve_task()`/`queue_task_request()` הקיימים יטפלו ב-0/1/multiple matches
  בעצמם, וה-Agent לא יגיע לתרחישים האלה כלל.
- **המלצה:** לצרף את עדויות הדוח (12 התרחישים + ציטוטי הלוג) כראיית-אימות
  ל-`PA-01_PLANNING_GATE.md` עצמו (Phase 0/Rollout section), ולהשתמש בהן
  להצדיק תעדוף מימוש PA-01 — במקום לפתוח 8 מספרי BUG-TC נפרדים לאותו שורש.
- **סטטוס:** 🟡 root cause מאומת בקוד + מסמך תכנון קיים (PA-01) עדיין
  **PLANNING ONLY** — אין קוד runtime שנכתב. כל שינוי דורש Cross-Layer Impact
  Matrix לפי `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` (PA-01 עצמו כבר בנוי
  כ-Planning Gate תואם-contract).

### ממצא 2 (TC-06, TC-07) — לא באגים חדשים: אותו שורש כמו BUG-126 + BUG-127C הקיימים

- **Root Cause (אומת בקוד, 07/08/2026):** `core/turn_evidence.py`'s
  `_classify_response_claim()` — `_FAILURE` regex (שורה 134) כולל את התו `❌`
  עצמו כתנאי-התאמה יחיד, ללא תלות בהקשר: `re.compile(r"(?:❌|\b(?:failed|
  failure|error)\b|נכשל|שגיאה|לא הושלמ)")`. הבוט משתמש ב-`❌` גם להודעות
  "not found" לגיטימיות (`"❌ לא מצאתי משימה בשם..."`), לא רק לכישלונות
  אמיתיים. `compare_shadow_final_status()` (שורות 169-229) ממפה
  `evidence_status="verified_read_only"` ל-`expected_claim="neutral"` בלבד
  (שורה 179) — אין הכרה במצב "verified zero-match עם ניסוח failure-כמו".
  זו **בדיוק** אותה שרשרת-קוד שכבר תועדה בפירוט מלא תחת **BUG-126** (mismatch
  כוזב כש-status=no_evidence אך תשובה מתארת כישלון) ו-**BUG-127C**
  (A32 Single-Speaker מדכא read מאומת אמיתי) — כולל אותה מסקנה שכבר נרשמה:
  "אין תיקון בטוח ברמת A32/regex... בעיית הבנת-שפה סמנטית".
- **חשוב:** מאומת כ-**shadow-only** — `observe_shadow_finalizer()`'s docstring
  קובע במפורש "always return user text unchanged", ותואם את סטטוס WS2
  שכבר מתועד ב-`docs/architecture/turn-coordinator/README.md` (return value
  נזרק בשתי נקודות הקריאה). **אין השפעה בפועל על מה שהמשתמש רואה** — זה
  ממצא-לוגים, לא regression התנהגותי.
- **מסקנה:** לא נפתחים מספרי BUG-TC חדשים. ה-`❌` על zero-match מצטרף כדפוס-
  הפעלה מאושש נוסף שנוסף כהערה לבלוק **BUG-126** הקיים — אותה מסקנה תקפה
  (shadow-only, אין תיקון בטוח ברמת ה-regex, ממתין להחלטת owner על כיוון).
- **סטטוס:** 🔴 (ירושה מ-BUG-126/BUG-127C) — לא שונה ע"י הממצא הזה.

### BUG-163 (TC-02) — כיסוי intent חסר ל-complete_task/update_task בניסוחים טבעיים — ✅ תוקן ומאומת (טרם deployed/verified בפרודקשן)

- **דווח:** 07/08/2026, ע"י owner — נצפה תוך כדי אותה סבב בדיקות E2E
- **סביבה:** Production — `my-bot-approval-staging`
- **מסך / מודול:** `core/router/intent_router.py:51-52`
- **קלט (שני מקרים שנצפו בלוג):**
  - `"השלם את המשימה בדיקת Complete לא קיימת"` → `intent=unknown confidence=0.00`
  - `"סמן משימת מעקב כבוצעה"` → `intent=unknown`
- **Root Cause (אומת בקוד ישירות, כולל ניתוח regex מדויק מול שני הקלטים):**
  ```python
  (r"(עדכן|שנה|תעדכן).*(משימ|טאסק|task)", Intent.UPDATE_TASK, 0.95),
  (r"(סגור|סיים|סמן.*סיים|complete).*(משימ|טאסק|task)", Intent.COMPLETE_TASK, 0.95),
  ```
  שני פערים נפרדים באותו regex:
  1. **"השלם"** (פועל נפוץ ל-"complete"/"finish") **אינו** ברשימת המילים
     המזוהות כלל (`סגור|סיים|סמן.*סיים|complete`) — גם אם המילה "Complete"
     מופיעה במשפט (בתוך שם-המשימה עצמו), היא מגיעה **אחרי** "המשימה" בסדר
     המחרוזת — וה-regex דורש שהמילה-המזהה תקדם ל-`משימ/טאסק/task`, לא
     ההפך.
  2. **"סמן X כבוצעה"** (ניסוח יומיומי נפוץ ל-"mark as done") נכשל כי
     האלטרנטיבה השלישית ב-regex היא **`סמן.*סיים`** — צירוף דו-מילתי
     שדורש גם "סמן" **וגם** "סיים" באותו משפט. "סמן" לבדו, ללא "סיים",
     אינו תואם אף אלטרנטיבה ב-`(סגור|סיים|סמן.*סיים|complete)`. "כבוצעה"
     (done/completed, צורת פועל אחרת לגמרי מ"סיים") אינו מכוסה כלל.
- **Severity:** גבוהה — כל בקשת complete_task בניסוח "מקובל"/יומיומי (לא רק
  edge-case) נופלת ל-`intent=unknown handler=agent` עם אפס עדיפות דטרמיניסטית,
  עוד לפני שממצא 1 (למעלה) בכלל נכנס לתמונה.
- **קריטריוני סגירה:**
  - `"השלם את המשימה X"` מזוהה כ-`complete_task`
  - `"סמן/סמן X כבוצע/כבוצעה"` מזוהה כ-`complete_task` בלי לדרוש "סיים"
    בנוסף
  - אין regression לניסוחים הקיימים שכבר מכוסים (`סגור משימה`, `סיים
    משימה`, `complete task`)
  - שינוי מוגבל ל-`intent_router.py` בלבד — לא נוגע ב-routing/handler
    logic (זה ממצא 1, PA-01)
- **תלות:** משלים את ממצא 1 — גם אחרי ש-PA-01 ייסגר וייתן `Handler.TOOL`
  ל-update/complete, בקשות שמלכתחילה מסווגות `intent=unknown` לא יגיעו
  לשם בכלל. תיקון BUG-163 נדרש **בנוסף**, לא כתחליף.
- **תוקן (07/08/2026):** נוסף הפועל `השלם` לקבוצת-הפעלים הקיימת של
  `COMPLETE_TASK` (verb-then-target, ללא שינוי מבני), ונוספה תבנית שנייה
  נפרדת `(סמן|mark).{0,40}(משימ|טאסק|task).{0,20}(כבוצע|בוצעה|done|
  complete)` — ממוקדת ל-"סמן"/"mark" בלבד כדי לא להתנגש עם `LIST_TASKS`
  ("אילו משימות כבר בוצעו"). תיקון מוגבל ל-`core/router/intent_router.py`
  בלבד, כפי שתוכנן — לא נוגע ב-`Handler`/routing logic (זה עדיין PA-01,
  לא נסגר כאן).
- **Cross-Layer Impact Matrix:** מולא ב-`docs/architecture/action-gateway/
  BUG-160_161_162_163_TURN_COORDINATOR_FALLBACK_AUTHORITY_PLANNING_GATE_
  20260807.md` (נכתב יחד עם BUG-161/162 לפי בקשת ה-owner) — שכבה 2
  (TurnCoordinator, `intent_router.py` נצרך ישירות ע"י `router.py`)
  touched directly; שכבות 1/3 not touched (grep=0 מאומת); שכבה 4 not
  touched כלל (אין ActionContract/Gateway בסקופ).
- **בדיקות:** `test_bug163_complete_task_intent_coverage.py` (חדש, 12/12
  — כולל שני התרחישים המדויקים מהלוג, אי-שינוי ל-UPDATE_TASK/CREATE_TASK/
  DELETE_TASK, ובדיקת אי-התנגשות מפורשת עם `LIST_TASKS`) +
  `core/router/test_router.py` (44/44, ללא regression) + `smoke_tests.py`
  (PASS).
- **סטטוס:** ✅ CODE DONE, מאומת מקומית (טסטים חדשים + regression מלא) —
  **לא** נדחף/נפרס עדיין (ראה EVIDENCE בסוף הבלוק "אימות Turn Coordinator
  E2E" למעלה). לא VERIFIED IN PROD עד push+deploy+אימות production בפועל,
  לפי כלל הברזל.

### TC-12 (duplicate callback) — לא באג, פער testability

הדוח עצמו מציין זאת נכון: לא ניתן היה לשחזר callback כפול על אותו כפתור
Telegram כי הכפתור מתבטל אחרי שימוש. זה פער בכלי-הבדיקה (אין harness ל-replay
של אותו callback payload), לא ממצא על התנהגות שגויה בקוד. לא נפתח מספר BUG.
מומלץ: אם נדרש אימות אמיתי, להוסיף integration test שמדמה קריאה כפולה ל-handler
הפנימי ישירות (ללא Telegram UI), לא במסגרת הדוח הזה.

**סטטוס:** STATUS: 🟡 CODE DONE (תיעוד/מסגור בלבד), NOT VERIFIED IN PROD —
לא נכתב/שונה קוד runtime בסבב הזה. EVIDENCE: קריאה ישירה מאומתת ב-`core/
router/router.py`, `core/router/risk_router.py`, `core/router/task_resolvers.py`,
`core/turn_coordinator_runtime.py`, `app.py:966-1079,3946-3958`,
`core/turn_evidence.py:120-260`, `core/router/intent_router.py:51-52`,
`docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` (status header),
`docs/architecture/turn-coordinator/README.md`. Push לענף `claude/pr-546-
turn-coordinator-bugs-jhdrtl` ממתין לביצוע בסוף העריכה הזו.

---

## סדר עדיפות מומלץ לתיקונים

כל הפריטים למטה **מוזגים ל-`main`** (אומת 07/08/2026 ע"י `git merge-base
--is-ancestor <commit> origin/main` על כל אחד), וכולם **גם Deployed
מאומת** (Render: "Deploy live for `44fe0fb`", 07/08/2026 11:34 — `44fe0fb`
עצמו הוא הקומיט הפרוס, וכל שאר ה-commits ברשימה הם ancestors מאומתים
שלו). **BUG-153, 154, 155, 156, 158, 159 גם Verified בפרודקשן ישירות**
(owner, 07/08/2026 13:24-15:03 — ראו הבלוקים המלאים למעלה, כולל התיקון
של הראיה השגויה שסופקה בהתחלה ל-BUG-155). **BUG-157 בלבד נשאר 🟡** —
concurrency race, test-evidence (34/34) בלבד, לא production.

### PR #546 — סטטוס closure מתוקן (07/08/2026, עודכן שוב 15:03)

**כמעט "CLOSED / VERIFIED" — 6 מתוך 7 הבאגים+ה-invariants המרכזיים כן
VERIFIED IN PROD** (153, 154, 155, 156, 158, 159, וגם duplicate-suppression
+ deterministic-routing-ללא-Agent שנצפו בכל אחת מהבדיקות החיות). BUG-155
נדרשה עוד סבב אחד: הראיה הראשונה שסופקה (13:24) הייתה בפועל אותה ראיה
של BUG-158 (ראו התיקון המפורש בבלוק של BUG-155); הראיה השנייה (15:03,
לחיצת ✅ אחרי >10 דק') כן פגעה בדיוק ב-`_reject_stale_telegram_approval()`
— אומת מול הקוד (`rejected_by="ttl_expired"` ייחודי בריפו לנתיב המתוקן)
— **BUG-155 עכשיו VERIFIED IN PROD.** **BUG-157 בלבד נשאר 🟡**
deployed-בלבד — race מקביל, אין ערך מעשי בניסיון שחזור ידני, test
evidence (34/34) נחשב closure evidence מספק. **בנוסף**, אימות ה-
production הזה עצמו חשף 3 באגים חדשים (BUG-160/161/162, למטה) בנתיב
ה-fallback ל-Agent — לא חלק מ-#546 המקורי, אך מספיק קרובים ארכיטקטונית
(אותו turn/reply-ownership contract) שסגירה "סופית" ראויה להמתין
לפחות להכרעת owner על BUG-161 (מדיניות reconfirmation ב-Agent path).

1. **BUG-155** — TTL expiry משאיר pending חי (קריטי) — ✅ מוזג + deployed + **VERIFIED IN PROD** (PR #550)
2. **BUG-153** — create חדש אחרי rejection נחסם (גבוה) — ✅ מוזג + deployed + **VERIFIED IN PROD** (PR #550)
3. **BUG-154** — parser crash בניסוח "ל־תאריך" (גבוה) — ✅ מוזג + deployed + **VERIFIED IN PROD** (PR #550)
4. **BUG-156** — שעה אינה נשמרת (בינוני-גבוה) — ✅ מוזג + deployed + **VERIFIED IN PROD** (PR #550)
5. **בדיקת suppression fallback** — ✅ נסגר, מוזג + deployed (PR #550)
6. **BUG-157** — `propose_action()` לא-אטומי (concurrency, **נגיש בפועל** —
   לא latent, ראה "Root Cause" למעלה: scheduler thread + webhook thread
   יכולים לקרוא במקביל תחת ה-deployment הנוכחי) — ✅ מוזג + deployed ל-main
   (PR #552, PR #555), **Verified בפרודקשן: לא (test evidence בלבד)**
7. **BUG-158** — כפתור שפג מדווח "אינה זמינה" גם כש-contract עדיין pending
   (גבוה) — ✅ מוזג + deployed + **VERIFIED IN PROD** (PR #556)
8. **BUG-159** — פרסר create_task לא מזהה "משימת"/הוסף/תוסיף (בינוני-גבוה)
   — ✅ מוזג + deployed + **VERIFIED IN PROD** (PR #557)
9. **BUG-160** — מרכאה לא מאוזנת עוקפת את המסלול הדטרמיניסטי (גבוה) —
   ✅ **תוקן ומאומת** (15/15 טסטים חדשים, regression מלא ירוק) — טרם
   deployed/verified בפרודקשן
10. **BUG-161** — reconfirmation לא עקבי בין המסלול הדטרמיניסטי ל-Agent
    (גבוה) — 🟡 **Cross-Layer Impact Matrix הושלם** + מומש חלקית
    (`core_knowledge.py` honesty rule, מונע הבטחה מראש) + **תלות ה-
    enforcement (BUG-162) תוקנה בקוד** — סגירה מלאה תלויה באימות-
    production חוזר
11. **BUG-162** — הפרת turn-ownership: Agent מדבר ב-turn של gateway
    (בינוני-גבוה) — 🟡 **interim patch תוקן בקוד (07/08/2026, לא TC6
    עצמו — ראו סיווג מתוקן בבלוק המלא למעלה):** ⚠️ המסקנה הקודמת
    ("ממתין רק להפעלת flag") הייתה **שגויה** — ה-owner הראה שהדגל
    כבר `true` ב-Render ובכל זאת הבאג קרה. ה-root cause האמיתי:
    `_queue_approval_detailed_impl()`'s בלוק ה-block הגנרי (זה שבפועל
    מטפל ב-BUG-153's rejected-block) פשוט לא הגדיר `reply_owner`/
    `lifecycle_result` בכלל — ללא קשר לדגל. תוקן: **32/32 טסטים חדשים**
    (`test_bug162_gateway_reply_owner_on_generic_block.py`, כולל
    enumeration ממצה על כל 6 ערכי `existing.status` שמגיעים ל-branch
    הזה) + regression מלא (11 קבצי טסט נוספים, כולם ירוקים). **Closure
    audit מלא בוצע** — ראו `docs/architecture/action-gateway/BUG-162_
    SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md`: מיפוי כל 11 exit-paths של
    הפרודיוסר (רק זה היה שגוי, שאר ה-10 נכונים-בעיצוב), הסבר תהליכי
    מדויק ל"למה זה קרה למרות ה-DoD" (Gate C ב-`TURN_COORDINATOR_
    PROPOSAL_V2.md` מחייב regression-coverage מלא, אבל חל רק על "Phase 3
    הרשמי" שמעולם לא נפתח — PR #471 שלח מימוש-מקדים לא-רשמי של אותו
    מנגנון בלי לעבור מול ה-DoD הזה), וממצא "duplicate authority" פתוח
    (שני מנגנונים עצמאיים לחישוב "turn שייך ל-gateway" — אחד לאכיפה,
    אחד ל-shadow — לא תוקן, רק מתועד, לפי הנחיה מפורשת שלא לתכנן מנגנון
    חדש). נותר: אימות-production חוזר לתרחיש המקורי; חלק ב' של ההחלטה
    ("Clarification כסוג-הודעה של Coordinator", מכסה את תרחיש-ה-
    Agent-מבטיח-מראש בלי tool_use) עדיין לא מומש — סעיף פתוח נפרד
12. **BUG-163** — כיסוי intent חסר ל-complete_task/update_task ("השלם",
    "סמן...כבוצע/ה") (גבוה) — ✅ **תוקן ומאומת** (12/12 טסטים חדשים,
    44/44 regression) — טרם deployed/verified בפרודקשן

**עדכון מסגור (07/08/2026, אימות Turn Coordinator E2E):** דוח בדיקות E2E
נוסף (12 תרחישים על Update/Complete task) נבדק מול הקוד ושולב — ראו הבלוק
המלא "אימות Turn Coordinator E2E" למעלה. תוצאה: השורש המרכזי (`Handler.TOOL`
נקבע דטרמיניסטית רק ל-`CREATE_TASK`, לא ל-`UPDATE_TASK`/`COMPLETE_TASK`,
למרות שה-resolver/gateway המלא כבר קיים ומחובר) **אינו באג חדש** — הוא הפער
המדויק ש-`docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` (Status:
PLANNING ONLY) כבר קיים כדי לסגור; הבדיקות החדשות הן ראיית-production חיה
לכך שהפער אמיתי, לא רק תיאורטי. ממצא evidence-classification נוסף (❌ על
zero-match) שויך ל-BUG-126/BUG-127C הקיימים (shadow-only, אין תיקון בטוח
ברמת regex). ממצא אחד חדש ואמיתי נפתח כ-**BUG-163** (כיסוי intent regex).
