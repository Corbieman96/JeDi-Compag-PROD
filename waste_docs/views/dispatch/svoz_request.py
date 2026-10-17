"""Sběrný dvůr — hlášení (požadavek na svoz): matice kontejnerů → SvozTask pro dispečera."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from catalogs.models import NameSubjectProfile
from users.services.sberny_dvur import can_create_svoz_request, get_sberny_dvur_subject
from waste_docs.services.svoz_dispatch.yard_day_reminder import (
    create_day_reminder_for_svoz_task,
    create_unknown_passport_day_reminder,
    should_create_yard_dispatch_note,
)
from waste_docs.services.yard_hazard_request import (
    is_hazardous_matrix_pair,
    submit_hazard_line_if_allowed,
)
from waste_docs.services.svoz_matrix_post_collect import collect_pending_svoz_matrix_lines
from waste_docs.services.container_passport_ride_validation import normalize_container_number
from waste_docs.services.svoz_task_submit import submit_svoz_line_if_allowed
from waste_docs.services.svoz_request_daily_limit import (
    is_svoz_yard_daily_submit_limit_disabled,
    svoz_subject_has_submitted_today,
)
from waste_docs.services.svoz_matrix_submit_error_log import (
    acknowledge_unread_for_subject,
    record_error_messages,
    record_matrix_open,
    rows_for_subject,
)
from waste_docs.services.svoz_matrix_submit_error_log.query import display_row
from waste_docs.services.yard_svoz_submission_log import (
    record_submission_log_line,
    yard_svoz_submissions_grouped,
)
from waste_docs.services.yard_svoz_submission_result import (
    result_summary_for_hazard,
    result_summary_for_svoz_task,
)
from waste_docs.svoz_schedule import svoz_target_date_for_matrix_submit
from waste_docs.yard_matrix import yard_svoz_matrix_rows, yard_svoz_matrix_stats


@login_required
def svoz_request_create(request):
    if not can_create_svoz_request(request.user):
        raise Http404("Požadavek na svoz není pro tento účet k dispozici.")
    subject = get_sberny_dvur_subject(request.user)
    if not subject:
        raise Http404("Chybí přiřazený subjekt sběrného dvora.")
    if not subject.yard_allow_matrix:
        messages.warning(request, "U tohoto subjektu není povolena matice požadavků sběrného dvora.")
        return redirect(reverse("waste_docs:yard_hub"))

    rows = yard_svoz_matrix_rows(subject)
    matrix_stats = yard_svoz_matrix_stats(subject)
    target = svoz_target_date_for_matrix_submit()
    errors: list[str] = []

    def _render():
        already_submitted = svoz_subject_has_submitted_today(subject_profile_id=subject.pk)
        submission_groups = yard_svoz_submissions_grouped(subject_profile_id=subject.pk)
        error_entries = rows_for_subject(subject_profile_id=subject.pk)
        return render(
            request,
            "waste_docs/svoz_request_matrix.html",
            {
                "subject": subject,
                "rows": rows,
                "matrix_stats": matrix_stats,
                "next_target_hint": target,
                "errors": errors,
                "already_submitted_today": already_submitted,
                "yard_daily_limit_disabled": is_svoz_yard_daily_submit_limit_disabled(),
                "submission_today": submission_groups["today"],
                "submission_history_by_day": submission_groups["history_by_day"],
                "history_total_count": submission_groups["history_total_count"],
                "submit_error_log_rows": [display_row(e) for e in error_entries],
            },
        )

    if request.method != "POST":
        already_submitted = svoz_subject_has_submitted_today(subject_profile_id=subject.pk)
        record_matrix_open(
            subject=subject,
            user=request.user,
            already_submitted_today=already_submitted,
        )
        return _render()

    if svoz_subject_has_submitted_today(subject_profile_id=subject.pk):
        errors.append(
            "Dnes jste již odeslali hlášení ze sběrného dvora. Další odeslání až zítra."
        )
        record_error_messages(subject=subject, user=request.user, messages=errors)
        return _render()

    posted_pks = request.POST.getlist("pair_pk")
    pending_lines, validation_errors = collect_pending_svoz_matrix_lines(
        posted_pks, request.POST, subject, target,
    )

    if validation_errors:
        errors.extend(validation_errors)
        record_error_messages(subject=subject, user=request.user, messages=errors)
        return _render()

    if not pending_lines:
        errors.append("Vyplňte alespoň u jednoho řádku číslo kontejneru.")
        record_error_messages(subject=subject, user=request.user, messages=errors)
        return _render()

    created = 0
    hazard_created = 0
    ride_warnings: list[str] = []
    pairs_reminded: set[int] = set()
    seen_containers: set[str] = set()
    skip_messages: list[str] = []
    with transaction.atomic():
        NameSubjectProfile.objects.select_for_update().get(pk=subject.pk)

        for pline in pending_lines:
            container_key = normalize_container_number(pline.container_numbers or "")
            if container_key and container_key in seen_containers:
                skip_messages.append(
                    f"{pline.matrix_display_label or 'Řádek'}: kontejner {pline.container_numbers} "
                    "přeskočen — v tomto hlášení je zadaný vícekrát."
                )
                continue
            if container_key:
                seen_containers.add(container_key)

            pair = pline.pair
            if is_hazardous_matrix_pair(pair):
                result = submit_hazard_line_if_allowed(pline, subject, request.user)
                if result.created:
                    record_submission_log_line(
                        pline=pline,
                        subject=subject,
                        user=request.user,
                        is_hazardous=True,
                        result_summary=result_summary_for_hazard(),
                    )
                    hazard_created += 1
                else:
                    skip_messages.append(
                        f"{pline.matrix_display_label or 'Řádek'}: kontejner {pline.container_numbers} "
                        "přeskočen — nebezpečný odpad už je ve frontě."
                    )
                continue

            result = submit_svoz_line_if_allowed(pline, subject, request.user, target)
            if not result.created:
                skip_messages.append(
                    f"{pline.matrix_display_label or 'Řádek'}: kontejner {pline.container_numbers} "
                    "přeskočen — už má požadavek nebo jízdu."
                )
                continue
            record_submission_log_line(
                pline=pline,
                subject=subject,
                user=request.user,
                is_hazardous=False,
                target_date=target,
                result_summary=result_summary_for_svoz_task(
                    task=result.task,
                    ride_warning=result.ride_warning,
                ),
            )
            task = result.task
            if result.ride_warning:
                ride_warnings.append(result.ride_warning)
            if getattr(pline, "claimed_unknown_container", ""):
                create_unknown_passport_day_reminder(
                    task=task,
                    pair=pair,
                    created_by=request.user,
                    claimed_number=pline.claimed_unknown_container,
                )
            if should_create_yard_dispatch_note(pair) and pair.pk not in pairs_reminded:
                create_day_reminder_for_svoz_task(
                    task=task, pair=pair, created_by=request.user,
                )
                pairs_reminded.add(pair.pk)
            created += 1

    if skip_messages:
        record_error_messages(subject=subject, user=request.user, messages=skip_messages)

    if created or hazard_created:
        acknowledge_unread_for_subject(
            subject_profile_id=subject.pk,
            user=request.user,
        )
        parts: list[str] = []
        if created:
            parts.append(
                f"{created} požadavků na svoz ({target.strftime('%d.%m.%Y')})"
            )
        if hazard_created:
            parts.append(f"{hazard_created} nebezpečných odpadů do fronty dispečera")
        messages.success(
            request,
            "Odesláno: " + ", ".join(parts) + ". Dispečer je uvidí na dashboardu.",
        )
        for w in ride_warnings[:5]:
            messages.warning(request, w)
        if len(ride_warnings) > 5:
            messages.warning(request, f"… a dalších {len(ride_warnings) - 5} upozornění k auto-založení jízdy.")
        for sm in skip_messages[:8]:
            messages.warning(request, sm)
        if len(skip_messages) > 8:
            messages.warning(request, f"… a dalších {len(skip_messages) - 8} přeskočených řádků (viz Log SD).")
        return redirect(reverse("waste_docs:svoz_request"))

    if pending_lines:
        # Všechny řádky přeskočeny — dříve tichý redirect; teď jasná hláška (+ už v Log SD).
        if skip_messages:
            errors.extend(skip_messages)
            return _render()
        messages.warning(
            request,
            "Nic se neodeslalo — vybrané řádky už mají požadavek nebo jízdu.",
        )
        record_error_messages(
            subject=subject,
            user=request.user,
            messages=["Nic se neodeslalo — vybrané řádky už mají požadavek nebo jízdu."],
        )
        return redirect(reverse("waste_docs:svoz_request"))

    return _render()
