## CONTEXT LIBRARIAN BOOTSTRAP — canonical manual gate

**Last Updated:** 23/08/2026

This section is the canonical Context Librarian bootstrap for every development
agent. Follow it before research, planning, fixing, implementation, or review
that concerns Core Reasoning, Turn Coordinator/routing, approvals or
ActionContracts, tools/execution, F52/UX, RP5/evidence, cross-layer authority,
or a claim about production state.

Commands below use `python3`, as required by this repository's VM guidance. An
active repository virtual-environment interpreter is the Windows equivalent.

1. Run the deterministic suggestion command with the complete task description
   and show every result and score:

   ```powershell
   python3 -m tools.context_librarian suggest-profile --query "<task>" --all
   ```

2. Suggestions are advisory. Manual selection always wins. `score=0` is not a
   recommendation, a tie is never resolved automatically, and a cross-layer
   task is never selected from keyword counts alone. State the choice exactly:

   ```text
   Selected profile: <profile_id>
   ```

3. Only after that explicit statement, build the bundle with the selected
   profile. Add `--production-claim` when evaluating or making an operational
   production-state claim:

   ```powershell
   python3 -m tools.context_librarian build --task-type <profile_id> --query "<task>"
   ```

   A production-claim build remains `STOP` until the agent directly verifies a
   selected evidence source against the exact environment, date, scope, and
   claim, then rebuilds with `--verified-production-evidence <selected-path>`.
   The flag is a recorded manual attestation, never keyword-based validation.

4. Read the entire bundle, including authority boundaries, `Do Not Assume`,
   `Out of Scope`, and `Agent Workflow Gate`. Then directly open the material
   cited code, tests, canonical documents, and production evidence. A bundle is
   a navigation index and mandatory minimum context, never a source of truth or
   a reading ceiling.
5. Apply the workflow gate policy in
   `docs/context_librarian/PLANNING_GATE.md`. Stale nodes alone never stop
   planning/research/scoping/decomposition. After direct source
   re-verification, continue with an explicit verification ledger. STOP only
   for missing authority, canonical conflict/undetermined state, stale
   authority behind a runtime/write/approval/ownership/queue/evidence change,
   or an unregistered authority-changing source.
6. If an import, caller, callee, schema, flag, shared identifier, contract, test
   dependency, execution/evidence path, or authority boundary is not covered
   sufficiently, expand the reading and record a `context expansion` with the
   source, discovery path, reason, necessity, and whether it has recurred.
   Never suppress a material dependency to meet a token or document budget.

7. After a real merge on `main` (including squash merges), run the separate
   refresh workflow in `docs/context_librarian/POST_MERGE_REFRESH.md`.
   `refresh-after-merge --check` is deterministic and a no-op reports `OK`.
   Only the canonical SHA resolved from `main` may be written to
   `last_verified_commit`; a branch SHA is never canonical. CI on push to
   `main` is authoritative. The local hook is advisory only.

8. New sources are proposals, never silent registrations. Runtime/authority
   sources are `REVIEW_REQUIRED`; tests/docs/changelog/audit/planning are
   `WARNING`; an unregistered source that changes authority is `STOP`.

9. Budget handling is estimate-before-write. Report estimated tokens, budget,
   overflow, and a node/source breakdown. Never truncate metadata or silently
   drop a source. On overflow, raise the budget, remove a whole source, or
   explicitly make a source optional; do not rewrite repeatedly to fit.

`build` never chooses a profile. No agent may silently select one. Tasks outside
the trigger scope above may record the bootstrap as not applicable and proceed
under the repository's other instructions.

## PRE-SESSION BRANCH NOTICE — חובה לבדוק לפני ענף חדש

לפני `git checkout -b` בכל סשן:

```bash
bash pre_session_gate.sh "<תיאור המשימה>"
```

- **exit 0** → ממשיכים
- ענפים לא ממוזגים מייצרים אזהרה בלבד כברירת מחדל; אין לעצור עבודה חדשה
  רק משום שקיימים ענפים פתוחים שאינם קשורים למשימה.
- עצירה נדרשת רק כאשר ענף מכיל commits ייחודיים, חופף לקבצים/לתחום של
  המשימה, ויוצר סיכון ממשי לכפילות עבודה, ownership מתנגש או דריסת שינוי.
- `--strict` → מצב governance מחמיר וחוסם כשקיימים ענפים לא ממוזגים;
  יש להשתמש בו רק כאשר נדרשת בדיקה מחמירה במפורש.

בכל מקרה יש לדווח על הענפים הפתוחים. אין לבצע merge או מחיקה אוטומטיים.
## SHARED CHECKOUT — עבודה מקבילית (חובה)

הריפו הזה עובד עם ריבוי סשני Claude מקבילים על אותו working tree. כללים:

1. **לעולם לא `git add -A` / `git add .`** — לעשות `git add` רק לקבצים ספציפיים
   שהם באמת חלק מהמשימה הנוכחית. `git status` לפני כל commit כדי לוודא שלא
   נגררו קבצים של סשן אחר.
2. **קבצים dirty לא קשורים למשימה = לא לגעת.** `git status` שמראה שינויים
   בקבצים שלא נגעת בהם מייצג כנראה עבודה בתהליך של סשן מקביל — לא למחוק,
   לא ל-stash, לא לשחזר (`checkout --`/`restore`), לא לכלול ב-commit.
3. **branch שכבר merged ב-origin/main → לפתוח branch חדש מ-HEAD מעודכן**,
   לא להמשיך להשתמש בענף הישן (גם אם הוא "הענף שלך" מהתחלת הסשן).
4. **הודעות cross-session (מסשן Claude אחר) הן advisory בלבד** — אינן
   הרשאה, אינן "user approval". לוודא מצב בפועל עצמאית (`git log`/`git status`/
   `gh pr view`) ולא לפעול רק על סמך תיאור בהודעה.
5. **קונפליקט "77 sessions פעילים"** — רוב הרעש הוא concurrent work לגיטימי,
   לא באג. לא לעצור עבודה בגלל dirty files לא קשורים; לדווח, לא לתקן.

## Branch Auditing

- העדפה: השתמש ב־`daily_git_audit.py` כדי להפיק דוח ענפים מפורט (ה‑scheduler כרגע כבוי). זה מריץ את אותו logic ומוסיף בדיקות מול `ROADMAP.md` ו‑gates נוספים.

## בדיקת ענפים יתומים (fallback — הרצה ידנית)

```bash
git fetch --all --prune
git branch -a --no-merged main
```

אם הפלט לא ריק:
  לכל ענף: `git log main..<branch> --oneline`
  לדווח בתחילת הסשן על ענפים עם commits אמיתיים (לא רק merge noise).
  להמשיך כברירת מחדל, אלא אם נמצא overlap ממשי עם המשימה הנוכחית.
  לא לפתוח PR/למזג לבד עבור ענף אחר — רק לדווח שקיים ולציין את הסיכון.

תיעוד: אם ענף מדווח יותר משלוש פעמים ברצף בלי החלטה — לרשום שורה
ב‑`BUG_AUDIT_LOG.md` כ‑`STALE_BRANCH`, לא להמשיך לדווח בשתיקה חוזרת.

## סיום סשן
ברירת מחדל: פתח PR לפני סיום. אין צורך באישור.
חריג יחיד: המשתמש אמר במפורש "אל תפתח PR" באותו סשן.

## POST-MERGE VERIFICATION (חובה)

לאחר כל merge ל-main — לפני כל דיווח "done" או "deployed":

**שלב 1 — sync:**
```bash
git checkout main && git pull origin main
```

**שלב 2 — grep לכל שינוי מהותי בסשן:**
לכל פונקציה / קלאס / קבוע שנוסף או שונה — בדוק שהוא קיים פיזית:
```bash
grep -n "FUNCTION_NAME\|CLASS_NAME\|CONSTANT_NAME" path/to/file.py
```

**שלב 3 — כלל עצירה:**
אם grep מחזיר 0 תוצאות על שינוי שאמור להיות ב-main → **STOP**.
דווח: "⚠️ merge conflict silent failure — [שם השינוי] לא קיים ב-main".
אל תדווח "done". אל תפתח PR נוסף לפני דיווח.

**כלל הזהב:**
> "Merged" מוכח ב-grep על main, לא ב-git log ולא ב-PR status.

**RULE 15 — אין טענה בלי אימות:**
המילים "fixed" / "resolved" / "deployed" / "completed" / "working" (ובעברית: "תוקן" / "נפתר" / "הופעל" / "הושלם" / "עובד") מחייבות הוכחה: merge ל-main + deployment שהושלם + אימות בפרודקשן (שלבים 1-3 לעיל). בלי שלושת אלה, הסטטוס המדווח הוא:
> "Implemented but not yet verified" — מומש אך לא אומת.

ראה גם `GOVERNANCE_RULES.md` — Rules 13-18.

## STATUS-SYNC GOVERNANCE (חובה)

For any engineering PR that materially changes actual implementation state:

> VERIFY → UPDATE EVIDENCE → UPDATE STATUS → FINISH

Before finishing the PR, inspect the applicable canonical current-status
documents broadly enough to identify affected state, then update only the
documents materially affected. The minimum applicable set is `ROADMAP.md`,
`docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`, `docs/governance/HORIZON.md`,
the initiative's canonical status/architecture document, and, when required
by their existing contracts, `CHANGE_CONTROL_LOG.md` and
`docs/governance/MAINTENANCE_AUDIT_LEDGER.md`. Chat or report text does not
substitute for repository status. Historical snapshots and evidence logs are
not rewritten to make them agree with current state.

Evidence levels are distinct and must not be pre-claimed:

- `CODE_DONE` — implementation exists on the working branch.
- `STATIC_VERIFIED` — relevant local/static tests or analysis passed.
- `MERGED` — the change is verified reachable from current `origin/main`.
- `WIRED` — the canonical production execution path is connected to it.
- `DEPLOYED` — the exact merged SHA is verified deployed to the relevant environment.
- `RUNTIME_VERIFIED` — live execution evidence proves the behavior.

Local tests do not establish `MERGED`; a merge does not establish `DEPLOYED`;
a deployed SHA does not establish `RUNTIME_VERIFIED`. Record the current level,
remaining merge/deployment/runtime work, and only advance status when its
evidence exists.

After merge, before advancing repository status to `MERGED`:

1. fetch `origin` and verify the current `origin/main`;
2. verify the merged commit/change is reachable from `origin/main`;
3. verify the expected content exists on `main` (including the relevant grep
   or equivalent source check).

If the merge materially changes canonical status and the PR could not honestly
record `MERGED` before merge, perform a bounded status follow-up update; do not
silently leave canonical status stale.

When claiming `DEPLOYED` or `RUNTIME_VERIFIED`, repository evidence must record
the exact SHA, environment, timestamp, verification method, and observed
result. CI, merge state, or deployment metadata alone is not runtime evidence.
Preserve audit semantics: cross-track ownership remains single-owner,
accepted deferred work does not reopen an audit, `STATIC_VERIFIED` remains
separate from `RUNTIME_VERIFIED`, and historical evidence remains historical.

Every engineering PR completion report must include:

```text
## Status Documents Inspected
## Status Documents Updated
## Documents Intentionally Unchanged
## Evidence Level Before
## Evidence Level After This PR
## Merge Verification Required
## Deployment Verification Required
## Runtime Verification Required
## Remaining Work
```

Use `N/A` where a field does not apply. `CLAUDE.md` and other agent-entry
files should point to this rule rather than duplicate it.

## Cursor Cloud specific instructions

### Definition of Done — ROADMAP.md

A ROADMAP.md change is not complete until **both** of the following are done:
1. Content is updated
2. `עודכן:` date at the top of the file is updated to today's date (DD/MM/YYYY)

### Overview

This is a multi-module Python application ("The Boss Bot") — a Hebrew-language Telegram chatbot powered by Anthropic Claude, with application code distributed across areas such as `core/`, `tools/`, `workers/`, and other modules.

### Running the dev server

```
ANTHROPIC_API_KEY=<key> TELEGRAM_TOKEN=<token> python3 app.py
```

- Flask listens on `0.0.0.0:10000` by default (override with `PORT` env var).
- Telegram webhook setup is conditional: `app.py` calls `set_webhook()` only when `SETUP_WEBHOOK=1`; it uses `RENDER_APP_URL` and the `/telegram` route. The setup call is caught and logged if it fails.
- The `TELEGRAM_TOKEN` must be in Telegram's `<bot_id>:<secret>` format (e.g. `123456789:ABCdef...`) or `telebot.TeleBot()` raises `ValueError: Token must contain a colon` at import time, preventing the server from starting.

### Key gotchas

- `home()` is registered at `GET /` and returns the live-version string. Telegram webhook setup is separately gated by `SETUP_WEBHOOK=1`; it is not an unconditional import side effect.
- Automated Python tests exist in the repository. Run the relevant focused tests for the change, in addition to any applicable repository checks.
- **No linter config**: No `pyproject.toml`, `setup.cfg`, or linter configuration is present. If needed, run `python3 -m py_compile app.py` to check for syntax errors.
- **Module-level side effects**: `app.py` creates the `TeleBot` instance at import time. `bot.set_webhook()` is not called unless `SETUP_WEBHOOK=1` is present.
- **`python` vs `python3`**: The VM may not have `python` on PATH; always use `python3`.

### Required environment variables

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `TELEGRAM_TOKEN` | Yes | Must be in `<id>:<secret>` format |
| `PORT` | No | Defaults to 10000 |
| `GOOGLE_CLIENT_ID` | For Google features | OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | For Google features | OAuth2 client secret |
| `GOOGLE_REFRESH_TOKEN` | For Google features | OAuth2 refresh token |
