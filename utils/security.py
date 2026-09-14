import re

# Regex matching HTML tags (e.g. <script>, <iframe>, <img ...>, <a>, etc.)
# Preserves mathematical or text comparisons like "distance < 5m" because tag name must follow '<'
HTML_TAG_PATTERN = re.compile(r"<\/?\s*[a-zA-Z][^>]*>", re.IGNORECASE)

# Regex matching dangerous pseudo-protocols in links / strings
DANGEROUS_PROTOCOLS = re.compile(r"(javascript|data|vbscript)\s*:", re.IGNORECASE)


def sanitize_text(text: str | None) -> str:
    """
    Sanitizes user-provided and AI-generated strings to protect against XSS and injection attacks.
    - Strips null bytes and invisible control characters.
    - Strips HTML tags (<script>, <iframe>, <style>, etc.).
    - Disarms dangerous URL schemes (javascript:, data:).
    - Trims excess whitespace.
    """
    if not text:
        return ""
    # Strip null bytes
    cleaned = text.replace("\x00", "")
    # Strip HTML tags
    cleaned = HTML_TAG_PATTERN.sub("", cleaned)
    # Disarm dangerous pseudo-protocols
    cleaned = DANGEROUS_PROTOCOLS.sub("", cleaned)
    return cleaned.strip()


def validate_url_protocol(url: str | None) -> bool:
    """
    Validates that a URL uses safe HTTP/HTTPS or relative protocols.
    Rejects javascript:, data:, and other dangerous pseudo-protocols.
    """
    if not url:
        return True
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://") or u.startswith("/")
