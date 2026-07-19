# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026, `main` head שם `d249147`)
> — **לא** מקור אמת נוכחי, מפגר בעשרות PRs; `main` + `ROADMAP.md` גוברים עליו בכל סתירה.
> `ROADMAP.md` (עודכן 19/07/2026), `CHANGE_CONTROL_LOG.md` (אחרון: C148/PR #396), `CHANGELOG.md`
> ו-`BUG_AUDIT_LOG.md` סונכרנו כולם עד `main` `587d1fe` (PR #396) בעדכון הזה — הפער שתועד כאן
> ("MAIN > DOCS") נסגר. הערת גבולות שנשארת: `CHANGELOG.md` עדיין חסר itemization נפרד ל-#348–#353
> (PA-01), ו-`CHANGE_CONTROL_LOG.md` עדיין חסר רשומות #327–#353 אחרי C111 — פערים היסטוריים ישנים
> יותר, מסומנים במפורש, לא backfilled בסבב הזה.

**עודכן:** 2026-07-19 · **main:** `587d1fe` · **סטטוס:** אין ענף פעיל פתוח כרגע (PRs עד #396 ממוזגים ב-`main` — מאומת ב-git log + grep על התיקונים העיקריים בסבב הזה)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד. אין שינוי במסלול הזה.
- **BUG-111 (lead batch parsing)** — סגור בשני סבבים: PR #386 (טלפונים עם מפרידים, domain-hint, batch clarification) + PR #390 round-2 (paste קומפקטי בלי newline לפני header של batch/chat-export עדיין הפיק שם-ליד מזויף; תוקן + safety-net חדש: candidate יחיד מבוטל-אוטומטית ל-clarification אם יש יותר מטלפון אחד בטקסט הגולמי). קוד תמיד-פעיל, לא flag-gated, ירוק ב-tests; **לא** production-verified מול תעבורה חיה עדיין.
- **F52 (Message Contract Foundation)** — עכשיו 6+1 PRs (#381–#385, #389, #392, #393): שכבת ה-shadow logging של `ActionGateway` מכסה כעת גם rejection/cancellation (PR5, #389) וגם approval_pending prompt (PR6, #392) — כולל תיקון עוקב (PR6-FU, #393) שמרחיב את סיווג ה-EvidenceFinalizer עבור turns מעורבים (read מאומת + approval יחד). **`FEATURE_UNIFIED_STATUS_FORMATTER` נשאר `off` בכל מקום — אין הפעלת flag, אין שינוי התנהגות בפרודקשן.**
- **PR #392 חשף וסגר 3 פערים אמיתיים**: `_queue_approval_detailed_impl()` שלח טקסט hardcoded ישירות (בלי לעבור דרך ActionGateway — shadow לא ראה את זה בכלל); `_classify_response_claim()` קרא את דיכוי-הטקסט התקין של A32 (Single-Speaker gate) כ-false mismatch; `build_ownership_signal()` לא סימן `reply_owner="gateway"` כשה-agent דוכא. שלושתם תוקנו ללא שינוי בהתנהגות הבפועל (A32 suppression עצמו לא שונה).
- **BUG-112 (Telegram approval TTL)** — המנגנון עצמו (PR #387) **✅ VERIFIED IN PROD**: לחיצה אמיתית על כפתור שכבר פג תוקף הפיקה את ההודעה הצפויה ולא בוצע dispatch חוזר. סבב UX נוסף (PR #394) איחד שלושה ניסוחים חופפים של "stale/missing callback" (שהתגלו כתצפית production נפרדת) לביטוי אחד עקבי — קוד מוכן, tests ירוקים, טרם production-verified מחדש אחרי ה-deploy הזה.
- **BUG-113 (חדש, PR #396)** — A32's Single-Speaker gate לא דיכא פרוזת approval-invite של ה-agent ("✅ מוכנה להוספה... שלח מאשר") כשאישור אמיתי כבר נכנס לתור השבוע — נחשף מיד אחרי validation ל-F52 PR6, ולא נגרם ממנו (לא באג taxonomy). תוקן בענף דיכוי חדש הגדור ב-ראיית `__approval_queued__` אמיתית. **✅ VERIFIED IN PROD** (evidence מדויק: לוג דיכוי + ownership_signal נכון + EvidenceFinalizerShadow ללא mismatch).
- **BUG-104 (Core Reasoning ל-Leads)** — ללא שינוי: Phase 1/1.1/2A.1/2A.2 ממוזג ומאומת ב-tests, `FEATURE_CORE_REASONING_LEADS_STATE` נשאר off/shadow, Phase 2A.0 (ניקוי סכמה) עדיין SPEC-בלבד וממתין להחלטת owner.
- **RP5 (Evidence Finalizer enforcement) — חסום**: קוד-שלם, `FEATURE_EVIDENCE_FINALIZER=off`, אין עדיין דגימות shadow אמיתיות שנאספו במלואן. פעולה הבאה תלויה ב-operator.
- **פער תיעוד — נסגר בעדכון הזה**: `ROADMAP.md`/`CHANGE_CONTROL_LOG.md`/`CHANGELOG.md`/`BUG_AUDIT_LOG.md` כולם סונכרנו עד PR #396 (כולל C125–C148 חדשים, שסוגרים backfill מלא מ-#373). הערת גבולות היסטורית שנשארת (לא נסגרה): `CHANGELOG.md` עדיין חסר #348–#353 (PA-01), `CHANGE_CONTROL_LOG.md` עדיין חסר #327–#353 אחרי C111.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram+WhatsApp inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow (כולל אכיפת TTL על כפתור טלגרם, BUG-112); Daily Digest; Finance Pulse; TMA read path; Cost Watchdog; חילוץ-ליד מ-WhatsApp (כולל תיקוני batch/domain/sender-prefix/compact-paste, BUG-111 סבב 1+2); RP1 tool-registry invariants (תמיד פעיל); TMA Lead Event Bridge; `lead_conversion.py`/`ad_attribution.py::mark_converted()` כותבים ערכים קנוניים (BUG-110).

**עובד בפרודקשן, VERIFIED IN PROD:** BUG-111 (שני הסבבים — פענוח batch לידים); BUG-112 core TTL enforcement (כפתור אישור טלגרם); A32 Single-Speaker suppression כולל BUG-113 (פרוזת approval-invite כפולה).

**מיושם וממוזג ב-main, טרם אומת מול תעבורה חיה בפרודקשן (Render):**
- BUG-112 UX follow-up (PR #394) — איחוד ניסוח stale/missing-callback — קוד תמיד-פעיל, tests ירוקים, טרם production-verified מחדש אחרי ה-deploy הזה.

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

## 3. Completed Since Last Update (19/07, main `440234f` → `587d1fe`)

1. **PR #394 — BUG-112 production follow-up: נרמול UX ל-stale/missing-callback** (`8ac0c93`) — לחיצה כפולה על כפתור אישור שפג תוקף הפיקה שלושה ניסוחים חופפים-אך-שונים. אושרו שני נתיבי callback נפרדים באמת (פריט ידוע-ופג-תוקף מול "לא נמצא כלום" — 30 דקות TTL פנימי של event_bus או כבר-נצרך). `_notify_missing_or_expired_callback()` חדש מאחד את הנתיב השני לביטוי אחד עקבי בשלוש הבמות (פופ-אפ/הודעה קבועה/עריכה). אין שינוי לסמנטיקת ביצוע. 8 בדיקות חדשות (30 סה"כ). ראה `BUG_AUDIT_LOG.md`'s BUG-112 (סבב 2).
2. **PR #395 — docs: AI_CONTEXT daily briefing ל-PR #388–#393** (`951b1b2`) — רענון שגרתי, זיהה במפורש ש-`ROADMAP.md`/`CHANGE_CONTROL_LOG.md` מפגרים אחרי `main` (הפער שנסגר בעדכון הנוכחי).
3. **PR #396 — BUG-113: A32 מדכא פרוזת approval-invite כפולה** (`2d86de6`) — production evidence הראתה שגם כשאישור אמיתי כבר בתור (הודעת gateway תקינה נשלחה), פרוזה חופשית של ה-agent ("✅ מוכנה להוספה... שלח מאשר כדי לאשר") עברה ללא דיכוי — `EvidenceFinalizerShadow` דיווח `response_claim=success` נגד `evidence_status=approval_pending`, פער Single-Speaker אמיתי, לא taxonomy. שער ה-Single-Speaker הקיים (`_AGENT_ACTION_STATUS_PATTERN`/`_AGENT_PENDING_STATUS_PATTERN`) לא כיסה את הניסוח; `_AGENT_APPROVAL_INVITE_PATTERN` הקיים כן תואם, אבל נבדק רק בכיוון ההפוך (ללא ראיה). תוקן: ענף דיכוי חדש הגדור ב-`_gateway_active` וראיית `__approval_queued__` אמיתית. **VERIFIED IN PROD מיד אחרי ה-deploy** (evidence מדויק בלוגים: דיכוי + ownership_signal נכון + EvidenceFinalizerShadow `mismatch=false`). 18 בדיקות חדשות. ראה `BUG_AUDIT_LOG.md`'s BUG-113 (חדשה).
4. **סנכרון תיעוד מלא (סבב זה)** — `ROADMAP.md` (header + entry חדש), `AI_CONTEXT.md` (זה), `CHANGELOG.md` (#391–#396), `BUG_AUDIT_LOG.md` (BUG-112 סבב 2 + BUG-113 חדשה), ו-`CHANGE_CONTROL_LOG.md` (C125–C148, backfill מלא מ-#373) — כל הרשומות מאומתות מול `main` (`git log`/`git diff --stat`) לפני כתיבה. סוגר את פער "MAIN > DOCS" שתועד בעצמו כאן ב-3 עדכונים קודמים ברציפות.

**פער תיעוד היסטורי שנשאר פתוח (לא נסגר, מסומן בכוונה):** `CHANGELOG.md` עדיין חסר itemization נפרד ל-#348–#353 (PA-01); `CHANGE_CONTROL_LOG.md` עדיין חסר רשומות #327–#353 אחרי C111. שני הפערים ישנים מ-16/07/2026, לא גדלו השבוע.

---

## 4. Next Priorities

1. **production verification: BUG-112 UX follow-up (#394)** — קוד תמיד-פעיל, tests ירוקים, אך הניסוח המאוחד טרם נצפה live על callback stale אמיתי אחרי ה-deploy הזה (הדגימה שהובילה לתיקון נצפתה לפני המיזוג).
2. **operator: F52 shadow rollout** — הפעלת `FEATURE_UNIFIED_STATUS_FORMATTER=shadow` (לא `on`) ב-Render — כעת יש כיסוי shadow לארבעה נתיבים (executed/status-query, rejection/cancellation, approval_pending כולל mixed turns) לאיסוף דגימות אמיתיות.
3. **operator: RP5 preflight** — הפעלת `FEATURE_EVIDENCE_FINALIZER=shadow` ב-Render ואיסוף דגימה לכל אחד מ-9 מצבי הסיווג לפני שRP5 עצמו יכול להתחיל.
4. **החלטת owner: BUG-104** — הפעלת `FEATURE_CORE_REASONING_LEADS_STATE` (קוד מוכן ומאומת) וניקוי סכמת Phase 2A.0 (`tier`/`Domain category`/`Domain risk assessment`/`Domain summary`).
5. **היסטורי, לא דחוף:** backfill אופציונלי ל-`CHANGELOG.md`/#348–#353 ול-`CHANGE_CONTROL_LOG.md`/#327–#353 — פערים ישנים ומסומנים, לא גדלים.
