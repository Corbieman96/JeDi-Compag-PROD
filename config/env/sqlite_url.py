"""Převod `DATABASE_URL` ve tvaru sqlite:… na cestu k souboru (jen SQLite)."""

from pathlib import Path
from urllib.parse import unquote, urlparse


def sqlite_path_from_database_url(url: str) -> Path | None:
    if not url or not url.lower().startswith("sqlite:"):
        return None
    parsed = urlparse(url)
    # sqlite:///rel.db  nebo  sqlite:////abs/path  nebo  sqlite:///C:/win/path
    path = unquote((parsed.path or "").strip())
    if parsed.netloc:
        path = f"{parsed.netloc}/{path}".rstrip("/")
    if not path:
        return None
    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]
    elif path.startswith("/"):
        # sqlite:///db.sqlite3 → relativní soubor vůči BASE_DIR (ne kořen disku)
        path = path.lstrip("/")
    return Path(path)
