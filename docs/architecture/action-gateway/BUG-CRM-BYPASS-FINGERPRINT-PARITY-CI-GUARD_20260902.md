# FINGERPRINT_PAYLOAD_DIVERGENCE CI guard + 3 more pre-existing instances found and fixed

**תאריך:** 02/09/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
— הרחבת שער CI קיים (`tools/audit_turn_coordinator_bypass.py`) + תיקון
נקודתי בשלושה מודולי scheduler; אין שינוי ל-`ActionGateway`, ל-`tools/dispatcher.py`,
או למדיניות אישור.
**Cross-Layer Planning Gate assessment:** SINGLE-LAYER — כל תיקון מוכל
בתוך פונקציית ה-caller שהציעה את ה-contract; אין חוזה/authority/routing
חדש.

## הרקע

בעקבות `BUG-CRM-BYPASS-FINGERPRINT-PARITY` (אותו יום), הבעלים ביקש הוספת
שער CI שימנע הישנות של מחלקת הבאג הזו — deterministic route שמעביר
`fingerprint_payload` מותאם-אישית ל-`propose_action()` שמתפצל מה-`tool_inputs`
האמיתי שנשלח לביצוע.

## הממצא (במהלך בניית השער)

הרצת השער הראשונית (לפני תיקוני false-positive) גילתה **3 מופעים נוספים,
קיימים מראש, לא קשורים ל-Deal**, של אותה מחלקת באג בדיוק:

1. `scheduler.py::_apply_weekly_quest_mutation()` — **לא** מוגן flag כלל,
   רץ אוטומטית כל יום ראשון 08:00.
2. `abandoned_lead_worker.py::create_human_pipeline_task()` — מוגן
   `ABANDONED_LEADS` (כבוי כברירת מחדל, לא אומת אם דלוק live).
3. `interaction_engine.py`'s task-creation-from-analysis — מוגן
   `INTERACTION_INTELLIGENCE` (כבוי כברירת מחדל, מתועד בקוד עצמו).

אומת ישירות בקוד (`core/action_gateway.py:4555-4568`, `_make_dispatch_executor()`):
`execution_context["business_action_fingerprint"]` **תמיד** נלקח מהערך
המקורי שנשמר על ה-contract בזמן ה-propose (`contract.business_action_fingerprint`)
— **לעולם לא מחושב מחדש** בזמן האישור/ביצוע. `tools/dispatcher.py::_validate_execution_proof()`
מחשב expected מחדש תמיד מה-`inputs` האמיתיים. כל שלושת המופעים הנ"ל
היו נכשלים ב-100% מהריצות בפועל (אם/כאשר יופעלו), באותה הודעה בדיוק:
"approval-sensitive execution proof does not match the action payload."

**המשמעות המעשית:** ה-Weekly Quest Reset (לא מוגן flag) ככל הנראה כשל
**בכל ריצה** מאז שהקוד הזה נוסף — ללא תלות ב-Deal creation כלל.

## התיקון

לכל שלושת המופעים: **הוסרה ה-divergence מהמקור**, לא סונכרנה ידנית:

1. **`scheduler.py`** — אין שום שדה תנודתי; ה-`fingerprint_payload` היה
   כפילות כמעט-מדויקת של `tool_inputs` עם שני מפתחות עליונים מיותרים
   ("action"/"week"). הוסר לגמרי — **אין פשרה, אין אובדן יכולת** (אותם
   ערכים דטרמיניסטיים ממילא).
2. **`abandoned_lead_worker.py`** — `minutes_silent` הוא תוכן אמיתי,
   פונה-למשתמש (לא debug breadcrumb), ולכן לא ניתן פשוט להסיר אותו מה-
   payload בלי לאבד מידע אמיתי. הוסר `fingerprint_payload` המותאם-אישית
   בכל זאת — **פשרה מודעת**: retry עם `minutes_silent` שונה כבר לא
   מזוהה כאותה זהות עסקית (dedup לא-רגיש-לזמן אבד), אבל המשימה **בפועל
   נוצרת** במקום להיכשל תמיד. עדיפות מוצהרת: כתיבה שעובדת עדיפה על
   dedup מושלם שאף פעם לא רץ. dedup אמיתי חסין-לזמן, אם רצוי, דורש
   מנגנון נפרד (בדיקה ייעודית לפי `(sender, channel, domain, step)`
   **לפני** `propose_action()`, לא ייצוג fingerprint שני).
3. **`interaction_engine.py`** — Memory ID היה embedd-ed בתוך `DESCRIPTION`
   הנשלח בפועל, עם `fingerprint_fields` נפרד שהחריג אותו. **אין פשרה
   כאן**: Memory ID הוא בסך הכול הערת מעקב לצורכי דיבוג, לא תוכן עסקי
   הכרחי — הוסר **לגמרי** מה-`DESCRIPTION` הנשלח (לא רק מה-fingerprint),
   כך ש-`tool_inputs` עצמו הפך invariant ל-Memory ID — אותו דפוס בדיוק
   כמו `due_time`'s החרגה ב-Task (בטוחה כי אף פעם לא נשלחת, לא כי אובייקט
   fingerprint שני מנסה להסתיר אותה בדיעבד).

## שער CI חדש — `FINGERPRINT_PAYLOAD_DIVERGENCE`

נוסף כ-guard רביעי ל-`tools/audit_turn_coordinator_bypass.py`:
- סורק AST על כל קובצי `.py` במעקב git (לא test_*) לאיתור כל קריאה
  שמעבירה `fingerprint_payload=` לא-`None`.
- מתעלם מ-passthrough (`fingerprint_payload=fingerprint_payload` בתוך
  wrapper דק) — אלה לא יוצרים divergence חדשה במקום הקריאה עצמו.
- משייך כל ממצא לפונקציה החיצונית ביותר שמכילה אותו (לא ה-closure
  הפנימי) — כך ש-Task's `_queue_task()` הפנימי משויך נכון ל-
  `_queue_deterministic_create_task()` החיצונית.
- כל ממצא שאינו רשום מפורשות ב-`_FINGERPRINT_DIVERGENCE_REGISTRY` (עם
  סיבה מתועדת ונבדקת, בדיוק כמו התקדים של `due_time`) → חוסם.
- לאחר תיקון שלושת המופעים, הרישום היחיד שנשאר הוא Task's `due_time`
  exclusion המקורי, המתועד והבטוח.

## Verification

- `python3 tools/audit_turn_coordinator_bypass.py` — `PASS` (0 ממצאים לא-רשומים)
- `python3 -m pytest test_f52_g4_s3_abandoned_lead_task.py test_f52_g4_s4_interaction_task_writer.py test_f52_g4_s5_weekly_quest_reset.py` — 19/19 (עודכנו לבדוק `tool_inputs` במקום `fingerprint_payload` שכבר לא קיים; `abandoned_lead_worker`'s טסט שוכתב במפורש לתעד את הפשרה)
- `python3 test_phase_4b2_wiring.py` — 86/86
- `python3 test_bug157_atomic_fingerprint_claim.py` — 34/34
- `python3 -m pytest test_interaction_flag_scheduler.py test_c86_scheduler_emergency_matrix.py test_weekly_summary_scheduler_registration.py test_p23_m5_interaction_attribution.py test_r24_04e_interaction_capability.py` — 20/20
- `python3 -c "import scheduler; import abandoned_lead_worker; import interaction_engine"` — עבר
- `python3 -m compileall -q .` — עבר
- `git diff --check` — נקי

## סטטוס

קוד מומש ונבדק מקומית (STATIC_VERIFIED). **לא מוזג, לא deployed, לא
verified בפרודקשן.** שלושת המודולים האלה לא נבדקו בקנרייה חיה — ה-Weekly
Quest Reset הבא (יום ראשון) הוא ההזדמנות הראשונה לאמת בפועל; שני
האחרים דורשים הפעלת flag לפני שניתן לבדוק.
