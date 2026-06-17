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

---

## פיצ'רים (לא באגים) — מעקב אימות

### FEATURE — Approval Policy: Emergency Window + OTP + Policy Gate
- **דווח/תוכנן:** 17/06/2026 — לפי `Approval_Policy_Spec.md`
- **מסך / מודול:** `core/emergency_window.py` (phase 1), `core/otp.py` (phase 2), `tma_api.py` — `_queue_tma_write_approval` policy gate (phase 3); טבלת Airtable `Emergency_Window` (`tblyC9hb6INMUCOkR`); `tma-frontend/src/api.ts` — header `X-TMA-Platform`
- **תיאור:** שכבת אישור מדורגת לפי סיכון (Low/Medium/High/Critical) × פלטפורמה (mobile/desktop). Low תמיד מותר; Medium מהטלפון דורש אישור כפול (`confirmed`); High מהטלפון דורש Emergency Window פעיל + OTP; Critical לעולם לא מהטלפון, ודורש OTP בכל מצב — כולל desktop. `web` מסווג כ-mobile (fail-closed — Telegram Web עשוי לרוץ בדפדפן בטלפון). חסר platform header = mobile (fail-closed). Emergency **Window** (חריג מבוקר ל-High) ≠ Emergency **Stop** (C33, מקפיא הכל).
- **תוקן/מומש ב-commits:** `8209d36` (phase 1: טבלה + `emergency_window.py`), `a57fd7f` (phase 2: `otp.py`), `44457dd` (phase 3: policy gate + 3-tuple status + frontend header), `ce111bb` (`web`→mobile fix + doc updates), `92e4b2b` (CORS `X-TMA-Platform` header + derived RISK_LEVEL write) — **merge commit `4e933b0`** ("Merge pull request #69")
- **תוקן ב-branch:** `claude/meta-whatsapp-phase-1-q6pp3e`
- **Feature Flag:** `EMERGENCY_WINDOW` — **כבוי כברירת מחדל.** דגל כבוי = התנהגות זהה 100% להיום (כולל 202 קשיח).
- **Merged:** **כן — PR #69, מוזג ל-`main` ב-commit `4e933b0`.** אומת ישירות: GitHub API `pull_request_read` → `merged: true`, `merged_by: 10026782`, `merged_at: 2026-06-17T18:56:00Z`; `git fetch origin main` → `origin/main` על `4e933b0`.
- **Deployed:** לא ידוע — Render Auto-Deploy מוגדר על `main` (`docs/operations/DEPLOYMENT.md`), כך שמיזוג ל-`main` ככל הנראה הפעיל deploy אוטומטי, אך **לא אומת ידנית** מול Render Dashboard מהסביבה הזו. `EMERGENCY_WINDOW` נשאר כבוי כך שגם אם ה-deploy רץ, אין שינוי התנהגות בפרודקשן.
- **Verified בפרודקשן:** לא — ממתין לאימות ידני
- **Verification ראיה:** `py_compile` עבר על `tma_api.py`; `npm run build` עבר; `smoke_tests.py` 5/6 PASS (כשל `anthropic` import תלוי-סביבה, ידוע מראש); מטריצת 12 תרחישים (Low/Medium/High/Critical × mobile/desktop/web + window on/off + OTP) אומתה מול קוד הגייט האמיתי — כולל אימות חוזר ש-`web` נחסם כ-mobile וש-flag off מחזיר 202 זהה; CORS preflight מאומת מחזיר `X-TMA-Platform`; כתיבת RISK_LEVEL מאומתת מול live Airtable choices (`low`/`medium`/`high`). אין עדיין אימות בפרודקשן החיה.
- **סטטוס:** 🟡 MERGED TO MAIN (PR #69, `4e933b0`) — flag off, ממתין לאימות פרודקשן לפני הדלקת `EMERGENCY_WINDOW`
