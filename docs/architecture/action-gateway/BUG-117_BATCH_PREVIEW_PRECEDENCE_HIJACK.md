# BUG-117 — Tier-2 batch lead-preview hijacked by Tier-1's unconditional precedence

**Status:** ✅ Fix implemented, tests green (11 new + full 140-file regression sweep clean), **not yet production-verified**.
**Scope:** narrow precedence fix between `app.py`'s `_CONFIRM_WORDS` handler and `core/lead_candidate_handler.py`. Same underlying root cause class as BUG-115 (stale `ActionContracts` never expire — BUG-114 §2 Q6 — making "Tier-1 has something live" a near-permanently-true, mostly-irrelevant signal), but a genuinely separate code path: BUG-115 fixed Tier-1-vs-Tier-1 hijacking (a fresh single-lead/general-approval prompt losing to old Tier-1 contracts); this fixes Tier-1-vs-Tier-2 hijacking (a fresh **batch** lead preview, which has no `ActionContract` at all, losing to old Tier-1 contracts). Not touched: BUG-114's fix, BUG-115's bookmark mechanism itself, `route_disambiguation()`, `route_cancellation_word()`/the `_CANCEL_WORDS` branch (out of scope — see §5).

## 1. Production evidence

```
BOSS: 📋 זיהיתי 2 לידים אפשריים בקבוצה:
      • יצחק גלבר (0527696084)
      • אהרון שמחה (0548421060)

      ענה "כן" לשמירת כולם, או "לא" לביטול. (בתוקף ל-30 דקות)

Eli: כן

BOSS: יש כמה פעולות הממתינות לאישור — איזו?
      • 1. הוספה ב-Tasks: בדוק פר4
      • 2. הוספה ב-Tasks: בדוק pull request
      ... (9 items total, all old/unrelated Tasks + Leads contracts)

      שלח את המספר (1, 2, ...) כדי לאשר פעולה ספציפית.
```

**Expected:** the "כן" confirms the freshly-shown 2-lead batch preview.
**Actual:** it fell into `ActionGateway`'s generic disambiguation of 9 old, unrelated contracts — the batch was never touched.

## 2. Root cause

The batch lead preview ("📋 זיהיתי N לידים אפשריים בקבוצה...") is produced by `core/lead_candidate_handler.py`'s Tier-2 clean-batch path (BUG-058) and stored via `_store_pending_preview()` → `session_store.py`'s `set_pending_lead_preview()`. Unlike the single-lead preview (BUG-056, converted to a real Tier-1 `ActionContract`), the batch preview is **not** an `ActionContract` — it's a plain session-store dict with its own 30-minute TTL, resolved later by `resolve_pending_lead_preview()`.

`app.py`'s `_CONFIRM_WORDS` branch (`app.py:2632` at the time of the bug) checked Tier-1 first, unconditionally:

```python
if _gw_cw.find_live_contracts(identity.memory_key):
    _gw_reply = _gw_cw.route_confirmation_word(...)
    ...
    return _gateway_reply_with_promotion(_gw_reply, identity.memory_key)

# BUG-058: no live Tier-1 ActionGateway contract — check the
# Tier-2 batch lead-preview next ...
```

The comment documented the assumption explicitly: *"Tier 1 always wins when both exist simultaneously"* (mirrored in `resolve_pending_lead_preview()`'s own docstring, `core/lead_candidate_handler.py:1415-1419` before this fix). That assumption was safe when Tier-1 contracts didn't linger — but BUG-114 already established pending `ActionContracts` never expire on their own (§2 Q6). So `find_live_contracts()` returning non-empty says nothing about *recency* — it's true almost permanently once a handful of contracts accumulate, exactly as observed here (9 old ones). The unconditional check meant the Tier-2 batch preview branch (`app.py:2665` at the time) was **never even reached** whenever any old Tier-1 contract existed, no matter how irrelevant.

This is the same failure mode BUG-115 fixed — but BUG-115's fix lives entirely *inside* `route_confirmation_word()` (a bookmark keyed to a specific `ActionContract`), which only gets a chance to run once `app.py` has already decided to call it. It never touched the outer `app.py` gate that decides *whether* to call Tier-1's resolver at all before considering Tier-2. Since the batch preview has no `ActionContract`, BUG-115's bookmark was never a candidate fix for this path.

## 3. Fix

New `core.lead_candidate_handler.should_prefer_batch_preview(canonical_user_id, chat_id)`:

```python
def should_prefer_batch_preview(canonical_user_id: str, chat_id: str) -> bool:
    preview = _ls.get_pending_lead_preview(chat_id)
    if preview is None:
        return False
    bookmark = _ls.get_last_prompted_contract(canonical_user_id)
    if bookmark is None:
        return True
    return preview.get("set_at", 0) > bookmark.get("set_at", 0)
```

Compares the Tier-2 batch preview's own `set_at` timestamp (already tracked, 1800s TTL, self-clearing via `get_pending_lead_preview()`) against BUG-115's Tier-1 `last_prompted_contract` bookmark's `set_at` (600s TTL, self-clearing via `get_last_prompted_contract()`). Whichever prompt is genuinely more recent wins. Does no expiry logic of its own — it only compares timestamps of whatever each pre-existing getter already considers live, so both TTL mechanisms remain exactly as they were.

`app.py`'s `_CONFIRM_WORDS` branch now calls this **before** the unconditional Tier-1 `find_live_contracts()` gate, and short-circuits to `resolve_pending_lead_preview()` when it returns `True`. When it returns `False` (no live Tier-2 preview, or Tier-1's bookmark is newer), execution falls through unchanged to the pre-existing logic — including the existing Tier-2 fallback further down (`app.py:2665`-ish, unchanged), which still runs as a safety net for edge cases.

### Note on key spaces (pre-existing, not introduced by this fix)

`chat_id` (Tier-2's key, e.g. a raw Telegram chat id) and `canonical_user_id`/`identity.memory_key` (Tier-1's key, e.g. `"boss_hq:eliyahu"`) are two different, pre-existing key spaces in this codebase — BUG-058 always keyed `pending_lead_preview` by `chat_id`, BUG-115 always keyed `last_prompted_contract` by `canonical_user_id`. `should_prefer_batch_preview()` looks each up under its own correct existing key; this fix does not introduce or resolve that discrepancy, just reads consistently with how each mechanism already stores its own state.

## 4. Test file structural note

`test_c89_preview_confirmation.py`'s `test_app_py_confirm_word_checks_gateway_before_flag_branch()` statically asserts `find_live_contracts()` appears in the source before the `FEATURE_ACTION_GATEWAY` flag branch, within a fixed-size character window from the `elif _lower in _CONFIRM_WORDS:` marker. Adding the new precedence check *before* the existing `find_live_contracts()` call pushed everything after it further from the marker — the window was widened (3000→5000 chars for the `find_live_contracts()`/flag-branch pair, 5000→6500 for the `_CANCEL_WORDS` check) with a comment explaining the second widening, mirroring the same adjustment BUG-058 already made once for the same reason. The invariant itself (`find_live_contracts()` precedes the flag branch) is unchanged.

## 5. Explicitly out of scope

- **`_CANCEL_WORDS` branch** — `route_cancellation_word()` has a different, arguably more consequential existing behavior (it cancels **all** live Tier-1 contracts when any exist, not just one) that is a separate topic from this fix and was not touched.
- **BUG-114's fix, BUG-115's bookmark mechanism itself, `route_disambiguation()`** — none touched.
- **No TTL/cleanup policy for stale `ActionContracts`** — still the same open item from BUG-114 §2 Q6; this fix (like BUG-115) works around its symptom for one more code path rather than addressing root accumulation.

## 6. Verification

- New `test_bug117_batch_preview_precedence.py` (11 checks): production reproduction (fresh batch preview, no Tier-1 bookmark → prefer Tier-2), no-preview regression (never prefer Tier-2), both-mechanisms-live recency comparisons in both directions, expired-preview and expired-bookmark edge cases (both self-clear correctly, no crash), chat_id isolation, and an end-to-end check that `resolve_pending_lead_preview()` actually confirms both leads in the batch once preferred.
- `test_c89_preview_confirmation.py` (9 checks, including the structural invariant with its widened window) re-run clean.
- `test_bug115_confirmation_routing_bookmark.py` (22 checks) re-run clean — no regression to BUG-115's own bookmark logic.
- Full regression sweep: all 140 `test_*.py` files, exit 0.
- `smoke_tests.py` PASS, `python3 -m compileall -q .` clean, `git diff --check` clean.
- **Not yet production-verified** — awaiting a real post-deploy sample: a batch lead preview (2+ leads) confirmed with "כן"/"מאשר" while multiple old, unrelated `ActionContracts` are simultaneously live, showing the batch resolves directly instead of falling into disambiguation.
