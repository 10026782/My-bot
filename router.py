def detect_topic(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(word in text for word in ("crm", "עסקה", "לקוח", "ליד", "lead", "deal")):
        return "crm"
    if any(word in text for word in ("finance", "כסף", "מימון", "תשלום", "roi")):
        return "finance"
    return "general"
