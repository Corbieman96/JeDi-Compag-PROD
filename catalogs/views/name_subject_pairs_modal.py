from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from catalogs.models import NameSubjectProfile, ZpoDocument
from catalogs.services.name_subject_pairs_save import (
    apply_pairs_ordering,
    build_pair_formset,
    save_name_subject_waste_suffix_pairs,
)
from catalogs.services.name_subject_pruvodka_snapshot import (
    get_profile_for_pruvodka_snapshot,
    subject_snapshot_for_pruvodka,
)
from catalogs.services.pair_fulfillment_address import (
    known_fulfillment_addresses_for_subject,
    resolved_central_fulfillment_address,
)
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from catalogs.views.name_subject import name_catalog_access_required
from users.services.access import can_see_all_waste_docs


def _pairs_modal_context(request, profile: NameSubjectProfile, formset):
    pio_revision_counts: dict[int, int] = {}
    if profile.pk:
        pio_revision_counts = {
            row["pk"]: row["cnt"]
            for row in profile.waste_suffix_pairs.annotate(cnt=Count("pio_revisions")).values("pk", "cnt")
        }
    zpo_url_by_id = {
        str(d.pk): (d.file.url if d.file and getattr(d.file, "name", None) else "")
        for d in ZpoDocument.objects.only("pk", "file")
    }
    return {
        "formset": formset,
        "item": profile,
        "show_dispatch_plan_fields": can_see_all_waste_docs(request.user),
        "pio_revision_counts": pio_revision_counts,
        "zpo_url_by_id": zpo_url_by_id,
        "waste_type_combo_meta": waste_type_combo_metadata(),
        "full_edit_url": reverse("catalogs:name_edit", args=[profile.pk]),
        "known_fulfillment_addresses": known_fulfillment_addresses_for_subject(profile),
        "central_fulfillment_address": resolved_central_fulfillment_address(profile=profile),
    }


@login_required
@name_catalog_access_required
@require_http_methods(["GET", "POST"])
def name_subject_pairs_modal(request, pk: int):
    profile = get_object_or_404(
        NameSubjectProfile.objects.select_related(
            "name",
            "ico",
            "address_profile__fulfillment_address",
            "address_profile__facility_address",
        ),
        pk=pk,
    )

    if request.method == "POST":
        result = save_name_subject_waste_suffix_pairs(profile, request.user, request.POST, request.FILES)
        if not result.ok:
            formset = result.formset or build_pair_formset(request.user, profile, data=request.POST, files=request.FILES)
            html = render(
                request,
                "catalogs/partials/name_subject_pairs_modal_body.html",
                _pairs_modal_context(request, profile, formset),
            ).content.decode("utf-8")
            return JsonResponse(
                {"ok": False, "error": result.error_text or "Formulář nelze uložit.", "html": html},
                status=400,
            )
        refreshed = get_profile_for_pruvodka_snapshot(profile.pk)
        return JsonResponse(
            {
                "ok": True,
                "subject": subject_snapshot_for_pruvodka(refreshed),
            }
        )

    formset = build_pair_formset(request.user, profile)
    apply_pairs_ordering(formset)
    return render(
        request,
        "catalogs/partials/name_subject_pairs_modal_body.html",
        _pairs_modal_context(request, profile, formset),
    )
