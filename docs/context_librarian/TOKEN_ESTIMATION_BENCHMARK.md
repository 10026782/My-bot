# Token Estimation Benchmark — N17 item 1

## Status: script written, not yet executed

`tools/context_librarian/librarian.py`'s token-budget check
(`_approximate_char_estimate()`, `_path_char_estimate()`) has always used
`ceil(chars / 4)` as a proxy for real Anthropic token usage. This is an
unvalidated heuristic, not a measured tokenizer count — English prose,
Hebrew text, and code do not all average 4 characters per token, and no
comparison against a real tokenizer had been run.

`tools/context_librarian/benchmark_token_estimate.py` builds a real bundle
for each of the 7 task profiles (using representative queries that pull in
the same Hebrew/English/code mix real bundles contain) and compares the
`chars / 4` estimate against a real token count from Anthropic's
`messages.count_tokens` API (already available via the `anthropic` package in
`requirements.txt` — no new dependency).

**This benchmark has not been run.** This development sandbox does not have
`ANTHROPIC_API_KEY` set, and the script fails closed rather than fabricating
numbers. Per this repository's own governance (`GOVERNANCE_RULES.md` Rule 15
— no claim without verification), the divisor stays at `4` until someone with
API access runs the script and this document is updated with the actual
output.

## How to run it

```bash
ANTHROPIC_API_KEY=<key> python3 tools/context_librarian/benchmark_token_estimate.py
```

Paste the full output below, under a dated heading, before changing
`_CHARS_PER_APPROXIMATE_TOKEN` in `librarian.py`. The script itself prints a
"conservative divisor" recommendation (the largest divisor that would not
have understated real token usage for any sampled bundle) — do not lower the
divisor by intuition; use that computed value.

## Why this matters

The `approximate_char_estimate_budget` line in every rendered bundle, and the
`build_bundle()` fail-closed check against `maximum_approximate_token_budget`,
both rely on this estimate never *understating* real usage — otherwise a
bundle could pass the budget check while actually exceeding the caller's real
token limit. A conservative (i.e. non-understating) divisor is the goal, not
the most "accurate" one on average.

## Results

_(none yet — see Status above)_
