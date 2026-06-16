"""Content-addressed finding identity (D-04 / LIFE-02)."""

from __future__ import annotations

import hashlib
import re
import unicodedata


def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title)
    t = t.casefold()
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def fingerprint(path: str, title: str) -> str:
    payload = f"{path}|{normalize_title(title)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
