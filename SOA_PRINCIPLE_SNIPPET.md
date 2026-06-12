## Single Source of Authority (SoA)

Every persistent fact, state, calculation, memory, approval, message, or external action must have exactly one declared owner module — its Source of Authority.

Other modules may request, read, or display this data — but must not independently decide, mutate, recompute, send, or execute it unless they are the declared SoA for that item.

**Practical test before writing new code**: "Am I the SoA for this? If not — call the SoA, don't duplicate its logic."

**כלל מעשי לקוד חדש בעברית**: לפני שמודול כותב/שולח/מחשב משהו - לבדוק: יש לזה כבר בעל-בית מוצהר? אם כן - לקרוא לו, לא לשכפל את הלוגיקה שלו. אם לא קיים בעל-בית - לתעד את הקובץ הזה כ-SoA זמני ב-`FILE_OWNERSHIP.md`, ולא להניח שזה בסדר שכל מודול יחזיק עותק.

**איתור הפרות (לאודיטים עתידיים)**: כל פעם ש-grep מוצא 2+ קבצים שכותבים/שולחים את אותו דבר (Airtable table, Telegram message, approval state) - זו לא "כפילות נוחה", זו הפרת SoA וצריכה שורה ב-`ARCHITECTURE_DRIFT_MAP.md`.
