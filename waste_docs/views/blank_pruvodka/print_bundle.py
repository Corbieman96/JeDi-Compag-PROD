from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from waste_docs.services.blank_pruvodka.print_bundle import (
    build_blank_print_file_rows,
    parse_blank_print_pks,
    rides_for_blank_print,
)


@login_required
def blank_pruvodka_print(request):
    pks = parse_blank_print_pks(
        pks_raw=request.GET.get("pks") or "",
        pk_raw=request.GET.get("pk") or "",
    )
    if not pks:
        raise Http404("Chybí parametr pks.")

    rides = rides_for_blank_print(pks, request.user)
    if not rides:
        messages.warning(request, "Bianko průvodky k tisku nejsou dostupné.")
        return redirect(reverse("core:dashboard"))

    print_rows, file_rows, zpo_warnings, prepare_ctx = build_blank_print_file_rows(pks, request.user)
    if zpo_warnings:
        preview = ", ".join(zpo_warnings[:8])
        extra = f" (+{len(zpo_warnings) - 8} dalších)" if len(zpo_warnings) > 8 else ""
        messages.warning(
            request,
            f"ZPO se u bianko průvodek negeneruje — přeskočeno u: {preview}{extra}.",
        )

    selected_date = rides[0].drive_date
    pks_csv = ",".join(str(p) for p in pks)
    return render(
        request,
        "waste_docs/blank_print_bundle.html",
        {
            "selected_date": selected_date,
            "selected_date_iso": selected_date.isoformat(),
            "print_rows": print_rows,
            "file_rows": file_rows,
            "rides_count": len(rides),
            "pks": pks_csv,
            **prepare_ctx,
            "print_prepare_url": reverse("waste_docs:blank_pruvodka_print_prepare"),
        },
    )
