# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד),
> `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`. `CANONICAL_STATE.md` **לא קיים** בריפו.

**עודכן:** 2026-07-11 · **main:** `20cdac7` (PR #291) · **סטטוס:** תדרוך קודם היה תקוע ב-PR #265 (07-08/07) — פער של 26 PR נסגר בעדכון הזה.

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, בנוי סביב Identity → Router → Context → Agent, Airtable כ-CRM.
- הסבב האחרון (09-10/07) סגר שרשרת batch lead-capture: BUG-058 (Tier-2 batch-confirm resolver, `session_store.py`/`core/lead_candidate_handler.py`) נבנה ומחווט, ובדיקה חיה שלו בפרודקשן חשפה 3 באגים נפרדים ב-upstream שנסגרו יחד תחת BUG-094 (חלון שם ±60 תווים "דולף" בין מועמדים סמוכים; dedup עיוור-לטלפון שהופך "דליפה" לכתיבה כפולה לאותה רשומה; דומייני-מטא של ה-Router `CRM`/`INTERNAL` שזלגו ל-`Domain` field של `Leads`/`Lead Events` וגרמו ל-422). `test_bug094_batch_name_bleed.py` 25/25.
- שרשרת אבטחה/ראוטר נוספת נסגרה: BUG-090 (הודעת חסימה נכונה לפי סוג פעולה ב-Leads write gate), BUG-091 (`_source` כבר לא נאמן מ-`tool_inputs` — תיקון privilege-escalation), BUG-092 (דחיות דטרמיניסטיות נחסמות *לפני* שה-Agent רץ בכלל, לא אחריו).
- שכבת Airtable Schema Governance הושלמה (PR3 series, כל השלבים ממוזגים): snapshot archive (PR3A), RuntimeSchemaProvider + canonical-snapshot fallback tier (PR3B/B.1), diagnostic CLI ידני (PR3C), ואימות ערכי select לפני כתיבה (PR2 rev.2).
- Anti-hallucination חוזק: guard מבני גנרי ל-claims על פעולות (יצירה/העברה/המשך) שאין להן כיסוי כלי אמיתי, וכמה תיקוני ניסוח כוזב קונקרטיים (הודעת "forward" מדומה ב-Restricted flow, "המשך" מדומה ב-Single-Speaker fallback).
- רוב דגלי הפיצ'רים (`FEATURE_AUTO_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`, `FEATURE_DECISION_HUB`) **כבויים בכוונה** — קוד מוכן/ממוזג, לא מופעל בפרוד. C89 נסגר רשמית כ-CLOSED/VERIFIED עם הדגל כבוי (החלטת בעלים מפורשת, לא production-verification במובן המקורי).
- שני items בעדיפות 🔴 דחוף **עדיין** פתוחים ולא טופלו מאז התדרוך הקודם: C81-FU (אימות משלוח ב-Recovery) ו-C82-FU (gate מרכזי ל-EMERGENCY_STOP_AUTOMATION).
- כלל ברזל: "הושלם" ≠ "מאומת". שום claim כאן לא production-verified אלא אם צוין כך במפורש.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (normalize→validate→audit, כולל אימות ערכי select כעת); Approval flow (ActionGateway + `tool_registry.enforce`) עם דחיות דטרמיניסטיות שמתבצעות לפני כניסה ל-Agent (BUG-092); Daily Digest; Finance Pulse; TMA (Leads/Projects/Game/Finance Pulse); Cost Watchdog; C94 Ingress Envelope (דגל ON כברירת מחדל); Airtable Schema Runtime Provider (Meta API חי → in-memory אחרון-טוב → snapshot archive → `schema_cache.json`, בסדר עדיפות הזה).

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- C89 Capture Policy (auto-write tiers) — נסגר כ-CLOSED/VERIFIED בהחלטת הבעלים, `FEATURE_AUTO_CAPTURE` נשאר כבוי בכוונה.
- BUG-058 Tier-2 batch-confirm resolver — קוד מוכן ומחווט, precedence מול Tier-1 ActionGateway מוכרע (Tier-1 מנצח תמיד).
- C90 (קבצי xlsx/csv), Lead Scoring/Memory/Followup (N02-N04) — code done, flags off, לא מאומת בתעבורה אמיתית.
- Decision Hub (Stages 0-6, F17-F22) — כל השלבים ממוזגים ל-main; `FEATURE_DECISION_HUB` כבוי, חסום עד production evidence (ראו חסימות למטה).
- N15 (Restricted-flow `notify_owner`) — שדה נקבע אך לעולם לא נצרך; נפתח 09/07, עדיין PLANNED, לא מומש.

**חסום:**
- Decision Hub activation — חסום ל-BUG-DH-03/04 (Formula Injection): התיקון עצמו **ממוזג** (PR #251), אבל עדיין אין production evidence שמאשר את זה live.
- WhatsApp outbound אמיתי — honest stub, ממתין לאישור Meta Cloud API.
- C93 (OCR/כרטיסי ביקור) — חסום על צבירת ≥2 שבועות נתוני `AgentObservation` אמיתיים (עדיין לא מתקיימים כי C89 לא הופעל).
- C87 Unified Approval Store — תכנון בלבד, חסום עד שC81-FU–C83 ייסגרו (C83 כבר סגור; C81-FU/C82-FU עדיין פתוחים).

---

## 3. Completed Since Last Update

תדרוך קודם היה מבוסס PR #265 (07-08/07); להלן עיקרי 26 ה-PR שנסגרו מאז (#266-#291), לפי נושא:

1. **Batch lead-capture hardening (BUG-058 + BUG-094, 09-10/07)** — Tier-2 batch-confirm resolver נבנה בפועל (הודעת "אישור קבוצתי" סוף-סוף מחוברת ל-resolver אמיתי, לא רק נכתבת ל-state). בדיקה חיה שלו בפרודקשן חשפה וסגרה 3 באגים ב-upstream: חלון-שם דולף בין מועמדים סמוכים, dedup עיוור-לטלפון, וזליגת דומייני-מטא (`CRM`/`INTERNAL`) לשדה `Domain` העסקי ב-`Leads`/`Lead Events` (422). `_lead_domain_key()` חדש סוגר את הפער השלישי.
2. **אבטחת ראוטר/אישורים (BUG-090/091/092/093)** — הודעת חסימה מדויקת יותר ב-Leads write gate; `_source` כבר לא נאמן ישירות מ-`tool_inputs` (סגר וקטור privilege-escalation); דחיות דטרמיניסטיות (BUG-041/058/070 guard coverage) קוצרות-מעגל לפני שה-Agent בכלל רץ; LL-13 double-execution fix אומת כבר ממוזג (תיעוד בלבד, לא קוד חדש).
3. **Airtable Schema Governance PR3 series** — snapshot archive scheduler job (PR3A), `RuntimeSchemaProvider` עם fallback chain מלא כולל canonical-snapshot tier (PR3B/PR3B.1), CLI אבחון ידני `tools/check_airtable_schema_runtime.py` (PR3C), ואימות ערכי select לפני כתיבה ב-gateway (PR2 rev.2). BUG-085 (`run_snapshot_archive()` לא כתב `Drift Detected`) נסגר בתוך אותה עבודה.
4. **Response contract + anti-hallucination hardening** — כתיבות Airtable מסוג fire-and-forget קיבלו visibility לכישלון (במקום להיבלע בשקט); בדיקות הצלחה מבוססות string/regex הוחלפו ב-`result.get("ok")` בכל הריפו; guard מבני גנרי חדש ל-claims על פעולות ללא כיסוי כלי, כולל תיקון סימטרי ל-claims מסוג CREATE (BUG-NEW-09 symmetry); שתי הודעות ניסוח כוזבות ספציפיות תוקנו (Restricted-flow "forward" מדומה, Single-Speaker fallback "המשך" מדומה).
5. **Business Memory Domain lookup** — מיפוי סטטי ל-`Domain` הוחלף בחיפוש live מול schema; `_save_to_business_memory` מחזיר עכשיו contract `{ok,...}` אמיתי במקום `None` גולמי.
6. **TMA schema alignment** — task/deal schema field values יושרו (PR #289).

---

## 4. Next Priorities

1. **🔴 C81-FU** — Recovery: לאמת תוצאת שליחה בפועל לפני סימון `recovery_count`/הושלם (כרגע גדל גם כשההודעה לא נמסרה). **עדיין פתוח.**
2. **🔴 C82-FU** — Gate מרכזי אחד ל-`EMERGENCY_STOP_AUTOMATION` לפני כניסה לכל scheduler job (היום נאכף רק ב-followup/payment reminders). **עדיין פתוח.**
3. **🟡 N15** — החלטה + מימוש: Restricted-flow `notify_owner` — לבנות מנגנון התראה אמיתי לבעלים או להסיר את השדה שנקבע ולעולם לא נצרך.
4. **🟡 C84-C86** — TMA approvals TTL/freshness check, structural test ל-orphan approval actions, coverage מטריציוני ל-Emergency Stop על כל scheduler jobs.
5. **Decision Hub activation gate** — `FEATURE_DECISION_HUB` יישאר כבוי עד שיתקבל production evidence אמיתי ל-BUG-DH-03/04 (formula injection fix כבר ממוזג, חסר רק אימות live).
