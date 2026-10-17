"""Detekce kolize `modul.py` + stejnojmenný balíček `modul/` u Django aplikací."""

from __future__ import annotations

from pathlib import Path

# Časté Django moduly — v chybové hlášce zdůrazníme, že právě ty se u refaktoru nejčastěji zdvojí.
RISKY_MODULE_NAMES = frozenset({"models", "forms", "views", "services", "serializers"})


def find_conflicts_in_app_directory(app_dir: Path) -> list[tuple[str, Path, Path]]:
    """Vrátí seznam (stem, cesta_k_modulu_py, cesta_k_balíčku)."""
    out: list[tuple[str, Path, Path]] = []
    if not app_dir.is_dir():
        return out
    for mod in sorted(app_dir.glob("*.py")):
        stem = mod.stem
        if stem.startswith("_"):
            continue
        pkg = app_dir / stem
        if mod.is_file() and pkg.is_dir() and (pkg / "__init__.py").is_file():
            out.append((stem, mod, pkg))
    return out


def find_conflicts_under_project_root(project_root: Path) -> list[tuple[str, str, Path, Path]]:
    """
    Projde přímé podsložky project_root, které vypadají jako Django app (mají apps.py).
    Vrátí (název_app_adresáře, stem, mod_path, pkg_path).
    """
    found: list[tuple[str, str, Path, Path]] = []
    if not project_root.is_dir():
        return found
    for child in sorted(project_root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if not (child / "apps.py").is_file():
            continue
        for stem, mod, pkg in find_conflicts_in_app_directory(child):
            found.append((child.name, stem, mod, pkg))
    return found
