# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד
> למתוכנן), `BUG_AUDIT_LOG.md` (המקור **הכי עדכני** בפועל — ראה הערה למטה), `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו.

**עודכן:** 2026-07-13 · **main:** `b962773` (PR #326, P0 unhashable-Identity fix) · **סטטוס:** ראו §1

**⚠️ פער תיעוד שהתגלה בעת יצירת מסמך זה:** `ROADMAP.md` (עודכן לאחרונה 10/07), `CHANGELOG.md` ו-`CHANGE_CONTROL_LOG.md` (שניהם עוצרים סביב 08/07) **לא** משקפים סבב עבודה שלם מ-10-12/07 (SPEC A1, BUG-094..101, BUG-099b/099b.1, BUG-102..105) — כל הסבב הזה מתועד רק ב-`BUG_AUDIT_LOG.md`, שהוא כרגע המקור העדכני ביותר בפועל, לא שלושת המסמכים ש"אמורים" להיות מקור האמת. יש לרענן את שלושתם (כולל בומפ לתאריך `עודכן:` ב-ROADMAP) לפני שסומכים עליהם לסטטוס "עכשווי".

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, Identity→Router→Context→Agent, Airtable כ-CRM.
- סבב 10-12/07 סגר **SPEC A1** (כתיבות Airtable הופכות ל-fail-closed אטומי — dropped fields חוסמים כתיבה כליל, במקום payload חלקי בשקט) ושרשרת ארוכה של באגי חילוץ-ליד מ-WhatsApp (BUG-094..101, BUG-099b) — **רובם VERIFIED IN PROD** עם רשומות Airtable אמיתיות/לוגים חיים.
- **BUG-099b.1** (PR #306) התמזג הרגע ל-`main` (`a04ec47`) אך **עדיין לא deployed/verified בפרודקשן** — אין לטעון "תוקן בחיים" עד אימות Render hash + בדיקה חוזרת על הטקסט המדויק שגרם לבאג.
- נזק ידוע קיים כרגע ב-Airtable: רשומת ליד אמיתית (`recRvK6hFTNgyj8ag`, "יעל רייס") נכתבה בעבר עם `Name="חדרים קומה ראשונה"` (BUG-099 לפני התיקון) — טרם תוקנה ידנית.
- רוב דגלי הפיצ'רים עדיין כבויים בכוונה: `FEATURE_AUTO_CAPTURE`, `LEAD_SCORING`, `LEAD_MEMORY`, `FOLLOWUP_AUTOMATION`, `FEATURE_DECISION_HUB` — קוד מוכן/ממוזג, לא מופעל בפרוד. `FEATURE_INGRESS_ENVELOPE` נשאר יוצא-דופן: ברירת מחדל **ON**.
- שני items בעדיפות 🔴 דחוף מסבבים קודמים עדיין פתוחים ולא טופלו: C81-FU (אימות משלוח ב-Recovery) ו-C82-FU (gate מרכזי ל-EMERGENCY_STOP_AUTOMATION).
- 4 ממצאים חדשים מ-12/07 נרשמו בלבד, לא תוקנו: BUG-102/103/104 ("מנגנון קיים אך לא מחובר לחיים" — normalized_text נזרק, EvidenceTrace לא נשמר, Core Reasoning Layer ללא caller חי) ו-BUG-105 (טלפון בין-לאומי עם מקף פנימי נשמט בשקט).
- אין harness pytest — בדיקות הן סקריפטים עצמאיים (`python3 <file>.py`); CI מריץ את כולן על כל PR/push ל-main.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד, כעת **fail-closed אטומי** (SPEC A1); Approval flow; Daily Digest; Finance Pulse; TMA; Cost Watchdog; C94 Ingress Envelope (ON כברירת מחדל); צינור חילוץ-ליד מ-WhatsApp (batch/single, chat-export, bidi-control stripping) — מאומת חי אחרי BUG-094..101/099b.

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- C89 Capture Policy — נסגר CLOSED/VERIFIED בהחלטת הבעלים, `FEATURE_AUTO_CAPTURE` נשאר כבוי בכוונה.
- C90 (xlsx/csv), Lead Scoring/Memory/Followup (N02-N04) — code done, flags off.
- Decision Hub (Stages 0-6) — ממוזג ל-main; `FEATURE_DECISION_HUB` כבוי, חסום עד production evidence.
- `IngressEnvelope.normalized_text` נבנה אך נזרק בנתיב טקסט (BUG-102); `EvidenceTrace` נבנה ונרשם אך אף פעם לא נשמר ל-DB (BUG-103); Core Reasoning Layer / `leads_adapter.py` ממוזגים, אפס קוראים חיים (BUG-104).
- **Phase 4B0 — Atomic Claims (13/07, PR #325+#326, ראו C110/C111 ב-CHANGE_CONTROL_LOG.md):** `FEATURE_ATOMIC_CLAIMS` — קוד מוכן ומאומת ב-staging (real PostgreSQL + Telegram confirmation smoke, לוג חי מלא), **Production נשאר כבוי בכוונה** (`FEATURE_ATOMIC_CLAIMS=false`). שרשרת תקריות P0 אמיתיות תוקנה ברצף: (1) עקיפת רכישת claim בכל 4 מסלולי האישור, (2) אובדן זהות + סיווג-הצלחה שגוי דרך ה-wrapper האטומי, (3) `unhashable type: 'Identity'` שנבע מקריאה פוזיציונלית ל-executor האמיתי (`contract_id` הוחלף בשקט ב-`Identity`), (4) `dispatch_tool()` מעולם לא החזיר בפועל `DispatcherOutcome` — כל ביצוע אמיתי היה נכשל ב-"type mismatch" גם אחרי תיקון הזהות. עדיין נדרש לפני הפעלה: staged rollout plan (5%→25%→100%) ותקופת תצפית.

**חסום:**
- Decision Hub activation — התיקון ל-BUG-DH-03/04 (Formula Injection) ממוזג, עדיין אין production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין לאישור Meta Cloud API.
- C93 (OCR/כרטיסי ביקור) — חסום על צבירת ≥2 שבועות `AgentObservation` אמיתיים (לא מתקיימים כי C89 לא הופעל).
- BUG-099b.1 — merged אך לא deployed/verified (ראו §1).

---

## 3. Completed Since Last Update (08/07 → 12/07)

1. **SPEC A1 (10/07)** — `airtable_gateway.py`'s `airtable_patch`/`airtable_create` חוסמים כתיבה כליל אם `validate_airtable_fields()` השמיטה שדות, במקום לכתוב payload חלקי בשקט. משפיע על כל נתיב כתיבה בקוד. 32/32 טסטים.
2. **BUG-094/095/096/097 (10/07)** — שרשרת bleed בין לידים בדיקטציית batch: חלון-שם דלף בין מועמדים, `_at_find_lead` נפל ל-name-only match, domain מטא-router זלג לשדה Domain, טלפון פגום באמצע batch "בלע" בלוק שכן, ופעלי-כוונה (מעוניין/רוצה) נדבקו לשם. תוקן ב-`core/ingress_classifier.py`'s `_extract_lead_candidates()` (המימוש **החי** — לא `core/lead_candidate_handler.py`'s גרסה המתה, שתוקנה בטעות תחילה).
3. **BUG-098 (10/07)** — `_FOLLOWUP_WORDS` (substring match) תפס "קומה" בטעות כ-"ומה" (המשך-batch), חטף הודעות ליד חדשות והחזיר "✅ נשמר בהצלחה" כוזב פעמיים ברצף בלי שום ליד נוצר בפועל. תוקן ל-word-boundary regex. **VERIFIED IN PROD.**
4. **BUG-099/099a/099b (10-12/07)** — המשך חקירת BUG-098: חלון חילוץ-שם מעוגן ל-±80 תווים סביב הטלפון בלבד, בלי העדפה שם-מול-תיאור-נכס; שם אמיתי ("יעל רייס") הפך בפועל ל-`Name="חדרים קומה ראשונה"` ברשומת Airtable אמיתית (ראו §1). 099a הרחיב `_NAME_STOP`; **099b (PR #305)** שינה אסטרטגיה — פיצול הרצף לסגמנטים לפי מילות-עצירה ובחירת הארוך ביותר. **VERIFIED IN PROD** — 5 בדיקות חיות, 2 רשומות Airtable תקינות.
5. **BUG-101a/b/c (12/07, PR #304)** — ייבוא-ייצוא WhatsApp: תווי כיווניות (RLM/LRM) שברו זיהוי Tier-4; `_BLOCK_SEP` לא זיהה `[תאריך, שעה] שם:` כגבול-הודעה; `_SENDER_LINE_RE` לא סבל קידומת timestamp. **VERIFIED IN PROD** — grep-anchored על `origin/main` + Render deploy מאושר.
6. **BUG-099b.1 (12/07, PR #306, `a04ec47`)** — helper משותף `_is_name_stop_token()` סוגר call-site שני (`_candidate_confidence()`) שפספס טוקנים עם קידומת-יחס חד-אותית ("בקומה"), שהופקו כשם-ליד שגוי כשלא היה שם בכלל. **ממוזג ל-main, לא deployed/verified.**
7. **נרשמו (לא תוקנו):** BUG-102/103/104 (מנגנון-קיים-לא-מחובר), BUG-105 (טלפון בין-לאומי עם מקף פנימי נשמט בשקט), פער UX ב-preview שלא מאוחד (single-lead/batch/disambiguation) — כל אחד ב-PR נפרד עתידי.

---

## 4. Next Priorities

1. **🔴 Production-verify BUG-099b.1** — Render deploy hash מול `a04ec47`, ואז בדיקה חוזרת על הטקסט המדויק ("...בקומה חמישית טלפון...") שמצפה ל-`candidates=[]`/Tier 5, לא `Name="בקומה"`.
2. **תיקון ידני** לרשומת `recRvK6hFTNgyj8ag` ("יעל רייס", כרגע `Name="חדרים קומה ראשונה"`) ב-Airtable — נזק אמיתי שכבר קיים, לא תלוי בקוד.
3. **BUG-099c** — fallback form כש-LCH נכשל בחילוץ אבל ה-Router בטוח שזו כוונת create_lead (הפריט הבא בתור בשרשרת BUG-099).
4. **🔴 C81-FU / C82-FU** — אימות משלוח בפועל ב-Recovery לפני סימון הושלם; gate מרכזי אחד ל-`EMERGENCY_STOP_AUTOMATION` לפני כל scheduler job (היום נאכף רק ב-followup/payment reminders). שני הפריטים משבבים קודמים, עדיין לא טופלו.
5. **רענון תיעוד** — לעדכן `ROADMAP.md`/`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md` עם סבב 10-12/07 (כולל בומפ תאריך `עודכן:` ב-ROADMAP) — שלושתם כרגע לא-עקביים מול `BUG_AUDIT_LOG.md` (ראו §1).
