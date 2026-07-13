from __future__ import annotations

import unicodedata


def normalize_public_name(value: str) -> str:
    """Return a stable lookup key without exposing an internal alias."""

    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()
