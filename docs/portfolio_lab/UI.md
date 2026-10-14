# Portfolio Lab — מסך סימולטור (Phase 1.5)

מסך מקומי נפרד; אינו משנה את ממשק הבוט, אינו מחובר ל-`app.py`/TMA, ללא Airtable, LLM או נתוני Production.

```bash
python3 -m portfolio_lab.ui --port 8765   # http://127.0.0.1:8765/ (loopback בלבד)
python3 -m pytest test_portfolio_lab_ui.py -q
```

## מבנה והפרדה

- `portfolio_lab/simulator_view.py` — `build_simulator_view(params, tax_model=None)`: כל החישוב מ-`simulate`/`compare`; הקובץ בוחר תרחישים (רגישות, משבר) ומנסח תובנות. מחזיר JSON מובנה (KPI, סדרות גרפים, טבלה, תובנות, הנחות, אזהרות). **זו נקודת החיבור העתידית ל-Decision Hub / מחקרים** — ללא תלות ב-UI.
- `portfolio_lab/ui.py` + `ui_page.html` — שרת stdlib ודף RTL עם גרפי SVG (ללא ספריות/CDN).

## הנחות שמוצגות במסך
תשואה/דמי ניהול/אינפלציה שהוזנו; תשואות רכיבי האסטרטגיות האחרות (World 7.5%, EM 6.5%, S&P 8.5%, אירופה 7%, מניות 6% — כמו `comparison.json`, להמחשה בלבד); משקלים לדוגמה ללא איזון מחדש; פיזור שנתי על 12 חודשים; מס "לא מחושב" ללא מודל מס תקף (תוצאה עם מודל שלא אומת מסומנת "תיאורטית בלבד").

## תרחיש משבר
ירידה 10–50% בשנה נבחרת, ואז התאוששות לנתיב המגמה: מהירה (שנה) או ממושכת (3 שנים), לפי (1-d)·g^n=(1+r)^(n+1). מוחל על האסטרטגיה הראשית; התאוששות החורגת מהאופק נחתכת. עקב הפקדה שוטפת בזמן הירידה השווי הסופי עשוי לעלות — תוצאת המודל, לא תחזית.

## פערים לשלב הבא
משבר על כל האסטרטגיות בהשוואה; תשואות רכיבים ניתנות לעריכה ב-UI (קיימות ב-API: `component_returns_pct`); מודל מס מאומת; חיבור ל-TMA/Decision Hub; משבר תוך-שנתי; ייצוא CSV/PDF.

## מודל אבטחה (כלי מקומי, לא ממשק פרודקשן)

- מאזין ל-`127.0.0.1` בלבד; אין דגל `--host`; `make_server` מאמת פורט. מסרב לעלות כשמוגדרים `RENDER*`/`DYNO`/`KUBERNETES_SERVICE_HOST`/`GUNICORN_CMD_ARGS` או `ENV/APP_ENV/FLASK_ENV/ENVIRONMENT=production`. אינו מיובא מ-`app.py`/`tma_api.py`/scheduler/Docker (נבדק בטסט).
- ללא אימות — מכוון: אין נתונים רגישים, אין Airtable/LLM, החישוב דטרמיניסטי ובלתי-מזיק.
- DNS rebinding / CSRF: `Host` חייב להיות `127.0.0.1:<port>`/`localhost:<port>`, `Origin` (אם נשלח) חייב להיות אותו מקור, `POST` רק עם `Content-Type: application/json`; אין כותרות CORS.
- קלט: גוף עד 64KB, `Content-Length` חובה, timeout של 10 שניות לחיבור, חישוב מקבילי מוגבל ל-2 (סימולציה במקרה הגרוע ~0.3 שנ'), ולידציה קפדנית ב-`normalize_params` + המנוע. שגיאות: 400 עם הודעת ולידציה בלבד; כל חריגה אחרת → 500 גנרי בלי פרטים פנימיים.
- דפדפן: CSP עם nonce לכל בקשה (בלי `unsafe-inline`/`eval`, `default-src 'none'`, `connect-src 'self'`), `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, `no-store`. ה-JS כותב ל-DOM רק דרך `textContent`.

## רשומות governance
- Planning Gate (`CROSS_LAYER_GOVERNANCE_REVISED_PLANNING_GATE.md`): **Cross-Layer Impact: NONE.** שכבה בעלים: `portfolio_lab` (מחקר מקומי עצמאי); אין שינוי גבול סמכות, חוזה משותף, persistence או routing; אין קשר חדש בין שכבות; לא מפעיל קוד רדום בבוט; אין fallback/bypass; שכבה אחרת לא מקבלת החלטה. הוכחה: `grep portfolio_lab app.py tma_api.py scheduler.py Dockerfile gunicorn.conf.py` ריק (טסט `test_not_wired_into_deployed_runtime`).
- Context Librarian: `suggest-profile --all` → `no_match` (כל הפרופילים score=0). **Selected profile: none — מחוץ לתחום ה-trigger של AGENTS.md** (לא Core Reasoning/routing/approvals/tools/F52/RP5/production claim). `validate` תקין, `reconcile-pr` → `CLEAN` (מקור אזהרה יחיד: `UI.md`), 268 בדיקות librarian/reconcile/status-sync עברו על clone מלא. `reconcile --check` מחזיר `AUTO_MAINTENANCE_REQUIRED` גם על `origin/main` נקי — קיים מראש, לא קשור ל-PR.


## חיבור ל-TMA: "תכנון חיסכון לטווח ארוך" (PR-1, 14/10/2026)

החלטות בעלים: שם המסך **תכנון חיסכון לטווח ארוך** (קבוע אחד: `SCREEN_TITLE`); הרשאות = דגל `FEATURE_FINANCIAL_CONTROL_CENTER` + `FCC_CANARY_USER_IDS` + בעלים; הפקדה בפועל = אירועי `one_time` ביעד ה-`long_term` ("דיווח עצמי", לא מאומת מול בנק); הפקדה מתוכננת = רמת יעדי ה-`savings`; "צפוי להתפנות" (`savings_release.expected`) אינו תוכנית; יתרת תיק — הערכה לפי הפקדות עם עדכון ידני מדי כמה חודשים (**שלב PR-2**, דורש החלטת סכמה; ב-PR-1 מוצג "לא זמינה").

**מה נבנה:** כרטיס כניסה בלשונית "התנהלות חודשית" של המרכז הכלכלי -> מסך בן שתי לשוניות (`החיסכון שלי` מנתוני ה-overview הקיימים בלבד; `מעבדת העתיד` = הסימולטור). ללא שינוי ב-`App.tsx` (הניווט מקומי ל-`FinancialControlCenter`, כך שהמסך נגיש רק דרך שער ה-FCC). `FccTabBar` הורחב בצורה תואמת-לאחור (`tabs`/`idPrefix`/`ariaLabel`).

**API:** `POST /api/portfolio-lab/simulate` (`tma_api.py`) — `require_tma_auth`, אותו `_fcc_enabled` + `identity.is_owner` (אחרת 404), `application/json` בלבד (415), `Content-Length` חובה (411), עד 64KB (413), 12 בקשות לדקה למשתמש (429), חישוב מקבילי עד 2 (503), ולידציה -> 400 עם הודעת ולידציה בלבד, כל חריגה אחרת -> 500 גנרי. קורא רק ל-`build_simulator_view` (ייבוא עצל; הקשר היחיד בין `tma_api` ל-`portfolio_lab`, נעול בטסט). ללא Airtable/LLM/כתיבה. השרת המקומי העצמאי (`portfolio_lab.ui`) אינו נפרס ואינו מוגש משם.

**ה-frontend מציג בלבד:** אין מנוע חישוב ב-TS (טסט סטטי אוסר חזקות/ריבית דריבית/אנואיטה); אחוזי החלוקה מחושבים בשרת; גיאומטריית הגרפים היא סקאלה של מספרים שהשרת הפיק.

**Planning Gate:** `Cross-Layer Impact: FULL` — קשר חדש `tma_api` -> `portfolio_lab` ו-endpoint חדש. סמכות: ללא שינוי (אין כתיבה, אין מקור אמת חדש; ה-overview נקרא כמות שהוא). Bypass/fallback: אין. הוכחה: טסטי `test_portfolio_lab_tma_api.py` (שער, מגבלות, קריאה-בלבד, ייבוא יחיד) + `familyWealth.test.ts` (המסך נפתח רק מתוך `FinancialControlCenter`).

**לא נבנה (PR-2, בכפוף להחלטות):** סך הפקדות שנה/ממוצע/רצף חודשים (נגזר בשרת מאירועים קיימים, ללא טבלה), פער מתוכנן-מול-דיווח, תווית "דיווח עצמי" במסכי ה-FCC הקיימים, איחוד/שינוי שם של `expected` ב-`FccKpiCard`, יתרה משוערת + עדכון ידני, טעינת נתוני החיסכון לתרחיש.
