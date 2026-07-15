# הצעה כוללת (v2) — TurnCoordinator + TurnEnvelope

**סטטוס:** ARCHITECTURAL PROPOSAL — READY FOR PHASE 0 IMPLEMENTATION PLANNING (לא עדיין READY FOR IMPLEMENTATION — לפני כתיבת קוד צריך להפוך את Phase 0 לרשימת call sites ומקורות state מדויקים)
**מחליפה/מרחיבה:** `TURN_COORDINATOR_PROPOSAL.md` (v1) — אותם עקרונות יסוד, מוכללים לכל תרחיש
**זיהוי:** שני מקרי מבחן חיים — כשל (batch לידים) והצלחה (בקשת קפה) — מוכיחים ששני המנגנונים חייבים להתאחד תחת envelope אחד

---

## שני מקרי המבחן שמגדירים את הדרישה

### מקרה A — כשל: מודעות למצב ממתין חסרה
```
BOSS: 5 מועמדים ממתינים... ענה כן/לא
Eli:  שמור 3
BOSS: לא הבנתי — משימה? ליד? קובץ?     ← וואקום מוחלט, לא ראה את הרשימה
Eli:  ליד מספר 3
BOSS: לא מצאתי "ליד מספר 3"            ← חיפש ב-CRM במקום לקרוא את הרשימה שהוא עצמו הציג
```

### מקרה B — הצלחה: מודעות ליכולת עצמית קיימת
```
Eli:  תכין לי קפה
BOSS: אני עוזר דיגיטלי — לא יכול להכין קפה.
      אבל אני כן יכול: תזכורת / הודעה / משימה
```

**התובנה המרכזית:** מקרה B כבר עובד היטב — הסוכן יודע להסביר מה הוא **לא** יכול לעשות ומציע חלופות קונקרטיות מתוך היכולות האמיתיות שלו. מקרה A נכשל כי אותה יכולת בדיוק — "לדעת מה אני לא יודע ולהסביר את זה נכון" — לא הוחלה על **מצב שיחה ממתין**, רק על **גבולות יכולת קבועים**.

**המסקנה:** אלה לא שני בעיות נפרדות. זו אותה יכולת ("מודעות עצמית של הסוכן"), שצריכה להיות מוזנת מ**מקור אחד מאוחד**, לא משני מנגנונים שונים שיכולים להיסחף זה מזה.

---

## עיקרון העל (ללא שינוי מ-v1, מוכלל)

```
✅ הסוכן מקבל context מלא — גם על pending state, גם על capability boundaries
✅ הסוכן מנסח תשובה טבעית, מסביר מגבלות, מציע חלופות אמיתיות
✅ הסוכן מציע פרשנות ("התכוונת ל-X?") מתוך מה שהוא באמת יודע

❌ הסוכן לא מבצע resolution בעצמו על משהו שהוא לא בטוח בו
❌ הסוכן לא מנחש/מהמצא יכולת שלא קיימת (למשל "אני יכול להכין קפה וירטואלי")
❌ הסוכן לא מחפש בעצמו כשהתשובה כבר ברשימה שהוא עצמו הציג
```

**התפקיד הכולל:** הסוכן הוא **המסביר של המערכת** — של מה שהוא יודע, של מה שהוא לא יודע, ושל המצב שבו השיחה נמצאת. שלושתם מגיעים מאותו מקור.

---

## TurnEnvelope מוכלל — שלושה חלקים נפרדים בתוך אותו מבנה

חשוב להבחין: יש שלושה סוגי מודעות שונים באופיים, וצריך להזין את כולם, אבל לא לבלבל ביניהם.

### חלק 1 — Pending Awareness (פרואקטיבי, ידוע מראש) — **מתוקן: תמיכה במספר queues בו-זמנית**

**התיקון הזה נדרש בגלל סתירה מבנית שהתגלתה:** ה-DoD דרש תמיכה במצב שבו יש יותר ממקור pending אחד בו-זמנית (למשל batch לידים + follow-up נפרד ממתין) — אבל הגרסה הקודמת של ה-schema הגדירה `pending: Optional[PendingAwareness]` יחיד. זו לא הרחבה, זו תיקון של סתירה.

```python
@dataclass
class PendingItem:
    index: int            # 1-based, בדיוק כמו שהוצג למשתמש
    id: str               # מזהה קנוני: contract_id / lead_id / task_id / file_id...
    kind: str             # "lead_candidate" | "task" | "file" | "action_contract" | ...
    label: str            # בדיוק הטקסט שהוצג למשתמש, לא תיאור מחדש

@dataclass
class PendingQueueAwareness:
    queue_id: str
    source: Literal["action_gateway", "lead_capture", "file_flow", "task_flow", "system"]
    kind: str
    summary: str                          # תבנית דטרמיניסטית, לעולם לא LLM
    items: list[PendingItem]
    approval_granularity: Literal["all_or_nothing", "per_item", "single_choice", "none"]
    allowed_actions: list[str]
    forbidden_actions: list[str]          # אזהרה בלבד — ראה §Policy Source למקור האמיתי
    expires_at: Optional[datetime]
    priority: int
```

**עקרון מפתח (ללא שינוי):** `items` הוא **חובה** בכל queue פעיל. כל רשימה ממוספרת שהמערכת מציגה — לידים, משימות, קבצים, disambiguation — נכנסת לאותו מבנה. "מספר 3" תמיד נפתר דרך `items[2].id` **בתוך ה-queue הפעיל**, לא גלובלית.

### מדיניות עדיפות — הכרעה מפורשת, לא סדר query מקרי

כשיש כמה queues בו-זמנית, צריך לדעת לאיזה מהם ההודעה הנוכחית כנראה מתייחסת:

```text
סדר עדיפות:
1. תשובה מפורשת המתייחסת ל-queue נקוב (למשל המשתמש ציין הקשר מפורש)
2. reconfirmation_required
3. disambiguation פעיל
4. approval pending
5. capture pending
6. free agent
```

זו מדיניות קבועה, לא תוצאה מקרית של סדר הבדיקות בקוד — היא צריכה להיות מתועדת ובדיקה ב-DoD בפני עצמה.

### חלק 2 — Capability Awareness (תמידי, לא תלוי mode) — **מתוקן: לפי פעולה, לא לפי קטגוריה**

זה מגיע ישירות ממקרה הקפה. בניגוד ל-pending state, הסוכן **לא יכול לדעת מראש** שהמשתמש יבקש קפה — לכן זה לא "mode" שה-Coordinator קובע, אלא **הקשר שתמיד קיים ברקע**, שהסוכן שוקל בעצמו כשמבקשים ממנו משהו שלא מתאים.

**התיקון הנדרש:** הגרסה הקודמת (`available_categories`/`restricted_categories`, "זמין/מוגבל") מטעה. הסוכן עצמו לא שולח, לא יוצר רשומות ולא משנה מערכות — הוא מנסח, מציע, ומבקש ביצוע ממנגנון הפעולות. "אני יכול לשלוח הודעות" הוא ניסוח לא מדויק: גם אם הכלי זמין, הפעולה עשויה לדרוש אישור, להיות חסומה בהקשר הנוכחי, או זמינה רק לקריאה.

### הכלל המכריע: לסוכן יכולות שיחה; למערכת יכולות ביצוע

```text
The agent has conversational capabilities.
The system has operational capabilities.
The agent may describe and propose operational capabilities,
but may never present them as its own direct actions.
```

בעברית: לסוכן יש יכולות שיחה, ניתוח וניסוח. למערכת יש יכולות קריאה וביצוע באמצעות כלים. הסוכן רשאי להסביר ולהציע את יכולות המערכת, **אך אינו מציג אותן כפעולות שהוא מבצע בעצמו**.

### מסלול היכולת — לא זמין/מוגבל, אלא `CapabilityMode`

```python
class CapabilityMode(Enum):
    RESPOND_DIRECTLY = "respond_directly"          # יכולת שפה של הסוכן עצמו — לא דורש כלי
    READ_VIA_TOOL = "read_via_tool"                # קריאה בלבד דרך כלי
    PROPOSE_ACTION = "propose_action"               # יוצר הצעה/ActionContract, לא מבצע
    EXECUTE_AFTER_APPROVAL = "execute_after_approval"  # ביצוע אמיתי, דורש אישור
    UNAVAILABLE = "unavailable"

@dataclass
class CapabilityAction:
    action_id: str
    category: str
    user_description: str
    mode: CapabilityMode
    requires_approval: bool
    currently_available: bool
    unavailable_reason: Optional[str]
    alternatives: list[str]

@dataclass
class CapabilityScope:
    domain_description: str              # "עוזר דיגיטלי" — לא רשימת tools גולמית
    actions: list[CapabilityAction]       # ← החליף את available_categories/restricted_categories
```

**דוגמה — תחום המייל:**

```python
[
    CapabilityAction(
        action_id="compose_email_text", category="email",
        user_description="לנסח תוכן למייל בתוך השיחה",
        mode=CapabilityMode.RESPOND_DIRECTLY,
        requires_approval=False, currently_available=True,
        unavailable_reason=None, alternatives=[],
    ),
    CapabilityAction(
        action_id="create_gmail_draft", category="email",
        user_description="ליצור טיוטה אמיתית ב-Gmail",
        mode=CapabilityMode.EXECUTE_AFTER_APPROVAL,
        requires_approval=True, currently_available=True,
        unavailable_reason=None, alternatives=["להציג את הנוסח כאן בלבד"],
    ),
]
```

כך הסוכן יודע לומר: **"אני יכול לנסח את המייל כאן עכשיו. כדי לשמור אותו כטיוטה ב-Gmail, אכין פעולה לאישור."** — לא "אני יכול להשתמש במייל."

### הבחנת שמות: ניסוח בשיחה ≠ אובייקט אמיתי במערכת חיצונית

המילה "טיוטה" מבלבלת כי היא מתארת גם טקסט בשיחה וגם אובייקט אמיתי ב-Gmail. שתי שכבות שונות:
- **ניסוח טקסט למייל** הוא יכולת שפה רגילה — כמו ניסוח הודעה, סיכום או מסמך. `RESPOND_DIRECTLY`, לא דורש כלי.
- **יצירת טיוטה אמיתית בחשבון Gmail** היא יכולת תפעולית של המערכת, דורשת כלי ואישור. `EXECUTE_AFTER_APPROVAL`.

לכן שמות שונים, לא אותה מילה:
```text
email_text_draft       = נוסח מוצע בתוך השיחה
gmail_saved_draft       = טיוטה שנוצרה בפועל ב-Gmail
```

**למה לא dump מלא של tool registry:** דחיסת 21 שמות tools גולמיים לפרומפט כל turn היא בזבוז וגם מסוכנת (הסוכן עלול "לזהות" tool ולנסות לקרוא לו ישירות מתוך זה שהוא ברשימה). `CapabilityAction.user_description` נותן לסוכן ניסוח טבעי בלי לחשוף incantation מדויק של tool call.

### מקור אמת יחיד ל-mode/approval — Policy Source

**פער שהתגלה:** לא היה מוגדר מי מייצר את `forbidden_actions`/רשימת ה-capabilities ואיך זה נשאר מסונכרן עם מה ש-`dispatcher`/`tool_registry.enforce()` אוכף בפועל בזמן אמת. בלי מקור משותף, אפשר לקבל drift: הפרומפט אומר "מותר" בזמן שה-dispatcher חוסם, או להפך.

**תיקון נוסף:** `PolicyDecision` עם `allowed: bool` יחיד אינו מספיק — פעולה יכולה להיות "מותר להציע: כן, מותר לבצע ישירות: לא, מותר לאחר אישור: כן" בו-זמנית. Boolean יחיד לא מבטא את זה.

```python
@dataclass
class PolicyDecision:
    action: str
    capability_mode: CapabilityMode
    allowed_to_propose: bool
    allowed_to_execute: bool
    approval_required: bool
    reason_code: str
    user_explanation: str

policy_snapshot = policy_engine.evaluate_scope(
    identity=identity,
    domain=domain,
    turn_mode=mode,
    pending_context=pending_queues,
)
```

**הכלל:** ה-Coordinator לא מחזיק רשימה ידנית. `CapabilityAction.mode`/`requires_approval`/`PendingQueueAwareness.forbidden_actions` **כולם נגזרים בזמן אמת מאותו policy evaluator** ש-`dispatcher` מריץ בפועל בזמן ביצוע — לא רשימה מתוחזקת בנפרד ב-Coordinator. קיום tool ברג'יסטרי **לבדו אינו הופך פעולה ל"זמינה"** — `currently_available` נגזר גם ממדיניות האישור וגם מהמצב הנוכחי (health, tenant, role).

### חלק 3 — Last Outbound Kind (ראה §Message Kind למטה)

```python
@dataclass
class TurnEnvelope:
    pending_queues: list[PendingQueueAwareness]   # ← היה יחיד, עכשיו רשימה
    active_queue_id: Optional[str]                # ← חדש: מי מהם רלוונטי לתגובה הנוכחית
    capability: CapabilityScope
    last_outbound_kind: Optional[MessageKind]
    reply_owner: Optional[str]                    # ראה §מסלול הטמעה, Phase 3
```

**התוצר הסופי אינו "רשימת דברים שהסוכן יכול לעשות" — הוא:** מה ממתין עכשיו, למה מתייחסת ההודעה, מי בעל התשובה, מה המערכת יודעת לעשות, ובאיזה מסלול כל יכולת זמינה. ההבדל הזה הוא מה שמונע מהמערכת לומר "אני יכול לשלוח מייל" ואז לעצור ולבקש אישור, או לגלות שהכלי כלל אינו זמין.



---

## Mode — נשאר כמו ב-v1, אבל בלי "capability mode" נפרד

חשוב להבהיר טעות אפשרית: **capability awareness אינו mode**. ה-Coordinator לא יכול לדעת מראש "המשתמש עומד לבקש קפה" ולקבוע mode מתאים. לכן:

```python
mode: Literal[
    "approval_pending",
    "reconfirmation_required",
    "partial_selection_ambiguous",
    "free_agent"
]
```
נשאר זהה ל-v1. `capability` מוזרק **בנוסף**, בכל mode, כולל `free_agent` — כי בקשת "קפה" יכולה להגיע גם כשאין שום pending state.

```python
def build_turn_envelope(user, conversation_state) -> TurnEnvelope:
    mode = decide_mode(conversation_state)                       # כמו קודם
    pending_queues = collect_pending_queues(conversation_state)   # מכל המקורות הקיימים
    active_queue_id = select_active_queue(pending_queues, mode)   # לפי מדיניות העדיפות
    capability = build_capability_scope(user.domain)              # תמיד
    return TurnEnvelope(
        pending_queues=pending_queues,
        active_queue_id=active_queue_id,
        capability=capability,
    )
```

---

## Resolver מאוחד — מנגנון אחד ל"מספר N" בכל תחום, בתוך ה-queue הפעיל

זו התוצאה הישירה של מקרה A. במקום שכל feature (leads, tasks, files, disambiguation) יממש בעצמו זיהוי "מספר N", יש **פונקציה אחת**, שפועלת בתוך `active_queue_id`:

```python
@dataclass
class ResolvedReference:
    queue_id: str
    item_id: str
    index: int
    label: str

def resolve_numbered_reference(
    user_text: str, active_queue: PendingQueueAwareness
) -> Optional[ResolvedReference]:
    n = extract_ordinal_or_number(user_text)   # "3", "מספר 3", "השלישי" וכו'
    if n is None or not (1 <= n <= len(active_queue.items)):
        return None
    item = active_queue.items[n - 1]
    return ResolvedReference(queue_id=active_queue.queue_id, item_id=item.id, index=n, label=item.label)
```

הפונקציה מחזירה **עובדה**, לא ביצוע. הסוכן **לא** מנחש/מחפש בעצמו — הוא מקבל את התוצאה הזו, ומנסח סביבה תשובה טבעית:

> "ה-5 המועמדים ממתינים כחבילה אחת ('all_or_nothing') — אי אפשר לשמור רק את אלי קורן (מספר 3) לבד. רוצה לאשר את כולם, לבטל הכל, או שאפתח בקשה נפרדת רק לאלי קורן?"

זו תשובה אחת, בתור אחד — לא שני turns שגויים כמו במקרה A בפועל.

---

## Commitment Grounding — הצהרות ללא כיסוי (נפרד מ-Execution Boundary ומ-Single Speaker)

חשוב להבחין בין **שלושה** מנגנוני הגנה שונים שקל לבלבל ביניהם, כי כולם "מונעים שהסוכן יגיד/יעשה משהו שגוי" — אבל כל אחד תופס שכבה אחרת:

| מנגנון | מונע מה | כבר קיים/מתוכנן? |
|---|---|---|
| **Execution Boundary** (4C-1A) | ביצוע כתיבה מסוכנת בפועל בלי claim חי (למשל ליד עצמאי, AP-11) | כן — מטופל |
| **Reply Ownership / Single Speaker** (Phase 3) | **יותר מרכיב אחד** עונה לאותו turn, תשובות סותרות/כפולות | כן — מתוכנן, אבל **פותר מי מדבר, לא מה שנאמר** |
| **Commitment Grounding** (Phase 5, חדש) | הרכיב **היחיד** שכן מדבר, אומר משהו שלא קרה בפועל | **לא — עדיין חסר** |

**הנקודה הקריטית:** גם אחרי ש-Reply Ownership ייושם במלואו, יישאר בדיוק רכיב אחד עונה בכל turn — וזה בדיוק הרכיב שיכול לכתוב "אני אגיד לאליהו שיחזור אליך" בלי שום tool-call מאחורי זה. Reply Ownership פותר **ריבוי דוברים**, לא **אמינות תוכן הדובר היחיד**. אלה שני צירים אורתוגונליים; אי אפשר לסמוך שהאחד יפתור את השני.

### הכלל (הרחבה של BUG-091)

```
Agent may propose. Agent may NOT self-certify.               ← קיים
Agent may describe an action as done or promise a third      ← חדש
party's future action ONLY if a corresponding durable record
(ActionContract / Task / tool_result) was created in this
exact turn. Otherwise: phrase conditionally, never as fact.
```

### מנגנון: בדיקה אחרי ניסוח, לא context נוסף

בשונה מ-`TurnEnvelope` (מידע *לפני* שהסוכן מנסח), זה שער *אחרי*:

```python
def validate_agent_output(
    agent_reply_text: str,
    actions_taken_this_turn: list[ActionRecord],
) -> ValidationResult:
    claimed_commitments = extract_commitment_phrases(agent_reply_text)
    # דפוסים כמו: "אני אגיד ל-X", "X יחזור אליך", "שמרתי", "נשלח", "עדכנתי"

    for claim in claimed_commitments:
        if not any(action.matches(claim) for action in actions_taken_this_turn):
            return ValidationResult(
                blocked=True,
                reason=f"התחייבות '{claim}' בלי רשומת פעולה תואמת בתור הזה",
            )
    return ValidationResult(blocked=False)
```

**מה קורה כשנחסם:** לא "לתקן" את הטקסט אוטומטית (זה בעצמו ניחוש נוסף) — להחזיר לסוכן לניסוח מחדש עם ההנחיה המפורשת: תאר את זה כהצעה/יכולת, לא כעובדה מושלמת. בשלב ראשון (Phase 0-1) מספיק **log-only**, כדי למדוד כמה זה קורה בפועל לפני שאוכפים חסימה.

### דוגמה — לפני/אחרי

❌ "אני אגיד לאליהו שיחזור אליך" — בלי tool-call, בלי Task, בלי שום רשומה.
✅ "אני יכול ליצור תזכורת/משימה שאליהו יחזור אליך — רוצה שאפתח כזו?" (או, אם באמת נוצר Task באותו turn: "יצרתי תזכורת שאליהו יחזור אליך.")

---

## Message Kind — הכיוון השני: מודעות המשתמש (ולסוכן) למקור ההודעה

עד כה כל ההצעה עסקה בכיוון אחד: **הסוכן מודע למערכת**. יש כיוון שני, נפרד לגמרי, שגם הוא חייב להיפתר: **המשתמש (וגם הסוכן עצמו, כשהוא קורא היסטוריה) צריך לדעת שהודעה מסוימת היא הודעת מערכת, לא תגובה של הסוכן**.

בלי זה, "5 מועמדים ממתינים... ענה כן/לא" נראה למשתמש בדיוק כמו תגובה רגילה של הסוכן — והוא לא יודע להבחין בין "המערכת פנתה אליי ביוזמתה" לבין "זו תגובה למה שאמרתי". וכשהסוכן עצמו בונה את התשובה הבאה, הוא צריך לדעת שההודעה הקודמת בהיסטוריה לא הייתה שלו — אחרת הוא עלול "להתייחס אליה כאילו אמר אותה".

### תיוג לכל הודעה יוצאת

```python
class MessageKind(Enum):
    AGENT_REPLY = "agent_reply"                  # תגובה חופשית של הסוכן
    SYSTEM_NOTIFICATION = "system_notification"   # נשלח ביוזמת scheduler/job, לא כתגובה לפנייה
    APPROVAL_PROMPT = "approval_prompt"           # בקשת אישור מפורשת, ממתינה לכן/לא
    CLARIFICATION_REQUEST = "clarification_request"  # המערכת תקינה, אבל יש עמימות/חוסר מידע
    CAPABILITY_BOUNDARY = "capability_boundary"   # "לא יכול X, אבל כן Y" — תבנית קבועה
    SYSTEM_ERROR = "system_error"                 # רכיב נכשל בפועל, לא רק עמימות
```

**הבחנה סמנטית שהייתה חסרה:** "5 מועמדים, שמור 3, לא הבנתי" **אינה** שגיאת מערכת — זו שאלת הבהרה לגיטימית באמצע flow תקין. אם זה מתויג `SYSTEM_ERROR`, אנליטיקה עתידית (כמה שגיאות קרו) תבלבל בין תקלה אמיתית לתהליך בירור רגיל.

```text
"ביקשת 4 אבל זיהיתי 5 — אילו לשמור?"        → CLARIFICATION_REQUEST (המערכת עובדת נכון)
"לא הצלחתי לטעון את הפעולות הממתינות"        → SYSTEM_ERROR (רכיב נכשל בפועל)
```

### שני שימושים — לא אחד

**1. UX — רינדור עקבי לפי סוג, לא לפי החלטת הסוכן:**
- `APPROVAL_PROMPT` → כותרת ברורה + טיימר גלוי גם בגלילה אחורה ("⏳ בתוקף 30 דק'")
- `SYSTEM_NOTIFICATION` → סימון נפרד מגוף שיחה ("🔔 התראת מערכת")
- `AGENT_REPLY` → ללא תיוג מיוחד, שיחה רגילה

**2. הזנה חזרה ל-`TurnEnvelope` — כדי שהסוכן יידע להתייחס נכון להיסטוריה:**
```python
@dataclass
class TurnEnvelope:
    pending_queues: list[PendingQueueAwareness]
    active_queue_id: Optional[str]
    capability: CapabilityScope
    last_outbound_kind: MessageKind        # ← חדש
```

כך אם המשתמש עונה על הודעה שסומנה `APPROVAL_PROMPT`, הסוכן יודע להתייחס אליה כ"מה שהמערכת שאלה", לא "מה שאני אמרתי" — בלי לבנות entity כבד: זה שדה אחד שמתווסף בזמן שליחת כל הודעה יוצאת, על ידי ה-adapter ששולח אותה ממילא.

---

## הפרדת שכבות (ללא שינוי מ-v1 — עדיין קריטי)

| שכבה | מדיניות fail | דוגמה |
|------|--------------|-------|
| **אבטחה** (LeadsWriteGate, trusted_source, tool_registry.enforce) | **Fail-closed**, בלתי תלויה ב-Coordinator | `forbidden_actions`/tool-call על partial selection נחסם ב-dispatcher, לא רק "מוזכר" בפרומפט |
| **אורקestרציה** (TurnCoordinator) | **Fail-open** ל-`free_agent` | כשל ב-identity resolution → לא לחסום, ליפול לברירת מחדל |

**הבהרה מפורשת (הייתה חסרה ב-v1):** `forbidden_actions` הוא **אזהרה בפרומפט בלבד** — הוא לא מנגנון אכיפה. האכיפה האמיתית תמיד ברמת `tool_registry.enforce()`/`dispatcher`, לפי ה-mode. אם הסוכן בכל זאת ינסה tool-call אסור, הקוד חוסם — לא הפרומפט.

---

## תפקידי הרכיבים — מניעת God Object

`TurnCoordinator` **לא** מנהל Leads, Contracts, Tasks או Messages בעצמו. אם הוא יתחיל לעשות זאת, הוא הופך ל-God Object חדש — בדיוק ההפך ממה שהמסמך הזה מנסה למנוע. תפקידו מוגבל במפורש:

```text
Agent            = מנסח ומציע
Approval Gateway = מחזיק ומבצע חוזים (ActionContract, PostgreSQL claim)
Capture flows    = מפענחים קלט ייעודי (leads, files, tasks)
Output Gateway   = שולח בפועל
TurnCoordinator  = בעל הבית של ה-turn בלבד:
                     - מי מטפל ב-turn
                     - איזה context הוא מקבל (TurnEnvelope)
                     - מה מותר לו לעשות (policy snapshot)
                     - מי מחזיר את התשובה היחידה (reply_owner)
```

`TurnCoordinator` **מחבר עובדות ומעניק בעלות על התור** — הוא לא מחליף אף רכיב קיים, ולא הופך להיות עוד מקום שמחזיק state עסקי.

---

## Agent Independence and Degraded Operations

**העיקרון:** הסוכן הוא ספק פרשנות אחד אפשרי — לא runtime המערכת עצמו.

```text
The agent may fail.
The business runtime must not fail with it.
```

זו יכולת של ה-`TurnCoordinator` לנהל **מצב תפעולי**, לא fallback פנימי נוסף בתוך הסוכן. ה-Coordinator כבר מחליט מי בעל התשובה ומהו המסלול הפעיל — לכן הוא המקום הטבעי להכריע גם כשאין סוכן זמין בכלל.

### שדה חדש: `AgentAvailability` — **מתוקן: מופרד מ-`TurnOutcome`**

**הבחנה שהייתה חסרה:** מצב שבו "אין סוכן זמין" (`AGENTLESS`) **אינו** אותו דבר כמו "המערכת כולה לא מסוגלת לטפל בבקשה" (`SYSTEM_UNAVAILABLE`). כשאין סוכן, המערכת עדיין פועלת במלואה במסלולים דטרמיניסטיים — זה לא כשל, זו מצב תפעולי לגיטימי. `UNAVAILABLE` שייך ל-**תוצאת התור** (האם הצלחנו לענות בכלל), לא ל-**זמינות הסוכן** כשלעצמה.

```python
class AgentAvailability(Enum):
    PRIMARY = "primary"    # הספק שנבחר לפי מדיניות הניתוב (default/escalation) עונה כמצופה
    FALLBACK = "fallback"  # מנגנון ההתאוששות מכשל נכנס — לא הספק שנבחר במקור
    AGENTLESS = "agentless"  # אין אף ספק זמין; המערכת ממשיכה לפעול דטרמיניסטית

@dataclass
class AgentAvailabilityStatus:
    mode: AgentAvailability
    active_provider_id: Optional[str]   # provider_id לוגי של מי שענה בפועל
    selection_reason: Optional[str]     # ← ראה §Model Provider Registry: "why", לא רק "who"

class TurnOutcome(Enum):             # ← נפרד לגמרי מ-AgentAvailability
    HANDLED = "handled"
    SYSTEM_UNAVAILABLE = "system_unavailable"   # לא הסוכן נכשל — אף מנגנון (גם לא דטרמיניסטי) לא הצליח

@dataclass
class TurnEnvelope:
    pending_queues: list[PendingQueueAwareness]
    active_queue_id: Optional[str]
    capability: CapabilityScope
    last_outbound_kind: Optional[MessageKind]
    reply_owner: Optional[str]
    agent_availability: AgentAvailabilityStatus
```

### `CapabilityAction` — **מתוקן: הפרדת עובדות-בסיס (config) מסטטוס נגזר (runtime)**

**הבעיה שתוקנה:** `requires_agent`/`available_in_agentless_mode`/`currently_available` כ-booleans עצמאיים יכולים לסתור זה את זה (למשל `requires_agent=True` וגם `available_in_agentless_mode=True` בו-זמנית — סתירה לוגית). הפתרון: מקור התצורה מחזיק **עובדת בסיס יחידה** (`execution_kind`), וכל שאר הסטטוס **נגזר בזמן אמת** מפונקציה אחת, לא ממוחזק כשדות עצמאיים.

```python
class ExecutionKind(Enum):
    CONVERSATIONAL = "conversational"        # יכולת שפה של הסוכן, לא דורש handler נפרד
    DETERMINISTIC = "deterministic"          # handler קבוע, לא תלוי סוכן בכלל
    AGENT_INTERPRETED = "agent_interpreted"  # דורש פרשנות טקסט חופשי — תלוי סוכן

@dataclass(frozen=True)
class CapabilityActionConfig:
    action_id: str
    category: str
    user_description: str
    execution_kind: ExecutionKind
    deterministic_handler: Optional[str]   # רלוונטי רק כש-execution_kind == DETERMINISTIC

@dataclass
class CapabilityAction:
    """Snapshot מחושב לכל turn — לא config סטטי שיכול להיסחף."""
    config: CapabilityActionConfig
    mode: CapabilityMode
    requires_approval: bool
    currently_available: bool
    available_in_agentless_mode: bool
    unavailable_reason: Optional[str]
    alternatives: list[str]

def resolve_capability_action(config: CapabilityActionConfig, ctx: RuntimeContext) -> CapabilityAction:
    """מקור יחיד לגזירת הסטטוס — health + policy + identity + handler availability + approval mode.
    available_in_agentless_mode := (execution_kind != AGENT_INTERPRETED) and currently_available.
    שני ה-booleans האלה אף פעם לא נכתבים ידנית במקור אחר."""
    ...
```

כך ה-Coordinator יודע להבחין: אישור/דחיית חוזה קיים, פתיחת מסך משימות, פקודה קשיחה מוכרת — `DETERMINISTIC`, עובדים גם ב-`AGENTLESS`. פירוק הודעה חופשית לכמה משימות — `AGENT_INTERPRETED`, לא זמין ב-`AGENTLESS`.

### סדר הניתוב

```text
1. האם יש reply_owner קיים? (approval / clarification / capture flow / deterministic handler)
   → אם כן, זה מטפל בתור, בלי צורך בסוכן כלל.
2. האם הבקשה ניתנת לטיפול בלי סוכן (execution_kind != AGENT_INTERPRETED)?
   → כן: מסלול דטרמיניסטי.
3. האם נדרש סוכן (AGENT_INTERPRETED)?
   → מדיניות ניתוב בוחרת default (Haiku) או escalation (Sonnet) מפורש —
     זו בחירת עלות/איכות, לא התאוששות מכשל.
   → אם הספק שנבחר נכשל בפועל (rate limit, timeout, שגיאת ספק) →
     fallback (מנגנון זמינות נפרד, לא "המודל הבא בתור איכות").
   → אם גם ה-fallback לא זמין: AGENTLESS.
```

**העיקרון המרכזי שהיה חסר:** Sonnet אינו "מודל הגיבוי" ל-Haiku. הוא **מודל הסלמה** שנבחר במפורש לפי מדיניות ניתוב (מורכבות הבקשה, בקשה מפורשת וכו') — עניין של עלות/איכות. Fallback הוא **מנגנון זמינות נפרד לחלוטין**, שנכנס רק כשהספק שכבר *נבחר* (בין אם default ובין אם escalation) נכשל בפועל. בלי ההפרדה הזו, `primary`/`secondary` עלול להתפרש כאילו "Sonnet נכנס כשHaiku נכשל" — וזה לא מה שקורה בפועל.

כשה-mode הוא `AGENTLESS`: **בקשות `AGENT_INTERPRETED` אינן מנוחשות או מבוצעות חלקית** — הן מקבלות תשובת degraded-mode מבוססת (`reply_owner = DEGRADED_SYSTEM`), כדי שהמערכת עצמה תחזיר תשובה אמינה, ולא שהסוכן ה"נופל" ינסה להסביר את התקלה של עצמו.

### Model Provider Registry — **מתוקן שוב: שלושה תפקידים שונים, לא שרשרת priority אחידה**

**תיקון קריטי על גבי התיקון הקודם:** שרשרת `priority` גנרית (`agent_primary → agent_fallback_fast → agent_fallback_low_cost`) עדיין מטעה, כי היא מתארת את שלושת הספקים כאילו הם דרגות של **אותו ציר** (עדיפות טכנית). בפועל יש אצל BOSS **מדיניות ניתוב היברידית** עם שלושה תפקידים שונים באופיים:

- **`default`** — Haiku, ברירת המחדל לרוב הבקשות.
- **`escalation`** — Sonnet, נבחר **במפורש** לפי מדיניות ניתוב (מורכבות/בקשה מפורשת) — **לא** fallback על כשל.
- **`fallback`** — ספק/מודל חלופי, נכנס **רק** כשהספק שכבר נבחר (בין אם `default` ובין אם `escalation`) נכשל בפועל.

```python
class ProviderRole(Enum):
    DEFAULT = "default"          # Haiku — ברירת מחדל
    ESCALATION = "escalation"    # Sonnet — נבחר במפורש, לא fallback
    FALLBACK = "fallback"        # מנגנון התאוששות מכשל, נפרד לגמרי

@dataclass(frozen=True)
class ModelProviderConfig:
    provider_id: str
    vendor: str
    model_string: str
    role: ProviderRole
    priority: int       # רלוונטי בתוך אותו role בלבד (למשל כמה fallbacks); לא חוצה roles
    enabled: bool

@dataclass(frozen=True)
class ModelProviderRegistry:
    providers: list[ModelProviderConfig]

    def by_role(self, role: ProviderRole) -> list[ModelProviderConfig]:
        return sorted([p for p in self.providers if p.enabled and p.role == role], key=lambda p: p.priority)

def load_model_registry(env: Mapping[str, str]) -> ModelProviderRegistry:
    """נקרא ב-startup בלבד. חוסר משתנה לתפקיד לא-קריטי לא מפיל את ה-import."""
    providers = []
    if env.get("AGENT_MODEL_DEFAULT"):
        providers.append(ModelProviderConfig("agent_default", "anthropic", env["AGENT_MODEL_DEFAULT"], role=ProviderRole.DEFAULT, priority=0, enabled=True))
    if env.get("AGENT_MODEL_ESCALATION"):
        providers.append(ModelProviderConfig("agent_escalation", "anthropic", env["AGENT_MODEL_ESCALATION"], role=ProviderRole.ESCALATION, priority=0, enabled=True))
    if env.get("AGENT_MODEL_FALLBACK"):
        providers.append(ModelProviderConfig("agent_fallback", "anthropic", env["AGENT_MODEL_FALLBACK"], role=ProviderRole.FALLBACK, priority=0, enabled=True))
    return ModelProviderRegistry(providers=providers)

def validate_registry_at_startup(registry: ModelProviderRegistry) -> None:
    """מתעד בלבד — לא מפיל את השירות. חוסר ב-DEFAULT הוא הקריטי ביותר לתיעוד."""
    if not registry.by_role(ProviderRole.DEFAULT):
        log.critical("No default agent model configured — system may run AGENTLESS for routine requests.")

def resolve_model_string(registry: ModelProviderRegistry, provider_id: str) -> str:
    """המקום היחיד בכל הקוד שממיר provider_id → model_string בפועל."""
    entry = next(p for p in registry.providers if p.provider_id == provider_id)
    if not entry.enabled:
        raise ProviderUnavailable(provider_id)
    return entry.model_string

def select_provider(registry: ModelProviderRegistry, escalation_requested: bool) -> tuple[ModelProviderConfig, str]:
    """מחזיר (ספק, selection_reason). Escalation היא בחירת מדיניות, לא תוצאה של כשל."""
    role = ProviderRole.ESCALATION if escalation_requested else ProviderRole.DEFAULT
    candidates = registry.by_role(role)
    if candidates:
        reason = "explicit_escalation" if escalation_requested else "default_route"
        return candidates[0], reason
    # הספק המבוקש לפי מדיניות לא זמין בכלל (לא כשל בזמן קריאה, אלא חסר בתצורה)
    fallback = registry.by_role(ProviderRole.FALLBACK)
    if fallback:
        return fallback[0], "config_missing_fallback"
    raise NoAvailableProvider()
```

**כשל בפועל בזמן קריאה (rate limit / timeout / שגיאת ספק) לעומת חוסר בתצורה:** שני מקרים שונים, אבל שניהם מובילים ל-`fallback` אם קיים:
```text
selection_reason = "default_route"           → Haiku נבחר, בקשה רגילה
selection_reason = "explicit_escalation"     → Sonnet נבחר, מדיניות ניתוב הכריעה שנדרשת הסלמה
selection_reason = "primary_failure"         → הספק שנבחר (default או escalation) נכשל בזמן קריאה, fallback נכנס
selection_reason = "rate_limit_fallback"     → מקרה פרטי של primary_failure, שימושי לסנן ב-telemetry
```

`AgentAvailabilityStatus.selection_reason` מחזיק אחד מהערכים האלה — לא רק "מי ענה", אלא **למה** נבחר. זה קריטי כדי להבדיל תקלה אמיתית (`primary_failure`/`rate_limit_fallback`) מבחירת מדיניות תקינה (`default_route`/`explicit_escalation`).

**תיקון 3 — הפרדת telemetry מ-user-facing, לא הסתרה גורפת:** גרסת המודל **כן** צריכה להופיע איפשהו — אחרת קשה לאבחן incident שנגרם משדרוג מודל. ההפרדה הנכונה:

```text
TurnEnvelope         → provider_id לוגי + selection_reason בלבד (agent_availability.active_provider_id/.selection_reason)
Operational telemetry → provider_id + resolve_model_string(provider_id) (המחרוזת בפועל) + selection_reason
User-facing output    → ללא שם מודל בכלל, ללא selection_reason גולמי
```

**DoD מדויק יותר (לא grep גורף):**
```text
אין model string גולמי ב-runtime call sites מחוץ ל-registry/config.
מותר בתיעוד, fixtures, migration tests ו-telemetry assertions.
```

### הכנה למולטי-אייג'נט עתידי (שם ומבנה בלבד — לא ממומש עכשיו)

**היום יש רק תפקיד סוכן אחד** ("עוזר דיגיטלי כללי"). אבל אם בעתיד יתווספו סוכנים מתמחים (לדוגמה: agent לאיכלוס לידים, agent לתזמון) — עדיף לקבוע כבר עכשיו שמות/מבנה שלא ידרשו rename מאוחר יותר, בלי לממש את הלוגיקה בפועל:

```python
@dataclass(frozen=True)
class AgentRoleConfig:
    role_id: str                        # "general_assistant" — יחיד היום
    registry: ModelProviderRegistry     # default/escalation/fallback ספציפי לתפקיד הזה
    capability_scope_ref: str           # איזה subset של CapabilityScope רלוונטי לתפקיד
```

`reply_owner` שהוא agent-owned יכול בעתיד להיות `f"agent:{role_id}"` במקום `"agent"` גנרי, בלי לשבור את ההנחה של היום (`role_id` תמיד `"general_assistant"`). **לא בונים את זה עכשיו** — ראה טבלת "ישויות עתידיות שנדחו במודע" למטה.

### מה לא להכניס ל-Coordinator (חשוב לא פחות ממה שכן)

```text
❌ קריאות ישירות ל-Anthropic/OpenAI API
❌ retry logic מפורט
❌ מימוש כל handler
❌ ביצוע כלים בעצמו
```

אלה נשארים ברכיבים נפרדים: `AgentRuntime`, `CapabilityRegistry`, `DeterministicHandlers`, `ActionGateway`. **ה-Coordinator רק מקבל מהם מצב ומחליט מי רשאי לענות** — לא מממש בעצמו אף אחד מהם.

### מיקום בשלבים — **מתוקן: מאוחד עם מסלול ההטמעה הראשי, לא מספור מקביל**

Degraded Operations **אינו** מסלול Phase 0-3 נפרד — הוא משולב בתוך אותם Phase 0-5 של ההצעה הראשית (ראה §מסלול הטמעה למטה, המעודכן).



## מה זה לא (מוכלל מ-v1)

```
❌ לא rewrite של agent/approval/gateway הקיימים
❌ לא rules-engine נוקשה עם template responses
❌ לא הזרקת רשימת באגים היסטוריים לפרומפט
❌ לא dump מלא של tool registry — קטגוריות בלבד
❌ לא "capability mode" נפרד — capability הוא תמיד-נוכח, לא mode
❌ לא whitelist/blacklist כמנגנון אכיפה — הוא אזהרה; האכיפה מבנית
❌ לא God Object — Coordinator מחליט mode + envelope בלבד, לא תוכן התשובה
❌ לא שם מודל גולמי בשום מקום מלבד Model Provider Registry
❌ לא retry/קריאות API ישירות בתוך ה-Coordinator עצמו
```

---

## מסלול הטמעה מוצע (מתוקן — 6 שלבים)

```
Phase 0 — מיפוי ואבחון בלבד. TurnEnvelope (pending_queues + capability + reply_owner +
          agent_availability) נבנה בכל turn, log-only מובנה (turn_mode, queue_count,
          queue_sources, active_queue_id, resolved_reference, reply_owner, message_kind,
          policy_snapshot_version, agent_availability_mode). כולל מיפוי אילו
          CapabilityAction הן execution_kind == AGENT_INTERPRETED (תלויות סוכן) מול
          DETERMINISTIC/CONVERSATIONAL (לא תלויות). בלי שינוי UX, בלי הזרקה לפרומפט עדיין.
Phase 1 — הזרקת capability תמיד; הזרקת pending_queues + active_queue_id כש-mode != free_agent.
          Coordinator מזהה reply_owner דטרמיניסטי **לפני** שהוא פונה לסוכן כלל (§סדר
          הניתוב); תשובת AGENTLESS מבוססת (לא מנוחשת) לבקשות AGENT_INTERPRETED כשאין
          ספק זמין. TurnStateProjection (§Persistence) נכנס **רק אם** Phase 0 מוכיח
          שצריך אותו. עדיין לא חוסמים tool-calls. "שמור 3" כבר מקבל כאן תשובה מודעת נכונה.
Phase 2 — resolve_numbered_reference() לפני הרצת הסוכן; התוצאה היא ResolvedReference
          (עובדה), לא ביצוע. features מפסיקים לפרש מספרים בעצמם בהדרגה. במקביל: חיבור
          AgentRuntime ל-Model Provider Registry בפועל (default/escalation/fallback,
          §Model Provider Registry); telemetry על selection_reason פעיל.
Phase 3 — Reply ownership: reply_owner נקבע לכל turn; רק הבעלים מחזיר טקסט למשתמש,
          כולל `DEGRADED_SYSTEM` כ-reply_owner תקף כשה-agent_availability הוא AGENTLESS.
          רכיבים אחרים מחזירים facts/state changes/action results/suggested message
          kind, לא שולחים בעצמם. **דחיפות מוגברת:** יש כבר incident מתועד (approval
          prompt מול fallback סותר, הודעת הצלחה כפולה, Agent שהמשיך לדבר בזמן
          שה-Gateway כבר החזיק את התור) — זו לא הגנה תיאורטית, הקריטריון כבר התקיים.
Phase 4 — MessageKind: כל outbound מתויג (אישור/הבהרה/הודעת מערכת/גבול יכולת/שגיאה
          אמיתית/AGENTLESS-degraded), ה-adapter מרנדר את הסוג באופן עקבי.
Phase 5 — Commitment Grounding: log-only תחילה — האם הסוכן הבטיח משהו בלי
          ActionRecord תואם? רק אחרי נתונים אמיתיים מחליטים מה לחסום.
```

### Persistence — תיקון: אין צורך ב-Postgres חדש ב-Phase 0

**תיקון עובדתי:** נבדק בפועל מול Render dashboard — Manual Scaling = 1, Total Instances שטוח על 1 לאורך 48 שעות. BOSS רץ כיום **single-instance**, לא multi-instance כפי שנטען קודם בטעות.

זה משנה את החלטת ההטמעה, אבל **לא** בגלל single-instance כשלעצמו — אלא בגלל עיקרון עמוק יותר: תשתית ה-Postgres atomic claims ב-4B0.1/4B2 נבנתה מראש לקראת multi-instance עתידי, וזה מוצדק **שם** כי זו תשתית ליבה לכתיבות עסקיות (Leads/Approvals), שבה מחיר "לתקן אחר כך" הוא migration בפרודקשן חיה.

**TurnCoordinator שונה מהותית:** הוא אינו תשתית עצמאית, אלא **שכבת אורקestרציה מעל תשתית קיימת**. לכן:

- לא בונה Postgres row + optimistic locking משלו ב-Phase 0.
- `TurnEnvelope` הוא **snapshot נגזר** בכל turn מהמקורות הקיימים (ActionContracts הקנוני, pending batch state קיים, EventBus/state קיים כל עוד הוא חי, metadata של ההודעה האחרונה) — **ולא נשמר כמקור אמת עצמאי**.
- כש-4B0.1C יגמר (ActionGateway מחובר ל-atomic claims באופן מלא) — TurnCoordinator קורא מה-`ActionContract` הקנוני שכבר ב-Postgres, **לא משכפל persistence משלו**.

**העיקרון:** לא כל רכיב בונה persistence "ליתר ביטחון". מקור אמת אחד (`ActionContracts` ב-Postgres), ורכיבים אחרים (TurnCoordinator) נשענים עליו לקריאה. כשהמערכת בפועל תעבור ל-multi-instance, יש להעביר את ה-pending state הלא-עמיד למקור קנוני — אבל אין סיבה להקדים בניית טבלה נוספת רק בשביל ה-Coordinator לפני שהוכח שצריך.

### סתירה שתוקנה: ConversationState נדחה, אבל persistence עדיין נדרש — `TurnStateProjection`

**הסתירה שהתגלתה:** סעיף אחד קבע ש-pending state צריך persistence עמיד (Postgres) כבר מוקדם; סעיף אחר (§ישויות עתידיות שנדחו במודע) דוחה `ConversationState` כטבלה עצמאית. שני הדברים נכונים בו-זמנית **רק** אם מבחינים בין שתי שאלות שונות: **"האם זה מקור אמת?"** לעומת **"האם זה עמיד ל-restart?"**

```python
@dataclass
class TurnStateProjection:
    """
    Cache/projection נגזר — לא מקור אמת עצמאי.
    נכתב ל-Postgres כדי לשרוד restart של תהליך יחיד (RAM נמחק בכל restart,
    גם ב-single-instance), אבל נבנה מחדש בכל רגע מהמקורות האמיתיים אם אבד.
    """
    projection_id: str
    derived_from: list[str]        # ["action_contracts", "event_bus", "lead_batch_state", ...]
    ttl_seconds: int
    version: int                   # עולה בכל שכתוב; לא optimistic locking עסקי, רק staleness check
    rebuildable: bool = True       # אם True — אובדן הרשומה אינו incident, רק re-compute
```

**ההבחנה המכרעת:**
- **`ConversationState` (נדחה):** היה אמור להיות **מקור אמת חדש** — כלומר אם הוא ו-`ActionContracts` לא מסכימים, מישהו צריך להכריע מי צודק. זה בדיוק ה-fragmentation.
- **`TurnStateProjection` (מוצג עכשיו):** הוא **תוצר נגזר בלבד** — אם הוא אבד/התיישן, בונים אותו מחדש מה-`ActionContracts`/`EventBus`/batch state האמיתיים, ואף אחד לא "מכריע" נגדם. `rebuildable=True` הוא לא detail טכני, הוא ההבטחה שמונעת מזה להפוך למקור אמת רביעי בטעות.

**מסקנה:** `TurnStateProjection` יכול להיכנס בלי לסתור את העיקרון "אין מקור אמת חדש" — כי הוא לא אחד. אבל **אין להתחייב לו מראש**:

```text
Phase 1 may introduce a rebuildable TurnStateProjection only if Phase 0
demonstrates that required turn context cannot be reconstructed reliably
or cheaply from canonical sources after restart.
```

כלומר לא קובעים כבר עכשיו שחייבים cache ב-Postgres — קודם מודדים ב-Phase 0 (log-only) האם הקריאה החוזרת מ-`ActionContracts`/`EventBus`/batch state מספיקה בפועל. רק אם המדידה מראה אובדן context אמיתי או עלות גבוהה מדי — נכנסים ל-`TurnStateProjection`, לא לפני.

---

## ישויות עתידיות שנדחו במודע — לא נשכחות, רק לא עכשיו

הישויות הבאות עלו בדיון המקורי ונדחו בכוונה מ-v2, כדי לא לבנות "בעל בית" נתונים רביעי לפני שהוכח שצריך אותו. הן מתועדות כאן במפורש כדי שנדע לחזור אליהן, לא כדי שיישכחו.

| ישות | למה נדחתה מ-v2 | מתי לחזור אליה | מה יגדיר "עכשיו כן צריך" |
|---|---|---|---|
| **`ConversationState` כמקור אמת עצמאי** (טבלה עם `current_phase`, `active_pending_contract_id` שמכריעה מול `ActionContracts`) | יוצרת מקור state רביעי, נוסף על ActionGateway/`_pending_approvals`/EventBus — בדיוק ה-fragmentation שרצינו לתקן | **נפתר עקרונית — ראה §TurnStateProjection.** אבל `TurnStateProjection` עצמו **לא** נכנס אוטומטית ב-Phase 1 — רק אם מדידת Phase 0 (log-only) מוכיחה שקריאה חוזרת מ-`ActionContracts`/מקורות קיימים לא מספיקה | תוצאות Phase 0 מראות אובדן context אמיתי אחרי restart, לא הנחה מראש |
| **Turn Entity** (audit log לכל הודעה נכנסת/יוצאת, `turn_id`, `phase_before/after`) | לא נדרש כדי לתקן את הבאג הנוכחי; רק "נחמד לדיבוג" | כשיתעורר צורך אמיתי ב-audit trail — חקירת incident, דרישת compliance, או ניתוח דפוסי כשל חוזרים | דרישת audit קונקרטית מגיעה בפועל, לא "כדאי שיהיה" |
| **Turn Reply Bottleneck המלא** (טרנזקציה אטומית: turn+state+outbound יחד) | **הקריטריון כבר התקיים בפועל** — incident מתועד: approval prompt מול fallback סותר, הודעת הצלחה כפולה, וה-Agent המשיך לדבר בזמן שה-Gateway כבר החזיק את התור. **המסקנה השתנתה:** Reply Ownership הבסיסי (Phase 3, `reply_owner` יחיד לכל turn) הופך לדחוף עכשיו, לא רק ל"ברירת מחדל עתידית" | ה-**גרסה המלאה בלבד** (טרנזקציה אטומית inbound+state+outbound יחד) עדיין נדחית — היא פותרת דרישת atomicity שלא הוכחה, בעוד ה-incident המתועד דורש רק נקודת החלטה יחידה, לא טרנזקציה מלאה | אם יתגלה מקרה שגם Reply Ownership הבסיסי (נקודת החלטה יחידה) לא מספיק — למשל race אמיתי בין שני threads על אותו turn |
| **`superseded_by_presentation_id` / `render_version`** (מ-SPEC 4C, Presentation Projection) | לא נדרש לפתיחת 4C-1; שדות עתידיים מוגדרים אך לא ממומשים | כש-voice-edit / supersession מגיע לתור (מחוץ ל-4C-1) | תלוי בלוח הזמנים של 4C-4 ומעלה, לא ב-Turn Coordinator |

**הכלל המנחה לכל השורות הטבלה:** דחייה על בסיס "אין הוכחה שצריך עכשיו", לא על בסיס "לא חשוב". כל שורה כאן היא תזכורת מכוונת לחזור ולבדוק, לא מחיקה של הרעיון.

---

## Definition of Done (מוכלל, מתוקן, מחולק ל-3 Gates)

**למה לחלק:** ה-DoD הכולל גדול מספיק כדי להיראות כפרויקט שלם. פיצול ל-3 gates עצמאיים מונע מצב שבו מכריזים "TurnCoordinator נכשל" רק כי, למשל, Commitment Grounding של Phase 5 עדיין לא הושלם — כל gate נסגר ומאושר בנפרד.

### Gate A — Phase 0: תצפית בלבד, אין שינוי התנהגות

- [ ] `pending_summary`/`capability.domain_description`/`available_categories` הם תמיד תוצר template דטרמיניסטי, לעולם לא קריאת LLM
- [ ] `LeadsWriteGate`/`trusted_source` נשארים fail-closed, בלתי תלויים ב-Coordinator
- [ ] regression: PR-0 (mode 1/2), BUG-091, BUG-090 לא נשברים
- [ ] אין בניית `ConversationState`/Postgres חדש ב-Phase 0; `TurnEnvelope` הוא snapshot נגזר מ-`ActionContracts` הקנוני ומקורות קיימים, לא מקור אמת עצמאי — נבדק שאין טבלה חדשה נוצרת בשלב זה
- [ ] `TurnStateProjection` **לא** נבנה אוטומטית — רק אם log-only של Phase 0 מוכיח בפועל שקריאה חוזרת מ-`ActionContracts`/מקורות קיימים אינה מספיקה (costly/unreliable); אם נבנה, מוגדר כ-`rebuildable=True` ונבדק שמחיקת הרשומה לא גורמת לאובדן מידע
- [ ] מתועד באופן חד-משמעי: `TurnStateProjection` הוא cache, `ActionContracts` הוא מקור האמת — אין בדיקת קוד או decision path שמכריעה נגד `ActionContracts` על בסיס `TurnStateProjection`
- [ ] טבלת "ישויות עתידיות שנדחו במודע" נשארת בקובץ ומתעדכנת בכל פעם שנבדקת מחדש (גם אם ההחלטה היא "עדיין לא")
- [ ] `resolve_model_string(registry, provider_id)` הוא נקודת הכניסה היחידה להמרת provider_id→model string; חיפוש קוד (`grep`) לא מוצא model string גולמי ב-runtime call sites מחוץ ל-registry/config (מותר בתיעוד, fixtures, migration tests, telemetry assertions)
- [ ] שדרוג מודל (שינוי `AGENT_MODEL_DEFAULT`/`AGENT_MODEL_ESCALATION`/`AGENT_MODEL_FALLBACK`) לא דורש שינוי קוד באף קובץ מלבד קובץ ה-config/registry עצמו — נבדק ב-test ייעודי
- [ ] `AgentAvailabilityStatus.active_provider_id`/`selection_reason` מכילים ערכים לוגיים בלבד — לא מחרוזת מודל גולמית — גם ב-`TurnEnvelope` וגם ב-user-facing output; המחרוזת הגולמית מופיעה רק ב-operational telemetry
- [ ] `TurnCoordinator` אינו מכיל קריאות API ישירות/retry logic/מימוש handler — נבדק בסקירת קוד שכל אלה נשארים ב-`AgentRuntime`/`DeterministicHandlers`/`ActionGateway` בלבד

### Gate B — Pending / Capability / Agentless Routing

- [ ] `TurnEnvelope.capability` מוזרק בכל turn, בכל mode, כולל `free_agent`
- [ ] `TurnEnvelope.pending_queues` (רשימה, לא יחיד) מלא (index→id→label) בכל queue פעיל, בכל תחום (leads/tasks/files/disambiguation) — לא רק batch לידים
- [ ] `active_queue_id` נבחר לפי מדיניות עדיפות מתועדת (תשובה מפורשת → reconfirmation → disambiguation → approval → capture → free agent), לא לפי סדר query מקרי
- [ ] regression: שני queues פעילים בו-זמנית (למשל batch לידים + follow-up נפרד) — המערכת בוחרת `active_queue_id` נכון ולא מערבבת ביניהם
- [ ] `resolve_numbered_reference()` הוא המימוש היחיד לפענוח "מספר N" בכל הקוד, פועל בתוך `active_queue_id`; אין מימוש כפול per-feature
- [ ] מקרה A (batch לידים, "שמור 3") נפתר ב-turn אחד, לא שניים — נבדק כ-regression test מפורש
- [ ] מקרה B (בקשת קפה) ממשיך לעבוד זהה — regression test שמוודא capability-mismatch עדיין מקבל חלופות קונקרטיות, לא נשבר ע"י המיזוג
- [ ] אין `CapabilityAction` שמוצג רק כ-"available" בלי לציין את `mode` המדויק (ניסוח ישיר / קריאה / הצעת פעולה / ביצוע לאחר אישור / לא זמין)
- [ ] הסוכן אינו אומר "אני יכול לשלוח/ליצור/לעדכן" כאשר בפועל הוא רשאי רק ליצור `ActionContract` שממתין לאישור — regression test מפורש
- [ ] ניסוח תוכן בשיחה מובחן במפורש מיצירת אובייקט חיצוני באמצעות שמות שונים (`email_text_draft` ≠ `gmail_saved_draft`), לא אותה מילה לשני דברים
- [ ] `CapabilityScope`/`CapabilityAction.currently_available` נגזר גם מ-tool registry וגם ממדיניות האישור והמצב הנוכחי — קיום tool ברג'יסטרי לבדו אינו הופך פעולה ל"זמינה"
- [ ] regression מלא: "נסח לי מייל" → `RESPOND_DIRECTLY` ללא approval; "שמור כטיוטה ב-Gmail" → `PROPOSE_ACTION`/`EXECUTE_AFTER_APPROVAL`; "שלח את המייל" → מסלול ביצוע מאושר בלבד; tool חסר/לא תקין → הסבר מגבלה + חלופה, בלי הבטחה
- [ ] `forbidden_actions`/`restricted_categories` **נגזרים בזמן אמת מאותו policy evaluator** ש-`dispatcher` מריץ בפועל — לא מתוחזקים ידנית בנפרד ב-Coordinator; test מאמת שאין drift בין השניים
- [ ] Coordinator fail-open ל-`free_agent` בכל כשל טכני (identity resolution, envelope build failure וכו')
- [ ] `AgentAvailabilityStatus` מוזרק ב-`TurnEnvelope` בכל turn; `AGENTLESS` מזוהה נכון כשאין אף ספק זמין (`DEFAULT`/`ESCALATION`/`FALLBACK` כולם לא זמינים)
- [ ] מסלולים דטרמיניסטיים (אישור/דחיית חוזה, פתיחת מסך משימות, פקודה קשיחה מוכרת) ממשיכים לעבוד תחת `AGENTLESS` — regression מפורש לכל אחד
- [ ] בקשות `AGENT_INTERPRETED` חדשות תחת `AGENTLESS` **לא** מנוחשות/מבוצעות חלקית — מקבלות תשובת degraded-mode מבוססת בלבד
- [ ] regression מפורש לארבעת מסלולי הניתוב: בקשה רגילה → `default_route` (Haiku); בקשת הסלמה מפורשת → `explicit_escalation` (Sonnet); כשל Haiku בבקשה רגילה → `fallback`, **לא בהכרח Sonnet**; כשל Sonnet לאחר הסלמה → `fallback` לפי מדיניות, לא ריצה חוזרת על Haiku
- [ ] test מוודא ש-`ProviderRole.ESCALATION` לעולם לא נבחר כתוצאה מכשל של `DEFAULT` — רק `explicit_escalation`/מדיניות מפורשת מפעילה אותו; כשל מוביל אך ורק ל-`ProviderRole.FALLBACK`

### Gate C — Reply Ownership / MessageKind / Commitment Grounding

- [ ] כל הודעה יוצאת מתויגת ב-`message_kind` (לא רק חלק מהערוצים) — נאכף ברמת ה-adapter המשותף, לא per-feature
- [ ] `CLARIFICATION_REQUEST` מובחן במפורש מ-`SYSTEM_ERROR`; regression test: "ביקשת 4 אבל זיהיתי 5" → `CLARIFICATION_REQUEST`, "נכשלה טעינת state" → `SYSTEM_ERROR`
- [ ] `TurnEnvelope.last_outbound_kind` מוזרק בכל turn; הסוכן לא מתייחס להודעת `SYSTEM_NOTIFICATION`/`APPROVAL_PROMPT` קודמת כאילו הוא עצמו אמר אותה
- [ ] UX: `APPROVAL_PROMPT` ו-`SYSTEM_NOTIFICATION` מרונדרים באופן ויזואלי עקבי ושונה מ-`AGENT_REPLY`, כולל בגלילה אחורה בהיסטוריה
- [ ] Reply Ownership (Phase 3) מתועד עם reference ל-incident הממשי (approval prompt/fallback סותר, הודעת הצלחה כפולה) — לא רק כהגנה תיאורטית; מקדם את סדר העדיפויות בפועל, לא רק "כברירת מחדל"
- [ ] regression: תרחיש ה-incident המתועד (approval prompt במקביל ל-fallback) לא חוזר לאחר Phase 3
- [ ] בעת `AGENTLESS`: reply_owner = `DEGRADED_SYSTEM`, לא הסוכן עצמו — regression test שמוודא שאין ניסיון של הסוכן "להסביר" את התקלה של עצמו
- [ ] `validate_agent_output()` רץ log-only ב-Phase 0/5, לפני שנהפך לחוסם — כדי למדוד שכיחות בפועל
- [ ] regression: "אני אגיד ל-X שיחזור אליך" בלי Task/tool_result תואם → מזוהה כהתחייבות ללא כיסוי
- [ ] מאומת במפורש: Reply Ownership (Phase 3) ו-Commitment Grounding (Phase 5) הם שני מנגנונים נפרדים — סגירת Phase 3 לא נחשבת כפתרון להצהרות ללא כיסוי
- [ ] הצעה מותנית ("אני יכול ל...") לעולם לא נחסמת ע"י ה-validator — רק ניסוח כעובדה מושלמת בלי רשומה תואמת
