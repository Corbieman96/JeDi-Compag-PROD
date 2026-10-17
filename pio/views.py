from __future__ import annotations

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.views.name_subject import name_catalog_access_required
from pio.forms import PioRevisionUploadForm
from pio.models import PioRevision
from pio.services import effective_pio_file
from pio.services.archive import archive_pair_pio_document, set_pair_active_pio_from_revision
from pio.services.global_search import search_pio_items
from pio.xlsx_generate import build_user_pio_download_filename, generate_user_pio_xlsx_bytes_for_pair
from users.services.access import can_export_name_subject_pio_profile


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


def _get_pair_for_subject(subject_pk: int, pair_pk: int) -> NameSubjectWasteSuffixPair:
    subject = get_object_or_404(NameSubjectProfile, pk=subject_pk)
    pair = get_object_or_404(
        NameSubjectWasteSuffixPair.objects.select_related(
            "subject_profile",
            "subject_profile__name",
            "subject_profile__ico",
            "subject_profile__address_profile__fulfillment_address",
            "subject_profile__address_profile__facility_address",
            "waste_type",
            "suffix",
            "suffix__site_profile",
        ),
        pk=pair_pk,
        subject_profile_id=subject.pk,
    )
    return pair


@name_catalog_access_required
def pair_pio_archive(request, subject_pk: int, pair_pk: int):
    pair = _get_pair_for_subject(subject_pk, pair_pk)
    subject = pair.subject_profile

    if request.method == "POST":
        form = PioRevisionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            rev: PioRevision = form.save(commit=False)
            rev.pair = pair
            rev.created_by = request.user if request.user.is_authenticated else None
            rev.save()
            set_pair_active_pio_from_revision(pair, rev)
            messages.success(request, "PIO bylo nahráno do archivu a nastaveno jako aktivní u páru.")
            return redirect("catalogs:name_pair_pio", subject_pk=subject_pk, pair_pk=pair_pk)
    else:
        form = PioRevisionUploadForm()

    revisions = list(
        PioRevision.objects.filter(pair=pair)
        .select_related("created_by")
        .order_by("-created_at", "-pk")
    )
    legacy = pair.pio_document if pair.pio_document and getattr(pair.pio_document, "name", "") else None
    has_revisions = bool(revisions)
    return render(
        request,
        "pio/pair_archive.html",
        {
            "subject": subject,
            "pair": pair,
            "form": form,
            "revisions": revisions,
            "legacy_pio": legacy,
            "effective_pio": effective_pio_file(pair),
            "subject_edit_url": reverse("catalogs:name_edit", args=[subject_pk]),
            "has_revisions": has_revisions,
        },
    )


@name_catalog_access_required
def pair_pio_archive_active(request, subject_pk: int, pair_pk: int):
    """Přesune aktivní PIO z pole na páru do archivu (stejně jako zaškrtnutí ve formuláři subjektu)."""
    pair = _get_pair_for_subject(subject_pk, pair_pk)
    if request.method != "POST":
        return redirect("catalogs:name_pair_pio", subject_pk=subject_pk, pair_pk=pair_pk)
    if pair.pio_document and getattr(pair.pio_document, "name", ""):
        archive_pair_pio_document(
            pair,
            note="Přesunuto z aktivního PIO u páru (stránka archivu)",
            created_by=request.user if request.user.is_authenticated else None,
        )
        messages.success(request, "Aktivní PIO bylo přesunuto do archivu. Pole na páru je volné pro nový soubor.")
    return redirect("catalogs:name_pair_pio", subject_pk=subject_pk, pair_pk=pair_pk)


@name_catalog_access_required
def pair_pio_download_xlsx(request, subject_pk: int, pair_pk: int):
    """Stejná uživatelská šablona PIO jako ``catalogs:name_user_pio_xlsx`` — údaje z profilu a z daného páru."""
    if not can_export_name_subject_pio_profile(request.user):
        raise PermissionDenied
    pair = _get_pair_for_subject(subject_pk, pair_pk)
    subject = pair.subject_profile
    try:
        payload = generate_user_pio_xlsx_bytes_for_pair(subject, pair)
        fname = build_user_pio_download_filename(subject, waste_suffix_pair=pair)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("catalogs:name_pair_pio", subject_pk=subject_pk, pair_pk=pair_pk)
    resp = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=fname)
    return resp


@admin_required
def pio_global_search(request):
    q = (request.GET.get("q") or "").strip()
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()

    date_from = None
    date_to = None
    if date_from_raw:
        try:
            date_from = datetime.fromisoformat(date_from_raw).date()
        except ValueError:
            date_from = None
    if date_to_raw:
        try:
            date_to = datetime.fromisoformat(date_to_raw).date()
        except ValueError:
            date_to = None

    items = search_pio_items(q=q, date_from=date_from, date_to=date_to, limit=500)
    return render(
        request,
        "pio/global_search.html",
        {
            "items": items,
            "q": q,
            "date_from": date_from_raw,
            "date_to": date_to_raw,
        },
    )
