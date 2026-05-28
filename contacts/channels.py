# contacts/channels.py
MSG_CHANNEL = {
    "invoice":"email","contract":"email","document":"email","proposal":"email",
    "quick":"whatsapp","reminder":"whatsapp","update":"whatsapp",
}

def get_channel(contact_fields: dict, message_type: str = "general") -> str:
    preferred = contact_fields.get("Preferred Channel","")
    if preferred in ("email","whatsapp","telegram"):
        return preferred
    if message_type in MSG_CHANNEL:
        ch = MSG_CHANNEL[message_type]
        if ch == "email" and contact_fields.get("Email"): return "email"
        if ch == "whatsapp" and (contact_fields.get("WhatsApp") or contact_fields.get("Phone")): return "whatsapp"
    if contact_fields.get("WhatsApp") or contact_fields.get("Phone"): return "whatsapp"
    if contact_fields.get("Email"): return "email"
    return "whatsapp"

def get_contact_address(contact_fields: dict, channel: str) -> str | None:
    if channel == "email":    return contact_fields.get("Email")
    if channel == "whatsapp": return contact_fields.get("WhatsApp") or contact_fields.get("Phone")
    if channel == "telegram": return contact_fields.get("Telegram")
    return None
