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

## פעולה הבאה בנכס = משימות עם מחזור חיים (09/10/2026)
**החלטות הבעלים:** כמה פעולות פתוחות לנכס; "בוטלה" = "בוצע" עם הערה (בלי סטטוס חדש); 7 הטקסטים הישנים נשארים כמות שהם; **אפשרות עריכה** (פעולה לא תמיד זהה לתכנית, ולפעמים רק חלק ממנה התחיל).
- **מקור הנתונים:** משימה בטבלת `Tasks` (Topic `כספים`, Owner = הבעלים), מתויגת `[FCC-ASSET:<מזהה נכס>]` בתיאור (שורה שנייה: `אחראי: <בחירה מהרשימה החיה>`); תג משימות היעדים הוא `[FCC:` ולכן אין חפיפה. סטטוסים קיימים בבסיס: ממתין / בביצוע / בוצע. **אין שינוי סכמה.**
- **הוספת פעולה** (`asset.next_step`): יוצרת משימה **חדשה**; פעולות פתוחות אחרות לא נדרסות. אחראי ותאריך יעד אופציונליים (עריכה ב־Review: "אחראי אורי", "תאריך יעד 2026-11-01").
- **פעולות על כרטיס** (`entity_id` = המשימה; כולן Review + "אשר"): `asset.step_start` (ממתין ← בביצוע, "בתהליך"), `asset.step_done` (בוצע), `asset.step_cancel` (בוצע + שורת היסטוריה "בוטלה ב־…"), `asset.step_edit` (טקסט / אחראי / תאריך; הסטטוס וההיסטוריה נשמרים; אפשר לעדכן "רק חלק").
- **היסטוריה:** כל מעבר מוסיף שורה לתיאור ("התחילה ב־…", "הושלמה ב־…", "בוטלה ב־…"). משימה סגורה יוצאת מהמסך ונשארת ב־`Tasks`.
- **אחרי סיום/ביטול** של הפעולה האחרונה הפתוחה בנכס: "מה הפעולה הבאה ב<נכס>?" — הוסף פעולה / אין פעולה נוספת (`follow_up_asset` בתשובת `executed`).
- **טקסט ישן:** `Assets.Next Step` / `Next Step Owner` ממשיכים להיקרא ומוצגים כ"פעולה קודמת (ישנה)"; כבר לא נכתבים. אין העברה אוטומטית.
- **בטיחות:** משימה של אחר / סגורה / לא קיימת = `denied`; כתיבה חוזרת אחרי שנסגרה = `duplicate`; בדיקת בעלות ברשומה בביצוע (מדיניות `Tasks`).
- **כללי הטקסט החופשי (נבדק):** טקסט הפעולה נשמר כפי שנכתב, שורה אחת (רווחים/שורות חדשות מתכווצים), עד 500 תווים; מילות פקודה (אשר/ערוך/דלג/בטל) אינן פעולה. בעריכה רק שני כללים קבועים: `אחראי <שם מהרשימה החיה>` ו־`תאריך יעד <תאריך>` — ערך שלא נקרא = "לא הבנתי" ולא נשמר כטקסט; כל טקסט אחר (גם אם מתחיל במילת תווית כמו "הפעולה…") הוא הפעולה החדשה. שם אחראי כטקסט בודד ("אורי") נחשב טקסט הפעולה, לא בחירת אחראי.

## כפתור "עדכן יעד" על כל כרטיס יעד (10/10/2026)
- כל כרטיס יעד במסך "חודשי" מציג כפתור **עדכן יעד**; הלחיצה שולחת `{intent: "monthly.goal_update", entity_id}` בלבד — אותו מסלול כותב דטרמיניסטי כמו הצ'יפ "+ עדכון יעד" (ללא נתיב כתיבה חדש).
- בורר "איזה יעד?" מציג כעת גם את היעד הנוכחי (`goalPickLabel`, למשל "הכנסה חודשית קבועה · ‏₪15,000").
- אומת מול הנתונים החיים (קריאה בלבד): היעד "הכנסה חודשית קבועה" (15,000) קיים, פעיל ושייך ל־Eliyahu, ולכן אמור להופיע ברשימה; לא שוחזר מקרה שבו הוא חסר.

## הלוואות: פרעון חלקי, הסדר פירעון, פעולה הבאה, וחובות שחייבים לי (10/10/2026)
כולם עוברים באותה זרימה דטרמיניסטית (צ'יפ/כפתור כרטיס → טיוטה → סקירה → "אשר" → writes קפואים דרך `tma_fcc_write`); אין מודל ואין נתיב כתיבה חדש.

- **כיוון החוב** — שדה `Loans.Direction` (`אני חייב` | `חייבים לי`; ריק = אני חייב, כך שההלוואות הקיימות לא משתנות). **השדה עוד לא נוצר בטבלה החיה** (הכנסתו נחסמה בסשן, ראו דוח הסשן): עד שייווצר, קריאה עובדת (כל הרשומות "אני חייב") אבל יצירת "חוב שחייבים לי" תיכשל בביצוע. חובות שחייבים לי מוצגים בנפרד ולא נכנסים לסך ההתחייבויות, לדירוגים, לסימולטור הפירעון ולחוב המקושר לנכסים.
- **פרעון חלקי** (`loan.partial_payment`): סכום → "מאיפה שולם / מה נעשה עם הכסף" (חיסכון / שוטף / נכס פעיל של הבעלים — כפתורים בלבד) → סקירה "יתרה ישנה ← חדשה". כתיבה: patch אחד להלוואה (יתרה חדשה = ישנה − סכום, לא מתחת ל־0, + שורת היסטוריה בהערות) ולחוב *שלי* עם יעד חוב פעיל אחד גם אירוע התקדמות (מפתח כפילות לפי הטיוטה). חוב שחייבים לי: בלי אירוע ובלי יעד — תשלום שהתקבל אינו הכנסה. סכום גדול מהיתרה נדחה (מפנה ל"סגירת הלוואה"). ההחזר החודשי ומספר התשלומים לא משתנים. היעד/המקור נרשמים כטקסט בלבד — הכסף לא מועבר בפועל לחיסכון/נכס.
- **הסדר פירעון** (`loan.arrangement`, וגם חלק מ"חוב חדש שחייבים לי"): בחירה בכפתורים — פירעון חודשי קבוע (סכום) / מועד פירעון (תאריך) / אין הסדר. נשמר ב־`Payment Schedule` (Monthly/Custom), `Current Monthly Payment`, `End Date` + שורה מתוארכת בהערות. "אין הסדר" נרשם בהערות בלבד (אין שדה נפרד), והכרטיס מציג "לא הוגדר הסדר פירעון" עד שמוגדר.
- **פעולה הבאה בהלוואה/חוב** (`loan.next_step` + אותם `asset.step_*` על Task): אותו מנגנון Tasks של נכסים עם תג `[FCC-LOAN:<id>]` (`service.next_actions` מכליל נכסים והלוואות; `asset_tasks`/`loan_tasks` מסננים). שאלת "מה הפעולה הבאה?" אחרי סיום נשארת לנכסים בלבד.
- **חוב חדש שחייבים לי** (`loan.receivable_new`): שם החייב, יתרה, הסדר פירעון → שורה חדשה ב־`Loans` עם `Direction = חייבים לי`. סגירה ("נפרע במלואו") משתמשת ב־`loan.close` בלי אירוע התקדמות.
- בדיקות: 19 חדשות ב־`test_financial_control_center.py` (258 עוברות) + בדיקות פרונט ב־`fccLoans/fccTabs`.

## עדכון יעד: שלב "איזה שדה" + מאזן חובות והון אישי (10/10/2026)
- **עדכון יעד** (באג שדווח: "מה לעדכן?" ואז "לא הבנתי את העריכה"): הזרימה היא עכשיו שני שלבים בכפתורים — איזה שדה (סכום יעד / שם / קטגוריה / תקופה / שיטת חישוב / תאריך יעד / תאריך התחלה), ואז הערך החדש (עם "היום: …"; שדה סגור — בכפתורים). המשתמש עדיין יכול להקליד ישירות "סכום יעד 18000" / "סכום 18000" / "18,000" ולדלג על שלב השדה. "ערוך" בסקירה מציג שוב את בחירת השדה. ערך לא תקין שואל שוב את אותו שדה.
- **מאזן חובות** (`loans.debt_balance`, מפתח `balance` ב־payload ההלוואות): חייבים לי (כל החובות הפעילים) מול החובות שלי **ללא הלוואות המקושרות לנכס** (`Related Asset`) — החוב שלהן כבר בהון הנכס, ולכן לא נספרות פעמיים. נטו חיובי = נכס פיננסי נטו; נטו שלילי = אינו נכס אך נכנס להון האישי. יתרה לא ידועה מדווחת ולא הופכת ל־0. הכרטיס מוצג בטאב ההלוואות כשיש חובות שחייבים לי.
- **הון אישי מחושב** (`assets.personal_equity`, בטאב הנכסים): חלקי בהון הנכסים הפעילים (`My Equity` כשקיים, אחרת (שווי − משכנתא בנכס) × אחוז בעלות; חסר קלט = לא ידוע, בלי להניח 100%) + הנטו מהמאזן. מציג כיסוי ("מבוסס על N מתוך M נכסים").
- קריאת `Direction` סלחנית לרווח מיותר בשם האפשרות; הכתיבה משתמשת ב־`חייבים לי` (בלי רווח) — יש לוודא ששם האפשרות בטבלה זהה.

## מקורות הכנסה קבועים: "+ מקור הכנסה" (10/10/2026)
הנושא האחרון שנשאר ברשימה ("יצירת מקורות כמו אבי / תיווכים"): במקום ליצור רשומות בבסיס החי ידנית — הבעלים יוצר אותן במסך, כל אחת עם סקירה ואישור.
- צ'יפ **+ מקור הכנסה** (`monthly.source_new`, entity `fcc_source_new`): שם → יעד לתקופה → תקופה (חודשי / שבועי, כפתורים) → סקירה → "אשר". כתיבה: post אחד ל־`Financial Goals` — `Category=income`, `Calc Method=period_sum`, `Status=active`, `Contributes To=[יעד ההכנסה הכולל]`. המקור נספר **בתוך** היעד הכולל (roll-up קיים), לא מעליו; היעד הכולל לא מתנפח.
- ההורה הוא יעד ההכנסה הכולל היחיד של הבעלים (ללא "Contributes To"); אין יעד כזה או יש כמה — מבקשים הבהרה ולא מנחשים. שם כפול נחסם (`duplicate`).
- אבטחה: ל־`Financial Goals` נוסף `linked_owner_checks` על `Contributes To` ב־`core/data_access_policy.py` — אי אפשר לתלות מקור מתחת ליעד של אדם אחר (גם בנתיב הגנרי).
- לא נוצרה שום רשומה בבסיס החי על ידי הסשן.

## יתרות הלוואות מתעדכנות אוטומטית בכל תאריך חיוב (12/10/2026)
**החלטת הבעלים:** עיקר העדכון אוטומטי, והעדכון הידני הוא תיקון מדי פעם מול הבנק.
- **הלוגיקה** (`loans.auto_step`, טהורה): בכל תאריך חיוב מוחל תשלום אחד לפי `יתרה × (1 + ריבית שנתית/12) − החזר חודשי`; `Payments Remaining` יורד באחד; `Next Payment Due` מתקדם חודש (תאריך חיוב 31 מתקצר לסוף החודש); התשלום האחרון מאפס את היתרה. שורת היסטוריה "עדכון אוטומטי (תאריך): N תשלומים — יתרה X ← Y" נוספת להערות (הישנות נשמרות). אומת על הלוואה חיה: היתרה השמורה שווה לערך הנוכחי של תשלומיה לפי אותה נוסחה (±0.7%).
- **אידמפוטנטיות:** `Next Payment Due` הוא המפתח — הלוואה נוגעים בה רק כשהגיע זמנה; ריצה שנייה באותו יום לא כותבת כלום. ריצה ראשונה (אין `Next Payment Due`) רק קובעת אותו מ־`Monthly Due Day` (היתרה השמורה היא "נכון להיום"). פער ארוך מוחל בפרוסות של עד 12 חודשים.
- **מה לא נעשה אוטומטית:** לא נסגרת הלוואה (תשלומים אחרונים → תג "כל התשלומים שולמו — לסגור?"); חוב שחייבים לך לא נוגעים בו; הלוואה עם קלט חסר (ריבית/החזר/יתרה) או החזר נמוך מהריבית (היתרה הייתה גדלה) — מדלגים עם סיבה ביומן, בלי להמציא יתרה. ריבית משתנה (כמו הפועלים בפריים) = הערכה; מתקנים ב"עדכון יתרה".
- **תיקון ידני:** "עדכון יתרה" אחרי שתאריך החיוב חלף מקדם גם את `Next Payment Due` לחיוב הבא (מצוין בסקירה), כדי שהחיוב שכבר כלול ביתרה המתוקנת לא יוחל שוב.
- **הרצה:** `scheduler._job_fcc_loan_auto_step` יומי 05:20, שקט (בלי הודעה), flag **`FEATURE_FCC_LOAN_AUTO_STEP` — ברירת מחדל כבוי**. פועל רק לבעלים ש־`FEATURE_FINANCIAL_CONTROL_CENTER` + `FCC_CANARY_USER_IDS` מתירים; התכנון (`service.plan_loan_auto_step`) קריאה-בלבד ובעל-scope, והכתיבה (patch אחד להלוואה) דרך `airtable_gateway` מה־scheduler — חבילת FCC עצמה לא כותבת.
- **תצוגה:** כשה־flag דלוק, מסך ההלוואות אומר שהיתרות מתעדכנות אוטומטית (הערכה); בכרטיס שורת "תשלום הבא".
- **הפעלה (שלך):** להוסיף `FEATURE_FCC_LOAN_AUTO_STEP=true` ב־Render ולבצע redeploy. בהפעלה הראשונה כל הלוואה שתאריך החיוב שלה (`Next Payment Due`) כבר חלף (למשל 10/10) תקבל את התשלום שחלף.

## שינוי ריבית פריים — מספר אחד מזיז את כל ההלוואות (12/10/2026)
**החלטת הבעלים:** כל ההלוואות צמודות פריים; עדכון ידני במכה אחת.
- צ'יפ **שינוי פריים** (`loan.prime_change`, entity `fcc_prime_change`) בטאב ההלוואות: שואל מספר אחד — השינוי בנקודות אחוז (`+0.25`, `-0.5`, גם מינוס טיפוגרפי). 0 או יותר מ־5 נקודות נדחים (טעות הקלדה).
- הסקירה מציגה **כל** הלוואה מושפעת: ריבית ישנה ← חדשה והחזר חודשי ישן ← חדש. מושפעות: הלוואות פעילות שלך (לא חובות שחייבים לך, לא סגורות, לא של אדם אחר) עם ריבית ידועה.
- **ההחזר החדש** = ההחזר הקיים כפול יחס ההחזרים (`PMT`) בריבית החדשה מול הישנה על פני התשלומים שנותרו — תאריך הסיום נשמר, והבסיס הוא ההחזר האמיתי מהבנק ולא נוסחה גנרית. חסרים יתרה / החזר / תשלומים שנותרו → מתעדכנת רק הריבית (מצוין בסקירה). ריבית שהייתה יורדת מתחת ל־0 → ההלוואה לא מתעדכנת.
- כתיבה: patch אחד לכל הלוואה (`Interest Rate`, `Current Monthly Payment` כשאפשר, שורת היסטוריה מתוארכת בהערות; ההערות הקודמות נשמרות) דרך אותו מסלול "אשר"/`tma_fcc_write`; `_already_applied` מזהה הלוואה שכבר עודכנה (ניסיון חוזר לא כותב פעמיים). העדכון האוטומטי החודשי ממשיך מהריבית וההחזר החדשים.
- אחרי שהבנק מפרסם את ההחזר שלו אפשר לתקן הלוואה ספציפית ב"שינוי החזר".
- לא נבנה: שאיבה אוטומטית של ריבית בנק ישראל (שיקול: כל בנק מיישם בתאריך אחר).

## יעדי פעולה והעברת הפעולה הישנה (12/10/2026)

- **יעד של פעולה** (בלי סכום יעד וקטגוריה לא מספרית — למשל מכירת יבנאל) כבר לא מקבל ״עדכן יעד״ של סכומים. בכרטיס שלו שלושה כפתורים: ״פעולה הבאה״ (משימת מעקב עם תג היעד), ״הושלם״ ו״השהה״ (עדכון `Status` בלבד, דרך סקירה ואישור). ניסיון עדכון סכום ביעד כזה נענה בהסבר.
- **הפעולה הישנה** (שדה `Assets.Next Step` הבודד) מוצגת עכשיו כ״פעולה ישנה (טרם הועברה)״ עם כפתור ״העבר לפעולות פתוחות״: נוצרת משימה פתוחה (טקסט + אחראי) והשדה הישן מתרוקן, בסקירה ואישור אחד. בלי הכפתור שום דבר לא נכתב.
- `Status` של יעד נכתב כ־`done` / `paused` לפי התיעוד בסכמה; לא אומת מול ה־base החי.

## מכסה שבועית קבועה (12/10/2026)

- ליד ״יעד דינמי לשבוע״ (נשאר כמו שהוא) נוסף חישוב קבוע ליעדים חודשיים: **יעד ÷ ימי החודש × 7**, כל יום לפי החודש שלו. שבוע שחוצה גבול חודש לוקח את ימיו האחרונים מהחודש הבא (`calc.weekly_quota`).
- שבועות מתחילים ביום ראשון. הימים של תחילת החודש שלפני יום ראשון הראשון שייכים לשבוע האחרון של החודש הקודם.
- חסר או עודף של שבוע עובר לשבוע הבא (`carry_in`); המצב האמיתי הוא `balance`, והעודף (`surplus`) הוא מה שאפשר להתרווח איתו או להפריש.
- מוצג בכרטיס יעד חודשי ובכרטיס ההכנסה בראש המסך. הלדג׳ר מחושב מחדש בכל קריאה מהאירועים, בלי כתיבה ל־Airtable.
- הקירוב: הלדג׳ר משתמש ביעד הנוכחי בכל השבועות (שינוי יעד באמצע החודש לא מחשב מחדש שבועות קודמים).

## שאלת העודף השבועי (12/10/2026)

- הכותרת של המכסה השבועית היא **הושג / נדרש** (למשל ₪1,660 / ₪1,547), ומתחתיה העודף או החסר.
- כשהשבוע נסגר (שישי/שבת), או עד שנענתה שאלה על השבוע האחרון שנסגר, יש עודף ואין תשובה — מופיע כרטיס עם השאלה ״מה לעשות בעודף?״ ושלושה כפתורים. בלי בחירה קבועה במסך.
  - **להעביר** — נשאר בחשבון ומקטין את הנדרש בשבוע הבא (זו גם ברירת המחדל אם לא עונים).
  - **להשתמש** — יוצא מהחשבון; בשבוע הבא נדרשת שוב המכסה המלאה. לא נרשמת הוצאה.
  - **לחסוך** — הפקדה לחיסכון (יעד ה־`long_term` היחיד והפעיל) ויציאה מהחשבון.
- כל תשובה עוברת סקירה ואישור. הסכום ניתן להורדה (לא להעלאה מעל העודף). הכתיבה: אירוע `note` על יעד ההכנסה (`עודף שבועי <יום ראשון>: הועבר/נוצל/נחסך`) — הוא מונע שאלה חוזרת והחשבון קורא ממנו מה נוצל; ל״לחסוך״ נוספת הפקדה רגילה.
- לא נשאלים על השבוע האחרון בחודש (שאלת סוף החודש מכסה אותו), והחשבון מתאפס בתחילת חודש.

## הכנסות אחרונות שנרשמו (12/10/2026)

- לפני כן המסך הציג רק את 10 האירועים האחרונים (תאריך וסכום, בלי שם המקור) — לא מספיק כדי לדעת מה כבר נרשם.
- נוסף `recent_incomes` ב־`/api/fcc/overview` (`service.recent_incomes`): עד 12 רשומות הכנסה והוצאה ישירה אחרונות של הבעלים בלבד, מהחדשה לישנה, עם שם המקור/היעד והערה. אותו יעד + סוג + סכום + יום מסומנים ״ייתכן כפילות״.
- במסך החודשי: ״הכנסות אחרונות שנרשמו״ מעל ״התקדמות אחרונה״. הפקדות חיסכון והערות מערכת לא מופיעות שם.

## עודף שבועי: שמירה להחלטה בסוף החודש היא ברירת המחדל (12/10/2026)

- **לכל שבוע התמריץ שלו.** עודף של שבוע כבר לא מקטין אוטומטית את הנדרש בשבוע הבא. **חסר** עדיין עובר קדימה (הוא עדיין חייב).
- ברירת המחדל לעודף היא **לשמור להחלטה בסוף החודש**. הסכום המצטבר (`held_total`) מוצג כל החודש — תמונת המצב באמצע החודש.
- השאלה בסגירת שבוע (פעם אחת לשבוע) עם ארבע תשובות: **לשמור לסוף החודש** (הראשונה), להעביר לשבוע הבא (מקטין את הנדרש בו), להשתמש, לחסוך. ״לשמור״ רק רושמת שהשאלה נענתה; בלי תשובה ההתנהגות זהה.
- **בסוף החודש** (בשבוע האחרון, ובימים הראשונים של החודש הבא): שאלה אחת על כל העודף שנשמר, עם שתי תשובות — להשתמש או לחסוך. הסימון: ״סיכום חודש YYYY-MM: נוצל/נחסך״.
- סימוני שבוע שנרשמו קודם (״הועבר״ בלי סכום) נקראים כהעברת כל העודף של אותו שבוע.

## עדכון ריבית ותשלומים שנותרו בהלוואה (12/10/2026)

- בכרטיס כל הלוואה פעילה, ובצ׳יפים של לשונית ההלוואות: ״עדכון ריבית״ (`loan.update_rate`) ו־״תשלומים שנותרו״ (`loan.update_term`). כל אחד מעדכן שדה אחד בלבד (`Interest Rate (%)` / `Payments Remaining`) דרך סקירה ואישור, ומציג את הערך הנוכחי.
- החזר חודשי ויתרה לא מחושבים מחדש בעדכון כזה; לשינוי פריים יש ״שינוי פריים״ שמחשב את ההחזר מחדש.

## Monthly cashflow — "תזרים" tab (01/11/2026, owner-approved; stage 1 `6e56723`, stage 2 this section)

- **Question it answers:** per month, income by source vs. expenses by category, the balance (or the shortfall), month-over-month change, spikes and large items. Pure model `core/financial_control/cashflow.py` (no I/O); owner-scoped reads in `service.cashflow_view`; `GET /api/fcc/cashflow` (same gate as net-worth: flag + canary + owner, 404 otherwise).
- **Category storage (owner decision):** a new field on `Financial Progress Events` — `Expense Category` (live `fldG6juSyoViNriOf`, **singleLineText**). Text, not a select, so a new category needs no schema change: the 15 built-in keys (`cashflow.EXPENSE_CATEGORIES`: the owner's ten + בריאות, פנאי ובילויים, מיסים ואגרות, מתנות ואירועים, כללי) or any other non-empty text (a custom category, capped at 40 chars). Empty = "לא מסווג" (never guessed). Finer detail later (sub-categories) can be a second text field or a `Parent/Child` naming — not built.
- **Income sources:** a source goal (it `Contributes To` a parent) or a goal with no sources is a source by its title; events on a TOTAL goal are "כללי" unless the note is `מקור: <שם>`; `fixed_income` goals are standing monthly sources at their effective target from their start date (a recorded entry replaces the standing amount, never adds). `monthly_recurring` income events are not read here (limitation).
- **Expenses:** `household_expense` events, superseded ignored, `abs(amount)`. **Obligations are not added** (the actual charge is the expense; adding both counts it twice) — they are for the recommendations stage. **Loans are an expense:** a recorded loan charge wins; otherwise the active loans' scheduled monthly payment fills the CURRENT month only, marked "הערכה".
- **Unknown != 0:** a month with no income or no expenses recorded has no balance (`missing` says which) and is excluded from changes/spikes.
- **Not built yet:** the category / source questions in the write flow (stage 3 — until then new household expenses are uncategorized), recommendations from obligations (stage 4), bank / credit-card history import (stage 5).
- Verification: `test_fcc_cashflow.py` (17), `test_fcc_cashflow_service.py` (7), `fccCashflow.test.ts`. Device/production: NOT verified.

### Stage 3 (01/11/2026): the write flow asks the category and the income source

- **Expense category:** `fcc_event` gets `expense_category` (-> `Expense Category`), REQUIRED when `kind = household_expense`, asked after the amount. Buttons: the 15 built-in categories, the owner's own categories already in use (own events only, most used first, max 12) and "+ קטגוריה חדשה" (asks a name). Typing a built-in label = clicking it; any other text is a custom category (whitespace collapsed, capped at 40 chars); a command word or a bare number is not a category and the question is asked again. A category that does not exist yet is created by the approval itself and the review says so. Written only for household expenses (never on income / direct-cost / note events).
- **Income source:** "מקור אחר" is gone. The list ends with **"כללי"** (booked on the total income goal, no name asked; the cashflow reads a note-less total-goal entry as "כללי") and **"+ מקור חדש"** (asks a name, stored as `מקור: <שם>` in the note and grouped by that name in the cashflow). A permanent source is still created with "+ מקור הכנסה". Both choices exist only when there is exactly one total income goal.
- **TMA:** the "תזרים" tab has "+ הכנסה" / "+ הוצאה" chips (same intents and the same one shared draft as the monthly tab) and refreshes in place after a saved entry.
- **Not done:** the classifier / agent (`fcc_update`) does not supply a category (the question is asked); recommendations (stage 4); bank / credit-card import (stage 5). Verification: `test_financial_control_center.py` (399), `fccTabs.test.ts`. Device/production: NOT verified.

### Stage 4 (01/11/2026): savings opportunities ("הזדמנויות לחיסכון")

- **Deterministic, numbers-only** (`cashflow.recommendations`; no model, no invented amount). Each card carries `kind`, a title, optional `amount` with a `basis`, the `facts` it stands on and an optional `hint`.
- **Amount bases are never blended:** `stated` (a saving the owner entered on an obligation), `inferred` (a `cancel` decision with no stated saving = its monthly cost; a decision is not a cancellation, so the hint is the existing "ביטלתי את X" phrase) and `upper_bound` (a rising category / a spike — a ceiling, not a saving). The summary totals only `stated` and `inferred`, separately, and shows what share of the average monthly gap (up to 3 known complete months) they cover.
- **Cards:** flagged obligations; optional + unreviewed obligations (no amount; `keep` is respected); a non-loan category that rose 3 known complete months in a row by >= ₪300; category spikes; an uncategorized share >= 20%; the largest non-loan category when >= 30%. Sorted commitment > rising > spike > optional > uncategorized > focus, capped at 12 (`total` says how many exist).
- **Boundaries:** obligations are read owner-scoped and are never part of an expense or balance; an unreadable obligations table is `commitments_known: false`. Nothing is written by this stage; acting on a card uses the existing obligation chat/draft flow. Thresholds are exposed in `thresholds`.
- Verification: `test_fcc_cashflow.py`, `test_fcc_cashflow_service.py`, `fccCashflow.test.ts`. Device/production: NOT verified.

### Stage 5a (01/11/2026): bank-statement parser + classifier (offline, read-only)

- **Source format:** the bank's "תנועות בחשבון" PDF has a text layer (`pdftotext -layout`): date, description, debit, credit, running balance. Verified on the owner's real statement (191 rows, 15/07-19/10/2026): every one of the 190 transitions between neighbouring rows adds up and agrees with the amount's column; the oldest row has no older neighbour and is the only one decided by its column alone.
- **Trust rule:** a row counts as `verified` only if the balance chain and the column agree; a conflict, a broken chain or an unparsed line makes the whole statement `ok = False` (an incomplete statement is not imported).
- **A statement is a ledger of movements, not of expenses:** credit-card settlements, own transfers and returned charges are classified apart. In the owner's statement ~68% of all debits are card settlements — their categories exist only on the card statements (stage 5c). Until a card statement covers a period, the settlement is the only trace of that spending (open owner decision: show it as an uncategorized "כרטיס ללא פירוט" line that IS counted, and drop it once the card statement is imported).
- **Classification:** high-precision built-in rules on whole tokens + direction; unknown stays unknown; the owner's rules (match / kind / category / direction) win. Every credit is an `income_candidate` until a source is assigned.
- **Idempotency:** each row has a key from (account label, date, direction, amount, balance, description) — the balance keeps two identical same-day charges apart; the account number is never part of it.
- **Privacy:** the script refuses an output directory inside the repository; tests use synthetic statements only.
- **Next:** 5b = owner-scoped rules table (owner approval for a new table) + one bulk review -> אשר into `Financial Progress Events` (expenses as `household_expense` with the category, credits as income on the chosen source, `Verification = statement`); 5c = credit-card statements and matching of settlements. Verification: `test_fcc_bank_import.py`. Production: NOT verified.

### Stage 5c (01/11/2026): credit-card statement parser + matching to the bank (offline, read-only)

- **Format (Max):** the PDF's Hebrew is stored in visual order, so `pdftotext` returns unreadable text; `pdfminer.six` returns the fragments with positions, and the script reverses every Hebrew run. The parser works on `Fragment(page, x, y, text)` (logical Hebrew): a row = fragments within 4 points vertically; columns are read RTL (date, merchant, type, transaction amount, charge amount, remarks); a section ends at its own `סה"כ חיובים בתאריך ... ₪total` line and takes that billing date.
- **Trust rule:** the sum of a section's charge amounts must equal the statement's own total. On the owner's statement every one of the 7 sections reconciles to the agora (e.g. card 7716: ₪8,005.00 over 61 rows; card 6428: ₪4,516.01 over 24 rows incl. four loan instalments).
- **What the card statement revealed about the bank statement:** the bank's "מקס איט פיננסי" debits are this card — both the monthly bill and the *immediate* charges, which are ATM cash withdrawals made with the card (₪1,000 / 2,500 / 2,800 / 500 / 2,500). A withdrawal is `cash_withdrawal`, not spending. Four card loans are charged inside the bill: only the monthly instalment is an expense (`loans`), never the loan's full amount.
- **No double counting:** a section total is matched to the bank's card-settlement debit (same amount, billing date .. +3 days, each bank line once). A matched settlement is no longer spending — its merchant rows take its place; an unmatched one keeps counting until its own card statement is imported. All 7 sections matched (₪21,821.01); the other 48 settlements (₪115,804) need their statements (other months / Isracard / Cal / Mastercard).
- **Not done:** writing any of this to Airtable (5b), other issuers' layouts. Verification: `test_fcc_card_import.py` (synthetic fragments). The PDF extraction layer was run on the owner's real statement but has no repo test (no real statement may be committed). Production: NOT verified.

### Owner decisions on the bank / card import (01/11/2026)

- **Card payments are not spending until itemized.** Max / Isracard debits are sometimes the monthly bill and sometimes a cash withdrawal repaid after a day or two; neither is counted as an expense until the card statement itemizes it (this supersedes the earlier proposal of counting an un-itemized settlement as a "card without detail" line). The bank report shows the pending amount apart.
- **Cash:** an ATM withdrawal is neutral (`cash_withdrawal`), and a cash deposit is never income by itself.
- **Income only by explicit approval:** every credit (cash deposit, bit, mobile transfer, bank credit) is a candidate; only an owner rule `income` + a source name makes income. The owner's accounts are not assumed (no built-in `transfer` rule).
- **Importable = decided:** an expense with a category, or approved income with its source. Everything else waits.
- **Owner classification (as rules, kept OUT of the repo — these are personal recipients):** institutions (`institutions`): חכמי דורות, אורחות תורה, מרכז התורה; `loans`: רובי קבוצות (a loan on an asset); donations (`donations`): the other charities named in the statement. To be stored in the owner-scoped rules table of 5b once the owner approves creating it.

### Transfers for review, tax refunds, Isracard (01/11/2026)

- **Transfers are checked one by one (owner decision):** every transfer / bit, credit or debit, and a credit from another bank is `needs_review` — not classified, not counted, not importable. The bank report writes `review_one_by_one.csv` (date, direction, amount, description, key, and an empty decision column: own account / income / loan / other). A single row is settled by an owner rule with its `key`; for now rows are only MARKED. A cash deposit (ATM / teller) is not a transfer: it stays an income candidate.
- **A tax refund is a refund:** a credit from the tax authorities / a VAT credit is `refund` in `taxes` (a negative expense), importable, never income.
- **Scholarship:** a recurring credit the owner described as a scholarship stays an income CANDIDATE until the owner approves it as income with a source name (describing it is not approving it).
- **Isracard:** same section-must-add-up rule; columns differ (sector instead of type, a card-at-the-business column, undated fee lines with VAT). Installment purchases ("תשלום 4 מתוך 12") are the purchase's instalment; only a card LOAN (Max) is `loans`.
- **Open:** the owner's approval to create the owner-scoped rules table (5b) and the remaining card statements ("כרטיסי אשראי ל", Mastercard, other months). Verification: `test_fcc_bank_import.py`, `test_fcc_card_import.py`. Production: NOT verified.

### Excel card statements (01/11/2026) — the preferred input

- **Why Excel:** the issuers' PDFs differ per issuer and (Max) store Hebrew in visual order; the Excel export has named columns. `parse_card_table` finds them by header name, so another issuer's export with the same headers needs no new code; a table without them is reported, not guessed. The three issuers can all export either format — **send Excel**.
- **Rolling credit ("שירות אשראי מתגלגל"):** a debt carried between bills. On the owner's Cal statement the header total (₪4,253.59) equals the other rows exactly, and the bank was debited ₪3,772.31 = the sum of ALL charge cells (the rolling-credit lines net −₪481.28). So `Section.total` is checked against the rows without them and the bank match uses `Section.payment`. These lines are `credit_service`: neither spending nor income, never imported; the apparent interest (₪1,640.29 charged on ₪1,617.84) is shown, not booked.
- **Loans on the card:** instalments of card loans ("הלוואת אקספרס", "הלוואה מחוץ למסגרת", 72 instalments) are `loans` at the instalment — on this statement ₪3,242.92 a month, on top of the Max card's ₪3,273.26.
- Verification: `test_fcc_card_import.py` (23). Production: NOT verified.

### Cashflow Rules table (01/11/2026, owner-approved) — 5b step 1

- **Where the owner's classification lives:** table `Cashflow Rules` (`tbl98SEP03oiaQ6uY`, owner-scoped like the other FCC tables). One row = "this description (or ONE imported row, via `Row Key`) means this kind and category". The system will add every description it cannot classify as a `pending` row with no Kind; the owner fills Kind + Category in Airtable and the rule applies to every future statement.
- **Only decided rows count:** a row with an empty Kind, `Status = pending|disabled`, or neither Match nor Row Key is ignored. `income` is the owner's EXPLICIT approval of a credit as income (with the source name as Category); `transfer` means "between my own accounts". Applies To (`bank` / `card` / `any`) and Direction narrow a rule.
- **Seeded rows:** only what the owner decided in the chat (12 rows, see the changelog); nothing was inferred. The scholarship and the kids' trips stay `pending`.
- **Not wired yet:** no app write path touches this table (not in the TMA write allow-list). Next: the import preview (statement -> classified rows, unknown descriptions added as pending rows) and ONE bulk review -> אשר into `Financial Progress Events`. Verification: `test_fcc_cashflow_rules.py`. Production: NOT verified.

### Import plan (01/11/2026) — 5b step 2

- **Plan before write:** `import_plan` turns classified bank / card rows into data: the events that WOULD be written, what is skipped (with the reason and the amount) and what the owner is asked. Nothing executes here.
- **Decided rows only; never the same money twice:** a bank settlement, cash withdrawal, rolling-credit line, benefit line, transfer, returned charge and a row marked for review are never written. A second import of the same statement writes nothing (idempotency keys). A card line is written only with a category.
- **No goal on an imported row** (it is not goal progress and must not inflate an income goal): `Source = import:bank|import:card`, `Verification = statement`; income carries `מקור: <name>`. The read side (cashflow, monthly household card) understands such rows; the "recent progress" list ignores them. A refund is a negative expense.
- **The owner classifies in Airtable:** every undecided description becomes ONE pending row in `Cashflow Rules` (a pending ROW rule per transfer); a description already in the table (any status) is never added again.
- **Owner decisions applied in the table (01/11/2026):** the 530 monthly credit from יגדיל תורה is approved income "מלגת לימוד — יגדיל תורה"; the kids' trips merchant is `leisure`.
- **Next:** the upload + preview endpoint and the BATCHED execution through the ActionGateway (a write per event through the single-write path would exceed one request): one review -> אשר, chunks of N events per approval, idempotent and resumable. Verification: `test_fcc_import_plan.py`. Production: NOT verified.

### Statement import — upload, one review, chunked write (01/11/2026) — 5b step 3

- **Flow:** the owner picks bank / card, optionally an account label (keep it constant between imports: it is part of every row's idempotency key), and a file. **Preview** reads, classifies (the owner's `Cashflow Rules` first, then the high-precision built-ins) and shows the plan: per month the expenses / income that would be written, what is skipped and why, and which descriptions will be added to the rules table as `pending`. Nothing is written. **Confirm once** and the client calls **run** repeatedly; each call writes the next chunk (20 rows) and finally the pending rule rows.
- **One approval, still the gateway:** the digest of the reviewed plan (user, kind, label, the keys of every event the plan contains) is the authorization for the whole run. Each chunk is ONE ActionGateway contract (`tma_write op=post_many`, owner auto-approved like every other TMA owner write: projection row, claim, audit, receipt). A different file or a changed rule set changes the digest and the run stops (409).
- **The client never sends a record.** The server rebuilds the writes from the uploaded file on every call; the executor re-validates every record (allow-list of fields and values, no goal / account link, `Source = import:*`, `Verification = statement`), applies the owner policy to every record before the first write, skips keys the owner already has, and stops a chunk at the first failed create (the retry skips what was written).
- **Reading without binaries:** `statement_reader` (pdfminer + openpyxl, both pure Python) — the bank PDF needs no `pdftotext`. A bank Excel export is refused until a sample exists.
- **Imported rows never touch goals:** no goal link, `Source = import:*`; `my_events` excludes them by default (the 500-row read cap can no longer cut goal progress), the cashflow and the monthly household card read them with a wide, date-limited query; the "recent progress" list ignores them. Long numbers (8+ digits) are masked in anything copied from a statement.
- **Not done:** verification on a device and in production (needs a deploy: `pdfminer.six` in requirements.txt); a bank Excel export; the card-to-bank match is a report-script feature, not part of the import (card settlements are simply never written). Verification: `test_fcc_import_api.py` (26), `fccImport.test.ts`. Production: NOT verified.


### One-by-one classification of imported expenses + fee categories (01/11/2026) — owner request after the first on-device look

- **Finding:** at that point Airtable held no imported row and no pending rule: the import had not been written (previewed, or the write did not complete), so the cashflow showed only the manual entries.
- **Categories:** `card_fees` "דמי כרטיס" and `fees_interest` "עמלות וריביות" are built-in (the owner's: fees that can be negotiated or removed). The bank rules "דמי כרטיס" and "עמלה / עמלת / עמלות / ריבית" and the card's own fee lines map to them.
- **Decision applied:** an UNKNOWN bank debit and an itemized card purchase that no rule decides are now written WITHOUT a category and shown as "לא מסווג" (previously they were skipped, which left the screen empty). Income, refunds, credits and transfers are still never written without the owner's decision. The import review states how many rows are written uncategorized.
- **Classification screen:** `GET|POST /api/fcc/classify` (owner only, 404 otherwise). GET = the next uncategorized imported expense (largest first, `?skip=` for this visit). POST = ONE patch of ONE field (`Expense Category`) of a record the server re-read as the caller's own, imported, uncategorized expense, through the normal ActionGateway ceremony (`tma_fcc_write`); optionally the same category for up to 10 other waiting rows with the same description per call. The client names a record and a category; table and field are the server's. The screen: category buttons / a new category / skip -> a review line -> "אשר סיווג".
- **Not done:** verification on a device and in production; classification does not create a rule for future imports (a follow-up); the Max / Isracard / Cal statements still decide only what the card itemizes.

### Classification screen: manual entries and the legacy fee label (01/11/2026) — owner screenshot after the first real import

- **Finding:** the first import (120 rows, checked in Airtable) had every expense categorized — the rows no rule decides were skipped by the code that ran at that time — so the "הוצאות לסיווג" section, which counted only imported rows, correctly showed nothing, while the cashflow's "לא מסווג ₪420" was a manually recorded household expense. The first import also wrote the card's fee lines and bank charges under the custom label "עמלות וריבית" (shown with ✦).
- **Change:** the screen's queue now includes manually recorded uncategorized household expenses (labelled "רישום ידני", never grouped); the legacy singular label maps to the built-in `fees_interest`. Re-importing the same statements after the deploy of the previous change writes only the rows that were skipped, uncategorized, and the screen then lists them.
- **Not done:** verification on a device and in production.

### Classifying descriptions from the rules table (01/11/2026) — owner request

- **Why:** the first import left ~120 pending rows in `Cashflow Rules` (a description, an example amount, a count). A pending row has no per-row date or amount, so it cannot be turned into events; but classifying the DESCRIPTION once decides every row with it, now and in every later import — the owner no longer has to classify the same merchant per event or per month.
- **Flow:** `GET /api/fcc/classify-rules` (the caller's pending expense descriptions, most seen first) -> the owner picks a category (built-in, own, or new) -> a review line -> "אשר סיווג" -> `POST /api/fcc/classify-rules` patches ONE rule (Kind expense, Category, Status active) through the ActionGateway ceremony. The next import writes the rows already classified.
- **Guard:** `tma_write` may patch `Cashflow Rules` only with exactly Kind / Category / Status (`validate_rule_patch`, checked at proposal and at execution, owner only). Credits (income needs the owner's explicit approval) and row-key rules (transfers checked one by one) are never offered.
- **Not done:** verification on a device and in production; previously imported events that were written uncategorized keep their category until classified on the events screen.

### Classifying an imported expense leaves a rule behind (01/11/2026) — owner report

- **Report:** "יש חסד" was classified for all five rows of one statement; the next statement asked again. **Cause:** the event screen patched only the written events (the limitation noted when it was built); nothing told the importer about the description.
- **Change:** after the events are patched, `POST /api/fcc/classify` patches the existing rule row for that description (pending, or decided with another category) or creates one decided expense rule; the same category as the existing rule writes nothing. The next import classifies every row with that description by itself. A manual entry has no description and leaves no rule.
- **Guard:** the rules table is writable through `tma_write` only with the one-rule classification patch or that exact new-rule shape (owner only; checked at proposal and at execution).
- **Not done:** verification on a device and in production; rows already classified before this change have no rule until they are classified again (or until their description is classified on the descriptions screen).

### Two tabs, two dates: cashflow by billing, consumption by purchase (02/11/2026) — owner decision "א', כן, בנה את לשונית הצריכה"

- **Decision (owner):** the "תזרים" tab tracks charges and balances per month (when the money leaves — a month with a hole); the new "צריכה" tab tracks when the money was actually consumed (real savings advice and real over-spending, not a billing-date illusion). Loans are consumption of no month: the consumption tab never counts them (cashflow only). An instalment purchase is counted on each payment's billing month and labelled "תשלומים" (option א').
- **Data:** new date field `Financial Progress Events.Billing Date` (`fldzXOVaX0KMhRdB1`, created 02/11/2026 with the owner's approval). `Occurred At` is unchanged: the purchase day for a regular card row, the billing date for an instalment / loan / card fee (as before), the movement date for a bank row. A card row without a `Billing Date` (imported earlier) is counted by `Occurred At` in the cashflow tab until its statement is imported again.
- **Backfill:** importing the SAME card statement again now fills `Billing Date` (and the "תשלומים" Note) on the rows imported earlier — only when the field is empty, never overwriting (`_tma_write_many`; the review says "N רישומים שכבר יובאו יקבלו תאריך חיוב"; a new import step "billing"). The batch allow-list accepts `Billing Date` for card rows and the Note `תשלומים` for card expenses only.
- **Read:** `service.cashflow_inputs(..., basis="billing"|"occurred")`; `cashflow_view` uses "billing", `consumption_view` uses "occurred", drops the loans category, sums the instalments per month. `GET /api/fcc/consumption` (owner only, 404 otherwise) returns months with expenses by category, installments, and changes / spikes / large items. It carries no income, balance, shortfall or recommendations (those use the gap and the commitments — they stay in the cashflow tab).
- **Not done:** verification on a device and in production; recommendations by purchase date (they stay on the cashflow side, which counts by billing); the last month is partial until the next card statement is imported.

### Importing several statements at once (02/11/2026) — owner "כן, בנה ייבוא מרובה"

- **Why it was single-file:** the import card's file input took one file; the server already processes ONE statement per request (it rebuilds every record from the uploaded file at each chunk, by design — the client never sends records) and allows one import at a time.
- **Change (frontend only):** `<input multiple>`; each file gets its own preview (sequential), status and detail; a file that does not parse or add up is marked and skipped, the others go on; ONE confirm covers the batch and the files are written one after the other (the same chunked `run` per file, with the digest of its own preview); a blocked file can be retried alone. Files are kept in the browser for the session; nothing is stored on a server / Drive / Airtable (they carry account and card numbers).
- **Not done:** automatic bank-vs-card detection (the owner picks the type once per batch); verification on a device and in production.

### Loans are not imported (02/11/2026) — owner decision

- **Why:** loan rows from the statements produced errors, and the loans tab already holds the exact balances and monthly payments; the system is not yet accurate enough to warn about inaccuracies it cannot check.
- **Change:** a row classified as a loan (bank rules "הלוואה / משכנתא", card loan lines, a purchase the owner classified as `loans`) is recognised but not written (`import_plan` skip reason `loan`). The cashflow ignores imported loan rows already stored (not deleted), so the loan figure comes only from the loans tab's scheduled monthly payment (current month, an estimate). Consumption never counted loans.
- **Consequence stated to the owner:** previous months show no loan repayments in the cashflow. Applying today's scheduled payment to earlier months would be a guess and was not done.
- **Not done:** deleting the loan rows already imported; verification on a device and in production.

### The loans tab's schedule in every month (02/11/2026) — owner decision

- **Decision:** a loan is a cost from the month it started until it ends (or is closed early), per the loans tab — not guessed from statements and not only in the current month.
- **Change:** `loans.monthly_schedule` (pure) gives each month's total from `Start Date` / `End Date` (else start + term; active with neither -> to today) × the current monthly payment; the cashflow and the monthly tab's month summary use it (`cashflow.build(..., loans_by_month=...)`). Closing a loan writes its closing day as `End Date`. Undated loans are counted in the current month only and named; closed loans without an end date are not counted and named; debts owed TO the owner are not costs.
- **Limit (stated to the owner):** the payment used for past months is today's `Current Monthly Payment`; a payment that changed over time is not reconstructed. Loans without start dates are shown in a note until the owner fills them.
- **Not done:** verification on a device and in production; backfilling End Date for loans closed before this change.

### Loans: interest vs principal, exact amortization schedules, prime re-projection (08/11/2026) — owner decision

- **Decision:** the loans tab shows how much of each month's payment is interest and how much principal (total and per loan), from the lender's own schedule when there is one; a schedule is stored per loan, and a prime change projects it again.
- **Change:** `loans.payment_split` (estimate: balance × rate ÷ 12) is replaced by the lender's figures when `Loans."Amortization Schedule"` (long text JSON, live fld52A7z7dN8O7U1N, created 08/11/2026) holds a schedule. `amortization.parse_file` reads the Max Excel and the Cal PDF letter and trusts a schedule only if it adds up. `POST /api/fcc/loans/schedule` (owner only, 404 otherwise) previews without writing and, on confirm, patches ONE loan through the approval ceremony. A missing `End Date` is derived from `Payments Remaining` (shown ≈). A confirmed prime change recomputes the not-yet-charged rows in the same patch as the new rate and payment (`amortization.reproject`; charged months stay).
- **Limit (stated to the owner):** future rows assume the prime of the schedule's issue date (`asof`); without a prime change recorded in the system a new schedule must be uploaded. Loans without a schedule keep the estimate and are labelled "הערכה".
- **Not done:** verification on a device and in production; schedules for the loans the owner has not yet uploaded.

### Loan schedule sent twice (08/11/2026) — owner report

- **What happened:** the Max ₪30,000 file was uploaded twice; the first write saved it, the second identical proposal was refused as a duplicate and the card showed "הכתיבה לא הושלמה". Checked in Airtable: all seven schedules (Max 105k and 30k, five Cal letters) are stored.
- **Change:** the schedule preview marks a loan whose stored schedule is identical, and confirming an identical schedule reports "saved" (`already`) without a write.
- **Not done:** verification on a device and in production.

### Refinance simulator (08/11/2026) — owner decision

- **Decision:** the owner can test an offer for rolling loans into one mortgage: what to include, the payment relief, the interest, and when the costs pay back — not every loan is worth including.
- **Change:** `refinance.simulate` (pure) + `POST /api/fcc/loans/refinance` (owner only, read-only) + the loans tab's "סימולטור מחזור" card. Per-loan verdicts; unknown early-repayment fees and loans without balance / payment / payments left are never guessed; the same-term and offer-term comparisons are always shown together, and the worthwhile set must cover the offer's fixed costs (`recommended_pays`).
- **Limit (stated to the owner):** every figure assumes today's prime and rates stay; a single rate per offer (no track mix, no index-linking); the result is a comparison, not advice to sign.
- **Not done:** verification on a device and in production; multi-track offers and several offers side by side.

### Refinance: loans whose interest is mostly paid (08/11/2026) — owner decision

- **Decision:** a loan near its end (mostly principal left) is not worth rolling into a mortgage even at a lower rate.
- **Change:** each row of the refinance simulator shows the interest share of the payments still ahead and the full-term cost of leaving the principal in the mortgage; a loan is "worth" only if its net saving (same repayment pace, after the early-repayment fee) is at least 1% of its balance; a worthwhile loan that costs more over the mortgage's whole term is marked as worth it only if repaid at the current pace.
- **Not done:** verification on a device and in production; the 1% threshold is a stated heuristic, not a bank rule.

### Refinance by monthly relief; payoff engine on the real remaining interest (08/11/2026) — owner decision

- **Decision:** the refinance simulator must not only say worth / not worth by interest — a loan can be worth it for the monthly relief, with its price shown; and the early-payoff engine must use the real remaining interest, not payment × months − balance.
- **Change:** each refinance row carries the monthly relief and its price per ₪100; the answer lists the relief set (cheapest first) with totals next to the interest-worthy set. For loans with a stored schedule `loan_item` takes the remaining payments and interest from the schedule and the payoff engine's cost / saving use it (`interest_from_schedule`).
- **Limit:** loans without a schedule still use the estimate (labelled "משוער"); the monthly relief assumes the loan alone at the offer's term.
- **Not done:** verification on a device and in production.

### The practical remaining interest on every loan (08/11/2026) — owner decision

- **Decision:** every loan shows the interest still to be paid until it ends, besides the monthly interest and the other figures.
- **Change:** `loan_item` carries `interest_remaining` (+ `interest_remaining_exact`): the lender's schedule when stored, else payment × payments left − balance; the loan card shows it as "ריבית שנותרה עד הסיום" (exact / "≈ הערכה" / unknown).
- **Not done:** verification on a device and in production; a total across all loans in the header.

### The refinance simulator in plain language (08/11/2026) — owner decision

- **Decision:** the simulator must speak plainly: the practical interest in shekels until the end of each loan (not a share of the payments), the relief price as two shekel figures (not "₪X per ₪100"), and everything explained in everyday words. The owner chose the layout from options.
- **Change:** per-loan before / after tables for two scenarios ("אם תמשיך לשלם כמו היום" / "אם תפרוס לכל התקופה"), a one-sentence reason per verdict, a plain-language "איך חישבתי?" section; the numbers are unchanged.
- **Not done:** verification on a device and in production.

### Refinance comparison — phase 1 accuracy (08/11/2026) — owner decision

- **Decision (clarifications of 08/11/2026):** use the lender's real schedule when it exists, otherwise a clearly labelled estimate; for several loans sum each loan's cash flows by its own payment dates; compare every alternative on one time axis; show the saving, the monthly relief and the future debt separately; count one-time costs once.
- **Change:** `refinance.simulate` builds, per loan, its payments ahead (stored schedule or estimate) and the alternatives from scratch with one formula (`amortization.annuity_rows`), sums them month by month on a shared axis, and reports the nominal saving, the monthly relief and the debt left after N years. The old "same pace" group figure (one annuity over the longest loan) is gone. `loan_item` adds `payoff_now_total` and `first_payment_date`; stored schedules are read by date.
- **Stated limits:** estimated schedules are not the bank's; rates are assumed constant; a single rate per offer.
- **Not done:** verification on a device and in production; phase 2 (alternatives engine: prepay, invest, scenarios) is design only and not built.

### Refinance simulator on a phone (08/11/2026) — owner decision

- **Decision:** a focused display fix only: wide tables scroll inside their own box instead of widening the page, and a payment-by-payment cell has two lines. The calculation engines and the loans data are unchanged; the 150 ₪ materiality threshold was NOT approved (small or negligible savings are reported separately, without a new rule).
- **Change:** `.fcc-table-scroll` / `.fcc-refi` in `index.css` and the wrappers in `FccRefinance.tsx`; `monthRows` returns a payment line and an interest / principal line.
- **Verification:** mobile Chromium emulation at 390 / 360 / 320 / 280px (page width unchanged, tables scroll inside); not on a real phone or in Telegram.

### Interest vs principal without mortgages + partial prepayment in the budget simulator (10/11/2026) — owner decision

- **Decision:** (1) the "ריבית מול קרן החודש" card also shows the same split over the non-mortgage loans only; (2) the budget simulator drops the assumption "whole-loan payoffs only": the budget left after the whole-loan closures is applied as one partial prepayment of the next loan in the strategy order.
- **Change:** `loans.summarize` adds `split_no_mortgage` (sums of the existing per-loan split); `payoff.partial_prepay` / `_leftover_partial` add `partial_prepay` to every scenario and combination result, as an estimate in two ways (same instalment: ends sooner; same term: lower instalment). `used` / `remaining_budget` and the whole-loan figures are unchanged. Display in `FccPayoff.tsx` / `fccPayoff.ts`, `fccLoans.ts`.
- **Stated limits:** fixed rate, level instalments from the loan's balance / rate / months left; no partial-prepayment fee; the lender's schedule is not re-cut. The refinance simulator is not changed (comparing refinance vs prepayment is phase 2, not built).
- **Not done:** verification on a device and in production.

### Loans timeline — when the payment drops and the interest share falls (10/11/2026) — owner decision

- **Decision:** a read-only timeline over the owner's active loans, without and with mortgages: the months in which the monthly payment drops, the months in which the interest falls below 30 / 25 / 20 / 15 / 10 / 5% of the payment, a year-by-year table and the remaining interest split into schedule-based and estimated.
- **Change:** `core/financial_control/loan_timeline.py` (pure) sums each loan's payments ahead from the stored lender schedule or the existing labelled estimate (`refinance._remaining`) — no new formula; `service.loans_overview` adds `timeline`; `LoanTimeline` card + `fccLoanTimeline.ts` in the loans tab.
- **Stated limits:** assumes today's rates (a prime change re-cuts schedules); loans without a schedule are estimates and shown apart; a loan without balance / payment / payments left is not priced and is counted ("N of M").
- **Not done:** verification on a device and in production.
