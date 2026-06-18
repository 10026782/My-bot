#!/usr/bin/env python3
"""
Branch Cemetery Cleanup
מזהה ענפות claude/* שלא מוזגו ל-main ומציע מחיקה.
רץ פעם אחת ידנית — לא חלק מה-scheduler.

Usage:
  python branch_cemetery_cleanup.py           # דוח בלבד
  python branch_cemetery_cleanup.py --delete  # מחק ישנות (>3 ימים)
"""
import subprocess, sys
from datetime import datetime, timezone


def get_unmerged_claude_branches(days_old: int = 3) -> list[dict]:
    result = subprocess.run(
        ["git", "fetch", "origin", "--prune"],
        capture_output=True, text=True
    )

    result2 = subprocess.run(
        ["git", "branch", "-r", "--no-merged", "origin/main"],
        capture_output=True, text=True
    )

    branches = []
    for line in result2.stdout.splitlines():
        branch = line.strip()
        if "claude/" not in branch or "HEAD" in branch:
            continue

        ts_out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", branch],
            capture_output=True, text=True
        ).stdout.strip()

        if not ts_out:
            continue

        age_days = (datetime.now(timezone.utc).timestamp() - int(ts_out)) / 86400
        branches.append({
            "branch": branch,
            "age_days": round(age_days, 1),
            "stale": age_days > days_old
        })

    return sorted(branches, key=lambda x: x["age_days"], reverse=True)


def main():
    print("\n🪦 BRANCH CEMETERY REPORT")
    branches = get_unmerged_claude_branches()
    stale  = [b for b in branches if b["stale"]]
    fresh  = [b for b in branches if not b["stale"]]

    print(f"סה\"כ ענפות claude/* לא ממוזגות: {len(branches)}")
    print(f"ישנות (>3 ימים): {len(stale)}")
    print(f"טריות (<3 ימים): {len(fresh)}")

    if fresh:
        print("\n⚠️  ענפות טריות — ייתכן שיש עבודה לממזג:")
        for b in fresh:
            print(f"  {b['branch']} ({b['age_days']} ימים)")

    if stale:
        print(f"\n🗑️  ישנות — מועמדות למחיקה ({len(stale)}):")
        for b in stale[:15]:
            print(f"  {b['branch']} ({b['age_days']} ימים)")
        if len(stale) > 15:
            print(f"  ... ועוד {len(stale) - 15}")

    if "--delete" in sys.argv:
        print("\n🗑️  מוחק ענפות ישנות...")
        deleted, failed = 0, 0
        for b in stale:
            name = b["branch"].replace("origin/", "")
            r = subprocess.run(
                ["git", "push", "origin", "--delete", name],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                print(f"  ✅ {name}")
                deleted += 1
            else:
                print(f"  ❌ {name} — {r.stderr.strip()[:60]}")
                failed += 1
        print(f"\nסיכום: {deleted} נמחקו, {failed} נכשלו")
    else:
        print("\n✅ כדי למחוק:")
        print("   python branch_cemetery_cleanup.py --delete")


if __name__ == "__main__":
    main()
