"""Hledání existující práce pro řádek matice sběrného dvora — deduplikace na cílový den."""



from __future__ import annotations



from datetime import date, datetime



from django.db.models import Q

from django.utils import timezone



from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair

from waste_docs.models import Pruvodka, SvozTask

from waste_docs.services.container_passport_ride_validation import normalize_container_number





def dates_for_yard_submit(*, target_date: date, now: datetime | None = None) -> list[date]:
    """Dny ke kontrole — jen cílový den (existující jízdy neblokují nové hlášení)."""
    return [target_date]





def find_open_svoz_task_for_line(

    *,

    subject_profile_id: int,

    pair_id: int,

    container_number: str,

    target_date: date,

) -> SvozTask | None:

    number = normalize_container_number(container_number)

    if not number:

        return None

    return (

        SvozTask.objects.filter(

            subject_profile_id=subject_profile_id,

            source_waste_suffix_pair_id=pair_id,

            target_date=target_date,

            status=SvozTask.Status.OPEN,

            resolved_pruvodka__isnull=True,

            container_numbers__iexact=number,

        )

        .order_by("created_at", "pk")

        .first()

    )





def find_open_svoz_task_for_yard_container(

    *,

    subject_profile_id: int,

    container_number: str,

    target_date: date,

) -> SvozTask | None:

    """Otevřený úkol se stejným kontejnerem u subjektu (bez ohledu na řádek matice)."""

    number = normalize_container_number(container_number)

    if not number:

        return None

    return (

        SvozTask.objects.filter(

            subject_profile_id=subject_profile_id,

            target_date=target_date,

            status=SvozTask.Status.OPEN,

            resolved_pruvodka__isnull=True,

            container_numbers__iexact=number,

        )

        .order_by("created_at", "pk")

        .first()

    )





def _container_match_q(number: str) -> Q:

    return (

        Q(container_number__iexact=number)

        | Q(container_number_2__iexact=number)

        | Q(container_passport__container_number__iexact=number)

    )





def find_active_pruvodka_for_yard_line(

    *,

    subject_profile: NameSubjectProfile,

    pair: NameSubjectWasteSuffixPair,

    container_number: str,

    target_date: date,

) -> Pruvodka | None:

    number = normalize_container_number(container_number)

    if not number or not subject_profile.name_id:

        return None

    return (

        Pruvodka.objects.filter(

            is_archived=False,

            drive_date=target_date,

            name_id=subject_profile.name_id,

            waste_type_id=pair.waste_type_id,

            suffix_id=pair.suffix_id,

        )

        .filter(_container_match_q(number))

        .order_by("pk")

        .first()

    )





def find_active_pruvodka_for_yard_container(

    *,

    subject_profile: NameSubjectProfile,

    container_number: str,

    drive_date: date,

) -> Pruvodka | None:

    """Aktivní jízda se stejným kontejnerem u subjektu (bez ohledu na odpad/koncovku)."""

    number = normalize_container_number(container_number)

    if not number or not subject_profile.name_id:

        return None

    return (

        Pruvodka.objects.filter(

            is_archived=False,

            drive_date=drive_date,

            name_id=subject_profile.name_id,

        )

        .filter(_container_match_q(number))

        .order_by("pk")

        .first()

    )





def yard_container_ride_exists_on_dates(

    *,

    subject_profile: NameSubjectProfile,

    container_number: str,

    dates: list[date],

) -> Pruvodka | None:

    """Aktivní jízda kontejneru u subjektu na kterýkoli z daných dnů."""

    seen: set[date] = set()

    for day in dates:

        if day in seen:

            continue

        seen.add(day)

        ride = find_active_pruvodka_for_yard_container(

            subject_profile=subject_profile,

            container_number=container_number,

            drive_date=day,

        )

        if ride is not None:

            return ride

    return None





def yard_container_open_task_on_dates(
    *,
    subject_profile_id: int,
    container_number: str,
    dates: list[date],
    exclude_svoz_task_id: int | None = None,
) -> SvozTask | None:
    """OPEN úkol v panelu — blokuje nové hlášení stejného kontejneru."""
    seen: set[date] = set()
    for day in dates:
        if day in seen:
            continue
        seen.add(day)
        task = find_open_svoz_task_for_yard_container(
            subject_profile_id=subject_profile_id,
            container_number=container_number,
            target_date=day,
        )
        if task is not None and (exclude_svoz_task_id is None or task.pk != exclude_svoz_task_id):
            return task
    return None


def yard_container_already_scheduled_on_dates(
    *,
    subject_profile: NameSubjectProfile,
    container_number: str,
    dates: list[date],
    exclude_svoz_task_id: int | None = None,
) -> SvozTask | None:
    """OPEN úkol kontejneru u subjektu na cílový den — jízdy se nekontrolují."""
    return yard_container_open_task_on_dates(
        subject_profile_id=subject_profile.pk,
        container_number=container_number,
        dates=dates,
        exclude_svoz_task_id=exclude_svoz_task_id,
    )





def yard_line_already_scheduled(
    *,
    subject_profile: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    container_number: str,
    target_date: date,
) -> SvozTask | None:
    """OPEN úkol na cílový den — nové hlášení se nezakládá."""
    return yard_line_already_scheduled_on_dates(
        subject_profile=subject_profile,
        pair=pair,
        container_number=container_number,
        dates=[target_date],
    )


def yard_line_already_scheduled_on_dates(
    *,
    subject_profile: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    container_number: str,
    dates: list[date],
) -> SvozTask | None:
    """OPEN úkol na cílový den — existující jízda neblokuje."""
    return yard_container_already_scheduled_on_dates(
        subject_profile=subject_profile,
        container_number=container_number,
        dates=dates,
    )


def find_done_svoz_task_for_yard_container(
    *,
    subject_profile_id: int,
    container_number: str,
    target_date: date,
) -> SvozTask | None:
    """Vyřízený úkol se stejným kontejnerem a propojenou průvodkou."""
    number = normalize_container_number(container_number)
    if not number:
        return None
    return (
        SvozTask.objects.filter(
            subject_profile_id=subject_profile_id,
            target_date=target_date,
            status=SvozTask.Status.DONE,
            resolved_pruvodka__isnull=False,
            container_numbers__iexact=number,
        )
        .order_by("created_at", "pk")
        .first()
    )


def yard_container_already_fulfilled_on_target(
    *,
    subject_profile: NameSubjectProfile,
    container_number: str,
    target_date: date,
) -> bool:
    """
    True pokud pro subjekt + kontejner + cílový den už existuje práce
    (aktivní jízda, OPEN úkol nebo DONE úkol s průvodkou).
    """
    if find_active_pruvodka_for_yard_container(
        subject_profile=subject_profile,
        container_number=container_number,
        drive_date=target_date,
    ):
        return True
    if find_open_svoz_task_for_yard_container(
        subject_profile_id=subject_profile.pk,
        container_number=container_number,
        target_date=target_date,
    ):
        return True
    if find_done_svoz_task_for_yard_container(
        subject_profile_id=subject_profile.pk,
        container_number=container_number,
        target_date=target_date,
    ):
        return True
    return False


__all__ = [
    "dates_for_yard_submit",
    "find_active_pruvodka_for_yard_container",
    "find_active_pruvodka_for_yard_line",
    "find_done_svoz_task_for_yard_container",
    "find_open_svoz_task_for_line",
    "find_open_svoz_task_for_yard_container",
    "yard_container_already_fulfilled_on_target",
    "yard_container_already_scheduled_on_dates",
    "yard_container_open_task_on_dates",
    "yard_container_ride_exists_on_dates",
    "yard_line_already_scheduled",
    "yard_line_already_scheduled_on_dates",
]

