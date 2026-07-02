# PLANNING_GATE — שער תכנון

**מתי:** לפני כל תכנון של פיצ'ר/שינוי. אני (Claude Chat) וקלוד קוד עוברים את זה **לפני** שורת קוד או ספק.
**למה נפרד מ-MODULE_RULES:** MODULE_RULES הוא רפרנס (קוראים כשצריך). זה שער (עוברים תמיד).

**מקור:** הוזן לריפו 25/06/2026, גובש תוך כדי בניית Decision Hub (יוני 2026).
**הערת מספור:** שער 5 למטה (מבחן הכביש האחד) מתאים לחוק 12 ב-`MODULE_RULES.md`
(לא חוק 11 — חוק 11 הקיים שם הוא כתיב שמות שדות ב-airtable_schema.py, ראו הערת
המספור שם).

---

## שלוש השאלות (תנאי סף — קיים)
לפני כל שינוי:
1. האם באמת יש בעיה?
2. האם הבעיה כבר נפתרה במקום אחר במערכת?
3. מה השינוי הקטן ביותר שפותר אותה?

רק אם שלושתן מצביעות על פער אמיתי — בונים חדש. אחרת משלבים בקיים.

---

## ארבעת השערים הארכיטקטוניים (חדש — חובה לפני תכנון)

### שער 1 — הפרדת ליבה↔פלאגאין
```
❓ האם הפיצ'ר מייבא תשתית (Airtable/memory/LLM/contacts) ישירות?
✅ נכון:  מדבר דרך port/interface. נקודת הזרקה אחת מכירה את התשתית.
❌ אסור:  import airtable_gateway בתוך לוגיקת הפיצ'ר.
בדיקה:   grep -c "import <infra>" <feature>.py  → ציפייה 0 בליבת הפיצ'ר.
תואם:    F08/F13 (multi-tenancy). פיצ'ר שמפר את זה = חוב טכני ל-V4.
```

### שער 2 — הפרדת כלי↔גייט
```
❓ האם הפיצ'ר מערבב "כלי" (עושה פעולה) עם "שער" (מחליט אם להמשיך)?
✅ נכון:  שער מחזיר חוזה אחיד (GateResult/VerifyResult). שער ≠ כלי.
❌ אסור:  פונקציה שגם מחליטה וגם מבצעת. שערים מאחורי registry דקלרטיבי.
דפוס:    _GATE_REGISTRY / register_gate — כמו _REGISTRY ב-tool_registry.
```

### שער 3 — Input Precedence (בדיקת התנגשות קלט)
```
❓ האם הפיצ'ר מקבל קלט שכבר יש לו handler (קובץ/הודעה/קולי/אימייל)?
✅ נכון:  מפה את ה-handler הקיים. הגדר precedence מפורש מי מנצח.
❌ אסור:  להוסיף יעד שני לקלט בלי לבדוק מי כבר תופס אותו.
דוגמה לכישלון: Drive↔Decision Inbox — קובץ נחטף ל-Drive לפני שה-Inbox ראה.
ברירת מחדל: handler קיים ממשיך כרגיל; context ייעודי פעיל מנצח אותו.
```

### שער 4 — Raw-First, Never Interrogate
```
❓ האם הפיצ'ר מנסה לפרסר/להבין קלט מושלם לפני שמירה?
✅ נכון:  שמור גולמי מיד. נחש + צור טיוטה + תן למשתמש לתקן.
❌ אסור:  חקירה חוזרת ("תן שם מדויק", "מי בדיוק"). מקסימום שאלה אחת,
          ורק אחרי שהגולמי כבר נשמר.
עיקרון:   BOSS never deletes signal — only down-ranks. גולמי תמיד נשמר.
```

### שער 5 — מבחן הכביש האחד (Domain-Agnostic)
```
❓ האם הפיצ'ר עובד גם לרופא וגם לחתונה — או רק לדומיין אחד?
✅ נכון:  ישות ליבה אחת. דומיין = שדה + vocabulary. כלי = port. ייעוד = tenant.
❌ אסור:  ישות/קוד ייעודי לדומיין (MedicalX, MarriageY).
מבחן בפועל: נסח את הפיצ'ר בלי לציין דומיין. אם אי אפשר — זה feature, לא core.
```

---

## בדיקת התנגשות כלים (חוזר על חוק MODULE_RULES — מפורש)
```
❓ האם שני flows כותבים לאותו כלי / תופסים אותו קלט / מנהלים אותו state?
אם כן → הגדר precedence מפורש לפני בנייה. אל תבנה על התנגשות סמויה.
```

---

### שער 6 — F52 Evidence (כתיבה/שליחה/שינוי מצב)
```
❓ אם הפעולה כותבת, שולחת, או משנה מצב — מי שומר את הראיה ואיפה?

✅ Gateway    — עובר דרך airtable_gateway / COG / dispatcher → מכוסה אוטומטית
✅ ActionResult — מחזיר structured result שנכנס ל-tool_results_log → מכוסה
🟡 Design Review — מתועד ב-F52_BYPASS_MAP כ-"design review" + סיבה → מותר זמנית
❌ לא ידוע  — עצור. לא בונים עד שיש תשובה.

חל על: כלי חדש, route חדש, scheduler job חדש, כל פעולה שמשנה state חיצוני.
לא חל על: פעולות read-only, health checks, לוגים פנימיים.
```

---

## פלט השער
לפני שמתחילים תכנון, תשובה קצרה ל-7 הסעיפים. אם אחד נכשל — מתקנים
את התכנון לפני קוד, לא אחרי.

---

## Discovery & Execution Integrity Rules
(נלמד בפועל — 02/07/2026, סשן Router/Capture Policy/Document Converter)

1. Current State Gate = live repo only. git grep --all, branch -a,
   actual file view — לעולם לא זיכרון, project knowledge cache,
   או סיכומי שיחה קודמים. אם כלי החיפוש של הסוכן פספס משהו —
   זו לא הוכחה שהוא לא קיים.

2. Router is the first business decision point. אין פעולה עסקית
   (write, classify-with-consequence, gate) שרצה *לפני* שהראוטר
   (Identity → Router → Context → Agent) סיים. אם קיים short-circuit
   כזה בקוד — הוא BUG, לא feature, גם אם הוא כבר בפרודקשן.

3. Feature flags must define exact scope: classify / route /
   preview / execute / write. לפני הצגת flag חדש או שימוש חוזר
   בשם קיים — grep לכל השימושים החיים קודם. flag שכבר שולט
   בהתנהגות אחת לא יכול לקבל משמעות שנייה בשקט.

4. DoD must prove the execution path, not only the output.
   "הבדיקות עברו" לא מספיק — צריך הוכחה שהקוד שנבדק הוא הקוד
   שרץ בפרודקשן (exit code אמיתי, לא script שנבלע בשקט,
   assertion שרצה בפועל לא רק collected).

5. Any code that calls an existing module must cite the actual
   function signature (view/grep מהסשן הנוכחי) לפני שנכתב call-site.
   לעולם לא הנחה מתיאור SPEC או מסיכום קודם.

6. A documented governance rule is not self-enforcing. סיכומי סשן
   חייבים לציין סטטוס ציות מפורש מול AGENTS.md ("PR נפתח לפי כלל
   סיום-סשן") — לא רק להשלים את המשימה ולשתוק לגביו.

7. Orphaned-branch audit is routine, not incidental — ראה AGENTS.md
   PRE-SESSION GATE. לא תלוי בכך שאיזה SPEC אחר יעבור שם במקרה.

8. Test-count claims ("N/N pass") must state what layer they exercise
   (unit / integration / e2e) — a passing count does not by itself
   imply the full execution chain was proven, especially where no
   e2e harness exists for that chain.
