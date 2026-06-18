#!/bin/bash
# PRE-SESSION GATE — Branch Merge Enforcement
#
# מטרה: לעצור Claude Code מלפתוח ענף חדש כשיש ענף פתוח ולא ממוזג.
# ריצה: בתחילת כל סשן, לפני git checkout -b
#
# שימוש: bash pre_session_gate.sh "<task-description>"
# דוגמה: bash pre_session_gate.sh "fix schema cache"
#
# exit 0 = מותר להמשיך
# exit 1 = STOP — חייב טיפול לפני המשך

TASK="${1:-unknown task}"

echo "======================================"
echo "PRE-SESSION GATE"
echo "משימה: $TASK"
echo "======================================"

# --- שלב 1: בדוק ענפות claude/* לא ממוזגות ---
OPEN_BRANCHES=$(git branch -r --no-merged origin/main 2>/dev/null \
  | grep "claude/" \
  | grep -v HEAD \
  | sed 's/^[[:space:]]*//')

if [ -z "$OPEN_BRANCHES" ]; then
  echo ""
  echo "✅ אין ענפות claude/* פתוחות. ממשיך."
  echo "======================================"
  exit 0
fi

# --- שלב 2: הצג את הענפות הפתוחות ---
COUNT=$(echo "$OPEN_BRANCHES" | wc -l | tr -d ' ')
echo ""
echo "⛔ נמצאו $COUNT ענפות claude/* לא ממוזגות ל-main:"
echo ""
echo "$OPEN_BRANCHES" | head -10
if [ "$COUNT" -gt 10 ]; then
  REMAINING=$((COUNT - 10))
  echo "  ... ועוד $REMAINING ענפות"
fi

# --- שלב 3: הנחיות מה לעשות ---
echo ""
echo "======================================"
echo "STOP — נדרשת החלטה לפני פתיחת ענף חדש"
echo "======================================"
echo ""
echo "אפשרויות:"
echo "  A) checkout לענף קיים והמשך שם:"
echo "     git checkout <branch-name>"
echo ""
echo "  B) מזג ענף קיים ל-main לפני שממשיכים:"
echo "     git checkout main && git merge <branch-name>"
echo ""
echo "  C) קיבלת אישור מפורש מהמשתמש לפתוח ענף חדש בכל זאת:"
echo "     bash pre_session_gate.sh \"$TASK\" --force"
echo ""
echo "❌ אסור להריץ git checkout -b לפני בחירת אחת מהאפשרויות."
echo ""

# --- שלב 4: force override (עם תיעוד) ---
if [ "$2" = "--force" ]; then
  echo "⚠️  FORCE OVERRIDE — פתיחת ענף חדש למרות ענפות פתוחות."
  echo "⚠️  זה מותר רק אם קיבלת אישור מפורש מהמשתמש."
  echo "⚠️  תעד את הסיבה ב-commit message הראשון."
  echo ""
  exit 0
fi

exit 1
