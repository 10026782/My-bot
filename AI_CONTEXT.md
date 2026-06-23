# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.

**עודכן:** 2026-06-23
**עודכן על ידי:** Claude Code — daily briefing regen (git-verified `main` HEAD `01558a0`)

> מקור אמת: `ROADMAP.md` + `BOSS_CURRENT_STATE.md` (מיושן, 19/06) + `CHANGELOG.md` + git log. `CANONICAL_STATE.md` לא קיים בריפו. כאשר המסמכים סתרו זה את זה, עדיפות: main (git) > ROADMAP.md > AI_CONTEXT.md הקודם > BOSS_CURRENT_STATE.md.

---

## 1. Executive Summary
- `main` = `01558a0`. Identity → Router → Context → Agent + Approval flow (3-state, fail-closed) — **תקינים ופעילים בפרודקשן**.
- **F16 Media Layer הושלם (7/7 batches)** — code-complete ומחובר ל-pipeline החי, אך **כבוי בפרודקשן** מאחורי `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` (off by default). דורש יצירת טבלת "Media Files" ידנית ב-Airtable לפני הדלקה.
- **N07/N08/N09/N11/N12 הושלמו** (Schema Governance, CI/CD, Monitoring, Finance Pulse wiring, Daily Git Audit scheduler) — כולם code-complete ומוזגים; N12 ו-N10 (Rollback) נשארים flag-off/planned בהתאמה.
- כל פיצ'רי הצמיחה (Lead Scoring/Memory/Followup, N02-N04) — **קוד מוכן, דגלים כבויים כברירת מחדל**, אפס תעבורת ייצור אמיתית אומתה עד כה.
- 4 באגים תועדו ונסגרו בסשן האחרון (BUG-013/014/015/016) — כולם **מוזגים ל-main**, טרם אומתו בפרודקשן.
- מצב Render: דיפלוי קודם אושר ע"י המשתמש ל-`d91a9df`; **לא אומת עצמאית מהסביבה הזו** (אין egress/Dashboard access).
- WhatsApp outbound (Meta Cloud API) — חסום, ממתין לאישור Meta.

## 2. Current System State

**עובד (Operational):** Identity/Router/Context/Agent core; `tool_registry`+`dispatcher` enforcement; Approval flow (`verify_execution()` נבדק לפני דיווח הצלחה); Airtable single-write-path gateway (`tools/airtable_gateway.py`); Daily Digest; Payment Reminder; Twilio signature validation; TMA auth+CORS; Screen Filter Gateway; Finance Pulse (Payments/Expenses חיים); A32 anti-hallucination evidence gate (כולל Drive מאז BUG-014).

**חלקי (קוד קיים, כבוי/לא מאומת):** Lead Scoring/Memory/Followup (`LEAD_SCORING`/`LEAD_MEMORY`/`FOLLOWUP_AUTOMATION`=off, שרשרת תלויה); F16 Media Layer (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`=off, טבלת Media Files חסרה ב-Airtable); Approval Policy Emergency Window/OTP (`EMERGENCY_WINDOW`=off); N12 Daily Git Audit (`GIT_AUDIT_SCHEDULER`=off); WhatsApp outbound = honest stub; Google integrations (OAuth נדרש).

**חסום:** F05 WhatsApp Production (Meta approval). TMA Activity Feed / Assets / Personal Mode (`coming_soon` stubs, כנים).

## 3. Completed Since Last Update

**BUG_AUDIT_LOG.md תוקן (commit `881b41e`/`01558a0`):**
- **BUG-013** (PR #117, `aae59c4`) — קובץ Telegram oversized (voice/photo/document >50MB) הוריד את כל הקובץ *לפני* בדיקת גודל; כעת `_classify_size(file_size)` נבדק מול `message.voice/photo/document.file_size` **לפני** `bot.get_file()`/`download_file()` — דוחה מיידית עם `FILE_TOO_LARGE`, ללא הורדה כושלת/תקועה.
- **BUG-014 תיעוד תוקן** — סטטוס "Merged: לא עדיין" היה שגוי; PR #115 מוזג בפועל (`cf0ded7`, אומת מול GitHub API).
- **BUG-015** (PR #108, `095b59d`) — `MediaFileFields` לא היה ב-`TABLE_CLASS_MAP` (`schema_audit.py`) → N07 לא בדק את טבלת Media Files בכלל; נוסף ל-map, וטבלה חסרה ב-live עכשיו `❌`+exit 1 (לא `⚠️` שקט).
- **BUG-016** (PR #108, `095b59d`) — תזכורת אבטחה שבועית הציגה תמיד "999 ימים" כי שום קוד לא כתב ל-`LAST_SECURITY_REVIEW`; נוסף `record_security_review()` הכותב ל-`/tmp/security_review.json` (תבנית זהה ל-emergency flags).

**ניקוי ענפים (סשן 23/06/2026):** audit מלא של 37 ענפי `claude/*` לא ממוזגים → 34 נמחקו (ממוזגים בפועל/זהי-תוכן/orphan/collision שנפתר בעבר). שני ענפים הכילו עבודה אמיתית שחולצה לפני מחיקה: N12 (PR #108) ותיקון תיעוד C56 (PR #112). מסמך `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` שוחזר ישירות ל-`main` (`783a680`).

**F16 Media Layer — הושלם במלואו (PR #96/#97/#98/#99/#100/#101):** STT (Whisper), Drive upload, Airtable Media Files metadata, `app.py`/`tma_api.py` hooks, schema — קוד שלם ומחובר, flags כבויים. תוקנו בדרך 2 באגים חוסמים (`upload_file()` kwarg שגוי, כשל Airtable מוסתר) ו-2 gaps קטנים (`send_chat_action`, `linked_lead_id` ב-TMA).

**N07/N08/N09/N11 — תוקן תיעוד:** שלושתם תועדו בטעות כ-`🔲 PLANNED` ב-ROADMAP אף שהיו ממוזגים; תוקן אחרי grep ישיר על `main` (לא git log/PR status).

**שאר ה-PRs האחרונים (לפירוט מלא ראו `CHANGELOG.md`/`CHANGE_CONTROL_LOG.md`):** C22 Weekly Business Summary (PR #94, off by default), C53/O4 Screen Filter Gateway + Finance Pulse, C53-A structured tool-result contract + A32 hardening (PR #80), C54/C55 Business Update command + Origin Lead linking (PR #85/#86), C56 Approval Policy stack (PR #69, off by default).

## 4. Next Priorities
1. **לאמת BUG-013/014/015/016 בפרודקשן בפועל** — כולם מוזגים ל-`main`, אפס אימות ידני עד כה (קובץ >50MB אמיתי / Drive evidence gate / N07 מול live Airtable / security-review persistence).
2. **F16 — הדלקת flags** (`FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD`) — אך ורק אחרי יצירת טבלת "Media Files" ידנית ב-Airtable.
3. **להריץ N07 (`tools/schema_governance.py`) מול live Airtable** — עדיין לא רץ פעם ראשונה (אין credentials בסביבת sandbox).
4. **לאמת מצב Render בפועל מול `main` HEAD (`01558a0`)** — לא ניתן מהסביבה הזו (egress חסום); סיכון פתוח שתועד כבר בגרסאות קודמות.
5. **החלטה על הדלקת N02-N04** (Lead Scoring/Memory/Followup) — קוד מוכן ושלם, אפס תעבורת ייצור אמיתית אומתה עד כה.
