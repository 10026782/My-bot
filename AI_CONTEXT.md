# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026, `main` head שם `d249147`)
> — **לא** מקור אמת נוכחי, מפגר בעשרות PRs; `main` + `ROADMAP.md` גוברים עליו בכל סתירה.
> `ROADMAP.md` (עודכן 17/07/2026) ו-`CHANGE_CONTROL_LOG.md` (אחרון: C124/PR #372) מפגרים
> אחרי `main` — PR #373–#393 עדיין לא מתועדים שם. `CHANGELOG.md` סונכרן עד #390 (ע"י PR #391);
> PR #391–#393 עצמם עדיין לא מתועדים באף אחד מהשלושה. MAIN > DOCS עד שיתוקן.

**עודכן:** 2026-07-19 · **main:** `440234f` · **סטטוס:** אין ענף פעיל פתוח כרגע (כל PRs עד #393 ממוזגים ב-`main` — מאומת ב-git log, לא נבדק grep-לפי-סימבול בסבב הזה)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד. אין שינוי במסלול הזה.
- **BUG-111 (lead batch parsing)** — סגור בשני סבבים: PR #386 (טלפונים עם מפרידים, domain-hint, batch clarification) + PR #390 round-2 (paste קומפקטי בלי newline לפני header של batch/chat-export עדיין הפיק שם-ליד מזויף; תוקן + safety-net חדש: candidate יחיד מבוטל-אוטומטית ל-clarification אם יש יותר מטלפון אחד בטקסט הגולמי). קוד תמיד-פעיל, לא flag-gated, ירוק ב-tests; **לא** production-verified מול תעבורה חיה עדיין.
- **F52 (Message Contract Foundation)** — עכשיו 6+1 PRs (#381–#385, #389, #392, #393): שכבת ה-shadow logging של `ActionGateway` מכסה כעת גם rejection/cancellation (PR5, #389) וגם approval_pending prompt (PR6, #392) — כולל תיקון עוקב (PR6-FU, #393) שמרחיב את סיווג ה-EvidenceFinalizer עבור turns מעורבים (read מאומת + approval יחד). **`FEATURE_UNIFIED_STATUS_FORMATTER` נשאר `off` בכל מקום — אין הפעלת flag, אין שינוי התנהגות בפרודקשן.**
- **PR #392 חשף וסגר 3 פערים אמיתיים**: `_queue_approval_detailed_impl()` שלח טקסט hardcoded ישירות (בלי לעבור דרך ActionGateway — shadow לא ראה את זה בכלל); `_classify_response_claim()` קרא את דיכוי-הטקסט התקין של A32 (Single-Speaker gate) כ-false mismatch; `build_ownership_signal()` לא סימן `reply_owner="gateway"` כשה-agent דוכא. שלושתם תוקנו ללא שינוי בהתנהגות הבפועל (A32 suppression עצמו לא שונה).
- **BUG-112 (Telegram approval TTL)** — ללא שינוי מהסבב הקודם: VERIFIED IN MAIN, לא production-verified.
- **BUG-104 (Core Reasoning ל-Leads)** — ללא שינוי: Phase 1/1.1/2A.1/2A.2 ממוזג ומאומת ב-tests, `FEATURE_CORE_REASONING_LEADS_STATE` נשאר off/shadow, Phase 2A.0 (ניקוי סכמה) עדיין SPEC-בלבד וממתין להחלטת owner.
- **RP5 (Evidence Finalizer enforcement) — חסום**: קוד-שלם, `FEATURE_EVIDENCE_FINALIZER=off`, אין עדיין דגימות shadow אמיתיות שנאספו במלואן. פעולה הבאה תלויה ב-operator.
- **פער תיעוד**: `CHANGELOG.md`/`BUG_AUDIT_LOG.md` סונכרנו עד #390 (PR #391), אבל #391–#393 עצמם, ו-`ROADMAP.md`/`CHANGE_CONTROL_LOG.md` כולם (עוד מ-#373), עדיין לא מתועדים. הפער לא גדל השבוע אך גם לא נסגר.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram+WhatsApp inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow (כולל אכיפת TTL על כפתור טלגרם, BUG-112); Daily Digest; Finance Pulse; TMA read path; Cost Watchdog; חילוץ-ליד מ-WhatsApp (כולל תיקוני batch/domain/sender-prefix/compact-paste, BUG-111 סבב 1+2); RP1 tool-registry invariants (תמיד פעיל); TMA Lead Event Bridge; `lead_conversion.py`/`ad_attribution.py::mark_converted()` כותבים ערכים קנוניים (BUG-110).

**מיושם וממוזג ב-main, טרם אומת מול תעבורה חיה בפרודקשן (Render):**
- BUG-111 (שני הסבבים) — קוד תמיד-פעיל, tests ירוקים, אין אימות מול production traffic אמיתי.
- BUG-112 — אכיפת TTL על callback אישור טלגרם — קוד תמיד-פעיל, tests ירוקים, אין אימות מול production traffic אמיתי.

**מיושם חלקית / קוד מוכן אך flag כבוי:**
- F52 Message Contract Foundation + PR4–PR6 + PR6 follow-up (#381–#385, #389, #392, #393) — כל שכבת ה-shadow logging (executed/status-query, rejection/cancellation, approval_pending) קוד מוכן; אין שום צריכה חיה של הפורמט המאוחד עצמו. `FEATURE_UNIFIED_STATUS_FORMATTER` off. פעולה מומלצת הבאה: operator מפעיל `shadow` (לא `on`) ב-Render.
- BUG-104 Core Reasoning (Phase 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests בלבד. `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow.
- RP2/RP3 Tool Availability Filter — off. RP4 Evidence Finalizer — off, גם "enforce" הוא comparison-only.
- PA-01 structural enforcement — off, ממתין להחלטת shadow rollout.
- Phase 4B Atomic Claims — off, ללא שינוי.
- BUG-104 Phase 2A.0 — SPEC בלבד; ניקוי שדות `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` טרם בוצע.

**חסום:**
- RP5 enforcement — ממתין לדגימות shadow אמיתיות.
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- BUG-110 חוב טכני: `ad_attribution.py::mark_converted()` לא עובר דרך canonical gateway; `build_attribution_report()`/`audience_intelligence.py` עדיין קוראים `status=="converted"` הישן.
- חוב UX (מ-BUG-111): `resolve_pending_lead_preview()`/`_handle_batch()` עדיין חושפים record_id inline וכותרת שגויה בהודעת batch — לא תוקן, ממתין ל-cutover של הפורמטר המאוחד.
- PR #341 (Single-Speaker fix), C81-FU/C82-FU, רשומת Airtable `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו הסבב הזה.

---

## 3. Completed Since Last Update (18/07 → 19/07, main `2136a14` → `440234f`)

1. **PR #389 — F52 PR5: rejection/cancellation replies דרך unified formatter shadow** (`9973cc5`) — `reject()`/`route_cancellation_word()`/`route_combined_word()`'s cancel branch בנו טקסט legacy קבוע בלי מעורבות formatter; נוסף `ActionGateway._render_rejection_reply()` עם אותה מכונת off/shadow/on. לא נוגע ב-Telegram inline-button reject path (פער נפרד, מתועד). `"rejected"` ממשיך למופה ל-`"failure"` הקיים.
2. **PR #390 — BUG-111 follow-up: compact/newline-stripped WhatsApp paste** (`4635bcd`) — paste בלי newline לפני header של batch/chat-export עדיין הפיק שם-ליד מזויף (`"לידים חדשים"`). תוקן: `_BLOCK_SEP`/`_SENDER_LINE_RE` הורחבו, stop-words ברבים נוספו, ו-safety-net חדש ב-`_classify_ingress_core()` — candidate יחיד מבוטל אוטומטית ל-clarification כשיש יותר מטלפון אחד בטקסט. אומת נגד שתי דוגמאות production. 29 בדיקות חדשות.
3. **PR #391 — docs: sync BUG_AUDIT_LOG.md/CHANGELOG.md ל-PR #385–#390** — סגר חלק מהפער התיעודי (לא את כולו — ROADMAP/CHANGE_CONTROL_LOG עדיין לא סונכרנו, וגם #391 עצמו לא מתועד).
4. **PR #392 — F52 PR6: approval_pending prompt דרך unified formatter shadow + תיקון EvidenceFinalizer/ownership** (`38c2820`) — `_queue_approval_detailed_impl()` שלח hardcoded text בעקיפין ל-`bot.send_message()` בלי מעורבות formatter כלל; נוסף `ActionGateway._render_pending_prompt()`. במקביל תוקנו שני false-positive: `_classify_response_claim()` קיבל `approval_prompt_sent` param (claim="sent_for_approval" כש-final_text ריק אך prompt נשלח בפועל), ו-`build_ownership_signal()`'s call site ב-`app.py` מסמן `reply_owner="gateway"` כשה-agent דוכא ע"י A32. לא נוגע ב-BUG-111/112, לא משנה את החלטת הדיכוי של A32 עצמו. 50 בדיקות חדשות.
5. **PR #393 — F52 PR6 follow-up: הרחבת taxonomy ל-turns מעורבים** (`53eb19d`) — validation ב-production של PR6 חשף מקרה נוסף: turn שמבצע גם read מאומת וגם מעלה approval מסווג כ-`evidence_status="mixed"` (לא `"approval_pending"`), וה-compatibility check עדיין דיווח false mismatch. הורחב במדויק: `"sent_for_approval"` תואם גם ל-`"mixed"` כשה-non-success היחיד הוא `approvals_pending` (אפס כשלים/effects לא-מאומתים/unknown). 5 בדיקות הגנה נוספות (55 סה"כ בקובץ).

**פער תיעוד פתוח:** PR #373–#393 עדיין לא ב-`ROADMAP.md`/`CHANGE_CONTROL_LOG.md`; PR #391–#393 גם לא ב-`CHANGELOG.md`/`BUG_AUDIT_LOG.md`.

---

## 4. Next Priorities

1. **סנכרון מסמכי ממשל** — להשלים רשומות ל-`ROADMAP.md`/`CHANGE_CONTROL_LOG.md` (חסרים מ-#373) ול-`CHANGELOG.md`/`BUG_AUDIT_LOG.md` (חסרים #391–#393), כדי ש-MAIN ו-DOCS יתאמו.
2. **production verification: BUG-111 (שני סבבים) / BUG-112** — קוד תמיד-פעיל, tests ירוקים, אך טרם נצפה מול תעבורה חיה בפרודקשן (Render deploy + מעקב).
3. **operator: F52 shadow rollout** — הפעלת `FEATURE_UNIFIED_STATUS_FORMATTER=shadow` (לא `on`) ב-Render — כעת יש כיסוי shadow לשלושה נתיבים (executed/status-query, rejection/cancellation, approval_pending, כולל mixed turns) לאיסוף דגימות אמיתיות.
4. **operator: RP5 preflight** — הפעלת `FEATURE_EVIDENCE_FINALIZER=shadow` ב-Render ואיסוף דגימה לכל אחד מ-9 מצבי הסיווג לפני שRP5 עצמו יכול להתחיל.
5. **החלטת owner: BUG-104** — הפעלת `FEATURE_CORE_REASONING_LEADS_STATE` (קוד מוכן ומאומת) וניקוי סכמת Phase 2A.0 (`tier`/`Domain category`/`Domain risk assessment`/`Domain summary`).
