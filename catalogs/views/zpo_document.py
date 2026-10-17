from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogs.forms.zpo_document import ZpoDocumentForm
from catalogs.models import ZpoDocument
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from catalogs.services.zpo_list_search import filter_zpo_documents_for_query
from catalogs.views.name_subject import name_catalog_access_required


def _zpo_option_payload(doc: ZpoDocument) -> dict:
    return {
        "id": doc.pk,
        "label": doc.label,
        "url": doc.file.url if doc.file and getattr(doc.file, "name", None) else "",
        "waste_type_id": doc.waste_type_id,
        "suffix_id": doc.suffix_id,
    }


@name_catalog_access_required
def zpo_list(request):
    q = (request.GET.get("q") or "").strip()
    items = ZpoDocument.objects.select_related("waste_type", "suffix").order_by("label", "id")
    if q:
        items = filter_zpo_documents_for_query(items, q)
    return render(
        request,
        "catalogs/zpo_list.html",
        {"items": items, "q": q},
    )


def _zpo_form_context(form, *, is_edit):
    return {
        "form": form,
        "is_edit": is_edit,
        "waste_type_combo_meta": waste_type_combo_metadata(),
    }


@name_catalog_access_required
def zpo_create(request):
    form = ZpoDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:zpo_list")
    return render(request, "catalogs/zpo_form.html", _zpo_form_context(form, is_edit=False))


@name_catalog_access_required
def zpo_edit(request, pk):
    item = get_object_or_404(ZpoDocument, pk=pk)
    form = ZpoDocumentForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:zpo_list")
    ctx = _zpo_form_context(form, is_edit=True)
    ctx["item"] = item
    return render(request, "catalogs/zpo_form.html", ctx)


@name_catalog_access_required
def zpo_delete(request, pk):
    item = get_object_or_404(ZpoDocument, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:zpo_list")
    return render(request, "catalogs/zpo_confirm_delete.html", {"item": item})


@name_catalog_access_required
def zpo_options_json(request):
    """Serazeny seznam ZPO pro dropdown + informace pro predvolbu podle waste/suffix."""
    waste_id = request.GET.get("waste_type_id") or ""
    suffix_id = request.GET.get("suffix_id") or ""
    try:
        waste_pk = int(waste_id) if str(waste_id).strip().isdigit() else None
    except (TypeError, ValueError):
        waste_pk = None
    try:
        suffix_pk = int(suffix_id) if str(suffix_id).strip().isdigit() else None
    except (TypeError, ValueError):
        suffix_pk = None

    docs = list(ZpoDocument.objects.select_related("waste_type", "suffix").order_by("label", "id"))

    def rank_key(d: ZpoDocument) -> tuple:
        if waste_pk and suffix_pk and d.waste_type_id == waste_pk and d.suffix_id == suffix_pk:
            return (0, d.label.lower(), d.pk)
        if waste_pk and d.waste_type_id == waste_pk:
            return (1, d.label.lower(), d.pk)
        if suffix_pk and d.suffix_id == suffix_pk:
            return (2, d.label.lower(), d.pk)
        return (3, d.label.lower(), d.pk)

    docs.sort(key=rank_key)

    preferred_id = None
    for d in docs:
        if waste_pk and suffix_pk and d.waste_type_id == waste_pk and d.suffix_id == suffix_pk:
            preferred_id = d.pk
            break
    if preferred_id is None:
        for d in docs:
            if waste_pk and d.waste_type_id == waste_pk:
                preferred_id = d.pk
                break
    if preferred_id is None:
        for d in docs:
            if suffix_pk and d.suffix_id == suffix_pk:
                preferred_id = d.pk
                break

    return JsonResponse(
        {
            "ok": True,
            "options": [_zpo_option_payload(d) for d in docs],
            "preferred_id": preferred_id,
        }
    )


@name_catalog_access_required
@require_POST
def zpo_inline_create(request):
    form = ZpoDocumentForm(request.POST, request.FILES)
    if not form.is_valid():
        err = ""
        if form.errors:
            first = next(iter(form.errors.values()))
            err = first[0] if first else ""
        return JsonResponse({"ok": False, "error": err or "Chyba validace."}, status=400)

    doc = form.save()
    return JsonResponse({"ok": True, **_zpo_option_payload(doc)})
