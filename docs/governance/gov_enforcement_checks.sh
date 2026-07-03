#!/usr/bin/env bash
# Governance enforcement minimal checks (read-only heuristics)
# Run from repo root:
#   ./docs/governance/gov_enforcement_checks.sh [--full] [--include-docs] [--include-worktrees]

set -euo pipefail

MODE="quick"
INCLUDE_DOCS=0
INCLUDE_WORKTREES=0

for arg in "${@:-}"; do
  if [[ "$arg" == "--full" ]]; then
    MODE="full"
  elif [[ "$arg" == "--include-docs" ]]; then
    INCLUDE_DOCS=1
  elif [[ "$arg" == "--include-worktrees" ]]; then
    INCLUDE_WORKTREES=1
  elif [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
    cat <<'USAGE'
Usage: gov_enforcement_checks.sh [--full] [--include-docs] [--include-worktrees]

Default: quick mode (excludes docs/tests/output, worktrees, node_modules, and .git).
  --full               run the full heuristic suite
  --include-docs       include findings from docs, tests, output files
  --include-worktrees  include ./.c*/ and ./.claude/ directories
  --help               show this help
USAGE
    exit 0
  fi
done

EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=node_modules
  --exclude-dir=.venv
  --exclude-dir=__pycache__
  --exclude-dir=.pytest_cache
  --exclude-dir=.idea
  --exclude-dir=.github
)
RG_GLOBS=(
  --glob='!/.git/**'
  --glob='!/node_modules/**'
  --glob='!/.venv/**'
  --glob='!/**/__pycache__/**'
  --glob='!/.pytest_cache/**'
  --glob='!/.idea/**'
  --glob='!/.github/**'
)
RG_OPTIONS=(--hidden --line-number --no-heading --color=never)

if [[ "$INCLUDE_WORKTREES" -eq 0 ]]; then
  EXCLUDES+=(--exclude-dir='.c*' --exclude-dir=.claude)
  RG_GLOBS+=(--glob='!/.c*/**' --glob='!/.claude/**')
else
  RG_OPTIONS+=(--no-ignore)
fi

if [[ "$INCLUDE_DOCS" -eq 0 ]]; then
  EXCLUDES+=(--exclude-dir=docs)
  RG_GLOBS+=(--glob='!/docs/**')
fi

search_repo() {
  local pattern="$1"
  if command -v rg >/dev/null 2>&1; then
    rg "${RG_OPTIONS[@]}" -e "$pattern" "${RG_GLOBS[@]}" . || true
  else
    grep -r --line-number -I -E "$pattern" . "${EXCLUDES[@]}" || true
  fi
}
RESULT_FILE=$(mktemp)
trap 'rm -f "${RESULT_FILE}"' EXIT

declare -A COUNT
declare -A FINDINGS_SHOWN
declare -A FILES_AFFECTED
declare -A WAS_CAPPED
declare -A SEEN_FILE

append_finding() {
  local family="$1" fileline="$2" class="$3" message="$4"
  local file="${fileline%%:*}"
  local current=${COUNT[$family]:-0}
  COUNT[$family]=$((current + 1))
  if [ "$current" -lt 10 ]; then
    printf '%s|%s|%s|%s\n' "$family" "$fileline" "$class" "$message" >> "$RESULT_FILE"
    FINDINGS_SHOWN[$family]=$((${FINDINGS_SHOWN[$family]:-0} + 1))
    # Track unique files
    local seen_key="${family}|${file}"
    if [[ -z "${SEEN_FILE[$seen_key]+x}" ]]; then
      SEEN_FILE[$seen_key]=1
      FILES_AFFECTED[$family]=$((${FILES_AFFECTED[$family]:-0} + 1))
    fi
  elif [ "$current" -eq 10 ]; then
    WAS_CAPPED[$family]=true
  fi
  return 0
}

emit_family() {
  local family="$1" title="$2"
  local printed=0
  while IFS='|' read -r fam fileline class message; do
    if [[ "$fam" == "$family" ]]; then
      if [ "$printed" -eq 0 ]; then
        echo "--- $title ---"
      fi
      printf '%s: %s: %s\n' "$class" "$fileline" "$message"
      printed=1
    fi
  done < "$RESULT_FILE"
}

print_summary() {
  echo "GOV CHECKS: mode=$MODE (include_docs=$INCLUDE_DOCS include_worktrees=$INCLUDE_WORKTREES)"
  echo "Summary:"
  for family in gateway missing_auth false_success dual_mechanism; do
    local shown=${FINDINGS_SHOWN[$family]:-0}
    local files=${FILES_AFFECTED[$family]:-0}
    local capped=${WAS_CAPPED[$family]:-false}
    printf '  %s: findings_shown=%d files_affected=%d capped=%s\n' "$family" "$shown" "$files" "$capped"
  done
  echo
}

run_quick() {
  local patterns='airtable_add\(|airtable_update\(|httpx\.post|requests\.post|telebot\.send(_message)?|sheets_append|drive_.*upload|drive_.*append'

  while IFS= read -r line; do
    file="${line%%:*}"
    file="${file//\\//}"
    rest="${line#*:}"
    fileline="${file}:${rest%%:*}"
    if [[ "$INCLUDE_DOCS" -eq 0 && "$file" =~ (^|/)(tests?|docs?|output)/ ]]; then
      continue
    fi
    append_finding gateway "$fileline" WARN_TRUE "gateway bypass outside dispatcher/media_gateway"
    if [[ "${WAS_CAPPED[gateway]:-false}" == "true" ]]; then
      break
    fi
  done < <(search_repo "$patterns" | grep -vE '\.git/|\.venv/|__pycache__/' || true)

  while IFS= read -r line; do
    file="${line%%:*}"
    file="${file//\\//}"
    rest="${line#*:}"
    fileline="${file}:${rest%%:*}"
    if [[ "$INCLUDE_DOCS" -eq 0 && "$file" =~ (^|/)(tests?|docs?|output)/ ]]; then
      continue
    fi
    if ! grep -qE 'identity|role|ownership' "$file"; then
      append_finding missing_auth "$fileline" WARN_REVIEW "endpoint missing identity/role/ownership check"
      if [[ "${WAS_CAPPED[missing_auth]:-false}" == "true" ]]; then
        break
      fi
    fi
  done < <(search_repo '^def .*(_approve|approve|callback|action)\s*\(' | grep -vE '/test_|/tests?/|\.git/|\.venv/|__pycache__/' || true)

  while IFS= read -r line; do
    file="${line%%:*}"
    file="${file//\\//}"
    rest="${line#*:}"
    fileline="${file}:${rest%%:*}"
    if [[ "$INCLUDE_DOCS" -eq 0 && "$file" =~ (^|/)(tests?|docs?|output)/ ]]; then
      continue
    fi
    append_finding false_success "$fileline" WARN_REVIEW "success/counter/completed/status without evidence/result/status_code"
    if [[ "${WAS_CAPPED[false_success]:-false}" == "true" ]]; then
      break
    fi
  done < <(search_repo '\b(business_success|completed|counter|status)\b' | grep -vE 'status_code|result|evidence|response|return|\.git/|\.venv/|__pycache__/' || true)

  while IFS= read -r line; do
    file="${line%%:*}"
    file="${file//\\//}"
    rest="${line#*:}"
    fileline="${file}:${rest%%:*}"
    if [[ "$INCLUDE_DOCS" -eq 0 && "$file" =~ (^|/)(tests?|docs?|output)/ ]]; then
      continue
    fi
    append_finding dual_mechanism "$fileline" WARN_REVIEW "raw feature flag env access bypasses registry"
    if [[ "${WAS_CAPPED[dual_mechanism]:-false}" == "true" ]]; then
      break
    fi
  done < <(search_repo "os\.getenv\(\s*[\"']FEATURE_|os\.environ\.get\(\s*[\"']FEATURE_" | grep -vE '\.git/|\.venv/|__pycache__/' || true)

  while IFS= read -r line; do
    file="${line%%:*}"
    file="${file//\\//}"
    rest="${line#*:}"
    fileline="${file}:${rest%%:*}"
    if [[ "$INCLUDE_DOCS" -eq 0 && "$file" =~ (^|/)(tests?|docs?|output)/ ]]; then
      continue
    fi
    append_finding dual_mechanism "$fileline" WARN_TRUE "direct tool implementation import bypasses dispatcher"
    if [[ "${WAS_CAPPED[dual_mechanism]:-false}" == "true" ]]; then
      break
    fi
  done < <(search_repo 'from .* import .*airtable_tools|import airtable_tools|from .* import .*gmail_tools|import gmail_tools|from .* import .*calendar_tools|import calendar_tools|from tools\.airtable_tools|from tools\.google_tools' | grep -vE '\.git/|\.venv/|__pycache__/' || true)
}

run_full() {
  echo "Running full checks is supported but may be noisy. Use --full only for full audit runs."
  exit 0
}

run_checks() {
  if [[ "$MODE" == "full" ]]; then
    run_full
  else
    run_quick
  fi
}

run_checks
print_summary
emit_family gateway "Gateway bypass"
emit_family missing_auth "Missing auth"
emit_family false_success "False success"
emit_family dual_mechanism "Dual mechanism"

exit 0
