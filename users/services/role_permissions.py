from __future__ import annotations

from core.models import AppSettings
from users.constants import (
    ROLE_ADMIN,
    ROLE_CHOICES,
    ROLE_DISPECER,
    ROLE_ZADAVATEL,
)

ROLE_PERMISSION_FLAG_KEYS: tuple[str, ...] = ("export_pio_profile",)

ROLE_PERMISSION_LABELS_CZ: dict[str, str] = {
    "export_pio_profile": "PIO — profilová šablona u subjektu F/P",
}


def fallback_role_permission_matrix() -> dict[str, dict[str, bool]]:
    """Výchozí oprávnění podle role (před globálním nastavením v AppSettings)."""
    allowed_roles = {ROLE_ADMIN, ROLE_DISPECER, ROLE_ZADAVATEL}
    out: dict[str, dict[str, bool]] = {}
    for role, _ in ROLE_CHOICES:
        out[role] = {
            "export_pio_profile": role in allowed_roles,
        }
    return out


def merged_role_permission_matrix(stored: dict | None = None) -> dict[str, dict[str, bool]]:
    base = fallback_role_permission_matrix()
    if not stored:
        return base
    for role, row in stored.items():
        if role not in base or not isinstance(row, dict):
            continue
        for key, val in row.items():
            if key in ROLE_PERMISSION_FLAG_KEYS and isinstance(val, bool):
                base[role][key] = val
    return base


def _matrix_from_db() -> dict[str, dict[str, bool]]:
    try:
        raw = AppSettings.load().role_permission_defaults or {}
    except Exception:
        raw = {}
    return merged_role_permission_matrix(raw if isinstance(raw, dict) else {})


def role_default_export_pio_profile(role: str) -> bool:
    matrix = _matrix_from_db()
    if role in matrix:
        return bool(matrix[role].get("export_pio_profile"))
    return bool(matrix.get(ROLE_DISPECER, {}).get("export_pio_profile"))
