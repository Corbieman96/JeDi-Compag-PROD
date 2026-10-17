from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from waste_docs.forms import SvozTaskQuickEditForm
from waste_docs.models import SvozTask
from waste_docs.services.svoz_task_auto_pruvodka import try_create_pruvodka_for_assigned_svoz_task
from waste_docs.services.svoz_task_permissions import can_user_quick_edit_svoz_task


@login_required
@require_POST
def svoz_task_quick_edit(request, pk: int):
    task = get_object_or_404(SvozTask, pk=pk)
    if not can_user_quick_edit_svoz_task(request.user, task):
        return HttpResponseForbidden("Úprava tohoto požadavku není povolena.")

    form = SvozTaskQuickEditForm(request.POST, instance=task)
    redirect_date = task.target_date
    prev_driver_id = task.assigned_driver_id
    if form.is_valid():
        form.save()
        task.refresh_from_db()
        redirect_date = task.target_date
        auto_ok = False
        auto_err = None
        if (
            task.status == SvozTask.Status.OPEN
            and not task.resolved_pruvodka_id
            and task.assigned_driver_id
            and task.assigned_driver_id != prev_driver_id
        ):
            auto_ok, auto_err = try_create_pruvodka_for_assigned_svoz_task(task, request.user)
        if auto_ok:
            messages.success(
                request,
                "Požadavek byl vyřízen: založena jízda a odebrán z fronty na dashboardu.",
            )
        elif auto_err:
            messages.warning(
                request,
                f"Řidič byl uložen, ale jízdu se nepodařilo založit automaticky ({auto_err}). "
                "Doplňte údaje nebo založte jízdu odkazem u řádku.",
            )
        else:
            messages.success(request, "Požadavek na svoz byl uložen.")
    else:
        messages.error(request, "Údaje se nepodařilo uložit. Zkontrolujte vyplnění.")

    return redirect(reverse("core:dashboard") + f"?date={redirect_date.isoformat()}")
