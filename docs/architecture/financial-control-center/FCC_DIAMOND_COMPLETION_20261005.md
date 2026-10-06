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

---

## 9. Sessions privacy gate (נבדק 06/10/2026)
ה-FCC draft נשמר בשורת `Sessions` (State JSON). נבדק כנתון רגיש, **לפני** merge.

### Sessions access map (מקור: grep על כל ה-repo)
| נתיב | קורא/כותב | מצב לפני | מצב אחרי |
|---|---|---|---|
| `session_store.py` (`_sync_to_db`, `_load_from_db`, `_find_best_session_in_db`, dedupe cleanup) | `airtable_add/update/get_records` ישיר, מפתח (Sender ID, Channel) | נתיב פנימי מורשה | **ללא שינוי** (לא עובר דרך מדיניות הכלים) |
| 31 קריאות `lead_sessions.*` ב-`app.py`, `lead_candidate_handler`, `action_gateway`, `cmd_decision`, `furniture_lead_funnel`, `core/deterministic_commercial_update` | דרך ה-API של ה-store בלבד, `sender` נגזר מזהות ההודעה | פנימי | ללא שינוי |
| `interaction_engine._adapter_whatsapp` → `get_all_active()` | RAM בלבד, רק sessions עם `done` + `summary` | FCC draft אינו נכלל (אין `summary`) | ללא שינוי |
| **generic `airtable_get` / `airtable_add` / `airtable_update` (agent + approvals)** | owner/manager/employee: `enforce_tenant_scope` החזיר "מותר הכל" לכל טבלה | ⚠️ **כל role פנימי יכול היה לקרוא/לכתוב Sessions** (כולל drafts של אחרים) | ✅ נחסם לכל role דרך `data_access_policy` (מצב חדש `SYSTEM_INTERNAL`) |
| raw table id (`tblHLfE24lTkVUhz0`) | נחסם מראש לכל נתיב כללי (`is_raw_table_id`) | חסום | חסום (נבדק) |
| partner | `airtable_get` מוגבל לטבלאות דומיין; Sessions לא ברשימה | חסום | חסום + מדיניות |
| `airtable_tools.airtable_get` (render) | | מרנדר | מחזיר `SYSTEM_STATE_MESSAGE` |
| TMA | אין endpoint לקריאת Sessions; `tma_write` allowlist לא כולל Sessions | חסום | חסום (נבדק) |
| debug/admin (`/status`, `/schema`, `boss_doctor`, `health_monitor`) | אין קריאת Sessions | — | — |

### החלטה
הרחבה במדיניות המרכזית הקיימת (`core/data_access_policy.py`), **לא** מדיניות מקבילה ולא סינון FCC בלבד: מצב `SYSTEM_INTERNAL` ל-`Sessions` (ול-`LeadSessions` הישן) — כל כלי נתונים כללי נחסם לכל role; `filter_records`→`[]`, `authorize_record`/`scope_new_record_fields` נדחים. אין השפעה על lead qualifier / BusinessDraft הקיים (הם עוברים דרך `session_store` ולא דרך הכלים הכלליים); הוכח בהרצת כל בדיקות ה-BusinessDraft וה-session.

### זהות / מפתח ה-session
`sender = "<tenant_id>:<user_id>"`, `channel = "fcc"`; בנוסף נבדקים בכל load: `tenant_id`, `actor_user_id`, `source_channel` (`DraftIdentityMismatchError`). אין שם תצוגה; tenant/user חסר או "unknown" ⇒ `denied` (fail closed); אין fallback למשתמש אחר. המפתח הוא מזהה, **לא** מדיניות גישה — הגישה נשלטת ע"י הכלל למעלה.

## 10. הודעה לא קשורה באמצע draft
- ערך תקף לשדה → נשמר. פקודה (אשר/ערוך/בטל/דלג) → מטופלת (דלג על שדה חובה נדחה).
- ערך שנראה כערך אך לא תקין (תאריך לא קיים, סכום שלילי) → **לא נשמר**; אותה שאלה מוצגת שוב ("❌ ערך לא תקין").
- טקסט שאינו תשובה כלל ("מה מצב הלידים שלי?") → **לא נשמר**, מצב `unrelated`, ה-draft ללא שינוי. ב-TMA מוצגת השאלה שוב; בצ'אט ההודעה ממשיכה לזרימה הרגילה (הסוכן) וה-draft נשאר פתוח.
- מנגנון: ערכים "בצורת ערך" (מספר/תאריך עם ספרות/בחירה מוצגת) מאומתים דטרמיניסטית; כל השאר דרך `fill_reply` שחייב **ציטוט** מהטקסט לכל שדה (אין ציטוט ⇒ אין שדה); שדות נוספים מתקבלים רק לצד תשובה תקפה לשדה שנשאל. כותרות/הערות (טקסט חופשי) אינן מתקבלות דטרמיניסטית.

## 11. Follow-up: FCC-CHAT-SINGLE-CONFIRM
בצ'אט יש כרגע שני אישורים: אישור ה-draft (הבנה) ואחריו אישור ה-ActionGateway הרגיל (הרשאה). `self_confirm` הוא שינוי authorization ולכן **לא** נכלל ב-PR זה. אחרי runtime verification תוחלט האם פעולות FCC עצמיות ברמת סיכון נמוכה יעברו ActionGateway ללא אישור שני. ב-TMA נשארת מדיניות האישור הקיימת (owner auto-approve).

## Goal families (תצוגה לפי סוג יעד)

ללא שינוי בטבלת Goals וללא טבלה חדשה — המשפחה נגזרת מנתונים קיימים (`Calc Method`, `Category`, קיום סכום יעד):

| משפחה | תנאי | תצוגה |
|---|---|---|
| recurring | `period_sum` | יעד/בפועל/נשאר + יעד דינמי לשבוע |
| monthly_level | `recurring_level` | יעד חודשי/הושג/נשאר — ללא קצב שבועי |
| cumulative | `cumulative` | התקדמות מול יעד כולל; קצב שבועי רק עם `end_date` מפורש |
| project | אין סכום יעד + קטגוריה לא-מספרית | כרטיס אבן-דרך: סטטוס, פעולה הבאה, תאריך יעד — ללא סכומים |

`summarize()` מצרף לפי משפחה בלבד, מדלג על פרויקטים ולא מערבב משפחות; כרטיס "יעד הכנסה לשבוע" בכותרת הוא הכנסה בלבד.


## Income hierarchy + calendar-day pacing (06/10/2026)

- **Parent / source**: Financial Goals has an explicit link field `Contributes To` (-> Financial Goals). A goal with a parent is a *source*: its target is **not** added to the parent target; its events roll up into the parent actual **once** (de-duplicated by event record id). A source's `target_change` never moves the parent target. Self-links, cycles and non-active / foreign parents are ignored (the goal then stands alone). No inference from titles.
- **Summary**: header cards aggregate top-level goals only (`is_source` rows are skipped). Parent rows carry `sources`, `weekly_sources_required` (what weekly sources still owe this week) and `other_sources_needed = max(weekly pace - weekly_sources_required, 0)`.
- **Pacing**: monthly `period_sum` weekly pace = `remaining / calendar_days_left * min(7, calendar_days_left)` (today included). Weekly goals reset on Sunday, monthly goals on the 1st. Other goal families are unchanged (`weeks_left`).
- Verification: `test_financial_control_center.py` (hierarchy, roll-up, 28/30/31-day, resets, over/under-performance); frontend `fccPresentation.test.ts`. Production/device: NOT verified.

## Gross -> direct costs -> net (06/10/2026)

- New event `Kind` value **`direct_cost`** in Financial Progress Events (no new table, owner-scoped, append-only). A direct cost is a positive amount tied to producing income (fuel, parking, fees) and is linked to the income source goal (e.g. travel).
- `actual` stays **gross** (progress vs target and the weekly pace are never reduced by costs). Each goal row also carries `direct_costs` (same period window as `one_time`; superseded rows ignored) and `net = actual - direct_costs`. Costs of a source roll up into the parent once (same de-duplication as income). Project rows carry no cost fields.
- Header income card shows `ברוטו · הוצאות ישירות · נטו` only when there are direct costs. Chat/TMA: the classifier maps "דלק/כביש/חניה" costs to `kind=direct_cost` on the source goal; goes through the same draft/confirm primitive.
- **Live Airtable prerequisite**: the `direct_cost` choice must exist on `Financial Progress Events.Kind` before the first write.
- Household expenses, business expense receipts and recurring obligations are separate follow-ups (privacy: `Expenses` is a shared business ledger, `REVIEW_REQUIRED_FOR_PERSONAL_FINANCE_SCOPE`).
