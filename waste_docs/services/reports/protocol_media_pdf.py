"""Kompatibilita: PDF protokolů přes obecný media_download."""

from __future__ import annotations

from pathlib import Path

from waste_docs.services.reports.media_download import (
    MediaDownloadError,
    normalize_media_download_rel,
    resolve_media_download_path,
)

ProtocolMediaPdfError = MediaDownloadError


def normalize_protocol_pdf_rel(media_rel: str) -> str:
    rel = normalize_media_download_rel(media_rel)
    if not rel.lower().endswith(".pdf"):
        raise ProtocolMediaPdfError("Povoleno je jen PDF.")
    if not (
        rel.startswith("protokoly/") or rel.startswith("print_cache/protokoly/")
    ):
        raise ProtocolMediaPdfError("Soubor není v povoleném adresáři.")
    return rel


def resolve_protocol_pdf_path(media_rel: str) -> Path:
    return resolve_media_download_path(normalize_protocol_pdf_rel(media_rel))


def protocol_pdf_url_for_media_rel(media_rel: str) -> str:
    # Stejný view jako media_download; URL zůstává protocol-media.pdf kvůli existujícím odkazům.
    from urllib.parse import urlencode

    from django.urls import reverse

    rel = normalize_protocol_pdf_rel(media_rel)
    return f"{reverse('waste_docs:protocol_media_pdf')}?{urlencode({'rel': rel})}"
