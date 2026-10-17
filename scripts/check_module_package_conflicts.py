#!/usr/bin/env python3
"""
Kontrola: žádná Django app v kořeni projektu nesmí mít současně např. models.py i models/.

Spuštění z kořene repozitáře:
    python scripts/check_module_package_conflicts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Kořen repozitáře (nad scripts/)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.module_package_guard import find_conflicts_under_project_root  # noqa: E402


def main() -> int:
    conflicts = find_conflicts_under_project_root(ROOT)
    if not conflicts:
        return 0
    print("Kolize modul.py + stejnojmenný balíček:", file=sys.stderr)
    for app_name, stem, mod_path, pkg_path in conflicts:
        print(f"  • {app_name}: {mod_path.name} + {pkg_path.name}/", file=sys.stderr)
        print(f"      {mod_path}", file=sys.stderr)
        print(f"      {pkg_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
