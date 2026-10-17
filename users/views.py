from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from users.constants import ROLE_ADMIN
from users.forms import (
    UserAdminEditForm,
    UserWithRoleCreationForm,
    access_profile_defaults_for_save,
)
from users.models import UserAccessProfile
from users.services import build_role_access_context, get_user_role_label, set_user_role
from users.services.sberny_dvur_subject_search import search_sberny_dvur_subjects


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


@admin_required
def user_list(request):
    users = list(User.objects.order_by("username").prefetch_related("groups"))
    for user in users:
        user.role_label = get_user_role_label(user)
    return render(
        request,
        "users/user_list.html",
        {"users": users},
    )


@admin_required
def user_create(request):
    form = UserWithRoleCreationForm(request.POST or None, editor=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        set_user_role(user, form.cleaned_data["role"])
        prof_defaults = access_profile_defaults_for_save(form, existing_profile=None)
        UserAccessProfile.objects.update_or_create(user=user, defaults=prof_defaults)
        messages.success(request, "Uživatel byl vytvořen.")
        return redirect("users:list")
    return render(
        request,
        "users/user_form.html",
        {"form": form, "page_title": "Nový uživatel", "is_edit": False, "preview_access": None},
    )


@admin_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = UserAdminEditForm(request.POST or None, instance=target, editor=request.user)
    if request.method == "POST" and form.is_valid():
        new_role = form.cleaned_data["role"]
        if target == request.user and new_role != ROLE_ADMIN:
            form.add_error("role", "Nemůžete sám sebe odebrat z role Admin.")
        else:
            form.save()
            set_user_role(target, new_role)
            existing_profile = UserAccessProfile.objects.filter(user=target.pk).first()
            prof_defaults = access_profile_defaults_for_save(form, existing_profile=existing_profile)
            UserAccessProfile.objects.update_or_create(user=target, defaults=prof_defaults)
            messages.success(request, "Uživatel byl uložen.")
            return redirect("users:list")
    preview_access = build_role_access_context(target)
    return render(
        request,
        "users/user_form.html",
        {
            "form": form,
            "page_title": "Upravit uživatele",
            "is_edit": True,
            "target_user": target,
            "preview_access": preview_access,
        },
    )


@admin_required
def sberny_dvur_subject_search(request):
    query = (request.GET.get("q") or "").strip()
    data = search_sberny_dvur_subjects(query)
    return JsonResponse({"ok": True, "data": data})


@admin_required
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if user == request.user:
            messages.error(request, "Nelze smazat právě přihlášeného uživatele.")
        else:
            try:
                user.delete()
            except ProtectedError:
                messages.error(
                    request,
                    "Uživatele nelze smazat z databáze: existují k němu navázané záznamy "
                    "(např. průvodky). Nejdřív tyto záznamy převeďte nebo odstraňte.",
                )
            else:
                messages.success(request, "Uživatel byl trvale odstraněn z databáze.")
        return redirect("users:list")
    return render(request, "users/user_confirm_delete.html", {"target_user": user})
