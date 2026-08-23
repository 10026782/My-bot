# BOSS Bot — ROADMAP
**מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE.**

**CORE status (10/08/2026):** `CORE v1 — COMPLETE` / `READY TO FREEZE`.
Canonical current source:
`docs/audit/CORE_COMPLETION_AUDIT_20260810.md`. The four-layer verdict is
**PARTIAL / NON-BLOCKING**; formal Layer 2 TurnCoordinator implementation is
not complete. Freeze remains an owner/governance decision. Dated status
snapshots below are historical evidence and do not override this audit.

## C02–C04 Approval Coverage — current sequence (24/08/2026)

Current status: **CODE CLOSED / POLICY ITEMS REMAIN**. Detailed status and evidence live in
[`MAINTENANCE_STATUS_MATRIX.md`](MAINTENANCE_STATUS_MATRIX.md).

- Completed and statically verified: PR #881, #886, #889, #891, and #895.
- Ordinary direct business bypasses remaining: **0**.
- Policy queue: **A2 system-generated Tasks**; see `R-C07-A2` in the deferred register.
- Runtime status: **NOT PRODUCTION VERIFIED**.

עודכן: 24/08/2026 — **Canonical Leads Schema v1 — Track A/B הושלמו במלואם (ידני + קוד).**
בוצע ידנית ב-Airtable UI (owner, 22/08): (1) הוסרה האופציה `"ליד חדש"` מרשימת ה-choices
של `status` וגם של `Business Outcome`; (2) שינוי-שם ל-7 מתוך 8 האופציות של `Business
Outcome` (הוסר ה-trailing space — `"open "`→`"open"` וכו', `"archived"` היה כבר נקי) —
אומת ישירות דרך Airtable MCP `get_table_schema` על שני השדות, לא רק דווח. לוג ה-
`option_fallback` ב-Render היה שקט לגמרי מאז ה-rename (יום תצפית מלא). בהתאם, בוצע Track
B step 5: הוסרו `LeadOutcome.LEGACY_VALUE_FOR`, `airtable_schema.leads_outcome_option_fallback`,
`tools/airtable_gateway.py`'s `_is_invalid_option_error` וה-`option_fallback` param/logic
כולו מ-`airtable_patch`, וה-wiring משלושת ה-call sites (`tma_api.py::_at_patch`,
`tools/approval_actions.py::tma_write`, `tools/airtable_tools.py::airtable_update`) — ה-
`.strip()` בצד הקריאה (`core/adapters/leads_adapter.py`, `audience_intelligence.py`) נשאר
לצמיתות לפי החלטת owner מפורשת (21/08/2026), לא כ-scaffolding זמני. `tier`-field ו-
`Next Action`-field עדיין מכילים את האופציה `"ליד חדש"` — לא היו בסקופ הניקוי הזה, נותרו
כמתוכנן לצעד עתידי נפרד. טסטים: 37/37 (`test_airtable_gateway.py`, לאחר הסרת 17 בדיקות
T7 שבדקו את המנגנון שהוסר), smoke + כל רגרסיית BUG-104/105/A32/lead_service ללא שינוי.
עודכן קודם: 21/08/2026 — **Canonical Leads Schema v1 (owner-approved) — Phase 3 prep, שלבים ראשונים.**
תיקון תיעוד סותר על שדה `tier` (ראה Known Issues + N05 למעלה): אומת ישירות דרך Airtable
MCP ש-`tier` הוא singleSelect אמיתי וכתיב (לא formula, לא read-only, לא "לא קיים בסכמה"
כפי שנטען בעבר) — פשוט ריק ב-100% מהרשומות (0/39 נכון ל-21/08, 0/92 ב-17/07) וללא כותב
מכוון בקוד. תוקן במקביל ב-`daily_digest.py`, `.claude/skills/CLAUDE_SKILLS.md`, וכאן.
`status`-field data cleanup בוצע: רשומה יחידה עם `status="ליד חדש"` (ערך לא-קנוני, מחוץ
ל-`LeadStatus.ALL`) עודכנה ל-`new` דרך Airtable MCP; אימות `isNotEmpty`/`=` מראה 0 רשומות
נותרות על האופציה. הסרת האופציה עצמה מרשימת ה-choices דורשת עריכה ידנית ב-Airtable UI —
כלי ה-MCP הזמין (`update_field`) לא תומך בעריכת choices של singleSelect. מסמך מלא:
Canonical Leads Schema v1 (artifact, owner-approved 21/08/2026) — כולל targeted trace
ל-6 שדות ה-linked-record ו-atomic migration plan ל-`status`/`Business Outcome`.
עודכן קודם: 21/08/2026 — **N18 Phase 2, פרוסה חמישית (וסוגרת): terminal-turn-result
primitive (scope מצומצם, לפי החלטת owner מפורשת).** ROADMAP's Phase 2 description רשם
"terminal-turn-result" כאחד הדברים להוציא ל-shared infrastructure, אך אותו טקסט עצמו גם
מציין שזה בפועל שייך ל-Phase 4 (Structured UX Contract: entity/operation/status/
display_name/domain/owner/external_id, שכבת UX נפרדת, הסתרת internal IDs) — scope גדול
ומצטלב עם single-speaker/UX, ולכן נדחה במפורש לאחרון. לפני תחילת עבודה נבדק בפועל (לא
הונח): **אין כרגע double-response bug** — `app.py`'s early כן/לא-word dispatch (branches
── 2.55 ── confirm/cancel) וה-handle_lead_candidate() call site כבר עוצרים עיבוד נוסף
דרך `return` מיידי ברגע שמתקבלת תשובה לא-None; הסגירה קיימת כבר בזכות מבנה ה-control-flow
עצמו, לא בזכות חוזה מפורש. הריח האמיתי היחיד שנמצא: `_process_structured_file_upload`
(`app.py:5725-5732`) מסיק pending/written/failed ע"י התאמת prefix אימוג'י על המחרוזת
המוצגת (`reply.startswith("✅")` וכו') במקום שדה מובנה.
הוצג ל-owner בחירה בין (א) פורמליזציה מצומצמת של הקונבנציה הקיימת מול (ב) Phase 4 המלא —
**owner בחר (א) במפורש.** מומש: `core/turn_result.py` (חדש) — `TurnResult(message, status)`
dataclass קטן + 4 קבועי status (confirmed/cancelled/incomplete/failed), עם docstring
שמבהיר מפורשות שזה **לא** ה-Phase 4 המלא. הוחל **רק** על נתיב ה-draft confirm/cancel
הגנרי-אמיתי (זה שכבר הופרד ל-`core/draft_flow.py`): `_finalize_draft_cancel`/
`_finalize_draft_confirm`/`resolve_lead_draft_confirmation`/`_resolve_lead_draft`
(`lead_candidate_handler.py`) עכשיו מחזירים `TurnResult` במקום `Optional[str]` גולמי;
`handle_lead_candidate()` עצמה ממשיכה להחזיר `Optional[str]` כלפי חוץ ללא שינוי (unwrap
של `.message` בנקודת המעבר היחידה, `lead_candidate_handler.py:~1128`) — אין שינוי לחוזה
החיצוני שלה. **במפורש לא טופל בסלייס הזה** (סקופ גדול/עסקי מדי ל"פורמליזציה מצומצמת"):
ה-emoji string-sniffing ב-`_process_structured_file_upload` (עדיין קיים כפי שהוא —
`handle_lead_candidate()`'s רוחב Tier 1-5 לא נגע), ו-Phase 4 המלא (UX formatter,
internal-ID hiding, reply ownership) — עדיין ממתין, לא הפך פתאום ל-in-scope. 2 קריאות
ב-`test_lead_service_phase1.py` (section 9, בדיקת `resolve_lead_draft_confirmation`
ישירות) עודכנו להתאים לטיפוס ההחזרה החדש — אין שינוי התנהגות, 107/107 עדיין ירוקים.
עודכן קודם: 21/08/2026 — **Governance/Horizon refresh מול `origin/main` `6a0ba6a`.**
הבדיקה מול main המעודכן משנה את תמונת ההורייזונים: **H6 Command Center כבר אינו
PLANNED** — unified owner API/UI, owner attention, owner development projection ו־registry
projection קיימים על main, ולכן הסטטוס הוא `ACTIVE / MERGED / needs runtime verification`.
**H1/N18 פעיל** — Lead הפך ל-consumer ראשון של תשתית כתיבה משותפת (`structured_command`,
`draft_flow`, canonical Lead creation, Draft Card, confirm/cancel unification); עדיין חסרים
terminal-turn-result contract ואימות חי לשרשרת Draft→Approval→Write→Evidence על ה־deployed
SHA הנוכחי. **H4 התקדם אבל נשאר gated** — MoneyPrinterTurbo הוא staging-only, ו־Media Probe,
Artifact Contract v1, StoredArtifact MIME, Gateway readiness ו־fail-closed canary harness
מוזגו עד PR #804; אין להסיק production activation בלי gate evidence מפורש.

**סדר עדיפות נוכחי לפי Horizon:** (1) H0 Production Truth — deployed SHA + canaries
ל־BUG-164/BUG-051-FU/Tool Catalog/Command Center/N18; (2) H6 Command Center hygiene —
לאמת route חי ולסגור/לרשום את מקור `system_health` שמידרדר ל־`UNKNOWN`; (3) H1/N18 —
לסגור terminal-turn-result ולבחור consumer הבא רק אחרי gate; (4) H4 — להשאיר
MPT/Media/Gateway מאחורי artifact/hash/path/publishing-off gates; (5) H3 — החלטת בעלים
ל־Decision Hub/Layer 2 לפני activation; (6) H2/H5/H7 — רק אחרי שה־upstream יציב ומאומת.
עודכן קודם: 21/08/2026 — **N18 Phase 2, בירור פרוסה רביעית: clarification/validation-loop
wiring כבר בוצע.** נבדק לעומק לפני תחילת עבודה חדשה (per owner's staged plan) — המכניקה
המבוקשת (field ממתין → תשובת משתמש → validator → invalid נשאר על אותו שדה → valid מתקדם
לשדה הבא → review כשהכל מלא) **כבר קיימת** ב-`core/draft_flow.py`'s `resolve_draft_reply(text,
draft, DraftSpec)`, ו-Lead כבר צורך אותה כ-consumer דרך `core.lead_service.LEAD_DRAFT_SPEC`
(`_resolve_lead_draft()`, ── 2.55 ── בליבת `lead_candidate_handler.py:974-1034`) — בוצע
בפרוסה השנייה (20/08/2026, ראו למטה) לפני שהמשימה הזו התבקשה. אין duplicate Lead-specific
state-machine לזרימה הזו. הפער היחיד שנמצא מול הדרישה המפורשת: לא היה טסט רגרסיה יחיד
ורציף דרך ה-real orchestration path (`handle_lead_candidate()`) שעובר על **שני** שדות
נדרשים ברצף אחד (invalid phone → נשאר על phone → valid phone → invalid domain → נשאר על
domain → valid domain → review) — טסט תקין ל-phone וטסט נפרד ל-domain-by-number היו קיימים,
אך לא שרשרת רציפה אחת. נוסף `test_lead_service_phase1.py` section 7h (5 assertions חדשות,
107/107 ירוקים). Genericity (הוכחה שהמנגנון אינו Lead-specific) כבר מכוסה במלואה על ידי
`test_draft_flow.py` הקיים (synthetic title/due spec, 16/16 ירוקים) — לא נוסף כפילות.
**ממצא נפרד, לא טופל בסלייס הזה:** קיימת זרימה נוספת, נפרדת ומקבילה —
`_resolve_lead_clarification()`/`_maybe_start_lead_clarification()` (`lead_candidate_handler.py:612-857`)
— מטפלת ב-"טקסט חופשי חילץ טלפון אך לא שם" (Tier 5, capture אורגני, לא "ליד חדש" מפורש).
זו state machine נפרדת עם session key שונה (`active_lead_candidate`/`needs_clarification`,
לא `lead_draft`), שדה יחיד (name) או batch (names, per-phone), סדר עדיפויות משלה
(TTL/cancel/interrupt/valid/unclear) — **אינה** משתמשת ב-`DraftSpec`/`resolve_draft_reply`.
טכנית זו "duplicate Lead-specific validation-state machine" נוספת, אך הצורה שלה (שדה יחיד,
לא multi-field walk עם phone/domain) לא תואמת את התיאור/התרחיש המפורש שהתבקש בסלייס הזה.
איחוד שלה לתוך `draft_flow.py` הוא decision נפרד וגדול יותר (trigger שונה, batch mode,
priority-ordering) — לא בוצע כאן, ממתין להחלטת owner אם ומתי.
עודכן קודם: 21/08/2026 — **N18 Phase 2, פרוסה שלישית: Confirm/Cancel Dispatch
Unification.** `app.py`'s early כן/לא-word interception היה קורא ל-`should_prefer_lead_draft()`
עד 3 פעמים באותו turn (PR2 fast-path + ── 2.55 ── confirm branch + ── 2.55 ── cancel branch),
כל אחד עם קריאת Sessions עצמאית משלו. עכשיו מחושב פעם אחת בלבד ומשמש בשתי הענפים — נקודת
החלטה יחידה, ללא שינוי התנהגות (`resolve_lead_draft_confirmation`/`_finalize_draft_confirm`/
`_finalize_draft_cancel` לא זזו). לא תלוי ב-`_snapshot_fetch_failed` (זו הייתה תקלה נפרדת
לגמרי ב-ActionGateway, לא ב-Sessions). טסט חדש `test_n18_draft_dispatch_unification.py` מוכיח
זאת end-to-end דרך `app.run_agent()` (לא רק ברמת ה-unit של `core/lead_candidate_handler.py`
כמו section 9 הקיים ב-`test_lead_service_phase1.py`). עדיין לא הועבר: clarification/
validation-loop wiring (הפרוסה הבאה) ו-terminal-turn-result (אחרון, per owner sequencing).
עודכן קודם: 20/08/2026 — **N18 Phase 2 (בעבודה): שתי פרוסות ראשונות של Shared Write
Primitives.** לפי הבהרת owner ("Phase 2 הוא תיקון ארכיטקטוני, לא רק הכנה לעתיד") — המכניקה
הכלל-מערכתית שכבר נבנתה בתוך Lead מוצאת בהדרגה משם ל-primitives משותפים, ללא שינוי
התנהגות (99/99 טסטי Lead נשארים ירוקים, לכל primitive טסטים ייעודיים משלו):
`core/structured_command.py` (trigger/delimiter/split מכניקה, commit `45ef423`) ו-
`core/draft_flow.py` (מכונת מצבים filling/edit_choice/review טהורה — ללא I/O, ללא כתיבה —
`resolve_draft_reply(text, draft, DraftSpec)`). Lead נשאר consumer: כל שדות/prompts/
validators שלו מרוכזים ב-`core.lead_service.LEAD_DRAFT_SPEC`. עדיין לא הועבר: terminal-
turn-result contract (Phase 4) ו-Canonical Writers consolidation (Phase 3). ראו N18 למטה
לפירוט מלא.
עודכן קודם: 20/08/2026 — **N18 נפתח: Canonical Write Infrastructure.** Phase 1 (canonical Lead
creation, PR #780) נסגר לפי קריטריון היציאה שלו (QA report מלא + תיקון structured note
parsing, commit `4e44bca`). החלטת owner: לא בונים מערכת לידים נפרדת — התשתית שנבנתה
(Draft→Validation→Edit→Preview→Approval→Canonical write→Evidence→UX) הופכת ל-shared write
framework עבור BOSS כולו (Lead=consumer ראשון, לא יחיד). ראו N18 למטה לפירוט Phase 2-6
המלא ולעקרון "Never solve the same write interaction twice".
עודכן קודם: 16/08/2026 — **Owner Truth-Reset (docs only, ops/owner-handoff handoff)**:
בעל הבית אימת ידנית 4 מתוך 5 באגים היסטוריים (BUG-002/004/005/007, ראו
`BUG_AUDIT_LOG.md`) כ-RUNTIME/PRODUCTION VERIFIED; BUG-003 נשאר **PARTIAL /
DEFERRED** במפורש (owner decision — לא להשקיע ב-game internals כרגע).
בטבלת "C — הושלם" למטה: C13 (Shared Memory) סומן **SUPERSEDED** — הקובץ
ההיסטורי `core/shared_memory.py` לא קיים, היכולת פוצלה ליכולות Business
Memory קיימות; C18 (Store Protocol) סומן **PARTIAL/DEFERRED — לא סגור**
ומוזג לתכנית storage-decoupling רחבה יותר (`core/stores/base.py` לא קיים,
`AirtableStorageProvider` הצר יותר ב-`providers/airtable_shim.py` בלבד).
**סתירה שנמצאה ולא יושמה:** ה-handoff הניח מיפוי C04="Context layer"
ו-C10/C11/C15="Lead Qualifier"/"Lead Memory"/"Followup Engine" — מיפוי זה
לא תואם את טבלת C-numbers האמיתית כאן (C04 בפועל = Feature Flags; C10/C11/C15
לא קיימים כפריטי C בטבלה זו כלל — Lead Qualifier/Lead Memory/Followup Engine
מתועדים כ-F09/F10/F11 בהמשך המסמך, לא כ-C). לא בוצע שינוי סטטוס תחת ID שגוי;
ראו `CHANGELOG.md` לפירוט מלא.
עודכן: 15/08/2026 — **`BUG-164` הגנת-עומק ל-`compose_brief()` + תיקון תיעוד-דריפט.**
`creative_ideas` עצמו כבר **תוקן דטרמיניסטית וממוזג** (PR2, `e9d1ca8`, ראה
`BUG_AUDIT_LOG.md::BUG-164`) — אינו עובר יותר דרך `compose_brief()` כלל, אלא דרך תפריט
סגור + `authority_filter_and_render()`. השורות מ-13/08/2026 למטה תיארו זאת כ"טרם PR/merge"
כי נכתבו לפני ש-PR2 קויים; התוכן שלהן תוקן בהתאם. מה שכן חדש כאן: `_DEMAND_FIDELITY_RULE`
(commit `b375602`, ענף `claude/continue-f23-dmbgr7`) מוסיף הגנת-עומק ברמת prompt ל-3 סוגי
המשימה הנותרים של `compose_brief()` — `creative_review`/`ad_package`/`publishing_plan` —
שעדיין free-text וללא authority gate דטרמיניסטי. בדיקות מקומיות עברו (`test_marketing_brief_
composer.py` חדש 5/5, `smoke_tests.py`, `test_marketing_orchestrator.py`,
`test_cmd_marketing_status.py`, `compileall`, TC10 isolated regression `--repeat 2` STABLE
32/33 — הכשל היחיד משוחזר זהה על `origin/main` נקי, pre-existing). **לא VERIFIED**: תיקון
ברמת prompt-contract בלבד, לא הוכח מול קריאת AI חיה. פרטים מלאים ב-`BUG_AUDIT_LOG.md::BUG-164`.
עודכן קודם: 14/08/2026 — **תיעוד בלבד: `BOSS_MEDIA_MARKETING_AUDIT.md` מוזג ל-`main`.** קובץ
ה-audit ההיסטורי של F23 (reuse מול Ventures/Decisions/Interaction Log/Sessions — כולם
נפסלו) הועבר (cherry-pick, ללא שינוי תוכן) מהענף הבלתי-ממוזג `docs/media-marketing-
enablement-audit` ל-`main`, וההפניה אליו בסעיף F23 למטה עודכנה בהתאם (הוסרה ההערה
"קיים רק בברנץ'... לא מוזג"). אין שינוי קוד/schema/behavior — תיעוד בלבד.
עודכן קודם: 13/08/2026 — **F23 M2 (Telegram slice) — ✅ VERIFIED IN PROD.** PR #613 מוזג,
Render deploy `98f3626` מאשר את הקוד חי (ancestry מאומת), והבעלים הריץ live regression
אמיתי ב-`/telegram` production מול Demand ייעודי לבדיקה: `/marketing_status` הציג רשימה
נכונה, כרטיס Next Action לשלב `ideas_generated` תאם בדיוק ל-`compute_next_action()`, ובחירת
רעיון הפעילה בהצלחה את מסלול הכתיבה הקיים מ-M1 (`mkt_select:`→`select_creative()`→
`save_production_handoff()`→`update_demand_stage`) והפיקה Production Handoff — **החלקים
הדטרמיניסטיים שלו** (persona/חוקים/פרטי הדרישה/קלטי הפקה מסומנים "לא סופק") נכונים
ומאומתים; **תוכן `[הרעיון שנבחר]` המוטמע בתוכו אינו מאומת/מוגן** ומכיל עיוות עובדתי
אמיתי. **מאותה בדיקה חיה נפתח גם ממצא נפרד, לא-חוסם**: הרעיון שה-AI יצר (Prompt 1) עיוות
עובדה כמותית מה-Demand — נרשם כ-`BUG-164` (Creative Ideas grounding), במפורש לא
כ-regression של M2 ולא מעכב את הסטטוס VERIFIED שלו (שמכסה orchestration/runtime, לא את
תוכן הרעיונות שה-AI מייצר). פירוט מלא בסעיף F23 למטה.
עודכן קודם: 12/08/2026 — **F23 (BOSS Marketing Bridge M2, Telegram slice) — `/marketing_status`
נוסף.** רשימת Demands מורשית (`identity.can_access_domain()`, נבדק גם ב-list וגם שוב
ב-callback — לא מסתמכים על הסתרת ה-ID בתוך `callback_data` כאבטחה) + כרטיס "Next Action"
לכל דרישה, מחושב ע"י מודול חדש `marketing_orchestrator.py` (pure/pull-only, אותו חוזה כמו
`decision_orchestrator.py` — לעולם לא כותב canonical state). כשיש בדיוק Creative אחד
Pending Review, הכרטיס משתמש מחדש ב-`_idea_keyboard()`/`mkt_select:` הקיימים מ-M1 —
**M2 לא מוסיף מסלול כתיבה חדש, רק נקודת כניסה מורשית נוספת לזה הקיים.** יותר מ-Creative
אחד ממתין נחשב מצב לא עקבי ונכשל בבטחה (לא בוחר "הראשון" שרירותית) — לא לנחש; שלבים
שמורים-בסכמה-אך-לא-חיים (`brief_composed`/`selected`/`closed`) מקבלים כרטיס "לא מטופל
אוטומטית", לא behavior מומצא. TMA screen (החלק השני של M2 לפי הסעיף למטה) **לא נבנה
בשינוי הזה במפורש** — נשאר לתכנית נפרדת. קבצים: `marketing_orchestrator.py` (חדש),
`marketing_gateway.list_demands()` (חדש), `cmd_marketing.py` (`/marketing_status`+
`מצב_שיווק`, `mkt_status:` callback). בדיקות: `test_marketing_orchestrator.py`,
`test_cmd_marketing_status.py` (חדשים) + self-tests מורחבים.
עודכן קודם: 12/08/2026 — **F23 (BOSS Marketing Bridge M1) — 3 PR נוספים מוזגו ל-`main`
ואומתו חי בפרודקשן, כולל תיקון bug ארכיטקטוני אמיתי שנמצא רק בבדיקה חיה.** תמצית
מלאה בסעיף F23 למטה; כאן רק ה-headline: (1) PR #602 — redesign ל-`/marketing_new`
wizard ללא Airtable record IDs גלויים (invoked `decision.ux_no_internal_ids`).
(2) PR #603 — "Manual Context Brain": `DomainProfile.business_rules` עם תוכן אמיתי
ל-recruitment (לא placeholder), ושלב `Constraints` חדש ב-wizard. (3) PR #604 —
**תיקון קריטי**: כל טקסט חופשי שנשלח ל-wizard (כולל "כן"/מספרים) היה נופל בשקט
ל-`run_agent()` (ה-Agent הכללי) במקום להיתפס ע"י `cmd_marketing.py`, כי
`app.py`'s `_webhook_telegram_impl` בדק בעלות (`has_pending_text_capture`) רק
עבור `cmd_update`, לא עבור `cmd_marketing`. נמצא ע"י הבעלים בבדיקה חיה אמיתית
(לא ע"י review), תוקן ע"י הוספת `cmd_marketing.has_pending_capture()` +
governance check סטטי חדש ב-`smoke_tests.py` שמונע רגרסיה שקטה. **אומת חי**:
webhook regression אמיתי מול production (`recfrUEj6e7uHEEf9`) — "כן"/"3 שנים"
נתפסו נכון כתשובות intake, לא דלפו ל-Agent. `STATUS` בסעיף F23 עודכן ל-✅
VERIFIED IN PROD.
עודכן קודם יותר: 11/08/2026 — **תיעוד PR #595–#597 (פער-תיעוד, נסגר ישירות מ-`git log
origin/main`, לא הועלה כ-PR נפרד ע"י מי שביצע אותם):** אומת ישירות ב-`git
log`/`git show --stat` על `origin/main` (`f69d7b3`), לא לפי claim. תמצית
(לפירוט מלא ראו `CHANGELOG.md`, 11/08/2026): **PR #595 — PA-01**: `Intent.
UPDATE_TASK`/`COMPLETE_TASK` מקבלים כעת `Handler.TOOL` דטרמיניסטי דרך
`parse_deterministic_task_reference()` חדש ב-`core/router/router.py` (אותה
תבנית fail-closed כמו CREATE_TASK) — סגר את ה-CORE blocker האחרון שנותר;
הקוד ה-downstream (`app.py`'s `_queue_deterministic_task_update()`) כבר היה
קיים אך לא היה נגיש מניתוב חי. ללא flag; פרוס ל-Production 15:57 UTC
10/08/2026 (מאומת מול Render API), Staging-verified מ-15:30 UTC (pre-merge,
content-identical). **PR #596 — Canonical CORE Completion Audit**
(`docs/audit/CORE_COMPLETION_AUDIT_20260810.md`) — verdict סופי: `CORE v1 —
COMPLETE` / `READY TO FREEZE` (freeze עצמו נשאר החלטת owner, לא מוכרז).
שני פערים לא-חוסמים נותרים: main's CI אדום על שער ה-freshness של Context
Librarian (governance, לא regression פונקציונלי — דורש
`refresh-after-merge --apply`), ו-Layer 2 (`TurnCoordinator` פורמלי) עדיין
ללא מימוש כלל בקוד — מוחלף היום ע"י `router.py::route_request()`. מסמך זה
הוא ה-CORE status הקנוני המצוטט בראש הקובץ הזה (שורות 4–9). **PR #597** —
תיקון טסט חד-שורתי ל-Context Librarian budget assertion, ללא שינוי runtime.
עודכן קודם: 10/08/2026 — **F15 (crm.py → airtable_gateway) — עדות Staging אמיתית
נוספה**: `scripts/verify_f15_staging.py` הורץ מ-Render staging shell,
`run_id=f15-20260810T142420Z-01c6bc0a1f`, `F15 — COMPLETE AND STAGING
VERIFIED`, כל 13 gates `PASS` (כולל `f14_gate_path` — אישור אינטגרציה חיה
עם F14 Contact Gate, ו-`crm_static_no_direct_http_writes`). פירוט מלא
בסעיף F15 למטה.

עודכן: 10/08/2026 — **TC10 COMPLETE AND VERIFIED**: real-staging run
(`scripts/verify_tc8_staging.py` + `scripts/verify_tc9_staging.py`, Render
staging shell) confirmed `FINAL: DONE` on both — pending/turn_id/real
successful execution/failed/clean-cleanup all verified against real
staging Airtable+PostgreSQL. One more self-caught bug fixed along the way
(PR #592 — an Airtable-base-id name check that could never pass for any
real base). `CORE OPERATIONAL VERIFICATION GATE — READY`. See
`docs/architecture/turn-coordinator-full/TC10_OPERATIONAL_VERIFICATION_HARNESS.md`
§6.3/§10.

עודכן: 10/08/2026 — **TC10 operational verification harness (implementation
complete, staging verification pending)**: `scripts/run_isolated_regression.py`
+ `scripts/regression_matrix.py` + `scripts/staging_identity.py` (new
isolated-regression mode, immune to ambient credentials), `scripts/verify_tc9_staging.py`
(new TC9 MessageContract staging canary — written, not yet run against real
staging), `scripts/verify_tc8_staging.py` fixed to stop running the full
regression matrix against real shared staging Airtable (the root cause of
the BUG-122 contamination TC8 handed off). The isolated runner's own first
version regressed 2 test files by over-scoping its credential override
(Telegram, not just Airtable); caught by this PR's real CI + review,
root-caused and fixed within the same PR — 21/21 full matrix, stable
across 2 repeated runs, confirmed both locally and by this PR's own real
GitHub Actions `backend-ci` run on the corrected commit (`2b6ecb3`, run
31362450916, `FINAL: PASS`). See
`docs/architecture/turn-coordinator-full/TC10_OPERATIONAL_VERIFICATION_HARNESS.md`
for the full audit/evidence. No ActionGateway/TC7/TC8/TC9/F14/router/
approval-policy runtime code changed.

עודכן: 10/08/2026 — **תיעוד PR #572–#588 (17 מספרי PR ברצף, כולל #576 שהוחלף
ע"י #579 באותו branch — לא deliverable נפרד; פער-תיעוד, נסגר ישירות מ-`git log
origin/main`, לא הועלה כ-PR נפרד ע"י מי שביצע אותם):** אומת ישירות ב-`git log`/
`git show --stat`/grep על `origin/main` (`cec3f83`), לא לפי claim. תמצית (לפירוט
מלא ומאומת-קוד ראו `CHANGELOG.md` ו-`AI_CONTEXT.md`, 10/08/2026): **TC7-B1/B1.1**
(#583/#587) — מוסיף `core/claim_authorization.py`, **grep מאשר אפס קוראים** מחוץ
למודול/לטסט שלו; למרות השם "TC7-B", **אינו** מחבר בפועל את TC7-A ל-RP4 לכדי החלטת
claim-authorization חיה — עדיין unwired. **TC7/RP5 execution-shadow** (#579,
מחליף #576) — מחבר את TC7-A ל-RP4 בפועל תחת `FEATURE_EVIDENCE_FINALIZER` (כבוי
כברירת מחדל), אך זו RP4 shadow logging, לא claim-authorization. **TC8** (#585) —
`core/turn_state_repository.py` חדש, **ללא flag, חי ומחווט בפועל** בארבע נקודות
callback/text ב-`app.py` (approve/reject/cancel), fail-closed בכשל; "staging
verified" הוא טענה בתיעוד בלבד, לא artifact מאומת. **TC9** (#588) — `ActionFact`/
`GatewayReply` מקבלים שדות MessageContract, בנייה חיה תמיד, אך המרת-הטקסט בפועל
עדיין מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER` כבוי. **TC7-A** (#573) — סגירת
review, unit-tested, shadow-only. **F14-B2** (#577, לא #572 שהיה docs-only) —
שני קוראים חדשים ל-`find_or_create_contact()` (`dispatcher.py` ה-`airtable_add`
path, `approval_actions.py`'s `tma_write`), אך **עדיין אין gate מרכזי ב-
`ActionGateway`/dispatcher** — נקודות-יירוט קשיחות נוספות, לא ריכוזי. **Track A**
(#581/#582) — קנוניזציה צרה של "מחר" בכותרת משימה ל-due-date, ללא flag, חי; #582
מספק ראיית staging ומכריז "COMPLETE". **Track D** (#580) — logging חדש ואמיתי
ל-RuntimeSchemaProvider/IngressEnvelope (סוגר "OBSERVABILITY DEBT" שתועד ב-
`BOSS_UNIFIED_MASTER_PLAN.md` §3.5), אך **לא** אומת עדיין מול deploy/Render חי.
שאר הפרים (#572/#574/#575/#578, docs; #584/#586, CI/test hardening) ללא שינוי
runtime. **חשוב:** `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1 (Program
Map) **עודכן באותו סבב** (10/08/2026) לשורות A/F/H/I/J מול הממצאים לעיל — אך
§3.5.2 (target chain diagram) ו-§3.5 (Runtime Capability Status snapshot) שם
**נשארו מתוארכים 09/08/2026 ולא נסקרו מחדש בסבב הזה** — לא לצטט אותם כעדכניים.
עודכן קודם: 09/08/2026 — **תיעוד PR #562–#570 (8 substantive PRs) + BUG-105 verification:**
**Substantive PRs merged 08/08–09/08/2026:** TC5 entity resolver (PR #562, 08/08/2026), TC4 lead builders (PR #564, 08/08/2026), TC4 task-integration hardening (PR #565, 08/08/2026), TC6 WS2 reply-ownership (PR #566, 08/08/2026), Emergency Stop backing hardening (PR #567, 08/08/2026), F14-A1 contact gate (PR #568, 09/08/2026), TC6 integrator app.py cutover (PR #569, 09/08/2026 — ראו TC6_APP_INTEGRATOR_PATCH_SPEC.md §0 Cross-Layer Impact Matrix), F14-B1 legacy caller migration (PR #570, 09/08/2026). כל שמונה PRs מוזגו בפועל ואומתו ב-`git log origin/main` / `git merge-base --is-ancestor`.
**BUG-105 verification (docs-only):** אומת מחדש מול `origin/main` (`38d9226`), כבר מכוסה ב-code — אין שינוי קוד פתוח. BUG-105: regex לפני/אחרי זהה; 204 suites + 11 בדיקות מטריצת פורמטים עברו. **F14 Discovery/Planning** הוא תיעוד היסטורי של מפת נתיבי הכתיבה: שני נתיבי Contact creation בפועל (`crm_add_contact` legacy, `airtable_add` generic), ללא dedup; import scripts ו-`session_store.py`/`contact_resolver.py` אינם gates. **מאז:** F14-A מוזג (#568), F14-B1 מעביר `crm_add_contact()` ו-`convert_lead_to_contact()` דרך אותו gate; F14-B2 עדיין לא התחיל. **TC, Emergency Stop, F14 phases A-B1 status:** TC6 (PR #566/#569) מחליף בפועל את ה-approval reply-ownership projection תחת `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` — ברירת המחדל בקוד נשארת `false`, אך ב-runtime הפרוס בפועל הדגל `true` (אומת מול Render dashboard + לוגי production חיים + תמלול Telegram, 09/08/2026 — ראו `docs/architecture/turn-coordinator-full/TC6_APP_INTEGRATOR_PATCH_SPEC.md` §Status ו-N17 item 4 למטה לתחולה המדויקת); אכיפת TC6 reply-ownership פעילה כעת בפרודקשן. שאר 7 ה-PRs לא שינו behavior חי בעת המיזוג; F14/TC4/TC5/Emergency-Stop נשארים structural/foundational, live אך enforcement/integration נדחה.
עודכן קודם: 07/08/2026 — **תיעוד PR #525–#552 (פער-תיעוד, נסגר ישירות מ-`git log origin/main`,
לא הועלה כ-PR נפרד ע"י מי שביצע אותם):** 28 PRs נוספים מוזגו ל-`main` בין 05–06/08/2026 בלי
עדכון ROADMAP נלווה — אומת ישירות ב-`git log`/`git merge-base --is-ancestor` על `origin/main`
(`c5dbe86`), לא לפי claim. תמצית (לפירוט מלא ראו `AI_CONTEXT.md`, 06/08/2026): Context
Librarian automation hardening (#525/#526/#534, dev tooling בלבד); status-routing/terminal-
replay bug fixes (#528–#533, חיים ללא flag); TurnCoordinator Phase 2 WS1–WS3 (#536–#544, WS1
מוזג ומחווט חלקית, WS2/WS3 מוזגים כמודולים עצמאיים לא-מחווטים); אינטגרציית runtime צרה +
תיקון fingerprint (#545/#546, follow-up #547/#548/#549 — תיעוד בלבד ב-#549); ארבעה תיקוני
באג מאימות Staging ל-PR #546 — BUG-153/154/155/156 (#550, ללא flag, מוזגים אך **טרם deployed
ו-טרם verified בפרודקשן**); BUG-157 concurrency race ב-`propose_action()` שנמצא ע"י CodeRabbit
על PR #550, תוקן עם CAS אטומי (#552, מוזג אך **טרם deployed**); שתי רגנרציות `AI_CONTEXT.md`
(#551 ו-#553). **`BUG_AUDIT_LOG.md` מסמן את חמשת התיקונים הללו כ-"Merged: לא עדיין" — שדה
זה לא עודכן אחרי המיזוג בפועל; אומת ב-ancestry-check שהם כן מוזגים.** אף אחד מהם לא רשם flag
חדש ב-`feature_flags.py`. הפער ל-deploy החי (`5ec37b8`, PR #516) המשיך לגדול — 36 PRs
(#517–#552) עדיין לא אומתו כפרוסים.
עודכן קודם: 02/08/2026 — **תיעוד PR #521–#524 (פער-תיעוד, נסגר ישירות מ-`git log origin/main`,
לא הועלה כ-PR נפרד ע"י מי שביצע אותם):** ארבעה PRs נוספים מוזגו ל-`main` ב-01/08/2026 בלי
עדכון ROADMAP/CHANGELOG נלווה — תוקן כאן, אומת ישירות ב-`git show`/`git log` על `origin/main`
(`7c3833a`), לא לפי claim. **PR #521** (`271b293`, merge `a2be204`) — רגנרציית `AI_CONTEXT.md`
הקודמת (סגרה את פער PR #517–#520; הוחלפה ברגנרציה מ-02/08). **PR #522** (`baabd46`, merge
`ef55cd9`) — תיקון פער parity ב-shadow: `_compose_status_reply_unified()` תיאר כל pending
contract גנרית ("הוספת רשומה: ...") גם כש-Task-creation contracts אמורים להציג את כותרת
המשימה עצמה (כפי שהמסלול החי, `build_approval_lifecycle_result()`, כבר עושה) — נסגר;
`FEATURE_UNIFIED_STATUS_FORMATTER` נשאר כבוי, אין שינוי ל-approval logic/ownership/routing.
**PR #523** (`093a46c`+`4569e7e`+`ce7cee8`+`713ca5c`+`bd25327`+`c5bd7f8`+`86b6e58`, merge
`96a8313`) — F52 D-014 עד D-017: (D-014) הבעלים אישר Option B — "לאשר? כן / לא" נשאר הניסוח
הקנוני חוצה-ערוצים; (D-015) פיצול ניסוח בין prompt-חדש (מיד אחרי שבקשה נכנסת לתור) לבין
status-query (שאלה על פעולה שכבר ממתינה), שניהם task-noun-aware ("משימה" מול "פעולה");
(D-016) `query_execution_status()`'s מקרה יחיד-ב-queue מחווט ל-renderer החדש; (D-017) פתרון
5 השאלות הפתוחות (OQ1–OQ5) של Approval Pending Batch Migration — count=0 מציג "אין כלום
ממתין" (STATE_IDLE הקיים), count=1 מציג ניסוח יחיד (D-016), count≥2 מתכנס ל-
`STATE_APPROVAL_PENDING_BATCH` המשותף, שם "ActionContracts"/ניסוח legacy יורד לגמרי מהטקסט
היעד; דליפת `tool_name` גולמי (OQ4) הופרדה במפורש כמעקב-המשך נפרד (ראה D-018). כולל שני
מסמכי scope תכנוניים (`APPROVAL_PENDING_BATCH_MIGRATION_SCOPE_V1.md`,
`RECONFIRMATION_TOOL_NAME_LEAK_FIX_SCOPE_V1.md`) ותיקון תאריכי ratification + markdownlint
בעקבות ביקורת CodeRabbit. כל D-014–D-017 עדיין מאחורי `FEATURE_UNIFIED_STATUS_FORMATTER`
(shadow/כבוי) — אין שינוי runtime חי. **PR #524** (`76c08f3`, merge `7c3833a`) — D-018: תיקון
דליפת `tool_name` גולמי ב-`_describe_contract_for_reconfirmation()` בשלושה מסלולים חיים
(`describe_pending_queue()`, `describe_superseded_reason()`, פרומפט reconfirmation ב-
`_resolve_single_contract()`) שהיו חשופים ל-9 מתוך 11 tools עם `requires_approval=True`.
**זהו היחיד מבין ארבעת ה-PRs שאינו מאחורי flag** — הטקסט משתנה בפועל ברגע ה-deploy הבא, לא
shadow. תיקן גם assertion ישן שהתבסס על הדליפה. **כל ארבעת ה-PRs מוזגו בפועל ואומתו ב-`git
log origin/main`; פרט ל-D-018, אף אחד מהם לא שינה טקסט/התנהגות חיה של הבוט העסקי.** ראו
`AI_CONTEXT.md` (02/08/2026) לתמונת מצב מלאה.
עודכן קודם: 01/08/2026 — **תיעוד PR #517–#520 (פער-תיעוד, נסגר ישירות מ-`git log origin/main`,
לא הועלה כ-PR נפרד ע"י מי שביצע אותם):** ארבעה PRs מוזגו ל-`main` בין 30/07–31/07/2026 בלי
עדכון ROADMAP/CHANGELOG נלווה — תוקן כאן, אומת ישירות ב-`git show`/`git log` על `origin/main`
(`9f203f4`), לא לפי claim. **PR #517** (`9184834`+`c5f5516`+`dd63c4a`, merge `0ddd91c`) —
`daily_digest.py`: `_lead_temperature_counts()`/`_leads_scoring_summary()` חדשים, מוסיפים שורת
"📊 לידים: HOT/WARM/COLD" לדוח היומי; אין flag, קוד תמיד פעיל ברגע שפרוס. Force-gate override
אושר במפורש ע"י המשתמש (ענפי `claude/*` לא-ממוזגים היו פתוחים באותו רגע). **טרם פרוס** — deploy
החי המתועד האחרון (`5ec37b8`) קודם ל-commit הזה. **PR #518** ("PR E", `4e52561`, merge `952bb02`)
— `core/action_gateway.py`'s `_compose_status_reply_unified()`: outcome `pending` (בנוסף ל-`failed`
הקיים מ-PR D) עובר עכשיו גם הוא דרך `MessageContract`/`ActionFact` adapter; עדיין מאחורי
`FEATURE_UNIFIED_STATUS_FORMATTER` (shadow/comparison), אין שינוי ל-evidence/approval authority.
Force-gate override אושר במפורש (חמישה ענפי `claude/*` לא-ממוזגים היו פתוחים). **PR #519**
(`82df448`, merge `49d6af8`) — רגנרציית `AI_CONTEXT.md` קודמת; הוחלפה ברגנרציה הנוכחית (01/08).
**PR #520** (`ae7aaba`+`b700fa4`, merge `9f203f4`) — Context Librarian: תיקון אכיפת token-budget
ב-`librarian.py` + `profiles.json`, ו-refactor ל-rendering של notes בלי slicing; dev tooling
בלבד, אין שינוי runtime לבוט העסקי. Force-gate override אושר במפורש (אותה סיבה). **כל ארבעת
ה-PRs מוזגו בפועל ואומתו ב-`git log origin/main`; אף אחד מהם לא שינה ברירת-מחדל של הבוט
העסקי.** ראו `AI_CONTEXT.md` (01/08/2026) לתמונת מצב מלאה.
עודכן קודם: 30/07/2026 — **PR #515 מוזג ל-`main`** (commit `15fe851`, אומת ב-grep ישיר):
Non-raising dry-run estimation mode for Context Librarian (`estimate_bundle()` + `estimate_all_profiles()` + CLI `estimate` subcommand). Hebrew translation fixes from PR #513. All docstrings translated to Hebrew. 104/104 tests passing. Feature-flag-off by default (no production wiring). Addresses need for dry-run estimation without side effects in refresh-after-merge tool and planning gates (Phase 2 enablement + consumption gating deferred).
עודכן קודם: 30/07/2026 — **PR #504 מוזג ל-`main`** (commit `55312ab`, אומת ב-grep ישיר):
Multi-layer alignment stages 3-5 — first real Consumption Enforcement pilot
(`cross_layer_architecture` profile) + catalog completeness fix (0 removed, 10 added;
רה-verify: `CONSUMPTION: COMPLETE`). Planning-only, אין שינוי runtime/CI. Verdict נשאר
`PASS_WITH_GAPS`; Phase 3 נשאר NOT READY. ראו N17 item 12 ל-backlog הממוקד שנפתח בעקבות
זה, ו-`docs/governance/librarian/FIRST_REAL_CONSUMPTION_PILOT.md`/
`docs/architecture/multilayer/BOSS_MULTILAYER_ALIGNMENT_PLAN.md` לפירוט המלא.
עודכן קודם: 30/07/2026 — **PR2 staging acceptance audit — סבב אימות חי בפרודקשן** (Hotfix B/#496,
E/#497, C/#498+#499 כולם מוזגו; E ו-C אומתו חי בפרודקשן, B רדום כש-PR2 דלוק, BUG-151's
יכולת עסקית כללית אומתה חי אך תיקון #1 [הממיר]/#2 [חריגת mutation-budget] עדיין לא —
שניהם דורשים `CanonicalizationError` בפועל, שלא קרה בסבב הזה). ראו N17 item 11 לפירוט המלא ו-
`AI_CONTEXT.md`/`CHANGE_CONTROL_LOG.md` C182–C184 להוכחות.
עודכן קודם: 29/07/2026 — **PR2 (Deterministic Approval Cost Cuts) מוזג ל-`main`** —
PR #491 (preflight, `12e2a45`) + PR #492 (implementation, `db51afc`), שניהם אומתו
ב-grep ישיר. תיקון סטטוס נלווה: item 10 (Consumption Enforcement Phase 1, PR #490)
תוקן מ-"PR נפתח, טרם מוזג" ל-✅ מוזג — הסטטוס הקודם היה טעות-רישום, ה-PR כבר היה
ממוזג. ראו N17 למטה, item 11 לפירוט המלא.
עודכן קודם: 29/07/2026 — **N17 עדכון: Consumption Enforcement PR #488 מוזג ל-`main`** (commit
`abf2804`, אומת ב-grep ישיר על `origin/main`) — סעיף 8 עבר מ-`PLANNING APPROVED BY OWNER`
ל-✅ מוזג. **Phase 1 implementation נפתח כ-PR נפרד** (PR #490, עדיין לא מוזג):
`consumption_checklist()` וסעיף `## Consumption Checklist` חדש בכל bundle (5.1) — **תוכן
ה-bundle, לא flag-gated: מתווסף לכל build קיים, לא "opt-in"** (ניסוח מוקדם ב-PR body תוקן);
ולידציה מלאה ל-Consumption Ledger ופונקציית `verify_consumption()` (5.2/5.3); תת-פקודת CLI
חדשה, opt-in, `verify-consumption`; שדה אופציונלי, backward-compatible
`required_for_conclusion` על `bounded_local_expansions` (5.5). **סקירה עצמאית על הענף לפני
מיזוג** מצאה 4 פערים ממשיים ב-`verify_consumption()` המקורי ותוקנו באותו PR: (1) `path` של
receipt/waiver לא נבדק מול ה-`item_id` בפועל — אפשר היה לטעון "נבדק" תוך הפניה לקובץ אחר
לגמרי; (2) `production_claim` לא היה חלק מזהות ה-ledger — ledger שנוצר עבור production claim
יכול היה לעבור בלי `--production-claim` ולדלג בשקט על evidence; (3) `required_sources`
ב-ledger לא הושווה לעולם ל-checklist המחושב בפועל; (4) item_id לא-מוכר/כפול (כולל receipt+waiver
לאותו item) התקבלו בלי בדיקת קונפליקט. גם תוקן: `reason`/`evidence_reference` לא-string (למשל
list) היה גורם ל-`TypeError` לא-מטופל במקום כשל-סגור. 35 בדיקות רגרסיה חדשות (112/112
עוברות, `validate`/`smoke_tests.py` נקיים). הסעיף החדש הגדיל את גודל ה-bundle במידה שחייבה
עדכון `maximum_approximate_token_budget` בחמישה profiles (`approval_ux`, `tool_execution`,
`turn_coordinator_routing`, `ux_f52_message`, `cross_layer_architecture`) — שינוי נתוני-profile
בלבד, לא שינוי סכימה. **Phase 3 (CI blocking gate + hard-must ב-`AGENT_CONSUMPTION_CONTRACT.md`)
לא מיושם כאן** — לפי התכנית עצמה (סעיף 8, שלב Phase 3) הוא ממתין לשימוש ראשון אמיתי ב-Phase 1,
ולא נפתח כאן. ראה N17 למטה, סעיפים 8/10.
עודכן: 28/07/2026 — **N17 עדכון: Consumption Enforcement — `STATUS: PLANNING APPROVED
BY OWNER` (סעיף 8), אין implementation, אין שינוי runtime.** נכתב על `origin/main` לאחר
PR #485+#487+#489. מטרה: איך למנוע מצב שבו מקור חובה כבר ב-bundle אך הסוכן מגיע למסקנה
בלי לפתוח אותו — בדיוק הפער ש-PR #487 מצא. ראה
`docs/context_librarian/CONSUMPTION_ENFORCEMENT_PLAN.md` לפירוט מלא — כולל Cross-Layer
Impact Matrix (ללא cross-layer risk) והחלטות owner מלאות: מודל שכבתי (self-attested ledger
לכל משימה + independent review חובה על production claim/Cross-Layer/waiver כלשהו); כל
waiver דורש independent reviewer approval ופג-תוקף בשינוי commit/profile/query; ה-ledger
disposable מקומית ומועלה כ-CI artifact (לא committed); Option C (harness-level tracking)
נדחה לפרופוזל נפרד. **אין תיקון ל-BUG-130/BUG-140/BUG-150/fail-open; אין ריצה חוזרת של
הפיילוט. אין לפתוח PR implementation לפני שה-PR המתוקן הזה עצמו נסקר ומוזג** — תנאי מפורש
מהמשתמש.
עודכן: 28/07/2026 — **N17 Context Librarian remediation — ✅ מוזג ל-`main`** (PR #489,
ענף `codex/context-librarian-audit-remediation`, מיזוג `20914f2`): cross-platform
bounded-local-expansion path validation מטפל עכשיו עקבית בנתיבי POSIX ו-Windows מוחלטים
ושומר נתיבים יחסיים תקינים; `FEATURE_AUTO_CAPTURE` ממופה ב-`layer.turn_coordinator` עם
code reference ו-evidence scope; provenance מבחין בין `on_main_history` ל-
`at_origin_main_tip` תוך שמירת ה-alias התואם-לאחור `on_main`. בדיקות ה-provenance
משתמשות רק ב-`origin/main` המקומי (ללא fetch אוטומטי); היעדר `origin/main` מחזיר
`unknown` וה-assertion המתאים נכשל-סגור. **Codex הסיר בעצמו את
`SOURCE_CONSUMPTION_GATE_PLAN.md` (הצעת-תכנון מקבילה) לפני המיזוג**, ונדחה במפורש
ל-`#488` כמסמך-תכנון הקנוני היחיד — ללא כפילות.
עודכן: 28/07/2026 — **N17 עדכון: rerun ממוקד — האם התיקונים סגרו את 4 הכשלים שהפיילוט
מצא?** (על `origin/main` ב-`ffde1d6`, אחרי PR #485+#486; לא ריצה חוזרת של הפיילוט — אין
Gold Set חדש, אין blind review). לכל אחת מ-4 המשימות (לא `tool_execution` — PASS נקי):
נבנה bundle טרי, ונבדק ב-grep ישיר על הפלט האם התוכן החסר שהממצא ציין קיים עכשיו בפועל.
**תוצאה: 2/4 סגורים structurally** (לא תלוי-משקיע) — `turn_coordinator_routing`'s BUG-140
(מאומת: טקסט האירוע המלא, כולל `recLwJhPNh4EDbw56`/"דנה כהן", משוקע ב-bundle תמיד) ו-
`rp5_evidence_mismatch`'s Critical mislabeling (מאומת דו-כיווני: `--assert-main` על `main`
אמיתי → הצליח, `on_main: yes`; על commit סינתטי על branch לא-ממוזג → נכשל-סגור, exit 2).
**2/4 תוקנו חלקית בלבד** — ב-`approval_ux` וב-`core_reasoning_change`, רוב הפריטים
שהחקירה החמיצה כבר היו קיימים ב-bundle *לפני* PR #485 (למשל `core/leads_reasoning_projection.py`,
`tma_api.py`, `FEATURE_CORE_REASONING_LEADS_STATE` — כולם כבר שם); הפער האמיתי היחיד היה
`core/adapters/decision_adapter.py` (עכשיו תוקן) ב-`core_reasoning_change`, ותיעוד
parallel-sources-of-truth (עכשיו תוקן) ב-`approval_ux` — אבל הגורם-שורש הדומיננטי בשניהם
היה משמעת-קריאה של החקירה, לא כיסוי-קטלוג, ותיקון-קטלוג לא יכול לאכוף קריאה. שני פערים
קטנים יותר אושרו כפתוחים ומחוץ לסקופ PR #485 במכוון: `FEATURE_AUTO_CAPTURE` עדיין חסר
מ-Feature Flags של `turn_coordinator`; שכבת ה-evidence-shadow השלישית ב-rp5 מעולם לא הייתה
פער-קטלוג (הקובץ וה-flag כבר היו רשומים תחת `required_dependency_layers`). **קביעה: Phase 1
non-inferiority עדיין לא מבוסס** — וה-rerun הזה לא נועד לבסס אותו; זה דורש ריצה מלאה מחדש
של הפיילוט (Gold Sets עצמאיים טריים + blind review). פירוט מלא ב-
`docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md`, סעיף "2026-07-28 targeted rerun".
עודכן: 28/07/2026 — **N17 עדכון: Context Librarian Pilot Findings Remediation — ✅ PR #485
מוזג ל-`main`** (merge `4e12bf5`, ענף `claude/librarian-pilot-remediation`). אומת ישירות:
נבדק checkout נקי של `origin/main` ב-`4e12bf5` — `python -m tools.context_librarian
validate` (14 nodes, 24 edges, 7 profiles) ו-`pytest test_context_librarian.py` (62/62)
ירוקים על ה-commit הזה עצמו, לא רק לפי מטא-דאטה של ה-merge. מיישם ישירות תיקון לארבעה
מתוך חמשת ה-gaps שהפיילוט (28/07, ראו למטה) מצא בספרן עצמו — לא בבאגי runtime שהפיילוט
חשף: (1) `core_reasoning_change` כולל עכשיו את `core/adapters/decision_adapter.py` (המודול
החי במקום `decision_orchestrator.py` שכבר לא קיים) והערה על `tma_api.py` כצד-כתיבה; (2)
`approval_ux` מתעד עכשיו את 4 מנגנוני האישור המקבילים (`ActionContract`,
`event_bus.PendingActionsStore`, `app.py._pending_approvals`, TMA Approvals) עם קבצים/TTL
מדויקים; (3) פיצ'ר חדש `bounded_local_expansions` — חלון-הקשר קבוע-גודל, מוגדר-פרופיל, לא
query-driven — גורם ל-`turn_coordinator_routing` bundle לכלול תמיד את BUG-140 יחד עם
BUG-130; (4) `## Bundle Provenance` חדש בכל bundle מדווח `generated_commit`/
`generated_branch`/`on_main` בפועל (במקום שמישהו יצטרך לנחש), ו-`--assert-main` חדש נכשל-
סגור אם commit לא מוכח כ-ancestor של `main` — מטפל ישירות בטעות ה-Critical של הפיילוט
(bundle מענף לא-ממוזג תואר כ-`main`). תוך כדי נמצא ויושם תיקון גם לבאג נפרד ומהותי יותר:
`_render()` הציג רק `notes[0]` של כל node, כל ההערות הנוספות (עד 9 ב-`layer.approvals`)
מעולם לא הופיעו באף bundle שנבנה אי-פעם — יושם תיקון לכל ה-notes, עם regression test ייעודי.
סעיף 6 בסקופ המקורי (BUG-140/BUG-150/fail-open ב-ActionGateway) **לא נגע ולא יושם** ב-PR
הזה — עדיין חסום ע"י `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`, לפי אותה החלטה כמו בפיילוט
עצמו. 17 בדיקות regression חדשות (כולל ארבע שנוספו בעקבות ביקורת CodeRabbit — notes[1:] ייעודי,
path traversal, absolute path, malformed entry), `test_context_librarian.py` המלא
(62 בדיקות) ירוק, כל 7 ה-profiles נבנים בהצלחה ודטרמיניסטית — אומת ישירות על `main` לאחר
המיזוג (`4e12bf5`), לא רק על ענף ה-PR.
עודכן: 28/07/2026 — **N17 עדכון: non-inferiority pilot advancement (סעיף 5) מוזג ל-`main`**
(PR #483, ענף `claude/context-librarian-non-inferiority-pilot`, merge `51d370b`). אומת ב-grep
ישירות על `origin/main`: `docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md`'s
"2026-07-28 non-inferiority pilot advancement" section, וארבעת ה-catalog nodes
(`approvals`/`turn_coordinator`/`ux_f52`/`rp5`) עם `last_verified_commit: ffa678a7` — קיימים
בפועל ב-`main`. **התקדמות ממשית, לא acceptance** — 1/5 PASS נקי, 4/5 עם ממצאי גילוי-חסר עד
Critical. אין implementation לשלושת הבאגים האמיתיים שנחשפו (BUG-150, fail-open ב-ActionGateway,
BUG-130/140) — חסומים ע"י CROSS_LAYER_AUTHORITY_CONTRACT_V1.md. ראה N17 למטה לפירוט.**
עודכן: 28/07/2026 — **N17 עדכון: Verification Coverage Model plan (חצי מסעיף 6, תכנון בלבד)
מוזג ל-`main`** (PR #482, ענף `claude/context-librarian-vcm-plan`, merge `ffa678a`). אומת
ב-grep: `docs/context_librarian/VERIFICATION_COVERAGE_MODEL_PLAN.md` קיים ב-`origin/main`.
ראה N17 למטה לפירוט. אין implementation, אין nodes חדשים.**
עודכן: 28/07/2026 — **N17 עדכון: Librarian Hardening PR (סעיפים 1-3 + CI validation, סדר
עבודה מחייב שלב 4) מוזג ל-`main` (PR #481, ענף `claude/context-librarian-hardening-n17`).
אומת ב-grep ישירות על `origin/main`: `.json` catalog (10 קבצים), `_load_catalog_json`,
`_approximate_char_estimate`, `_CHARS_PER_APPROXIMATE_TOKEN`, ושלושת ה-CI steps
(`fetch-depth: 0`, `persist-credentials: false`, `pytest context librarian`) — כולם קיימים
בפועל. **אין אימות production/staging** (dev tooling בלבד, לא רלוונטי). ראה N17 למטה
לפירוט מלא.**
עודכן: 27/07/2026 — **N17 נוסף: Context Librarian Follow-up Hardening & Verification Backlog (6 נקודות המשך + סדר עבודה מחייב), בעקבות PR #475 (Re-verification Alignment, `89e2b4e`, ראה למטה). אין ליישום עדיין.** עדכון PR #471 הקודם נשמר בהמשך.

**Context Librarian Re-verification Alignment — PR #475 (`e4d29d0`+`34e31a4`, merge `89e2b4e`):** תיעוד/מטא-דאטה בלבד, ללא שינוי runtime. יישר את ארבעת ה-context-librarian nodes (`approvals`, `turn_coordinator`, `ux_f52`, `rp5`) מול PR #471 — נוסף `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` לארבעתם, תועדו ה-callback עם `contract_id`, BUG-144 reject, ה-Gateway reply-ownership handoff המותנה, ו-RP5 שממשיך לרוץ במסלול ה-Gateway-owned. `task_profiles/profiles.yaml`'s `turn_coordinator_routing` כבר לא חוסם rp5 באופן גורף. תוקן assertion ישן ב-`test_phase_4b_1b_durable_lifecycle.py` (נוסח ✅ הישן). נוספו erratum notes ל-5 מסמכים קנוניים + רשומת `DECISION_LOG.md` D-011 (מתעדת שנוצר renderer מקביל, `ApprovalLifecycleResult`, במקום הרחבת `compose_status_reply()` לפי D-010 — ממצא פתוח, לא תוקן). `last_verified_commit` רוענן ל-`a885561d` רק אחרי ש-30/30 test_paths עברו, `validate`/`test_context_librarian.py` נקיים, וחמשת ה-pilot bundles נבנו פעמיים כל אחד (STOP→PROCEED, hash דטרמיניסטי). Post-merge verification בוצע ישירות על `main` (`89e2b4e`) — כל הסמלים אומתו ב-grep, כל חמשת ה-pilot bundles PROCEED. **אין אימות production/staging.** ראו N17 למטה להמשך המחייב.

**Single-Speaker Approval UX Base — PR #471 (`5e2c244` + תיקון CI `dadf851`, merge `c64da20`):** נוסף `ApprovalLifecycleResult` כתוצאת UX קנונית למחזור חיי אישור; Gateway הוא בעל התשובה במסלולי approval כשהדגל מופעל, וה-Agent נעצר אחרי בחירת בעלות Gateway. Telegram ו-WhatsApp ממפים אותו lifecycle state לאותה משמעות. callback approve/reject, דחייה טקסטואלית, repeated completion/rejection, pending/no-pending ו-cross-chat delivery מכוסים ברגרסיות. BUG-144 (callback reject לא סגר את `ActionContract`) ו-BUG-145 (שתי הודעות סופיות לאותו callback) מיושמים וממוזגים; BUG-118 נסגר ברמת הקוד באמצעות redaction בלתי-מותנה של `tool_name`, UUID/contract ID, ActionContract record ID ו-business record ID. `ActionContracts` נשאר מקור האמת היחיד; לא נוסף state ל-Sessions או store חלופי. `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false` בקוד וב-`.env.example`; staging/production דורשים הפעלה מפורשת לאחר acceptance. payload ה-callback הארוך ביותר שנבדק הוא 53 bytes מתוך מגבלת Telegram של 64, ללא truncation. CI לאחר תיקון סמכות-אישור: `backend-ci` ו-`frontend-ci` עברו. **סטטוס אמת:** ממוזג ונבדק ב-CI, טרם אומת ב-staging/production; אין לסמן Production Verified. **נדחה במפורש:** deterministic approval cost cuts, per-turn counters, queue redesign, Sessions/Business Memory, RP5, CETERRA, durable memory ו-full formatter migration.

עודכן קודם: 21/07/2026 — **PATCH 3B הושלם: Steps 5, 5.1, 6 + prerequisite ממוזגים ל-main, ✅ Production Verified אמיתי (לא רק tests); TMA frontend fix ממתין למיזוג.** בהמשך ישיר ל-Steps 2–4 (למטה) — הבעלים אישר כל שלב בנפרד, כולל דחיית PR #427 הראשון עם 3 blockers ספציפיים לפני שאושר סופית.

**Step 5 — `app.py` bootstrap/injection (PR #427, merge commit `7765a46`):** `core/emergency_stop_bootstrap.py` חדש — `bootstrap_emergency_stop()` בונה `AirtableEmergencyStopStore`+`EmergencyStopManager`, מזריק דרך `configure_emergency_stop_manager()`, ומבצע hydration סינכרוני אחד. **תוקנו 3 blockers שהבעלים דחה בסבב הראשון:** (1) `import app` בפועל ביצע קריאת Airtable אמיתית — תוקן ע"י `gunicorn.conf.py` חדש (`post_worker_init`) + `app.run_startup_sequence()` מפורש, מאומת ב-subprocess שחוסם `httpx` גלובלית. (2) סדר bootstrap-לפני-scheduler לא היה מובטח מבנית — תוקן ל-`run_startup_sequence()` יחיד עם סדר קריאה טעון-משמעות. (3) הכלה רחבה מדי של exceptions — הוסרו כל ה-catch-all-ים; רק `unavailable`/`invalid` (תוצאות מתועדות) לא זורקים, כל שגיאה בלתי-צפויה מתפשטת וחוסמת את ה-scheduler. **Step 5.1 (P0, אותו PR):** `gunicorn.conf.py` ננעל ל-`workers=1` (scheduler הוא in-process state, יותר מ-worker אחד = N שכפולים) — אומת אמפירית (הרצת `workers=3` אמיתית, ראה שלוש worker processes, revert). `_require_valid_store_status()` הופך `store_status` בלתי-צפוי (או `None`) ל-`RuntimeError` במקום המשך שקט. 38+24+12 טסטים.

**Prerequisite לפני Step 6 (PR #432, merge commit ב-`main`):** בזמן אימות Step 5 התגלה שבאג test-isolation אמיתי (`test_emergency_stop_bootstrap.py` — assertions שרצו מחוץ ל-`with patch(...)`) גרם ל-CI לגעת בטבלת `Emergency Stop Flags` **החיה** בפועל (קריאה בלבד, לא כתיבה) כי unit CI החזיק `AIRTABLE_API_KEY`/`AIRTABLE_BASE_ID` אמיתיים. תוקן: `ci.yml` עכשיו עם מפתחות מזויפים קבועים + חסימת `/etc/hosts` ל-`api.airtable.com` (defense-in-depth) + `test_ci_no_airtable_secrets.py` structural.

**Step 6 — atomic cutover (PR #433, merge commit `e6922e2`):** `is_enabled()`/`set_flag()` מיירטים עכשיו את 5 השמות הקנוניים — `is_enabled()` מפנה ל-`evaluate_emergency_stop()` (fail-closed ל-`True` אם המנג'ר לא מוגדר), `set_flag()` זורק `EmergencyStopLegacyWriteBlocked`. מנגנון `/tmp/emergency_flags.json` **הוסר לחלוטין**. `_env_force_stop_provider()` חדש (קורא `os.environ` ישירות, לא `is_enabled()`, רק `"true"` כופה). `cost_monitor.py` עבר ל-`set_emergency_stop(source="cost_watchdog")` עם retry-on-failed-write. `tma_api.py`: `GET /api/health` מחזיר `{enabled, operation_id}` לכל אחד מ-5 הדגלים (לא רק 4); `POST /api/health/emergency` (stop, `source="tma_owner_stop"`) ו-`POST /api/health/emergency/clear` חדש (`source="tma_owner_clear"`, דורש `expected_operation_id`, 409 על stale, מוצלח רק ב-`ok+verified`). 60+ טסטים חדשים (`test_feature_flags_cutover.py`) + 15 קבצי test קיימים תוקנו לברירת-מחדל fail-closed החדשה. **✅ Production Verified ע"י הבעלים ישירות (לא רק tests):** `stop_email` דרך ה-TMA → נשאר פעיל אחרי **restart אמיתי של Render** (מוכיח שה-durable persistence עובד, לא רק ה-in-memory הישן) → `clear` עם `operation_id` נכון → הצליח, TMA חזר ל"כל המערכות תקינות". Bootstrap log אישר סדר: hydration→5 flags→scheduler.

**TMA frontend fix (PR #436, ✅ ממוזג ל-main):** `SystemHealth.tsx` — כפתור Stop AI, כפתור Clear לכל דגל פעיל (קורא `operation_id` מ-`GET /api/health`, שולח `expected_operation_id`), טיפול ב-409 (רענון + הודעה), הסרת הטקסט השגוי "לביטול: הפעל מחדש את השרת" (restart לא מבטל דגל durable). אומת תחילה בדפדפן מקומי (Playwright/Chromium מול backend מזויף), ואז **ישירות בפרודקשן ע"י הבעלים** (21/07/2026, תמונות מסך): `stop_email` → "🚨 חירום פעיל" עם כפתור "✅ בטל עצירת Email" → לחיצה → "✅ כל המערכות תקינות". **עדכון (21/07/2026, אחרי המיזוג):** הבעלים אישר בפירוש, **עם ראיה ישירה** (פלט אמיתי של הודעות `_notify_owner()` מ-Telegram production עבור AI/Automation/WhatsApp/ALL, תואם מילה-במילה לתבנית ב-`tma_api.py`, כולל `על ידי: אליהו חזן`), שכל 5 כפתורי ה-Stop **וה-Clear המתאימים להם** נבדקו ועובדים בפרודקשן החי, **כולל Stop All** (לא רק ה-4 הצרים). זה סוגר את בדיקת-ההשלמה השנייה שנותרה פתוחה מ-C161 (ש-Stop All בכלל עובד כ-UI round-trip) — עם ראיית לוג אמיתית, לא רק אישור מילולי. ראה `CHANGE_CONTROL_LOG.md` C162 לפלט המלא. **נשאר לא מאומת במפורש** (שונה מ"הכפתור פועל"): (א) תרחיש 409 עם `operation_id` שגוי/מיושן בפרודקשן החי עצמו (אומת רק ב-backend מקומי מדומה, ראה C162) — לא בוצע ע"י הבעלים; (ב) שניסיון פעולה guarded אמיתית (למשל שליחת מייל אמיתית) אכן נחסם **בזמן ש-Stop All פעיל** — "הכפתור עובד" מוכיח round-trip UI, לא בהכרח שנוסתה פעולה guarded אמיתית מול ה-dispatcher באותו חלון.

ראה `CHANGE_CONTROL_LOG.md` C159–C162 לפירוט מלא לכל שלב.

עודכן קודם: 21/07/2026 — **PATCH 3B Steps 2–4 ממוזגים ל-main (PR #425, `3ce949e`) + ✅ Production Verified אמיתי (לא רק tests).** הבעלים יצר ידנית את הטבלה `Emergency Stop Flags` ב-Airtable החי (`app4bcgoX7t0HUVnm`) עם 7 השדות הנדרשים, זרע חמש הרשומות (`EMERGENCY_STOP_ALL`/`WHATSAPP`/`EMAIL`/`AUTOMATION`/`AI`, כולן `Enabled=false` — תואם למצב production תצפיתי: אין אף env var פעיל ב-Render), ואז הריץ בעצמו על שירות ה-Render החי (לא מקומית, לא mock) גם `python -m core.emergency_stop_preflight` וגם `python -m core.predeploy` — שניהם `exit 0`, כולל שתי קריאות Airtable אמיתיות (`200 OK`) וריצה מוצלחת של `core.database_migrations` הקיים (מוכיח ש-`python -m core.database_migrations` לא שינה סמנטיקה). **שלושת התנאים המוקדמים להחלפת Render Pre-Deploy Command מולאו** (טבלה + זריעה + הרצה ידנית מוצלחת) — ההחלפה עצמה (Render dashboard, מחוץ לריפו) עדיין לא בוצעה, ממתינה להחלטת/פעולת הבעלים. הקוד עצמו נשאר **inert** — `configure_emergency_stop_manager()` עדיין ללא production caller, `app.py`/`scheduler.py`/`tma_api.py`/`cost_monitor.py` לא נגעו (Step 5, טרם בוצע). ראה `CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` C156 לפלט הריצה המלא.
עודכן קודם: 21/07/2026 — **N16: תיקון ליקוי ארכיטקטוני ב-N12 — Git Audit הופרד לחלוטין מהבוט העסקי.** N12 (PR #108, `c26c5e1`) חיבר את `daily_git_audit.py` (כלי GOV-02) ל-`scheduler.py` של **הבוט העסקי** (`_job_daily_git_audit`, ריצה יומית ב-06:45) והעניק לו שליחה ישירה דרך `TELEGRAM_TOKEN`/`ELIYAHU_CHAT_ID` של הבוט עצמו — כלומר תהליך ה-Python של הבוט ב-Render קרא Git מהעותק הפרוס אליו ושלח את התוצאה בטלגרם, על אף שהבוט העסקי לא אמור להיות קשור לריפו בכלל. זו לא הייתה בעיית ניסוח/הודעה דומה — זו כפילות ארכיטקטונית אמיתית מול Claude Code Routine נפרד שכבר קיים לאותה מטרה בדיוק (audit קריאת-ריפו + התראה, ראה טריגר "Road map false positive check"). **החלטת בעלים (21/07/2026):** git audit הוא אחריות בלעדית של ה-Routine; הבוט העסקי ממשיך לשלוח רק digest והתראות עסקיות. **תוקן:** (1) `_job_daily_git_audit`/`git_audit_time`/הרשמת ה-schedule **הוסרו לגמרי** מ-`scheduler.py` (לא רק flag-gated — היה כבר `GIT_AUDIT_SCHEDULER` כבוי כברירת מחדל, וההודעה בכל זאת נשלחה, כלומר הדגל הודלק בפועל או שהסקריפט הורץ ידנית בסביבה עם פרטי הטלגרם). (2) `daily_git_audit.py`'s `_send_telegram()` הוסרה כליל (שני call sites — GOV-02 abort ודוח סופי) — הקובץ מדפיס ל-stdout בלבד, אפס תלות ב-`TELEGRAM_TOKEN`/`telebot`. (3) דגל `GIT_AUDIT_SCHEDULER` הוסר מ-`feature_flags.py` (0 call sites נותרו) ומ-`.env.example` (`GIT_AUDIT_TIME`). GOV-02 (`audit_truth_gate.py`) עצמו **לא נגע** — נשאר read-only tool בריפו, זמין ל-Routine להריץ ישירות. ראה N12 למטה (עדכון), `CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` C155. **✅ ממוזג ל-`main`** (PR #424, commit `99981fb`).
עודכן קודם: 20/07/2026 — **Truth Reset: אימות ישיר מול `origin/main` לכל פריט בתכנית העבודה — נמצאו 6 פריטים נוספים שה-BUG_AUDIT_LOG/ROADMAP טענו "לא ממוזג" עליהם, כשבפועל כבר ממוזגים ופעילים.** בעקבות דרישת הבעלים לתקן את התכנית עצמה לפי git reality לפני שמתחילים לבצע — כל פריט בתכנית נבדק בפועל (`git merge-base`, grep על `origin/main`, הרצת הטסט הרלוונטי), לא לפי מה שהתיעוד טוען. **ממצאים:** (1) **BUG-072** (לוגים חושפים sender ID/טלפון) — כבר merged, 7/7 טסטים עוברים, נותרה רק production verification, בדיוק כפי שנטען. (2) **BUG-058** (Tier-2 batch resolver) — **כבר merged ופעיל ללא flag gate**, אף תועד כ-production-verified ב-10/07/2026 עם ראיית לוג אמיתית — השורה "Merged: ממתין ל-push/PR" בקובץ הייתה עצמה stale; **אין כאן "עבודה חדשה", זה סגור לגמרי**. (3) **BUG-071** (WhatsApp attachments) — **כבר merged** (הקבצים עברו מ-`providers/` לשורש ב-commit נפרד, `76128ba`), 6/6 טסטים עוברים; הרשומה טענה "Merged: לא עדיין" בטעות. (4) **BUG-BATCH-DISCARD** — **כבר merged** (`ba579f2`, 17/07), 33/33 טסטים עוברים; גם כלל שורת "סטטוס" שגויה/לא-קשורה שהוסרה. (5) **BUG-007** (CORS preflight) — **כבר merged**, אומת עם Flask test client אמיתי (204 על כל 4 הנתיבים). (6) **BUG-049** (CI silent-pass) — **כבר merged**, 6/6 עובר בפועל. בנוסף: תוקן פריט drift נוסף (כפילות של אותה טעות `/status` decorator בטבלת "פערים ידועים" השנייה), ותוקנה תווית "חסום על C81-FU–C83" ב-**C87** — שלושתם כבר סגורים, C87 לא-חסום יותר. **המשמעות לתכנית:** יום 2 (merge קוד קיים) כמעט ריק — כל 6 הפריטים שסומנו "לא-ממוזג" כבר ב-`main`; מה שנותר הוא production verification בלבד, לא merge. תכנית מתוקנת מלאה + patch-stack לפי workstreams במקום ימים — ראה תגובת הסשן/הודעת commit לפירוט.
עודכן קודם: 20/07/2026 — **Post-N15 Work Survey: דוח מלא + 3 תיקוני drift ב-ROADMAP עצמו.** לקראת תכנית עבודה למספר ימים נוספים (הכל מחוץ ל-RP5/F52/FEATURE_ACTION_GATEWAY/כל דבר חסום אחר), 4 סוכני חקירה מקבילים סרקו את ROADMAP.md, BUG_AUDIT_LOG.md, feature_flags.py, וחוב טכני/governance drift כללי. הדוח המלא (לא מקוצר) נשמר ב-`docs/audit/POST_N15_WORK_SURVEY_20260720.md`. **תוך כדי הסקירה נמצאו 3 פריטים ב-ROADMAP עצמו שהתבררו כ-stale** (הקובץ טוען דבר-אחד, המציאות אחר) — תוקנו: (1) **C84** סומן "טרם ממוזג" — בפועל כבר merged (`c5c5a97`, PR #408), אומת קודם השבוע. (2) **C86** סומן "planned, not started" — בפועל `test_c86_scheduler_emergency_matrix.py` כבר קיים ועובר, תועד כבר בעדכון C82-FU (19/07) בקובץ הזה עצמו, סתירה פנימית. (3) טבלת "Known Issues" טענה ש-`/status` decorator הוסר ב-PR #55 — בפועל קיים ורשום (`app.py:401`), תואם ל-BUG-005 שכבר סגור; עבדנו על `/status` ישירות השבוע (BUG-120/BUG-121). שלושתם תוקנו בגוף הקובץ. ראה הדוח המלא לרשימת כל הפריטים הפתוחים (ROADMAP/BUGs/flags/tech-debt) והתכנית המוצעת ל-5 ימים.
עודכן קודם: 20/07/2026 — **Day-3 flag pre-activation prep: FEATURE_WEEKLY_SUMMARY בדיקה תוקנה + FEATURE_LAST_TOOL_RESULT_SHADOW קיבל בדיקות.** (1) `weekly_summary.py::_group_by_domain()` קיבץ לפי `Tags[0]` — אבל `cmd_update.py` לעולם לא כותב domain ל-Tags, רק לשדה `Domain` הייעודי ("Real Estate" וכו') — כל רשומה קובצה בשקט לא-נכון. תוקן + `test_weekly_summary_domain_grouping.py` (11 בדיקות). (2) `FEATURE_LAST_TOOL_RESULT_SHADOW` לא היה לו קובץ test ייעודי — נוסף `test_last_tool_result_shadow.py` (23 בדיקות) המכסה את שלוש נקודות הקריאה האמיתיות; תפס באג-אבחון זעיר ב-`core/output_gateway.py::_shadow_record_send()` (enum שיבוץ שגוי במחרוזת לוג, תוקן). שני הפריטים האלה היו תנאי-סף מוצהר לפני הפעלת הדגלים — עכשיו מוכנים. פריטים 7-9 (`FEATURE_CORE_REASONING_LEADS_STATE`/`GIT_AUDIT_SCHEDULER`/`FEATURE_TOOL_AVAILABILITY_FILTER`) קוד מוכן, ההפעלה עצמה דורשת שינוי env var ב-Render — להחלטת/ביצוע הבעלים. ראה `CHANGE_CONTROL_LOG.md` C149 (branch `claude/n15-owner-decision-p73c3k`, commit `23c1a35`, **טרם ממוזג ל-main**).
עודכן קודם: 20/07/2026 — **BUG-110 residual תוקן: read-side stale `status=="converted"` ב-`ad_attribution.py`/`audience_intelligence.py`.** BUG-110 (17/07/2026) תיקן את שני אתרי הכתיבה אבל השאיר במפורש כחוב טכני שני צרכני-קריאה שהמשיכו לבדוק את הליטרל הישן `status=="converted"` — `ad_attribution.py::build_attribution_report()` ו-`audience_intelligence.py::_parse_records()` — כך שלידים שהומרו **אחרי** התיקון (status="done"+Business Outcome="converted ") הוחסרו בשקט מדוחות attribution/segmentation. תוקן: שני הצרכנים בודקים עכשיו גם `Business Outcome == LeadOutcome.CONVERTED` (קבוע קנוני, לא ליטרל) לצד הבדיקה הישנה — OR, לא replace, אין backfill. `mark_converted()`'s gateway migration (חוב טכני נפרד מ-BUG-110) נשאר בכוונה לא-נוגע. Full `test_*.py` sweep + `smoke_tests.py` + `compileall` נקיים. ראה `BUG_AUDIT_LOG.md` BUG-110 ו-`CHANGE_CONTROL_LOG.md` C148 (branch `claude/n15-owner-decision-p73c3k`, commit `e6efa3a`, **טרם ממוזג ל-main**).
עודכן קודם: 19/07/2026 — **C81-FU ו-C82-FU נסגרים (docs-only audit): שניהם כבר פתורים בקוד, ה-🔴 דחוף היה stale.** אומת ישירות מול `main` `c5c5a97` (לא זיכרון/תיעוד ישן): (1) **C81-FU** — `tools/approval_actions.py::send_recovery()` (C53 FIX-1) כבר דורש `owner_delivery.delivery_success` לפני `ok=True`, ו-`recovery_count` אינו נכתב כלל בנתיב הזה (בניגוד מכוון ל-`send_followup()` שכן מעדכן `followup_count`) — הבעיה המתוארת ("recovery_count גדל גם כשהלקוח לא קיבל") כבר לא קיימת. `test_c81_recovery_truth.py` (4 בדיקות) מאמת את זה — **אך נמצא שהקובץ חסר בלוק `if __name__ == "__main__":`**, אז `python3 test_c81_recovery_truth.py` (הקונבנציה של הריפו) הריץ בפועל **0 assertions** בשקט (אותה משפחת באג כמו BUG-049/CI-SILENT-PASS-DOCUMENT-CONVERTER, קובץ אחר). תוקן עם אותו pattern בדיוק; 4/4 רצות בפועל עכשיו. (2) **C82-FU** — `scheduler.py`'s `_automation_guard()` עוטף היום את **כל** רישום `.do(...)` (אומת עם grep שלילי — 0 שורות `.do(` בלי העטיפה), לא רק followup/payment reminders כפי שהבעיה המקורית תיארה. `test_c86_scheduler_emergency_matrix.py` (כולל `test_emergency_stop_matrix_blocks_every_registered_scheduler_job`) כבר מכסה את זה ורץ תקין (יש לו `__main__`). ראה `CHANGE_CONTROL_LOG.md` C144 (branch `claude/c81-c82-roadmap-docs-cleanup`, טרם ממוזג).
עודכן קודם: 19/07/2026 — **C84 (TMA Approvals TTL) מיושם, tests ירוקים, טרם ממוזג ל-main (branch `claude/c84-tma-approval-ttl`):** `tma_api.py`'s `_claim_and_execute_approval()` — הנקודה היחידה ש-`act_on_approval()` וגם `bulk_approve()` עוברים דרכה לביצוע — אוכפת עכשיו freshness check לפני `ActionGateway.approve()`: contract עם `created_at` ישן מ-`_TMA_APPROVAL_TTL_SECONDS` (24 שעות) נדחה (`reject()`, מאומת, לא מונח כמובן מאליו — אותו עיקרון כמו `_reject_stale_telegram_approval()` ב-BUG-112) במקום להתבצע, ומחזיר `ok=False status_code=410`. `created_at` חסר/לא-תקין נכשל closed (מטופל כ-פג-תוקף, לא כ-טרי — בכוונה ההפך מבחירת BUG-112 בטלגרם). **סטיה מכוונת מהצעת ה-ROADMAP המקורית** (`expires_at` שדה חדש על רשומת Approvals): נעשה שימוש ב-`ActionContract.created_at` הקיים במקום — Approvals מתועד כ-"non-authoritative TMA display projection" (`ApprovalsFields` docstring), אז ה-contract הקנוני הוא מקור האמת ל"כמה זמן זה באמת", לא שדה חדש שדורש יצירה ידנית ב-Airtable + resync של `schema_cache.json`. 44 בדיקות חדשות (`test_c84_tma_approval_ttl.py`) + 3 קבצי test קיימים עודכנו (`test_approval_concurrency.py`/`test_phase_4b2_wiring.py`/`test_pr0c0_tma_approval_truthfulness.py`) כדי ש-`_FakeContract`'s test doubles יכללו `created_at` (ברירת מחדל "עכשיו" — משמר את כל ההתנהגות הקיימת ללא שינוי). Full sweep + smoke + compileall נקיים. ראה `CHANGE_CONTROL_LOG.md` C143. **branch זה מכיל C84 בלבד** — RP5 staging fault injection הופרד ל-branch נפרד, `claude/rp5-staging-fault-injection-v4akit`.
עודכן קודם: 19/07/2026 — **PR #405 מוזג ל-main; BUG-117 VERIFIED IN PROD / CLOSED — BUG-115/BUG-116/BUG-117 כולם סגורים:** PR #405 מוזג (`main` `4546880`). דגימת production ישירה: batch dictation ("צור לידים חדשים ענף גיוס... בניימין אסולין... אהרון שמחה") נכנס עם `[TurnEnvelope] case_c_signal kind=C1 detail=live_contracts=9` (9 contracts ישנים pending), תצוגת batch הוצגה נכון ("📋 זיהיתי 2 לידים אפשריים בקבוצה..."), ואחרי "כן" שני הלידים אושרו ונכתבו בפועל: `✅ שמרתי את בניימין אסולין (0533123482) | recoLSXsLQNKQG6Gy`, `✅ שמרתי את אהרון שמחה (0548421060) | recgwDYidGrTc9KEU` — ללא תפריט disambiguation. **BUG-117 עכשיו ✅ VERIFIED IN PROD / CLOSED.** הערת דיוק: שורת `live_contracts=9` נלכדה ל-turn של ה-batch dictation עצמו, לא ל-turn של "כן" בפני עצמו — נחשב מספיק כי תצוגת batch (Tier-2) לא יוצרת/מסירה ActionContracts, אין סיבה טכנית למספר להשתנות בין שתי הודעות רצופות באותה שיחה. **סיכום סבב BUG-114→BUG-117:** ארבעה באגים שכולם נבעו בסופו של דבר מאותה עובדה בסיסית (contracts pending לא פוקעים לעולם, BUG-114 §2 שאלה 6) — כולם נחקרו בנפרד, תוקנו בנפרד, ואומתו בנפרד: BUG-114 (call amplification, PR #402), BUG-115 (Tier-1-מול-Tier-1 confirmation hijack, PR #403), BUG-116 (Tier-4 airtable_id regex false positive, לא קשור ל-3 האחרים, PR #404), BUG-117 (Tier-1-מול-Tier-2 batch preview hijack, PR #405) — **כולם ✅ VERIFIED IN PROD / CLOSED**. ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-117, ו-`CHANGE_CONTROL_LOG.md` C142.

עודכן קודם: 19/07/2026 — **BUG-117 narrow fix מיושם, tests ירוקים, טרם נבדק בפרודקשן:** בהמשך לזיהוי (עודכן קודם), התיקון יושם: פונקציה חדשה `core.lead_candidate_handler.should_prefer_batch_preview(canonical_user_id, chat_id)` משווה recency בין ה-Tier-2 batch preview's `set_at` (TTL 1800s קיים, `session_store.py`'s `pending_lead_preview`) לבין ה-Tier-1 bookmark's `set_at` (TTL 600s קיים, BUG-115's `last_prompted_contract`) — מי שטרי יותר מנצח. `app.py`'s `_CONFIRM_WORDS` קורא לפונקציה הזו **לפני** ה-gate הבלתי-מותנה של Tier-1 (`find_live_contracts()`), ומדלג ישירות ל-`resolve_pending_lead_preview()` כשהיא מחזירה `True`; נופל בחזרה ללוגיקה הקיימת ללא שינוי כשלא. שני מנגנוני ה-TTL הקיימים לא שונו כלל. נדרשה הרחבת חלון-תווים בבדיקה מבנית קיימת (`test_c89_preview_confirmation.py`'s `test_app_py_confirm_word_checks_gateway_before_flag_branch`, 3000→5000/5000→6500) — מהלך זהה למה ש-BUG-058 כבר עשה פעם אחת קודם לאותה סיבה, האינווריאנט עצמו לא השתנה. 11 בדיקות חדשות (`test_bug117_batch_preview_precedence.py`) + `test_c89_preview_confirmation.py` (9/9) ו-`test_bug115_confirmation_routing_bookmark.py` (22/22) רצו מחדש ללא רגרסיה. Full regression sweep: 140/140 קבצי `test_*.py`, exit 0. מחוץ לסקופ במפורש: BUG-114, בוקמארק BUG-115 עצמו, `route_disambiguation()`, ו-`_CANCEL_WORDS`/`route_cancellation_word()` (התנהגות שונה ומורכבת יותר — מבטלת את **כל** ה-contracts החיים כשקיימים — נושא נפרד, לא נגעו). ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-117, `docs/architecture/action-gateway/BUG-117_BATCH_PREVIEW_PRECEDENCE_HIJACK.md`, ו-`CHANGE_CONTROL_LOG.md` C141.

עודכן קודם: 19/07/2026 — **BUG-115 VERIFIED IN PROD / CLOSED (הראייה החסרה סופקה); BUG-117 (חדש) מזוהה, ממתין לאישור:** דגימת production עם `[TurnEnvelope] case_c_signal kind=C1 detail=live_contracts=10` (10 contracts pending בו-זמנית) — "כן" על ליד טרי ("יצחק גלבר") נפתר ישירות מול ה-contract הנכון (`approved: contract=4c7b539b...` → `Dispatch airtable_add → POST /Leads 200 OK → executed: external_id=rec34IdTmCFVbRABo` → `"✅ בוצע: יצירת ליד: יצחק גלבר, 0527696084, general"`) ללא תפריט disambiguation. זהו התנאי `live_contracts>1` המפורש שהיה חסר בעדכון הקודם (C139) כדי להבחין מהמסלול הקודם (`len(live)==1`, לא-קשור-לבאג). **BUG-115 עכשיו ✅ VERIFIED IN PROD / CLOSED במלואו.** גם F52 executed-shadow נקייה (`outcome=executed mapped_state=success`, ללא דגלי leak); **לא** נספרת כדגימת RP5/EvidenceFinalizer בהיעדר שורת `EvidenceFinalizerShadow` תואמת — סטטוס RP5 לא עודכן. **BUG-117 (חדש, נפרד מ-BUG-115):** אותה סבב-שיחות חשף גם ש-batch lead-preview ("📋 זיהיתי 2 לידים אפשריים בקבוצה... ענה כן לשמירת כולם") נחטף לאותה disambiguation גנרית — הבוקמארק של BUG-115 לא מכסה אותו כי זה מנגנון Tier-2 נפרד (`session_store.py`'s `pending_lead_preview`, לא ActionContract). Root cause מאומת בקוד: `app.py:2649`'s בדיקת Tier-1 (`find_live_contracts()`) רצה **תמיד ראשון וללא-תנאי**, לפני שהיא בכלל מגיעה לבדיקת Tier-2 (`app.py:2665`) — הנחת "Tier 1 מנצח תמיד" (`core/lead_candidate_handler.py:1415-1419`, BUG-058 docstring) שכבר נשברה עבור Tier-1-מול-Tier-1 (BUG-115) מעולם לא תוקנה עבור Tier-1-מול-Tier-2. תיקון מוצע (לא ממומש עדיין): השוואת recency בין שני הבוקמארקים הקיימים (`get_last_prompted_contract()` מול `get_pending_lead_preview()`'s `set_at`) לפני הבדיקה הבלתי-מותנית. **ממתין לאישור המשתמש לפתיחה/מימוש.** ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-115, ו-`CHANGE_CONTROL_LOG.md` C140.

עודכן קודם: 19/07/2026 — **PR #404 מוזג ל-main; BUG-116 VERIFIED IN PROD / CLOSED:** PR #404 מוזג (`main` `0ef018f`) — BUG-116's fix (ראה עדכון קודם) עכשיו על `main` ובפרודקשן בפועל. דגימת production מיד אחרי המיזוג, בניסוח שונה מהדגימה המקורית ("domain recruitment" באנגלית, בלי `לדומיין`/מקף — מוודא שהתיקון כללי): `📋 זיהיתי ליד: יונתן כהן (0534820022)` נכון, "כן" → `✅ בוצע: יצירת ליד... מזהה: recNhWVHDd9Noeql1` — אין יותר חסימת "📄 זה נראה כמו טבלה". **BUG-116 סגור במלואו.** **הערה על BUG-115:** אותה דגימה מראה גם "כן" שנפתר ישירות בלי disambiguation — עקבי עם תיקון BUG-115, אך לא מספיק לסמן אותו כ-verified (חסרה ראייה מפורשת ש-`live_contracts>1` באותו רגע, מבחינה בין "הבוקמארק פתר נכון" לבין "היה רק contract חי אחד ממילא" — מסלול קודם, לא-קשור-לבאג). BUG-115 נשאר "לא נבדק בפרודקשן", ממתין לדגימה עם ספירת contracts מפורשת. ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-116, ו-`CHANGE_CONTROL_LOG.md` C139.

עודכן קודם: 19/07/2026 — **PR #403 מוזג ל-main (BUG-114 verified + BUG-115 fix); BUG-116 (חדש) נחקר ותוקן:** PR #403 מוזג (`main` `4ce2fae`) — BUG-115's fix (ראה עדכון קודם) עכשיו על `main` בפועל, לא רק על ענף. **BUG-116 (חדש, נפרד לגמרי מ-BUG-114/115):** דגימת production נפרדת — "צור ליד חדש לדומיין recruitment... יהודה גרוס 0533968395" (משפט ליד תקין, שם+טלפון אמיתיים) נחסם עם "📄 זה נראה כמו טבלה/ייצוא/פלט מודבק" על 3 ניסיונות רצופים, לפני שחילוץ מועמדים בכלל רץ. Root cause מאומת בהרצה ישירה: `core/ingress_classifier.py`'s `_AIRTABLE_ID_RE = re.compile(r"\b(?:fld|rec)[A-Za-z0-9]{8,}\b")` ללא גבול עליון/דרישת-צורה תופס כל מילה אנגלית שמתחילה ב-`rec`/`fld` ומלווה ב-8+ אותיות — `recruitment` = `rec`+`ruitment` (8 אותיות) תואם במקרה, ID אמיתי או לא. ניסיון ראשון (גבול-אורך מדויק, `rec[A-Za-z0-9]{14}`, תואם רגקסי-ID אמיתיים אחרים בקוד) נדחה — היה שובר fixture קיים ב-`test_c89_tier4_precedence.py` (`recABC1234567890`, זנב 13 תווים בלבד, לא 14). **תוקן** עם lookahead הדורש ספרה אחת לפחות ברצף התואם — אומת תכנותית מול כל fixture ID אמיתי בסוויטה (כולם מכילים ספרות, ID אמיתי הוא base62 אקראי; מילה אנגלית לעולם לא). מחוץ לסקופ במפורש: `core/agent_message_formatter.py`'s רגקס נפרד לצנזור פלט-agent (פרופיל-סיכון שונה, לא נגעו). 15 בדיקות חדשות (`test_bug116_airtable_id_word_false_positive.py`), full regression sweep — 138/138 קבצי `test_*.py`, exit 0, כולל `test_c89_tier4_precedence.py` (13/13) ללא רגרסיה. **קוד תוקן, tests ירוקים, טרם PR/מיזוג, טרם נבדק בפרודקשן.** ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-116, `docs/architecture/ingress-classifier/BUG-116_AIRTABLE_ID_REGEX_WORD_FALSE_POSITIVE.md`, ו-`CHANGE_CONTROL_LOG.md` C138.

עודכן קודם: 19/07/2026 — **BUG-115 narrow fix מיושם (PR #403), tests ירוקים, טרם נבדק בפרודקשן:** בהמשך ל-audit (עודכן קודם), התיקון המוצע יושם: bookmark "contract שהוצג לאחרונה" חדש ב-`session_store.py` (`set_last_prompted_contract`/`get_last_prompted_contract`/`clear_last_prompted_contract`, TTL 600s) נבדק ב-`route_confirmation_word()` **לפני** ספירת contracts חיים גנרית — אם הבוקמארק מצביע על contract pending חי לאותו משתמש ולא פג תוקף, "כן"/"מאשר" מאשר אותו ישירות ומדלג על disambiguation. הבוקמארק נקבע משני נתיבי prompt: `core/lead_candidate_handler.py::_handle_single_candidate()` (תצוגת ליד) ו-`app.py::_queue_approval_detailed_impl()` (ActionGateway כללי) — רק אחרי שהוכח שההודעה נשלחה בפועל. נמחק רק בתוצאה טרמינלית (approve/reject/supersede/expire/disambiguation-fallback) — **נשמר** דרך בקשת reconfirmation (BUG-108 FSM) כדי שה-"כן" הבא עדיין יפתור את אותו contract. תוויות disambiguation גולמיות (`airtable_add (id: ...)`) הוחלפו ב-`_describe_contract_for_disambiguation()` חדש — פונקציה **נפרדת**, לא הרחבת `_describe_contract_for_reconfirmation()` המשותפת: ניסיון ראשון להרחיב את הפונקציה המשותפת שבר את `test_stage_b_full_suite.py`'s DoD20 (נתפס ב-full regression sweep, לא בבדיקה הממוקדת). 22 בדיקות חדשות (`test_bug115_confirmation_routing_bookmark.py`) + full sweep 145+ קבצים ירוק, כולל וידוא שהתיקון לא נוגע ב-BUG-114/FSM האישור-החוזר. ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-115, `docs/architecture/action-gateway/BUG-115_CONFIRMATION_ROUTING_HIJACK_AUDIT.md`'s §7, ו-`CHANGE_CONTROL_LOG.md` C137.

עודכן קודם: 19/07/2026 — **BUG-114 VERIFIED IN PROD / CLOSED; BUG-115 (חדש) נחקר ורשום:** ה-burst שנצפה קודם (ראו עדכון קודם) אובחן כ-BUG-114 — `ExecutionLedger.mark_context_interrupted()` (`core/action_gateway.py:558`) סימן מחדש כל contract pending, כולל כאלה שכבר `context_interrupted=True`. תוקן (PR #402) עם `and (c.reconfirmation_required or not c.context_interrupted)` — **לא** ה-filter הנאיבי המקורי, שנתפס תוך כדי כתיבת בדיקות כשובר את FSM האישור-החוזר הקיים (BUG-108). **✅ VERIFIED IN PROD (19/07/2026):** דיווח מפורש — אין יותר burst חוזר. **BUG-115 (חדש, נפרד במפורש מ-BUG-114):** אותה דגימת production ("צור ליד חדש לענף גיוס... כן") חשפה ש-"כן" אחרי תצוגת "📋 זיהיתי ליד..." (contract Tier-1 אמיתי, עיצוב BUG-056 מכוון) נחטף ל-disambiguation גנרי של 8 contracts ישנים ולא-קשורים במקום לאשר את הליד שהוצג — `route_confirmation_word()` סופר contracts חיים בלבד, בלי לזהות "לאיזה contract ה-'כן' מתייחס"; חושף גם tool_name/id גולמיים. `TurnEnvelope.active_queue_id` נבדק ונשלל כגורם (תצפית-בלבד, Phase 0). תיקון מוצע (bookmark "contract שהוצג לאחרונה" + תוויות אנושיות ל-disambiguation) **לא ממומש עדיין** — audit בלבד. ראה `AI_CONTEXT.md` §1/§4, `BUG_AUDIT_LOG.md` BUG-114/BUG-115, ו-`CHANGE_CONTROL_LOG.md` C134–C136.

עודכן קודם: 19/07/2026 — **PR #393 exact branch VERIFIED IN PROD; PR #399/#400 merged — BUG-113 סבב 2 + TurnOwnershipShadow:** דגימת production חדשה (Eli: "תבדוק מה הסטטוס של המשימה בדיקת pull request 393... הוסף לה עדכון") לכדה בדיוק את הענף המדויק של PR #393 שהיה חסר עד עכשיו: `evidence_status=mixed response_claim=sent_for_approval mismatch=false verified_reads=1 approvals_pending=1` — turn שביצע `airtable_get` מאומת ואז `airtable_update` requires_approval באותו turn. **PR #393 עכשיו VERIFIED IN PROD במלואו** (שני הענפים — adjacent וגם המדויק). אותה דגימה גם אימתה **PR #400 (TurnOwnershipShadow)** עובד נכון: `final_reply_nonempty=false`, אין violation, כי A32 דיכא כראוי. בנוסף, שני PRs נוספים שלא תועדו קודם: **PR #399 (BUG-113 סבב 2/FU)** — דגימת production אחרי #396 עדיין הראתה כפילות, עם ניסוח שונה (bold markdown `**מאשר**`, וצורת-זכר `ממתין` ללא סיומת — שתי אותיות יוניקוד שונות ל-נ, לא רק "סיומת חסרה"); תוקן עם `_strip_markdown_emphasis()` (בלתי-תלוי-בכמות כוכביות) ואלטרנציה מפורשת ל-ממתין; **✅ VERIFIED IN PROD**. **PR #400 (TurnOwnershipShadow)** — אינווריאנט shadow חדש, לא flag-gated, ללא שינוי התנהגות: מזהה ורושם מקרה שבו `reply_owner="gateway"` אך ה-agent עדיין "דיבר" (final_reply לא ריק) — כולל סיווג `pattern_class`. **נצפה בו-זמנית, לא טופל:** burst קריאות Airtable חוזרות (contract_id כפול, meta/tables חוזר, 18 שורות Sessions ל-sender יחיד) — נושא נפרד, טרם אובחן, שונה מ-C118-ish read-amplification הישן (תוקן כבר 15/07). ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-113 (סבב 2), ו-`CHANGE_CONTROL_LOG.md` C127/C131/C132.

עודכן קודם: 19/07/2026 — **Runtime evidence sync (PR #391–#396) — BUG-111/BUG-112 VERIFIED IN PROD, F52/RP5 shadow runtime-observed:** תיעוד זה עודכן לפי הכלל "Runtime evidence > main code > docs > memory" (ראו `AI_CONTEXT.md`'s process rule) — ברירת מחדל של flag בקוד אינה הוכחה שדבר לא רץ בפרודקשן; לוגים אמיתיים גוברים. **BUG-111** (PR #386+#390, פענוח batch לידים) — **✅ VERIFIED IN PROD**: paste קומפקטי עם 3 טלפונים כבר לא יצר ליד מזויף, ביקש 3 שמות. **BUG-112** (PR #387, TTL על כפתור אישור טלגרם) — מנגנון הליבה **✅ VERIFIED IN PROD**: כפתור שפג תוקף הציג "⏰ פג תוקף — הפעולה לא בוצעה", 0 ביצוע, כפתור נעלם; **PR #394** (נרמול ניסוח stale/missing-callback, נתיב **נפרד**) — merged/tests green, defensive/idempotency cleanup, טרם production-verified בנפרד. **F52 Unified Approval Runtime** (PR1–PR6, #381–#385/#389/#392/#393) — `FEATURE_UNIFIED_STATUS_FORMATTER` ברירת מחדל בקוד `off`, **אך** לוגי production מציגים `[UnifiedStatusFormatterShadow]` עבור `outcome=executed`/`rejected`/`pending` — **shadow רץ בפועל**, לא רק קוד מוכן; לא הופעל `on`. **PR #393** (mixed read+approval_pending taxonomy) — merged/tests green, דגימה סמוכה נצפתה נקייה, אך הענף המדויק (`response_claim=sent_for_approval` על turn מעורב) **עדיין לא נצפה** — לא overclaimed כ-production-proven. **RP5/EvidenceFinalizer** — `FEATURE_EVIDENCE_FINALIZER` ברירת מחדל בקוד `off`, **אך** `[EvidenceFinalizerShadow]` נצפה בלוגים בפועל — **shadow runtime-observed**; enforcement (RP5 עצמו) עדיין חסום, ממתין לדגימת #393 המדויקת בין שאר הדגימות. **BUG-113** (חדש, PR #396) — A32 לא דיכא פרוזת approval-invite כפולה כשאישור אמיתי כבר בתור — **✅ VERIFIED IN PROD, סגור**, evidence מדויק מלוגים (דיכוי + ownership נכון + EvidenceFinalizerShadow ללא mismatch). **בלוקר נוכחי מתוקן:** לא "הפעלת shadow ראשונית" (זה כבר קרה וגם נצפה) — אלא **shadow soak / חלון תצפית נקי** וניטור דגלי leak, ולפני RP5 enforcement גם דגימת ה-#393 המדויקת. ראה `AI_CONTEXT.md` §1/§3/§4, `BUG_AUDIT_LOG.md` BUG-111/BUG-112/BUG-113, ו-`CHANGE_CONTROL_LOG.md` C125–C130.

עודכן קודם: 17/07/2026 — **BUG-104 Phase 2A.0 + 2A.1 SPEC (PR #370, #371) + BUG-110 fix (PR #372):** שני מסמכי audit+SPEC חדשים תחת `docs/architecture/bug-104/` — (2A.0) אינוונטר סכמת Leads חי (39 שדות, 16 רלוונטיים) + ערכים חיים על 92 רשומות + מפת read/write בקוד + מודל קנוני מוצע: `status`/`Business Outcome`/`Score`/`domain` כקנוניים, 6 שדות formula כ-display-only, `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` כמועמדי-ניקוי (ריקים/לא-אמינים בפועל — `tier` 0/92, `Domain summary` הוא Airtable aiText שמפרש בטעות את `domain` הפנימי כשם-דומיין-אינטרנט). (2A.1) מדיניות precedence מוצעת בין `Business Outcome`/`status` ל-`state` המוקרן — מתעד עובדתית (לא הנחה) ש-`Business Outcome` **לא נכנס בכלל** ל-`ReasoningEntity` היום, ושרק 2 מתוך 10 ערכי `status` חיים ממופים בכוונה ב-`LeadsAdapter._normalise_status()`. **שני המסמכים הם audit+SPEC בלבד — אין קוד runtime; יישום Phase 2A ממתין לאישור owner.** בנפרד, **PR #372 (BUG-110, במקור תויג BUG-105 בקוד/PR — התנגשות מספור עם BUG-105 קיים ולא-קשור ב-`BUG_AUDIT_LOG.md`, תוקן בתיעוד ל-BUG-110 לפי החלטת owner)** תיקן שני נתיבי כתיבה (`lead_conversion.py`, `ad_attribution.py::mark_converted`) שכתבו `status="converted"` הלא-קנוני ל-`status=LeadStatus.DONE`+`Business Outcome=LeadOutcome.CONVERTED`; `ad_attribution.py` נשאר במכוון על `tools.airtable_tools.airtable_update` (לא canonical gateway) כדי לא לשבור טסט קיים — חוב טכני מתועד. ראה `AI_CONTEXT.md` §1/§3, `BUG_AUDIT_LOG.md` BUG-110, ו-`CHANGE_CONTROL_LOG.md` C122–C124.

עודכן קודם: 17/07/2026 — **F52 Unified Approval Runtime — Unified User Messages, PR 0 (PR #366 Draft):** התכנון והאודיט הושלמו ותועדו; היישום טרם התחיל. PR 0 הוא documentation-only ומכיל תקן UX, מפת נקודות פלט, החלטת `display_payload` מול `human_summary` ותוכנית יישום מדורגת. הצעד הבא לאחר מיזוג ובדיקה הוא PR 1 — Message Contract Foundation בלבד, מנותק מנתיבי production. אין שינוי בקוד, ב־approval policy או בהתנהגות production.

עודכן קודם: 17/07/2026 — **9 PRs נוספים מוזגו ל-main מאז 16/07 (#354–#362)** — כל השרשרת flag-gated `off`/`shadow` או docs/תשתית-בלבד, **ללא הפעלת production חדשה**. (1) **BUG-104 P1-A/B/C re-audit** (PR #354, `71f04fb`) — Lead Events lookup לפי reverse-link record IDs (לא scan מלא/לא match לפי display-value), נורמליזציית שדות live-schema (lowercase) ל-`LeadsAdapter` לפני הרצתו, readiness הפך למצב-אמת מפורש (`unknown`/`unavailable`) ולא הועתק מ-`phase`. (2) **PR-RP0** (PR #355, `4efb61b`) — מסמכי תכנון בלבד (`RUNTIME_RELIABILITY_AND_PERMISSION_HARDENING_SPEC.md`, `BOSS_PRODUCTION_RUNTIME_MAP.md`), נפתח ב-`--force` על `pre_session_gate.sh` (מאושר במפורש). (3) **PR-RP1** (PR #356, `b29fbcb`) — `tool_registry.py` מקבל `validate_tool_invariants()` תמיד-פעיל (לא flag) לבדיקת מבנה ה-registry, 120 בדיקות חדשות. (4) **BUG-104 Phase 1.1** (PR #357, `08ad671`) — `LeadsAdapter._normalise_status()` מחזירה עכשיו את ערכי `DecisionStatus` הליטרליים ש-Attention/Orchestrator באמת משווים מולם (במקום אוצר-מילים מקביל שמעולם לא התאים), ואימות linkage דו-כיווני ל-Lead Events (השדה `Lead` של האירוע עצמו חייב להכיל את `lead_id`, לא רק reverse-link). (5) **PR-RP2** (PR #358, `1b17337`) — shadow diagnostics לזמינות כלים per-role (`FEATURE_TOOL_AVAILABILITY_FILTER=shadow`), לוגים בלבד, אין שינוי schema. (6) **PR-RP3** (PR #359, `59eafd1`) — `enforce` מסנן בפועל schemas של כלים לא-זמינים לפני שה-Agent רואה אותם, **ברירת מחדל עדיין `off`**. (7) **BUG-104 TMA Lead Event Bridge** (PR #360, `0a0c331`) — `core/lead_event_writer.write_tma_lead_event()` חדש, מחווט ל-`tma_api.py::patch_lead/set_lead_outcome` (owner-immediate) ול-`tools/approval_actions.py::tma_write()` (manager-approved, כולל `update_lead_status`) — כתיבות ליד מה-TMA כותבות עכשיו גם ל-Lead Events, לא רק inbound chat; לא תלוי ב-`LEAD_CAPTURE`, אין שינוי סכימה/mapping/backfill. (8) **TMA saas-card hide** (PR #361, `bee46b5`) — `tma_api.py::_get_project_cards()` מסנן `domain="saas"` מהתצוגה של Projects Hub בלבד; הרשומה/slug/domain ב-Airtable לא נגעו. (9) **PR-RP4** (PR #362, `3a3edbe`) — `core/turn_evidence.py` חדש, evidence finalizer shadow-mode, `FEATURE_EVIDENCE_FINALIZER=off` (comparison-only גם ב-"enforce", עד RP5). **Docs governance:** PR #363 (`28d4f09`, merge `60991c1`) רענן את `AI_CONTEXT.md` בלבד; PR #364 (`1d31aab`, merge `80fdfae`) הוא שסנכרן בפועל את `ROADMAP.md`, `CHANGELOG.md` ו-`CHANGE_CONTROL_LOG.md` עבור #354–#362. ראה `AI_CONTEXT.md` §3 ו-`CHANGE_CONTROL_LOG.md` C112–C121 לפירוט. **גבול הסקופ נשמר:** `CHANGELOG.md` עדיין אינו מפרט בנפרד את #348–#353 (PA-01), ו-`CHANGE_CONTROL_LOG.md` חסר רשומות #327–#353 אחרי C111; שני הפערים מסומנים במפורש ולא בוצע להם backfill.

עודכן קודם: 16/07/2026 — **PA-01 (Phantom Approval Prompt structural enforcement) נמזג ל-main (PR #352, squash `2be2472`)**, ענף `claude/f52-audit-turn-ownership-u1gizk`. state-only enforcement שחוסם תשובת "הפעולה ממתינה לאישור" כשלא נוצרה בפועל ראיה תקפה בסבב הנוכחי — 5-row decision matrix, לעולם לא בודק טקסט-תשובה. עבר תכנון מאושר + מימוש + **5 סבבי Codex re-audit** רצופים (כל אחד סגר פער אמיתי: `created_this_turn`≠`contract_id`; שם-כלי קנוני; fingerprint אינו הוכחת-בעלות; TOCTOU race ב-reject האטומי; Airtable/durable repository ללא CAS אמיתי → fail-closed) + סבב חילוץ מבני (`core/approval_queue_recovery.py` חדש, אפס שינוי behavior). נשלט ע"י `FEATURE_PA01_ENFORCEMENT_STATE` (three-state off/shadow/enforce), **ברירת מחדל `off`, לא הופעל בפרודקשן**. 110/110 בדיקות ייעודיות + 117/117 full sweep + smoke + compileall, בכל סבב מחדש. ראה סעיף **"PA-01 — Phantom Approval Prompt Structural Enforcement"** למטה ו-`docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md`. **הערה:** אותו PR מיזג גם עבודת Phase 0 TurnCoordinator ownership-signal קודמת (`core/turn_envelope.py`'s `OwnershipSignal`) שהייתה כבר בענף — לא תוארה כאן בפירוט, ראה `docs/architecture/turn-coordinator/README.md`.

עודכן קודם: 16/07/2026 — **BUG-104 קיבל שם קנוני: Core Reasoning Activation Program** (└── Phase 1 — Leads Read-Only Reasoning Projection). שינוי שם *תוכנית ההפעלה* בלבד — שמות המודולים (`core/reasoning_*`, `core/adapters/leads_adapter.py`) והשם הטכני-היסטורי "Core Reasoning Layer" (F22) לא שונו. Phase 1: projection קריא-בלבד `"reasoning"` ל-`GET /api/leads/<lead_id>`, דגל `FEATURE_CORE_REASONING_LEADS_STATE`=off/shadow/on (ברירת מחדל off), ללא mutation/persistence. ראה U1 למטה + `BUG_AUDIT_LOG.md` BUG-104.

עודכן קודם: 13/07/2026 — **PR #326 (P0 unhashable-Identity in atomic-claims wrapper)** נמזג ל-main (`b962773`). עקיפת-וילון-אישור נסגרה (C110/PR #325) + תוקן היום P0 קריטי בexecution wrapper (C111/PR #326): `execute_with_atomic_claim()` קראה ל-executor בצורה מיקומית, Identity התחייב ל-contract_id (unhashable dict key) → ExecutionLedger.find_by_id() קרש. תיקונים: (1) כל 3 קריאות executor_fn → keyword args; (2) Identity fail-closed reconstruction מ-frozen ActionContract; (3) DispatcherOutcome structured contract + verify_execution-based classification; (4) 18-test regression suite מול pre-fix code. Staging verified: real PostgreSQL, Airtable write, claim lifecycle, identity preservation. FEATURE_ATOMIC_CLAIMS production OFF (pending staged rollout). ראה CHANGE_CONTROL_LOG.md C110/C111.

עודכן קודם: 12/07/2026 — BUG-PENDING-APPROVAL-B (Pending Approval Context Safety) נסגר במלואו, ✅ VERIFIED IN PROD, שרשרת של 4 PRs (#311-#314) שכל אחד נבדק חי בפרודקשן בנפרד ולבסוף כולם יחד: (1) **PR #311** — `ActionContract` קיבל `context_interrupted`/`reconfirmation_required`; `route_confirmation_word()`'s single-contract gate מציג מחדש תיאור עסקי במקום לבצע בשקט פעולה ישנה כשהודעת-ביניים הגיעה בינתיים ("context poisoning"). (2) **PR #312** — התגלה בבדיקה חיה שה-hook היה בתוך `run_agent()` בלבד, ולכן לא ראה מסלולים שעוקפים אותו (`/update` ו-slash commands אחרים, callbacks, wizard text/media, Decision Hub, מדיה כללית) — הוחלף ב-**global ingress context gate** יחיד לכל webhook (Telegram+WhatsApp Twilio+Meta), אחרי auth/dedup/identity, לפני כל ניתוב; `ActionGateway.is_own_resolution_event()` מזהה resolution אמיתי בלי לשכפל את לוגיקת ה-routing. (3) **PR #313** — בדיקה חיה נוספת חשפה ש-`guards/idempotency`'s Telegram dedup key היה מבוסס טקסט-הודעה, לא זהות-אירוע — "כן" שני זהה-טקסט נחסם כ-duplicate; תוקן ל-`update_id:message_id`. (4) **PR #314** — עוד בדיקה חיה חשפה שהבוליאנים לא ייצגו הפרעות *חוזרות*: אחרי reconfirmation אחד, הפרעה שנייה לא נתפסה, "כן" הבא ביצע ישירות. הוחלף ב-FSM חסום-סיבוב-אחד: `PENDING → (הפרעה) → RECONFIRM_REQUIRED → (הפרעה נוספת) → SUPERSEDED` (סופי, לא רקורסיבי) — הודעת supersede ספציפית ("הפעולה הקודמת בוטלה... שלח מחדש"), לא dead-end שקט. גם: קבלת-ביצוע מציגה תיאור עסקי (`compose_status_reply`), לא `tool_name`/`airtable_add` גולמי. **אימות סופי (12/07/2026):** לוג פרודקשן מילולי מלא — preview → 2 הפרעות → "כן" (re-display מדויק, מילה-במילה) → הפרעה שלישית → "כן" (superseded מדויק, אין ביצוע) — כל השרשרת ביחד, לא רק חתיכה אחת. ראה BUG_AUDIT_LOG.md BUG-108/BUG-PENDING-APPROVAL-B + 3 ה-Follow-ups.
עודכן קודם: 10/07/2026 — SPEC A1 (Atomic Fail-Closed) נסגר: audit של "Preview Integrity" (Contract Chain, אותו סבב) איתר ש-`tools/airtable_gateway.py`'s `airtable_patch()`/`airtable_create()` כתבו payload חלקי בהצלחה כש-`validate_airtable_fields()` השמיטה רק חלק מהשדות — ה-`errors` שהפונקציה מחזירה תועדו ב-log בלבד, לעולם לא נבדקו ע"י הקוראות. משפיע על **כל** נתיב כתיבה בקוד (לא ספציפי ל-Leads). תוקן: שתי הפונקציות מחשבות `dropped = set(fields) - set(clean)` וחוסמות כתיבה כליל אם לא ריק (fail-closed אטומי) — בלי לגעת ב-`validate_airtable_fields` עצמה. Coercion (linked-record string→list) נשאר תחת אותו מפתח, לכן לא נחסם — מקרה קצה קריטי שנבדק במפורש (T3). 5 טסטים חדשים ב-`test_airtable_gateway.py` (32/32 בקובץ). ראה BUG_AUDIT_LOG.md SPEC A1.
עודכן קודם: 10/07/2026 — BUG-097 (NAME-TRAILING-INTENT-VERB) נסגר: בדיקה חיה שנייה בפרודקשן **אחרי** מיזוג BUG-096 אישרה שה-block-splitting עובד נכון (3 לידים, טלפון פגום אחד — נדחה נקי, ללא זיהום שכן!), אבל חשפה שורש צר יותר — כשהטלפון בסוף הבלוק (לא מייד אחרי השם), פועל-כוונה כמו "מעוניין" נדבק לשם כי `_HEBREW_NAME_RE` תופס greedy את כל הרצף העברי הרציף ו-`_NAME_STOP` לא כלל פעלי-עניין. תוקן: `מעוניין`/`רוצה`/`מחפש`/`צריך`/`מבקש` (+נטיות) נוספו ל-`_NAME_STOP` — אותו מנגנון חיתוך קיים, לא regex חדש. `test_bug096_ingress_classifier_batch_bleed.py` הורחב ל-29/29. ראה BUG_AUDIT_LOG.md BUG-097.
עודכן קודם: 10/07/2026 — 🔴 **תיקון-טעות: BUG-094/BUG-095 (למטה) תוקנו בקוד מת**, לא נגעו בפרודקשן. `parse_batch_dictation()`/`parse_lead_dictation()` ב-`core/lead_candidate_handler.py` (שהם תוקנו) אין להן אף קורא חי — `handle_lead_candidate()` בפועל משתמש ב-`core/ingress_classifier.py`'s `_extract_lead_candidates()`, מימוש כפול ונפרד עם אותו באג בדיוק. **BUG-096 (חדש) הוא התיקון האמיתי**, במקום הנכון: `_extract_lead_candidates()` מפוצל עכשיו לבלוקים דרך `_BLOCK_SEP` חדש, ומצורף `raw_text` per-candidate (סוגר גם ממצא נוסף שנמצא — Summary/Lead Event של כל ליד בבאצ' הכיל בטעות את כל הבאצ', לא רק את הליד עצמו). `_at_find_lead`/`_lead_domain_key` (BUG-094-B/C) כן היו תיקונים חיים תקפים — לא הושפעו. `test_bug096_ingress_classifier_batch_bleed.py` (חדש, 24/24). ראה BUG_AUDIT_LOG.md BUG-096 + תיקון-הטעות בסוף BUG-095.
עודכן קודם: 10/07/2026 — BUG-095 (BATCH-MALFORMED-PHONE-BLOCK-BLEED) נסגר: בדיקה חיה בפרודקשן **אחרי** מיזוג BUG-094 חשפה שורש נוסף — כשמספר טלפון באמצע באצ' פגום (לא מזוהה ע"י `_PHONE_RE` בכלל), אין גבול-טלפון-שכן לחסום מולו, והבלוק כולו "נבלע" לתוך המועמד הבא (garbled name + phone מיוחס למועמד הלא-נכון). תוקן: `parse_batch_dictation()` מפצל עכשיו לבלוקים דרך `_BLOCK_SEP` (regex קיים בקובץ, מעולם לא נקרא בפועל עד עכשיו) *לפני* חילוץ טלפון/שם — גבול-בלוק, לא רק מיקום-טלפון, חוסם bleed. קלט מסוג אחר לגמרי שהמשתמש בדק (WhatsApp chat-export עם headers) אומת כ**לא**-רלוונטי — `classify_ingress()` כבר מסווג אותו tier=4/table (BUG-064 hard-marker gate קיים), לא מגיע בכלל ל-`parse_batch_dictation`. `test_bug094_batch_name_bleed.py` הורחב ל-31/31. ראה BUG_AUDIT_LOG.md BUG-095.
עודכן קודם: 10/07/2026 — PR4 (Airtable Schema Refresh — docs cleanup) הושלם, סוגר את יוזמת PR3A/3B/3C/
PR2/PR_RESPONSE_CONTRACT (כל 5 ה-PRs הקודמים כבר ממוזגים ל-`main`). נוסף `docs/governance/
AIRTABLE_SCHEMA_GOVERNANCE.md` (source-of-truth vs. seed vs. runtime provider vs. snapshot archive,
מה כל PR מכסה, למה response-contract היא משפחת באג נפרדת). `CLAUDE.md`'s module list עודכן עם
`core/runtime_schema_provider.py`/`tools/schema_snapshot.py`/`tools/check_airtable_schema_runtime.py`.
באותו סבב: BUG-018/020/021 נסגרו (doc drift — הקוד כבר תוקן, לא היה מתועד), BUG-019 3/5 תת-בעיות
נסגרו + 1/5 חלקית (Deals ADDRESS/FUNDING_COST/ROI תוקנו ב-commit `9b51537` ישיר של המשתמש,
RISK_LEVEL/NOTES עדיין לא אומתו) + 1/5 פתוחה (Payments contact_id/notes — silent data loss, לא
crash), ו-3 מחלקות קוד מת (`ImportsFields`/`TenantsFields`/`DailyTaskFields`) נמחקו מ-
`airtable_schema.py` (0 שימושים, מאומת מחדש לפני מחיקה). `schema_cache.json` (seed מטעה) נשאר
במכוון — הוא ה-fallback הפעיל של BUG-021, לא קוד מת. ראה BUG_AUDIT_LOG.md לפירוט מלא.
עודכן קודם: 10/07/2026 — BUG-094 (BATCH-NAME-WINDOW-BLEED) נסגר: בדיקה חיה בפרודקשן של BUG-058's resolver (למטה) חשפה 3 באגים נפרדים ב-upstream — (1) `parse_batch_dictation()`'s חלון ±60 תווים "דלף" שם של מועמד קודם למועמד הבא כששני בלוקי-ליד קרובים; (2) `_at_find_lead()` נפל בעיוור ל-name-only match בלי לוודא phone, מה שהפך את (1) ל"שתי כתיבות לאותה רשומה" בפועל; (3) `RouterDomain.CRM`/`INTERNAL` (דומייני-מטא של ה-Router, לא ורטיקלים עסקיים) זלגו ל-`Leads`/`Lead Events`' Domain field, גרמו ל-422 על Lead Events. שלושתם תוקנו (`_lead_domain_key()` חדש מטפל ב-(3)). `test_bug094_batch_name_bleed.py` (חדש, 25/25). ראה BUG_AUDIT_LOG.md BUG-094 + עדכון BUG-058.
עודכן קודם: 10/07/2026 — BUG-058 סגור במלואו: Tier-2 batch-confirm resolver נבנה (`session_store.py`'s `set/get/clear_pending_lead_preview()`, `core/lead_candidate_handler.py`'s `resolve_pending_lead_preview()`), מחווט ב-`app.py` section 2.55. Precedence-decision שנדרש לפני בנייה (ראה 03/07 למטה) הוכרע: Tier-1 ActionGateway מנצח תמיד Tier-2 כששני המנגנונים חיים בו-זמנית לאותו chat_id — אותו precedent שכבר קיים ב-BUG-056 ("check ActionGateway live contracts FIRST"), לא הכרעה חדשה משורש. `test_tier2_silent_preview.py` נכתב מחדש (9/9). אפס רגרסיה. ראה BUG_AUDIT_LOG.md BUG-058.
עודכן קודם: 09/07/2026 — N15 נפתח (Restricted-flow `notify_owner` — שדה נקבע אך לעולם לא נצרך, אין
מנגנון התראה אמיתי לבעלים; התגלה תוך כדי תיקון claim-without-evidence כוזב באותו איזור —
`_SINGLE_SPEAKER_FALLBACK` (PR #280) ו-`app.py`'s Restricted tool loop). שני הניסוחים הכוזבים
תוקנו מיידית; ה-N15 עצמו (החלטה: לבנות התראה אמיתית או להסיר את השדה) עדיין PLANNED, לא מומש.
עודכן קודם: 08/07/2026 — BUG-078/079/080/081 (שרשרת `/update`+Business Memory, PR #255/#256/#257/#258/#259/#260/#261/#263/#265) **✅ PRODUCTION VERIFIED במלואו, 6/6 domains**: `/update` נבדק ברצף אמיתי (real_estate/SaaS/media/import/general/finance) → `Other` → טקסט חופשי → נשמר בהצלחה בכולם, "📌 Other | <domain>" מוצג נכון, אין 422 באף אחד. מכסה: BUG-078 (זרימת `/update` הכללית), BUG-079 (`capture_text`), BUG-080 (`cmd_update.py`'s Event Date בלבד — שאר 6 נקודות הכתיבה טרם נבדקו), BUG-081 המלא כולל PR #263 (root cause — domain לא נכתב ל-Tags בכלל) ו-PR #265 (רווח בסוף ב-"Real Estate "/"SaaS ", מאומת מול Meta API) עבור כל 6 המפתחות. **נותר לבדוק:** C99 (חילוץ מסמך). ראה `BUG_AUDIT_LOG.md` BUG-078..081 ו-`CHANGE_CONTROL_LOG.md` C97-C101 לפירוט מלא.
עודכן קודם: 07/07/2026 (מאוחר יותר עוד עוד) — BUG-078/079/080/081 תוקנו ומוזגו ל-main (PR #255/#256/#258/#259/#260/#261): (1) BUG-078/079 — `app.py`'s webhook היה מדלג על ה-pending state של `/update` עבור photo/document וגם עבור טקסט חופשי, ובורח לזרימות אחרות (Drive הכללי / `run_agent`) — שני ה-bypass-ים נסגרו. (2) BUG-080 — 7 נקודות כתיבה שלחו `datetime` מלא לשדות Date-בלבד ב-Airtable (422), תוקן ל-`.date().isoformat()`. (3) BUG-081 — Business Memory קיבלה שדה `Domain` ייעודי במקום למחזר domain לתוך `Tags` הכללי; דרש 2 סבבי תיקון נוספים על בסיס production evidence (422 חי אחרי מיזוג, "real_estate" lowercase לא היה option קיים יותר). גם C99 (feature, לא באג) — חילוץ טקסט ממסמך שנשלח באמצע `/update`. כל השישה ✅ מוזגים ל-main, **לא מאומתים בפרודקשן**. ראה `BUG_AUDIT_LOG.md` BUG-078..081 לפירוט מלא. גם: BUG-077 (השורה הקודמת כאן) התברר **כבר מוזג בפועל** (PR #254) — תוקן.
עודכן קודם: 07/07/2026 (מאוחר יותר עוד) — BUG-077 root cause נסגר בקוד: `propose_action()` (`core/action_gateway.py`) מאמת כעת `requires_approval` מול `tool_registry.needs_approval()` fail-closed, פרט ל-`self_confirm` carve-out (BUG-076). דרש גם תיקון ל-`core/lead_candidate_handler.py::_write_one_lead()` (payload היה חסר "fields", מנע ממנו self_confirm תקין) — ראה `BUG_AUDIT_LOG.md` BUG-077 לפירוט מלא כולל קונפליקט עם יישום ראשוני נאיבי שתוקן לפני push. 🟡 קוד מוכן, טרם ממוזג.
עודכן קודם: 07/07/2026 — 3 תיקוני doc-drift: (1) BUG-077 (Tier 3 auto-capture gate, `core/lead_candidate_handler.py`) ✅ ממוזג ל-`main` (PR #250, `cdc41b5`) — `BUG_AUDIT_LOG.md` עדיין רשם "Merged: לא", תוקן. (2) F12 vs F13: הכרעת בעלים מפורשת — F13 סופגת את F12, F12 נגנז. ראה סעיפי F12/F13 למטה. (3) BUG-DH-03/04 גם ✅ ממוזג ל-`main` (PR #251, `d51e6be`) — השורה הקודמת כאן טענה "לא ממוזג" בטעות (זה כבר תוקן, נשאר רק production verification). `FEATURE_DECISION_HUB` נשאר חסום עד production evidence.
עודכן קודם: 07/07/2026 — BUG-DH-03/04 (Formula Injection ב-Decision Hub) תוקן בקוד: `_safe_formula_param()` נוסף ל-`tools/airtable_gateway.py`, מיושם ב-`cmd_decision.py::_resolve_decision_ref`, `decision_pipeline.py::maybe_supersede`, ו-`core/lead_candidate_handler.py::_search_formulas`. ראה BUG_AUDIT_LOG.md BUG-036/BUG-037 וסעיף BUG-DH-03/04 למטה.
עודכן קודם: 06/07/2026 — C83 (Single Policy Source: הפרדת requires_approval מ-blocked_by_emergency) נסגר: מאומת בקוד ש-`event_bus.ACTIONS_REQUIRING_APPROVAL` הוא alias טהור ל-`tool_registry.TOOLS_REQUIRING_APPROVAL`, לא רשימה עצמאית סותרת. אותה בדיקה אימתה מחדש (לא פתחה חדש) את BUG-077 הקיים (`core/action_gateway.py`/`propose_action()`) — ראה BUG_AUDIT_LOG.md ו-`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5/§7.
עודכן קודם: 05/07/2026 — ניקוי doc-drift: כמה "חסמים"/"PARTIAL" ב-ROADMAP היו סטטוס תיעודי ישן שסתר סעיפים מעודכנים יותר באותו קובץ, לא חסם אמיתי בקוד. תוקן: (1) C91/C92 סומנו "לא חסום על C89" (C89 סגור 05/07) — C93 נשאר חסום, אך על צבירת AgentObservation data, לא על C89. (2) F09/F10/F11 עודכנו — F10 היה כפול/vestige ל-N02/N03 שכבר מיושמים (lead_memory כבר מחובר בפועל), F11 כבר לא "MVP חסר" (N04+N05-B מיושמים), F09 נשאר החלטת-מוצר לא חסם-טכני. (3) "פערים ידועים" table עודכן בהתאם, שורת F10 הוסרה (מיושן/כפול). (4) F12/F13 קיבלו הבהרה מפורשת: חוסמים רק multi-tenant/SaaS provider-abstraction עתידי, לא שום עבודה שוטפת. (5) בלוק Audit ישן (14/06/2026) שטען N02-N05 "PARTIAL" סומן במפורש כהיסטורי/מוחלף — לא נמחק (evidence), אבל לא עוד קריא כסטטוס נוכחי. Decision Hub (BUG-DH-03/04) ו-N05-C (Meta outbound) נשארים חסמים אמיתיים — לא שונו.
עודכן קודם: 05/07/2026 — C94 production verification הושלם 4/5 ע"י הבעלים: Telegram+WhatsApp+File(xlsx/csv, נבדק זמנית עם flag ON, הוחזר ל-OFF)+Render commit hash (`41f3305`) — כולם ✅. הפריט היחיד שנשאר (חריגת classify_ingress) נשאר לא-נבדק live בכוונה. ראה סעיף C94 למטה.
עודכן קודם: 05/07/2026 — BUG-070 gap #1 (מתוך 3) נסגר: `core/action_gateway.py` מקבל `route_combined_word()`/`_parse_combined()` — מפרש "כן 1"/"אשר 3" (אישור ממוקד, סוגר siblings כמו `route_disambiguation`) ו-"לא 2" (דחייה ממוקדת — נשארת gap חדשה: reject-by-index לא היה קיים בכלל קודם, לא רק ניסוח). מחווט ב-`app.py` *לפני* בדיקת ה-disambiguation הרגילה (כדי לא לנקות בטעות state ישן) ולפני `_CONFIRM_WORDS`/`_CANCEL_WORDS`. `test_bug070_combined_wording.py` (חדש, 27/27). gap #2 כבר נסגר קודם (ראה עודכן קודם 05/07). **gap #3 (daily_collector numbered-reply ללא backend) ו-BUG-058 (Tier-2 batch-confirm resolver) נשארים פתוחים במכוון** — gap #3 קיבל רק תיקון מינימלי (הוסרה ההבטחה המטעה "ענה במספר" מ-`daily_collector.py`, ללא בניית backend); BUG-058 נשאר תיעוד-בלבד כפי שתועד ב-03/07 (דורש עיצוב precedence לפני קוד). ראה BUG_AUDIT_LOG.md BUG-070.
עודכן קודם: 05/07/2026 — C89 סטטוס סגור: ✅ CLOSED/VERIFIED עם `FEATURE_AUTO_CAPTURE=false` (החלטה מפורשת של הבעלים — קוד+טסטים מאומתים מחדש, כולל RAW-OBS 15/15; flag נשאר כבוי בפרוד בכוונה, לא production-verification במובן המקורי). C90 לא נוגע — כבר בנוי ומוזג מקודם (PR #228). ראה סעיף C89 למטה.
עודכן קודם: 05/07/2026 — C94: נוסף `FEATURE_INGRESS_ENVELOPE` כ-kill-switch ל-envelope-dispatch ב-`run_agent()` — **ברירת מחדל ON** (נוסף ל-`_DEFAULTS` ב-feature_flags.py, אותו מנגנון בדיוק כמו `IMPORT_DOMAIN`), כי C94 כבר ב-main/כנראה בפרוד ודגל שברירת המחדל שלו OFF היה מכבה אותו שקט ב-deploy. אומת: `is_enabled()` על דגל לא-מוגדר מחזיר `False` כברירת מחדל הרגילה — בלי ה-`_DEFAULTS` entry זה היה שובר את מה שכבר רץ. 138 הבדיקות (57+41+28+12) רצות זהה כשה-flag לא מוגדר בסביבה וכש-`=true` מפורש; אומת גם ש-`=false` באמת מדכא את בניית ה-envelope (0 קריאות ל-`build_telegram_envelope`). שינוי שורה אחת בתנאי + 2 שורות ב-feature_flags.py, שום refactor. ראה AI_CONTEXT.md §0.12 + סעיף C94 למטה.
עודכן קודם: 05/07/2026 — C94 (Unified Ingress Envelope + Evidence Trace) שלב ד׳ הושלם: `core/whatsapp_ingress_adapter.py` חדש (`build_whatsapp_envelope()`, provider="twilio_whatsapp" דרך מיפוי, לא "twilio") + `run_agent()`'s envelope-dispatch הוכלל ל-telegram/whatsapp. Meta WhatsApp Cloud API נשאר gated/לא נוגע לגמרי (אין raw_event_id מועבר משם) — במפורש כדי לא לחזור על תבנית BUG-071 (ingress ש"מתבדר" בין providers). `test_c94_stage_d_whatsapp.py` 12/12 — כולל equivalence מלא דרך `run_agent()` בפועל (לא רק route_request()). אפס רגרסיה. C94 נחשב הושלם לכל הערוצים המאושרים (Telegram+File+WhatsApp/Twilio) — Meta Cloud API נשאר scope עתידי נפרד. ראה סעיף C94.
עודכן קודם: 05/07/2026 — C94 שלב ג׳ הושלם: `core/telegram_ingress_adapter.py` חדש (`build_telegram_envelope()`) + `core/router/capture_router.py`'s `classify_capture_ic()` עטוף try/except (חריגת classify_ingress יורדת ל-capture_ic=None במקום להפיל את כל ה-router ל-Approval/UNKNOWN דרך `_safe_route()`'s catch הגורף), עם EvidenceTrace(classification_error) מסוניטז מההתחלה. `test_c94_stage_c_telegram.py` 28/28 — כולל הוכחה ש-intent/domain/risk ממשיכים לעבוד נכון ובלתי-תלוי, ושה-catch הכללי ב-`_safe_route()` נשאר בדיוק כמו שהיה לכל חריגה אחרת. אפס רגרסיה.
עודכן קודם: 05/07/2026 — C94 שלב א׳+ב׳ הושלמו: `core/ingress_envelope.py` — `IngressEnvelope`/`EvidenceTrace` כ-dataclasses נפרדים (3 תיקוני schema, A.1/A.2/A.3, נסגרו לפני/תוך כדי — ראה סעיף C94 לפירוט: source_ref במקום raw_ref, envelope_id FK + append-only retries, trace_id/attempt_no/status). Stage ב: `core/file_ingress_adapter.py`'s `build_file_row_envelope()` + `app.py` מחווטים ל-File adapter → Envelope → C90 pipeline קיים ללא שינוי, כולל תיקון גap אמיתי שנתפס (classify_ingress() לא היה עטוף try/except, exception בשורה היה מפיל את כל הקובץ). `test_c94_ingress_envelope.py` 57/57, `test_c90_structured_file_capture.py` 41/41, אפס רגרסיה.
עודכן קודם: 05/07/2026 — BUG-066 עד BUG-069 (BUG-DAILY-01..04) תועדו — **פתוחים, לא תוקנו**: (1) Daily Tasks נתקע — אין fail-safe/logging פר-שלב ב-`daily_collector.py`, wrapper גורף יחיד ב-`scheduler.py`. (2) Daily Digest נשלח בשבת — `shabbat_guard.py`'s gate האמיתי (`shabbat_safe`) קיים ומיושם ל-6 jobs אחרים ב-`scheduler.py`, אבל לא ל-`_job_daily_digest`/`_job_daily_collector` — הם משתמשים רק ב-`shabbat_status_message()` (טקסט בלבד, לא חוסם). (3) הדוח ארוך מדי — אין cap על אורך/מספר פריטים. (4) משימות שהושלמו מוצגות בפירוט מלא במקום ספירה בלבד. ראה BUG_AUDIT_LOG.md BUG-066..069.
עודכן קודם: 05/07/2026 — C90 (Structured File Capture, PR #228): file upload כ-ingress source adapter בלבד — `core/file_ingress_adapter.py` חדש מפרסר xlsx/csv לשורות, כל שורה עוברת ללא special-casing דרך אותו `classify_ingress()`/`handle_lead_candidate()` כמו טקסט (שורה ברורה יכולה להיות Tier1 לגיטימי). הוחלט לבנות למרות ש-C89 עדיין לא production-verified, כי C90 לא תלוי בנתיב auto-write. ראה סעיף C90.
עודכן קודם: 04/07/2026 — BUG-061 עד BUG-065 (C89 QA closure, PR #220–#227, כולם מוזגו ל-main): prefix-ביטויים דו-משמעיים, owner שאיבד role אחרי אישור, Session lookup fail-closed, hard markers ל-Tier 4 (טבלה/CSV/Airtable-status), raw_ref+AgentObservation מחוברים. `FEATURE_AUTO_CAPTURE` עדיין כבוי בפרודקשן — production verification (התלות של C90) עדיין לא בוצע. ראה סעיף C89 + BUG_AUDIT_LOG.md.
עודכן קודם: 03/07/2026 — BUG-058 (TIER2-SILENT-PREVIEW-NO-READER): Tier 2 batch preview (`_handle_clean_batch`) הבטיח "אישור קבוצתי" (`ענה כן`) שאף resolver לא קורא בפועל — `pending_lead_preview` נכתב, 0 קוראים בכל הריפו. תוקן: הודעת Tier 2 שונתה לתצפית-בלבד, ללא CTA מטעה; `_store_pending_preview` מתועד כ-`INTENTIONAL — no resolver yet`; השדה נשאר נכתב (audit/future design). Batch-confirm resolver עצמו נדחה בכוונה — דורש עיצוב precedence מול Tier 1 ActionGateway contract *לפני* בנייה. תיקון ב-`branch fix/bug058-tier2-silent-preview`. ראה BUG_AUDIT_LOG.md BUG-058.
עודכן קודם: 03/07/2026 — BUG-057 (LL-14/AD-ATTRIBUTION-UTM-UNGATED): `_inject_utm()` רץ על כל הודעת WhatsApp נכנסת ללא תלות ב-flag `AD_ATTRIBUTION`, כשל נבלע ב-`logger.debug` (שקט). תוקן: `_flag_enabled("AD_ATTRIBUTION")` נוסף לתנאי, log level הועלה ל-`warning`. ממוספר מחדש מ-`BUG-040` (התנגשות ID עם BUG-040 הקיים). מאותר מחדש מענף לא-ממוזג `claude/leads-write-gate-verify-aodpud` בסבב ניקוי ענפים. תיקון ב-`branch fix/bug057-ad-attribution-utm-gate`. ראה BUG_AUDIT_LOG.md BUG-057.
עודכן קודם: 03/07/2026 — BUG-056 (C89-ROUTER-PREVIEW-HARDENING): 4 ממצאי QA ידני על C89/BUG-IC-01 — BUG-IC-01 regex coverage gap ("בדיקת מערכת" יחיד לא נתפס), C89 preview confirmation dead-end (pending_lead_preview נשמר אך לא נקרא בחזרה, "כן" מחזיר "אין פעולה שממתינה"), C89 Tier 4 לא עוצר routing (טקסט מודבק/table/bot-output ממשיך ל-Agent, מפעיל intent שגוי), double-classification cleanup (ingress_classifier רץ פעמיים). תיקון ב-`branch fix/c89-router-preview-hardening`. ראה BUG_AUDIT_LOG.md BUG-056.
עודכן קודם: 02/07/2026 — BUG-051 (SPEC-1-LCH-ROUTER-BYPASS): LeadCandidate Handler רץ לפני route_request() לכל sender פנימי — Router עוקף לגמרי, domain מנוחש ב-regex פנימי. תוקן: capture_tier/capture_reason/raw_ref על RouteDecision (additive), core/router/capture_router.py חדש עוטף classify_ingress() הקיים, LCH הועבר לרוץ אחרי ה-Router עם domain אמיתי. `branch feature/capture-policy-stage-3`, טרם ממוזג. ראה סעיף C89 + BUG_AUDIT_LOG.md.
עודכן קודם: 02/07/2026 — BUG-049 (BUG-CI-SILENT-PASS-DOCUMENT-CONVERTER): `test_document_converter.py` רץ ב-CI בלי לבצע אף assertion (exit 0 שקרי). `__main__` guard נוסף, מוזג ל-main (PR #204). ראה סעיף "Fxx — Safe Document Converter" + BUG_AUDIT_LOG.md.
עודכן קודם: 02/07/2026 — PR #203 מוזג: C89 קוד הושלם (flag כבוי, ממתין ל-production verification), BUG-047/BUG-048 (session dedup + ambiguous phrase gate) תוקנו. ראה BUG_AUDIT_LOG.md.
עודכן קודם: 02/07/2026 — Stage 3 Capture Policy (C89–C93) נוסף. IngressClassification + tiered auto-write. ראה SPEC_Stage_3_Capture_Policy.md.
עודכן: 01/07/2026 — סקירת `fix/c53-approval-hardening`: הוחלט לא למזג את הענף. נפתחו שמונה follow-ups בעדיפות ראשונה (`C81-FU`, `C82-FU`, `C83`–`C88`).
עודכן קודם: 30/06/2026 — Lead Lifecycle + Decision Hub Quality Gate session log. N-LEAD-EVENT/N-CXX/N-LEADBUF/N14 נוספו. BUG-DH-03/04 כblocker לפני FEATURE_DECISION_HUB.
עודכן קודם: 29/06/2026 — Git Diff Gap Report session, main = `debb270` (אומת
`git fetch origin main` + `git log origin/main --oneline -30`). מבוסס על
`SPEC_GIT_DIFF_GAP_FINDER.md`. ממצאים: **(1)** סעיף "Fxx — Safe Document Converter" למטה היה
כתוב "Not merged to main" כשבפועל מוזג מ-26/06/2026 (PR #158, `db719ab`) — תוקן ל"מוזג אך לא
מחובר" (EXISTS_UNWIRED, pattern F20/F22) + ממצא CI חדש (test_document_converter.py רץ ב-CI
בלי לבצע assertion, ראו פירוט בסעיף עצמו). **(2)** שני commits מוזגים ל-`main` ב-29/06/2026
(`4e1d7ed` "Wire lead capture evidence into A32", PR #171; `257a5e4` "Fix safe lead metadata
patch", PR #172) לא תועדו בכלל ב-CHANGE_CONTROL_LOG/ROADMAP — שניהם **כן** מחוברים (caller
אמיתי מאומת: `app.py:1124`, `lead_capture.py:215`), זה לא MISSING/EXISTS_UNWIRED, רק תיעוד
שהוחמץ — תועד למטה ב-CHANGE_CONTROL_LOG.md. **(3)** `reports/daily_changes/` (BUG-022, סשן
קודם) — מאומת קיים ב-remote (`debb270` מכיל `AUDIT_SUMMARY.md`). דוח מלא:
`reports/gap_report_29jun2026.md`. לא בוצע שינוי קוד/wiring — תיעוד בלבד.

עודכן (קודם): 29/06/2026 — Governance Repair session, main = `6b20028` (אומת
ב-`git fetch origin main` + `git merge --ff-only`). **תיקון סטייה ממצא 27/06/2026:**
F20 (Decision Hub Stage 5, Auto Ingestion) נמצא **מוזג אך לא מחובר** — `decision_auto_ingestion.py`
ו-`ingest_message()` אין להם קורא אמיתי באף אחד מ-`app.py`/`inbound_handler.py`/
`email_inbound.py`/`voice_adapter.py`/נתיב מדיה כלשהו (grep מלא על הריפו, לא רק על חמשת
הקבצים שנבדקו). **נוסף ל-`smoke_tests.py`** check חדש (`check_decision_hub_call_sites`)
שמשווה את מצב החיווט המוצהר מול גרף ה-import האמיתי מתוך קבצי entrypoint חיים בלבד —
מונע מצב עתידי שבו פיצ'ר מתועד כ"עבד" בלי נתיב הרצה אמיתי. ראו פירוט מתחת ל-F20 למטה.
**ממצא נוסף, לא היה מתועד בכלל:** שכבת "Core Reasoning Layer" (`core/reasoning_engines.py`,
`core/reasoning_entity.py`, `core/reasoning_ports.py`, `core/adapters/decision_adapter.py`,
`core/adapters/leads_adapter.py`) נמצאת ב-`main` (הועלתה ב-28/06/2026 23:06–23:09 דרך
"Add files via upload" ישירות ל-`main`, לא דרך PR/session) עם 59/59 בדיקות עוברות
(`test_core_reasoning.py`) אך **אפס קריאה חיה** — `run()` ו-`append_reasoning_block()`
נקראים רק מתוך הבדיקות של עצמם. אין תיעוד קודם לזה ב-ROADMAP/AI_CONTEXT/
CHANGE_CONTROL_LOG. נרשם כ"קיים, נבדק, לא מחובר" — לא "פעיל". **בדיקת Airtable חיה
(להחלטה ב-#3 למטה) נחסמה בסשן הזה:** שלושת כלי ה-Airtable MCP (`search_bases`,
`list_tables_for_base`, `get_table_schema`) החזירו "MCP tool call requires approval" על כל
קריאה — לא permission prompt חד-פעמי אלא חסימה ברמת הסשן; `schema_cache.json` עדיין
`fetched_at: "seed-from-schema-py"` (לא live) ולא נערך/נמחק בסשן זה (לפי התקדים ב-BUG_AUDIT_LOG
FLAGGED — לא נמחק/שונה בלי אישור מפורש). מסקנה: שלב Decision Hub Airtable readiness (Evidence
Ids / Evidence Summary / Confidence Score / Missing Evidence / DecisionReadiness.REVIEW)
**נשאר לא מאומת מול Airtable חי** — נחסם **activation blocker** ל-`FEATURE_DECISION_HUB`.

עודכן (קודם): 29/06/2026 — branch `fix/cxx-action-integrity-cleanup`, מבוסס על
`origin/main` ב-`ca1f5a0`. **CXX Action Integrity cleanup — Implemented but not yet
verified:** `core/adapters/__init__.py` תוקן; ששת קובצי `DOC-20260628-WA*.py` הוסרו לאחר
השוואה וחילוץ; WhatsApp stub מחזיר `ActionResult` בלי לטעון לשליחה; Output Gateway משמר
את ראיית ה-adapter; `RequestContext` חובר ל-identity/lead/session/domain ב-`run_agent` בלי
לדרוס את תיקוני session-cache/resolved-domain שכבר ב-main; נוספו 6 בדיקות CXX. רצף
ה־backend CI המלא עבר מקומית עם dependencies מבודדים; GitHub CI עבר ב-PR #169 על commit
`46d470b` (run `28337822793`, backend+frontend ירוקים). Merge, deploy ואימות פרודקשן עדיין
לא בוצעו.

עודכן (קודם): 28/06/2026 — main = `2c55c59` (אומת ב-`git pull origin main` + grep
פיזי לפי AGENTS.md). **PR #166 מוזג** — Decision Hub Stage 6 (F21): orchestrator read-only עם
ששת מצבי ה-lifecycle (`COLLECTING`/`BLOCKED`/`REVIEW`/`AWAITING`/`DECIDED`/`CLOSED`),
ניתוב first-match, שימוש ב-`ConfidenceResult` שכבר חושב Stage 2, fallback דטרמיניסטי ללא
AI conflict detection, וחיבור fail-open ל-`/decision status`. commit `9011923`, merge
`2c55c59`; Stage 6 ‏13/13 וכל Decision Hub ‏128/128. Stages 4–5 מוזגו קודם ב-PRs #161–#164
(F19/F20; פירוט למטה). `FEATURE_DECISION_HUB` ו-`FEATURE_DECISION_AUTO_INGESTION` נשארו
כבויים כברירת מחדל. **Production Verified: לא — נדרש אימות ידני לאחר פריסה.**

עודכן (קודם): 26/06/2026 (מאוחר ביותר) — main = `50f6351` (אומת עצמאית, GitHub MCP `pull_request_read`
(`merged:true`) + `git fetch origin main` + `git merge-base --is-ancestor`). **PR #159 מוזג** —
Decision Hub Stage 3 (Readiness Engine, F18): `decision_readiness.py` (`calc_readiness()`/
`build_readiness_message()`/`detect_escalation()`), מקבל את `ConfidenceResult` של Stage 2 כפרמטר
(לא מחשב AI Conflict Detection בשנית). READY/NOT_READY/REVIEW — `REVIEW` הורחב לתוך
`class DecisionReadiness` הקיים ב-`airtable_schema.py` (SoA — נבדק לפני כתיבת קוד). 8 חוקי הספק +
3 הספים + 4 תבניות escalation מיושמים כלשונם; READY מאותת בלבד, לא מבצע פעולה. 1 סטייה מהספק
מתועדת (partner-disagreement escalation מזוהה רק דרך אות עקיף ב-blockers). Daily Digest hook —
דולג (אופציונלי במפורש בספק). 25/25 self-tests עוברים; 25/25 Stage 2 + 33/33 Stage 1 ללא
רגרסיה. דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל. ענף המקור `claude/new-session-be1ckb` נמחק
מה-remote אחרי המיזוג. **פריסה בפועל ל-Render לא אומתה** (אין גישת dashboard/egress מה-sandbox).
ראו פירוט: F18 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 26/06/2026 — branch `claude/new-session-be1ckb`. **F18 Decision Hub Stage 3
(Readiness Engine) — קוד הושלם**, אישור הבעלים "Yes, implement now" דרך `AskUserQuestion` על ספק
מלא (PLANNING_GATE + SPEC). דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל — אפס שינוי התנהגות
בפרודקשן. (היסטורי — ראו עדכון מאוחר יותר למעלה: מוזג ב-PR #159.)

עודכן (קודם): 26/06/2026 — branch `claude/new-session-be1ckb`, main = `78f9bae`. **תיקון doc-drift** שאותר ע"י audit יומי (סשן `claude/gifted-clarke-ajyjsa`, AI_CONTEXT.md refresh): שני פיצ'רים תועדו כאן כ"קוד הושלם, לא ממוזג" בזמן שהם **מוזגו בפועל ל-`main`** — אומת עצמאית דרך `git merge-base --is-ancestor` על שני המקרים: (1) **C60 Tool Context Awareness** — PR #152, commit `2d85b84`, merge `3e0094b`; (2) **F17 Decision Hub Stage 2** — PR #157, commit `9252b1e`, merge `78f9bae` (תוקן כבר בסבב קודם של סשן זה). גם תוקן: סעיף F52 כאן רשם רק 3 מ-4 קבצי audit שנוצרו בפועל (`F52_STATE_FLOW_MAP.md` היה חסר מהרשימה, מוזג ב-PR #156) ופרט סטטוס "branch" שגוי (F52 מוזג במלואו ל-`main`). פריסה בפועל ל-Render לכל הפיצ'רים האלה **לא אומתה** (אין גישת dashboard/egress מה-sandbox) — ראו פירוט בכל סעיף בנפרד, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 (מאוחר ביותר) — main = `78f9bae` (אומת, GitHub MCP `pull_request_read` + `git merge-base --is-ancestor`). **PR #157 מוזג** — Decision Hub Stage 2 (F17, Smart Trust Layer): AI Conflict Detection Lazy+Cached (לא Eager — לא רץ ב-ingest, רק בפתיחת/Refresh של `/decision status`, מוגבל ל-Claim Topic זהה + Trust>=T1, deduped לפי `event_pair_hash`, מוגבל ל-5 קריאות Claude חדשות לריצה), Decision Confidence Score, Evidence Graph, Missing Evidence Detector (template-based, לא LLM). 3 סטיות מהטקסט המילולי של הספק תועדו ומומשו (ראו F17 למטה). 25/25 self-tests עוברים (`test_decision_confidence.py`); 33/33 Stage 1 ללא רגרסיה. דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל — אפס שינוי התנהגות בפרודקשן. 4 שדות Airtable חדשים עדיין לא נוצרו ביד; פריסה בפועל ל-Render **לא אומתה** (אין גישת dashboard/egress מה-sandbox). ראו פירוט: F17 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — branch `claude/new-session-be1ckb`. **F17 Decision Hub Stage 2 (Smart Trust Layer) — קוד הושלם**, אישור הבעלים בכפוף לתנאי: AI Conflict Detection הוא Lazy+Cached, לא Eager — לא רץ ב-ingest, רק בפתיחת/Refresh של `/decision status`, מוגבל ל-Claim Topic זהה + Trust>=T1, deduped לפי `event_pair_hash`, מוגבל ל-5 קריאות Claude חדשות לריצה. קובץ חדש `decision_confidence.py`: `calc_confidence()` (ממוצע משוקלל של Trust מינוס קנס קונפליקטים/חסר, clamped 0-1), `detect_conflicts_ai_lazy()`, `detect_missing_evidence()` (template-based, לא LLM), `build_evidence_summary()`. מוזרק ל-`_format_decision_card()` ב-`cmd_decision.py` (אין `get_decision()` במערכת — נקודת החיווט הקיימת). 3 סטיות מהטקסט המילולי של הספק תועדו (ראו F17 למטה) — בעיקר: מיקום הקובץ (root, לא `core/`), `REQUIRED_EVIDENCE` ממופה על `DecisionDomain` הקיים במקום "decision_type" לא-מוגדר, ונקודת החיווט (`_format_decision_card` במקום `get_decision()`). 25/25 self-tests עוברים (`test_decision_confidence.py`); 33/33 Stage 1 ללא רגרסיה. 4 שדות Airtable חדשים (`Evidence Ids`/`Evidence Summary`/`Confidence Score`/`Missing Evidence`) **לא נוצרו עדיין ביד ב-Airtable חי** — `airtable_patch()` משמיט אותם בשקט עד אז; תצוגת הטלגרם תקינה בכל מקרה (חישוב in-memory). דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל. **🟡 CODE DONE — לא מאומת בפרודקשן.** ראו פירוט: F17 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — branch `claude/new-session-be1ckb`. **C60 Tool Context Awareness — קוד הושלם** לפי `SPEC_C59_Tool_Context_Awareness.md` (אישור הבעלים דרך `AskUserQuestion`: "Yes, implement now"; ⚠️ הספק תייג עצמו "C59" — מתנגש עם C59 הקיים (Trust Layer, PR #151) — תויג מחדש **C60**): `last_tool_result` נשמר ב-session אחרי כל tool dispatch אמיתי, מוזרק ל-system prompt כ-"🔧 הקשר כלים" (TTL 5 דקות), ו-`resolve_context_pronouns()` מחליף כינויי הצבעה עבריים בהתייחסות מפורשת לפני ה-Router. 3 סטיות מהספק תועדו ומומשו (ראו C60 ב-`CHANGE_CONTROL_LOG.md`) — בעיקר: חוזה tool_result האמיתי (C53-A: `{ok,tool,external_id,evidence,user_message}`) שונה מהשדות שהספק הניח (`id`/`record_id`/`url`/`drive_url`). 40/40 self-tests עוברים. **🟡 CODE DONE — לא מאומת בפרודקשן** (§10 פריט 7 בספק — "העלה קובץ → 'תעלה לדסישנס' → BOSS זוכר" — פתוח עד בדיקת לייב). ראו פירוט: `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `b289ab6` (אומת, GitHub MCP `pull_request_read` + `git log`). **PR #151 מוזג** — Decision Hub Stage 1 (Trust Layer): `gate_trust` ב-`decision_pipeline.py` ממומש במלואו (Authority×Medium×Verify, Claim Topic אוטומטי, Supersedes בטוח) לפי `SPEC_Decision_Hub_Stage1_Trust_Rev2.md`. 9 סטיות מהטקסט המילולי של הספק תועדו ומומשו (ראו N13 למטה) — בעיקר: `VerifierPort` dict-לא-object, `decision["id"]` חסר (הוזרק כ-`event["_decision_id"]`), tags אנגלית-לא-קיימת (נעשה שימוש בקבוע עברי קיים + 2 קבועים חדשים **לא מאומתים מול Airtable חי**), `_has_keyword_conflict` מוגדר ב-spec אך לא יושם (stub). 33/33 self-tests עוברים (`test_decision_trust.py`). דגל `FEATURE_DECISION_HUB` כבוי כברירת מחדל; §10 פריט 11 בספק (T0 אמיתי→user_flag בטלגרם) עדיין לא אומת בפרודקשן. ראו פירוט: N13 למטה, `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `d6b6bc7` (אומת, GitHub MCP `pull_request_read` + `git log`). **PR #150 מוזג** — C58 Universal Sessions: `session_store.py` כותב/קורא מ-`Tables.SESSIONS` (טבלה אמיתית, `tblHLfE24lTkVUhz0`) במקום `Tables.LEAD_SESSIONS` (טבלה שלא קיימת בפועל — הייתה 403 בכל כתיבה). 4 סטיות מהספק תועדו ומומשו במקום הטקסט המילולי (ראו C58 למטה). 36/36 self-tests עברו במיזוג (כולל תיקון באג קדם-קיים ב-mock שהיה מסתיר כשלי DB-sync). סעיף 7 בספק (רשומה אמיתית ב-Sessions ב-Airtable חי) עדיין לא אומת בפרודקשן. ראו פירוט: C58 למטה (Sprint 19/06/2026), `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `1d08402` (אומת, `git fetch origin main` + `git merge-base --is-ancestor`). **PR #149 מוזג** — C57 Agent Tool Awareness (commit `cc6142b`): דיכוי `text_block` מוקדם שנוצר באותה תשובה עם `tool_use` (`app.py`) + כלל 7 ב-`core_knowledge.py`. ⚠️ הספק החיצוני (`SPEC_C54_Agent_Tool_Awareness.md`) קרא לזה "C54" — מתנגש עם C54 הקיים (Business Memory /update, PR #85); תויג מחדש **C57** בתיעוד (הלוג בקוד עצמו עדיין `[C54]`, לא שונה). ראו פירוט: C57 למעלה (Sprint 19/06/2026), `CHANGE_CONTROL_LOG.md`.

עודכן (קודם): 25/06/2026 — main = `483851f` (אומת, `git merge-base --is-ancestor` + `git log`). **PR #147 מוזג** — Decision Hub Stage 0.5 (File/Voice Precedence Routing) ו-Stage 0.6 (File Context Reference) הושלמו והתחברו ל-pipeline החי מאחורי `FEATURE_DECISION_HUB` (כבוי כברירת מחדל); BUG-017 (`session_store._sync_to_db` קרא את חוזה ה-dict של `airtable_add`/`airtable_update` כ-string) ו-BUG-B (LeadSessions תחת schema governance) תוקנו; `MODULE_RULES.md` קיבל חוקים 7-10 ו-12 (Ports / Tool↔Gate / Input Precedence / Raw-First / Domain-Agnostic Core); נוסף `docs/governance/PLANNING_GATE.md`. **N13 (Decision Hub) נוסף לראשונה לקובץ זה** — ראו למטה; לא היה מתועד כאן לפני כן. ראו פירוט: N13, `CHANGE_CONTROL_LOG.md`, `BUG_AUDIT_LOG.md`.

עודכן (קודם): 23/06/2026 (מאוחר יותר) — main = `f737f61` (אומת). **F13 (TenantConfig + Provider Interfaces) סומן במפורש כ-DEAD CODE** — אזהרת "אין לחבר" הוספה מיד אחרי כותרת הסעיף (קוד קיים, אפס imports מקוד חי, כפילות עם `TenantConfig` ב-`tenant_provisioner.py`, הכרעת F12-מול-F13 עדיין לא בוצעה). ראו SPEC-C / PR בענף `claude/fix-f13-status-docs`.

עודכן (קודם): 23/06/2026 (מאוחר) — main = `d1c48a1` (אומת). **ניקוי ענפי `claude/*` ישנים** —
בוצע audit מלא של 29+8 ענפים לא ממוזגים מול `main` (ancestry/diff/content, לא רק
תאריך/שם): 34 ענפים נמחקו בפועל (ממוזגים בפועל / זהים תוכן ל-main / orphan history /
היסטוריית collision שנפתרה כבר בעבר לטובת גרסה אחרת). שני ענפים הכילו עבודה אמיתית
שחולצה לפני המחיקה — **N12** (למטה) ותיקון תיעוד C56 (PR #112). מסמך audit ארכיטקטוני
(`APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md`, 257 שורות, ללא קוד) שוחזר ונשמר ישירות ל-main
(commit `783a680`) לפני שהענף המקורי נמחק. בנוסף: **BUG-014** (`core/anti_hallucination.py`
— Drive נוסף ל-NO-TOOL-EVIDENCE gate, PR #115) ו-**תיקון תיעוד ל-BUG-011** (תועד "לא
ממוזג" בטעות, PR #110 מוזג בפועל ב-`a4c8f27`, PR #116).

עודכן (קודם): 23/06/2026 — main = `29b009e` (אומת). **C56 (Approval Policy: Emergency Window + OTP + Policy Gate) — תועד כ"לא ממוזג" ב-`BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` ולא היה ב-ROADMAP בכלל, אבל בפועל מוזג ל-`main` כבר ב-17/06/2026** (PR #69, merge commit `4e933b0`, מאומת דרך `gh pr view 69` + `git merge-base --is-ancestor`) — נוסף ל-ROADMAP, תוקן בשני המסמכים האחרים. דגל `EMERGENCY_WINDOW` נשאר כבוי — אין שינוי התנהגות בפרודקשן.

עודכן (קודם): 22/06/2026 — main = `24237e6` (אומת, PR #96/#97/#98/#99/#100/#101/#103/#104 ממוזגים). **F16 (Media Layer) הושלם** — כל שבעת ה-batches (א-ז) קיימים ומחוברים ל-pipeline החי, מאחורי דגלים כבויים כברירת מחדל (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`). ⚠️ ה-spec החיצוני קרא לפיצ'ר "F12" ואז "F09" — שני ה-IDs תפוסים (F12=Model Provider Adapter, F09=Lead Qualifier Wire-up); הוקצה F16 כדי למנוע התנגשות בסטייל C20/C21/F14/F15. **N07 (Schema Governance) הושלם** — `tools/schema_governance.py` (PR #101), standalone read-only drift detector, ראו פירוט למטה. **N08 (CI/CD) ו-N09 (Monitoring/Alerting) הושלמו** (PR #103/#104) — תוקנו כ-PLANNED בטעות, ראו פירוט למטה. **N11 (Finance Pulse wiring) התגלה כממוזג מ-PR #77 קודם** — תועד כ-PLANNED בטעות, תוקן.

עודכן (קודם): 20/06/2026 — main = `62eddda` (אומת). PR #85/#86/#87/#88/#89 ממוזגים (ראה C54/C55 למטה + CHANGE_CONTROL_LOG.md). F13 (TenantConfig + Provider Interfaces) — קוד נכתב ומוזג (PR #87), **לא מחובר ל-pipeline**; ⚠️ חפיפה עם F12 עדיין לא הוכרעה, אל תחבר ל-pipeline לפני הכרעה. `contact_merge.py` (PR #88) — כלי CLI עצמאי למיזוג אנשי קשר, לא ב-ROADMAP (admin utility, לא feature). נוספו F14 (Contact Gate: find_or_create_contact) ו-F15 (crm.py → airtable_gateway write path migration) — ⚠️ הספק ביקש F12/F13, אך שני ה-IDs האלה תפוסים (F12=Model Provider Adapter, F13=TenantConfig); הוקצו F14/F15 כדי למנוע התנגשות בסטייל C20/C21.

---

## עיקרון ניהול
- **C** = Completed — הושלם ובפרודקשן
- **W** = Completed (World 2 sprint) — נוסף במהלך Lead Flow Audit
- **N** = Next — הבא בתור, מסודר לפי תלויות
- **F** = Future — מתוכנן, אין תאריך

כל פיצ'ר חדש נרשם כאן לפני שנוגעים בקוד.
כל batch מתחיל מקריאת ROADMAP — לא מזיכרון.

---

## 🧭 BOSS Core Harness — Program Map

**עבר ל-`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1** (עודכן 09/08/2026) —
זהו כעת המקור הקנוני היחיד למצב תכניות-הליבה חוצות-התוכנית (Turn Coordinator
TC1-TC10, ActionGateway/Approval Runtime, RP4/RP5 Evidence Finalizer, A32,
F52, F14/Entity Resolution, Agent Cost). `ROADMAP.md` **אינו** מחזיק יותר
טבלת current-state מקבילה לתכניות האלה — רק milestones/backlog ספציפיים
לכל C/N/F item, כפי שהיה מאז ומתמיד. לסטטוס עדכני, ל-Master Program Map
המלא, ל-Target Canonical Harness Authority Chain, ולסדר ה-Next Gates — קרא
`BOSS_UNIFIED_MASTER_PLAN.md` §3.5.1-§3.5.3.

---

## C — הושלם

### CORE — תשתית
| ID | שם | קבצים |
|----|----|--------|
| C01 | Identity + Roles | identity.py, tool_registry.py, context.py |
| C02 | Router — Intent / Domain / Risk | core/router/ (7 קבצים) |
| C03 | Anti-Hallucination | core/anti_hallucination.py |
| C04 | Feature Flags | feature_flags.py |
| C05 | Action Validator | action_validator.py |
| C06 | Event Bus + Approval Flow | event_bus.py |
| C07 | Domain Prompts (לפי דומיין) | domain_prompts.py |
| C08 | Memory Store (שיחה קצרת-טווח, TTL) | memory_store.py |
| C09 | Circuit Breaker + Rate Limiter | circuit_breaker.py, rate_limiter.py |

### Lead System
| ID | שם | קבצים | הערה |
|----|----|----|------|
| C12 | Lead Events (audit log) | core/lead_events.py | |
| C13 | Shared Memory (תובנות עסקיות לפי דומיין) | core/shared_memory.py | **SUPERSEDED (עודכן 16/08/2026, Owner Truth-Reset) — הקובץ ההיסטורי `core/shared_memory.py` לא קיים יותר על `main` (מאומת: `ls` נכשל). היכולת לא נעלמה, פוצלה: Business Memory search/schema דרך dispatcher/schema/validator, ו-`core/lead_events.py` קורא אירועי business-memory לפי domain. תיעוד supersession — לא re-open.** |
| ~~C14~~ | ~~Lead Scoring~~ | ~~lead_scoring.py~~ | **הוסר — zombie file; scoring consolidated ל-lead_capture.py (N02/N03)** |

### CRM + Storage
| ID | שם | קבצים | הערה |
|----|----|--------|------|
| C16 | CRM Repository (get_lead / save_lead) | crm.py | |
| C17 | Airtable Search + Schema Self-Sync | airtable_tools.py | |
| C18 | Store Protocol (LeadStore / EventStore) | core/stores/base.py | **⚠️ PARTIAL / DEFERRED TO STORAGE DECOUPLING — לא לסגור (עודכן 16/08/2026, Owner Truth-Reset).** `core/stores/base.py` לא קיים על `main` (מאומת: `ls` נכשל) בצורה ההיסטורית המבוקשת. קיים `AirtableStorageProvider` צר יותר ב-`providers/airtable_shim.py`, אבל `crm.py`/`lead_capture.py`/`lead_memory.py`/`core/lead_events.py` עדיין מכילים ידע Airtable-ספציפי בלוגיקה עסקית. **החלטת ארכיטקטורה של הבעלים:** לא לבנות store ייעודי ל-Leads בלבד רק כדי לסגור את הסעיף — C18 מתמזג לתוך תכנית storage-decoupling רחבה יותר (Leads/Tasks/Contacts/Deals/Ventures/Marketing Demands וכו', repository/provider contracts). "הסרת Airtable מהקוד" = הסרת ידע Airtable מלוגיקה עסקית, לא בהכרח הסרת Airtable כ-provider. |

### App Layer
| ID | שם | קבצים |
|----|----|--------|
| C19 | app.py — 4 Hooks (H1–H4) | app.py |
| C20 | Scheduler (jobs קיימים) | scheduler.py |
| C21 | Daily Digest | daily_digest.py |

### חוזה (Contract Fix)
| ID | שם | מה תוקן |
|----|----|---------|
| C22 | feature_flags — is_enabled() alias | 3 קבצים שיובאו בשם לא קיים |
| C23 | config — תיעוד input provider בלבד | מנע מקור אמת כפול עם domain_router |
| C24 | lead_qualifier — detect_domain() | get_domain(channel,sender) לא קיים |

### Stabilization Sprint — 07/06/2026
| ID | שם | מה תוקן | קבצים |
|----|----|---------| ------|
| C25 | Google Tools merge conflict | SyntaxError שורה 21 — נפתר | tools/google_tools.py |
| C26 | lead_qualifier TypeError | get_domain signature mismatch — תוקן | lead_qualifier.py |
| C27 | Event Bus fail-closed | confirm() מחזיר הצלחה רק אם handler רץ בפועל | event_bus.py |
| C28 | email_inbound honest stub | ImportError → mock הוסר; stub כנה | email_inbound.py |
| C29 | TMA approval stubs | TODO הוחלף ב-coming_soon / רשימה ריקה | tma_api.py |
| C30 | tool_registry sync | כלים מיושרים: schemas / validator / registry / dispatcher | tool_registry.py, schemas.py |
| C31 | Airtable shim | תיקון imports עקביים לכל מודולי עזר | airtable_tools.py |
| C32 | Twilio signature validation | WhatsApp webhook מאמת חתימה | app.py |
| C33 | Emergency Stop persistence | flag נשמר ב-restart | feature_flags.py |
| C34 | Mock data removed | דוחות מציגים כשלים אמיתיים | daily_digest.py, workers |
| C35 | Approval subscribers x4 | send_email_reply, send_followup, send_recovery, send_bounce | event_bus.py |
| C36 | Approval UX honest | הצלחה מוצגת רק אחרי פעולה אמיתית | app.py |
| C37 | Payment Reminder fix | self-test עובר (commit 0744ce9) | payment_reminder.py |
| C38 | WhatsApp outbound honest stub | לא מעמיד פנים — מחזיר stub כנה | app.py / whatsapp tools |
| C39 | TMA CORS + auth 401 | CORS origin נוסף ל-Render env; 401 נפתר | tma_api.py, Render env |
| C40 | Golden Path Approval Gate | TMA write endpoints now require approval before Airtable writes: POST /api/projects, PATCH /api/leads/<lead_id>/status, POST /api/followup. Writes execute only after approve; reject does not write; receipt returned after execution; audit runs only after successful execution. | tma_api.py (commit 4e5d00d on origin/approval-gate; supersedes local f3172ba) |

### World 2 — Lead Flow Sprint (08/06/2026)
| ID | שם | מה נעשה | קבצים | commit |
|----|----|---------|--------|--------|
| W0 | WhatsApp Lead Capture | ליד נכנס ← נוצר/מתעדכן Leads ב-Airtable | lead_capture.py, app.py | 2b861bd |
| W1 | Airtable Schema Fix (N01) | LeadFields.SCORE/TIER + schema_intelligence sync | airtable_schema.py, schema_intelligence.py, tma_api.py, daily_digest.py | f095036 |
| W1b | W1 Completion — Score/Next Followup case fix | LeadFields.SCORE "score"→"Score"; FIELD_ALIASES aligned; schema_cache.json updated | airtable_schema.py, schema_cache.json, schema_intelligence.py, lead_memory.py, tools/airtable_tools.py | a6b471c |
| W2 | Airtable Gateway — single write path | tools/airtable_gateway.py: normalize→validate→audit→httpx; tma/agent/lead_capture migrated; 22-test regression suite | tools/airtable_gateway.py, tma_api.py, airtable_tools.py, lead_capture.py, app.py | b43357e |

### Sprint 16/06/2026
| ID | שם | מה נעשה | קבצים | PR |
|----|----|---------|--------|-----|
| C41 | LLM Fallback Handlers | APIStatusError + APITimeoutError → flag-gated OpenAI fallback או Hebrew error נקי | app.py | — |
| C42 | FEATURE_LLM_FALLBACK flag | default=False, registry comment | feature_flags.py | — |
| C43 | Hebrew Mojibake fix | כל Hebrew error strings תוקנו ב-byte level | app.py | — |
| C44 | ⏳ thinking indicator restored | C1 control char → ⏳ תקין | app.py | — |
| C45 | BossCheckin duplicate block removed | TS2451/TS1308 Vercel build errors נפתרו | tma-frontend/ | PR #59 + UX follow-up |
| C46 | Furniture WhatsApp Funnel | Deterministic flow + app.py intercept — rebased on main | app.py | PR #61 |
| C47 | Game today task filtering | Roadmap_Tasks filtered by Due_Date ≤ Today + Owner | tma_api.py | PR #62 |
| C48 | Coins Log schema fix + approval concurrency hardening | Note→Notes תוקן; approval 3-state atomic hardened | tma_api.py | PR #63 |
| C49 | Ops Docs | README, CHANGELOG, RUNBOOK, DEPLOYMENT נוצרו | docs/, root | PR #60 |
| C50 | F12 Model Provider Adapter | תועד כ-Future item ב-ROADMAP | ROADMAP.md | — |
| C51 | Approval Concurrency Regression Test | test ל-3-state approval flow: pending→processing→approved/failed + double approve guard | test_approval_concurrency.py | branch furniture-funnel-clean |
| C52 | Customer Output Gateway (COG) | נקודת כניסה יחידה לכל שליחה ללקוח — Financial Gate (shadow mode), ESCALATE לא BLOCK, Secondary Guard ב-Send Adapters | core/output_gateway.py, core/financial_gate.py, tools/whatsapp_adapter.py | PR #70 |

### Sprint 18/06/2026
| ID | שם | מה נעשה | קבצים | PR |
|----|----|---------|--------|-----|
| C53 | Screen Filter Gateway | `SCREEN_CONFIGS` + `_build_formula()` — Gateway מבצע, Screen מחליט. `get_leads()` (`GET /api/leads`) תומך ב-`?view=active\|monitoring\|all` + `available_views` בתשובה; view לא חוקי → fallback ל-`active` (לא 400). `_get_project_cards()` ו-`get_project_dashboard()` חוברו ל-`project_hub_kpi` config לספירת לידים אחידה. תשתית additive ל-multi-tenant עתידי (`finance_pulse`, `assets_overview`, `activity_feed` configs מוכנים בזמן הכתיבה; `finance_pulse` חובר בפועל ב-PR #77, ראו O4 למטה) | tma_api.py בלבד (commit `5b07088`) | **PR #75 — ממוזג ל-`main`** (merge commit `6218155`, 18/06/2026) |

### Sprint 19/06/2026
| ID | שם | מה נעשה | קבצים | PR |
|----|----|---------|--------|-----|
| O4 | Finance Pulse — English schema + Screen Filter Gateway wiring | `Tables.PAYMENTS`/`EXPENSES` ו-`PaymentFields`/`ExpenseFields`/`PaymentStatus` עברו לשמות השדות האנגליים החיים ב-Airtable (מיגרציה ידנית בוצעה מראש). `finance_pulse()` עבר דרך `SCREEN_CONFIGS["finance_pulse"]` + `_build_formula()`, כמו `/api/leads`. נוסף `?view=active\|overdue\|all` + `available_views`. שני gaps קיימים תועדו ב-CHANGELOG.md ולא נסגרו במכוון (מחוץ ל-scope): `crm.py`'s `PaymentFields.CONTACT/NOTES` מצביעים על שדות שלא קיימים בטבלת Payments החיה; case-mismatch ב-`_build_formula()` לדומיין Payments/Expenses | airtable_schema.py, tma_api.py, smoke_tests.py | **PR #77 — ממוזג ל-`main`** (merge commit `0608798`, commits `f7d7e4f`+`daab73e`) |
| C53-A | Structured tool results + verify_execution dict contract | טפסי tool-result עברו מ-string חופשי ל-contract structured: `{ok, tool, external_id, evidence, user_message}`. מוחל על `airtable_add`/`airtable_update`/`gmail_draft`/`gmail_send_draft`/`calendar_create_event`. `core/anti_hallucination.verify_execution()` עכשיו בודק `ok`+`external_id`/evidence ייעודי per-tool (לא substring matching). `guards/rate_limiter.validate_tool_output()` משמר dict (לא הופך ל-string). `_handle_approval_callback` ב-app.py בודק `verify_execution()` אחרי dispatch ומודיע למשתמש על כשל ביצוע בלי לדווח הצלחה כוזבת. | app.py, core/anti_hallucination.py, guards/rate_limiter.py, tools/airtable_tools.py, tools/google_tools.py, tools/schemas.py | **PR #79 — ממוזג ל-`main`** (merge commit `be65801`, commits `ffa3afc`+`3a34529`) |
| A32 / C53-A Hotfix | identity-based NO-TOOL-EVIDENCE enforcement + app.py crash fix | PR #79's dict contract לא נגע ב-`app.py` — קריאה ישירה (לא approval) ל-4/5 tools קרסה (`KeyError: slice(...)`), ו-approval callback דיווח הצלחה בלי לבדוק `verify_execution()`. תוקן עם helper `_tool_user_message()` בשתי הנקודות. בנוסף חוּזק A32's NO-TOOL-EVIDENCE gate ב-`core/anti_hallucination.py` — evidence נבדק לפי tool identity+ok per-claim-category, לא keyword guessing; `_NO_TOOL_EVIDENCE_FALLBACK` ספציפי יותר. נוסף `test_a32_enforcement.py` (end-to-end run_agent). | app.py, core/anti_hallucination.py, test_a32_enforcement.py, test_c53a.py | **PR #80 — ממוזג ל-`main`** (merge commit `7496628`, commit `42dd137`) |
| C54 | Business Memory /update command | פקודת `/update` לboss_hq — שמירת הקשר עסקי שקיים "בראש" (פגישות, החלטות, שיחות). tenant isolation, TTL, `/cancel` support, context injection cap. | cmd_update.py, app.py, context.py | **PR #85 — ממוזג ל-`main`** |
| C55 | Origin Lead backlink (Lead→Contact + Lead→Deal) | שדה "Origin Lead" (linked record) נוסף ל-Contacts (`fldGE1seCyCdWJGCO`) ו-Deals (`fldoobGq4PS78C0Em`). Contact/Deal שנוצרו מליד מקושרים חזרה לרשומת הליד המקורית. | airtable_schema.py, crm.py, lead_conversion.py | **PR #86 — ממוזג ל-`main`** |
| C56 | Approval Policy: Emergency Window + OTP + Policy Gate | שכבת אישור מדורגת לפי סיכון (Low/Medium/High/Critical) × פלטפורמה (mobile/desktop). Low תמיד מותר; Medium מהטלפון דורש אישור כפול; High מהטלפון דורש Emergency Window פעיל + OTP; Critical לעולם לא מהטלפון ודורש OTP בכל מצב. `web` מסווג כ-mobile (fail-closed). ⚠️ לא תועד ב-ROADMAP עד 23/06/2026 — `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` תיעדו "Merged: לא" בזמן שהקוד היה כבר מוזג בפועל; תוקן. `EMERGENCY_WINDOW` flag כבוי כברירת מחדל — אין שינוי התנהגות בפרודקשן. | core/emergency_window.py, core/otp.py, tma_api.py, tma-frontend/src/api.ts | **PR #69 — ממוזג ל-`main`** (merge commit `4e933b0`, 17/06/2026) |
| C57 | Agent Tool Awareness — דיכוי text_block מוקדם לצד tool_use | Claude מחזיר לעיתים text+tool_use באותה תשובה — ה-text נכתב לפני שראה תוצאת כלי, נשלח למשתמש ומבלבל ("לא הבנתי" לצד כלי שרץ בהצלחה). תיקון כפול: (1) `app.py` — אם `tool_uses and text_blocks` באותה response, ה-text מבוטל (`text_blocks = []`) ולוג `[C54] Suppressed premature text_block...` נכתב; הלולאה ממשיכה לתוצאה האמיתית ב-turn הבא. (2) `core_knowledge.py` — כלל 7 חדש ב-`_NEVER_FAKE_CONTROL`: לא לכלול טקסט הסבר/הבהרה באותה תשובה עם הפעלת כלי. ⚠️ **הערת מספור:** מסמך המקור (`SPEC_C54_Agent_Tool_Awareness.md`) קרא לזה "C54" — מתנגש עם C54 הקיים מעלה (Business Memory /update, PR #85). לוג הקוד עצמו עדיין מתויג `[C54]` (string בקוד, לא שונה כדי לא לגעת בלוג production ללא צורך) — אך **בתיעוד** (ROADMAP/CHANGE_CONTROL/BUG_AUDIT) המספור הוא **C57**. | app.py, core_knowledge.py | **PR #149 — ממוזג ל-`main`** (merge commit `1d08402`, commit `cc6142b`) |
| C58 | Universal Sessions — Sessions table (לא LeadSessions) | `LeadSessions` לא קיימת בפועל ב-Airtable (הייתה גורמת ל-403 בכל כתיבה); הוחלפה ב-`Tables.SESSIONS` (`tblHLfE24lTkVUhz0`, טבלה קיימת) עם schema גנרי משותף לכל הדומיינים: `Context Type` (select) + `State JSON` (כל ה-state הקיים — domain/step/answers/done/drop_off_step/score/tier/last_uploaded_file — בשדה טקסט יחיד, אפס אובדן מידע) + שדות `Linked *` אופציונליים. `context_type="lead"` ברירת מחדל — תאימות לאחור מלאה לזרימת lead_qualifier הקיימת. `Tables.LEAD_SESSIONS` הוצא משימוש (deprecated, לא נמחק מהקוד). ⚠️ **4 סטיות מהספק (`SPEC_C58_Universal_Sessions.md`), כולן מתועדות ב-commit ו-`CHANGE_CONTROL_LOG.md`:** (1) `external_id` נקרא ישירות מ-`result.get("external_id", "")` לפי חוזה C53-A האמיתי, לא שרשרת fallback שגויה שהספק הציע; (2) `last_uploaded_file` נוסף ל-State JSON (הספק השמיט אותו, בסתירה לעקרון "אפס אובדן מידע" שהוא עצמו הצהיר); (3) `SF.LINKED_MEDIA_FILE` מקושר רק כש-`last_uploaded_file.type == "drive_file"` (Media Files record) — לא כש-`type == "inbox_file"` (Decision Inbox record, טבלה אחרת; קישור היה גורם ל-`INVALID_RECORD_ID`); (4) `_delete_from_db` משמר את כל ה-state הקודם ב-tombstone (`done`/`deleted=True` בתוך State JSON הקיים), לא מוחק אותו כמו שהספק הציע. תוקן גם באג קדם-קיים (לא קשור ל-C58): mock ה-self-tests רשם `sys.modules["airtable_tools"]` במקום `sys.modules["tools.airtable_tools"]` — היה גורם לכל בדיקות ה-DB-sync "לעבור" בלי לבדוק כלום (ImportError נתפס בשקט). | airtable_schema.py, session_store.py | 🟡 CODE DONE — לא נוצרה PR; ממתין לאימות רשומה אמיתית ב-Sessions בפרודקשן |

---

## N — הבא בתור

**סדר ביצוע קשיח — כל N תלוי ב-N שלפניו.**

### C81-FU — ✅ סגור (אומת 19/07/2026) — Recovery: אמת משלוח לפני סימון הושלם
**עדיפות:** ~~🔴 דחוף~~ (היה stale — כבר פתור)
**בעיה (היסטורי):** `recovery_count` גדל גם כשהלקוח לא קיבל את ההודעה בפועל.
**מצב בפועל:** `tools/approval_actions.py::send_recovery()` (C53 FIX-1) מחזיר `ok=False` אלא אם `owner_delivery.delivery_success` אומת; `recovery_count` אינו נכתב כלל בנתיב הזה (בכוונה, בניגוד ל-`send_followup()`). `test_c81_recovery_truth.py` (4 בדיקות) מכסה זאת — תוקן ב-19/07/2026 חוסר `__main__` runner שגרם ל-0 assertions בפועל בהרצה ישירה (`python3 test_c81_recovery_truth.py`), אותה משפחת באג כמו BUG-049.
**קובץ ראשי:** `tools/approval_actions.py` (לא scheduler/followup_engine כפי שנרשם במקור)

### C82-FU — ✅ סגור (אומת 19/07/2026) — EMERGENCY_STOP_AUTOMATION: gate מרכזי לכל עבודות scheduler
**עדיפות:** ~~🔴 דחוף~~ (היה stale — כבר פתור)
**בעיה (היסטורי):** ה-flag נאכף רק ב-followup וב-payment reminders; lead recovery ושאר jobs לא נבדקים.
**מצב בפועל:** `scheduler.py::_automation_guard()` עוטף היום **כל** רישום `.do(...)` בקובץ (אומת עם `grep -n "\.do(" scheduler.py | grep -v _automation_guard` — 0 תוצאות), לא רק followup/payment. `test_c86_scheduler_emergency_matrix.py::test_emergency_stop_matrix_blocks_every_registered_scheduler_job` מכסה את זה במפורש ורץ תקין.
**קובץ ראשי:** `scheduler.py`

### C83 — Single Policy Source: הפרדת requires_approval מ-blocked_by_emergency
**עדיפות:** ✅ סגור
**הערה:** מאומת בקוד 06/07/2026 — event_bus.ACTIONS_REQUIRING_APPROVAL הוא alias ל-tool_registry, לא רשימה עצמאית.
**בעיה (היסטורי):** `TOOLS_REQUIRING_APPROVAL` ו-`ToolMeta.requires_approval` סותרים (`crm_mark_payment_paid` חסר).
**פעולה (היסטורי):** לגזור רשימות מה-registry; להפריד בין שני המושגים; consistency test ב-CI.
**קובץ ראשי:** tool_registry / action_validator

### C84 — ✅ סגור (אומת 20/07/2026) — TMA Approvals: TTL + freshness check
**עדיפות:** ~~🟡 גבוה~~ (היה stale — כבר merged)
**בעיה (היסטורי):** רשומת `PENDING` יכולה להישאר פעילה ללא הגבלת זמן.
**מצב בפועל:** ממוזג ל-`main` — `git merge-base --is-ancestor c5c5a97 origin/main` מאשר (PR #408). `_claim_and_execute_approval()` ב-`tma_api.py` בודקת `time.time() - ActionContract.created_at` מול `_TMA_APPROVAL_TTL_SECONDS` (24h) לפני `ActionGateway.approve()`; contract שחצה את החלון נדחה (`reject()`, מאומת) והתגובה `ok=False status_code=410`. מכסה גם את `act_on_approval()` וגם `bulk_approve()`. Approvals projection מסונכרן לדחייה גם כן.
**קובץ ראשי:** `tma_api.py`
**בדיקות:** `test_c84_tma_approval_ttl.py` (44 checks) + עדכון תואם ל-3 קבצי test קיימים.
**Production verification:** לא עדיין — קוד merged, עדיין לא נצפה על contract אמיתי בפרודקשן.

### C85 — Structural test: כל request_approval(action=...) מחזיק subscriber
**עדיפות:** 🟡 גבוה (זול ובעל ערך)
**פעולה:** test שרץ ב-CI, מוודא שאין action ללא handler.
**קובץ ראשי:** tests/

### C86 — ✅ סגור (אומת 20/07/2026) — Emergency Stop: coverage מטריציוני לכל scheduler jobs
**עדיפות:** ~~🟡 גבוה~~ (היה stale — כבר קיים)
**פעולה (היסטורי):** בדיקות: followup, recovery, payment וכל job מול flag פעיל.
**מצב בפועל:** `test_c86_scheduler_emergency_matrix.py::test_emergency_stop_matrix_blocks_every_registered_scheduler_job` כבר קיים ועובר — תועד ב-C82-FU (19/07/2026) אבל הפריט הזה עצמו לא סומן סגור בעדכון ההוא.
**קובץ ראשי:** tests/

### C87 — Unified Approval Store: החלטת ארכיטקטורה לפני מימוש
**עדיפות:** 🟠 תכנון — **לא חסום יותר** (היה stale: C81-FU/C82-FU/C83 ששלושתם מתועדים כ"חוסמים" כאן — כולם ✅ סגורים, אומת 20/07/2026). ממתין רק להחלטת owner, אין חסם טכני.
**בעיה:** כמה stores עצמאיים בזיכרון וב-Airtable.
**פעולה:** להכריע אם משתמשים בטבלת `Approvals` הקיימת, ואז לקדם `SPEC_LL13`.
**הערה:** אין ליצור מנגנון חמישי לפני ההחלטה.

### C88 — Secondary Guard: חסום כברירת מחדל
**עדיפות:** 🟠 בינוני
**בעיה:** נכשל פתוח ב-staging.
**פעולה:** fail-closed כברירת מחדל; override מפורש לטסטים בלבד.

---

### C89 — ✅ קוד הושלם ומוזג (PR #203, `bb81e6c`) — Stage 3: Capture Policy — Tiered Auto-Write (טקסט)
**עדיפות:** 🔴 גבוה — flag כבוי, ממתין להפעלה מפורשת + production verification לפני C90+
**Branch:** מוזג מ-`claude/session-duplication-claimgate-gnkfiy`, ענף נמחק
**Feature Flag:** `FEATURE_AUTO_CAPTURE` (כבוי כברירת מחדל — ללא שינוי התנהגות בפרודקשן)
**תלות:** Action Gateway (Stage B) פעיל + SB-01–SB-04 סגורים. ✅ עברו.
**בעיה שנפתרה:** LCH batch auto-write לא היה בטוח — parser בלבל שולח/ליד, פלט כלי, ייצוא WhatsApp. ראה live test 02/07/2026.
**מה נבנה:** `classify_ingress() → IngressClassification` — מדיניות מדורגת:
- Tier 1 (SIMPLE_CAPTURE): שם+טלפון ברור → כתיבה אוטומטית דרך Gateway, בלי preview (כש-flag דלוק).
- Tier 2 (CLEAN_BATCH): כמה שורות high-confidence → כתיבה אוטומטית + סיכום.
- Tier 3 (MIXED_BATCH): ברורים נכתבים, עמומים → needs_review.
- Tier 4 (EXPORT/TABLE/LOG): אפס writes — תמיד, לא משנה flag.
- Tier 5 (UNKNOWN_USEFUL): ממשיך ל-agent, לא יוצר Leads/Tasks.
**עקרונות נעולים:** auto-write = additive-only (create בלבד, לא update/overwrite). כל tier עובר Gateway. Raw נשמר תמיד.
**קובץ ראשי:** `core/ingress_classifier.py` (חדש), `core/lead_candidate_handler.py`
**DoD:** ראה SPEC_Stage_3_Capture_Policy.md §7 — **קובץ זה לא קיים בפועל בריפו** (grep מאמת, 02/07/2026); reference תלוי באוויר, לא תוקן — ה-DoD המחייב עכשיו הוא BUG-051 (למטה) + `test_capture_router_wiring.py`.
**עדכון 04/07/2026 (BUG-061..065, PR #220–#227, כולם מוזגו):** כל הממצאים הפתוחים מ-QA ידני נסגרו: prefix-ביטויים דו-משמעיים (BUG-061), owner שאיבד role אחרי אישור (BUG-062), Session lookup fail-closed (BUG-063), hard markers ל-Tier 4 (טבלה/CSV/fixed-width/Airtable-status-output, BUG-064), ו-raw_ref/AgentObservation מחוברים בפועל (BUG-065, כולל hardening ב-PR #227 שמסיר `raw_ref=""` מילולי מכל נתיב קוד). **חשוב — לא לבלבל בין "קוד+טסטים מאומתים ב-sandbox" ל"production-verified":** `FEATURE_AUTO_CAPTURE` **עדיין כבוי** בפרודקשן; לא בוצעה הפעלה חיה ולא נאסף נתון `AgentObservation` אמיתי אחד. ראה BUG_AUDIT_LOG.md BUG-061 עד BUG-065.
**עדכון 05/07/2026 — סטטוס C89: ✅ CLOSED/VERIFIED עם `FEATURE_AUTO_CAPTURE=false` (החלטה מפורשת של הבעלים, לא production-verification במובן המקורי):**
כל הממצאים הידועים מ-QA ידני על C89 סגורים: IC ambiguous routing (BUG-IC-01/IC-01B), Sessions root (BUG-SESSIONS-ROOT), Gateway path/no direct dispatch, Preview pending approval, Approval identity Telegram+WhatsApp (BUG-C89-APPROVAL-IDENTITY), Existing lead update UX, Dedupe/idempotency, Tier 4 hard-precedence (BUG-C89-TIER4-PRECEDENCE), RAW-OBS (`test_c89_raw_obs.py`, 15/15 — מאומת מחדש 05/07/2026: raw_ref לעולם לא ריק בכל Tier כולל flag OFF/כשל כתיבה, AgentObservation `kind="capture_classification"` `contract_id=None` לכל קריאה, ללא תלות ב-ActionContract). **החלטה מפורשת:** `FEATURE_AUTO_CAPTURE` **נשאר כבוי בפרודקשן בכוונה** — זו לא "production verification" במובן המקורי של הסעיף הזה (הפעלת flag + מעקב AgentObservation על תעבורה אמיתית) אלא סגירה מודעת של ה-scope: קוד+טסטים מאומתים, הבעלים בחר שלא להפעיל. **התלות של C90/C91/C92/C93 ב"C89 production-verified" נחשבת כעת מסופקת תחת ההגדרה הזו** (C90 כבר נבנה ומוזג ממילא, ראה למטה).
**נותר (אם ירצו בעתיד production verification במובן המלא):** הפעלת `FEATURE_AUTO_CAPTURE` בפועל ב-Render + מעקב `AgentObservation` על תעבורה אמיתית — לא בוצע ולא מתוכנן כרגע.

**עדכון 02/07/2026 (BUG-051, `feature/capture-policy-stage-3`, טרם ממוזג) — Router-Integration:**
`handle_lead_candidate()` (LCH) רץ עד עכשיו ב-`app.py` שלב "1.45", **לפני** `route_request()` — Identity→Router→Context→Agent לא רץ בכלל לכל sender פנימי שנתפס כ-lead candidate; domain נקבע ע"י regex mirror פנימי (`_detect_domain`), לא ה-`domain_router` האמיתי. תוקן: `RouteDecision` קיבל 3 שדות אופציונליים (`capture_tier`/`capture_reason`/`raw_ref`, additive-only — אין טיפוס מקביל חדש), `core/router/capture_router.py` חדש עוטף את `classify_ingress()` הקיים (אין שכתוב, אין import לתשתית), `router.py` קורא לו כשלב חדש. `app.py`'s LCH call הועבר ל-**אחרי** ה-Router, עם `domain=resolved_route_domain` (LCH קיבל פרמטר `domain` אופציונלי חדש, תאימות לאחור מלאה). ראה BUG-051 ב-`BUG_AUDIT_LOG.md` לפירוט מלא כולל 3 סטיות מכוונות מהספק המקורי (capture_tier הוא observability בלבד לא gate; אין intent/confidence filter בשלב 4 — היה שובר capture עם intent בביטחון גבוה; LCH קיבל פרמטר domain חדש למרות שהספק ביקש "חתימה זהה"). 10/10 טסטים חדשים + 29/29 + 4/4 קיימים + כל 30 קבצי `test_*.py` בריפו — ירוק. לא ממוזג, לא נבדק מול Airtable/Gateway חי.

### C90 — ✅ קוד הושלם ומוזג ל-main (PR #228, `f585d9d`, merge commit `004fbf9`) — Stage 3.1: Capture Policy — קבצים מובנים (xlsx/csv)
**עדיפות:** 🟠 בינוני — **הוחלט לבנות עכשיו** למרות ש-C89 עדיין לא production-verified (ראו סעיף C89 למעלה): C90 לא נוגע כלל בנתיב auto-write (כל שורה עוברת דרך אותו Approval gate כמו טקסט, ו-`FEATURE_AUTO_CAPTURE=false` בפרודקשן כבר חוסם כתיבה אוטומטית) — אין תלות אמיתית ב-production-verification של C89.
**Feature Flag:** `FEATURE_STRUCTURED_FILE_CAPTURE` (כבוי כברירת מחדל — ללא שינוי התנהגות בפרודקשן)
**עיקרון (חשוב — תוקן אחרי גרסה ראשונה שגויה):** קובץ שמועלה הוא **ingress source adapter בלבד** — לא capture pipeline חדש, לא classifier חדש, לא write path חדש. `core/file_ingress_adapter.py` (חדש) מפרסר xlsx/csv לשורות; **כל שורה** עוברת, אחת בכל פעם, דרך אותו `classify_ingress()`/`handle_lead_candidate()` בדיוק כמו הודעת טקסט — **ללא special-casing**. שורה עם שם+טלפון ברור יכולה להיות Tier 1 באופן לגיטימי (לא נכפה Tier 4 באופן גורף). גרסה ראשונה (commit `da49d3e`) כן כפתה Tier 4 גורף לכל קובץ — תוקנה בהמשך אותו PR אחרי שהמפרט המפורט הובהר.
**קבצים:** `core/file_ingress_adapter.py` (חדש), `core/ingress_classifier.py` (`_classify_ingress_core` — `source_type="file"` עובר באותה לוגיקה בדיוק כמו `"text"`, לא branch נפרד), `app.py` (`_process_structured_file_upload`, `_is_structured_file`, wiring ל-`_handle_telegram_media`).
**Guards:** אין bulk auto-approve (כל שורה יוצרת contract נפרד ב-ActionGateway, דורשת "כן" פרטני); raw_ref + AgentObservation(`kind=capture_classification`) לכל שורה בנפרד; שורה פגומה (ragged/לא ניתנת לפרסור) לא נעלמת בשקט — מוחזרת כטקסט raw מסומן וממשיכה לעבור דרך אותו pipeline; קובץ שלם שלא ניתן לפתיחה → הודעת שגיאה מפורשת. מגבלת בטיחות תפעולית `_MAX_FILE_ROWS_PROCESSED=200` — לא dropping שקט, מדווחת במפורש בתשובה אם הקובץ חורג.
**באג שנתפס ותוקן במהלך הבנייה:** row-to-text format השתמש במפריד `" | "` — התנגש עם `_TABLE_RE` הקיים (מזהה 2+ שדות מופרדי-pipe כ-Tier 4 אוטומטי) עבור כל שורה עם 3+ עמודות מאוכלסות, כפיית Tier 4 שגויה על נתונים לגיטימיים. תוקן ל-`", "` (לא מתנגש עם אף hard marker קיים). ראו regression test ב-`test_c90_structured_file_capture.py`.
**בדיקה:** `test_c90_structured_file_capture.py` (37/37) — פרסור xlsx/csv אמיתי (openpyxl/csv), no-merging/no-dropping, שורה ברורה→Tier1 אמיתי (לא נכפה), שורת export→Tier4 (hard markers עדיין עובדים), raw_ref+observation נפרדים לכל שורה, אין auto-write ללא אישור, שורה פגומה לא נעלמת, קובץ לא-תקין→שגיאה מפורשת, gating על flag+is_internal+סוג-קובץ. אפס רגרסיה על 30+ קבצי טסט קיימים + `smoke_tests.py`.
**לא אומת:** production/Render (אין גישה מה-sandbox). C91-C93 (voice/email/image) נשארים לא-ממומשים (Tier 5), חוץ מהסעיף הזה.

### C91 — Stage 3.2: Capture Policy — קול (Whisper → טקסט)
**עדיפות:** 🟠 בינוני — **לא חסום על C89** (C89 נסגר 05/07/2026 כ-CLOSED/VERIFIED עם `FEATURE_AUTO_CAPTURE=false`, החלטת הבעלים — ראה N13/AI_CONTEXT.md §0.14). לא התחיל בפועל; פתוח לביצוע/החלטת flag בכל עת.
**פעולה:** Whisper תמלול → `classify_ingress(source_type="voice")`. confidence baseline מופחת אוטומטית.

### C92 — Stage 3.3: Capture Policy — מייל נכנס
**עדיפות:** 🟡 גבוה — **לא חסום על C89** (ראה הערה ב-C91 למעלה). תלוי רק בהחלטת flags ובחיבור נתיב ה-inbound הקיים.
**פעולה:** `email_inbound.py` מתחבר לאותו `classify_ingress()` במקום לוגיקה נפרדת — איחוד, לא בנייה.

### C93 — Stage 4: OCR / כרטיסי ביקור
**עדיפות:** 🟠 בינוני — עדיין חסום, אך **לא על C89** (סגור) — חסום על צבירת ≥2 שבועות `AgentObservation` data (needs_review rate + תיקונים ידניים ב-Tier 1), תנאי מוצהר מראש שעדיין לא מתקיים.
**פעולה:** תמונה → OCR → `classify_ingress(source_type="image")`. נפתח רק אם שיעור needs_review ושיעור תיקונים ידניים ב-Tier 1 נמוכים (נתוני AgentObservation).

### C94 — 🟡 שלב א׳+ב׳+ג׳+ד׳ הושלמו — Unified Ingress Envelope + Evidence Trace
**עדיפות:** 🟠 בינוני — לא תלוי ב-C89 production verification; שכבה *לפני* הכניסה ל-classify_ingress/C90, לא נוגעת בהם.
**הערת מספור:** מקורי בדוח שהתקבל תויג "C91" — שונה ל-C94 כדי לא להתנגש עם C91 (Stage 3.2 — קול) הקיים כבר למעלה.
**עקרון:** שתי שכבות נפרדות, אף פעם לא ממוזגות לאובייקט אחד (נבדק במפורש מול הצעה חלופית לאחד ל-container אחד מתמלא בהדרגה — נדחתה, ראה עדכון 05/07/2026 למטה):
- `IngressEnvelope` (7 שדות + `envelope_id`: source_channel, provider, raw_event_id, sender_identity, normalized_text, attachments, `source_ref`) — תקף **לפני** סיווג; שום שדה לא תלוי בתהליך מאוחר יותר.
- `EvidenceTrace` (FK `envelope_id` + `trace_id`/`attempt_no`/`status` + classification_result/classification_error/raw_ref/approval_contract_id/agent_observation) — נוצר **אחרי** classify_ingress/preview/approval; trace חלקי (Tier 3/4, או classification_error) הוא מצב תקין, לא כשל.
**קובץ ראשי:** `core/ingress_envelope.py` (schemas), `core/file_ingress_adapter.py` (`build_file_row_envelope()` — Stage ב), `app.py`'s `_process_structured_file_upload` (מחווט ל-Envelope, לא משנה את C89/C90 עצמם).
**בדיקה:** `test_c94_ingress_envelope.py` (57/57), `test_c90_structured_file_capture.py` (41/41, כולל 4 טסטים חדשים ל-Stage ב) — אפס רגרסיה על כל חבילת ה-`test_*.py` הקיימת + `smoke_tests.py`.
**עדכון 05/07/2026 — 3 תיקוני schema לפני/תוך כדי Stage ב (C94-A.1/A.2/A.3), כולם נסגרו לפני שהמשך הקוד נכתב:**
- **A.1:** `raw_ref` הועבר מ-Envelope ל-Trace — פיזית לא יכול להיות מלא לפני `classify_ingress()` (הוא מיוצר *בתוכה*). Envelope קיבל `source_ref` (מצביע adapter-level, זמין תמיד לפני סיווג) במקום. `classify_ingress()`/C90 לא שונו.
- **הצעה שנדחתה במפורש:** לאחד Envelope+Trace לאובייקט אחד מתמלא בהדרגה (10 שדות). הוחלט לשמור על שני אובייקטים נפרדים — זה בדיוק העיקרון המרכזי שהדוח המקורי ("גרסה מתוקנת") נועד לתקן, וה-timing gap שהעלה הצידוד לאיחוד כבר נפתר ע"י A.1 (FK בין השניים, לא nesting).
- **A.2:** נוסף `envelope_id` (FK, uuid) על שני האובייקטים; Trace אחד יכול להיות לו כמה attempts (retry) — `record_classification()` הוא הדרך היחידה לרשום תוצאה, ונכשל בקריאה שנייה (append-only, לא overwrite); `classification_error` נוסף (מוציא-הדדית מ-classification_result) כדי ש-exception בתוך `classify_ingress()` עדיין ישאיר evidence, לא ייעלם בשקט.
- **A.3:** נוסף `trace_id` (ייחודי per attempt), `attempt_no` (1-based, עולה לפי envelope_id דרך `next_attempt()` בלבד), `status` (property מחושב, לא שדה שמור — נמנע drift; `"classification_error"` הוא ערך legit, לא כשל). `latest_trace()`/`next_attempt()` הן הדרך היחידה לבחור/ליצור attempt.
- **תיקון נלווה אמיתי שנתפס תוך כדי:** `_process_structured_file_upload` לא היה עוטף את קריאת `classify_ingress()` עצמה ב-try/except (רק את `handle_lead_candidate()`) — exception בשורה בודדת היה מפיל בשקט את כל שאר שורות הקובץ. תוקן כחלק מחיווט Stage ב; `classification_error` שנשמר על ה-trace הוא `type(exc).__name__` בלבד (לא `str(exc)`/raw text) כדי לא לדלוף PII משורת הקובץ.
- **עדכון נוסף אותו יום:** גם ה-`logger.error()` הפנימי (לא רק שדה ה-trace) תוקן — `str(exc)`+`exc_info=True` הוחלפו במטא-דאטה בטוחה בלבד (envelope_id/row/error_type), כי traceback מלא לרוב חוזר ומדפיס את אותה הודעת-שגיאה/PII "מהדלת האחורית".

**עדכון 05/07/2026 — שלב ג׳ (Telegram wiring):**
- `core/telegram_ingress_adapter.py` (חדש) — `build_telegram_envelope()`, מיפוי `_CHANNEL_TO_PROVIDER` כמו ב-file adapter. אין שינוי ב-`classify_ingress()`/C89/C90 עצמם.
- **פער אמיתי שנחשף (ולא רק תוקן רטרואקטיבית כמו בשלב ב׳):** ל-Telegram אין row-loop עצמאי כמו לקבצים — `classify_ingress()` נקרא עמוק בתוך `router.route_request()` (דרך `core/router/capture_router.py`), ו-`app.py`'s `_safe_route()` עטף את **כל** `route_request()` ב-catch גורף שנכשל-סגור (Handler.APPROVAL, intent=UNKNOWN) על **כל** חריגה — כולל חריגת classify_ingress ספציפית. `core/router/capture_router.py`'s `classify_capture_ic()` עטוף עכשיו בעצמו: חריגה מסוננת ל-`None` (כמו מצב "לא internal" הקיים, שכל הקוראים כבר מטפלים בו), עם `EvidenceTrace(classification_error=type(exc).__name__)` מסוניטז מההתחלה (לא כתיקון מאוחר). `_safe_route()`'s ה-catch הגורף **לא שונה** לכל חריגה אחרת בראוטר — צומצם ה-fail-closed רק לנקודה הצרה הזו.
- **אישור מפורש התקבל לפני מימוש**, כולל 3 תנאים לטסט: (1) סניטיזציה זהה ל-Stage ב (`type(exc).__name__` בלבד), (2) טסט מוכיח שחריגה לא מפילה את כל ה-router + intent/domain/risk ממשיכים לעבוד נכון ובלתי-תלוי (כולל risk=high שעדיין נחסם נכון), (3) `_safe_route()`'s catch הכללי לכל חריגה אחרת נשאר בדיוק כמו שהיה.
- `route_request()`/`_safe_route()`/`run_agent()` קיבלו פרמטר אופציונלי חדש `envelope_id`/`raw_event_id` (additive-only, ברירת מחדל ריקה — אפס שינוי לכל קורא קיים). רק ה-webhook של Telegram מעביר `raw_event_id=str(update.update_id)` בפועל.
**בדיקה:** `test_c94_stage_c_telegram.py` (28/28) — כולל שלושת התנאים שאושרו, equivalence (זהה עם/בלי envelope_id), ו-PII-safety בלוג. אפס רגרסיה על `test_capture_router_wiring.py`/`core/router/test_router.py`/כל חבילת ה-`test_*.py` + `smoke_tests.py`.
**ידוע ומכוון, לא נשכח — EvidenceTrace עדיין לא persisted:** בשני מקומות שבהם `EvidenceTrace` נבנה כיום (`app.py`'s `_process_structured_file_upload` משלב ב', `core/router/capture_router.py`'s `classify_capture_ic()` משלב ג') — האובייקט נבנה, `record_classification()`/`record_classification(classification_error=...)` נקרא עליו, הוא נרשם ל-`logger.debug` בלבד, ואז יוצא מהיקף (scope) ונזרק. `EvidenceTrace` נכון להיום הוא שכבת schema+validation בזיכרון (מוכיחה שהאירועים/הכשלים *נרשמים נכון ברגע שהם קורים*), **לא** evidence store עם היסטוריה נשאלת (queryable). "persist Trace ל-storage אמיתי (Airtable/DB, שאילתת `latest_trace(envelope_id)` אמיתית לא רק helper בזיכרון)" הוא scope עתידי מפורש — לא שלב ד' (WhatsApp) ולא נכלל כרגע באף שלב מתוכנן; צריך סעיף/שלב נפרד משלו כשיוחלט לבנות אותו.
**עדכון 05/07/2026 — שלב ד׳ (WhatsApp Twilio wiring):**
- `core/whatsapp_ingress_adapter.py` (חדש) — `build_whatsapp_envelope()`, `source_channel="whatsapp"`, `provider="twilio_whatsapp"` (דרך `_CHANNEL_TO_PROVIDER`, לא hardcoded, ולא "twilio" — BUG-071 pattern נבדק במפורש בטסט). `raw_event_id` = Twilio `MessageSid`.
- `app.py`'s `run_agent()` — הבלוק שבנה Envelope ל-Telegram (2.7, שלב ג') הוכלל (generalize) לדיספאץ' per-channel: `telegram` → `build_telegram_envelope()`, `whatsapp` → `build_whatsapp_envelope()`. אותו try/except/validate/degrade-gracefully pattern בדיוק כמו Telegram — כשל בבנייה/ולידציה לא חוסם את התשובה, רק מוריד ל-envelope_id="".
- **Meta WhatsApp Cloud API נשאר gated/לא נוגע:** `webhook_meta_whatsapp()`'s `run_agent()` call (רץ רק אם `META_OUTBOUND_ENABLED=true`, כבוי כברירת מחדל) **לא** מעביר `raw_event_id` בכלל — אין adapter/envelope חדש ל-Meta בשלב הזה. זה לא מקרי: BUG-071 (הבאג שהוליד את כל הספק הזה) היה בדיוק על media/ingress ש"התבדר" בין providers של WhatsApp — בניית envelope שני ספציפי ל-Meta לפני שהוא בכלל ערוץ outbound חי הייתה חוזרת על אותה טעות במיניאטורה. כשMeta יאושר כשלב עצמאי, אותו source_channel="whatsapp" עם provider="meta_cloud_api" (כבר ערך תקף ב-`PROVIDERS`) — בלי שינוי קוד נוסף.
- ה-router-level exception-safety fix (Stage ג, `capture_router.classify_capture_ic()`) כבר חל על כל הערוצים כולל WhatsApp — לא נדרש תיקון נוסף שם.
**בדיקה:** `test_c94_stage_d_whatsapp.py` (12/12) — schema conformance, equivalence מלא **דרך `run_agent()` בפועל** (לא רק `route_request()`) עם/בלי raw_event_id, degrade-gracefully כשבניית ה-envelope עצמה זורקת חריגה, regression check שה-branch של Telegram לא נפגע, והוכחה source-level ש-Meta לעולם לא מעביר raw_event_id. אפס רגרסיה על `test_whatsapp_media.py`/`core/router/test_router.py`/כל חבילת ה-`test_*.py` + `smoke_tests.py`.
**נותר:** אין שלבים נוספים מתוכננים כרגע ל-C94 מעבר לזה (Meta Cloud API נשאר עתידי/לא מאושר; persist EvidenceTrace ל-storage אמיתי — ראה ההערה למעלה — הוא scope נפרד עתידי).

**עדכון 05/07/2026 — Feature Flag / Render env vars / production verification audit:**
- **סגור: נוסף `FEATURE_INGRESS_ENVELOPE`.** במקור C94 לא היה לו flag (equivalence-preserving בכל שלב, נחשב "always-on plumbing") — סטייה מ-`RELEASE_CHECKLIST.md`'s "Feature flag הוגדר וכבוי ברירת מחדל" שתועדה כפער מודע. נסגר: `FEATURE_INGRESS_ENVELOPE` עוטף עכשיו את בלוק ה-envelope-dispatch ב-`run_agent()` (שינוי שורה אחת בתנאי — `if _flag_enabled("FEATURE_INGRESS_ENVELOPE") and raw_event_id and channel in (...)`). **ברירת מחדל ON, לא OFF** — נוסף ל-`_DEFAULTS` ב-`feature_flags.py` (אותו מנגנון בדיוק כמו `IMPORT_DOMAIN`, הדגל היחיד האחר עם ברירת מחדל הפוכה) כי C94 כבר במיין; דגל חסר שברירת המחדל שלו הייתה False היה מכבה שקט את מה שכבר רץ. אומת: 138 הבדיקות זהות בין flag לא-מוגדר ל-`=true` מפורש, ו-`=false` באמת מדכא בניית envelope (0 קריאות ל-adapter).
- **דגלים סמוכים (לא C94 עצמו) וברירות המחדל שלהם בקוד** (`feature_flags.py`'s `_DEFAULTS` מכיל רק `IMPORT_DOMAIN`; כל שאר הדגלים כבויים אלא אם Render env var דורס): `FEATURE_STRUCTURED_FILE_CAPTURE` (C90) — כבוי; `FEATURE_AUTO_CAPTURE` (C89) — כבוי; `FEATURE_RAW_CAPTURE` — כבוי; `META_OUTBOUND_ENABLED` — כבוי (Meta נשאר לא-נוגע ל-C94 Stage ד' במפורש). **אין גישת Render Dashboard מה-sandbox** — אלו ברירות מחדל בקוד + הסנאפשוט הידוע האחרון (ראו AI_CONTEXT.md), לא אימות live; הבעלים צריך לבדוק את ה-env vars האמיתיים ב-Render.
- **אין Render env vars חדשים ל-C94** — נבדק grep מלא (`os.environ`/`getenv`) על כל 5 קבצי ה-C94 (`ingress_envelope.py`/`file_ingress_adapter.py`/`telegram_ingress_adapter.py`/`whatsapp_ingress_adapter.py`/`capture_router.py`) — אפס hits. C94 משתמש אך ורק בתשתית identity/classify_ingress/ActionGateway הקיימת.
- **Production verification — ✅ 4/5 בוצעו ע"י הבעלים, 05/07/2026 (העדכון האחרון):**
  1. ✅ הודעת Telegram אמיתית — נכנסה תקין, Identity resolved, Router עבד, `classify_ingress` לא הפיל את ה-router, **אין** `[C94] telegram envelope build/validate failed` בלוגים.
  2. ✅ הודעת WhatsApp/Twilio אמיתית — נכנסה תקין, Identity resolved, Router עבד, **אין** `[C94] whatsapp envelope build/validate failed`, `MessageSid` אמיתי נראה כ-`raw_ref`.
  3. ✅ קובץ xlsx/csv אמיתי — נבדק לאחר הדלקה זמנית של `FEATURE_STRUCTURED_FILE_CAPTURE` לצורך הבדיקה בלבד; **הוחזר ל-OFF מיד אחרי** — מצב הדגל בפרוד נשאר כפי שהיה (כבוי), אין שינוי התנהגות מתמשך.
  4. ✅ commit hash ב-Render מול `main` — אומת: `41f3305` חי בפרוד (זהה למיזוג PR #241, ה-commit האחרון שנוגע קוד; PR-ים מאוחרים יותר הם docs-only).
  5. ➖ מסלול "חריגת classify_ingress מתדרדרת בעדינות" — **לא נבדק בפרוד בכוונה** (=לשבור prod), נשען על 138 הבדיקות (`test_c94_*.py`) בלבד. זה הפריט היחיד שנשאר, ולא בטעות — סיכון מיותר להפעיל תקלה אמיתית רק כדי "לראות שהיא נתפסת".
- **שני ממצאים נוספים מהסבב הזה (לא C94, לא תוקנו כאן):**
  1. **WhatsApp outbound — honest stub, מחוץ ל-scope של C94.** כבר מתועד/צפוי (`META_OUTBOUND_ENABLED=false` כברירת מחדל — `feature_flags.py`), אומת כעת גם באופן live שההתנהגות תואמת את המתועד.
  2. **BUG-072 (חדש, פתוח, לא תוקן):** לוגים קיימים (לא C94 — נתיבים ישנים יותר) עדיין חושפים sender IDs/מספרי טלפון גולמיים. נתפס אגב בדיקת ה-smoke הזו של C94; **לא** אותו מנגנון כמו C94's sanitization (`type(exc).__name__` בלבד) — זה pre-existing logging gap בקוד אחר. ראה BUG_AUDIT_LOG.md BUG-072 לפירוט.
**ראה:** AI_CONTEXT.md §0.12/§0.15 לפירוט המלא.

---

### N01 — ✅ הושלם (W1 לעיל)

### N02 / N03 — Lead Scoring + Lead Memory Wire-up ✅ מיושם
**lead_capture.py בלבד** — single path:
1. יצירת Lead ב-Airtable (`LEAD_CAPTURE=true`)
2. `_score_inbound_message()` → `airtable_patch(Score)` (`LEAD_SCORING=true`)
3. `lead_memory.update()` עם `domain/channel/contact_name/summary/last_message` — **תמיד** בעת create, גייטד ב-`LEAD_MEMORY` בלבד (N04-A)
4. `lead_memory.update()` עם `tier/score/record_id` אחרי scoring (N04-B)
**lead_scoring.py** הוסר — היה zombie code.
**flags:** LEAD_SCORING, LEAD_MEMORY (שניהם כבויים ברירת מחדל).
**commits:** 4d1130a (consolidation), 02f7e75 (N04-A/B wiring)

### N04 — Followup Activation ✅ scheduler מחובר (flag כבוי)
`scheduler._job_followup_scan()` רץ כל 60 דקות, קורא ל-`followup_engine.run_followup_scan()`.
גייטד ב-`FOLLOWUP_AUTOMATION=true` — כבוי ברירת מחדל.
`lead_memory.all_active()` מחזיר כעת entries אמיתיים (N04-A/B — commit 02f7e75).
**המתנה לפני הפעלה**: לאמת ב-Render env עם הודעת WhatsApp אמיתית + `LEAD_CAPTURE=true`.
**קבצים:** `scheduler.py` (קיים), `followup_engine.py` (קיים).

### N05-B — send_followup.confirmed handler ✅ מיושם (commit 643f929)
Owner מאשר followup → טיוטה מגיעה ב-Telegram לשליחה ידנית.
`lead_memory.followup_count` מתעדכן אחרי כל אישור.
**אין שליחה יוצאת לליד** — Meta outbound blocked עד N05-C.
**flag:** `FOLLOWUP_AUTOMATION` (אותו gate כמו N04).

### N05 — Daily Digest שדרוג ✅ מיושם
**תלוי ב:** N02 (כדי שציונים אמיתיים יופיעו בדוח).
**מה:** חיבור score + tier לדוח הבוקר. `_hot_leads()` עבר מפילטר
status='hot' מת (לא נכתב לעולם בקוד) לפילטר `Score>=50` עם fallback
ל-status הישן. tier מחושב בזיכרון מ-Score (אותם ספים כמו
`lead_capture._score_inbound_message`) — לא נקרא משדה Airtable; השדה
`tier` כן קיים בסכמה (singleSelect אמיתי, לא formula) אך ריק ב-100%
מהרשומות (0/39, 21/08/2026) וללא כותב מכוון (ראה Known Issues, עודכן).
**קבצים:** daily_digest.py בלבד.

### N06 — Ventures Screen (TMA) ✅ מיושם
**תלוי ב:** N05 (Daily Digest שדרוג).
**מה:** מסך TMA חדש — 🔭 Ventures. חילוץ Strategic Pipeline מ-OCC + 
חיבור לטבלת Ventures הקיימת ב-Airtable.

**החלטה ארכיטקטונית (17/06/2026 — סופית):**
- Ventures = טבלה נפרדת (קיימת: tblsXFq5AwxUkdAJ7)
- לא הרחבת Deals.Status (גישה ישנה מ-13/06 — בוטלה)
- Deals = כסף שכבר על השולחן
- Ventures = האם בכלל כדאי לפתוח שולחן (לפני ליד, לפני עסקה)

**Airtable — כבר מוכן לחלוטין:**
- טבלת Ventures קיימת ומחוברת ל: Profile, Contacts, Deals, 
  Business Memory, Interaction Log
- שדות מרכזיים: Venture Name, Stage, Domain, Conviction, 
  Estimated Potential (NIS), Target Decision Date, Decision Log,
  Next Action, Linked Contacts, Interaction Log, Business Memory,
  Converted To Deal (multipleRecordLinks), Owner, Created At

**שלבי ה-Venture (דומיין-אגנוסטי):**
Research → Supplier/Source → Due Diligence → Smoke Test → GO/NO-GO → [Convert]

**קבצים לכתוב:**
- `src/screens/Ventures.tsx` (חדש)
- `tma_api.py` — endpoints: GET /api/ventures, GET /api/ventures/<id>,
  POST /api/ventures, PATCH /api/ventures/<id>
- `airtable_schema.py` — הוסף Tables.VENTURES = "Ventures"
- `_TMA_WRITE_ALLOWED_TABLES` — הוסף "Ventures"

**קבצים לשנות:**
- `OwnerControlCenter.tsx` — חלץ את Strategic Pipeline לקומפוננטה
  נפרדת; ה-OCC יציג רק summary (count by stage), קישור ל-Ventures

**מה לא לגעת בו:**
- Approval Gate — כל PATCH/POST עובר דרכו כרגיל
- Lead Capture, Scoring, Routing — לא נוגעים

**UX — מסך Ventures:**
```
┌─────────────────────────────────┐
│ 🔭 Ventures                     │
│ [Research] [DD] [Smoke] [GO/NO] │ ← פילטר לפי Stage
├─────────────────────────────────┤
│ 🏗️ ייבוא ריהוט עץ              │
│ Stage: Due Diligence            │
│ Conviction: גבוה                │
│ ₪ 2.4M פוטנציאל | 30/07 deadline│
│ Next: פגישה עם עמיל מכס        │
├─────────────────────────────────┤
│ 🏠 פרויקט יבניאל 2              │
│ Stage: Smoke Test               │
│ ...                             │
├─────────────────────────────────┤
│ [+ Venture חדש]                 │
└─────────────────────────────────┘
```

**כלל ברזל לפי ROADMAP #6:** N06 = קובץ אחד ראשי (Ventures.tsx) + 
endpoints ב-tma_api.py + שורה ב-airtable_schema.py. לא יותר.

**הערות מימוש (סטייה מהתכנון המקורי, מתועדת):**
- `Ventures.tsx` נוצר ב-`tma-frontend/src/components/` ולא ב-`src/screens/` —
  בקונבנציה הקיימת ברפו אין תיקיית `screens/` כלל; כל מסכי ה-TMA חיים שטוח
  ב-`components/`. נשמרה הקונבנציה הקיימת על פני הנתיב התיאורטי במסמך.
- כתיבות (POST/PATCH) הן ישירות ל-Owner בלבד, ללא Approval Gate — כמו
  Assets (`update_asset`), לא כמו ה-flow המתואר ב"מה לא לגעת בו". הוחלט
  כי Venture הוא כלי אסטרטגי owner-only (זהה ל-OCC) ולא דורש תור אישורים,
  ולכן `_TMA_WRITE_ALLOWED_TABLES` לא עודכן (לא בשימוש ע"י venture writes).
- `strategic_pipeline` ב-OCC שונה משלוש-דליים (`new_opportunities`/
  `in_evaluation`/`pending_decision`) לפורמט `{stage_counts, total, active}` —
  count-by-stage אמיתי לפי 8 השלבים בטבלת Ventures, כפי שהמסמך דרש.

**עדכון תיעוד (14/08/2026, תיעוד-דריפט — לא בדיקה מחודשת של N06 עצמו):**
ההערות למעלה מתארות את המימוש המקורי (17/06/2026, commit `eebf73b`). מאז
עבר `Ventures.tsx` שכתובים משמעותיים נוספים דרך PR #625 (`codex/vux-0-ventures-foundations`),
#629 (`codex/vux-1-ventures-workspace-shell`), #632 (`codex/vux-2-ventures-collection-lifecycle`),
#636 (`codex/vux-2-5-soft-3d-calibration`), #642 (`codex/vux-3-ventures-detail`) — מאות שורות
שונו בכל אחד. **הסטטוס "✅ מיושם" נשאר נכון**, אבל הערות המימוש למעלה הן היסטוריות
ולא תוארו-מחדש מול הקוד הנוכחי (מחוץ ל-scope של סבב תיעוד זה — לא נבדק תוכן ה-PRs האלה).

### N07 — Schema Governance script ✅ הושלם (PR #101, `e465eff`)
**מה:** `tools/schema_governance.py` — סקריפט standalone שמשווה live Airtable
schema (Metadata API, `GET /meta/bases/{baseId}/tables`) מול `airtable_schema.py`
(import, לא parse), בעזרת `TABLE_CLASS_MAP`/`_class_values` הקיימים מ-`schema_audit.py`.
מזהה: שדה בקוד שחסר ב-live (התאמה whitespace-tolerant) → ERROR; שדה ב-live
שלא בקוד → WARNING; trailing/leading spaces בשמות שדות → WARNING (ממוזג עם
ה-whitespace-tolerant match, לא משוכפל); trailing/leading spaces ב-select
options → WARNING; שינוי סוג שדה → ERROR (מול ריצה קודמת שנשמרה ב-
`schema_drift_report.json`, כי `airtable_schema.py` לא מכיל מטא-דאטה של סוגים).
מדפיס דוח עברית ל-console, exit code 1 אם יש ERROR. READ ONLY לחלוטין — אפס
כתיבה ל-Airtable, לא נוגע ב-`schema_cache.json`. self-test (`--self-test`,
ללא רשת) כלול בקובץ.
**מניע:** BUG-008 (`Leads."Business Outcome"` trailing space) התגלה
ad-hoc תוך כדי חקירת באג, לא דרך audit שיטתי — ראו `AI_CONTEXT.md` §8.
**מצב נוכחי:** קוד הושלם ומוזג ל-main, עדיין לא רץ ב-CI (אין CI בריפו —
ראו N08 למטה) — הרצה היא manual לעת עתה (ראו `RELEASE_CHECKLIST.md`).

### N08 — CI/CD GitHub Actions ✅ הושלם (PR #103, `abf4835`)
**מה:** `.github/workflows/ci.yml` — מריץ `smoke_tests.py`/`test_integration.py` +
`npm run build` (frontend, skip חינני אם `tma-frontend/package.json` חסר) על כל PR.
Secrets נכונים (`TELEGRAM_TOKEN` וכו') ממופים מ-GitHub secrets.
**מצב נוכחי:** ממוזג ל-main, פעיל על כל PR.

### N09 — Monitoring / Alerting ✅ הושלם (PR #104, `4ac6d24`)
**מה:** `core/error_reporter.py` — `report_error(error, context, level)` שולח
התראת Telegram על שגיאות פרודקשן בלבד (`RENDER=="true"` + `ERROR_REPORTING` flag),
rate-limited (10/שעה), בלי payload/תוכן הודעות/מידע לקוח (context = שם פונקציה בלבד,
traceback גולמי). מחובר ב-`app.py` ב-3 נקודות: `_handle_approval_callback`,
`webhook_telegram`, `webhook_whatsapp`.
**מצב נוכחי:** ממוזג ל-main, פעיל בפרודקשן (תלוי ב-`ERROR_REPORTING`/`ELIYAHU_CHAT_ID`).

### N10 — Rollback אוטומטי 🔲 PLANNED
**תלוי ב:** N08 (CI/CD — הושלם).
**מה:** rollback אוטומטי ל-commit יציב אחרון כש-health check/monitoring
מזהה כשל אחרי deploy.
**עד שמיושם:** manual gate בלבד (ראו `RELEASE_CHECKLIST.md`).

### N11 — Screen Filter Gateway: Finance Pulse wiring ✅ הושלם (PR #77, `f7d7e4f`/`daab73e`)
**תלוי ב:** C53 (Screen Filter Gateway — מיושם, PR #75).
**מה:** `GET /api/finance/pulse` מחובר ל-`SCREEN_CONFIGS["finance_pulse"]` +
`_build_formula()` עם `entity="Payment"` (`status_field=PaymentFields.STATUS`),
תומך ב-`?view=active|overdue|all` ומחזיר `available_views`. סיווג overdue/pending/
income לפי תאריך מתבצע ב-Python על תוצאת ה-formula (status-based, לא raw_formula
דינמי לתאריך — נמצא מספיק כש-`exclude_statuses`/`include_statuses` עושים את הסינון
העיקרי והקטגוריזציה לפי תאריך נשארת בקוד האפליקציה, לא ב-Airtable formula).
אפס שינוי ל-`_build_formula()` עצמה.
**עתידי (multi-tenant):** override per-tenant מ-`ProjectsHub.screen_overrides`
(JSON, נדרש שדה חדש בסכמה) — ראו הערה ב-`tma_api.py` ליד `SCREEN_CONFIGS`.
**מצב נוכחי:** ממוזג ל-main (`tma_api.py`/`airtable_schema.py`), לפני הסשן הנוכחי —
תועד כ-PLANNED ב-ROADMAP בטעות; תוקן כאן.

### N12 — Daily Git Audit scheduler wiring ⚠️ בוטל (N16, 21/07/2026) — ליקוי ארכיטקטוני, ראה למעלה
**עדכון (21/07/2026):** החיבור המתואר למטה **הוסר לגמרי**. הבעלים קבע שהבוט העסקי לא
אמור להיות קשור לריפו/Git בשום צורה — git audit הוא אחריות בלעדית של Claude Code Routine
נפרד. `_job_daily_git_audit`/`git_audit_time`/הרשמת ה-schedule הוסרו מ-`scheduler.py`,
`daily_git_audit.py`'s `_send_telegram()` הוסרה כליל, דגל `GIT_AUDIT_SCHEDULER` הוסר.
GOV-02 (`audit_truth_gate.py`) עצמו נשאר בריפו כ-read-only tool, ללא שינוי. ראה N16 (חדש)
ו-changelog בראש הקובץ. הטקסט המקורי מתחת נשמר כתיעוד היסטורי של מה שהיה קיים.
---
**מה (היסטורי — כבר לא נכון, ראה עדכון למעלה):** `daily_git_audit.py` (קיים מ-GOV-02) חוּבר ל-`scheduler.py` (`_job_daily_git_audit`,
`schedule.every().day.at(git_audit_time)`, `GIT_AUDIT_TIME` env var, ברירת מחדל `06:45`
כדי לא להתנגש עם digest ה-game ב-07:00/digest רגיל ב-07:30). נוספו ל-`daily_git_audit.py`
עצמו: `check_unmerged_vs_roadmap()` (משווה ענפים לא ממוזגים מול טענות ✅/DONE ב-ROADMAP.md —
**ROADMAP.md ראשון בעדיפות**, לא BOSS_CURRENT_STATE.md, כדי לא לסתור את הכרזת הקובץ
עצמו כ"מקור האמת היחיד"), `check_duplicate_schemas()` (שמות tool כפולים ב-
`tools/schemas.py`/`tool_registry.py`), `check_recent_commits()`, `check_cors_env_drift()`
(`tma_api.py` מול `.env.example`).
**Feature Flag:** `GIT_AUDIT_SCHEDULER` — כבוי כברירת מחדל (נשאר manual-only, תואם
ל-docstring הקיים של `daily_git_audit.py`).
**מניע:** נמצא תוך כדי ניקוי ענפי `claude/*` ישנים — `claude/lucid-franklin-0os9ma`
ו-`claude/tender-hypatia-h5n0d3` הכילו את המימוש הזה אבל לא מוזגו מעולם; חולץ ותוקן
(ה-bug ב-precedence) לפני שהענפים נמחקו.
**מצב נוכחי (היסטורי):** היה ממוזג ל-main, דגל כבוי. **בוטל ב-N16 (21/07/2026) — ראה עדכון למעלה.**

### N13 — Decision Hub (Stage 0 / 0.5 / 0.6) ✅ הושלם, דגל כבוי (PR #147, `4ac2a05`/`e0f0111`)
**מה:** ליבת "החלטה" domain-agnostic (`Decision`, `decision_pipeline.py`) עם Inbox raw-first
(Stage 0), File/Voice Precedence Routing (Stage 0.5) ו-File Context Reference — קישור
"זה הנספח" לקובץ האחרון שהועלה (Stage 0.6). מימוש ראשון של MODULE_RULES חוקים 7-10 בקוד
חי (`decision_ports.py`/`DecisionPorts`, `GateResult`/`_GATE_REGISTRY`).
**קבצים:** `cmd_decision.py` (`decision_context_active`, `route_file_to_decision_inbox`,
`_suggest_decision_link`, `is_attachment_reference`, `handle_attachment_reference`),
`decision_pipeline.py`, `decision_ports.py`, `app.py` (`_handle_telegram_media` precedence
gate + Drive-upload `set_last_file` hook + `_webhook_telegram_impl` "זה הנספח" gate),
`session_store.py` (`FileUploadResult`, `set_last_file`/`get_last_file`), `airtable_schema.py`
(Decision Hub tables/fields).
**Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן.
**מצב נוכחי:** Stages 0–6 ממוזגים ל-`main`: Stage 0/0.5/0.6 ב-PR #147; Stage 1 ב-PR #151;
Stage 2 ב-PR #157; Stage 3 ב-PR #159; Stage 4 ב-PR #161; Stage 5 ב-PRs #162–#164;
Stage 6 ב-PR #166. דגלי Decision Hub כבויים כברירת מחדל. המיזוגים אומתו ב-main, אך
**Production Verified נשאר לא** עד אימות ידני לאחר פריסה. ראו F17–F21 למטה.

**app.py אומת 29/06/2026:** Sessions×1, domain drift דרך _resolved_domain,
UTM memory_key fix, A32 bridge, Lead Buffer recovery — כולם ב-main.

#### Decision Hub — ledger מאוחד ל-Stages 1–6

| Stage | ROADMAP | יכולת שמומשה | PR | Commit / Merge | בדיקות | סטטוס מאומת |
|---|---|---|---|---|---|---|
| 1 | C59 / N13 | Trust Layer — Authority × Medium × Verify | #151 | `73f6fe8` / `b289ab6` | 33/33 | מוזג ל-`main`; Production Verified: לא |
| 2 | F17 | Smart Trust — conflicts, confidence, evidence graph, missing evidence | #157 | `9252b1e` / `78f9bae` | 28/28 | מוזג ל-`main`; Production Verified: לא |
| 3 | F18 | Readiness Engine — READY / NOT_READY / REVIEW | #159 | `84cfcff` / `50f6351` | 25/25 | מוזג ל-`main`; Production Verified: לא |
| 4 | F19 | Attention Engine — תעדוף דטרמיניסטי read-only | #161 | `3e79a03`, `1281dda` / `fb4d041` | 11/11 | מוזג ל-`main`; Production Verified: לא |
| 5 | F20 | Auto Ingestion — WhatsApp/email/document/voice ל-Inbox בלבד | #162–#164 | `9b97319` / `8f58634`; `bbea097` / `ebf0261`; `22eae2e` / `076fb0c` | 18/18; Confidence 28/28 | מוזג ל-`main`; Production Verified: לא |
| 6 | F21 | Lifecycle Orchestrator — COLLECTING עד CLOSED | #166 | `9011923` / `2c55c59` | 13/13 | מוזג ל-`main`; Production Verified: לא |

**סיכום בדיקות Decision Hub:** ‏128/128 (33 + 28 + 25 + 11 + 18 + 13). כל השלבים
1–6 קיימים ב-`main`; דגלי הפיצ'ר נשארים כבויים כברירת מחדל, ואין כאן טענת פריסה או אימות
ידני בפרודקשן.

**Verification ראיה:** `py_compile` נקי על שלושת הקבצים; `session_store.py` self-test
18/20 עברו (2 כשלים קיימים מראש, mock-import-path בלתי תלוי בשינוי זה); אין אימות
בפרודקשן עדיין — דגל כבוי.

**Stage 1 — Trust Layer (Rev 2):** `gate_trust` מחושב לפי `AUTHORITY_SCORE`×`MEDIUM_SCORE`
(`compute_trust`/`score_to_level`), `extract_claim_topic` אוטומטי (4 מקורות + ידני כ-fallback,
מורחב ל-(topic, source, confidence) סביב 2 השדות שאליהו הוסיף מעבר לספק — `Claim Topic Source`/
`Claim Topic Confidence`), `maybe_supersede` בטוח (אותו Claim Topic בלבד + Trust גבוה יותר בלבד).
**9 סטיות מהטקסט המילולי של הספק, מתועדות (לא הוסתרו):**
1. `VerifierPort.verify()` מחזיר `dict` לא object — שונה ל-`{"status": ..., "reason": ...}`.
2. `decision` שמועבר ל-`run_pipeline` הוא `decision["fields"]` בלבד (אין `"id"`) — `maybe_supersede`
   קורא את ה-ID מ-`event["_decision_id"]` שמוזרק ב-`cmd_decision.py` לפני הקריאה, לא מ-`decision["id"]`.
3. Tags: "potential_conflict"/"low_confidence"/"pressure_high_risk" (אנגלית, בספק) לא קיימים
   כאופציות Multi-Select חיות — נעשה שימוש ב-`DecisionEventTag.CONFLICT`("קונפליקט") הקיים,
   ונוספו 2 קבועים עבריים חדשים (`LOW_CONFIDENCE`="אמינות_נמוכה", `PRESSURE_HIGH_RISK`="לחץ_סיכון_גבוה")
   **שלא אומתו מול Airtable חי** — ייתכן שיידרש ליצור אותם כאופציות לפני כתיבה ראשונה בפרודקשן.
4. `_has_keyword_conflict()` — הספק מפנה לפונקציה זו (§5 שלב ו') אך לא הגדיר את גוף הלוגיקה כלל.
   מומשה כ-stub שמחזיר `False` — נתיב ה-"potential_conflict"/`DecisionEventTag.CONFLICT` לא ייושם
   בפועל עד שתוגדר לוגיקת ה-keyword-conflict (Stage 1.x/Stage 2).
5. `DecisionSourceReliability` היו חסרים 4 מתוך 10 מפתחות `AUTHORITY_SCORE` — נוספו
   `DOCUMENT`/`MANUAL`/`EMPLOYEE`/`UNKNOWN`.
6. `event["Channel"]`/`event["Source Reliability"]` לא היו מועברים ל-`gate_trust` כלל לפני התיקון —
   Channel תוקן ב-2 נקודות הקריאה ב-`cmd_decision.py` (`_handle_update_step`/`_link_inbox_to_decision`).
   **Source Reliability עדיין לא מוזן ע"י שום UI קיים** — `gate_trust` ייפול תמיד ל-default "ידני"
   (ציון authority=55) עד שתיווסף שאלת "מי אמר/כמה אמין" לדיאלוג `/decision update` — מחוץ לטקסט
   המילולי של הספק, לא תוקן בסבב הזה.
7. פלטי ה-Trust Layer לא נכתבו ל-Airtable כלל — `_create_decision_event`/`event_fields`
   (`_link_inbox_to_decision`) הורחבו עם `_add_trust_fields()` חדשה (Trust Level/Confidence/Tags/
   Claim Topic+Source+Confidence/Source Reliability/Supersedes).
8. `run_pipeline()` היה מזניח את `user_flag` של שערים שעברו (fabricate `GateResult` חדש) —
   נוסף `collected_flag` שעוקב ומועבר ל-`GateResult` הסינתטי בסוף, כדי שההודעה "לא זיהיתי נושא"
   (T2/T3) תוצג בפועל.
9. `_format_pipeline_outcome` לא טיפל ב-`halted_at == "trust"` ולא בדק `result.user_flag` בנתיב
   ההצלחה — נוסף branch מפורש + הצמדת `user_flag` להודעת ההצלחה.

**§10 פריט 11 (אימות פרודקשן — T0 אמיתי → user_flag בטלגרם) נשאר פתוח עד פריסה.**
**קבצים שנוספו/שונו:** `airtable_schema.py` (קבועים), `decision_ports.py` (verifier stub),
`decision_pipeline.py` (Trust Model מלא), `cmd_decision.py` (חיווט), `test_decision_trust.py`
(33 self-tests, כולם עוברים).

### N-LEAD-EVENT — Lead Events Layer ✅ הושלם (28-29/06/2026)
**מה:** `Tables.LEAD_EVENTS`, `capture_lead_event()`, `LeadEventFields`/`LeadEventType`.
ליד קיים + הודעה חדשה → Event נכתב אוטומטית עם `event_type`, `domain`, `message`.
**קבצים:** `lead_capture.py`, `airtable_schema.py`
**Evidence:** Lead Events table + Link to Lead — אומתו ב-Airtable
**PR:** #171, #172

### N-CXX — Action Integrity Contract ✅ הושלם (28/06/2026)
**מה:** `core/action_result.py` + `core/request_context.py` + `core/claim_gate.py`.
`ActionResult` dataclass עם 5 שלבים. `ClaimGate` — FOUND ≠ CREATED.
**Evidence:** 16/16 claim_gate tests, 33/33 anti_hallucination tests
**PR:** #169

### N-LEADBUF — Lead Buffer ✅ הושלם (29/06/2026)
**מה:** `core/lead_buffer.py` — thread-local buffer per-request.
מונע אובדן payload כשAgent נחסם ע"י Leads Write Gate.
**Evidence:** 22/22 buffer tests
**PR:** #176

### N14 — Core Reasoning Layer (F22) ✅ הועלה ל-`main` ישירות (28/06/2026)
**מה:** `core/reasoning_entity.py` + `core/reasoning_ports.py` + `core/reasoning_engines.py` + `core/adapters/decision_adapter.py` + `core/adapters/leads_adapter.py`.
Pull-only reasoning engine. `run()` מחבר Stages 1→2→4→6. `RequestState(domain, session)` — per-request mutable context.
**בדיקות:** `test_core_reasoning.py` 59/59 (A:5, B:5, C:11, D:13, E:15, F:10); `test_core_reasoning_integration.py` 58/58 + 2 xfail מתועדים.
**ספקים:** `SPEC_Core_Reasoning_Layer.md` + `SPEC_Stakeholder_Pressure_Pattern.md` (v2).
**מצב:** EXISTS_UNWIRED — `append_reasoning_block()` נקרא רק מ-`cmd_decision.py._format_decision_card()` כ-fallback (F22-WIRE, PR #177), `run()` ו-`core.adapters.leads_adapter` טרם חוברו לpipeline חי.

**Quality Gate 30/06/2026:** 5 בעיות נמצאו. 2 תוקנו (missing_penalty + domain drift).
2 formula injection (BUG-DH-03/04) — תוקנו בקוד 07/07/2026 (🟡 לא ממוזג/מאומת עדיין), ראה סעיף BUG-DH-03/04 למטה — עדיפות גבוהה לפני הפעלת `FEATURE_DECISION_HUB`.
2 xfail מתועדים (`domain_rules`, `lead_score`) — design decisions.
Stage 6 Orchestrator מוזג. CI ירוק ✅.

### N15 — Restricted-flow owner notification: `notify_owner` field is set but never consumed 🔲 PLANNED
**מה:** `RouteDecision.notify_owner` (`core/router/route_decision.py`) נקבע ל-`True` עבור
`Handler.RESTRICTED` (`core/router/router.py`) — אבל `grep -rn "\.notify_owner"` על כל הריפו
מראה שהוא **אף פעם לא נקרא** מחוץ ל-assertions בטסטים. אין שום מנגנון שמודיע בפועל לבעלים
כשמשתמש מוגבל מנסה פעולה חסומה — הנראות היחידה היא שורת `logger.warning(...)` בלוגי שרת
(`app.py`), לא push/הודעה שאדם יראה בפועל.
**רקע:** התגלה תוך כדי תיקון `_SINGLE_SPEAKER_FALLBACK`'s טענת-המשך כוזבת (PR #280) ואותה
בעיה בדיוק ב-`app.py`'s Restricted-flow tool loop (`"הבקשה נרשמה במערכת."` — קוד תוקן באותו
audit, ראה `git log` על `app.py`'s tool loop לקומיט המדויק) — שני המקומות תוקנו מיידית להיות
כנים על המצב הנוכחי (אין מנגנון). זה ה-backlog item המקביל: **להחליט בפועל**, לא רק לתקן ניסוח.
**להחליט:** (א) לבנות מנגנון התראה אמיתי לבעלים (ערוץ עדיין לא נקבע — Telegram push? לוג
מרכזי שנבדק אקטיבית?), או (ב) אם ההתראה מעולם לא הייתה נחוצה בפועל — להסיר את השדה/לפשט את
לוגיקת `Handler.RESTRICTED` במקום להשאיר שדה מת.
**עד שמוחלט:** ה-copy בקוד (`app.py`, `core/anti_hallucination.py`) כבר לא מבטיח העברה
שלא קיימת — זה סגר את הסיכון המיידי (claim-without-evidence), לא את שאלת המדיניות.

### N16 — Git Audit descope: ביטול N12, הפרדת GOV-02 מהבוט העסקי ✅ הושלם (21/07/2026)
**מה:** N12 (PR #108) חיבר את `daily_git_audit.py`/GOV-02 ל-`scheduler.py` של הבוט העסקי
וזיכה אותו בשליחה ישירה דרך `TELEGRAM_TOKEN`/`ELIYAHU_CHAT_ID` — כלומר תהליך הפרודקשן של
הבוט קרא Git ושלח לטלגרם, במקביל ל-Claude Code Routine נפרד שכבר עושה בדיוק אותה עבודה
(audit קריאת-ריפו + התראה) דרך תשתית שונה לגמרי. כפילות ארכיטקטונית — לא רק בעיית ניסוח.
**החלטת בעלים:** git audit הוא אחריות בלעדית של Routine; הבוט העסקי לא אמור להיות קשור
לריפו כלל, ושולח רק digest + התראות עסקיות.
**תוקן:**
1. `scheduler.py` — הוסרו לגמרי `_job_daily_git_audit`, `git_audit_time`, ורישום
   ה-`schedule.every()...do(...)` שלו (לא הושאר flag-gated — הודעת "AUDIT ABORTED" בפועל
   בטלגרם הוכיחה ש-`GIT_AUDIT_SCHEDULER` הודלק בפועל או שהסקריפט הורץ ידנית בסביבה עם
   פרטי הטלגרם — flag-off לבדו לא מנע את זה בעבר, ולכן לא מספיק כתיקון).
2. `daily_git_audit.py` — `_send_telegram()` הוסרה כליל, שני call sites (GOV-02 STOP +
   דוח סופי) הפכו ל-`print()` בלבד; הקובץ מדפיס ל-stdout, לא שולח כלום בעצמו. docstring
   עודכן לתעד מפורשות: repo tool בלבד, ללא קשר ל-app.py/scheduler.py/TELEGRAM_TOKEN.
3. `feature_flags.py` — דגל `GIT_AUDIT_SCHEDULER` הוסר (0 call sites נותרו אחרי #1).
   `.env.example` — `GIT_AUDIT_TIME` הוסר (env var מת).
4. `test_c86_scheduler_emergency_matrix.py`'s `SCHEDULER_JOB_NAMES` עודכן (הוסר
   `_job_daily_git_audit`, שכבר לא קיים).
**לא נגע:** `audit_truth_gate.py` (GOV-02) — נשאר בדיוק כפי שהיה, read-only tool בריפו,
זמין ל-Routine להריץ ישירות (`python3 audit_truth_gate.py`/`python3 daily_git_audit.py`).
**מצב נוכחי:** ✅ ממוזג ל-`main` (PR #424, commit `99981fb`). Production verified: לא עדיין
דווח בפירוש (אין דרך אקטיבית לבדוק "היעדר הודעה עתידית"; אין תקלת GOV-02 חדשה מאז).
ראה `CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` C155.

### N17 — Context Librarian: Follow-up Hardening & Verification Backlog 🔲 PLANNED (נרשם 27/07/2026)

**הקשר:** PR #475 (Re-verification Alignment, `89e2b4e`) יישר את `docs/context_librarian/`
מול PR #471 עבור ארבעת ה-nodes (`approvals`, `turn_coordinator`, `ux_f52`, `rp5`) — תיעוד/מטא-דאטה
בלבד, ללא שינוי runtime. במהלך אותו audit נמצאו שש נקודות המשך מחייבות שלא טופלו בכוונה
באותו PR. **אין לממש את כולן באותו PR; אין לערבב runtime, catalog hardening, production
verification ו-multi-session orchestration באותו PR.**

**עדכון 28/07/2026 — Librarian Hardening PR (סדר עבודה מחייב שלב 4) מוזג ל-`main`**
(PR #481, ענף `claude/context-librarian-hardening-n17`). אומת ב-grep ישירות על
`origin/main` לאחר המיזוג: `.json` catalog (10 קבצים), `_load_catalog_json`,
`_approximate_char_estimate`, `_CHARS_PER_APPROXIMATE_TOKEN`, ושלושת ה-CI steps
(`fetch-depth: 0`, `persist-credentials: false`, `pytest context librarian`) — כולם
קיימים בפועל ב-`main`. CodeRabbit על ה-PR: 5 ממצאים, 4 תוקנו (ניסוח README
לא-שמרני, תרגום הערות לעברית, `_path_char_estimate` שספר bytes במקום תווים,
`persist-credentials: false` — ממצא אבטחה אמיתי מ-zizmor), 1 נדחה כ-false positive
(דרישת ניתוב benchmark script דרך dispatcher — לא רלוונטי לסקריפט dev-only ללא
identity/tenant, אותה קטגוריה כמו `llm_fallback.py`; CodeRabbit אימת ומשך את
הממצא בעצמו).

**1. Token estimation hardening — ✅ מוזג ל-main, אומת.**
`_approx_tokens` שונה ל-`_approximate_char_estimate` (+ `_path_char_estimate` לגודל קובץ על
דיסק), עם הבהרה מפורשת בקוד/README/AGENT_CONSUMPTION_CONTRACT.md שזהו אומדן תווים, לא
token count אמיתי. הדיווח בבundle שונה מ-`approximate_token_budget` ל-
`approximate_char_estimate_budget` (+ תווית "NOT a real tokenizer count"). נכתב
`tools/context_librarian/benchmark_token_estimate.py` — משווה `chars/4` מול token count אמיתי
דרך `anthropic` SDK's `messages.count_tokens` (כבר תלות קיימת, לא נוספה תלות כבדה) על bundle
אמיתי לכל אחד מ-7 הפרופילים. **ה-benchmark לא הורץ** — סביבת הפיתוח הזו חסרת
`ANTHROPIC_API_KEY`, והסקריפט נכשל-סגור במקום להמציא מספרים. `_CHARS_PER_APPROXIMATE_TOKEN`
נשאר `4` ללא שינוי, לפי Rule 15 (אין טענה בלי אימות) — שינוי מקדם דורש קודם להריץ את ה-
benchmark ולתעד תוצאות אמיתיות ב-`docs/context_librarian/TOKEN_ESTIMATION_BENCHMARK.md`.
לא שונה שם ה-schema field הציבורי `maximum_approximate_token_budget` — נמנע breaking change
ל-schema 1.0 בכוונה (הוחלט מול המשתמש).

**2. Catalog format hardening — ✅ מוזג ל-main, אומת.**
כל 10 קובצי הקטלוג (`schema/*.yaml`, `layers/*.yaml`×6, `task_profiles/profiles.yaml`,
`decisions/canonical_boundaries.yaml`) שונו בפועל ל-`.json` (`git mv`, תוכן זהה בייט-לבייט —
כבר היה JSON תקני). `librarian.py`'s `_load_json_yaml`→`_load_catalog_json`, glob
`*.yaml`→`*.json`, כל ה-path strings עודכנו. עודכנו גם `README.md`,
`node_schema.json`'s `catalog_discovery` string, ורפרנס פנימי אחד בתוך `rp5.json`'s notes.
עודכנו גם שני רפרנסים חיצוניים ישנים ל-`.yaml` שנמצאו ב-
`SINGLE_SPEAKER_APPROVAL_UX_PRODUCTION_VERIFICATION_PLAN.md` ו-`DECISION_LOG.md`.
`validate` + מלוא `test_context_librarian.py` (44 בדיקות, כולל 6 חדשות) ירוקים.

**3. Query and profile-selection hardening — ✅ מוזג ל-main, אומת.**
הקוד כבר הבטיח את האינווריאנט structurally (`_selection_roles`/`_conditional_layers` — query
יכול רק להוסיף conditional evidence, לעולם לא להשמיט primary/required/mandatory). נוספו
regression tests מפורשים: garbage/ריק query על פני כל 7 הפרופילים לא משמיט אף primary/
required/mandatory node; query עוין הבנוי מ-`selection_terms` של layers מוחרגים לא מדליף
אותם (`core_reasoning_change`); ניסוחים שווי-משמעות בעברית/אנגלית מפעילים אותו conditional
evidence. תועד `selection_terms`/`query_terms` כ-controlled vocabulary יחיד ב-README.

**CI validation (חלק משלב 4) — ✅ מוזג ל-main, אומת.** נמצא ממצא קונקרטי: `test_context_librarian.py`
הוא pytest-only (אין `if __name__`), ולולאת ה-CI הקיימת `for f in test_*.py; do python "$f"; done`
מריצה אותו כ-no-op שקט (exit 0, אפס בדיקות בפועל) — 44 הבדיקות של הספרן מעולם לא רצו ב-CI.
נוספו שני steps ב-`.github/workflows/ci.yml`: `python -m tools.context_librarian validate`
ו-`pytest test_context_librarian.py` ייעודי.

**4. Live production verification — לא בוצע. אין להסיק מצב production מהקוד/מה-flag/מבדיקות.**
נדרשת הכנת Production Verification Plan נפרד עבור:
- האם `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` פעיל ב-staging/production בפועל;
- האם מתקבלת תשובה סופית אחת בלבד בפועל;
- האם callback עם `action_id:contract_id` עובד end-to-end;
- האם identifiers פנימיים אינם מופיעים בתעבורה חיה;
- האם RP5 מסווג נכון Gateway-owned approval turns;
- האם replay/stale callback אינם גורמים לביצוע נוסף.

לכל טענה: required evidence, why required, environment, test date, exact scope, supplied
evidence, missing evidence, allowed status. **אין לעדכן את הספרן ל-`production_verified` ללא
ראיה ישירה.**

**עדכון 09/08/2026 — סבב ראשון של live production verification עבור TC6/`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`:**
הבעלים סיפק Render dashboard env-var read, live application-log excerpt, ו-Telegram
transcript עבור contract `90671635-7dd9-42c7-a467-cc928b18a2a4` על deploy
`7dbddddbe84bbdffd813704094a7d583d948ea96` (live 03:25). מכסה בראיה ישירה:
- (1) הדגל פעיל ב-production בפועל — **כן**, מאומת (screenshot של env var `=true`).
- (2) מתקבלת תשובה סופית אחת בלבד בפועל — **כן**, בשלושת התרחישים שנבדקו (יצירה→pending,
  שאילתת סטטוס פעמיים, חסימת יצירה שנייה דרך BUG-122); הלוגים מראים `reply_owner=gateway`
  ו-`agent_calls=0`/`duplicate_reply_suppressed=true` בכל תרחיש.
- (4) identifiers פנימיים — שני לוגי `[UnifiedStatusFormatterShadow]` שנדגמו (שני התרחישים
  שהפיקו לוג כזה) דיווחו `record_id_leak=False tool_name_leak=False contract_id_leak=False`;
  זו הראיה המדויקת, לא הוכחה שאף identifier לא הופיע באיזשהו לוג יישום בחלון הזה — רק
  בשני הלוגים הספציפיים שנדגמו.

**לא כוסה בסבב הזה — נשאר `לא בוצע`:**
- (3) callback עם `action_id:contract_id` end-to-end — רק flow טקסטואלי (הודעות "מאשר"/"בטל")
  נבדק, לא כפתורי inline-callback אישור/דחייה.
- (5) האם RP5 מסווג נכון Gateway-owned approval turns — לא נצפה לוג RP5 ישיר בחלון הזה.
- (6) replay/stale callback אינם גורמים לביצוע נוסף — לא נבדק בסבב הזה.

**מסקנה:** אין לסמן את כל ששת סעיפי ה-checklist כ-`production_verified` — רק (1),(2),(4) יש
להם ראיה ישירה מהתאריך הזה. (3),(5),(6) נשארים פתוחים לסבב אימות נפרד.

**5. Multi-session coordination — טרם תוכנן, לא בוצע.**
ארכיטקטורה עתידית שבה Session A (research/librarian verification) ו-Session B
(implementation/review) עובדים במקביל ללא דריסה, כששני הסוכנים חולקים context קנוני זהה
מהספרן, וTurn Coordinator/שכבת coordination מנהלים ownership. הפתרון העתידי צריך לכלול:
session identifier; task/branch ownership; claimed files/claimed architectural areas; selected
profile; bundle hash; current gate; handoff status; stale detection; conflict detection לפני
שינוי; איסור על שני סוכנים שמשנים אותו ownership area ללא הכרעה. **אין להשתמש בזיכרון
process-local כמקור אמת לתיאום בין סשנים.** יש לתכנן זאת בנפרד לפני implementation.

**6. Context Librarian dogfooding — טרם תוכנן, לא בוצע.**
הספרן צריך בהמשך לנהל גם ידע על עצמו — nodes/claims עבור: catalog loader; schemas; profiles;
bundle builder; workflow gate; freshness; token estimation; verification process; CI
validation; known limitations; current rollout status. המטרה: השאלה "מה בנוי בספרן, מה אומת,
מה חסר ומה השלב הבא?" תיענה על ידי הספרן עצמו (עם מקורות וסטטוס), לא מזיכרון של סוכן.
בהמשך יש לבחון שימוש רחב יותר בספרן כבסיס ידע אמיתי למערכת, תוך שמירה על ההבחנה: **הספרן
הוא index ו-governance layer; הקוד, הנתונים והראיות נשארים מקורות האמת; bundle הוא mandatory
minimum context, לא תחליף למקורות; אין להפוך את הספרן למקור אמת מקביל.**

**עדכון 28/07/2026 — Verification Coverage Model plan (חצי מסעיף 6, תכנון בלבד) — ✅ מוזג
ל-`main` (PR #482, merge `ffa678a`), אומת ב-grep:** נכתב
`docs/context_librarian/VERIFICATION_COVERAGE_MODEL_PLAN.md` — מגדיר 6 ממדי coverage
(schema conformance; freshness; production-evidence coverage; test-path coverage כולל
pass/fail — הממד היחיד שדורש מנגנון חדש; authority-level justification; confidence
justification), איך זה יחושב דטרמיניסטית מה-catalog הקיים בלי runtime/מקור אמת חדש, הקשר
ל-Dogfooding (אותו מנגנון גנרי ישרת גם nodes על הספרן עצמו כשייכתבו), ו-non-goals מפורשים
(אין implementation, אין nodes חדשים, אין כתיבה אוטומטית ל-metadata). Dogfooding עצמו (כתיבת
ה-nodes) נשאר משימה נפרדת עתידית — מסמך זה מכסה את חצי ה-VCM של סעיף 6 בלבד.

**עדכון 28/07/2026 — non-inferiority pilot advancement (סעיף 5) — ✅ מוזג ל-`main`** (PR #483,
ענף `claude/context-librarian-non-inferiority-pilot`, merge `51d370b`), אומת ב-grep ישירות על
`origin/main` **— התקדמות ממשית, לא acceptance:**
תוקנו ישירות (grep+Read מול הקוד החי, לא הוסק מהמסמכים) ארבעת ה-nodes שהיו stale ב-preflight
27/07 (`approvals`, `turn_coordinator`, `ux_f52`, `rp5` — `last_verified_commit`/`valid_from`
רועננו, תוקנו ציטוטי שורה שסחפו). על בסיס זה, לכל חמש משימות ה-pilot: נבנה Authority Gold
Set בלתי-תלוי (subagent נפרד, ללא גישה לספרן/לשיחה — לפי הנחיית המשתמש המפורשת "תשתמש
בסאב-אייגנט בלתי-תלוי"), נבנה bundle מפורש (`Selected profile:` + `build`, gate `PROCEED`
בחמישתן), בוצע מחקר Librarian-track עצמאי (פתיחת מקורות מצוטטים, הרצת בדיקות), ולבסוף
subagent שני בלתי-תלוי סקר את המחקר מול ה-Gold Set. תוצאה: 1/5 (`tool_execution`) PASS
נקי; 4/5 עם ממצאי גילוי-חסר בדרגות Medium עד **Critical** (כולל תיוג שגוי של commit/branch
ב-`rp5_evidence_mismatch` שהתגלה בזמן כתיבת ה-packet — באותו רגע ה-`PROCEED` היה נכון רק
לענף ה-pilot, לא ל-`main`; לאחר מיזוג PR #483 גם `main` עצמו מציג כעת את אותם ארבעת nodes
מרועננים, `last_verified_commit: ffa678a7`, אומת ב-grep). שלוש משימות חשפו באג אמיתי,
מאושר-Gold-Set (`approval_ux`→BUG-150; `tool_execution`→
fail-open ב-`_execute_contract`; `turn_coordinator_routing`→BUG-130/BUG-140) — כולן בתחום ש-
`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` מגדיר כ-mandatory gate (Durable Atomic Approval /
ActionContract), ואין Cross-Layer Impact Matrix שלם לאף אחת — **לא בוצע implementation לאף
אחת מהן ב-PR הזה**, לפי אותו gate ולפי כלל ה-pilot עצמו לא לעקוף STOP אמיתי. פירוט מלא
(per-run records, חומרות, ציטוטים) ב-`docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md`
תחת "2026-07-28 non-inferiority pilot advancement". **Phase 1 acceptance עדיין לא
מבוסס** — Codex/Claude-Code dual-vendor bundle-hash equality לא בוצע; 4/5 משימות נכשלות
בקריטריון "zero material authority misses / zero Critical/High architecture defects".

**סדר עבודה מחייב:**
1. ✅ להשלים ולמזג Re-verification Alignment (PR #475, `89e2b4e`).
2. ✅ (היסטורי, `89e2b4e`) — התקף מחדש לאחר מיזוג PR #483. עריכות ניסוח לא-קשורות ב-`app.py`
   (PR #479/#480) הפכו שוב 4 מ-5 ה-nodes ל-stale זמנית; ריענון ה-nodes (PR #483, merge
   `51d370b`) עכשיו על `main` עצמו — אומת ב-grep. `main` שוב מציג חמש PROCEED, לא רק ענף
   ה-pilot.
3. 🔲 להשלים Production Verification Plan (סעיף 4 לעיל).
4. ✅ Librarian Hardening מוזג ל-`main` (PR #481): token estimation (סעיף 1); catalog
   format (סעיף 2); query/profile hardening (סעיף 3); CI validation. POST-MERGE
   VERIFICATION בוצע ישירות על `origin/main` (`AGENTS.md`) — כל הסמלים אומתו ב-grep.
5. 🟡 non-inferiority pilot — **✅ PR #483 מוזג ל-`main` (`51d370b`), התקדמות ממשית, לא
   הושלם.** 5/5 משימות עם Gold Set + מחקר + סקירה עצמאית. Phase 1 acceptance עדיין לא
   מבוסס — ראו עדכון 28/07 לעיל ואת המסמך המלא. **✅ Pilot Findings Remediation PR #485
   מוזג ל-`main` (`4e12bf5`), אומת ישירות ב-checkout+pytest על `origin/main`** — מתקן 4
   מ-5 ה-gaps שהפיילוט מצא בספרן עצמו (ראו עדכון 28/07 לעיל); לא מוכיח מחדש את הפיילוט
   ולא מטפל בשלושת הבאגים האמיתיים (BUG-150/BUG-130/BUG-140, fail-open) — עדיין חסומים
   ע"י CROSS_LAYER_AUTHORITY_CONTRACT_V1.md.
6. 🔲 לתכנן Multi-session Coordination (סעיף 5) — תכנון בלבד לפני implementation.
7. ✅ VCM plan מוזג ל-`main` (PR #482, merge `ffa678a`) — תכנון בלבד, אין implementation.
   Dogfooding (כתיבת nodes על הספרן עצמו) עדיין טרם תוכנן.
8. ✅ Consumption Enforcement planning — **PR #488 מוזג ל-`main`** (commit `abf2804`, אומת
   ב-grep ישיר על `origin/main`). מסמך התכנון (`docs/context_librarian/CONSUMPTION_ENFORCEMENT_PLAN.md`)
   עונה על הפער ש-PR #487 מצא (investigation discipline, לא קטלוג). 5 הערות סקירה
   (CodeRabbit) נפתרו + Cross-Layer Impact Matrix נוסף (ללא cross-layer risk) + כל החלטות
   ה-owner אושרו: מודל שכבתי (ledger + independent review חובה); waiver דורש independent
   approval ופג-תוקף בשינוי commit/profile/query; ledger disposable מקומית, מועלה כ-CI
   artifact (לא committed — היפוך החלטה קודמת); Option C נדחה לפרופוזל נפרד. PR #488 עצמו
   לא הכיל implementation.
9. ✅ N17 Context Librarian remediation (audit עצמאי של Codex) מוזג ל-`main` (PR #489,
   ענף `codex/context-librarian-audit-remediation`, merge `20914f2`) — סוגר את שני ה-gaps
   הקטנים שנשארו פתוחים מהעדכון הקודם: `FEATURE_AUTO_CAPTURE` ממופה עכשיו ב-
   `layer.turn_coordinator`; תיקון cross-platform לבדיקת נתיב מוחלט
   (POSIX/Windows); provenance מבחין `on_main_history`/`at_origin_main_tip`. Codex הסיר
   בעצמו את הצעת-התכנון המקבילה שלו (`SOURCE_CONSUMPTION_GATE_PLAN.md`) לפני המיזוג,
   ונדחה במפורש ל-PR #488 כמסמך הקנוני — אין כפילות תכנון.
10. ✅ Consumption Enforcement Phase 1 implementation — **PR #490 מוזג ל-`main`**
    (commit `7ee5c5b`, אומת ב-grep ישיר על `origin/main`). מיישם בדיוק את סעיפים 5.1–5.3 + 5.5 (החלק האופציונלי `required_for_conclusion`) +
    בדיקות הרגרסיה של סעיף 7 מהתכנית המאושרת (item 8), כפי שהתכנית עצמה קבעה כ-Phase 1
    (סעיף 8 ברשימת ה-rollout): `consumption_checklist()` וסעיף `## Consumption Checklist`
    חדש בכל bundle — **תוכן ה-bundle עצמו, לא flag-gated: מתווסף אוטומטית לכל `build`
    קיים.** (תת-פקודת ה-CLI `verify-consumption` וה-ledger format כן opt-in — שום דבר
    לא קורא להם עדיין.) ולידציה מלאה ל-Consumption Ledger (identity ברמת top-level וגם
    per-item כולל `production_claim`, waiver עם `approved_by`/`approved_at` שונה מ-
    `reviewed_by`, דחיית שדות מחושבים מזויפים כמו `unreviewed_sources`, קישור `path` בפועל
    ל-`item_id`, דחיית item_id לא-מוכר/כפול); `verify_consumption()` שמחשב
    `unreviewed_sources` בעצמו בלבד ומחזיר `CONSUMPTION: COMPLETE`/`CONCLUSION_BLOCKED`;
    תת-פקודת CLI חדשה `python -m tools.context_librarian verify-consumption`; שדה
    אופציונלי, backward-compatible `required_for_conclusion` על `bounded_local_expansions`
    (ברירת מחדל `true`, לא משנה שום bundle קיים). **סקירה עצמאית על הענף לפני מיזוג** מצאה
    4 פערים ממשיים ב-`verify_consumption()` המקורי (path לא נבדק מול item_id;
    `production_claim` לא היה חלק מזהות ה-ledger וניתן היה לעקוף דרישת evidence;
    `required_sources` לא הושווה ל-checklist המחושב; item_id לא-מוכר/כפול התקבל) — כולם
    תוקנו באותו PR, plus תיקון ל-`TypeError` לא-מטופל על `reason`/`evidence_reference`
    לא-string. 35 בדיקות רגרסיה חדשות (112/112 עוברות בסה"כ, `validate`/`smoke_tests.py`
    נקיים). **תופעת-לוואי אמיתית שטופלה:** הסעיף החדש מגדיל bundle במידה שחרגה
    מ-`maximum_approximate_token_budget` הקיים בחמישה profiles — עודכנו (רק המספר, לא
    מבנה ה-JSON): `approval_ux` 5200→7000, `tool_execution` 4000→6000,
    `turn_coordinator_routing` 15500→18500, `ux_f52_message` 4800→5500,
    `cross_layer_architecture` 7000→9000. **Phase 3 (CI blocking gate שמריץ
    `verify-consumption` בפועל + hard-must ב-`AGENT_CONSUMPTION_CONTRACT.md`) לא מיושם
    כאן** — לפי סעיף 8 של התכנית עצמה, Phase 3 ממתין לשימוש ראשון אמיתי ב-Phase 1
    (task אמיתי), ולא נפתח בסבב הזה. Phase 2 (`FEATURE_AUTO_CAPTURE`) כבר נסגר עצמאית
    ב-item 9 לעיל.
11. ✅ PR2 — Deterministic Approval Cost Cuts (תוכנית F52 — Unified Approval
    Runtime, לא N17 עצמו; מוזכר כאן כי הוא המשימה האמיתית הראשונה שהשתמשה במשמעת
    שה-Context Librarian/Consumption Enforcement נועד לאכוף — פירוט מלא ב-
    `CHANGE_CONTROL_LOG.md`/`CHANGELOG.md`, לא בסעיף F52 נפרד כאן): **PR #491**
    (preflight audit, `12e2a45`) + **PR #492** (implementation,
    `db51afc`) שניהם מוזגו ל-`main`, אומתו ב-grep ישיר. משתמש לראשונה במשמעת שה-Context
    Librarian/Consumption Enforcement (item 8-10 לעיל) נועד לאכוף — reading pack קנוני
    נבנה ידנית (`docs/architecture/f52-unified-approval-runtime/audits/PR2_READING_PACK.md`)
    מהמסמך הקנוני + מקורות תומכים מזוהים במפורש, כולל Cross-Layer Impact Matrix שהיה
    חסר ב-preflight ותוקן/אושר עם ה-owner. **הערה כנה:** ה-CLI בפועל (`verify-consumption`,
    Consumption Ledger) לא הופעל בסבב הזה — המשמעת יושמה ידנית, לא דרך הכלי הפורמלי;
    "השימוש הראשון האמיתי" ש-Phase 3 ממתין לו (item 10) עדיין לא קרה במובן המדויק.
    ריויו רב-שכבתי אימת את עצמו בפועל: הריויו שלי על ה-implementation תפס 3 סטיות
    מאילוצים מחייבים ותיקן אותן; CodeRabbit על ה-PR עצמו תפס עוד 7 באגים אמיתיים שהריויו
    הידני פספס — כולל אחד שביטל בשקט בדיוק את תיקון ה-24h bound שכבר אושר (`recent_terminal
    or find_most_recent_by_user()` נופל בחזרה להיסטוריה בלתי-מוגבלת כש-`recent_terminal`
    הוא `None` מפורש). כל 10 הממצאים (3+7) תוקנו ואומתו מחדש עצמאית לפני המיזוג.
    **עדכון 30/07/2026:** staging acceptance audit של PR2 (המשך item 11) הוליד 4 hotfixes —
    Hotfix A/#494 (BUG-151, מתועד ב-C181), Hotfix B/#496 (legacy cancel-word guard, C182),
    Hotfix E/#497 (shared replay-policy, C183), Hotfix C/#498+#499 ("תייצר" verb, C184) —
    כולם מוזגו ל-`main`. סבב אימות חי בפרודקשן (30/07/2026, שלושת הדגלים `true`) אישר:
    Hotfix E ✅, Hotfix C ✅, BUG-151's היכולת העסקית הכללית ✅ — כולם Verified בפרודקשן
    (האחרון: המסלול העסקי בלבד, **לא** תיקון #1/#2 עצמם — שניהם דורשים `CanonicalizationError`
    בפועל שלא קרה). שני פערים נשארו פתוחים: הממיר הספציפי `sheets_append→airtable_add`
    (BUG-151 Fix #1 בבידוד) עדיין לא נצפה חי; Hotfix B רדום כל עוד PR2 דלוק (verified by
    test בלבד). ראו
    `AI_CONTEXT.md`/`CHANGE_CONTROL_LOG.md` C182–C184 להוכחות מלאות. ממצא חדש לא-קשור נפתח
    כ-BUG-152 (בקשה חוזרת נעצרה פעם אחת, לא root-caused).
12. ✅ Multi-layer alignment (stages 3-5) — first real Consumption Enforcement pilot +
    catalog completeness fix — **PR #504 מוזג ל-`main`** (commit `55312ab`, אומת ב-grep
    ישיר). Run 1: פרופיל `cross_layer_architecture`, `PROCEED`/`CONSUMPTION: COMPLETE`;
    independent review מצא פער coverage אמיתי (Business Intent, Planning Gate, Master
    Plan, ROADMAP, Change Control Log, Message Contract V1/migration/implementation —
    חסרים מה-mandatory tier). Run 2: הפער נסגר בקטלוג (0 removed, 10 added), רה-verify:
    `CONSUMPTION: COMPLETE`. **Verdict נשאר `PASS_WITH_GAPS`** — סגירת הפער הנקודתי אינה
    independent review מלא וטרי על כל 117 הפריטים. **Phase 3 (CI-blocking gate) נשאר NOT
    READY** — פרופיל יחיד נבדק, בלי sample size מוגדר. ראו
    `docs/governance/librarian/FIRST_REAL_CONSUMPTION_PILOT.md` (§10, "Phase 3 readiness
    decision") ו-`docs/architecture/multilayer/BOSS_MULTILAYER_ALIGNMENT_PLAN.md`.

    **Backlog ממוקד לספרן, שנפתח על ידי הפיילוט הזה (רישום בלבד — אין implementation כאן):**
    - בדיקת פרופילים נוספים (מעבר ל-`cross_layer_architecture`) בפיילוט עתידי אמיתי.
    - קביעת sample size מפורש (כמה profiles/משימות אמיתיות) לפני שמוכנות Phase 3 יכולה
      להיטען.
    - מדדי recall/noise/token-budget כמותיים לפיילוט, לא רק קריטריוני קבלה איכותיים (§6
      של המסמך).
    - final-commit verification invariant — לוודא שזהות ה-ledger (commit/branch) נבדקת
      גם מול ה-commit הסופי לאחר merge, לא רק מול ה-branch tip בזמן בניית ה-ledger.
    - אכיפת independent-review trigger בכלי (לא רק כלל self-applied) — פער כבר מתועד
      ב-§1/§8 של המסמך.
    - Phase 3 owner gate מפורש — צ'קפוינט חתימת owner ייעודי לפני הפעלת ה-flag, נפרד
      מעמידה בקריטריונים הטכניים.

    אף אחד מהפריטים האלה אינו דורש שינוי runtime/CI/profile/pilot חדש כרגע — נרשם
    כ-backlog בלבד עד החלטת owner.

**קבצים:** `docs/context_librarian/` (הספרן עצמו, כולל `TOKEN_ESTIMATION_BENCHMARK.md` החדש),
`tools/context_librarian/librarian.py` (token estimation, catalog loading,
`consumption_checklist()`, `verify_consumption()`),
`tools/context_librarian/__main__.py` (`verify-consumption` CLI),
`tools/context_librarian/benchmark_token_estimate.py` (חדש), `test_context_librarian.py`,
`.github/workflows/ci.yml`, `docs/context_librarian/PHASE1_NON_INFERIORITY_PILOT.md`,
`docs/context_librarian/CONSUMPTION_ENFORCEMENT_PLAN.md` (סעיף 8, תכנון בלבד — item 10
מיישם רק את מה שהתכנית הזו כבר אישרה).

### N18 — Canonical Write Infrastructure (Lead System → Shared Write Framework) 🔲 בעבודה (נרשם 20/08/2026)

**הקשר:** Phase 1 (canonical Lead creation service, `core/lead_service.py`, ענף
`feat/canonical-lead-creation-phase1`, PR #780) נסגר — QA report מלא (15 תרחישים ממוספרים)
אישר את כל המסלול; הפער היחיד שנמצא בבנייה עצמה (structured note parsing, `/` כ-delimiter
חלופי ל-`|` שלא זוהה כלל ונפל בשקט למסלול ה-NLP) תוקן ואומת (commit `4e44bca`, 99/99 טסטים).
Phase 1 מסומן **הושלם** לפי קריטריון היציאה שהוגדר לו במפורש (owner decision).

**החלטה ארכיטקטונית (owner, 20/08/2026):** לא להמשיך לבנות מערכת לידים נפרדת. ה-Draft →
Field collection → Validation → Edit → Preview → Approval → Canonical write → Evidence →
Canonical UX response flow שנבנה עבור Lead הופך לתשתית כתיבה כללית של BOSS — Lead הוא
ה-consumer הראשון, לא היחיד. Entities עתידיים (Tasks/Payments/Deals/Contacts/Expenses)
צריכים לצרוך את אותה תשתית ולא לבנות מחדש draft/confirm/edit flow משלהם. עקרון מנחה:
**Parsing mechanics is shared. Field semantics belong to the entity schema.**
כלל המשך: **Never solve the same write interaction twice** — מנגנון שימושי ליותר מ-entity
אחד מקודם ל-shared infrastructure לפני שבונים entity נוסף עליו.

**שלבים (F — ללא תאריך, ימוספרו בנפרד עם תחילת מימוש כל שלב):**
- **Phase 2 — Shared Write Primitives ✅ סגור (21/08/2026, PR #807):** להוציא מ-Lead את
  ה-Draft/filling/edit/validation loop/confirm-cancel/structured parsing/terminal-turn-result
  לתשתית משותפת. Entity code
  מגדיר רק schema/required/optional/validators/business rules/defaults/permissions — לא
  בונה מחדש "איך שואלים שדה חסר"/"איך מאשרים"/"איך נשמר state".
  **התקדמות (20/08/2026):** שתי פרוסות ראשונות מוצו ומאומתות (99/99 טסטי Lead + טסטים
  ייעודיים לכל primitive, ללא שינוי התנהגות):
  (1) `core/structured_command.py` — מכניקת trigger/delimiter-detection/split של פקודות
  `<trigger> | field | field...`, מופרד מ-`parse_structured_command()` (commit `45ef423`).
  (2) `core/draft_flow.py` — מכונת המצבים הגנרית filling/edit_choice/review (כולל אוצר
  המילים כן/ערוך/לא, TTL, מעברי מצב) כ-`resolve_draft_reply(text, draft, DraftSpec)` טהור
  (ללא I/O, ללא כתיבה) — מופרד מ-`_resolve_lead_draft()`; Lead מספק רק `DraftSpec`
  (`core.lead_service.LEAD_DRAFT_SPEC`: שדות/prompts/validators/render). עדיין בליבת
  `lead_candidate_handler.py`, לא הועברו עדיין: structured-command field mapping (Lead-
  specific, נשאר ב-lead_service.py כמתוכנן), terminal-turn-result contract (Phase 4).
  (3) **Confirm/Cancel Dispatch Unification** (21/08/2026) — `app.py`'s early כן/לא-word
  interception קרא ל-`should_prefer_lead_draft()` עד 3 פעמים באותו turn (PR2 fast-path +
  ── 2.55 ── confirm + ── 2.55 ── cancel), כל אחד עם Sessions read עצמאי. מחושב עכשיו פעם
  אחת (`_prefer_draft_now`) ומשמש בשני הענפים — נקודת החלטה יחידה, ללא שינוי בהתנהגות
  (`resolve_lead_draft_confirmation`/`_finalize_draft_confirm`/`_finalize_draft_cancel` לא
  זזו — עדיין השלב הבא). `test_n18_draft_dispatch_unification.py` (חדש) מוכיח זאת
  end-to-end דרך `app.run_agent()`, לא רק ברמת ה-unit כמו section 9 הקיים ב-
  `test_lead_service_phase1.py`.
  (4) **clarification/validation-loop wiring** (21/08/2026, בדיקה בלבד — ראו למעלה) —
  התברר שכבר בוצע בפרוסה (2): `resolve_draft_reply()`+`LEAD_DRAFT_SPEC` הם המנגנון הגנרי
  המבוקש, ללא duplicate. נוסף רק טסט רגרסיה רציף חסר (section 7h, 5 assertions) שמוכיח
  שרשרת מלאה: invalid phone→נשאר→valid phone→invalid domain→נשאר→valid domain→review.
  זוהה (לא טופל, decision נפרד) ממצא נוסף: `_resolve_lead_clarification()` היא state
  machine נפרדת ומקבילה ל-organic Tier-5 capture (טלפון בלי שם) שאינה משתמשת ב-DraftSpec —
  ראו פירוט למעלה. terminal-turn-result נשאר אחרון (owner sequencing — כבר נוגע ב-
  single-speaker/UX).
  (5) **terminal-turn-result primitive, scope מצומצם** (21/08/2026, סוגר Phase 2 — ראו
  למעלה לפירוט מלא) — `core/turn_result.py` (חדש): `TurnResult(message, status)` דק,
  הוחל רק על נתיב ה-draft confirm/cancel הגנרי (`_finalize_draft_cancel`/
  `_finalize_draft_confirm`/`resolve_lead_draft_confirmation`/`_resolve_lead_draft`).
  `handle_lead_candidate()`'s חוזה חיצוני (`Optional[str]`) לא השתנה. במפורש לא טופל:
  ה-emoji string-sniffing ב-`_process_structured_file_upload` (`app.py:5725-5732`) ו-Phase 4
  המלא (UX Contract) — owner בחר מפורשות בסקופ המצומצם מול Phase 4 המלא.
- **Phase 3 — Canonical Writers:** איחוד כל Lead writers החיים (כולל אלה שעוקפים
  dispatcher/governance checks, שנמצאו באודיט) למסלול `create_lead(payload, context)` יחיד;
  כל מקור (Telegram/WhatsApp/UI/Campaign/API/Voice/Email) הופך ל-adapter שלא כותב בעצמו.
  `lead_capture.py` לא נשאר writer עצמאי — רכיבי parsing/enrichment שימושיים בו נשמרים,
  אך היצירה עצמה עוברת דרך ה-canonical service.
- **Phase 4 — UX Contract:** ה-service מחזיר structured result
  (`entity`/`operation`/`status`/`display_name`/`domain`/`owner`/`external_id`), לא
  final user-facing string; שכבת UX נפרדת מחליטה מה מוצג. Internal IDs (Airtable record
  IDs, contract/execution/field IDs) לא מוצגים כברירת מחדל — נשמרים ב-structured result
  ל-logs/evidence/debugging/idempotency בלבד. סוגר גם double-response אחרי הצלחה (turn
  ownership: `handled=true`/`terminal=true` חייב לעצור עיבוד נוסף של אותו turn ע"י general
  agent/handler אחר — primitive משותף, לא Lead-specific patch).
- **Phase 5 — Attribution + Lead Screen:** taxonomy קנונית ל-campaign attribution
  (source/platform/campaign/ad set/ad/creative/tracking IDs — `ad_attribution.py` נמצא
  כותב UTM fields שלא קיימים בסכימה החיה) ול-Score/Temperature/Status (נמצאו כמה
  taxonomies + חישובים שונים ב-backend/frontend). Business state קנוני, צבע = presentation
  בלבד.
- **Phase 6 — Downstream + Learning:** Lead → Task/Contact/Deal שומר attribution/ownership
  (כרגע חלקי/חסר); `lead_memory.py`/event writer/learning reader מתיישרים על אותו source —
  **לא כחלק מה-Lead Creation build**, רק אחרי שה-canonical write יציב.

**קבצים (Phase 1, סגור):** `core/lead_service.py`, `core/lead_candidate_handler.py`,
`test_lead_service_phase1.py` (99 טסטים).
**קבצים (Phase 2, סגור):** `core/structured_command.py` + `test_structured_command.py`
(11 טסטים), `core/draft_flow.py` + `test_draft_flow.py` (16 טסטים) — שני primitives
משותפים, ללא תלות ב-Lead; `core/lead_service.py`/`core/lead_candidate_handler.py` צורכים
אותם כעת במקום מכניקה מקומית. `app.py` (confirm/cancel dispatch unification) +
`test_n18_draft_dispatch_unification.py` (8 טסטים, end-to-end דרך `app.run_agent()`).
`test_lead_service_phase1.py` section 7h (5 טסטים חדשים — שרשרת רגרסיה רציפה דרך שני שדות,
clarification/validation-loop wiring, ראה (4) למעלה). `core/turn_result.py` (חדש, ראה (5)
למעלה) — אין טסט ייעודי (dataclass טריוויאלי, מכוסה דרך שימוש אמיתי ב-section 9 הקיים).
**מקור מלא:** דוח QA מלא + מסמך ההחלטה הארכיטקטוני הועברו ע"י הבעלים בצ'אט ב-20/08/2026 —
אין מסמך נפרד ב-`docs/` כרגע; אם/כשמתחיל מימוש Phase 2 בפועל, להעתיק את תוכן ההחלטה
ל-`docs/architecture/` ייעודי במקום להסתמך על ROADMAP בלבד.

### F17 — Decision Hub Stage 2: Smart Trust Layer (PR #157, מוזג ל-`main`, commit `9252b1e`/merge `78f9bae`)
**מה:** שכבת ביטחון על גבי Stage 1 — מסתכלת על ה-Decision כולו (לא Event בודד): האם
האירועים התומכים מסכימים, מה חסר, כמה ביטחון לפני חתימה. 4 יכולות: (1) AI Conflict
Detection — Lazy+Cached (תנאי אישור אליהו, לא Eager): רץ רק בפתיחת/Refresh של Decision,
לא ב-ingest, מוגבל ל-Claim Topic זהה + Trust>=T1, dedup לפי `event_pair_hash`, מוגבל
ל-`_MAX_AI_COMPARISONS_PER_RUN=5` קריאות Claude חדשות לריצה (זוגות ב-cache לא נספרים).
(2) Evidence Graph — `evidence_ids`/`evidence_summary` על ה-Decision. (3) Decision
Confidence Score — ממוצע משוקלל של Trust מינוס 0.15×קונפליקטים, clamped [0,1]. (4)
Missing Evidence Detector — בדיקת מילת-מפתח (לא LLM) מול תבנית `REQUIRED_EVIDENCE` לפי
Domain.
**זה ממלא בפועל** את ה-stub `_has_keyword_conflict()` שStage 1 השאיר פתוח (ראו N13 סטייה
4 למעלה) — לא כתחליף, אלא כאיתות AI מקביל (`DecisionEventTag.CONFLICT`).
**3 סטיות מהטקסט המילולי של הספק, מתועדות:**
1. הספק כתב `core/decision_confidence.py` — נכתב ב-root, לצד `decision_pipeline.py`/
   `decision_ports.py`/`cmd_decision.py` (שאר מודולי Decision Hub), לעקביות ארכיטקטונית.
2. הספק הגדיר `REQUIRED_EVIDENCE` לפי "decision_type" — קונספט שלא קיים בסכמה (ל-Decisions
   יש רק Domain). נמופה על `DecisionDomain` הקיים (`REAL_ESTATE`/`IMPORT`/`PARTNERSHIP`/
   `RECRUITMENT`/`GENERAL`); `IMPORT` ו-`PARTNERSHIP` משתפים את אותה רשימת ראיות (אין
   ל-spec רשימה ספציפית יותר לאף אחד מהם).
3. הספק הניח `get_decision()` — פונקציה כזו לא קיימת. החיווט נעשה ב-`_format_decision_card()`
   (הנקודה הקיימת היחידה שמרכיבה כרטיס Decision מלא, נקראת מ-`/decision status`, כבר
   מאחורי `FEATURE_DECISION_HUB`).
**שדות Airtable חדשים (לא נוצרו עדיין ביד):** `Evidence Ids` (Long text JSON), `Evidence
Summary` (Long text), `Confidence Score` (Number 0.0-1.0), `Missing Evidence` (Long text
JSON) — `airtable_patch()` משמיט שדות לא-מוכרים בשקט (`schema_cache.json` עדיין לא מכיר
אותם), כך שתצוגת הטלגרם תקינה בלי תלות בהשלמת השדות; הפרסיסטנס הוא best-effort עד שהם
ייוצרו ו-`schema_audit.py` ירוץ מחדש.
**Verification ראיה:** `py_compile` נקי על `decision_confidence.py`/`cmd_decision.py`/
`airtable_schema.py`/`app.py`; `test_decision_confidence.py` 25/25 עוברים (`detect_conflict_ai`
מ-mock — אפס קריאות רשת); `test_decision_trust.py` 33/33 ללא רגרסיה; `smoke_tests.py` —
אותם 2 כשלים קיימים מראש (`flask`/`httpx` חסרים בסביבה), אין כשלים חדשים.
**קבצים שנוספו/שונו:** `decision_confidence.py` (חדש), `cmd_decision.py`
(`_format_confidence_block`/`_persist_confidence`/`_list_decision_events` + תיקון רגרסיה
ב-`_latest_event` inline שבדק `not events` הפוך), `airtable_schema.py` (4 קבועי שדה חדשים),
`test_decision_confidence.py` (חדש, 25 self-tests).
**מצב נוכחי:** מוזג ל-`main` (PR #157, commit `9252b1e`, merge commit `78f9bae`) —
אומת עצמאית דרך `mcp__github__pull_request_read` (`merged:true`) + `git merge-base
--is-ancestor`. **פריסה ל-Render לא אומתה** (אין גישת dashboard/egress מה-sandbox), דגל
`FEATURE_DECISION_HUB` כבוי כברירת מחדל. Stages 3–6 מוזגו לאחר מכן; ראו F18–F21.

### F18 — Decision Hub Stage 3: Readiness Engine (PR #159, מוזג ל-`main`, commit `84cfcff`/merge `50f6351`)
**מה:** שכבה מעל Stage 1+2 שעונה: האם ה-Decision מוכנה להכרעה אנושית? `calc_readiness()`
מקבל `decision`/`events`/`confidence_result` (Stage 2's `ConfidenceResult` — לא מחושב
פעמיים, אין קריאת AI Conflict Detection כפולה) ומחזיר `ReadinessResult`
(`status`∈{READY,NOT_READY,REVIEW}, `score`, `blockers`, `missing_info`, `escalation`,
`user_message`, `can_decide`). **READY הוא איתות בלבד — לא מבצע שום פעולה** (לא Gateway,
לא app.py, לא טבלה חדשה, לא auto-action). 8 חוקי הספק + 3 הספים יושמו כלשונם: T0 פעיל
חוסם READY; חשיפה משפטית/כספית עם ראיות חסרות → REVIEW (anomaly) ולא יכול ל-READY בכל
מקרה (חוסם); Confidence Score<0.75 → לא READY; קונפליקטים פתוחים → REVIEW; Missing
Evidence לא ריק → חוסם; אירועי "לחץ בלבד" מסוננים לפני בדיקת "ראיות T2/T3 מספיקות" ולכן
לעולם לא משדרגים מוכנות (גם אם Trust שלהם T3) — נבדק ישירות ב-test (`pressure-only` case).
4 תבניות escalation מיושמות כלשונן (עו"ד/רו"ח-יועץ פיננסי/עמדת שותף/מסמך תומך).
**Single Source of Authority (MODULE_RULES):** `DecisionFields.READINESS` ו-
`class DecisionReadiness` (READY/NOT_READY) **היו קיימים מראש** ב-`airtable_schema.py`
(עם הערה "Stage 3 fills, default empty") — נבדק לפני כתיבת קוד חדש, לפי כלל ה-SoA.
הורחב (לא הוחלף) עם `REVIEW` — ערך חדש, **לא מאומת** כאופציית singleSelect חיה ב-Airtable
(אותה תבנית best-effort-write כמו שדות Stage 2 שלא נוצרו עדיין). `detect_missing_evidence()`
מ-Stage 2 נקרא ישירות (לא משוכפל) — Stage 3 לא קורא לשדה `Missing Evidence` המאוחסן
ב-Decision כדי למנוע race עם נתון לא-טרי מאותה בקשת תצוגה.
**1 סטייה מהטקסט המילולי של הספק, מתועדת:** הספק מציין "Stakeholders if available" ב-
Inputs, אבל חתימת `detect_escalation(decision, result)` (כפי שהוגדרה במפורש בספק) אינה
מקבלת `events`/stakeholders בנפרד. "עמדת שותף" (partner-disagreement) מזוהה לכן רק
דרך אות עקיף — קונפליקט פתוח שמופיע ב-`blockers` — ולא דרך ניתוח ישיר של Stakeholder
records. אם בעתיד תידרש הבחנה מדויקת יותר (איזה שותפים בדיוק חלוקים), יידרש שינוי חתימה
ואישור נפרד.
**Daily Digest hook (ספק §4, "אופציונלי, רק אם קיימת נקודת חיבור נקייה"):** נבדק –
`daily_digest.py` לא מזכיר Decision Hub בכלל, אין נקודת חיבור קיימת. **דולג** לפי
האופציונליות המפורשת של הספק עצמו — לא נוסף קוד חדש ל-`daily_digest.py`.
**חיווט:** `cmd_decision.py`'s `_format_confidence_block()` שונה להחזיר `(text,
ConfidenceResult)` במקום `text` בלבד (כדי שלא יחושב Stage 2 פעמיים); `_format_readiness_block()`
ו-`_persist_readiness()` נוספו במקביל ל-`_format_confidence_block`/`_persist_confidence`
הקיימים, נקראים מ-`_format_decision_card()` (אותה נקודת תצוגה קיימת — `get_decision()`
לא הומצאה, כמו ב-F17).
**פרסיסטנס:** רק `DecisionFields.READINESS` (שדה שכבר היה מוגדר) נכתב, best-effort, דרך
`airtable_patch`. Score/Message/Escalation **לא נשמרים** — תצוגת Telegram בלבד, לפי הנחיית
הספק "Prefer no schema change for MVP… add only after approval".
**Verification ראיה:** `py_compile` נקי על `decision_readiness.py`/`cmd_decision.py`/
`airtable_schema.py`/`test_decision_readiness.py`; `test_decision_readiness.py` 25/25
עוברים (6 ה-cases מהספק + מקרי גבול נוספים); `test_decision_confidence.py` 25/25 ו-
`test_decision_trust.py` 33/33 ללא רגרסיה; `smoke_tests.py` — אותם 2 כשלים קיימים מראש
(`flask`/`httpx` חסרים בסביבה), אין כשלים חדשים.
**קבצים שנוספו/שונו:** `decision_readiness.py` (חדש), `cmd_decision.py`
(`_format_confidence_block` שונה להחזיר tuple, `_format_readiness_block`/`_persist_readiness`
נוספו), `airtable_schema.py` (`DecisionReadiness.REVIEW` נוסף), `test_decision_readiness.py`
(חדש, 25 self-tests).
**מצב נוכחי:** מוזג ל-`main` (PR #159, commit `84cfcff`, merge commit `50f6351`) —
אומת עצמאית דרך `mcp__github__pull_request_read` (`merged:true`) + `git merge-base
--is-ancestor`. ענף המקור `claude/new-session-be1ckb` נמחק מה-remote אחרי המיזוג. **פריסה
ל-Render לא אומתה** (אין גישת dashboard/egress מה-sandbox), דגל `FEATURE_DECISION_HUB`
כבוי כברירת מחדל. Stages 4–6 מוזגו לאחר מכן; ראו F19–F21.

### F19 — Decision Hub Stage 4: Attention Engine (PR #161, מוזג ל-`main`, commits `3e79a03`/`1281dda`, merge `fb4d041`)
**מה:** מנוע read-only ודטרמיניסטי לדירוג החלטות הדורשות תשומת לב. `calc_priority()` מחשב
עדיפות מסיגנלים קיימים (readiness ישן, deadline, לחץ עם שינוי אמיתי, שינויי עמדה, חוסר
פעילות ומידע חסר); `detect_attention()` מדרג רשימה; `build_attention_summary()` מציג בכרטיס.
ה-policy מבודד ב-`decision_attention_policy.py`; אין sender/writer חדש ואין פעולה אוטומטית.
**Verification ראיה:** `test_decision_attention.py` ‏11/11. המיזוג קיים ב-main.
**מצב נוכחי:** מוזג; `FEATURE_DECISION_HUB` כבוי; Production Verified לא אומת ידנית.

### F20 — Decision Hub Stage 5: Auto Ingestion (PRs #162–#164, מוזג ל-`main`)
**מה:** `decision_auto_ingestion.py`/`ingest_message()` בנוי לנתב WhatsApp/email/document/voice
ל-Decision Inbox בלבד, raw-first, ללא כתיבה ל-Decision canonical. PR #162 הוסיף את
`decision_auto_ingestion.py` (commit `9b97319`, merge `8f58634`); PR #163 חילץ matcher משותף
(commit `bbea097`, merge `ebf0261`); PR #164 הוסיף missing-evidence penalty ל-confidence
(commit `22eae2e`, merge `076fb0c`). `FEATURE_DECISION_AUTO_INGESTION` כבוי כברירת מחדל.
**Verification ראיה:** ancestry של שלושת ה-commits מול main + grep פיזי; Auto Ingestion
18/18 ו-Confidence 28/28 — אבל הבדיקות מריצות את `ingest_message()` ישירות כפונקציה טהורה,
לא דרך אף נתיב הודעה נכנסת אמיתי.
**⚠️ ממצא Governance (29/06/2026):** `decision_auto_ingestion.py` **מוזג אך לא מחובר**.
grep מלא על הריפו (`grep -rln "decision_auto_ingestion"`) מוצא קריאה רק מתוך הקובץ עצמו
ומתוך `test_decision_auto_ingestion.py` — אין שום קריאה מ-`app.py`, `inbound_handler.py`,
`email_inbound.py`, `voice_adapter.py`, או נתיב מדיה/document כלשהו. `decision_matching.py`
(ה-matcher המשותף שחולץ ב-PR #163) **כן מחובר**, אך בנפרד — דרך `cmd_decision.py::_suggest_decision_link()`
בזרימת Forward-to-Inbox הטלגרמית, לא דרך F20. הוחלט **לא** לחבר את F20 לנתיבי ה-inbound
החיים כחלק מתיקון governance זה (חיווט לתוך `app.py`/`inbound_handler.py`/`email_inbound.py`/
`voice_adapter.py` הוא שינוי ארכיטקטוני, לא תיקון תיעוד — מנוגד לדרישת "Do not create new
architecture" של המשימה). נוסף guard ב-`smoke_tests.py` (`check_decision_hub_call_sites`)
שיכשל אם מישהו "יתקן" את הדגל הזה ל-wired=True בלי קריאה אמיתית, או יסיר את הקריאות הקיימות
של F19/F21/decision_matching בלי לעדכן את המסמך הזה.
**מצב נוכחי:** מוזג ל-`main`; **לא מחובר לאף pipeline חי** (merged-but-unreachable); Production
Verified לא אומת ידנית; `FEATURE_DECISION_AUTO_INGESTION` חייב להישאר כבוי עד שיוחלט במפורש
לחבר (אופציה a) או להותיר כקוד מתועד-לא-פעיל (אופציה b — המצב הנוכחי).

### F21 — Decision Hub Stage 6: Lifecycle Orchestrator (PR #166, מוזג ל-`main`, commit `9011923`/merge `2c55c59`)
**מה:** orchestrator pull-only/read-only שמחזיר `OrchestratorResult` עם phase, מצב נוכחי,
צעד הבא, אחראי וחסמים. הניתוב הוא first-match בין `NOT_READY`, stakeholder פתוח,
confidence נמוך, readiness REVIEW, READY/high-confidence ומצבים סופיים. Stage 6 משתמש
ב-`precomputed_confidence` של Stage 2; fallback מפעיל `calc_confidence(..., conflicts=[])`
בלבד ולכן אינו יוזם AI conflict detection. החיבור ל-`_format_decision_card()` משתמש ב-readiness
שחושב באותה בקשה וב-snapshot שאינו משנה את הרשומה המקורית; כל כשל משמיט רק את בלוק Stage 6.
**קבצים:** `decision_orchestrator.py`, `cmd_decision.py`, `test_decision_orchestrator.py`.
**Verification ראיה:** Stage 6 ‏13/13; Decision Hub ‏128/128; post-merge `git pull origin main`
+ grep פיזי על `OrchestratorResult`/`orchestrate`/`append_orchestrator_to_card` והחיווט בכרטיס.
**מצב נוכחי:** מוזג ל-main. Vercel preview היה ירוק; **Production Verified: לא** — נדרש
אימות ידני של הפריסה והזרימה החיה לפני שינוי הסטטוס.

### F22 — Core Reasoning Layer (הועלה ישירות ל-`main` ב-28/06/2026 23:06–23:09, לא דרך PR/session)
**מה:** שכבת "מנוע הרצה" משותפת שמתכננת לאחד Stages 1/2/4/6 (Trust/Confidence/Attention/
Orchestrator) מאחורי API יחיד (`core/reasoning_engines.run(entity, ports) -> ReasoningResult`),
עם entity/ports גנריים (`core/reasoning_entity.py`, `core/reasoning_ports.py`) ו-Adapters
ל-Decision ול-Leads (`core/adapters/decision_adapter.py`, `core/adapters/leads_adapter.py`)
שכל אחד מהם חושף `append_reasoning_block()` כ"נקודת חיבור" מתועדת בקוד (`# Integration
point: call append_reasoning_block() from ...`).
**Verification ראיה:** `test_core_reasoning.py` ‏59/59 עוברות; `py_compile` נקי.
**⚠️ ממצא Governance (29/06/2026) — לא תועד בכלל לפני זה:** קיים ב-`main`, נבדק, אך
**אפס נתיב הרצה חי**. grep מלא: `reasoning_engines`/`ReasoningEntity`/`decision_adapter`/
`leads_adapter`/`append_reasoning_block` מופיעים רק בתוך `core/` עצמו ובקובץ הבדיקות שלו —
אין קריאה מ-`cmd_decision.py`, `app.py`, או כל entrypoint חי אחר. בנוסף, ה-commits שהציגו
את הקבצים (`92fb0c3`, `1ee9b6c`, וקבצי `__init__.py` נלווים) הם "Add files via upload" ישירות
על `main`, לא PR עם CI — לא עברו את שרשרת הבדיקה הרגילה (backend-ci) לפני שהגיעו ל-main.
נוסף ל-`smoke_tests.py::check_decision_hub_call_sites` כך שאם מישהו יתחבר בעתיד (יוסיף קריאה
אמיתית מ-`cmd_decision.py` או דומה ל-`append_reasoning_block`) בלי לעדכן את ה-manifest שם
ל-`expected_wired=True`, ה-check ימשיך "להצליח בטעות" — ה-manifest עצמו הוא מקור האמת
ועליו לעודכן יחד עם החיווט, לא רק כתגובה לכשל.
**מצב נוכחי:** קוד קיים, נבדק (unit-level בלבד), **לא מחובר** לאף pipeline חי. אין דגל feature
ייעודי — מאחורי `FEATURE_DECISION_HUB` דרך `core/reasoning_engines.FEATURE_FLAG` בלבד, אבל זה
לא רלוונטי כל עוד אין קורא. אין כאן עדיין "פיצ'ר" במובן המוצרי — שכבת תשתית בלי משתמש.

**עדכון 29/06/2026 — `decision_adapter` חובר (`leads_adapter` נשאר לא מחובר):**
`cmd_decision.py._format_decision_card()` קורא ל-`core.adapters.decision_adapter.append_reasoning_block()`
כ-fallback block, **רק כש-`FEATURE_DECISION_HUB` כבוי** (`not is_enabled(decision_orchestrator.FEATURE_FLAG)`).
הסיבה: `append_orchestrator_to_card()` (F21, Stage 4/5) ו-`append_reasoning_block()` (Stage 6)
מציגים בעיקרם את אותו מידע (state/phase, confidence bar, צעד הבא, אחראי) — הצגת שניהם יחד
בכרטיס אחת תיצור כפילות ויזואלית, לא ערך מוסף. נבדק ונקבע מול המשתמש דרך `AskUserQuestion`
לפני המימוש. `core.adapters.leads_adapter` **עדיין לא מחובר** — אין caller חי, נשאר
`expected_wired=False` ב-`smoke_tests.py::DECISION_HUB_ENTRYPOINTS`.
`smoke_tests.py::check_decision_hub_call_sites` עודכן בהתאם (`core.adapters.decision_adapter`
→ `expected_wired=True`) ועובר. `core.reasoning_engines` עצמו נשאר `expected_wired=False` —
הוא מיובא רק מתוך `decision_adapter.py` (לא ישירות מקובץ entrypoint חי), והבדיקה בודקת ייבוא
ישיר בלבד, לא טרנזיטיבי.

### F23 — BOSS Marketing Bridge (M1: Core Marketing Exit)

**מה זה, בקצרה:** Demand → intake conversational (שאלות ספציפיות לפי Demand Type) →
Brief (דטרמיניסטי) → AI חיצוני (קריאה יחידה) → 3 רעיונות → בחירה אנושית (כפתור בטלגרם) →
Production Handoff (דטרמיניסטי) → Asset (Media Files/Drive קיימים) → Publication ידנית →
Attribution (Source Code). נבנה אחרי audit מקיף שבדק reuse מול Ventures/Decisions/
Interaction Log/Sessions — כולם נפסלו מסיבה מבנית (ראה `BOSS_MEDIA_MARKETING_AUDIT.md`,
עודכן 14/08/2026: מוזג ל-main מענף `docs/media-marketing-enablement-audit`); רק 3 טבלאות
חדשות קטנות נוצרו בפועל.

**נקודת כניסה חיה:** `/marketing_new` בטלגרם (wizard, לא ID-argument commands — ראה למטה).

**היסטוריית build, PR-by-PR (חשוב לקרוא בסדר — כל PR תיקן פער אמיתי בקודם):**
- **PR #601** (`5774db6`/`f33fc43`) — הבנייה הראשונית: טבלאות, gateway, brief composer,
  ופקודות `/marketing_brief`+`/marketing_handoff` שדרשו **Airtable record ID כארגומנט
  גלוי בטקסט**.
- **PR #602** (`ca05628`) — **תוקן ע"י הבעלים בבדיקה חיה, לא ע"י review**: חשיפת
  record ID גלוי מפרה עיקרון נעול בקודבייס (`decision.ux_no_internal_ids`,
  `docs/architecture/f52-unified-approval-runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md`).
  נבנה מחדש כ-wizard `/marketing_new` ללא ID גלוי בכלל — ה-ID עובר רק בתוך
  `callback_data` הבלתי-נראה של טלגרם, בדיוק כמו `cmd_update.py`.
- **PR #603** — "Manual Context Brain": שכבת ה-`DomainProfile` הייתה כמעט ריקה (משפט
  persona גנרי אחד + משפט key_points גנרי אחד שחוזר על ידע קופירייטינג שהמודל כבר יודע
  לבד) — ולכן 3 הרעיונות שה-AI מייצר יצאו דומים מדי ושטחיים. הוחלף `key_points` ב-
  `business_rules` — כללים עסקיים **אמיתיים וייחודיים** (recruitment בלבד יש לו תוכן
  אמיתי כרגע; שאר 4 סוגי הדרישה מחזיקים ערך ניטרלי מפורש "אין כרגע חוקי עסק ייחודיים...
  אין להמציא פרטים" — **במכוון לא placeholder מזויף**). נוסף שלב `Constraints` ל-wizard
  (השדה כבר היה קיים ב-schema/gateway, רק לא נאסף). `compose_production_handoff()`
  **נשאר דטרמיניסטי במכוון** — לא נוסף call AI שני (הבעלים דחה זאת מפורשות: ה-M1 spec
  מגדיר Production Handoff כטקסט provider-neutral ל-worker חיצוני, לא כמחולל מודעות פנימי).
- **PR #604** — **באג ארכיטקטוני אמיתי, נמצא רק בבדיקה חיה**: כל טקסט חופשי שנשלח
  ל-wizard (למשל "כן", "3 שנים") נפל בשקט ל-`run_agent()` (ה-Agent הכללי, כולל
  `_CONFIRM_WORDS` matching) במקום להיתפס ע"י `cmd_marketing.py`. שורש הבעיה:
  `app.py`'s `_webhook_telegram_impl()` קורא ל-`bot.process_new_updates()` (הדבר היחיד
  שמפעיל handlers רשומים דרך `@bot.message_handler`) רק עבור slash commands, או כש-
  `cmd_update.has_pending_text_capture()` מחזיר True — לא הייתה בדיקה מקבילה ל-
  `cmd_marketing`. תוקן ע"י הוספת `cmd_marketing.has_pending_capture(user_id)` (True
  לכל step פעיל, לא רק free-text steps) + קריאה מקבילה ב-`app.py` מיד אחרי בדיקת
  `cmd_update` הקיימת. גם עודכן ה-intake עצמו: מרשימת שדות שטוחה
  (target_audience/location/goal/constraints זהה לכל הסוגים) ל-`INTAKE_QUESTIONS` —
  3 שאלות עם **מפתחות סמנטיים** ספציפיות לכל Demand Type (למשל `real_estate_listing`
  שואל "סוג נכס וחדרים"/"מיקום"/"מחיר ומטרת הפרסום", לא "קהל יעד"). `_materialize_
  demand_fields()` מרכיב את התשובות הסמנטיות לתוך שדות ה-Demand הקיימים (`target_
  audience`/`location`/`goal`, ללא שינוי schema) עם תיוג מפורש איפה שהמשמעות לא תואמת
  באמת (`real_estate_listing`'s "פרטי הנכס: ..." בתוך שדה שנקרא ספרותית target_audience).
  נוסף governance check סטטי חדש ב-`smoke_tests.py` (`check_marketing_capture_ownership`)
  שאוכף ש-`has_pending_capture(` מופיע **לפני** `run_agent(` ב-`_webhook_telegram_impl` —
  מונע רגרסיה שקטה אם מישהו יסדר מחדש/ימחק את הבדיקה בעתיד.

**אימות חי (12/08/2026):** simulated webhook POSTs אמיתיים מול `/telegram` בפרודקשן
(identity אמיתי, Airtable אמיתי, קריאת Anthropic אמיתית) — נשלחו בדיוק המחרוזות ששברו
קודם ("כן"/"3 שנים"), נוצר רשומת Demand אמיתית (`recfrUEj6e7uHEEf9`) עם השדות המדויקים
שהתקבלו כתשובות intake (לא כטקסט Agent), וה-flow השלים עד `Current Stage=ideas_generated`
כולל Creative record (`recMyaGzpIvYfNX0i`) עם 3 רעיונות. Render logs מאותו חלון זמן:
אפס פעילות `run_agent`/Router — קריאת Anthropic יחידה בלבד (`llm_fallback` שלנו).

**טבלאות Airtable** (base `app4bcgoX7t0HUVnm`): `Marketing Demand` (`tbljxJMyeSlF4VC42`),
`Marketing Creatives` (`tblLWwYRntaZtpVgW`), `Marketing Publications` (`tblUhWCdS8s4H1aS7`).
**הרחבות לטבלאות קיימות:** `Media Files` (+Linked Demand/+Linked Creative/+Approval Status),
`TRAFFIC_SOURCES` (+URL/+Location/+Suitable Domains/+Free-Paid/+Suitable Demand Types/
+Posting Rules/+Last Published At/+Quality Notes).

**Domain vs. Demand Type:** `Marketing Demand.Domain` משתמש אך ורק ב-6 הערכים הקנוניים של
`identity.Domain` (real_estate/import/media/saas/finance/general) — לא נוספה טקסונומיה
חדשה. `Demand Type` (recruitment/furniture_import/fiber_equipment/real_estate_listing/
service) הוא שדה נפרד, Marketing-owned, שבוחר איזה `DomainProfile`/`INTAKE_QUESTIONS`
לטעון — לא Domain.

**Marketing Rules (Business Memory) — עדיין ריק, לא שכבה פעילה כרגע:** מתוכנן להיות
מאוחסן ב-`Business Memory` הקיים (Event Type="Other", תחילית כותרת "[Marketing Rule]").
`marketing_gateway.save_marketing_rule()`/`get_marketing_rules()` קיימים, אבל
`save_marketing_rule()` **ללא caller בכלל בקוד החי** — אין שום מסלול, אנושי או
אוטומטי, שממלא את השכבה הזו כרגע. הוחלט במפורש (12/08/2026) לדחות את זה ל-"Later —
Structured Company Brain" — לא M1. אם מישהו יחזור לזה: צריך קודם להחליט מנגנון
כתיבה (Airtable ידני עם ה-prefix convention? פקודת טלגרם חדשה?).

**קבצים:** `marketing_domain_profiles.py` (GLOBAL_RULES + 5 DomainProfile עם
`persona`/`business_rules` — `default_tone`/`key_points` הוסרו, היו dead
code/גנריים), `marketing_brief_composer.py` (compose_brief/compose_production_handoff —
פונקציות טהורות, ללא I/O וללא קריאת AI — `_TASK_INSTRUCTIONS["creative_ideas"]` **לא
שונה** מאז ה-build המקורי, במכוון: הבעיה הייתה בהקשר העסקי החסר, לא בניסוח ההוראה),
`marketing_gateway.py` (מראה את `media_gateway.py` — dataclass → fields →
`airtable_gateway.airtable_create/patch`), `cmd_marketing.py` (`/marketing_new` wizard —
handler ישיר בסגנון `cmd_update.py`/`cmd_decision.py`, **לא** dispatcher tool/
ActionGateway — ה-Canonical Reuse Gate קבע שזו הפעולה הנכונה לפעולות מופעלות-פקודה-ישירה
שבהן המשתמש האנושי עצמו הוא האישור; מחזיק `INTAKE_QUESTIONS`/`_materialize_demand_fields`/
`has_pending_capture`), `app.py` (רישום + ownership check ב-`_webhook_telegram_impl`,
מראה את בדיקת `cmd_update` הקיימת בדיוק), `smoke_tests.py` (`check_marketing_capture_
ownership`).

**Flag:** `FEATURE_MARKETING_BRIDGE` — **דלוק בפרודקשן כרגע** (הודלק לבדיקה חיה
ולא כובה מאז; לא ברירת המחדל בקוד, שנשארת כבויה).

**M1 scope (מומש בפועל):** `/marketing_new` wizard מקצה לקצה — יצירת Demand דרך intake
conversational, קריאת AI יחידה ל-3 רעיונות, בחירה בכפתור, Production Handoff דטרמיניסטי.
בחירת קריאייטיב וקישור ל-Publication נשארים ידניים דרך Airtable ישירות. ממשק מלא (רשימת
דרישות, Next Action כפקודת שאילתה, TMA) נדחה ל-M2 — חלק Telegram (רשימה + Next Action)
מומש (ראה להלן); ה-TMA screen נשאר בתכנית נפרדת, לא התחיל כאן.

**Deferred (לא נבנה כלל):** פרסום אוטומטי, scheduler/queue חדשים, מנוע memory/approval/
router/Airtable-gateway חדשים, עורך גרפי/production/AI runtime פנימיים, recommendation
engine, Marketing Intelligence, Drive prompt-library (הוזכר באודיט כ-gap, לא נבנה, לא
צריך ל-M1), Business Memory Marketing Rules writer (ראה למעלה), Prompt 2 כ-AI call שני
(נדחה במפורש ע"י הבעלים).

**מה עשוי להיות הצעד הבא (לא הוחלט, לא מאושר לביצוע):** תוכן `business_rules` אמיתי
לארבעת סוגי הדרישה הנותרים (furniture_import/fiber_equipment/real_estate_listing/
service) — דורש ידע עסקי אמיתי מהבעלים, לא ניתן להמציא. עד אז הם ישתמשו בערך הניטרלי
המפורש. אם התוכן העשיר יותר עדיין לא משפר את איכות הרעיונות לאחר שיתווסף, הצעד הבא
המוצע (שהוצג לבעלים אך טרם אושר ליישום) הוא חוזה output מובנה יותר ל-Prompt 1
(Creative Director עם 7 שדות: שם כיוון/hook/רעיון מרכזי/הבטחה/למה זה יעבוד/מבנה
מסר/מה מבדיל) — **לא ליישם בלי אישור מפורש**.

STATUS: ✅ VERIFIED IN PROD
EVIDENCE: PR #601 (`f982217`-adjacent merge)/#602 (`ca57b29`, `2026-08-11T13:20:02Z`)/
#603 (`59a38e9`, `2026-08-11T14:38:35Z`)/#604 (`a1caa82`, `2026-08-11T23:47:16Z`) —
כולם ממוזגים ל-`main`, Render deploy `dep-d9tr91jl550s738take0`=`live` (מאומת מול
Render API). Live regression מפורט למעלה. `FEATURE_MARKETING_BRIDGE=true` בפרודקשן
כרגע — אם מכבים אותו, `/marketing_new` לא יירשם (fail-safe, ראה `register_marketing_
command`).

**M2 — Telegram slice (רשימת דרישות + Next Action כפקודת שאילתה; TMA screen לא בסקופ,
תכנית נפרדת):** `/marketing_status`/`מצב_שיווק` — רשימת Demands מורשית לפי
`identity.can_access_domain()` (owner: הכל; partner: רק `identity.allowed_domains`;
שאר תפקידים פנימיים: ללא הגבלה כרגע, לפי `identity.py`), נבדק גם בזמן הרשימה וגם שוב
ב-`mkt_status:` callback — לא מסתמכים על כך שה-record id רק "מוסתר" בתוך `callback_data`
כאבטחה; מזהה שגוי/לא מורשה מחזירים אותה הודעה גנרית ("הדרישה לא נמצאה") כדי לא לחשוף
אילו records קיימים. מודול חדש `marketing_orchestrator.py` (pure, pull-only — אותו
חוזה בדיוק כמו `decision_orchestrator.py`, לעולם לא כותב canonical state) מחשב כרטיס
Next Action לפי `Current Stage`/`Status`: `published`→מעקב ידני; `handoff_sent`→מציג את
טקסט ה-Production Handoff השמור; `ideas_generated`→אם יש **בדיוק** Creative אחד
Pending Review, מציג את 3 הרעיונות ומשתמש מחדש ב-`_idea_keyboard()`/`mkt_select:`
**הקיימים מ-M1** (M2 לא מוסיף מסלול כתיבה חדש, רק נקודת כניסה מורשית נוספת לזה הקיים —
`select_creative()`→`save_production_handoff()`→`update_demand_stage(HANDOFF_SENT)`);
0 או **יותר מ-1** Creative ממתין נחשבים fail-closed (לא בוחרים "הראשון" שרירותית, מדווחים
"מצב לא עקבי"). שלבים שמורים-בסכמה-אך-לא-חיים כרגע (`brief_composed`/`selected`/`closed`)
מקבלים כרטיס מפורש "לא מטופל אוטומטית" — לא הסקה/ניחוש של behavior שלא קיים בקוד החי.
`marketing_gateway.list_demands()` חדש (עטיפה דקה על `at_list_by_formula`, `limit=15`
ברירת מחדל; הקריאה בפועל מ-`cmd_marketing.py` מגבילה ל-10 כדי לשמור על גודל סביר
ל-inline keyboard). `Marketing Demand.Next Action` (השדה הקיים ב-Airtable) עדיין לא
נכתב ע"י אף caller חי — `marketing_gateway.py` תומך בכתיבה אליו
(`DemandRecord.next_action`/`update_demand_stage(..., next_action=...)`) אך M2 נשאר
read-pull-only לגביו בכוונה, כמו ה-orchestrator עצמו.
**קבצים:** `marketing_orchestrator.py` (חדש), `marketing_gateway.list_demands()` (חדש),
`cmd_marketing.py` (`/marketing_status`+`מצב_שיווק`, `mkt_status:` callback,
`_authorized_demand_list`/`_get_next_action_card`/`_truncate_for_telegram`).
**בדיקות:** `test_marketing_orchestrator.py`, `test_cmd_marketing_status.py` (חדשים,
מריצים ישירות `python3 <file>.py` כמו שאר הבדיקות בריפו) + self-tests מורחבים
ב-`marketing_orchestrator.py`/`cmd_marketing.py` עצמם. `smoke_tests.py`/
`test_integration.py` נשארו ירוקים ללא שינוי.

STATUS: ✅ VERIFIED IN PROD
EVIDENCE: PR #613 מוזג ל-`main` (`d5e8369`→`89087b4`, `merged_by=10026782`,
`merged_at=2026-08-12T21:24:17Z`, אומת דרך `pull_request_read` — לא רק `git log`).
Render deploy מאומת: commit חי `98f3626` (הודעת deploy אמיתית מהבוט), `git merge-base
--is-ancestor 89087b4 98f3626` מאשר שקוד ה-PR נכלל בפריסה החיה. **Live regression חי
בפועל ע"י הבעלים ב-`/telegram` production** (12-13/08/2026), מול Demand ייעודי לבדיקה
("דרישה למתקינים - בית שמש (בדיקת M1 חיה)", בדיוק לפי הזהירות שנרשמה כאן): (1)
`/marketing_status` החזיר "📋 דרישות שיווק פעילות (2):" עם רשימה אמיתית; (2) לחיצה על
הדרישה החזירה כרטיס Next Action מדויק לפי `compute_next_action()` לשלב `ideas_generated`
("🔄 שלב: ideas_generated | סטטוס: Active" + "➡️ צעד הבא: בחר אחד מ-3 הרעיונות למטה");
(3) לחיצה על "רעיון 2" הפעילה את מסלול הכתיבה **הקיים** מ-M1 (`mkt_select:` →
`select_creative()`→`save_production_handoff()`→`update_demand_stage(HANDOFF_SENT)`)
בהצלחה — "✅ נבחר רעיון 2" + טקסט Production Handoff. **החלק הדטרמיניסטי** (persona/חוקים/
פרטי הדרישה/קלטי הפקה מסומנים "לא סופק" כנדרש), שנוצר ב-`compose_production_handoff()`
ללא קריאת AI, תקין וללא המצאת עובדות — **אך `[הרעיון שנבחר]` המוטמע בתוכו אינו מאומת
ומכיל עיוות עובדתי אמיתי (ראה `BUG-164` למטה)**, כך שהמסמך כולו אינו "תקין" גורף. מוכיח גם שהמסלול
החדש (`mkt_status:`) וגם הישן (`mkt_select:`) פעילים זה לצד זה בפרודקשן ללא התנגשות,
בדיוק כפי שהוכח סטטית לפני המיזוג.

**הפרדת ממצאים (13/08/2026, מבדיקת ה-live regression עצמה) — שלושה thread נפרדים,
בכוונה לא מעורבבים:**
1. **F23 M2 orchestration/runtime — ✅ CLOSED.** `/marketing_status`/`marketing_orchestrator.py`/רשימה/authorization/callback lifecycle — מאומת חי, ללא regression (ראה אודיט למעלה). לא נפתח מחדש.
2. **Production Handoff grounding — ✅ RUNTIME VERIFIED.** ה-wrapper הדטרמיניסטי (`compose_production_handoff()`) התנהג בדיוק כמתוכנן בלייב: תייג את הרעיון כ"כיוון קריאייטיבי בלבד, לא מקור אמת", סימן כל קלט הפקה לא-ידוע כ"לא סופק", ולא המציא דבר בעצמו.
3. **Creative Ideas grounding (Prompt 1) — 🟢 `BUG-164` `creative_ideas` תוקן דטרמיניסטית (PR2, מוזג), + הגנת-עומק ל-3 סוגי המשימה הנותרים.** הרעיון שה-AI יצר (קריאה יחידה, `_create_demand_and_generate_ideas()`) עיוות עובדה כמותית מה-Demand ("10 מועמדים תוך שבוע" → "10 משרות פתוחות") + הוסיף ניסוחים לא-נתמכים. נצפה באותה בדיקה חיה, אך זהו gap ב-M1 (Prompt 1 אין לו grounding/fact-check אחרי היצירה, בניגוד ל-Handoff הדטרמיניסטי) — **לא regression מ-M2** (M2 לא קורא ל-AI כלל, רק חשף מחדש תוכן קיים). **עדכון (14/08/2026):** PR #623 ("PR1: Authority/Foundation") מוזג — מוסיף `ProtectedFact`/registry סגור/`CreativeProposal` renderer. **עדכון (14/08/2026, PR2):** PR #645 מחווט את ה-foundation בפועל ל-`_create_demand_and_generate_ideas()` — תפריט סגור + `authority_filter_and_render()` במקום free-text, ללא נתיב fallback לטקסט AI גולמי. **`creative_ideas` — הוקטור שבו נצפה הבאג — תוקן דטרמיניסטית וממוזג; טרם live-verified בפרודקשן.** **עדכון (15/08/2026):** `compose_brief()` קיבל `_DEMAND_FIDELITY_RULE` (commit `b375602`, ענף `claude/continue-f23-dmbgr7`) — הגנת-עומק ברמת prompt ל-3 סוגי המשימה שעדיין ללא authority gate דטרמיניסטי: `creative_review`/`ad_package`/`publishing_plan`. בדיקות מקומיות עברו; לא live-verified. ראה `BUG_AUDIT_LOG.md::BUG-164` לפרטים מלאים. לא נפתח מחדש M2 בגללו.

**C60 — Tool Context Awareness (PR #152, מוזג ל-`main`, commit `2d85b84`/merge `3e0094b`):**
לפי `SPEC_C59_Tool_Context_Awareness.md` (הועלה ע"י הבעלים בלי טקסט מלווה; אישור דרך
`AskUserQuestion`: "Yes, implement now"). ⚠️ **ID collision מתועד** — הספק תייג עצמו "C59",
מתנגש עם C59 הקיים (Trust Layer שלעיל, PR #151) — תויג מחדש **C60** בתיעוד בלבד; כותרת
הספק וכל מחרוזות הקוד נשארו ללא שינוי (אותו דגם כמו C54→C57). פותר עיוורון כלים בין סבבי
agent: `last_tool_result` נשמר ב-session אחרי כל tool dispatch אמיתי (`session_store.py`:
`set_last_tool_result`/`get_last_tool_result`, מסונכרן ל-`State JSON` כמו `last_uploaded_file`
מ-C58), מוזרק ל-system prompt כ-"🔧 הקשר כלים" (`_build_tool_context()`, TTL 5 דקות),
ו-`resolve_context_pronouns()` מחליף כינויי הצבעה עבריים ("זה"/"הנספח"/"הקודם"/"ההוא"/"אותו")
בהתייחסות מפורשת לפני ה-Router (שלב חדש "2.6" ב-`run_agent()`).
**3 סטיות מהטקסט המילולי של הספק, מתועדות:**
1. הספק מניח חוזה `tool_result` עם `id`/`record_id`/`url`/`drive_url` — החוזה האמיתי בקוד
   (C53-A, `test_c53a.py`) הוא `{ok, tool, external_id, evidence, user_message}` בלבד. תוקן:
   `record_id` ← `external_id`, `url` ← `evidence.get("htmlLink") or evidence.get("url")`.
2. `_seconds_ago()` מוזכר ב-§5 בלי הגדרה (כמו `_has_keyword_conflict` ב-C59) — מומש inline
   כ-diff בין `datetime.now(timezone.utc)` ל-`datetime.fromisoformat(timestamp)`.
3. §6 "Table Registry fix" — אומת מראש ש-4 קבועי Decision Tables כבר קיימים (מ-C59) — no-op.
**Verification ראיה:** `py_compile` נקי על `app.py`/`session_store.py`/`airtable_schema.py`;
`session_store.py` self-test 40/40 עברו (4 חדשים ל-C60); `test_c53a.py` 50/50; `test_integration.py`
4/4; §9 greps כולם תקינים. §10 פריט 7 בספק (בדיקת לייב) פתוח עד מיזוג+פריסה.
**קבצים שנוספו/שונו:** `session_store.py` (`last_tool_result` + 2 מתודות + 4 self-tests),
`app.py` (`_capture_last_tool_result`/`_build_tool_context`/`resolve_context_pronouns`/`CONTEXT_PRONOUNS`
+ 3 נקודות חיווט).
**מצב נוכחי:** מוזג ל-`main` (PR #152, commit `2d85b84`, merge commit `3e0094b`) — אומת
עצמאית דרך `git merge-base --is-ancestor 2d85b84 origin/main`. **לא flag-gated** (additive),
כך שהקוד פעיל בפרודקשן אם נפרס; פריסה בפועל ל-Render **לא אומתה** (אין גישת dashboard/egress
מה-sandbox). §10 פריט 7 בספק (בדיקת לייב) עדיין פתוח.

### F05a — Meta WhatsApp Phase 1 (Inbound, ללא תעבורת פרודקשן)
**מה:** `/webhooks/meta/whatsapp` (GET verify + POST inbound) — נתיב נפרד מ-Twilio.
מנרמל payload → אותו pipeline של `run_agent()` כמו Twilio. Outbound נשאר stub כנה.
**קבצים:** `app.py` (2 helpers + 1 route, additive בלבד).
**guard:** `EMERGENCY_STOP_WHATSAPP` נבדק לפני כל processing.
**env:** `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`.
**סטטוס:** test-only — אין תעבורת לידים אמיתית עד F05 (חיבור Meta מלא).

---

## 📌 Business Lifecycle Gap Analysis (נוסף 2026-06-13)

ה-CRM/Workflow הקיים מכסה כ-20-25% ממחזור החיים העסקי המלא.
מיפוי 8 השלבים:

| שלב | תיאור | סטטוס |
|---|---|---|
| 1. Opportunity Pipeline | איתור הזדמנויות (Ventures) | ✅ טבלה קיימת → N06 TMA screen |
| 2. Deal Evaluation | בדיקת כדאיות (שמאי/עו"ד/רו"ח/מיסוי/סיכונים) | ❌ לא קיים → **Future** |
| 3. Demand Research | מחקר שוק (לקוחות/מתחרים/תמחור) | ❌ לא קיים → **Future** |
| 4. Deal Structuring | בניית עסקה (מימון/שותפים/מבנה רווחים) | ❌ לא קיים → **Future** |
| 5. Marketing & Sales | קמפיינים/לידים/פולואפים | ✅ הכי מפותח - הליבה הקיימת |
| 6. Execution | חוזים/גבייה/תשלומים/מסירה | 🟡 חלקי (Payments table קיים) |
| 7. Profit Distribution | חלוקת רווחים לשותפים/משקיעים | ❌ לא קיים → **Future** |
| 8. Capital Management | מעקב הון - כמה נשאר/מושקע/חוזר/יוצא | ❌ לא קיים → **Future** |

**החלטה (2026-06-13)**: לא בונים שלבים חדשים כרגע. ממשיכים ברודמאפ הקיים
(Cost Watchdog → Meta WhatsApp → N04/N05 → Digest). שלבים 1-4, 7-8
מתועדים כ-Future items, יישקלו לאחר השלמת השכבה התפעולית.

**עקרון מנחה**: המערכת היום היא "Operating Layer" (תפעול). שכבת
"Business Management" (ניהול העסק - הזדמנויות, כדאיות, הון) היא
השכבה הבאה, אחרי שהתפעול מבוסס לחלוטין.

---

## 📌 CORE_05 Cost Watchdog — Spec v2 (גנרי, multi-source)

### תיקון תיעוד חשוב
`interaction_engine.py` (שהוזכר כקורא Sonnet כל 15 דקות) **לא קיים בקודבייס**.
הארכיטקטורה התפתחה ל-`context.py` שכולל `_select_model()` חכם:
- Owner + הודעה מתחילה ב-`#` → Sonnet (מצב מחקר)
- כל שאר המקרים → Haiku

**נקודת הדליפה האמיתית**: `creative_generator.py` קרא ל-Sonnet תמיד — **תוקן** (Haiku עכשיו).

### מרכיבי הפתרון (מיושם 2026-06-13)
- `core/cost_watchdog.py` (חדש) — `log_usage(source_type, units, meta, user_id)` → `logs/usage.jsonl`
- `creative_generator.py` — עבר ל-Haiku + log_usage אחרי כל קריאה
- `app.py` — `log_usage()` אחרי כל `client.messages.create` (source_type לפי model name)
- `scheduler.py` — `_job_daily_usage_report` כל יום 08:00 → aggregation + Airtable + alert
- `airtable_schema.py` → `Tables.AI_USAGE_DAILY = "AI_Usage_Daily"` (טבלה חדשה, 1 שורה/יום)
- Feature flag: `COST_WATCHDOG_ENABLED=true` (default on)
- ספים: `SONNET_DAILY_LIMIT=50` (configurable), `WHATSAPP_CONV_DAILY_LIMIT` (להגדיר עם Meta)

### עלויות נסתרות (לא בקוד — מעקב ידני)
- Meta WhatsApp Cloud API: per-conversation pricing (utility/marketing/auth) — לבדוק לפני חיבור
- Render: per-plan-tier (compute/RAM), לא per-call — רלוונטי לסקלביליות 1000 משתמשים
- Airtable: rate limit 5 req/sec/base — סיכון 429 errors בעומס גבוה

---

## F — עתיד (אין תאריך, יש spec)

### F01 — Lead Recovery
מה: לידים שדעכו → זיהוי אוטומטי → הצעת פנייה מחדש לowner.
תלוי ב: N04 Followup.

### F02 — Learning Engine
מה: מעל lead_events (C12). לומד מדפוסים, התנגדויות, מה סגר עסקאות.
תלוי ב: N04, כמה חודשי דאטה.

### F03 — Revenue Attribution
תלוי ב: F02.

### F04 — KPI Engine
תלוי ב: C21 Daily Digest + F03.

### F05 — WhatsApp Production (Meta Cloud API)
חסם: אישור Meta Cloud API. כרגע honest stub.

### F06 — Email Channel (Inbound)
תלוי ב: Google Tools הפשרה.

**תלות דגלים (אומת בקוד, 19/06/2026):** F06 **לא** תלוי רק ב-`EMAIL_INBOUND`. `email_inbound.run_email_poll()` נכנס ל-loop רק אם `EMAIL_INBOUND=true`, אבל מעביר כל מייל ל-`inbound_handler.handle_inbound()` (`inbound_handler.py:155`) שעושה `if not is_enabled("LEAD_CAPTURE"): return` — early-return בלי ליצור/לעדכן שום רשומת Lead. כלומר אם `EMAIL_INBOUND=true` ו-`LEAD_CAPTURE=false`: המיילים *נסרקים* (ונספרים כ-`routed` ב-`PollResult`, מטעה — אין כתיבה בפועל ל-Airtable), אבל שום ליד לא נוצר/מתעדכן בשקט. **שני הדגלים חייבים להיות `true` יחד כדי ש-F06 יעבוד בפועל.** שניהם כבויים כיום ברירת מחדל — `EMAIL_INBOUND` נשאר `false` עד שתתקבל החלטה מודעת על השלכת הפעלת `LEAD_CAPTURE` (שמשפיעה גם על WhatsApp lead capture, לא רק email).

### F07 — Voice / IVR
מודל עסקי: White-Glove.

### F08 — SaaS Multi-Tenant
תלוי ב: הכל לפניו.

### F09 — Lead Qualifier Wire-up
מה: חיבור lead_qualifier.handle_lead_message() לתוך run_agent — state machine שאלון לכל ליד WhatsApp.
מצב: **בנוי ובדוק** — lead_qualifier.py קיים ומלא. לא מחובר לפרודקשן.
**עדכון 05/07/2026:** N04 כבר מיושם (scheduler מחובר, flag כבוי — ראה N04 למטה) — התלות המקורית ("קודם צריך N04") סגורה. הנותר הוא **החלטת מוצר**, לא חסם טכני: לחבר את ה-state-machine הזה כמו-שהוא, או להחליף ב-Claude-native scoring (הנתיב שכבר פעיל דרך N02/N03).
קבצים: lead_qualifier.py (קיים), app.py (hook).

### F10 — Lead Memory Wire-up
מה: חיבור lead_memory.update() לתוך lead_capture — זיכרון ארוך-טווח per lead.
מצב: **✅ בפועל כבר מחובר** — לא רק "בנוי ובדוק". N02/N03 (למטה) חיווטו בדיוק את זה: `lead_capture.py` קורא ל-`lead_memory.update()` הן ב-create (domain/channel/contact_name/summary/last_message, N04-A) והן אחרי scoring (tier/score/record_id, N04-B), גייטד ב-`LEAD_MEMORY` בלבד. הסעיף הזה היה כפול ל-N02/N03 מרגע שהם נבנו — נשאר כאן רק כהפניה היסטורית, לא כפריט עבודה נפרד.
תלוי ב: כלום — התלות המקורית (N02) כבר מומשה.
קבצים: core/lead_memory.py (קיים), lead_capture.py.

### F11 — Followup Engine Full Activation
מה: הפעלת core/followup_engine.py המלא — determine_followup_needed, יצירת טיוטות, שליחה לאישור.
מצב: **תשתית קיימת + הרחבה חלקית כבר בפרודקשן-קוד.** N04 (MVP: scheduler+scan, למטה) ו-N05-B (טיוטת followup מגיעה בטלגרם לאישור owner, למטה) כבר מיושמים — שני הרכיבים המרכזיים שה-"MVP" המקורי דיבר עליהם קיימים. **לא חסום עוד** — מה שנשאר הוא הרחבה עתידית אופציונלית (למשל: זיכרון/היסטוריית followups עשירה יותר), לא MVP חסר.
תלוי ב: כלום.
קבצים: core/followup_engine.py (קיים), scheduler.py.

### F14 — Contact Gate: find_or_create_contact()
מה: פונקציה יחידה ב-`crm.py` — בודקת קיום איש קשר לפי טלפון לפני כל כתיבה.
סיבה: התכונה "חפש לפי טלפון" נדרשת בשלושה מקומות: import ידני, `crm_add_contact`, המרת ליד→contact (עתידי). ללא gate — כפילויות בלתי נמנעות.
ממשק: `find_or_create_contact(phone, name, **fields) → ContactResult` עם `created | existing | ambiguous | invalid | lookup_error`.
F14-A מוזג ב-PR #568. F14-B1 מעביר את `crm_add_contact()` ואת `lead_conversion.py::convert_lead_to_contact()` דרך אותו gate; `ambiguous`, `invalid` ו-`lookup_error` נעצרים fail-closed.
קבצים: crm.py, lead_conversion.py

### F15 — crm.py → airtable_gateway (write path migration)
מה: החלפת `_post` / `_patch` הישירים ב-`crm.py` בקריאות ל-`airtable_gateway.upsert()`.
סיבה: `crm.py` עוקף את כלל הברזל — "ALL writes go through airtable_gateway.py". drift מודע.
Piggyback trigger: כשנוגעים ב-`crm.py` לסיבה אחרת (F14 או lead→contact).
קבצים: crm.py, airtable_gateway.py, `scripts/verify_f15_staging.py` (חדש)

**עדות Staging אמיתית (10/08/2026)** — `F15_STAGING_NON_PRODUCTION=true
F15_STAGING_ENVIRONMENT=staging python3 scripts/verify_f15_staging.py`,
הורץ מ-Render staging shell, `run_id=f15-20260810T142420Z-01c6bc0a1f`.
תוצאה: `F15 — COMPLETE AND STAGING VERIFIED`, כל 13 ה-gates `PASS`:
`staging_preflight`, `gateway_table_preflight`,
`contact_create_id`/`contact_create_gateway`, `contact_gate_no_duplicate`
(בדיקת כפילות אמיתית — יצירה שנייה עם אותו טלפון החזירה `status='existing'`
על אותו `record_id`, לא רשומה חדשה), `contact_update_same_id`,
`deal_create_gateway`/`deal_update_same_id`,
`payment_create_gateway`/`payment_update_same_id`,
`crm_static_no_direct_http_writes` (אימות סטטי — `crm.py` לא מכיל
`httpx.post()`/`httpx.patch()` ישירים יותר), ו-`f14_gate_path` (יצירת
Contact עברה דרך `crm_add_contact`/`find_or_create_contact` — מאשר
אינטגרציה חיה עם F14 Contact Gate, לא רק F15 בבידוד). שלוש רשומות אמיתיות
נוצרו ב-Airtable staging (Contact `recysbBSKfxQ9uRoC`, Deal
`receo6WZ06VzcOIzS`, Payment `recrxDHC47wCmbG1t`) ונוקו בסוף הריצה
(`cleanup_owned_records: PASS`, 3/3).

### F12 — Model Provider Adapter
⚠️ **STATUS: ABSORBED BY F13 — לא ייבנה בנפרד.** הכרעת בעלים סופית (07/07/2026): F13 סופגת את F12; F12 נגנז כתכנון עצמאי. נשאר בתיעוד כהיסטוריה/הקשר-כוונה בלבד — ה-`providers/` overlap שתועד למטה (F13) הוכרע לטובת F13.
מה: abstraction layer אחיד ל-LLM providers — interface יחיד `generate(prompt, context, model_tier) → text` שמאחד Anthropic, OpenAI, ו-providers עתידיים.
מטרה: שינוי provider = שינוי config בלבד, לא קוד. כולל sanitization עקבי (A32) בכל provider.
פרטים:
- interface: `LLMProvider.generate(prompt, context, model_tier) → text`
- כל implementation עוטף API ספציפי + sanitize_agent_response
- selection: env config / cost watchdog / health-based fallback אוטומטי
- כל domain יכול לבחור model tier שונה (domain skill documents)
מצב (היסטורי — לפני ההכרעה): לא קיים — Fix #1/#3 + `FEATURE_LLM_FALLBACK` מטפלים בעכשיו.
תלוי ב: domain skill documents (F-future), `FEATURE_LLM_FALLBACK` יציב בפרודקשן.
קבצים לעתיד: `providers/` (חדש, ראה F13 — זה המימוש הנבחר), `llm_fallback.py` (migrate/replace).
**חשוב:** F12 חוסם אך ורק multi-tenant/SaaS provider-abstraction עתידי — **אינו** חוסם שום עבודה שוטפת (לידים, digest, C89-C94, Decision Hub וכו').

### F13 — TenantConfig + Provider Interfaces
⚠️ **STATUS: DEAD CODE — DO NOT WIRE** (ללא קשר להכרעת F12, ראה למטה)
**חשוב:** כמו F12 — חוסם אך ורק F08 (SaaS Multi-Tenant) עתידי. אינו חוסם, ואינו קשור ל, שום עבודה שוטפת אחרת ברשימה הזו.
- היסטורי: `core/tenant_config.py` נוצר במסגרת F13 ולאחר מכן הוסר ב-PR #851; shims ה-provider תחת `providers/` עדיין קיימים, אך אינם מחוברים ל-pipeline.
- מצב נוכחי: אפס imports מקוד חי אל ה-shims; אין להציג את `core/tenant_config.py` כרכיב קיים.
- כפילות: `TenantConfig` קיים גם ב-`tenant_provisioner.py`
- **F12 vs F13 overlap ב-`providers/` — הוכרע 07/07/2026: F13 סופגת את F12** (הכרעת בעלים מפורשת). עדיין **אין לחבר** — ה-DEAD CODE status למעלה נשאר בתוקף עד sprint multi-tenancy ייעודי; ההכרעה קובעת רק *איזה* תכנון ממשיך (F13), לא מתירה activation.
- Piggyback Trigger: sprint multi-tenancy בלבד

מה: שכבת תשתית SaaS — `TenantConfig` (dataclass: storage/LLM/memory/channel/features/allowed_tools per tenant) + `Protocol`-based interfaces (`StorageProvider`, `LLMProvider`, `ChannelAdapter`) + שלושה shims שעוטפים את האינטגרציות הקיימות (`AirtableStorageProvider`, `AnthropicLLMProvider`, `TwilioChannelAdapter`) בלי לשנות אותן.
scope: **infrastructure only — אפס שינוי runtime behavior** בשלב זה. שלב 1 = hardcoded default tenant (`boss_hq`) + env override; `get_tenant_config()` תמיד מחזיר singleton. שלב 3 (חלק מ-F08) = loader מטבלת Tenants ב-Airtable.
תלוי ב: C01 (Identity), W2 (`airtable_gateway`), C52 (COG / `core/output_gateway.py`).
חוסם: F08 (SaaS Multi-Tenant) — F08 לא יכול להיבנות בלי החוזה הזה קודם.
⚠️ **חפיפה עם F12** — שני הספקים מציעים `providers/` כתיקייה חדשה ל-LLM abstraction (F12: `LLMProvider.generate(prompt, context, model_tier)`; F13: `LLMProvider.generate(messages, system, model, max_tokens, tools)` + עוד שני providers ל-storage/channel). **לא להתחיל מימוש של אף אחד מהשניים לפני שמחליטים אם F13 סופג את F12 או שהם משלימים זה את זה** — אחרת ניצור שתי תיקיות `providers/` עם interfaces סותרים, כמו התנגשות ה-ID של C20/C21 שתועדה ב-`AI_CONTEXT.md`.
מצב: **CODE COMPLETE היסטורי; לא מחובר ל-pipeline** — PR #87 מוזג ל-`main`, אך `core/tenant_config.py` הוסר ב-PR #851 ו-shims ה-provider שנותרו אינם מחוברים. אפס import מקוד קיים אליהם — `app.py`/`tools/dispatcher.py` לא משתמשים בהם. ה-spec המקורי הניח חתימות פונקציות שלא קיימות בקוד (`gateway_add`/`gateway_update`/`gateway_delete`, `send_via_cog`, `airtable_get(max_records=...)` כ-`list[dict]`, `_validate_twilio_signature(headers, body)`) — תוקן מול הקוד האמיתי, מתועד ב-`BUG_AUDIT_LOG.md` כ-SPEC-001. הכרעת F12-מול-F13 (השורה הקודמת) **עדיין לא בוצעה** — ה-shims הקיימים לא נבחרו כפתרון הסופי.
הקבצים שנוצרו היסטורית: `core/tenant_config.py`, `providers/__init__.py`, `providers/interfaces.py`, `providers/airtable_shim.py`, `providers/anthropic_shim.py`, `providers/twilio_shim.py`.

### F16 — Media Layer (voice notes + file uploads → Drive + Airtable) — ✅ הושלם
מה: שכבת מדיה מלאה — קליטת קובץ/הקלטה מ-Telegram או TMA, העלאה ל-Google Drive, תמלול (STT), ושמירת metadata בטבלת Airtable "Media Files". מחולק לשבעה batches (א-ז).
⚠️ היסטוריית ID: הספק החיצוני קרא לפיצ'ר "F12" בהתחלה (תפוס — Model Provider Adapter, ראה מעלה) ואז "F09" (תפוס — Lead Qualifier Wire-up, ראה מעלה). הוקצה F16 כדי למנוע התנגשות, באותו דפוס שתועד עבור C20/C21 (`AI_CONTEXT.md`) ו-F14/F15 (מעלה).
מצב Batches:
- **Batch א — `voice_stt_adapter.py`** (PR #96, מוזג): STT provider = OpenAI Whisper (PRIMARY, חי — `OPENAI_API_KEY` קיים בסביבה). Groq רשום כ-stub מוער ("Phase 2") — לא מחובר ל-`transcribe()`. קודי שגיאה: `OVERSIZED`/`STT_FAILED` (אין `EMPTY_AUDIO` בספק הנוכחי). `_normalize_hebrew()` — הסרת ניקוד + כיווץ רווחים. **אומת מוזג ל-`main` — grep על `OVERSIZED`/`STT_FAILED` תואם.**
- **Batch ב — `drive_adapter.py`** (PR #97, מוזג): `upload_file(file_bytes, filename, mime_type, parent_folder_id)` — `parent_folder_id` חובה, אין default. Temp file נמחק תמיד ב-`finally`. `_safe_filename` מנקה רק תווים אסורים ל-Drive (עברית נתמכת native). `GOOGLE_DRIVE_FOLDER_ID` (BOSS root, מאומת) הוא ה-parent, לא תיקייה ליצירה. **אומת מוזג ל-`main` — grep על `parent_folder_id` בחתימת `upload_file`/`_upload_to_drive` תואם.**
- **Batch ג — `media_gateway.py`** (PR #97, מוזג): טבלה `"Media Files"` (לא "Assets" — collision עם נדל"ן), `MediaFileFields`, כתיבה דרך `tools/airtable_gateway.airtable_create` בלבד (אין `httpx` ישיר), `linked_lead_id` → `[record_id]` (array), `raw_transcript`+`normalized_transcript` שניהם נשמרים, `save_asset()` מחזיר `record_id: str | None`. הקובץ נמצא **תואם 100% לספק כבר מהבנייה המקורית — אפס שינויי קוד בסשן הזה**.
- **Batch ד — `media_handler.py`** (PR #98, מוזג, `8dd3bca`): כניסה יחידה `handle_voice_note()`/`handle_file_upload()`/`handle_tma_upload()` (שמות נשמרו כפי שהיו בקוד הקיים — לא שונו ל-`handle_telegram_media()` כפי שהוצע ב-spec החיצוני, ראה החלטת המשתמש בסשן). שכבות גודל: `normal` ≤10MB / `large` 10-50MB / `oversized` >50MB (reject מיידי, בלי upload). Idempotency: `source:file_id:user_id` → hash (16 תווים). Approval רק ל-Business Memory write (לא לשמירת ה-asset עצמו — Drive+Airtable נשמרים סינכרונית, ללא approval). PR #98 תיקן שני באגים אמיתיים שהיו קיימים בקוד מאז `ee4d2ed` (לפני כל מאמץ הבאצ'ים): (1) `upload_file()` נקרא עם חתימה לא תקפה (`domain=domain` קיים שלא קיים בפונקציה האמיתית — `TypeError` מובטח עם כל flag דלוק); (2) כשל כתיבה ל-Airtable לאחר Drive upload מוצלח הוחזר כ-`ok=True` בשקט (קודי שגיאה חדשים: `DRIVE_FAILED`/`ASSET_SAVE_FAILED`).
- **Batch ה — `app.py` hooks**: ✅ מוזג. `_handle_telegram_media()` כבר היה מחובר ל-webhook (voice/photo/document) מאז `ee4d2ed`; PR #99 הוסיף `send_chat_action` לפני עיבוד (typing/upload_document) שהיה חסר.
- **Batch ו — `tma_api.py` endpoint**: ✅ מוזג. `POST /api/tma/upload` (multipart, `@require_tma_auth`) כבר היה מחובר ל-`handle_tma_upload()` מאז `ee4d2ed`, כולל `coming_soon` כש-`FEATURE_MEDIA_UPLOAD` כבוי; PR #99 הוסיף קליטת `linked_lead_id` מה-form ומעביר אותו ל-`handle_file_upload()`. `domain` נשאר נגזר מה-identity המאומת בלבד (לא משדה form של הלקוח) — tenant scope לא נקבע ע"י הלקוח.
- **Batch ז — `airtable_schema.py`**: ✅ קיים מהבנייה המקורית — `Tables.MEDIA_FILES = "Media Files"` ו-`MediaFileFields` (NAME/FILE_TYPE/MIME_TYPE/DRIVE_URL/DRIVE_FILE_ID/DOMAIN/SOURCE/SIZE_BYTES/CREATED_BY/TELEGRAM_FILE_ID/LINKED_LEAD/RAW_TRANSCRIPT/NORMALIZED_TRANSCRIPT) מכסים את כל מה ש-`media_gateway.py` כותב. `AssetsFields` (נדל"ן) לא נגע. ⚠️ הטבלה עצמה חייבת להיווצר ידנית ב-Airtable לפני הדלקת flag — הקוד לא יוצר טבלה.
תלוי ב: כלום (עומד בפני עצמו). דגלים `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` קיימים ב-`feature_flags.py`, **כבויים כברירת מחדל** (`is_enabled()` חוזר `False` ללא env var) — הקוד רץ במלואו אך אינו פעיל בפרודקשן עד הדלקה מפורשת.
קבצים: `voice_stt_adapter.py`, `drive_adapter.py`, `media_gateway.py`, `media_handler.py`, `app.py`, `tma_api.py`, `airtable_schema.py` — כולם מוזגים ל-`main`. בדיקות: `test_media_layer.py` (33/33).

---

### U1 — Understanding Layer Architecture Decision (נרשם 12/07/2026)
מה: החלטה ארכיטקטונית רחבה — האם לבנות "שכבת הבנה" כללית חדשה (Interaction Envelope + Understanding Contract + PendingAction Store, כפי שהוצע בדיון נפרד) או להרחיב/לחבר מנגנון קרוב שכבר קיים בקוד (`core/reasoning_entity.py`/`core/reasoning_engines.py` + `core/adapters/leads_adapter.py`/`decision_adapter.py` — ראה BUG-104 ב-`BUG_AUDIT_LOG.md`).
מצב: 🟡 **רישום בלבד, ממתין להחלטה** — BUG-102/103/104 מיפו כל מנגנון קיים בנפרד (מה קיים, מה שבור, מה מחובר לחיים — ראה `DOC-20260712-WA0001` המוזכר ב-BUG_AUDIT_LOG.md). `leads_adapter.py` (`entity_type=ENTITY_LEAD`) הוא **הכי קרוב מבנית** למה שהצעת "שכבת הבנה כללית" מבקשת (`PHASE_COLLECTING`/`PHASE_BLOCKED`/`PHASE_REVIEW`/`PHASE_AWAITING`/`PHASE_DECIDED`/`PHASE_CLOSED` ≈ RESOLVED/NEEDS_CLARIFICATION/REJECTED) — **אפס קוראים חיצוניים** בכל הריפו מעבר ל-smoke test. `decision_adapter.py` כן מחובר לחיים (`cmd_decision.py`), אבל `FEATURE_DECISION_HUB`=OFF כברירת מחדל, כלומר "חי" רק תיאורטית. **זו הבדיקה שקובעת אם צריך לבנות Understanding Contract חדש בכלל, או רק לחבר+להדליק flag קיים** — לפני שממשיכים בכל דיון נוסף על הארכיטקטורה הרחבה.

**עדכון 16/07/2026 — BUG-104 = Core Reasoning Activation Program:** BUG-104 קיבל שם קנוני לתוכנית ההפעלה — **Core Reasoning Activation Program** — עם **Phase 1 — Leads Read-Only Reasoning Projection** (חיבור קריא-בלבד ראשון של Core Reasoning Layer/F22 הקיים ל-`GET /api/leads/<lead_id>`, דגל תלת-מצבי `FEATURE_CORE_REASONING_LEADS_STATE`=off/shadow/on, ברירת מחדל off; ללא mutation/persistence/Decision Hub). זו הפעלה מבוקרת של הקיים, לא הכרעת U1 כולה — U1 (Understanding Contract כללי חדש מול הרחבת הקיים) נשאר פתוח. השם הטכני-היסטורי "Core Reasoning Layer" (F22) ושמות המודולים לא שונו. ראה `BUG_AUDIT_LOG.md` BUG-104 + `core/leads_reasoning_projection.py`.
תלוי ב: כלום טכני — החלטת ארכיטקטורה/מוצר גרידא, לא חסם קוד.
חוסם: UX-01 (למטה) — אין טעם לבנות שכבת ניסוח-הודעות אחידה פעמיים אם שכבת הבנה כללית עומדת לשנות את מבנה ה-clarification/status/error messages בעצמה.
קבצים: `core/reasoning_entity.py`, `core/reasoning_engines.py`, `core/adapters/leads_adapter.py`, `core/adapters/decision_adapter.py`.

### UX-01 — Unified BOSS Experience (נרשם 12/07/2026, PLANNED — לא התחיל)

**סדר תלות מחייב (הוראה מפורשת): ייצוב Pending Approval (✅ הושלם — BUG-PENDING-APPROVAL-B, מעלה) → סגירת U1 architecture (🟡 פתוח, מעלה) → ואז UX-01.** נרשם עכשיו כשלב רשמי ב-tracker; **אין לגעת בניסוחי הודעות בקוד עד שהלוגיקה עצמה (U1) סגורה** — כדי לא לקבל טלאים שונים בין Telegram/WhatsApp/Daily Digest/אישורים/שגיאות/Mini App תוך-כדי תיקוני-באגים נפרדים.

**מטרה:** כל הודעה של BOSS → אותו קול → אותו מבנה → אותו מינוח → אותה היררכיה → בלי פרטי מערכת פנימיים.

**עקרונות מחייבים:**
- לא מציגים `record_id`/`contract_id`/`fingerprint`/שם כלי טכני (כמו `airtable_add`).
- לא מציגים שמות טכניים של טבלאות אלא אם זה מידע עסקי שהמשתמש ביקש.
- אימוג'ים רק כשיש להם תפקיד ברור, לא כקישוט.
- הודעות קצרות, נקיות, עם פעולה אחת ברורה.
- אותה פעולה נראית אותו דבר בכל ערוץ.
- שגיאה אומרת מה קרה ומה אפשר לעשות עכשיו.
- אישור תמיד מציג מה עומד לקרות.
- קבלה אחרי ביצוע מציגה מה בוצע בפועל, לא את המנגנון הטכני.

דוגמה: במקום `✅ בוצע: airtable_add | מזהה: rec...` → "הליד מלי חני נשמר בהצלחה." במקום `❌ Gmail לא מחובר כרגע` → "לא הצלחתי לקרוא את המיילים כי חשבון Gmail אינו מחובר. אפשר לחבר אותו בהגדרות."
(הערה: `compose_status_reply`'s תיקון תיאור-עסקי מ-BUG-PENDING-APPROVAL-B/Follow-up #3 הוא צעד ראשון בכיוון הזה, בהיקף מצומצם — לא UX-01 המלא.)

**מה נכנס לשלב:** Daily Digest, confirmations, cancellations, errors, success receipts, clarification questions, search results, empty states, multi-step wizards, Telegram, WhatsApp, Mini App, system notices, loading/retry/expired states.

**מה בונים:** לא רק "נוסחים" — שכבה אחידה: `UXMessage` / `MessageType` / `BusinessDescription` / `ChannelRenderer`. לדוגמה:
```python
UXMessage(
    type="success",
    title="הליד נשמר",
    body="מלי חני · 0567467372",
    action=None,
)
```
וה-renderer מתאים אותו ל-Telegram/WhatsApp/Mini App בלי לשנות את המשמעות.

**סדר העבודה:** (1) ייצוב מערכת ואישורים. (2) אודיט של כל ההודעות הקיימות. (3) מילון UX אחיד. (4) Message Contract. (5) renderer משותף. (6) מעבר מודול־מודול. (7) בדיקות snapshot. (8) rollout הדרגתי.

**DoD לשלב:**
- אין מזהי Airtable בהודעות משתמש.
- אין שמות כלים טכניים.
- אין אימוג'ים כפולים או אקראיים.
- כל success/error/confirm משתמש באותו מבנה.
- אותה פעולה מוצגת זהה בכל ערוץ.
- Mini App והודעות הצ'אט משתמשים באותו vocabulary.
- יש snapshot tests לכל סוג הודעה מרכזי.
- הודעות ישנות לא נשארות מפוזרות כ-strings בתוך handlers.

מצב: 📋 PLANNED — רישום בלבד, ממתין ל-U1 (מעלה). לא לגעת עד שהלוגיקה סגורה.
תלוי ב: U1 (מעלה), ייצוב מלא של Pending Approval flow (✅ הושלם).

---

### BUG-DH-03/04 — Formula Injection ב-Decision Hub 🟡 MERGED, NOT PRODUCTION-VERIFIED (עודכן 07/07/2026)
**קבצים:** `cmd_decision.py` (`_resolve_decision_ref`), `decision_pipeline.py` (`maybe_supersede`)
**מה:** Claim Topic + decision ref מגיעים מ-raw user content ללא sanitization לפני הכנסה ל-formula Airtable
**חסום:** לפני הפעלת `FEATURE_DECISION_HUB` בפרודקשן — **עדיין חסום** עד production evidence (המיזוג עצמו כבר בוצע)
**תיקון (✅ בוצע בקוד, ✅ ממוזג ל-`main`):** `_safe_formula_param()` נוסף ל-`tools/airtable_gateway.py`, שני call sites + `core/lead_candidate_handler.py::_search_formulas` (שכבר עשה escaping דומה, הוחלף במקור המשותף) מעודכנים. בדיקה: `test_bugdh03_04_formula_injection.py` (15/15). Merged: PR #251, commit `d51e6be`.
**ראו:** BUG_AUDIT_LOG.md BUG-036, BUG-037

---

## Known Issues / Tech Debt (מתועד, לא קריטי)

| פריט | תיאור | מתי לטפל |
|------|--------|----------|
| `_ALIAS_MAP` כפול | מיפוי English→Hebrew זהה קיים גם ב-`tools/dispatcher.py:43` וגם ב-`tools/airtable_tools.py:111`. סנכרוני כרגע, אבל עדכון ב-אחד לא יתפשט לשני — סיכון drift שקט. | בפעם הבאה שנוגעים באחד |
| `crm_mark_payment_paid` — approval חובה | כאשר כלי זה יוממש, **חייב** להירשם עם `requires_approval=True` לפי `SECURITY_CHECKLIST.md:62`. פעולות סימון תשלום דורשות Golden Path Approval Gate. | לפני מימוש הכלי |
| `lead_memory.py:155` — dead write | שדה `"updated_at"` נכתב ל-Leads אך אינו קיים בסכמת Airtable — הכתיבה נדחית בשקט ע"י gateway. | ניקוי בפגישת Tech Debt הבאה |
| Worlds table — constraint חסר | `game_today()` מחפש `Status=Active` עם `max_records=1`. אם שני Worlds מסומנים Active, התוצאה לא צפויה. אין constraint ב-Airtable. | לפני F12 / aggregator |
| `/api/game/today` — shared endpoint | גם `BossCheckin.tsx` (Screen #1) וגם `GameScreen.tsx` (Screen #2) משתמשים באותו endpoint. aggregator F12 חייב לשמור על filter הנוכחי (NOT Done + Due_Date≤today + Owner) כדי לא לשבור את Screen #2. | לפני פיתוח F12 |
| `LeadFields.TIER = "tier"` — שדה קיים אך ריק וללא כותב | **מתוקן (21/08/2026, Canonical Leads Schema v1):** ההצהרה הקודמת בשורה זו הייתה שגויה — Airtable MCP `get_table_schema` מאמת ששדה `tier` **כן קיים** בטבלת Leads (`app4bcgoX7t0HUVnm`), הוא singleSelect אמיתי (לא formula, לא read-only-by-type), אך **ריק ב-100% מהרשומות** (0/92 ב-17/07, 0/39 ב-21/08 — נשאר ריק לאורך חודש) וללא כותב מכוון בקוד. `tools/airtable_gateway.py` לא חוסם כתיבה אליו (אינו ב-`READ_ONLY_FIELDS`) — פשוט אף קוד לא כותב אליו. **החלטה נדרשת:** להסיר את השדה מ-Airtable + את `LeadFields.TIER` מהקוד (ראה migration plan ב-Canonical Leads Schema v1). | לפני N18 Phase 3 |
| Assets schema drift | שמות שדות ב-live שונים מ-MIGRATION doc: `"Mortgage Balance"` (לא `"Mortgage"`), אין `"Purchase Cost"`, אין `"Documents"`. `AssetFields` בקוד עשוי להשתמש בשמות לא נכונים. | לפני פיתוח Assets tools |
| `Table 16` ב-Airtable | טבלת placeholder ריקה (`tblXeDnLTAvpej3cC`) — לא בשימוש. למחוק ידנית מ-Airtable UI. | Housekeeping הבא |
| ~~`/status` Telegram handler חסר~~ | **✅ סגור (אומת 20/07/2026, BUG-005/BUG-120/BUG-121).** ה-decorator קיים ורשום בפועל (`app.py:401`); בזמן עבודה על BUG-120/121 גם תוקן באג נוסף ב-`/status` עצמו (קריסה על `ApiTelegramException` — ראו BUG_AUDIT_LOG). שורה זו הייתה stale. | — |

---

## פערים ידועים (לא באגים — החלטות מודעות)

| פער | סיבה | מתי נטפל |
|-----|-------|----------|
| F09 lead_qualifier — לא מחובר | state machine בנוי; N04 שהוא היה מחכה לו כבר מיושם — נותרה החלטת מוצר (לחבר את ה-state-machine או להישאר עם Claude-native scoring דרך N02/N03), לא חסם טכני | F09 |
| F11 followup_engine — הרחבה עתידית אופציונלית | N04 (MVP) + N05-B (טיוטת אישור) כבר מיושמים ומחוברים — לא "חלקי" עוד; מה שנשאר הוא הרחבה (זיכרון/היסטוריה עשירה יותר), לא MVP חסר | F11 |
| core_knowledge.py smoke test false positive | _NEVER_FAKE_CONTROL מכיל פראזה שהtest מזהה בטעות | לתעד כ-known false positive |
| Voice/IVR Twilio signature validation | לא קריטי עד שF07 פעיל | לפני F07 |
| ~~/status handler חסר decorator~~ | **✅ סגור (אומת 20/07/2026)** — ה-decorator קיים בפועל (`app.py:401`), ראו BUG-005/BUG-120/BUG-121. שורה זו הייתה stale (כפילות של אותו ממצא שגוי בטבלת "Known Issues" למעלה). | — |
| schema_cache.json stale | Coins_Log, Roadmap_Tasks, Leads מציגים [] | רענון בסשן הבא |

---

## כללי ברזל — לא לגעת בלי אישור

1. **Feature flag = כבוי ברירת מחדל.**
2. **app.py — 4 hooks בלבד (H1–H4).**
3. **Agent לא נוגע ב-Airtable ישירות.** תמיד דרך crm.py.
4. **זיכרון ליד = identity.memory_key בלבד.**
5. **מקור אמת לדומיין = detect_domain() בלבד.**
6. **לא בונים batch לפי פיצ'ר — בונים לפי קובץ.**
7. **schema_intelligence.SCHEMA["Leads"] חייב להיות מסונכרן לפני כל כתיבה.**

---

## ארכיב מסמכים

| קובץ | תפקיד |
|------|--------|
| ROADMAP.md | **זה. מקור האמת היחיד.** |
| BOSS_CURRENT_STATE.md | מצב מודולים בפועל |
| CLAUDE.md | הוראות לקלוד קוד — קרא ראשון |
| ARCHIVE_additions_log.md | specs מפורטים A01–A43, היסטוריה |
| SETUP.md | env vars, טבלאות Airtable, הפעלה ראשונה |
## Audit note - 2026-06-14

Active planning source of truth is now limited to:
- `ROADMAP.md`: priorities, blockers, next actions.
- `BOSS_CURRENT_STATE.md`: current architecture, implemented features, decisions, known risks.

All other planning/report Markdown files are archived historical evidence unless a future batch explicitly promotes content back into one of these two files.

**עדכון 05/07/2026 — הבלוק הבא (מ-14/06/2026) התיישן ומנוגד ישירות לסעיפי N02/N03/N04/N05/N05-B למעלה (שכולם ✅ מיושם, single path, קוד+טסטים) — נשאר כתיעוד היסטורי בלבד, לא כסטטוס נוכחי:**

Current verified status for N02-N05 (**היסטורי — 14/06/2026, לפני N02-N05 המיושמים למעלה**):
- N02 Live Lead Scoring: PARTIAL. Code exists in `lead_capture.py` behind `LEAD_SCORING`; default off and not verified active in production.
- N03 Lead Memory Wire-up: PARTIAL. `lead_memory.update()` is wired from `lead_capture.py` after successful scoring behind `LEAD_MEMORY`; default off and not verified active in production.
- N04 Followup Activation: PARTIAL. Scheduler job and approval queuing exist behind `FOLLOWUP_AUTOMATION`, but the flow depends on populated `lead_memory` and is not active end-to-end.
- N05 Daily Digest upgrade: PARTIAL. Digest reads `Score`, but hot-lead filtering still uses status only and does not filter by score/tier as documented.

**סטטוס נוכחי (ראה N02/N03/N04/N05/N05-B למעלה בקובץ זה):** כל הארבעה **✅ מיושם** — קוד+single-path+flags, לא PARTIAL. הנותר האמיתי אינו "לתקן קוד" אלא **החלטת הפעלה בלבד**: להדליק את `LEAD_SCORING`/`LEAD_MEMORY`/`FOLLOWUP_AUTOMATION` ב-Render ולאמת על תעבורה חיה — לא בעיה בקוד.

Recommended next action (היסטורי, 14/06/2026 — כבר בוצע): Fix docs first, then choose whether to activate/ship the intended single N02 path.

Archived / historical Markdown disposition:

| File | Disposition | Destination / section |
|---|---|---|
| `BOSS_MASTER_PLAN_2026_v2.md` | ARCHIVE | Historical strategy notes; active priorities live in `ROADMAP.md`. |
| `BOSS_MASTER_PLAN_GAP_ANALYSIS.md` | ARCHIVE | Historical audit notes; superseded by `BOSS_CURRENT_STATE.md`. |
| `boss_bot_summary.md` | ARCHIVE | Early generated implementation summary; superseded by current code and `BOSS_CURRENT_STATE.md`. |
| `PATCH_REPORT.md` | ARCHIVE | Historical patch log; keep as evidence, not active plan. |
| `SECURITY_CHECKLIST.md` | MERGE / ARCHIVE | Security triggers and open findings summarized in `BOSS_CURRENT_STATE.md`. |
| `reports/capability_map.md` | ARCHIVE | Historical generated report; high-signal blockers reflected in `BOSS_CURRENT_STATE.md`. |
| `reports/governance_mapping_report.md` | ARCHIVE | Historical governance map; table decisions reflected in `BOSS_CURRENT_STATE.md`. |
| `reports/registry_calibration_report.md` | ARCHIVE | Historical registry calibration; keep as evidence. |
| `reports/system_registry_report.md` | ARCHIVE | Generated environment snapshot; not an active plan. |
| `reports/airtable_structure_governance_audit.md` | ARCHIVE | Historical Airtable governance audit; keep as evidence. |
| `BOSS_Refactor_Plan.md` | ACTIVE REFERENCE | תוכנית 8 מסכים + BOSS Layer — Stage 0 הושלם, N06 = Stage 1 |
### F52 — Tool Architecture Audit Maps

Status: Merged to `main` across 3 PRs (#153, #155, #156), branch `f52-current-tool-map-audit`. Production deploy not verified from this sandbox (no Render dashboard/egress access).

What: audit-only documentation before F52 implementation — 4 docs (not 3; `F52_STATE_FLOW_MAP.md` landed in the third PR and was previously missing from this list):

- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_CURRENT_TOOL_MAP.md` — PR #153, commit `6afc393`, merge `0ffdc7c`
- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_CONTRACT_COVERAGE_MAP.md` — PR #155, commit `84762f0`, merge `d57f405`
- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_BYPASS_MAP.md` — PR #155, commit `84762f0`, merge `d57f405`
- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_STATE_FLOW_MAP.md` — PR #156, commit `4b0f5d3`, merge `64a018b`

Scope guard: no production behavior changes, no `app.py` changes, no refactor, and no Airtable schema changes. The audit maps current tool architecture, contract coverage, bypass categories, high-risk bypasses, safe audit tests, and design-review items.

### PA-01 — Phantom Approval Prompt Structural Enforcement (TurnCoordinator) ✅ קוד הושלם ומוזג ל-`main` (PR #352, squash `2be2472`), דגל כבוי — לא מופעל בפרודקשן

Status: Merged to `main`, branch `claude/f52-audit-turn-ownership-u1gizk`, 22 commits squashed. Production deploy not verified from this sandbox (no Render dashboard/egress access). `FEATURE_PA01_ENFORCEMENT_STATE` (three-state `off`/`shadow`/`enforce`) defaults to `off` when unset or invalid — no production activation shipped in this PR.

What: prevents the agent from presenting an approval-pending response (`"⏳ הפעולה ממתינה לאישור..."`) unless the current turn holds structurally valid evidence — a genuine `ActionContract` created *this turn*, for the *expected canonical tool* — for the intent being served. Lives under `docs/architecture/turn-coordinator/` (a separate TurnCoordinator program, distinct from the `f52-unified-approval-runtime/` planning-only merge effort above — TurnCoordinator consumes F52's audit maps as input, does not replace it; see `docs/architecture/turn-coordinator/README.md`).

Core mechanism — a 5-row, state-only decision matrix in `run_agent()` (`app.py`), evaluated only for contract-required intents (`core/router/risk_router.py`'s `_CONTRACT_REQUIRED_INTENT_TO_TOOL`), and **never** inspecting the agent's own response text:
1. not contract-required → unaffected (pass-through).
2. a genuine contract for the expected tool was created *this turn* → Gateway's own prompt stands.
3. a real, gate-authored terminal outcome exists for the expected tool (duplicate, rejection, `APPROVAL_QUEUE_ORPHANED`, `APPROVAL_DEFERRED_BATCH`, ...) → that outcome's own message replaces the reply.
4. contract-required, capable, but no evidence at all → the Phantom fallback (generic "לא ניתן לאמת" message).
5. contract-required but not capable (role/permission gap) → the capability-unavailable fallback.

Planning → implementation → **5 sequential Codex re-audit rounds**, each closing a real correctness gap found by an independent review, not a cosmetic pass:

1. **`created_this_turn`** added as its own field — a non-`None` `contract_id` alone is not proof a contract was created this turn (`ActionGateway.propose_action()` returns a real `contract_id` for a pre-existing/rejected/duplicate contract too).
2. **Canonical tool wiring** — the sentinel's `action_tool` must be `resolve_canonical_tool()`'s output, never the raw `tool_use` block's `tu.name`, or a genuine contract for a Sheets/Drive-rewritten-to-Airtable tool could look "irrelevant" to the intent and trigger a false Phantom fallback.
3. **Architectural ruling: fingerprint is not ownership proof.** A business-action fingerprint proves two calls describe the same action, never that *this* call created or owns the specific `ActionContract` found under it (could be pre-existing or concurrently-created by a different turn). All fingerprint-based destructive cleanup was removed outright; mutation is now permitted only on a `contract_id` this call received directly from its own `propose_action()`. New terminal outcome `APPROVAL_QUEUE_ORPHANED` (alongside the existing `APPROVAL_QUEUE_ERROR`) — `contract_id=None` there means "not attributable to this call," never "confirmed absent."
4. **TOCTOU race in the atomic reject.** `ActionGateway.reject()` checked `status=="pending"` then wrote in a separate step — a concurrent approval could land in that window and be silently clobbered. Fixed: `ExecutionLedger.update_status(require_status=...)` performs the guard-and-set inside a single lock (RAM path); new additive `ActionGateway.reject_if_pending()` (the original `reject()` is untouched, still used by `route_cancellation_word`/the Telegram callback).
5. **The RAM-only atomic fix from round 4 was not atomic for the durable path.** Airtable-backed `ActionContractRepository.transition()` is read→check→PATCH, not a real compare-and-swap. Fixed: the repository declares `supports_atomic_conditional_transition = False`; the ledger refuses to route a conditional destructive write through a repository that doesn't declare `True` (fails closed, zero PATCH attempted — maps to `APPROVAL_QUEUE_ORPHANED`). Also fixed a real ordering bug found in the same round: `transition()`'s idempotent shortcut ran *before* the `expected_status`/`expected_version` check, so `expected=pending` against an actual `rejected` record could return false success — reordered to check expectations first.
6. **Structural cleanup round** — mechanical-only extraction of 4 helpers (`_revoke_and_verify_contract`, `_cancel_and_verify_pending`, `_orphan_cleanup_failure_response`, `_SAFE_CANCELLED_CONTRACT_STATUSES`) from `app.py` into new `core/approval_queue_recovery.py`. No circular import (module never imports `app.py`); `app.py` re-imports the names so every existing call site resolves unchanged. Verified via a dedicated structural audit — same object identity, byte-identical output, identical test counts before/after.

Files: `app.py`, `core/action_gateway.py` (`reject_if_pending()`, ownership rule), `core/action_contract_repository.py` (`supports_atomic_conditional_transition`, ordering fix), `core/approval_queue_recovery.py` (new), `core/router/risk_router.py`, `feature_flags.py`, `test_pa01_phantom_approval_enforcement.py` (new, 110 assertions), `docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md` (new, ~1750 lines — the source of record for every decision/deviation across all 6 rounds).

Also merged in the same PR (pre-existing on the branch, not part of the PA-01 work described above): **TurnCoordinator Phase 0 ownership-signal instrumentation** — `core/turn_envelope.py`'s `OwnershipSignal`, wired into `run_agent()`, the Telegram approval callback, TMA's write-approval entry point, and 2 scheduler proposal functions (`followup_engine.py`, `core/lead_recovery.py`). See `docs/architecture/turn-coordinator/README.md` and `docs/architecture/f52-unified-approval-runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`. Not independently re-verified as part of this ROADMAP update.

Validation (re-run at every round): `test_pa01_phantom_approval_enforcement.py` 110/110, full `test_*.py` script sweep 117/117, `smoke_tests.py` PASS, `python3 -m compileall .` clean, `git diff --check` clean.

**Scope guard, explicitly excluded from every round:** BUG-104 (Core Reasoning Layer, unrelated), any PostgreSQL/Atomic-Claims migration, full Airtable CAS implementation, general refactor of `ActionGateway`/`EventBus` beyond what's listed, any change to PA-01's own predicate/matrix/user-facing wording beyond what's described above.

**Side finding, not yet acted on:** several test files (`test_phase_4b_1b_durable_lifecycle.py`, `test_phase_4b_1a_lookup_correctness.py`, and others) are written `pytest`-style (fixtures, no `if __name__ == "__main__"` guard) and are **not** in `ci.yml`'s explicit `pytest` step — they're only picked up by the plain `for f in test_*.py; do python "$f"; done` sweep, which runs them with zero assertions executed and a false "green" exit. Same pattern as the historical BUG-049 (`test_document_converter.py`). Confirmed by reading `ci.yml` directly; not yet filed as a numbered BUG or fixed.

**Next:** decide on `FEATURE_PA01_ENFORCEMENT_STATE=shadow` production activation (log-only, no reply changes) to gather real evidence before `enforce`; no staged-rollout plan is written yet (same gap as Phase 4B below).

### Fxx — Safe Document Converter

Status: ⚠️ **תוקן 29/06/2026 (Gap Report) — היה כתוב "Not merged to main", שגוי.** מוזג בפועל
ל-`main` ב-PR #158, commit `db719ab`, **26/06/2026** — שלושה ימים לפני שהתיעוד עדכן את עצמו.
**מוזג אך לא מחובר** (אותו pattern כמו F20/F22): `convert_document()` נקרא רק מתוך
`test_document_converter.py` — אפס caller ב-`app.py`/`tools/dispatcher.py`/כל מודול חי אחר.
אין `FEATURE_` flag (אין צורך — אין נתיב הרצה חי שדורש הגנת flag).

**ממצא CI נוסף (29/06/2026), תוקן 02/07/2026 (BUG-049 / BUG-CI-SILENT-PASS-DOCUMENT-CONVERTER):**
`test_document_converter.py` היה כתוב בסגנון `pytest` (פונקציות `def test_...(tmp_path)` עם
fixtures) **בלי `if __name__ == "__main__":` block**. `ci.yml` מריץ כל `test_*.py` דרך
`python "$f"` (לא דרך `pytest`) — כלומר ב-CI הקובץ **רץ בלי לבצע אף assertion** (`exit 0`, 0
נבדקו בפועל), אף שהוא "ירוק". הרצה ידנית דרך `python3 -m pytest test_document_converter.py`
(עם `beautifulsoup4`/`markdown`/`python-docx`/`openpyxl` שכבר ב-`requirements.txt`) אישרה 6/6
PASS אמיתי — כלומר הקוד תקין, הבעיה הייתה רק בהרצה ב-CI. **תיקון (branch
`fix/ci-silent-pass-document-converter`, טרם ממוזג):** נוסף `__main__` guard לקובץ הבדיקה
בלבד (קורא לכל 6 הפונקציות במפורש עם temp dir, ללא שינוי ב-`ci.yml` וללא שינוי בלוגיקת
`document_converter/`) — `python3 test_document_converter.py` מריץ כעת 6/6 assertions אמיתיות
(אומת גם עם שבירה מכוונת → exit 1). ה-wiring (חיבור לנתיב חי) עדיין **לא** נפתר — ראו הפסקה
הבאה, EXISTS_UNWIRED נשאר בתוקף לגבי זה.

Status המקורי (לתיעוד היסטורי): Implemented but not yet verified. Local converter tests pass
(6/6) — תוקן מ-"Not merged" ל-"מוזג אך לא מחובר", per Gap Report 29/06/2026.

What: standalone deterministic conversion package `document_converter` with public API `convert_document(input_file, input_type, output_type)`. Supported MVP conversions: Markdown<->HTML, Markdown<->TXT, HTML<->TXT, Markdown/HTML/TXT->DOCX, DOCX->Markdown/TXT, CSV<->XLSX.

Governance: no AI for format conversion, no OCR, no PDF reconstruction, no guessed layout recovery. Unsupported or uncertain conversions fail closed with `confidence="low"` and `output_file=None`. Pandoc is preferred when installed; deterministic Python libraries are used as fallback for simple formats.

Files: `document_converter/`, `test_document_converter.py`, `docs/document_converter/SAFE_DOCUMENT_CONVERTER.md`, `docs/governance/DOCUMENT_CONVERSION_RULES.md`.
