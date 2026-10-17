from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from customer_requests.models import CustomerRequest
from customer_requests.recurrence_series.forms import (
    SeriesCancelAllForm,
    SeriesCancelRangeForm,
    SeriesCancelSelectedForm,
    SeriesDefinitionForm,
    SeriesShiftForm,
)
from customer_requests.recurrence_series.services.cancel import (
    cancel_open_occurrences,
    cancel_series_range,
)
from customer_requests.recurrence_series.services.series_ops import (
    is_open_occurrence,
    partition_open_frozen,
    propagate_fields,
    series_occurrences,
    shift_open_occurrences,
    update_series_definition,
)
from waste_docs.services.customer_request_recurrence import (
    format_recurrence_label,
    recurrence_series_root,
)
from waste_docs.views.customer_requests.common import can_dispatcher_review


def _parse_selected_ids(request) -> list[int] | None:
    raw_list = request.POST.getlist("occurrence_ids")
    if raw_list:
        out: list[int] = []
        for part in raw_list:
            for bit in str(part).split(","):
                bit = bit.strip()
                if bit.isdigit():
                    out.append(int(bit))
        return out
    raw = (request.POST.get("occurrence_ids") or "").strip()
    if not raw:
        return None
    out = []
    for bit in raw.replace(";", ",").split(","):
        bit = bit.strip()
        if bit.isdigit():
            out.append(int(bit))
    return out


def _resolve_series_root(pk: int) -> CustomerRequest | None:
    item = (
        CustomerRequest.objects.select_related("recurrence_parent_request")
        .filter(pk=pk)
        .first()
    )
    if not item:
        return None
    root = recurrence_series_root(item)
    if root.is_recurring or root.recurrence_child_requests.exists() or item.recurrence_parent_request_id:
        return root
    return None


@login_required
@require_http_methods(["GET", "POST"])
def series_manage(request, pk: int):
    if not can_dispatcher_review(request.user):
        return HttpResponseForbidden("Nemáte oprávnění spravovat sérii.")
    root = _resolve_series_root(pk)
    if root is None:
        messages.error(request, "Požadavek není součástí opakované série.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    rows = series_occurrences(root)
    open_rows, frozen_rows = partition_open_frozen(rows)

    definition_form = SeriesDefinitionForm(
        initial={
            "recurrence_weekdays_pick": [
                x for x in (root.recurrence_weekdays or "").split(",") if x
            ],
            "recurrence_until": root.recurrence_until,
        }
    )
    shift_form = SeriesShiftForm(initial={"delta_days": 0})
    cancel_all_form = SeriesCancelAllForm()
    cancel_selected_form = SeriesCancelSelectedForm()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        selected = _parse_selected_ids(request)

        try:
            if action == "definition":
                definition_form = SeriesDefinitionForm(request.POST)
                if definition_form.is_valid():
                    result = update_series_definition(
                        root,
                        weekdays_csv=definition_form.weekdays_csv(),
                        until=definition_form.cleaned_data["recurrence_until"],
                        actor=request.user,
                    )
                    messages.success(
                        request,
                        (
                            f"Pravidelnost uložena. Zrušeno {result['cancelled']}, "
                            f"doplněno {result['created']}."
                            + (
                                f" Zmrazených mimo sadu: {result['frozen_outside']}."
                                if result["frozen_outside"]
                                else ""
                            )
                        ),
                    )
                    return redirect("customer_request_recurrence_series:manage", pk=root.pk)

            elif action == "propagate":
                n = propagate_fields(root, request.user, occurrence_ids=selected)
                messages.success(request, f"Propagováno na {n} otevřených termínů.")
                return redirect("customer_request_recurrence_series:manage", pk=root.pk)

            elif action == "shift":
                shift_form = SeriesShiftForm(request.POST)
                if shift_form.is_valid():
                    result = shift_open_occurrences(
                        root,
                        shift_form.cleaned_data["delta_days"],
                        request.user,
                        occurrence_ids=selected,
                    )
                    messages.success(
                        request,
                        f"Posunuto {result['shifted']} termínů"
                        + (
                            f", přeskočeno {result['skipped']}."
                            if result["skipped"]
                            else "."
                        ),
                    )
                    return redirect("customer_request_recurrence_series:manage", pk=root.pk)

            elif action == "cancel_selected":
                cancel_selected_form = SeriesCancelSelectedForm(request.POST)
                if not selected:
                    messages.error(request, "Vyberte alespoň jeden otevřený termín.")
                elif cancel_selected_form.is_valid():
                    cancelled = cancel_open_occurrences(
                        root,
                        request.user,
                        reason=cancel_selected_form.cleaned_data["reason"],
                        occurrence_ids=selected,
                    )
                    messages.success(request, f"Zrušeno {len(cancelled)} vybraných termínů.")
                    return redirect("customer_request_recurrence_series:manage", pk=root.pk)

            elif action == "cancel_all":
                cancel_all_form = SeriesCancelAllForm(request.POST)
                if cancel_all_form.is_valid():
                    cancelled = cancel_open_occurrences(
                        root,
                        request.user,
                        reason=cancel_all_form.cleaned_data["reason"],
                        from_date=cancel_all_form.cleaned_data.get("from_date"),
                    )
                    messages.success(request, f"Zrušeno {len(cancelled)} otevřených termínů.")
                    return redirect("customer_request_recurrence_series:manage", pk=root.pk)

            else:
                messages.error(request, "Neznámá akce.")
        except ValueError as exc:
            messages.error(request, str(exc))

        rows = series_occurrences(root)
        open_rows, frozen_rows = partition_open_frozen(rows)

    occurrence_rows = []
    for row in rows:
        occurrence_rows.append(
            {
                "item": row,
                "is_open": is_open_occurrence(row),
                "is_root": row.pk == root.pk,
            }
        )

    return render(
        request,
        "customer_requests/recurrence_series/manage.html",
        {
            "root": root,
            "occurrence_rows": occurrence_rows,
            "open_count": len(open_rows),
            "frozen_count": len(frozen_rows),
            "series_label": format_recurrence_label(
                root.recurrence_weekdays, root.recurrence_until
            ),
            "definition_form": definition_form,
            "shift_form": shift_form,
            "cancel_all_form": cancel_all_form,
            "cancel_selected_form": cancel_selected_form,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def series_cancel_range(request, pk: int):
    if not can_dispatcher_review(request.user):
        return HttpResponseForbidden("Nemáte oprávnění spravovat sérii.")
    root = _resolve_series_root(pk)
    if root is None:
        messages.error(request, "Požadavek není součástí opakované série.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    form = SeriesCancelRangeForm()
    if request.method == "POST":
        form = SeriesCancelRangeForm(request.POST)
        if form.is_valid():
            try:
                cancelled = cancel_series_range(
                    root,
                    request.user,
                    from_date=form.cleaned_data["from_date"],
                    to_date=form.cleaned_data["to_date"],
                    reason=form.cleaned_data["reason"],
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Zrušeno {len(cancelled)} otevřených termínů v zadaném rozsahu.",
                )
                return redirect("customer_request_recurrence_series:manage", pk=root.pk)

    open_rows = [r for r in series_occurrences(root) if is_open_occurrence(r)]
    return render(
        request,
        "customer_requests/recurrence_series/cancel_range.html",
        {
            "root": root,
            "form": form,
            "open_count": len(open_rows),
            "series_label": format_recurrence_label(
                root.recurrence_weekdays, root.recurrence_until
            ),
        },
    )
