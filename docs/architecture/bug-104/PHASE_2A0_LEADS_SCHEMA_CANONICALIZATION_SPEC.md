# BUG-104 Phase 2A.0 — Leads Schema Cleanup & Current State Canonicalization

**סוג מסמך:** Audit + SPEC בלבד. **אין קוד. אין mutation לסכמת Airtable. אין מחיקת/שינוי שם שדה. אין שינוי frontend.**

**תאריך:** 2026-07-17 · **Branch:** `claude/bug-104-phase2a0-leads-schema-canonicalization` · **main בזמן הכתיבה:** `f48741e`

**שיטה:** שדות ה-Leads שנבדקו נמשכו חיים מ-Airtable (base `app4bcgoX7t0HUVnm`, table `Leads` / `tblersBI4EZoOBTdU`) דרך Airtable MCP (`get_table_schema` + `list_records_for_table`) ב-17/07/2026, ולא מתוך תיעוד/הנחות קוד. מפת קריאה/כתיבה בקוד הופקה בגריפ ממוקד לפי file:line על כל הריפו (לא רק הקבצים שצוינו), ואומתה ידנית נקודתית (ציטוטים ב-§5/§6 להלן) לפני הכללתה כאן.

---

## 1. Problem Statement

טבלת `Leads` צברה **39 שדות חיים**, מתוכם 16 קשורים ישירות למצב/ציון/עדיפות של ליד — אך הם נכתבו/נוצרו בכמה גלים לא-מתואמים: שדה `status` ידני, שדה `Score` ידני, שדה `tier` ידני-לכאורה (אך ריק לגמרי בפועל), שרשרת שדות **formula** שמחושבים אוטומטית מתוך `Score` (טמפרטורה/אימוג'י/מד ציון/עדיפות/תצוגת ליד/Suggested Followup), ושרשרת שדות **Domain\* חדשה** (`Domain category`/`Domain risk assessment`/`Domain summary`) שמתבררת כשימוש שגוי-מיסודו של Airtable AI Field על השדה `domain` (ראה §7).

בקוד יש **חמישה** מימושים עצמאיים לא-מתואמים של "tier/temperature מ-Score" (§7), **שני** אתרי כתיבה בלתי-תלויים שכותבים ערך `status` לא-קנוני (`"converted"`, שאינו ב-`LeadStatus.ALL`), ומנוע ה-Reasoning (BUG-104 Phase 1) קורא דרך שרשרת נורמליזציה כפולה (`FIELD_ALIASES` + `_LIVE_TO_ADAPTER_FIELDS` + נפילות `or` פנימיות ב-`LeadsAdapter`) כדי לגשר בין שמות שדה live לבין שמות legacy שה-Adapter מצפה להם.

המטרה של Phase 2A.0: **לתעד את המצב הקיים במדויק ולהחליט מהו מודל קנוני מוצע** — בלי לגעת בקוד או בסכמה — כך ש-Phase 2A (יישום) יהיה שינוי ממוקד על בסיס החלטה מתועדת, לא ניחוש נוסף.

---

## 2. Current Live Leads Schema Inventory

טבלה `Leads` (`tblersBI4EZoOBTdU`), 39 שדות סה"כ. 16 השדות המבוקשים (שמות/סוגים כפי שאומתו ב-MCP `get_table_schema`, 17/07/2026):

| # | Field name (Airtable) | Field ID | Type |
|---|---|---|---|
| 1 | `status` | `fldvTgONHx7D8JFw0` | singleSelect |
| 2 | `Business Outcome` | `fldVa5wSmAqcKLi86` | singleSelect |
| 3 | `Next Action` | `fldWt6lcf7uf8X6uj` | singleSelect |
| 4 | `Next Followup` | `fldrswrSwXCflaL9Y` | date |
| 5 | `Score` | `fld9T7Gg2JCgFi2Ah` | number (precision 0) |
| 6 | `tier` | `fld4eC2mEYrviL3oP` | singleSelect |
| 7 | `טמפרטורה` | `fldcSLwbtkvpy0LA8` | formula → text |
| 8 | `אימוג'י טמפרטורה` | `fldHpAQKuU6Z5svHp` | formula → text |
| 9 | `מד ציון` | `fldbeBENvalUrBadW` | formula → text |
| 10 | `עדיפות` | `fldX3IyspDobq8Z91` | formula → text |
| 11 | `תצוגת ליד` | `fld1ffrHxnPFFB9J6` | formula → text |
| 12 | `Suggested Followup` | `fldaE6FSxUN34Gqjz` | formula → text |
| 13 | `Domain category` | `fldEi5SckYAE8hfvq` | singleSelect |
| 14 | `Domain risk assessment` | `fld9zeXgqEYWefrsu` | singleSelect |
| 15 | `Domain summary` | `fldQfCD1k9s0sE2X5` | **aiText** (Airtable-native AI field) |
| 16 | `domain` | `fldcGcUgM2R2E5xzU` | singleLineText |

**Formulas (verbatim, all keyed off `Score` alone — `fld9T7Gg2JCgFi2Ah`):**

- `טמפרטורה`: `Score<=20→"❄️ קר / Cold"`, `<=40→"🧊 פושר / Cool"`, `<=60→"🌤️ חם / Warm"`, `<=80→"🔥 לוהט / Hot"`, `else→"🚀 רותח / Ultra Hot"`.
- `אימוג'י טמפרטורה`: אותם ספים, אימוג'י בלבד (❄️/🧊/🌤️/🔥/🚀).
- `מד ציון`: אותם ספים, פס בלוקים (`██░░░░░░░░` … `██████████`).
- `עדיפות`: `Score>=81→"מיידי / Immediate"`, `>=61→"היום / Today"`, `>=41→"השבוע / This Week"`, `>=21→"מעקב / Follow Up"`, `else→"נמוכה / Low"`.
- `תצוגת ליד`: שרשור `אימוג'י טמפרטורה & " " & טמפרטורה & " — " & Score & "/100\n" & מד ציון`.
- `Suggested Followup`: `Score>=81→"📞 התקשר עכשיו"`, `>=61→"☎️ התקשר היום"`, `>=41→"📅 קבע מעקב השבוע"`, `>=21→"📩 שלח הודעה"`, `else→"📝 השאר במעקב"`.
- `Domain summary` (aiText): `referencedFieldIds: ["domain"]` — Airtable-native AI מייצר תקציר טקסט **מהמחרוזת הגולמית שבשדה `domain`** (ראה §7 — זו לא ה"דומיין העסקי" שהקוד מכיר).

**Live singleSelect options (choice names בדיוק כפי שקיימים ב-Airtable, לא הנחות קוד):**

- `status`: `waiting_call, active, high_confidence, new, waiting_response, archived, lost, duplicate, not_relevant, done, ליד חדש`
- `Business Outcome`: `"open ", "needs_followup ", "meeting_scheduled ", "converted ", "not_relevant ", "lost ", "duplicate ", "archived", "ליד חדש"` — **שימו לב לרווח הזנב** בכל אופציה חוץ מ-`archived` ו-`ליד חדש`.
- `Next Action`: `Call Back, Send Details, Follow Up, Waiting Response, Create Deal, Convert Contact, "Schedule Meeting ", Closed Won, Closed Lost, ליד חדש`
- `tier`: `קר, חם, רותח, לוהט, ליד חדש`
- `Domain category`: `Technology, Finance, Healthcare, Retail, Education, Manufacturing, Real Estate, Consulting, Other`
- `Domain risk assessment`: `Low risk, Medium risk, High risk`

---

## 3. Current Live Values Inventory (92 records, 17/07/2026)

נבדק על כל 92 הרשומות החיות בטבלה (`totalRecordCount: 92`), עם דגימת שדות ממוקדת ובדיקת `isNotEmpty` מדויקת לשדות הבעייתיים:

| Field | Populated? | Distribution |
|---|---|---|
| `status` | רוב הרשומות | `new` הכי נפוץ; נצפו גם `active, waiting_response, archived, lost, duplicate, not_relevant, waiting_call, high_confidence`. **`ליד חדש` (האופציה ה-11) לא נצפה בדגימה אך קיים כ-choice חי.** |
| `Score` | רוב הרשומות (חלק ריק/0) | ערכים שנצפו: `0, 8, 20, 25, 35, 50, 60, 68, 78, 80, 90, 98` |
| `Business Outcome` | מיעוט (~20/92) | `"meeting_scheduled ", "needs_followup ", "not_relevant ", "archived", "duplicate ", "lost "` — כולם עם/בלי הרווח בדיוק כפי שמוגדר בסכמה |
| `domain` | רוב הרשומות | `general, recruitment, real_estate, media, saas, import, crm` — תואם 1:1 ל-allowlist הפנימי ב-`core/lead_event_writer.py` (§7) |
| `tier` | **0/92 — ריק לחלוטין** | מאומת ישירות: `filters: isNotEmpty("tier")` → `totalRecordCount: 0` |
| `Next Action` | **0/92 — ריק לחלוטין** | מאומת ישירות: `filters: isNotEmpty("Next Action")` → `totalRecordCount: 0` |
| `Next Followup` | **1/92** | הרשומה היחידה: `rec3ZMxHh9ewQRktl`, `2026-06-15` |
| `Domain category` | 10/92, כולן `"Other"` | אך ורק קבוצת רשומות שנוצרו 10–14/07/2026 (domain=`general`), נראה כמו נתוני seed/בדיקה, לא שימוש אורגני |
| `Domain risk assessment` | 10/92 (אותה קבוצה) | `Low risk` (רוב) / `Medium risk` (מיעוט) |
| `Domain summary` | 10/92 (אותה קבוצה) | טקסט AI-generated שמפרש את המחרוזת `"general"` **כאילו היא שם דומיין אינטרנטי** (לדוגמה: *"A general-purpose term... generic brand, catch-all website..."*) — לא קשור לדומיין העסקי (`real_estate`/`saas`/וכו') |

**מסקנת ביניים:** `tier` ו-`Next Action` הם **שדות מתים בפועל בנתונים**, לא רק "לא נכתבים בקוד" — 0 מתוך 92. `Next Followup` כמעט מת (1/92). שלושת שדות ה-`Domain*` פעילים רק על אצווה קטנה אחת של רשומות בדיקה/seed, ומייצרים תוכן שגוי סמנטית (ראה §7).

---

## 4. Field-by-Field Canonical Decision

| # | Field | Type | Live values/formula | User-editable? | Canonical source? | Display-only? | Legacy? | Safe to ignore in reasoning? | Proposed action | Risk if changed now |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `status` | singleSelect | ראה §2/§3 | כן (TMA `patch_lead`/`update_lead_status`, יצירה) | **כן** | לא | לא | **לא** — כבר בשימוש (Attention/Orchestrator status mapping) | **keep** | נמוך — נבדק ומאומת (Phase 1.1) |
| 2 | `Business Outcome` | singleSelect | ראה §2/§3 | כן (TMA בלבד) | **כן** (החלטה עסקית טרמינלית, נפרדת מ-status התפעולי) | לא | לא | לא | **keep** | נמוך — נכתב רק מ-TMA, מוגן ע"י `LeadOutcome.BY_KEY` validation |
| 3 | `Next Action` | singleSelect | 0/92, ללא כותב קוד בכלל | "כן" לפי `_LEAD_EDITABLE` אך אין כותב אמיתי | **כן** (מוצע — "next planned action") | לא | **כן, הלכה למעשה** (מוגדר ב-schema, לא בשימוש) | לא רלוונטי — ריק | **stop writing / keep field, no active writer to build yet** | נמוך — לא נוגעים |
| 4 | `Next Followup` | date | 1/92 | כן (TMA, pass-through בלבד) | **כן** (מוצע — "next scheduled followup date") | לא | כן להלכה, כמעט-מת בפועל | לא רלוונטי — כמעט ריק | **keep field / migrate later** (אין backend שכותב חישוב אמיתי) | נמוך |
| 5 | `Score` | number | 0–100 | כן (מספר מקומות בקוד, ראה §5) | **כן** | לא | לא | **לא** — נצרך ע"י ה-Reasoning projection כ-passthrough מוצהר | **keep** | נמוך — שדה יציב, מקור אמת מוצהר כבר ב-BUG-104 Phase 1 |
| 6 | `tier` | singleSelect | **0/92, ריק לחלוטין** | טכנית כן, בפועל אף כותב לא כותב אליו בכוונה | **לא** | **לא** (זה singleSelect ריק, לא display) | **כן — legacy/dead** | **כן** | **stop writing (already true) / delete later** — אחרי אישור owner | **בינוני** — 3 מקורות תיעוד סותרים זה את זה לגבי הסטטוס שלו (ראה §7); צריך להחליט על טקסט אחיד לפני מחיקה |
| 7 | `טמפרטורה` | formula | תלוי Score | **לא** (formula) | לא (נגזר) | **כן** | לא | כן | **display-only, keep** | אין — Airtable חוסם כתיבה מאליו; gateway חוסם גם הוא |
| 8 | `אימוג'י טמפרטורה` | formula | תלוי Score | לא | לא | **כן** | לא | כן | **display-only, keep** | אין |
| 9 | `מד ציון` | formula | תלוי Score | לא | לא | **כן** | לא | כן | **display-only, keep** | אין |
| 10 | `עדיפות` | formula | תלוי Score | לא | לא | **כן** | לא | כן | **display-only, keep** | אין |
| 11 | `תצוגת ליד` | formula | שרשור 4 formula-ים | לא | לא | **כן** | לא | כן | **display-only, keep** | אין |
| 12 | `Suggested Followup` | formula | תלוי Score | לא | לא | **כן** | לא | כן | **display-only, keep** | אין |
| 13 | `Domain category` | singleSelect | 10/92, ריק ברובם | כן טכנית | **לא** | מוצג כ"display" אך תוכנו לא אמין (ראה §7) | **כן — misapplied AI feature** | **כן** | **stop using in reasoning; consider delete later** | נמוך — לא בשימוש קוד היום |
| 14 | `Domain risk assessment` | singleSelect | 10/92, ריק ברובם | כן טכנית | **לא** | כנ"ל | **כן — misapplied AI feature** | **כן** | **stop using in reasoning; consider delete later** | נמוך |
| 15 | `Domain summary` | aiText | 10/92, ריק ברובם | לא (AI-generated) | **לא** | טכנית "תצוגה" אך מטעה סמנטית | **כן — misapplied AI feature (מפרש `domain` כשם-דומיין-אינטרנט, לא כדומיין עסקי)** | **כן** | **stop using in reasoning; consider delete later (או לשקול לחבר ל-referencedField נכון אם רוצים לשמר את היכולת)** | נמוך — לא בשימוש קוד היום |
| 16 | `domain` | singleLineText | `real_estate/saas/import/recruitment/general/media/crm` | כן (רק ביצירה — לא חשוף ל-PATCH TMA) | **כן** | לא | לא | **לא** — מקור אמת לדומיין עסקי, גם ל-Lead Event bridge | **keep** | נמוך — מאומת שה-allowlist בקוד (`core/lead_event_writer.py`) תואם 1:1 לערכים החיים |

---

## 5. Current Write Paths

**`status`:**
- יצירה תמיד `"new"`: `lead_capture.py:257`, `core/lead_candidate_handler.py:431,484,619`, `inbound_handler.py:123`, `furniture_lead_funnel.py:159-164`, `voice_adapter.py:243`.
- `tma_api.py` — **owner-immediate**: `patch_lead` (`tma_api.py:1704`, `_at_patch("Leads", lead_id, fields)`) ו-`set_lead_outcome` (`tma_api.py:1752`). **Approval-queued**: `update_lead_status` (`tma_api.py:1587-1614`, כל קריאה — אין נתיב owner-immediate לנקודת קצה זו כלל) וגם `patch_lead`/`set_lead_outcome` עבור Manager (`tma_api.py:1712-1724`, `1760-1772`), מבוצע בפועל דרך `tools/approval_actions.py::tma_write`.
- `patch_lead` מאמת `status` מול `LeadStatus.ALL` **לפני** כתיבה (`tma_api.py:1691-1693`) — דוחה ערך לא-חוקי עם 400.
- **שני אתרי כתיבה עוקפים את הוולידציה הזו לגמרי**, שניהם כותבים את המחרוזת `"converted"` שאינה קיימת ב-`LeadStatus.ALL` (הערך הקנוני ל"הומר" הוא `LeadStatus.DONE="done"`):
  - `lead_conversion.py:93-96` — דרך `_at_patch(Tables.LEADS, ...)` ישירות (עוקף את בדיקת ה-TMA endpoint, אך עדיין דרך ה-gateway).
  - `ad_attribution.py:195-199` (`mark_converted`) — דרך `tools.airtable_tools.airtable_update` **ישירות, לא דרך `tools/airtable_gateway.py`** — עוקף גם את ה-gateway (dedup/read-only-fields/audit log).

**`Business Outcome`:** נכתב **אך ורק** מ-`tma_api.py` — `patch_lead` (owner-immediate `:1704`, queued `:1712`) ו-`set_lead_outcome` (owner-immediate `:1752`, queued `:1760`). שני הנתיבים מוולדים מול `LeadOutcome.BY_KEY` לפני כתיבה (`tma_api.py:1694-1698`).

**`Next Action`:** **אין אתר כתיבה בכל הריפו.** מופיע ב-`_LEAD_EDITABLE`/`_LEAD_FIELD_ALIASES` של TMA (`tma_api.py:1618-1625`), כלומר ה-frontend *יכול* טכנית לשלוח אותו ב-PATCH, אך אין קוד שרת שיוזם כתיבה אליו בעצמו.

**`Next Followup`:** אין אתר כתיבה עצמאי — רק pass-through אם ה-frontend שולח `next_followup` ב-body של `patch_lead` (`tma_api.py:1620,1625`). אף מודול (`lead_qualifier.py`, `followup_engine.py`, `core/lead_recovery.py`) לא כותב אליו בפועל, למרות שכולם מחשבים תזמון מעקב בזיכרון בלבד.

**`Score`:** `lead_capture.py:259,291-293` (`_score_inbound_message`), `lead_memory.py:172`, `furniture_lead_funnel.py:165,172` (`_score_answers`), `core/lead_candidate_handler.py:433,486,549-551,621`.

**`tier`:** **אין אתר כתיבה בכוונה תחילה** — כל אתר חישוב tier (§7) נמנע במפורש מלכתוב אליו, עם שלוש נוסחאות תיעוד שונות וסותרות להסבר למה (ראה §7).

**שדות formula (`טמפרטורה`/`אימוג'י טמפרטורה`/`מד ציון`/`עדיפות`/`תצוגת ליד`/`Suggested Followup`):** כתיבה חסומה ע"י Airtable עצמו (422 אם ינסו), וגם חסומה יזומה ב-`tools/airtable_gateway.py:31-39` (`READ_ONLY_FIELDS["Leads"]`) וב-`tma_api.py:1628` (`_LEAD_IGNORED_PATCH_FIELDS = {"tier", "טמפרטורה"}` — striped מכל PATCH נכנס מה-TMA, גם אם רק חלקי כיסוי).

**`Domain category` / `Domain risk assessment` / `Domain summary`:** **אין אתר כתיבה בקוד כלל** — 0 references בכל הריפו (לא read, לא write, לא comment). הערכים שקיימים (10/92) הוזנו ידנית/דרך Airtable UI ישירות, לא דרך אף pipeline מנוהל.

**`domain`:** `lead_capture.py:255`, `core/lead_candidate_handler.py:419,429,469,482,599,617`, `inbound_handler.py:121`, `furniture_lead_funnel.py:172`, `voice_adapter.py:240`. **לא חשוף ל-PATCH מה-TMA** (`_LEAD_EDITABLE` לא כולל `domain`) — פעם שנוצר ליד, רק נתיבי היצירה יכולים לקבוע/לשנות דומיין.

---

## 6. Current Read Paths

- **`tma_api.py`** — `GET /api/leads/<id>` מחזיר `status` (`:1327/:1564`), `Business Outcome` (`:1573`), `tier` (`:1572`), `Next Action` (`:1569`), `Next Followup` (`:1574`), `Score` (`:1556`), `domain` (`:1563`). כל השדות האלה חוזרים כ-raw passthrough בתגובת ה-API — אין חישוב/נגזרת בצד השרת.
- **`core/leads_reasoning_projection.py`** (BUG-104 Phase 1, read-only, ה-live path היחיד היום שמזין reasoning אמיתי) — מבצע נורמליזציה משמות live לשמות legacy שה-`LeadsAdapter` מצפה להם (`_LIVE_TO_ADAPTER_FIELDS`, `core/leads_reasoning_projection.py:71-84`): `status→"Status"`, `tier→"Tier"`, `domain→"Domain"`, `Score→"Score"` (passthrough). קורא ל-`core/adapters/leads_adapter.py::LeadsAdapter.to_entity()` עם ה-record המנורמל.
- **`core/adapters/leads_adapter.py`** (`LeadsAdapter`) — קורא `fields.get("Status")`/`fields.get("Score") or fields.get("Lead Score")`/`fields.get("Tier") or fields.get("Lead Tier")`/`fields.get("Domain")` — שמות **capitalized** שאינם קיימים live בגרסתם המקורית (`status`/`domain` הם lowercase live); מגיעים נכונים רק כי `leads_reasoning_projection.py` כבר תרגם אותם קודם. `_normalise_status()` (שם, `:237-272`) ממפה ערכי `status` (כולל תרגומי-תיוג ישנים כמו `"hot"`/`"cold"`/עברית) ל-`DecisionStatus` (Phase 1.1 hardening) — mapping שלישי-בשרשרת לאותו מושג status.
- **`ad_attribution.py:324,371`**, **`audience_intelligence.py:171-177`** — כל אחד קורא `status`/`Score`/`domain`/`tier` בנפרד עם ברירות-מחדל/פולבאקים משלו (`f.get("Score") or f.get("score") or 0`, `f.get("Tier") or f.get("tier") or "COLD"`).
- **`daily_digest.py:75,83-85`** — שולף Leads עם formula `OR({Score}>=50, {status}='hot', {status}='Hot', {status}='HOT')`. **הענפים `status='hot'/'Hot'/'HOT'` מתים מבנית** — אין ב-`status` הלייב אף אופציה כזו (§2) — רק ענף ה-`Score>=50` יכול אי-פעם להתאים. שם, `f.get("next_step", "—")` קורא מפתח שגוי (`next_step` lowercase, לא `Next Action` הלייב) — גם זה תמיד נופל ל-`"—"`.
- **`lead_conversion.py:57`** — קורא `status` לפני כתיבה מותנית.
- **שדות `Domain category`/`Domain risk assessment`/`Domain summary`:** **0 קריאות בכל הריפו.**

---

## 7. Duplicate/Conflicting Fields

**A. חמישה מימושי tier/temperature עצמאיים, ללא תיאום:**

| # | מיקום | ספים | תוצאה |
|---|---|---|---|
| 1 | `lead_capture.py::tier_from_score` (`:90-102`) | ULTRA_HOT≥70 / HOT≥50 / WARM≥25 / COLD | תווית פנימית (session/log), לא נכתב ל-Airtable |
| 2 | `lead_capture.py::_score_inbound_message` (`:78-85`) | זהה ל-#1, אך מיושם שוב במקום אחר (כפילות קוד) | כנ"ל |
| 3 | `furniture_lead_funnel.py::_classify` (`:131-136`) | HOT≥60 / WARM≥30 / COLD | funnel נפרד לגמרי, ספים שונים מ-#1/#2 |
| 4 | `daily_digest.py::_tier_label` (`:55-67`) | 70/50/25 (כמו #1) אך תוויות עבריות שונות (`🔥 רותח`/`🌶️ לוהט`/`🌤️ חם`/`❄️ קר`) | מימוש שלישי, אותם ספים אך תוויות אחרות מ-#1 |
| 5 | `score_display.py::get_temperature` (`:12-26`) | 81/61/41/21/0 | **המימוש היחיד שהספים שלו תואמים בדיוק לספי ה-formula הלייב** (`טמפרטורה`/`עדיפות`), אך אינו מייבא/צורך מ-`airtable_schema.py` כלל, ותוויותיו (BOILING/VERY HOT/HOT/WARM/COLD) שונות מהתוויות ב-Airtable (Cold/Cool/Warm/Hot/Ultra Hot) |

**אף אחד מהחמישה לא נחשב "המקור" הרשמי** — אין import אחד מהשני, ואין הפניה ל-formula הלייב כרפרנס לספים. #5 מקרי-דומה בלבד (אין תיעוד שמישהו כיוון אליו בכוונה).

**B. שני אתרי כתיבת status לא-קנוניים (`"converted"`):** ראה §5 — `lead_conversion.py:94` ו-`ad_attribution.py:195`, שניהם כותבים ערך שאינו קיים ב-`LeadStatus.ALL` ועוקף לחלוטין את הבדיקה שקיימת ב-`tma_api.py::patch_lead`. הערך הקנוני התואם הוא `LeadStatus.DONE`.

**C. תיעוד סותר לגבי `tier`:** שלוש הצהרות מתנגשות בקוד/דוקס עצמם:
- `airtable_schema.py:311` — *"tier singleSelect — writable. Values: קר/חם/לוהט/רותח (set by scoring logic)"*.
- `daily_digest.py:58-59` / `ROADMAP.md:1172` — *"אין שדה tier ב-Airtable... מחושב בזיכרון מתוך Score בלבד"*.
- `.claude/skills/CLAUDE_SKILLS.md:216` — *"❌ אסור: LeadFields.TIER — formula, read-only"*.
- **המציאות (מאומתת ישירות ב-MCP):** `tier` הוא **singleSelect אמיתי וקיים**, לא formula — אבל **ריק ב-100% מהרשומות** (§3), ואף כותב בקוד לא כותב אליו. שלוש ההצהרות שגויות בדרכים שונות; רק ההתנהגות בפועל (לא-נכתב) נכונה.

**D. שלושת שדות ה-`Domain*` — misapplied Airtable AI feature:** `Domain summary` הוא שדה `aiText` שה-reference שלו הוא `domain` (הטקסט הגולמי — למשל `"general"`, `"real_estate"`). Airtable מפרש את זה **כאילו `domain` הוא שם-דומיין-אינטרנט** (ה-AI generation שהוחזר מתאר "website"/"online presence"), לא כדומיין-עסקי-פנימי (recruitment/saas/וכו') כפי שהקוד מתכוון. `Domain category`/`Domain risk assessment` (singleSelect ידניים לצידו) מכילים אותם ערכי placeholder (`Other`/`Low risk`) על אותה אצווה קטנה של רשומות — נראה כמו ניסוי/seed נקודתי ב-Airtable UI, לא feature מחובר. **קונפליקט שם:** `Domain category`/`Domain risk assessment`/`Domain summary` (עסק-לקוח לפי תעשייה) מול `domain` (routing פנימי לפי RouterDomain) — שני מושגים שונים לגמרי חולקים את המילה "Domain".

**E. `daily_digest.py`'s status filter מת חלקית:** `OR({Score}>=50, {status}='hot'|'Hot'|'HOT')` — הענפי status אף פעם לא יתאימו (§6). לא תוקן כאן (מחוץ לתחום), רק מתועד כממצא נלווה.

---

## 8. Source-of-Truth Policy (מוצע)

| קטגוריה | מדיניות מוצעת |
|---|---|
| **מצב תפעולי (operational)** | `status` בלבד. כל קוד המבצע ניתוב/סינון/reasoning לפי "האם ליד פתוח/סגור" צריך להשוות מול `LeadStatus.ALL`/הערכים הקנוניים — לא מול tier, לא מול Score thresholds. |
| **החלטה עסקית טרמינלית** | `Business Outcome` בלבד — נכתב אך ורק דרך `tma_api.py` המוולד. אין לשכפל בקוד מחוץ ל-`tma_api.py`. |
| **ציון מספרי** | `Score` בלבד — הקוד היחיד שמותר לו לחשב/לכתוב הוא `lead_capture.py`/`lead_memory.py`/`furniture_lead_funnel.py` (הקיימים כבר). Reasoning צריך לצרוך אותו כ-passthrough (כפי שכבר קורה ב-Phase 1) ולעולם לא לחשב Score עצמאי. |
| **דומיין עסקי** | `domain` (lowercase, plain text) בלבד — **לא** `Domain category`/`Domain risk assessment`/`Domain summary`. |
| **תצוגה חזותית (temperature/priority/gauge)** | שדות ה-formula בלבד (`טמפרטורה`/`אימוג'י טמפרטורה`/`מד ציון`/`עדיפות`/`תצוגת ליד`/`Suggested Followup`) — מחושבים אוטומטית מ-`Score`. אם צריך תצוגה בקוד (Telegram/TMA), יש לצרוך את ה-formula הקיים או לגזור זהה לספיו — **לא** להמציא סולם רביעי/חמישי חדש. |
| **`tier`, `Next Action`, `Next Followup`, `Domain category`, `Domain risk assessment`, `Domain summary`** | **לא מקור אמת לשום דבר כרגע** — ריקים/לא-אמינים בפועל. אין לבנות עליהם היגיון עסקי חדש עד החלטת ניקוי (§12/§16). |

---

## 9. Fields to Keep as Canonical

`status`, `Business Outcome`, `Score`, `domain`. (רביעיית הליבה שה-Reasoning Projection של BUG-104 Phase 1 כבר בנוי סביבה.)

## 10. Fields to Keep as Display-Only

`טמפרטורה`, `אימוג'י טמפרטורה`, `מד ציון`, `עדיפות`, `תצוגת ליד`, `Suggested Followup` — formula, מחושבים מ-`Score`, לא-ניתנים-לכתיבה ע"י עיצוב, בטוחים להצגה כפי-שהם.

## 11. Fields to Stop Using in Reasoning

`tier` (ריק, קונפליקט תיעוד), `Domain category`/`Domain risk assessment`/`Domain summary` (misapplied AI feature, קונפליקט סמנטי עם `domain`). אף אחד מהם לא נצרך כרגע ב-`core/leads_reasoning_projection.py`/`core/adapters/leads_adapter.py` בתור קלט אמיתי (tier מגיע כ-metadata ריק בלבד) — ההמלצה היא **לא להתחיל** לצרוך אותם, לא "להפסיק" צריכה קיימת.

## 12. Fields to Consider for Future Cleanup/Migration

- `tier` — מועמד למחיקה (0/92, ללא כותב מכוון) — **רק** אחרי שה-owner בוחר איזו מבין שלוש ההצהרות הסותרות (§7C) לעדכן/למחוק תחילה, כדי שלא יישאר תיעוד שקרי אחרי המחיקה.
- `Domain category`/`Domain risk assessment`/`Domain summary` — מועמדים למחיקה או לניתוק ה-aiText מהשדה `domain` (אם רוצים לשמר יכולת AI-summary, יש לחברה לשדה חדש שבאמת מייצג "web domain", לא ל-`domain` הפנימי).
- `Next Action` — לשקול אם לבנות כותב אמיתי (Phase 2A+) או למחוק אם אין תוכנית שימוש.
- `Next Followup` — כמעט-מת (1/92) — לשקול אם לחבר בפועל ל-`followup_engine.py`/`core/lead_recovery.py` (שכבר מחשבים תזמון בזיכרון) או לתעד כ"לא בשימוש הלכה למעשה".
- שני אתרי `"converted"` הלא-קנוניים (`lead_conversion.py:94`, `ad_attribution.py:195`) — לתקן ל-`LeadStatus.DONE` (ולציין: `ad_attribution.py` גם צריך לעבור מ-`tools.airtable_tools.airtable_update` הישיר ל-gateway המוולד) — **מחוץ לתחום Phase 2A.0 עצמה (audit-only), אך מודגש כאן כפריט Phase 2A מיידי מומלץ.**

## 13. Migration Risks

- **כל שינוי ל-`tier`** (מחיקה/שינוי שם) — נמוך בפועל (0/92) אך **תלוי בהחלטה על התיעוד הסותר תחילה** (§7C) — מחיקה ללא עדכון שלושת המקורות תשאיר תיעוד שקרי.
- **כל שינוי ל-`Domain*`** — נמוך (ללא code references), אך יש לבדוק אם יש Airtable Views/Interfaces (TMA לא נבדק כאן — מחוץ לתחום; ראה §14) שמסתמכים על השדות האלה ויזואלית לפני מחיקה.
- **תיקון שני אתרי `"converted"`** — סיכון בינוני: אם Airtable typecast כבוי (מאומת ב-`LeadOutcome` docstring, `airtable_schema.py:351-353`), כתיבת ערך לא-קיים אמורה להיכשל עם 422 — צריך לוודא בפרודקשן שהכתיבות האלה לא נכשלות שקטות (`lead_conversion.py:99-100` כבר מטפל בכישלון עם הודעת אזהרה למשתמש; `ad_attribution.py:201` מחזיר `bool(result.get("ok"))` — לבדוק בפועל מה קורה כשזה נכשל).
- **אין סיכון לשדות ה-formula** — Airtable/gateway כבר חוסמים כתיבה מלאה, אין מה "לשנות" בהם מלבד להשאיר כפי-שהם.

## 14. No-Change-Now List

כל 16 השדות — **אין לשנות שום דבר בפועל בשלב הזה**. במפורש: אין למחוק `tier`/`Domain*`, אין לתקן את שני אתרי `"converted"`, אין לחבר `Next Action`/`Next Followup` לכותב אמיתי, אין לגעת ב-formula-ים, אין לשנות frontend (TMA לא נגעה כלל בביקורת הזו).

## 15. Proposed Phase 2A Implementation Plan (after approval)

*מותנה באישור owner מפורש על ההחלטות ב-§8/§12 — לא מתחיל אוטומטית מ-SPEC זה.*

1. תיקון שני אתרי כתיבת `"converted"` (`lead_conversion.py:94`, `ad_attribution.py:195`) ל-`LeadStatus.DONE`, כולל מעבר `ad_attribution.py` לכתיבה דרך `tools/airtable_gateway.py` במקום `tools.airtable_tools.airtable_update` הישיר.
2. תיקון `daily_digest.py`'s status filter המת (`{status}='hot'/'Hot'/'HOT'`) לענף שאכן קיים (או הסרתו אם `{Score}>=50` מספיק).
3. תיקון `daily_digest.py:85`'s `f.get("next_step", ...)` למפתח הנכון (`LeadFields.NEXT_STEP`) — **רק** אם מוחלט לבנות כותב אמיתי ל-`Next Action` באותו סבב; אחרת תיעוד שזה שדה-לא-מוזן במפורש.
4. החלטת owner על `tier`: מחיקה / השארה-ריקה-מתועדת / בניית כותב אמיתי — ולאחר ההחלטה, תיקון שלושת מקורות התיעוד הסותרים (§7C) לעקביות.
5. החלטת owner על שלושת שדות ה-`Domain*`: מחיקה / ניתוק ה-aiText מ-`domain` וחיבורו לשדה חדש ייעודי / השארה כפי-שהיא כ-experiment מבודד.
6. איחוד חמשת מימושי tier/temperature (§7A) לפונקציה משותפת אחת (מוצע: להתבסס על ספי ה-formula הלייב, התואמים ל-`score_display.py`), אם/כאשר מוחלט לא למחוק tier/temperature display לגמרי.

## 16. Proposed Later Cleanup Plan (after production confidence)

- לאחר שבוע-שבועיים ללא רגרסיה מ-Phase 2A: לשקול מחיקת `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` בפועל מ-Airtable (אם הוחלט במחיקה ולא בשימור), כולל עדכון `airtable_schema.py::LeadFields`/`schema_cache.json` בהתאם.
- לשקול אם `Next Action`/`Next Followup` מקבלים כותב אמיתי (Phase 2B?) או מוסרים גם הם אם נשארים לא-בשימוש לאחר תקופת תצפית.
- לשקול backfill/ניקוי היסטורי לרשומות ה-seed שיצרו ערכי `Domain category="Other"` וכו' (10 רשומות), אם השדות נמחקים.

## 17. Test Plan

בהתאם לתשתית הבדיקות הקיימת בריפו (ראה `CLAUDE.md`'s Tests section) — **לא נכתב כאן קוד בדיקה, רק תוכנית לביצוע ב-Phase 2A בפועל**:

- הרחבת `test_airtable_gateway.py` לוודא ש-`READ_ONLY_FIELDS["Leads"]` עדיין חוסם את כל 6 שדות ה-formula אחרי כל שינוי עתידי (regression guard).
- הרחבת `test_bug104_leads_reasoning_projection.py`/`test_bug104_phase1_1_contract_hardening.py` לוודא שה-Reasoning Projection ממשיך להתנהג זהה (`tier` metadata ריק, `Score` passthrough) אחרי כל תיקון ב-Phase 2A — regression, לא feature חדש.
- בדיקת unit חדשה (Phase 2A) עבור תיקון `"converted"`: לוודא ש-`lead_conversion.py`/`ad_attribution.py` כותבים `LeadStatus.DONE` ולא `"converted"` הגולמי, ושה-gateway/validation לא דוחה את הכתיבה.
- בדיקת unit חדשה (Phase 2A, אם מתוקן) עבור `daily_digest.py`'s status filter — לוודא שהענף שנשאר/נוסף אכן תואם ערך `status` חי.
- `smoke_tests.py` ו-`python3 -m py_compile` בכל קובץ שישונה ב-Phase 2A, כמקובל בריפו.

---

**Files changed in this SPEC-only branch:** `docs/architecture/bug-104/PHASE_2A0_LEADS_SCHEMA_CANONICALIZATION_SPEC.md` (חדש). אין שינוי קוד, אין שינוי סכמה, אין שינוי frontend.
