# LL-13 — Pending Approval: Durable Store, Evidence Gate, Dedup

סטטוס: Draft Spec — טרם ממומש
מקור: LL-13 (אישור כפול שביצע פעולה פעמיים על "כן" שני)
תלוי ב: `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` (C53) — קרא אותו קודם, הוא כבר ממפה את מצב היום

---

## 0. למה הספק הזה לפני שכותבים קוד

C53 כבר תיעד שב-`main` היום יש **ארבעה מנגנוני אישור עצמאיים**, לא אחד:

1. `_pending_approvals` dict ב-`app.py` (`app.py:81`) — keyed by `chat_id`, TTL=600s (`_PENDING_APPROVAL_TTL`, `app.py:98`), מאושר/מבוטל לפי מילים חופשיות מ-`_CONFIRM_WORDS`/`_CANCEL_WORDS` (`app.py:82-83`). **In-memory בלבד — לא שורד restart.**
2. `event_bus.bus` / `PendingActionsStore` (`event_bus.py:24`) — keyed by `action_id`, מאושר דרך Telegram inline keyboard callback (`approve:{action_id}` / `reject:{action_id}`), נוצר דרך `_queue_approval()` (`app.py:562`).
3-4. שני מנגנונים נוספים (TMA `Approvals` table, ועוד אחד) — ראה C53 §0 לרשימה המלאה.

הספק הזה (LL-13) **לא** מציע טבלת `Pending_Approvals` כמנגנון חמישי. הוא מציע אותה כ**תחליף ל-#1 ו-#2** — store יחיד, durable, ב-Airtable, במקום שני in-memory stores מקבילים. כל מימוש חייב לכלול plan להחליף/לבטל את `_pending_approvals` ו-`PendingActionsStore`, לא רק להוסיף עוד אחד לערימה. זו ההחלטה הארכיטקטונית המרכזית כאן — **לא להתחיל לממש בלי לאשר את זה קודם**, כי זה משנה את `_handle_approval_callback` וכל מקום שקורא ל-`_queue_approval`.

---

## 1. Pending Approval — סכמת טבלה (Airtable)

**טבלה: `Pending_Approvals`**

| שדה | טיפוס | הערות |
|---|---|---|
| approval_id | Autonumber / UUID | מזהה ייחודי |
| session_id | Text | מקשר לשיחה/Lead |
| action_type | Single select | `create_draft`, `send_message`, `update_lead` וכו' |
| action_payload | Long text (JSON) | הפרמטרים המדויקים לביצוע |
| status | Single select | `pending` / `executed` / `expired` / `cancelled` |
| created_at | Date/time | |
| executed_at | Date/time | ריק עד לביצוע בפועל |
| requested_by_message_id | Text | ה-Telegram message id שיצר את הבקשה |

### לוגיקה

- בכל פעם שנדרש אישור → יוצרים רשומה חדשה עם `status=pending`, וכל בקשת אישור ישנה לאותו `session_id` הופכת ל-`expired` (כדי שלא יהיו כמה `pending` במקביל לאותו session).
- כשמגיע "כן" → שולפים את ה-`pending` האחרון לאותו `session_id`. אם אין כזה → "אין פעולה הממתינה לאישור".
- מבצעים את `action_payload` **פעם אחת**, מעדכנים `status=executed`, `executed_at`.
- אם מגיע "כן" נוסף על `approval_id` שכבר `executed` → תשובה: "הפעולה כבר בוצעה ב-[זמן]" ולא ביצוע חוזר.

### הבהרה קריטית — ביצוע עוקף ניתוב רגיל

זה בדיוק הבאג שראינו ב-LL-13:

```
Pending approval execution bypasses normal intent routing.

"כן" אינו מסווג מחדש.
הוא רק:
1. מאתר את ה-pending approval.
2. מבצע את הפעולה השמורה.
3. מסמן executed.
4. מחזיר את תוצאת הביצוע.
```

כלומר — ברגע שיש `pending` פעיל ל-`session_id`, הודעת "כן" **לא** עוברת דרך `route_request()` / Router הרגיל (`Intent`, `RouterDomain` וכו'). זו צריכה להיות בדיקה מוקדמת, *לפני* הניתוב — תואם למבנה הקיים ב-`app.py` §2.5 (Pending Approval Gate, היום מול ה-dict, יעבור להיות מול `Pending_Approvals`).

הערה תואמת לכלל הברזל ב-`tool_registry.py`/`dispatcher.py`: גם ביצוע מ-pending approval **חייב** לעבור דרך `dispatch_tool()` + `enforce()` מחדש לפני ביצוע — לא להריץ `action_payload` ישירות נגד Airtable/Gmail/Calendar. תואם להערה הקיימת ב-`AGENTS.md`/`CLAUDE.md`: *"re-runs `enforce()` for the original requester immediately before dispatching — never trust a stored decision blindly."* זה חל גם כאן.

---

## 2. ניסוח לפי ראיות (Evidence Gate)

כלל קוד (פסאודו):

```python
if tool_call_in_this_turn includes create_draft (success):
    say "טיוטה מוכנה"
else:
    say "נוסח מוצע"
```

- אסור לכתוב "✅ כן / ❌ לא" כטקסט — אם אין Telegram `InlineKeyboardMarkup` מצורף בפועל, הניסוח הוא: "להמשך, השב 'כן'".
- כל הודעת סטטוס עוברת בדיקה: "האם קריאת הכלי שמוכיחה את הטענה הזו מופיעה בלוג של ה-turn הנוכחי?" אם לא — מורידים את הטענה.

**הערה ליישום:** זה למעשה אותו עיקרון שכבר ממומש ב-`core/anti_hallucination.py` (`verify_execution`/`sanitize_agent_response`, A32 NO-TOOL-EVIDENCE gate — ראה `test_a32_enforcement.py`). אל תבנו gate נפרד — בדקו קודם אם A32 כבר מכסה את ניסוח "טיוטה מוכנה" מול "נוסח מוצע", ורק הרחיבו אם יש פער.

---

## 3. Deduplication ברמת ה-tool calls

- מפתח דה-דופ: hash של `(tool_name + params)` בתוך אותו request/turn.
- לפני קריאה ל-Sessions/Leads → בדיקה אם כבר נקרא באותו turn עם אותם פרמטרים → אם כן, משתמשים בתוצאה הקיימת בזיכרון במקום לקרוא שוב.
- ניתן לממש כ-cache פשוט במשתנה ברמת ה-request handler (לא צריך טבלה נפרדת לזה).

**הערה ליישום:** ראו LL-11 (`SPEC` קודם, ממומש ב-PR #181) — אותו עיקרון בדיוק כבר מומש שם ל-Sessions ספציפית, ע"י snapshot יחיד שנטען פעם אחת ב-`run_agent` ומועבר במפורש לכל קורא (`_session_snapshot`, `app.py` §1.6). אל תבנו מנגנון דה-דופ כללי חדש בלי לבדוק אם להרחיב את אותו snapshot מספיק — ה-hash-cache הכללי דרוש רק אם יש tool calls מחוץ ל-Sessions שצריכים את זה (למשל Leads).

---

## 4. Regression Requirements

- "כן" שני על `approval_id` שכבר `executed` → לא מבצע שוב, מחזיר "הפעולה כבר בוצעה ב-[זמן]".
- `pending` שפג תוקף (TTL) → הודעה מתאימה ("אין פעולה הממתינה לאישור" או מקביל).
- `pending` שבוטל (`status=cancelled`) → לא מבוצע.
- לכל `session_id` יכול להיות `pending` פעיל אחד בלבד (יצירת חדש מבטלת/מפקיעה את הקודם).
- אין יותר מקריאת Sessions אחת באותו request (תלוי ב-LL-11, ראה §3 לעיל).

---

## 5. פתוח לפני מימוש

1. **ה-store היחיד**: לאשר שזה אכן מחליף את `_pending_approvals` ו/או `PendingActionsStore`, לא מתווסף עליהם (ראה §0).
2. **דרך הביצוע**: לאשר שביצוע `action_payload` עובר דרך `tools/dispatcher.dispatch_tool()` עם `enforce()` מחדש, לא ביצוע ישיר.
3. **יחס ל-A32**: לבדוק חפיפה בין "Evidence Gate" כאן לבין `core/anti_hallucination.py` הקיים לפני בניית gate נפרד.
4. **יחס ל-TMA `Approvals`**: C53 §1.1/§3.1 כבר מתעד טבלת `Approvals` קיימת בשימוש ע"י `tma_api.py`. לבהיר אם `Pending_Approvals` (הספק הזה) זהה לה, מחליפה אותה, או טבלה שלישית נפרדת — לא להכפיל בלי החלטה מפורשת.
