Summary

תיאור קצר וברור של השינוי ומה הוא פותר.

Scope

- Phase / Stage:
- Bug / Ticket:
- Branch:
- שינוי קוד / תיעוד בלבד:
- מחוץ לתחום:
- Governance Gate
  - [ ] ה־PR מיועד ל־"main", והענף נוצר או עודכן מול "origin/main" העדכני
  
  - [ ] נבדק שהשינוי אינו כבר קיים ב־"main" או נפתר במקום אחר
  
  - [ ] השינוי תואם ל־ROADMAP, לתכנית הארכיטקטונית ול־SPEC הפעילים
  
  - [ ] אין יצירת תכנית, runtime, write path או מקור אמת מקביל
  
  - [ ] ה־diff כולל רק קבצים השייכים ל־scope של ה־PR
- 
- סתירה או חריגה:
  "None" / פרט בקצרה והפנה להכרעת הבעלים או למסמך המאשר:

Problem

מה הייתה ההתנהגות הקיימת או הבעיה שנצפתה?

Root Cause

מהו שורש הבעיה שאומת בקוד, בלוגים או בבדיקות?

Changes

- 
- 
- 

Architecture and Contracts

ציין אילו חוזים, invariants או שכבות מושפעים:

- Turn Coordinator:
- ActionContracts / Approval Runtime:
- Atomic Claim / Idempotency:
- Tool Registry / Canonical Tool:
- Sessions / Identity:
- Evidence Finalizer / RP5:
- Unified Status Formatter / F52:
- Mini-app / API:
- Other:

Safety Invariants

אשר שהשינוי שומר על הכללים הרלוונטיים:

- [ ] אין execution ללא אישור מפורש כאשר policy דורש אישור
- [ ] לכל business action יש ActionContract אחד בלבד
- [ ] atomic claim יחיד לכל contract
- [ ] אין Agent response כאשר Gateway הוא "reply_owner"
- [ ] אין יצירת contract עם tool או payload לא קנוניים
- [ ] אין ערבוב tenant, user, channel או context
- [ ] אין resurrection של פעולה שנדחתה
- [ ] אין bypass ישיר לכתיבה עסקית
- [ ] אין שינוי התנהגות מחוץ ל־scope

Feature Flags and Runtime State

- Feature flags שנוספו או שונו:
- ערכי ברירת מחדל:
- Production:
- Staging:
- Shadow / Enforce / Off:
- האם נדרש שינוי Environment:

Database and Airtable

- [ ] אין שינוי schema
- [ ] יש migration מצורף
- [ ] migration idempotent
- [ ] pre-deploy נדרש
- [ ] אין גישה חדשה לטבלה ללא entity/table resolution

פירוט:

Tests

Automated

- 
- 

Targeted / Regression

- 
- 

Live or Staging Evidence

- 
- 

Test Results

הדבק כאן את פלט הבדיקות המרכזי.

Observability

לוגים, counters או shadow signals שנוספו או השתנו:

- 
- 

Performance and Call Volume

- Anthropic calls לפני:
- Anthropic calls אחרי:
- Airtable calls לפני:
- Airtable calls אחרי:
- האם השינוי משפיע על מסלול legacy שעומד להימחק:

Deployment

- [ ] ללא deploy מיוחד
- [ ] Staging תחילה
- [ ] Production לאחר exit criteria
- [ ] נדרש restart
- [ ] נדרש pre-deploy command
- [ ] נדרש cleanup ידני

שלבי deploy:

1. 
2. 
3. 

Rollback

כיצד חוזרים להתנהגות הקודמת בבטחה?

- Flag / commit revert:
- Data cleanup:
- Runtime considerations:

Documentation

- [ ] "AI_CONTEXT.md" עודכן
- [ ] "BUG_AUDIT_LOG.md" עודכן
- [ ] SPEC / Decision Log עודכן
- [ ] Current Execution Status עודכן
- [ ] לא נדרש עדכון תיעוד

Evidence and References

- Logs:
- Contracts:
- Airtable records:
- Test files:
- Related PRs / commits:

Final Checklist

- [ ] ה־diff תואם ל־scope
- [ ] אין קבצים לא קשורים
- [ ] אין secrets או tokens
- [ ] כל הבדיקות הרלוונטיות עברו
- [ ] backward compatibility נבדקה
- [ ] rollback אפשרי
- [ ] Exit criteria הוגדרו
- [ ] מוכן ל־review
