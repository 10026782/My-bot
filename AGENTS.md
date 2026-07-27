## CONTEXT LIBRARIAN BOOTSTRAP — canonical manual gate

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
5. Stop before planning or changing code when the workflow gate reports stale
   nodes, mandatory authority below 100%, missing qualifying evidence for a
   production claim, an unresolved source conflict, or excluded-layer leakage.
   Stale bundles must still be built and read so they can identify what needs
   direct re-verification.
   A stale STOP permits only direct source re-verification and a separately
   reviewed metadata-refresh task after the source is verified on `main`; it
   does not permit planning or implementation of the original task. Resume the
   original task only from a newly built bundle whose gate can proceed.
6. If an import, caller, callee, schema, flag, shared identifier, contract, test
   dependency, execution/evidence path, or authority boundary is not covered
   sufficiently, expand the reading and record a `context expansion` with the
   source, discovery path, reason, necessity, and whether it has recurred.
   Never suppress a material dependency to meet a token or document budget.

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

This is a single-file Python/Flask application ("The Boss Bot") — a Hebrew-language Telegram chatbot powered by Anthropic Claude, with optional Google Workspace and Twilio/WhatsApp integrations.

### Running the dev server

```
ANTHROPIC_API_KEY=<key> TELEGRAM_TOKEN=<token> python3 app.py
```

- Flask listens on `0.0.0.0:10000` by default (override with `PORT` env var).
- At startup, `app.py` attempts to set a Telegram webhook pointing to the hardcoded Render URL. This call will fail in local dev (expected; caught by try/except). The Flask server still starts normally.
- The `TELEGRAM_TOKEN` must be in Telegram's `<bot_id>:<secret>` format (e.g. `123456789:ABCdef...`) or `telebot.TeleBot()` raises `ValueError: Token must contain a colon` at import time, preventing the server from starting.

### Key gotchas

- **No `@app.route('/')` on `home()`**: The `home()` function exists but has no route decorator, so `GET /` returns 404. The only HTTP route is `POST /<TELEGRAM_TOKEN>` (the webhook).
- **No automated tests**: The repository has no test suite. Verify changes by starting the server and sending simulated Telegram webhook POSTs via `curl`.
- **No linter config**: No `pyproject.toml`, `setup.cfg`, or linter configuration is present. If needed, run `python3 -m py_compile app.py` to check for syntax errors.
- **Module-level side effects**: `app.py` creates the `TeleBot` instance and calls `bot.set_webhook()` at module load time (lines 11, 23-24). Any import of `app.py` triggers these calls.
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
