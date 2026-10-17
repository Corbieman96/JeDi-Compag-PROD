from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.ride_soft_delete import RideSoftDeleteError, soft_delete_pruvodka
from waste_docs.services.ride_soft_delete.permissions import can_soft_delete_pruvodka
from waste_docs.services.ride_soft_delete.validation import MAX_REASON_LEN, MIN_REASON_LEN
from waste_docs.views.access import waste_docs_list_access_required


def _load_ride_for_soft_delete(pk: int) -> Pruvodka:
    return get_object_or_404(
        Pruvodka.objects.select_related("activity"),
        pk=pk,
        is_archived=False,
    )


@waste_docs_list_access_required
@require_http_methods(["GET", "POST"])
def ride_soft_delete_confirm(request, pk):
    item = _load_ride_for_soft_delete(pk)
    if not can_soft_delete_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")

    reason_value = ""
    if request.method == "POST":
        reason_value = (request.POST.get("reason") or "").strip()
        try:
            soft_delete_pruvodka(pruvodka=item, actor=request.user, reason=reason_value)
        except RideSoftDeleteError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Jízda byla bezpečně smazána.")
            return redirect("waste_docs:ride_soft_delete_log_list")

    return render(
        request,
        "waste_docs/ride_soft_delete/confirm.html",
        {
            "item": item,
            "reason_value": reason_value,
            "min_reason_len": MIN_REASON_LEN,
            "max_reason_len": MAX_REASON_LEN,
        },
    )
