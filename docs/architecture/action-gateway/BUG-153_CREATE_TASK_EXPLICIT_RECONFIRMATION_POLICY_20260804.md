# BUG-153 — Deterministic Create-Task Explicit Reconfirmation Policy

**תאריך:** 04/08/2026
**שער מחייב:** מסמך זה נכתב לפי `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` —
כל מסמך Planning Gate הנוגע ב-routing/tools/actions/approvals חייב לפתוח בהפניה
מפורשת לשער הזה (§7 שם). Cross-Layer Impact Matrix מלא ב-§4 למטה.
**מעדכן/מספק את החסר ב:** `docs/architecture/action-gateway/DETERMINISTIC_TASK_ROUTING_AND_REPLAY_POLICY_20260802.md`'s
המשפט "An explicit retry of the same rejected identity would require a
separately approved reconfirmation policy" — זהו אותו policy, מוגדר ומאושר כאן.

## 1. הבעיה שדווחה (BUG-153, staging 03/08/2026)

לאחר rejection של פעולת create_task, שליחה חדשה ומפורשת של אותה בקשה (אותו
title/due_date/due_time — אותו fingerprint) נחסמה שוב ושוב עם "יצירת המשימה
כבר בוטלה". המשתמש לא יכול היה ליצור מחדש פעולה שביטל בטעות, או לשנות דעתו.

## 2. הקונפליקט עם התיעוד הקיים (למה זה לא "רק תיקון קוד")

`DETERMINISTIC_TASK_ROUTING_AND_REPLAY_POLICY_20260802.md` (מוזג עם PR #546
עצמו, יום לפני דוח ה-staging) קובע במפורש: "An exact canonical business
action that reached rejected remains rejected on replay... An explicit retry
of the same rejected identity would require a **separately approved
reconfirmation policy**; it must not weaken fingerprint deduplication."

כלומר: ה-blocking הקיים הוא **החלטת עיצוב מכוונת**, לא תקלה. הפער האמיתי הוא
שאותה "reconfirmation policy" שהמסמך מתאר כתנאי-מוקדם — **מעולם לא עוצבה
ואושרה בפועל**. זה בדיוק מה שמסמך זה עושה.

## 3. העיצוב

### 3.1 מה נשאר ללא שינוי (הגנות שלא זזות)

- **Autonomous replay נשאר חסום ללא תנאי.** כל proposal שמקורו ב-Agent
  tool_use loop הגולמי (`trusted_source == "agent"`) ומכוון לאותו fingerprint
  שכבר `rejected` — ממשיך להיחסם בדיוק כמו היום. שום דבר במסמך הזה לא מרפה
  את ה-guard הזה.
- **ה-fingerprint עצמו לא משתנה.** לא מוצע כאן שום נרמול/hashing חדש. אותה
  זהות עסקית (title+due_date+due_time מנורמלים) ממשיכה להפיק את אותו hash.
- **ה-contract הישן (`rejected`) לעולם לא נמחק/נכתב-מחדש.** נשאר terminal,
  ניתן-לאחזור דרך `contract_id` שלו, ולא ניתן ל-reconfirm/execute.
- **דדופ בתוך אותו turn (BUG-122's live-contract boundary) לא נוגע.** אם
  יש כבר contract חי (`pending`/`approved`/...), אף אחד מהמסלולים לא עוקף
  את זה — הבדיקה הזו (`propose_action()` שורה 1421-1453) קודמת ל-branch
  הזה ונשארת בדיוק כמו שהיא.

### 3.2 מה מתאפשר (ה-carve-out המצומצם)

בקשת **create_task דטרמיניסטית** בלבד — כלומר בקשה שעברה דרך
`core/router/router.py::parse_deterministic_create_task()` והתאימה
ל-grammar המובנה ("צור משימה...") ב-turn הזה, **מעולם לא דרך ה-Agent
tool_use loop** (`agent_calls=0` מאומת, ראה `DETERMINISTIC_TASK_ROUTING_AND_
REPLAY_POLICY_20260802.md`) — רשאית לפתוח contract **חדש** גם כשקיים כבר
contract עם אותו fingerprint במצב `rejected`.

**למה זה בטוח ולא "מחליש דדופ", כנדרש במפורש במסמך המקורי:**

1. **מוגן כבר ע"י idempotency guard במעלה הזרימה.** `app.py:5247`
   (`idempotency.is_duplicate("telegram", sender_user_id, f"{update_id}:{message_id}")`)
   מסנן redelivery מכני של אותו webhook update **לפני** ש-`route_request()`
   בכלל נקרא. `_queue_deterministic_create_task()` לכן מובטח להיקרא רק
   כתוצאה של הודעה נכנסת **חדשה וממשית** מהמשתמש — לא replay טכני.
2. **המסלול הדטרמיניסטי לא יכול "להחליט" לבד לחזור על עצמו.** בניגוד
   ל-Agent tool_use loop (שיכול, מתוך המשך-שיחה או halucination, להציע שוב
   tool call בלי קלט חדש מפורש) — הקוד הדטרמיניסטי הוא regex match ישיר על
   הטקסט הנכנס של ה-turn הנוכחי בלבד. אין שום מנגנון retry/loop פנימי
   שמפעיל אותו שוב מבלי טקסט נכנס חדש.
3. **ה-fingerprint עצמו לא נחלש** — אותו fingerprint עדיין מזהה את אותה
   זהות עסקית, ועדיין חוסם duplicate תוך כדי `pending`. הcarve-out נוגע
   **רק** בשאלה "האם מותר לפתוח contract *חדש* אחרי rejection", לא בזיהוי
   הזהות עצמה.
4. **מצומצם ל-signal קיים, לא flag חדש.** `trusted_source` הוא כבר המנגנון
   הרשמי (BUG-091) להבחין מקור-proposal — ערך חדש (`"deterministic_create_task"`)
   מתווסף לרשימה הקיימת (`"agent"`, `"lead_capture"`, `"tma_api"`,
   `"followup_engine"`, ...), מועבר אך ורק ע"י `_queue_deterministic_create_task()`
   — Python קוד מהימן, לעולם לא נגזר מ-tool_inputs/טקסט משתמש.

### 3.3 מה **לא** כלול (scope מוצהר)

- `_queue_deterministic_task_update()` (UPDATE_TASK/COMPLETE_TASK) **לא**
  משתתף ב-carve-out הזה — נשאר `trusted_source="agent"` כברירת מחדל,
  ללא שינוי התנהגות. הבאג המדווח עוסק ב-create_task בלבד; אין ראיה
  מ-staging שאותה בעיה קיימת שם, ואין סיבה להרחיב שינוי לא-נבדק.
- `lead_capture`/`tma_api`/`followup_engine` וכל trusted_source אחר —
  ללא שינוי. ה-branch החדש ב-`propose_action()` בודק שוויון מדויק ל-מחרוזת
  `"deterministic_create_task"` בלבד, לא "כל non-agent source".

## 4. Cross-Layer Impact Matrix

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
input/output/authority impact: אין
shared identifiers: אין
invariants: לא רלוונטי
failure semantics: לא רלוונטי
observability: לא רלוונטי
cross-layer tests: `grep -n "leads_reasoning_projection\|BUG-104" <diff>` — 0 תוצאות

### שכבה 2 — TurnCoordinator
touched: indirectly
input impact: אין שינוי ל-`route_request()`/`parse_deterministic_create_task()` עצמם
output impact: `RouteDecision` הנוצר ע"י router.py לא משתנה
authority impact: אין — ה-router עדיין קובע `Handler.TOOL` בדיוק כמו היום; מה שמשתנה הוא רק מה ש-`_queue_deterministic_create_task()` (הצרכן ב-app.py) מעביר הלאה כ-`trusted_source`
shared identifiers: `trusted_source="deterministic_create_task"` הוא identifier חדש שמצטט את המקור (הroute הדטרמיניסטי), לא מגדיר-מחדש שום שם קיים בשכבה 2
invariants: `agent_calls=0` לבקשת create_task דטרמיניסטית — נשאר ללא שינוי (שום קריאת Agent לא נוספת)
failure semantics: ללא שינוי
observability: `logger.info` חדש ב-`propose_action()` כשה-carve-out מופעל (contract_id ישן + fingerprint + user) — נראות מלאה לכל הפעלה
cross-layer tests: `core/router/test_router.py` הורץ ללא שינוי (לא נוגע בקובץ הזה כלל)

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly
input impact: אין שינוי ל-`ToolMeta`/`tools/schemas.py`/`tools/dispatcher.py`
output impact: אין שינוי לחוזה C53a
authority impact: אין — policy/capability של tool_registry לא נוגע; `classify_approval_policy()`/BUG-076/BUG-077 הגנות נשארות זהות (ממשיכות לרוץ אחרי ה-branch הזה, ללא שינוי)
shared identifiers: `trusted_source` כבר מוגדר ונצרך בשכבה הזו (`dispatch_tool(trusted_source=...)`) — לא שם חדש, ערך חדש בלבד
invariants: ה-approval_policy classification (BUG-076) עדיין מחושב מה-payload בפועל, לא מ-trusted_source
failure semantics: ללא שינוי
observability: ראה שכבה 2
cross-layer tests: `test_bug091_source_trust_boundary.py` (הסבת trusted_source הקיימת) הורץ ללא שינוי בהתנהגות — ראה §5

### שכבה 4 — Durable Atomic Approval
touched: directly
input impact: `propose_action()` מקבל אותה חתימה בדיוק (trusted_source כבר פרמטר קיים) — רק ערך חדש אפשרי
output impact: כש-carve-out מופעל — `GatewayResult(ok=True, contract_id=<NEW uuid4>)` במקום `GatewayResult(ok=False, reason="business action already rejected")`. ה-contract הישן (`existing`) **אינו** נגע — `status` שלו נשאר `"rejected"`, `contract_id` שלו נשאר תקף לאחזור נפרד. `_by_fingerprint` index מתעדכן לכוון ל-contract החדש (כפי שכבר קורה בכל `save()` — לא לוגיקה חדשה, ראה `_cache_contract()` שורה 580)
authority impact: אין הרחבת סמכות — `requires_approval`/`approval_policy` מחושבים מהתוכן בפועל, בדיוק כמו לכל proposal חדש; owner עדיין צריך לאשר את ה-contract החדש
shared identifiers: אין שימוש-חוזר בזהות קיימת (§4 איסור #9 ב-Cross-Layer doc) — `trusted_source="deterministic_create_task"` הוא ערך חדש, לא הגדרה-מחדש של קיים
invariants: **הבטחה קריטית שנשמרת** — autonomous replay (agent) נשאר חסום; ה-fingerprint לא נחלש (אותו hash עדיין מזהה את אותה זהות ועדיין חוסם duplicate-תוך-pending); ה-contract הישן נשאר terminal לעד. **הבטחה חדשה שנוספת** — בקשת create_task דטרמיניסטית מפורשת פותחת contract חדש אחרי rejection.
failure semantics: fail-closed נשאר — אם ה-lookup הראשוני (`find_by_fingerprint`) נכשל, מוחזר `persistence_lookup_failed` בדיוק כמו היום, לפני שה-branch החדש בכלל נבדק
observability: `logger.info` חדש (ראה שכבה 2), ללא שינוי ל-logs קיימים
cross-layer tests: `test_bug_canonical_tool_wiring.py`, `test_create_task_deterministic_route.py` (existing suite) הורצו ללא שינוי; טסט חדש (`test_bug153_create_task_reconfirmation_after_rejection.py`) מוסיף כיסוי ל-carve-out עצמו + regression ל-agent-replay-still-blocked + regression ל-task_update-not-included

### Proof of non-impact — שכבה 1
1. grep evidence: `grep -rn "leads_reasoning_projection\|BUG-104" app.py core/action_gateway.py` (בטווח השינויים) — 0 תוצאות
2. unchanged-tests evidence: `test_bug104_*.py` (5 חבילות) הורצו ללא שינוי בתוצאה
3. no-new-coupling evidence: אין import חדש מ-`core/leads_reasoning_projection.py`/`core/adapters/leads_adapter.py`

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: yes — נוגע ב-`ActionContract.status` (יצירת contract חדש כש-ישן `rejected`)
ובניסוח-הפונה-למשתמש. **איך:** אין מנגנון grounding/evidence עצמאי נוסף —
עדיין נסמך אך ורק על `core/action_gateway.py`'s `ActionContract`/`GatewayResult`
כ-source of truth. `build_approval_lifecycle_result()` הקיים ממשיך לרנדר
את התשובה למשתמש לפי ה-contract האמיתי (עכשיו: ה-contract *החדש*, לא הישן).

## 5. Verification (לפני מיזוג)

- `python3 -m py_compile app.py core/action_gateway.py`
- `python3 test_bug153_create_task_reconfirmation_after_rejection.py` (חדש)
- `python3 test_create_task_deterministic_route.py` — ירוק, ללא שינוי
- `python3 test_bug_canonical_tool_wiring.py` — ירוק, ללא שינוי
- `python3 test_bug091_source_trust_boundary.py` — ירוק, ללא שינוי
- `python3 core/router/test_router.py` — ירוק, ללא שינוי
- `python3 smoke_tests.py` / `test_integration.py` — ירוק

## 6. סטטוס

עיצוב מאושר (ע"י owner, 04/08/2026, דרך AskUserQuestion — "Design a
reconfirmation policy"). קוד מומש בהמשך לאותו commit batch. **לא מוזג,
לא deployed, לא verified בפרודקשן** — לא ✅ עד commit+push+deploy+production
verification לפי כלל-הברזל.
