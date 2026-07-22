# TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md

**סטטוס:** CONTRACT FREEZE — חוסם תחילת Shadow Decision עד לאישור
**תנאי מוקדם:** תשתית Phase 0 (Observation Only) כבר קיימת בפועל — `TurnEnvelope`, pending queues, `active_queue_id`, `reply_owner` כתצפית, execution-kind classification, agent availability placeholder, logging של ownership signals. מסמך זה **אינו מחליף** אותה — הוא קובע את מה שחסר בה: חוזה ההחלטה, מטריצת הקדימות, טיפוסי תוצאה, בידוד turn, וסמנטיקת כשל.

**לא בסקופ של מסמך זה:**
- מיקום האחסון (storage) של ה-resource claim חוצה-processes (§4ב/§7 — מסומן פתוח במפורש, לא חוסם תחילת Shadow אך כן חוסם טענה ש-"TurnCoordinator סגור")
- מיזוג PR #445 לתוך `lead_candidate_handler` — נדחה במפורש בצורתו הנוכחית; חלקים שנשמרים ממנו מפורטים ב-§0.1

## 0.1 מה נשמר מ-#445 (לא נמזג, אבל לא נזרק)

- בדיקות ה-intent (regression tests)
- דוגמאות ה-production שנאספו
- הרחבת זיהוי `UPDATE_LEAD`
- בדיקות ההגנה של BUG-094

ההכרעה `create`/`update` ו-`name-only resolution` **עוברות לפרוסת ה-Coordinator** (§3, §5) — לא נשארות בתוך `lead_candidate_handler`.

---

## 1. Inputs ל-Coordinator

```python
@dataclass(frozen=True)
class TurnInput:
    turn_id: str                       # ייחודי לכל הודעה נכנסת, נוצר ב-ingress
    user_id: str
    channel: str                        # telegram | whatsapp | tma
    raw_text: Optional[str]
    signals: TurnSignals                # עובדות שסופקו ע"י רכיבים קיימים; Coordinator לא גוזר אותן מחדש


class SignalClassification(Enum):
    EXPLICIT  = "explicit"   # מבוסס כלל/pattern מפורש שמזהה כוונה עסקית ישירות (למשל regex UPDATE_LEAD)
    HEURISTIC = "heuristic"  # מבוסס זיהוי תבנית כללית (למשל "יש כאן שם+טלפון") ללא כוונה עסקית מוצהרת


@dataclass(frozen=True)
class IntentSignal:
    """
    מחליף Optional[Intent] גולמי. ה-wrapper עצמו תמיד קיים (לא Optional) —
    גם כשלא זוהתה כוונה, ה-Coordinator מקבל אובייקט טיפוסי עם intent=None,
    לא היעדר-אובייקט. כך confidence/source/classification/evidence_span
    זמינים תמיד לצורך logging ו-disagreement analysis (§8).
    """
    intent: Optional[Intent]                    # None אם לא זוהתה כוונה עסקית
    confidence: float                            # 0.0–1.0, כפי שחושב ע"י intent_router
    source: str                                  # "intent_router" | "ingress_classifier" | ...
    classification: SignalClassification
    evidence_span: Optional[tuple[int, int]]     # אופסטים ב-raw_text שהניבו את ההתאמה; None אם לא רלוונטי


@dataclass(frozen=True)
class CaptureSignal:
    """
    מחליף Optional[CaptureCandidate] גולמי — אותו עיקרון כמו IntentSignal.
    capture הוא כמעט תמיד HEURISTIC (זיהוי תבנית טלפון/שם), לא EXPLICIT.
    """
    candidate: Optional[CaptureCandidate]        # None אם לא זוהה payload לשליפה
    confidence: float
    source: str                                  # "lead_candidate_handler" | ...
    classification: SignalClassification
    evidence_span: Optional[tuple[int, int]]


@dataclass(frozen=True)
class PendingReplySignal:
    """
    הוכחה — לא הנחה — שההודעה הנוכחית מתייחסת ל-active_queue_id ספציפי.
    §3 כלל 1 דורש signal זה (לא רק "יש pending queue כלשהו כלשהו ברקע")
    לפני שההודעה מטופלת כתשובה לתור ממתין. queue_id=None משמעו במפורש
    "אין ראיה שזו תשובה לתור קיים", גם אם pending_queues אינו ריק.
    """
    queue_id: Optional[str]                      # ה-active_queue_id שההודעה כנראה עונה לו
    match_basis: Optional[Literal[
        "callback_correlation",       # callback עם payload/token שמצביע במפורש על אותו queue_id
        "expected_reply_shape_match", # תשובה תואמת את הצורה שה-queue מצפה לה (למשל שם יחיד אחרי בקשת-הבהרה)
        "explicit_confirmation_word", # "כן"/"לא"/"מאשר" וכו', כשיש queue אחד פעיל וחד-משמעי
    ]]
    confidence: float


@dataclass(frozen=True)
class TurnSignals:
    intent_signal: IntentSignal
    capture_signal: CaptureSignal
    pending_reply_signal: PendingReplySignal      # תמיד קיים; ראה PendingReplySignal לעיל
    pending_queues: list[PendingQueueAwareness]
    capability: CapabilityScope
    agent_availability: AgentAvailabilityStatus
    last_outbound_kind: Optional[MessageKind]
```

**כלל:** ה-Coordinator צורך signals — הוא **לא** מפרש מחדש `raw_text` כדי לגזור intent/capture/pending-reference בעצמו. זה נשאר ברכיבים שכבר עושים את זה (router, capture flow, ingress adapters). תפקידו היחיד הוא הכרעה בין signals סותרים, על בסיס signals טיפוסיים — לא ניחוש חוזר על הטקסט הגולמי.

## 2. חוזה הפלט — `TurnDecision` (קנוני)

```python
class HandlerId(Enum):
    CAPTURE_FLOW                 = "capture_flow"
    PENDING_APPROVAL             = "pending_approval"
    AGENT                        = "agent"
    DETERMINISTIC_SHOW_LAST_TASK = "deterministic:show_last_task"
    # הרשימה המלאה מוגדרת/מורחבת במימוש — אבל תמיד כערך HandlerId סגור,
    # לעולם לא string חופשי בזמן ריצה.


class ReplyOwnerKind(Enum):
    AGENT            = "agent"
    CAPTURE_FLOW     = "capture_flow"
    PENDING_APPROVAL = "pending_approval"
    DETERMINISTIC    = "deterministic"
    DEGRADED_SYSTEM  = "degraded_system"   # AGENTLESS מצב, ראה PROPOSAL_V2 §agent_availability


@dataclass(frozen=True)
class ReplyOwner:
    kind: ReplyOwnerKind
    qualifier: Optional[str] = None    # למשל role_id עתידי ("agent:general_assistant") — לא בשימוש היום, ראה PROPOSAL_V2


class DecisionReason(Enum):
    EXPLICIT_INTENT_PRECEDENCE = "explicit_intent_precedence"
    PENDING_QUEUE_ACTIVE       = "pending_queue_active"
    NO_CONFLICT                = "no_conflict"
    NO_BACKING_QUEUE           = "no_backing_queue"    # ראה §7, תרחיש 11/23 — phantom approval
    ALREADY_CLAIMED            = "already_claimed"      # ראה §4ב
    # הרשימה סגורה — מורחבת רק דרך שינוי-חוזה מפורש (bump ל-contract_version),
    # לא string חופשי בזמן ריצה.


class ExecutionKind(Enum):
    CONVERSATIONAL    = "conversational"
    DETERMINISTIC     = "deterministic"
    AGENT_INTERPRETED = "agent_interpreted"


class PayloadKind(Enum):
    CAPTURE_CANDIDATE  = "capture_candidate"
    RESOLUTION_REQUEST = "resolution_request"
    APPROVAL_REFERENCE = "approval_reference"
    # מורחב רק דרך שינוי-חוזה מפורש, כמו HandlerId/DecisionReason.


@dataclass(frozen=True)
class TurnPayload:
    """
    עוטף את המידע שמועבר ל-selected_handler. `data` נשאר אטום מבחינת
    ה-Coordinator (הוא לא פותח/מפרש אותו) — אבל `kind` טיפוסי, לא dict
    גולמי חסר-תווית, כדי ש-mismatch בין Coordinator ל-handler ייתפס
    כשגיאת-טיפוס, לא כ-KeyError ב-runtime עמוק בתוך ה-handler.
    """
    kind: PayloadKind
    data: dict


@dataclass(frozen=True)
class TurnDecision:
    turn_id: str
    selected_handler: HandlerId
    reply_owner: ReplyOwner              # יחיד — ראה §4א
    recognized_intent: Intent
    execution_kind: ExecutionKind        # לשעבר action_mode: Literal[...] — שם ותוכן טיפוסי כעת
    active_queue_id: Optional[str]
    payload: TurnPayload
    reason_code: DecisionReason          # לשעבר str חופשי — עכשיו enum סגור
    contract_version: str                # גרסת מסמך זה שההחלטה נוצרה תחתיה, למשל "1.0.0"
    policy_snapshot_version: str          # גרסת מטריצת-העדיפות/ה-rules table שהוחלה בפועל, ייתכן שתשתנה בלי לשנות contract_version
```

**כלל:** שום handler לא מבצע ולא עונה בלי `TurnDecision` שמציין אותו במפורש כ-`selected_handler`+`reply_owner` לאותו `turn_id`. `contract_version`/`policy_snapshot_version` מאפשרים לזהות בדיעבד (ב-Shadow ובאכיפה כאחד) תחת איזו גרסת-חוזה ומדיניות התקבלה כל החלטה בודדת — נדרש ל-§8 (disagreement analysis לא יכול להיות משמעותי בלי לדעת אם שתי החלטות שונות פעלו תחת אותה מדיניות).

## 3. מטריצת הקדימות (מלאה, סדר קנוני)

```text
1. תשובה ממתינה פעילה **עם PendingReplySignal תקף** (queue_id תואם ל-
   active_queue_id הספציפי, לא רק "יש queue כלשהו ברקע")
   (reconfirmation → disambiguation → approval, לפי active_queue_id)
2. כוונה עסקית מפורשת (EXPLICIT — לא HEURISTIC): UPDATE_LEAD, DELETE_LEAD,
   DELETE_CONTACT, CREATE_LEAD, CREATE_CONTACT וכו'
   — מנצחת **בעלות** capture גנרי גם כששני ה-signals יורים על אותו קלט
3. בקשת קריאה/פעולה דטרמיניסטית (למשל "תראה לי משימה אחרונה")
   — לא דורשת סוכן, ולא נבלעת ע"י pending queue מסוג אחר
4. capture גנרי (HEURISTIC בלבד — זיהוי תבנית טלפון/שם)
   — עדיפות הכי נמוכה; חייב לוותר גם ל-(2) וגם ל-intent-gate
     (בדיקת פועל כמו תמחק/עדכן לפני שהטלפון בכלל נבדק)
5. free agent (שיחה חופשית) — ברירת מחדל כשאין תופס אחר
```

**כלל 1 המתוקן — pending לא בולע לפי נוכחות בלבד:** קיומו של `active_queue_id` ברקע (`pending_queues` לא ריק) **אינו מספיק** כדי לנתב הודעה חדשה כתשובה לתור. נדרש `pending_reply_signal.queue_id` שמצביע במפורש על אותו queue — אחרת ההודעה ממשיכה לרמה 2 ומטה כאילו אין pending בכלל (ראה תרחיש 3, המתוקן, ותרחיש 8).

### 3.1 דיכוי בעלות capture — לא זריקת ה-signal

**כלל הכניסה הראשון לאכיפה (BUG-130):** אם `intent_signal.classification == EXPLICIT` (UPDATE_LEAD/DELETE_LEAD/DELETE_CONTACT/CREATE_LEAD/CREATE_CONTACT — ראה §3.2 לחוזה ה-delete הקנוני) וגם `capture_signal` יורה על אותו substring →

- ה**בעלות** של ה-capture handler הגנרי על ה-turn (`selected_handler`, `reply_owner`, ההכרעה create-vs-update) **מדוכאת** — capture_flow אינו `selected_handler` ואינו קובע את מסלול הפעולה.
- `capture_signal.candidate` (ה-payload שחולץ — שם/טלפון/context) **אינו נזרק**. ה-explicit-intent handler שנבחר (למשל UPDATE_LEAD handler) רשאי — ולרוב חייב — לצרוך אותו payload (למשל את ה-name שחולץ) כדי לבצע resolution (§5), בדיוק כפי ש-#445 כבר עושה בפועל (`_at_find_lead_by_name_only(name)`).

במילים אחרות: **capture ownership is suppressed; capture payload may still be consumed by the selected explicit-intent handler.** התיקון של #445 שנשמר ב-§0.1 הוא דוגמה קונקרטית לכלל הזה, לא חריג ממנו.

### 3.2 חוזה Delete Intent קנוני (קפוא, V1)

ה-Intent catalog הקיים (`core/router/route_decision.py`) בנוי כבר כזוגות `CREATE_X`/`UPDATE_X` נפרדים לכל סוג ישות (`CREATE_LEAD`/`UPDATE_LEAD`, `CREATE_CONTACT`/`UPDATE_CONTACT`) — **לא** כ-intent גנרי מפורמט `X_ENTITY(entity_type=...)`. כדי לא להכניס תבנית ארכיטקטונית שנייה, שונה, לצד הקיימת:

**קפוא: `DELETE_LEAD` ו-`DELETE_CONTACT` כ-intents נפרדים** (לא `DELETE_ENTITY(entity_type)` גנרי) — מראים את `CREATE_LEAD`/`UPDATE_LEAD` ו-`CREATE_CONTACT`/`UPDATE_CONTACT` הקיימים. אין עוד "או routing למסלול intent" כניסוח פתוח.

**דורש תוסף-מימוש (לא קיים היום — נבדק ישירות בקוד):** ה-Intent catalog **אינו** מכיל היום `DELETE_LEAD`/`DELETE_CONTACT` בכלל. הוספתם ל-`route_decision.py`/`intent_router.py` היא תנאי-סף לפני ששלב 3 (אכיפה) יכול לטפל בתרחישי delete בפועל — לא רק תיאור-חוזה. עד אז, "תמחק איש קשר X" ממשיך לפול ל-fallback קיים ברמת ה-router הנוכחי (למשל `UNKNOWN`) — זו תלות-מימוש מוצהרת, לא פרצה בחוזה הזה.

זו החלטה שנבחרה מבין שתי האפשרויות שהוצגו (`DELETE_LEAD`/`DELETE_CONTACT` מול `DELETE_ENTITY(entity_type)`) — טעונה אישור מפורש של הבעלים לפני מימוש; ראה "החלטות פתוחות" בסוף הדוח המלווה את המסמך.

## 4. Reply-Owner Invariant (per turn_id) ו-Resource Claim (per resource, חוצה-turns)

שני מנגנונים נפרדים — לא לבלבל ביניהם. `reply_owner` פותר "מי מדבר בטורן הזה"; resource claim פותר "מי מבצע על המשאב הזה", ואלה שתי שאלות שונות כש-turn_id-ים שונים נוגעים באותו משאב.

### 4א. Reply-Owner — יחיד לכל turn_id

- `reply_owner` **יחיד** לכל `turn_id`.
- נקבע **לפני** שהandler רץ — לא נגזר בדיעבד ממי שהגיב הכי מהר.
- תוצאה שחושבה תחת `turn_id=N` יכולה להימסר **רק** כתשובה ל-`turn_id=N`. היא לא יכולה לענות ל-`turn_id=N+1` (סוגר את דליפת "משימה אחרונה").
- אם, בטעות מימוש, שני handlers בתוך **אותו turn_id** תובעים `reply_owner` — התביעה השנייה נדחית כ-violation מבני (§7); זה bug, לא תרחיש-race לגיטימי.

### 4ב. Resource Claim — per resource_id, חוצה turn_id

**זה המנגנון שסוגר את ה-incident המתועד (תרחיש 16) — `reply_owner` לבדו אינו מספיק לו.**

callback טלגרם (`turn_id=A`) וטקסט חופשי (`turn_id=B`) שמגיעים כמעט בו-זמנית לאותו `pending contract`/`active_queue_id` הם **שני turns שונים לגמרי**. כל אחד יכול, באופן תקין ועצמאי, "לנצח" את ה-`reply_owner` **של ה-turn שלו בלבד** — `reply_owner` לא מונע משניהם להמשיך במקביל לנסות resolve/execute על **אותו** `ActionContract`. לכן:

- לכל resource בר-ביצוע (ActionContract, pending item עם `active_queue_id`) יש claim **נפרד מ-`reply_owner`**, ממופתח לפי `resource_id` (contract_id / active_queue_id), לא לפי `turn_id`.
- claim על resource נתפס אטומית **לפני** ביצוע/resolution כלשהו על אותו resource — מי שלא הצליח לתפוס מקבל `DecisionReason.ALREADY_CLAIMED` ו**לא** תשובה כפולה, לא fallback סותר.
- **פתוח ב-V1 (לא חוסם Shadow, חוסם טענת "Coordinator סגור"):** מיקום האחסון (storage) של ה-resource claim הזה כשה-processes מרובים (לא thread יחיד בזיכרון) — ראה §7 והכותרת.

## 5. טיפוסי תוצאה — Entity Resolution

```python
class EntityType(Enum):
    LEAD    = "lead"
    CONTACT = "contact"
    # מורחב בעתיד רק דרך שינוי-חוזה מפורש.


class ResolutionOutcomeKind(Enum):
    FOUND_ONE = "found_one"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    UNAVAILABLE = "unavailable"   # למשל Airtable לא זמין — שונה מ-NOT_FOUND


@dataclass(frozen=True)
class EntityMatch:
    entity_type: EntityType
    record_id: str


@dataclass(frozen=True)
class ResolutionOutcome:
    kind: ResolutionOutcomeKind
    searched_entity_types: tuple[EntityType, ...]   # אילו טבלאות בפועל נבדקו — ראה §5.1
    record_id: Optional[str] = None                 # מוגדר רק כש-kind == FOUND_ONE
    matches: tuple[EntityMatch, ...] = ()            # מוגדר רק כש-kind == AMBIGUOUS
    unavailable_reason: Optional[str] = None         # מוגדר רק כש-kind == UNAVAILABLE
```

**כלל:** כל lookup של entity (כולל ה-name-only resolution מ-#445) חייב להחזיר `ResolutionOutcome` טיפוסי כמו למעלה — לעולם לא `Optional[str]`/`None` גולמי שממוטט FOUND_ONE/NOT_FOUND/UNAVAILABLE לערך יחיד, וללא `matches`/`searched_entity_types` שממש אין דרך לדעת אחרת מה בכלל נבדק.

### 5.1 מדיניות Leads-vs-Contacts (קפואה, V1)

- Resolution הוא **table-scoped לפי סוג הכוונה המפורשת**: `UPDATE_LEAD`/`DELETE_LEAD`/`CREATE_LEAD` מחפשים **רק** ב-Leads; `UPDATE_CONTACT`/`DELETE_CONTACT`/`CREATE_CONTACT` מחפשים **רק** ב-Contacts. `searched_entity_types` תמיד משקף זאת במפורש — `(LEAD,)` או `(CONTACT,)`, לעולם לא משתמע.
- **V1 אינו מבצע חיפוש חוצה-טבלאות (cross-table) כברירת מחדל** — אין fallback שקט מ-Leads ל-Contacts או להפך. אם רשומה עם אותו שם קיימת בשתי הטבלאות, ה-resolution של V1 עדיין ימצא רק את מה שהוא חיפש לפי סוג הכוונה — הוא לא "מגלה" את הכפילות בטבלה השנייה, וזה בכוונה, לא bug: אין עדיין intent מוצהר שמבקש cross-table search.
- **אם/כש-cross-table search יתווסף בעתיד** (מחוץ לסקופ V1): `AMBIGUOUS` חייב להיות מסוגל לשאת `matches` עם `entity_type` מעורב (גם LEAD וגם CONTACT), ו-Coordinator **לעולם לא בוחר אוטומטית טבלה אחת על פני השנייה** — זה בדיוק אותו עיקרון "לא מנחשים" של §5 עצמו. עד אז, ההנחה ש-"שם קיים פעם אחת בלבד על פני שתי הטבלאות יחד" **אינה מאומתת** ואינה אמורה להיות מאומתת — זה frozen scope-limit, לא frozen correctness claim.

## 6. חוזה בידוד Turn

- כל `tool_result` **שנוצר בתוך אותו turn** מתויג/מקושר (correlated) ל-`turn_id` שלו — מספר קריאות tool_use בתוך turn יחיד חולקות את אותו turn_id.
- אחסון עמיד (`ActionFact`/`ExecutionReceipt`) נוצר **רק** כשיש צורך אמיתי בהפניה עתידית חוצה-turn (למשל "מה עשית עכשיו" בטורן מאוחר יותר) — לא כל `tool_result` הופך אוטומטית לרשומה עמידה; רוב תוצאות ה-tool נשארות tool-call-scoped ונעלמות בסוף ה-turn, כפי שהיה.
- **"תראה לי משימה אחרונה" (תרחיש 10) הוא לא lookup של `tool_result`/`ActionFact` ישן — הוא קריאה (read) דטרמיניסטית *חדשה* ממקור ה-Tasks האמיתי (Airtable) בזמן ה-query עצמו.** רשומת ה-`ActionFact`/`ExecutionReceipt` העמידה, אם קיימת, יכולה **לכל היותר** לעזור להיקף את החיפוש (tenant/session/זמן) — היא לעולם לא "התשובה" עצמה, וזה בכוונה: משימה יכולה להשתנות (סטטוס, שם) בין רגע היצירה לרגע השאלה, ותשובה מקריאה-חוזרת של הרשומה הישנה הייתה יכולה להחזיר מידע מיושן/שגוי.
- handler שנשאל "מה עשית עכשיו" חייב להיפתר מרשומות עמידות per-turn (`ActionFact`/`ExecutionReceipt`, לא מ-`tool_result` גולמי) **רק** כשהשאלה עצמה היא על היסטוריית-פעולה (למשל "מה יצרת הרגע"), לא כשהשאלה היא לקרוא מצב נוכחי (למשל "מה המשימה האחרונה" — read חי, כמו למעלה).

## 7. סמנטיקת כשל לכל מצב

| מצב | תוצאה |
|---|---|
| Coordinator עצמו נכשל בבניית `TurnEnvelope`/`TurnDecision`, **ואין pending queue רלוונטי, ואין explicit operational/mutating intent מזוהה בטורן זה** (למשל שיחה חופשית) | fail-**open** ל-`free_agent`, log critical, לעולם לא להשמיט את התור בשקט |
| Coordinator עצמו נכשל בבניית `TurnEnvelope`/`TurnDecision`, **וקיים pending queue פעיל, או ש-`intent_signal.classification == EXPLICIT` על intent תפעולי/משנה-מצב** (UPDATE_LEAD/DELETE_LEAD/DELETE_CONTACT/CREATE_LEAD/CREATE_CONTACT וכו') | fail-**safe**: **אסור** capture/proposal/write כלשהו. log critical. תשובת degraded-mode מפורשת ("לא הצלחתי לעבד את הבקשה בבטחה, נסה שוב") — **לא** fail-open ל-`free_agent`, כי agent חופשי עלול לנחש/להציע פעולה על גבי מצב לא-ידוע |
| Entity resolution → `UNAVAILABLE` | להודיע שהמאגר לא זמין, לא לבדות `NOT_FOUND` |
| שני handlers תובעים `reply_owner` לאותו `turn_id` (**באותו turn** — bug במימוש, לא race לגיטימי) | התביעה השנייה נדחית כ-violation מבני; אין שליחה כפולה |
| שני `turn_id` שונים תובעים resource claim לאותו `resource_id` (ActionContract/pending item — **זה** ה-race הלגיטימי, תרחיש 16) | ראה §4ב — התביעה השנייה נדחית כ-`DecisionReason.ALREADY_CLAIMED`; אין שליחה כפולה, אין fallback סותר |
| הודעת אישור עומדת להישלח אבל אין `active_queue_id` תקף במאגר | `StructuralViolation` — ההודעה לא נשלחת כ-`APPROVAL_PROMPT` (ראה שער `emit_reply`, מקרה phantom approval) |
| capture signal יורה, אבל `intent_signal` EXPLICIT מנצח לפי §3/§3.1 | בעלות ה-capture על ה-turn **מדוכאת** (ניתוב ל-selected explicit-intent handler); ה-payload שחולץ **לא נזרק** — נשאר זמין לאותו handler |
| **פתוח:** מיקום אחסון (storage) של resource claim (§4ב) חוצה-processes | לא נפתר ב-V1 — מסומן במפורש כחוסם טענת "Coordinator סגור", לא חוסם תחילת Shadow Decision |

---

## Acceptance Corpus — כ-24 תרחישים דטרמיניסטיים, מתויגים לפי משפחה

כל התרחישים נגזרים מדוגמאות אמיתיות שכבר נאספו בשיחה זו. השדות `selected_handler`/`reply_owner`/`reason_code` הם הציפייה, לא בהכרח הניסוח המדויק.

### משפחה: Pending Ownership

**1.** "שמור 3" מול רשימת 5 לידים ממתינה → `selected_handler=PENDING_APPROVAL`, `active_queue_id=<batch>`, `pending_reply_signal.match_basis="expected_reply_shape_match"`, מזהה item #3 מתוך `pending_items`, לא מחפש ב-CRM.

**2.** 4 משימות + הבהרה על משימה 4 → תשובה → "מאשר" → חייב לפתור לאותו `active_queue_id` שנוצר ב-turn 1, לא ליצור queue מקביל (Case C, "פר 349"-adjacent). `pending_reply_signal.queue_id` של "מאשר" חייב להיות אותו queue_id, לא ניחוש.

**3 (מתוקן).** אישור ליד ("דני לוי") לא נסגר (pending queue פעיל), ואז "תוסיף איש קשר בדיקה" נכנס כטורן חדש → **אין `pending_reply_signal` שמצביע על ה-queue הקיים** (ההודעה החדשה היא בקשת-יצירה עצמאית ומלאה, לא תשובה/אישור) → §3 כלל 1 **לא חל**; ההודעה החדשה מנותבת לפי כללים 2-4 (§3.2/capture) כרגיל, ושני הפריטים (הליד הממתין וה-capture החדש) נשארים **שני מצבים נפרדים**, לא נערמים זה על זה ולא נבלעים זה בזה. (זו התיקון הישיר לניסוח הקודם — "מדיניות עדיפות מחליטה איזה pending פעיל" — שהניח בטעות ששני הפריטים מתחרים על אותו slot.)

**4.** "ביבי נתניהו" — capture signal יורה תקין (אין verb הפוך), אך flag-סבירות נפרד (לא Coordinator) מסמן אזהרה לפני "לשמור?".

### משפחה: Explicit Intent vs Capture (BUG-130 — אכיפה ראשונה)

**5 (מתוקן).** "תעדכן את הטלפון של דני לוי ל-0525111122" → `intent_signal` EXPLICIT `UPDATE_LEAD` מנצח **בעלות** (§3.1); capture flow עדיין מריץ חילוץ payload (שם/טלפון) שנצרך ע"י ה-`UPDATE_LEAD` handler ל-resolution (§5) — לא כ-trigger עצמאי ולא כבעל ה-turn.

**6 (מתוקן).** "תמחק איש קשר 0536272637" → `intent_signal` EXPLICIT **`DELETE_LEAD`** (חוזה delete קנוני — §3.2; **אין** יותר "או routing למסלול intent") מנצח בעלות; `capture_signal` (אם יורה) **לא נזרק**, אך בעלותו **מדוכאת** לפי §3.1 — אסור לו ליצור הצעת "לשמור?"; ה-`DELETE_LEAD` handler קובע את הפעולה בפועל.

**7 (מתוקן).** "תוסיף איש קשר בדיקה טלפון 0500000000" → `intent_signal` EXPLICIT **`CREATE_CONTACT`** (לא רק "None/CREATE" כללי) מזוהה ומנצח בעלות; capture flow מספק payload (השם "איש קשר בדיקה"+טלפון) ל-handler שנבחר — capture עצמו **אינו** קובע create-vs-update (§3.1). זה שונה, ולא זהה, ל"capture פועל כרגיל" כפי שנוסח לפני התיקון.

### משפחה: Cross-Turn Leakage

**8 (מתוקן).** "תראה לי משימה אחרונה" (עם ליד ממתין ברקע) → אין `pending_reply_signal` תואם → §3 כלל 1 לא חל → ממשיך לכלל 3 (דטרמיניסטי) → `selected_handler=DETERMINISTIC_SHOW_LAST_TASK`. לא "לא הצלחתי לבצע פעולה" (כשל שגוי), ולא בליעה ע"י pending queue.

**9.** תשובת "משימה אחרונה" מופיעה על גבי turn של "5 כפול 5" → `turn_id` mismatch; אסור. כל `tool_result` בתוך turn מקושר ל-turn_id שלו (§6) — לא summary משותף.

**10 (מתוקן).** אחרי ש-agent ענה "5 כפול 5 = 25", בקשה חוזרת ל"משימה אחרונה" → תשובה נכונה, לא "אני לא יכול לדעת מזיכרון" סתמי; **התשובה מבוצעת כ-read דטרמיניסטי חדש ממקור ה-Tasks (Airtable), לא כשליפה של `tool_result`/`ActionFact` ישן** (§6, התיקון המרכזי) — רשומה עמידה, אם קיימת, משמשת לכל היותר להיקף החיפוש, לא כתחליף לקריאה חיה.

### משפחה: Phantom Approval

**11.** "צור משימה לבדוק פר 349 עד 8 בערב" → "✅ מוכן להוספה... שלח מאשר" בלי שום `tool_call`/`ActionContract` → `emit_reply` gate חוסם שליחה כ-`APPROVAL_PROMPT` כי אין `active_queue_id` תקף במאגר.

**12.** "מאשר"/"כן" אחרי phantom prompt → "אין פעולה שממתינה לאישור" — תוצאה **נכונה טכנית** אך המניעה חייבת להיות ב-turn 11, לא כאן.

**13.** רצף 4 המשימות → הבהרה → "מוכנות לאישור" מוצג שוב בטורן 2 → "מאשר" נכשל → אותו gate, נקודת המניעה ב-turn ההצגה השנייה.

### משפחה: Lifecycle Fabrication

**14.** הסוכן כותב "אני אגיד לאליהו שיחזור אליך" בלי `Task`/`tool_result` תואם → `validate_agent_output()` מזהה כהתחייבות ללא כיסוי (log-only תחילה).

**15.** ביטול/השלמת משימה מדווחת בטקסט בלי canonical status transition תואם ב-`ActionContract`/Airtable → נחסם/מסומן זהה לתרחיש 14.

### משפחה: Concurrency

**16 (מתוקן).** callback טלגרם (`turn_id=A`) + טקסט חופשי (`turn_id=B`) מגיעים כמעט בו-זמנית לאותו pending contract (`resource_id`) → **זה תרחיש resource claim (§4ב), לא reply_owner** — כל אחד עשוי "לנצח" את ה-`reply_owner` **של ה-turn שלו בלבד**, אבל רק מי שתפס בהצלחה את ה-resource claim על ה-`resource_id` המשותף מבצע בפועל; השני מקבל `DecisionReason.ALREADY_CLAIMED` — לא approval/fallback סותרים (ה-incident המתועד).

**17 (מתוקן).** שני workers/processes מנסים לתפוס resource claim (§4ב) לאותו `resource_id` (**לא** `reply_owner` — ראה ההבחנה ב-§4) → מוגדר כ"פתוח" ב-V1 (§7, השורה האחרונה) — טסט זה מתעד את הפער (מיקום אחסון ה-claim חוצה-processes), לא פותר אותו.

### משפחה: Capability Boundary

**18.** "תכין לי קפה" → capability boundary תקין, מציע חלופות אמיתיות (regression — לא לשבור את מה שכבר עובד).

**19.** "בדוק 5 מיילים אחרונים" כש-Gmail לא מחובר → `unavailable_reason` מדויק; לא מציע `gmail_draft` כחלופה מבלי לבדוק שהיא לא תלויה באותו dependency שנכשל.

**20.** לאחר תרחיש 19: "שלח את המייל" → מסלול `EXECUTE_AFTER_APPROVAL` תמיד, גם כשה-Gmail יחזור להיות זמין — לא "תוכל לשלוח בעצמך ברגע שיתחבר".

### משפחה: Self-Output Ingestion (שוחזרה = BUG-129, תוקנה חלקית בשכבת ingress_classifier)

**21 (מתוקן).** הדבקת הודעת "📋 זיהיתי ליד: *משה חביב* (0501112222)" (פלט קודם של הבוט עצמו) חזרה כקלט →

- **שוחזרה במפורש ותועדה כ-BUG-129** (`BUG_AUDIT_LOG.md`): `_extract_name_from_window()` תפס "זיהיתי" (המילה הראשונה בתבנית-הבוט) כשם-מועמד במקום "משה חביב" האמיתי שמופיע באותה הודעה, כי הלולאה חוזרת על ההתאמה הראשונה שעוברת ולידציה ולא ממשיכה להתאמה השנייה. **תוקן ב-`ingress_classifier.py`** (הוספת "זיהיתי" ל-`_NAME_STOP`, PR #444) — regression test קיים ב-`test_bug135_command_verb_name_stop.py` (T1-T2, קורא ישירות ל-`_extract_lead_candidates()`).
- **הכיסוי של BUG-129 חלקי ביחס לתרחיש הזה, לא זהה לו:** BUG-129 תיקן רק את התסמין הנקודתי (המילה "זיהיתי" הספציפית לא-מזוהה כ-stop-word). הוא **לא** מוסיף שום מנגנון כללי שמזהה "זה נראה כמו פלט-עבר של הבוט עצמו" ברמת ה-Coordinator — אם תבנית-תשובה עתידית של הבוט תשתנה (מילת-פתיחה אחרת, אמוג'י אחר), אותה משפחת-באג יכולה לחזור בצורה חדשה שה-stop-word הנוכחי לא מכסה.
- **Regression test קונקרטי נדרש ברמת ה-Coordinator (טרם נכתב — זה ה-flag שממשיך לעמוד):** קלט טקסט שמזוהה כתואם ל-template של הודעה יוצאת קודמת (למשל ע"י provenance/`message_kind` tagging של ההודעה היוצאת המקורית — לא ע"י ניחוש טקסטואלי בלבד) חייב לקבל `capture_signal.classification`/עדיפות שממנה ניתן להסיק "לא-אמין כ-trigger עצמאי", **בנוסף** לכל תיקון stop-word ברמת ה-ingress. כלומר: תיקון-הbug הנקודתי (BUG-129) לא פוטר את ה-Coordinator מהחוזה הכללי הזה.

### משפחה: Reason Code Correctness (בדיקות-על למטריצה)

**22 (מתוקן).** כל תרחיש 5-7 חייב לשאת `reason_code=DecisionReason.EXPLICIT_INTENT_PRECEDENCE` כש-intent מנצח, לא ערך גנרי/string חופשי.

**23 (מתוקן).** כל תרחיש phantom approval (11-13) חייב לשאת `reason_code=DecisionReason.NO_BACKING_QUEUE`, לא רק "blocked" כללי.

**24.** בדיקת echo: אותו קלט מוזן פעמיים ב-turn_id שונים (לא חלק מ-concurrency) → שתי `TurnDecision` עצמאיות (כולל `contract_version`/`policy_snapshot_version` תואמים לשתיהן), לא caching/reuse של `TurnDecision` קודם.

---

## 8. קריטריוני יציאה מ-Shadow (Shadow Exit Criteria) — חוסמים מעבר לשלב 3

שלב 2 (Shadow Decision) **אינו** רשאי לעבור לשלב 3 (אכיפה ראשונה, BUG-130) עד שכל הקריטריונים המדידים הבאים מתקיימים בפועל, מתועדים — לא "נראה שזה עובד":

1. **חלון תצפית מינימלי:** לפחות N ימי production (N ייקבע לפני תחילת Shadow — לא retroactively) עם כיסוי של כל סוגי הערוצים (telegram, whatsapp, tma) וכל תפקידי הזהות הרלוונטיים (owner/partner/manager).
2. **0 אי-הסכמות בלתי-מוסברות** בין `current_handler` (ההתנהגות הקיימת בפועל) לבין `coordinator_selected_handler` (מה ש-Shadow היה בוחר) — **כל** אי-הסכמה שנרשמה חייבת artifact מפורש (bug number, decision log) שמסביר אם ה-Coordinator צודק, הקוד הקיים צודק, או שהתרחיש עצמו לא מכוסה ב-Acceptance Corpus (ואז ה-corpus מתעדכן לפני שממשיכים).
3. **100% מ-24 התרחישים ב-Acceptance Corpus** מניבים את `selected_handler`/`reply_owner`/`reason_code` המצופים, **בהרצה אוטומטית חוזרת** (לא רק ווידוא ידני חד-פעמי בזמן כתיבת המסמך).
4. **0 עלייה במקרי phantom-approval / תשובה כפולה** שנרשמו ב-audit log בהשוואה לחלון-הביקורת שלפני תחילת Shadow (Shadow עצמו אינו כותב/שולח דבר — אבל התצפית שלו חייבת להראות שהיא **הייתה** מונעת את המקרים שכבר תועדו, לא רק "לא מזיקה").
5. **Sign-off מפורש של הבעלים** על תוצאות 1–4, מתועד (תאריך + הפניה ל-artifact), לפני יצירת ה-branch של שלב 3.

עד שכל 5 מתקיימים ומתועדים — "TurnCoordinator ב-Shadow" הוא הטענה המקסימלית המותרת. "TurnCoordinator מוכן לאכיפה" בלי תיעוד מפורש של 1–5 הוא claim לא-מאומת ומפר את "כלל ברזל" (`CLAUDE.md`).

---

## סדר היישום (עודכן — שער מפורש בין שלב 2 ל-3, שלב resource-claim נפרד משלב reply-ownership)

```text
שלב 1 — Contract Freeze (מסמך זה): schema, precedence, resolution outcomes,
         failure matrix, acceptance corpus — ללא שינוי התנהגות.
שלב 2 — Shadow Decision: מחשבים בכל turn current_handler/coordinator_selected_handler/
         current_reply_owner/coordinator_reply_owner/reason_code, משווים, לא משנים תשובה.
         >>> שער חובה: §8 (קריטריוני יציאה מ-Shadow) — לא עוברים לשלב 3 בלעדיו <<<
שלב 3 — אכיפה צרה ראשונה: BUG-130 (explicit intent beats generic capture) —
         דטרמיניסטי, ללא concurrency, ללא pending מורכב. תלוי §3.2 (DELETE_LEAD/
         DELETE_CONTACT להוספה ל-Intent catalog) אם רוצים לכסות גם delete בשלב הזה.
שלב 4 — Turn Result Isolation: קושר tool_result ל-turn_id (§6), סוגר "משימה אחרונה"
         כ-read חי ממקור המידע, לא replay של turn ישן.
שלב 5 — Reply Ownership: single speaker בפועל, כולל send gateways (§4א).
שלב 6 — Resource Claim מאוחד (§4ב) — ActionContract claim חוצה-turn. שלב נפרד
         משלב 5 בכוונה (§4 מבחין בין שני המנגנונים) — עדיין חסום ע"י הפריט הפתוח
         של מיקום ה-storage חוצה-processes.
שלב 7 — Pending/Resolver מאוחד: approval, clarification, capture queues, ו-"מספר 3",
         עם PendingReplySignal (§1/§3) כתנאי-סף לכל אחד מהם.
```
