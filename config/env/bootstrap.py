import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Načte KEY=VALUE z `.env` do `os.environ` (hodnoty z `.env` přepisují stávající)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # Soubor `.env` v kořeni projektu má přednost před systémovými proměnnými,
        # aby lokální cesty (např. DATABASE_URL na jiném disku) nebyly přepsané
        # starým nastavením z uživatelského prostředí Windows.
        os.environ[key] = value


def load_project_env(base_dir: Path) -> None:
    path = base_dir / ".env"
    if path.is_file():
        _load_env_file(path)
