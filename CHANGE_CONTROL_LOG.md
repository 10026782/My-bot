# CHANGE_CONTROL_LOG.md
> נכתב אוטומטית בכל merge ל-main. אל תערוך ידנית.

## פורמט רשומה

### [ID] — [שם השינוי]
- **תאריך:** 
- **סוג:** Feature / Bug Fix / Security / Schema Change / Hotfix
- **Requirement:** [קישור ל-ROADMAP item]
- **Commit:** [hash]
- **PR:** [מספר/קישור]
- **Review על ידי:** 
- **Deploy תאריך:** 
- **Verified בפרודקשן:** כן / לא / לא רלוונטי
- **Verification ראיה:** [מה נבדק, מה התוצאה]
- **Docs עודכנו:** ROADMAP / CURRENT_STATE / AI_CONTEXT / אחר
- **Feature Flag:** [שם / N/A]
- **Rollback plan:** [אם רלוונטי]

---

## לוג שינויים

> נבנה מ-`git log --since="30 days ago"` (~172 commits, `f935c53`→`eebf73b`) + טבלאות ROADMAP.md (Stabilization Sprint, World 2, Sprint 16/06). כל commit hash צוטט ישירות מ-git או מ-ROADMAP — שורות שלא נמצאה להן ראיה ישירה מסומנות "לא ידוע".

### C60 — Tool Context Awareness (last_tool_result + system-prompt injection + pronoun resolution)
- **תאריך:** 25/06/2026
- **סוג:** Feature — לא flag-gated (additive, לא נוגע בלולאה הקיימת)
- **Requirement:** `SPEC_C59_Tool_Context_Awareness.md` (הועלה ע"י הבעלים, ללא טקסט מלווה; אישור התקבל דרך `AskUserQuestion`: "Yes, implement now")
- ⚠️ **ID collision מתועד (כמו C54→C57):** הספק החיצוני תייג את עצמו "C59" — מתנגש עם C59 הקיים (Decision Hub Stage 1 Trust Layer, PR #151, ראו למעלה). תויג מחדש **C60** בכל מסמכי התיעוד; כותרת הספק עצמו ("SPEC_C59_...") וכל מחרוזות הקוד/log לא שונו.
- **תיאור:** פותר "עיוורון כלים" — הסוכן לא ידע מה כלי קודם עשה בסבב הקודם, מה שגרם ל-intent שגוי (למשל "תעלה לדסישנס" אחרי שקובץ כבר נמצא ב-context). שלושה חלקים: (1) **`session_store.py`** — `last_tool_result` נוסף ל-`_new_session()` + `set_last_tool_result`/`get_last_tool_result` חדשים ב-`PersistentSessionStore`, מסונכרנים ל-`State JSON` (sync/load/delete) בדיוק כמו `last_uploaded_file` הקיים מ-C58. (2) **`app.py`** — `_capture_last_tool_result()` נקרא אחרי כל dispatch אמיתי בלולאת ה-agent (לא על branches חסומים/ממתינים לאישור); `_build_tool_context()` מזריק "🔧 הקשר כלים" ל-`ctx.system_prompt` (TTL 5 דקות לפי timestamp); `resolve_context_pronouns()` מחליף כינויי הצבעה עבריים ("זה"/"הנספח"/"הקודם"/"ההוא"/"אותו") בהתייחסות מפורשת לפני ה-Router (שלב חדש "2.6").
- ⚠️ **3 סטיות מהטקסט המילולי של הספק, כולן מתועדות:**
  1. **חוזה tool_result שגוי בספק** — הספק מניח `tool_result.get("id")`/`("record_id")`/`("url")`/`("drive_url")`; החוזה האמיתי בקוד (C53-A, אומת ב-`test_c53a.py` — `set(r) == {"ok","tool","external_id","evidence","user_message"}`, ללא מפתחות נוספים) הוא `{ok, tool, external_id, evidence, user_message}`. תוקן: `record_id` נשלף מ-`external_id`, `url` נשלף מ-`evidence.get("htmlLink") or evidence.get("url")`.
  2. **`_seconds_ago()` מוזכר ב-§5 אך לא מוגדר בספק** (כמו `_has_keyword_conflict` ב-C59) — מומש inline ב-`_build_tool_context()` כ-diff בין `datetime.now(timezone.utc)` ל-`datetime.fromisoformat(timestamp)`, עטוף ב-try/except ל-timestamps פגומים.
  3. **§6 "Table Registry fix" (4 קבועי Decision Tables)** — אומת מראש דרך §8 PRE-SESSION GATE grep שכל 4 הקבועים (`DECISIONS`/`DECISION_EVENTS`/`DECISION_STAKEHOLDERS`/`DECISION_INBOX`) כבר קיימים ב-`airtable_schema.py` מ-C59 — no-op, לא נוצר שינוי מיותר.
- **Commit:** ייכלל ב-commit הקרוב על `claude/new-session-be1ckb`
- **PR:** אין — לא התבקש, ולא מבוצע ללא אישור מפורש לפי הנחיית הסשן
- **Review על ידי:** הבעלים (אישור "Yes, implement now" דרך `AskUserQuestion`)
- **Deploy תאריך:** לא רלוונטי — לא מוזג ל-`main`
- **Verified בפרודקשן:** לא — §10 פריט 7 בספק עצמו ("העלה קובץ → 'תעלה לדסישנס' → BOSS זוכר ומנתב נכון") עדיין לא אומת בלייב
- **Verification ראיה:** `python3 -m py_compile app.py session_store.py airtable_schema.py` נקי; `python3 session_store.py` → 40/40 self-tests עוברים (4 חדשים ל-C60: set/get round-trip, sync includes field, missing-session→None); `python3 test_c53a.py` → 50/50 (ללא רגרסיה בחוזה C53-A); `python3 test_integration.py` → 4/4; `python3 smoke_tests.py` — 2 כשלים קיימים-מראש (`flask`/`httpx` לא מותקנים בסביבת dev זו), אומת עם `git stash` שהם זהים על main, לא קשור לשינוי; §9 greps כולם תקינים (`set_last_tool_result`/`get_last_tool_result`/`_build_tool_context`/`הקשר כלים`/`resolve_context_pronouns`/4 קבועי Decision tables כולם נמצאים).
- **Docs עודכנו:** ROADMAP.md (C60 חדש + header, תיקון סטטוס מיזוג ל-C58/C59), CHANGE_CONTROL_LOG.md (רשומה זו + תיקון PR/Deploy ל-C58/C59), AI_CONTEXT.md
- **Feature Flag:** אין — תמיד-פעיל (additive, כמו `last_uploaded_file` ב-C58)
- **Rollback plan:** revert ה-commit הקרוב — שדה `last_tool_result` חדש ב-State JSON, אין breaking change לצרכנים קיימים; אם injection ל-system prompt גורם לבעיה (גודל/רעש), ניתן להסיר את שורת `ctx.system_prompt += _build_tool_context(chat_id)` בלבד בלי לגעת בשאר הקוד

### C59 — Decision Hub Stage 1: Trust Layer (Authority × Medium × Verify)
- **תאריך:** 25/06/2026
- **סוג:** Feature — flag-gated (`FEATURE_DECISION_HUB`, כבוי כברירת מחדל)
- **Requirement:** `SPEC_Decision_Hub_Stage1_Trust_Rev2.md` (הועלה ע"י הבעלים עם אישור מפורש: "ניתן ליישם ספק" — מהווה את אישור "אליהו" שהספק דרש ב-header שלו; הבעלים גם דיווח על יצירת 3 שדות Airtable: `Claim Topic`/`Claim Topic Source`/`Claim Topic Confidence`)
- **תיאור:** `gate_trust()` ב-`decision_pipeline.py` (היה stub) מומש במלואו — מודל Trust דו-מימדי: `AUTHORITY_SCORE`(מי אמר)×`MEDIUM_SCORE`(איך הגיע), עם medium ceiling (`compute_trust`/`score_to_level`); `extract_claim_topic()` גוזר נושא אוטומטית מ-4 מקורות לפי עדיפות (filename→Event Type→Delta Type→Raw Content keywords) עם ידני כ-fallback, מורחב להחזיר `(topic, source, confidence)` סביב 2 השדות שהבעלים הוסיף מעבר לטקסט המילולי של הספק; `maybe_supersede()` — supersede בטוח (רק אותו Claim Topic + Trust גבוה יותר). Verify-fail על מקור עם authority≥65 → T0 ישיר (לא T1 רך). T1 שקט (`user_flag=None`), T0 עם אזהרה.
- ⚠️ **9 סטיות מהטקסט המילולי של הספק, כולן מכוונות ומתועדות:**
  1. `VerifierPort.verify()` (`decision_ports.py`) מחזיר `dict` (`{"verified": bool, ...}`) — לא object עם `.status` כפי שהספק מניח. שונה ל-`{"status": "ok"/"warn"/"failed"/"hallucination", "reason": ...}`; `gate_trust` קורא עם `.get("status", "ok")`.
  2. `decision["id"]` — `maybe_supersede` בספק קורא ID ישירות מ-`decision`, אבל שתי נקודות הקריאה האמיתיות ב-`cmd_decision.py` מעבירות ל-`run_pipeline` רק את `decision["fields"]`/`decision_record["fields"]` (sub-dict בלי `"id"`) — היה גורם ל-`KeyError`. תוקן: ה-ID מוזרק כ-`event["_decision_id"]` בנקודות הקריאה (`_handle_update_step`/`_link_inbox_to_decision`), ו-`maybe_supersede` קורא משם.
  3. Tags: הספק כותב מחרוזות אנגלית ("potential_conflict"/"low_confidence"/"pressure_high_risk") — אלה לא קיימות כאופציות Multi-Select חיות ב-Airtable (סיכון `INVALID_MULTIPLE_CHOICE_OPTIONS`). נעשה שימוש ב-`DecisionEventTag.CONFLICT`("קונפליקט") הקיים; נוספו 2 קבועים עבריים חדשים (`LOW_CONFIDENCE`="אמינות_נמוכה", `PRESSURE_HIGH_RISK`="לחץ_סיכון_גבוה") **שלא אומתו מול Airtable חי** — בניגוד ל-`Claim Topic Source` שהבעלים אישר במפורש.
  4. `_has_keyword_conflict()` — הספק מפנה לפונקציה זו ב-§5 שלב ו' אך **לא הגדיר את גוף הלוגיקה בכלל** בטקסט הספק. מומשה כ-stub שמחזיר `False` עם תיעוד inline; נתיב ה-"conflict tag" לא פעיל בפועל עד שתוגדר לוגיקה (Stage 1.x/Stage 2 — מתאים ל-§11 "AI Conflict Detection — Stage 2" שכבר מוחרג בספק).
  5. `DecisionSourceReliability` (`airtable_schema.py`) היו חסרים 4 מתוך 10 מפתחות `AUTHORITY_SCORE` — נוספו `DOCUMENT`("מסמך")/`MANUAL`("ידני")/`EMPLOYEE`("עובד")/`UNKNOWN`("לא_ידוע").
  6. `event["Channel"]` לא היה מועבר כלל ל-`gate_trust` לפני התיקון (היה נכתב רק ב-write-time, אחרי שהשער כבר רץ) — תוקן בשתי נקודות הקריאה. `event["Source Reliability"]` **עדיין לא מוזן ע"י שום UI קיים** ב-`/decision update` — `gate_trust` יחזיר תמיד authority=55(ידני) default עד שתיווסף שאלה ייעודית; מחוץ לטקסט המילולי של הספק, לא תוקן בסבב הזה (דגול ל-Stage 1.x).
  7. פלטי ה-Trust Layer (Trust Level/Confidence/Tags/Claim Topic+Source+Confidence/Source Reliability/Supersedes) לא נכתבו ל-Airtable כלל — נוספה `_add_trust_fields()` ב-`cmd_decision.py`, מחוברת לשני נתיבי הכתיבה (`_create_decision_event`/`event_fields` ב-`_link_inbox_to_decision`).
  8. `run_pipeline()` היה מזניח את `user_flag` של שערים שעברו בהצלחה (בנה `GateResult` סינתטי חדש עם `user_flag=None` בסוף) — נוסף `collected_flag` שעוקב על ה-flag האחרון שאינו `None` בכל איטרציה, ומועבר ל-`GateResult` הסינתטי הסופי. בלי התיקון, הודעת "📝 לא זיהיתי נושא" (T2/T3 בלי Claim Topic) לא הייתה מוצגת למשתמש אף פעם.
  9. `_format_pipeline_outcome()` לא טיפל ב-`halted_at == "trust"` (T0/T1) ולא בדק `result.user_flag` בנתיב ההצלחה — נוסף branch מפורש ל-trust + הצמדת `user_flag` (אם קיים) להודעת ההצלחה הגנרית.
- **Commit:** `73f6fe8`
- **PR:** #151 — **מוזג ל-`main`** (`merged: true`, אומת ע"י GitHub MCP `pull_request_read`, לא רק לפי דיווח המשתמש); branch מרוחק `claude/new-session-be1ckb` נמחק בהתאם
- **Review על ידי:** הבעלים (אישור "ניתן ליישם ספק" על ספק שהיה מסומן SPEC ONLY)
- **Deploy תאריך:** לא ידוע — מיזוג ל-`main` אומת, אך פריסה בפועל ל-Render **לא ניתנת לאימות מתוך sandbox זה** (אין גישת dashboard/egress)
- **Verified בפרודקשן:** לא — §10 פריט 11 בספק עצמו ("אירוע T0 אמיתי → user_flag בטלגרם") עדיין לא אומת מול פרודקשן חי
- **Verification ראיה:** `python3 -m py_compile airtable_schema.py decision_ports.py decision_pipeline.py cmd_decision.py test_decision_trust.py` נקי; `python3 test_decision_trust.py` → 33/33 self-tests עוברים (compute_trust edge cases, extract_claim_topic priority order, maybe_supersede same-topic-only, gate_trust T0/T1/T2/T3 branches, run_pipeline user_flag propagation); §9 greps כולם תקינים (`AUTHORITY_SCORE`/`MEDIUM_SCORE`/`compute_trust`/`extract_claim_topic`/`maybe_supersede`/`Claim Topic` נמצאים, `grep -n "trust stub"`→0 matches, `grep -c "SOURCE_TRUST"`→0); `python3 smoke_tests.py`/`python3 test_integration.py` — אין רגרסיה (2 כשלי smoke_tests קיימים-מראש, נבדק עם `git stash` שהם זהים על main, סיבה: `flask`/`httpx` לא מותקנים בסביבת dev זו, לא קשור לשינוי).
- **Docs עודכנו:** ROADMAP.md (N13 הורחב + header), CHANGE_CONTROL_LOG.md (רשומה זו), AI_CONTEXT.md
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן
- **Rollback plan:** revert ה-commit הבא — דגל כבוי כך שאין breaking change בפרודקשן בכל מקרה; אם נדרש rollback חלקי, `gate_trust` חוזר ל-stub הישן (`GateResult(True, "trust stub — stage 1", next_gate="readiness")`)

### C58 — Universal Sessions: Sessions table replaces non-existent LeadSessions
- **תאריך:** 25/06/2026
- **סוג:** Bug Fix (latent 403 on every session write) + Schema Change — לא flag-gated
- **Requirement:** `SPEC_C58_Universal_Sessions.md` (הועלה ע"י הבעלים עם הוראה מפורשת "implement" — מהווה את אישור "אליהו" שהספק דרש ב-header שלו)
- **תיאור:** `Tables.LEAD_SESSIONS` ("LeadSessions") **לא קיימת בפועל ב-Airtable** — כל כתיבה אליה הייתה מחזירה 403 (באג latent, לא תועד קודם ב-`BUG_AUDIT_LOG.md`). הוחלפה ב-`Tables.SESSIONS` (טבלה אמיתית, `tblHLfE24lTkVUhz0`) עם schema גנרי משותף: `class SessionsFields` (`airtable_schema.py`) — `Context Type` (select, ברירת מחדל `"lead"` לתאימות לאחור), `State JSON` (כל ה-state הקיים — domain/step/answers/done/drop_off_step/score/tier/last_uploaded_file — בשדה טקסט יחיד), `Sender ID`/`Channel`/`Created At`/`Updated At`, ו-10 שדות `Linked *` אופציונליים (Lead/Contact/Decision/Deal/Task/Payment/Venture/Media File/Business Memory/Decision Event). `session_store.py`'s `_sync_to_db`/`_load_from_db`/`_delete_from_db` נכתבו מחדש מלא לשימוש ב-Sessions; `_extract_balanced_json()` חדש (brace-depth counting, לא regex naive) מחלץ את ה-JSON המקונן מתוך הפורמט הטקסטואלי שמ-`airtable_get()` מחזיר.
- ⚠️ **4 סטיות מהטקסט המילולי של הספק, כולן מכוונות ומתועדות:**
  1. **`external_id` extraction** — הספק הציע `result.get("id") or result.get("record_id") or result.get("external_id")`; מומש כ-`result.get("external_id", "")` ישירות, לפי חוזה C53-A האמיתי שאומת ב-`tools/airtable_tools.py` (`_tool_result()` מחזיר מפתח `external_id` בלבד).
  2. **`last_uploaded_file` חסר ב-State JSON** — הספק השמיט אותו מה-snippet המוצע, בסתירה לעקרון "State JSON = כל ה-state הקיים. אפס אובדן מידע" שהוא עצמו מצהיר ב-§4. נוסף ל-State JSON וגם `set_last_file()` עודכן לקרוא בפועל ל-`_sync_to_db()` (לפני כן לא היה מסונכרן ל-DB בכלל).
  3. **`LINKED_MEDIA_FILE` table-identity mismatch** — הספק הציע לקשר את `last_uploaded_file.file_id` תמיד; אומת ב-`cmd_decision.py`/`app.py` ש-`type="inbox_file"` שומר record ID מטבלת **Decision Inbox**, ו-`type="drive_file"` שומר record ID מטבלת **Media Files** — שני סוגי record ID שונים. קישור ה-inbox_file record ל-`LINKED_MEDIA_FILE` (שמייעד ל-Media Files) היה גורם ל-`INVALID_RECORD_ID` באירטייבל. תוקן: הקישור מתבצע רק כש-`type == "drive_file"`.
  4. **`_delete_from_db` מאבד state** — הספק הציע להחליף את כל ה-`State JSON` ב-`{"done": True, "deleted": True}` בלבד, מוחק domain/step/answers/score/tier. תוקן: `_delete_from_db` מקבל גם את `session` המלא ובונה tombstone ששומר את כל השדות הקיימים + `done`/`deleted=True`.
  - בנוסף תוקן באג קדם-קיים (לא קשור ל-C58, התגלה תוך כדי הוספת בדיקות): ה-mock ב-`_run_tests()` רשם `sys.modules["airtable_tools"]` במקום `sys.modules["tools.airtable_tools"]` (הנתיב האמיתי שממנו `session_store.py` מייבא) — `ImportError` נתפס בשקט ב-`_sync_to_db`/`_load_from_db`, כך שכל בדיקות ה-DB-sync "עברו" מבלי לבדוק דבר (כפי שתועד גם ב-N13 לעיל: "18/20, 2 כשלים קיימים מראש" — אלה היו אותם 2 כשלים, לא קשורים-בטעות לתיקון).
- **Commit:** `84f2ef3`
- **PR:** #150 — **מוזג ל-`main`** (`merged: true`, אומת ע"י GitHub MCP `pull_request_read`, לא רק לפי דיווח המשתמש); branch מרוחק `claude/new-session-be1ckb` נמחק בהתאם
- **Review על ידי:** הבעלים (הוראת "implement" על הספק שהיה מסומן SPEC ONLY)
- **Deploy תאריך:** לא ידוע — מיזוג ל-`main` אומת, אך פריסה בפועל ל-Render **לא ניתנת לאימות מתוך sandbox זה** (אין גישת dashboard/egress)
- **Verified בפרודקשן:** לא — סעיף 7 בספק עצמו (item 5, "session חדש → רשומה נוצרת ב-Sessions ב-Airtable") עדיין לא אומת מול Airtable חי
- **Verification ראיה:** `python3 -m py_compile session_store.py airtable_schema.py app.py cmd_decision.py` נקי; `python3 session_store.py` → 36/36 self-tests עוברים (כולל 11 בדיקות חדשות ל-C58: `_extract_balanced_json` עם JSON מקונן, `context_type` ברירת מחדל, מבנה `State JSON` ב-`_sync_to_db`, gating נכון בין drive_file/inbox_file, round-trip מלא של `_load_from_db` מול מחרוזת מזויפת בפורמט האמיתי של `airtable_get()`); spec §6 greps כולם תקינים (`grep -c "LeadSessions" session_store*.py` → 0, `class SessionsFields`/`Tables.SESSIONS`/`State JSON`/`context_type` כולם נמצאים)
- **Docs עודכנו:** ROADMAP.md (C58 חדש + header), CHANGE_CONTROL_LOG.md (רשומה זו), AI_CONTEXT.md
- **Feature Flag:** אין — תשתית sessions תמיד-פעילה (לא אופציונלית), כמו `session_store.py` הקודם
- **Rollback plan:** revert ה-commit הבא — `Tables.LEAD_SESSIONS` עדיין קיים בקוד (deprecated, לא נמחק) כך שאין breaking change בממשק; הסיכון העיקרי הוא ש-`Tables.SESSIONS`/שדות `SessionsFields` לא תואמים 1:1 לשמות השדות האמיתיים ב-Airtable (לא אומת ישירות מול ה-base, רק לפי הספק) — אם כתיבה ראשונה בפרודקשן תיכשל, יש לבדוק שמות שדות מול schema חי לפני כל דבר אחר

### C57 — Agent Tool Awareness: suppress premature text_block alongside tool_use (PR #149)
- **תאריך:** 25/06/2026
- **סוג:** Bug Fix (UX-level, behavior change — לא flag-gated)
- **Requirement:** `SPEC_C54_Agent_Tool_Awareness.md` (הועלה ע"י הבעלים, אושר במלואו: "Yes, both changes")
- **תיאור:** Claude מחזיר לעיתים `text_block` ו-`tool_use` באותה API response. ה-text נכתב לפני שהמודל ראה את תוצאת הכלי — אם הוא נשלח למשתמש (כמו "לא הבנתי מה לעלות") לפני שהכלי רץ בפועל, נוצרת תשובה סותרת/מבלבלת ב-turn אחד בלבד, גם כשהכלי בפועל הצליח. תיקון בשתי שכבות: (1) **`app.py`** (אחרי חילוץ `tool_uses`/`text_blocks` בלולאת ה-agent) — אם שניהם קיימים באותה תשובה, `text_blocks` מאופס ל-`[]` ונכתב `logger.info("[C54] Suppressed premature text_block alongside tool_use: ...")`; הלולאה ממשיכה, הכלי רץ, והתשובה האמיתית מגיעה ב-turn הבא עם תוצאת הכלי. (2) **`core_knowledge.py`** — כלל 7 חדש בבלוק `_NEVER_FAKE_CONTROL`: "כשאתה מפעיל כלי, אל תכלול טקסט הסבר או שאלת הבהרה באותה תשובה. הפעל את הכלי. קבל את התוצאה. ענה למשתמש רק אחרי שיש לך תוצאה." השכבה הראשונה (קוד) מגנה על מה שהשנייה (prompt) לא תפסה.
- ⚠️ **ID collision מתועד:** הספק החיצוני תייג את התיקון "C54" — מתנגש עם C54 הקיים ב-`ROADMAP.md` (Business Memory /update command, PR #85). תויג מחדש **C57** בכל מסמכי התיעוד (ROADMAP/CHANGE_CONTROL); `logger.info` בקוד עצמו וה-docstring ב-`core_knowledge.py` נשארו עם תג `[C54]`/הערת "C54" כפי שנכתבו, כדי לא לגעת בלוג production string ללא צורך תפעולי — ה-mapping מתועד כאן.
- **Commit:** `cc6142b`
- **PR:** #149 — https://github.com/10026782/My-bot/pull/149 — **מוזג ל-`main` ב-commit `1d08402`**
- **Review על ידי:** הבעלים (אישר את שני השינויים במפורש לפני כתיבת קוד, per SPEC ONLY gate)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — ממתין לראות `[C54] Suppressed premature text_block` ב-Render logs (ראו §8 של הספק המקורי); אם לא מופיע תוך שבוע מה-deploy, סימן ש-prompt rule בלבד הספיק.
- **Verification ראיה:** `git fetch origin main` + `git merge-base --is-ancestor cc6142b origin/main` → exit 0; `python3 -m py_compile app.py core_knowledge.py` נקי.
- **Docs עודכנו:** ROADMAP.md (C57 חדש + header), CHANGE_CONTROL_LOG.md (רשומה זו)
- **Feature Flag:** אין — שינוי קוד תמיד-פעיל בלולאת ה-agent, לא flag-gated (תיקון התנהגות בסיסי, לא פיצ'ר)
- **Rollback plan:** revert PR #149 — מחזיר התנהגות קודמת (text+tool_use לעיתים נשלחים יחד); אין סיכון דאטה, רק UX

### N13 — Decision Hub Stage 0.5/0.6 + BUG-017/BUG-B + MODULE_RULES 7-10/12 (PR #147)
- **תאריך:** 25/06/2026
- **סוג:** Feature (flag off) + Bug Fix + Docs
- **Requirement:** ROADMAP.md N13 (נוסף באותו commit — Decision Hub לא היה מתועד ב-ROADMAP לפני כן)
- **תיאור:** `cmd_decision.py`/`app.py` — Stage 0.5 (File/Voice Precedence Routing: `decision_context_active()`, `route_file_to_decision_inbox()`, מוטמע ב-`_handle_telegram_media` עם fail-safe exception handling) ו-Stage 0.6 (File Context Reference: `FileUploadResult`/`set_last_file`/`get_last_file` ב-`session_store.py`, וזיהוי "זה הנספח" דרך `is_attachment_reference()`/`handle_attachment_reference()`, ממוקם ב-`_webhook_telegram_impl` הטלגרם-ספציפי ולא ב-`run_agent()` המשותף-לכל-הערוצים — תיקון ארכיטקטוני שנעשה תוך כדי הבנייה). תוקנו: BUG-017 (`session_store._sync_to_db` קרא חוזה dict כ-string) ו-BUG-B (LeadSessions תחת schema governance, additive). `docs/governance/MODULE_RULES.md` קיבל חוקים 7 (Ports), 8 (Tool↔Gate), 9 (Input Precedence), 10 (Raw-First), 12 (Domain-Agnostic Core — ממוספר 12 לא 11 כדי לא להתנגש עם חוק 11 הקיים, כתיב שמות שדות). נוסף `docs/governance/PLANNING_GATE.md`. נוסף `archive/BOSS_MASTER_PLAN_One_Road.md` (ARCHIVE, לא מקור אמת — ראו הערת מקור בראש הקובץ).
- **Commit:** `a6483c8` (MODULE_RULES 7-10 + BUG-B), `fdeb039` (BUG-017), `4ac2a05` (Stage 0.5), `e0f0111` (Stage 0.6)
- **PR:** #147 — https://github.com/10026782/My-bot/pull/147 — **מוזג ל-`main` ב-commit `483851f`**
- **Review על ידי:** הבעלים (אישר מיזוג מפורשות אחרי שאי-מיזוג קודם זוהה ותוקן)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא — `FEATURE_DECISION_HUB` כבוי כברירת מחדל, אפס שינוי התנהגות בפרודקשן
- **Verification ראיה:** `git fetch origin main` + `git merge-base --is-ancestor origin/claude/new-session-be1ckb origin/main` → exit 0 (מאומת PR ממוזג בפועל, לא רק לפי הצהרה); `py_compile` נקי על `app.py`/`cmd_decision.py`/`session_store.py`; `session_store.py` self-test 18/20 (2 כשלים קיימים מראש, מתועדים, לא קשורים לשינוי)
- **Docs עודכנו:** ROADMAP.md (N13 חדש), AI_CONTEXT.md, BUG_AUDIT_LOG.md (BUG-017), MODULE_RULES.md, PLANNING_GATE.md (חדש), archive/BOSS_MASTER_PLAN_One_Road.md (חדש)
- **Feature Flag:** `FEATURE_DECISION_HUB` — כבוי כברירת מחדל
- **Rollback plan:** revert PR #147 — דגל כבוי, אפס סיכון פונקציונלי מיידי בפרודקשן

### N08 / N09 / N11 — ROADMAP status drift correction (docs-only)
- **תאריך:** 22/06/2026
- **סוג:** Docs-only correction, אפס שינוי קוד
- **Requirement:** התגלה בתחילת מימוש N11 (`pre_session_gate.sh` + `git checkout -b claude/n11-finance-pulse`) — לפני כתיבת קוד, נקרא `tma_api.py`/`airtable_schema.py` כדי לאמת שמות שדות לפי הנחיית המשתמש ("שמות שדות חייבים להתאים ל-live Airtable"), ונמצא ש-`finance_pulse()` כבר עובר דרך `SCREEN_CONFIGS["finance_pulse"]` + `_build_formula(entity="Payment")` — כל היקף N11 כבר ממומש ומאוחד. בדיקה נוספת (grep על `main`) חשפה שגם N08 ו-N09 — שהושלמו ומוזגו **בתוך הסשן הזה עצמו** (PR #103/#104) — נשארו מתויגים `🔲 PLANNED` ב-`ROADMAP.md`.
- **תיאור:** `ROADMAP.md` — שלוש רשומות (N08/N09/N11) עודכנו מ-`🔲 PLANNED` ל-`✅ הושלם` עם commit hash + PR, header (שורה 3) עודכן ל-`main` HEAD נכון (`24237e6`). `AI_CONTEXT.md` — Executive Summary, "חסום", "Next Priorities" item 3, ושלוש רשומות חדשות ב-"Completed Since Last Update" (PR #103/#104 + הערת התיקון עצמו). `CHANGELOG.md` — רשומת Unreleased חדשה. אפס שינוי ב-`tma_api.py`/`core/error_reporter.py`/`.github/workflows/ci.yml` עצמם — כולם נכונים כבר.
- **Commit:** (ראו commit log על `claude/n11-finance-pulse`)
- **PR:** טרם נפתח
- **Review על ידי:** —
- **Deploy תאריך:** N/A — docs-only
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** `git log --oneline --merges main | grep -i "n08\|n09"` אישר PR #103 (`abf4835`)/PR #104 (`24237e6`) על `main`; `grep -n "report_error\|error_reporter" app.py` אישר 3 קריאות חיות; `ls .github/workflows/ci.yml` אישר קיום; `grep -n "_build_formula\|entity.*Payment" tma_api.py` אישר wiring N11 (PR #77, `f7d7e4f`/`daab73e`, מאומת `git merge-base --is-ancestor f7d7e4f main`).
- **Docs עודכנו:** ROADMAP.md, AI_CONTEXT.md, CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה)
- **Feature Flag:** ללא שינוי
- **Rollback plan:** revert — docs-only, אפס סיכון

### C22 (spec ID, לא ROADMAP) — Weekly Business Summary
- **תאריך:** 22/06/2026
- **סוג:** Feature
- **Requirement:** spec חיצוני "C22 — Weekly Business Summary" (⚠️ ID זה מתנגש עם ROADMAP.md's C22 הקיים — "feature_flags is_enabled() alias", לא קשור; אותו דפוס תועד עבור C20/C21)
- **Commit:** `c4527b7`
- **PR:** #94 (`claude/weekly-business-summary-4crnek`)
- **Review על ידי:** Claude Code (session), אושר ע"י המשתמש
- **Deploy תאריך:** 22/06/2026 — Render (אישור משתמש)
- **Verified בפרודקשן:** לא ידוע — המשתמש אישר deploy ל-`d91a9df`, לא אומת עצמאית מסביבת Claude (אין גישת Dashboard/egress)
- **Verification ראיה:** `py_compile` נקי; `smoke_tests.py`/`test_integration.py`/`core/router/test_router.py` עוברים; תרחישי A/B/C/D מהספק נבדקו ידנית עם mock data
- **Docs עודכנו:** AI_CONTEXT.md, CHANGELOG.md, feature_flags.py (רישום הדגל), CHANGE_CONTROL_LOG.md (זה)
- **Feature Flag:** `FEATURE_WEEKLY_SUMMARY` — כבוי כברירת מחדל
- **Rollback plan:** `FEATURE_WEEKLY_SUMMARY=false` (ברירת מחדל); try/except ב-scheduler בולע כל כשל; המערכת עולה רגיל גם בלי `weekly_summary.py`

### C25–C40 — Stabilization Sprint (07/06/2026)
- **תאריך:** 07/06/2026
- **סוג:** Bug Fix (batch — 16 פריטים, C25–C40)
- **Requirement:** ROADMAP.md "Stabilization Sprint — 07/06/2026"
- **Commit:** מפתחות עיקריים: `0744ce9` (C37, payment_reminder self-test), `4e5d00d` (C40, Golden Path Approval Gate על branch `origin/approval-gate`, supersedes local `f3172ba`); שאר ה-IDs (C25–C36, C38, C39) — commit ייחודי לכל אחד לא תועד ב-ROADMAP בנפרד, רק שם הקובץ ששונה.
- **PR:** לא ידוע — דרוש בדיקה ידנית (ROADMAP לא מצטט מספרי PR לטווח זה)
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין ראיה מתועדת מעבר לתיאור "מה תוקן" בטבלת ROADMAP
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A (חלק נוגע ב-EMERGENCY_STOP persistence — C33)
- **Rollback plan:** לא תועד

### C40 — Golden Path Approval Gate
- **תאריך:** 07/06/2026
- **סוג:** Security
- **Requirement:** ROADMAP.md C40 — "TMA write endpoints now require approval before Airtable writes"
- **Commit:** `4e5d00d` (origin/approval-gate; supersedes local `f3172ba` per ROADMAP)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### W0 — WhatsApp Lead Capture
- **תאריך:** 08/06/2026
- **סוג:** Feature
- **Requirement:** ROADMAP.md "World 2 — Lead Flow Sprint", N01 prerequisite
- **Commit:** `2b861bd`
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `LEAD_CAPTURE`
- **Rollback plan:** לא תועד

### W1 / W1b — Airtable Schema Fix (N01)
- **תאריך:** 08/06/2026
- **סוג:** Schema Change
- **Requirement:** ROADMAP.md N01 ("✅ הושלם — W1 לעיל")
- **Commit:** W1 = `f095036`; W1b (Score/Next Followup case fix) = `a6b471c`
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md, `schema_cache.json`
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### W2 — Airtable Gateway, single write path
- **תאריך:** 08/06/2026 (refactor המשך: `f964070` ,`b43357e`)
- **סוג:** Feature / Security (consolidates write-path enforcement)
- **Requirement:** ROADMAP.md W2 — "tools/airtable_gateway.py: normalize→validate→audit→httpx"
- **Commit:** `b43357e` (refactor: single write path), `f964070` (gateway bonus fix — Owner multipleRecordLinks coercion)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** "22-test regression suite" מוזכר ב-ROADMAP — קובץ הטסטים (`test_airtable_gateway.py`) קיים בריפו, **לא הורץ בפועל בסשן האודיט הזה**
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### N02 / N03 — Lead Scoring + Lead Memory Wire-up
- **תאריך:** לא ידוע מדויק (לפני 17/06/2026, אחרי W2)
- **סוג:** Feature
- **Requirement:** ROADMAP.md N02/N03 — "✅ מיושם" (קוד), אך flags כבויים בפרודקשן
- **Commit:** `4d1130a` (consolidation, lead_scoring.py הוסר), `02f7e75` (N04-A/B wiring — lead_memory.update בעת create + אחרי scoring)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא — flags `LEAD_SCORING`/`LEAD_MEMORY` כבויים ברירת מחדל (ראה BOSS_CURRENT_STATE.md citations: `lead_capture.py:32,90,96,130,134-138`)
- **Verification ראיה:** אין אימות production; קוד בלבד
- **Docs עודכנו:** ROADMAP.md, BOSS_CURRENT_STATE.md
- **Feature Flag:** `LEAD_SCORING`, `LEAD_MEMORY` (שניהם כבויים ברירת מחדל)
- **Rollback plan:** N/A — flags כבר כבויים, אין expose בפרודקשן

### N04 — Followup Activation
- **תאריך:** לא ידוע מדויק
- **סוג:** Feature
- **Requirement:** ROADMAP.md N04 — "✅ scheduler מחובר (flag כבוי)"
- **Commit:** `02f7e75` (N04-A/B — lead_memory.all_active תיקון)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא — ROADMAP מצהיר במפורש "המתנה לפני הפעלה: לאמת ב-Render env עם הודעת WhatsApp אמיתית + LEAD_CAPTURE=true"
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `FOLLOWUP_AUTOMATION` (כבוי ברירת מחדל)
- **Rollback plan:** N/A — flag כבוי

### N05-B — send_followup.confirmed handler
- **תאריך:** לא ידוע מדויק
- **סוג:** Feature
- **Requirement:** ROADMAP.md N05-B — "✅ מיושם"
- **Commit:** `643f929`
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין; ROADMAP מציין "אין שליחה יוצאת לליד — Meta outbound blocked עד N05-C"
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `FOLLOWUP_AUTOMATION`
- **Rollback plan:** לא תועד

### N05 — Daily Digest שדרוג (Score+Tier wiring)
- **תאריך:** 17/06/2026 (`5490943`, ממוזג ל-main דרך `422c280`)
- **סוג:** Feature
- **Requirement:** ROADMAP.md N05 — "✅ מיושם", תלוי ב-N02
- **Commit:** `5490943` ("N05: wire real Score + computed tier into daily digest")
- **PR:** לא ידוע מספר — ממוזג ל-main כ-`422c280` ("Merge claude/meta-whatsapp-phase-1-q6pp3e: N05 Daily Digest Score+tier wiring")
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A (קורא Score, לא כתיבה)
- **Rollback plan:** לא תועד

### N06 — Ventures Screen (TMA)
- **תאריך:** 17/06/2026
- **סוג:** Feature
- **Requirement:** ROADMAP.md N06 — "✅ מיושם", תלוי ב-N05; החלטה ארכיטקטונית 17/06/2026 (Ventures = טבלה נפרדת)
- **Commit:** `eebf73b` ("N06: add Ventures Screen (TMA) — strategic pre-lead/pre-deal pipeline")
- **PR:** #67 (ממוזג ל-main ב-`7313b2e3`, "Merge pull request #67: N06 — Ventures Screen (TMA)")
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע — שדות הקוד תואמים 1:1 לסכמה חיה של טבלת Ventures (אומת ע"י Airtable MCP, 17/06/2026), אך לא בוצעה בדיקה ידנית במסך TMA החי
- **Verification ראיה:** Airtable MCP schema dump — התאמה מלאה בין `VentureFields`/`tma_api.py` לסכמה חיה
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### Sprint 16/06/2026 — C41–C51
- **תאריך:** 16/06/2026
- **סוג:** Feature / Bug Fix (batch — 11 פריטים)
- **Requirement:** ROADMAP.md "Sprint 16/06/2026"
- **Commit:** ראו פירוט: C45=PR #59, C46=PR #61, C47=PR #62, C48=PR #63, C49=PR #60, C51=branch `furniture-funnel-clean` (`test_approval_concurrency.py`); C41–C44, C50 — אין PR מצוטט ב-ROADMAP
- **PR:** #59, #60, #61, #62, #63 (פירוט לפי שורה למעלה)
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md
- **Feature Flag:** `LLM_FALLBACK` (C41/C42, כבוי ברירת מחדל — `feature_flags.py:40`)
- **Rollback plan:** לא תועד

### Stage 0 — BOSS Refactor Plan bug fixes (BUG-001–006)
- **תאריך:** 16–17/06/2026
- **סוג:** Bug Fix
- **Requirement:** `BOSS_Refactor_Plan.md` Stage 0; פירוט מלא ב-`BUG_AUDIT_LOG.md`
- **Commit:** `628d2bb` (BUG-005/006), `a462633` (BUG-003/004, ומשפיע גם על BUG-002), `d3243ef`+`1876842` (BUG-002)
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא — ראו `BUG_AUDIT_LOG.md`, כל הפריטים "Fixed — ממתין ל-Verify" מעבר ל-BUG-005/006 שמסומנים "Fixed ✅" בקוד בלבד (לא verified-בפרודקשן)
- **Verification ראיה:** אין בדיקה ידנית מתועדת בפרודקשן
- **Docs עודכנו:** `BOSS_Refactor_Plan.md`, `BUG_AUDIT_LOG.md` (קובץ זה)
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### Security fixes — אצווה מרוכזת (07–16/06/2026)
- **תאריך:** טווח 07–16/06/2026
- **סוג:** Security
- **Requirement:** לא ידוע — אין רשומת ROADMAP מאוחדת; כל commit מתעד את עצמו
- **Commit:** `9384f89` (Batch 1 — permission/schema hardening), `aca037b` (fail-closed router + strip public /health), `63966dd` (remove DEV_MODE dead code + worker impersonation fix), `e76c247` (7 audit findings — app.py/tma_api.py/dispatcher), `eb1f42b` (2 HIGH — formula injection + approval TOCTOU), `2bae2e6` (3 MEDIUM findings), `126e34c` (2 HIGH — 3-state approval claim + concurrency lock), `f6281a5` (webhook fail-closed + bus._pending private access), `badfb84` (webhook moved from /<TOKEN> to /telegram), `3a4dbc5`/`ef05dcf` (READ_ONLY_FIELDS[Leads] expansion), `9e609cb` (block 5 non-existent/formula fields)
- **PR:** לא ידוע — דרוש בדיקה ידנית
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין ראיה production; `SECURITY_CHECKLIST.md` מסומן ARCHIVED מ-2026-06-14 ולא מתעד ולידציה לאחר מכן
- **Docs עודכנו:** `docs/governance/SECURITY_CHECKLIST.md` (חלקית, לפני 14/06)
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### Schema fix — tier writable singleSelect
- **תאריך:** לא ידוע מדויק
- **סוג:** Schema Change
- **Requirement:** ROADMAP.md "Known Issues / Tech Debt" (רשומה זו **מיושנת** — ראו AI_CONTEXT.md §8 OPEN RISKS)
- **Commit:** `3d8ab50` ("fix: tier is now writable singleSelect — unblock in READ_ONLY_FIELDS, remove dangerous alias, update tests")
- **PR:** לא ידוע
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע
- **Verified בפרודקשן:** כן — סכמה חיה (Airtable MCP, 17/06/2026) מאשרת ששדה `tier` קיים כ-`singleSelect` (`fld4eC2mEYrviL3oP`) בטבלת Leads, תואם להחלטת הקוד
- **Verification ראיה:** Airtable MCP `list_tables_for_base` schema dump, 17/06/2026
- **Docs עודכנו:** **לא** — ROADMAP.md "Known Issues" עדיין מתאר את `tier` כ"לא קיים... החלטה נדרשת" (drift מתועד)
- **Feature Flag:** N/A
- **Rollback plan:** N/A

### C52 — Customer Output Gateway (COG)
- **תאריך:** 18/06/2026 (מוזג)
- **סוג:** Feature
- **Requirement:** ROADMAP.md "Sprint 16/06/2026" → C52
- **Commit:** ראו ROADMAP.md C52 row
- **PR:** #70
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** אין
- **Docs עודכנו:** ROADMAP.md (בזמן ה-PR); תיעוד זה (CHANGE_CONTROL_LOG) — retroactively, 19/06/2026
- **Feature Flag:** Financial Gate ב-shadow mode (לא חוסם, ESCALATE בלבד)
- **Rollback plan:** לא תועד

### C53 — Screen Filter Gateway
- **תאריך:** 18/06/2026 (מוזג)
- **סוג:** Feature
- **Requirement:** ROADMAP.md "Sprint 18/06/2026" → C53
- **Commit:** `5b07088` (תוכן), `96559d2` (docs)
- **PR:** #75
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא — `py_compile`/`smoke_tests.py`/`test_integration.py` עברו לפני merge, אך production לא אומת
- **Verification ראיה:** ראו AI_CONTEXT.md §2 LAST VERIFIED
- **Docs עודכנו:** ROADMAP.md, AI_CONTEXT.md (תוקן 19/06/2026 — היה מתועד כ-"לא ממוזג", drift תוקן)
- **Feature Flag:** N/A (additive, default behavior נשמר)
- **Rollback plan:** לא תועד

### O4 — Finance Pulse: English schema + Screen Filter Gateway wiring
- **תאריך:** 18/06/2026 (מוזג)
- **סוג:** Feature / Schema Change
- **Requirement:** לא ידוע — אין רשומת ROADMAP מקורית מצוטטת; נוסף ל-ROADMAP.md retroactively ב-19/06/2026
- **Commit:** `f7d7e4f` (migration + wiring), `daab73e` (ExpenseFields.STATUS lowercase fix)
- **PR:** #77
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע
- **Verification ראיה:** "Verified against the live Airtable base via MCP" (commit message `f7d7e4f`) — סכמה אומתה, התנהגות בפרודקשן לא
- **Docs עודכנו:** CHANGELOG.md (בזמן ה-PR); ROADMAP.md/AI_CONTEXT.md — retroactively, 19/06/2026 (drift)
- **Feature Flag:** N/A
- **Rollback plan:** לא תועד

### C53-A — Structured tool results + verify_execution dict contract
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Feature / Hardening
- **Requirement:** ROADMAP.md "Sprint 19/06/2026" → C53-A; קשור ל-audit item "C53 approval/action truth"
- **Commit:** `ffa3afc`, `3a34529`
- **PR:** #79
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `py_compile` exit 0 (6 קבצים), `smoke_tests.py` 6/6 PASS, `test_integration.py` 4/4 PASS — כל הריצות מקומיות, לא בפרודקשן
- **Docs עודכנו:** ROADMAP.md, AI_CONTEXT.md, CHANGE_CONTROL_LOG.md (זה) — 19/06/2026
- **Feature Flag:** N/A (משנה contract פנימי של tool results; אין flag — כל tools שהשתנו פעילים תמיד)
- **Rollback plan:** לא תועד — revert PR #79 מ-`main` אם מתגלה רגרסיה בפרודקשן

### A32 / C53-A Hotfix — identity-based NO-TOOL-EVIDENCE enforcement + app.py crash fix
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Bug Fix (P0 — production regression) + Hardening
- **Requirement:** התגלה ב-audit ממוקד על "C53 approval/action truth" (מבוקש על ידי הבעלים, 19/06/2026)
- **תיאור הבאג:** PR #79 שינה 5 tools (`airtable_add`/`airtable_update`/`gmail_draft`/`gmail_send_draft`/`calendar_create_event`) להחזיר `dict` structured במקום `str`, אבל **לא נגע ב-`app.py`** (לפי commit message `3a34529` — "Complete the C53-A contract on tools missing from cherry-pick" מצטט רק `google_tools.py`/`airtable_tools.py`/`rate_limiter.py`). שני מקומות ב-`app.py` עדיין הניחו `str`:
  1. Main tool loop — `result[:80]` על dict → `KeyError: slice(...)` בכל קריאה ישירה (לא דרך approval) ל-4 מתוך 5 הכלים. נתפס ע"י ה-`except Exception` הגלובלי ב-`run_agent()` → המשתמש מקבל "משהו השתבש" גנרי, אבל אין כתיבה מאומתת ל-Airtable/Calendar/Gmail בפועל בתגובה למודל.
  2. Approval callback (`_handle_approval_callback`) — לא קרא ל-`verify_execution()` בכלל; דיווח "✅ הפעולה בוצעה" למשתמש ללא תלות ב-`result["ok"]` — בדיוק כשל "approval truth" שה-audit חיפש.
- **תיקון:** נוסף helper `_tool_user_message()` ב-`app.py`; שני המקומות עכשיו קוראים ל-`verify_execution()`/מחלצים `user_message` לפני logging/slicing/שליחה למשתמש. אם `ok=False` — מדווח כשל בפועל, לא הצלחה כוזבת. בנוסף, חוּזק A32's NO-TOOL-EVIDENCE gate (`core/anti_hallucination.py`): קודם התאמת evidence הייתה מבוססת ניחוש keywords בטקסט התגובה (פספסה קטגוריית Airtable כליל וניסוח "טיוטה נשמרה" ב-Gmail); עכשיו evidence נבדק לפי tool identity (`tool_results_log` נושא שם tool אמיתי + סטטוס `ok` מ-`app.py`) מול סט כלים נדרשים מפורש per-claim-category. כלי שנכשל בעצמו לא נחשב evidence. `_SAFE_FALLBACK` הוחלף ב-`_NO_TOOL_EVIDENCE_FALLBACK` ספציפי יותר. נוסף `test_a32_enforcement.py` שמריץ את `app.run_agent()` קצה-לקצה (Identity/Router/Context/Anthropic מדומים).
- **Commit:** `42dd137` (תוכן), `b34c59f` (docs drift fix)
- **PR:** #80 — **ממוזג ל-`main`** (merge commit `7496628`)
- **Review על ידי:** לא ידוע
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית
- **Verified בפרודקשן:** לא ידוע — נבדק מקומית בלבד
- **Verification ראיה:** שכפול מדויק של ה-crash (`KeyError: slice(None, 80, None)`) על dict לפני התיקון; `py_compile` exit 0; `core/anti_hallucination.py` self-tests 31/31; `test_c53a.py` 50/50; `test_integration.py` 4/4; `smoke_tests.py` 6/6; `test_a32_enforcement.py` 6/6 — כל הריצות מקומיות
- **Docs עודכנו:** AI_CONTEXT.md (PR #81, `56f3ce9`), CHANGE_CONTROL_LOG.md (זה), ROADMAP.md — 19/06/2026, retroactively (drift תוקן)
- **Feature Flag:** N/A
- **Rollback plan:** revert PR #80 מ-`main` אם מתגלה רגרסיה בפרודקשן (שינוי מבודד ב-`app.py`/`core/anti_hallucination.py`)

### Calendar schema restoration + A32 negative-claim gate
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Bug Fix (P0 — production regression) + Hardening
- **Requirement:** התגלה מתוך transcript פרודקשן (הבעלים) שהראה את הסוכן "ממציא" בדיקת קלנדר ודרישת אימייל לא קיימת
- **תיאור הבאג:** commit `9384f89` (14/06/2026, "permission/schema hardening") הסיר 5 schemas מ-`tools/schemas.py` — בהן `calendar_create_event` — מכיוון ש-`GOOGLE_REFRESH_TOKEN` לא היה מוגדר בזמנו. ה-OAuth כבר חי בפרודקשן (אומת מלוגים אמיתיים — `gmail_draft` הצליח), אבל ה-schema לא הוחזר. תוצאה: הסוכן לא יכול היה לקרוא ל-`calendar_create_event` בכלל (לא משנה role/registry/dispatcher), ופיצה על זה ב"המצאת" צ'קים/דרישות לא קיימות (כמו "אני צריך את האימייל שלך" — לפונקציה אין בכלל פרמטר email). בנוסף, A32 (`core/anti_hallucination.py`) הגן רק על הצלחות מומצאות, לא כשלים מומצאים — הסוכן יכל לדווח "הפגישה לא נשמרה" בלי שום קריאת tool בפועל.
- **תיקון:** (1) הוחזרו 5 schemas ל-`tools/schemas.py` (`search_drive`, `read_drive_file`, `calendar_create_event`, `gmail_send_draft`, `gmail_read`). (2) הורחב `_NO_TOOL_CLAIMS` הקיים ב-A32 לתפוס ניסוח עתיד-קרוב ("יוצר את הפגישה"/"קובע את האירוע") וגם וריאנט "קלנדר" (לא רק "ביומן"). (3) נוסף gate סימטרי חדש — `_NEGATIVE_NO_TOOL_CLAIMS` + `_has_negative_evidence()` — שתופס דיווחי כשל מומצאים. שונה מ-gate ההצלחה: `ok=False` *כן* נחשב evidence תקין (קריאה אמיתית שנכשלה מצדיקה דיווח כשל), בניגוד ל-gate ההצלחה שדורש `ok=True`.
- **Commit:** `aa06c4c`, `4712416`, `ab7c1b4`, `870d874`
- **PR:** #82 — **ממוזג ל-`main`**
- **Review על ידי:** הבעלים (אישור מפורש "yes" להחזרת schemas, ואישור מפורש לבניית negative-claim gate)
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render
- **Verified בפרודקשן:** לא — נבדק מקומית בלבד; ראו PR #83 למטה לאימות חלקי בפרודקשן (calendar+gmail_read אומתו דרך לוגים אחרי deploy)
- **Verification ראיה:** `py_compile` exit 0; `smoke_tests.py` PASS; `test_integration.py` 4/4; `core/router/test_router.py` 29/29; `test_a32_enforcement.py` 6/6; `test_c53a.py` 50/50; טסט inline ייעודי אימת שכשל אמיתי (`ok=False`) ממשיך לעבור דרך ה-gate החדש בלי לדרוס אותו ב-fallback
- **Docs עודכנו:** CHANGE_CONTROL_LOG.md (זה), ROADMAP.md — 19/06/2026
- **Feature Flag:** N/A
- **Rollback plan:** revert PR #82 מ-`main` אם מתגלה רגרסיה — שינוי מבודד ב-`tools/schemas.py`/`core/anti_hallucination.py`

### Drive error reporting fix + daily_digest Payments English-schema fix
- **תאריך:** 19/06/2026 (מוזג)
- **סוג:** Bug Fix
- **Requirement:** התגלה מבדיקת פרודקשן ידנית של הבעלים אחרי deploy של PR #82 (לוגים: calendar ✅, gmail_read ✅, drive ❌)
- **תיאור הבאג (1 — Drive):** `drive_search()`/`drive_read_file()` ב-`tools/google_tools.py` קראו ל-`r.json().get("files", [])` בלי לבדוק `r.status_code`. לוג פרודקשן הציג `403 Forbidden` מ-Drive API, אבל הקוד דיווח "לא נמצא כלום בדרייב" — כישלון הרשאות דיווח כ"לא קיים". הסיבה הסבירה ביותר ל-403: ל-`GOOGLE_REFRESH_TOKEN` אין Drive scope (תיקון credential, לא קוד — מחוץ לטווח PR זה).
- **תיאור הבאג (2 — Daily Digest):** `daily_digest.py`'s `_upcoming_payments()` חיפש טבלה `"תשלומים (Payments)"` עם שדות עבריים (`סכום`/`תאריך`/`סטטוס`/`אסמכתא`, ערך `'התקבל'`). אומת מול ה-Airtable **החי** (base `app4bcgoX7t0HUVnm`, table `tbl027IEVotG1cy46`) שהטבלה/השדות כבר `Payments`/`reference`/`amount`/`date`/`status` (ערך `'received'`) — `airtable_schema.py`'s `PaymentFields`/`PaymentStatus` כבר תיקנו את זה, אבל `daily_digest.py` מעולם לא עבר לקבועים החדשים. תוצאה: סקציית התשלומים בדוח הבוקר החזירה אפס רשומות תמיד.
- **תיקון:** (1) שלושת קריאות ה-Drive API ב-`google_tools.py` בודקות `status_code` ומחזירות שגיאה מפורשת. (2) `daily_digest.py` עבר לייבא ולהשתמש ב-`Tables.PAYMENTS`/`PaymentFields`/`PaymentStatus` מ-`airtable_schema.py` במקום literals עבריים.
- **Commit:** `86087e6` (Drive), `acf676f` (Daily Digest)
- **PR:** #83 — **ממוזג ל-`main`** (merge commit `7df22c3`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render
- **Verified בפרודקשן:** לא — נבדק מקומית בלבד
- **Verification ראיה:** `py_compile` exit 0; `smoke_tests.py` PASS; `test_integration.py` 4/4; `core/router/test_router.py` 29/29; שדות/ערכים אומתו ישירות מול live schema דרך Airtable MCP (`get_table_schema`)
- **Docs עודכנו:** CHANGE_CONTROL_LOG.md (זה), ROADMAP.md — 19/06/2026; PR #83 comment תיעד 8 קבצים נוספים עם drift דומה (`tma_api.py`, `tools/airtable_tools.py`, `schema_intelligence.py` ועוד) — **לא תוקנו**, מחוץ לטווח הסשן
- **Feature Flag:** N/A
- **Rollback plan:** revert PR #83 מ-`main` אם מתגלה רגרסיה — שינוי מבודד ב-`tools/google_tools.py`/`daily_digest.py`

### F16 Media Layer — Batch א/ב/ג (STT provider fix, Drive upload contract, Airtable metadata gateway)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Feature (new, flag-gated — קוד לא מחובר ל-pipeline החי עדיין)
- **Requirement:** F16_MEDIA_LAYER_SPEC.md (ספק חיצוני), batches א/ב/ג, מבוקש ע"י הבעלים בסדר קפדני
- **תיאור הבאג:** הספק המקורי כינה את הפיצ'ר "F12" ואז "F09" — שניהם תפוסים ב-ROADMAP.md (F12=Model Provider Adapter, F09=Lead Qualifier Wire-up). תוקן ל-F16. בנוסף, `voice_stt_adapter.py`'s self-test ו-`drive_adapter.py`'s self-test שניהם השתמשו ב-`unittest.mock.patch("module_name.fn", ...)` כדי למנוע קריאות רשת אמיתיות בזמן `python3 module_name.py` — דפוס שנכשל בשתיקה: הרצה ישירה של סקריפט יוצרת `__main__` כ-namespace הרץ, אבל `patch("module_name.fn")` מבצע `import module_name` טרי שיוצר עותק מודול שני, נפרד, ב-`sys.modules` — ה-patch פוגע בעותק הלא-רץ. תוצאה: `voice_stt_adapter.py` ביצע קריאת רשת אמיתית ל-`api.openai.com` (נחסם ע"י sandbox allowlist), ו-`drive_adapter.py` החזיר תוצאות שגויות/None כי לא היה OAuth מוגדר בסביבת הבדיקה.
- **תיקון:** Batch א — `voice_stt_adapter.py` נכתב מחדש: OpenAI Whisper כ-PRIMARY חי (`OPENAI_API_KEY` קיים), Groq כ-stub מוער לא מחובר; קודי שגיאה `OVERSIZED`/`STT_FAILED` (הוסר `EMPTY_AUDIO` — לא בספק). Batch ב — `drive_adapter.py` נכתב מחדש: `upload_file(file_bytes, filename, mime_type, parent_folder_id)` עם `parent_folder_id` חובה (אין default), ניקוי temp file תמיד ב-`finally`, `_safe_filename` מנקה רק תווים אסורים ל-Drive (עברית native). Batch ג — `media_gateway.py` נמצא תואם 100% לספק כבר מהבנייה המקורית, אפס שינוי קוד. שני באגי ה-self-test תוקנו ע"י החלפת `patch("module.fn")` ב-`patch.object(sys.modules[__name__], "fn")` בשני הקבצים. `test_media_layer.py` עודכן בשני סבבים נפרדים (לפי הוראה מפורשת לאחר כל batch) להתאים לקונטרקט החדש — 33/33 עוברים.
- **Commit:** `9485431` (Batch א + test round 1), `33a560c`/`d073b1f` (Batch ב + test round 2), Batch ג (media_gateway.py ללא שינוי קוד, נכלל ב-PR #97)
- **PR:** #96 (Batch א), #97 (Batch ב+ג) — **שניהם ממוזגים ל-`main`** (merge commit `8f9c648`)
- **Review על ידי:** הבעלים (אישר כל batch בנפרד, כולל שני amend+force-push מפורשים ל-`test_media_layer.py`)
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render (קוד לא מחובר ל-pipeline החי — אין סיכון production מעצם המיזוג)
- **Verified בפרודקשן:** N/A — אין feature flag פעיל, הקוד לא נקרא מאף מקום חי עדיין (Batch ד-ז עדיין לא בנו את ה-hooks)
- **Verification ראיה:** מוזג אומת בפועל דרך `git fetch origin main` + grep על תוכן הקבצים שמוזגו ב-`origin/main` (`OVERSIZED`/`STT_FAILED` ב-`voice_stt_adapter.py`, `parent_folder_id` בחתימת `upload_file`/`_upload_to_drive` ב-`drive_adapter.py`) — לא הסתמכות על git log/PR status בלבד, לפי AGENTS.md POST-MERGE VERIFICATION. self-tests עברו (34/34 → 33/33 לאחר הסרת assertion אחת, צפוי).
- **Docs עודכנו:** ROADMAP.md (נוסף F16, עודכן header), CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` — עדיין לא קיימים ב-`feature_flags.py`; יתווספו ב-Batch ה כשה-hooks ל-`app.py` נבנים
- **Rollback plan:** revert PR #96/#97 מ-`main` אם נדרש — שינוי מבודד בשלושה קבצים עצמאיים (`voice_stt_adapter.py`, `drive_adapter.py`, `media_gateway.py` ללא שינוי), אפס import מקוד פעיל אחר

### F16 Media Layer — Batch ד (`media_handler.py` bug fix)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Bug fix (קוד היה כבר קיים ב-`main` מ-commit `ee4d2ed` קודם, לא נכתב מאפס)
- **Requirement:** F16_MEDIA_LAYER_SPEC.md סעיף 4, מבוקש ע"י הבעלים. בתחילת המימוש התגלה ש-`media_handler.py` **כבר קיים** ב-`main` (מ-`ee4d2ed`, לפני מאמץ הבאצ'ים), עם שמות פונקציות שונים מהספק (`handle_voice_note()`/`handle_file_upload()`/`handle_tma_upload()` במקום `handle_telegram_media()`) וכבר מחובר ל-`app.py`/`tma_api.py`. הוצג למשתמש כקונפליקט (`AskUserQuestion`) — הוכרע: לשמור שמות קיימים, לתקן internals בלבד, לא לגעת ב-`app.py`/`tma_api.py`.
- **תיאור הבאג:** (1) `upload_file()` נקרא עם `domain=domain` — kwarg שלא קיים בחתימה האמיתית של `drive_adapter.upload_file(file_bytes, filename, mime_type, parent_folder_id)` (תוקנה ב-Batch ב) — `TypeError` מובטח בכל הפעלה אמיתית, לא התגלה ע"י `test_media_layer.py` הקיים כי 33 ה-assertions שלו בודקים רק short-circuits (oversized/duplicate), לא את ה-success path. (2) כשל כתיבה ל-Airtable לאחר Drive upload מוצלח הוחזר כ-`MediaResult(ok=True, asset_id="")` בשקט — ללא דרך לצרכן לזהות כשל.
- **תיקון:** נוסף `_resolve_drive_folder(domain)` המשתמש ב-`drive_adapter._get_upload_folder(domain)` לפני קריאה ל-`upload_file()`. נוסף בדיקת `if not asset_id` עם קוד שגיאה `ASSET_SAVE_FAILED`; כשל resolve מחזיר `DRIVE_FAILED`. הודעות שגיאה תורגמו לעברית. נוספו 4 self-test scenarios חדשים (`media_handler.py`'s `__main__`) שמכסים את ה-success path שחשף את הבאג. שמות פונקציות/`_idem_store`/קודי שגיאה קיימים (`FILE_TOO_LARGE`/`DUPLICATE`) לא שונו — `test_media_layer.py` תלוי בהם במדויק.
- **Commit:** `0fcf81b`
- **PR:** #98 — **מוזג ל-`main`** (merge commit `8dd3bca`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render (flag כבוי — אין סיכון production)
- **Verified בפרודקשן:** N/A — `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` כבויים
- **Verification ראיה:** `git fetch origin main` + grep על `_get_upload_folder`/`DRIVE_FAILED`/`ASSET_SAVE_FAILED` ב-`origin/main:media_handler.py` — תואם. `test_media_layer.py` 33/33 עוברים גם לפני וגם אחרי התיקון.
- **Docs עודכנו:** ROADMAP.md, CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` — כבויים כברירת מחדל (לא השתנה)
- **Rollback plan:** revert PR #98 מ-`main` — שינוי מבודד ל-`media_handler.py` בלבד

### F16 Media Layer — Batches ה/ו/ז (app.py hooks, tma_api.py endpoint, airtable_schema.py — gap-fill)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Feature gap-fill (רוב הקוד כבר היה קיים ומחובר; לא מימוש מאפס)
- **Requirement:** F16_MEDIA_LAYER_SPEC.md, מבוקש ע"י הבעלים לפתוח `claude/f16-final` ולממש שלושה batches.
- **תיאור הממצא:** לפני מימוש, אומת ש-Batch ה (`_handle_telegram_media()` ב-`app.py`) ו-Batch ו (`/api/tma/upload` ב-`tma_api.py`) **כבר מחוברים** ל-pipeline החי מאז `ee4d2ed` — לא רק קוד עומד, אלא בפועל נקראים מה-webhook/route. Batch ז (`Tables.MEDIA_FILES`/`MediaFileFields` ב-`airtable_schema.py`) כבר קיים ומלא, מכסה את כל השדות ש-`media_gateway.py` כותב. נמצאו 2 gaps אמיתיים בלבד.
- **תיקון:** `app.py` — נוסף `bot.send_chat_action()` (typing/upload_document) לפני עיבוד voice/photo/document ב-`_handle_telegram_media()`. `tma_api.py`/`media_handler.py` — נוסף קליטת `linked_lead_id` מה-multipart form ב-`/api/tma/upload`, מועבר ל-`handle_tma_upload()` → `handle_file_upload()`. `domain` נשאר נגזר מה-identity המאומת בכוונה (לא משדה form של הלקוח) — מנע tenant scope הנקבע ע"י הלקוח. `airtable_schema.py` — אפס שינוי (כבר שלם).
- **Commit:** `32c6629`
- **PR:** #99 — **מוזג ל-`main`** (merge commit `4924030`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** לא ידוע — דרוש בדיקה ידנית מול Render (flag כבוי — אין סיכון production)
- **Verified בפרודקשן:** N/A — `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` כבויים
- **Verification ראיה:** `git fetch origin main` + grep על `send_chat_action.*upload_document`, `linked_lead_id` ב-`origin/main:app.py`/`tma_api.py`/`media_handler.py` — תואם. `test_media_layer.py` 33/33, `media_handler.py` self-test 4/4, `smoke_tests.py` עובר.
- **Docs עודכנו:** ROADMAP.md, CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` — כבויים כברירת מחדל (לא השתנה). **F16 Media Layer הושלם במלואו (כל 7 batches) — כבוי בפרודקשן עד הדלקה מפורשת + יצירת טבלת "Media Files" ב-Airtable.**
- **Rollback plan:** revert PR #99 מ-`main` — שינוי מבודד בשלושה קבצים, 17 שורות בלבד

### F16 Media Layer — Docs correction (ROADMAP/AI_CONTEXT/CHANGELOG/CHANGE_CONTROL_LOG)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** Docs-only correction, אפס שינוי קוד
- **Requirement:** בקשת הבעלים — אחרי שאומת ש-PR #99 כבר מוזג ל-`main` (`pull_request_read`, merged_by=10026782, לא ע"י Claude), עדכון `ROADMAP.md`/`AI_CONTEXT.md` לשקף ש-F16 הושלם במלואו, כולל commit hash + תאריך, ב-PR נפרד קטן.
- **תיאור:** `ROADMAP.md` — header (שורה 3) + סעיף F16 (שורות 412-424) עודכנו לשקף סטטוס אמיתי per-batch (לא "תכנון", אלא "✅ מוזג"/"✅ קיים מהבנייה המקורית" לפי המקרה), כולל תיקון הטענה השגויה על feature flags (הם קיימים ב-`feature_flags.py`, כבויים כברירת מחדל — אומת ב-grep). `AI_CONTEXT.md` — header, Executive Summary, סעיף "חלקי", שתי רשומות חדשות ב-"Completed Since Last Update" (PR #98/#99), "Next Priorities" item 0. `CHANGELOG.md` — תוקן ה-Unreleased entry הקיים. `CHANGE_CONTROL_LOG.md` — שתי רשומות חדשות נוספו (append-only, היסטוריה לא נערכה).
- **Commit:** `1ad9919`
- **PR:** #100 — **מוזג ל-`main`** (merge commit `de5765b`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** N/A — docs-only, אין קוד רץ
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** `git fetch origin main` + grep אחרי כל הטענות המתוקנות ב-4 הקבצים על `origin/main` — אומת שאין יותר טענות "לא מומש"/"עדיין לא בנוי" שמתייחסות ל-F16/Batch ד/ה/ו/ז. `git diff --stat` אומת diff מוגבל ל-4 קבצי docs בלבד (61 insertions/18 deletions).
- **Docs עודכנו:** זה עצמו הוא ה-docs update
- **Feature Flag:** ללא שינוי
- **Rollback plan:** revert PR #100 — docs-only, אפס סיכון

### N07 — Schema Governance script (`tools/schema_governance.py`)
- **תאריך:** 22/06/2026 (מוזג)
- **סוג:** New feature, קובץ יחיד חדש (קוד שלם מאפס)
- **Requirement:** ROADMAP.md N07 (עדיפות גבוהה), מבוקש ע"י הבעלים. מניע: BUG-008 (`Leads."Business Outcome"` trailing space שהתגלה ad-hoc).
- **תיאור:** `tools/schema_governance.py` — סקריפט standalone, READ ONLY לחלוטין. שולף live schema מ-Airtable Metadata API (`GET /meta/bases/{baseId}/tables`, httpx, Bearer auth מ-env). משווה מול `airtable_schema.py` (import, לא parse) דרך `TABLE_CLASS_MAP`/`_class_values` **קיימים** מ-`schema_audit.py` (יובאו, לא שוכפלו — נמנע מיפוי כפול שיכול לסחוף). מזהה 5 סוגי drift: שדה בקוד חסר ב-live (whitespace-tolerant match, נמנע double-report) → ERROR; שדה ב-live שלא בקוד → WARNING; trailing/leading spaces בשם שדה → WARNING; trailing/leading spaces ב-`singleSelect`/`multipleSelects` choice names → WARNING; שינוי סוג שדה → ERROR (מול ריצה קודמת שנשמרה ב-`schema_drift_report.json` בעצמו — baseline זמני, כי `airtable_schema.py` לא מכיל מטא-דאטה של סוגים בכלל). מדפיס דוח עברית ל-console, שומר `schema_drift_report.json` (נוסף ל-`.gitignore` — לא מתווסף ל-git), exit 1 אם יש ERROR ≥1 אחרת 0. self-test (`--self-test`) עם mock schema, אפס קריאות רשת. אינו נוגע ב-`schema_cache.json` (בבעלות `schema_validator.py`).
- **החלטות תכנון שתועדו במפורש (לא הוסתרו):** (1) baseline זמני לבדיקת סוג שדה (לא קוד) — כי אין מטא-דאטה של סוג ב-`airtable_schema.py`. (2) הוצא מהיקף: "select options חסרות/כפולות" — הופיע רק בטיוטה לא-פורמלית, לא ברשימה הממוספרת הסופית. (3) נמצא ניגוד בין הדוגמה החזותית בספק (`Assets."Purchase Cost"` כ-WARNING) לכלל הסיווג המספרי המפורש (שדה חסר מ-live=ERROR) — הוכרע ללכת לפי הכלל המספרי כסמכותי, הדוגמה החזותית רק עיצובית.
- **Commit:** `cbe9363`
- **PR:** #101 — **מוזג ל-`main`** (merge commit `e465eff`)
- **Review על ידי:** הבעלים
- **Deploy תאריך:** N/A — כלי CLI עצמאי, לא חלק מה-pipeline החי, אין deploy
- **Verified בפרודקשן:** N/A — לא נקרא מאף קוד pipeline; טרם הורץ פעם ראשונה מול live Airtable אמיתי (אין credentials בסביבת ה-sandbox)
- **Verification ראיה:** `git fetch origin main` + grep על תוכן `tools/schema_governance.py` ו-`.gitignore` ב-`origin/main` ישירות — תואם. `python3 -m py_compile` עבר. `--self-test`: 6/6 assertions עברו. `smoke_tests.py` עבר במלואו.
- **Docs עודכנו:** ROADMAP.md (N07 → ✅ הושלם), CHANGELOG.md, CHANGE_CONTROL_LOG.md (זה), AI_CONTEXT.md — 22/06/2026
- **Feature Flag:** ללא — כלי CLI עצמאי, לא flag-gated
- **Rollback plan:** revert PR #101 — קובץ יחיד חדש + שורה אחת ב-`.gitignore`, אפס import מקוד פעיל אחר, אפס סיכון

### C56 — Approval Policy: Emergency Window + OTP + Policy Gate (docs correction)
- **תאריך:** 23/06/2026 (תיקון תיעוד; הקוד עצמו מוזג כבר ב-17/06/2026)
- **סוג:** Docs correction
- **Requirement:** לא היה ב-ROADMAP.md בכלל לפני תיקון זה; `BUG_AUDIT_LOG.md` תיעד "Merged: לא" בזמן שהקוד היה כבר מוזג. התגלה בעת בדיקת ענפי `claude/*` לא ממוזגים לקראת ניקוי — `claude/meta-whatsapp-phase-1-q6pp3e` (הענף שממנו עלה PR #69) המשיך להצטבר commits **אחרי** שה-PR שלו עצמו מוזג, כולל ניסיון תיקון תיעוד דומה שעצמו לא הגיע ל-`main`.
- **Commit (קוד, לא docs):** `8209d36`, `a57fd7f`, `44457dd`, `92e4b2b` — **merge commit `4e933b0`**
- **PR:** #69 — https://github.com/10026782/My-bot/pull/69
- **Review על ידי:** 10026782 (owner — `mergedBy` ב-GitHub API)
- **Deploy תאריך:** לא ידוע — Render Auto-Deploy מוגדר על `main`, לא אומת ידנית מול Render Dashboard
- **Verified בפרודקשן:** לא
- **Verification ראיה:** `gh pr view 69 --json state,mergedAt,mergedBy,mergeCommit` → `{"state":"MERGED","mergedAt":"2026-06-17T18:56:00Z","mergedBy":"10026782","mergeCommit":"4e933b0536c03e270f7e4547e7c1d6a0a232b09e"}`; `git merge-base --is-ancestor 4e933b0 main` → exit 0 (אב-קדמון בפועל, לא רק PR API). מטריצת 12 התרחישים (Low/Medium/High/Critical × mobile/desktop/web × window/OTP) שאומתה בזמן הבנייה המקורית (17/06/2026) לא הורצה חזרה בתיקון תיעוד זה — אין שינוי קוד.
- **Docs עודכנו:** ROADMAP.md (נוסף C56, לא היה קיים), AI_CONTEXT.md, BUG_AUDIT_LOG.md, RELEASE_CHECKLIST.md
- **Feature Flag:** `EMERGENCY_WINDOW` — כבוי כברירת מחדל; ללא שינוי בתיקון תיעוד זה
- **Rollback plan:** revert — docs-only, אפס סיכון פונקציונלי

### N12 — Daily Git Audit scheduler wiring
- **תאריך:** 23/06/2026
- **סוג:** New feature (flag off) + docs salvage
- **Requirement:** ROADMAP.md N12; חולץ מ-2 ענפים לא ממוזגים לפני מחיקתם במהלך ניקוי ענפי `claude/*`
- **תיאור:** `daily_git_audit.py` חובר ל-`scheduler.py` (`_job_daily_git_audit`, `GIT_AUDIT_TIME` env var, ברירת מחדל `06:45`). נוספו ל-`daily_git_audit.py`: `check_unmerged_vs_roadmap()`, `check_duplicate_schemas()`, `check_recent_commits()`, `check_cors_env_drift()`. תוקן bug ב-precedence שהיה בענף המקורי: בדק `BOSS_CURRENT_STATE.md` לפני `ROADMAP.md` — הפוך מהכרזת `ROADMAP.md` כ"מקור האמת היחיד, כל מסמך תכנון אחר הוא ARCHIVE". `_CANONICAL_DOC_PRIORITY` סודר מחדש: `ROADMAP.md` ראשון.
- **Commit:** `c26c5e1`
- **PR:** #108 — **מוזג ל-`main`**
- **Review על ידי:** הבעלים
- **Deploy תאריך:** N/A — דגל כבוי, אין שינוי התנהגות בפרודקשן
- **Verified בפרודקשן:** N/A — `GIT_AUDIT_SCHEDULER=off`
- **Verification ראיה:** `py_compile` נקי; פונקציות הבדיקה הורצו ידנית מול הריפו והחזירו ממצאים תקינים (כולל גילוי אמיתי של ענף תקוע אחד); `smoke_tests.py` ללא רגרסיה (אותם 2 כשלים תלויי-סביבה כמו על `main`)
- **Docs עודכנו:** ROADMAP.md (N12 חדש), AI_CONTEXT.md, CHANGELOG.md
- **Feature Flag:** `GIT_AUDIT_SCHEDULER` — כבוי כברירת מחדל
- **Rollback plan:** revert PR #108 — דגל כבוי, אפס סיכון פונקציונלי מיידי

### Docs salvage — `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md`
- **תאריך:** 23/06/2026
- **סוג:** Docs-only, commit ישיר ל-`main` (לא PR — אישור משתמש מפורש)
- **Requirement:** נמצא תוך כדי ניקוי ענפי `claude/*` — מסמך audit ארכיטקטוני (257 שורות, ללא קוד) שהתקיים רק בענף `claude/spec-c52-implementation-uqmu1g`, שלא מוזג מעולם
- **תיאור:** מסמך audit מלא של 4 מנגנוני approval + 2 kill switches, risk matrix, gap analysis, ומפרט test harness ל-C53 (test categories A-J). נכתב 17/06/2026 מול הקוד של אותו יום. נוסף הערת provenance בראש המסמך + הערה ב-`CLAUDE.md` (מבדיל מ-`Approval_Policy_Spec.md` החסר — מסמך אחר)
- **Commit:** `783a680`
- **PR:** ללא — commit ישיר ל-`main`
- **Review על ידי:** הבעלים (אישר במפורש "לשמור כקובץ ב-main, לא PR")
- **Deploy תאריך:** N/A — docs-only
- **Verified בפרודקשן:** N/A
- **Verification ראיה:** תוכן הקובץ זהה ל-blob המקורי בענף שנמחק (`git show <branch>:<path>` לפני המחיקה); `git diff --stat` אומת diff מוגבל ל-2 קבצים (`APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` חדש + שורה אחת ב-`CLAUDE.md`)
- **Docs עודכנו:** זה עצמו + `CLAUDE.md`
- **Feature Flag:** אין — docs-only
- **Rollback plan:** revert commit `783a680` — docs-only, אפס סיכון
