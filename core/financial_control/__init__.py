"""Private Financial Control Center (FCC) — owner-of-record personal finance.

Pure calculation (``calc``), owner-scoped service (``service``) and the
free-text writer planner (``writer``). Nothing here writes to Airtable
directly: writes are proposed through the canonical ActionGateway path.
"""
