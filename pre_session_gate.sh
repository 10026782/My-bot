#!/bin/bash
# PRE-SESSION BRANCH NOTICE — Warning by default, strict on request
#
# מטרה: לדווח על ענפים לא ממוזגים בלי לחסום עבודה לא קשורה.
# ריצה: בתחילת כל סשן, לפני git checkout -b
#
# שימוש: bash pre_session_gate.sh "<task-description>" [--strict]
# דוגמה: bash pre_session_gate.sh "fix schema cache"
# בדיקה מחמירה: bash pre_session_gate.sh "governance audit" --strict
#
# exit 0 = מותר להמשיך
# exit 1 = STOP — רק במצב --strict

TASK="${1:-unknown task}"
MODE="${2:-}"

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

# --- שלב 3: ברירת מחדל — אזהרה והמשך ---
echo ""
echo "======================================"
echo "WARNING — נמצאו ענפים לא ממוזגים; המשך מותר כברירת מחדל"
echo "======================================"
echo ""
echo "בדוק overlap של הענפים עם scope המשימה לפני פתיחת ענף חדש."
echo "אין לבצע merge או מחיקה אוטומטיים."
echo ""

# --- שלב 4: strict mode (אופציונלי) ---
if [ "$MODE" = "--strict" ]; then
  echo ""
  echo "STOP — strict mode: נדרשת החלטה לפני פתיחת ענף חדש."
  echo "השתמש בברירת המחדל עבור עבודה שאינה חופפת לענפים אלה."
  echo ""
  exit 1
fi

exit 0
