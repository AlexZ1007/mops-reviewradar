"""Content hash used to detect exact duplicate reviews (unique per project in the database)."""
import hashlib
import unicodedata


def normalize_content(text: str) -> str:
    """Make two spellings of the same text equal: unicode form, collapsed whitespace, case-insensitive."""
    return " ".join(unicodedata.normalize("NFC", text).split()).casefold()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()
