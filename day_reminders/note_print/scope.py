from __future__ import annotations

SCOPE_REQUEST = "request"
SCOPE_OTHER = "other"
SCOPE_ALL = "all"

SCOPE_CHOICES = (
    (SCOPE_REQUEST, "Požadavek"),
    (SCOPE_OTHER, "Ostatní"),
    (SCOPE_ALL, "Vše"),
)

_ALLOWED = {SCOPE_REQUEST, SCOPE_OTHER, SCOPE_ALL}


def parse_print_scope(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in _ALLOWED:
        return value
    return SCOPE_ALL


def scope_label(scope: str) -> str:
    return dict(SCOPE_CHOICES).get(scope, "Vše")
