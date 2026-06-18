#!/usr/bin/env python3
"""
Daily Git Audit
בודק ענפות claude/* לא ממוזגות ל-main ומדווח ממצאים.
רץ ידנית או מה-scheduler (לא רשום כברירת מחדל) — שער GOV-02 חוסם הרצה על מידע ישן.

Usage: python daily_git_audit.py
"""
import os
from pathlib import Path

from branch_cemetery_cleanup import get_unmerged_claude_branches

STALE_DAYS = 3
CRITICAL_BRANCH_COUNT = 10


def _send_telegram(text: str) -> None:
    owner_chat_id = os.environ.get("OWNER_TELEGRAM_ID", "") or os.environ.get("ELIYAHU_CHAT_ID", "")
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not owner_chat_id or not token:
        print(f"[daily_git_audit] לא ניתן לשלוח טלגרם (חסר token/chat_id):\n{text}")
        return
    try:
        import telebot  # type: ignore
        telebot.TeleBot(token).send_message(int(owner_chat_id), text)
    except Exception as e:
        print(f"[daily_git_audit] שגיאת שליחת טלגרם: {e}")


def main():
    # ── GOV-02 GATE ──────────────────────────────────────────────────────
    import subprocess as _sp, json as _json
    from pathlib import Path as _Path

    _gate = _sp.run(["python3", "audit_truth_gate.py"], capture_output=True, text=True)
    if _gate.returncode == 1:
        # STOP mode — שלח הודעה ועצור בשקט
        try:
            _send_telegram("🚫 AUDIT ABORTED (GOV-02 STOP)\n" + _gate.stdout[-400:])
        except Exception:
            pass
        return

    _gate_state = _json.loads(_Path("audit_gate_state.json").read_text())
    AUDIT_MODE = _gate_state["_mode"]  # "FULL" | "READ_ONLY"
    # ── END GOV-02 GATE ──────────────────────────────────────────────────

    severity_prefix = "[UNVERIFIED] " if AUDIT_MODE == "READ_ONLY" else ""

    print("=" * 50)
    print("DAILY GIT AUDIT")
    print(f"MODE: {AUDIT_MODE}")
    print("=" * 50)

    branches = get_unmerged_claude_branches(days_old=STALE_DAYS)
    stale = [b for b in branches if b["stale"]]

    print(f"\nסה\"כ ענפות claude/* לא ממוזגות: {len(branches)}")
    print(f"ישנות (>{STALE_DAYS} ימים): {len(stale)}")

    if len(branches) > CRITICAL_BRANCH_COUNT:
        print(f"\n{severity_prefix}CRITICAL: {len(branches)} ענפות לא ממוזגות (סף: {CRITICAL_BRANCH_COUNT})")

    if stale:
        print(f"\n{severity_prefix}MISSING merge — ענפות ישנות שלא מוזגו:")
        for b in stale[:15]:
            print(f"  {b['branch']} ({b['age_days']} ימים)")
        if len(stale) > 15:
            print(f"  ... ועוד {len(stale) - 15}")

    if not branches:
        print("\n✅ אין ענפות claude/* לא ממוזגות.")


if __name__ == "__main__":
    main()
