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
