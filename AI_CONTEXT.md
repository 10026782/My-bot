# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-26
**עודכן על ידי:** Claude (scheduled daily-briefing routine) — סנכרון מול `main` בפועל (git log/merge-base), לא מול תיעוד

> מקור אמת: `main` (git) > `ROADMAP.md` > `AI_CONTEXT.md` הקודם > `BOSS_CURRENT_STATE.md`/`CHANGELOG.md`. `CANONICAL_STATE.md` לא קיים בריפו. **תיקון חשוב היום:** `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` תיארו את C60 ו-F17 כ"לא ממוזגים" — אומת ישירות מול `git merge-base --is-ancestor` שהם **כן ממוזגים ל-main בפועל** (ראו §3). `BOSS_CURRENT_STATE.md` ו-`CHANGELOG.md` מיושנים — לא משקפים שום דבר מ-25-26/06 (C58-F17, BUG-018, F52); אל תסתמך עליהם לאירועים האחרונים.

---

## 1. Executive Summary
- **`main` = `78f9bae`** (אומת `git fetch origin main` + `git log`, branch העבודה תואם 1:1).
- **תיקון תיעוד קריטי:** C60 (Tool Context Awareness, PR #152) ו-F17 (Decision Hub Stage 2, PR #157) **ממוזגים בפועל ל-`main`** — ROADMAP.md/CHANGE_CONTROL_LOG.md עדיין מתעדים אותם כ-"קוד מוכן, לא ממוזג". מקור התיעוד טעון תיקון; הקוד עצמו פעיל ב-main.
- **Decision Hub (N13/F17) — Stage 0 עד Stage 2 שלם וממוזג**, כולו מאחורי `FEATURE_DECISION_HUB` (כבוי כברירת מחדל). אפס שינוי התנהגות בפרודקשן כל עוד הדגל כבוי.
- **BUG-018** (mojibake encoding corruption ב-132 שורות `app.py`) — מוזג ל-main (PR #154), לא אומת בפרודקשן.
- **F52** — audit תיעודי בלבד (3 מסמכים תחת `docs/f52/`: tool map, contract/bypass map, state flow map) — אפס שינוי קוד.
- Identity → Router → Context → Agent + Approval flow (3-state, fail-closed) — **תקינים ופעילים בפרודקשן**, ללא שינוי מאז C57.
- כל פיצ'רי הצמיחה (Lead Scoring/Memory/Followup) ו-F16 Media Layer — קוד מוכן, דגלים כבויים, אפס תעבורת ייצור אומתה.
- מצב Render: לא ניתן לאימות עצמאי מהסביבה הזו (אין egress/Dashboard access) — דיפלוי קודם אושר ע"י המשתמש ל-`d91a9df`, לא עודכן מאז.

## 2. Current System State

**עובד (Operational):** Identity/Router/Context/Agent core; `tool_registry`+`dispatcher` enforcement; Approval flow; Airtable single-write-path gateway; Daily Digest; Payment Reminder; Twilio signature validation; TMA auth+CORS; Screen Filter Gateway; Finance Pulse (Payments/Expenses); A32 anti-hallucination evidence gate.

**חלקי (קוד קיים, כבוי/לא מאומת):** Decision Hub Stage 0-2 (`FEATURE_DECISION_HUB`=off — Trust Layer, AI Conflict Detection Lazy+Cached, Confidence Score, Evidence Graph; 4 שדות Airtable חדשים שנדרשים ל-F17 עדיין לא נוצרו ביד בבסיס החי); Lead Scoring/Memory/Followup (off); F16 Media Layer (off, טבלת "Media Files" חסרה ב-Airtable); Approval Policy Emergency Window/OTP (off); N12 Daily Git Audit (off); WhatsApp outbound = honest stub; Google integrations (OAuth נדרש).

**חסום:** F05 WhatsApp Production (Meta approval). TMA Activity Feed/Assets/Personal Mode (`coming_soon` stubs, כנים).

## 3. Completed Since Last Update (מאז ה-AI_CONTEXT הקודם, 25/06)

- **C60 Tool Context Awareness — מאומת כממוזג ל-`main` (PR #152)**, לא רק "code done on branch" כפי שתועד קודם. `last_tool_result` + הזרקה ל-system prompt + פתרון כינויי-הצבעה עבריים — פעיל בקוד הליבה (לא flag-gated), לא אומת בפרודקשן.
- **F17 Decision Hub Stage 2 (Smart Trust Layer) — מאומת כממוזג ל-`main` (PR #157)**, לא "code done, לא ממוזג" כפי שתועד ב-ROADMAP/CHANGE_CONTROL_LOG. AI Conflict Detection (Lazy+Cached, מוגבל ל-5 קריאות Claude/ריצה), Confidence Score, Evidence Graph, Missing Evidence Detector — כולו מאחורי `FEATURE_DECISION_HUB` (off). 4 שדות Airtable חדשים נדרשים לפני שהפרסיסטנס המלא יעבוד (כרגע best-effort, מוצגים תקין בטלגרם בכל מקרה).
- **BUG-018** — מוזג ל-main (PR #154): תיקון corruption של 132 שורות עברית/סימבולים ב-`app.py` שנגרם מ-decode שגוי (cp1255 במקום UTF-8). לא אומת בפרודקשן (הודעת בוט אמיתית בעברית).
- **F52 tool architecture audit** — שלוש תוספות תיעוד (`F52_CURRENT_TOOL_MAP.md`, `F52_CONTRACT_COVERAGE_MAP.md`/`F52_BYPASS_MAP.md`, `F52_STATE_FLOW_MAP.md`) — docs-only, אפס שינוי ב-`app.py`/Airtable.
- C59 Decision Hub Stage 1 (Trust Layer, PR #151) — ממשיך להיות ממוזג, ללא שינוי סטטוס.

## 4. Next Priorities
1. **תקן את ROADMAP.md/CHANGE_CONTROL_LOG.md** — סמן C60 ו-F17 כ"ממוזג ל-main" (לא "code done, branch only") לפי §3 לעיל, לפני שעוד אג'נט מבוסס על הסטטוס השגוי.
2. **החלטה על הדלקת `FEATURE_DECISION_HUB`** — Stage 0-2 שלמים על main; דורש יצירת 4 שדות Airtable חדשים (Evidence Ids/Summary, Confidence Score, Missing Evidence) לפני אקטיבציה מלאה.
3. **לאמת בפרודקשן בפועל**: BUG-013/014/015/016/018 (כולם מוזגים, אפס אימות ידני) — בעיקר BUG-018 (הודעה עברית תקינה אחרי deploy).
4. **F16 — הדלקת flags** רק אחרי יצירת טבלת "Media Files" ידנית ב-Airtable.
5. **להריץ N07 (`tools/schema_governance.py`) מול live Airtable** — לא רץ פעם ראשונה (אין credentials בסביבת sandbox); וכן לאמת מצב Render מול `main` HEAD (`78f9bae`) — לא ניתן מהסביבה הזו.
