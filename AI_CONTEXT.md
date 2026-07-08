# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד),
> `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`. `CANONICAL_STATE.md` **לא קיים** בריפו.

**עודכן:** 2026-07-08 (מאוחר יותר עוד) · **main:** `def0a00` (PR #265) · **סטטוס:** `/update`→Business Memory ✅ VERIFIED במלואו, 6/6 domains (ראו §3)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, בנוי סביב Identity → Router → Context → Agent, Airtable כ-CRM.
- הסבב האחרון (07-08/07) סגר שרשרת של 6+ תיקוני `/update`/Business Memory (BUG-078..081, C97-C101) — **כולם ממוזגים ל-main, ומאומתים בפרודקשן בכל 6 ה-domains** (ראו §3).
- PR #263 סגר את הסאגה העיקרית: `domain` כבר לא נכתב ל-`Tags` בשום נתיב (רק לשדה `Domain` הייעודי), תוקן מיפוי `media`→Title Case, ותוקנה קריאת ההקשר (`get_recent_business_context`) לסנן לפי `Domain`. PR #265 (אחריו) תיקן רווח בסוף ב-`"Real Estate "`/`"SaaS "` (מאומת מול Airtable Meta API) — זהו המיפוי הנכון הסופי.
- רוב דגלי הפיצ'רים (`FEATURE_AUTO_CAPTURE`, `FEATURE_STRUCTURED_FILE_CAPTURE`, `FEATURE_DECISION_HUB`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`) **כבויים בכוונה** — קוד מוכן/ממוזג, לא מופעל בפרוד.
- שני items בעדיפות 🔴 דחוף עדיין פתוחים ולא טופלו: C81-FU (אימות משלוח ב-Recovery) ו-C82-FU (gate מרכזי ל-EMERGENCY_STOP_AUTOMATION).
- אין harness pytest — בדיקות הן סקריפטים עצמאיים (`python3 <file>.py`); ב-sandbox הנוכחי `smoke_tests.py` מדווח 2 כשלים בגלל תלויות חסרות (`flask`/`httpx`) — **מגבלת סביבה, לא רגרסיית קוד** (שאר 5 הבדיקות עוברות).
- כלל ברזל: "הושלם" ≠ "מאומת". שום claim כאן לא production-verified אלא אם צוין כך במפורש.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (normalize→validate→audit); Approval flow (ActionGateway + `tool_registry.enforce`); Daily Digest; Finance Pulse; TMA (Leads/Projects/Game/Finance Pulse); Cost Watchdog; C94 Ingress Envelope (דגל ON כברירת מחדל).

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- C89 Capture Policy (auto-write tiers) — נסגר כ-CLOSED/VERIFIED בהחלטת הבעלים, `FEATURE_AUTO_CAPTURE` נשאר כבוי בכוונה.
- C90 (קבצי xlsx/csv), Lead Scoring/Memory/Followup (N02-N04) — code done, flags off, לא מאומת בתעבורה אמיתית.
- Decision Hub (Stages 0-6, F17-F22) — כל השלבים ממוזגים ל-main; `FEATURE_DECISION_HUB` כבוי, חסום עד production evidence (ראו חסימות למטה).

**חסום:**
- Decision Hub activation — חסום ל-BUG-DH-03/04 (Formula Injection): התיקון עצמו **ממוזג** (PR #251), אבל עדיין אין production evidence שמאשר את זה live.
- WhatsApp outbound אמיתי — honest stub, ממתין לאישור Meta Cloud API.
- C93 (OCR/כרטיסי ביקור) — חסום על צבירת ≥2 שבועות נתוני `AgentObservation` אמיתיים (עדיין לא מתקיימים כי C89 לא הופעל).

---

## 3. Completed Since Last Update

שרשרת תיקוני `/update` + Business Memory (07-08/07/2026, PRs #255-#263, #265):

1. **BUG-078/079** — webhook היה מדלג על ה-pending state של `/update` (photo/document וגם טקסט חופשי בורחים לזרימה הכללית) — שני ה-bypass נסגרו.
2. **C99** — חילוץ טקסט ממסמכים שנשלחים באמצע `/update` (feature, לא באג).
3. **BUG-080** — 7 נקודות כתיבה ששלחו `datetime` מלא לשדות Date-בלבד ב-Airtable (422) → `.date().isoformat()`.
4. **BUG-081 + תיקון סופי (PR #263)** — Business Memory קיבלה שדה `Domain` ייעודי; אחרי 3 סבבי תיקון על בסיס production evidence, הפתרון הסופי: `domain` **לא נכתב ל-`Tags` בכלל** (רק ל-`Domain`), `media` תוקן ל-Title Case, וקריאת ההקשר (`get_recent_business_context`) עברה לסנן לפי `Domain`.
5. **BUG-077** (root cause) — `propose_action()` מאמת כעת `requires_approval` מול `tool_registry.needs_approval()` fail-closed — ✅ merged.

**✅ PRODUCTION VERIFIED במלואו (08/07/2026):** `/update` נבדק ב-**כל 6** ה-domains ברצף אמיתי (Telegram) — `נדל"ן`/`SaaS`/`מדיה`/`ייבוא`/`כללי`/`כספים`, כולם → `Other` → טקסט חופשי → נשמר בהצלחה, "📌 Other | <domain>" הוצג נכון בכולם, **אין 422** באף אחד. מאמת בפועל את השרשרת המלאה כולל PR #265 (רווח בסוף, המיפוי הנכון הסופי): BUG-078 (טקסט מגיע ל-`capture_text`), BUG-080 (Event Date — נקודת הכתיבה של `cmd_update.py` בלבד), BUG-081+#265 (Domain נכתב עם הערך המדויק לכל 6 המפתחות, לא Tags). **לא מאומת עדיין:** C99 (חילוץ מסמך), שאר 6 נקודות הכתיבה של BUG-080 (`media_handler.py`, `cmd_decision.py`).

**פער ידוע שנותר, לא בטיפול:** `weekly_summary.py::_group_by_domain()` ו-Business Memory listing ב-`tma_api.py` עדיין קוראים `Tags[0]` כ-domain — ישברו בשקט על רשומות חדשות. לא דחוף — שני הצרכנים כבויים (`FEATURE_WEEKLY_SUMMARY` off, TMA business-memory screen לא בשימוש).

---

## 4. Next Priorities

1. **🔴 C81-FU** — Recovery: לאמת תוצאת שליחה בפועל לפני סימון `recovery_count`/הושלם (כרגע גדל גם כשההודעה לא נמסרה).
2. **🔴 C82-FU** — Gate מרכזי אחד ל-`EMERGENCY_STOP_AUTOMATION` לפני כניסה לכל scheduler job (היום נאכף רק ב-followup/payment reminders).
3. **Production verification** של שאר שרשרת BUG-078..081/C97-C99 — כל 6 ה-domains כבר מאומתים; נותר C99 (חילוץ מסמך), שאר 6 נקודות הכתיבה של BUG-080, + בדיקת commit hash מול Render.
4. **🟡 C84-C86** — TMA approvals TTL/freshness check, structural test ל-orphan approval actions, coverage מטריציוני ל-Emergency Stop על כל scheduler jobs.
5. **Decision Hub activation gate** — `FEATURE_DECISION_HUB` יישאר כבוי עד שיתקבל production evidence אמיתי ל-BUG-DH-03/04 (formula injection fix כבר ממוזג, חסר רק אימות live).
