"""Formátování telefonních čísel (národní tvar)."""


def format_czech_contact_phone(raw: str) -> str:
    """Číslo ve tvaru „000 000 000“ — bere posledních 9 číslic z vstupu."""
    text = (raw or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 9:
        return text
    digits = digits[-9:]
    return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
