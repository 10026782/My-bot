# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026) — **לא** מקור אמת נוכחי;
> main + ROADMAP גוברים עליו בכל סתירה.
> `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עצמם מפגרים אחרי `main` בסבב הזה —
> ראו §3/§4 (PR #380–#387 עדיין לא מתועדים שם; MAIN > DOCS עד שיתוקן).

**עודכן:** 2026-07-18 · **main:** `2136a14` · **סטטוס:** אין ענף פעיל פתוח כרגע (כל PRs עד #387 ממוזגים ומאומתים ב-`main` בפועל — grep, לא רק `git log`)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד. אין שינוי במסלול הזה.
- **BUG-104** (ליבת reasoning ל-Leads): Phase 1/1.1/2A.1/2A.2 קוד ממוזג ומאומת ב-main+tests. `FEATURE_CORE_REASONING_LEADS_STATE` נשאר `off`/`shadow` — **אין effect על תגובות פרודקשן בפועל**. Phase 2A.0 (ניקוי סכמה) — SPEC בלבד, ממתין להחלטת owner. ללא שינוי מהסבב הקודם.
- **F52 (Message Contract Foundation)** — כעת 4 PRs (#381–#385): PR4 (#385) הוסיף shadow-observability + בדיקות ל-`ActionGateway.compose_status_reply()` (הנתיב הראשון האמיתי ל-cutover) — לוג ה-shadow עכשיו כולל שדות בטוחים בלבד (outcome/mapped_state/leak-flags בוליאניים/redaction_count), לעולם לא טקסט גולמי/record_id/tool_name. **`FEATURE_UNIFIED_STATUS_FORMATTER` נשאר `off` — אין הפעלת flag, אין שינוי התנהגות בפרודקשן.**
- **BUG-111 — VERIFIED IN MAIN (לא production-verified)**: תוקן פרסור batch של לידים (`core/ingress_classifier.py`/`core/lead_candidate_handler.py`) — מילת דומיין ("דומיין גיוס") כבר לא נכתבת כשם ליד, prefix של שולח WhatsApp כבר לא נחשב לשם, טלפונים עם שני מפרידים (`05X-XXX-XXXX`/`+972 XX-XXX-XXXX`) מזוהים עכשיו, ו-batch של כמה טלפונים-בלי-שם שומר את **כל** המספרים ב-clarification (לא מצמצם לאחד). זהו התיקון האמיתי ל-symptom "יצירת ליד ידנית חסומה" — כי עכשיו candidate/clarification תקין נמצא *לפני* שההודעה מגיעה ל-Agent וננעלת ע"י LeadsWriteGate.
- **BUG-112 — VERIFIED IN MAIN (לא production-verified)**: כפתור אישור טלגרם הכריז "פג תוקף בעוד 10 דקות" אך בפועל בוצע עד 30 דקות (TTL הפנימי של `event_bus.py`'s `PendingActionsStore` שונה מה-TTL המוצג). `app.py`'s `_handle_approval_callback_impl()` אוכף עכשיו את אותו `_PENDING_APPROVAL_TTL` (600s) בנפרד על נתיב ה-callback — callback שפג תוקפו לא מבצע, דוחה contract תואם אם קיים, ומודיע למאשר בהודעה קבועה (לא רק popup).
- **RP5 (Evidence Finalizer enforcement) — חסום**: RP4 קוד-שלם אך `FEATURE_EVIDENCE_FINALIZER=off` בפרודקשן; אין עדיין דגימות shadow אמיתיות. פעולה הבאה תלויה ב-operator (מחוץ ליכולת סשן קוד). ללא שינוי מהסבב הקודם.
- **BUG-110 — VERIFIED**: שני נתיבי כתיבה תוקנו מ-`status="converted"` הלא-קנוני ל-`status=done`+`Business Outcome=converted`. חוב טכני מתועד: `ad_attribution.py::mark_converted()` עדיין לא עובר דרך ה-gateway הקנוני. ללא שינוי מהסבב הקודם.
- **פער תיעוד גדל**: `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עדיין לא מכילים רשומות עבור PR #380–#387 (F52 PR4 + BUG-111 + BUG-112 נוספו הסבב הזה, מעל הפער הקודם). `main` הוא המקור המאומת; ארבעת המסמכים דורשים סנכרון.
- פריטים ללא שינוי/לא נבדקו בסבב הזה: PR #341 (Single-Speaker fix, לא production-verified), C81-FU/C82-FU, רשומת Airtable `recRvK6hFTNgyj8ag`.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram+WhatsApp inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow (כולל אכיפת TTL על כפתור טלגרם, BUG-112); Daily Digest; Finance Pulse; TMA read path; Cost Watchdog; חילוץ-ליד מ-WhatsApp (כולל תיקוני batch/domain/sender-prefix, BUG-111); RP1 tool-registry invariants (תמיד פעיל); TMA Lead Event Bridge; `lead_conversion.py`/`ad_attribution.py::mark_converted()` כותבים ערכים קנוניים (BUG-110).

**מיושם וממוזג ב-main, טרם אומת מול תעבורה חיה בפרודקשן (Render):**
- BUG-111 — תיקון פרסור לידים (`core/ingress_classifier.py`, `core/lead_candidate_handler.py`) — קוד תמיד-פעיל (לא flag-gated), עבר grep על `main`, כל ה-tests ירוקים; אין אימות מול production traffic אמיתי עדיין.
- BUG-112 — אכיפת TTL על callback אישור טלגרם (`app.py`) — קוד תמיד-פעיל (לא flag-gated), עבר grep על `main`, כל ה-tests ירוקים; אין אימות מול production traffic אמיתי עדיין.

**מיושם חלקית / קוד מוכן אך flag כבוי:**
- BUG-104 Core Reasoning (Phase 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests בלבד, לא runtime-verified מול תעבורה חיה. `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow.
- F52 Message Contract Foundation + reconciliation + display_payload mapping + PR4 shadow-observability (PR #381–#385) — קוד מוכן, אין שום צריכה חיה (`app.py`/dispatcher/scheduler לא מייבאים את `agent_message_formatter` ישירות; `ActionGateway.compose_status_reply()` מדלג רק מאחורי הדגל); `FEATURE_UNIFIED_STATUS_FORMATTER` off. הפעולה המומלצת הבאה: operator מפעיל `shadow` (לא `on`) ב-Render — ראו `docs/architecture/f52-unified-approval-runtime/PR4_ACTION_STATUS_SHADOW_VERIFICATION.md`.
- RP2/RP3 Tool Availability Filter — off. RP4 Evidence Finalizer — off, גם "enforce" הוא comparison-only.
- PA-01 structural enforcement — off, ממתין להחלטת shadow rollout.
- Phase 4B Atomic Claims — off, ללא שינוי.
- BUG-104 Phase 2A.0 — SPEC בלבד; ניקוי שדות `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` טרם בוצע.

**חסום:**
- RP5 enforcement — ממתין לדגימות shadow אמיתיות; operator בתהליך הפעלת `FEATURE_EVIDENCE_FINALIZER=shadow` ב-Render (מחוץ לסבב קוד).
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- BUG-110 חוב טכני: `ad_attribution.py::mark_converted()` לא עובר דרך canonical gateway; `build_attribution_report()`/`audience_intelligence.py` עדיין קוראים `status=="converted"` הישן — יחסירו לידים שהומרו לאחר התיקון.
- PR #341, C81-FU/C82-FU, רשומת `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו.

---

## 3. Completed Since Last Update (18/07, אותו יום — 3 PRs חדשים מעל c1b00c0)

1. **PR #385 — F52 PR4: Action Status Live Surface Shadow Verification** (`1432eba`) — הנתיב האמיתי הראשון ל-formatter cutover: `ActionGateway.compose_status_reply()`'s `shadow` mode עכשיו לוגג רק שדות בטוחים (`outcome`/`mapped_state`/`text_differs`/leak-flags בוליאניים/`redaction_count`/`fallback_used`/`formatter_version`/אורכי טקסט) — **לעולם לא** טקסט legacy/unified גולמי, לא record_id, לא tool_name. תוספת בדיקות ל-approval_pending (ממופה נכון, לעולם לא success, לא חושף tool_name/record_id/contract_id) ול-executed/failed/rejected/unknown state-mapping. `off` נשאר identical-to-byte; אין הפעלת flag; אין שינוי ל-RP5/ActionGateway execution/approval policy.
2. **PR #386 — BUG-111: lead batch parsing (domain context + sender-prefix)** (`6bb3b61`, `7b2cd5c`, `c3499f5`) — הנתיב החי `core/ingress_classifier.py::_extract_lead_candidates()` (לא ה-dead-code cluster ב-`lead_candidate_handler.py`, ראו BUG-096) תוקן: (א) `_PHONE_RE` מזהה עכשיו טלפונים עם שני מפרידים (`05X-XXX-XXXX` מקומי / `+972 XX-XXX-XXXX` בינלאומי — סגר גם gap ידוע מ-BUG-101); (ב) timestamp WhatsApp בפורמט "`[D.M, HH:MM]`" (בלי שנה) מזוהה עכשיו כ-block boundary/sender prefix, כך ש-`_SENDER_LINE_RE` לא נכשל וה-sender לא נכתב כשם ליד; (ג) `_extract_domain_hint()`/`_strip_domain_hint()` חדשים — "דומיין X"/"לדומיין X" (למשל "דומיין גיוס") מוסר מחלון-חילוץ-השם *לפני* שם, ונשמר בנפרד כ-`candidate["domain_hint"]` (ממופה ל-`recruitment` וכו') ולא הולך לאיבוד; `_detect_domain()` ב-`lead_candidate_handler.py` בודק את ה-hint המפורש הזה קודם. (ד) `_maybe_start_lead_clarification()` עכשיו מזהה **את כל** הטלפונים בהודעה (`.finditer()`, לא `.search()`) — batch של 2+ טלפונים-בלי-שם שומר clarification חדש (`expected_field="names"`, `partial_payload["phones"]`) ולעולם לא מצמצם ל-1 בשקט; `_resolve_batch_name_clarification()` חדש פותר אותו (שם אחד לשורה, לפי סדר) ומזין ל-`resolve_pending_lead_preview()` הקיים (BUG-058) — הרינדור של resolve_pending_lead_preview עצמו (record_id inline, "עובדתי N לידים") **לא** תוקן כאן, נשאר חוב UX נפרד. תיקון סופי לתסמין המדווח: "יצירת ליד ידנית חסומה" ל-`+972 53-396-8395` — השורש היה gap ב-`_PHONE_RE` שגרם להודעה ליפול עד ל-Agent tool_use loop ולהיחסם ע"י LeadsWriteGate; עכשיו candidate/clarification תקין נמצא לפני שזה קורה. 87 בדיקות חדשות (2 קבצים), sweep מלא של `test_*.py` ירוק, `compileall`/`diff --check` נקיים.
3. **PR #387 — BUG-112: Telegram approval button TTL enforcement** (`f639c33`) — כפתור אישור טלגרם הכריז "פג תוקף בעוד 10 דקות" (`_PENDING_APPROVAL_TTL=600`), אך `_handle_approval_callback_impl()` הסתמך רק על `event_bus.bus.pop()`, שאוכף TTL **שונה ופנימי** של `PendingActionsStore` (`PENDING_TTL_MINUTES=30`) — לחיצה בין דקה 10 ל-30 עדיין ביצעה. תיקון: בדיקה עצמאית של `_PENDING_APPROVAL_TTL` מיד אחרי ה-pop, לכל callback "approve" (tool/non-tool כאחד), *לפני* כל החלטת dispatch. callback שפג תוקפו: לא מבצע; דוחה contract Gateway תואם אם קיים ואומת (לא מונח בעיוורון); מודיע למאשר בהודעת chat קבועה ("⏰ פג תוקף — הפעולה לא בוצעה") ולא רק ב-popup; עורך את הודעת האישור המקורית כך שלא תיראה פעילה; לא נופל ל-legacy dispatch. 22 בדיקות חדשות כולל regression guard מפורש שה-TTL של free-text "מאשר" (הנתיב הישן ב-`run_agent()`) לא השתנה.

**פער תיעוד פתוח, גדל:** PR #380–#387 עדיין לא מתועדים ב-`ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` — סנכרון הממשל טרם בוצע (ראו §4 סעיף 1).

---

## 4. Next Priorities

1. **סנכרון מסמכי ממשל** — להוסיף רשומות ל-`ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עבור PR #380–#387 (F52 PR1–PR4, BUG-111, BUG-112), כדי ש-MAIN ו-DOCS יתאמו שוב. הפער גדל הסבב הזה (3 PRs נוספים מעל #380–#383 הקודמים).
2. **production verification: BUG-111/BUG-112** — שני התיקונים ממוזגים ב-`main`, כל הבדיקות ירוקות, אך **לא** אומתו מול תעבורה חיה בפרודקשן עדיין (Render deploy + תצפית בפועל). קוד תמיד-פעיל, לא flag-gated — verification הבא הוא deploy + מעקב, לא decision.
3. **operator: RP5 preflight** — הפעלת `FEATURE_EVIDENCE_FINALIZER=shadow` ב-Render, ואיסוף דגימה אחת לפחות לכל אחד מ-9 מצבי הסיווג (`RP5_PREFLIGHT_BLOCKER.md` §3) לפני שRP5 עצמו יכול להתחיל.
4. **operator: F52 shadow rollout** — הפעלת `FEATURE_UNIFIED_STATUS_FORMATTER=shadow` (לא `on`) ב-Render עבור נתיב ה-`approval_pending`, ואיסוף דגימות לפי הצ'קליסט ב-`docs/architecture/f52-unified-approval-runtime/PR4_ACTION_STATUS_SHADOW_VERIFICATION.md`.
5. **החלטת owner: הפעלת `FEATURE_CORE_REASONING_LEADS_STATE`** — קוד BUG-104 מוכן ומאומת ב-main; טרם נצפה על תעבורה חיה.
6. **החלטת owner: ניקוי סכמת BUG-104 Phase 2A.0** — `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` מועמדי-מחיקה, טרם טופלו.
7. **חוב טכני BUG-110** — להעביר את `ad_attribution.py::mark_converted()` ל-canonical gateway ולעדכן את `build_attribution_report()`/`audience_intelligence.py` שעדיין בודקים `status=="converted"` הישן.
8. **חוב UX ידוע (BUG-111 PR)** — `resolve_pending_lead_preview()`/`_handle_batch()` ב-`core/lead_candidate_handler.py` עדיין חושפים record_id inline וכותרת "עובדתי N לידים" (ניסוח שגוי) בהודעת אישור batch — לא תוקן ב-BUG-111 (נשאר חוב F52/UX נפרד, יש לתקן במסגרת cutover ל-formatter המאוחד).
