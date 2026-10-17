from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404

from users.services.waste_doc_permissions import (
    can_access_pruvodka_files,
    can_access_waste_docs_list,
)


def waste_docs_list_access_required(view_func):
    """Přístup k seznamu jízd a read-only detailu — podle menu Jízdy / nav_pruvodky."""

    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not can_access_waste_docs_list(request.user):
            raise Http404("Stránka neexistuje.")
        return view_func(request, *args, **kwargs)

    return wrapped


def pruvodka_file_access_required(view_func):
    """PDF / download průvodky — uživatel se seznamem jízd nebo oprávněním ze sběrného dvora."""

    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not can_access_pruvodka_files(request.user):
            raise Http404("Stránka neexistuje.")
        return view_func(request, *args, **kwargs)

    return wrapped
