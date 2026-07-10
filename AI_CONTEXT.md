# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד),
> `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`. `CANONICAL_STATE.md` **לא קיים** בריפו (נבדק בסבב הזה).

**עודכן:** 2026-07-10 · **main:** `20cdac7` (PR #291, BUG-094) · **סטטוס:** BUG-094 (batch dedup) ✅ ממוזג ל-main, ⚠️ production verification עדיין לא בוצע

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, בנוי סביב Identity → Router → Context → Agent, Airtable כ-CRM.
- **BUG-094 (10/07, PR #291, `f96b5f1`) — ✅ ממוזג ל-main היום:** ראיה חיה מפרודקשן של BUG-058's resolver (השורה הבאה) חשפה 3 באגים נפרדים ב-batch lead capture — חלון שם דולף בין מועמדים סמוכים, fallback עיוור ל-name-only בלי לוודא phone, ודליפת `RouterDomain.CRM/INTERNAL` (מטא-דומיינים של הראוטר) לשדה `Domain` העסקי → 422. שלושתם תוקנו, `test_bug094_batch_name_bleed.py` (25/25). **טרם אומת בפרודקשן** — נדרשת בדיקה חיה שמראה שני `record_id` שונים לשני לידים בבאצ' קרוב, ללא 422.
- **BUG-058 (10/07, PR #290) — ✅ ממוזג:** Tier-2 batch-confirm resolver נבנה בפועל (`session_store.py`, `lead_candidate_handler.py::resolve_pending_lead_preview`). Precedence: Tier-1 ActionGateway תמיד מנצח Tier-2 כששניהם חיים לאותו chat_id. **טרם אומת בפרודקשן** בזרימה חיה.
- שרשרת `/update`+Business Memory (BUG-078..081, C97-C101, 08/07) נשארת **✅ PRODUCTION VERIFIED במלואה, 6/6 domains** — ללא שינוי בסבב הזה.
- רוב דגלי הפיצ'רים (`FEATURE_AUTO_CAPTURE`, `FEATURE_STRUCTURED_FILE_CAPTURE`, `FEATURE_DECISION_HUB`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`) **כבויים בכוונה** — קוד מוכן/ממוזג, לא מופעל בפרוד.
- שני items בעדיפות 🔴 דחוף עדיין פתוחים ולא טופלו: C81-FU (אימות משלוח ב-Recovery) ו-C82-FU (gate מרכזי ל-EMERGENCY_STOP_AUTOMATION).
- אין harness pytest — בדיקות הן סקריפטים עצמאיים; הורץ מחדש היום בסבב זה: `smoke_tests.py` — 5/7 עוברים, 2 נכשלים על `flask`/`httpx` חסרים (**מגבלת סביבת ה-sandbox, לא רגרסיית קוד** — אותו מצב כמו בעדכון הקודם).
- כלל ברזל: "הושלם" ≠ "מאומת". שום claim כאן לא production-verified אלא אם צוין כך במפורש.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד; Approval flow (ActionGateway + `tool_registry.enforce`); Daily Digest; Finance Pulse; TMA (Leads/Projects/Game/Finance Pulse); Cost Watchdog; C94 Ingress Envelope (דגל ON כברירת מחדל); Deterministic Denial short-circuit (BUG-092, מאומת בפרודקשן).

**מיושם חלקית / ממתין להפעלה או לאימות:**
- C89 Capture Policy — נסגר כ-CLOSED/VERIFIED בהחלטת הבעלים, `FEATURE_AUTO_CAPTURE` נשאר כבוי בכוונה.
- C90 (קבצי xlsx/csv), Lead Scoring/Memory/Followup (N02-N04) — code done, flags off, לא מאומת בתעבורה אמיתית.
- Decision Hub (Stages 0-6, F17-F22) — כל השלבים ממוזגים ל-main; `FEATURE_DECISION_HUB` כבוי, חסום עד production evidence.
- **BUG-094 (batch lead dedup) — ✅ קוד ממוזג ל-main (`f96b5f1`), 25/25 טסטים חדשים + אפס רגרסיה. UNVERIFIED בפרודקשן** — לא נבדק עדיין מול תעבורה חיה אחרי המיזוג.
- **BUG-058 (Tier-2 batch resolver) — ✅ קוד ממוזג ל-main. UNVERIFIED בפרודקשן** — לא נבדק בזרימת "אישור קבוצתי" אמיתית.

**חסום:**
- Decision Hub activation — חסום ל-BUG-DH-03/04 (Formula Injection): התיקון עצמו ממוזג (PR #251), אין עדיין production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין לאישור Meta Cloud API.
- C93 (OCR/כרטיסי ביקור) — חסום על צבירת ≥2 שבועות נתוני `AgentObservation` אמיתיים (לא מתקיימים, C89 לא הופעל).
- N15 — Restricted-flow `notify_owner`: שדה נקבע אך לעולם לא נצרך, אין מנגנון התראה אמיתי לבעלים. פתוח, PLANNED, לא התחיל.

---

## 3. Completed Since Last Update
*(מאז הרענון הקודם של מסמך זה, 08/07/2026)*

1. **BUG-058 (10/07/2026, PR #290)** — Tier-2 batch-confirm resolver נבנה: `session_store.py`'s `set/get/clear_pending_lead_preview()`, `core/lead_candidate_handler.py::resolve_pending_lead_preview()`, מחווט ב-`app.py`. הוכרע precedence (Tier-1 ActionGateway מנצח תמיד Tier-2). `test_tier2_silent_preview.py` נכתב מחדש (9/9), אפס רגרסיה.
2. **BUG-094 (10/07/2026, PR #291, `f96b5f1`) — ✅ ממוזג ל-main:** נמצא תוך כדי הבדיקה החיה הראשונה של BUG-058 — שני לידים בבאצ' קרוב נכתבו לאותה רשומה עם שם שגוי. שלושה שורשים נפרדים: (1) `parse_batch_dictation()`'s חלון ±60 תווים דלף שם בין מועמדים סמוכים; (2) `_at_find_lead()` נפל בעיוור ל-name-only match בלי לוודא phone; (3) `RouterDomain.CRM/INTERNAL` (מטא-דומיינים) זלגו לשדה `Domain` העסקי → 422 על Lead Events. תוקן (`_lead_domain_key()` חדש), `test_bug094_batch_name_bleed.py` (25/25 חדש), אפס רגרסיה על שאר חבילת הטסטים. **נדרש עדיין:** בדיקה חוזרת בפרודקשן שמראה שני `record_id` שונים ואין 422.
3. שרשרת `/update`+Business Memory (BUG-078..081, C97-C101, 08/07) — ללא שינוי, נשארת production-verified מלא ב-6/6 domains.

**פער ידוע שנותר, לא בטיפול:** `weekly_summary.py::_group_by_domain()` ו-Business Memory listing ב-`tma_api.py` עדיין קוראים `Tags[0]` כ-domain — ישברו בשקט על רשומות חדשות. לא דחוף (שני הצרכנים כבויים).

---

## 4. Next Priorities

1. **🔴 C81-FU** — Recovery: לאמת תוצאת שליחה בפועל לפני סימון `recovery_count`/הושלם.
2. **🔴 C82-FU** — Gate מרכזי אחד ל-`EMERGENCY_STOP_AUTOMATION` לפני כניסה לכל scheduler job (היום נאכף רק ב-followup/payment reminders).
3. **BUG-094 production verification** — לוודא בתעבורה חיה: שני `record_id` שונים לשני לידים בבאצ' קרוב, אפס 422 על Lead Events. תנאי לסגירה סופית.
4. **🟡 C84-C86** — TMA approvals TTL/freshness check, structural test ל-orphan approval actions, coverage מטריציוני ל-Emergency Stop על כל scheduler jobs.
5. **Decision Hub activation gate** — `FEATURE_DECISION_HUB` יישאר כבוי עד שיתקבל production evidence אמיתי ל-BUG-DH-03/04 (הפיקס כבר ממוזג, חסר רק אימות live).
