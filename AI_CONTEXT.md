# AI_CONTEXT.md
> קרא אותי לפני כל דבר אחר. אם אני ישן מ-7 ימים — עדכן אותי לפני שאתה עובד.
> זהו מסמך תדרוך (briefing), לא תיעוד מלא. לפרטים מלאים: `ROADMAP.md` (מקור אמת יחיד
> למתוכנן), `BUG_AUDIT_LOG.md` (המקור **הכי עדכני** בפועל — ראה הערה למטה), `CHANGE_CONTROL_LOG.md`.
> `CANONICAL_STATE.md` **לא קיים** בריפו.

**עודכן:** 2026-07-07 (מאוחר ביותר עוד, סבב אימות עצמאי) — סשן נפרד (C95A audit) אימת מחדש, ב-execution בפועל, את מצב BUG-077 (Tier-3 + root-cause) ו-BUG-DH-03/04: כולם **כן ממוזגים ל-`origin/main`** (`git fetch` + `git merge-base --is-ancestor` על `e1c0ea5`/`07caf9d`/`2e9bb57`, כולם ⊂ `4ba3002`, PR #254) — השורה הקודמת כאן ("🟡 קוד מוכן, טרם ממוזג") הייתה נכונה רק ברגע כתיבתה, לפני שה-PR התמזג, ולא עודכנה מאז. הותקנו `httpx`/`pyTelegramBotAPI` בסביבת ה-sandbox (היו חסרים) והורצו בפועל: `test_bugdh03_04_formula_injection.py` 15/15 ✅, `test_bug077_tier3_auto_capture_gate.py` 5/5 ✅, `test_action_gateway.py` 41/41 ✅, `smoke_tests.py`'s Decision Hub call-site governance check ✅ (מאשר גם F22/N14). ראה 0.24. **עדיין 🟡 NOT PRODUCTION-VERIFIED** — הרצה מקומית/sandbox בלבד, אין Render/Airtable חי בסבב הזה.
**עודכן על ידי:** Claude Code — doc-drift fix + test-execution verification בלבד (אין שינוי קוד בסבב הזה, מלבד סנכרון branch ל-`origin/main`), ראה 0.24 למטה

**⚠️ פער תיעוד שהתגלה בעת יצירת מסמך זה:** `ROADMAP.md` (עודכן לאחרונה 10/07), `CHANGELOG.md` ו-`CHANGE_CONTROL_LOG.md` (שניהם עוצרים סביב 08/07) **לא** משקפים סבב עבודה שלם מ-10-12/07 (SPEC A1, BUG-094..101, BUG-099b/099b.1, BUG-102..105) — כל הסבב הזה מתועד רק ב-`BUG_AUDIT_LOG.md`, שהוא כרגע המקור העדכני ביותר בפועל, לא שלושת המסמכים ש"אמורים" להיות מקור האמת. יש לרענן את שלושתם (כולל בומפ לתאריך `עודכן:` ב-ROADMAP) לפני שסומכים עליהם לסטטוס "עכשווי".

---

## 0.24 סבב אימות עצמאי — BUG-077/BUG-DH-03/04 היו כבר ממוזגים בפועל, לא זוהה כי `git fetch` לא הורץ קודם — 2026-07-07 (קרא לפני 0.23)

**מה קרה:** במהלך C95A audit session נפרד (`docs/audit/C95A_ARCHIVE_CARRY_FORWARD_GAP_REPORT.md`), הוצגה טענה שBUG-077 "מיושם, נבדק, ממוזג — PR #250" ו-BUG-DH-03/04 "תוקן, ממוזג — PR #251". הבדיקה הראשונה (`git branch -a`, `git log --all --oneline`) **לא כללה `git fetch` מוקדם**, ולכן לא ראתה את ה-commits/branch שכבר היו קיימים ב-`origin` — הניבה מסקנה שגויה ש"שום ראיה לא נמצאה". אחרי `git fetch origin` מפורש, אותם commits (`e1c0ea5`, `07caf9d`, `2e9bb57`) אותרו, ואומתו כ-ancestors אמיתיים של `origin/main` (`git merge-base --is-ancestor`).

**מה תוקן בסבב הזה (רק תיעוד + הרצת בדיקות, אין שינוי קוד):**
- `ROADMAP.md`: 2 מקומות תוקנו מ-"טרם ממוזג"/"לא ממוזג/מאומת עדיין" ל-"✅ ממוזג, 🟡 NOT PRODUCTION-VERIFIED".
- `BUG_AUDIT_LOG.md`: BUG-036/BUG-037 (`Merged: לא` → `✅ כן`) ו-BUG-077's root-cause subsection (`Merged: בתהליך` → `✅ כן`) עודכנו, עם evidence של `git merge-base --is-ancestor` וגם עם evidence חדש של הרצת הטסטים בפועל (לא רק grep על commit messages).
- `core/lead_candidate_handler.py`, `core/action_gateway.py`, `cmd_decision.py`, `decision_pipeline.py`, `tools/airtable_gateway.py` — סונכרנו לגרסת `origin/main` (fast-forward merge, `3a64c93..4ba3002`), אין diff/שינוי קוד נוסף בסבב הזה.

**הרצת בדיקות בפועל (לא רק "הקובץ קיים"):** הותקנו `httpx==0.28.1` ו-`pyTelegramBotAPI` בסביבת ה-sandbox (חסרו — `flask` נשאר חסר, קונפליקט `blinker` ברמת debian, לא קשור לריפו). לאחר ההתקנה:
- `python3 -m py_compile app.py cmd_decision.py decision_pipeline.py core/action_gateway.py tools/airtable_gateway.py core/lead_candidate_handler.py` → נקי.
- `python3 test_bugdh03_04_formula_injection.py` → **15/15 עברו**.
- `python3 test_bug077_tier3_auto_capture_gate.py` → **5/5 עברו**.
- `python3 test_action_gateway.py` → **41/41 עברו**, כולל לוג חי: `"[ActionGateway] propose_action: caller passed requires_approval=False for 'sheets_append' but tool_registry requires True — overriding to True (fail-closed, BUG-077)"`.
- `python3 smoke_tests.py` → 6/7 (הכשל היחיד: `flask` חסר בסביבה, לא קשור לקוד); "Decision Hub call-site governance" ✅ "7 Decision Hub entrypoints match their declared wiring state" — מאשר מכנית גם את מצב F22/N14 (`core.adapters.decision_adapter` wired כ-fallback, `core.reasoning_engines`/`leads_adapter` unwired) בלי להסתמך על תיעוד ידני.
- C20 (`/update` callback routing) אומת בקוד: `cmd_update.py:93,116` (`@bot.callback_query_handler`) + `298,307` (keyboards תואמים) + `app.py:2439-2454` (`bot.process_new_updates` מנתב).

**מה *לא* אומת (וחשוב להישאר `🟡`, לא `✅`):** אין גישה מכאן ל-Render deployment hash או ל-Airtable חי. כל commit message הרלוונטי (`07caf9d`, `2e9bb57`) כבר מציין בעצמו "not yet merged/verified" ברמת production — הסטטוס הנכון לכל שלושת הפריטים נשאר `🟡 MERGED, TESTS PASS LOCALLY, NOT PRODUCTION-VERIFIED`, לא `✅ VERIFIED IN PROD`.

**לקח לתהליך (לא רק לתיקון הזה):** כל בדיקת "האם commit/branch X קיים ב-origin" **חייבת** `git fetch origin` מפורש קודם — `git branch -a`/`git log --all` בלבד יכולים להראות מצב מקומי stale ולהוביל למסקנת "לא קיים" שגויה, בדיוק כמו שקרה כאן.

---

## 0.23 BUG-077 root cause נסגר — `propose_action()` מאמת מול `tool_registry.needs_approval()`, פרט ל-self_confirm — 2026-07-07 (קרא לפני 0.22)

**מה תוקן:** `core/action_gateway.py::propose_action()` — `approval_policy` (מ-`classify_approval_policy()`, BUG-076) מחושב לפני ה-cross-check, ומשמש גם אותו וגם את שדה ה-contract (לא קריאה כפולה). Override ל-`requires_approval=True` מתבצע **רק אם**: (א) `approval_policy != self_confirm`, (ב) `tool_registry.needs_approval(tool_name)` אמת, (ג) הקורא העביר `False`.

**תיקון עובדתי ל-SPEC שהתקבל:** אין פונקציה `tool_registry.get_tool_meta()` — האקססור האמיתי הוא `needs_approval(tool_name) -> bool`, כבר מכוסה ב-2 טסטים קיימים.

**קונפליקט שהתגלה ותוקן לפני push:** יישום ראשוני נאיבי (override גורף, בלי תנאי (א)) שבר 2 טסטים קיימים (`test_bug077_tier3_auto_capture_gate.py`, `test_c89_preview_confirmation.py`) — כי `_write_one_lead()` (`core/lead_candidate_handler.py`) קרא ל-`propose_action()` עם payload בלי מפתח `"fields"`, ולכן **תמיד** קיבל `approval_policy="approval"` (לעולם לא `self_confirm`), אף שמדובר בדיוק בתרחיש הבטוח (ליד חדש, שדות allowlisted) ש-BUG-076 התכוון לפטור מאישור. תוקן שני הקבצים יחד: ה-cross-check מכבד self_confirm, ו-`_write_one_lead()`'s payload נעטף תחת `"fields"` (זהה למה שנכתב בפועל), תואם למה ש-`_lead_safe_fields()`'s docstring כבר הניח כעובדה (`core/action_gateway.py:79`).

**בדיקה:** `test_action_gateway.py` — 3 טסטים חדשים (override ל-`sheets_append`, ללא-שינוי כשcaller כבר True, ללא-override ל-`airtable_get`). אפס רגרסיה: כל 50+ קבצי `test_*.py` ירוקים, `smoke_tests.py` ירוק, `compileall` נקי.

**Merged:** לא עדיין — ענף `claude/tool-approval-metadata-mi89lu`. **Deployed/Verified בפרודקשן:** לא.

**סטטוס:** 🟡 CODE DONE, NOT MERGED — BUG-077 סגור במלואו בקוד (root cause + תסמין Tier 3), ר' `BUG_AUDIT_LOG.md` BUG-077.

## 0.22 C83 — Single Policy Source סגור: `event_bus.ACTIONS_REQUIRING_APPROVAL` הוא alias ל-`tool_registry`, לא רשימה עצמאית — 2026-07-06 (קרא לפני 0.21)

**מה נסגר:** `ROADMAP.md` §C83 עבר מ-🔴 דחוף ל-✅ סגור. אומת בקוד: `event_bus.py:187-188` — `from tool_registry import TOOLS_REQUIRING_APPROVAL; ACTIONS_REQUIRING_APPROVAL = TOOLS_REQUIRING_APPROVAL` — כלומר אין שתי רשימות סותרות, יש alias טהור אחד למקור אחד. `test_c83_single_policy_source.py` (קיים) 3/3 עובר.

**תוצר לוואי חשוב — אותה בדיקה חשפה מחדש (לא פתחה) את BUG-077:** `propose_action()` ב-`core/action_gateway.py` עדיין סומך על `requires_approval` שמצהיר הקורא בלי לאמת מול `tool_registry.get_tool_meta()`. **תיקון לניסוח ראשוני שגוי בתוך אותה בדיקה:** הועלתה השערה ש-BUG-077 "לא חי" כי `FEATURE_AUTO_CAPTURE=false` — ההשערה נמצאה **שגויה בקוד**: Tier 3 (`_handle_mixed_batch`, `core/lead_candidate_handler.py`) קרא ל-`_write_one_lead` ללא שום בדיקת flag כלל — חי בפרודקשן היום, לא תלוי בדגל. ראו 0.21 למטה לתיקון בפועל.

**Merged:** ✅ כן — `main` `6f7062c` (PR #249, C83+merge master plan docs). **Deployed/Verified בפרודקשן:** לא נבדק.

**Docs:** `ROADMAP.md` §C83, `BUG_AUDIT_LOG.md` BUG-077 (addendum, לא רשומה כפולה), `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` (מסמך מאוחד חדש, ממזג `BOSS_ROADMAP_CONTINUATION.md`+`BOSS_UNIFIED_MASTER_PLAN_v2.md` שהועברו ל-`archive/`).

## 0.21 BUG-077 (חלקית) — Tier 3 mixed-batch מקבל את אותו auto-write gate כמו Tier 1/2 — 2026-07-06 (קרא לפני 0.20)

**הבעיה שתוקנה:** `_handle_mixed_batch()` (Tier 3 lead dictation, `core/lead_candidate_handler.py`) קרא ל-`_write_one_lead()` ללא תנאי לכל candidate high-confidence — עוקף לגמרי את `FEATURE_AUTO_CAPTURE` וגם כותב עדכון ללִיד קיים בלי שלב אישור, בניגוד לכלל C89 (עדכון ליד קיים תמיד עובר אישור). חי בפרודקשן, ללא תלות בדגל.

**מה תוקן:** פונקציה משותפת חדשה `_should_auto_write(auto_capture, existing_id)` — כתיבה אוטומטית רק ל-lead חדש לגמרי + auto_capture דלוק. Tier 1/2 עברו לשימוש בה (איחוד קוד, ללא שינוי התנהגות). Tier 3 קיבל את השער בפועל: `high`-confidence candidate נבדק מול `_should_auto_write()` לפני `_write_one_lead()`; אחרת עובר דרך `_propose_lead_write()` כמו Tier 1. כותרת סיכום ה-batch תוקנה גם היא — לא טוענת "X נשמרו" יותר כשבפועל רק נוצר contract ממתין.

**מה *לא* תוקן (במכוון, scope מוגבל):** ה-root cause הארכיטקטוני — `propose_action()` עצמו (`core/action_gateway.py`) עדיין לא מאמת `requires_approval` מול `tool_registry.get_tool_meta()`. קורא עתידי אחר שיצהיר ערך שגוי עדיין לא ייתפס. SPEC המקורי (מאושר ע"י הבעלים) הגביל את ההיקף לקובץ `lead_candidate_handler.py` בלבד — זה נשאר backlog item נפרד (`C-CORE-05` ב-`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §7).

**בדיקה:** `test_bug077_tier3_auto_capture_gate.py` (חדש, 5/5). אפס רגרסיה: כל 50+ קבצי `test_*.py` ירוקים, `smoke_tests.py` ירוק, `compileall` נקי.

**Merged:** ✅ כן — `main` (PR #250, commits `e1c0ea5`/`d3732cb`/`f0deee2`). **Deployed/Verified בפרודקשן:** לא.

**סטטוס:** 🟡 CODE DONE, MERGED, NOT PRODUCTION-VERIFIED — התסמין החי (Tier 3) סגור ובדוק; ה-root cause הארכיטקטוני נשאר 🟡 OPEN בנפרד (`BUG_AUDIT_LOG.md` BUG-077).

## 0.20 BUG-DH-03/04 — Formula Injection ב-Decision Hub תוקן: `_safe_formula_param()` — 2026-07-07 (קרא לפני 0.19)

**הבעיה שתוקנה:** Airtable formula strings משתמשים ב-`'` כתוחם מחרוזת. שלושה call sites הזריקו טקסט מבוקר-משתמש ל-`filterByFormula` דרך f-string גולמי, מאפשרים ל-`'` לשבור את גבול המחרוזת ולהזריק לוגיקת formula: `cmd_decision.py::_resolve_decision_ref` (ref), `decision_pipeline.py::maybe_supersede` (decision_id, Claim Topic — **תיקון לתפיסה שגויה שנבדקה בתחילת אותו סשן:** הקוד הרלוונטי ב-`decision_pipeline.py`, לא ב-`decision_ports.py` — `StoragePort.get()` שם הוא רק passthrough ל-`filterByFormula`, לא בונה אותו), ו-`core/lead_candidate_handler.py::_search_formulas` (name+phone — כבר עשה escaping דומה inline, הוחלף במקור משותף).

**מה נוסף:** `tools/airtable_gateway._safe_formula_param()` — helper יחיד, משותף לשלושת ה-call sites. אין builder חדש נפרד לכל סוג formula (SPEC מינימלי, מאושר ע"י הבעלים).

**בדיקה:** `test_bugdh03_04_formula_injection.py` (חדש, 15/15) — escaping unit tests + injection-blocked על שני ה-call sites שתוקנו + no-regression על `_search_formulas`. אפס רגרסיה על שאר הסוויטה, `smoke_tests.py` ירוק, `compileall` נקי.

**Merged:** ✅ כן — `main` (PR #251, commits `2e9bb57`/`011f5ea`). **Deployed/Verified בפרודקשן:** לא.

**Docs:** `BUG_AUDIT_LOG.md` BUG-036/BUG-037 עודכנו ל-🟡 CODE DONE, NOT VERIFIED; `ROADMAP.md` §BUG-DH-03/04 + 2 אזכורים נוספים עודכנו; `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §3.5/§5/§9 עודכנו.

**סטטוס:** 🟡 CODE DONE, MERGED, NOT PRODUCTION-VERIFIED — `FEATURE_DECISION_HUB` נשאר חסום עד production evidence.

## 0.19 doc-drift fix — C60 Tool Context Awareness was documented here as unmerged; it's merged (PR #152) — 2026-07-07 (קרא לפני 0.18)

**מה נמצא:** בזמן session נפרד (BUG-DH-03/04 formula-injection fix + grep audit), המשתמש שאל לבדוק את מצב C59/C60 ID-collision mapping מול `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` §9. הריצה `grep` הראתה ש-`ROADMAP.md` (עודכן 26/06/2026) כבר תיעד את C60 כמוזג ל-`main` (PR #152, commit `2d85b84`, merge `3e0094b`), אבל `AI_CONTEXT.md` (מסמך זה) עדיין טען ב-3 מקומות שונים ("Executive Summary" §1, "Completed Since Last Update" §3, "Next Priorities" §4) שC60 "לא ממוזג" — סתירה ישירה, בדיוק דוגמת ה-doc-drift ש-Rule 17 (Single Source of Status) נועד למנוע.

**אימות:** בדיקה מקומית ראשונה נכשלה כי ה-clone היה shallow (`2d85b84` לא valid object). לאחר `git fetch origin main --unshallow` — `git merge-base --is-ancestor 2d85b84 origin/main` **מאושר**. המשתמש גם אישר ויזואלית ב-GitHub ("✅ מוזג ל-main — PR #152, 'Merged', מאומת ויזואלית").

**מה תוקן:** שלוש הרשומות ב-`AI_CONTEXT.md` עודכנו לשקף מיזוג (§1/§3/§4, לפי מספור השורות הקודם). לא נמחק/שוכתב תוכן היסטורי — נוסף הבהרה בכל מקום שהמצב הקודם ("לא ממוזג") היה נכון רק ביום הכתיבה המקורי ולא עודכן מאז. §10 פריט 7 של ספק C60 (production verification בפועל — "העלה קובץ → 'תעלה לדסישנס' → BOSS זוכר") **נשאר פתוח** — המיזוג ל-main אינו production verification.

**הערה:** בזמן כתיבת רשומה זו, C83/BUG-077/BUG-DH-03/04 (0.22/0.21/0.20 למעלה) סומנו "מחוץ להיקף" — הם הושלמו ותועדו בהמשך אותו יום, לפי בקשת המשתמש.

---

## 0.18 BUG-076 — הפרדת "confirmation" מ-"approval" ל-lead capture בטוח — 2026-07-06 (קרא לפני 0.17)

**החלטת הבעלים בתגובה לתופעת-הלוואי של BUG-074 (0.17 למטה):** lead capture הוא low-risk ולא אמור לדרוש אישור owner — "confirmation" (המבקש מאשש שהמערכת הבינה נכון) שונה מ-"approval" (זהות מורשית מסמיכה פעולה רגישה). `approve()` **נשאר** שער האכיפה המרכזי — לא הוחלש גורפית, נוסף carve-out צר ומחושב מרכזית.

**מה נוסף:** `core/action_gateway.py`'s `classify_approval_policy(tool_name, tool_inputs)` — מחזירה `self_confirm` **רק** ל-`airtable_add`/`airtable_update` על טבלת `Leads`, עם שדות שכולם בתוך allowlist בטוח (יצירה: `Name/phone/channel/memory_key/domain/source/status/summary/Score/sender_id` — תואם בדיוק את `_write_one_lead()`; עדכון: **רק** `phone/summary/domain`, בלי status/score/tier/Owner/Next Action). כל דבר אחר (טבלה אחרת, כלי אחר, שדה מוגן) → `approval` (fail-closed, ברירת מחדל). `ActionContract` קיבל שדה `approval_policy` המחושב פעם אחת ב-`propose_action()` מתוך ה-payload בפועל (לא נסמך על טענת הקורא). `approve()`: כש-`approval_policy == "self_confirm"` — מאשר רק אם המאשר הוא **בדיוק** אותה זהות שביקשה **וגם** מחזיק role פנימי — לא "כל אחד יכול לאשש כל דבר".

**תוצאה מעשית:** manager/partner/employee יכולים כעת לאשש בעצמם ("כן") טיוטת יצירת/עדכון-בטוח של ליד ב-Tier-1 preview — בדיוק כפי שכתיבת ליד אוטומטית (`FEATURE_AUTO_CAPTURE`) כבר עושה היום ללא אישור נפרד. מחיקה, שדות מוגנים (סטטוס/ציון/שיוך), דילס/פיננסים/יוצא/bulk — עדיין דורשים owner/"actions.approve" בדיוק כמו ב-BUG-074, ללא שינוי.

**בדיקות:** `test_bug076_lead_confirmation_policy.py` (חדש, 32/32) — ראה BUG_AUDIT_LOG.md BUG-076 לפירוט מלא של כל התרחישים. `test_bug074_approval_authority.py` עודכן (תרחיש הבסיס הוחלף לטבלת "Deals" כדי להמשיך לבדוק את הכלל הכללי, לא את ה-carve-out) — נשאר 22/22. כל 50 קבצי `test_*.py` ירוקים חוץ מ-`test_document_converter.py` (לא קשור, חבילת pip חסרה).

**עדכון (06/07/2026) — מוזג ל-main:** commit `bb4b9ca` נדחף ל-`claude/quirky-cori-yrgrvb`, ואז מוזג ל-`main` (PR #246, merge commit `e1436e9`) — הענף נמחק לאחר המיזוג. **מאומת ישירות מול origin/main (לא לפי דיווח המשתמש בלבד):** `git fetch origin main` → head `e1436e9`; `git merge-base --is-ancestor bb4b9ca origin/main` → true; `git show origin/main:core/action_gateway.py | grep -c "classify_approval_policy\|approval_policy"` → 15; `git ls-tree -r origin/main --name-only | grep test_bug07` מציג את כל 5 קבצי הטסט החדשים. **לא בוצע עדיין:** deploy ל-Render, production verification.

---

## 0.17 Security Audit — `app.py`/`tma_api.py`/`tools/` + BUG-072/074/075 — 2026-07-06 (קרא לפני 0.16)

**ביקורת אבטחה** (DEV_MODE bypass, endpoints ללא auth, approval workflows, Twilio signature validation) הריצה מול הקוד הנוכחי על `main` (לא מול `BOSS_CURRENT_STATE.md`, שנמצא **סותר את עצמו** — טבלה אחת שם מסמנת DEV_MODE/`/worker/trigger`/`/health` כ-"✅ FIXED", בלוק "Security checklist consolidation" באותו קובץ מסמן את אותם ממצאים כ-"active risk to carry forward"). נמצא: DEV_MODE bypass **כבר תוקן ומאומת** בקוד (`tma_api.py:52-58`, `_DEV_MODE=False` קשיח + אזהרה אם `TMA_DEV_MODE` מוגדר) — ה-"carry forward" ב-`BOSS_CURRENT_STATE.md` **מיושן**. Twilio/Meta webhook signature validation תקינים ואוכפים fail-closed.

**3 ממצאים אמיתיים נתפסו ותוקנו באותו סבב (קוד + טסטים, לא merged עדיין):**

1. **BUG-074 (בטיקט: "BUG-073") — ActionGateway free-text confirmation מאפשר אישור עצמי.** `core/action_gateway.py`'s `approve()` הפך לשער האכיפה היחיד — מקבל `approver_role` חדש, חוסם (לא רק warning) אם למאשר אין `owner`/`"actions.approve"`, גם כשהמאשר הוא בדיוק אותה זהות שביקשה את הפעולה (וזה תמיד המצב במסלולי הטקסט החופשי). **קריטי לדעת:** זה לא היה תלוי-flag בלבד — מסלול Tier-1 lead-preview (`_propose_lead_write`, BUG-056) קורא ל-`route_confirmation_word()` **תמיד**, גם כש-`FEATURE_ACTION_GATEWAY` כבוי (ברירת המחדל) — כך שהבאג היה חי בפרודקשן היום עבור אישור-עצמי של כתיבת/עדכון ליד. **תופעת-לוואי שדורשת החלטת בעלים (לא הוכרעה כאן):** אחרי התיקון, staff שאינו owner (manager/partner/employee) כבר לא יכול לאשר בעצמו כתיבת ליד דרך Tier-1 preview ("כן") — אין עדיין מנגנון owner-notification לזרימה הזו (בניגוד ל-`_queue_approval` הרגיל). ה-contract פשוט יישאר pending עד תפוגה. ראו BUG_AUDIT_LOG.md BUG-074 לפירוט המלא + המלצה.
2. **BUG-075 (בטיקט: "BUG-074") — `/api/tma/upload` בלי role check.** נוסף `if identity.role not in {OWNER, MANAGER, PARTNER}: 403` — תואם למדיניות בכל endpoint כתיבה אחר ב-`tma_api.py`. דורם — `FEATURE_MEDIA_UPLOAD` כבוי כברירת מחדל.
3. **BUG-072 — raw chat_id/user_id בלוגים — כעת ✅ תוקן** (היה פתוח מ-05/07). נוסף `_sanitize_id()` (`app.py`) — sha256 fingerprint קצר לא-הפיך; 19 מופעים תוקנו (8 מהממצא המקורי + 11 נוספים שנתפסו בסריקה מלאה).

**⚠️ שים לב למספור:** הטיקט שהזמין את התיקון קרא לבאגים "BUG-073"/"BUG-074", אבל `BUG-073` כבר תפוס ב-`BUG_AUDIT_LOG.md` (ROADMAP-DOC-DRIFT-01, לא קשור) — התיקונים תועדו כ-BUG-074/BUG-075 כדי לא ליצור doc drift (בדיוק סוג הבעיה ש-BUG-073 עצמו עוסק בה). קוד/comments/שמות קבצי טסט (`test_bug074_approval_authority.py`, `test_bug075_tma_upload_role_gate.py`) עקביים עם המספור המתוקן.

**בדיקות:** 3 קבצי טסט חדשים (`test_bug072_log_sanitization.py` 7/7, `test_bug074_approval_authority.py` 22/22, `test_bug075_tma_upload_role_gate.py` 17/17). 7 קבצי טסט קיימים עודכנו (קריאות ל-`approve()`/`route_confirmation_word()`/וכו' קיבלו `approver_role=`) ונשארו ירוקים במלואם. כל 50 קבצי `test_*.py` בריפו הורצו מקומית — ירוקים חוץ מ-`test_document_converter.py` (חבילת pip `markdown` חסרה בסביבה, לא קשור לשינויים כאן).

**עדכון (אותו יום, 06/07/2026):** commit `54961f1` נדחף בפועל ל-`origin/claude/quirky-cori-yrgrvb` (`git push` הוצג ואומת). `BOSS_CURRENT_STATE.md` תוקן (הסתירה הפנימית שתועדה למעלה תוקנה בפועל — לא רק תועדה — ראה "Security checklist consolidation" בקובץ). **✅ מוזג ל-main בהמשך (ראה 0.18 למעלה)** — PR #246, `e1436e9`, מאומת ישירות מול origin/main. **לא בוצע:** deploy, production verification.

---

## 0.16 C94 — Production verification הושלם 4/5 — 2026-07-05 (קרא לפני 0.15)

**עדכון ל-0.15 (למטה) — כל הפריטים הפתוחים שם נסגרו חוץ מאחד, ע"י הבעלים:**
1. ✅ Telegram inbound live — verified (ראה 0.15).
2. ✅ WhatsApp/Twilio inbound live — verified (ראה 0.15).
3. ✅ File/xlsx/csv live — verified, **לאחר הדלקה זמנית** של `FEATURE_STRUCTURED_FILE_CAPTURE` לצורך הבדיקה בלבד. **אושר במפורש: הוחזר ל-OFF מיד אחרי** — אין שינוי מתמשך למצב הדגל בפרוד; ההתנהגות הקיימת (flag כבוי) ממשיכה כרגיל.
4. ✅ Render commit hash ל-C94 — verified: `41f3305` חי בפרוד. זה ה-merge commit של PR #241 (kill-switch) — ה-commit האחרון שנוגע בקוד בפועל; PR-ים מאוחרים יותר (#242 ואילך) הם docs-only, אין להם commit hash קוד חדש לאמת.
5. ➖ מסלול "classify_ingress exception graceful-degradation" — **test-covered only, לא נבדק בפרוד בכוונה.** זה נשאר כך במפורש — הפריט היחיד מתוך 5 שלא ניתן/כדאי לאמת על תעבורה אמיתית בלי לשבור prod בכוונה; ה-138 בדיקות (`test_c94_*.py`) הן ההוכחה היחידה לו, וזה מספיק.

**מסקנה: C94 production verification נחשב הושלם ברמה המעשית (4/5, הפריט ה-5 נשאר test-only בכוונה).**

**ראה:** ROADMAP.md §C94 (checklist מעודכן).

---

## 0.15 C94 — Production verification (Telegram+WhatsApp) ✅ בוצע ע"י הבעלים; BUG-072 נמצא (לא C94) — 2026-07-05 (קרא לפני 0.14)

**Production verification — 2/5 בוצעו, ע"י הבעלים (לא מה-sandbox):**
- ✅ הודעת Telegram אמיתית: נכנסה תקין, Identity resolved, Router עבד, `classify_ingress` לא הפיל את ה-router, אין `[C94] telegram envelope build/validate failed` בלוגים.
- ✅ הודעת WhatsApp/Twilio אמיתית: אותו דבר — נכנסה תקין, Identity resolved, Router עבד, אין `[C94] whatsapp envelope build/validate failed`; `MessageSid` אמיתי (`SM...`) נראה כ-`raw_ref`, מאשר שה-envelope נבנה ונוצל בפועל.
- ⚠️ עדיין פתוח: commit hash מול Render לא אומת במפורש; קובץ xlsx/csv אמיתי (תלוי הפעלת `FEATURE_STRUCTURED_FILE_CAPTURE`, עדיין כבוי); מסלול "classify_ingress נכשל בעדינות" עדיין לא נבדק על תעבורה live בכוונה.
- ✅ נצפה גם: WhatsApp outbound מציג "honest stub" — תואם את המתועד (`META_OUTBOUND_ENABLED=false`), לא ממצא חדש.

**BUG-072 (חדש, פתוח, לא תוקן, לא C94):** לוגים קיימים ב-`app.py` חושפים `chat_id`/`user_chat_id`/`owner_chat_id` גולמי (מספר טלפון/user_id) ב-8 מקומות לפחות (שורות 677/844/853/900/1241/1248/1477/1980/1995) — מאומת ב-grep, לא רק נטען. שונה לגמרי ממנגנון הסניטיזציה של C94 עצמו (`type(exc).__name__` בלבד) — זה gap ב-לוגים ישנים, קדם ל-C94. לא תוקן בסבב הזה — ממתין להנחיה. ראה BUG_AUDIT_LOG.md BUG-072.

**ראה:** ROADMAP.md §C94 (עדכון "Production verification" + "שני ממצאים נוספים").

---

## 0.14 C89 — סטטוס סגור: ✅ CLOSED/VERIFIED עם `FEATURE_AUTO_CAPTURE=false` (החלטת הבעלים) — 2026-07-05 (קרא לפני 0.13)

**החלטה מפורשת של הבעלים:** כל הממצאים הידועים מ-QA ידני על C89 (Stage 3 Capture Policy — טקסט) סגורים בקוד+טסטים, מאומת מחדש היום (לא רק נטען): IC ambiguous routing, Sessions root, Gateway path/no direct dispatch, Preview pending approval, Approval identity (Telegram+WhatsApp), Existing lead update UX, Dedupe/idempotency, Tier 4 hard-precedence, RAW-OBS. `FEATURE_AUTO_CAPTURE` **נשאר כבוי בפרודקשן בכוונה** — לא הופעל, לא ייבדק על תעבורה אמיתית.

**חשוב לדייק — זו לא "production verification" במובן שה-ROADMAP המקורי הגדיר לסעיף הזה** (הפעלת flag + מעקב `AgentObservation` על תעבורה אמיתית). זו סגירת scope מודעת: "קוד+טסטים מאומתים, הבעלים בוחר במפורש לא להפעיל." C90/C91/C92/C93 שהיו "חסומים על C89 production-verification" נחשבים כעת משוחררים תחת ההגדרה הזו (C90 כבר נבנה ומוזג ממילא מקודם, PR #228 — לא נגעתי בו).

**RAW-OBS re-verified (05/07/2026):** `test_c89_raw_obs.py` 15/15 — כל bullet באודיט שהמשתמש הציג הושווה מול הרצה אמיתית ותאם במדויק: raw_ref לעולם לא ריק בשום Tier (כולל flag OFF וכשל כתיבת Airtable), `AgentObservation(kind="capture_classification", contract_id=None)` נרשם לכל קריאה, ללא coupling ל-ActionContract.

**ראה:** ROADMAP.md §C89 לפירוט מלא + היסטוריית ה-PRs (BUG-047 עד BUG-065).

---

## 0.13 C94 — נוסף `FEATURE_INGRESS_ENVELOPE` kill-switch, default ON — 2026-07-05 (קרא לפני 0.12)

**למה:** 0.12 (למטה) תיעד ש-C94 (4 שלביו) נבנה בלי feature flag בכלל — equivalence-preserving בכל שלב, נחשב "always-on plumbing". זו סטייה מפורשת מ-`RELEASE_CHECKLIST.md`'s "Feature flag הוגדר וכבוי ברירת מחדל", ולא היה קיים kill-switch לחירום אם ה-envelope-building עצמו יתחיל לזרוק שגיאות בפרודקשן.

**התיקון (תוסף מינימלי, לא refactor):** שורה אחת בתנאי ב-`app.py`'s `run_agent()`:
```python
# לפני:
if raw_event_id and channel in ("telegram", "whatsapp"):
# אחרי:
if _flag_enabled("FEATURE_INGRESS_ENVELOPE") and raw_event_id and channel in ("telegram", "whatsapp"):
```
פלוס entry ב-`feature_flags.py`'s registry docstring + `_DEFAULTS` dict.

**קריטי — ברירת המחדל היא ON, לא OFF (הפוך מכמעט כל דגל אחר במערכת):** C94 כבר ב-`main` (וכנראה בפרוד). נבדק ישירות בקוד לפני push: `is_enabled()` על שם flag שלא מוגדר בכלל (לא ב-Render, לא בקוד) מחזיר `False` — ז"א אם `FEATURE_INGRESS_ENVELOPE` היה מקבל את ברירת המחדל הרגילה (Off), ה-deploy הזה עצמו היה מכבה שקט את כל C94 לפני שמישהו יספיק להגדיר את הדגל ב-Render. נפתר בדיוק כמו `IMPORT_DOMAIN` (הדגל היחיד האחר עם ברירת מחדל הפוכה): `_DEFAULTS["FEATURE_INGRESS_ENVELOPE"] = os.environ.get("FEATURE_INGRESS_ENVELOPE", "true")`.

**אימות לפני push (חובה, בוצע):**
- 138 הבדיקות (`test_c94_ingress_envelope.py` 57 + `test_c90_structured_file_capture.py` 41 + `test_c94_stage_c_telegram.py` 28 + `test_c94_stage_d_whatsapp.py` 12) הורצו **פעמיים**: פעם עם `FEATURE_INGRESS_ENVELOPE` לא מוגדר בסביבה בכלל (מדמה "עוד לא הוגדר ב-Render"), פעם עם `=true` מפורש — **תוצאה זהה, 138/138 בשתי הריצות**.
- נבדק גם `=false` במפורש: `build_telegram_envelope()` נקרא **0 פעמים** — ה-kill-switch באמת מדכא את בניית ה-envelope, לא no-op.
- אפס רגרסיה על `smoke_tests.py` + כל חבילת `test_*.py` הקיימת + `core/router/test_router.py`.

**Render env var אופציונלי חדש:** `FEATURE_INGRESS_ENVELOPE` — לא נדרש (default true, אין שינוי התנהגות אם לא מוגדר), אבל זמין כעת כ-kill-switch חירום (`=false` ב-Render מכבה את ה-envelope-building בלי לגעת בקוד).

**ראה:** ROADMAP.md §C94 (סעיף "נוסף `FEATURE_INGRESS_ENVELOPE`"), `feature_flags.py`'s registry docstring.

---

## 0.12 C94 — Unified Ingress Envelope + Evidence Trace, כל 4 השלבים מוזגו ל-main (PR #236–#239) — 2026-07-05 (קרא לפני 0.11)

**מה זה:** שכבת envelope/trace אחידה לכל מקור ingress (File/Telegram/WhatsApp-Twilio), כשכבה *לפני* הכניסה ל-`classify_ingress()`/C89/C90 — לא נוגעת בהם. `IngressEnvelope` (pre-classification, 7 שדות+envelope_id) ו-`EvidenceTrace` (post-classification, envelope_id FK + trace_id/attempt_no/status + classification_result/error/raw_ref/approval_contract_id/agent_observation) הם שני dataclasses נפרדים, לעולם לא ממוזגים. פירוט מלא + כל תיקוני ה-schema (A.1/A.2/A.3) ב-ROADMAP.md §C94.

**שלבים:** א׳ (schemas, `core/ingress_envelope.py`) → ב׳ (File adapter, `core/file_ingress_adapter.py`, + תיקון gap אמיתי: `classify_ingress()` לא היה עטוף try/except ב-`_process_structured_file_upload`) → ג׳ (Telegram, `core/telegram_ingress_adapter.py` + `core/router/capture_router.py`'s `classify_capture_ic()` עטוף — חריגה כבר לא מפילה את כל ה-router ל-Approval/UNKNOWN) → ד׳ (WhatsApp/Twilio, `core/whatsapp_ingress_adapter.py`; Meta Cloud API נשאר gated/לא נוגע במפורש). 138 בדיקות חדשות סה"כ (57+41+28+12), אפס רגרסיה בכל שלב.

**✅ נסגר — `FEATURE_INGRESS_ENVELOPE` נוסף כ-kill-switch (ראה 0.13 למעלה).** במקור C94 לא היה לו flag כלל — סטייה מ-`RELEASE_CHECKLIST.md`'s "Feature flag הוגדר וכבוי ברירת מחדל" שתועדה כפער מודע. עכשיו קיים דגל אמיתי, **default ON** (לא OFF כמו כמעט כל דגל אחר במערכת — כי C94 כבר במיין, ודגל שברירת המחדל שלו False היה מכבה אותו שקט ב-deploy). מתועד גם ב-`feature_flags.py`'s registry docstring.

**עדכון (ראה 0.13 למעלה): `_DEFAULTS` כבר לא מכיל רק `IMPORT_DOMAIN` — נוסף גם `FEATURE_INGRESS_ENVELOPE` (default true).**

**דגלים סמוכים (לא C94 עצמו, אלא ה-pipelines שהוא עוטף) — ברירת מחדל בקוד:
- `FEATURE_STRUCTURED_FILE_CAPTURE` (C90) — כבוי בקוד; לפי הסנאפשוט הקודם של קובץ זה (0.10) — עדיין כבוי בפרודקשן.
- `FEATURE_AUTO_CAPTURE` (C89) — כבוי בקוד; אותו סנאפשוט — עדיין כבוי בפרודקשן.
- `FEATURE_RAW_CAPTURE` — כבוי בקוד.
- `META_OUTBOUND_ENABLED` — כבוי בקוד; C94 Stage ד' מוודא במפורש (טסט source-level) שהוא לא נוגע בנתיב Meta כלל.
**אין גישת Render Dashboard מה-sandbox** — הטבלה הזו היא ברירות מחדל בקוד + מה שהסנאפשוט הקודם של הקובץ הזה טוען, לא אימות live. הבעלים צריך לבדוק בפועל ב-Render env vars.

**Render env vars חדשים ל-C94:** אין. נבדק בגרפ מלא על `core/ingress_envelope.py`/`file_ingress_adapter.py`/`telegram_ingress_adapter.py`/`whatsapp_ingress_adapter.py`/`capture_router.py` — אפס `os.environ`/`getenv` חדשים. C94 משתמש אך ורק בתשתית identity/classify_ingress/ActionGateway הקיימת.

**Production verification — עדיין לא בוצע (לא claim, פתוח בפירוש):**
1. אימות commit hash ב-Render מול `main` (`33aaafd`→`a4af2b8`→`b76bdc2`).
2. הודעת Telegram אמיתית מהבעלים — תשובה זהה למצב לפני C94 + אין `[C94] telegram envelope build/validate failed` בלוגים.
3. הודעת WhatsApp/Twilio אמיתית — אותו דבר, מחפשים `[C94] whatsapp envelope build/validate failed`.
4. העלאת xlsx/csv אמיתית ב-Telegram (רלוונטי רק אם `FEATURE_STRUCTURED_FILE_CAPTURE` יופעל) — תשובה זהה + אין שגיאות `[C94]` פר-שורה.
5. מסלול "חריגת classify_ingress מתדרדרת בעדינות" (התיקון המרכזי בשלב ג') — **לא ניתן/לא כדאי** להפעיל בכוונה על תעבורה אמיתית (זה יהיה לשבור prod בכוונה) — ההוכחה נשענת על 138 הבדיקות (`test_c94_*.py`), לא על trigger live.

**ראה:** ROADMAP.md §C94 (הפירוט המלא של כל שלב + תיקוני schema A.1-A.3), `core/ingress_envelope.py`/`core/file_ingress_adapter.py`/`core/telegram_ingress_adapter.py`/`core/whatsapp_ingress_adapter.py`/`core/router/capture_router.py`.

---

## 0.11 BUG-066/BUG-067 — Daily Tasks/Daily Digest hardening, מוזגו ל-main (PR #230, #231) — 2026-07-05 (קרא לפני 0.10)

**רקע:** המשתמש דיווח 4 באגים תפעוליים ב-Daily Tasks/Daily Digest/Shabbat Mode (BUG-DAILY-01..04, מתועדים ב-BUG_AUDIT_LOG.md כ-BUG-066..069) והחליט במפורש על סדר עבודה: PR #229 (מוזג) — תיעוד באגים בלבד, בלי תיקונים; אחריו PR נפרד לכל תיקון, אחד בכל פעם. BUG-068/BUG-069 (Daily Digest UX/compact mode) נדחו במפורש ל"אחר כך" ולא הוחל עליהם עדיין שום תיקון.

**PR #230 — BUG-067 (Shabbat gate, ענף `fix/bug067-shabbat-gate-digest`, מוזג `b31b880`/`cfa3205`):** `daily_digest.py` השתמש רק ב-`shabbat_status_message()` (טקסט תצוגה בלבד) ולא ב-`shabbat_safe()`/`should_send_now()` (הגייט האמיתי החוסם) — הדוח נשלח בפועל בשבת עם כותרת "מושהה" סותרת. תוקן ב-2 שורות בלבד ב-`scheduler.py`: `_job_daily_digest`/`_job_daily_collector` נעטפו ב-`shabbat_safe(...)`, אותו pattern בדיוק כמו 6 jobs אחרים. לא נגע ב-`build_digest()`/Airtable queries/scoring/formatting (מאומת: `smoke_tests.py` מחזיר בדיוק אותם 215 תווים). 3/3 בדיקות חדשות (`test_bug067_shabbat_gates_scheduled_digest.py`).

**PR #231 — BUG-066 (fail-safe פר-שלב, ענף `fix/bug066-daily-collector-fail-safe`, מוזג `aa30695`/`f2431e1`):** `daily_collector.py`'s `collect_daily()` עטף רק את קריאת ה-LLM ב-try/except; fetch history ו-`format_collector_message()` היו ללא הגנה, וה-wrapper החיצוני ב-`scheduler.py` תפס הכל בבלוק אחד גורף ללא per-step logging — לוג לא ציין איזה שלב נכשל, ו-`bot.send_message()` ללא timeout יכול היה להקפיא את ה-scheduler thread הבודד-thread-י. תוקן: `collect_daily()`/`send_daily_collector()` פוצלו ל-4 שלבים מבודדים (fetch history / LLM+parse / format / send), כל אחד עם try/except+logging (start/done/error) נפרד — הפונקציות לעולם לא raise-ות. נוסף `_SEND_TIMEOUT=15` מפורש ל-`bot.send_message()`. `scheduler.py`'s job wrappers קיבלו logging `[Scheduler] job=X ...` ברמת ה-job. כאגב תוקנה corruption/mojibake בשתי שורות טקסט ב-`daily_collector.py` (דומה ל-BUG-018), לא קשורה לבאג המקורי. 8/8 בדיקות חדשות (`test_bug066_daily_collector_fail_safe.py`), אפס רגרסיה על `test_bug067_...`/`test_c86_scheduler_emergency_matrix.py`/`smoke_tests.py`.

**מצב:** שני ה-PR מוזגו ל-`main` (מאומת `git log origin/main --oneline`: `f2431e1`, `cfa3205`). **לא אומת עדיין ב-production/Render** (deploy hash מול origin/main לא נבדק במסגרת session זה). BUG-068/BUG-069 עדיין פתוחים, לא הוחל עליהם תיקון — ממתינים להנחיה מפורשת מהמשתמש להתחיל.

**ראה:** BUG_AUDIT_LOG.md BUG-066/BUG-067, CHANGE_CONTROL_LOG.md C91/C92.

---

## 0.10 C90 — Structured File Capture, מוזג ל-main (PR #228) — 2026-07-05 (קרא לפני 0.9)

**החלטה מפורשת של הבעלים:** ROADMAP.md חוסם C90 על "C89 production-verified" (`FEATURE_AUTO_CAPTURE` פעיל בפרוד + נתוני `AgentObservation` אמיתיים) — עדיין לא קרה. הבעלים בחר במפורש לבנות את C90 עכשיו בכל זאת, מהטעם ש-C90 עצמו לא נוגע בנתיב auto-write כלל (ראו למטה) — לא ignored את הגייט, decision מתועד.

**גרסה ראשונה הייתה שגויה, תוקנה באותו PR לפני מיזוג:** commit ראשון (`da49d3e`) כפה Tier 4 גורף על כל source_type="file" — טיפל בקובץ שלם כ-blob אחד עם הודעת preview גנרית יחידה. לאחר שהמשתמש סיפק ספק מפורט יותר, תוקן (`f585d9d`) ל-**ingress source adapter בלבד**: `core/file_ingress_adapter.py` (חדש) מפרסר xlsx/csv לשורות; כל שורה עוברת, ללא special-casing, דרך אותה `_classify_ingress_core()`/`handle_lead_candidate()` שהודעת טקסט הייתה עוברת — שורה עם שם+טלפון ברור יכולה להיות Tier1 לגיטימי (לא Tier4 כפוי). כל שורה: `raw_ref`+`AgentObservation` נפרדים, ו-Tier1-3 יוצר ActionGateway contract נפרד הדורש אישור פרטני (אין bulk auto-approve). מגבלת בטיחות `_MAX_FILE_ROWS_PROCESSED=200` מדווחת במפורש. גייט: `FEATURE_STRUCTURED_FILE_CAPTURE` (כבוי כברירת מחדל) + `identity.is_internal` + סיומת/mime xlsx/csv.

**באג עצמאי שנתפס ותוקן לפני מיזוג:** `_row_to_text()` השתמש במפריד `" | "` שהתנגש עם `_TABLE_RE` הקיים (Tier4 hard marker) — כל שורה עם 3+ עמודות מאוכלסות (Name/Phone/City, מקרה טיפוסי) נכפתה Tier4 בטעות מסיבת formatting, לא תוכן אמיתי. תוקן ל-`", "`, ננעל ב-regression test נגד הפלט האמיתי של הפרסר (לא string מומצא).

**בדיקה:** `test_c90_structured_file_capture.py` (37/37) — פרסור xlsx/csv אמיתי, no-merging/no-dropping, Tier1 אמיתי (לא נכפה) מול Tier4 hard-marker (עדיין עובד), raw_ref+observation נפרדים לכל שורה, אין auto-write ללא אישור, שורה פגומה לא נעלמת, קובץ לא-תקין→שגיאה מפורשת, gating מלא. אפס רגרסיה על `test_media_layer.py`/`test_c89_raw_obs.py`/`test_c89_tier4_precedence.py`/`test_capture_router_wiring.py`/`core/router/test_router.py` + `smoke_tests.py`.

**PR:** #228 (`claude/ic-01b-ambiguous-prefix-routing-zp109k`) — 3 commits (docs + C90-v1-שגוי + C90-v2-מתוקן), מוזג `004fbf9`. ראה CHANGE_CONTROL_LOG.md C88, ROADMAP.md §C90.

**לא אומת:** production/Render. C91-C93 (voice/email/image) נשארים לא-ממומשים (Tier 5) — מחוץ לסקופ הזה.

---

## 0.9 5 באגים C89-family — PR #220–#224, כולם מוזגים — 2026-07-04 (קרא לפני 0.8)

**5 באגים, 5 PR, כולם מוזגו ל-`main` באותו סשן (רצף בודד: כל PR נפתח, נבדק, ומוזג לפני שה-PR הבא נפתח):**

- **BUG-IC-01B (PR #220, מוזג `b76e6d5`):** `core/router/intent_router.py`'s `_AMBIGUOUS_PHRASES` (BUG-048/BUG-IC-01) תפס רק ביטויים דו-משמעיים חשופים ("סטטוס", "למלא משימות"). ביטויים עם prefix טבעי ("אני צריך למלא משימות", "צריך סטטוס", "תעזור לי ...") נפלו ל-`Intent.UNKNOWN` → `Handler.AGENT` עם כלים מלאים במקום שאלת הבהרה — דווח חי: "אני צריך למלא משימות" גרם ל-`airtable_get table=Tasks` בפועל. נוספו 3 patterns עם prefix אופציונלי. 44/44 בדיקות. ראו BUG_AUDIT_LOG.md BUG-061.

- **BUG-SESSIONS-ROOT (PR #221, מוזג `eead2cc`):** קוד נכתב בכלי/סשן נפרד (ענף מקומי `codex/bug-sessions-root` על מכונת Windows של המשתמש) — סשן זה סקר, בדק עצמאית (worktree מבודד: 49 internal + 4 pytest + 4 קבצי רגרסיה קיימים ירוקים, `merge-tree` נקי מול `main`) ופתח את ה-PR (הכלי המקורי נחסם ע"י auth שגוי ב-`gh` CLI). `session_store.py`'s Session lookup עבר מ-regex-parsing על string מפורמט ל-`airtable_get_records()` מובנה (חדש, `tools/airtable_tools.py`) עם pagination + fail-closed על שגיאות; POST מותר רק אחרי lookup שמאשש 0 רשומות בבירור — מונע כפילות שקטה שהייתה קיימת חלקית עוד מ-BUG-047/BUG-NEW-12. ראו BUG_AUDIT_LOG.md BUG-063.

- **BUG-C89-APPROVAL-IDENTITY (PR #222, מוזג `717465a`):** `ActionGateway.propose_action()` נקרא עם `origin_chat_id=identity.memory_key` (לא external_id אמיתי). ב-approve, ה-executor קרא `resolve_identity()` מחדש על ערך זה → נפילה שקטה ל-`Role.READONLY` → owner שאישר "כן" נחסם ע"י ה-dispatcher. תוקן: `ActionContract` שומר actor identity (role/external_id/...) שנפתרה בזמן ה-propose; ה-executor משתמש בה ישירות. גם: preview עדכון-ליד-קיים אומר "מצאתי ליד קיים. לעדכן אותו?" ותמיד דורש אישור (גם עם `FEATURE_AUTO_CAPTURE=true`). 37+9+44 בדיקות. ראו BUG_AUDIT_LOG.md BUG-062.

- **BUG-C89-TIER4-PRECEDENCE (PR #223, מוזג `b7d8445`):** `_is_tier4()` (השער היחיד, נצרך ע"י `router.py` וע"י `lead_candidate_handler.py`) פספס כותרות טבלה ללא separator מפורש, טבלאות fixed-width עבריות, ופלטי סטטוס/ציון Airtable (`Status:`/`Score:`/`View in Airtable`/`memory_key`/`@lead`/`owner_dictation`) — נסחפו כ-Tier 1/2/3 והגיעו ל-Agent/ActionGateway בפועל. הורחב `_is_tier4()` היחיד (לא נוסף שער מקביל); מילת "airtable" בודדת הוגבלה למבנה נוסף כדי לא לשבור פקודת בדיקת-מערכת מפורשת ("תבדוק עכשיו את Airtable") — regression שנתפס ותוקן לפני פתיחת ה-PR. 13/13 בדיקות חדשות. ראו BUG_AUDIT_LOG.md BUG-064.

- **C89-RAW-OBS (PR #224, מוזג `68f8c97`):** `IngressClassification.raw_ref` היה ריק תמיד ("future — empty for now"), ואין AgentObservation על אף החלטת סיווג. `classify_ingress()` הוסבה לעטיפה סביב הלוגיקה המקורית (`_classify_ingress_core`) — לכל קריאה (Tier 1-5) נשמר `raw_ref` לא-ריק (Decision Inbox record id כש-`FEATURE_RAW_CAPTURE` פעיל [חדש, כבוי כברירת מחדל], אחרת fallback מקומי) ונרשם `AgentObservation(kind="capture_classification")` דרך ה-API הקיים בלבד של `ActionGateway.record_agent_observation(contract_id=None, ...)`. 14/14 בדיקות חדשות. ראו BUG_AUDIT_LOG.md BUG-065.
  **עדכון (PR #227, מוזג `ca207ba`):** אותה תיקון היה פונקציונלית נכון, אבל `_classify_ingress_core()` עדיין כתב `raw_ref=""` מילולית ב-8 return statements פנימיים (נדרס מיד ע"י ה-wrapper, אבל grep סטטי עדיין מצא hits ותועד ע"י המשתמש כ"עדיין לא תוקן"). תוקן: `raw_ref` קיבל ברירת מחדל sentinel (`__unset__`) במקום `""`, כך שאפס מופעים של `raw_ref=""` נותרים בקוד בפועל (מאומת: `grep -rn 'raw_ref=""' --include="*.py" .`). 15/15 בדיקות (כולל guard סטטי חדש). אין שינוי התנהגות — hardening בלבד נגד false-negative בביקורת מבוססת-grep.

**⚠️ תבנית תפעולית שחזרה כמעט בכל מעבר בין PR-ים באותו סשן (#220→#222→#223→#224→#225→#227) — תועדה כדי שלא תתפוס בהפתעה בפעם הבאה:** הריפו הזה (או ה-workflow שהמשתמש מפעיל) ממזג PR-ים כמעט מיידית אחרי הפתיחה, ומוחק את ה-branch אוטומטית עם המיזוג. בכל מעבר, אם commit חדש נדחף לאותו שם-branch *אחרי* שה-PR שהיה פתוח עליו כבר מוזג ונמחק — נוצר "commit יתום" שאף PR לא עוקב אחריו ולעולם לא ימוזג ל-`main` בלי טיפול ידני. **הזיהוי:** `git fetch origin main && git merge-base --is-ancestor <commit> origin/main` לפני כל push לענף שכבר שימש PR קודם. **הפתרון בכל פעם:** `git fetch origin main && git checkout -B <branch> origin/main` (או `git rebase origin/main` אם יש כמה commits לא-ממוזגים לשמר), `push` (רגיל אם ה-branch המרוחק נמחק, `--force-with-lease` אם עדיין קיים), ואז PR חדש — לא לנסות "לתקן" את ה-PR הישן שכבר closed/merged.

**לקח נוסף מסבב זה (BUG-065/PR #227):** תיקון "פונקציונלית נכון" לא מספיק כשה-verification הוא grep סטטי — אם ליטרל `raw_ref=""` נשאר בקוד (אפילו בענף שלעולם לא מבצע), ביקורת חיצונית תדגל אותו כ"עדיין שבור". כשריאקציה לכשל היא regex/grep-based, לוודא שהקוד עצמו (לא רק ה-runtime behavior) לא מכיל את הדפוס שמחפשים.

**לא אומת:** deploy ל-Render / production verification לאף אחד מה-5 הבאגים (אין גישת Render Dashboard מה-sandbox). **חשוב:** `FEATURE_AUTO_CAPTURE` עדיין כבוי בפרודקשן — "קוד+טסטים מאומתים" ≠ "production-verified" (התלות המפורשת של ROADMAP.md C90 עדיין פתוחה, ראו שם).

**עדכון תיעוד מלא:** `BUG_AUDIT_LOG.md` (BUG-061/062/063/064/065), `CHANGE_CONTROL_LOG.md` (C83/C84/C85/C86/C87), `CHANGELOG.md` (Unreleased), `ROADMAP.md` (סעיף C89).

---

## 0.8 F52 Stage 1 + chokepoint/scope-verification session — 2026-07-03 (קרא לפני 0.7)

**7 PR ממוזגים ל-`main` בסשן אחד (#207–#213), כולם additive/flag-off/docs-only — אין שינוי אחד ב-`app.py`:**

- **PR #207/#208 (F52 Stage 1):** `tools/audit_gateway_bypass.py`/`tools/audit_result_parsing.py` — warning-only static audits, baseline נבנה מ-grep אמיתי נגד main (לא מ-SPEC ישן שלא תאם את המצב בפועל — `cmd_decision.py:806` התברר כלא-httpx בכלל, ורוב קבצי ה-SPEC המקוריים לא הכילו את דפוס ה-"✅"/`rec\w+` כלל). `core/last_tool_result_shadow.py` — recorder פסיבי RAM-only, `FEATURE_LAST_TOOL_RESULT_SHADOW` (כבוי כברירת מחדל), חווט ל-`tools/dispatcher.py`/`tma_api.py`. `docs/governance/PLANNING_GATE.md` אוחד ל-שער יחיד "8 שאלות" + Rule 00 (ראה למטה).
- **PR #209:** מיזוג ענף יתום `claude/fix-drive-sheets-conversion` (BUG-DRIVE-READ-UNSUPPORTED-CONVERSION + BUG-SHEETS-SEARCH-STATUS ב-`tools/google_tools.py`) — קוד היה כתוב ונבדק (3/3), פשוט לא נפתח PR לפניו.
- **PR #210:** `llm_fallback.py` איחד flag כפול (`OPENAI_FALLBACK_ENABLED` גולמי מול `feature_flags.LLM_FALLBACK`) לדגל יחיד.
- **PR #212:** `core/output_gateway._execute_send()` קיבל שורת shadow-record פסיבית — סוגר פער שבו `send_outbound()` (הנקרא מ-`app.py`/`followup_engine.py`/`payment_reminder.py`/`providers/twilio_shim.py`) לא עבר דרך `tools/dispatcher.py` ולכן לא נראה ל-recorder של F52 Stage 1.
- **`ce2ea76` (docs, ישיר ל-main):** `docs/f52/F52_BYPASS_MAP.md` gap-fill (`cmd_decision.py:700` חסר מהמפה המקורית) + BUG-055 — תיקון claim: "action_gateway.py:552 + 3 נוספים" התברר כ-1 מופע מאומת בלבד (dormant, `FEATURE_ACTION_GATEWAY=off`; הנתיב החי `app.py:909` כבר חוסם קשיח).
- **PR #213:** `document_converter/` (חבילה code-complete מ-29/06, **אפס call sites בפרודקשן עד עכשיו**) חוברה סוף-סוף — `tools/google_tools.py`'s `drive_read_file()` ממיר קבצים לא-native (docx/csv/xlsx וכו') ל-markdown במקום להחזיר בייטים גולמיים מקולקלים. 5 באגים אמיתיים ב-SPEC המקורי נתפסו ותוקנו **לפני** מימוש (לא אחרי) דרך 4+ סבבי grep נגד main: שם/חתימת פונקציה שגויים (`convert()` לא קיים, האמיתי `convert_document(input_file, input_type, output_type)`), `input_type` חסר (אין הסקה אוטומטית בשום מקום), גישה ל-return value כ-dataclass attributes במקום dict, תלות ב-download-מ-Drive שלא קיים (מסלול קודם ננטש בגללה), ו-cleanup חסר ל-`output_file` (ה-engine מנקה רק בכישלון, לא בהצלחה).

**לקח מתועד כ-Rule 00 (`docs/governance/PLANNING_GATE.md`):** SPEC לא נכתב/מבוצע לפני שמוצגת שרשרת חוזה מאומתת (Entry Point → Public API → Data Contract → Execution Point → Verification Point), כל חוליה מוכחת ב-grep נגד main, לא בהנחה או שם משוער.

**לא אומת:** deploy ל-Render / הפעלה חיה של אף flag חדש. כל השינויים flag-off/docs-only — אין שינוי התנהגות בפרודקשן עד הפעלה מפורשת.

---

## 0.7 BUG-051 — Capture Policy Router-Integration — 2026-07-02 (קרא לפני 0.6)

**מה נמצא:** `core.lead_candidate_handler.handle_lead_candidate()` (LCH, C89) רץ ב-`app.py` שלב "1.45" — **לפני** `route_request()` — לכל sender פנימי (owner/staff). אומת ב-grep: `core/ingress_classifier.py` (שה-LCH קורא לו) אפס אזכורים ל-`RouteDecision`/`route_request`/`intent_router` — מסווג עצמאי לגמרי, לא "מרחיב" את ה-Router. domain נקבע ע"י `_detect_domain()` הפנימי (regex mirror ידני של `domain_router._DOMAIN_RULES`), לא ה-domain_router האמיתי — ולכן מפספס למשל `domain_from_channel`.

**מה תוקן (`feature/capture-policy-stage-3`, טרם ממוזג):** `RouteDecision` קיבל 3 שדות אופציונליים חדשים (`capture_tier`/`capture_reason`/`raw_ref`, additive-only). `core/router/capture_router.py` חדש — עטיפה דקה סביב `classify_ingress()` הקיים (אין שכתוב לוגיקה, אין import ל-airtable/drive/gateway). `router.py` קורא לו כשלב חדש, גייט על `identity.is_internal` בלבד. `app.py`'s LCH call הועבר ל-**אחרי** ה-Router, `domain=resolved_route_domain` מועבר ל-LCH דרך פרמטר `domain` אופציונלי חדש (default `""`, נופל חזרה ל-`_detect_domain()` הישן — תאימות מלאה לאחור).

**3 סטיות מכוונות מהספק המקורי, כולן documented ב-`BUG_AUDIT_LOG.md` BUG-051:** (1) `capture_tier` הוא observability-בלבד — gate כפי שהוצע בספק היה שובר `_handle_batch_followup()`. (2) הוסר intent/confidence filter משלב 4 ב-router — היה גורם ל-`RouteDecision` "לשקר" (capture_tier=None בזמן ש-LCH עדיין כותב) עבור הודעות עם intent בביטחון גבוה. (3) `handle_lead_candidate()` קיבל פרמטר `domain` חדש (לא "חתימה זהה" כפי שהספק ביקש) — נדרש כדי שתיקון ה-domain יהיה בר-מימוש בפועל.

**בדיקות:** `test_capture_router_wiring.py` חדש (10/10, כולל regression guards לכל 3 הסטיות למעלה). `core/router/test_router.py` (29/29) ו-`test_integration.py` (4/4) — שני MockIdentity נפרדים קיבלו `is_internal`/`memory_key`; ב-`test_integration.py` זו הייתה תקלה שקטה אמיתית לפני התיקון (`route_request()` זרק `AttributeError` שנבלע ב-`except Exception` הרחב של ה-`_safe_route` המקומי של הבדיקה, מדמה 3/4 כשלים מזויפים). כל 30 קבצי `test_*.py` בריפו ירוקים. אין אימות מול Airtable/Gateway/Render חי (sandbox).

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
