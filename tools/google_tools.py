"""
google_tools.py — Google API integrations (Gmail, Drive, Calendar)
מבוסס על bot.py המקורי, מותאם לארכיטקטורת הכלים החדשה.

env vars נדרשים:
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_REFRESH_TOKEN
"""

import os
import base64
import logging
import httpx
from datetime import datetime, timedelta
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def get_google_token() -> str | None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        logger.warning("Google OAuth env vars missing")
        return None

    try:
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        return r.json().get("access_token")
    except Exception as e:
        logger.error(f"get_google_token error: {e}")
        return None


# ─── Gmail ────────────────────────────────────────────────────────────────────

def gmail_send(to: str, subject: str, body: str) -> str:
    """יוצר טיוטה ב-Gmail — לא שולח ישירות. תמיד טיוטה קודם."""
    token = get_google_token()
    if not token:
        return "❌ חסרים GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN"

    try:
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        r = httpx.post(
            "https://www.googleapis.com/gmail/v1/users/me/drafts",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"message": {"raw": raw}},
            timeout=15,
        )
        if r.status_code in (200, 201):
            return (
                f"📝 טיוטה נשמרה ב-Gmail ל-{to}\n"
                f"נושא: {subject}\n"
                f"⚠️ הטיוטה ממתינה לאישורך — לא נשלחה עדיין."
            )
        return f"❌ שגיאת Gmail {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ שגיאה ביצירת טיוטה: {e}"


def gmail_read(max_results: int = 5) -> str:
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = httpx.get(
            "https://www.googleapis.com/gmail/v1/users/me/messages",
            headers=headers,
            params={"maxResults": max_results},
            timeout=10,
        )
        messages = r.json().get("messages", [])
        if not messages:
            return "📬 אין הודעות חדשות."

        lines = [f"📬 {len(messages)} מיילים אחרונים:"]
        for msg in messages:
            info = httpx.get(
                f"https://www.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                headers=headers,
                timeout=10,
            ).json()
            snippet = info.get("snippet", "")
            lines.append(f"• {snippet[:120]}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה בקריאת מיילים: {e}"


# ─── Google Drive ─────────────────────────────────────────────────────────────

def drive_search(query: str) -> str:
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    # Sanitize: strip single-quotes to prevent Drive query injection
    safe_query = str(query).replace("'", "\\'")

    try:
        r = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "q": f"name contains '{safe_query}' and trashed = false",
                "fields": "files(name, webViewLink)",
            },
            timeout=10,
        )
        files = r.json().get("files", [])
        if not files:
            return f"לא נמצא כלום בדרייב עבור '{query}'."
        lines = [f"🔍 תוצאות דרייב עבור '{query}':"]
        for f in files:
            lines.append(f"• {f['name']}\n  🔗 {f.get('webViewLink', 'ללא קישור')}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה בחיפוש דרייב: {e}"


def drive_read_file(file_name: str) -> str:
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    # Sanitize: strip single-quotes to prevent Drive query injection
    safe_name = str(file_name).replace("'", "\\'")

    try:
        headers = {"Authorization": f"Bearer {token}"}
        search = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params={
                "q": f"name contains '{safe_name}' and trashed = false",
                "fields": "files(id, name, mimeType)",
            },
            timeout=10,
        )
        files = search.json().get("files", [])
        if not files:
            return f"לא נמצא קובץ בשם '{file_name}' בדרייב."

        file_id = files[0]["id"]
        mime = files[0].get("mimeType", "")

        if "google-apps" in mime:
            r = httpx.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
                timeout=15,
            )
        else:
            r = httpx.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
                timeout=15,
            )

        content = r.text[:3000]
        return f"📄 תוכן '{files[0]['name']}':\n{content}"
    except Exception as e:
        return f"❌ שגיאה בקריאת קובץ: {e}"


# ─── Google Calendar ──────────────────────────────────────────────────────────

def calendar_create_event(summary: str, start_time: str, duration_minutes: int = 60) -> str:
    """start_time: ISO format — '2025-06-01T14:00:00'"""
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
        }

        r = httpx.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event,
            timeout=15,
        )
        if r.status_code in (200, 201):
            return f"✅ אירוע '{summary}' נוצר ביומן ל-{start_dt.strftime('%d/%m/%Y %H:%M')}."
        return f"❌ שגיאת Calendar {r.status_code}: {r.text[:200]}"
    except ValueError:
        return f"❌ פורמט תאריך שגוי. השתמש ב-ISO: 2025-06-01T14:00:00"
    except Exception as e:
        return f"❌ שגיאה ביצירת אירוע: {e}"


def calendar_get_events(max_results: int = 5, days_ahead: int = 7) -> str:
    """שליפת אירועים קרובים מ-Google Calendar."""
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    try:
        from datetime import timezone
        now     = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        r = httpx.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "maxResults":  max_results,
                "orderBy":     "startTime",
                "singleEvents": "true",
                "timeMin":     now.isoformat(),
                "timeMax":     time_max.isoformat(),
            },
            timeout=10,
        )
        if r.status_code != 200:
            return f"❌ Calendar שגיאה {r.status_code}: {r.text[:200]}"

        items = r.json().get("items", [])
        if not items:
            return f"✅ אין אירועים ב-{days_ahead} הימים הקרובים."

        lines = [f"📅 {len(items)} אירועים קרובים:"]
        for ev in items:
            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "?"))
            lines.append(f"• {ev.get('summary','(ללא שם)')} — {start}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ שגיאה בשליפת אירועים: {e}"


def gmail_send_draft(draft_id: str) -> str:
    """שליחת טיוטה קיימת לפי draft ID."""
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    try:
        r = httpx.post(
            f"https://www.googleapis.com/gmail/v1/users/me/drafts/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"id": draft_id},
            timeout=15,
        )
        if r.status_code == 200:
            return f"📧 טיוטה {draft_id} נשלחה בהצלחה!"
        return f"❌ שגיאת Gmail {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ שגיאה בשליחת טיוטה: {e}"


def sheets_append(spreadsheet_name: str, row_data: list) -> str:
    """הוספת שורה לגוגל שיטס לפי שם הקובץ בדרייב."""
    token = get_google_token()
    if not token:
        return "❌ חסרים פרטי Google OAuth"

    try:
        headers = {"Authorization": f"Bearer {token}"}
        search  = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params={
                "q": f"name = '{spreadsheet_name}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false",
                "fields": "files(id, name)",
            },
            timeout=10,
        )
        files = search.json().get("files", [])
        if not files:
            return f"❌ לא נמצא קובץ שיטס בשם '{spreadsheet_name}' בדרייב."

        sid = files[0]["id"]
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/A1:append"
        body = {"range": "A1", "majorDimension": "ROWS", "values": [row_data]}
        r = httpx.post(url, headers=headers, params={"valueInputOption": "USER_ENTERED"},
                       json=body, timeout=10)
        if r.status_code == 200:
            return f"📊 שורה נוספה לטבלה '{spreadsheet_name}' בהצלחה."
        return f"❌ שגיאת Sheets {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ שגיאה בכתיבה לשיטס: {e}"
