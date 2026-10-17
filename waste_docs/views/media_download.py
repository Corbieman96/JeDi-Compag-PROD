"""Stažení generovaného souboru z MEDIA_ROOT — funguje i při DEBUG=False."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.reports.media_download import (
    MediaDownloadError,
    content_type_for_media_path,
    resolve_media_download_path,
)


def _user_may_open_media_download(user) -> bool:
    if can_see_all_waste_docs(user):
        return True
    return Pruvodka.objects.filter(created_by=user, is_archived=False).exists()


@login_required
def media_download(request):
    media_rel = (request.GET.get("rel") or "").strip()
    try:
        path = resolve_media_download_path(media_rel)
    except MediaDownloadError as exc:
        raise Http404(str(exc)) from exc
    if not _user_may_open_media_download(request.user):
        raise Http404("Soubor není k dispozici.")
    return FileResponse(
        path.open("rb"),
        content_type=content_type_for_media_path(path),
        as_attachment=False,
        filename=path.name,
    )
