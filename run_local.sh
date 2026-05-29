#!/usr/bin/env bash
# run_local.sh — הרצת Boss Bot מקומית עם ngrok
# שימוש: ./run_local.sh

set -e

# ── בדיקות תנאי מוקדם ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "❌  קובץ .env לא נמצא — צור אותו לפי .env.example"
    exit 1
fi

if ! command -v ngrok &> /dev/null; then
    echo "❌  ngrok לא מותקן."
    echo "    Mac:     brew install ngrok"
    echo "    Windows: https://ngrok.com/download"
    exit 1
fi

if ! python -c "import dotenv" &> /dev/null; then
    echo "📦 מתקין תלויות..."
    pip install -r requirements.txt -q
fi

# ── הפעלת ngrok ────────────────────────────────────────────────────
PORT=10000
echo "🌐 מפעיל ngrok על פורט $PORT..."
ngrok http $PORT --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# המתן ל-ngrok להתחיל
sleep 3

# שלוף את ה-URL הציבורי
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels \
    | python -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "❌  ngrok לא עלה — בדוק /tmp/ngrok.log"
    kill $NGROK_PID 2>/dev/null
    exit 1
fi

echo "✅ ngrok URL: $NGROK_URL"

# עדכן RENDER_APP_URL בסביבה (ללא שכתוב .env)
export RENDER_APP_URL="$NGROK_URL"
export SETUP_WEBHOOK=1

# ── הפעלת הבוט ─────────────────────────────────────────────────────
echo ""
echo "🤖 מפעיל Boss Bot..."
echo "   לעצור: Ctrl+C"
echo ""

# טעינת .env + הרצה
python -m dotenv -f .env run -- python app.py

# ניקוי ngrok בסיום
kill $NGROK_PID 2>/dev/null
