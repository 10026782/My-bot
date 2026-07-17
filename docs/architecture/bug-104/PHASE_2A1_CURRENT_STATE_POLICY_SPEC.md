# BUG-104 Phase 2A.1 — Current State Policy SPEC

**סוג מסמך:** SPEC בלבד. **אין קוד runtime. אין mutation לסכמת Airtable. אין data migration. אין שינוי frontend. אין שינוי feature flag.**

**תאריך:** 2026-07-17 · **Branch:** `claude/bug-104-phase-2a1-current-state-policy-spec` · **main בזמן הכתיבה:** `a4d04c0` (כולל PR #370, Phase 2A.0)

**תלות:** מסמך זה בונה על `docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md` — הרביעייה הקנונית שנקבעה שם (`status`, `Business Outcome`, `Score`, `domain`) היא בסיס ה-Inputs כאן. לא חוזר על אינוונטר הסכמה/הערכים החיים — רק מפנה אליו.

**שיטה:** לפני כתיבת המדיניות המוצעת, נבדק ותועד **המצב הקיים בפועל** של חישוב ה-`state`/`phase` ל-Lead דרך הקוד החי (`core/leads_reasoning_projection.py` → `core/adapters/leads_adapter.py` → `core/reasoning_engines.py` → `decision_orchestrator.py`), עם ציטוטי file:line — לא הונח דבר. זה קריטי כי חלק מהפערים שהמדיניות המוצעת סוגרת (למשל: **Business Outcome לא נכנס בכלל ל-ReasoningEntity היום**) הם עובדה נבדקת, לא הנחת עבודה.

---

## 0. Current State (as-is) — איך `state`/`phase` מחושב היום ל-Lead, בפועל

זהו הבסיס להשוואה מול המדיניות המוצעת בהמשך (§8 מנוגד ל-§0 בכל דוגמה).

**שרשרת הקריאה (Phase 1, read-only, פעילה כרגע מאחורי `FEATURE_CORE_REASONING_LEADS_STATE`):**

1. `core/leads_reasoning_projection.py::build_reasoning_projection()` — מקבל `lead_record`/`events`/`as_of` מהקורא, בלי לקרוא בעצמו. מחזיר `"state": result.phase` (`:149`) — **passthrough ישיר** של `ReasoningResult.phase`, אין לוגיקת Lead-specific נוספת מעל.
2. `_normalize_lead_snapshot()` (`core/leads_reasoning_projection.py:255-268`) ממפה שמות שדה live ל-legacy דרך `_LIVE_TO_ADAPTER_FIELDS` (`:71-84`) — **הטבלה הזו לא כוללת `Business Outcome` בכלל.** רק `phone/status/tier/source/channel/domain/created_at/updated_at/notes/summary/Score/Name` מועברים הלאה.
3. `core/adapters/leads_adapter.py::LeadsAdapter.to_entity()` (`:60-131`) בונה `ReasoningEntity` — קורא `fields.get("Status","")` ומעביר דרך `_normalise_status()` (`:237-272`). **גם כאן: אין קריאה ל-`Business Outcome` בשום שורה בקובץ.**
4. `_normalise_status()` (`core/adapters/leads_adapter.py:237-272`) — טבלת מיפוי קשיחה:
   ```
   new/חדש/hot/חם/warm/פושר/cold/קר   → DecisionStatus.OPEN
   converted/הומר                      → DecisionStatus.DECIDED_YES
   lost/אבוד                           → DecisionStatus.DECIDED_NO
   cancelled/בוטל                      → DecisionStatus.CANCELLED
   כל ערך אחר (כולל ריק)                → DecisionStatus.OPEN (ברירת מחדל)
   ```
5. `core/reasoning_engines.py::run()` (`:49-120`) מריץ Trust→Confidence→Readiness(stub)→Attention→Orchestrator. `readiness = entity.metadata.get("readiness","")` (`:90`) — **`LeadsAdapter` אף פעם לא ממלא `metadata["readiness"]`**, כך ש-readiness הוא תמיד `""` עבור Lead.
6. `decision_orchestrator.py::orchestrate()` (`:82-261`) — הראוטינג בפועל, לפי סדר-first-match:
   - `status in (DECIDED_YES, DECIDED_NO)` → `phase=DECIDED` (`:106-125`)
   - `status == CANCELLED` → `phase=CLOSED` (`:127-134`)
   - `_is_not_ready(readiness)` (תמיד `False` ל-Lead, כי readiness תמיד `""`) → `BLOCKED`
   - `pending_stakeholders` (תמיד ריק ל-Lead — `LeadsAdapter` לא ממלא stakeholders) → `BLOCKED`
   - `confidence_score < 0.60 and event_records` (יש אירועים) → `phase=REVIEW`, next_step = **"סקור את הראיות הקיימות והחלט אם להמשיך"** (`:183-205`)
   - `_is_review(readiness)` (תמיד `False` ל-Lead) → `REVIEW`
   - `confidence_score >= 0.75 or _is_ready(readiness)` → `phase=AWAITING`, next_step = "קבל את ההחלטה הסופית" (`:225-245`)
   - אחרת (ברירת מחדל — כולל confidence 0.60–0.75 **עם** אירועים, וגם confidence כלשהו **בלי** אירועים) → `phase=COLLECTING`, next_step = **"הוסף ראיות ועדכן אירועים"** (`:247-261`)

**מסקנות עובדתיות (לא הנחות):**

- **`Business Outcome` לא משפיע על `state` היום בשום צורה** — הוא לא נקרא באף שלב בשרשרת הזו. שינוי מ-`open`→`converted` ב-`Business Outcome` בלי שינוי מקביל ב-`status` **לא ישנה את ה-`state` המוקרן בכלל.**
- מתוך 10 ערכי `status` החיים (§2A0 §2), **רק `new` ו-`lost` ממופים בכוונה תחילה** ב-`_normalise_status()`. שאר השמונה (`active, high_confidence, waiting_response, waiting_call, archived, duplicate, not_relevant, done, ליד חדש`) נופלים כולם לברירת המחדל `DecisionStatus.OPEN` — **כולל `done`**, שהוא לפי `tma_api.py::_OUTCOME_STATUS_MAP` (`tma_api.py:1663-1672`) הערך הקנוני ל"הומר" בפועל. כלומר ליד שהומר דרך ה-TMA (`status="done"`) **לא מגיע ל-`phase=DECIDED` היום** — הוא ממשיך להיות מנותב לפי confidence כמו ליד רגיל.
- `missing_evidence`/`REQUIRED_EVIDENCE` (`decision_confidence.py:56-63`) הוא מנגנון שנבנה ל-Decisions (`חוזה`/`שמאות`/`קורות חיים` וכו') ולא ל-Leads — `DOMAIN.GENERAL` נופל ל-`["מסמך תומך"]` (מסמך תומך גנרי). זה boundary condition ידוע של Phase 1 (לא בתחום התיקון כאן), אבל רלוונטי לדוגמה A למטה: "missing_evidence לא 'אין אירועים מקושרים'" — כי בפועל `missing_evidence` כבר לא אומר את זה; הוא אומר משהו כמו "מסמך תומך" חסר, שגם הוא לא מדויק ל-Lead, אך שונה מהחשש המקורי.

---

## 1. Inputs Allowed for Phase 2A.1

| Input | מקור | הערה |
|---|---|---|
| `status` | `Leads.status` (`LeadFields.STATUS`) | כבר נכנס ל-entity היום (§0) |
| `Business Outcome` | `Leads.Business Outcome` (`LeadFields.OUTCOME`) | **לא נכנס ל-entity היום** — זו התוספת המרכזית של Phase 2A.1 |
| `Score` | `Leads.Score` (`LeadFields.SCORE`) | כבר נכנס (passthrough בלבד, §1D — לא קובע state) |
| `domain` | `Leads.domain` (`LeadFields.DOMAIN`) | כבר נכנס (`_canonical_domain`, `core/leads_reasoning_projection.py:186-188`) |
| Lead Events count/evidence | `Lead Events` (linked, נטען ע"י הקורא) | כבר נכנס (`events`/`event_records`) — מזין confidence/missing_evidence בלבד, לא state ישירות |

## 2. Inputs Explicitly Excluded for Now

`tier`, `Next Action`, `Next Followup`, `Domain category`, `Domain risk assessment`, `Domain summary` — תואם ל-Phase 2A.0 §11 ("Fields to Stop Using in Reasoning"). ריקים/לא-אמינים בפועל (Phase 2A.0 §3); שילובם היום היה מזין ל-reasoning ערכים ריקים/מטעים.

---

## 3. Business Outcome Normalization

```python
normalized_outcome = str(raw_business_outcome or "").strip().lower()
```

חל על ערכי Airtable החיים שיש להם רווח-זנב מובנה (`LeadOutcome`, `airtable_schema.py:348-377`) — `.strip()` מנטרל את זה בצד הקריאה **בלי לגעת בסכמת Airtable עצמה** (Phase 2A.0 §7C — "אל תתקן את הרווח בקוד, זה יחזיר את הבאג"; ההבחנה: שם מדובר בשכבת ה-**כתיבה** ל-Airtable, כאן מדובר בשכבת ה-**קריאה/נורמליזציה לצורך reasoning** — אין סתירה, `.strip()` בקריאה בלבד לא כותב כלום בחזרה ל-Airtable).

## 4. Business Outcome Policy

| קטגוריה | ערכים מנורמלים | משמעות |
|---|---|---|
| **terminal positive** | `converted` | ליד נסגר בהצלחה |
| **terminal negative** | `lost`, `not_relevant` | ליד נסגר בלי המרה |
| **terminal administrative** | `duplicate`, `archived` | נסגר מסיבה מנהלתית, לא עסקית |
| **intermediate** | `open`, `needs_followup`, `meeting_scheduled`, `ליד חדש` | ליד עדיין פתוח/בתהליך — לא סוגר |
| **unknown** | כל ערך אחר (כולל מחרוזת ריקה לאחר נורמליזציה) | ראה הערת דיוק למטה |

**הערת דיוק (לא סטייה מהמדיניות שסופקה, רק תיעוד השלכה):** מחרוזת ריקה (`Business Outcome` לא מוזן כלל) נופלת היום ל-"unknown" באותה קטגוריה כמו ערך שגוי/typo — זהו המקרה השכיח ביותר בפועל (Phase 2A.0 §3: ~72/92 רשומות ללא `Business Outcome`). לצורך *observability* (לא לצורך ה-precedence עצמו) ייתכן שכדאי ל-Phase 2A implementation להבחין `missing`/`not_set` מ-`unknown`/`unrecognized_value` באיפיון הפנימי (למשל בשדה `basis`/`reason` בפרויקציה) — **לא** משנה את חלוקת הקטגוריות שהתבקשה, רק מוצע כפירוט יישום פנימי; ראה §9.

## 5. Status Normalization

```python
normalized_status = str(raw_status or "").strip().lower()
```

## 6. Status Policy (canonical mapping, proposed)

`_normalise_status()` הקיים (§0.4) ממפה כמעט את כל ערכי ה-status החיים לברירת מחדל אחת (`OPEN`) — זה בדיוק הפער ש-Phase 2A.1 בא לסגור. מיפוי קנוני מוצע (**operational bucket**, לשימוש כש-Business Outcome אינו terminal — precedence rule C):

| ערך `status` חי | Bucket מוצע | הערה |
|---|---|---|
| `new`, `ליד חדש` | **INTAKE** | ליד חדש, טרם טופל |
| `active`, `waiting_call`, `waiting_response` | **ACTIVE** | בטיפול שוטף |
| `high_confidence` | **ACTIVE_HIGH_SIGNAL** | בטיפול, אך עם אות חוזק נוסף — ראוי ל-state שונה מ-`active` הגנרי (ראה דוגמה D) |
| `done` | **TERMINAL_UNSPECIFIED** | קנוני ל"הומר" ב-`_OUTCOME_STATUS_MAP`, אך אין הבטחה ש-`Business Outcome` תואם בפועל — ראה שאלה פתוחה #11.3 |
| `lost` | **TERMINAL_NEGATIVE** | תואם ישירות ל-Business Outcome `lost` |
| `archived`, `duplicate` | **TERMINAL_ADMINISTRATIVE** | תואם ל-Business Outcome `archived`/`duplicate` |
| `not_relevant` | **TERMINAL_NEGATIVE** | תואם ישירות ל-Business Outcome `not_relevant` |

**חשוב:** זהו bucket "אם אין Business Outcome terminal" בלבד (precedence C). זה **לא** מחליף את ה-`DecisionStatus`/`PHASE_*` הקיימים של ה-Orchestrator — זו שכבת מדיניות ביניים, שה-Implementation Plan (§9) צריך להחליט איך לחבר אליהם (למשל: `TERMINAL_ADMINISTRATIVE` → `PHASE_CLOSED` הקיים? או phase חדש? ראה שאלה פתוחה #11.2).

---

## 7. Precedence (as specified)

| # | כלל | נובע מ- |
|---|---|---|
| A | Business Outcome terminal (positive/negative/administrative) גובר על status | חדש — לא קיים היום (§0: Business Outcome לא נכנס לחישוב כלל) |
| B | Business Outcome intermediate לא סוגר ליד | חדש |
| C | אם אין Business Outcome terminal, status קובע state תפעולי (§6) | מרחיב את ההתנהגות הקיימת (§0.6) — אך עם bucket עשיר יותר מ-`OPEN`/`DECIDED_YES`/`DECIDED_NO`/`CANCELLED` הבינארי-כמעט של היום |
| D | Score לא קובע state | תואם למצב הקיים — `Score` כבר passthrough בלבד (`core/leads_reasoning_projection.py:159`, `SCORE_PRESENT`/`MISSING`/`INVALID` — אף פעם לא `state`) |
| E | Lead Events מעלים confidence/evidence אך לא סוגרים state לבד | תואם למצב הקיים — `event_records` כבר רק קלט ל-`calc_confidence`/REVIEW-threshold, לא branch עצמאי ב-orchestrator |
| F | אין שימוש ב-tier/Next Action/Next Followup ב-Phase 2A.1 | תואם ל-Phase 2A.0 §11 |

---

## 8. Expected Outputs

לכל דוגמה: התנהגות **היום** (as-is, §0) מול **התנהגות מצופה** (המדיניות המוצעת, לאחר Phase 2A code PR עתידי — **לא ממומש כאן**).

### Example A — Business Outcome=`meeting_scheduled`, status=`active`, events.count=2

- **היום:** `Business Outcome` מתעלם לגמרי. `status="active"` → `_normalise_status()` ברירת מחדל → `OPEN`. הענפים הבאים תלויים ב-`confidence_score` שמחושב מ-2 האירועים (לא נגזר כאן — תלוי ב-`decision_confidence.calc_confidence`): אם `<0.60` → `phase=REVIEW`, next_step="סקור את הראיות הקיימות" (**כבר תואם** לציפייה "not terminal"/"next_step לא רק הוסף ראיות"). אך אם `confidence` נופל ב-0.60–0.75 (טווח ביניים, עם אירועים) → **`phase=COLLECTING`, next_step="הוסף ראיות ועדכן אירועים"** — זה בדיוק המקרה שהדוגמה מבקשת למנוע, וקורה היום תלוי-מזל בציון confidence.
- **מצופה (Phase 2A.1 policy):** `Business Outcome=meeting_scheduled` הוא **intermediate** (§4) → כלל B: לא סוגר. `status=active` הוא **ACTIVE** (§6). אין terminal משום צד → הענף הרגיל (confidence-based) ממשיך לרוץ, **אך** ה-Implementation Plan (§9) צריך להבטיח שכש-`Business Outcome` הוא intermediate ולא ריק, ה-next_step/state לא נופל ל-`COLLECTING`/"הוסף ראיות" הגנרי — כי יש כבר סיגנל עסקי קונקרטי (פגישה נקבעה). מוצע: `state=REVIEW` (או תיוג מקביל, ראה שאלה פתוחה #11.1), **לא** terminal, ו-`next_step` ינוסח סביב "אשר/עקוב אחרי הפגישה שנקבעה" ולא "הוסף ראיות" גנרי. **זו נקודת ההחלטה המרכזית שדורשת קוד עתידי** — המדיניות כאן קובעת את הכיוון (לא-terminal, לא-generic-collecting), לא את המימוש המדויק.

### Example B — Business Outcome=`converted`, status=`active`/`new`/anything

- **היום:** `Business Outcome` מתעלם. אלא אם `status` עצמו הוא `"converted"`/`"הומר"` (ואף אחד מהם אינו ערך חי אמיתי — §2A0 קבע ש-`"converted"` הוא כתיבה לא-קנונית שלא אמורה להתרחש, והערך הקנוני האמיתי הוא `"done"`, שגם הוא לא ממופה!) — **התוצאה בפועל: `phase` לעולם לא `DECIDED` עבור Business Outcome=converted, ללא תלות ב-status.**
- **מצופה:** כלל A — `converted` הוא **terminal positive** → גובר על status לחלוטין. `state` = terminal-positive (מוצע: `PHASE_DECIDED` הקיים — ראה §11.1), `next_step` לא מבקש עוד ראיות/מעקב — misson accomplished. **זו התוספת המרכזית ביותר של Phase 2A.1**: ליד עם `Business Outcome=converted` צריך להיסגר ב-reasoning ללא קשר לכל שילוב status.

### Example C — Business Outcome=`lost`/`not_relevant`

- **היום:** מתעלם. `status` צריך להיות `"lost"`/`"אבוד"` בדיוק כדי ש-`phase=DECIDED` (current_state "הוחלט — לא") יתרחש — ואם `status` הוא כל דבר אחר (למשל `active` בזמן שה-Business Outcome כבר `lost`) הליד ימשיך להיראות "פתוח" ב-reasoning.
- **מצופה:** כלל A — `lost`/`not_relevant` הם **terminal negative** → סוגר ללא תלות ב-status. `next_step` לא מבקש מעקב גנרי (אין טעם לעקוב אחרי ליד שאבד/לא רלוונטי).

### Example D — Business Outcome ריק, status=`high_confidence`, events.count=0

- **היום:** `status="high_confidence"` → ברירת מחדל `_normalise_status()` → `OPEN` (**זהה** לכל status לא-ממופה אחר — אין הבחנה בין `high_confidence` ל-`active`/`waiting_call` וכו'). עם 0 אירועים: `confidence_score<0.60 and event_records` נכשל (`event_records` ריק=falsy) → נופל לברירת המחדל → `phase=COLLECTING`, next_step="הוסף ראיות ועדכן אירועים" — **מתעלם לגמרי מהעובדה שהצוות כבר סימן `high_confidence` ידנית.**
- **מצופה:** Business Outcome ריק/unknown → אין terminal מ-כלל A. כלל C — status קובע state תפעולי: `high_confidence` → bucket **ACTIVE_HIGH_SIGNAL** (§6, שונה מ-`active` הגנרי). ה-state המוקרן אמור לשקף review/high-confidence תפעולי (לא COLLECTING הגנרי), ו-`missing_evidence` יכול עדיין לציין חוסר אירועים (`events.count=0`) כעובדה, **אבל בלי לגרום ל-state "לדרוס" את סימון ה-status הידני** — כלומר ה-projection לא כותב בחזרה ל-Airtable (Phase 1 read-only, כבר מובטח מבנית — `core/leads_reasoning_projection.py`'s hard boundaries, §1 בקובץ עצמו) וגם לא "מתעלם" מהסימון ברמת הקריאה.

---

## 9. Implementation Plan for Future Code PR (לאחר אישור)

*מותנה באישור owner על §4/§6/§7/§11 — לא מתחיל אוטומטית מ-SPEC זה.*

1. **היכן להוסיף את הנורמליזציה:** מוצע `core/leads_reasoning_projection.py` (לא `LeadsAdapter` עצמו) — משום שזה כבר המקום שמבצע נורמליזציית live→adapter (`_LIVE_TO_ADAPTER_FIELDS`, `_normalize_lead_snapshot`) ושומר על "pure, no adapter refactor" (התיעוד העצמי של הקובץ, `:67-70`). להוסיף `("Business Outcome", ...)` לרשימת השדות המנורמלים ופונקציית `_normalize_business_outcome()`/`_normalize_status_bucket()` חדשות באותו סגנון כמו `_normalize_lead_score()` הקיים (`:278-300`) — honest, לעולם לא ממציא ערך.
2. **האם להרחיב את ה-entity של `LeadsAdapter`:** כן, בזהירות — `ReasoningEntity.metadata` (`core/reasoning_entity.py:89-101`) הוא ה-extension point המיועד ("Adapter-specific extras"), לא שדה חדש ב-dataclass המשותף. מוצע: `entity.metadata["business_outcome_bucket"]` + `entity.metadata["status_bucket"]`, ואז **`LeadsAdapter._normalise_status()` עצמו** (או פונקציה חדשה לצידו) קובעת את `entity.status` הסופי (`DecisionStatus.*`) לפי כלל A/B/C — לא ה-Orchestrator (שהוא domain-agnostic, DecisionStatus-only, ולא אמור לדעת על "Business Outcome" של Lead).
3. **האם ה-projection צריכה להעביר Business Outcome:** כן — `build_reasoning_projection()` צריך להוסיף `"business_outcome"` (raw + normalized + bucket) לפלט ה-JSON, באותו סגנון honest-state כמו `lead_score`/`verifier` הקיימים (ערך + state + source, לא ערך גולמי בלבד) — כדי שה-TMA/כל צרכן אחר יראה גם את הקלט הגולמי וגם את הפרשנות, לא black box.
4. **בדיקות מינימליות:** ראה §10.
5. **אין הרחבת response contract ללא אישור** — `PROJECTION_VERSION` (`core/leads_reasoning_projection.py:38`) נשאר `1` אלא אם הוחלט אחרת מפורשות; אם נוסף מפתח `"business_outcome"` לתשובה, זו תוספת non-breaking (מפתח חדש, לא שינוי מפתח קיים) — לשקול אם זה עדיין דורש bump גרסה לפי המדיניות הקיימת בקובץ ("bump only on a breaking projection-shape change") — תוספת שדה כנראה **אינה** breaking, אך יש לאשר את הפרשנות הזו מול owner לפני המימוש.

## 10. Tests for Future Code PR

- **terminal positive** — `Business Outcome="converted "` (עם/בלי רווח-זנב, אחרי `.strip().lower()`) + status כלשהו → `state`=terminal-positive, `next_step` לא מבקש ראיות/מעקב.
- **terminal negative** — `Business Outcome="lost "`/`"not_relevant "` + status כלשהו → terminal-negative, לא next_step גנרי.
- **administrative terminal** — `Business Outcome="duplicate "`/`"archived"` → terminal-administrative, מובחן מ-terminal positive/negative.
- **intermediate outcome** — `Business Outcome="meeting_scheduled "`/`"needs_followup "`/`"open "`/`"ליד חדש"` → לא סוגר, ממשיך לענף confidence-based.
- **status-only fallback** — `Business Outcome` ריק/unknown, status מכל אחד מ-10 הערכים החיים → bucket מ-§6 מוחזר נכון, אין terminal מלאכותי.
- **score does not become confidence** — `Score=98` עם `Business Outcome` ריק ו-0 אירועים → `state` לא `AWAITING`/`DECIDED` רק בגלל Score גבוה (regression guard על כלל D).
- **events count affects evidence only** — מספר אירועים משתנה (0/1/50) לא משנה `state` ישירות כשיש Business Outcome terminal (כלל A גובר על E).
- **excluded fields ignored** — הזרקת ערכים מלאכותיים ל-`tier`/`Next Action`/`Domain category` וכו' בקלט ל-`build_reasoning_projection()` לא משנה את הפלט כלל (regression guard על §2/כלל F).

---

## 11. Open Questions

1. **שמות enum ציבוריים מדויקים ל-state המוקרן** — האם לעשות reuse ל-`PHASE_DECIDED`/`PHASE_REVIEW`/`PHASE_AWAITING`/`PHASE_COLLECTING`/`PHASE_CLOSED` הקיימים (`core/reasoning_entity.py:34-39`, כבר בשימוש היום כ-`result.phase`), או להוסיף ערכים ייעודיים ל-Lead (למשל `LEAD_CONVERTED`/`LEAD_LOST`)? Reuse שומר על עקביות עם Decisions אך מטשטש את ההבדל הסמנטי בין "הוחלט" (Decision) ל"הומר" (Lead); ערכים ייעודיים מוסיפים סיווג אך שוברים את ה-"state"=`result.phase` הפשוט הקיים.
2. **Terminal administrative → `PHASE_CLOSED` הקיים או phase נפרד?** `PHASE_CLOSED` היום משמש רק ל-`DecisionStatus.CANCELLED` (Decision "בוטל"). אימוץ אותו ל-`duplicate`/`archived` של Lead עלול לבלבל צרכנים שכבר מכירים `CLOSED`="בוטל" כ-Decision. לחלופין: `ARCHIVED`/`DUPLICATE` כ-phase-ים חדשים.
3. **האם `status=done` אמור להשתמע כ-"הומר" כש-`Business Outcome` ריק?** (§6, bucket `TERMINAL_UNSPECIFIED`) — `done` הוא הערך הקנוני ל"הומר" ב-`_OUTCOME_STATUS_MAP` (`tma_api.py:1667`), אך תיאורטית אפשר שליד יגיע ל-`done` בלי ש-`Business Outcome` עודכן בפועל (למשל race/עדכון חלקי). לקבוע: `done` בלי Business Outcome → treat as converted, או → treat as "terminal, לא ידוע איזה סוג" (state נפרד, לא positive/negative)?
4. **האם לתקן את שני כותבי ה-`status="converted"` הלא-קנוניים (`lead_conversion.py:94`, `ad_attribution.py:195`, Phase 2A.0 §5/§7B) לפני או במסגרת Phase 2A.1 code PR?** אם לא מתוקנים, ליד שעבר דרך הנתיבים האלה יגיע ל-`status="converted"` (לא ב-`LeadStatus.ALL`, לא ב-bucket §6 בכלל) — צריך fallback honest (`unknown` bucket, לא crash) עד שהתיקון עצמו יבוצע.
