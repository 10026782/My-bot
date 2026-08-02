#!/usr/bin/env bash
set -euo pipefail
python3 -m tools.context_librarian refresh-after-merge --check
