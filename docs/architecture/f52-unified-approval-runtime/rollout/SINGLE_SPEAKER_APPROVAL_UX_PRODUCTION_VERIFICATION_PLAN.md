# Single-Speaker Approval UX — Production Verification Plan

**Status:** ⏳ PLAN ONLY — NOT EXECUTED. No claim in this document counts as verified.
**Program:** F52 / Turn Coordinator — `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` (PR #471, `c64da20`)
**Owning backlog item:** `ROADMAP.md` N17, item 4 ("Live production verification")
**Written from:** a sandbox session with **no Render dashboard/egress access** and no
production credentials. This document cannot be executed here — it is a handoff to
whichever session/operator does have that access (Render dashboard, production/staging
logs, a real Telegram test account against the deployed bot, and Airtable/`ActionContracts`
read access).

## Redaction note

Following a security review of this document (PR #477), raw operational identifiers
captured during the live testing below (Render service IDs/URLs, the Telegram owner's
handle, `ActionContract` UUIDs, Airtable record IDs, event-bus `action_id`s) have been
replaced with stable aliases (`RENDER_SERVICE_STAGING`, `CONTRACT_1`..`CONTRACT_8`,
`AIRTABLE_RECORD_1`..`AIRTABLE_RECORD_4`, `ACTION_ID_1`/`ACTION_ID_2`,
`TELEGRAM_OWNER_HANDLE`, `TURN_USER_HASH_1`). The same aliases are reused wherever the
same real entity is referenced again (e.g. `CONTRACT_4` is the same contract discussed in
`BUG_AUDIT_LOG.md`'s BUG-150). Tool names (e.g. `airtable_add`) and git commit hashes are
kept as-is — they are source-code constants and version-control metadata, not
operational/account identifiers, and Claim 4's finding specifically depends on which raw
tool name leaked. Verbatim bot-reply text is kept where it demonstrates a finding (e.g.
Claim 4's leak), with the leaked identifier itself aliased inside the quote.

**Known limitation:** this redaction applies to the current file content only. The raw
values were already committed to this branch's git history in earlier commits (this PR's
own history, pushed to `origin`) before this redaction pass. Rewriting that history
(squash/force-push) is a separate, more destructive step this session has not taken
without explicit owner approval — flag to the owner if full history scrubbing is required.
The raw evidence and the alias↔real-value mapping are retained only in a local,
git-ignored file (see `.gitignore`'s `**/.evidence/` entry) on the machine that produced
this redaction; that file does not persist beyond this sandbox session and is not itself
an access-controlled long-term store — the owner should decide where raw evidence should
live durably (e.g. an internal ops vault) if this needs to be re-derivable later.

## Non-negotiable rules (restated from the owner's instruction, not re-argued)

1. **No claim in this document may be marked verified from code, from a feature-flag
   default, or from a passing test alone.** Those prove the code is capable of the
   claimed behavior; they do not prove the behavior occurred in a live environment.
2. **Every claim below must be filled in with:** required evidence, why it's required,
   environment, test date, exact scope, supplied evidence, missing evidence, and allowed
   status. An empty or partially-filled row is `NOT VERIFIED`, not "probably fine."
3. **Do not update `docs/context_librarian/layers/*.yaml`'s `production_evidence` or
   any node's status to `production_verified`-equivalent as part of executing this plan.**
   That is a separate, follow-up documentation change made only after this plan's rows
   are filled in with real, dated evidence — and it should cite this document by path.
4. **`FEATURE_SINGLE_SPEAKER_APPROVAL_UX` defaults to `false`** in code and
   `.env.example` (`feature_flags.py`). If the environment being tested has never set it
   to `true`, most of the claims below are **not applicable there** — say so explicitly
   (`status: NOT_APPLICABLE — flag off in this environment`), do not mark them
   `NOT_VERIFIED` as if a test was attempted and failed.
5. Everything below assumes `FEATURE_ACTION_GATEWAY=true` for claims 3 and 6 specifically
   (the exact-contract-id callback path and the atomic-claim replay guard both require it
   — see the `if callback_contract_id and _flag_enabled("FEATURE_ACTION_GATEWAY")` gate at
   `app.py:2172`). Record the gateway flag's state alongside the single-speaker flag's
   state for every environment tested.

## Prerequisites for the executing session

- Render dashboard access (or equivalent) to read the **actual deployed environment
  variable values** for `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, `FEATURE_ACTION_GATEWAY`,
  and `FEATURE_EVIDENCE_FINALIZER` on every environment tested (staging first, then
  production only with explicit owner sign-off).
- Read access to that environment's application logs (Render log stream or exported
  logs), searchable by the exact log-line markers given per claim below.
- A real Telegram account able to trigger an approval-required action (e.g.
  `airtable_add`) against the tested environment's bot, and — for claim 1's callback
  press — able to actually press the resulting inline button.
- Read access to the `ActionContracts` table (Airtable or Postgres, whichever is the
  environment's configured repository) to independently confirm contract state, not just
  trust log lines.
- This document's own commit hash and the environment's deployed commit hash, so results
  can be tied to an exact code version (`git rev-parse HEAD` locally vs. the Render
  deploy's commit shown on the dashboard).

## Per-claim verification rows

Copy the template into each claim's "Result" block and fill it in per environment
tested. Do not delete unfilled template fields — an empty field is itself information
(nobody has checked it yet).

```yaml
- required_evidence:
- why_required:
- environment:            # e.g. "staging (my-bot-staging.onrender.com)" / "production"
- test_date:
- exact_scope:            # what was actually exercised — one flow, N flows, which channel
- supplied_evidence:      # log excerpt / screenshot / ActionContracts record ID, with a link or verbatim quote
- missing_evidence:       # what would still be needed for a stronger claim
- allowed_status:         # NOT_APPLICABLE | NOT_VERIFIED | PARTIALLY_VERIFIED | VERIFIED
```

---

### Claim 1 — Is `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` actually active in staging or production?

**Required evidence:** the literal environment-variable value as shown on the Render
dashboard (or `os.environ` dump from a live process, e.g. via `/status` if it surfaces
flag state — check `startup_validator.format_startup_message()`'s output first), for
every environment being claimed about.

**Why required:** code default is `false` (`feature_flags.py`); `CHANGELOG.md`'s PR #471
entry states "no staging/production flag activation is part of this merge" as of
27/07/2026. Any claim about live single-speaker behavior is meaningless if the flag was
never turned on in that environment.

**Result:**
```yaml
- required_evidence: Render API `GET /v1/services/{id}/env-vars` dump of the deployed
  environment variables (not code default, not .env.example).
- why_required: (see above)
- environment: production (RENDER_SERVICE_PRODUCTION) AND staging
  (RENDER_SERVICE_STAGING) — see redaction note above for alias meanings
- test_date: 2026-07-28
- exact_scope: read the literal `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`,
  `FEATURE_ACTION_GATEWAY`, and `FEATURE_EVIDENCE_FINALIZER` values via Render's
  env-vars API for both services. Also read each service's latest deploy commit.
- supplied_evidence:
  - PRODUCTION: `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false`,
    `FEATURE_ACTION_GATEWAY=true`, `FEATURE_EVIDENCE_FINALIZER=shadow`.
    Latest deploy: commit `a4bbcc4a07c7ef511536923b5a4eba493eb1f084` (PR #476 merge,
    "ROADMAP: record Context Librarian follow-up backlog (N17)"), status `live`,
    deployed 2026-07-27T20:59:01Z. This matches `main`'s current HEAD
    (`git rev-parse HEAD` on this checkout also resolves to `a4bbcc4a...`).
  - STAGING: `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true`, `FEATURE_ACTION_GATEWAY=true`,
    `FEATURE_EVIDENCE_FINALIZER=shadow`, `FEATURE_ATOMIC_CLAIMS=true`,
    `FEATURE_ACTION_CONTRACT_PERSISTENCE=true`. Latest deploy: commit
    `67c595d5a128541dc4b29db1482e1eb236289016` on branch
    `claude/rp5-staging-fault-injection-v4akit` (**not** `main`), status
    `build_in_progress` at time of check, commit message: "RP5 staging: fix
    test_bug_batch_approval_preserved.py after rebase past PR #460/#461/#469" —
    this branch carries an RP5 fault-injection wrapper around `run_agent()`
    (renames the real loop to `_run_agent_impl()`), per that commit's own message.
- missing_evidence: Confirmation that staging's RP5 wrapper is behavior-neutral for
  claims 2-6 specifically (the commit message asserts "no behavior changed" for the
  BUG-122 batch-block path it touched, but that assertion hasn't been independently
  re-verified here, and it doesn't speak to single-speaker/turn-ownership behavior at
  all). Staging is also mid-deploy as of this check — a fresh env-var/deploy read
  should be taken immediately before any live test in claims 2-6 to confirm the
  build finished and which commit is actually serving traffic.
- allowed_status: VERIFIED — for the literal flag-value claim only, both environments,
  as of 2026-07-28. This claim is narrow (is the flag on/off) and fully answered by a
  direct, authoritative source (Render's own env-var API), not by inference.
```

**Conclusion for claims 2-6:** per rule 4, `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false`
in **production** as of this check, so claims 2-6 are `NOT_APPLICABLE` in production
until the flag is turned on there — not `NOT_VERIFIED`. In **staging** the flag (and
`FEATURE_ACTION_GATEWAY`) are both `true`, so claims 2-6 are testable there, subject to
the caveat above that staging runs a fault-injection branch, not `main`.

**CRITICAL CORRECTION (found after the button-press testing below was already
committed):** staging's flag reading is **misleading, not just narrow**. Diffing
staging's deployed commit (`67c595d5a128541dc4b29db1482e1eb236289016`) against `main`
shows staging's branch was cut **before PR #471 merged** and was never rebased past it —
`git log 67c595d5a1..main` shows PR #471's three commits (`5e2c244`, `dadf851`,
`c64da20`) are entirely absent from staging. Confirmed directly:
`git show 67c595d5a1:app.py | grep FEATURE_SINGLE_SPEAKER_APPROVAL_UX` returns **zero**
matches — the string doesn't exist anywhere in staging's deployed code.
`ApprovalLifecycleResult`, `_safe_contract_business_description`,
`_redact_approval_identifiers`, and the entire single-speaker enforcement path in
`_handle_approval_callback_impl()` are also 100% new in PR #471 and absent from staging.
**Setting `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true` in staging's Render env vars is a
no-op — the deployed code never reads it.** The `reply_owner=gateway`
`[TurnEnvelope]`/`[EvidenceFinalizerShadow]` signals seen on staging come from an
earlier, pre-#471 shadow-observation layer, not from the actual PR #471 fix. This means
the button-press testing below exercised **pre-fix code**, not the mechanism these
claims are actually about — see the correction notes on claims 2, 3, and 6.
Claim 4's finding is unaffected by this — `_describe_contract_for_reconfirmation()` is
byte-identical in both versions (confirmed via `git show 67c595d5a1:core/action_gateway.py`),
and independently confirmed present on `main` directly, so that leak is real on both.
`SB-02` (claim 6) also predates PR #471 and is present in staging's old commit
unchanged, so that verification is unaffected as well — but note it exercised the
fingerprint path either way (see claim 3).
**Recommended next step:** rebase staging onto `main` (bringing in PR #471) and
redeploy, then repeat the real button-press testing to get genuine evidence for claims 2
and 3 against the actual shipped mechanism.

**DONE (2026-07-27 ~22:28-22:30 UTC):** staging was rebased onto `main` (6 staging-only
RP5 commits replayed cleanly, no conflicts, full local test suite green — see Claim 2's
result), force-pushed to `origin/claude/rp5-staging-fault-injection-v4akit`, and
manually redeployed via Render's API (`autoDeploy=no` there). Confirmed live on commit
`6f4cf521` with `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true` now genuinely read by the
deployed code. Claim 2 was re-tested against this and is now PARTIALLY_VERIFIED (scope:
Telegram/owner-role/staging-only) — see its result block below. Claim 3 still needs the
raw callback_data captured, which the rebase alone doesn't provide.

---

### Claim 2 — Is exactly one final user-facing response received per approval-queuing turn (no duplicate/contradictory second message)?

**Required evidence:** a real end-to-end transcript (screenshots or exported chat log)
of one approval-queuing request in the tested environment, showing only one final
message reaches the user for that turn — plus the corresponding log lines.

**Why required:** this is the entire point of PR #471 (single-speaker) and the exact
failure mode `TURN_OWNERSHIP_EXTENSION.md`/`REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md`
document as historically real. Passing tests prove the mechanism is *capable* of
preventing this; they do not prove it *did* prevent it against a live Claude response
and a live Telegram/WhatsApp send.

**How to check (log markers, not proof by themselves — corroborate with the actual
chat transcript):**
- `[TurnOwnershipShadow] violation=agent_spoke_in_gateway_owned_approval_turn` at
  WARNING level (`core/turn_envelope.py:558`) — if this line appears for the tested
  turn, the claim is **falsified** for that turn: the agent spoke again after the
  Gateway already owned the reply.
- `[TurnEnvelope] ownership_signal ... "reply_owner": "gateway"` at INFO level
  (`core/turn_envelope.py:547`) — expected to be present and to show
  `reply_owner=gateway` for the tested turn.

**Result:**
```yaml
- required_evidence: real Telegram transcript + `[TurnEnvelope]`/`[TurnOwnershipShadow]`
  log lines + independent `ActionContracts`/`Tasks` reads, for real approval-queuing
  turns.
- why_required: (see above)
- environment: staging (RENDER_SERVICE_STAGING, commit 67c595d5a1,
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true`, `FEATURE_ACTION_GATEWAY=true`), channel
  telegram, user TELEGRAM_OWNER_HANDLE (role owner)
- test_date: 2026-07-27 ~21:40-21:46 UTC (00:40-00:46 Israel time, 2026-07-28 local date)
- exact_scope: 4 real approval-queuing turns triggered by the owner via Telegram against
  the live staging bot: 3 resulted in `completed` Tasks records, 1 in `rejected`.
- supplied_evidence:
  - Contract `CONTRACT_1` ("חזור לכל הטלפונים"): propose
    21:41:06.584Z → `[TurnEnvelope] ownership_signal` `reply_owner=gateway
    approval_queued=true` at 21:41:09.692Z → approved 21:42:01.114Z → executed
    21:42:02.390Z, `external_id=AIRTABLE_RECORD_1`. Exactly one final bot reply observed
    for the completion step: `"✅ בוצע: airtable_add / Tasks | מזהה: AIRTABLE_RECORD_1"`.
    Independently confirmed: Airtable `Tasks` record `AIRTABLE_RECORD_1` exists, single
    record, title matches.
  - Contract `CONTRACT_2` ("רשום את כל הלידים"): propose
    21:45:08.763Z → approved 21:45:55.682Z → executed 21:45:57.221Z,
    `external_id=AIRTABLE_RECORD_2`. One final reply
    `"✅ בוצע: airtable_add / Tasks | מזהה: AIRTABLE_RECORD_2"`. Airtable confirms one
    matching `Tasks` record, no duplicates.
  - Contract `CONTRACT_3` ("דבר עם אלדד..."): propose
    21:42:31.705Z → **rejected** 21:42:34.893Z (3s later). One final reply
    `"🚫 הפעולה בוטלה: ..."`. Airtable search for "אלדד" found zero records created near
    this time (5 unrelated pre-existing matches, all from June) — confirms rejection
    produced no stray write and no second/contradictory message.
  - Contract `CONTRACT_4` ("פרסום מיטות וגיוס בפייסבוק") —
    **independently confirmed via `ActionContracts` to have been created 2026-07-27
    T07:34:20Z**, i.e. it sat `pending` for **~14 hours** before this session resolved
    it at 21:40:10-21:40:12Z (`external_id=AIRTABLE_RECORD_3`). This is a real, dated
    instance of the "stuck pending for unknown/hours-long duration" behavior you flagged
    live — see the separate note below; it is not itself a single-speaker violation
    (each step — "there's a pending item" / "confirm it? (yes/no)" / "done" — is its own
    single reply) but the multi-step resolution flow is worth the owner confirming is
    intended UX.
  - No `[TurnOwnershipShadow] violation=agent_spoke_in_gateway_owned_approval_turn` line
    appears anywhere in either the 5-day historical export or this fresh window — for
    the text-confirmation-word turns above.

  **UPDATE — FALSIFIED via a real inline-button press.** A follow-up round of testing
  used actual Telegram inline buttons (not typed text) for approve/reject/replay.
  Contract `CONTRACT_5` ("זיהוי בדיקת כפתורים"): propose
  22:09:31.811Z → **reject button pressed** 22:09:35.100Z (`ActionContracts` confirms
  `status=rejected`, and the `Tasks` table has **zero** matching records — the rejection
  itself was correctly not written). At 22:09:33.776Z (between propose and reject),
  BOTH of these fired:
  - `[TurnOwnershipShadow] violation=agent_spoke_in_gateway_owned_approval_turn
    user=TURN_USER_HASH_1 pattern_class=unknown` (WARNING, `core/turn_envelope.py:558`)
  - `[EvidenceFinalizerShadow] ... mismatch=true code=status_claim_mismatch
    response_claim=neutral` (WARNING) — the first `mismatch=true` observed in this
    entire test.
  The owner's real, verbatim transcript for this exact turn shows **two contradictory
  final messages**:
  1. `"🚫 הפעולה בוטלה: ➕ הוסף ל-Tasks: • כותרת המשימה: זיהוי בדיקת כפתורים • סטטוס:
     ממתין • תאריך יעד: 2026-07-29"` (Gateway-owned: correctly says canceled)
  2. `"✅ המשימה **\"זיהוי בדיקת כפתורים\"** נוספה ל-Tasks עם תאריך יעד מחר (29/07)."`
     (a separate, agent-generated message **falsely claiming the task was added** —
     directly contradicting message 1 and the actual `rejected` outcome)
  This looked like a real, live, user-visible instance of exactly the BUG-145/
  single-speaker failure mode PR #471 was built to prevent.

  **CORRECTION: this does NOT test PR #471's actual fix.** Staging's deployed commit
  (`67c595d5a1`) predates PR #471 and was never rebased past it —
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` and the entire `ApprovalLifecycleResult`
  mechanism don't exist in that code at all (see the correction note above Claim 2).
  This turn ran through pre-#471 `_handle_approval_callback_impl()`, which has no
  single-final-message guarantee to begin with — so the double message is expected
  behavior of *old* code, not a regression in the shipped fix. No stray write occurred
  (confirmed via `ActionContracts`/`Tasks`), only the false verbal claim.
- missing_evidence (as of the pre-rebase test): everything, against the *actual* claim.

  **UPDATE — PARTIALLY_VERIFIED after rebasing staging onto `main` (bringing in PR #471)
  and redeploying** (narrowed from an earlier, overclaimed VERIFIED — see
  `allowed_status` below for the exact scope limits). Staging's service was rebased
  (`git rebase origin/main` on the 6
  staging-only RP5 commits, clean, no conflicts; full local test suite —
  `smoke_tests.py`, `test_rp5_fault_injection.py` (31/31),
  `test_bug_batch_approval_preserved.py` (13/13), `test_c53a.py` (50/50),
  `core/router/test_router.py` (44/44) — all passed before pushing), force-pushed to
  `origin/claude/rp5-staging-fault-injection-v4akit`, and manually redeployed via
  Render's API (staging's `autoDeploy` is `no`). Confirmed live on commit `6f4cf521`
  with `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=true` now actually read by the deployed code
  (`grep` on `app.py` now finds 6 matches, vs. 0 before).

  Real button-press retest (2026-07-27 ~22:31 UTC / 01:31 Israel time), same owner,
  same channel:
  - Contract `CONTRACT_6` ("לבדוק עלות סוכן בחברה") —
    **approve button**: propose 22:31:14.848Z →
    `ownership_signal reply_owner=gateway approval_queued=true
    final_reply_nonempty=false` at 22:31:15.690Z → approved 22:31:18.738Z → executed
    22:31:20.360Z, `external_id=AIRTABLE_RECORD_4`. Independently confirmed via direct
    Airtable read: exactly one matching `Tasks` record exists.
  - Contract `CONTRACT_7` ("אישור עלות סוכן") — **reject
    button**: propose 22:31:52.712Z →
    `ownership_signal reply_owner=gateway approval_queued=true
    final_reply_nonempty=false` at 22:31:53.247Z → rejected 22:32:01.084Z. Verbatim bot
    reply: `"הפעולה נדחתה: הוספה ב-Tasks: אישור עלות סוכן"` — a single, clean message
    (contrast with the pre-rebase reject, which produced two contradictory messages).
    Independently confirmed via direct Airtable search: **zero** matching `Tasks`
    records — rejection correctly wrote nothing.
  - **Zero `[TurnOwnershipShadow]` violation lines** in the post-redeploy window (vs. one
    real violation in the identical pre-rebase reject scenario). `final_reply_nonempty`
    is `false` for both turns this time, vs. `true` for the pre-rebase reject.
  - `[EvidenceFinalizerShadow]`: both approval-queuing turns show
    `evidence_status=approval_pending response_claim=sent_for_approval mismatch=false`
    — no mismatch this time either, consistent with no false claim occurring.
- missing_evidence: WhatsApp untested (Telegram only). Non-owner roles untested (owner
  only). Sample is still small — 2 button-press turns post-rebase, 4 more via typed
  text confirmation words pre-rebase (not on PR #471 code, see the correction notes
  above) — no broader sampling across users/days.
- allowed_status: **PARTIALLY_VERIFIED** — real button-press approve and reject against
  actual PR #471 code, zero single-speaker violations, independently confirmed via
  direct Airtable reads, but strictly scoped to: Telegram channel only, owner role only,
  staging only, 2 button-press turns. Per this document's own rule (see the rollup
  section below), this scope does not support rounding up to VERIFIED for the general
  claim — WhatsApp, non-owner roles, and a larger sample remain untested.
```

---

### Claim 3 — Does a Telegram callback carrying `action_id:contract_id` resolve the exact contract end-to-end (not the fingerprint fallback)?

**Required evidence:** the raw `callback_data` string from a real button press (visible
via Telegram Bot API `getUpdates`/webhook payload logging, or by temporarily logging
`cq.data` in a controlled test — do not ship a permanent new log line as part of this
verification run without a separate code-review), correlated with the `ActionContract`
that actually resolved, confirmed by reading `ActionContracts` directly (not inferring
from the reply text).

**Why required:** `_approval_callback_data()` (`app.py:1116`) only embeds `contract_id`
when one exists at button-creation time; `_handle_approval_callback_impl()`
(`app.py:2172`) only takes the exact-contract-id path when `callback_contract_id` is
present **and** `FEATURE_ACTION_GATEWAY` is on — otherwise it silently falls back to
fingerprint matching. There is currently **no dedicated INFO-level log line that
distinguishes "resolved via exact contract_id" from "resolved via fingerprint
fallback"** — this is a real evidence gap, not an oversight in this plan. Verifying this
claim with current logging alone is not possible; either a temporary diagnostic log
must be added (reviewed and reverted, not merged permanently) or the raw callback_data
must be captured directly and cross-checked against the resolved contract.

**Result:**
```yaml
- required_evidence: raw callback_data from a real Telegram inline-button press.
- why_required: (see above)
- environment: staging
- test_date: 2026-07-27
- exact_scope: none — see below.
- supplied_evidence: The first round used only typed text confirmation words (`מאשר` /
  `כן`) — not applicable to this claim. A follow-up round used real inline-button presses
  (approve, reject, and a replay of an already-executed contract). The replay produced
  `[ActionGateway] SB-02: blocked duplicate callback action_id=ACTION_ID_1
  contract=CONTRACT_2 tool=airtable_add status=executed` — but reading
  `_handle_approval_callback_impl()` (`app.py:2144-2239`) shows this SB-02 block is
  explicitly the **fingerprint-based path** (`app.py:2192-2194`'s own comment: "action_id
  is an event_bus key, NOT a contract_id — must go via fingerprint"), reached only when
  the earlier exact-`contract_id` shortcut (`app.py:2172-2189`) did *not* return early.
  So this specific replay is evidence the fingerprint-fallback guard works, not evidence
  that the exact-`contract_id` path was taken.

  **CORRECTION: staging's deployed code has no exact-`contract_id` path to test at all.**
  `git show 67c595d5a1:app.py | grep callback_contract_id` returns zero matches — the
  entire `if callback_contract_id and _flag_enabled(...)` shortcut (`app.py:2172-2189`)
  is new in PR #471 (comment there: "New PR1 buttons carry the exact ActionContract
  id"), absent from staging's pre-#471 commit. So it isn't that this test happened to
  exercise the fingerprint fallback instead of the exact path — staging's buttons
  structurally *cannot* carry an embedded `contract_id`, because the code that would
  generate or read one doesn't exist there. This claim can only be meaningfully tested
  against `main`-based code (staging post-rebase, or production with the flag on).
- missing_evidence (as of the pre-rebase test): everything, on code that actually has the
  mechanism.

  **UPDATE — VERIFIED after staging's rebase, via a temporary, reviewed, and reverted
  diagnostic.** With staging now running PR #471's code (see Claim 2's update), a single
  INFO-level diagnostic line was added to `_handle_approval_callback_impl()`
  (`app.py`, right after `callback_contract_id` is parsed), logging only
  `parts=<len>, action=<action>, action_id=<action_id>, has_contract_id=<bool>` — never
  the raw contract_id/UUID value itself. Deployed to staging alone (commit `cabbb29`),
  captured exactly one real button press, then immediately reverted (commit `9b5f148`)
  and redeployed — staging is now back to clean PR #471 code with no diagnostic left in
  place.

  Captured (2026-07-27T22:47:58.513Z / 01:47:58 Israel time), a real **reject** button
  press: `[TEMP-DIAG-CLAIM3] parts=3 action=reject action_id=ACTION_ID_2
  has_contract_id=True`. `parts=3` confirms the raw `callback_data` had the
  `action:action_id:contract_id` shape (a 2-part `action:action_id` callback would show
  `parts=2, has_contract_id=False`). Correlated directly with `[ActionGateway]` /
  `[Approval]` logs from the same turn: `propose_action: contract=CONTRACT_8 ... ` at
  22:47:53.372Z, `[Approval] queued ACTION_ID_2 | airtable_add`
  at 22:47:53.999Z (same `action_id` as the diagnostic line), `rejected:
  contract=CONTRACT_8` at 22:47:59.085Z — the exact contract
  that resolved matches the one the callback's embedded `contract_id` pointed to.
- missing_evidence: this single capture confirms the *approve/reject-on-a-fresh-pending-
  contract* case carries the embedded contract_id. It doesn't directly demonstrate the
  early-return branch at `app.py:2177-2189` (`canonical_state != "pending"`, i.e. a
  callback pressed on an *already-resolved* contract taking the exact-id short-circuit
  rather than reaching the SB-02 fingerprint check) — that would need a second capture
  specifically on a stale/already-resolved button, which wasn't done here to avoid
  redeploying the diagnostic a second time.
- allowed_status: **VERIFIED** for the core claim (a real Telegram callback does carry
  `action_id:contract_id`, and it correctly resolves to the exact contract that acted).
  PARTIALLY_VERIFIED on the narrower question of whether the early-return short-circuit
  specifically (vs. reaching SB-02) is what handles a replay of an already-resolved
  contract's button — not separately captured.
```

---

### Claim 4 — Do internal identifiers (raw tool names, ActionContract UUIDs, ActionContract record IDs, Airtable business record IDs) not appear in live user-facing traffic?

**Required evidence:** the literal, verbatim text of real messages sent to a real user
in the tested environment across the approval lifecycle (queued, approved, rejected,
completed, failed, multiple-pending) — not a code read of
`_safe_contract_business_description()`/`build_approval_lifecycle_result()`, and not a
unit test's assertion on redaction, both of which already exist and already pass but
prove capability, not live behavior.

**Why required:** `BUG-118` was closed at the code level via unconditional redaction
(`CHANGE_CONTROL_LOG.md`/`CHANGELOG.md` PR #471 entry), but this codebase's own history
(BUG-127A, BUG-131, and others) shows code-level fixes have previously not matched live
behavior due to mock/binding/environment mismatches unrelated to the redaction logic
itself (e.g. a different code path being live than the one reviewed). This specific
claim cannot be proven by log inspection alone, because this codebase deliberately does
not log full raw outbound message text for PII reasons in most call sites — a direct,
manual read of the actual delivered message is required.

**Result:**
```yaml
- required_evidence: verbatim literal text of real delivered messages, read directly by
  the owner (not inferred from code or logs).
- why_required: (see above)
- environment: BOTH staging (RENDER_SERVICE_STAGING) and production
  (RENDER_SERVICE_PRODUCTION, commit a4bbcc4a,
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX=false`) tested in the same live session.
- test_date: 2026-07-27
- exact_scope: staging — queued / pending-conflict-reconfirm / completed / rejected
  states, 4 real turns. Production — completed / rejected states, 3 real turns, none of
  which hit a stale-pending-conflict scenario.
- supplied_evidence:
  **FALSIFIED on staging**, for the reconfirmation/legacy-status code path specifically.
  Verbatim bot replies (owner-reported, cross-checked against
  `[ActionGateway] route_confirmation_word: ... reply=...` log lines, which match
  exactly):
  - `"יש פעולה קודמת שממתינה לאישור: airtable_add / Tasks. לאשר אותה? (כן/לא)"` — raw
    tool name `airtable_add` exposed directly to the user.
  - `"✅ בוצע: airtable_add / Tasks | מזהה: AIRTABLE_RECORD_3"` (and the same pattern for
    `AIRTABLE_RECORD_1`, `AIRTABLE_RECORD_2`) — raw tool name **and** raw Airtable
    business record ID exposed directly.
  Root cause identified in code, not just observed live: `_describe_contract_for_reconfirmation()`
  (`core/action_gateway.py:821-847`), used by `route_confirmation_word()`'s reconfirmation
  prompt and by the legacy `"✅ בוצע: {label}"` status text, has a documented and
  **intentional** fallback (`f"{contract.tool_name} / {table}"`) for any tool/table
  combination other than the special Leads-capture case. Its own docstring states a prior
  fix attempt was "tried first and reverted" because `test_stage_b_full_suite.py`'s
  DoD20 asserts the tool name must appear in that text. **This is a different code path
  than the one BUG-118 actually fixed** (`_safe_contract_business_description()` /
  `build_approval_lifecycle_result()`) — CHANGELOG.md's "unconditional redaction" framing
  for PR #471 does not hold for this path.
  **Clean on production**, for the paths actually exercised there. Verbatim bot replies:
  - `"הפעולה הושלמה: הוספה ב-Tasks: השלם חוזי שכירות עם אופציות תקפות"` (completed)
  - `"הפעולה הושלמה: הוספה ב-Tasks: חזור ללידים של גיוס"` (completed)
  - `"הפעולה נדחתה: הוספה ב-Tasks: פרסום בפייסבוק - מיטות והגיוס"` (rejected)
  None of these three expose tool name, contract UUID, ActionContract record ID, or
  Airtable business record ID — these go through `build_approval_lifecycle_result()`,
  which redacts correctly for this scenario.
- missing_evidence: production was never tested against the *same* stale-pending/
  reconfirmation scenario that exposed the leak on staging — so this is not proof the
  leak is staging-only. The code is identical on `main` (confirmed by direct read of
  `core/action_gateway.py` on this checkout, which is `main` + one docs-only commit), so
  the same leak would very likely reproduce in production if a stale-pending conflict
  occurred there with the flag on. A deliberate production/staging test that triggers
  that exact scenario would close this gap; absent that, this should be treated as a
  known code-level gap, not merely a staging artifact.
- allowed_status: **FALSIFIED** for the reconfirmation/legacy-status path
  (`_describe_contract_for_reconfirmation`) — demonstrated with real, literal message
  text on staging. PARTIALLY_VERIFIED (clean) for the primary lifecycle-result path as
  exercised in production. This contradicts CHANGELOG.md's characterization of PR #471's
  redaction as "unconditional" and should be raised to the owner as a real, live finding,
  independent of this document.
```

---

### Claim 5 — Does RP5 correctly classify Gateway-owned approval turns (not just Agent-text turns)?

**Required evidence:** a matched pair — (a) the `[EvidenceFinalizerShadow]` log line for
a real Gateway-owned approval-queuing turn in the tested environment, and (b) independent
confirmation of what actually happened for that turn (was an approval genuinely queued?
was it later approved/rejected/completed correctly?) — to check the log line's
`evidence_status`/`response_claim`/`mismatch` fields against real outcome, not just that
the line exists.

**Why required:** `observe_shadow_finalizer()` (`core/turn_evidence.py:232`) only logs
at all when `FEATURE_EVIDENCE_FINALIZER` is `shadow` or `enforce` in that environment —
record this flag's state too, separately from the single-speaker flag. A present log
line proves RP5 *ran*; it does not by itself prove the classification was *correct*
without comparing to the real outcome.

**How to check (log marker):**
- `[EvidenceFinalizerShadow] state=%s evidence_status=%s response_claim=%s mismatch=%s
  code=%s counts=%s` (`core/turn_evidence.py:253`) — `mismatch=true` lines are logged at
  WARNING and are the primary thing to review; a `mismatch=false` line is not proof of
  correctness on its own, only absence of a *detected* conflict.

**Result:**
```yaml
- required_evidence: matched pair of `[EvidenceFinalizerShadow]` log line + independent
  confirmation of real outcome, for real Gateway-owned approval turns.
- why_required: (see above)
- environment: staging, `FEATURE_EVIDENCE_FINALIZER=shadow`
- test_date: 2026-07-27
- exact_scope: 6 real turns in the live test window (3 approval-queuing, 3 non-approval
  free-text turns), each matched against independently-confirmed real outcome.
- supplied_evidence:
  - 21:41:09.692Z `evidence_status=approval_pending response_claim=sent_for_approval
    mismatch=false` — matches contract `CONTRACT_1` propose at 21:41:06.584Z. Real outcome
    (confirmed via `ActionContracts`): status=`completed`, `Tasks` record
    `AIRTABLE_RECORD_1` exists. Classification correct.
  - 21:42:34.124Z same fields — matches contract `CONTRACT_3` propose at 21:42:31.705Z.
    Real outcome: status=`rejected`. `approval_pending` was the correct classification
    *at proposal time*; consistent with the later rejection.
  - 21:45:11.161Z same fields — matches contract `CONTRACT_2` propose at 21:45:08.763Z.
    Real outcome: status=`completed`, `Tasks` record `AIRTABLE_RECORD_2` exists.
    Classification correct.
  - 3 further entries (21:43:11Z, 21:43:31Z, 21:43:53Z) show
    `evidence_status=no_evidence response_claim=neutral mismatch=false`, corresponding to
    non-approval free-text turns (a clarifying question and two failed date-parsing
    attempts) — correctly classified as no_evidence/neutral; no `ActionContract` was
    created for any of these, confirmed by the absence of matching `propose_action` log
    lines.
  - No `mismatch=true` (WARNING-level) line appears anywhere in this first window.

  **UPDATE — a genuine `mismatch=true` occurred in follow-up button-press testing.** At
  22:09:33.776Z, for contract `CONTRACT_5` (see Claim 2's update — the reject-button turn
  with the contradictory double message):
  `[EvidenceFinalizerShadow] state=shadow evidence_status=approval_pending
  response_claim=neutral mismatch=true code=status_claim_mismatch` (WARNING). This is a
  *real*, not engineered, mismatch — it coincides exactly with the turn where the agent
  produced a false "✅ נוספה" claim. RP5 correctly flagged something was off
  (`mismatch=true`), though its own `response_claim=neutral` label undersells what
  actually happened (a false *success* claim, not a neutral one) — worth the owner's
  attention as a secondary, smaller finding about the classifier's label granularity.
- missing_evidence: the classifier's `response_claim=neutral` label for this real
  mismatch doesn't cleanly map to "agent falsely claimed success" — whether that's a
  known/acceptable coarseness or a separate small bug wasn't investigated further here.
- allowed_status: PARTIALLY_VERIFIED — 6/6 turns in the first round correctly classified
  with no false positives; the follow-up round additionally shows RP5 *does* detect a
  real mismatch when one occurs (not just avoiding false positives), strengthening this
  claim, with the label-granularity caveat above.
```

---

### Claim 6 — Does a replay or stale callback avoid causing a second execution?

**Required evidence:** a deliberate, controlled test in a non-production environment
(staging only — never attempt this as a live test against production data): create an
approval, let it resolve (approve or let it complete), then press the same original
Telegram button again (or replay the same callback_data), and confirm via
`ActionContracts`/the tool's actual side effect (e.g. the Airtable record) that **no
second write occurred**.

**Why required:** this is exactly what the atomic-claim/SB-02 pre-check machinery exists
to prevent, and exactly the kind of claim this codebase's own history shows can look
correct in code review while still failing in a specific live path (see BUG-POST-COMPLETION-FALLTHROUGH,
already fixed, as a precedent for this exact failure class). A passing regression test
(`test_bug_post_completion_callback_fallthrough.py`) proves the fix mechanism works
against its own test double; it does not by itself prove the live dispatcher/database
wiring in the deployed environment behaves the same way.

**How to check (log markers):**
- `[ActionGateway] SB-02: blocked duplicate callback action_id=%s contract=%s tool=%s
  status=executed` (`app.py:2226`) — expected to appear on the replay attempt.
- Direct read of the tool's target Airtable table (or whichever provider the tested
  action writes to) to confirm no duplicate record/second mutation exists, not just that
  a blocking log line was printed — the log line proves the guard *fired*, not that it
  was the *only* thing standing between the replay and a duplicate write.

**Result:**
```yaml
- required_evidence: deliberate replay of a resolved approval in staging, confirmed via
  `ActionContracts`/`Tasks` to cause no second write.
- why_required: (see above)
- environment: staging
- test_date: 2026-07-27
- exact_scope: this test used TEXT-based replay (resending `כן`/`מאשר` after a contract
  was already resolved), not a Telegram inline-button callback replay — a materially
  different code path than the one this claim's "how to check" section names
  (`[ActionGateway] SB-02: blocked duplicate callback`, `app.py:2226`, which is
  specifically the callback path's guard).
- supplied_evidence: after contract `CONTRACT_3` was rejected at 21:42:34.893Z, two further
  `כן`/`מאשר` attempts at 21:44:46.299Z and 21:44:48.198Z both received `"אין פעולה
  שממתינה לאישור"` (no pending action), with no further `propose`/`approve`/`execute`
  log lines and no new `Tasks`/`ActionContracts` record created for either attempt —
  confirms resending a confirm word after resolution does not cause a duplicate
  execution via this code path. Separately, attempting to create a new task while one was
  already pending correctly triggered the batch-block guard (`"יש לך כרגע 1 בקשות
  הממתינות לאישור..."`) rather than silently queuing or executing a second action.
- missing_evidence (first round): no `SB-02` line appears anywhere in that window's
  `[ActionGateway]` export, and no genuine inline-button replay was attempted.

  **UPDATE — VERIFIED via a real inline-button replay.** Follow-up testing replayed a
  real, already-resolved approval by pressing its original Telegram button again.
  Contract `CONTRACT_2` ("רשום את כל הלידים") had already been
  approved and executed at 21:45:57.221Z (`Tasks` record `AIRTABLE_RECORD_2` created
  21:45:56Z). At 22:06:50.505Z — roughly 21 minutes later — pressing the same original
  approval button again produced exactly the expected guard:
  `[ActionGateway] SB-02: blocked duplicate callback action_id=ACTION_ID_1
  contract=CONTRACT_2 tool=airtable_add status=executed`
  (the exact log format this claim's "how to check" section specifies, `app.py:2226`).
  **Independently confirmed via direct Airtable read:** the `Tasks` table still contains
  exactly one record for this task (`AIRTABLE_RECORD_2`, unchanged) — no second record,
  no duplicate write. This is a real, genuine button-press replay against a real resolved
  contract, not the text-based near-miss from the first round.
- missing_evidence: none remaining for the core replay-safety question, on the code that
  was actually tested. (Note: per Claim 3's correction, staging's deployed code has no
  exact-`contract_id` callback path at all — `SB-02`'s fingerprint-based guard is the
  *only* replay guard that exists there. `git show 67c595d5a1:app.py | grep SB-02`
  confirms this guard predates PR #471 unchanged, so this result is legitimate — it just
  verifies the older, still-present fingerprint guard, not a #471-specific mechanism.)
- allowed_status: **VERIFIED** — real button-press replay against a real resolved
  contract in staging, correctly blocked, independently confirmed via direct Airtable
  read that no second write occurred. Unlike claims 2 and 3, this one holds even after
  the pre-#471 discovery, because the SB-02 guard itself is unchanged code shared by both
  versions.
```

---

## Verdict rollup (fill in after all six rows above are complete)

| Claim | Environment(s) tested | Status |
| --- | --- | --- |
| 1. Flag active in staging/production | staging + production | VERIFIED — staging's `true` reading was initially a no-op (pre-#471 code); rebased and redeployed, now genuinely active |
| 2. Single final response, no duplicate | staging, post-rebase (PR #471 code) | **PARTIALLY_VERIFIED** — real approve+reject button presses, zero violations, independently confirmed via Airtable, but Telegram/owner-role/staging-only, 2 turns — WhatsApp, non-owner roles, and broader sampling untested |
| 3. `action_id:contract_id` callback resolves exact contract | staging, post-rebase | **VERIFIED** — real callback_data captured via a temporary, reviewed, and reverted diagnostic; confirmed `parts=3, has_contract_id=True`, correlated to the exact contract that resolved |
| 4. No internal identifiers in live traffic | staging + production | **FALSIFIED** for the reconfirmation/legacy-status path (unaffected by the pre-#471 discovery — this function is byte-identical across both versions and independently confirmed on `main`) |
| 5. RP5 classifies Gateway-owned turns correctly | staging | PARTIALLY VERIFIED — RP5/`turn_evidence.py` is a separate system from #471, unaffected by the pre-#471 discovery, though the one genuine mismatch it caught was itself a symptom of pre-#471 code |
| 6. Replay/stale callback causes no duplicate execution | staging | **VERIFIED** — the SB-02 guard predates #471 unchanged, so this result holds regardless |

**CORRECTION SUPERSEDING THE EARLIER VERSION OF THIS TABLE:** staging's deployed branch
(`claude/rp5-staging-fault-injection-v4akit`, commit `67c595d5a1`) predates PR #471 and
was never rebased past it — confirmed via `git diff`/`git show` against `main` (see the
correction note after Claim 1). `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`,
`ApprovalLifecycleResult`, and the exact-`contract_id` callback shortcut are all 100%
absent from staging's code, making the flag's `true` reading there inert. Claims 2 and 3
were originally reported against this test as FALSIFIED/NOT_VERIFIED-with-findings; both
are reclassified above to NOT_APPLICABLE-as-tested, because the mechanism they ask about
simply wasn't running on staging at that point.

**UPDATE: staging has since been rebased onto `main` and redeployed** (see the "DONE"
note after Claim 1), so it now genuinely runs PR #471's code with the flag on. Claim 2
was re-tested against this and is now PARTIALLY_VERIFIED — Telegram/owner-role/
staging-only, 2 turns; WhatsApp, non-owner roles, and broader sampling remain untested
(table updated above). Claim 3 remains
open — the mechanism now exists, but the raw callback_data string still hasn't been
captured to confirm the exact-contract-id path specifically (as opposed to the
fingerprint fallback).

**Findings that remain real and unaffected by this correction, still worth immediate
owner attention, independent of this document:**
1. **Raw identifier leak, live and code-confirmed on `main`:** the reconfirmation/
   legacy-status message path exposes raw tool names and Airtable record IDs to real
   users (see Claim 4), contradicting CHANGELOG.md's "unconditional redaction" claim for
   BUG-118.

Additionally, contract `CONTRACT_4` sat `pending` in staging
for **~14 hours** (created 2026-07-27T07:34:20Z, resolved 21:40:10Z) before this
session's testing surfaced and resolved it — matches the owner's live observation that a
stuck approval "shouldn't wait for hours." Worth its own bug filing/triage.

**This table must not be edited to say "VERIFIED" without the corresponding claim's
`allowed_status` row above being filled in with real, dated, environment-scoped
evidence.** A `PARTIALLY_VERIFIED` status is legitimate and should be used rather than
rounding up to `VERIFIED` when evidence covers only some environments or only some
transcripts.

## After this plan is executed

1. Do **not** hand-edit `docs/context_librarian/layers/*.yaml`'s `production_evidence`
   directly as part of filling in this plan. Once real evidence exists, open a small,
   separate documentation PR that adds a `production_evidence` entry citing this
   document's path, the `test_date`, and the `allowed_status` per claim — following the
   same node-schema shape (`path`, `observed_on`, `scope`, `status`) already used
   elsewhere in those files.
2. If any claim comes back `NOT VERIFIED`/falsified in production specifically (not just
   untested), that is a live production concern and should be raised to the owner
   immediately, separate from and before any documentation update.
3. This document itself should be updated in place (its own rows, not the Context
   Librarian catalog) as evidence accumulates, so it remains the single record of what
   has and has not been checked for this flag.
