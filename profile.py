"""
profile.py — User Profile Layer (Airtable Backend)
זיכרון ארוך טווח ב-Airtable במקום דיסק מקומי.
טבלה: Profile | שורה אחת בלבד | שדה ProfileData = JSON כ-Long Text.

הגדרת הטבלה ב-Airtable:
  שם טבלה: Profile
  שדות:
    - Name        (Single line text) — ערך קבוע: "main"
    - ProfileData (Long text)        — ה-JSON המלא
"""

import json
import os
import time
import requests
from threading import Lock
from datetime import datetime

_lock = Lock()

# ─── Airtable Config ──────────────────────────────────────────────────────────
_AT_TOKEN   = os.environ.get("AIRTABLE_TOKEN", "")
_AT_BASE    = os.environ.get("AIRTABLE_BASE_ID", "")
_AT_TABLE   = os.environ.get("AIRTABLE_PROFILE_TABLE", "Profile")
_AT_HEADERS = {"Authorization": f"Bearer {_AT_TOKEN}", "Content-Type": "application/json"}
_AT_URL     = f"https://api.airtable.com/v0/{_AT_BASE}/{_AT_TABLE}"

# ─── Cache קצר (60 שניות) — לא קוראים Airtable בכל הודעה ─────────────────────
_cache: dict = {"profile": None, "record_id": None, "ts": 0}
_CACHE_TTL = 60

# ─── ברירת מחדל ───────────────────────────────────────────────────────────────
DEFAULT_PROFILE = {
    "name": "אלייהו",
    "tone": "direct",
    "active_projects": [],
    "goals": [],
    "focus_areas": [],
    "known_contacts": {},
    "preferences": {
        "response_length": "short",
        "risk_sensitivity": "high",
        "language": "he",
    },
    "events": [],
    "reminders_pending": [],
    "last_updated": None,
}


# ─── Load / Save ──────────────────────────────────────────────────────────────
def load_profile() -> dict:
    with _lock:
        # החזר מ-cache אם טרי
        if _cache["profile"] and (time.time() - _cache["ts"]) < _CACHE_TTL:
            return dict(_cache["profile"])

        try:
            r = requests.get(
                _AT_URL,
                headers=_AT_HEADERS,
                params={"filterByFormula": "{Name}='main'", "maxRecords": 1},
                timeout=10,
            )
            r.raise_for_status()
            records = r.json().get("records", [])

            if records:
                rec = records[0]
                raw = rec["fields"].get("ProfileData", "{}")
                profile = json.loads(raw)
                merged = {**DEFAULT_PROFILE, **profile}
                _cache["profile"] = merged
                _cache["record_id"] = rec["id"]
                _cache["ts"] = time.time()
                return dict(merged)
            else:
                # שורה לא קיימת — צור אותה
                _create_profile_record()
                return dict(DEFAULT_PROFILE)

        except Exception as e:
            print(f"[profile] load error: {e}", flush=True)
            return dict(DEFAULT_PROFILE)


def save_profile(profile: dict):
    with _lock:
        profile["last_updated"] = datetime.now().isoformat()
        payload = json.dumps(profile, ensure_ascii=False)

        try:
            record_id = _cache.get("record_id")

            if record_id:
                r = requests.patch(
                    f"{_AT_URL}/{record_id}",
                    headers=_AT_HEADERS,
                    json={"fields": {"ProfileData": payload}},
                    timeout=10,
                )
            else:
                r = requests.post(
                    _AT_URL,
                    headers=_AT_HEADERS,
                    json={"fields": {"Name": "main", "ProfileData": payload}},
                    timeout=10,
                )
                _cache["record_id"] = r.json().get("id")

            r.raise_for_status()
            _cache["profile"] = profile
            _cache["ts"] = time.time()

        except Exception as e:
            print(f"[profile] save error: {e}", flush=True)


def _create_profile_record():
    try:
        payload = json.dumps(DEFAULT_PROFILE, ensure_ascii=False)
        r = requests.post(
            _AT_URL,
            headers=_AT_HEADERS,
            json={"fields": {"Name": "main", "ProfileData": payload}},
            timeout=10,
        )
        r.raise_for_status()
        _cache["record_id"] = r.json().get("id")
        _cache["profile"] = dict(DEFAULT_PROFILE)
    except Exception as e:
        print(f"[profile] create error: {e}", flush=True)


# ─── Event Processing ─────────────────────────────────────────────────────────
def process_events(events: list) -> list:
    alerts = []
    today = datetime.now().date()

    for e in events:
        try:
            etype = e.get("type")

            if etype == "birthday":
                d = datetime.fromisoformat(e["date"]).date().replace(year=today.year)
                days_left = (d - today).days
                remind_before = e.get("remind_days_before", 3)
                if 0 <= days_left <= remind_before:
                    suffix = "היום! 🎂" if days_left == 0 else f"בעוד {days_left} ימים"
                    alerts.append(f"🎂 {e['title']} — {suffix}")

            elif etype == "shabbat":
                if today.weekday() in (4, 5):
                    alerts.append("🕯️ ערב שבת / שבת — בדוק לוחות זמנים")

            elif etype == "deadline":
                d = datetime.fromisoformat(e["date"]).date()
                days_left = (d - today).days
                if 0 <= days_left <= e.get("remind_days_before", 2):
                    suffix = "היום!" if days_left == 0 else f"בעוד {days_left} ימים"
                    alerts.append(f"⏰ דד-ליין: {e['title']} — {suffix}")

        except Exception:
            continue

    return alerts


# ─── Profile → System Prompt ──────────────────────────────────────────────────
def build_profile_context(profile: dict) -> str:
    lines = ["\n--- הקשר אישי (זיכרון ארוך טווח) ---"]

    if profile.get("active_projects"):
        lines.append(f"פרויקטים פעילים: {', '.join(profile['active_projects'])}")

    if profile.get("goals"):
        lines.append(f"מטרות עכשוויות: {' | '.join(profile['goals'][:3])}")

    if profile.get("focus_areas"):
        lines.append(f"תחומי עיסוק: {', '.join(profile['focus_areas'])}")

    if profile.get("known_contacts"):
        contacts = ", ".join(
            f"{n} ({r})" for n, r in list(profile["known_contacts"].items())[:5]
        )
        lines.append(f"אנשי קשר: {contacts}")

    risk = profile.get("preferences", {}).get("risk_sensitivity", "high")
    lines.append(f"רמת ספקנות: {risk}")

    alerts = process_events(profile.get("events", []))
    if alerts:
        lines.append("התראות להיום: " + " | ".join(alerts))

    lines.append("--- סוף הקשר אישי ---")
    return "\n".join(lines)


# ─── Update Helpers ───────────────────────────────────────────────────────────
def add_project(name: str):
    p = load_profile()
    if name not in p["active_projects"]:
        p["active_projects"].append(name)
        save_profile(p)


def remove_project(name: str):
    p = load_profile()
    p["active_projects"] = [x for x in p["active_projects"] if x != name]
    save_profile(p)


def add_goal(goal: str):
    p = load_profile()
    if goal not in p["goals"]:
        p["goals"].insert(0, goal)
        p["goals"] = p["goals"][:10]
        save_profile(p)


def add_contact(name: str, role: str):
    p = load_profile()
    p["known_contacts"][name] = role
    save_profile(p)


def update_preference(key: str, value):
    p = load_profile()
    p["preferences"][key] = value
    save_profile(p)
