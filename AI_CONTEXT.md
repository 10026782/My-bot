# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד
> למתוכנן), `BUG_AUDIT_LOG.md`, `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו. `BOSS_CURRENT_STATE.md` מיושן (עודכן לאחרונה
> 26/06/2026) — נשמר כארכיון, לא מקור אמת נוכחי.

**עודכן:** 2026-07-15 · **main:** `5c94e20` (PR #341, Single-Speaker fallback fix) · **סטטוס:** ראו §1

**⚠️ פער תיעוד:** `ROADMAP.md` (עודכן לאחרונה 13/07, `b962773`) ו-`CHANGELOG.md`/`CHANGE_CONTROL_LOG.md`/`BUG_AUDIT_LOG.md` (עוצרים באותה נקודה, PR #326) **לא** משקפים ~15 PRs שמוזגו מאז (#327-#341): Phase 4B-1A/1B/2 (durable proposals+claims, Approvals→projection), כלי ה-rollout ל-Phase 4B, תוכנית F52 Unified Approval Runtime, ותיקון Single-Speaker (PR #341). שום דבר מזה **לא** נבדק כרגע מול פרודקשן — לא VERIFIED, לא CRITICAL, פשוט UNVERIFIED. יש לרענן את ROADMAP/CHANGELOG/CHANGE_CONTROL_LOG/BUG_AUDIT_LOG (כולל בומפ `עודכן:` ב-ROADMAP) לפני שסומכים עליהם לסטטוס עכשווי.

---

## 1. Executive Summary

- הבוט חי בפרודקשן (Telegram + WhatsApp/Twilio) על `main`, Identity→Router→Context→Agent, Airtable כ-CRM. אין שינוי במסלול הזה מהעדכון הקודם.
- מאז 13/07: שרשרת ארוכה של עבודת תשתית על **Phase 4B — Atomic Claims** (durable ActionContract persistence ב-PostgreSQL, "Approvals" הופך ל-projection לא-אותנטי של ActionContracts, כלי rollout מלאים — canary/readiness/reconciliation/repair). כל זה **קוד מוכן, לא מופעל**: `FEATURE_ATOMIC_CLAIMS` ו-`FEATURE_ACTION_CONTRACT_PERSISTENCE` שניהם עדיין כבויים כברירת מחדל (`feature_flags.py:50-51`), הפעלה בפרודקשן **טרם התבצעה**.
- תוכנית ה-rollout שתועדה (`docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md`) היא flip בינארי + קנרי יחיד — **אין** בה תוכנית %-staged (5%→25%→100%) שנזכרה קודם כ"נדרש"; אם רוצים staged rollout אמיתי, הוא עדיין לא נכתב.
- נפתח `docs/architecture/f52-unified-approval-runtime/` — תוכנית מיזוג ל-runtime אישורים אחד. **תכנון/מחקר בלבד, אפס קוד** — README מסמן "Planning Gate", CUTOVER_PLAN עדיין draft ריק, 9 החלטות תכנון (D-001..D-009) סגורות ב-14/07 אך ללא build.
- **PR #341 (החדש ביותר, `e26df5a`)** תיקן 2 באגים חיים ב-Single-Speaker: (א) הודעת אישור-ממתין נדרסה בטעות בפולבאק כשלון גנרי; (ב) טקסט הצלחה כפול הוצג פעמיים. **קוד מוכן, ממוזג — לא נבדק בפרודקשן עדיין.**
- שני items בעדיפות 🔴 דחוף מסבבים קודמים (C81-FU, C82-FU) — אין ראיה שטופלו, נחשבים עדיין פתוחים.
- נזק ידוע שהיה קיים ב-Airtable (רשומת ליד `recRvK6hFTNgyj8ag`, "יעל רייס" עם `Name` שגוי) — לא אומת שתוקן ידנית מאז הדיווח הקודם.
- אין harness pytest — בדיקות הן סקריפטים עצמאיים; CI מריץ את כולן על כל PR/push ל-main.

---

## 2. Current System State

**עובד בפרודקשן:** Telegram + WhatsApp(Twilio) inbound עם Identity resolution; Airtable Gateway כנתיב-כתיבה יחיד (fail-closed אטומי, SPEC A1); Approval flow (Airtable `Approvals` כרגע עדיין הנתיב האמיתי — ה-projection החדש דורם); Daily Digest; Finance Pulse; TMA; Cost Watchdog; C94 Ingress Envelope (ON כברירת מחדל); צינור חילוץ-ליד מ-WhatsApp.

**מיושם חלקית / ממתין להפעלה (קוד מוכן, flag כבוי):**
- **Phase 4B — Atomic Claims (PostgreSQL):** durable proposal persistence (4B-1A), durable execution-ledger lifecycle (4B-1B), Approvals הופך ל-projection לא-אותנטי + `tma_write` דורש claim חי לפני כתיבה (4B-2). כל השכבה נעולה מאחורי `FEATURE_ACTION_CONTRACT_PERSISTENCE`+`FEATURE_ATOMIC_CLAIMS` (שניהם OFF) — "dormant" במפורש בקוד. כלי rollout (`tools/phase_4b_*`) קיימים ומתועדים אך לא הופעלו על פרודקשן.
- **F52 Unified Approval Runtime** — תוכנית מיזוג ל-4 מנגנוני אישור קיימים למנוע אחד. תכנון בלבד (README="Planning Gate", CUTOVER_PLAN=draft ריק). אין קוד production.
- C90 (xlsx/csv), Lead Scoring/Memory/Followup (N02-N04), Decision Hub (Stages 0-6) — ללא שינוי מהעדכון הקודם: code done, flags off.
- `IngressEnvelope.normalized_text` נבנה ונזרק (BUG-102); `EvidenceTrace` נבנה ולא נשמר ל-DB (BUG-103); Core Reasoning Layer ללא קוראים חיים (BUG-104) — ללא עדכון סטטוס.

**חסום:**
- Decision Hub activation — ממתין ל-production evidence.
- WhatsApp outbound אמיתי — honest stub, ממתין ל-Meta Cloud API.
- C93 (OCR) — חסום על צבירת `AgentObservation`.
- BUG-099b.1, PR #341 — ממוזגים, לא deployed/verified בפרודקשן.

---

## 3. Completed Since Last Update (13/07 → 15/07)

1. **Phase 4B-1A (PR #329, #331) — Durable ActionContract proposals**: פרסיסטנס אמיתי (PostgreSQL) + recovery lookups, מחליף את ה-in-memory contract store. Fail-closed על שגיאות lookup.
2. **Phase 4B-1B (PR #332) — Durable execution-ledger lifecycle**: מחזור-חיים מלא (`ActionContract` lifecycle) נשמר, לא רק ב-RAM.
3. **Phase 4B-2 (PR #333, #334) — Approvals הופך ל-projection לא-אותנטי**: טבלת Airtable `Approvals` היא עכשיו תצוגה בלבד של ה-`ActionContracts` הקנוני; `tma_write` (כלי חדש, internal-only) דורש claim חי (`EXECUTING`) מה-repository לפני כל כתיבה — סוגר עקיפת-dispatch ישירה וזיוף-זהות בקבלות. פעיל רק כששני הדגלים ON (שניהם כרגע OFF) — dormant בפרודקשן.
4. **Phase 4B rollout tooling (PR #335, #336, #337, #338)** — סקריפטי readiness/canary-verify/reconciliation/repair-projections (`tools/phase_4b_*`) + `docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md` (gates G1-G6, deploy sequence, rollback). **הערה חשובה:** זו תוכנית flip בינארי + קנרי יחיד — לא תוכנית %-staged כפי שצוין קודם כדרוש.
5. **F52 Unified Approval Runtime — פתיחת תוכנית (commit ba20796, 14/07)**: מסמכי תכנון/מחקר בלבד תחת `docs/architecture/f52-unified-approval-runtime/` (audit maps, decision log עם 9 החלטות D-001..D-009, cutover plan כ-draft ריק). אפס שינוי קוד.
6. **Stage-B identity fixture fixes (PR #339, #340)** — תיקוני קובץ-בדיקה בלבד (`test_stage_b_full_suite.py`), אין שינוי בקוד production.
7. **PR #341 — Single-Speaker: תוקנו 2 באגים חיים** (תקרית `contract_id=9c6ff34e...`): (א) `sanitize_agent_response()` דרס בטעות הודעת אישור-ממתין שכבר נשלחה בפולבאק-כשלון גנרי; תוקן ע"י sentinel דיכוי. (ב) `ActionGateway._execute_contract()` הציג טקסט הצלחה כפול; תוקן להחזיר רק את `compose_status_reply()`. 23 בדיקות חדשות + מלוא ה-suite עובר. **קוד מוכן, ממוזג — לא נבדק בפרודקשן.**
8. **אין רישום** ל-#2-#7 לעיל ב-`BUG_AUDIT_LOG.md`/`CHANGE_CONTROL_LOG.md` — פער תיעוד פעיל, ראו §0.

---

## 4. Next Priorities

1. **רענון תיעוד** — לעדכן `ROADMAP.md` (כולל בומפ `עודכן:`), `CHANGELOG.md`, `CHANGE_CONTROL_LOG.md`, `BUG_AUDIT_LOG.md` עם כל סבב Phase 4B-1/4B-2/F52/PR #341 — 4 המסמכים כרגע לא-עקביים מול מצב `main` בפועל.
2. **🔴 Production-verify PR #341** — לוודא ב-Render שה-hash החדש פרוס, ואז לשחזר את תקרית ה-Single-Speaker המקורית (`contract_id=9c6ff34e...`) ולוודא ששני התיקונים אכן מונעים אותה חי.
3. **החלטה על Phase 4B staged rollout** — אם דרוש %-staged אמיתי (5%→25%→100%) לפני הפעלת `FEATURE_ATOMIC_CLAIMS`/`FEATURE_ACTION_CONTRACT_PERSISTENCE` בפרודקשן, התוכנית עדיין לא קיימת בכתב — לכתוב אותה או להחליט במפורש על מודל ה-flip-הבינארי+קנרי הקיים.
4. **🔴 C81-FU / C82-FU** — אימות משלוח בפועל ב-Recovery; gate מרכזי ל-`EMERGENCY_STOP_AUTOMATION` לפני כל scheduler job. שני הפריטים משבבים קודמים, עדיין ללא ראיה שטופלו.
5. **תיקון ידני** לרשומת `recRvK6hFTNgyj8ag` ("יעל רייס") ב-Airtable — לא אומת שבוצע.
