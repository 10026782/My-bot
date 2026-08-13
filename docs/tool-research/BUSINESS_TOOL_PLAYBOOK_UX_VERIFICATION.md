# SCOREBOS Business Tool Playbook UX Verification

## Current UX problems

The post-PR #631 renderer exposed dense inline steps, internal-sounding Hebrew, and Markdown links without a parse-mode guarantee. The webhook also sent the reply without a scoped preview flag.

## Canonical render contract

Every normal-user Business Tool recommendation now uses format_recommendation():

יש לי כלי מתאים לזה:

[Tool Name](internal-url)

מה הוא עושה
One concise purpose sentence.

איך משתמשים
• One operational step per line

חשוב
One bounded warning only when relevant.

עזרה נוספת
One short line only for useful optional_agent tools.

Internal registry fields, raw URL lines, approval language, and agent instructions are not rendered.

## Tools audited

All 13 enabled normal-user Business Tools in list_tools() were checked through the shared formatter for need-based and direct-name lookup. Operator and infrastructure candidates remain excluded.

## Wording changes

- מה זה עוזר → מה הוא עושה
- dense inline numbering → one bullet per line
- approval/governance wording → practical user guidance
- מקור אמת, production database, and similar internal terms → plain task-oriented language
- optional assistance appears only under עזרה נוספת and only when configured

## Privacy normalization

Each playbook has one bounded warning class: COPY_ONLY, NO_SENSITIVE_DATA, REDACT_FIRST, VERIFY_DESTINATION, or KEEP_ORIGINAL. No vague approval requirement is displayed.

## RTL decisions

Headings are isolated on their own lines. Steps use • on separate lines. Technical terms remain inside short lines rather than long numbered paragraphs. URLs occur only inside the Markdown link token and are not emitted as a standalone visible line.

## Formatter implementation

format_recommendation() is the only user-facing formatter. maybe_recommend() uses the same formatter for need and direct tool-name lookup. No per-tool renderer or new source of truth was added.

## Tests

The registry regression tests cover link shape, no raw URL line, no leaked Markdown image syntax, headings, separate steps, normalized wording, warning behavior, no-agent behavior, optional assistance, direct/need parity, all-tools rendering, operator hiding, and unknown-need non-invention.

## Preview/transport finding

Telegram uses Markdown in existing send paths, but the Business Tool reply previously used the default send call. The smallest scoped fix passes parse_mode=Markdown and disable_web_page_preview=True only when _out_meta[source_module] is business_tool_registry. No global transport behavior changed.

## Runtime verification checklist

After merge and deployment, verify at least PDF merge → BentoPDF, image compression → Squoosh, broken CSV → csv.repair, chart selection → RAWGraphs, JSON understanding → JSON Crack, and one additional tool such as SVGOMG. For each check clickable name, no raw URL or syntax, readable RTL headings/bullets, practical warning, and correct optional help.

## Unresolved issues

Live Telegram rendering requires post-deploy owner verification. Unit tests prove the contract and scoped transport selection, not the client-rendered result.

## VERDICT

### TOOLS AUDITED

13

### SHARED FORMATTER

PASS

### LINK UX

NEEDS RUNTIME VERIFICATION

### RTL

NEEDS RUNTIME VERIFICATION

### PRIVACY WORDING

PASS

### AGENT UX

PASS

### TRANSPORT CHANGE

PATCH PROPOSED

### NEXT STEP

Deploy the merged change and run the six-message Telegram runtime matrix.
