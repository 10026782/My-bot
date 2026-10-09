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
- הערה לפרטיות: ה-draft נשמר בשורת `Sessions` הקיימת (State JSON). הפער נסגר: `Sessions` תחת `data_access_policy` במצב `SYSTEM_INTERNAL` (ראו §9; נבדק ב־`test_generic_tools_cannot_read_or_write_sessions` וב־`test_raw_sessions_table_id_and_tma_write_cannot_bypass_policy`).

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
- ~~`Sessions` מכיל draft פיננסי של הבעלים; הטבלה אינה תחת מדיניות owner-of-record.~~ **נסגר** (§9): `Sessions` ו־`LeadSessions` במצב `SYSTEM_INTERNAL` — חסומות לכל role בכלים הכלליים, גם דרך table id גולמי; ה־TMA write allowlist לא כולל אותן. מעודכן 09/10/2026 אחרי אימות מחדש מול `main`.
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

`summarize()` מצרף לפי משפחה בלבד, מדלג על פרויקטים ולא מערבב משפחות; כרטיס "קצב נדרש לשבוע (מעכשיו)" בכותרת הוא הכנסה בלבד.


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

## Weekly card shows direct costs (06/10/2026)

- Device test showed direct costs in the monthly income card but not in the weekly card. Each parent `sources[]` entry now carries `direct_costs` and `net` (its own period window), and the weekly income card line shows `<source>: actual / target השבוע · הוצאות ישירות -₪X · נטו ₪Y`.
- **Owner decision (06/10/2026): progress is NET.** `remaining`, weekly pace and status use `net = gross - direct costs` (profit, not turnover); `actual` stays the gross display value. Goal: learn what to cut (EV, smarter trips) — direct vs indirect vs household. Header income card shows net / target, hint shows gross and costs. This supersedes the earlier "costs never reduce progress" wording above.

## Business-expense fields on `Expenses` (06/10/2026)

- Six fields added live to `Expenses` (owner-approved): `Expense Scope` (business_direct | business_reportable | indirect), `Receipt Required` (checkbox), `Receipt Status` (missing | received | not_required), `Vendor`, `Payment Method` (cash | card | transfer | standing_order), `Related Goal` (link -> Financial Goals). Constants in `ExpenseFields`, listed in `schema_cache.json`.
- The `Related Goal` link auto-created an inverse link field on `Financial Goals` (`fldVcBORLDgrCVaa0`); it is not used by code.
- `household` is deliberately **not** a scope: `Expenses` is a shared business ledger (manager/employee can read it). Household spending stays private (FCC events). No code reads or writes the new fields yet; an FCC receipts-missing counter needs an owner-scope decision first (`REVIEW_REQUIRED_FOR_PERSONAL_FINANCE_SCOPE`).

## Household spend + receipts counter (06/10/2026, owner-approved)

- **Household expenses stay private**: new Progress Event `Kind` value `household_expense` (owner-scoped table, never the shared `Expenses` ledger). The month-to-date total (`overview.household.month_total`, superseded rows ignored) is a separate card; it never enters income `actual`, `direct_costs` or `net`. Logged through the same draft/confirm primitive against a goal such as "הוצאות בית" (`goal_hint`). **Live prerequisite**: the `household_expense` choice must exist on `Financial Progress Events.Kind` (added manually in Airtable) and a household goal must exist.
- **Receipts counter**: `service.receipts_overview` reads `Expenses` read-only and keeps only rows whose `owner` link is the caller, with `Receipt Required` and `Receipt Status != received`; returns `missing_count` + `missing_amount` only (no row details). Unresolved identity or read failure -> zeros. `Expenses` policy is NOT changed (manager/employee access unchanged); this does not close `REVIEW_REQUIRED_FOR_PERSONAL_FINANCE_SCOPE`.

## Recurring Obligations (06/10/2026, owner-approved structure)

- **Live table** `Recurring Obligations` (`tblAvpGNDWs1tNoKG`): Name, Financial Owner (-> Profile), Scope (household|business|personal), Obligation Type, Category, Amount, Frequency, Monthly Equivalent (Airtable formula, display-only), Next Charge Date, Active, Essentiality, Review Status, Potential Monthly Saving, Vendor, Payment Method, Related Goal (-> Financial Goals), Notes, Created At, Updated At. Constants: `Tables.REC_OBLIGATIONS`, `RecObFields`; cache reconciled with the live base.
- **Owner-scoped** in `data_access_policy` exactly like Financial Goals (owner-of-record only; no manager/employee access, no `airtable_get`; `Related Goal` is cross-owner-link guarded). Allowed for the FCC write path only via `_TMA_WRITE_ALLOWED_TABLES`.
- **A commitment, not an expense**: a monthly charge is stored once and never rewritten monthly; it never enters income, net, direct costs or household spend. The monthly equivalent is computed in code (`calc.monthly_equivalent`: monthly 1, quarterly 1/3, yearly 1/12, `custom` = not counted), so the number does not depend on the Airtable formula.
- **Screen**: three numbers from `overview.obligations` — total monthly commitments, how many are marked reduce/cancel/negotiate, and potential monthly saving (stated saving wins; a `cancel` without a stated saving = its monthly cost, shown as inferred in the review).
- **Operating rule**: "נטפליקס 70 לחודש לבטל" -> classifier `upsert_obligation` -> draft/review/confirm -> CREATE a Recurring Obligation, or UPDATE (patch only changed fields) when an active one with that name already exists. Never a Financial Progress Event. Scope is asked when not stated.
- Verification: `test_financial_control_center.py` (85 tests), frontend `fccPresentation.test.ts`. Device/production: NOT verified.

## Obligations: cancel decision vs actual cancellation (06/10/2026, owner-approved)

- **"לבטל X" is a decision, not an action**: `Review Status = cancel` only records the intent; nothing is cancelled at the vendor. When the name is not tracked yet, the review says so ("לא מצאתי התחייבות בשם X. לרשום אותה חדשה ולסמן: לבטל?") instead of silently creating a "new commitment".
- **Screen**: the flagged card also shows how many are `cancel` and still waiting for the real cancellation; the potential-saving card is labelled "רק אחרי ביטול בפועל".
- **"ביטלתי את X"** (classifier action `deactivate_obligation`) -> UPDATE draft with `status = inactive` -> patch `Active = false` only; the obligation leaves the monthly total. An untracked name is clarified, never created. A cancelled (inactive) commitment does not block adding the same name again.
- Saving inference runs only when review status / amount / frequency / saving are part of the turn, so an unrelated update never touches other fields.

## Weekly card wording (07/10/2026)

- The weekly income target already INCLUDES the weekly sources (travel is a part of it, never added on top). The card line now shows what each source still owes so the parts add up to the headline: `מזה: נסיעות: נשאר ₪746 מתוך ₪2,500 השבוע · ממקורות אחרים: ₪2,963` (746 + 2,963 = 3,709). Wording only; no calculation changed.

## Savings = a standing monthly allocation vs target (07/10/2026, owner decision)

- **Savings** (`category = savings`) is a **standing monthly allocation to the capital market, like a standing order** (e.g. target ₪5,000 per month). It is a **level, not a sum that resets**: `recurring_level` / `monthly`, family `monthly_level`. The current level = the running total of `monthly_recurring` events (each raise/cut of the allocation is an event: positive = raise, negative = cut), so cutting costs / raising income is tracked as progress toward the target and nothing resets at month end. One-time deposits are not part of the level. **A one-time accumulated pot is the emergency fund** (`cumulative`).
- New savings goals infer `monthly` + `recurring_level` (no end date asked); the classifier prompt states the distinction and the delta convention. The earlier same-day wording (monthly `period_sum`, resets on the 1st) is superseded by this section.
- **Header card** `savings` counts `monthly_level` goals ("הפרשה חודשית לחיסכון", hint "הוראת קבע מול יעד · לא מתאפס"). A legacy cumulative savings goal still shows only while no monthly-level one exists (`_CARD_FALLBACKS`); families are never summed. The goal card shows "יעד הפרשה חודשית / מופרש כרגע לחודש / חסר ליעד".
- **Live data**: the existing live savings goal (target 10,000) is still cumulative until it is switched (chat: "עדכן יעד חיסכון: חודשי, שיטת חישוב שינוי קבוע בחודש" + target 5,000, or an owner-approved edit of the record). Not changed by this commit.

## Set a savings level + structured intent from the agent (08/10/2026)

- **"אני מפריש עכשיו X בחודש"** = the NEW total level, not a delta. Classifier/agent intent key `level`; the conversation computes `delta = level - current standing level` (`calc.monthly_level_now`, running total of `monthly_recurring` events) and logs one `monthly_recurring` event (note "קביעת רמה: ₪X לחודש"). Same level -> "nothing to update"; goal chosen later -> delta computed then. Raises/cuts stated as a change ("הגדלתי ב-1,000") keep using `amount` (negative = cut).
- **No second model call from chat**: the `fcc_update` tool takes an optional structured `intent` (the calling agent already understood the message). It is validated like classifier output (`writer.validate_intent`) and used for the FIRST classification via `chat.PresetIntentExtractor`; missing/invalid -> the Haiku classifier runs as before. Draft -> review -> confirm is unchanged. The TMA free-text box still uses the classifier (no calling agent there).
- Open (owner decision): what a missed savings month means (shortfall recorded + follow-up task vs automatic catch-up).

## Savings plan vs actual: a missed month is a visible gap (08/10/2026, owner-approved)

- **Plan** = the standing level (running total of `monthly_recurring` events). **Actual** = `one_time` deposits recorded in the calendar month ("הפקדתי החודש X"). `calc.deposit_status` yields `deposited_month`, `gap_month = max(level - deposited, 0)` and the same for last month (`gap_last_month`, using the level as of last month's end). Superseded events are ignored.
- **A missed month never inflates the next one**: the level/target is untouched (no automatic catch-up). A make-up deposit is simply a deposit in the month it is made (it does not rewrite last month). The gap stays visible: goal card rows "הופקד בפועל החודש / פער החודש / פער בחודש שעבר" and the savings card hint ("הופקד החודש ₪X · פער ₪Y · פער בחודש שעבר ₪Z"), which suggests the chat phrase "משימת המשך לפער בחיסכון" — the follow-up task is created through the existing `follow_up` draft/confirm primitive, never silently by a background job.
- Classifier: "הפקדתי החודש X" = `log_progress`, `kind=one_time` on the savings goal (a real deposit, not a level change).

## הלוואות וחוב (07/10/2026) — קריאה בלבד

אזור "הלוואות וחוב" בתוך ה־FCC, מעל טבלת `Loans` הקיימת (לא נוצרה טבלה חדשה; SSOT של יעד סגירת ה־₪700,000 נשאר ב־Financial Goals).

- **קוד:** `core/financial_control/loans.py` (טהור, ללא I/O) + `service.loans_overview` (קריאה owner-scoped דרך `data_access_policy`, שמות נכסים רק מ־Assets של אותו בעלים) → מפתח `loans` ב־`/api/fcc/overview`. שמות השדות ב־`airtable_schema.LoanFields` וב־`schema_cache.json`.
- **פרטיות:** `Loans` כבר `OWNER_SCOPED`; סיכומים מחושבים רק על הרשומות שעברו סינון.
- **Unknown ≠ 0:** ערך חסר נשאר `None`; נגזרות `None` כשחסר קלט; סכומים וממוצעים מדלגים על חסרים ומחזירים `coverage` (על כמה הלוואות הם מבוססים). ממוצע ריבית משוקלל ביתרת סילוק רק על הלוואות עם ריבית ויתרה.
- **עלות עתידית:** `תשלום חודשי × תשלומים שנותרו − יתרת סילוק`; `future_cost_exact` רק כשעמלת הפירעון מספרית (או "אין"); אחרת מוצגת "≈ משוער".
- **פעילה:** כל הלוואה שאינה `Payment Status = Paid Off`. תיבת `Active Loan` לא יכולה לסגור הלוואה, כי Airtable לא מבחין בין תיבה לא מסומנת לתיבה שלא מולאה. הלוואה עם תיבה לא מסומנת ושאינה Paid Off מקבלת `status_unknown` (מוצגת "סטטוס לא הוגדר", נכללת בסיכומים, ו־`unknown_status_count` בסיכום).
- **תעדוף:** שלושה סדרי תצוגה (ריבית גבוהה / פינוי תזרים / יתרה קטנה), לא החלטה אוטומטית; ערכים חסרים בסוף. השוואה בין שתי הלוואות — נתונים בלבד.
- **UI:** `tma-frontend/src/lib/fccLoans.ts` (פרזנטציה טהורה) + `LoansSection` ב־`FinancialControlCenter.tsx`. שלב 2 (עדכון/סגירת הלוואה דרך Diamond ואירוע ליעד) טרם נבנה.

## מנוע פרעון מוקדם (07/10/2026) — קריאה בלבד

מנוע חישוב/דירוג/הסבר בתוך "הלוואות וחוב", על `Loans` הקיימת בלבד (owner-scoped). לא סוגר הלוואה, לא כותב ל־Airtable, לא עובר ב־ActionGateway, בלי שינוי schema.

- **קוד:** `core/financial_control/payoff.py` (טהור) → `loans.build()` מוסיף `payoff` ל־`/api/fcc/overview`; סימולציית תקציב ב־`GET /api/fcc/loans/scenario?budget=` (קריאה בלבד, אותו flag/auth/owner-scope).
- **עובדות ומדדים (אין מדד אחוזי של "יעילות"):** לכל הלוואה ארבע עובדות — יתרת סילוק, ריבית, החזר חודשי שמתפנה, חודשים שנותרו — ושני אומדנים: `עלות המשך משוערת = החזר חודשי × תשלומים שנותרו − יתרת סילוק` ו־`עומס ריבית שנתי משוער = יתרת סילוק × ריבית`. `חיסכון בעלות = עלות המשך − עמלת פירעון ידועה`; עמלה לא ידועה/לא מספרית → "משוער" (לא נטו); תוצאה ≤ 0 → "אין חיסכון חיובי". מדדי `annualized_cash_release`/`monthly_cash_efficiency` הוסרו לחלוטין מה־contract: הם ערבבו קרן וריבית ונראו כמו תשואה (למשל 307%).
- **איכות נתונים (שתי רמות):** *אי־עקביות קשיחה* — `החזר חודשי × תשלומים שנותרו < יתרת סילוק` → `data_inconsistent`, לא מחשבים עלות/חיסכון, לא בדירוג החיסכון. *חשד* — העלות רחוקה מאוד מאומדן גס `יתרה × ריבית × חודשים ÷ 24` (מתחת ל־40% או מעל 250%) → `data_suspicious`: העלות והחיסכון לא מוצגים ולא בדירוג, אך ארבע העובדות נשארות. עמלה גדולה מעלות ההמשך אינה אי־עקביות אלא "אין חיסכון". הסף היוריסטי ואינו חוסם נתון — הוא רק מסמן "יש לבדוק".
- **ציונים:** ארבעה ציונים 0–100 min-max מול ההלוואות הפעילות של אותו Owner (ללא cut-off קשיח; אין פיזור = 50). ריבית/תזרים/זמן שנותר — גבוה = ציון גבוה; סכום לסילוק — הפוך. `balanced = 0.30·ריבית + 0.30·תזרים + 0.25·סכום + 0.15·זמן` (קבוע `WEIGHTS`). חסר גורם → נשמט והמשקלים מנורמלים מחדש על הידועים; `score_coverage` (למשל 3/4) ו־`missing_factors`. לעולם לא 0 מומצא.
- **אסטרטגיות:** מאוזן / ריבית גבוהה / פינוי תזרים / חיסכון בעלות — מיון בלבד, ערכים חסרים או חשודים אחרונים, ללא "מנצח". הציון המאוזן (ריבית, תזרים, סכום, זמן) לא השתנה.
- **תקציב:** סוגר הלוואות שלמות לפי סדר האסטרטגיה (≤ היתרה שנותרה; גבול מדויק נכלל); הלוואה שלא נכנסת מדולגת ללא פרעון חלקי; יתרת סילוק לא ידועה לא נכללת; אסטרטגיית החיסכון ושילובי האופטימום לא סוגרים הלוואה שהמדד שלהם לגביה לא ידוע (`excluded_no_data`). מחזיר נסגרות, ניצול, נשאר, תזרים משתחרר, חוב שנעלם, עלות עתידית שנחסכת. בנוסף שילוב אופטימלי (חיפוש ממצה עד 16 הלוואות) לפי מקסימום תזרים / מקסימום עלות שנחסכת. preset: יעד סגירת החוב מ־Financial Goals (סימולציה, לא מזומן קיים).
- **UI:** `FccPayoff.tsx` + `lib/fccPayoff.ts` — לשוניות אסטרטגיה, כרטיס לכל הלוואה עם "למה כאן" (עובדות בלבד), סימולטור תקציב. הסימולציה נטענת מה־endpoint (מקור חישוב יחיד); אין ניסוח המלצה.

## פיצול המסך ללשוניות + "נכסים והון" (07/10/2026)

המרכז הכלכלי חולק לשלוש לשוניות במסך אחד (ה־payload והקריאה הרשתית ללא שינוי): **התנהלות חודשית** (ברירת מחדל: כרטיסי כותרת כולל הוצאות בית והתחייבויות, עדכון מהיר, משימות, יעדים, התקדמות אחרונה), **הלוואות וחוב** (אזור ההלוואות + מנוע הפרעון המוקדם), **נכסים והון** (חדש, קריאה בלבד).

- **זיכרון לשונית:** רק בזיכרון המודול (`lib/fccTabs.ts`) — נשמר כל עוד האפליקציה פתוחה; פתיחה חדשה חוזרת ל"התנהלות חודשית". כל הלוחות נשארים mounted (hidden כשלא פעילים) כדי שטיוטת עדכון, סינון הלוואות וסכום תקציב לא יאבדו בהחלפת לשונית.
- **עדכון מהיר** נשאר בתוך "התנהלות חודשית" (לא גלובלי) עד שיהיה Diamond גם ל־Loans/Assets.
- **נכסים והון:** `core/financial_control/assets.py` (טהור, קריאה בלבד) + `service.assets_overview` (owner-scoped דרך `data_access_policy`) → מפתח `assets` ב־`/api/fcc/overview`. הערכים מוצגים כפי שהם ב־Assets (`Equity`/`My Equity` הן נוסחאות Airtable, לא נגזרות מחדש); ערך חסר = `None` ("לא הוגדר"), סכומים מדלגים על חסרים ומחזירים `coverage`. **משכנתא רשומה בנכס** ו**הלוואות מקושרות** (Loans.Related Asset, פעילות בלבד) מוצגות בנפרד ולעולם לא מחוברות (עשויות לתאר אותו חוב); מוצג גם חוב הלוואות שאינו מקושר לאף נכס.
- אין כתיבה, אין שינוי חישובים קיימים ואין שינוי schema (נוסף רק `AssetFields` וקבועי שדות). פעולות על נכסים — בשלב מאוחר יותר דרך Diamond.

## שלב 2 — סגירת הלוואה (08/10/2026) — נתיב כתיבה ראשון באזור ההלוואות

פעולה אחת בלבד: "סגרתי את ההלוואה". אישור אחד כותב שני דברים, ושום דבר אחר.

- **כניסה:** כפתור "סגרתי את ההלוואה" בכרטיס של הלוואה פעילה → `POST /api/fcc/intent/start {intent:"loan.close", entity_id}` (flag + auth + owner-scope; הלוואה לא קיימת/של אחר = אותה תשובה `denied`). הקריאה פותחת טיוטה ולא כותבת דבר. הכניסה מובנית (בלי classifier/LLM); שפה חופשית לסגירה לא נבנתה.
- **Diamond, בלי מנגנון חדש:** ישות `fcc_loan_close` על `BusinessDraft` הקיים, באותו slot משותף של ה־FCC (טיוטה אחת לאדם). שדות הניתנים לעריכה: סכום ששולם בפועל (ברירת מחדל = יתרת הסילוק השמורה, מסומן "הוסק"; חסרה יתרה — נשאל, לא מנוחש) ותאריך (ברירת מחדל היום). **איזו הלוואה נסגרת ואיזה יעד חוב** נשמרים ב־source_context ולא ניתנים לעריכה — עריכה לא יכולה להפנות את הסגירה להלוואה אחרת. זרימה: review → אשר / ערוך / בטל דרך `/api/fcc/write` הקיים; תוצר האישור הוא `ConfirmedSnapshot` קפוא שמבוצע כמו שהוא.
- **מה נכתב (שני writes קפואים, דרך ActionGateway → `tma_fcc_write`):** (1) `Loans.Payment Status = "Paid Off"` על רשומת ההלוואה בלבד — אף שדה יתרה/תשלום/ריבית לא נכתב מחדש; (2) אירוע התקדמות אחד (`one_time`) ביעד החוב הפעיל היחיד של הבעלים עם הסכום ששולם. אין יעד חוב פעיל אחד (אפס או כמה) → נכתב רק הסטטוס, וה־review אומר זאת במפורש. `Active Loan` לא נוגעים בו.
- **Idempotency:** מפתח האירוע נגזר מההלוואה + יעד + סכום + יום (`close_loan:<record>`), ו־`_already_applied` מדלג על status שכבר `Paid Off` ועל אירוע שכבר קיים. כישלון חלקי נשאר כטיוטה מאושרת — "אשר" שוב ממשיך רק במה שחסר ולא מכפיל. הלוואה שכבר `Paid Off` → `info`, בלי טיוטה.
- **הרשאות:** `Loans` נוספה ל־`_TMA_WRITE_ALLOWED_TABLES`; הטבלה OWNER_SCOPED ו־`_enforce_personal_data_policy` בודק ברגע הביצוע שהרשומה שייכת לבעלים המבקש (בדוק: patch על הלוואה של אחר נדחה). אין `self_confirm` חדש; אין נתיב כתיבה ישיר.
- **תצוגה:** סכום עם אגורות מוצג עם אגורות (מה שנבדק = מה שנשמר). הפאנל ב־`FccLoans.tsx` (LoanClosePanel) מציג את ההודעה מהשרת ושולח את המילה הבאה; אחרי ביצוע — קבלה, ללא כפתור אישור, ורענון שקט של ה־overview (בלי מסך טעינה) כך שההלוואה יוצאת מהרשימה, מהסיכומים ומהמנוע.
- **לא נבנה:** סגירה בשפה חופשית/צ'אט; סגירה חלקית; עדכון יתרה/תשלום; Diamond לנכסים; אירוע תזרים או ביטול התחייבות מקבילה.


## Contextual Writer — P1 (08/10/2026)

אותו מנוע `BusinessDraft`/Diamond, draft יחיד משותף, composer הקשרי לכל לשונית. תכנון: `FCC_CONTEXTUAL_WRITER_PLAN_20261008.md`.

- **כניסה מובנית אחת:** `POST /api/fcc/intent/start {intent, entity_id?}` → `conversation.start_intent`. אין כתיבה; הטיוטה נפתחת עם השדות הקבועים של ה־intent בלבד (`kind`, תאריך), והמשך ההשלמה/Review/אישור הוא `/api/fcc/write` הקיים. `POST /api/fcc/loans/close` הוסר (נבלע ב־`loan.close`).
- **Registry:** `draft.INTENTS` — `monthly.income` (kind=one_time, יעדי הכנסה), `monthly.household_expense` (kind=**household_expense**, יעד "הוצאות בית" אם ייחודי), `monthly.direct_cost` (kind=direct_cost, יעדי הכנסה), `monthly.goal_update` (חובה לבחור יעד), `monthly.obligation`, `loan.close` (transition: Review + אישור נפרד, כמו קודם). `+ הוצאה ביתית` **לא** ממופה ל־`direct_cost`.
- **Owner scope:** `entity_id` שאינו של הקורא = `denied` (כמו "לא נמצא"); קטלוג בחירת היעד = יעדי הקורא בלבד.
- **Idempotency:** `raw_text` ייחודי לטיוטה (`intent:<id>#<hex>`) — ניסיון חוזר של אותה טיוטה אידמפוטנטי; שתי הכנסות לגיטימיות באותו סכום באותו יום אינן נחסמות.
- **Scope:** `/api/fcc/write` מקבל `scope`; בלשוניות `loans`/`assets` טקסט חופשי לא פותח טיוטה חדשה (ה־classifier לא נקרא); מענה לטיוטה פתוחה תמיד אפשרי.
- **Frontend:** `useFccWriter` (state יחיד) + `ContextualComposer` (ב־`FccTabBar.tsx`) מעל פאנלי הלשוניות; כותרת וצ'יפים לפי לשונית (`COMPOSER` ב־`fccTabs.ts`); `writerView`/`nextWriterState` טהורים. כפתור הסגירה בכרטיס הלוואה רק קורא `loan.close` עם ה־id. `LoanClosePanel` הוסר (כפילות).
- **לא נבנה (שלבים הבאים):** עדכון יתרה/החזר, הלוואה חדשה (P2), פעולות נכס (P3), נכס נמכר (P4). בלשונית נכסים אין צ'יפים ואין קלט.


## Contextual Writer — P2: הלוואות (08/10/2026)

אותו מנגנון intent (`POST /api/fcc/intent/start`) ואותו `BusinessDraft`; שלוש ישויות חדשות ב־`FCC_CONTRACTS`, ללא מסלול כתיבה חדש (ActionGateway → `tma_fcc_write`; `Loans` כבר ברשימה המורשית). סכמה חיה נקראה לקריאה בלבד (08/10/2026): `Loan Type` = פרטית/עסקית/משכנתא; `Payment Schedule` = Monthly/Quarterly/Annually/Custom; אין שינוי סכמה.

- `loan.update_balance` → `fcc_loan_balance`: patch **שדה אחד** — `Outstanding Principal for Early Closure` (ה"יתרה" שהמסך ומנוע הסילוק מציגים). `Outstanding Balance` לא נכתב. ה־Review מציג "היום: ₪X" → חדש.
- `loan.update_payment` → `fcc_loan_payment`: patch שדה אחד — `Current Monthly Payment` (חיובי).
- `loan.create` → `fcc_loan_new`: post ל־`Loans`; חובה: שם, סוג (פרטית/עסקית/משכנתא), יתרה לסגירה, החזר חודשי, ריבית (0–100); אופציונלי (דרך "ערוך"): מלווה, סכום מקורי, תשלומים שנותרו. נכתב גם `Active Loan=true`; `Owner` נוסף בביצוע ע"י מדיניות הבעלות. לא נכתבים `Payment Status`, `Domain`, נכס מקושר.
- שדה היעד ברשומה נקבע בשרת לפי הישות (לא מטקסט המשתמש); ההלוואה המטרה נשמרת ב־`source_context` ולא ניתנת לעריכה. הלוואה של אחר = `denied`; הלוואה סגורה = `info`.
- אידמפוטנטיות: עדכון לערך שכבר שמור = `duplicate`; `loan.create` עם שם זהה להלוואה פעילה קיימת = `duplicate`.
- UI: צ'יפים `עדכון יתרה · שינוי החזר · הלוואה חדשה · סגירת הלוואה`; בכרטיס הלוואה פעילה: `עדכון יתרה · שינוי החזר · סגרתי את ההלוואה`.
- **לא נבנה:** עדכון `Outstanding Balance`/ריבית/תאריכים של הלוואה קיימת, קישור נכס בהלוואה חדשה, `Monthly Due Day`.

**החלטת SSOT ליתרה (08/10/2026, אושרה):** `Outstanding Principal for Early Closure` הוא היתרה הקנונית של ה־FCC (סילוק, חוב נוכחי, ריבית משוקללת, עלות ריבית שנתית). `Outstanding Balance` = legacy: ה־FCC לא קורא ולא כותב אותו, אין סנכרון אוטומטי, ואין fallback אליו — יתרה חסרה מוצגת "לא הוגדר". הוסרו: `current_balance` מה־payload ומה־type, ושני ה־fallback ב־`loans.py` (ממוצע ריבית משוקלל, עלות ריבית שנתית). נעילה בטסט: `test_early_closure_principal_is_the_only_balance_...`.


## Contextual Writer — P3: נכסים (08/10/2026)

אותו `POST /api/fcc/intent/start` / `BusinessDraft` / draft משותף. ללא מסלול כתיבה חדש (`Assets` כבר ברשימה המורשית; בדיקת בעלות ברשומה בביצוע). סכמה חיה נקראה לקריאה בלבד: `Assets.Next Step` = multilineText; `Next Step Owner` = select (אליהו / אהרן / אורי / משפטי / —); `Status` כולל "נמכר" ו"לא פעיל".

- `asset.update_value` → `fcc_asset_value`: patch שדה אחד — `Current Value` (≥0). `Equity`/`My Equity` הם formula ולא נכתבים.
- `asset.update_mortgage` → `fcc_asset_mortgage`: patch שדה אחד — `Mortgage Balance` (≥0; 0 = אין). ה־Review אומר במפורש שהיתרה על הנכס **לא מסתנכרנת** להלוואות המקושרות ולא נוספת אליהן.
- `asset.next_step` → `fcc_asset_step`: patch אחד של `Next Step` (טקסט חופשי; מחליף את הקיים — ה־Review מציג "היום: …") ו־`Next Step Owner` **רק אם נבחר** ערך מהרשימה החיה (ערך אחר נדחה; אין ערכים מומצאים).
- הנכס נבחר לפי id בלבד (כרטיס / בורר), נכס של אחר = `denied`, נכס עם סטטוס נמכר / לא פעיל = `info` (אין מה לעדכן). הנכס היעד ב־`source_context` ולא ניתן לעריכה. עדכון לערך/טקסט שכבר שמור = `duplicate`.
- קריאה: כרטיס נכס מציג את `Next Step` ואת האחראי כפי שנשמרו (`next_step`, `next_step_owner` ב־payload).
- UI: צ'יפים בלשונית נכסים `עדכון שווי · עדכון משכנתא · פעולה הבאה` (עם בורר נכס); בכרטיס נכס פעיל אותם שלושה כפתורים.
- **לא נבנה:** `נכס נמכר` (P4 — עדיין לא הוחלט איפה נשמרים תאריך וסכום המכירה), עדכון סוג/סטטוס/אחוז בעלות/הכנסה חודשית של נכס.


## Contextual Writer — P4: נכס נמכר (08/10/2026)

**שינוי סכמה חי (אושר ע"י הבעלים, בוצע 08/10/2026, תוספתי בלבד):** בטבלת `Assets` נוספו `Sale Date` (`fldKjiycqEVDzivsd`, date ISO) ו־`Sale Amount` (`fldubyOnMOwgpe5uT`, currency ₪ precision 2). לא נגעו בשדות/רשומות קיימים; כל 7 הנכסים (אף אחד לא נמכר) ריקים בשני השדות — אין backfill. Rollback: מחיקת שני שדות ריקים ב־UI. קבועים: `AssetFields.SALE_DATE/SALE_AMOUNT`; `schema_cache.json` עודכן (שכבת הכתיבה מאמתת שדות מולו).

- `asset.mark_sold` → `fcc_asset_sold` — **transition**: Review + אישור בתור נפרד. חובה: `sale_date` (ברירת מחדל היום, "הוסק", ניתן לעריכה) ו־`sale_amount` (>0; מחיר העסקה המלא של 100%, לפני עלויות ומיסים). אין סימון נמכר בלי מחיר.
- **כתיבה אחת אטומית:** PATCH יחיד — `Status="נמכר"` + `Sale Date` + `Sale Amount`. לא נסגרת הלוואה, לא מתאפסת משכנתא, לא נוצר נכס מזומן / אירוע כספי.
- ה־Review מציג: נכס, תאריך, מחיר (100%), **החלק שלך** (מחיר × `Ownership %`; אחוז לא ידוע = "לא ניתן לחשב", לא מניחים 100%), הלוואות פעילות מקושרות ש**יישארו פתוחות**, יתרת משכנתא ברשומה ש**לא מתאפסת**, ושהנכס יוצא מסיכומי הנכסים הפעילים ושהתמורה לא נרשמת כנכס/מזומן.
- **Read model:** נכס `נמכר` לא נכנס ל־`items`/`summary` (שווי, הון, משכנתא, הכנסה חודשית, חוב ביחס לנכסים); מוצג ב־`sold` (תאריך, מחיר, החלק שלי, הלוואות שעדיין פתוחות). `Current Value` לא מתאפס. הסיכומים מסומנים "פעילים", ובנוכחות נכס שנמכר מוצגת הערה שזה אינו "הון כולל".
- UI: צ'יפ `נכס נמכר` + כפתור `נמכר` בכרטיס נכס פעיל; אזור מקופל "נכסים שנמכרו" (בלי פעולות כתיבה).
- בטיחות: נכס של אחר = `denied`; כבר נמכר = `info`; אישור חוזר אחרי שהמכירה כבר נרשמה = `duplicate`; הנכס ב־`source_context` ולא ניתן לעריכה.
- **לא נבנה:** ביטול סימון "נמכר" (תיקון ידני ב־Airtable), `Sale Notes`, חישוב רווח/הפסד, רישום התמורה כנכס/מזומן.

## הכנסה נרשמת על "מקור", לא על "יעד" + "מקור אחר" (09/10/2026)
- **משוב הבעלים:** ב־"+ הכנסה" הוצעו רק שני יעדי הכנסה (הכנסה חודשית קבועה / הכנסה מנסיעות), בלי דרך לרשום הכנסה ממקור אחר; והמסך קרא לכל דבר "יעד" (יעד = מטרה, מקור = מאיפה ההכנסה).
- **ניסוח:** אירועי הכנסה/עלות ישירה מנוסחים "מקור" ("מאיזה מקור?", "כמה לרשום במקור X?", "• מקור: X"); הוצאה ביתית — "סעיף"; "יעד" נשאר רק ליעדים עצמם (`draft.record_noun`).
- **"מקור אחר":** בחירה נוספת בצ'יפ ההכנסה / עלות ישירה. נרשמת על יעד ההכנסה הכולל (היחיד ללא "Contributes To" — אם אין בדיוק אחד, האפשרות לא מוצעת), נשאלת שם המקור (טקסט חופשי) ונשמר בשדה ההערה הקיים של האירוע: `מקור: <שם>`. נספר בתוך היעד הכולל, לא מעליו.
- **ללא שינוי סכמה, ללא מסלול כתיבה חדש:** אותו `fcc_event`, אותו Review ואישור, בדיקת בעלות כרגיל (המזהה הסינתטי `other` נפתר רק מול יעדי הבעלים).
- **לא נבנה:** שאלת "קבוע/חד-פעמי" לכל מקור — הסוג נקבע מראש (חד-פעמי) וניתן לעריכה ב־Review. רשומות מקור קבועות (אבי, תיווכים) = יעדי הכנסה חדשים בבסיס החי, בכפוף לאישור נפרד.

### המשך (09/10/2026): סוג ההכנסה נשאל במפורש
- **משוב אחרי בדיקה בטלגרם:** אחרי בחירת מקור ("מקור אחר" + שם) לא הוצעה בחירה בין הכנסה חד-פעמית לקבועה, וההנחיה "כמה לרשום במקור הכנסה חודשית קבועה?" הטעתה (הסוג נקבע בשקט כחד-פעמי).
- **`monthly.income`** שואל כעת "איזה סוג הכנסה זו?" — **חד-פעמית / חודשית קבועה** (כפתורים; הקלדת התווית עובדת כמו לחיצה) — אחרי המקור ולפני הסכום. תשובה שאינה אחת מהשתיים נשאלת שוב ללא שמירה. ל"מקור אחר" ההנחיה היא "כמה לרשום ממקור <שם>?".
- **אזהרה בסקירה:** `monthly_recurring` נספר רק ביעד מסוג `recurring_level` (`calc.compute_goal`); ביעד תקופתי (`period_sum`/`cumulative`) הוא נרשם אך לא נכלל בסכום החודש. לכן בבחירת "חודשית קבועה" על מקור כזה ה־Review מציג הערה מפורשת, וניתן לתקן ב"ערוך".
- חוזה ה־UI: תור `ask` עם `candidates` מוצג ככפתורי בחירה (`writerView`), ללא endpoint או מסלול כתיבה חדשים.

## מתפנה לחיסכון: ה־15,000 מול הכנסות נוף הגליל (09/10/2026)
**כלל (החלטת הבעלים):** הכנסה קבועה (נוף הגליל, 8,000) "מתפנה" לחיסכון רק לפי מה שיעד ההכנסה (15,000, **נטו**) הושג ממקורות אחרים. כל שקל שחסר ליעד נלקח מנוף הגליל, וכל שקל מעל היעד מתווסף: `available = max(net − (target − fixed), 0)`. דוגמה: הושג 10,000 → חסרים 5,000 → נשארים 3,000 מנוף הגליל; 17,000 → 8,000 + 2,000 = 10,000.
- **נגזר בלבד** (`calc.savings_release`, `service.savings_release_view` → `overview.savings_release`): ללא כתיבה וללא הנחה מכותרות. ה"הכנסה הקבועה" = יעדים פעילים בקטגוריה `fixed_income` (סכום היעד); יעד ההפקדה = יעד פעיל **יחיד** בקטגוריה `long_term` (היום "תכנון פנסיוני ארוך טווח"; שאינו יחיד/חסר → בוחרים בעת ההפקדה). שני יעדי החיסכון הקיימים (3,000 / 5,000) לא שונו.
- **שאלת המשך אחרי כל הכנסה חד-פעמית ביעד הכנסה** (`follow_up: "savings"` בתשובת `executed`): "מתפנים לחיסכון ₪X. להפקיד?" (רק כשנותר סכום פנוי) — כפתור פותח את `savings.deposit`, "לא עכשיו" סוגר.
- **`savings.deposit`:** אותו `fcc_event` (חד-פעמי) על יעד הפנסיה; הסכום המוצע = מה שנותר פנוי, ניתן לעריכה; Review + "אשר" כרגיל.
- **סוף חודש (אפשרות א, בלי הודעה יזומה):** בשבעת הימים האחרונים בחודש כרטיס "מתפנה לחיסכון" שואל "סך הפקדות החודש: ₪X. נכון?" ומציג פער מול חודש מלא (`expected = fixed + extra`).
- **סיבת פער (`savings.gap_reason`):** כשיש פער בסוף החודש — שאלה עם כפתורים (הוצאה חריגה בנוף הגליל / הוצאה חריגה בבית / קושי בהכנסה החודש, או טקסט חופשי); נרשמת כאירוע `note` קיים על יעד הפנסיה: `פער הפקדה YYYY-MM: <סיבה>`, סכום = גובה הפער. אינו משפיע על חישובים (`note` ללא סמנטיקת סכום).
- **ללא שינוי סכמה / מסלול כתיבה חדש / שינוי בבסיס החי.** בדיקות: 8 pytest חדשות; presentation + markup בצד הלקוח.
- **לא נבנה:** הודעה יזומה בטלגרם בסוף החודש (דורשת scheduler + דגל + פריסה); שאלת סוף חודש לחודש שעבר (החלון הוא 7 הימים האחרונים בלבד).

## פעולה הבאה בנכס: הטקסט נשמר כפי שנכתב (09/10/2026)
- **משוב אחרי בדיקה בטלגרם:** רישום "פעולה הבאה" הסתיים ב"לא הצלחתי לעבד את הבקשה כרגע — נסו שוב". הנתונים עצמם קיימים בבסיס החי (השדה `Next Step`, `fldOoc7gGuyAL2prL`, מלא בכל 7 הנכסים; האחראי ב־`Next Step Owner`), כלומר יש איפה לרשום.
- **שורש:** תשובת הטקסט החופשי (`step`) עברה את מודל ההשלמה (`classifier.fill_reply`), שנדרש להחזיר ציטוט־ראיה; כל כשל/חריגה במודל נפלו כקריסת תור. זה נתיב מיותר: טקסט חופשי של המשתמש לא צריך לעבור פרשנות.
- **תיקון:** `step` נשמר כפי שנכתב (עד 500 תווים; מילות פקודה — אשר/ערוך/דלג/בטל — אינן תשובה). בעריכה: "אורי" / "אחראי אורי" = בחירת אחראי מהרשימה החיה, כל טקסט אחר = הפעולה החדשה. בנוסף, חריגה בקריאת המודל בכל זרימה היא "לא הובן" ולא תור שקרס.
- בדיקות: המודל חסום (`RuntimeError`) והזרימה מלאה עוברת עד ה־PATCH היחיד של הנכס.

## הכותב דטרמיניסטי — בלי מודל בנתיב (09/10/2026)
- **למה:** לוגי הפרודקשן אישרו `anthropic.BadRequestError 400 — credit balance is too low`. כל תשובה שהצריכה את מודל ההשלמה (טקסט חופשי, מספרים בהלוואה/נכס, עריכה) נכשלה, וגם פתיחת טיוטה מטקסט חופשי. הכותב צריך לעבוד כמו "כותב הזהב" (BusinessDraft/Diamond): קבוע, בלי פרשנות.
- **מה שונה** (`conversation.DeterministicExtractor` מחליף את `LlmExtractor`; אף קריאת `call_anthropic_text` בנתיב ה־TMA):
  - **פתיחה:** רק מכפתורים/פעולות כרטיס (`/api/fcc/intent/start`). אין פתיחת טיוטה מטקסט חופשי. נוסף צ'יפ `+ יעד חדש` (`monthly.goal_new`) במקום "תוסיף יעד …" בטקסט.
  - **תשובות:** מספר/אחוז/תאריך נקראים בכלל; בחירה סגורה (קטגוריה, תקופה, שייכות, סוג הלוואה…) = **כפתורים** (לחיצה שולחת את התווית, כמו הקלדתה); טקסט חופשי (שם, כותרת, ספק, מלווה, הערה, פעולה הבאה) נשמר **כפי שנכתב**.
  - **עריכה ב־Review:** `<תווית> <ערך>` — התוויות שה־Review מציג ("סכום 8000", "קטגוריה חיסכון", "שם נטפליקס"). מה שלא מובן — לא משתנה ולא מנחשים.
  - חריגה בקריאת מודל (אם נשאר מחבר) = "לא הובן", לא תור שקרס.
- **צ'אט (סוכן):** `PresetIntentExtractor` נשאר (הסוכן כבר סיווג); ההשלמות והעריכות דטרמיניסטיות גם שם. `classifier.py` אינו בשימוש בנתיב ה־TMA.
