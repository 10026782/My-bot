# FCC — Diamond completion flow (05/10/2026)

מחליף את ה-planner החד-שלבי. **מנגנון אחד** ל-TMA ולצ'אט: `core/financial_control/conversation.py`.

```
free text → extract known fields → FCC draft (BusinessDraft) → filling → review → confirm
→ immutable ConfirmedSnapshot → ActionGateway → canonical writes → receipt
```

## 1. מה הוחזר בפועל מ-Diamond/BusinessDraft
| רכיב קיים | שימוש |
|---|---|
| `core/business_draft.py` (`BusinessDraft`, `create_draft`, lifecycle `CAPTURED→READY_FOR_REVIEW→EDITING→CONFIRMED`, `confirm()` → `ConfirmedSnapshot` immutable, `set_field`/`clear_field`, serialize/deserialize) | **כל** מצב ה-draft. תוספת קטנה ואדיטיבית: `register_entity_adapter()` כדי ש-`is_complete/set_field/confirm` ישתמשו ב-adapter של ישות שאינה commercial |
| `commercial_completion` (`EntityContract`/`FieldContract`/`Condition`/`validate_value`/coercion, required/conditional) | חוזי שדות FCC (`FCC_CONTRACTS`) באותו אוצר מילים |
| `core/draft_flow.py` | אוצרות מילים משותפים (`CONFIRM/CANCEL/EDIT/SKIP_WORDS`) ו-TTL `DRAFT_TTL_SECONDS=1800` — **אין TTL חדש** |
| `session_store.lead_sessions` (`create/save/load/delete_business_draft`, CAS, TTL עצל, קשירת זהות) | persistence. תוספת: פרמטר אופציונלי `contracts=` (ברירת מחדל = commercial, ללא שינוי התנהגות) |
| ActionGateway / `airtable_add`·`airtable_update` / `tma_write` | כתיבה: ללא שינוי. owner stamping + cross-owner link guard נשארים ב-`data_access_policy` |
לא נבנה session engine. `commercial_completion_routing.CommercialCompletionRouter` **לא** שומש: הוא קשור ל-`SUPPORTED_COMPLETION_ENTITIES`/`_primitive_inputs`/UX מסחרי; חיבור FCC אליו היה משנה מודולים מסחריים בלי יכולת אימות חי.

## 2. Session / draft storage
- slot אחד לאדם ולסוג-ישות: `lead_sessions` עם `sender = identity.user_id`, `channel = "fcc"`, `source_channel = "fcc"` ⇒ **אותו draft ב-TMA ובצ'אט**; בידוד לפי `user_id` קנוני (+ `tenant_id`, `actor_user_id` נבדקים בכל load; `DraftIdentityMismatchError` אחרת).
- 3 ישויות: `fcc_goal` (CREATE/UPDATE), `fcc_event`, `fcc_followup`. draft פתוח אחד בכל רגע בפועל.
- TTL 1800s (Diamond), פקיעה עצלה ב-load; terminal drafts מנוקים בתור הבא.
- הערה לפרטיות: ה-draft נשמר בשורת `Sessions` הקיימת (State JSON). נשאר פער פתוח: טבלת `Sessions` לא תחת `data_access_policy` (ראו §פערים).

## 3. מטריצת שדות חובה (יעד חדש)
| קטגוריה | חובה תמיד | מוסק בבטחה | נדרש עוד |
|---|---|---|---|
| `income` | Title, Target Amount, Category | Period Type=`monthly`, Calc Method=`period_sum` | End Date **לא** נדרש |
| `savings` | Title, Target Amount, Category | Calc Method=`cumulative` | End Date |
| `emergency_fund` | same | Calc Method=`cumulative` | End Date |
| `debt` | same | Calc Method=`cumulative` | End Date |
| `other` | same | **שום דבר** | Period Type + Calc Method (לא מנוחשים), ואם `cumulative` גם End Date |
אופציונלי ולעולם לא נשאל: `start_date`, `note`, `due_date`. אין דילוג על שדה חובה. ערכים מוסקים מסומנים "(הוסק)" ב-review.

## 4. TMA flow
`POST /api/fcc/write {text, goal_id?}` → `handle_turn` → `TurnResult` (`ask|review|confirmed→executed|…`). React רק מציג את `message`/`candidates`, ושולח את הטקסט הבא; הכפתורים "אשר ורשום / ערוך / בטל" שולחים את המילים. `GET /api/fcc/overview` מחזיר `draft` כדי לחדש שאלה פתוחה אחרי רענון. הביצוע: ה-writes ה**קפואים** עוברים אחד-אחד ב-`_queue_or_owner_execute` (ActionGateway). כשל ⇒ ה-draft נשאר `CONFIRMED` ו"אשר" מנסה שוב; `complete_execution` רק אחרי הצלחה.

## 5. Chat flow
- התחלה: כלי הסוכן `fcc_update(text)` (owner בלבד, canary) — פותח/ממשיך draft, **לא כותב**.
- המשך: `app.py` ב-webhook: כל עוד יש draft פתוח, `chat.maybe_handle` תופס את ההודעה **לפני** הסוכן (ללא פרשנות מחדש של המודל).
- אישור: ה-writes הקפואים → `airtable_add`/`airtable_update` דרך `_queue_approval_detailed` (מסלול האישור הרגיל; Single-Speaker דרך `_finalize_deterministic_queue_outcome`). **החלטת הרשאה:** בצ'אט יש אישור-הבנה (draft) ואז אישור-הרשאה רגיל של ה-ActionGateway — לא הוספתי `self_confirm` חדש. ב-TMA הבעלים מאושר אוטומטית כמו היום.
- שער אחד: `core/financial_control/gate.py` (flag + `FCC_CANARY_USER_IDS`) משותף ל-TMA ולצ'אט.

## 6. שדה חסר ≠ משימת המשך
שדה שאפשר להשלים בשיחה (סכום, תאריך, קטגוריה, איזה יעד) ⇒ שאלה בתוך ה-draft. משימת המשך נוצרת רק לפעולה חיצונית אמיתית ("דיברתי עם הבנק, צריך להביא יתרות"), עם `Owner`=המשתמש, `Topic=כספים`, תגית `[FCC:<goal>]`, ודדופליקציה מול משימה פתוחה זהה. התנהגות ישנה (חסר סכום ⇒ Task) בוטלה.

## 7. Golden Writer invariant
draft-reviewed payload = approved snapshot = ActionContract payload = written fields: `confirm()` בונה את ה-writes **פעם אחת** מ-`resolved_values()`; אחרי confirm אין classify/extractor (נבדק: extractor נכשל בקול רם אם נקרא), אין default חדש, ואין field loss. `update_goal`: base snapshot + overlay ⇒ patch רק של שדות ששונו; שינוי סכום יעד = אירוע `target_change` (היסטוריה לא נכתבת מחדש).

## 8. פערים
- `Sessions` מכיל draft פיננסי של הבעלים; הטבלה אינה תחת מדיניות owner-of-record.
- `update_goal` עם יעד לא חד-משמעי בצ'אט מחזיר רשימה ומבקש ניסוח מחדש (אין draft בלי יעד בסיס); ב-TMA הבחירה שולחת `goal_id`.
- סיווג הטקסט נעשה ב-LLM (`classifier.classify`/`fill_reply`) ולא נבדק על טקסטים אמיתיים (אין מפתח בסנדבוקס).
- לא נבדק חי: Airtable, PostgreSQL/ActionGateway בפועל, Telegram webhook.
