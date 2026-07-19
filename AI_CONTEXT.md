# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing), לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו — אין מקור בשם הזה, לא CRITICAL.
> `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה 26/06/2026, `main` head שם `d249147`)
> — **לא** מקור אמת נוכחי, מפגר בעשרות PRs; `main` + `ROADMAP.md` גוברים עליו בכל סתירה.
> `ROADMAP.md`, `CHANGE_CONTROL_LOG.md`, `CHANGELOG.md` ו-`BUG_AUDIT_LOG.md` סונכרנו כולם עד `main`
> `587d1fe` (PR #396) בעדכון הזה. הערת גבולות שנשארת: `CHANGELOG.md` עדיין חסר itemization נפרד
> ל-#348–#353 (PA-01), ו-`CHANGE_CONTROL_LOG.md` עדיין חסר רשומות #327–#353 אחרי C111 — פערים
> היסטוריים ישנים, מסומנים במפורש, לא backfilled בסבב הזה.

> **כלל תהליך (חדש, 19/07/2026):** **Runtime evidence > main code > docs > memory.**
> אין להסיק מצב flag פרוס/runtime מ-ברירת המחדל ב-`feature_flags.py` בלבד — ברירת מחדל בקוד
> אומרת מה קורה **בהיעדר** override, לא מה בפועל רץ ב-Render. אם לוגי production מציגים
> `[UnifiedStatusFormatterShadow]` או `[EvidenceFinalizerShadow]`, יש לסווג את ה-runtime כ-
> **shadow-observed**, גם אם ברירת המחדל בקוד היא `off`. אם התיעוד סותר לוגי production —
> **התיעוד** מסומן stale, **לא** מורידים את סטטוס ה-runtime.

**עודכן:** 2026-07-19 · **main:** `587d1fe` (אחרי מיזוג PR #396, "Fix A32: suppress approval-invite prose duplicating a queued approval prompt") · **סטטוס:** אין ענף פעיל פתוח כרגע (כל PRs עד #396 ממוזגים ב-`main` — מאומת ב-git log + git cat-file)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד. אין שינוי במסלול הזה.
- **BUG-111 (lead batch parsing) — ✅ VERIFIED IN PROD.** סגור בשני סבבים: PR #386 (טלפונים עם מפרידים, domain-hint, batch clarification) + PR #390 round-2 (paste קומפקטי בלי newline לפני header של batch/chat-export עדיין הפיק שם-ליד מזויף; תוקן + safety-net חדש: candidate יחיד מבוטל-אוטומטית ל-clarification אם יש יותר מטלפון אחד בטקסט הגולמי). **הוכחת production:** paste קומפקטי/WhatsApp עם 3 טלפונים (`0533968395`/`0533123482`/`0534185481`) כבר לא יצר ליד מזויף בשם "לידים חדשים" — BOSS זיהה את שלושת המספרים ושאל לשמות במקום ליצור Lead שגוי.
- **BUG-112 (Telegram approval TTL) — מנגנון הליבה ✅ VERIFIED IN PROD.** PR #387: `_handle_approval_callback_impl()` אוכף TTL של 10 דקות לפני dispatch. **הוכחת production:** לחיצה על כפתור שפג תוקף הציגה `"⏰ פג תוקף — הפעולה לא בוצעה"`, הפעולה לא בוצעה, וכפתור האישור נעלם (edited-message). **PR #394 (נפרד, ראה למטה)** הוא defensive/idempotency cleanup לנתיב **אחר** (callback חסר/stale/כבר-נצרך) — merged, tests green, **לא** נבדק production בנפרד עדיין (הדגימה שהובילה אליו נצפתה *לפני* המיזוג; דגימת ה-expiry האחרונה שהוכיחה את BUG-112 גם מסירה את מסלול הלחיצה-הכפולה הרגיל כי הכפתור נעלם אחרי הלחיצה הראשונה).
- **F52 (Message Contract Foundation) — קוד flag-gated `off`, אך runtime shadow observed בלוגי production.** עכשיו 6+1 PRs (#381–#385, #389, #392, #393): שכבת ה-shadow logging של `ActionGateway` מכסה executed/status-query, rejection/cancellation (PR5, #389), ו-approval_pending prompt (PR6, #392) — כולל תיקון עוקב (PR6-FU, #393). **הוכחת production (לוגים אמיתיים, לא רק קוד):** `[UnifiedStatusFormatterShadow] outcome=executed mapped_state=success ...`, `outcome=rejected mapped_state=failure ...`, `outcome=pending mapped_state=approval_pending ...` — שלושתם נצפו. `FEATURE_UNIFIED_STATUS_FORMATTER` ברירת המחדל בקוד היא `off`, אך זו ברירת-מחדל-בהיעדר-override, לא הוכחה ש-shadow לא רץ — הלוגים מוכיחים שהוא כן רץ. **לא** הופעל `on` — שומרים shadow.
- **PR #392 חשף וסגר 3 פערים אמיתיים**: `_queue_approval_detailed_impl()` שלח טקסט hardcoded ישירות (בלי לעבור דרך ActionGateway — shadow לא ראה את זה בכלל); `_classify_response_claim()` קרא את דיכוי-הטקסט התקין של A32 (Single-Speaker gate) כ-false mismatch; `build_ownership_signal()` לא סימן `reply_owner="gateway"` כשה-agent דוכא. שלושתם תוקנו ללא שינוי בהתנהגות הבפועל (A32 suppression עצמו לא שונה).
- **PR #393 (F52 PR6 follow-up, mixed taxonomy) — merged/tests green; לא overclaimed.** הרחיב את `compare_shadow_final_status()` כך ש-`"sent_for_approval"` תואם גם `evidence_status="mixed"` כשה-non-success היחיד הוא `approvals_pending`. **דגימת production שכן נצפתה:** `evidence_status=mixed verified_reads=1 approvals_pending=1 response_claim=mixed mismatch=false` — turn מעורב read+pending התנהג נקי. **הענף המדויק של PR #393 עדיין לא נלכד**: `evidence_status=mixed response_claim=sent_for_approval mismatch=false verified_reads=1 approvals_pending=1` — עדיין לא נצפתה דגימה אחת עם `response_claim=sent_for_approval` ספציפית (לא `mixed`) על turn מעורב. **אין לסמן את הענף המדויק הזה כ-production-verified עדיין** — רק את ההתנהגות הסמוכה (mixed turns כלליים).
- **PR #396 (BUG-113, A32 duplicate approval-pending prose) — ✅ VERIFIED IN PROD, closed.** ראה §3 למטה לפירוט מלא + evidence.
- **BUG-104 (Core Reasoning ל-Leads)** — ללא שינוי: Phase 1/1.1/2A.1/2A.2 ממוזג ומאומת ב-tests, `FEATURE_CORE_REASONING_LEADS_STATE` נשאר off/shadow, Phase 2A.0 (ניקוי סכמה) עדיין SPEC-בלבד וממתין להחלטת owner.
- **RP5 (Evidence Finalizer) — runtime shadow observed בלוגי production, enforcement עדיין חסום.** **הוכחת production:** `[EvidenceFinalizerShadow] state=shadow evidence_status=approval_pending response_claim=sent_for_approval mismatch=false code=match counts={'classification': 'approval_pending', 'verified_reads': 0, 'verified_writes': 0, 'failed_calls': 0, 'outcome_unknown': 0, 'approvals_pending': 1, 'unverified_effects': 0}`. `FEATURE_EVIDENCE_FINALIZER`'s ברירת מחדל בקוד `off` — לא אומר ש-shadow לא רץ; הלוג מוכיח שהוא כן רץ. Enforcement (RP5 עצמו) עדיין לא מוכן — חסר הענף המדויק של #393 (ראו למעלה) בין שאר הדגימות הנדרשות.
- **פער תיעוד — נסגר בעדכון הזה**: `ROADMAP.md`/`CHANGE_CONTROL_LOG.md`/`CHANGELOG.md`/`BUG_AUDIT_LOG.md` כולם סונכרנו עד PR #396.

---

## 2. Current System State

**עובד בפרודקשן, ✅ VERIFIED IN PROD:** Telegram+WhatsApp inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed); Approval flow כולל אכיפת TTL על כפתור טלגרם (BUG-112 מנגנון הליבה — evidence: `"⏰ פג תוקף — הפעולה לא בוצעה"`, 0 ביצוע, כפתור נעלם); Daily Digest; Finance Pulse; TMA read path; Cost Watchdog; חילוץ-ליד מ-WhatsApp כולל תיקוני batch/domain/sender-prefix/compact-paste (BUG-111 סבב 1+2 — evidence: paste 3-טלפונים לא יצר עוד ליד מזויף, ביקש 3 שמות); A32 Single-Speaker suppression כולל BUG-113/PR #396 (evidence: הודעה יחידה למשתמש, לא כפולה); RP1 tool-registry invariants (תמיד פעיל); TMA Lead Event Bridge; `lead_conversion.py`/`ad_attribution.py::mark_converted()` כותבים ערכים קנוניים (BUG-110).

**מיושם וממוזג ב-main, merged/tests green, טרם production-verified בנפרד:**
- BUG-112 UX follow-up (PR #394) — נרמול ניסוח stale/missing-callback ל-`_notify_missing_or_expired_callback()` — defensive/idempotency cleanup, לא נדרש לעצם BUG-112 שכבר verified. אין דגימת "missing/already-consumed callback" מפורשת עדיין (הדגימה שסגרה את BUG-112 הוכיחה את נתיב ה-expiry-ידוע, ומדגם מהעולם האמיתי כעת נדיר יותר כי הכפתור נעלם אחרי הלחיצה הראשונה).

**מיושם חלקית / קוד flag-gated `off`, אך עם runtime shadow evidence בלוגי production (לא רק ברירת-מחדל-בקוד):**
- F52 Message Contract Foundation + PR4–PR6 + PR6 follow-up (#381–#385, #389, #392, #393) — כל שכבת ה-shadow logging קוד מוכן, **וגם** נצפתה רצה בפרודקשן: `[UnifiedStatusFormatterShadow]` עבור `outcome=executed`/`rejected`/`pending` שלושתם נצפו בלוגים. `FEATURE_UNIFIED_STATUS_FORMATTER` ברירת המחדל בקוד `off` — אין להסיק מכך "shadow לא רץ"; הלוגים מוכיחים אחרת. **אין הפעלת `on`** — שומרים shadow, ממתינים לחלון soak נקי (ראו §4).
- RP4/RP5 Evidence Finalizer — קוד מוכן, **וגם** shadow evidence אמיתי בלוגים (`[EvidenceFinalizerShadow] ... mismatch=false code=match`). `FEATURE_EVIDENCE_FINALIZER` ברירת מחדל בקוד `off` — אותה הבחנה. Enforcement (RP5) עדיין חסום — ראו §4.
- BUG-104 Core Reasoning (Phase 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests בלבד, אין evidence runtime שנצפה עדיין. `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow.
- RP2/RP3 Tool Availability Filter — off, אין evidence runtime.
- PA-01 structural enforcement — off, ממתין להחלטת shadow rollout.
- Phase 4B Atomic Claims — off, ללא שינוי.
- BUG-104 Phase 2A.0 — SPEC בלבד; ניקוי שדות `tier`/`Domain category`/`Domain risk assessment`/`Domain summary` טרם בוצע.

**חסום:**
- RP5 enforcement — יש כבר shadow evidence (ראו למעלה), אך חסר עדיין הענף המדויק של PR #393 (`evidence_status=mixed response_claim=sent_for_approval mismatch=false`, לא רק `mixed`/`response_claim=mixed`) בין שאר הדגימות הנדרשות לכל 9 מצבי הסיווג לפני שאכיפה אמיתית יכולה להתחיל.
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- BUG-110 חוב טכני: `ad_attribution.py::mark_converted()` לא עובר דרך canonical gateway; `build_attribution_report()`/`audience_intelligence.py` עדיין קוראים `status=="converted"` הישן.
- חוב UX (מ-BUG-111): `resolve_pending_lead_preview()`/`_handle_batch()` עדיין חושפים record_id inline וכותרת שגויה בהודעת batch — לא תוקן, ממתין ל-cutover של הפורמטר המאוחד.
- PR #341 (Single-Speaker fix), C81-FU/C82-FU, רשומת Airtable `recRvK6hFTNgyj8ag` — לא נבדקו/טופלו הסבב הזה.

---

## 3. Completed Since Last Update (18/07 → 19/07, main `2136a14` → `587d1fe`)

1. **PR #389 — F52 PR5: rejection/cancellation replies דרך unified formatter shadow** (`9973cc5`) — `reject()`/`route_cancellation_word()`/`route_combined_word()`'s cancel branch בנו טקסט legacy קבוע בלי מעורבות formatter; נוסף `ActionGateway._render_rejection_reply()` עם אותה מכונת off/shadow/on. לא נוגע ב-Telegram inline-button reject path (פער נפרד, מתועד). `"rejected"` ממשיך למופה ל-`"failure"` הקיים.
2. **PR #390 — BUG-111 follow-up: compact/newline-stripped WhatsApp paste** (`4635bcd`) — paste בלי newline לפני header של batch/chat-export עדיין הפיק שם-ליד מזויף (`"לידים חדשים"`). תוקן: `_BLOCK_SEP`/`_SENDER_LINE_RE` הורחבו, stop-words ברבים נוספו, ו-safety-net חדש ב-`_classify_ingress_core()` — candidate יחיד מבוטל אוטומטית ל-clarification כשיש יותר מטלפון אחד בטקסט. **✅ VERIFIED IN PROD**: paste 3-טלפונים אמיתי לא יצר עוד ליד מזויף, ביקש 3 שמות. 29 בדיקות חדשות.
3. **PR #391 — docs: sync BUG_AUDIT_LOG.md/CHANGELOG.md ל-PR #385–#390** — סגר חלק מהפער התיעודי.
4. **PR #392 — F52 PR6: approval_pending prompt דרך unified formatter shadow + תיקון EvidenceFinalizer/ownership** (`38c2820`) — `_queue_approval_detailed_impl()` שלח hardcoded text בעקיפין ל-`bot.send_message()` בלי מעורבות formatter כלל; נוסף `ActionGateway._render_pending_prompt()`. במקביל תוקנו שני false-positive: `_classify_response_claim()` קיבל `approval_prompt_sent` param, ו-`build_ownership_signal()`'s call site ב-`app.py` מסמן `reply_owner="gateway"` כשה-agent דוכא ע"י A32. **runtime shadow evidence נצפה** (`[UnifiedStatusFormatterShadow] outcome=pending mapped_state=approval_pending`). 50 בדיקות חדשות.
5. **PR #393 — F52 PR6 follow-up: הרחבת taxonomy ל-turns מעורבים** (`53eb19d`) — `"sent_for_approval"` תואם גם ל-`"mixed"` כשה-non-success היחיד הוא `approvals_pending`. **דגימה סמוכה נצפתה** (`evidence_status=mixed response_claim=mixed mismatch=false`), **הענף המדויק** (`response_claim=sent_for_approval` על turn מעורב) **עדיין לא נלכד** — לא מסומן production-verified באופן ספציפי. 5 בדיקות הגנה נוספות (55 סה"כ בקובץ).
6. **PR #394 — BUG-112 production follow-up: נרמול UX ל-stale/missing-callback** (`8ac0c93`) — `_notify_missing_or_expired_callback()` חדש מאחד שלושה ניסוחים חופפים לביטוי אחד עקבי. **merged/tests green, defensive/idempotency cleanup** — לא נדרש לעצם BUG-112 שכבר verified; לא נבדק production בנפרד עדיין. 8 בדיקות חדשות (30 סה"כ).
7. **PR #395 — docs: AI_CONTEXT daily briefing ל-PR #388–#393** (`951b1b2`) — רענון שגרתי.
8. **PR #396 — BUG-113: A32 מדכא פרוזת approval-invite כפולה** (`2d86de6`) — production evidence: turn שמבצע approval אמיתי (הודעת gateway "⏳ בקשת אישור" נשלחה) עדיין הראה גם פרוזת agent חופשית ("✅ מוכנה להוספה... שלח מאשר כדי לאשר") ללא דיכוי — `EvidenceFinalizerShadow` דיווח `response_claim=success` נגד `evidence_status=approval_pending` (`mismatch=true`), פער Single-Speaker אמיתי. תוקן: ענף דיכוי חדש הגדור ב-`_gateway_active` וראיית `__approval_queued__` אמיתית. **✅ VERIFIED IN PROD מיד אחרי ה-deploy**, evidence מדויק:
   ```
   [A32] Single-Speaker: agent emitted approval-invite prose after an approval was already queued this turn — suppressing (not replacing with fallback)
   [TurnEnvelope] ownership_signal ... "approval_queued": true, "agent_claimed_approval": false, "reply_owner": "gateway"
   [EvidenceFinalizerShadow] state=shadow evidence_status=approval_pending response_claim=sent_for_approval mismatch=false code=match counts={'classification': 'approval_pending', 'verified_reads': 0, 'verified_writes': 0, 'failed_calls': 0, 'outcome_unknown': 0, 'approvals_pending': 1, 'unverified_effects': 0}
   ```
   הפלט למשתמש הכיל רק את הודעת ה-gateway — אין יותר כפילות. 18 בדיקות חדשות. **סגור.**
9. **סנכרון תיעוד + reclassification runtime evidence (סבב זה)** — `ROADMAP.md`/`CHANGE_CONTROL_LOG.md`/`CHANGELOG.md`/`BUG_AUDIT_LOG.md` סונכרנו עד #396, **וגם** BUG-111/BUG-112 (מנגנון ליבה)/F52 shadow/RP5 shadow שודרגו מ-"לא production-verified"/"קוד off" ל-status מדויק המבוסס על לוגי production בפועל, לפי הכלל "Runtime evidence > main code > docs > memory" (ראו הערה בראש המסמך). PR #393 ו-PR #394 **לא** overclaimed — כל אחד סומן במדויק למה שיש לו הוכחה ולמה שחסר.

**פער תיעוד היסטורי שנשאר פתוח (לא נסגר, מסומן בכוונה):** `CHANGELOG.md` עדיין חסר itemization נפרד ל-#348–#353 (PA-01); `CHANGE_CONTROL_LOG.md` עדיין חסר רשומות #327–#353 אחרי C111.

---

## 4. Next Priorities

1. **docs sync ל-runtime evidence** — ✅ הושלם בסבב הזה (עדכון זה עצמו).
2. **shadow soak / חלון תצפית** — להמשיך לצבור דגימות `[UnifiedStatusFormatterShadow]`/`[EvidenceFinalizerShadow]` מפרודקשן על פני חלון זמן, לא רק דגימות בודדות.
3. **ניטור אקטיבי במהלך ה-soak** — לעקוב אחרי כל אחד מהדגלים הבאים בלוגי shadow: `mismatch=true`, `record_id_leak=True`, `tool_name_leak=True`, `contract_id_leak=True`, `fallback_used=True`. כל הופעה דורשת חקירה לפני שממשיכים.
4. **רק אחרי חלון נקי** — לשקול הפעלת `FEATURE_UNIFIED_STATUS_FORMATTER=on` (לא לפני). זו החלטת operator/owner, לא אוטומטית.
5. **RP5 enforcement נשאר חסום** עד שנאספות מספיק דגימות נקיות לכל 9 מצבי הסיווג — כולל במפורש **הענף המדויק של PR #393** (`evidence_status=mixed response_claim=sent_for_approval mismatch=false`), שעדיין לא נצפה.
6. **החלטת owner: BUG-104** — הפעלת `FEATURE_CORE_REASONING_LEADS_STATE` (קוד מוכן ומאומת) וניקוי סכמת Phase 2A.0 (`tier`/`Domain category`/`Domain risk assessment`/`Domain summary`).
7. **production verification: PR #394 (BUG-112 UX cleanup)** — ממתין לדגימת "missing/already-consumed callback" אמיתית אחרי ה-deploy הזה.
