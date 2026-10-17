"""Validace kontejnerů u průvodky vůči číselníku pasportů a duplicitám mezi jízdami."""

from __future__ import annotations

from django.db.models import Q

from catalogs.models import ActivityFieldKey, ActivityFieldMode, ContainerPassport
from core.models import AppSettings
from waste_docs.activity_fields import get_effective_mode
from waste_docs.models import Pruvodka


def normalize_container_number(raw: str | None) -> str:
    return (raw or "").strip()


def passport_by_container_number(number: str) -> ContainerPassport | None:
    n = normalize_container_number(number)
    if not n:
        return None
    return (
        ContainerPassport.objects.filter(container_number__iexact=n)
        .select_related("vehicle_kind")
        .first()
    )


def passport_matches_vehicle_rz(
    passport: ContainerPassport | None,
    vehicle_rz,
    *,
    task_kind_id: int | None = None,
) -> bool:
    from catalogs.services.vehicle_kind_compatibility import passport_matches_vehicle_rz_compat

    return passport_matches_vehicle_rz_compat(
        passport,
        vehicle_rz,
        task_kind_id=task_kind_id,
    )


def _passport_matches_rz_for_kinds(
    passport: ContainerPassport | None,
    vehicle_rz,
    *,
    task_vehicle_kind_id: int | None,
    task_vehicle_kind_ids: list[int] | None,
) -> bool:
    if task_vehicle_kind_ids:
        return any(
            passport_matches_vehicle_rz(passport, vehicle_rz, task_kind_id=kid) for kid in task_vehicle_kind_ids
        )
    return passport_matches_vehicle_rz(passport, vehicle_rz, task_kind_id=task_vehicle_kind_id)


def _open_ride_exclude_pks(instance_pk: int | None) -> set[int]:
    """PK jízd, které se nemají počítat jako duplicita (editovaná + navazující řetězec)."""
    if not instance_pk:
        return set()
    try:
        pk = int(instance_pk)
    except (TypeError, ValueError):
        return set()
    exclude = {pk}
    row = (
        Pruvodka.objects.filter(pk=pk, is_archived=False)
        .values_list("follow_up_parent_id", flat=True)
        .first()
    )
    parent_id = row
    if parent_id:
        exclude.add(parent_id)
        exclude.update(
            Pruvodka.objects.filter(follow_up_parent_id=parent_id, is_archived=False).values_list("pk", flat=True)
        )
    exclude.update(
        Pruvodka.objects.filter(follow_up_parent_id=pk, is_archived=False).values_list("pk", flat=True)
    )
    return exclude


def _duplicate_ride_message(hit: Pruvodka, *, instance_pk: int | None) -> str:
    if instance_pk and hit.pk == int(instance_pk):
        return ""
    snd = (hit.snd_cislo_listu or "").strip()
    snd_part = f" (SND {snd})" if snd else ""
    return (
        f"Tento kontejner je již na jiné otevřené jízdě #{hit.pk}{snd_part}. "
        "Uzavřete nebo archivujte tu jízdu, nebo zadejte jiný kontejner."
    )


def open_ride_duplicate_message_for_container(number: str) -> str | None:
    """Vrátí chybovou hlášku, pokud číslo už je na jiné nearchivované jízdě."""
    n = normalize_container_number(number)
    if not n:
        return None

    qs_base = Pruvodka.objects.filter(is_archived=False)
    passport = passport_by_container_number(n)
    if passport:
        hit = qs_base.filter(container_passport_id=passport.pk).first()
        if hit:
            msg = _duplicate_ride_message(hit, instance_pk=None)
            if msg:
                return msg

    hit = qs_base.filter(Q(container_number__iexact=n) | Q(container_number_2__iexact=n)).first()
    if hit:
        return _duplicate_ride_message(hit, instance_pk=None)
    return None


def open_svoz_task_duplicate_message_for_container(
    number: str,
    *,
    subject_profile_id: int | None = None,
) -> str | None:
    """Vrátí chybovou hlášku, pokud číslo už je na otevřeném požadavku svozu."""
    from waste_docs.models import SvozTask

    n = normalize_container_number(number)
    if not n:
        return None
    qs = SvozTask.objects.filter(status=SvozTask.Status.OPEN, container_numbers__iexact=n)
    if subject_profile_id:
        qs = qs.filter(subject_profile_id=subject_profile_id)
    hit = qs.first()
    if not hit:
        return None
    return (
        f"Tento kontejner ({n}) je již na otevřeném požadavku svozu #{hit.pk}. "
        "Počkejte na vyřízení nebo zadejte jiný kontejner."
    )


def _duplicate_field_for_passport(
    *,
    pid: int,
    cp,
    num1: str,
    num2: str,
) -> str:
    if cp and cp.pk == pid:
        return "container_passport"
    if num2:
        p2 = passport_by_container_number(num2)
        if p2 and p2.pk == pid:
            return "container_number_2"
    return "container_number"


def _duplicate_field_for_number(
    *,
    n: str,
    cp,
    num1: str,
    num2: str,
) -> str:
    n_cf = n.casefold()
    if cp and normalize_container_number(cp.container_number).casefold() == n_cf:
        return "container_passport"
    if num1 and num1.casefold() == n_cf:
        return "container_number"
    if num2 and num2.casefold() == n_cf:
        return "container_number_2"
    return "container_number"


def _container_assignment_unchanged_on_edit(
    instance_pk: int | None,
    *,
    cp,
    num1: str,
    num2: str,
    c1_off: bool,
    c2_off: bool,
) -> bool:
    """Při editaci bez změny kontejneru neblokovat uložení kvůli starší duplicitě v DB."""
    if not instance_pk:
        return False
    try:
        pk = int(instance_pk)
    except (TypeError, ValueError):
        return False
    original = (
        Pruvodka.objects.filter(pk=pk)
        .values("container_passport_id", "container_number", "container_number_2")
        .first()
    )
    if not original:
        return False
    new_cp_id = cp.pk if cp else None
    if new_cp_id != original["container_passport_id"]:
        return False
    if not c1_off:
        orig_num1 = normalize_container_number(original.get("container_number"))
        if num1.casefold() != orig_num1.casefold():
            return False
    if not c2_off:
        orig_num2 = normalize_container_number(original.get("container_number_2"))
        if num2.casefold() != orig_num2.casefold():
            return False
    return True


def iter_container_passport_validation_errors(
    *,
    cleaned: dict,
    activity_id: int,
    vehicle_rz,
    instance_pk: int | None,
    task_vehicle_kind_id: int | None = None,
    task_vehicle_kind_ids: list[int] | None = None,
) -> list[tuple[str, str]]:
    """Vrací seznam (název pole, text chyby). Kontejnerová pole musí být v cleaned už podle režimu činnosti vyčištěná."""
    errors: list[tuple[str, str]] = []

    c1_off = get_effective_mode(activity_id, ActivityFieldKey.CONTAINER_1) == ActivityFieldMode.OFF
    c2_off = get_effective_mode(activity_id, ActivityFieldKey.CONTAINER_2) == ActivityFieldMode.OFF

    num1 = normalize_container_number(cleaned.get("container_number"))
    num2 = normalize_container_number(cleaned.get("container_number_2"))
    cp = cleaned.get("container_passport")

    if cp and num1 and num1.casefold() != normalize_container_number(cp.container_number).casefold():
        errors.append(
            (
                "container_number",
                "Číslo kontejneru (1) musí souhlasit s vybraným pasportem (jinak pole nechte prázdné).",
            )
        )

    if num1 and num2 and num1.casefold() == num2.casefold():
        errors.append(("container_number_2", "Číslo kontejneru (2) nesmí být stejné jako u kontejneru (1)."))

    unknown_msg = (
        "Toto číslo není v číselníku pasportů kontejnerů — založte pasport v Číselníky → Pasport kontejnerů "
        "nebo vyberte položku v poli Pasport kontejneru."
    )
    rz_msg = "Tento pasport (číslo) neodpovídá druhům vozidla u vybrané RZ."

    if not c1_off:
        if cp:
            if not _passport_matches_rz_for_kinds(
                cp,
                vehicle_rz,
                task_vehicle_kind_id=task_vehicle_kind_id,
                task_vehicle_kind_ids=task_vehicle_kind_ids,
            ):
                errors.append(("container_passport", rz_msg))
        elif num1:
            p1 = passport_by_container_number(num1)
            if not p1:
                errors.append(("container_number", unknown_msg))
            elif not _passport_matches_rz_for_kinds(
                p1,
                vehicle_rz,
                task_vehicle_kind_id=task_vehicle_kind_id,
                task_vehicle_kind_ids=task_vehicle_kind_ids,
            ):
                errors.append(("container_number", rz_msg))

    if not c2_off and num2:
        p2 = passport_by_container_number(num2)
        if not p2:
            errors.append(("container_number_2", unknown_msg))
        elif not _passport_matches_rz_for_kinds(
            p2,
            vehicle_rz,
            task_vehicle_kind_id=task_vehicle_kind_id,
            task_vehicle_kind_ids=task_vehicle_kind_ids,
        ):
            errors.append(("container_number_2", rz_msg))

    if errors:
        return errors

    if not AppSettings.load().enforce_container_passport_move_check:
        return errors

    if _container_assignment_unchanged_on_edit(
        instance_pk,
        cp=cp,
        num1=num1,
        num2=num2,
        c1_off=c1_off,
        c2_off=c2_off,
    ):
        return errors

    passport_ids: set[int] = set()
    numbers: set[str] = set()

    if cp:
        passport_ids.add(cp.pk)
        nn = normalize_container_number(cp.container_number)
        if nn:
            numbers.add(nn)

    if not c1_off and num1:
        p = passport_by_container_number(num1)
        if p:
            passport_ids.add(p.pk)
            numbers.add(num1)

    if not c2_off and num2:
        p2 = passport_by_container_number(num2)
        if p2:
            passport_ids.add(p2.pk)
            numbers.add(num2)

    exclude_pks = _open_ride_exclude_pks(instance_pk)
    qs_base = Pruvodka.objects.filter(is_archived=False)
    if exclude_pks:
        qs_base = qs_base.exclude(pk__in=exclude_pks)

    for pid in passport_ids:
        hit = qs_base.filter(container_passport_id=pid).first()
        if not hit or hit.pk in exclude_pks:
            continue
        msg = _duplicate_ride_message(hit, instance_pk=instance_pk)
        if not msg:
            continue
        errors.append(
            (
                _duplicate_field_for_passport(pid=pid, cp=cp, num1=num1, num2=num2),
                msg,
            )
        )
        return errors

    for n in numbers:
        if not n:
            continue
        hit = qs_base.filter(Q(container_number__iexact=n) | Q(container_number_2__iexact=n)).first()
        if not hit or hit.pk in exclude_pks:
            continue
        msg = _duplicate_ride_message(hit, instance_pk=instance_pk)
        if not msg:
            continue
        errors.append(
            (
                _duplicate_field_for_number(n=n, cp=cp, num1=num1, num2=num2),
                msg,
            )
        )
        return errors

    return errors
