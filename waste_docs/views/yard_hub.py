"""Rozcestník sběrného dvora: hlášení (svoz pro dispečera) vs. založení jízdy (přímé)."""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from users.services.sberny_dvur import can_create_svoz_request, get_sberny_dvur_subject
from waste_docs.yard_matrix import yard_pruvodka_pair_exists, yard_svoz_matrix_row_exists


@login_required
def yard_hub(request):
    if not can_create_svoz_request(request.user):
        raise Http404("Tato stránka není pro tento účet k dispozici.")
    subject = get_sberny_dvur_subject(request.user)
    if not subject:
        raise Http404("Chybí přiřazený subjekt sběrného dvora.")

    has_pruvodka = bool(subject.yard_allow_pruvodka and yard_pruvodka_pair_exists(subject))
    has_svoz = bool(subject.yard_allow_matrix and yard_svoz_matrix_row_exists(subject))

    if has_pruvodka and not has_svoz:
        return redirect(reverse("waste_docs:yard_ride_create"))
    if has_svoz and not has_pruvodka:
        return redirect(reverse("waste_docs:svoz_request"))

    return render(
        request,
        "waste_docs/yard_hub.html",
        {
            "subject": subject,
            "has_pruvodka": has_pruvodka,
            "has_svoz": has_svoz,
            "no_paths": not has_pruvodka and not has_svoz,
        },
    )
