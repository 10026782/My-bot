# AI CONTEXT

> תדרוך יומי תמציתי לכל AI agent שמתחיל עבודה על הריפו — לא תיעוד מלא.
> מקור אמת מלא: `ROADMAP.md` (מתוכנן) · `BUG_AUDIT_LOG.md` (באגים) · `CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` (מוזג).
> `CANONICAL_STATE.md` **לא קיים בריפו**. `BOSS_CURRENT_STATE.md` הוא ארכיון היסטורי (עודכן לאחרונה
> 26/06/2026) — **אינו** מקור אמת נוכחי, לא נעשה בו שימוש למסמך הזה. **`main` גובר על כל מסמך תכנון.**
> כל טענה שלא אומתה ישירות מסומנת `UNVERIFIED` ולא `CRITICAL`.

**עודכן:** 30/07/2026 · **main:** `a89fc67` (מיזוג PR #502)

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio): Identity→Router→Context→Agent, Airtable Gateway כנתיב-כתיבה יחיד. לא השתנה בסבב הזה.
- **Emergency Stop (PATCH 3B): ✅ הושלם ואומת בפרודקשן ישירות** — 5 דגלים דביקים ב-Airtable שורדים restart אמיתי, TMA Stop/Clear מלא.
- **PR2 (Deterministic Approval Cost Cuts) מוזג ואומת חי בפרודקשן (30/07/2026):** `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, `FEATURE_ACTION_GATEWAY` — קוד ברירת-מחדל `false` בשלושתם, אך **הבעלים אישר ששלושתם `true` בפרודקשן כרגע**. Hotfix E ו-Hotfix C אומתו חי; Hotfix B לא ניתן לאימות חי (מסלול ישן רדום כש-PR2 דלוק, מאומת בבדיקת יחידה בלבד).
- **BUG-152 (חדש, לא תוקן):** בקשה חוזרת/דומה נעצרה פעם אחת ע"י ה-Agent ורק בשליחה חוזרת נוצר כרטיס אישור. לא root-caused — נצפה כתופעת-לוואי של בדיקה אחרת, לא שוחזר במבודד.
- **שישה באגים פתוחים ממתינים להחלטת owner:** BUG-130, BUG-134, BUG-136, BUG-137, BUG-138 (`UNVERIFIED`), BUG-139 — פירוט ב-§2.
- **TurnCoordinator / Cross-Layer Authority Contract:** תכנון בלבד, אפס קוד runtime, חסום על 3 החלטות owner.
- **Cost Telemetry (`usage_events`):** shadow בלבד, לא מניע את ה-trigger החי (`COST_WATCHDOG_LIVE=false`).
- **פער תיעוד ידוע:** הבריפינג הקודם צבר עשרות תוספות מצטברות בלי לרענן את הגוף הראשי; המסמך הזה נכתב מחדש מהמקורות (`ROADMAP.md`/`CHANGELOG.md`/`BUG_AUDIT_LOG.md`) ולא מהעתקת התוספות.

---

## 2. Current System State

**עובד בפרודקשן, מאומת:**
- Identity→Router→Context→Agent; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed).
- Approval flow בסיסי: תיקוני BUG-111 עד BUG-127 (TTL, disambiguation, `/status`, pending-queue UX) — כולם עם evidence production.
- Emergency Stop: 5 דגלים דביקים, `is_enabled()`/`set_flag()` מיירטים אותם, מנגנון `/tmp` הישן הוסר לגמרי.
- PR2 track: Hotfix E (PR #497) ו-Hotfix C (PR #498+#499) — Verified בפרודקשן. BUG-151's יכולת עסקית הכללית (יצירת Tasks עם תאריך יעד) — Verified בפרודקשן, אך שני התיקונים הספציפיים (הממיר positional, חריגת mutation-budget) עדיין לא נבדקו בנתיב-הכשל המדויק שלהם.

**מיושם חלקית / flag off / shadow:**
- F52 Unified Status Formatter + RP5 Evidence Finalizer — shadow logging פעיל בפרודקשן; `enforce`/`on` לא הופעלו. RP5 מכסה 5/9 מצבי סיווג נדרשים.
- Cost Telemetry (`core/usage_telemetry.py`) — shadow-only, מחווט ל-6 נקודות-קריאה אמיתיות, לא מניע trigger. PR3 (cutover) לא נפתח.
- Context Librarian Consumption Enforcement — Phase 1 (checklist + `verify-consumption` CLI + ledger validation) מוזג. Phase 3 (CI blocking gate) לא מיושם, ממתין לשימוש-Phase-1 אמיתי.
- BUG-104 Core Reasoning (Phases 1/1.1/2A.1/2A.2) — ממוזג ומאומת ב-tests, flag off/shadow.
- F52 Message Contract Envelope (D-012) — `MessageContract` אושר כקלט הפורמטר הקנוני היחיד; תיעוד-תכנון בלבד, implementation לא מאושר.

**חסום / פתוח:**
- **BUG-130** — עדכון-ליד קיים מנותב כיצירת-ליד חדש; רשום, לא תוקן.
- **BUG-134** — TTL גנרי (24h) עלול ליירט contract לפני C84; אומת ישירות מ-Airtable (3 רשומות `pending` תקועות 4–14 יום).
- **BUG-136/137** — "בצע שוב \<קוד\>" עטוף ב-markdown bold נופל ל-Agent; הודעת עדכון-ליד מרכיבה domain פנימי בלי תווית. נוגעים ב-Approval layer — טעונים שער Cross-Layer Authority Contract לפני מימוש.
- **BUG-138** (`UNVERIFIED`) — כפתור אישור טלגרם לא נעלם אחרי אישור/דחייה; השערה מבוססת-קוד בלבד.
- **BUG-139** — RP5 shadow: `response_claim=failure/mixed` בלי tool call כלל (47% mismatch בדגימה); root cause לא אותר.
- **BUG-152** (חדש) — ראו §1; לא root-caused.
- ממצא נפרד, לא דחוף: `airtable_get` לא חושף למודל enum ערכי-domain תקפים, כך שהוא מנחש (למשל `hr` במקום `recruitment`) — הבעלים ביקש לטפל בזה במסגרת תכנית ה-Agent Surface Reduction, לא כ-hotfix נפרד.
- TurnCoordinator Contract V1 — `PLANNING BLOCKED`/`READY FOR OWNER DECISION`, אין flag ואין קוד.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.

---

## 3. Completed Since Last Update

- **PR2 — Deterministic Approval Cost Cuts** (PR #491 preflight + PR #492 impl, מוזג) — resolver דטרמיניסטי מוקדם ל-approve/reject/pending-query, מאחורי `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`. Review רב-שכבתי מצא ותיקן 10 ממצאים לפני מיזוג (כולל ביטול-בשקט של הגבלת 24h על terminal replay).
- **סבב אימות חי בפרודקשן (30/07/2026)** — Hotfix E, Hotfix C ו-BUG-151 (יכולת עסקית כללית) אומתו חי מול `my-bot-jqz2.onrender.com`; Hotfix B אומת בבדיקת יחידה בלבד (מסלול-ישן רדום).
- **BUG-151 fix** (PR #494) — הממיר תומך ב-1/2 ערכים positional ל-Tasks; כשל canonicalization לא נספר יותר נגד תקציב ה-mutation; "כן"/"לא" בלי live contract כבר לא משחזר contract לא-קשור.
- **Context Librarian Consumption Enforcement Phase 1** (PR #490, מוזג) — `consumption_checklist()`, CLI `verify-consumption`, ולידציית ledger fail-closed.
- **F52 Message Contract Envelope D-012** (PR #480, מוזג) — `MessageContract` אושר כקלט קנוני יחיד לפורמטר; מיישב drift מ-PR #471 בלי מחיקה.
- **תיקון דליפת שם-טבלת-Airtable** (PR #479, מוזג) — `_describe_contract_for_reconfirmation()` כבר לא חושף שם-טבלה גולמי בהודעות fallback.
- **Single-Speaker Approval UX Base** (PR #471, מוזג) — `ApprovalLifecycleResult` כתוצאת-UX קנונית; דגל כרגע `true` בפרודקשן (אושר ע"י הבעלים 30/07, לא רק staging).
- **Emergency Stop PATCH 3B** — כל השלבים (2–6 + prerequisite + TMA frontend) הושלמו ואומתו בפרודקשן ישירות (restart אמיתי + clear מוצלח).

---

## 4. Next Priorities

1. **Root-cause BUG-152** — לשחזר במבוקד עם לוג מלא (candidate roots: היסטוריית-שיחה / דדופ-fingerprint / race זמנים).
2. **החלטת owner: BUG-130/BUG-134** — כיווני תיקון ללידים-קיימים המנותבים כיצירה, ולמרוץ ה-TTL הגנרי מול C84.
3. **החלטת owner: BUG-136/BUG-137** — דורשים שער Cross-Layer Authority Contract לפני מימוש (נוגעים ב-Approval layer).
4. **TurnCoordinator Phase 2 Shadow** — 3 החלטות owner פתוחות (סביבת staging, איחוד ActionGateway, scope של CapabilityScope) לפני קוד shadow ראשון.
5. **המשך shadow soak ל-F52/RP5** — לצבור את יתרת מצבי-הסיווג לפני שיקול הפעלת `enforce`/`on`.
