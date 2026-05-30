# tools/gmail_tools.py — re-exports from google_tools
# gmail_send() in google_tools creates a draft → exposed here as gmail_draft
from .google_tools import gmail_send as gmail_draft, gmail_send_draft, gmail_read

__all__ = ["gmail_draft", "gmail_send_draft", "gmail_read"]
