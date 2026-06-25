> **הערת מקור (נוספה 25/06/2026, בעת הכנסת המסמך לריפו):** מסמך זה הוזן מחוץ לריפו
> ומכריז על עצמו למטה כ"ACTIVE REFERENCE — מקור אמת לצד BOSS_CURRENT_STATE.md". זה
> **מתנגש** עם `ROADMAP.md` (שורה 2): *"מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE."*
> ועם `CLAUDE.md`: *"Other planning docs (BOSS_MASTER_PLAN_*.md in archive/...) are
> archives/snapshots, not authoritative."* בהתאם לכלל הקיים, הקובץ ממוקם ב-`archive/`
> ולא כ-reference פעיל. תוכנו נשמר ללא שינוי כתיעוד היסטורי של עקרון "כביש אחד, יציאות
> רבות"; הסעיף "11 חוקי המבנה" שלמטה **לא תואם** את המספור החי ב-
> `docs/governance/MODULE_RULES.md` — שם "Domain-Agnostic Core" הוא חוק 12, לא 11
> (חוק 11 החי הוא כתיב שמות שדות ב-airtable_schema.py). לפרטי המספור הנוכחי, ראו
> `MODULE_RULES.md` ו-`PLANNING_GATE.md` בתיקיית `docs/governance/`.

---

# BOSS — התכנית הכוללת (One Road, Many Exits)

**Status:** ARCHIVE — תיעוד היסטורי בלבד. מקור האמת היחיד הוא `ROADMAP.md` (ראו הערת המקור מעלה).
**Owner:** אליהו | **יוני 2026

---

## העיקרון המכונן

> **כביש אחד, נקודות יציאה רבות.**
> ליבה חזקה ואחידה. כל השאר — התאמות יפות.

תהליך קבלת ההחלטה זהה בכל מקום: עסקה, נישואין, ניתוח רפואי, גיוס עובד,
קניית דירה. אותם צדדים, טיוטות, סיכונים, מה חסר, מה השתנה, האם מוכן.
ההבדל היחיד הוא ה-vocabulary. הליבה — זהה.

```
              ┌─────────────────────────────────────┐
              │           הכביש (CORE)              │
              │  Input → Memory → Understanding →   │
              │  5 Gates → Decision/Action          │
              └─────────────────────────────────────┘
                 │         │         │         │
            ┌────┘    ┌────┘    ┌────┘    └────┐
         דומיינים    כלים     ייעודים      ערוצים
         (יציאות)  (יציאות)  (יציאות)    (יציאות)
```

---

## שלוש שכבות היציאה — אותו כביש, פיצול בנקודה אחת

### יציאה 1 — דומיינים (Domain = שדה)
```
נדל"ן · ייבוא · גיוס · שותפות · רפואה · נישואין · משפט ...
= ערך ב-select + vocabulary. אפס קוד חדש.
"נספח" / "חוות דעת שנייה" / "הסכם ממון" — אותו Event, מילה אחרת.
```

### יציאה 2 — כלים (Tool = Port adapter)
```
Drive · Voice · Email · WhatsApp · Telegram · Calendar ...
= adapter מאחורי Port. הליבה לא מכירה את הכלי הקונקרטי.
build_default_ports() = נקודת ההזרקה היחידה.
```

### יציאה 3 — ייעודים (Purpose = Tenant config)
```
עו"ד לתיקים · רופא לאבחנות · יזם לעסקאות · זוג לחיים משותפים ...
= TenantConfig: vocabulary + providers + gate-strictness.
אותו קוד. אותו pipeline. tenant בוחר את היציאה.
```

---

## הליבה — מה חייב להיות חזק (כי הכל נשען עליו)

| רכיב ליבה | תפקיד | קיים? |
|---|---|---|
| **Input/Inbox** | דלת כניסה אחת, raw-first | Stage 0 ✓ |
| **Memory** | session + business memory + lead memory | קיים, חלקי |
| **Ports** | הפרדת ליבה↔תשתית (DecisionPorts) | Stage 0 ✓ |
| **5 Gates** | Delta→Entity→Trust→Readiness→Risk | 2/5 ✓ |
| **GateResult** | חוזה אחיד לכל שער | ✓ |
| **Approval Gate** | אישור אנושי לסיכון | קיים ✓ |
| **anti_hallucination** | Trust enforcement | קיים ✓ |
| **Decision (ישות)** | יחידת הבסיס, domain-agnostic | Stage 0 ✓ |

**העיקרון:** משקיעים בליבה. היציאות הן התאמות — זולות כשהליבה חזקה,
יקרות כשהיא חלשה.

---

## 11 חוקי המבנה (MODULE_RULES) — מה שומר על הכביש

```
1-6   קיימים (מגורי פיצ'ר · רזון app.py · כיוון תלויות · כלים בלי
       state · מקור אמת יחיד · memory לא מפעיל LLM)
7     הפרדת ליבה↔פלאגאין (Ports)
8     הפרדת כלי↔גייט (registry)
9     Input Precedence (context מנצח default)
10    Raw-First, Never Interrogate
11    Domain-Agnostic Core (כביש אחד, יציאות רבות)
```

## 5 שערי התכנון (PLANNING_GATE) — מה שעוברים לפני קוד
```
3 השאלות + 5 שערים:
  1. ליבה↔פלאגאין?   2. כלי↔גייט?   3. precedence?
  4. raw-first?       5. מבחן הכביש האחד (עובד לרופא ולחתונה?)
```

---

## מפת השלבים — מה כבר על הכביש ומה היציאות

```
═══ הליבה (קודם — חזקה) ═══════════════════════════════
Stage 0    ✓ Inbox + 4 טבלאות + Pipeline + Ports + 2 שערים
Stage 0.5  ⏳ File Precedence (Drive↔Inbox)
Stage 0.6  ⏳ File Context Ref (last_uploaded_file)
Stage 1    ○ Trust Layer (שער 3)
Stage 2    ○ AI Delta Classifier
Stage 3    ○ Readiness Engine (שער 4)
Stage 4    ○ Attention Engine (job יומי)

═══ היציאות (אחר כך — התאמות) ════════════════════════
Stage 5    ○ Auto-Ingestion (WhatsApp/Email channels)
Stage 6    ○ TMA Screen + Closure→Memory
Stage 7+   ○ Domains נוספים (רפואה/נישואין = שדה+vocab)
V4         ○ Multi-tenant (ייעודים = TenantConfig)
```

**סדר העבודה:** ליבה עד Stage 4 לפני יציאות. לא מחברים דומיין/ערוץ/ייעוד
חדש למנוע שעוד לא נבדק. כל יציאה נשענת על ליבה יציבה.

> **הערת ARCHIVE (25/06/2026):** Stage 0.5 ו-Stage 0.6 שלמעלה תועדו כ-⏳ במסמך
> המקורי; בפועל שניהם הושלמו ומוזגו ל-`main` ב-PR #147 (commits `4ac2a05`/`e0f0111`)
> לפני שמסמך זה הוכנס לריפו. הסטטוס החי נמצא ב-`ROADMAP.md`, לא כאן.

---

## למה זה Sales-First

```
לא מוכרים:  "CRM לנדל"ן"        → שוק מוגבל
מוכרים:     "מערכת קבלת החלטות"  → שוק אינסופי
```

כל בעל מקצוע שמקבל החלטות מורכבות הוא לקוח. הליבה אחת — השוק כל
מי שיש לו דיון, מחלוקת, טיוטה, סיכון. זה ה-TAM של "חשיבה", לא של
"נדל"ן".

---

## הסכנה היחידה — והשמירה מפניה

```
פיתוי:  לבנות MedicalDecision / MarriageDecision / BusinessDecision
תוצאה:  3 ישויות → איבדת אחידות → 3 מערכות מודבקות → הסיוט.
שמירה:  חוק 11 + שער 5. ישות אחת. דומיין = שדה. תמיד.
```

> בסוף — חשוב לבנות ליבה חזקה. כל השאר אלו התאמות יפות.
