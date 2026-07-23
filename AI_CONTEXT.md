# AI CONTEXT

> קרא אותי לפני כל דבר אחר. זהו מסמך תדרוך (briefing) תמציתי, לא תיעוד מלא.
> למקור אמת מלא: `ROADMAP.md` (מתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו. `BOSS_CURRENT_STATE.md` ארכיון היסטורי (עודכן לאחרונה
> 26/06/2026) — **לא** מקור אמת נוכחי. **main גובר על כל מסמך תכנון בכל סתירה.**
> **פער תיעוד ידוע:** `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` לא עודכנו מאז 21/07/2026 (עד N16/PATCH
> 3B), אך `main` התקדם משמעותית מעבר לזה (PR #440–#448, כולל Cost Telemetry, BUG-129/130/133/134/135,
> ומסמכי TurnCoordinator). מסמך זה נכתב ישירות מ-`main` (`5e691ea`) + `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md`,
> לא מ-`ROADMAP.md` בלבד, כדי לגשר על הפער.

**עודכן:** 23/07/2026 · **main:** `5e691ea` (מיזוג PR #448)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio), Identity→Router→Context→Agent, Airtable כ-CRM יחיד — ללא שינוי במסלול הזה בסבב הזה.
- **Emergency Stop (PATCH 3B) הושלם ואומת בפרודקשן ישירות ע"י הבעלים** — 5 דגלי `EMERGENCY_STOP_*` דביקים ב-Airtable (שורדים restart אמיתי), TMA UI עם כפתורי Stop/Clear מלאים כולל Stop All.
- **סבב תיקוני-באג נרחב באישור/ניתוב-הודעות (BUG-111 עד BUG-127, כולל 114/115/116/117/121-124) — כולם ✅ VERIFIED IN PROD** עם evidence מלוגים אמיתיים.
- **Cost Telemetry Reliability (`usage_events`) — shadow בלבד.** לא מזיז את ה-trigger החי (`COST_WATCHDOG_LIVE=false`); PR3 (cutover) חסום בכוונה עד שיצטברו ימי-נתונים מול חיוב פרודקשן.
- **שני באגים פתוחים, לא מטופלים, ממתינים להחלטת owner:** BUG-130 (עדכון-ליד קיים מנותב כיצירת-ליד חדש) ו-BUG-134 (מרוץ TTL גנרי מול C84 שעלול להשאיר Approvals row תקוע `pending` שקרי).
- **TurnCoordinator / Cross-Layer Authority Contract V1 (PR #446/#447)** — יוזמת תכנון חדשה למיזוג BUG-104/F52/Approval layer; **תכנון בלבד, אפס קוד runtime**. Phase 2 Shadow Planning סטטוס סופי: `READY FOR OWNER DECISION` (לא לביצוע), 3 החלטות פתוחות.
- **פער תיעוד פתוח:** `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` לא עודכנו מאז 21/07/2026 למרות ~9 PRs נוספים שמוזגו מאז (#440–#448). `BUG_AUDIT_LOG.md` גם מציג "Merged: ⏳ טרם" שגוי עבור BUG-129/133/135 — כולם בפועל כבר מוזגו ל-main (מאומת ב-git log), התיעוד לא עודכן אחרי המיזוג.

---

## 2. Current System State

**עובד בפרודקשן, מאומת:**
- Identity→Router→Context→Agent; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed).
- Approval flow: TTL אכיפה בטלגרם (BUG-112) ו-TMA (C84, 24h); תיקוני BUG-111/114/115/116/117/121-124 (batch/domain lead-parsing, confirm-word hijack ע"י contracts ישנים, Tier-4 false-positive, context-interrupt amplification, `/status` crash, pending-approval UX) — כולם עם evidence production.
- Emergency Stop: 5 דגלים דביקים ב-Airtable, `is_enabled()`/`set_flag()` מיירטים אותם, מנגנון `/tmp` הישן הוסר לגמרי. TMA Stop/Clear מלא.
- F52 Unified Status Formatter + RP5 Evidence Finalizer — **shadow logging פעיל בפרודקשן בפועל** (evidence בלוגים אמיתיים לרוב מצבי הסיווג); `enforce`/`on` **לא** הופעלו.

**מיושם חלקית / flag off / shadow:**
- Cost Telemetry (`core/usage_telemetry.py`, PostgreSQL `usage_events`) — shadow-only, מחווט ל-6 נקודות-קריאה אמיתיות (Anthropic + OpenAI Whisper), לא מניע את ה-trigger החי. PR3 (cutover מ-`cost_monitor.py`) לא נפתח.
- BUG-104 Core Reasoning (Phases 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests, `FEATURE_CORE_REASONING_LEADS_STATE` off/shadow. Phase 2A.0 (ניקוי סכמה) עדיין SPEC-בלבד.
- TurnCoordinator Contract V1 — תכנון בלבד (`docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` + `turn-coordinator/`), `PLANNING BLOCKED`/`READY FOR OWNER DECISION`, אין flag ואין קוד.

**חסום / פתוח:**
- BUG-130 — עדכון-ליד קיים מנותב ליצירת-ליד חדש; רשום, לא תוקן.
- BUG-134 — TTL גנרי (`ActionContractRepository`, 24h) עלול ליירט contract לפני שלוגיקת C84 מספיקה לרוץ; רשום, לא תוקן.
- RP5 enforcement — shadow evidence קיים לרוב מצבי הסיווג, טרם נאסף לכל 9 המצבים.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- ענף `claude/rp5-staging-fault-injection-v4akit` — staging-only בכוונה, לעולם לא ימוזג ל-main.

---

## 3. Completed Since Last Update

*(מקבץ PR #397–#448; לפירוט מלא ראה `BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` C156–C168)*

- **תיקוני אישור/ניתוב (BUG-111 עד BUG-127):** סדרת תיקונים ל-`ActionGateway`/`core/ingress_classifier.py`/`app.py` — חטיפת confirm-word ע"י contracts ישנים, false-positive של Tier-4 על מילים אנגליות, הכפלת burst קריאות Airtable, קריסת `/status`, חסימת פעולה חדשה ע"י תור אישורים ישן, false-positive של פסוקית הקשר. כולם ✅ VERIFIED IN PROD עם evidence מדויק מלוגים.
- **PATCH 3B הושלם:** Steps 2–6 + prerequisite (הקשחת CI מפני credentials חיים) + TMA frontend (#425, #427, #432, #433, #436) — Emergency Stop דביק לגמרי, אומת בפרודקשן כולל restart אמיתי.
- **Cost Telemetry Reliability:** PR1 (#435, תיקון BUG-131 — כתיבה שקטה שנכשלה) → hotfix (#437, תיקון BUG-132 — השוואת טקסט מול שדה DATE) → hotfix-followup (#438, תיקון smoke script) → PR2 (#439, `usage_events` חדש, shadow טהור).
- **BUG-129/131/132/133/135 תוקנו:** self-quote ("זיהיתי") ופקודת-מחיקה שהפיקו שם-ליד מזויף (#444); כתיבה שקטה ל-`AI_Usage_Daily` (#435); השוואת טקסט/DATE שגויה (#437); test שדלף 310 רשומות אמיתיות ל-Interaction Log בפרודקשן — תוקן + הרשומות נמחקו ע"י הבעלים (#442).
- **N16:** Git Audit הוצא לגמרי מהבוט העסקי (היה כפילות מול ה-Routine) — הבוט כבר לא נוגע ב-git כלל.
- **TurnCoordinator / Cross-Layer Authority Contract V1 (#446, #447):** מסמכי תכנון חדשים — שער חובה למניעת שינוי לא-מתואם בין 4 שכבות (Core Reasoning/TurnCoordinator/F52/Approval). נמצאה והוסרה התנגשות שם (`ActionFact`). Phase 2 Shadow תוכנן במלואו, מחכה להחלטת owner — **אין קוד production שהשתנה**.
- **`scripts/render_log_export.py` (#448):** כלי דיאגנוסטיקה אופליין לחילוץ/חיפוש לוגי Render — לא מיובא ע"י `app.py`, אין סיכון production.

**פער תיעוד היסטורי שנשאר פתוח:** `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` עדיין לא סונכרנו ל-#440–448; `BUG_AUDIT_LOG.md` עדיין מציג "Merged: ⏳ טרם" שגוי ל-BUG-129/133/135.

---

## 4. Next Priorities

1. **החלטת owner: BUG-130** — כיוון תיקון לעדכון-ליד-קיים המנותב כיצירה חדשה (מתח ארכיטקטוני מול השומר של BUG-094).
2. **החלטת owner: BUG-134** — כיוון תיקון למרוץ ה-TTL הגנרי מול C84 (Approvals row עלול להישאר `pending` שקרי).
3. **TurnCoordinator Phase 2 Shadow** — 3 החלטות owner פתוחות (סביבת staging, איחוד ActionGateway, scope של CapabilityScope) לפני שקוד shadow ראשון נכתב.
4. **המשך shadow soak ל-F52/RP5** — לצבור את שאר מצבי הסיווג הנדרשים לפני שיקול הפעלת `enforce`/`on`.
5. **סנכרון תיעוד** — לעדכן `ROADMAP.md`/`CHANGE_CONTROL_LOG.md` ל-PR #440–448 ולתקן את סטטוסי "Merged: ⏳ טרם" השגויים ב-`BUG_AUDIT_LOG.md`.
