from __future__ import annotations

from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_generated_files import (
    count_rides_missing_excel,
    ensure_excel_files_for_rides,
    rides_missing_excel,
)
from waste_docs.services.pruvodka_pair_docs import pair_docs_for_pruvodka
from waste_docs.services.zpo_instance_staleness import zpo_instance_needs_regeneration
from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk
from waste_docs.zpo_policy import system_may_generate_zpo_instance
from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka, effective_zpo_file


def _eligible_zpo_rides(rides: list[Pruvodka]) -> list[Pruvodka]:
    """Jízdy, u kterých smí systém generovat ZPO (činnost, SND, šablona v číselníku)."""
    eligible: list[Pruvodka] = []
    for ride in rides:
        if not system_may_generate_zpo_instance(ride):
            continue
        if not (ride.snd_cislo_listu or "").strip():
            continue
        pair_docs = pair_docs_for_pruvodka(ride)
        if not effective_zpo_file(pair_docs):
            continue
        eligible.append(ride)
    return eligible


def ride_needs_zpo_prepare(ride: Pruvodka, pair_docs=None) -> bool:
    """True pokud chybí instance ZPO nebo je zastaralá (SND, revize generátoru, soubor na disku)."""
    return zpo_instance_needs_regeneration(ride, pair=pair_docs)


def rides_missing_zpo(rides: list[Pruvodka]) -> list[Pruvodka]:
    return [ride for ride in rides if ride_needs_zpo_prepare(ride)]


def count_rides_missing_zpo(rides: list[Pruvodka]) -> int:
    return len(rides_missing_zpo(rides))


def prepare_progress_label(*, missing_excel_count: int, missing_zpo_count: int) -> str:
    if missing_excel_count and missing_zpo_count:
        return "Připravuji soubory k tisku…"
    if missing_excel_count:
        return "Generuji Excel průvodky…"
    if missing_zpo_count:
        return "Generuji ZPO…"
    return "Připravuji soubory k tisku…"


def print_prepare_context(rides: list[Pruvodka], *, include_zpo: bool = True) -> dict[str, object]:
    missing_excel_count = count_rides_missing_excel(rides)
    missing_zpo_count = count_rides_missing_zpo(rides) if include_zpo else 0
    needs_print_prepare = missing_excel_count > 0 or missing_zpo_count > 0
    label = prepare_progress_label(
        missing_excel_count=missing_excel_count,
        missing_zpo_count=missing_zpo_count,
    )
    return {
        "needs_print_prepare": needs_print_prepare,
        "missing_excel_count": missing_excel_count,
        "missing_zpo_count": missing_zpo_count,
        "prepare_progress_label": label,
    }


def ensure_zpo_files_for_rides(rides: list[Pruvodka]) -> tuple[int, list[str]]:
    generated_count = 0
    warnings: list[str] = []
    needs_prepare_pks = {ride.pk for ride in rides_missing_zpo(rides)}
    for ride in _eligible_zpo_rides(rides):
        was_missing = ride.pk in needs_prepare_pks
        ensure_zpo_instance_for_pruvodka_pk(ride.pk)
        ride.refresh_from_db()
        pair_docs = pair_docs_for_pruvodka(ride)
        if display_zpo_file_for_pruvodka(ride, pair_docs):
            if was_missing:
                generated_count += 1
            continue
        snd = (ride.snd_cislo_listu or "").strip()
        if snd:
            warnings.append(f"#{ride.pk} ({snd})")
    return generated_count, warnings


def prepare_print_bundle_files(
    rides: list[Pruvodka],
    *,
    include_zpo: bool = True,
) -> dict[str, object]:
    excel_generated = ensure_excel_files_for_rides(rides)
    zpo_generated = 0
    zpo_warnings: list[str] = []
    if include_zpo:
        zpo_generated, zpo_warnings = ensure_zpo_files_for_rides(rides)
    return {
        "excel_generated": excel_generated,
        "zpo_generated": zpo_generated,
        "zpo_warnings": zpo_warnings,
    }
