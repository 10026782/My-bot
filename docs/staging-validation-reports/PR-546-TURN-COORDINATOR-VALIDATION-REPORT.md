# דוח אימות Staging — PR #546 ו־Turn Coordinator

**תאריך:** 3 באוגוסט 2026
**סביבה:** `my-bot-approval-staging`
**בסיס Airtable:** `בסיס עיקרי`

---

## 1. מטרת האימות

לאמת לאחר מיזוג PR #546 את מסלול `create_task`, בדגש על:

- נרמול prefix, רווחים ו־NBSP.
- קנוניזציה של תאריך ושעה.
- יצירת fingerprint עסקי יציב.
- חסימת קלט תאריך או שעה פגומים.
- הפרדה בין `fingerprint_payload` לבין payload הכתיבה.
- מניעת תשובות כפולות.
- אימות חלקי של מסלול Turn Coordinator החי.

---

## 2. בדיקות שעברו

### 2.1 — Prefix אינו מפיל ל־Agent

**בקשה:**
```
Eli: צור משימה לבדוק משהו
```

**תוצאה:** זוהתה כ־`create_task` ונשארה במסלול הדטרמיניסטי.

**הוכחות:**
- `intent=create_task`
- `handler=tool`
- `agent_calls=0`
- `action_tool=airtable_add`
- `created_this_turn=True`
- `reply_owner=gateway`

**סטטוס:** ✅ עבר

---

### 2.2 — קלט תאריך פגום

**בקשה:**
```
צור משימה לבדוק תאריך פגום עד 35/8/26 בשעה 19:00
```

**תשובת הבוט:**
```
לא בטוח שהבנתי את כותרת המשימה או את התאריך/שעה. נא לנסח מחדש, בלי תיקון אוטומטי של שגיאות כתיב.
```

**הוכחות:**
- `intent=create_task`
- `handler=clarify`
- `agent_calls=0`
- לא נוצר `ActionContract`
- לא בוצע `airtable_add`
- לא נכתב לטבלת `משימות (Tasks)`

**סטטוס:** ✅ עבר — fail-closed כמתוכנן

---

### 2.3 — קלט שעה פגומה

**בקשה:**
```
צור משימה לבדוק שעה פגומה עד 9/8/26 בשעה 29:00
```

**תוצאה:** `clarification` בלבד, אין Agent, אין ActionContract, אין write.

**סטטוס:** ✅ עבר — fail-closed כמתוכנן

---

### 2.4 — שינוי אמיתי בכותרת מייצר זהות חדשה

**בקשה 1:**
```
צור משימה לבדוק את אימות 546
```

**בקשה 2:**
```
צור משימה לבדוק את אימות 546 המעודכן
```

**תוצאה:**
- fingerprint חדש נוצר ליישק אחד
- `ActionContract` חדש בstatus `pending`

**סטטוס:** ✅ עבר

---

### 2.5 — שינוי אמיתי בתאריך מייצר זהות חדשה

**בקשה 1:** `...עד למחר...` → fingerprint: `44f0c005fdb1...`

**בקשה 2:** `...עד 5/8/26...` → fingerprint חדש

**תוצאה:** `ActionContract` חדש נוצר.

**סטטוס:** ✅ עבר

---

### 2.6 — שינוי אמיתי בשעה מייצר זהות חדשה

**בקשה 1:** `...בשעה 19:00` → fingerprint: `3e79afbdc541...`

**בקשה 2:** `...בשעה 20:00` → fingerprint: `76e5eb2f8e74...`

**סטטוס:** ✅ עבר — שעה משתתפת בזהות העסקית

---

### 2.7 — NBSP ורווחים שונים מנורמלים לאותה זהות

**נוסח רגיל:**
```
צור משימה הדבקת מודעות לביקוש נרחב בכל נושא התשתיות עד 9/8/26 בשעה 19:00
```

**נוסח עם NBSP, רווחים כפולים:**
```
צור משימה הדבקת מודעות לביקוש נרחב בכל נושא התשתיות עד  9/8/26  בשעה19:00
```

**תוצאה:** לאחר ביטול הראשון, השני זוהה כאותה פעולה:
```
יצירת המשימה כבר בוטלה
```

**סטטוס:** ✅ עבר — נרמול עבד כמתוכנן

---

### 2.8 — אין כתיבה לפני approval

**בדיקה:** בכל בקשות ה־pending:
- נוצר `ActionContract` בלבד
- בוצע PATCH ל־`Sessions` בלבד
- לא בוצע POST לטבלת `משימות (Tasks)` לפני אישור

**סטטוס:** ✅ עבר

---

### 2.9 — Suppression של תשובה כפולה

**לוג:**
```
duplicate_reply_suppressed=true reason=owner_notification_already_sent
```

**תוצאה:** הודעת pending אחת בלבד התקבלה.

**סטטוס:** ✅ עבר במסלול תקין

---

### 2.10 — הפרדת fingerprint מ־payload הכתיבה

**בזמן approval:**
```
payload_keys=['fields', 'table']
```

**בזמן write בפועל:** רק
- כותרת המשימה
- תאריך יעד

**לא נשלחו:**
- `fingerprint_payload`
- `business_action_fingerprint`
- `normalized_payload`
- `contract_id`
- שדות governance פנימיים

**סטטוס:** ✅ עבר — payload נקי

---

## 3. אימות Turn Coordinator — create_task E2E

**מסלול מלא שאומת:**
```
בקשה
→ ownership של Turn Coordinator
→ agent_calls=0
→ ActionContract pending
→ approval
→ atomic claim
→ execution יחיד
→ Airtable write יחיד
→ outcome completed
→ תשובת completion אחת
```

**הוכחות:**
- `בעלות_coordinator=True`
- `agent_calls=0`
- `reply_owner=gateway`
- `Claim acquired`
- `Execution succeeded`
- `outcome=completed`
- `final_responses=1`
- אין דליפת `ActionContract ID`, `record ID` או `tool name` בתשובה הציבורית

**הרשומה שנוצרה:** `recJHmybGqfR3tq3G`

**סטטוס:** ✅ עבר — מסלול create_task E2E עבד

---

## 4. באגים מאומתים

### BUG-153 — בקשת create חדשה אחרי rejection נחסמת

**תיאור:** לאחר rejection של פעולה, בקשת create חדשה ומפורשת עם אותו תוכן נחסמת:
```
[ActionGateway] propose blocked: business action already rejected
```

**בעיה:** המערכת אינה מבדילה בין:
- replay אוטונומי (צריך להיחסם)
- בקשת create חדשה ומפורשת מהמשתמש (צריכה ליצור ActionContract חדש)

**חומרה:** גבוהה

**ראו:** `BUG_AUDIT_LOG.md` BUG-153

---

### BUG-154 — ניסוח "ל־תאריך" מפיל את parser

**בקשה:**
```
צור משימה ... ל־5/8/26 בשעה 10:30
```

**שגיאה:**
```
AttributeError: 'NoneType' object has no attribute 'start'
```

**מיקום:** `parse_deterministic_create_task()`

**תוצאה:** Fallback לאישור כללי בלא קנוני

**חומרה:** גבוהה

**ראו:** `BUG_AUDIT_LOG.md` BUG-154

---

### BUG-155 — פעולה שפג תוקפה נשארת pending

**תיאור:** TTL expiry של ActionContract אינו transition ל־terminal status.

**השפעות:**
- חסם בקשה חדשה
- נשאר ב־`live_contracts`
- חזר ל־reconfirmation
- היה ניתן לאשר ולבצע מאוחר יותר

**סתירה:** UI הצגה מצב terminal, אך backend הישאיר pending

**חומרה:** קריטית/גבוהה מאוד

**ראו:** `BUG_AUDIT_LOG.md` BUG-155

---

### BUG-156 — השעה אינה נשמרת ב־Airtable

**בקשה:**
```
צור משימה לבדוק את אימות 546 המעודכן עד 5/8/26 בשעה 10:30
```

**בבסיס הראשי נשמרה:**
- כותרת: `לבדוק את אימות 546 המעודכן`
- תאריך יעד: `2026-08-05`
- **שעה:** לא נשמרה

**הגדרת שדה:** `תאריך יעד` הוא `date` (לא `dateTime`)

**סתירה:** שעה משתתפת ב־fingerprint, אך אובדת בכתיבה

**חומרה:** בינונית עד גבוהה

**ראו:** `BUG_AUDIT_LOG.md` BUG-156

---

## 5. בדיקה שלא הושלמה

### כשל בשליחת הודעת ה־pending הראשונה

**מטרה:** לוודא שכאשר שליחת הודעת ה־owner הראשונה נכשלת:
- `duplicate_reply_suppressed` אינו מעלים תשובת fallback
- המשתמש מקבל הודעה ציבורית אחת בלבד (לא אפס)

**דרוש:** Fault injection זמני ב־staging שיפיל רק את ניסיון השליחה הראשון

**סטטוס:** ⏸️ לא השלים — דורש fault injection

**ראו:** `BUG_AUDIT_LOG.md` בדיקה חסרה

---

## 6. מסקנה

### ✅ הצליח

- Routing דטרמיניסטי לפי prefix
- `agent_calls=0` במסלול תקין
- Clarification fail-closed לקלט פגום
- Normalization של NBSP ורווחים
- Fingerprint יציב לפורמטים שקולים
- Fingerprint חדש לשינוי כותרת, תאריך או שעה
- אין write לפני approval
- Payload הכתיבה אינו מזוהם
- תשובה ציבורית אחת במסלול התקין
- Turn Coordinator create_task E2E — עד completion

### 🔴 נמצאו באגים

1. **BUG-153** — create חדש אחרי rejection נחסם
2. **BUG-154** — "ל־תאריך" מפיל את parser
3. **BUG-155** — TTL expiry אינו סוגר את pending (קריטי)
4. **BUG-156** — שעה משתתפת בזהות אך אינה נשמרת ב־Airtable

### ⏸️ בדיקה חסרה

- Fault injection ל־suppression fallback כשל בשליחת notification ראשונה

---

## 7. סדר עדיפות מומלץ לתיקונים

1. **BUG-155** — TTL expiry משאיר pending חי (קריטי)
2. **BUG-153** — create חדש אחרי rejection נחסם (גבוה)
3. **BUG-154** — parser crash בניסוח "ל־תאריך" (גבוה)
4. **BUG-156** — שעה אינה נשמרת (בינוני-גבוה)
5. **Fault injection** — suppression fallback (medium)

---

**דוח זה היא תיעוד מלא של אימות Staging ל־PR #546.**
**ראו `BUG_AUDIT_LOG.md` לפרטים ושדות נוספים של כל באג.**
