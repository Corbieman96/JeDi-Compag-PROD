"""Validace povinného důvodu zrušení zákaznického požadavku."""

from __future__ import annotations

CANCEL_REASON_MAX_LEN = 500
CANCEL_REASON_REQUIRED_MSG = "Zadejte důvod zrušení."


def normalize_cancel_reason(raw: str | None) -> str:
    reason = (raw or "").strip()
    if not reason:
        raise ValueError(CANCEL_REASON_REQUIRED_MSG)
    return reason[:CANCEL_REASON_MAX_LEN]
