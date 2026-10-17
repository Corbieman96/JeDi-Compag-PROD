import logging
import unicodedata
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import BooleanField, Case, Count, Prefetch, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from address_data.services import geocode_address, reverse_geocode, suggest_addresses
from catalogs.services.pair_fulfillment_address import (
    known_fulfillment_addresses_for_form,
    resolved_central_fulfillment_address,
)
from catalogs.forms import NameSubjectProfileForm
from catalogs.forms.name_subject_pairs import NameSubjectWasteSuffixPairFormSet
from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair, ZpoDocument
from catalogs.services.ares import fetch_company_by_ico
from catalogs.services.fulfillment_address import normalize_fulfillment_address
from catalogs.services.ruian_lookup import resolve_orp_and_iczuj
from catalogs.services.name_subject_pairs_save import (
    apply_pairs_ordering,
    build_pair_formset,
    format_pair_formset_errors,
    save_name_subject_waste_suffix_pairs,
)
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from core.models import AppSettings
from pio.xlsx_generate import (
    build_user_pio_download_filename,
    build_user_pio_download_filename_from_live_post,
    generate_user_pio_xlsx_bytes,
    generate_user_pio_xlsx_bytes_from_live_post,
)
from users.services.access import can_export_name_subject_pio_profile, can_see_all_waste_docs
from users.services.catalog_row_visibility import effective_show_catalog_index_row

logger = logging.getLogger(__name__)
NAME_SUBJECT_PER_PAGE_OPTIONS = (25, 50, 100, 200)
NAME_SUBJECT_PER_PAGE_DEFAULT = 50


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


def name_subject_delete_allowed(view_func):
    """Mazání subjektů v katalogu jmen — pouze Admin (superuser)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(request.user, "is_superuser", False):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


def name_catalog_access_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and effective_show_catalog_index_row(u, "name")
    )(view)


def _normalize_search_text(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    decomp = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomp if not unicodedata.combining(ch))


def _name_subject_row_search_blob(item: NameSubjectProfile) -> str:
    parts = [
        item.name.value if item.name_id else "",
        item.company_name or "",
        item.ico.value if item.ico_id else "",
        item.facility_address.value if item.facility_address_id else "",
        item.fulfillment_address.value if item.fulfillment_address_id else "",
    ]
    for pair in item.waste_suffix_pairs.all():
        parts.append(pair.waste_type.value if pair.waste_type_id else "")
        parts.append(pair.waste_type.code if pair.waste_type_id else "")
        parts.append(pair.suffix.value if pair.suffix_id else "")
    return " ".join(parts)


def _name_subject_list_queryset(query: str):
    items = (
        NameSubjectProfile.objects.select_related(
            "name",
            "ico",
            "address_profile__facility_address",
            "address_profile__fulfillment_address",
            "zpo_settings",
        )
        .prefetch_related(
            "allowed_waste_types",
            "allowed_suffixes",
            "waste_suffix_pairs__waste_type",
            "waste_suffix_pairs__suffix",
        )
        .annotate(
            zpo_vypnuto=Case(
                When(zpo_settings__system_generates_zpo=False, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
    )
    q = (query or "").strip()
    if q:
        items = items.filter(
            Q(name__value__icontains=q)
            | Q(company_name__icontains=q)
            | Q(ico__value__icontains=q)
            | Q(address_profile__facility_address__value__icontains=q)
            | Q(address_profile__fulfillment_address__value__icontains=q)
            | Q(waste_suffix_pairs__waste_type__value__icontains=q)
            | Q(waste_suffix_pairs__waste_type__code__icontains=q)
            | Q(waste_suffix_pairs__suffix__value__icontains=q)
        ).distinct()
    return items.order_by("company_name", "name__value")


def _name_subject_row_dict(item: NameSubjectProfile, *, include_delete_url: bool) -> dict:
    all_pairs = list(item.waste_suffix_pairs.all())
    n_pairs = len(all_pairs)
    pairs = []
    for p in all_pairs[:6]:
        pairs.append({"waste": str(p.waste_type), "suffix": (p.suffix.value or "") if p.suffix_id else ""})
    row = {
        "pk": item.pk,
        "name": item.name.value if item.name_id else "",
        "ico": (item.ico.value if item.ico_id else "") or "",
        "company": item.company_name or "",
        "is_municipality": bool(item.is_municipality),
        "zpo_vypnuto": bool(getattr(item, "zpo_vypnuto", False)),
        "pairs": pairs,
        "n_pairs": n_pairs,
        "facility": (item.facility_address.value if item.facility_address_id else "") or "",
        "fulfillment": (item.fulfillment_address.value if item.fulfillment_address_id else "") or "",
        "edit_url": reverse("catalogs:name_edit", args=[item.pk]),
    }
    if include_delete_url:
        row["delete_url"] = reverse("catalogs:name_delete", args=[item.pk])
    return row


@name_catalog_access_required
def name_subject_list(request):
    query = (request.GET.get("q") or "").strip()
    per_page_raw = (request.GET.get("per_page") or "").strip()
    try:
        per_page = int(per_page_raw or NAME_SUBJECT_PER_PAGE_DEFAULT)
    except (TypeError, ValueError):
        per_page = NAME_SUBJECT_PER_PAGE_DEFAULT
    if per_page not in NAME_SUBJECT_PER_PAGE_OPTIONS:
        per_page = NAME_SUBJECT_PER_PAGE_DEFAULT
    items = _name_subject_list_queryset(query)
    if query and not items.exists():
        # Fallback: diakritika/kolace databáze nemusí vždy vracet očekávané výsledky.
        q_norm = _normalize_search_text(query)
        base_items = (
            NameSubjectProfile.objects.select_related(
                "name",
                "ico",
                "address_profile__facility_address",
                "address_profile__fulfillment_address",
                "zpo_settings",
            )
            .prefetch_related(
                "allowed_waste_types",
                "allowed_suffixes",
                "waste_suffix_pairs__waste_type",
                "waste_suffix_pairs__suffix",
            )
            .annotate(
                zpo_vypnuto=Case(
                    When(zpo_settings__system_generates_zpo=False, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
            .order_by("company_name", "name__value")
        )
        fallback_ids = []
        for row in base_items:
            if q_norm and q_norm in _normalize_search_text(_name_subject_row_search_blob(row)):
                fallback_ids.append(row.pk)
        if fallback_ids:
            items = base_items.filter(pk__in=fallback_ids)
    paginator = Paginator(items, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    elided_pages = []
    if paginator.num_pages > 1:
        for p in paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1):
            if isinstance(p, int):
                elided_pages.append({"ellipsis": False, "number": p})
            else:
                elided_pages.append({"ellipsis": True})
    if request.GET.get("format") == "json":
        include_delete = bool(getattr(request.user, "is_superuser", False))
        data = [
            _name_subject_row_dict(row, include_delete_url=include_delete)
            for row in page_obj.object_list
        ]
        return JsonResponse(
            {
                "ok": True,
                "data": data,
                "count": len(data),
                "pagination": {
                    "page": page_obj.number,
                    "num_pages": paginator.num_pages,
                    "per_page": per_page,
                    "total_count": paginator.count,
                    "has_previous": page_obj.has_previous(),
                    "has_next": page_obj.has_next(),
                    "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
                    "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
                },
            }
        )
    return render(
        request,
        "catalogs/name_subject_list.html",
        {
            "items": page_obj.object_list,
            "page_obj": page_obj,
            "elided_pages": elided_pages,
            "per_page": per_page,
            "per_page_choices": NAME_SUBJECT_PER_PAGE_OPTIONS,
            "q": query,
        },
    )


def _name_subject_form_context(form, formset, item, is_edit, app_settings, *, actor_user):
    pio_revision_counts: dict[int, int] = {}
    if item and item.pk:
        pio_revision_counts = {
            row["pk"]: row["cnt"]
            for row in item.waste_suffix_pairs.annotate(cnt=Count("pio_revisions")).values("pk", "cnt")
        }
    zpo_url_by_id = {
        str(d.pk): (d.file.url if d.file and getattr(d.file, "name", None) else "")
        for d in ZpoDocument.objects.only("pk", "file")
    }
    if item and item.pk:
        pio_export_action_url = reverse("catalogs:name_user_pio_xlsx", args=[item.pk])
    else:
        pio_export_action_url = reverse("catalogs:name_user_pio_xlsx_draft")
    return {
        "form": form,
        "formset": formset,
        "item": item,
        "is_edit": is_edit,
        "default_map_lat": app_settings.default_map_lat,
        "default_map_lng": app_settings.default_map_lng,
        "waste_type_combo_meta": waste_type_combo_metadata(),
        "pio_revision_counts": pio_revision_counts,
        "zpo_url_by_id": zpo_url_by_id,
        "show_dispatch_plan_fields": can_see_all_waste_docs(actor_user) if actor_user else False,
        "pio_export_action_url": pio_export_action_url,
        "known_fulfillment_addresses": known_fulfillment_addresses_for_form(form=form, profile=item),
        "central_fulfillment_address": resolved_central_fulfillment_address(form=form, profile=item),
    }


def _pair_formset(request, instance=None, data=None, files=None):
    if instance is None:
        kwargs: dict = {
            "form_kwargs": {
                "show_dispatch_plan_fields": can_see_all_waste_docs(request.user),
                "actor_user": request.user,
            }
        }
        if data is not None:
            kwargs["data"] = data
        if files is not None:
            kwargs["files"] = files
        return NameSubjectWasteSuffixPairFormSet(**kwargs)
    return build_pair_formset(request.user, instance, data=data, files=files)


def _format_name_subject_form_errors(form, formset) -> str:
    parts = []
    if form.non_field_errors():
        parts.extend(str(e) for e in form.non_field_errors())
    for field_name, errors in form.errors.items():
        if field_name == "__all__":
            continue
        label = form.fields.get(field_name).label if form.fields.get(field_name) else field_name
        for err in errors:
            parts.append(f"{label}: {err}")
    pair_err = format_pair_formset_errors(formset)
    if pair_err:
        parts.append(pair_err)
    return " | ".join(parts)


@name_catalog_access_required
def name_subject_create(request):
    app_settings = AppSettings.load()
    item = None
    if request.method == "POST":
        pk_raw = (request.POST.get("existing_profile_pk") or "").strip()
        if pk_raw.isdigit():
            item = get_object_or_404(NameSubjectProfile, pk=int(pk_raw))
        form = NameSubjectProfileForm(request.POST, instance=item, actor_user=request.user)
        if form.is_valid():
            profile = form.save()
            pairs_result = save_name_subject_waste_suffix_pairs(
                profile, request.user, request.POST, request.FILES
            )
            if pairs_result.ok:
                messages.success(request, "Subjekt byl uložen.")
                return redirect(f"{reverse('catalogs:name_edit', args=[profile.pk])}?saved=1")
            formset = pairs_result.formset or _pair_formset(
                request, instance=profile, data=request.POST, files=request.FILES
            )
            error_text = _format_name_subject_form_errors(form, formset)
            if error_text:
                logger.warning("name_subject_create formset invalid: %s", error_text)
                messages.error(request, f"Formulář nelze uložit: {error_text}")
            return render(
                request,
                "catalogs/name_subject_form.html",
                _name_subject_form_context(
                    NameSubjectProfileForm(instance=profile, actor_user=request.user),
                    formset,
                    profile,
                    False,
                    app_settings,
                    actor_user=request.user,
                ),
            )
        formset = (
            _pair_formset(request, instance=item, data=request.POST, files=request.FILES)
            if item
            else _pair_formset(request, data=request.POST, files=request.FILES)
        )
        error_text = _format_name_subject_form_errors(form, formset)
        if error_text:
            logger.warning("name_subject_create form invalid: %s", error_text)
            messages.error(request, f"Formulář nelze uložit: {error_text}")
    else:
        form = NameSubjectProfileForm(actor_user=request.user)
        formset = _pair_formset(request)
        apply_pairs_ordering(formset)
    return render(
        request,
        "catalogs/name_subject_form.html",
        _name_subject_form_context(form, formset, item, False, app_settings, actor_user=request.user),
    )


@name_catalog_access_required
def name_subject_edit(request, pk):
    item = get_object_or_404(NameSubjectProfile, pk=pk)
    app_settings = AppSettings.load()
    if request.method == "POST":
        form = NameSubjectProfileForm(request.POST, instance=item, actor_user=request.user)
        formset = _pair_formset(request, instance=item, data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save()
            pairs_result = save_name_subject_waste_suffix_pairs(
                item, request.user, request.POST, request.FILES
            )
            if pairs_result.ok:
                messages.success(request, "Uloženo.")
                return redirect(f"{reverse('catalogs:name_edit', args=[item.pk])}?saved=1")
            formset = pairs_result.formset or formset
        error_text = _format_name_subject_form_errors(form, formset)
        if error_text:
            logger.warning("name_subject_edit invalid pk=%s: %s", item.pk, error_text)
            messages.error(request, f"Formulář nelze uložit: {error_text}")
    else:
        form = NameSubjectProfileForm(instance=item, actor_user=request.user)
        formset = _pair_formset(request, instance=item)
        apply_pairs_ordering(formset)
    return render(
        request,
        "catalogs/name_subject_form.html",
        _name_subject_form_context(form, formset, item, True, app_settings, actor_user=request.user),
    )


@name_catalog_access_required
@require_POST
def name_subject_user_pio_download_draft(request):
    """PIO z neuloženého formuláře nového subjektu (bez PK v URL)."""
    if not can_export_name_subject_pio_profile(request.user):
        raise PermissionDenied
    profile = NameSubjectProfile()
    try:
        data = generate_user_pio_xlsx_bytes_from_live_post(profile, request.POST)
        fname = build_user_pio_download_filename_from_live_post(profile, request.POST)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("catalogs:name_create")
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=fname)
    return resp


@name_catalog_access_required
def name_subject_user_pio_download(request, pk):
    """Stažení Excelu z uživatelské šablony PIO — POST použije aktuální stav formuláře (i neuložený)."""
    if not can_export_name_subject_pio_profile(request.user):
        raise PermissionDenied
    profile = get_object_or_404(
        NameSubjectProfile.objects.select_related(
            "name",
            "ico",
            "address_profile__facility_address",
            "address_profile__fulfillment_address",
            "pio_profile__pio_waste_type",
            "pio_profile__pio_suffix",
        ).prefetch_related(
            Prefetch(
                "waste_suffix_pairs",
                queryset=NameSubjectWasteSuffixPair.objects.select_related(
                    "waste_type",
                    "suffix",
                ).order_by("sort_order", "id"),
            )
        ),
        pk=pk,
    )
    use_live = request.method == "POST"
    try:
        if use_live:
            data = generate_user_pio_xlsx_bytes_from_live_post(profile, request.POST)
            fname = build_user_pio_download_filename_from_live_post(profile, request.POST)
        else:
            data = generate_user_pio_xlsx_bytes(profile)
            fname = build_user_pio_download_filename(profile)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("catalogs:name_edit", args=[pk]))
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=fname)
    return resp


@name_catalog_access_required
@name_subject_delete_allowed
def name_subject_delete(request, pk):
    item = get_object_or_404(NameSubjectProfile, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:name_list")
    return render(request, "catalogs/name_subject_confirm_delete.html", {"item": item})


@name_catalog_access_required
def ares_lookup(request):
    ico = (request.GET.get("ico") or "").strip()
    if not ico:
        return JsonResponse({"ok": False, "error": "Zadejte IČO."}, status=400)
    if not ico.isdigit() or len(ico) != 8:
        return JsonResponse({"ok": False, "error": "IČO musí mít 8 číslic."}, status=400)
    try:
        data = fetch_company_by_ico(ico)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    return JsonResponse({"ok": True, "data": data})


@name_catalog_access_required
def address_suggestions(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 3:
        return JsonResponse({"ok": True, "data": []})
    suggestions = suggest_addresses(query=query, limit=6)
    return JsonResponse({"ok": True, "data": suggestions})


@name_catalog_access_required
def address_geocode(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 3:
        return JsonResponse({"ok": False, "error": "Zadejte přesnější adresu."}, status=400)
    location = geocode_address(query=query)
    if not location:
        return JsonResponse({"ok": False, "error": "Adresu se nepodařilo najít."}, status=404)
    return JsonResponse({"ok": True, "data": location})


@name_catalog_access_required
def address_reverse_geocode(request):
    lat_raw = (request.GET.get("lat") or "").strip()
    lng_raw = (request.GET.get("lng") or "").strip()
    try:
        lat = float(lat_raw.replace(",", "."))
        lng = float(lng_raw.replace(",", "."))
    except ValueError:
        return JsonResponse({"ok": False, "error": "Neplatné souřadnice."}, status=400)
    location = reverse_geocode(lat=lat, lng=lng)
    if not location:
        return JsonResponse({"ok": False, "error": "Adresu se nepodařilo načíst."}, status=404)
    label = normalize_fulfillment_address((location.get("label") or "").strip())
    if label:
        location = {**location, "label": label}
    return JsonResponse({"ok": True, "data": location})


@name_catalog_access_required
def address_admin_units(request):
    lat_raw = (request.GET.get("lat") or "").strip()
    lng_raw = (request.GET.get("lng") or "").strip()
    query = (request.GET.get("q") or "").strip()

    lat = None
    lng = None
    if lat_raw and lng_raw:
        try:
            lat = float(lat_raw.replace(",", "."))
            lng = float(lng_raw.replace(",", "."))
        except ValueError:
            lat = None
            lng = None

    if lat is None or lng is None:
        if len(query) < 3:
            return JsonResponse({"ok": True, "data": {"orp": "", "iczuj": ""}})
        location = geocode_address(query=query)
        if not location:
            return JsonResponse({"ok": True, "data": {"orp": "", "iczuj": ""}})
        lat = float(location["lat"])
        lng = float(location["lng"])

    data = resolve_orp_and_iczuj(query=query, lat=lat, lng=lng)
    logger.info(
        "name/address-admin-units resolved query=%r lat=%s lng=%s orp=%r iczuj=%r",
        query[:120],
        lat,
        lng,
        data.get("orp", ""),
        data.get("iczuj", ""),
    )
    if not data.get("orp"):
        logger.warning(
            "name/address-admin-units missing ORP query=%r lat=%s lng=%s iczuj=%r",
            query[:120],
            lat,
            lng,
            data.get("iczuj", ""),
        )
    return JsonResponse({"ok": True, "data": data})
