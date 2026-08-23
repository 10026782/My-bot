# C02–C04 Remediation 2 — Findings #7 + #8

## Historical findings — preserved

Finding #7: `media_handler.py` logged raw transcript content and raw prefix
detection samples. This exposed user/business content in operational logs.

Finding #8: `app.py` logged raw tool input and raw tool result content around
the agent tool invocation path. This exposed CRM/business payloads in logs.

## Remediation note

Truth-reset against `origin/main` at `38a382cdee9481e8c4f0418166a069d4a2458455`
confirmed both findings. The content-bearing logs were replaced with metadata:
source, character counts, action outcome, prefix-match count, tool name, input
key count, and result type. The typing-indicator `except: pass` was changed to a
debug log containing only the exception class. Dispatch and media behavior were
not changed.

Status: implemented locally and locally verified; no production writes, merge,
or deployment. Final production verification is not performed.
