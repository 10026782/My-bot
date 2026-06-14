# Architecture Drift Map

**מקור**: אודיט Codex, 2026-06-12 (ראה `review_diffs` / audit מצורף).
**מטרה**: לתעד את הדריפט הארכיטקטוני שנשאר אחרי Airtable Write Gateway, ולקבוע איך כל פריט נטמע — לא בספרינט נפרד, אלא **כ"טרמפ" על עבודה שמתוכננת כך או כך**.

**עקרון מנחה**: "Do Not Break" — בכל migration: קודם facade שמקבל אותם inputs ומחזיר אותה צורה (no-op בהתחלה), רק אחר כך normalize → validate/policy → execute → audit. שום business logic לא זז בצעד הראשון.

---

## טבלת מעקב (Source of Truth)

| # | Area | Priority | Gateway עתידי | Piggyback Trigger (מתי לבצע) | סטטוס |
|---|------|----------|----------------|-------------------------------|--------|
| 1 | Emergency Stop coverage | P0 | `feature_flags.py` (policy helpers) | בזמן CORE_05 Cost Watchdog | TODO |
| 2 | Messaging policy (facade only) | P0 | `messaging_gateway` (עתידי) | בזמן N05 Followup Activation | TODO |
| 3 | Approvals canonicalization | P0 | Airtable `Approvals` = source of truth | בזמן עבודה הבאה על Approval Gate / TMA Approvals screen | TODO |
| 4 | Task taxonomy freeze | P1 | `task_gateway` (עתידי) | בזמן N04 Lead Memory (נוגע ב-task creation) | TODO |
| 5 | Audit event schema unification | P1 | `audit_gateway` (עתידי) | בזמן עבודה על Activity Feed v2 | TODO |
| 6 | Identity normalization (TMA↔Telegram↔WhatsApp) | P1 | `identity.py` (helpers) | לפני חיבור Meta WhatsApp בפועל (סעיף 1 ברודמאפ) | smoke test added — PASS (2026-06-14) |
| 7 | Google action risk metadata centralization | P1 | `tool_registry.py` | כשהקפאת Google Tools מבוטלת | DEFERRED (Google frozen) |
| 8 | Airtable read gateway | P2 | extend `airtable_gateway.py` | אופורטוניסטי — כל פעם שנוגעים בקובץ עם raw read | TODO |

---

## איך קוראים את הטבלה הזו (ל-Claude הבא)

כל פעם שמתחילים עבודה על ספרינט/רודמאפ-איטם:
1. בדוק אם יש שורה בטבלה שה-Piggyback Trigger שלה תואם לעבודה הנוכחית.
2. אם כן — לפני שמתחילים, קרא את הסעיף המתאים למטה (יש לכל פריט תיאור קצר + minimal step).
3. בצע **רק את ה-minimal step** המתואם לאותו שלב migration. לא לקפוץ שלבים.
4. עדכן את עמודת "סטטוס" בטבלה (TODO → IN PROGRESS → DONE-step-N).
5. אם הצעד הושלם והגיע לשלב האחרון של ה-migration עבור אותו פריט — סמן DONE ועדכן את `BOSS_CURRENT_STATE.md`.

**חשוב**: אסור להפעיל סעיף מהטבלה הזו כ"יזמה משלך" אם המשתמש לא ביקש לעבוד על ה-trigger המתאים. המסמך הזה הוא רשימת המתנה, לא backlog לביצוע אוטונומי.

---

## פירוט פריטים

### 1. Emergency Stop Coverage (P0)
**הבעיה**: `EMERGENCY_STOP_ALL` נבדק ב-dispatcher, אבל scheduler/worker/interaction_engine שולחים הודעות ללא בדיקה. `EMERGENCY_STOP_AI` לא מופיע ב-health response.

**הבעיה הנוספת (קריטית)**: emergency flags נשמרים ב-`/tmp`, שהוא ephemeral ב-Render — נמחק בכל deploy/restart. אם הבעלים מפעיל `EMERGENCY_STOP_ALL` ואז קורה restart (deploy, crash, sleep), הדגל מתאפס בשקט והמערכת חוזרת לפעול כאילו הכל תקין, בלי שהבעלים יודע. זו הפרת SoA קריטית: ה-storage layer של flag כל-כך חשוב חייב להיות persistent ולא תלוי-תהליך.

**Minimal step (כשמגיעים)**:
- העבר persistent emergency flags מ-`/tmp` ל-Airtable (טבלה קטנה `SystemFlags`, או שדה ב-`system_registry`). **שינוי storage layer בלבד** — `is_enabled`/`set_flag` API נשאר אותו דבר, רק המימוש הפנימי קורא/כותב ל-Airtable במקום קובץ. בלי שינוי בלוגיקת ה-checks שקוראים לפונקציות האלה.
- הוסף `EMERGENCY_STOP_AI` ל-health endpoint (`tma_api.py`).
- בכל אחד מ-4 ה-workers שמזכיר ה-audit (`scheduler`, `daily_digest`, `payment_reminder`, `cost_monitor`): הוסף guard clause `if not feature_flags.is_enabled('EMERGENCY_STOP_AUTOMATION'): return` בתחילת פונקציית השליחה. **לא לגעת בלוגיקה אחרת.**

**Definition of done לשלב 1**: flags שורדים restart (נבדק ע"י הפעלת flag, redeploy, ובדיקה שהוא עדיין דלוק), + worker אחד מתועד ונבדק (לוג מראה "blocked by emergency flag" כשהדגל פעיל).

---

### 2. Messaging Facade (P0)
**הבעיה**: 8+ מודולים שולחים הודעות בנפרד, חלקם דרך `telebot`, חלקם דרך `httpx`.

**Minimal step (facade בלבד, no policy yet)**:
- צור `messaging_gateway.py` עם פונקציה אחת: `notify_owner(text, parse_mode=None)` שעושה **בדיוק** מה ש-`app.py` עושה היום (אותו client, אותו error handling). No-op facade.
- בעבודה הבאה על N05 Followup: שנה רק את `abandoned_lead_worker.py` להשתמש ב-facade במקום ב-send ישיר. **קובץ אחד בכל פעם.**

**Definition of done לשלב 1**: facade קיים, אחד מהקוראים עבר אליו, שאר 7 הקוראים ללא שינוי.

---

### 3. Approvals Canonicalization (P0)
**הבעיה**: `event_bus._pending` (in-memory) ו-Airtable `Approvals` הם שתי מערכות אמת. App callback נכנס ל-`bus._pending` ישירות.

**Minimal step**:
- אל תמחק את `event_bus`. הוסף לו פונקציה `sync_to_airtable(approval_id)` שנקראת **בנוסף** (לא במקום) בכל מקום שכותב ל-`_pending`. שלב ראשון = כתיבה כפולה מבוקרת, לא איחוד.
- רק אחרי שכתיבה כפולה רצה בלי שגיאות שבוע — TMA approve/reject endpoint יקרא ל-Airtable כ-source, ו-`event_bus` יהפוך ל-cache.

**Definition of done לשלב 1**: כל approval חדש נכתב גם ל-Airtable, גם ל-memory, ללא breaking של TMA הקיים.

---

### 4. Task Taxonomy Freeze (P1)
**הבעיה**: "Task" = 3 משמעויות (CRM Tasks / Roadmap Tasks / Quests), סטטוסים בעברית/אנגלית מעורבים.

**Minimal step**:
- **לא לגעת בקוד**. רק תיעוד: טבלה ב-`AGENTS.md` או `MODULE_RULES.md` שמסבירה לכל קוד עתידי: "אם אתה כותב ל-Tasks table — באיזה status vocabulary להשתמש, ולמי לדווח coins". זה freeze על *כפילות חדשה*, לא תיקון כפילות קיימת.
- בזמן N04 Lead Memory (שיוצר tasks חדשים) — וודא שהקוד החדש הולך לפי הטבלה הזו, לא מוסיף status value חדש.

**Definition of done לשלב 1**: טבלת taxonomy קיימת במסמך governance, N04 לא מוסיף סטטוס חדש.

---

### 5. Audit Event Schema (P1)
**הבעיה**: `_audit`, `audit_log_airtable`, gateway logger, Activity Feed receipts — לא אותה צורה.

**Minimal step**:
- הגדר schema אחד (dict: `timestamp, actor, action, target, result, source_module`) ב-`schemas.py`.
- בעבודה הבאה על Activity Feed: ה-endpoint שקורא ל-audit events יעבור normalize ל-schema הזה *בזמן read* (adapter), בלי לשנות את ה-writers הקיימים.

**Definition of done לשלב 1**: Activity Feed מציג אירועים מכל המקורות בפורמט אחיד, בלי לשנות writers.

---

### 6. Identity Normalization (P1) — **לפני Meta WhatsApp**
**הבעיה**: WhatsApp unknown → `lead`, Telegram unknown → `readonly`. TMA dev-mode path נפרד מ-Telegram path.

**Minimal step (לבצע כחלק מ"לפני חיבור Meta")**:
- כתוב smoke test אחד: 4 מקרים (Telegram owner, WhatsApp owner, unknown WhatsApp→lead, unknown Telegram→readonly) שמריץ `resolve_identity` ובודק תוצאה. אל תשנה קוד — רק תפוס regression future.
- אם הטסט חושף שה-owner שלך (Eliyahu) לא מזוהה זהה בשני הערוצים — **זה ה-blocker האמיתי לחבר WhatsApp**, ותיקון ממוקד יחיד נדרש כאן (לא refactor כללי).

**Definition of done לשלב 1**: smoke test קיים וירוק, *או* זוהה blocker יחיד וטופל נקודתית.

---

### 7. Google Action Risk Metadata (P1) — DEFERRED
**הבעיה**: risk/approval policy מפוזר בין `event_bus`, `app.py`, `dispatcher`, `action_validator`, `core_knowledge`.

**הערה**: Google Tools מוקפאים ברודמאפ (סעיף 6, "cost of fixing outweighs current benefit"). **לא לפתוח את זה** עד שההקפאה מבוטלת. נשאר כתיעוד בלבד.

---

### 8. Airtable Read Gateway (P2)
**הבעיה**: `airtable_get`, `_at_list`, `_at_get_record` — reads ישירים, יכולים להחזיר `[]` בשקט בכשל.

**Minimal step (אופורטוניסטי)**:
- כל פעם שעובדים על קובץ שמכיל raw read אחד מאלה, ו**יש כבר סיבה אחרת לגעת בקובץ** — הוסף error logging לאותה read call (לא refactor, רק `try/except` עם `logger.error` אם התוצאה ריקה/שגיאה).
- אל תאסוף את כולם ביחד. זה P2 — שיפור אגב, לא משימה.

---

## עדכון מסמכי Governance

מסמך זה צריך:
1. קובץ זה נמצא ב-`docs/governance/ARCHITECTURE_DRIFT_MAP.md`.
2. אזכור קצר ב-`BOSS_CURRENT_STATE.md` תחת section "Known Architectural Drift — see docs/governance/ARCHITECTURE_DRIFT_MAP.md".
3. אזכור ב-`docs/governance/MODULE_RULES.md`: "לפני הוספת writer/sender/notifier חדש — בדוק ARCHITECTURE_DRIFT_MAP.md אם הקובץ הזה כבר מסומן לdrift".

**לא לעדכן** `ROADMAP.md` הראשי עם 8 השורות — זה ייצור רעש. הקישור ל-roadmap הוא רק דרך ה-"Piggyback Trigger" column, שמופעל כשמגיעים לאיטם המתאים באופן אורגני.
