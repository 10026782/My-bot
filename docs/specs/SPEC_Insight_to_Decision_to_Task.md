# SPEC — Insight → Decision → Task (השלמת Decision Hub, שני PRs)

**סטטוס: SPEC DRAFT — NOT IMPLEMENTED**
**גרסה:** v2 (13/10/2026) — מחליפה את v1 (commit `79b4213d`) אחרי החלטות בעלים O1–O6 ושבעת תיקוני החובה.
**בסיס Truth Reset:** `origin/main` @ `5e20e60` (נבדק מחדש 13/10/2026; אין commits חדשים מאז האודיט).
**מסמך אב:** `docs/specs/DECISION_HUB_MASTER_SPEC.md` — ספק זה הוא חלוקת משנה ל-Stage 0 (Inbox) ו-Stage 6 (Closure) שבו. בסתירה — המסמך האב קובע.
**מה אסור לעשות לפי ספק זה לפני אישור נפרד:** שינוי Airtable, מימוש, פתיחת PR, הפעלת Feature Flags.

---

## 0. החלטות בעלים שנקלטו

| # | החלטה | השפעה בספק |
|---|---|---|
| O1 | סגירה — Owner בלבד בשלב ראשון | §6.1 |
| O2 | שני אישורים נפרדים: החלטה ומשימה | §6.5 |
| O3 | אין כתיבה אוטומטית של `Outcome` ל-Learnings בשלב ראשון | §6.4, `Outcome` לא נכתב ע"י הקוד |
| O4 | לא מוסיפים `Research Status` לפני בדיקת השדה הקיים | §4 — נבדק, `Outcome` הקיים מספיק, אין שדה חדש |
| O5 | חוות דעת מייעצים נשמרות כ-Decision Events; אין פיתוח עדכון Stakeholder | מחוץ לתחום |
| O6 | לאמת `FEATURE_DECISION_HUB` לפני הפעלה | §9, תנאי הפעלה (לא אומת עד כה) |

## 1. Truth Reset — תיקונים לגרסה 1

מקור: קריאת קוד חי ב-`5e20e60` + סכמת Airtable חיה (קריאה בלבד, 13/10/2026).

| # | טענה ב-v1 | המציאות | תיקון |
|---|---|---|---|
| T1 | "`airtable_patch` משמיט שדות בשקט" | **שגוי.** `tools/airtable_gateway.py::airtable_patch/airtable_create` הם fail-closed (SPEC A1): שדה לא מוכר/מושמט → הכתיבה **נחסמת** ומוחזר `False`/`None` (או `AirtableCreateOutcome("failed")`). ההערות על "silently drop" ב-`airtable_schema.py` (בלוק Stage 2) וב-docstring של `_persist_confidence` מיושנות. | הוסר "סיכון השמטה שקטה". תחתיו: כל צעד כתיבה בודק את ערך ההחזרה; כישלון = כישלון גלוי (§5.5, §6.3). |
| T2 | הצעת שדה `Linked Decisions` ב-Learnings | קיים נתיב קישור מלא ללא שדה חדש (§4). | **הוסר.** אפס שינויי Airtable. |
| T3 | הצעת `tenant_id` ב-Learnings | אין ב-Learnings. מערכת חד-tenant (`MULTITENANT` כבוי, `Identity.tenant_id` ברירת מחדל `boss_hq`). | כלל home-tenant fail-closed (§5.4) במקום שדה חדש. |
| T4 | "Readiness = READY" כשער הסגירה | ל-`Decisions.Readiness` החי יש **רק** `READY`/`NOT_READY`. הערך `REVIEW` (`DecisionReadiness.REVIEW`) קיים בקוד בלבד; `_persist_readiness` ינסה לכתוב אותו ויחסם (נתפס ב-try/except ונרשם ללוג). | הפער נרשם (§10 פער G3). השער ב-PR2 מבוסס על `ReadinessResult` שמחושב בזיכרון, לא על השדה השמור. |
| T5 | "ראיות Stage 2 לא קיימות ב-Airtable" | `Evidence Ids/Summary`, `Confidence Score`, `Missing Evidence` **קיימים** חי ב-Decisions. | אין תלות בשדות חדשים. |
| T6 | שימוש ב-`trusted_source` ב-Gateway כפתרון פשוט | `propose_action` דורש טיפול ב-`trusted_source` ובאישור; קיימות שתי תבניות precedent (tma_api owner auto-approve; interaction_engine system self-approve) — **אף אחת לא מתאימה כמות שהיא** לאישור משתמש אמיתי ב-Hub. | נקבע כפריט Rule 00 ל-PR2 (§6.5, §8). |

## 2. Planning Gate — רישום (`docs/governance/PLANNING_GATE.md`, `CROSS_LAYER_GOVERNANCE_REVISED_PLANNING_GATE.md`)

### 2.1 שמונה השאלות
1. **בעיה אמיתית?** כן — נמדד באודיט: אין מסלול מתובנה להחלטה, אין סגירה/תיעוד מאשר, אין החלטה→משימה (ראיות: `cmd_decision.py`, חיפוש grep שלא מצא שימוש ב-`LINKED_TASKS`, `DECISIONS_LINK`).
2. **נפתרה במקום אחר?** חלקית: Inbox/Event/Readiness/Confidence קיימים — ממוחזרים. סגירה ומשימה אינם קיימים.
3. **השינוי הקטן ביותר:** שני PRs, ללא שדות Airtable חדשים, ללא טבלה/מנוע חדשים.
4. **Dual Mechanism?** לא: אין מסלול החלטות חדש; הכל תחת `FEATURE_DECISION_HUB` + flag סגירה אחד. סטטוס משימה לא משוכפל להחלטה.
5. **עקיפת Gateway/Router/Identity/Dispatcher/Policy?** לא מותר. כתיבות החלטה — `DecisionPorts`→`airtable_gateway` (כמו היום); משימות — Golden Writer + Action Gateway (§6.5). **הערה:** כתיבות ה-Hub להחלטות אינן עוברות Dispatcher — זה המצב הקיים והמתועד ב-`decision_ports.py`, ואינו מורחב.
6. **Evidence אמיתי?** כל צעד כתיבה מחזיר תוצאה מובנית (`DecisionPersistenceResult`/`AirtableCreateOutcome`) ו-audit דרך ה-gateway; דיווח הצלחה רק אחרי תוצאה (§5.5).
7. **השפעה אם לא מתקנים:** ההחלטות על קרן ההון נשארות ידניות מחוץ למערכת; אין תיעוד מי אישר מה. לא דחוף ל-production — flag כבוי.
8. **אכיפה קדימה:** בדיקות סקריפט (§7) + grep ל-bypass (`tools/audit_dispatcher_bypass.py`, `audit_gateway_bypass.py`) + CI.

### 2.2 ארבעת השערים הארכיטקטוניים + Gate 6
- **שער 1 (ליבה↔פלאגאין):** לוגיקת הסגירה והמקור בקבצים טהורים; I/O דרך `DecisionPorts`/read-adapter בלבד. בדיקה: `grep -c "import airtable_gateway|import httpx"` בקבצים החדשים = 0.
- **שער 2 (כלי↔גייט):** בדיקות תנאי קדם (`can_close`) הן שער טהור שמחזיר חוזה; הביצוע בנפרד.
- **שער 3 (Input Precedence):** `/decision from-insight` ו-`/decision close` הם subcommands חדשים בתוך ה-handler הקיים של `/decision`; אין קלט קובץ/קול חדש. callbacks עם prefix חדש (`dec_ins_*`, `dec_close_*`, `dec_task_*`) — יש לאמת שאין התנגשות ב-dispatcher של callbacks ב-`app.py` (פריט Rule 00 §8).
- **שער 4 (Raw-First):** התובנה כבר נשמרת גולמית ב-Learnings (המקור). לכן **אין כתיבה לפני אישור**; אחרי אישור — Inbox נכתב ראשון (§5.3). מוצדק מפורשות מול דרישת "אין כתיבה יתומה בעקבות ביטול".
- **שער 5 (Domain-Agnostic):** הליבה לא מזכירה השקעות; "קרן ההון" היא דוגמת בדיקה בלבד.
- **Gate 6 (F52 Evidence):** החלטות/Events/BM — `airtable_gateway` (audit + תוצאה). משימות — Action Gateway (ledger).

### 2.3 Cross-Layer Assessment (שבע שאלות) — סיווג: **FULL**
1. הבעלים: שכבת Decision Hub (`cmd_decision`, `decision_*`) + נקודת מגע אחת ל-Action Gateway/Golden Writer (PR2).
2. משנה authority boundary? לא; אך מוסיף **caller חדש** ל-Action Gateway.
3. משנה write path/persistence/lifecycle? כן — סגירת החלטה = מעבר מצב (`Open`→`Decided *`) חדש; משימה חדשה נכתבת מ-Hub.
4. caller/callee חדש בין שכבות? כן (Hub→ActionGateway, PR2).
5. מפעיל קוד רדום? `DecisionFields.LINKED_TASKS`/`FINAL_DECISION` קיימים בסכמה ולא בשימוש; אין הפעלת מודול רדום.
6. fallback/bypass? אסור להוסיף. אין.
7. שכבה אחרת מקבלת החלטה שהייתה אצל אחרת? לא — הסטטוס נשאר בבעלות Decisions, ביצוע בבעלות Tasks.

**PR1: `SINGLE-LAYER`** (Hub בלבד, קריאה מ-Learnings + כתיבות Hub קיימות) — דורש Mini Assessment בגוף ה-PR.
**PR2: `FULL`** — Cross-Layer Impact Matrix מלאה + Security review (`docs/governance/SECURITY_CHECKLIST.md`) לפני merge.

## 3. עקרונות מחייבים

1. Reuse before build. **אפס שדות/טבלאות Airtable חדשים בשני ה-PRs.**
2. מקור אמת יחיד: תובנה=Learnings; החלטה=Decisions; ציר זמן/ראיות=Decision Events; זיכרון עסקי=Business Memory; ביצוע=Tasks. אין העתקת סטטוסים.
3. אין כתיבה בלי אישור מפורש; אישור קשור לטוקן ולנתונים המדויקים שהוצגו (§5.2).
4. המערכת לא מחליטה, לא ממליצה ולא מבצעת עסקאות. אין תוצאה שמוצגת כ"מאומתת" אלא אם אומתה בפועל (§6.2).
5. אין מחיקה (BOSS never deletes signal): כישלון חלקי מטופל בהמשך/התאוששות, לא ב-rollback מוחק.
6. Flags כבויים כברירת מחדל; ספק זה לא מפעיל אותם.

## 4. סכמה וקישורים — מצב חי מאומת (13/10/2026, Airtable MCP, קריאה בלבד)

**קישורים הפוכים מאומתים (inverseLinkFieldId):**

| קישור | הפוך | משמעות |
|---|---|---|
| `Tasks.Decisions` (`fldSdH08g1ybwJBY6`) | `Decisions.Linked Tasks` (`fld9bO59Y9AvLa6wm`) | כתיבה בצד Tasks ממלאת אוטומטית את Decisions |
| `Decisions.Linked Memory` (`fldRhNYCA1yHosqz1`) | `Business Memory.Decisions` (`fldzSNn1TIJ3ZjXox`) | |
| `Business Memory.Related Learnings & Insights` (`fldZLIvwH39mZFmoa`) | `Learnings.Business Memory` (`fldnaXoOeFwsa04k5`) | |

**מסקנה:** שרשרת Learning ↔ Business Memory ↔ Decision קיימת במלואה בלי שדה חדש. רשומת Business Memory אחת (נוצרת בסגירה — Stage 6 המאושר במסמך האב) מקשרת גם את ההחלטה וגם את התובנה/ות המקור → מקור ההחלטה ניתן לניווט משני הצדדים.

**לפני סגירה** (תובנה שהועלתה להחלטה אך עוד לא נסגרה): ההוכחה למקור היא סמן טקסטואלי `[insight:<recId>]` ב-Inbox.Raw Input וב-Event.Raw Content — מספיק לדה-דופליקציה ולשחזור (§5.3), אך אינו ניווט ישיר מה-Learning. זה פער מקובל בשלב ראשון (פער G4).

**`Learnings.Outcome` (`fldNTSv6XM1hney3o`)** — אפשרויות חיות: `Archived`, `Decision Made ` *(עם רווח בסוף)*, `Insight Only`, `Action Required`. מכסה את מצב המחקר/ההחלטה → **לא נוסף `Research Status`** (O4). הקוד **לא** כותב אליו (O3). אזהרה לעתיד: ערכים עם רווח סופי (גם ב-`domain`: `Real Estate `, `SaaS `) — כל כתיבה עתידית חייבת להתאים byte-for-byte.

**Learnings — שדות שימושיים לקריאה:** `כותרת התובנה`, `תיאור`, `תאריך יצירה` (ב-`LearningFields`) וגם `title`, `summary`, `Next Action`, `Outcome`, `domain`, `source` (חיים, לא בקבועים). כותרת לתצוגה = הראשון הלא-ריק מ-[`כותרת התובנה`, `title`].

**Tenant:** אין `tenant_id` ב-Learnings ולא ב-Business Memory. כלל נבחר: §5.4.

**`Decision Events`:** `Event Type` חי = הודעה/מסמך/פגישה/טיוטה/לחץ/עמדה/**החלטה**; `Status` = Logged/Active/Superseded; `Channel` כולל `ידני`; `Source Reliability` כולל `רו"ח`. **`Decision Inbox`:** `Channel` כולל `Manual`; `Status` = Pending/Linked/Rejected. **`Decisions.Status`:** Open/Pending Input/Decided Yes/Decided No/Cancelled. **`Tasks.Status`:** ממתין/בביצוע/בוצע/Open. **Business Memory `Event Type`:** כולל `Decision`, `Learning`.

**Airtable changes נדרשים לשני ה-PRs: אין.** (שינויי קוד ב-`airtable_schema.py` בלבד: קבועים.)

---

## 5. PR1 — תובנה → החלטה (`/decision from-insight`)

**סיווג Cross-Layer:** SINGLE-LAYER. **Flag:** `FEATURE_DECISION_HUB` הקיים (ללא flag חדש; לא משנה משמעות שלו — הרחבת scope של אותה יכולת).

### 5.1 Contract Chain (Rule 00)

| חוליה | תוכן | סטטוס הוכחה |
|---|---|---|
| Entry Point | `cmd_decision.py::cmd_decision` (`@bot.message_handler(commands=["decision"])`), subcommand חדש | PROVEN (`cmd_decision.py:108-135`) |
| Public API | קריאה: `tools.airtable_read_adapter.list_records(table, Query|str, ...)` + `core.query_contract.contains/equals/all_of`; כתיבה: `DecisionPorts.storage.add/update` | PROVEN (`decision_ports.py`, `tools/airtable_read_adapter.py:131`, `core/query_contract.py`) |
| Data Contract | `add()`→`str|None` (record id); `update()`→`bool`; `airtable_create(..., return_outcome=True)`→`AirtableCreateOutcome(status∈created/failed/outcome_unknown)`. ה-Protocol `StoragePort.add` אינו חושף outcome. | PROVEN; **שינוי נדרש:** שיטה additive `add_with_outcome` ב-`_AirtableStorageAdapter` (לא נוגע ב-Protocol) — לאמת שאין מימוש Protocol אחר (grep) לפני PR |
| Execution Point | `tools/airtable_gateway.py::airtable_create/airtable_patch` (fail-closed, audit) | PROVEN |
| Verification Point | ערך ההחזרה + קריאה חוזרת לפי סמן (§5.3) | התכנון כאן; מימוש ב-PR |

### 5.2 זרימה ואישור קשור לשיוך המדויק

```
/decision from-insight [רמז]
 1. הרשאה (is_owner או role ∈ DECISION_ALLOWED_ROLES) + home-tenant (§5.4)
 2. בחירת תובנה (קריאה בלבד מ-Learnings) — כרטיס תובנה
 3. כפילות: חיפוש סמן [insight:<id>] (§5.3). נמצאה החלטה מקושרת → מציגים אותה;
    "החלטה נוספת" דורשת בחירה מפורשת.
 4. בחירת יעד (עדיין ללא כתיבה):  ⟶ החלטה קיימת (decision_matching, רשימת פתוחות)
                                    ⟶ החלטה חדשה (כותרת מוצעת מהתובנה, ניתנת לעריכה)
 5. כרטיס אישור אחד:  «תובנה: <כותרת> (rec…xxxx)  ⟶  החלטה: <כותרת / חדשה> »
      [✅ אשר שיוך]   [✏️ שנה יעד]   [↩️ ביטול]
 6. רק על ✅ — מתחילה כתיבה (§5.3).
```
- **State בצד שרת** (כמו `_pending`/`_new_decision_state`): `{token, insight_id, insight_fingerprint, target: {kind: existing|new, decision_id|draft}, identity, expires_at}`. `callback_data` = `dec_ins_confirm:<token>` בלבד (מגבלת 64 בתים).
- **`insight_fingerprint`** = hash(כותרת+תיאור+`Last Modified` אם קיים) ברגע ההצגה. ב-✅ קוראים את התובנה שוב; אם השתנתה → הכרטיס מוצג מחדש ולא נכתב כלום (האישור היה על תוכן אחר).
- **ביטול/פקיעה/טוקן שגוי/שינוי יעד = אפס כתיבות.** "שנה יעד" מנפיק טוקן חדש ומבטל את הישן. אין כתיבה "מקדימה" בשום שלב לפני ✅.
- re-check הרשאה ו-scope מיד לפני כתיבה (כמו `_handle_update_step`), לא סומכים על state ישן.

### 5.3 רצף כתיבה, אידמפוטנטיות וכישלון חלקי

סמן: `[insight:<learningRecId>]` בשורה האחרונה של הטקסט. כל צעד קודם **בודק קיום לפי סמן** ואז כותב.

| צעד | פעולה | אידמפוטנטיות / אימות |
|---|---|---|
| W1 | Decision Inbox: `Raw Input`=תוכן+סמן, `Channel=Manual`, `Status=Pending`, `tenant_id` | חיפוש `contains(Raw Input, marker)` + `Status ∈ {Pending, Linked}` לפני יצירה; נמצא → משתמשים בו |
| W2 | אם יעד חדש: `_create_decision` הקיים | כותרת+סמן ב-Inbox קשור; אם ה-Inbox כבר `Linked` להחלטה → משתמשים בה (לא יוצרים שנייה) |
| W3 | Decision Event: `Raw Content`=תוכן+סמן, `Channel=ידני`, `Status=Logged`, `Decision=[…]` | חיפוש `contains(Raw Content, marker)` על ההחלטה היעד |
| W4 | patch Inbox: `Status=Linked`, `Suggested Decision`, `Linked Event` | patch זהה אידמפוטנטי; מחזיר `bool` |

- **כישלון בצעד k:** מדווחים במדויק מה נשמר ומה לא (בלי "הצלחה"), שומרים על מה שנכתב (אין מחיקה), ומציגים `[המשך]` שמריץ מחדש מצעד k בלבד, על בסיס סמנים שנמצאו (לא על state בזיכרון).
- **`outcome_unknown`** (timeout ב-POST): לא עושים retry עיוור — קודם חיפוש לפי סמן; נמצא → נחשב הצלחה; לא נמצא → רק אז retry יחיד.
- **"יתום" מוגדר:** Inbox ב-`Pending` עם סמן ובלי Event, או החלטה חדשה בלי Event. הם גלויים (סמן + רשימת פתוחות) ונסגרים ע"י `[המשך]` או ידנית ב-Airtable; לא נמחקים אוטומטית. כיוון שהכתיבה מתחילה רק אחרי אישור, ביטול לעולם לא מייצר יתום.
- דיווח הצלחה מלאה **רק** כש-W1..W4 חזרו תקינים.
- הרצה כפולה (כולל אחרי ריסטארט, מטמון ריק) → אותו סמן → אותה רשומה; אין תלות ב-`_IDEMPOTENCY_CACHE` בזיכרון.

### 5.4 הרשאות ו-scope
- Capability: `owner|manager|partner` (כמו היום). אין הרחבה.
- **Home-tenant (במקום `tenant_id` ב-Learnings):** תובנות נקראות רק כש-`identity.tenant_id == "boss_hq"` (הקבוע הקנוני ב-`identity.py`). tenant אחר → דחייה (fail-closed) עם הודעה. כשיופעל `MULTITENANT` נדרש מסמך נפרד שיוסיף שיוך tenant לתובנות — מחוץ לתחום.
- הרשומות שנכתבות (Inbox/Decision/Event) נושאות `tenant_id` של ה-identity כמו היום.

### 5.5 מה מוצג כראיה
- אירוע שמקורו תובנה מקבל תווית בכרטיס: **"מקור: תובנה פנימית — לא אומת מול מקור חיצוני"**. הוא ממשיך להיכנס ל-`run_pipeline` הקיים (Trust/Delta) אך ראו §6.2 להבחנה בין Readiness לאימות.
- אין חישוב/מחקר חדש ואין פנייה ל-LLM בצעד זה.

### 5.6 קבצים (צפוי)
`cmd_decision.py` (subcommand+callbacks), `decision_insight_source.py` (חדש, קריאה בלבד: שליפת תובנות+כרטיס+סמן; ללא import של שכבת כתיבה), `decision_ports.py` (שיטה additive `add_with_outcome`), `airtable_schema.py` (קבועי `LearningFields` נוספים לקריאה: `NEXT_ACTION`, `OUTCOME`, `ALT_TITLE="title"`, `ALT_SUMMARY="summary"`), בדיקות.

---

## 6. PR2 — סגירת החלטה → משימה (`/decision close`)

**סיווג Cross-Layer:** FULL. **Flag חדש יחיד:** `FEATURE_DECISION_CLOSE` (כבוי; אין שימוש חוזר בשם קיים). **תלות:** PR1 ממוזג **לא** נדרש טכנית (ניתן לסגור כל החלטה), אך מומלץ לאחריו כדי שהשרשרת תיסגר על תובנות.

### 6.1 הרשאה (O1)
`identity.is_owner` בלבד. לא-owner → "אין הרשאה". הצגת הכרטיס נשארת לפי ה-capability הקיים. re-check לפני כל כתיבה ובכל callback.

### 6.2 הפרדה בין Readiness לאימות ראיות מהותי (תיקון 5)

| מושג | מה הוא | מקור | מה מותר לומר עליו |
|---|---|---|---|
| **Readiness** | איתות פרוצדורלי: ציון Confidence, קונפליקטים, חסרים, רמות אמינות מקור (T0–T3) | `decision_readiness.calc_readiness` | "מוכנה להכרעה לפי מדדי מקור" — **לא** "הראיות נכונות" |
| **אימות ראיות מהותי** | בדיקה בפועל מול מקור חיצוני (מסמך, רו"ח, חוק) | **אדם בלבד**. `_AntiHallucinationVerifierAdapter` הוא stub שמחזיר `ok` תמיד (`decision_ports.py:112`) | רק מה שהמשתמש הצהיר, בלשון "הצהרת הבעלים" |

הכרטיס מציג שני בלוקים נפרדים, והפוטר: **"Readiness מבוסס על מדדי מקור; המערכת אינה מאמתת תוכן."**

**הצהרת בדיקת ראיות (Evidence Attestation)** — שלב חובה בדיאלוג הסגירה:
- אפשרויות: `בוצעה — מקור: <טקסט חופשי/מסמך/שם יועץ>` | `לא בוצעה` | `לא רלוונטי`.
- כש-`Exposure Type ∈ {FINANCIAL, LEGAL}`: `לא בוצעה`/ללא מקור ⇒ ניתן **רק** `⏸ דחה להמשך` או `🚫 בטל`, או סגירה עם `override` + סיבה נרשמת. תוצאת `אשר`/`דחה` לא מותרת בלי הצהרה `בוצעה` + מקור.
- ההצהרה נשמרת בטקסט ה-Event של הסגירה (§6.3 S0) תחת "הצהרת הבעלים (לא אומתה ע"י המערכת)". לא נכתבת לשום שדה "verified".
- **שער הסגירה** = `calc_readiness(...)` בזיכרון (`can_decide`) **או** override עם סיבה, **וגם** הצהרה כנדרש. שדה `Decisions.Readiness` השמור אינו משמש כשער (T4).
- חיווי ל-`Needs real verifier` מתועד כפער G1; חיבור verifier אמיתי מחוץ לתחום.

### 6.3 מכונת מצבים, אידמפוטנטיות וכישלון חלקי (תיקון 4)

**Contract Chain (Rule 00):**

| חוליה | תוכן | סטטוס |
|---|---|---|
| Entry | `cmd_decision` subcommand `close` + callbacks `dec_close_*` | PROVEN (תבנית `dec_new_*`, `cmd_decision.py:427-480`) |
| Public API | `DecisionPorts.storage.add/update`; `_format_decision_card`; `calc_readiness` | PROVEN |
| Data Contract | `DecisionStatus.DECIDED_YES/NO/CANCELLED` (חיים ✔), `DecisionFields.FINAL_DECISION/LESSONS_LEARNED/LINKED_MEMORY` (חיים ✔); BM: `BusinessMemoryFields` + `normalize_business_memory_fields` (cmd_update) ל-Domain | PROVEN (סכמה חיה + קוד) |
| Execution | `airtable_gateway` | PROVEN |
| Verification | קריאה חוזרת של Decision (Status/Final Decision/Linked Memory) + חיפוש סמן | תכנון |

**סמנים:** `closureId` = טוקן יחיד שנוצר בכרטיס; מפתח = `close:<decisionId>:<closureId>`.

| צעד | פעולה | אידמפוטנטיות |
|---|---|---|
| S0 | **Journal Event** (Type=`החלטה`, Status=`Logged`): טקסט `[close-intent:<key>]` + JSON של הכוונה המאושרת (outcome, Final Decision, Lessons, הצהרת בדיקת ראיות, override+סיבה, approver user_id/שם, חותמת זמן, מפרט משימה אופציונלי) | חיפוש סמן לפני יצירה |
| S1 | patch Decision: `Status`, `Final Decision`, `Lessons Learned` | **לפני הכתיבה** קוראים מחדש: אם כבר טרמינלי עם **אותו** תוכן → נחשב בוצע; אם טרמינלי עם תוכן **שונה** → סירוב + התראה (לא דורסים); patch זהה אידמפוטנטי |
| S2 | Business Memory (`Event Type=Decision`): כותרת, תיאור (כולל סמן `[decision-close:<decId>]`), `Related Learnings & Insights` = כל התובנות שנמצאו לפי סמני `[insight:*]` באירועי ההחלטה | חיפוש `contains(Event Description, marker)`; נמצא → משתמשים |
| S3 | patch Decision: `Linked Memory += bmId` | בדיקה אם כבר מקושר |
| S4 | patch ה-Journal Event: `Status=Active` + שורת `[close-done:<key>]` | סימון סיום |

- **הסגירה נחשבת שלמה אחרי S4.** משימה (§6.5) **אינה** חלק ממצב הסגירה.
- **כישלון בצעד:** הודעה מפורטת (✅/⏳/❌ לכל צעד), לא "הצלחה", בלי מחיקה. `/decision close <ref>` (או כפתור `[המשך סגירה]`) על החלטה עם `close-intent` ללא `close-done` נכנס ל-**resume**: מזהה לפי עובדות שמורות מה בוצע, מציג כרטיס המשך, ודורש לחיצת ✅ נוספת. ה-payload נלקח מה-Journal — **אי אפשר לשנות אותו בהמשך** (שינוי = סגירה חדשה רק אחרי ביטול מפורש, ראו הבא).
- **S1 נכשל אחרי S0:** ההחלטה נשארת פתוחה, ה-Journal קיים → resume. **S1 הצליח, S2/S3 נכשלו:** ההחלטה סגורה ומתועדת, חסר רק BM → resume משלים. אין מצב שבו ההחלטה מדווחת סגורה ללא תיעוד מי אישר (S0 קודם).
- **החלטה שנסגרה ב-S1 כבר אינה ניתנת לסגירה נוספת**: `close` עליה = הצגת סטטוס/resume בלבד. שינוי החלטה סגורה מחוץ לתחום.
- **תחרות (שני קליקים/שתי תהליכים):** טוקן נצרך ב-pop אטומי בתהליך; בין תהליכים/workers ההגנה הברזל היא S0 (סמן) + קריאה-מחדש ב-S1. לא מניחים מצב תהליך משותף.
- **`outcome_unknown`** בכל POST → חיפוש סמן לפני retry (כמו §5.3).

### 6.4 מה לא נכתב
`Learnings.Outcome` — לא נכתב אוטומטית (O3). Stakeholders — לא מתעדכנים (O5). חוות דעת מייעצים נקלטות כ-Events רגילים דרך `/decision update` (קיים), ואם יש מייעץ שמוכר כ-Contact — דרך `Stakeholder` שבאירוע (קיים).

### 6.5 משימה — Golden Writer + Action Gateway, אישור נפרד (O2, תיקון 6)

**Contract Chain (Rule 00) — מצב הוכחה:**

| חוליה | תוכן | סטטוס |
|---|---|---|
| Entry | callback `dec_task_confirm:<token>` (כפתור נפרד אחרי סגירה שלמה) | תכנון; התנגשות prefix ב-`app.py` — **TO-PROVE** |
| Public API | `core.action_gateway.ActionGateway.propose_action(tenant_id, canonical_user_id, tool_name="airtable_add", tool_inputs={"table": Tables.TASKS, "fields": …}, origin_channel, origin_chat_id, requires_approval=True, identity=<owner אמיתי>, trusted_source=…, user_text)` | PROVEN (`core/action_gateway.py:2110`) |
| Gate 1 | `complete_task_proposal` → `core.task_writer` (כותרת תקינה, Cadence, אימות קישורים) נקרא אוטומטית מתוך `propose_action` | PROVEN (`:2166-2173`) |
| Gate 2 | `tools/dispatcher.py` (`prepare_task_create`, `_DEDUP_FIELDS` לפי `כותרת המשימה`) | PROVEN |
| Approval | אישור אמיתי של המשתמש. precedent קיים אך אינו מתאים כמות שהוא: `interaction_engine` מאשר בעצמו כ-system identity; `tma_api._queue_or_owner_execute` מאשר owner אוטומטית דרך `_claim_and_execute_approval` ודורש `FEATURE_ACTION_CONTRACT_PERSISTENCE`+`FEATURE_ATOMIC_CLAIMS` | **TO-PROVE (חוסם PR2)** — ראו הבא |
| `trusted_source` | מחרוזת בעלת שם דילוג על אימות-קישורים של מקור `agent` (`_UNTRUSTED_TASK_SOURCES={"agent",""}`) → ה-Hub חייב לאמת בעצמו שה-`decision_id` קיים ובאותו tenant לפני ההצעה | PROVEN (`:729`, `:916`) |
| Data Contract | שדה `Tasks.Decisions` חי ✔ ו-`schema_cache.json` מכיר אותו ✔; חסר קבוע `TaskFields.DECISIONS_LINK` בקוד; ערך חייב להיות list של rec ids (מחרוזת בודדת מוקנית ל-list רק בטבלאות ב-`LINKED_RECORD_FIELDS`) | PROVEN חלקית — לאמת `LINKED_RECORD_FIELDS[Tasks]` ו-`_TASK_WRITE_FIELDS` ב-`core/router/task_builders.py` לפני PR |
| Verification | `GatewayResult`/ledger + קריאה חוזרת: `Decisions.Linked Tasks` מכיל את המשימה (הפוך אוטומטי ✔) | תכנון |

**החלטת תכנון (ממתינה לאימות Rule 00):** שני אישורים נפרדים (O2):
1. אישור סגירה — §6.3.
2. אישור משימה — אחרי `close-done`, כרטיס נפרד «משימת המשך: <כותרת> | Owner | יעד | פעולה הבאה» + `[✅ אשר משימה] [⏭ דלג]`. ✅ → `propose_action` עם הזהות האמיתית של ה-owner, **ובנתיב האישור הרגיל של ה-Gateway** (אפשרות (i): ההצעה מוצגת בממשק האישורים הקיים כ-pending; Hub לא מאשר בעצמו). אפשרות (ii) (אישור inline תחת לחיצת ה-owner) תתאפשר רק אם ה-Rule 00 יוכיח שהיא מתיישבת עם `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` ועם מדיניות האישור, ובאישור Security review.
- אין יצירת Task ישירה מה-Hub בשום נתיב, ואין `airtable_create(Tables.TASKS…)` בקוד החדש (grep ב-CI).
- **תוכן המשימה:** `כותרת המשימה` (Golden Writer מנרמל), `תיאור` שורה ראשונה `פעולה הבאה: …` + סמן `[decision:<decId>]`, `תאריך יעד` ISO, `Owner` = רשומת Profile קיימת (כמו `TaskFields.OWNER`), `סטטוס`=`ממתין`, `Decisions=[decId]`. **Owner ותאריך יעד חובה** כדי להציע; פעולה הבאה חובה.
- **מניעת כפילות:** (א) אם ל-Decision כבר יש `Linked Tasks` → מציגים ולא מציעים אלא ב"משימה נוספת" מפורשת; (ב) fingerprint/dup של ה-Gateway + `_DEDUP_FIELDS` לפי כותרת; (ג) סמן `[decision:<decId>]` לאיתור יתומים.
- **דחיית/ביטול/כישלון משימה אינם מבטלים את הסגירה.** הכרטיס מציג «משימת המשך: ממתינה/נדחתה/נכשלה/בוצעה» לפי עובדה שנקראת מה-Gateway/Tasks, לא לפי העתק.

### 6.6 תוצאה חוזרת ל-Hub
`/decision status` מוסיף בלוק «ביצוע»: משימות מקושרות (קריאה בלבד מ-Tasks דרך `Linked Tasks`/`Tasks.Decisions`): סטטוס, יעד, Owner — מול מה שתוכנן (מה-Journal: כותרת+יעד). סימון "בוצע" נשאר ב-flow הקיים (`tma_api.py` + Golden Writer). "מה קרה בפועל" = Event רגיל או `Lessons Learned` (נכתב רק בסגירה). אין סנכרון סטטוסים.

### 6.7 קבצים (צפוי)
`cmd_decision.py` (close + callbacks + בלוק ביצוע), `decision_closure.py` (חדש, טהור: תנאי קדם, בניית payloads, מכונת צעדים; ללא I/O ישיר), `airtable_schema.py` (`TaskFields.DECISIONS_LINK`), `feature_flags.py` (רישום `FEATURE_DECISION_CLOSE` בדוקסטרינג+קוד), נקודת מגע ל-Gateway כפי שיוכח ב-Rule 00, בדיקות.

---

## 7. בדיקות וקריטריוני קבלה

בדיקות סקריפט עצמאיות בתבנית `test_*.py` (ללא Flask/Anthropic/Airtable אמיתיים; storage מוזרק). כל טענת "N עברו" תציין שכבה (unit/integration) לפי PLANNING_GATE §8. מסלול Gateway ב-PR2 — בדיקת integration עם Gateway מקומי/mock כמו `test_action_gateway.py`.

**PR1:** תובנה לא-home-tenant → נדחית | role לא מורשה → נדחה | תובנה ללא כותרת → כותרת חלופית `title` | ✅ לא נלחץ (ביטול/פקיעה/טוקן שגוי/שינוי יעד) → **0 כתיבות** (ספירת קריאות storage) | תובנה שונתה בין הצגה ל-✅ → אין כתיבה, כרטיס מחודש | הרצה כפולה + מטמון ריק → Inbox אחד, Event אחד | כישלון ב-W3 → הודעה מפורטת, Inbox+Decision נשארו, `[המשך]` משלים רק W3-W4 | `outcome_unknown` ב-W1 → חיפוש סמן לפני retry | `update()` החזיר False → דיווח כישלון | grep: אין import של שכבת כתיבה בקבצים החדשים.

**PR2:** לא-owner → נדחה | החלטה לא READY (בזיכרון) ללא override → חסומה | Exposure FINANCIAL/LEGAL בלי הצהרת בדיקה → רק דחייה/ביטול/override | `REVIEW` readiness לא נכתב כשער | כישלון ב-S1/S2/S3 → resume משלים, payload מה-Journal | החלטה טרמינלית עם תוכן שונה → סירוב | סגירה כפולה/שני קליקים → תיעוד אחד, BM אחד | סגירה לא יוצרת משימה לפני אישור נפרד | אישור משימה → payload שאושר = payload שנכתב | `Linked Tasks` קיים → נדרש "משימה נוספת" | דחיית משימה משאירה סגירה שלמה | grep: אין `airtable_create(Tables.TASKS` בקוד החדש.

**Definition of Done:** `CODE_EXISTS` = בדיקות ירוקות + `python3 smoke_tests.py` + CI. `RUNTIME_VERIFIED` = הרצה בסביבה אמיתית אחרי שהבעלים הפעיל flag (O6) — עד אז 🟡 CODE DONE, NOT VERIFIED.

**תרחיש בדיקה תיאורטי (קרן ההון, ללא רשומות אמיתיות וללא עסקאות):** תובנה "מימוש הפסדי הון לקיזוז מס" → `from-insight` → החלטה (Exposure=FINANCIAL) → Events עם חוות דעת רו"ח (`Source Reliability=רו"ח`) → סגירה: הצהרה `בוצעה — מקור: חוות דעת רו"ח מתאריך …` → `אשר בדיקה מוגדרת בלבד` → BM מקשר תובנה+החלטה → כרטיס משימה נפרד «לקבל חוות דעת מסכמת לפני כל פעולה» → אישור Gateway → בלוק ביצוע בכרטיס. המערכת לא ממליצה ולא מבצעת פעולה פיננסית.

## 8. פריטי Rule 00 שחייבים להיות מוכחים לפני פתיחת כל PR

| PR | פריט | דרך הוכחה |
|---|---|---|
| 1 | אין התנגשות prefix `dec_ins_*` ב-dispatcher של callbacks | grep ב-`app.py` + קריאת הקוד |
| 1 | `add_with_outcome` לא שובר מימושי `StoragePort` אחרים | grep מימושים/fakes בבדיקות |
| 1 | מקור הערך `"boss_hq"` ב-home-tenant: קבוע משותף ולא literal שנייה | grep `identity.py`/`config.py` |
| 2 | **נתיב אישור המשימה** (אפשרות (i) מול (ii)), כולל כיצד עובר contract שנוצר מ-callback של Telegram לממשק האישורים הקיים | קריאת `app.py::_queue_approval*` + `_handle_approval_callback` + בדיקת integration |
| 2 | ערך `trusted_source` ל-Hub: האם נדרש רישום ב-`classify_approval_policy`/`tool_registry` או ש-`airtable_add` מספיק | קריאת `core/action_gateway.py:203-290`, `tool_registry.py` |
| 2 | `LINKED_RECORD_FIELDS[Tasks]` ו-`_TASK_WRITE_FIELDS` כוללים `Decisions` או שמספיק list | קריאת `tools/airtable_gateway.py:95` ו-`core/router/task_builders.py` |
| 2 | קונפליקט prefix `dec_close_*`/`dec_task_*` | כמו PR1 |
| 2 | האם `FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ATOMIC_CLAIMS` נדרשים לנתיב הנבחר ומה מצבם ב-Render | `feature_flags.py` + אימות בעלים (O6-ממשיך) |

## 9. תנאי הפעלה (מחוץ לספק זה, בידי הבעלים)
1. אימות מצב `FEATURE_DECISION_HUB` ב-Render (O6) — **לא אומת**.
2. PR ממוזג ו-deployed + commit hash מול origin/main.
3. הפעלת flag בידי הבעלים בלבד; canary על החלטה אחת.
4. אימות בפרודקשן לפני כל הצהרת "פעיל".

## 10. פערים שנותרו (לא נסגרים בשני ה-PRs, בכוונה)

| # | פער | סטטוס |
|---|---|---|
| G1 | אין אימות תוכן אמיתי של ראיות (`VerifierPort` stub). הספק מונע הטעיה אך לא מוסיף verifier | מחוץ לתחום |
| G2 | נתיב אישור המשימה ל-Gateway מ-Telegram לא הוכח (§8) — חוסם PR2 | לפני PR2 |
| G3 | `DecisionReadiness.REVIEW` לא קיים חי; ערך שמור ייחסם. נדרש: אפשרות חדשה ב-Airtable (החלטת בעלים) **או** מיפוי `REVIEW→NOT_READY` בשמירה | החלטת בעלים |
| G4 | אין ניווט ישיר Learning→Decision לפני סגירה (רק סמן טקסטואלי) | מקובל בשלב ראשון |
| G5 | `tenant_id` לתובנות לא קיים — נפתר רק ע"י כלל home-tenant; multi-tenant דורש עבודה נפרדת | מחוץ לתחום |
| G6 | עמדות מייעצים (Stakeholder) לא מתעדכנות (O5) | מחוץ לתחום |
| G7 | `Learnings.Outcome` לא מתעדכן אוטומטית (O3) | מחוץ לתחום |
| G8 | הערות מיושנות בקוד על "silent drop" ו"שדות Stage 2 לא קיימים" | ניקוי תיעוד קטן, יכלל ב-PR1 רק אם בעלים יאשר |
| G9 | ROADMAP: טרם הוקצה מזהה, ו-`עודכן:` לא עודכן; חובה ב-PR הראשון (`AGENTS.md`) | לפני PR1 |

---

## 11. תוכנית עבודה — שני PRs נפרדים

### PR1 — `/decision from-insight` (Cross-Layer: SINGLE-LAYER)
**תנאי כניסה:** סגירת פריטי PR1 ב-§8; מזהה ROADMAP (G9); אישור בעלים לספק.
1. קבועי `LearningFields` (קריאה) ב-`airtable_schema.py`.
2. `decision_insight_source.py` — שליפה, כרטיס, סמן, fingerprint (טהור/קריאה בלבד).
3. `decision_ports.py` — `add_with_outcome` (additive).
4. `cmd_decision.py` — subcommand + callbacks + מכונת W1–W4 עם resume.
5. בדיקות (§7), `smoke_tests.py`, עדכון ROADMAP/CHANGE_CONTROL_LOG/CHANGELOG לפי `RELEASE_CHECKLIST.md`.
6. PR עם הצהרה `Cross-Layer Impact: SINGLE-LAYER` + Mini Assessment. **Flag:** קיים, נשאר כבוי.
**אין Airtable. אין flag חדש.**

### PR2 — `/decision close` + משימת המשך (Cross-Layer: FULL)
**תנאי כניסה:** PR1 ממוזג (מומלץ); כל פריטי PR2 ב-§8 מוכחים; החלטת בעלים על G3; Security review + Impact Matrix מלאה.
1. `TaskFields.DECISIONS_LINK` + רישום `FEATURE_DECISION_CLOSE` (כבוי).
2. `decision_closure.py` — תנאי קדם, הפרדת Readiness/הצהרת בדיקה, מכונת S0–S4 + resume.
3. `cmd_decision.py` — `/decision close`, כרטיסים, callbacks, בלוק «ביצוע».
4. נקודת מגע ל-Gateway לפי תוצאת Rule 00 (אישור נפרד, Golden Writer).
5. בדיקות integration ל-Gateway + grep guards (§7).
6. PR עם `Cross-Layer Impact: FULL` + Matrix + Security checklist. **Flag נשאר כבוי.**

### אחרי שני ה-PRs (בידי הבעלים)
אימות O6 → merge+deploy → הפעלת flag → canary → אימות בפרודקשן → רק אז עדכון סטטוס ל-RUNTIME_VERIFIED.
