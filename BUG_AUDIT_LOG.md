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
