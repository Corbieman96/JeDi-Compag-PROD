from __future__ import annotations

import re


def normalize_recipient_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if not email or len(email) > 254:
        raise ValueError("Zadejte platnou e-mailovou adresu.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Zadejte platnou e-mailovou adresu.")
    return email
