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
from zoneinfo import ZoneInfo
from typing import Any

logger = logging.getLogger(__name__)

_TZ_IL = ZoneInfo("Asia/Jerusalem")


def _tool_result(
    *,
    ok: bool,
    tool: str,
    external_id: str = "",
    evidence: dict[str, Any] | None = None,
    user_message: str = "",
) -> dict:
    """Structured C53-A result contract for external write/send tools."""
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id or "",
        "evidence": evidence or {},
        "user_message": user_message,
    }


def _check_calendar_conflict(token: str, start_time: str, duration_minutes: int) -> str:
    """שולף אירועים חופפים ומחזיר string תיאורי, או '' אם אין חפיפה."""
    try:
        start_dt = datetime.fromisoformat(start_time)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=_TZ_IL)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        r = httpx.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin":      start_dt.isoformat(),
                "timeMax":      end_dt.isoformat(),
                "singleEvents": "true",
                "orderBy":      "startTime",
                "maxResults":   5,
            },
            timeout=8,
        )
        if r.status_code != 200:
            return ""  # לא ניתן לבדוק — ממשיך ביצירה
        items = r.json().get("items", [])
        if not items:
            return ""

        parts = []
        for ev in items:
            ev_start = ev.get("start", {}).get("dateTime", "")
            ev_name  = ev.get("summary", "(ללא שם)")
            try:
                ev_dt = datetime.fromisoformat(ev_start)
                parts.append(f"'{ev_name}' ({ev_dt.strftime('%H:%M')})")
            except Exception:
                parts.append(f"'{ev_name}'")
        return f"⚠️ כבר קיים ביומן: {', '.join(parts)}"
    except Exception as e:
        logger.warning(f"[CalendarConflict] {e}")
        return ""  # בדיקה נכשלה — ממשיך ביצירה


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

def gmail_send(to: str, subject: str, body: str) -> dict:
    """יוצר טיוטה ב-Gmail — לא שולח ישירות. תמיד טיוטה קודם."""
    token = get_google_token()
    if not token:
        return _tool_result(
            ok=False,
            tool="gmail_draft",
            user_message="❌ חסרים GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN",
        )

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
            data = r.json()
            draft_id = data.get("id", "")
            return _tool_result(
                ok=bool(draft_id),
                tool="gmail_draft",
                external_id=draft_id,
                evidence={
                    "draft_id": draft_id,
                    "to": to,
                    "subject": subject,
                    "response": data,
                },
                user_message=(
                    f"📝 טיוטה נשמרה ב-Gmail ל-{to}\n"
                    f"נושא: {subject}\n"
                    f"draft_id: `{draft_id}`\n"
                    f"⚠️ הטיוטה ממתינה לאישורך — לא נשלחה עדיין.\n"
                    f"לשליחה: gmail_send_draft(draft_id=\"{draft_id}\")"
                    if draft_id
                    else "❌ Gmail דיווח על יצירת טיוטה אבל לא החזיר draft_id."
                ),
            )
        return _tool_result(
            ok=False,
            tool="gmail_draft",
            evidence={"status_code": r.status_code, "body": r.text[:500]},
            user_message=f"❌ שגיאת Gmail {r.status_code}: {r.text[:200]}",
        )
    except Exception as e:
        return _tool_result(ok=False, tool="gmail_draft", user_message=f"❌ שגיאה ביצירת טיוטה: {e}")


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
        if r.status_code != 200:
            logger.error(f"[DriveSearch] HTTP {r.status_code}: {r.text[:200]}")
            return f"❌ שגיאת גישה לדרייב (HTTP {r.status_code}) — לא ניתן היה לבדוק את התוכן."
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
        if search.status_code != 200:
            logger.error(f"[DriveReadFile] HTTP {search.status_code}: {search.text[:200]}")
            return f"❌ שגיאת גישה לדרייב (HTTP {search.status_code}) — לא ניתן היה לבדוק את התוכן."
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

        if r.status_code != 200:
            logger.error(f"[DriveReadFile] HTTP {r.status_code}: {r.text[:200]}")
            return f"❌ שגיאת גישה לדרייב (HTTP {r.status_code}) — לא ניתן היה לקרוא את הקובץ."

        content = r.text[:3000]
        return f"📄 תוכן '{files[0]['name']}':\n{content}"
    except Exception as e:
        return f"❌ שגיאה בקריאת קובץ: {e}"


# ─── Google Calendar ──────────────────────────────────────────────────────────

def calendar_create_event(summary: str, start_time: str,
                          duration_minutes: int = 60, force: bool = False) -> dict:
    """
    start_time: ISO format — '2025-06-01T14:00:00'
    force=True  — קבע גם אם יש חפיפה ביומן
    """
    token = get_google_token()
    if not token:
        return _tool_result(ok=False, tool="calendar_create_event", user_message="❌ חסרים פרטי Google OAuth")

    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt   = start_dt + timedelta(minutes=duration_minutes)

        # בדיקת חפיפה — אלא אם force=True
        if not force:
            conflict = _check_calendar_conflict(token, start_time, duration_minutes)
            if conflict:
                return _tool_result(
                    ok=False,
                    tool="calendar_create_event",
                    evidence={"conflict": conflict, "start_time": start_dt.isoformat()},
                    user_message=(
                        f"{conflict}\n"
                        f"לקבוע '{summary}' ב-{start_dt.strftime('%H:%M')} בכל זאת? "
                        f"(אם כן — שלח שוב עם force=true)"
                    ),
                )

        event = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Jerusalem"},
        }
        r = httpx.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event,
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            event_id = data.get("id", "")
            html_link = data.get("htmlLink", "")
            ok = bool(event_id and html_link)
            return _tool_result(
                ok=ok,
                tool="calendar_create_event",
                external_id=event_id,
                evidence={
                    "event_id": event_id,
                    "htmlLink": html_link,
                    "summary": data.get("summary", summary),
                    "start": data.get("start", {}),
                    "end": data.get("end", {}),
                    "response": data,
                },
                user_message=(
                    f"✅ אירוע '{summary}' נוצר ביומן ל-{start_dt.strftime('%d/%m/%Y %H:%M')}.\n"
                    f"event_id: `{event_id}`\n"
                    f"🔗 {html_link}"
                    if ok
                    else "❌ Calendar דיווח על יצירה אבל לא החזיר event_id ו-htmlLink."
                ),
            )
        return _tool_result(
            ok=False,
            tool="calendar_create_event",
            evidence={"status_code": r.status_code, "body": r.text[:500]},
            user_message=f"❌ שגיאת Calendar {r.status_code}: {r.text[:200]}",
        )
    except ValueError:
        return _tool_result(
            ok=False,
            tool="calendar_create_event",
            user_message="❌ פורמט תאריך שגוי. השתמש ב-ISO: 2025-06-01T14:00:00",
        )
    except Exception as e:
        return _tool_result(ok=False, tool="calendar_create_event", user_message=f"❌ שגיאה ביצירת אירוע: {e}")


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


def gmail_send_draft(draft_id: str) -> dict:
    """שליחת טיוטה קיימת לפי draft ID."""
    token = get_google_token()
    if not token:
        return _tool_result(ok=False, tool="gmail_send_draft", user_message="❌ חסרים פרטי Google OAuth")

    try:
        r = httpx.post(
            f"https://www.googleapis.com/gmail/v1/users/me/drafts/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"id": draft_id},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            message_id = data.get("id", "")
            return _tool_result(
                ok=bool(message_id),
                tool="gmail_send_draft",
                external_id=message_id,
                evidence={
                    "message_id": message_id,
                    "draft_id": draft_id,
                    "thread_id": data.get("threadId", ""),
                    "response": data,
                },
                user_message=(
                    f"📧 טיוטה {draft_id} נשלחה בהצלחה.\nmessage_id: `{message_id}`"
                    if message_id
                    else "❌ Gmail דיווח על שליחה אבל לא החזיר message_id."
                ),
            )
        return _tool_result(
            ok=False,
            tool="gmail_send_draft",
            evidence={"status_code": r.status_code, "body": r.text[:500], "draft_id": draft_id},
            user_message=f"❌ שגיאת Gmail {r.status_code}: {r.text[:200]}",
        )
    except Exception as e:
        return _tool_result(ok=False, tool="gmail_send_draft", user_message=f"❌ שגיאה בשליחת טיוטה: {e}")


def sheets_append(spreadsheet_name: str, row_data: list) -> dict:
    """הוספת שורה לגוגל שיטס לפי שם הקובץ בדרייב."""
    token = get_google_token()
    if not token:
        return _tool_result(ok=False, tool="sheets_append",
                            user_message="❌ חסרים פרטי Google OAuth")

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
            return _tool_result(ok=False, tool="sheets_append",
                                user_message=f"❌ לא נמצא קובץ שיטס בשם '{spreadsheet_name}' בדרייב.")

        sid = files[0]["id"]
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/A1:append"
        body = {"range": "A1", "majorDimension": "ROWS", "values": [row_data]}
        r = httpx.post(url, headers=headers, params={"valueInputOption": "USER_ENTERED"},
                       json=body, timeout=10)
        if r.status_code == 200:
            resp = r.json()
            updated_range = resp.get("updates", {}).get("updatedRange", "")
            rows_appended = resp.get("updates", {}).get("updatedRows", len(row_data))
            return _tool_result(
                ok=True,
                tool="sheets_append",
                external_id=sid,
                evidence={
                    "spreadsheet_id": sid,
                    "spreadsheet_name": spreadsheet_name,
                    "updated_range": updated_range,
                    "rows_appended": rows_appended,
                },
                user_message=f"📊 שורה נוספה לטבלה '{spreadsheet_name}' בהצלחה. (range: {updated_range})",
            )
        return _tool_result(ok=False, tool="sheets_append",
                            evidence={"status_code": r.status_code},
                            user_message=f"❌ שגיאת Sheets {r.status_code}: {r.text[:200]}")
    except Exception as e:
        return _tool_result(ok=False, tool="sheets_append",
                            user_message=f"❌ שגיאה בכתיבה לשיטס: {e}")
