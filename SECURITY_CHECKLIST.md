# 🔐 Boss Bot — Security Checklist

## מתי לבצע review

| טריגר | סוג בדיקה | זמן משוער |
|--------|-----------|-----------|
| קובץ חדש שנוגע ב-`dispatcher` / `crm` / `identity` / `auth` | מיידי לפני merge | 10 דקות |
| tool חדש נוסף | schema + registry + dispatcher | 15 דקות |
| role חדש נוסף | כל enforce rules מחדש | 20 דקות |
| endpoint חדש (webhook, worker) | auth + identity propagation | 10 דקות |
| 4 שבועות מהreview האחרון | סריקה מהירה | 15 דקות |
| 3 חודשים מהreview האחרון | review מלא | 60+ דקות |

---

## סריקה מהירה (15 דקות) — grep patterns

```bash
# 1. dispatch_tool ללא identity
grep -rn "dispatch_tool(" --include="*.py" | grep -v "identity"

# 2. _get/_post/_patch ללא tenant filter
grep -rn "def _get\|def _post\|def _patch" crm.py | grep -v "identity"

# 3. endpoint ללא auth
grep -rn "@app.route" --include="*.py" -A5 | grep -v "secret\|token\|abort"

# 4. כלי לא רשום ב-registry
grep -rn "case \"" tools/dispatcher.py | grep -v "#" | \
  sed 's/.*case "\(.*\)":.*/\1/' | \
  while read t; do grep -q "\"$t\"" tool_registry.py || echo "⚠️ לא ב-registry: $t"; done

# 5. import ישיר של tool functions (bypass dispatcher)
grep -rn "from crm import\|from airtable_tools import" --include="*.py" \
  | grep -v "dispatcher\|daily_digest\|daily_collector\|scheduler"
```

---

## צ'קליסט ידני לפני כל merge לmain

### שכבת Identity
- [ ] `dispatch_tool` מקבל `identity` בכל קריאה
- [ ] `run_agent` מוביל `identity` לאורך כל ה-tool loop
- [ ] `identity is None` → hard fail (לא fallback שקט)

### שכבת Tenant
- [ ] `crm._get()` — tenant filter פועל ל-external roles
- [ ] `airtable_security.enforce_tenant_scope()` נקרא לפני כל airtable raw tool
- [ ] `airtable_add` מוסיף `tenant_id` לרשומה חדשה

### שכבת Endpoints
- [ ] `/worker/trigger` — `X-Worker-Secret` header חובה
- [ ] `/webhook/*` — idempotency פועל
- [ ] אין endpoints חדשים ללא auth

### שכבת Registry
- [ ] כל tool חדש רשום ב-`tool_registry.py` עם `roles_allowed`
- [ ] כל tool חדש מוגדר ב-`tools/schemas.py`
- [ ] `gmail_read` — `roles_allowed={"owner"}` בלבד
- [ ] `crm_mark_payment_paid` — `requires_approval=True`

### שכבת Secrets
- [ ] אין tokens / secrets בלוגים (`logger.info`, `print`)
- [ ] `WORKER_SECRET` מוגדר ב-Render env
- [ ] `LAST_SECURITY_REVIEW` מעודכן אחרי כל review

---

## env vars נדרשים ב-Render

| Variable | מטרה | דוגמה |
|----------|------|-------|
| `WORKER_SECRET` | אימות `/worker/trigger` | מחרוזת אקראית ארוכה |
| `LAST_SECURITY_REVIEW` | תזכורת אבטחה אוטומטית | `2026-05-29` |
| `SECURITY_REMINDER_DAY` | יום בשבוע לתזכורת | `sunday` |
| `SECURITY_REMINDER_TIME` | שעת תזכורת | `09:00` |
| `DIGEST_CHAT_ID` | chat_id לקבלת התזכורות | מזהה טלגרם |

---

## היסטוריית Reviews

| תאריך | סוג | ממצאים עיקריים | סטטוס |
|-------|-----|----------------|-------|
| 2026-05-29 | review מלא | dispatch ללא identity, crm httpx ישיר, /worker/trigger ללא auth, Drive query injection | ✅ תוקן |
| 2026-06-12 | HIGH findings | /voice/incoming + /voice/step ללא Twilio auth; /schema ללא identity check; TMA query params → formula injection | ✅ תוקן |

---

*עדכן את הטבלה אחרי כל review.*
*עדכן `LAST_SECURITY_REVIEW` ב-Render אחרי כל review.*
