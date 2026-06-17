# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-17
**עודכן על ידי:** Claude Code Audit — session 7f9f89d8-d8dd-578a-8430-a9fedea6c089

---

## 1. SYSTEM STATE — מה רץ עכשיו בפרודקשן
- **Branch בפרודקשן:** `main` (לפי `docs/operations/DEPLOYMENT.md:87` — Auto-Deploy: Yes, main branch). לא אומת ישירות מול Render Dashboard.
- **Commit אחרון בפרודקשן:** לא ידוע — דרוש בדיקה ידנית. `origin/main` ב-GitHub עומד על `7313b2e3da6801196aaab88d1528af36b6c17aec` ("Merge pull request #67: N06 — Ventures Screen (TMA)", 2026-06-17 11:41 +0300), אבל אין גישה ל-Render Dashboard מהסביבה הזו כדי לאשר ש-Render בפועל פרוס על commit זה (DEPLOYMENT.md מזהיר במפורש: "Render על commit ישן" הוא תרחיש ידוע, ויש לבדוק עם `git ls-remote origin main` מול Render Events).
- **תאריך deploy אחרון:** לא ידוע — דרוש בדיקה ידנית (Render Dashboard → Events).
- **סטטוס `/health` endpoint:** לא ידוע — דרוש בדיקה ידנית. נסיון `curl https://my-bot-jqz2.onrender.com/health` מסביבת האודיט הזו נחסם ב-egress (`403 Host not in allowlist`) — לא ניתן לאמת מכאן.
- **סטטוס Telegram bot:** לא ידוע — דרוש בדיקה ידנית (`getWebhookInfo` לא נגיש מסביבה זו).
- **סטטוס Airtable connection:** ✅ עובד — אומת ישירות מסביבת האודיט הזו דרך Airtable MCP (`list_tables_for_base` על `app4bcgoX7t0HUVnm` החזיר סכמה מלאה של ~30 טבלאות פרודקשן, 2026-06-17). זה מאמת שה-Base ID נכון ונגיש, **לא** שהבוט עצמו (Render) מתחבר אליו בהצלחה.
- **Emergency Stop פעיל:** לא ידוע — דרוש בדיקה ידנית. הדגלים (`EMERGENCY_STOP_*`) נשמרים ב-`/tmp/emergency_flags.json` על תהליך ה-Render החי (`feature_flags.py:66`); הקובץ לא קיים בסביבת האודיט הזו (container זמני/נפרד) ולכן אין דרך לדעת את המצב האמיתי בפרודקשן מכאן.

## 2. LAST VERIFIED — מה אומת לאחרונה
| Feature | תאריך אימות | ראיה (commit/message) | מי אימת |
|---------|------------|----------------------|---------|
| Airtable Base ID `app4bcgoX7t0HUVnm` נגיש ותואם סכמה | 2026-06-17 | Airtable MCP `list_tables_for_base` — schema dump חי | Claude Code Audit |
| N06 Ventures — שדות תואמים 1:1 בין קוד לסכמה חיה | 2026-06-17 | השוואת `VentureFields`/`tma_api.py` מול סכמת Airtable חיה לטבלת Ventures | Claude Code Audit |
| `py_compile` על מודולי ליבה (`app.py`, `tma_api.py`, `airtable_schema.py`, `crm.py`, `tool_registry.py`, `tools/dispatcher.py`) | 2026-06-17 | exit code 0 | Claude Code Audit |
| `python3 test_integration.py` | 2026-06-17 | 4/4 PASS | Claude Code Audit |
| `python3 smoke_tests.py` | 2026-06-17 | 5 PASS, 1 FAIL (`anthropic` import — תלוי-סביבה, ידוע מראש, לא קשור לקוד) | Claude Code Audit |
| BUG-005/006 (`/status` decorator, Hub debug block) | 2026-06-16 | commit `628d2bb` | git log (לא אומת בפרודקשן בפועל) |
| תיקון tier ל-writable singleSelect | לא ידוע תאריך מדויק | commit `3d8ab50` + סכמה חיה מאשרת `tier` קיים כ-`singleSelect` (`fld4eC2mEYrviL3oP`) | Claude Code Audit (השוואת קוד מול סכמה חיה) |

## 3. KNOWN GAPS — קיים בקוד, לא בפרודקשן
| Item | סטטוס | Feature Flag | מה חסר |
|------|-------|-------------|--------|
| N02 Lead Scoring | PARTIAL | `LEAD_SCORING=off` | לא אומת בפרודקשן (`lead_capture.py:32,90,96,130,134-138`) |
| N03 Lead Memory | PARTIAL | `LEAD_MEMORY=off` | תלוי ב-N02 |
| N04 Followup | PARTIAL | `FOLLOWUP_AUTOMATION=off` | תלוי ב-N03 |
| F05a Meta WhatsApp | CODE DONE | — | ממתין ל-Render deploy + verify |
| N06 Ventures Screen (TMA) | CODE DONE, מאוחד ל-main | — | PR #67 ממוזג ל-main (`7313b2e3`); ✅ verified בפרודקשן — לא ידוע, דרוש בדיקה ידנית ב-TMA החי |
| LEAD_QUALIFIER | לא פעיל (F09) | `LEAD_QUALIFIER=off` | פיצ'ר לא הופעל מעולם |
| MULTITENANT | כבוי (F08) | `MULTITENANT=off` | לא בשימוש |
| VOICE_IVR | לא פעיל (F07) | `VOICE_IVR=off` | קו Twilio IVR לא מומש/לא מופעל |
| EMAIL_INBOUND | לא פעיל (F06) | `EMAIL_INBOUND=off` | ערוץ email נכנס לא מופעל |
| AUDIENCE_INTELLIGENCE / INTERACTION_INTELLIGENCE / KPI_ENGINE / LEARNING_ENGINE / REVENUE_ATTRIBUTION | FUTURE — לא פעיל | כבויים | לא מומשו (FUTURE per `feature_flags.py:46-51`) |

## 4. ACTIVE DECISIONS — החלטות ארכיטקטוניות שחייבים לכבד
1. Ventures = טבלה נפרדת (לא הרחבת Deals.Status) — החלטה 17/06/2026
2. BOSS Layer = שכבה רוחבית, לא מסך עצמאי
3. כל כתיבה ל-Airtable עוברת דרך Approval Gate
4. Agent לא נוגע ב-Airtable ישירות — תמיד דרך `crm.py`
5. Feature flag = כבוי ברירת מחדל
6. `app.py` — 4 hooks בלבד (H1-H4)
7. לא בונים batch לפי פיצ'ר — בונים לפי קובץ

## 5. DO NOT TOUCH — אסור לשנות בלי אישור מפורש
- Approval Gate ו-`_TMA_WRITE_ALLOWED_TABLES`
- HMAC validation (`_validate_initdata`)
- Emergency Stop mechanism
- `_get_active_world_dict()` — shared game service (`tma_api.py:2253`; משותף בין `game_status`/`game_today`/`game_checkin`, ראו BUG-002/BUG-003 ב-`BUG_AUDIT_LOG.md`)
- `tools/airtable_gateway.py` — single write path

## 6. WHERE TO FIND TRUTH — מקור האמת לכל נושא
| נושא | מקור אמת | לא לסמוך על |
|------|----------|-------------|
| Priorities & next steps | ROADMAP.md | שיחות ישנות, זיכרון |
| Architecture & decisions | BOSS_CURRENT_STATE.md | README, specs ישנים |
| What's live in production | Render dashboard + `/health` | commit messages |
| Airtable schema | Live Airtable + `airtable_schema.py` | מסמכים ישנים |
| Security rules | `docs/governance/SECURITY_CHECKLIST.md` (⚠️ מסומן ARCHIVED מ-2026-06-14 — בדוק אם קיים מסמך מחליף לפני הסתמכות) | הנחות |
| Audit trail | `CHANGE_CONTROL_LOG.md` | PR descriptions |
| Screen architecture | `BOSS_Refactor_Plan.md` (Stage 0 הושלם, N06 = Stage 1) | קבצי TMA ישנים |
| Deployment / Rollback | `docs/operations/DEPLOYMENT.md`, `docs/operations/RUNBOOK.md` | זיכרון/הנחות על Render |

## 7. CURRENT ROADMAP POSITION
- ✅ Stage 0 (Bug fixes) — הושלם 2026-06-17 (BUG-001 עד BUG-006, ראו `BUG_AUDIT_LOG.md`)
- ✅ N06 Ventures Screen (TMA) — קוד ממוזג ל-`main` דרך PR #67 (`7313b2e3`); verify בפרודקשן: לא ידוע
- 🔲 N04 Followup Activation — הבא בתור (תלוי ב-`FOLLOWUP_AUTOMATION` flag כבוי כיום)
- 🔲 N05 Daily Digest שדרוג — קוד קיים (commit `5490943`, "wire real Score + computed tier into daily digest"), verify בפרודקשן לא ידוע
- 🔲 F05a Meta WhatsApp — code done, לא verified

## 8. OPEN RISKS
| סיכון | חומרה | מה נדרש |
|-------|-------|---------|
| Render production state אינו ניתן לאימות מהסביבה הזו (network egress חסום, אין גישת Dashboard) | High (תהליכי) | חיבור MCP/API ל-Render, או אימות ידני קבוע לפני כל "✅ הושלם" |
| Emergency Stop flags נשמרים ב-`/tmp/emergency_flags.json` — אחסון אפמרי על Render; אם ה-instance מתאפס/נפרס מחדש, דגלי חירום (כולל `EMERGENCY_STOP_AI`) חוזרים ל-OFF בלי התראה | High | להעביר persistence למקור עמיד (Airtable/DB) או לפחות לתעד את הסיכון ב-runbook |
| תיעוד ROADMAP.md מיושן: טבלת "Known Issues / Tech Debt" עדיין מתארת את שדה `tier` ב-Leads כ"לא קיים... החלטה נדרשת", בזמן שהקוד (commit `3d8ab50`) ו-הסכמה החיה (`fld4eC2mEYrviL3oP`, singleSelect) מראים שההחלטה כבר בוצעה ומומשה | Medium (תיעוד, לא קוד) | לעדכן את ROADMAP.md — להסיר/לסגור את הרשומה הזו (Checkpoint #10 בטבלת ה-Traceability, ראו Mission 1 §2) |
| `lead_memory.py:155` — `updated_at` נכתב ל-Airtable אך השדה לא קיים בטבלת Leads בפרודקשן (אומת ישירות בסכמה החיה) — כתיבה מתעלמת בשקט | Medium | להסיר את השורה, או להוסיף שדה `updated_at` לסכמה אם רוצים מעקב |
| `_get_active_world_dict()` — אין hard constraint ב-Airtable שמבטיח World יחיד עם `Status=Active`; ההגנה היחידה היא לוגית בקוד (בחירת ה-Number הנמוך ביותר באופן דטרמיניסטי) | Medium | constraint/validation ב-Airtable או alert אם נמצא יותר מ-Active אחד |
| `BossCheckin.tsx:363` ו-`:530` — שדות Urgency/Source/Topic/Required ו-"יום חדש →" אינם persisted ל-Airtable (state אבד בסגירה) | Medium | לחבר ל-write-through בדומה ל-Daily_Checkin (BUG-004) |
| Render auto-deploy מ-`main` — push ל-`main` נכנס אוטומטית לפרודקשן בלי שלב review/staging ביניים (לפי `DEPLOYMENT.md`) | Medium (תהליכי) | להוסיף שלב verify-after-deploy חובה (כבר מתועד ב-RUNBOOK, אך תלוי באכיפה אנושית — אין enforcement אוטומטי) | 
| `docs/governance/SECURITY_CHECKLIST.md` מסומן ARCHIVED (2026-06-14) — לא ידוע אם קיים מסמך מחליף תקף, או שזהו עדיין מקור האמת בפועל | Medium | לאשר עם הבעלים אם יש מסמך security עדכני יותר, ולעדכן את AI_CONTEXT §6 בהתאם |
| **Traceability Matrix (Mission 1) — 12 commits של תיקוני אבטחה (07–16/06/2026: `9384f89`,`aca037b`,`63966dd`,`e76c247`,`eb1f42b`,`2bae2e6`,`126e34c`,`f6281a5`,`badfb84`,`3a4dbc5`,`ef05dcf`,`9e609cb`) ללא PR מספור, ללא ראיית review, וללא קישור ל-ROADMAP item — לא ניתן לשחזר מי אישר, מתי נפרס, או אם אומת בפרודקשן** | Critical | לקבוע מנגנון: כל commit עם prefix `security:`/`fix(security)` חייב PR עם reviewer רשום + רשומת `CHANGE_CONTROL_LOG.md` בזמן ה-merge (לא retroactively) |
| **Traceability Matrix — אצוות C25-C40 (16 פריטים, Stabilization Sprint 07/06) מתועדות ב-ROADMAP רק בשם קובץ, לא ב-commit hash ייחודי per-item (חוץ מ-C37, C40)** | High | לאכוף ש-ROADMAP entry חדש יצוטט עם commit hash ספציפי מהיום שנכתב, לא retroactively משוחזר |
