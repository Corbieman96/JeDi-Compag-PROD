from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from waste_docs.services.customer_request_day_kind_counts_modal import (
    build_day_kind_counts_modal_payload,
    resolve_day_for_customer_request,
)

from .common import can_dispatcher_review, role


@login_required
@require_GET
def customer_request_day_kind_counts_json(request, pk: int):
    if not can_dispatcher_review(request.user):
        return JsonResponse({"ok": False, "error": "Nemáte oprávnění."}, status=403)

    item = get_object_or_404(CustomerRequest.objects.only("pk", "target_date", "created_by_id"), pk=pk)
    r = role(request.user)
    if not request.user.is_superuser and r == ROLE_ZADAVATEL and item.created_by_id != request.user.pk:
        return JsonResponse({"ok": False, "error": "Tento požadavek nepatří k vašemu účtu."}, status=403)

    day = resolve_day_for_customer_request(item, request.GET.get("date"))
    if day is None:
        return JsonResponse({"ok": False, "error": "Neplatné datum."}, status=400)

    payload = build_day_kind_counts_modal_payload(request.user, day)
    return JsonResponse({"ok": True, "data": payload})
