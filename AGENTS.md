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

## PRE-SESSION GATE — חובה לפני כל ענף חדש

לפני `git checkout -b` בכל סשן:

```bash
bash pre_session_gate.sh "<תיאור המשימה>"
```

- **exit 0** → ממשיכים
- **exit 1** → STOP. דווח למשתמש מה הענפות הפתוחות ובקש הנחיה.
- **--force** → רק אם המשתמש אישר במפורש בשיחה הנוכחית.

כלל: ענף שלא ממוזג = סשן לא הסתיים. לא שותקים — מדווחים.
## Branch Auditing

- העדפה: השתמש ב־`daily_git_audit.py` כדי להפיק דוח ענפים מפורט (ה‑scheduler כרגע כבוי). זה מריץ את אותו logic ומוסיף בדיקות מול `ROADMAP.md` ו‑gates נוספים.

## בדיקת ענפים יתומים (fallback — הרצה ידנית)

```bash
git fetch --all --prune
git branch -a --no-merged main
```

אם הפלט לא ריק:
  לכל ענף: `git log main..<branch> --oneline`
  אם יש קומיטים אמיתיים (לא רק merge noise) — לדווח בתחילת הסשן,
  לפני שממשיכים לעבודה החדשה שהתבקשה. לא לפתוח PR/למזג לבד —
  רק לדווח שקיים, תלוי בבדיקה, ומחכה להחלטה.

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
