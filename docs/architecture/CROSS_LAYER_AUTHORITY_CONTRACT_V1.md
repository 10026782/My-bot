# CROSS_LAYER_AUTHORITY_CONTRACT_V1.md

**סטטוס:** MANDATORY GATE — חוסם כל planning/implementation שנוגע באחת מ-4 השכבות למטה, ללא Cross-Layer Impact Matrix מלא.
**מקור:** נוצר בעקבות הבקשה לאשר את `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` — זוהה הצורך בשער חוצה-שכבות *לפני* שאישור כזה ניתן, לא רק בשביל TurnCoordinator עצמו.
**מי כפוף לזה:** כל מחקר, מסקנה, מימוש, bug fix, או PR שנוגע — ישירות או בעקיפין — באחת מ-4 השכבות ב-§1. "נוגע בעקיפין" כולל: שינוי contract/schema/flag/identifier ששכבה אחרת קוראת אותו, לא רק קריאה ישירה לפונקציה בשכבה האחרת.

---

## 0. הכלל המחייב (Mandatory Rule)

> אף מחקר, החלטת-מימוש, תיקון-באג, או PR שנוגעים באחת מ-4 השכבות ב-§1 לא רשאים להתקדם ללא **Cross-Layer Impact Matrix** (§3) שממלא את כל 4 השכבות — כולל השכבות שה-PR "לא נוגע בהן".

**אם שינוי טוען שרק שכבה אחת מושפעת — הוא חייב להוכיח במפורש ש-3 החוזים האחרים נשארים ללא שינוי (§6), לא רק להצהיר את זה.**

**ללא Cross-Layer Impact Matrix מלא:**

```
STATUS = PLANNING BLOCKED
```

אסור: קוד runtime, PR מימוש, או סטטוס "תוקן"/"✅ Fixed" — עד שה-matrix הושלם ותועד.

---

## 1. ארבע השכבות הסמכותיות (כפי שהן קיימות היום — מבוסס grep, לא הנחה)

כל שכבה: מה היא **אמורה** לבעול (per היעד הארכיטקטוני) מול מה היא **בפועל** בעולה היום (עם gap מפורש כשיש).

### שכבה 1 — Core Reasoning / BUG-104

**בעלות (יעד):** business state, evidence, phase, confidence, recommended next step.

**מציאות היום:** Phase 1 בלבד — projection **read-only** על מצב Leads (`core/leads_reasoning_projection.py`), מחובר ל-`GET /api/leads/<lead_id>`, מאחורי flag תלת-מצבי `FEATURE_CORE_REASONING_LEADS_STATE` (off/shadow/on, **ברירת מחדל off**). המודולים `core/reasoning_entity.py`/`core/reasoning_engines.py` קדמו ל-BUG-104 עצמו (שם היסטורי F22/"Core Reasoning Layer"). **Scope מוצהר: Leads בלבד, לא Understanding Layer כללי** — הרחבה לכל תחומי העסק (U1) היא החלטה ארכיטקטונית נפרדת, עדיין פתוחה (`CHANGE_CONTROL_LOG.md`). Phase 2A.0/2A.1 הם SPECs בלבד, ללא קוד runtime, ממתינים לאישור בעלים.

**Gap:** "owns business state/evidence/phase/confidence" הוא היעד — המימוש בפועל הוא projection צר, flag-כבוי כברירת מחדל, תחום Leads בלבד.

### שכבה 2 — TurnCoordinator

**בעלות (יעד):** turn precedence, `selected_handler`, `reply_owner`, ניתוב turn-scoped.

**מציאות היום:** **אין מימוש כלל** — `grep -rl "class TurnCoordinator"` מחזיר אפס קבצים. `core/turn_envelope.py` הוא "Phase 0: observation only" — hooks ב-`app.py`/`tma_api.py`/`followup_engine.py`/`core/lead_recovery.py` שרושמים ללוג בלבד, **ללא השפעה על ניתוב בפועל**. החוזה עצמו קפוא ב-`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`, **ממתין לאישור** (ולכעת — גם ל-Cross-Layer Impact Matrix לפי המסמך הזה).

**מי בפועל ממלא את התפקיד היום:** `core/router/router.py::route_request()` (החלטת ניתוב/`Handler`, `route_decision.py:135`) + `core/lead_candidate_handler.py::handle_lead_candidate()` (קדימות capture-flow, בעלות-תשובה לזרימות ליד). אלה הבעלים ה-de-facto של מה ש-TurnCoordinator אמור להפוך לפורמלי.

### שכבה 3 — F52 / Phase 4C Action & Tool Contract layer

**בעלות (יעד):** הגדרות פעולה, capabilities, policy, מיפוי handler/tool, approval class, result contract, דרישות execution evidence.

**מציאות היום:** F52 = תוכנית "Unified Approval Runtime Migration and Implementation". Phase 4C = audit של מצב-קיים בתוך F52 (`docs/architecture/f52-unified-approval-runtime/audits/phase-4c/CURRENT_STATE_MAP.md`), לא תוכנית נפרדת. **חלקים ממומשים בפועל:** `ToolMeta` (`tool_registry.py:39-49` — `roles_allowed`/`tenant_scoped`/`requires_approval`/`high_risk`/`read_only`/`model_exposed` = capability+policy), `tools/schemas.py` (הגדרות פעולה), `tools/dispatcher.py::dispatch_tool()` (מיפוי handler/tool), חוזה-התוצאה של C53a `{ok, tool, external_id, evidence, user_message}` (result contract + execution evidence). ה-unification העצמי של F52 (`compose_status_reply()`, `FEATURE_UNIFIED_STATUS_FORMATTER`) flag-כבוי כברירת מחדל — Stage 1 (audit/shadow) שוגר, המיגרציה המלאה עדיין ב-shadow/בתהליך.

### שכבה 4 — Durable Atomic Approval layer

**בעלות (יעד):** מחזור חיים של `ActionContract`, atomic claim, ביצוע יחיד, סטטוס קנוני, `ExecutionReceipt`.

**מציאות היום:** `ActionContract` (`core/action_gateway.py:136`, שדה `status` — ליטרל `draft|pending|approved|rejected|completed|failed|outcome_unknown`), `ActionContractRepository` (`core/action_contract_repository.py:167`), `ActionGateway.propose_action()` (`:811`), atomic claim דרך `execute_with_atomic_claim()` (`core/action_gateway_atomic_executor.py`, נקרא מ-`:1861`). `FEATURE_ACTION_GATEWAY`/`FEATURE_ATOMIC_CLAIMS` שני הדגלים **כבויים כברירת מחדל** — התשתית code-complete, לא live במלואה.

**⚠️ ממצא-אזהרה שנתגלה תוך כדי כתיבת המסמך הזה — ראה §4 לדוגמה מלאה:** `"ExecutionReceipt"` **אינו מחלקה קיימת** בשום מקום בקוד — קיים רק כמונח מושגי בהערה (`action_gateway.py:4`: "ExecutionReceipt הוא ההוכחה היחידה לביצוע") וב-`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`'s §6. **יש כן `class ActionFact` אמיתית** (`action_gateway.py:241`) — אבל היא דבר **אחר לגמרי**: struct צר, scoped לקריאת-tool בודדת (`tool_name`/`contract_id`/`outcome`/`record_id`/`error_code`/`raw_tool_response`), משמש לבניית `GatewayReply` דרך `compose_status_reply()` — **לא** הרשומה העמידה חוצת-turn שתיאור ה-TurnCoordinator contract מתכוון אליה כש-הוא כותב "`ActionFact`/`ExecutionReceipt`".

---

## 2. Cross-Layer Impact Matrix — שדות חובה לכל שכבה

לכל אחת מ-4 השכבות ב-§1, כל שינוי (מחקר/מימוש/תיקון/PR) חייב למלא את כל 9 השדות הבאים — כולל שכבות שהשינוי "לא נוגע בהן" (שם התשובה יכולה להיות "לא נוגע", אבל **חייבת** להיות מפורשת, לא שורה חסרה):

| שדה | מה נדרש |
|---|---|
| **touched directly/indirectly** | האם קוד/schema/flag/identifier של השכבה הזו שונה ישירות, נקרא/נצרך בעקיפין ע"י השינוי, או לא נוגע בכלל |
| **input impact** | אילו signals/נתונים נכנסים לשכבה הזו משתנים (טיפוס, מקור, סמנטיקה) |
| **output impact** | אילו signals/נתונים יוצאים מהשכבה הזו משתנים, ומי צורך אותם בשכבות אחרות |
| **authority impact** | האם הבעלות/סמכות-ההחלטה של השכבה הזו (מה מותר לה להכריע) משתנה |
| **shared identifiers** | אילו שמות/מזהים (class names, field names, table names, flag names) חוצים את גבול השכבה הזו לשכבה אחרת — ואם יש התנגשות (ראה §4 לדוגמה אמיתית) |
| **invariants** | אילו הנחות-ברזל קיימות של השכבה (למשל BUG-094's exact-phone match) עדיין מתקיימות, ואילו נפרצות |
| **failure semantics** | מה קורה כשהשכבה הזו נכשלת אחרי השינוי — fail-open/fail-safe, ולמי (ראה TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md §7 לדוגמת-מבנה) |
| **observability** | אילו logs/audit entries/metrics חדשים או שהשתנו קיימים כדי לאמת בפועל (לא רק "אמור לעבוד") את ההשפעה על השכבה הזו |
| **cross-layer tests** | אילו טסטים קיימים/נוספו שמוודאים שהחוזה **בין** השכבה הזו לשכבות האחרות (לא רק בתוך שכבה אחת) עדיין מחזיק |

**תבנית למילוי (להעתקה ישירה ל-PR/מסמך):**

```text
## Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: [directly | indirectly | not touched]
input impact:
output impact:
authority impact:
shared identifiers:
invariants:
failure semantics:
observability:
cross-layer tests:

### שכבה 2 — TurnCoordinator
touched: [directly | indirectly | not touched]
...(same 8 fields)

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: [directly | indirectly | not touched]
...(same 8 fields)

### שכבה 4 — Durable Atomic Approval
touched: [directly | indirectly | not touched]
...(same 8 fields)

### Proof of non-impact (חובה לכל שכבה עם touched=not touched)
[ראה §6 — grep evidence + unchanged-tests evidence, לא הצהרה בלבד]
```

---

## 3. דוגמה מלאה, אמיתית — למה השער הזה קיים (לא תיאורטי)

תוך כדי כתיבת המסמך הזה עצמו (§1, שכבה 4) התגלה **collision אמיתי, קיים כרגע בריפו**:

- `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §6 משתמש ב-"`ActionFact`/`ExecutionReceipt`" כמושג ל**רשומה עמידה חוצת-turn** (שמאפשרת לענות "מה עשית עכשיו" בטורן מאוחר יותר).
- אבל `core/action_gateway.py:241` **כבר מגדיר `class ActionFact`** — struct **שונה לגמרי**: scoped לקריאת-tool בודדת בתוך turn, לא עמיד חוצה-turns, ומשמש למטרה אחרת (בניית `GatewayReply` דרך `compose_status_reply()`).

**אילו היה Cross-Layer Impact Matrix קיים בזמן כתיבת ה-TurnCoordinator contract**, שדה "shared identifiers" של שכבה 4 היה **חובה** לזהות את זה — לפני שהמונח "`ActionFact`" נכתב 3 פעמים במסמך חוזה קפוא, לא אחרי.

**Action item פתוח (לא מומש כאן — מחוץ לסקופ של המסמך הזה עצמו):** `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §6 צריך שם אחר לרשומה העמידה שהוא מתאר (למשל `TurnResultFact`/`DurableTurnReceipt`) לפני שכל מימוש שלב 4 (§6 בחוזה) מתחיל — אחרת מימוש עתידי עלול בטעות לנסות "להרחיב" את ה-`ActionFact` הקיים (שכבה 4) לתפקיד שהוא לא תוכנן אליו, או ליצור שני מושגים בשם זהה בשתי שכבות שונות.

---

## 4. איסורים מפורשים (Explicit Prohibitions)

השינויים/דפוסים הבאים **אסורים** ללא קשר לשאלה אם ה-matrix מולא — מילוי matrix אינו הופך אותם למותרים, הוא רק **מזהה** אותם לפני שהם קורים:

1. **מקורות-אמת מקבילים (parallel sources of truth)** — שתי שכבות (או שני מודולים בתוך אותה שכבה) שכל אחת "יודעת" עצמאית מה הסטטוס האמיתי של אותה ישות/פעולה, בלי אחת מהן מוגדרת כ-source of truth היחיד.
2. **מדיניות משוכפלת (duplicated policy)** — אותו כלל-הרשאה/אישור ממומש פעמיים בשני מקומות (למשל: אכיפת role גם ב-router וגם שוב, שונה במקצת, בתוך handler) — ראה `tool_registry.enforce()` מול `action_validator.validate_action()` כדוגמה **למותר** (שני gates *מכוונים*, מתועדים כ-"defense in depth" — ההבדל הוא כוונה מתועדת מול שכפול-בטעות).
3. **הכרעת create/update/delete בתוך capture flows** — capture flow רשאי לחלץ payload, **לא** לקבוע איזו פעולה (create/update/delete) תבוצע כשיש כוונה עסקית מפורשת (ראה BUG-130, `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §3.1).
4. **תביעת אישור בלי `ActionContract` קנוני** — כל "אישור ממתין" חייב `active_queue_id`/`contract_id` תקף במאגר (שכבה 4) — ראה phantom-approval incident, `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §7/תרחיש 11.
5. **ביצוע בלי `TurnDecision` + הרשאת-policy** — שום handler לא מבצע tool/write בלי `TurnDecision` (שכבה 2) שמצביע עליו במפורש **וגם** אישור-policy מהתשתית של שכבה 3 (`ToolMeta`/`action_validator`) — היעדר אחד מהשניים מספיק לחסימה.
6. **Core Reasoning מבצע פעולות** — שכבה 1 (BUG-104) קוראת/מחשבת state, evidence, phase, confidence — היא **אף פעם** לא הבעלים של ביצוע tool/write. אם קוד Core Reasoning קורא ל-dispatcher/tool ישירות, זו הפרת-שכבה.
7. **TurnCoordinator ממציא business state או approval policy** — שכבה 2 קובעת ניתוב/בעלות-תשובה, **לא** מחליטה מהו "מצב עסקי נכון" (זו שכבה 1) ולא ממציאה כללי-אישור משלה (זו שכבה 3/4). אם TurnCoordinator מתחיל "לנחש" confidence/phase, זו הפרת-גבול.
8. **תשובות/תוצאות לא-מקושרות בלי `turn_id` וראיית-ביצוע** — כל תשובה/tool_result חייב `turn_id` (שכבה 2, §6 ב-TurnCoordinator contract) **וגם** evidence-of-execution תואם (שכבה 3/4 — C53a contract / `ActionFact`/`ExecutionReceipt`) — אחד בלי השני אסור.

---

## 5. Proof of Non-Impact — מה נחשב "הוכחה", לא הצהרה

כשמשבצת "touched: not touched" נבחרת לשכבה כלשהי, ה-PR/מסמך חייב לצרף **לפחות** את שלושת אלה — לא רק את המילה "לא נוגע":

1. **grep evidence** — פקודת grep (או תוצאתה) שמראה ששום identifier/field/table/flag ששייך לשכבה הזו לא הופיע ב-diff.
2. **unchanged-tests evidence** — הרצה של סוויטת הטסטים הקיימת של השכבה הזו (אם קיימת) **לפני ואחרי** השינוי, עם תוצאה זהה — לא רק "לא הרצתי כי לא אמור להיות רלוונטי".
3. **no-new-coupling evidence** — אין import חדש ממודול בשכבה זו למודול שהשינוי נגע בו (או אם יש — הוא מתועד ומוצדק, לא side-effect לא-מכוון).

בלי שלושת אלה — "לא נוגע" הוא claim לא-מאומת, ומפר את אותו "כלל ברזל" (`CLAUDE.md`) שחל על כל claim אחר בריפו הזה.

---

## 6. אכיפה

```
STATUS = PLANNING BLOCKED
```

עד שה-Cross-Layer Impact Matrix (§2) הושלם במלואו (4 שכבות × 9 שדות, כולל proof-of-non-impact לכל שכבה שמסומנת "לא נוגע") — אין:
- קוד runtime חדש הנוגע לאחת מ-4 השכבות,
- PR מימוש שממזג שינוי לאחת מ-4 השכבות,
- הצהרת "תוקן"/"✅ Fixed"/"מוכן לאכיפה" על עבודה שנוגעת לאחת מ-4 השכבות.

---

## 7. איפה השער הזה חייב להיות מוזכר (מחייב)

- `CLAUDE.md` — סעיף "Planning & docs conventions" — הפניה תמציתית (ראה עדכון מלווה).
- `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` — הפניה מפורשת בכותרת: אישור סופי של אותו מסמך חוזה **תלוי** ב-Cross-Layer Impact Matrix מלא (ראה עדכון מלווה).
- **כל** מסמך Planning Gate עתידי שנוגע ב-reasoning, routing, tools/actions, approvals, או execution — חייב לפתוח בהפניה מפורשת למסמך הזה ולא להתקדם בלי Impact Matrix מלא, באותו אופן בדיוק כמו `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`. זה כלל עומד (standing rule) — לא נדרש לעדכן את המסמך הזה שוב בכל פעם שנוצר Planning Gate חדש; זו אחריות המסמך **החדש** להפנות לכאן.
