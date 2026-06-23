#!/usr/bin/env python3
"""
Daily Git Audit — Daily Integrity Check
בודק ענפות claude/* לא ממוזגות ל-main, פערי תיעוד מול ROADMAP, סכמות כפולות
ו-drift בין קוד למשתני סביבה (CORS/ALLOWED) — ומדווח לאליהו בטלגרם.
דוח בלבד — לא משנה קוד/ענפים/Airtable.

READ FIRST: ROADMAP.md הוא מקור האמת היחיד (ראה הכרזת הקובץ עצמו —
"מקור האמת היחיד. כל מסמך תכנון אחר הוא ARCHIVE"). BOSS_CURRENT_STATE.md/
CANONICAL_STATE.md הם ARCHIVE/snapshot ולא קובעים "done" — נבדקים רק אם
ROADMAP.md לא קיים. MAIN > DOCS: ה-hash של origin/main (נבדק ב-GOV-02 gate)
גובר על כל מסמך. FIXED != OPEN: סימון ✅/DONE במסמך לא מוכיח שהקומיט בפועל
מוזג ל-main — זה מה ש-check_unmerged_vs_roadmap() בודק. אם לא ניתן לאמת —
מסמנים UNVERIFIED, לא CRITICAL.

רץ ידנית או מה-scheduler (לא רשום כברירת מחדל) — שער GOV-02 חוסם הרצה על מידע ישן.

Usage: python daily_git_audit.py
"""
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from branch_cemetery_cleanup import get_unmerged_claude_branches

STALE_DAYS = 3
CRITICAL_BRANCH_COUNT = 10
RECENT_COMMIT_HOURS = 24

# ROADMAP.md ראשון בכוונה: הוא מקור האמת היחיד לפי הכרזת הקובץ עצמו.
# BOSS_CURRENT_STATE.md/CANONICAL_STATE.md הם ARCHIVE — נבדקים רק כ-fallback
# אם ROADMAP.md לא קיים.
_CANONICAL_DOC_PRIORITY = ["ROADMAP.md", "BOSS_CURRENT_STATE.md", "CANONICAL_STATE.md"]
_DONE_MARKERS = ("✅", "DONE", "VERIFIED", "MERGED", "הושלם", "מומש", "מוזג")
_STOPWORDS = {
    "fix", "add", "update", "fixed", "added", "updated", "the", "and",
    "for", "with", "this", "that", "from", "into", "also", "merge",
}


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


def _run(cmd: str) -> str:
    try:
        return subprocess.run(cmd.split(), capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return ""


def _parse_branches(raw: str) -> list[str]:
    branches = []
    for line in raw.splitlines():
        b = line.strip()
        if "claude/" not in b or "HEAD" in b:
            continue
        branches.append(b)
    return branches


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z֐-׿]{4,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


# מזהי פיצ'ר לפי קונבנציית הריפו (F3, W1, N03, D07, C53-A, A35.2, H2...) —
# סיגנל חד הרבה יותר מחפיפת מילים גנרית; זה ה-fallback היחיד כש-ID לא נמצא.
_ID_TOKEN_RE = re.compile(r"\b([A-Z]{1,3}\d{1,3}(?:\.\d+)?(?:-[A-Z])?)\b")
_MIN_KEYWORD_OVERLAP = 2


def _roadmap_claims_done(subject: str) -> bool:
    """FIXED != OPEN: בודק רק אם המסמך הנוכחי (ROADMAP.md > ARCHIVE) מסמן את הנושא כגמור."""
    if subject.lower().startswith("merge "):
        return False  # קומיטי merge הם רעש VCS, לא טענת פיצ'ר

    ids = set(_ID_TOKEN_RE.findall(subject))
    keywords = _keywords(subject)
    if not ids and not keywords:
        return False

    for doc_name in _CANONICAL_DOC_PRIORITY:
        doc = Path(doc_name)
        if not doc.exists():
            continue
        for line in doc.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not any(marker in line for marker in _DONE_MARKERS):
                continue
            if ids and ids & set(_ID_TOKEN_RE.findall(line)):
                return True
            if not ids and len(keywords & _keywords(line)) >= _MIN_KEYWORD_OVERLAP:
                return True
        break  # רק המסמך הראשון שקיים נחשב מקור אמת (ROADMAP.md אם קיים)
    return False


def check_unmerged_vs_roadmap() -> list[str]:
    """
    לכל ענף שלא מוזג ל-origin/main, בודק אם הקומיטים שבו מסומנים
    ✅/DONE/VERIFIED ב-ROADMAP.md (או ב-ARCHIVE אם ROADMAP.md לא קיים)
    בלי שהקומיט עצמו קיים ב-origin/main. מחזיר רשימת ממצאים, או [].
    """
    findings = []
    branches_raw = _run("git branch -r --no-merged origin/main")
    for branch in _parse_branches(branches_raw):
        commits = _run(f"git log origin/main..{branch} --oneline")
        for line in commits.splitlines():
            if " " not in line.strip():
                continue
            _commit_hash, subject = line.strip().split(" ", 1)
            if _roadmap_claims_done(subject):
                findings.append(f"{branch}: '{subject}' looks DONE in docs but not in origin/main")
    return findings


def _extract_tool_names(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    if path.endswith("schemas.py"):
        return re.findall(r'"name":\s*"([A-Za-z_][A-Za-z0-9_]*)"', text)
    return re.findall(r'^\s*"([A-Za-z_][A-Za-z0-9_]*)":\s*ToolMeta\(', text, re.MULTILINE)


def check_duplicate_schemas() -> list[str]:
    """
    סורק tools/schemas.py ו-tool_registry.py אחר שמות tool/function
    שמוגדרים פעמיים ומעלה. מחזיר רשימת "file: name (xN)", או [].
    """
    findings = []
    for f in ["tools/schemas.py", "tool_registry.py"]:
        names = _extract_tool_names(f)
        for name, count in Counter(names).items():
            if count > 1:
                findings.append(f"{f}: {name} defined {count}x")
    return findings


def check_recent_commits(hours: int = RECENT_COMMIT_HOURS) -> list[str]:
    """קומיטים שנכנסו ל-origin/main ב-N השעות האחרונות (מידע, לא ממצא)."""
    r = subprocess.run(
        ["git", "log", "origin/main", f"--since={hours} hours ago", "--oneline"],
        capture_output=True, text=True
    )
    return [line for line in r.stdout.splitlines() if line.strip()]


def check_cors_env_drift() -> list[str]:
    """
    משווה משתני סביבה הקשורים ל-CORS/ALLOWED שמוזכרים בקוד (tma_api.py)
    לעומת מה שמתועד ב-.env.example. מחזיר רשימת drift, או [].
    """
    findings = []
    code_path, env_path = Path("tma_api.py"), Path(".env.example")
    if not code_path.exists() or not env_path.exists():
        return findings

    code_vars = set(re.findall(
        r'os\.environ\.get\(\s*["\'](\w*(?:ALLOWED|CORS)\w*)["\']',
        code_path.read_text(encoding="utf-8", errors="ignore")
    ))
    documented_vars = set(re.findall(
        r'(\w*(?:ALLOWED|CORS)\w*)\s*=',
        env_path.read_text(encoding="utf-8", errors="ignore")
    ))
    for var in sorted(code_vars - documented_vars):
        findings.append(f"tma_api.py uses {var} — not documented in .env.example")
    return findings


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

    # אם לא ניתן לאמת מול live: UNVERIFIED, לא CRITICAL.
    unverified = AUDIT_MODE == "READ_ONLY"
    branch_count_label = "UNVERIFIED" if unverified else "CRITICAL"
    stale_branch_label = "UNVERIFIED — ענפות ישנות (לא אומת מול live)" if unverified else "MISSING merge — ענפות ישנות שלא מוזגו"

    report = "=" * 50
    report += f"\nDAILY GIT AUDIT — Daily Integrity Check\nMODE: {AUDIT_MODE}\n"
    report += "=" * 50

    branches = get_unmerged_claude_branches(days_old=STALE_DAYS)
    stale = [b for b in branches if b["stale"]]

    report += f"\n\nסה\"כ ענפות claude/* לא ממוזגות: {len(branches)}"
    report += f"\nישנות (>{STALE_DAYS} ימים): {len(stale)}"

    if len(branches) > CRITICAL_BRANCH_COUNT:
        report += f"\n\n{branch_count_label}: {len(branches)} ענפות לא ממוזגות (סף: {CRITICAL_BRANCH_COUNT})"

    if stale:
        report += f"\n\n{stale_branch_label}:\n"
        lines = [f"  {b['branch']} ({b['age_days']} ימים)" for b in stale[:15]]
        report += "\n".join(lines)
        if len(stale) > 15:
            report += f"\n  ... ועוד {len(stale) - 15}"

    if not branches:
        report += "\n\n✅ אין ענפות claude/* לא ממוזגות."

    recent_commits = check_recent_commits()
    report += f"\n\n📌 קומיטים ל-main ב-{RECENT_COMMIT_HOURS} השעות האחרונות:\n"
    report += "\n".join(recent_commits) if recent_commits else "none"

    report += "\n\n🔀 Unmerged-vs-Roadmap:\n"
    mismatches = check_unmerged_vs_roadmap()
    if mismatches and unverified:
        report += "[UNVERIFIED — cache mode]\n"
    if mismatches:
        report += "\n".join(mismatches[:10])
        if len(mismatches) > 10:
            report += f"\n  ... ועוד {len(mismatches) - 10}"
    else:
        report += "none"

    report += "\n\n🔁 Duplicate Schema Entries:\n"
    dupes = check_duplicate_schemas()
    report += "\n".join(dupes) if dupes else "none"

    report += "\n\n🌐 CORS/ALLOWED Env Drift:\n"
    drift = check_cors_env_drift()
    report += "\n".join(drift) if drift else "none"

    print(report)
    _send_telegram(report)


if __name__ == "__main__":
    main()
