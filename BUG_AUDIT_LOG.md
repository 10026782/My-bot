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

### BUG-008 — Lead Business Outcome 422 (trailing space in Airtable options)
- **דווח:** 17/06/2026 — Airtable PATCH נכשל עם `422 INVALID_MULTIPLE_CHOICE_OPTIONS`, `keys=['Business Outcome', 'status']`; ב-UI רק "סמן כמתאים" עבד, שאר כפתורי הסטטוס הציגו "update failed"
- **מסך / מודול:** `tma_api.py` — `update_lead_status`, `set_lead_outcome`, `patch_lead`; `airtable_schema.py` — קבועי `LeadStatus`/`LeadOutcome` חדשים
- **Severity:** High — חסם את כל כפתורי הסטטוס/תוצאה במסך Lead Detail מלבד אחד
- **Root Cause:** שדה `Leads."Business Outcome"` (singleSelect, `fldVa5wSmAqcKLi86`) כולל trailing space ב-7 מתוך 8 האופציות החיות שלו (`"open "`, `"needs_followup "`, `"meeting_scheduled "`, `"converted "`, `"not_relevant "`, `"lost "`, `"duplicate "` — רק `"archived"` נקי). הקוד שלח ערכים נקיים (ללא רווח), ו-Airtable (עם typecast כבוי) דחה את הכתיבה כניסיון ליצור אופציה חדשה. אומת ישירות מול הסכמה החיה דרך Airtable MCP `get_table_schema` (2026-06-17).
- **תוקן ב-commit:** `7d5cb3a`
- **תוקן ב-branch:** `claude/meta-whatsapp-phase-1-q6pp3e`
- **תיקון:** `LeadOutcome.BY_KEY` ב-`airtable_schema.py` ממפה מפתח נקי קנוני (ללא רווח) לערך המדויק בפועל ב-Airtable; `LeadStatus.ALL` לבדיקת תקינות `status`. שני השדות מאומתים לפני PATCH — אם הערך לא תקין, מוחזר 400 ברור במקום לאפשר ל-Airtable להחזיר 422.
- **Merged:** לא — ממתין לאימות ידני לפני merge (לפי הנחיית המשתמש)
- **Deployed:** לא ידוע — דרוש Render deploy
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` עבר; `test_integration.py` 4/4 PASS; `smoke_tests.py` 5/6 PASS (כשל אחד תלוי-סביבה, ידוע מראש — `anthropic` import); `npm run build` עבר. אין עדיין אימות בפרודקשן החיה (5 כפתורי סטטוס/תוצאה).
- **סטטוס:** 🟡 Fixed — ממתין לאימות ידני בפרודקשן

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
### BUG-020 — airtable_schema.py: כמה קבועי טבלה/שדה לא תאמו ל-base החי (מומש חלקית, לא אומת)
- **דווח:** 24/06/2026 — אודיט ידני מול "בסיס עיקרי" (`app4bcgoX7t0HUVnm`) דרך Airtable MCP (`list_tables_for_base`), אחרי שהתברר ש-`schema_cache.json` הקיים הוא seed שנוצר מהקוד עצמו ולא snapshot אמיתי מ-Airtable (ראה BUG-021).
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `airtable_schema.py`
- **תיאור:** השוואה שדה-שדה בין `class Tables` / `*Fields` ל-schema החי גילתה: `Tables.LEARNINGS = "למידות ותובנות"` בזמן שהטבלה החיה נקראת `"למידות ותובנות (Learnings & Insights)"`; `class AssetsFields` הגדיר 9 שדות עבריים ("שם הנכס", "סוג"...) לטבלת "Assets (Personal)" שלא קיימת — הטבלה החיה בשם "Assets" נבנתה לנדל"ן עם שדות אנגליים שונים בתכלית (Asset Type, Current Value, Equity, Asset Potential/Risks...); `ProfileFields.NAME = "Name"` בזמן שהשדה החי הוא `"name"` (אות קטנה), ו-`ProfileFields.PROFILE_DATA = "ProfileData"` לא קיים בכלל; `Tables.IMPORTS`/`Tables.TENANTS`/`Tables.DAILY_TASKS` מצביעים לטבלאות שלא קיימות ב-base בכלל. גם התגלתה טבלה חיה חדשה — `TRAFFIC_SOURCES` (BOSS Growth P0) — שלא הייתה מתועדת בקוד בכלל.
- **Severity:** Medium — `Tables.LEARNINGS`/`AssetsFields`/`ProfileFields`/`Tables.IMPORTS`/`Tables.TENANTS`/`Tables.DAILY_TASKS` אומתו כ-**לא נקראים משום קוד חי** (`grep` ברחבי הריפו) — drift תיעודי בלבד, לא באג פעיל. (לעומת BUG-017/018/019 למטה — אלה כן נקראים מקוד חי ונכשלים בפועל.)
- **Root Cause:** `airtable_schema.py` תיעד כוונה/תכנון שלא עודכן אחרי שהטבלאות נבנו/שונו בפועל ב-Airtable.
- **שינוי שבוצע:** עודכן ישירות ב-`airtable_schema.py` (ללא commit בזמן התיעוד המקורי): שם `Tables.LEARNINGS` עודכן; `AssetsFields` הוחלף לחלוטין לשדות האמיתיים; `ProfileFields.NAME` עודכן ל-`"name"` + הערה ש-`PROFILE_DATA` עדיין לא קיים חי; `Tables.IMPORTS`/`Tables.TENANTS`/`Tables.DAILY_TASKS`/`DailyTaskFields`/`DailyTaskStatus` סומנו במפורש כ-DEAD CODE (בדומה לסימון F13); נוסף `class TrafficSourcesFields` לתיעוד הטבלה החדשה.
- **תועד ב-commit:** commit הענף שמוסיף את BUG-020 ואת עדכון `airtable_schema.py`
- **Merged:** לא
- **Deployed:** לא
- **Verified בפרודקשן:** לא — `py_compile airtable_schema.py` ו-`smoke_tests.py` (6/6 PASS) הורצו מקומית בלבד
- **Verification ראיה:** השוואה ישירה ל-`list_tables_for_base`/`get_table_schema` החי דרך Airtable MCP, 24/06/2026; `py_compile` עבר; `smoke_tests.py` 6/6 PASS
- **סטטוס:** 🟡 Implemented but not yet verified — ממתין ל-merge + אימות

### BUG-017 — inbound_handler.py כותב ל-LeadFields.UPDATED_AT שלא קיים ב-Leads החי
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `inbound_handler.py` — `_update_existing()`, שורות 75-86 (F06, נקרא בפועל ע"י `email_inbound.py`)
- **תיאור:** `_update_existing()` עושה PATCH יחיד ל-Leads עם 3 שדות: `SUMMARY`, `UPDATED_AT`, `EXTERNAL_ID`. `LeadFields.UPDATED_AT = "updated_at"` — שדה שלא קיים בטבלת Leads החיה (אומת דרך Airtable MCP: אין `updated_at`, יש רק `created_at`). Airtable דוחה PATCH עם שדה לא קיים (422) — **כל הבקשה נכשלת**, לא רק השדה החסר, כך שגם `SUMMARY` וגם `EXTERNAL_ID` לא מתעדכנים בפועל כשליד קיים שולח הודעה נכנסת חדשה. ה-`except` הסוגר רק כותב ל-log, אז זה נכשל בשקט.
- **Severity:** High — F06 inbound-lead gate בשימוש בפועל; כל "ליד קיים עונה שוב" לא מתעדכן בכלל ב-production.
- **Root Cause:** הקוד הניח קיומו של שדה `updated_at` שלא נוצר בפועל ב-Airtable.
- **תוקן:** לא תוקן עדיין — ממתין להחלטת המשתמש בין: (א) להוסיף שדה Airtable מטיפוס "Last Modified Time" בשם "Updated At" (לא דורש כתיבה מהקוד בכלל) (ב) להוסיף שדה רגיל "updated_at" ולהשאיר את הקוד (ג) להוריד את השורה `LeadFields.UPDATED_AT: _now_iso()` ואת `LeadFields.UPDATED_AT` מ-`airtable_schema.py` לגמרי.
- **Merged:** לא
- **Deployed:** לא
- **Verified בפרודקשן:** לא
- **Verification ראיה:** אומת רק דרך השוואה ל-schema החי ב-Airtable MCP — לא אומת דרך webhook אמיתי
- **סטטוס:** Open — דורש החלטת המשתמש לפני תיקון

### BUG-018 — tma_api.py כותב ל-TaskFields.LEAD_LINK שלא קיים ב-Tasks החי → "צור משימה מליד" נכשל
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **דווח על ידי:** המשתמש
- **מסך / מודול:** `tma_api.py` — POST ל-`Tables.TASKS` ב-flow של "צור משימה מליד" ב-TMA, שורה 1499 (וגם 1513 ב-queue-for-approval path)
- **תיאור:** `task_fields[TaskFields.LEAD_LINK] = [lead_id]` — `TaskFields.LEAD_LINK = "Leads"`, אבל אין שדה linked-record כזה בטבלת "משימות (Tasks)" החיה (אומת דרך Airtable MCP). ה-POST השלם נכשל (500) כי Airtable דוחה שדה לא קיים — "צור משימה מליד" נכשל **בכל קריאה**, גם ל-owner וגם ב-approval flow למנהל.
- **Severity:** High — חוסם תכונה שלמה ב-TMA (יצירת משימה מתוך מסך ליד).
- **Root Cause:** הקוד הניח קיומו של שדה linked-record "Leads" על Tasks שלא נוצר בפועל.
- **תוקן:** לא תוקן עדיין — ממתין להחלטת המשתמש בין: (א) להוסיף שדה Linked Record בשם "Leads" לטבלת "משימות (Tasks)" ב-Airtable (ב) להוריד את השורה `task_fields[TaskFields.LEAD_LINK] = [lead_id]` ואת `TaskFields.LEAD_LINK` מ-`airtable_schema.py`.
- **Merged:** לא
- **Deployed:** לא
- **Verified בפרודקשן:** לא
- **Verification ראיה:** אומת רק דרך השוואה ל-schema החי ב-Airtable MCP — לא אומת דרך קריאה אמיתית ל-endpoint
- **סטטוס:** Open — דורש החלטת המשתמש לפני תיקון

### BUG-019 — crm.py: כמה פונקציות כותבות/מסננות לפי שדות ש-Contacts/Deals/Payments החיים לא מכילים
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
- **תוקן:** לא תוקן עדיין — ממתין להחלטת המשתמש לכל תת-סעיף (להוסיף שדות חסרים ל-Airtable מול להוריד/להחליף לוגיקה בקוד). מומלץ לתקן את כל הסעיף כמקבץ אחד ולהריץ טסט אינטגרציה ידני לפני merge.
- **Merged:** לא
- **Deployed:** לא
- **Verified בפרודקשן:** לא
- **Verification ראיה:** אומת רק דרך השוואה ל-schema החי ב-Airtable MCP — לא אומת דרך הרצת הפונקציות בפועל
- **סטטוס:** Open — דורש החלטת המשתמש לפני תיקון

### BUG-021 — schema_audit.py: UnboundLocalError במקום fallback ל-cache כשה-live fetch נכשל
- **דווח:** 24/06/2026 — תוך כדי ניסיון להריץ `schema_audit.py` בלי `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` ב-env
- **דווח על ידי:** המשתמש (זוהה ע"י קלוד תוך כדי ביצוע)
- **מסך / מודול:** `schema_audit.py` — `run_audit()`, שורות 48-65
- **תיאור:** אם `sv.refresh_cache()` זורק exception (חסרי credentials), הענף `except` (שורות 53-55) רק מדפיס אזהרה "ממשיך עם cache קיים" אבל **לא בפועל טוען cache** — המשתנה `tables` נשאר לא מוגדר, והקריאה הבאה ל-`tables.get(...)` (שורה 65) קורסת עם `UnboundLocalError`. ה-fallback ל-cache עובד רק אם מריצים עם `--offline` במפורש (`sys.argv`), לא אוטומטית כמו שההודעה מבטיחה.
- **Severity:** Low — הסקריפט עצמו לא בשימוש production, אבל ההודעה המוטעה ("ממשיך עם cache קיים") מטעה את מי שמריץ אותו.
- **Root Cause:** ה-except branch לא קורא בפועל את לוגיקת ה-fallback הקיימת בענף `else` (שורות 56-59) של `live=False`.
- **תוקן:** לא — מוצע: בענף ה-`except`, להוסיף את אותה לוגיקת טעינת cache מהדיסק שכבר קיימת בענף `else`.
- **Merged:** לא
- **Deployed:** לא
- **Verified בפרודקשן:** N/A — סקריפט פיתוח, לא production
- **Verification ראיה:** שוחזר ידנית: הרצת `python3 schema_audit.py` בלי env vars מתאימים קורסת עם `UnboundLocalError: tables`
- **סטטוס:** Open

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
- **סטטוס:** 🟡 MERGED TO MAIN (`ca1f5a0`) — ממתין לאימות פרודקשן על ליד **טרי** שנוצר אחרי התיקון (לא רק היסטוריה ישנה).

### FLAGGED (cleanup candidates, not bugs) — קוד מת ב-airtable_schema.py / קובץ cache מטעה
- **דווח:** 24/06/2026 — באותו אודיט כמו BUG-020
- **תיאור:** אומת ב-`grep` (0 שימושים מעבר להגדרה עצמה):
  - `class ImportsFields` + `Tables.IMPORTS` — הטבלה "Imports" לא קיימת ב-Airtable החי, ואין קובץ אחר שמשתמש בקבועים האלה. בטוח למחיקה מלאה.
  - `class TenantsFields` + `Tables.TENANTS` — הטבלה "Tenants" לא קיימת חי; `tenant_provisioner.py` (F08) לא מייבא מ-`airtable_schema` בכלל, אז אין תלות. בטוח למחיקה מלאה.
  - `class DailyTaskFields` + `class DailyTaskStatus` + `Tables.DAILY_TASKS` — הטבלה "Daily_Tasks" לא קיימת חי (`Daily_Checkin` היא הטבלה החיה הנפרדת בשימוש בפועל). תלות אחת: `tma_api.py:27` מייבא `DailyTaskFields, DailyTaskStatus` בלי להשתמש בהם בשום מקום אחר — import מת. מחיקה דורשת גם הסרת שני השמות האלה משורת ה-import ב-`tma_api.py:27`.
  - `schema_cache.json` (root) — מכיל `"fetched_at": "seed-from-schema-py"`, כלומר זה לא snapshot אמיתי מ-Airtable אלא seed שנוצר מתוך הקוד עצמו, ומכיל רק 15 מתוך כל הטבלאות החיות. מטעה כל הרצה של `schema_audit.py --offline`. אפשר למחוק (יחודש בהרצה חיה תקינה) או לרענן עם credentials אמיתיים.
- **למה לא נמחק:** ממתין לאישור מפורש של המשתמש למחיקה (לא בוצעה מחיקה יזומה ללא בקשה).
- **סטטוס:** Open — ממתין להחלטה

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
- **סטטוס:** ✅ תוקן | ⚠️ אימות מלא עם מספר חדש לגמרי — ממתין

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
- **סטטוס:** ✅ תוקן ומוזג

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

### BUG-036 (BUG-DH-03) — formula injection ב-`_resolve_decision_ref`
- **תאריך:** 30/06/2026
- **קובץ:** `cmd_decision.py`
- **שורש:** `FIND('{ref}', ...)` ללא sanitization על `ref` מגיע מ-user input
- **תיקון נדרש:** `_safe_formula_param` לפני הכנסה ל-formula
- **סטטוס:** 🔴 פתוח — עדיפות גבוהה | חסום לפני הפעלת `FEATURE_DECISION_HUB` בפרודקשן

### BUG-037 (BUG-DH-04) — formula injection ב-`maybe_supersede`
- **תאריך:** 30/06/2026
- **קובץ:** `decision_pipeline.py`
- **שורש:** Claim Topic מגיע מ-raw content ויכול לשבור Airtable formula
- **תיקון נדרש:** `_safe_formula_param` על Claim Topic לפני הכנסה
- **סטטוס:** 🔴 פתוח — עדיפות גבוהה | חסום לפני הפעלת `FEATURE_DECISION_HUB` בפרודקשן

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
- **סטטוס:** ✅ תוקן ומאומת מקומית — ממתין ל-merge + production verification (ראה "כלל ברזל" בתחתית הקובץ).

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
- **סטטוס:** ✅ תוקן ומאומת מקומית — ממתין ל-merge + production verification.

### BUG-075 — `/api/tma/upload` יש authentication אבל אין authorization לפי role — ✅ תוקן 06/07/2026
- **תאריך:** 06/07/2026
- **דווח על ידי:** ביקורת אבטחה (`app.py`/`tma_api.py`/`tools/`) — מכונה "BUG-074" בטיקט המקורי; ממוספר כאן BUG-075 בהמשך ל-BUG-074 למעלה.
- **קבצים:** `tma_api.py` (`tma_upload`, שורה 3033).
- **Severity:** Medium — דורם: `FEATURE_MEDIA_UPLOAD` כבוי כברירת מחדל (מחזיר `coming_soon` תמיד), אבל ברגע שיופעל, כל identity מאומתת (כולל `lead`/`guest`/`readonly`) תוכל להעלות קבצים — בניגוד לכל endpoint כתיבה אחר ב-`tma_api.py` שבודק role.
- **ממצא (מאומת בקוד):** בניגוד לכל שאר endpoints הכתיבה ב-`tma_api.py` (כולם בודקים `identity.is_owner` או `identity.role in {OWNER, MANAGER, PARTNER}`), `tma_upload()` היה מסתמך אך ורק על `@require_tma_auth` (מוודא HMAC initData תקין — כלומר *מי* זה, לא *מה מותר לו*) — ללא שום בדיקת role.
- **תיקון:** נוספה בדיקת role זהה למדיניות הקיימת ב-endpoints אחרים: `if identity.role not in {Role.OWNER, Role.MANAGER, Role.PARTNER}: return jsonify({"error": "forbidden"}), 403` — לפני גישה ל-`request.files`. בדיקת ה-flag (`FEATURE_MEDIA_UPLOAD`) נשארה **לפני** בדיקת ה-role (ללא שינוי בהתנהגות כש-flag כבוי).
- **בדיקה:** `test_bug075_tma_upload_role_gate.py` (חדש, 17/17) — flag כבוי מחזיר `coming_soon` לכל role (ללא שינוי); flag דלוק: guest/lead/readonly/employee נחסמים ב-403 עם body בטוח; owner/manager/partner עוברים את שער ה-role (מגיעים ללוגיקת ההעלאה עצמה — לא לצינור Drive/Airtable המלא, שאינו קשור לתיקון ההרשאה הזה). נקרא ישירות דרך `tma_upload.__wrapped__` (מעקף את בדיקת ה-HMAC של `@require_tma_auth`, שלא שונתה ואינה נבדקת כאן) בתוך `Flask.test_request_context`.
- **סטטוס:** ✅ תוקן ומאומת מקומית — ממתין ל-merge + production verification.

### BUG-076 — הפרדת "confirmation" מ-"approval": lead capture בטוח לא צריך אישור owner — ✅ תוקן 06/07/2026
- **תאריך:** 06/07/2026
- **דווח על ידי:** החלטת מוצר של הבעלים, בתגובה לתופעת-הלוואי שתועדה ב-BUG-074 למעלה — lead capture הוא low-risk ולא אמור לדרוש אישור owner.
- **קבצים:** `core/action_gateway.py` (`classify_approval_policy()`, `_lead_safe_fields()`, `_is_internal_role()`, `ActionContract.approval_policy`, `propose_action()`, `approve()`).
- **החלטת מדיניות (לא קוד, נקבעה ע"י הבעלים):** שני מושגים נפרדים — **"confirmation"**: המבקש מאשש שהמערכת הבינה נכון את הטיוטה/preview (סיכון נמוך, self-confirm מותר). **"approval"**: זהות מורשית (owner/"actions.approve") חייבת להסמיך פעולה רגישה (הכלל הקשיח של BUG-074, ללא שינוי). `approve()` **נשאר** שער האכיפה המרכזי לכל הפעולות — ה-carve-out הוא צר ומחושב מרכזית, לא "החלשה" גורפת.
- **תיקון:** `ActionContract` קיבל שדה חדש `approval_policy` (`"approval"` ברירת מחדל, או `"self_confirm"`). `classify_approval_policy(tool_name, tool_inputs)` מחושבת ב-`propose_action()` מתוך ה-payload המנורמל בפועל (לא נסמך על טענת הקורא) ומחזירה `self_confirm` **רק** עבור: `tool_name` ∈ {`airtable_add`, `airtable_update`}, טבלה=`Leads`, ושדות שכולם בתוך allowlist בטוח — `airtable_add` (יצירה): `Name/phone/channel/memory_key/domain/source/status/summary/Score/sender_id` (תואם בדיוק את מה ש-`_write_one_lead()`/`_propose_lead_write()` כבר כותבים ל-ליד חדש — קביעת מצב התחלתי, לא "escalation"). `airtable_update` (עדכון ליד קיים): allowlist **צר בהרבה** — רק `phone/summary/domain` (תואם בדיוק את `_propose_lead_write()`), **בלי** status/score/tier/Owner/Next Action — כל אלו escalation/assignment ונשארים `approval`. כל tool/table/field שלא ברשימה → `approval` (fail-closed). `approve()`: אם `contract.approval_policy == "self_confirm"` — מאושר רק אם המאשר הוא **בדיוק** אותה זהות שביקשה (`approver == contract.canonical_user_id`) **וגם** מחזיק role פנימי (owner/partner/manager/employee) — לא "כל אחד". אחרת (כולל כל מקרה אחר) — הכלל הקשיח של BUG-074 (owner/"actions.approve" בלבד) נשאר בעינה ללא שינוי.
- **תוצאה:** manager/partner/employee יכולים כעת לאשש בעצמם ("כן") טיוטת יצירת/עדכון-בטוח של ליד — בדיוק כמו שכתיבת ליד אוטומטית (`FEATURE_AUTO_CAPTURE`) כבר עושה היום ללא אישור נפרד. כל פעולה אחרת (מחיקה, שדות מוגנים, סטטוס/שיוך, דילס/פיננסים/יוצא/bulk) עדיין דורשת owner/"actions.approve" בדיוק כמו ב-BUG-074.
- **בדיקה:** `test_bug076_lead_confirmation_policy.py` (חדש, 32/32) — matrix של `classify_approval_policy()` (יצירה בטוחה→self_confirm, עדכון בטוח→self_confirm, עדכון סטטוס/Owner/Score→approval, טבלה אחרת→approval, כלי לא-ליד→approval, כלי פיננסי→approval, fields ריק/חסר→approval fail-closed, "airtable_delete" היפותטי על Leads→approval כי הכלי עצמו לא ב-allowlist); employee מאשש בעצמו יצירת ליד בטוחה (1); employee לא יכול לאשש בעצמו פעולה לא-ליד (2); employee לא יכול לאשש בעצמו עדכון סטטוס/שדה מוגן (3, כולל אימות שה-contract מסווג `approval` ולא `self_confirm`); owner עדיין יכול לאשר פעולת approval אמיתית אחרי הכל (4); manager אחר (לא המבקש המקורי) לא יכול "לאשש" preview של מישהו אחר — self_confirm דורש בדיוק אותה זהות, לא כל role פנימי (5). אפס רגרסיה: `test_bug074_approval_authority.py` עודכן לתרחיש שאינו lead-capture (טבלת "Deals" במקום "Leads") כדי להמשיך לבדוק את הכלל הכללי, נשאר 22/22 ירוק. כל 50 קבצי `test_*.py` בריפו ירוקים חוץ מ-`test_document_converter.py` (לא קשור).
- **סטטוס:** ✅ תוקן ומאומת מקומית — ממתין ל-merge + production verification.
