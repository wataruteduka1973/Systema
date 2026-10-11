"""Validation for listing image URLs that are rendered directly in pages."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlparse

# Yahoo! Auctions serves listing images from *.yimg.jp. Anything else is dropped because the
# value ends up in an <img src> attribute.
ALLOWED_IMAGE_HOST_SUFFIX = ".yimg.jp"
MAX_IMAGE_URL_LENGTH = 1000


def safe_image_url(value: object) -> str:
    """Return an https Yahoo image URL, or "" when the value is missing or not allowed."""
    if isinstance(value, Mapping):
        value = value.get("url") or value.get("src") or ""
    text = str(value or "").strip()
    if text.startswith("//"):
        text = f"https:{text}"
    if not text or len(text) > MAX_IMAGE_URL_LENGTH or any(ch.isspace() for ch in text):
        return ""
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host.endswith(ALLOWED_IMAGE_HOST_SUFFIX):
        return ""
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return ""
    return text
