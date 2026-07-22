# TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md

**סטטוס:** CONTRACT FREEZE — חוסם תחילת Shadow Decision עד לאישור
**תנאי מוקדם:** תשתית Phase 0 (Observation Only) כבר קיימת בפועל — `TurnEnvelope`, pending queues, `active_queue_id`, `reply_owner` כתצפית, execution-kind classification, agent availability placeholder, logging של ownership signals. מסמך זה **אינו מחליף** אותה — הוא קובע את מה שחסר בה: חוזה ההחלטה, מטריצת הקדימות, טיפוסי תוצאה, בידוד turn, וסמנטיקת כשל.

**שער מחייב נוסף, קודם לאישור המסמך הזה:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — TurnCoordinator (שכבה 2) הוא אחת מ-4 השכבות הסמכותיות שהמסמך ההוא מגדיר. **אישור סופי של המסמך הזה תלוי בהשלמת Cross-Layer Impact Matrix** (4 שכבות × 9 שדות, כולל proof-of-non-impact לכל שכבה שנטען שלא נוגעים בה) — לא רק באישור התוכן הפנימי כאן.

**תוקן (לא פתוח יותר):** ה-collision שנמצא בסבב הקודם — המונח "`ActionFact`/`ExecutionReceipt`" ב-§6 מול `class ActionFact` הקיימת (`core/action_gateway.py:241`, שכבה 4) — **נפתר** בסבב הזה: `ActionFact` שמור **בלעדית** ל-`core/action_gateway.py`; §6 למטה משתמש עכשיו ב-`TurnActionReference` (מטא-דאטה של קורלציה בלבד — לא outcome סמכותי) במקום. ראה §4 ב-`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` לפירוט המלא.

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
        "explicit_queue_reference",   # ההודעה מציינת במפורש item/queue (למשל "שמור 3", "לגבי דני לוי") — לא רק תבנית-תשובה תואמת
        "expected_reply_shape_match", # תשובה תואמת את הצורה שה-queue מצפה לה (למשל שם יחיד אחרי בקשת-הבהרה) — אין ציון מפורש
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

### 1.1 כללי-תקפות ל-`PendingReplySignal` (Validity Rules)

`PendingReplySignal` עם `queue_id` לא-`None` **אינו** אוטומטית "תקף" למטרת §3 כלל 1 — חובה שיתקיימו **כל** התנאים הבאים, אחרת ה-Coordinator מתייחס אליו כאילו `queue_id=None` (כלומר: ממשיך לכלל 2 ומטה, בדיוק כמו §3 כלל 1 המתוקן קובע):

1. `queue_id` תואם ל-queue שקיים בפועל ב-`pending_queues` **וגם** לא פג-תוקף (TTL נבדק בזמן בניית ה-signal, לא בזמן ההחלטה — כדי שלא ייווצר race בין "עוד תקף כשה-signal נבנה" ל-"פג ברגע ההחלטה").
2. `match_basis` **מתאים לרמת-הסיכון של ה-queue**:
   - queues מוטציה/אישור (`pending_approval`, ActionContract-backed) דורשים `callback_correlation` **או** `explicit_confirmation_word` **או** `explicit_queue_reference` — `expected_reply_shape_match` **לבדו אינו מספיק** לqueue מסוג הזה (זה בדיוק הסיכון של phantom approval — signal חלש מדי בשביל לאשר מוטציה).
   - queues הבהרה/disambiguation לא-מוטטים (למשל "איזה משימה, #1-#5?") רשאים להסתפק ב-`expected_reply_shape_match` לבדו.
3. `confidence >= 0.75` — תואם ל-`INTENT_CONFIDENCE_THRESHOLD` הקיים כבר ב-`core/router/router.py`, לעקביות בין הרכיבים.

תנאי אחד שלא מתקיים → `pending_reply_signal` נחשב לא-תקף, גם אם `queue_id` עצמו לא-`None`.

## 2. חוזה הפלט — `TurnDecision` (קנוני)

```python
class HandlerId(Enum):
    """
    קטלוג מלא וסגור ל-V1 — כל handler שמופיע איפשהו במסמך הזה (§3-§8,
    Acceptance Corpus) ורק הם. הרחבה רק דרך שינוי-חוזה מפורש (bump
    ל-contract_version), לא "מוגדר במימוש" כפי שהיה כתוב כאן קודם.
    """
    CAPTURE_FLOW                    = "capture_flow"                    # §3 כלל 4 — capture היוריסטי גנרי
    PENDING_APPROVAL                = "pending_approval"                # §3 כלל 1 — פתרון תור ממתין תקף
    EXPLICIT_INTENT_ACTION          = "explicit_intent_action"          # §3 כלל 2/§3.1 — CREATE/UPDATE מפורש, resolution+ActionContract
    DESTRUCTIVE_ENTITY_CLARIFICATION = "destructive_entity_clarification"  # §3.2 — DESTRUCTIVE_ENTITY_REQUEST, לעולם לא מבצע ישירות
    DETERMINISTIC_SHOW_LAST_TASK    = "deterministic:show_last_task"    # §3 כלל 3 — הדוגמה הקונקרטית היחידה שהוגדרה ב-V1
    AGENT                           = "agent"                           # §3 כלל 5 — ברירת מחדל


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
    """
    קטלוג מלא וסגור ל-V1 — ממפה 1:1 את 5 חוקי §3 + מסלולי-הכשל
    הרלוונטיים ב-§4ב/§7. הרחבה רק דרך שינוי-חוזה מפורש.
    """
    PENDING_REPLY_MATCHED       = "pending_reply_matched"        # §3 כלל 1, PendingReplySignal תקף (§1.1) — לשעבר PENDING_QUEUE_ACTIVE, שם מדויק יותר: "יש queue" לבדו כבר לא מספיק לנצח
    EXPLICIT_INTENT_PRECEDENCE  = "explicit_intent_precedence"   # §3 כלל 2 — CREATE/UPDATE מפורש מנצח capture
    DESTRUCTIVE_REQUIRES_CLARIFICATION = "destructive_requires_clarification"  # §3.2 — DESTRUCTIVE_ENTITY_REQUEST, לעולם לא ניתוב-לביצוע ישיר
    DETERMINISTIC_QUERY_MATCHED = "deterministic_query_matched"  # §3 כלל 3
    CAPTURE_DEFAULT             = "capture_default"              # §3 כלל 4 — שום EXPLICIT/pending/deterministic לא ניצח
    FREE_AGENT_DEFAULT          = "free_agent_default"           # §3 כלל 5 — שום דבר אחר לא תפס
    NO_BACKING_QUEUE            = "no_backing_queue"              # ראה §7, תרחיש 11/23 — phantom approval
    ALREADY_CLAIMED             = "already_claimed"                # ראה §4ב


# ExecutionKind: לא מוגדר מחדש כאן — **שימוש-חוזר** ב-core/turn_envelope.py:77-80
# הקיים כבר בפועל (Phase 0 scaffolding), אותם 3 חברים/ערכים בדיוק
# (CONVERSATIONAL/DETERMINISTIC/AGENT_INTERPRETED). הגדרה כפולה כאן הייתה
# בדיוק אותה טעות שגילינו ב-ActionFact (ראה CROSS_LAYER_AUTHORITY_CONTRACT_V1.md
# §4) — לא חוזרים עליה:
from core.turn_envelope import ExecutionKind


class PayloadKind(Enum):
    CAPTURE_CANDIDATE           = "capture_candidate"
    RESOLUTION_REQUEST          = "resolution_request"
    APPROVAL_REFERENCE          = "approval_reference"
    DESTRUCTIVE_ENTITY_REFERENCE = "destructive_entity_reference"   # §3.2 — חדש
    # מורחב רק דרך שינוי-חוזה מפורש, כמו HandlerId/DecisionReason.


@dataclass(frozen=True)
class CaptureCandidatePayload:
    name: str
    phone: str
    context: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionRequestPayload:
    entity_type_hint: EntityType   # ראה §5 — נגזר מה-intent שנבחר, לא מנוחש מחדש
    name: str
    phone: Optional[str]           # הערך לכתיבה (update) או ליצירה (create) — לא בהכרח מפתח-חיפוש, ראה §5


@dataclass(frozen=True)
class ApprovalReferencePayload:
    active_queue_id: str
    item_index: Optional[int] = None   # למשל "שמור 3" → item #3 מתוך pending_items


@dataclass(frozen=True)
class DestructiveEntityRequestPayload:
    """
    §3.2 — payload למסך-הבהרה בלבד. לעולם לא נושא כוונת-ביצוע/אישור —
    רק context לזיהוי הרשומה עבור ה-handler שמציג את התוצאות הבטוחות
    הקפואות (ארכיון / Do Not Contact / ניקוי נתוני-בדיקה).
    """
    entity_type_hint: EntityType
    name: Optional[str]
    phone: Optional[str]


# TurnPayload הוא union טיפוסי — לא dict גולמי. כל HandlerId יודע איזה
# variant לצפות לו (התאמה 1:1 ל-PayloadKind), ו-mismatch נתפס כשגיאת-
# טיפוס בזמן import/type-check, לא כ-KeyError ב-runtime עמוק בתוך handler.
TurnPayload = Union[
    CaptureCandidatePayload,
    ResolutionRequestPayload,
    ApprovalReferencePayload,
    DestructiveEntityRequestPayload,
]


@dataclass(frozen=True)
class TurnDecision:
    turn_id: str
    selected_handler: HandlerId
    reply_owner: ReplyOwner              # יחיד — ראה §4א
    recognized_intent: Intent
    execution_kind: ExecutionKind        # מיובא מ-core/turn_envelope.py — ראה למעלה
    active_queue_id: Optional[str]
    payload: TurnPayload
    reason_code: DecisionReason          # לשעבר str חופשי — עכשיו enum סגור ומלא
    contract_version: str                # גרסת מסמך זה שההחלטה נוצרה תחתיה, למשל "1.0.0"
    policy_snapshot_version: str          # גרסת מטריצת-העדיפות/ה-rules table שהוחלה בפועל, ייתכן שתשתנה בלי לשנות contract_version
```

**כלל:** שום handler לא מבצע ולא עונה בלי `TurnDecision` שמציין אותו במפורש כ-`selected_handler`+`reply_owner` לאותו `turn_id`. `contract_version`/`policy_snapshot_version` מאפשרים לזהות בדיעבד (ב-Shadow ובאכיפה כאחד) תחת איזו גרסת-חוזה ומדיניות התקבלה כל החלטה בודדת — נדרש ל-§8 (disagreement analysis לא יכול להיות משמעותי בלי לדעת אם שתי החלטות שונות פעלו תחת אותה מדיניות).

## 3. מטריצת הקדימות (מלאה, סדר קנוני)

```text
1. תשובה ממתינה פעילה **עם PendingReplySignal תקף** (§1.1 — queue_id תואם
   ל-active_queue_id הספציפי + match_basis מתאים לרמת-הסיכון, לא רק "יש
   queue כלשהו ברקע")
   (reconfirmation → disambiguation → approval, לפי active_queue_id)
2. כוונה עסקית מפורשת (EXPLICIT — לא HEURISTIC), משתי קבוצות נפרדות:
   2א. יצירה/עדכון: UPDATE_LEAD, CREATE_LEAD, CREATE_CONTACT, UPDATE_CONTACT
       — מנצחת בעלות capture גנרי, מנותבת ל-EXPLICIT_INTENT_ACTION (§3.1)
   2ב. בקשה הרסנית: DESTRUCTIVE_ENTITY_REQUEST — **גם היא** מנצחת בעלות
       capture גנרי, אבל **לעולם לא מבצעת** — מנותבת ל-הבהרה בלבד (§3.2).
       V1 **אין** לה DELETE_LEAD/DELETE_CONTACT כ-intents מבצעים רגילים —
       ראה §3.2 למדיניות המלאה.
3. בקשת קריאה/פעולה דטרמיניסטית (למשל "תראה לי משימה אחרונה")
   — לא דורשת סוכן, ולא נבלעת ע"י pending queue מסוג אחר
4. capture גנרי (HEURISTIC בלבד — זיהוי תבנית טלפון/שם)
   — עדיפות הכי נמוכה; חייב לוותר גם ל-(2) וגם ל-intent-gate
     (בדיקת פועל כמו תמחק/עדכן לפני שהטלפון בכלל נבדק)
5. free agent (שיחה חופשית) — ברירת מחדל כשאין תופס אחר
```

**כלל 1 המתוקן — pending לא בולע לפי נוכחות בלבד:** קיומו של `active_queue_id` ברקע (`pending_queues` לא ריק) **אינו מספיק** כדי לנתב הודעה חדשה כתשובה לתור. נדרש `pending_reply_signal` **תקף** (§1.1) — אחרת ההודעה ממשיכה לרמה 2 ומטה כאילו אין pending בכלל (ראה תרחיש 3, המתוקן, ותרחיש 8).

### 3.1 דיכוי בעלות capture — לא זריקת ה-signal

**כלל הכניסה הראשון לאכיפה (BUG-130):** אם `intent_signal.classification == EXPLICIT` (UPDATE_LEAD/CREATE_LEAD/CREATE_CONTACT/UPDATE_CONTACT **או** DESTRUCTIVE_ENTITY_REQUEST — ראה §3.2 למדיניות ה-destructive המלאה) וגם `capture_signal` יורה על אותו substring →

- ה**בעלות** של ה-capture handler הגנרי על ה-turn (`selected_handler`, `reply_owner`, ההכרעה create-vs-update) **מדוכאת** — capture_flow אינו `selected_handler` ואינו קובע את מסלול הפעולה.
- `capture_signal.candidate` (ה-payload שחולץ — שם/טלפון/context) **אינו נזרק**. `HandlerId.EXPLICIT_INTENT_ACTION` (למשל עבור `UPDATE_LEAD`) רשאי — ולרוב חייב — לצרוך אותו payload (למשל את ה-name שחולץ) כדי לבצע resolution (§5), בדיוק כפי ש-#445 כבר עושה בפועל (`_at_find_lead_by_name_only(name)`).

במילים אחרות: **capture ownership is suppressed; capture payload may still be consumed by the selected explicit-intent handler.** התיקון של #445 שנשמר ב-§0.1 הוא דוגמה קונקרטית לכלל הזה, לא חריג ממנו.

### 3.2 מדיניות בקשה הרסנית (Destructive-Entity Request) — קפוא, V1

**זה מחליף לגמרי את ה-freeze הקודם על `DELETE_LEAD`/`DELETE_CONTACT` כ-intents מבצעים.** לפי מדיניות-הבעלים: **אין ל-V1 שום מסלול שמבצע מחיקה על בקשת-משתמש בודדת** — לא `DELETE_LEAD`, לא `DELETE_CONTACT`, לא שום צורה אחרת של "תמחק X" → כתיבה בפועל.

**קפוא: `DESTRUCTIVE_ENTITY_REQUEST`** — intent **לא-מבצע** (non-executing), שתפקידו היחיד הוא ניתוב. מזהה כשההודעה מבטאת כוונה הרסנית כלפי ישות (ליד/איש-קשר) — "תמחק איש קשר X", "מחק את הליד הזה", "תוריד את X מהמערכת" וכו' — **בלי קשר** לניסוח (מילולי-delete/מחיקה-לצמיתות/כל ניסוח אחר).

- `intent_signal.classification == EXPLICIT` על `DESTRUCTIVE_ENTITY_REQUEST` **מנצח בעלות capture** בדיוק כמו intent-ים מבצעים אחרים (§3.1) — `capture_signal` מדוכא, לא נזרק.
- `selected_handler = HandlerId.DESTRUCTIVE_ENTITY_CLARIFICATION` — **תמיד** מנתב להבהרה, **אף פעם לא** לביצוע ישיר. אין "one-click אישור" למחיקה תחת V1.
- payload: `DestructiveEntityRequestPayload` (§2) — context לזיהוי הרשומה בלבד, לא trigger.

**תוצאות בטוחות קפואות (Frozen Safe Outcomes)** — אלה ה-**יחידות** שה-handler רשאי להציע למשתמש כתגובה ל-`DESTRUCTIVE_ENTITY_REQUEST`:

1. **ארכיון/לא רלוונטי** (archive / not relevant) — שינוי סטטוס, לא מחיקת רשומה.
2. **Do Not Contact** — סימון מפורש שלא ליצור קשר יותר, הרשומה נשארת.
3. **ניקוי נתוני-בדיקה** (test-data maintenance) — היקף **צר ומפורש בלבד**: רשומות שנוצרו ע"י הבעלים עצמו לצורכי בדיקה (למשל טלפוני-בדיקה מוסכמים מראש), **לא** מנגנון-מחיקה כללי בתחפושת.

**מחיקה פיזית (hard delete) נשארת מחוץ לסקופ V1 לגמרי** — אינה אחת מהאפשרויות שה-handler מציע, ואינה נגישה כלל דרך מסלול-האישור הרגיל (`כן`/`לא` על ActionContract סטנדרטי, §4/§7) — כל מימוש עתידי שלה דורש class-אישור **חזק יותר**, לא-מוגדר ב-V1 (למשל: דורש role גבוה יותר, אישור-כפול, או window-נפרד) — לא תוסף-הרשאה על אותו מסלול one-click.

**היקש-מודע מ-BUG-094:** בדיוק כמו שההגנה נגד cross-lead contamination (BUG-094) לא הוקלה בלי שיקול-דעת מפורש (§5.1), גם כאן — מניעת מחיקה-לא-הפיכה בטעות/בבהילות היא ההנחיה המפורשת, לא רק "עדיין לא הספקנו לממש delete".

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

- Resolution הוא **table-scoped לפי סוג הכוונה המפורשת**: `UPDATE_LEAD`/`CREATE_LEAD` מחפשים **רק** ב-Leads; `UPDATE_CONTACT`/`CREATE_CONTACT` מחפשים **רק** ב-Contacts. `DESTRUCTIVE_ENTITY_REQUEST` (§3.2) מחפש לפי `DestructiveEntityRequestPayload.entity_type_hint` (נגזר מה-capture/context שזיהה אם זה נראה כמו ליד או איש-קשר) — לא cross-table אוטומטית, אותו עיקרון בדיוק. `searched_entity_types` תמיד משקף זאת במפורש — `(LEAD,)` או `(CONTACT,)`, לעולם לא משתמע.
- **V1 אינו מבצע חיפוש חוצה-טבלאות (cross-table) כברירת מחדל** — אין fallback שקט מ-Leads ל-Contacts או להפך. אם רשומה עם אותו שם קיימת בשתי הטבלאות, ה-resolution של V1 עדיין ימצא רק את מה שהוא חיפש לפי סוג הכוונה — הוא לא "מגלה" את הכפילות בטבלה השנייה, וזה בכוונה, לא bug: אין עדיין intent מוצהר שמבקש cross-table search.
- **אם/כש-cross-table search יתווסף בעתיד** (מחוץ לסקופ V1): `AMBIGUOUS` חייב להיות מסוגל לשאת `matches` עם `entity_type` מעורב (גם LEAD וגם CONTACT), ו-Coordinator **לעולם לא בוחר אוטומטית טבלה אחת על פני השנייה** — זה בדיוק אותו עיקרון "לא מנחשים" של §5 עצמו. עד אז, ההנחה ש-"שם קיים פעם אחת בלבד על פני שתי הטבלאות יחד" **אינה מאומתת** ואינה אמורה להיות מאומתת — זה frozen scope-limit, לא frozen correctness claim.

## 6. חוזה בידוד Turn

**מונח-מפתח, לא לבלבל:** `ActionFact` **שמור בלעדית** ל-`core/action_gateway.py` (שכבה 4 — struct צר, scoped לקריאת-tool בודדת, ראה `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §4). הסעיף הזה **אינו** משתמש בו ולא מגדיר-מחדש אותו. הרשומה שהסעיף הזה זקוק לה — קורלציה חוצת-turn, לא outcome — נקראת `TurnActionReference` (מוגדר למטה), מונח **חדש**, לא שם-שאול.

```python
@dataclass(frozen=True)
class TurnActionReference:
    """
    מטא-דאטה של קורלציה בלבד — **לא** ה-outcome הסמכותי של הפעולה.
    ה-outcome הסמכותי תמיד נשלף מחדש משכבה 4 (`ActionContract`/
    `ActionContractRepository`, לפי `action_contract_id`) או משכבה 3
    (C53a result contract) — הרשומה הזו רק מצביעה לאן לפנות, לא
    מכילה את התשובה בעצמה. נוצרת **רק** כשיש צורך אמיתי בהפניה עתידית
    חוצה-turn (למשל "מה עשית עכשיו" בטורן מאוחר יותר) — לא כל
    tool_result הופך אוטומטית לרשומה עמידה.
    """
    turn_id: str
    decision_id: str              # מזהה ה-TurnDecision שהוליד את הפעולה
    action_contract_id: Optional[str]   # ה-contract_id בשכבה 4, אם קיים (למשל לא קיים לפעולות read-only)
    execution_evidence_ref: Optional[str]   # הפניה ל-evidence לפי C53a (שכבה 3) — לא ה-evidence עצמו, מצביע אליו
    created_at: float
```

- כל `tool_result` **שנוצר בתוך אותו turn** מתויג/מקושר (correlated) ל-`turn_id` שלו — מספר קריאות tool_use בתוך turn יחיד חולקות את אותו turn_id.
- `TurnActionReference` נוצר **רק** כשיש צורך אמיתי בהפניה עתידית חוצה-turn — רוב תוצאות ה-tool נשארות tool-call-scoped ונעלמות בסוף ה-turn, כפי שהיה.
- **"תראה לי משימה אחרונה" (תרחיש 10) הוא לא lookup של `tool_result`/`TurnActionReference` ישן — הוא קריאה (read) דטרמיניסטית *חדשה* ממקור ה-Tasks האמיתי (Airtable) בזמן ה-query עצמו.** `TurnActionReference` עמיד, אם קיים, יכול **לכל היותר** לעזור להיקף את החיפוש (tenant/session/זמן, או להצביע על ה-`action_contract_id` הרלוונטי) — הוא לעולם לא "התשובה" עצמה, וזה בכוונה: משימה יכולה להשתנות (סטטוס, שם) בין רגע היצירה לרגע השאלה, ותשובה מקריאה-חוזרת של הרשומה הישנה הייתה יכולה להחזיר מידע מיושן/שגוי.
- handler שנשאל "מה עשית עכשיו" חייב להיפתר מ-`TurnActionReference` per-turn (**לא** מ-`tool_result` גולמי, **ולא** מלהניח שהוא-עצמו ה-outcome — תמיד לשלוף מחדש את ה-outcome הסמכותי משכבה 3/4 דרך `action_contract_id`/`execution_evidence_ref`) **רק** כשהשאלה עצמה היא על היסטוריית-פעולה (למשל "מה יצרת הרגע"), לא כשהשאלה היא לקרוא מצב נוכחי (למשל "מה המשימה האחרונה" — read חי, כמו למעלה).

## 7. סמנטיקת כשל לכל מצב

| מצב | תוצאה |
|---|---|
| Coordinator עצמו נכשל בבניית `TurnEnvelope`/`TurnDecision`, **ואין pending queue רלוונטי, ואין explicit operational/mutating intent מזוהה בטורן זה** (למשל שיחה חופשית) | fail-**open** ל-`free_agent`, log critical, לעולם לא להשמיט את התור בשקט |
| Coordinator עצמו נכשל בבניית `TurnEnvelope`/`TurnDecision`, **וקיים pending queue פעיל, או ש-`intent_signal.classification == EXPLICIT` על intent תפעולי/משנה-מצב** (UPDATE_LEAD/CREATE_LEAD/CREATE_CONTACT/UPDATE_CONTACT/**DESTRUCTIVE_ENTITY_REQUEST**) | fail-**safe**: **אסור** capture/proposal/write כלשהו — **כולל** ניתוב ל-clarification הרסני (§3.2), גם אם ה-clarification עצמו "בטוח" לכאורה: אם ה-Coordinator כבר נכשל, אין לסמוך על שום החלטת-ניתוב שלו. log critical. תשובת degraded-mode מפורשת ("לא הצלחתי לעבד את הבקשה בבטחה, נסה שוב") — **לא** fail-open ל-`free_agent`, כי agent חופשי עלול לנחש/להציע פעולה על גבי מצב לא-ידוע |
| Entity resolution → `UNAVAILABLE` | להודיע שהמאגר לא זמין, לא לבדות `NOT_FOUND` |
| שני handlers תובעים `reply_owner` לאותו `turn_id` (**באותו turn** — bug במימוש, לא race לגיטימי) | התביעה השנייה נדחית כ-violation מבני; אין שליחה כפולה |
| שני `turn_id` שונים תובעים resource claim לאותו `resource_id` (ActionContract/pending item — **זה** ה-race הלגיטימי, תרחיש 16) | ראה §4ב — התביעה השנייה נדחית כ-`DecisionReason.ALREADY_CLAIMED`; אין שליחה כפולה, אין fallback סותר |
| הודעת אישור עומדת להישלח אבל אין `active_queue_id` תקף במאגר | `StructuralViolation` — ההודעה לא נשלחת כ-`APPROVAL_PROMPT` (ראה שער `emit_reply`, מקרה phantom approval) |
| capture signal יורה, אבל `intent_signal` EXPLICIT מנצח לפי §3/§3.1 | בעלות ה-capture על ה-turn **מדוכאת** (ניתוב ל-selected explicit-intent handler); ה-payload שחולץ **לא נזרק** — נשאר זמין לאותו handler |
| **פתוח:** מיקום אחסון (storage) של resource claim (§4ב) חוצה-processes | לא נפתר ב-V1 — מסומן במפורש כחוסם טענת "Coordinator סגור", לא חוסם תחילת Shadow Decision |

---

## Acceptance Corpus — 25 תרחישים דטרמיניסטיים, מתויגים לפי משפחה

כל התרחישים נגזרים מדוגמאות אמיתיות שכבר נאספו בשיחה זו. השדות `selected_handler`/`reply_owner`/`reason_code` הם הציפייה, לא בהכרח הניסוח המדויק.

### משפחה: Pending Ownership

**1.** "שמור 3" מול רשימת 5 לידים ממתינה → `selected_handler=PENDING_APPROVAL`, `active_queue_id=<batch>`, `pending_reply_signal.match_basis="expected_reply_shape_match"`, מזהה item #3 מתוך `pending_items`, לא מחפש ב-CRM.

**2.** 4 משימות + הבהרה על משימה 4 → תשובה → "מאשר" → חייב לפתור לאותו `active_queue_id` שנוצר ב-turn 1, לא ליצור queue מקביל (Case C, "פר 349"-adjacent). `pending_reply_signal.queue_id` של "מאשר" חייב להיות אותו queue_id, לא ניחוש.

**3 (מתוקן).** אישור ליד ("דני לוי") לא נסגר (pending queue פעיל), ואז "תוסיף איש קשר בדיקה" נכנס כטורן חדש → **אין `pending_reply_signal` שמצביע על ה-queue הקיים** (ההודעה החדשה היא בקשת-יצירה עצמאית ומלאה, לא תשובה/אישור) → §3 כלל 1 **לא חל**; ההודעה החדשה מנותבת לפי כללים 2-4 (§3.2/capture) כרגיל, ושני הפריטים (הליד הממתין וה-capture החדש) נשארים **שני מצבים נפרדים**, לא נערמים זה על זה ולא נבלעים זה בזה. (זו התיקון הישיר לניסוח הקודם — "מדיניות עדיפות מחליטה איזה pending פעיל" — שהניח בטעות ששני הפריטים מתחרים על אותו slot.)

**4.** "ביבי נתניהו" — capture signal יורה תקין (אין verb הפוך), אך flag-סבירות נפרד (לא Coordinator) מסמן אזהרה לפני "לשמור?".

### משפחה: Explicit Intent vs Capture (BUG-130 — אכיפה ראשונה)

**5 (מתוקן).** "תעדכן את הטלפון של דני לוי ל-0525111122" → `intent_signal` EXPLICIT `UPDATE_LEAD` מנצח **בעלות** (§3.1); capture flow עדיין מריץ חילוץ payload (שם/טלפון) שנצרך ע"י ה-`UPDATE_LEAD` handler ל-resolution (§5) — לא כ-trigger עצמאי ולא כבעל ה-turn.

**6 (מתוקן שוב — מדיניות-הרסנית חדשה, §3.2).** "תמחק איש קשר 0536272637" → `intent_signal` EXPLICIT **`DESTRUCTIVE_ENTITY_REQUEST`** מנצח בעלות (`reason_code=EXPLICIT_INTENT_PRECEDENCE`, כמו 5-7 האחרים); `capture_signal` (אם יורה) **לא נזרק**, אך בעלותו **מדוכאת** לפי §3.1 — אסור לו ליצור הצעת "לשמור?". `selected_handler=DESTRUCTIVE_ENTITY_CLARIFICATION` — **לא** מבצע מחיקה, מציג רק את 3 התוצאות הבטוחות הקפואות (ארכיון/Do Not Contact/ניקוי נתוני-בדיקה, §3.2). `reason_code` הפעם: `DESTRUCTIVE_REQUIRES_CLARIFICATION`, לא `EXPLICIT_INTENT_PRECEDENCE` לבד — שני ה-reason codes רלוונטיים כאן ברמות שונות (הבעלות-על-capture מנוצחת מסיבת EXPLICIT_INTENT_PRECEDENCE, אבל ההחלטה הסופית-שמוצגת נושאת DESTRUCTIVE_REQUIRES_CLARIFICATION כי זה הניתוב בפועל).

**7 (מתוקן).** "תוסיף איש קשר בדיקה טלפון 0500000000" → `intent_signal` EXPLICIT **`CREATE_CONTACT`** (לא רק "None/CREATE" כללי) מזוהה ומנצח בעלות; capture flow מספק payload (השם "איש קשר בדיקה"+טלפון) ל-handler שנבחר — capture עצמו **אינו** קובע create-vs-update (§3.1). זה שונה, ולא זהה, ל"capture פועל כרגיל" כפי שנוסח לפני התיקון.

### משפחה: Cross-Turn Leakage

**8 (מתוקן).** "תראה לי משימה אחרונה" (עם ליד ממתין ברקע) → אין `pending_reply_signal` תואם → §3 כלל 1 לא חל → ממשיך לכלל 3 (דטרמיניסטי) → `selected_handler=DETERMINISTIC_SHOW_LAST_TASK`. לא "לא הצלחתי לבצע פעולה" (כשל שגוי), ולא בליעה ע"י pending queue.

**9.** תשובת "משימה אחרונה" מופיעה על גבי turn של "5 כפול 5" → `turn_id` mismatch; אסור. כל `tool_result` בתוך turn מקושר ל-turn_id שלו (§6) — לא summary משותף.

**10 (מתוקן).** אחרי ש-agent ענה "5 כפול 5 = 25", בקשה חוזרת ל"משימה אחרונה" → תשובה נכונה, לא "אני לא יכול לדעת מזיכרון" סתמי; **התשובה מבוצעת כ-read דטרמיניסטי חדש ממקור ה-Tasks (Airtable), לא כשליפה של `tool_result`/`TurnActionReference` ישן** (§6, התיקון המרכזי) — `TurnActionReference` עמיד, אם קיים, משמש לכל היותר להיקף החיפוש, לא כתחליף לקריאה חיה, ולעולם לא כ-outcome עצמו.

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
- **Regression test קונקרטי נדרש ברמת ה-Coordinator (טרם נכתב — זה ה-flag שממשיך לעמוד) — מפוצל לשני מקרים נבדלים, לא מנגנון אחד:**
  1. **ציטוט עם provenance ידוע** — הפלטפורמה (Telegram/WhatsApp) מספקת מטא-דאטה מבנית שמצביעה על כך שההודעה מצטטת/עונה להודעה יוצאת ספציפית שהבוט שלח (`reply_to_message_id` או שווה-ערך) — signal **חזק**, structural, לא ניחוש. כשקיים, `capture_signal.classification` חייב לשקף "מקור: ציטוט-ידוע של פלט-בוט", לא HEURISTIC רגיל — אמינות גבוהה שזה **לא** trigger עצמאי.
  2. **הדבקת טקסט-רגיל ידנית** — התרחיש המדויק של BUG-129: אין שום מטא-דאטה מבנית, ההודעה מגיעה כטקסט חופשי רגיל שרק *מזדהה תוכנית* עם תבנית-פלט קודמת (למשל מתחילה ב-"📋 זיהיתי ליד:"). כאן **אין** signal מבני להסתמך עליו — כל זיהוי הוא content-based, ומזה נובע גם false-positive risk אמיתי (הודעת-משתמש לגיטימית שמתחילה באופן דומה). זה המקרה החלש/מסוכן יותר, ודורש טיפול שונה מ-(1) — לא אותו מנגנון "provenance tagging" שהניסוח הקודם רמז עליו כפתרון-אחיד.
  
  שני המקרים דורשים regression tests **נפרדים** — הצלחה ב-(1) לא מוכיחה כלום לגבי (2), ולהפך. תיקון-הbug הנקודתי (BUG-129, מקרה 2 בלבד) לא פוטר את ה-Coordinator מהחוזה הכללי לגבי מקרה 1.

### משפחה: Reason Code Correctness (בדיקות-על למטריצה)

**22 (מתוקן).** כל תרחיש 5-7 חייב לשאת `reason_code=DecisionReason.EXPLICIT_INTENT_PRECEDENCE` כש-intent מנצח, לא ערך גנרי/string חופשי.

**23 (מתוקן).** כל תרחיש phantom approval (11-13) חייב לשאת `reason_code=DecisionReason.NO_BACKING_QUEUE`, לא רק "blocked" כללי.

**24.** בדיקת echo: אותו קלט מוזן פעמיים ב-turn_id שונים (לא חלק מ-concurrency) → שתי `TurnDecision` עצמאיות (כולל `contract_version`/`policy_snapshot_version` תואמים לשתיהן), לא caching/reuse של `TurnDecision` קודם.

### משפחה: Destructive Entity Request (מדיניות-הרסנית קפואה, §3.2)

**25 (חדש).** "תמחק לצמיתות את הליד של דני לוי, אני בטוח" (בקשה מפורשת ל-hard delete, לא רק "תמחק") → **עדיין** מנותב ל-`DESTRUCTIVE_ENTITY_CLARIFICATION` בדיוק כמו תרחיש 6 — "לצמיתות"/"אני בטוח" **אינם** עוקפים את §3.2. ה-handler מציג **רק** את 3 התוצאות הבטוחות הקפואות; מחיקה פיזית **אינה** אחת האפשרויות המוצגות, ואין מסלול one-click-אישור שמוביל אליה — אם המשתמש מתעקש על מחיקה פיזית, התשובה היא שזה לא נתמך תחת V1 (לא ניסיון "לשכנע" את המשתמש לקבל את התחליף, ולא ביצוע חלקי/עוקף).

---

## 8. קריטריוני יציאה מ-Shadow (Shadow Exit Criteria) — חוסמים מעבר לשלב 3

שלב 2 (Shadow Decision) **אינו** רשאי לעבור לשלב 3 (אכיפה ראשונה, BUG-130) עד שכל הקריטריונים המדידים הבאים מתקיימים בפועל, מתועדים — לא "נראה שזה עובד":

1. **חלון תצפית מינימלי — מספרים סגורים, לא TBD:**
   - **7 ימים רצופים** של production, עם כיסוי כל סוגי הערוצים (telegram, whatsapp, tma) וכל תפקידי הזהות הרלוונטיים (owner/partner/manager).
   - **לפחות 100 `TurnDecision`** שחושבו ב-Shadow לאורך החלון.
   - **לפחות 20 מקרי contested-signal** (turns שבהם יותר מחוק אחד ב-§3 יכול היה תיאורטית לנצח — לא turns טריוויאליים עם signal יחיד) — עם **מינימום לכל משפחה** מתוך ה-Acceptance Corpus: Pending Ownership ≥5, Explicit Intent vs Capture ≥5, Cross-Turn Leakage ≥3, Concurrency ≥2, Destructive Entity Request ≥2 (סה"כ ≥17, מעוגל ל-≥20 עם שוליים). חלון שמכוסה ברובו ע"י משפחה אחת בלבד **אינו** מספיק, גם אם 100+ ה-`TurnDecision` הכולל מתקיים.
2. **0 אי-הסכמות בלתי-מוסברות** בין `current_handler` (ההתנהגות הקיימת בפועל) לבין `coordinator_selected_handler` (מה ש-Shadow היה בוחר) — **כל** אי-הסכמה שנרשמה חייבת artifact מפורש (bug number, decision log) שמסביר אם ה-Coordinator צודק, הקוד הקיים צודק, או שהתרחיש עצמו לא מכוסה ב-Acceptance Corpus (ואז ה-corpus מתעדכן לפני שממשיכים).
3. **100% מ-25 התרחישים ב-Acceptance Corpus** מניבים את `selected_handler`/`reply_owner`/`reason_code` המצופים, **בהרצה אוטומטית חוזרת** (לא רק ווידוא ידני חד-פעמי בזמן כתיבת המסמך).
4. **Incident Replay & Classification — מחליף לגמרי את מדד ה-"0 עלייה" הפסיבי הקודם.** מדד פסיבי ("0 מקרי phantom-approval/תשובה כפולה חדשים") עלול לעבור טריוויאלית באפס נפח-משתמשים בלי להוכיח שום דבר. במקום זה: **כל** incident מתועד קיים (למשל ה-phantom-approval incident, תרחיש 11; ה-concurrency incident, תרחיש 16; BUG-129 self-output ingestion, תרחיש 21) מוזן מחדש (**replay**) דרך לוגיקת ה-Shadow Decision, על הטקסט/state המקוריים שנאספו בזמן ה-incident, ומסווג במפורש לאחד משלושה:
   - **PREVENTED** — ה-Coordinator היה מונע/פותר את זה נכון.
   - **NOT_PREVENTED** — עדיין קורה תחת ה-Shadow logic.
   - **NOT_APPLICABLE** — התרחיש כבר לא רלוונטי (למשל תוקן בשכבה אחרת לגמרי, לא ע"י Coordinator).
   
   **חובה: 100% מהתקריות המתועדות המסווגות "רלוונטי" חייבות PREVENTED.** כל NOT_PREVENTED חוסם את המעבר לשלב 3, ללא יוצא מהכלל.
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
         דטרמיניסטי, ללא concurrency, ללא pending מורכב. תלוי §3.2
         (DESTRUCTIVE_ENTITY_REQUEST להוספה ל-Intent catalog, מנותב לניתוב-
         בלבד — לא לביצוע) אם רוצים לכסות גם בקשות-הרסניות בשלב הזה.
שלב 4 — Turn Result Isolation: קושר tool_result ל-turn_id (§6), סוגר "משימה אחרונה"
         כ-read חי ממקור המידע, לא replay של turn ישן.
שלב 5 — Reply Ownership: single speaker בפועל, כולל send gateways (§4א).
שלב 6 — Resource Claim מאוחד (§4ב) — ActionContract claim חוצה-turn. שלב נפרד
         משלב 5 בכוונה (§4 מבחין בין שני המנגנונים) — עדיין חסום ע"י הפריט הפתוח
         של מיקום ה-storage חוצה-processes.
שלב 7 — Pending/Resolver מאוחד: approval, clarification, capture queues, ו-"מספר 3",
         עם PendingReplySignal (§1/§3) כתנאי-סף לכל אחד מהם.
```
