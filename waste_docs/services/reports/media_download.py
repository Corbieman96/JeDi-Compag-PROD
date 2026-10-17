"""Bezpečné stažení generovaných souborů z MEDIA_ROOT (funguje i při DEBUG=False)."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

ALLOWED_MEDIA_DOWNLOAD_PREFIXES = (
    "pruvodky/",
    "protokoly/",
    "print_cache/protokoly/",
    "pio/",
    "name_subject_pairs/pio/",
    "zpo_library/",
    "name_subject_pairs/zpo/",
    "zpo/",
)

ALLOWED_MEDIA_DOWNLOAD_SUFFIXES = (
    ".pdf",
    ".xlsx",
    ".xls",
    ".png",
    ".jpg",
    ".jpeg",
)


class MediaDownloadError(ValueError):
    pass


def normalize_media_download_rel(media_rel: str) -> str:
    rel = (media_rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise MediaDownloadError("Neplatná cesta souboru.")
    lower = rel.lower()
    if not any(lower.endswith(suf) for suf in ALLOWED_MEDIA_DOWNLOAD_SUFFIXES):
        raise MediaDownloadError("Nepovolený typ souboru.")
    if not any(rel.startswith(prefix) for prefix in ALLOWED_MEDIA_DOWNLOAD_PREFIXES):
        raise MediaDownloadError("Soubor není v povoleném adresáři.")
    return rel


def resolve_media_download_path(media_rel: str) -> Path:
    rel = normalize_media_download_rel(media_rel)
    source = (settings.MEDIA_ROOT / rel).resolve()
    media_root = settings.MEDIA_ROOT.resolve()
    if media_root not in source.parents and source != media_root:
        raise MediaDownloadError("Soubor mimo media.")
    if not source.is_file():
        raise MediaDownloadError("Soubor neexistuje.")
    return source


def content_type_for_media_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    if path.suffix.lower() == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if path.suffix.lower() == ".xls":
        return "application/vnd.ms-excel"
    return "application/octet-stream"


def media_download_url_for_rel(media_rel: str) -> str:
    rel = normalize_media_download_rel(media_rel)
    return f"{reverse('waste_docs:media_download')}?{urlencode({'rel': rel})}"
