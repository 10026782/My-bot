"""Canonical, read-only catalog of curated external SCOREBOS tools."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata


ToolClass = str
VerificationStatus = str


@dataclass(frozen=True)
class ToolPlaybook:
    purpose: str
    supported_tasks: tuple[str, ...]
    prerequisites: tuple[str, ...]
    steps: tuple[str, ...]
    expected_output: str
    privacy_guidance: str
    common_mistakes: tuple[str, ...]
    agent_mode: str = "no_agent"
    agent_assist_capabilities: tuple[str, ...] = ()
    capability_type: str = "GUIDED_EXTERNAL_TOOL"
    internalization: str = "KEEP EXTERNAL"
    privacy_class: str = "OTHER_BOUNDED_WARNING"


@dataclass(frozen=True)
class BusinessTool:
    tool_id: str
    name: str
    url: str
    tool_class: ToolClass
    categories: tuple[str, ...]
    capabilities: tuple[str, ...]
    tasks: tuple[str, ...]
    short_description: str
    when_to_use: str
    when_not_to_use: str
    privacy_level: str
    allowed_data: str
    forbidden_data: str
    local_processing: bool | None
    signup_required: bool
    free_status: str
    verification_status: VerificationStatus
    last_verified_at: str
    source: str
    enabled: bool = True
    domain_tags: tuple[str, ...] = ()
    playbook: ToolPlaybook | None = None


_SOURCE = "docs/tool-research/NOSIGNUPS_BUSINESS_TOOLBOX.md"
_VERIFIED = "2026-08-13"


def _tool(
    tool_id: str,
    name: str,
    url: str,
    categories: tuple[str, ...],
    capabilities: tuple[str, ...],
    tasks: tuple[str, ...],
    description: str,
    use: str,
    avoid: str,
    privacy: str,
    allowed: str,
    forbidden: str,
    local: bool | None,
    *,
    tool_class: str = "business",
    status: str = "verified",
    domains: tuple[str, ...] = (),
    free: str = "no signup; free direct use",
) -> BusinessTool:
    return BusinessTool(
        tool_id=tool_id, name=name, url=url, tool_class=tool_class,
        categories=categories, capabilities=capabilities, tasks=tasks,
        short_description=description, when_to_use=use, when_not_to_use=avoid,
        privacy_level=privacy, allowed_data=allowed, forbidden_data=forbidden,
        local_processing=local, signup_required=False, free_status=free,
        verification_status=status, last_verified_at=_VERIFIED, source=_SOURCE,
        domain_tags=domains,
    )


TOOL_REGISTRY: tuple[BusinessTool, ...] = (
    _tool("bentopdf", "BentoPDF", "https://bentopdf.com/", ("documents", "pdf"),
          ("merge", "split", "compress", "convert", "redact"),
          ("merge pdf", "unite pdf", "compress pdf", "split pdf", "לאחד pdf", "איחוד pdf", "לדחוס pdf", "לפצל pdf"),
          "Merge, split, compress and organize PDF files.",
          "PDF preparation before sending or archiving.", "Sensitive files when local behavior is uncertain.",
          "low", "non-sensitive or approved browser-local files", "secrets, credentials, IDs, unapproved customer files", True,
          domains=("real_estate", "operations", "documents")),
    _tool("vert", "VERT", "https://vert.sh/", ("documents", "media"),
          ("convert", "format conversion"), ("convert file", "convert document", "convert image", "להמיר קובץ", "המרת קובץ"),
          "Convert common document and media formats in the browser.",
          "A quick format conversion without installing software.", "Sensitive files or video until handling is confirmed.",
          "low/medium", "synthetic or approved non-sensitive files", "identity, contract, lead and confidential files", True,
          domains=("documents", "marketing")),
    _tool("squoosh", "Squoosh", "https://squoosh.app/", ("images",),
          ("compress image", "resize image", "optimize image"), ("shrink image", "compress photo", "reduce image", "להקטין תמונה", "להקטין תמונות", "לדחוס תמונה", "תקטין לי תמונה", "תמונה לוואטסאפ"),
          "Compress and resize images before sharing or uploading.",
          "Photos and graphics that need a smaller file size.", "Never use as a substitute for preserving the original asset.",
          "low", "non-sensitive images and copies", "original evidence, private IDs, or files needing forensic integrity", True,
          domains=("marketing", "real_estate")),
    _tool("pairdrop", "PairDrop", "https://pairdrop.net/", ("transfer",),
          ("device transfer", "peer transfer"), ("transfer file", "move file", "phone to computer", "להעביר קובץ", "להעביר מהמכשיר למחשב"),
          "Transfer a file between nearby devices without an account.",
          "A one-off device-to-device transfer.", "Do not use as storage, archive, or approval path.",
          "medium", "non-sensitive files after verifying the peer", "unapproved confidential or regulated data", None,
          domains=("operations",)),
    _tool("rawgraphs", "RAWGraphs", "https://rawgraphs.io/", ("data", "charts"),
          ("chart", "visualize csv", "visualize data"), ("create graph", "graph from csv", "chart data", "ליצור גרף", "גרף מהנתונים", "תרשים מהנתונים", "איזה גרף"),
          "Create quick charts from a small CSV export.",
          "Exploratory or presentation-ready visualizations.", "Do not treat output as the system of record or dashboard.",
          "medium", "aggregated or redacted exports", "raw customer, financial, or identifying datasets", None,
          domains=("marketing", "operations")),
    _tool("csv-repair", "csv.repair", "https://www.csv.repair/", ("data",),
          ("repair csv", "validate csv", "inspect csv"), ("broken csv", "invalid csv", "csv not opening", "repair csv", "csv לא תקין", "csv לא נפתח", "שלא נפתח", "קובץ csv שבור", "csv שבור"),
          "Inspect and repair malformed CSV files.",
          "A CSV that fails to open or imports incorrectly.", "Do not upload sensitive exports without approval and redaction.",
          "low/medium", "synthetic or redacted CSV; approved non-sensitive export", "leads, credentials, IDs, customer exports without approval", None,
          domains=("operations", "data")),
    _tool("sql-for-files", "SQL for Files", "https://sqlforfiles.app/", ("data",),
          ("query csv", "query json", "join files", "profile data"), ("query csv", "join csv", "analyze file", "לנתח קובץ", "לשאול על csv", "לשאול שאלה על csv", "לחבר csv"),
          "Query, join and profile local CSV, JSON and Parquet files.",
          "Ad-hoc analysis without creating a new data store.", "Do not use as SCOREBOS source of truth or upload confidential data.",
          "low", "browser-local copies and redacted exports", "production databases, secrets, raw PII, canonical records", True,
          domains=("operations", "data")),
    _tool("cyberchef", "CyberChef", "https://gchq.github.io/CyberChef/", ("data", "security"),
          ("encode", "decode", "hash", "transform text"), ("decode text", "transform data", "inspect encoded value", "לפענח טקסט", "להמיר טקסט"),
          "Transform and inspect text or structured values in the browser.",
          "Technical text/data inspection by an operator.", "Do not paste live secrets or credentials.",
          "low", "synthetic, redacted, or explicitly approved values", "passwords, API keys, tokens, private keys", True,
          domains=("operations",)),
    _tool("svgomg", "SVGOMG", "https://jakearchibald.github.io/svgomg/", ("images", "design"),
          ("optimize svg", "shrink svg"), ("clean svg", "compress svg", "optimize logo", "לכווץ svg", "לנקות svg", "לכווץ לוגו svg"),
          "Clean and shrink SVG assets.", "Optimizing logos and icons before handoff.", "Keep the original asset and review visual output.",
          "low", "public or approved design assets", "assets containing sensitive embedded data", True,
          domains=("marketing",)),
    _tool("mr-data-converter", "Mr. Data Converter", "https://shancarter.github.io/mr-data-converter/", ("data",),
          ("convert csv", "convert tabular data"), ("csv to json", "spreadsheet to json", "csv to xml", "להמיר csv ל json"),
          "Convert small tabular data snippets to JSON or XML.", "A quick format handoff or inspection.", "Do not use for sensitive exports.",
          "low/medium", "synthetic or redacted samples", "raw business exports and personal data", None,
          domains=("operations",)),
    _tool("json-crack", "JSON Crack", "https://jsoncrack.com/", ("data",),
          ("visualize json", "understand json"), ("understand json", "visualize json", "json structure", "להבין json", "json מסובך", "להציג json"),
          "Visualize nested JSON structures.", "Understanding an API or export shape quickly.", "Do not paste secrets or unredacted customer data.",
          "low/medium", "synthetic or redacted JSON", "tokens, credentials, PII, private API responses", None,
          status="approved_with_restrictions", domains=("operations", "data")),
    _tool("metadata-remover", "Metadata Remover", "https://vaulternal.com/metadata-remover/", ("privacy", "images"),
          ("remove metadata", "strip exif"), ("remove photo metadata", "strip gps", "clean image"),
          "Remove common GPS, author and device metadata before sharing.", "A sharing safeguard for a copy of an image or document.", "It is not a complete anonymization guarantee.",
          "low/medium", "copies of approved files", "original evidence or files requiring provenance preservation", None,
          status="approved_with_restrictions", domains=("security",)),
    _tool("shareclean", "ShareClean", "https://pypi.org/project/shareclean/", ("privacy", "security"),
          ("redact text", "remove secrets", "sanitize logs"), ("clean logs", "redact config", "sanitize text", "לנקות לוג", "לנקות לוג לפני שליחה"),
          "Sanitize pasted text before sharing it externally.", "Preparing logs, configs or text for a vendor or support request.", "Never assume detection is complete; review the output.",
          "medium", "synthetic, redacted, or explicitly approved text", "live secrets, credentials, tokens, raw PII", None,
          status="approved_with_restrictions", domains=("security", "operations")),
    _tool("hoppscotch", "Hoppscotch", "https://hoppscotch.io/", ("operator", "http"),
          ("api inspection", "webhook inspection"), ("inspect api", "inspect webhook"),
          "Inspect safe staging HTTP requests and responses.", "Operator-only staging diagnostics.", "Production mutations, live credentials and customer payloads.",
          "medium", "synthetic payloads and fake credentials", "production secrets and customer data", None,
          tool_class="operator", status="approved_with_restrictions", domains=("developer",)),
    _tool("log-voyager", "Log Voyager", "https://www.logvoyager.cc/", ("operator", "logs"),
          ("inspect logs", "search logs"), ("inspect error logs", "search log export"),
          "Inspect already-authorized log exports locally.", "Operator-only local log triage.", "Unapproved hosted uploads or treating visual inspection as incident authority.",
          "medium", "approved sanitized local exports", "unapproved live logs and retained raw screenshots", True,
          tool_class="operator", status="approved_with_restrictions", domains=("developer",)),
    _tool("uptimerobot", "UptimeRobot", "https://uptimerobot.com/", ("monitoring",),
          ("uptime monitoring", "heartbeat"), ("monitor endpoint", "heartbeat"),
          "External uptime and heartbeat monitoring.", "Infrastructure POC evaluation only.", "Normal business recommendations and incident authority.",
          "medium", "public health endpoints only", "private URLs, credentials and business data", None,
          tool_class="infrastructure_candidate", status="deferred", free="POC decision required"),
    _tool("checkly", "Checkly", "https://www.checklyhq.com/", ("monitoring", "testing"),
          ("synthetic api testing", "browser testing"), ("test api", "test browser flow"),
          "Synthetic API and browser checks.", "Infrastructure POC evaluation only.", "Normal business recommendations and production writes.",
          "medium", "synthetic tenant and redacted responses", "customer data, live credentials and mutation tests", None,
          tool_class="infrastructure_candidate", status="deferred", free="POC decision required"),
    _tool("sentry", "Sentry", "https://sentry.io/", ("monitoring", "diagnostics"),
          ("error tracking", "exception grouping"), ("track error", "group exceptions"),
          "Group diagnostic exceptions and release context.", "Infrastructure POC evaluation only.", "Audit history, action evidence or normal business recommendations.",
          "high", "redacted exceptions without payloads", "tokens, prompts, PII and business records", None,
          tool_class="infrastructure_candidate", status="deferred", free="POC decision required"),
    _tool("socket", "Socket", "https://socket.dev/", ("security", "dependencies"),
          ("supply chain scan", "dependency scan"), ("scan dependencies", "dependency security"),
          "Evaluate dependency and supply-chain risk.", "Infrastructure/security POC evaluation only.", "Normal business recommendations or automatic dependency changes.",
          "medium", "repository metadata and approved manifests", "secrets and production data", None,
          tool_class="infrastructure_candidate", status="deferred", free="POC decision required"),
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)


def _runtime_tool_from_snapshot(record: dict) -> BusinessTool:
    playbook_data = record.get("playbook") or {}
    playbook = ToolPlaybook(
        purpose=playbook_data.get("purpose", ""),
        supported_tasks=tuple(),
        prerequisites=tuple(),
        steps=tuple(playbook_data.get("steps", ())),
        expected_output="",
        privacy_guidance=playbook_data.get("privacy_guidance", ""),
        common_mistakes=tuple(),
        agent_mode="optional_agent" if record.get("agent_mode") == "OPTIONAL_AGENT" else "no_agent",
        agent_assist_capabilities=tuple(playbook_data.get("agent_assist_capabilities", ())),
        privacy_class=record.get("privacy_class", "OTHER_BOUNDED_WARNING"),
    ) if playbook_data else None
    verification = {
        "VERIFIED": "verified",
        "APPROVED_WITH_RESTRICTIONS": "approved_with_restrictions",
    }.get(record.get("verification_status"), "unverified")
    tags = tuple(record.get("tags", ()))
    return BusinessTool(
        tool_id=record["tool_id"],
        name=record["name"],
        url=record["canonical_url"],
        tool_class=record["tool_class"],
        categories=tags,
        capabilities=tuple(record.get("capability_ids", ())),
        tasks=tuple(record.get("tasks", ())),
        short_description="",
        when_to_use="",
        when_not_to_use="",
        privacy_level=record.get("privacy_class", ""),
        allowed_data="",
        forbidden_data="",
        local_processing=None,
        signup_required=False,
        free_status="",
        verification_status=verification,
        last_verified_at=record.get("last_verified_at", ""),
        source="runtime_snapshot",
        enabled=bool(record.get("enabled")),
        domain_tags=tags,
        playbook=playbook,
    )


def list_tools(*, tool_class: str = "business", include_disabled: bool = False) -> tuple[BusinessTool, ...]:
    try:
        from tools.tool_runtime_snapshot import load_tool_runtime_snapshot
        records = load_tool_runtime_snapshot()["tools"]
    except Exception:
        return ()
    return tuple(
        _runtime_tool_from_snapshot(record)
        for record in records
        if record.get("tool_class") == tool_class
        and (include_disabled or record.get("runtime_visible"))
    )


_PLAYBOOKS: dict[str, ToolPlaybook] = {
    "bentopdf": ToolPlaybook("הכנת PDF לשליחה או ארכיון", ("איחוד", "פיצול", "דחיסה"), ("עותקי PDF מאושרים",), ("פתח את BentoPDF.", "העלה את עותקי ה־PDF.", "בחר Merge, סדר ובדוק את התוצאה.", "הורד את הקובץ החדש ושמור את המקור."), "קובץ PDF מאוחד או מעובד", "עבוד על עותקים בלבד; אל תעלה מסמכים רגישים ללא אישור.", ("מחיקת המקור לפני בדיקת התוצאה",)),
    "vert": ToolPlaybook("המרת פורמט לקובץ", ("המרת מסמך", "המרת תמונה"), ("קובץ שאינו סודי",), ("פתח את VERT.", "בחר את פורמט המקור והיעד.", "העלה את הקובץ והורד את התוצאה.",), "קובץ בפורמט היעד", "השתמש בקובץ סינתטי או לא־רגיש עד שאופן הטיפול מאושר.", ("החלפת המקור בתוצאה בלי בדיקה",)),
    "squoosh": ToolPlaybook("הקטנת תמונות לפני שיתוף או העלאה", ("דחיסה", "שינוי גודל"), ("עותק של התמונה",), ("פתח את Squoosh.", "גרור עותק של התמונה.", "בחר איכות וגודל, השווה תצוגה מקדימה.", "הורד את התוצאה ושמור את המקור."), "תמונה קטנה יותר", "עבוד על עותק; לא על ראיה מקורית או מסמך מזהה.", ("דריסת המקור",)),
    "pairdrop": ToolPlaybook("העברה חד־פעמית בין מכשירים קרובים", ("העברת קובץ",), ("שני מכשירים ברשת מאומתת",), ("פתח את PairDrop בשני המכשירים.", "ודא את שם המכשיר השני.", "שלח את הקובץ ואשר את הקבלה."), "עותק של הקובץ במכשיר היעד", "בדוק את היעד לפני שליחה; לא להשתמש כאחסון או ארכיון.", ("שליחה למכשיר שגוי",)),
    "rawgraphs": ToolPlaybook("יצירת תרשים מהיר מנתונים", ("בחירת תרשים", "המחשת CSV"), ("ייצוא קטן, מאוחד או מושחר",), ("פתח את RAWGraphs.", "הדבק או העלה את הנתונים.", "בחר תרשים ושייך עמודות.", "בדוק תוויות וייצא את התרשים."), "תרשים לייצוא או להצגה", "השתמש בנתונים מצטברים או מושחרים; זה לא מקור האמת.", ("הסקת מסקנות מנתונים חלקיים",), "optional_agent", ("הצעת סוג תרשים",)),
    "csv-repair": ToolPlaybook("בדיקה ותיקון של CSV שלא נפתח", ("תיקון CSV", "בדיקת מפרידים"), ("עותק CSV סינתטי או מושחר",), ("פתח את csv.repair.", "העלה את העותק.", "בדוק את השגיאות והחל את התיקון.", "הורד ופתח מחדש בכלי היעד."), "CSV תקין לייבוא", "אין להעלות ייצוא לקוחות גולמי ללא אישור; העדף נתונים מושחרים.", ("להניח שכל שורה תוקנה בלי בדיקת ספירה",)),
    "sql-for-files": ToolPlaybook("שאילתות וחיבור של קבצים מקומיים", ("שאילתת CSV", "חיבור קבצים"), ("קבצים מקומיים מושחרים",), ("פתח את SQL for Files.", "טען עותקים מקומיים.", "הרץ שאילתה לקריאה בלבד.", "ייצא תוצאה זמנית ובדוק אותה."), "תוצאה זמנית של שאילתה", "אין להשתמש במסד ייצור, סודות או רשומות קנוניות.", ("להתייחס לתוצאה כמקור אמת",), "optional_agent", ("עזרה בניסוח שאילתה",)),
    "cyberchef": ToolPlaybook("טרנספורמציה ובדיקה של טקסט", ("פענוח", "קידוד", "hash"), ("ערך סינתטי או מושחר",), ("פתח את CyberChef.", "בחר recipe מתאים.", "הדבק ערך לא־רגיש ובדוק את הפלט.", "העתק רק את התוצאה המאושרת."), "ערך שעבר טרנספורמציה", "לעולם לא להדביק סיסמאות, מפתחות או tokens חיים.", ("להניח שפענוח מאמת מקור",)),
    "svgomg": ToolPlaybook("ניקוי והקטנת SVG", ("אופטימיזציית לוגו",), ("עותק של SVG",), ("פתח את SVGOMG.", "טען את העותק.", "בדוק אפשרויות אופטימיזציה ותצוגה.", "הורד ושמור לצד המקור."), "SVG קטן יותר", "השתמש בנכסי עיצוב מאושרים בלבד.", ("אי־בדיקת המראה אחרי האופטימיזציה",)),
    "mr-data-converter": ToolPlaybook("המרת טבלה לפורמט אחר", ("CSV ל־JSON", "CSV ל־XML"), ("דוגמה קטנה ומושחרת",), ("פתח את Mr. Data Converter.", "הדבק את הטבלה.", "בחר פורמט יעד.", "בדוק את המבנה והעתק את התוצאה."), "נתונים בפורמט היעד", "אין להשתמש בייצוא עסקי גולמי או במידע אישי.", ("הדבקת עמודות לא תואמות",)),
    "json-crack": ToolPlaybook("הבנת מבנה JSON מקונן", ("המחשת JSON", "הבנת API"), ("JSON סינתטי או מושחר",), ("פתח את JSON Crack.", "הדבק את ה־JSON.", "נווט בעץ ובדוק את הקשרים.", "הסר את התוכן מהכלי לאחר השימוש."), "תצוגת מבנה JSON", "אין להדביק tokens, credentials או PII.", ("להניח שהתצוגה מאמתת את הנתונים",), "optional_agent", ("הסבר מבנה JSON",)),
    "metadata-remover": ToolPlaybook("הסרת metadata לפני שיתוף", ("ניקוי EXIF", "הסרת GPS"), ("עותק של הקובץ",), ("פתח את Metadata Remover.", "טען עותק.", "הסר metadata ובדוק את התוצאה.", "שתף רק את העותק לאחר בדיקה."), "קובץ עם פחות metadata", "לא לשמר את התוצאה כראיה מקורית; זו אינה הבטחת אנונימיזציה מלאה.", ("מחיקת המקור או provenance",)),
    "shareclean": ToolPlaybook("ניקוי טקסט לפני שיתוף חיצוני", ("ניקוי לוג", "השחרת secrets"), ("עותק טקסט מאושר",), ("פתח את ShareClean.", "הדבק עותק של הטקסט.", "הרץ ניקוי ובדוק ידנית את הפלט.", "שתף רק לאחר אישור אנושי."), "טקסט מושחר לשיתוף", "הכלי אינו מבטיח זיהוי מלא; אין להדביק secrets חיים.", ("לסמוך על זיהוי אוטומטי בלבד",), "optional_agent", ("הצעת נקודות לבדיקה ידנית",)),
}


_PRIVACY_CLASSES = {
    "bentopdf": ("COPY_ONLY", "עבוד על עותק של הקובץ; שמור את המקור אצלך."),
    "vert": ("NO_SENSITIVE_DATA", "אל תעלה לכלי חיצוני מידע רגיש או פרטי לקוחות."),
    "squoosh": ("COPY_ONLY", "עבוד על עותק כדי לשמור את התמונה המקורית."),
    "pairdrop": ("VERIFY_DESTINATION", "בדוק את שם המכשיר לפני השליחה."),
    "rawgraphs": ("REDACT_FIRST", "השתמש בנתונים מצטברים או מושחרים, לא במידע אישי גולמי."),
    "csv-repair": ("REDACT_FIRST", "השתמש בקובץ מושחר; אל תעלה ייצוא לקוחות גולמי."),
    "sql-for-files": ("NO_SENSITIVE_DATA", "השתמש בעותקים מושחרים, לא במידע אישי או במסד נתונים פעיל."),
    "cyberchef": ("NO_SENSITIVE_DATA", "אל תדביק סיסמאות, מפתחות או tokens."),
    "svgomg": ("COPY_ONLY", "שמור את קובץ ה־SVG המקורי ובדוק את התוצאה."),
    "mr-data-converter": ("REDACT_FIRST", "השתמש בדוגמה מושחרת, לא בייצוא עסקי גולמי."),
    "json-crack": ("REDACT_FIRST", "השתמש ב־JSON מושחר; הסר tokens ופרטים אישיים."),
    "metadata-remover": ("KEEP_ORIGINAL", "שמור את המקור; הסרת metadata אינה אנונימיזציה מלאה."),
    "shareclean": ("REDACT_FIRST", "בדוק ידנית את הפלט; אל תדביק secrets חיים."),
}
_OPTIONAL_HELP = {
    "rawgraphs": "אם תרצה, אני יכול לעזור לבחור סוג תרשים מתאים.",
    "sql-for-files": "אם תרצה, אני יכול לעזור לנסח שאילתת קריאה.",
    "json-crack": "אם תרצה, אני יכול להסביר את מבנה ה־JSON.",
    "shareclean": "אם תרצה, אני יכול להציע מה לבדוק לפני השיתוף.",
}

def _attach_playbooks(tools: tuple[BusinessTool, ...]) -> tuple[BusinessTool, ...]:
    result = []
    for tool in tools:
        playbook = _PLAYBOOKS.get(tool.tool_id)
        if playbook is not None:
            privacy_class, privacy_guidance = _PRIVACY_CLASSES.get(
                tool.tool_id, (playbook.privacy_class, playbook.privacy_guidance)
            )
            playbook = replace(
                playbook,
                privacy_class=privacy_class,
                privacy_guidance=privacy_guidance,
                agent_assist_capabilities=(
                    (_OPTIONAL_HELP[tool.tool_id],)
                    if tool.tool_id in _OPTIONAL_HELP else playbook.agent_assist_capabilities
                ),
            )
        result.append(replace(tool, playbook=playbook))
    return tuple(result)


TOOL_REGISTRY = _attach_playbooks(TOOL_REGISTRY)


def find_recommended_tools(task: str, *, limit: int = 3) -> list[BusinessTool]:
    """Return deterministic, eligible business matches; never returns verify-first tools."""
    normalized = _normalize(task)
    if not normalized.strip() or limit <= 0:
        return []
    matches: list[tuple[int, int, BusinessTool]] = []
    for position, tool in enumerate(list_tools(), start=1):
        if tool.verification_status not in {"verified", "approved_with_restrictions"}:
            continue
        score = sum(3 if _normalize(term) in normalized else 0 for term in tool.tasks)
        score += sum(1 if _normalize(term.replace("_", " ")) in normalized else 0 for term in tool.capabilities + tool.categories)
        score += 3 if _normalize(tool.name) in normalized or _normalize(tool.tool_id) in normalized else 0
        if score:
            matches.append((-score, position, tool))
    matches.sort(key=lambda item: (item[0], item[1]))
    return [tool for _, _, tool in matches[:limit]]


def get_playbook(tool_ref: str) -> BusinessTool | None:
    """Resolve a user-facing name or id to the same canonical registry record."""
    normalized = _normalize(tool_ref)
    return next((tool for tool in list_tools()
                 if _normalize(tool.name) in normalized or _normalize(tool.tool_id) in normalized), None)


def format_recommendation(task: str, tools: list[BusinessTool]) -> str | None:
    """Render every business recommendation through one Telegram-safe contract."""
    if not tools:
        return None
    lines = ["יש לי כלי מתאים לזה:"]
    for tool in tools:
        playbook = tool.playbook
        if not playbook:
            continue
        lines.extend(("", f"[{tool.name}]({tool.url})", "",
                      "מה הוא עושה", f"{playbook.purpose}.",
                      "", "איך משתמשים"))
        lines.extend(f"• {step}" for step in playbook.steps)
        if playbook.privacy_guidance:
            lines.extend(("", "חשוב", playbook.privacy_guidance))
        if playbook.agent_mode == "optional_agent" and playbook.agent_assist_capabilities:
            lines.extend(("", "עזרה נוספת", playbook.agent_assist_capabilities[0]))
    return "\n".join(lines)


def maybe_recommend(task: str) -> str | None:
    """Keep normal conversation untouched unless the message is a tool-seeking request."""
    normalized = _normalize(task)
    intent_markers = ("איזה כלי", "יש לי", "אני צריך", "אני רוצה", "איך ", "כלי ל")
    direct_tool = get_playbook(task) if ("איך" in normalized or "שימוש" in normalized) else None
    matches = [direct_tool] if direct_tool else find_recommended_tools(task)
    if not any(marker in normalized for marker in intent_markers) and not matches:
        return None
    if "כלים עסקיים" in normalized and ("איזה" in normalized or "מה" in normalized):
        return format_recommendation(task, list_tools()[:10])
    return format_recommendation(task, matches)


if __name__ == "__main__":
    assert find_recommended_tools("אני צריך לאחד כמה קבצי PDF")[0].tool_id == "bentopdf"
    assert find_recommended_tools("יש לי CSV לא תקין")[0].tool_id == "csv-repair"
    assert not find_recommended_tools("סוד token api_key")
