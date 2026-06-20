# BOSS MARKETING EXECUTION MAP

**מטרת המסמך:** מפה אחת שמראה מה עובד, מה חסר, ומה הסדר המדויק לביצוע.
**מה זה לא:** לא חזון, לא רשימת רעיונות, לא ספֵק. החזון כבר קיים (ראה למטה).

Status: REPO-READY
Date: 20/06/2026
Owner: Eliyahu

---

## הפרדת שלושת המסמכים

הבעיה עד היום: שלושה מסמכים שונים עם מטרות שונות התערבבו לאחד. הם נשארים נפרדים.

| מסמך | אופק | תפקיד | סטטוס |
|------|------|-------|--------|
| **BOSS Marketing Vision** | 1–3 שנים | כיוון. Content DNA, Marketing Orchestrator, Multi-Agent, Video, Community Intelligence, Auto-Publishing | מסמך כיוון — לא נכנס לריפו כמשימות |
| **BOSS Revenue Engine** | 90 יום | ביצוע. Lead Capture, Scoring, Source/Revenue/Partner Attribution, Owner Notifications, Deal Tracking | **מסמך ביצוע — זה מה שמתועדף כאן** |
| **BOSS Distribution Engine** | שכבת ביניים | הגשר. WhatsApp, Telegram, Facebook, Posters, Partnerships, Traffic Sources | נפתח רק כשרכיב Revenue דורש אותו |

המפה הזו = ה-Execution layer של **Revenue Engine** בלבד. Vision ו-Distribution מוזנים פנימה רק כשהם משרתים שורת money-first.

---

## שאלת השער (Money-First Gate)

לפני כל משימה חדשה, שאלה אחת:

> האם היא **מכניסה כסף**, **משפרת מדידה**, או **פותחת ערוץ הפצה**?

אם לא — היא יורדת לסוף הרשימה. אין חריגים.

---

## מקרא סטטוס

- ✅ — מאומת בפרודקשן (יש evidence)
- 🟡 — קוד קיים / חלקי — **לא מאומת בפרודקשן**
- ❌ — לא קיים

> הערה: שדרגתי שלוש שורות מ-✅ ל-🟡 לעומת הטיוטה שלך, כי לפי `BOSS_CURRENT_STATE.md` הדגלים כבויים ולא בוצע אימות עם הודעת WhatsApp אמיתית. מסמך אמת לא יכול לסמן ✅ על משהו שלא אומת — זה בדיוק העיקרון "NO CLAIM WITHOUT VERIFICATION".

---

## THE EXECUTION MAP

| רכיב | סטטוס | רכיב אמיתי בקוד / תלות | הערת אמת | עדיפות |
|------|--------|------------------------|-----------|--------|
| **Lead Capture** | 🟡 | `lead_capture.py` · flag `LEAD_CAPTURE` (OFF) | קוד מלא. כבוי. לא אומת בפרודקשן | **P0** |
| **Lead Scoring** | 🟡 | `lead_scoring.py` (N02) · flag `LEAD_SCORING` (OFF) | קוד תקין, write-path תוקן. לא אומת עם WhatsApp אמיתי | **P0** |
| **Telegram Alerts** | ✅ | `app.py` owner notifications | עובד ומאומת — נתיב hot-lead → owner | **P0** |
| **Source Attribution** | 🟡 | `_inject_utm` (`app.py`) · שדות `source`/`channel` ב-Leads | מנגנון קיים. לא אומת end-to-end שה-source נכתב בפועל. זה Rule M01 | **P0** |
| **Revenue Attribution** | 🟡 | Origin Lead backlink (C21) ✅ קיים · מנוע aggregation ❌ | הקישור ליד→עסקה קיים. חסר שכבת חישוב הכנסה לפי מקור | **P0** |
| **Distribution Database (TRAFFIC_SOURCES)** | ❌ | טבלת Airtable חדשה | עמוד השדרה של המדידה. בלעדיו Source/Revenue Attribution חצי-עיוורים | **P0\*** |
| **Partner Attribution** | ❌ | טבלת Partners + קודי referral | ROI הכי גבוה לפי Vision, tech הכי נמוך. בעיקר Airtable + ידני | **P1** |
| **Messaging Gateway (COG / C52)** | 🟡 | spec קיים · לא נבנה. P0 ב-horizon הקיים | חובה **לפני** כל broadcast אוטומטי. ESCALATE not BLOCK | **P1** |
| **WhatsApp Outbound (W01)** | ❌ | honest stub · חסום Meta Cloud API | תלוי ב-W01 + Gateway + פתרון Meta. כרגע Twilio interim | **P1** |
| **Content DNA** | ❌ | להרחיב `creative_generator.py` הקיים — **לא לבנות מקביל** | Vision. נכנס רק אחרי שהלולאה מוכיחה הכנסה | **P3** |
| **Video Engine** | ❌ | — | Vision | **P4** |
| **Marketing Orchestrator** | ❌ | — | Vision. שכבת אוטונומיה — אחרי הכל | **P5** |

\* TRAFFIC_SOURCES סומן P0 (לא P1) כי בלי טבלת המקורות, Source ו-Revenue Attribution לא יכולים להיסגר. הוא מדידה טהורה — עובר את שער ה-money-first.

---

## סדר ביצוע מדויק

**גל 1 — הפעלת הלולאה הקיימת (P0, ללא קוד חדש)**
1. `LEAD_CAPTURE=true` → לאמת יצירת רשומה ב-Leads עם הודעת WhatsApp אמיתית
2. אימות `_inject_utm`: לוודא ששדה `source` נכתב בפועל (M01)
3. `LEAD_SCORING=true` → לאמת score+tier נכתבים
4. לאמת נתיב hot-lead → Telegram alert ל-owner (כבר עובד)
→ **תוצאה: מערכת שמכניסה ומודדת כסף תוך שבוע, על צינורות שכבר עומדים.**

**גל 2 — סגירת ספֵק המדידה (P0)**
5. בניית טבלת TRAFFIC_SOURCES ב-Airtable
6. מנוע Revenue Attribution: aggregation לפי source דרך Origin Lead backlink (C21 קיים)

**גל 3 — הפצה מדודה בערוץ אחד (P1)**
7. ערוץ outbound שכבר עובד = Telegram. WhatsApp Status/Groups ידני עם קודי source. שימוש חוזר ב-`creative_generator.py`
8. Partner Attribution במקביל — ידני, צריך רק את גל 2

**גל 4 — שער בטיחות לפני אוטומציה (P1)**
9. Messaging Gateway / COG (C52) — ESCALATE not BLOCK. חובה לפני כל broadcast

**גל 5 — WhatsApp Outbound (P1)**
10. W01 — רק אחרי Gateway + פתרון Meta. per-domain routing, 24h window, audit per send

**Vision (P3+)** — Content DNA, Video, Orchestrator. נפתח רק אחרי שהלולאה הוכיחה הכנסה.

---

## תיאום עם מערכות מתוכננות (חוסם תלות)

- **Broadcast אוטומטי** לא קודם ל-**C52 COG** + **C53 Approval Hardening** (אחרת outbound עוקף emergency-stop)
- **WhatsApp Outbound** תלוי **W01** + פתרון **Meta Cloud API**
- **Content/Campaign memory** חייב לשבת ב-**Airtable** — לא ב-memory ה-RAM-only (מתאפס ב-restart)
- **Asset generation** מרחיב את `creative_generator.py` — בלי מערכת תוכן מקבילה

---

## Definition of Done (כל שורה)

שורה עוברת מ-🟡 ל-✅ רק עם:
`STATUS: ✅ VERIFIED IN PROD` + evidence (grep בקובץ + commit hash ב-Render + ריצה אמיתית).
לא דיווח עצמי. לא git log. אימות פוסט-מרג' בפועל.
