"""Kontrola číselníku druhů vozidel a souladu s maticí / pasporty."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from catalogs.models import ContainerPassport, VehicleKindCatalog
from catalogs.models.name_subject import NameSubjectWasteSuffixPair
from catalogs.services.vehicle_kind_compatibility import compatible_kind_ids


class Command(BaseCommand):
    help = (
        "Zkontroluje druhy vozidel: podobné zkratky (H/3H/H3), duplicitu H vs 300_ATEGO, "
        "chybějící strom kompatibility a pasporty vs řádky matice."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Audit druhů vozidel ===\n"))

        kinds = list(VehicleKindCatalog.objects.select_related("parent_kind").order_by("sort_order", "pk"))
        by_short = {k.shortcut.strip().upper(): k for k in kinds if k.shortcut}

        self._check_confusing_shortcuts(by_short)
        self._check_h_vs_atego(by_short)
        self._check_missing_names(kinds)
        self._check_tree_h_3h(by_short)
        self._check_matrix_passport_mismatch()
        self._print_data_guidance()

    def _check_confusing_shortcuts(self, by_short: dict) -> None:
        self.stdout.write(self.style.WARNING("\n— Zkratky snadno zaměnitelné —"))
        for sc in sorted(by_short):
            if sc in ("H3", "3H", "H"):
                k = by_short[sc]
                self.stdout.write(f"  {k.display_label()} (pk={k.pk})")
        if "H" in by_short and "3H" in by_short:
            h, three = by_short["H"], by_short["3H"]
            if three.parent_kind_id != h.pk:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Doporučení: nastavte u {three.display_label()} nadřazený {h.display_label()} "
                        f"(Číselníky → Druhy vozidel → upravit H → užší požadavky)."
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"  OK: {three.display_label()} je pod {h.display_label()}"))

    def _check_h_vs_atego(self, by_short: dict) -> None:
        self.stdout.write(self.style.WARNING("\n— H vs 300_ATEGO (import VOK / Atego) —"))
        h = by_short.get("H")
        atego = by_short.get("300_ATEGO")
        if h and atego:
            self.stdout.write(
                f"  V DB jsou oba: {h.display_label()} a {atego.display_label()}. "
                "Zvažte sloučení zkratky nebo parent_kind mezi nimi, pokud jde o stejný provoz."
            )
        elif h:
            self.stdout.write(f"  Pouze {h.display_label()} — import VOK může mapovat Atego na H.")
        elif atego:
            self.stdout.write(f"  Pouze {atego.display_label()} — doplnit zkratku H pro matici?")

    def _check_missing_names(self, kinds: list) -> None:
        self.stdout.write(self.style.WARNING("\n— Názvy vs zkratky —"))
        for k in kinds:
            name = (k.name or "").strip()
            sc = (k.shortcut or "").strip()
            if not name or name.upper() == sc.upper() or len(name) <= 2:
                self.stdout.write(
                    f"  Doplňte srozumitelný název u zkratky {sc!r} (pk={k.pk}), např. Hák, Tří nápravové."
                )

    def _check_tree_h_3h(self, by_short: dict) -> None:
        if "H" not in by_short or "3H" not in by_short:
            return
        self.stdout.write(self.style.WARNING("\n— Kompatibilita H <-> 3H —"))
        h_id, three_id = by_short["H"].pk, by_short["3H"].pk
        compat_from_h = compatible_kind_ids(h_id)
        if three_id in compat_from_h:
            self.stdout.write(self.style.SUCCESS("  RZ/pasport s druhem H může obsloužit úkol 3H."))
        else:
            self.stdout.write(self.style.ERROR("  3H není v kompatibilní množině H — nastavte strom v číselníku."))

    def _check_matrix_passport_mismatch(self) -> None:
        self.stdout.write(self.style.WARNING("\n— Matice (yard_vehicle_kind) vs pasporty —"))
        matrix_kinds = set(
            NameSubjectWasteSuffixPair.objects.filter(
                yard_svoz_enabled=True,
                yard_vehicle_kind_id__isnull=False,
            ).values_list("yard_vehicle_kind_id", flat=True)
        )
        issues = 0
        three_h = VehicleKindCatalog.objects.filter(shortcut__iexact="3H").first()
        hook = VehicleKindCatalog.objects.filter(shortcut__iexact="H").first()
        if three_h and three_h.pk in matrix_kinds and hook:
            compat = compatible_kind_ids(three_h.pk)
            if hook.pk not in compat:
                sample = list(
                    ContainerPassport.objects.filter(vehicle_kind_id=hook.pk).values_list(
                        "container_number", flat=True
                    )[:5]
                )
                issues += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  Matice pouziva {three_h.display_label()}, ale pasporty s {hook.display_label()} "
                        f"nebudou sedet bez stromu 3H pod H. Vzorek cisel: {', '.join(sample) or '—'}"
                    )
                )
        if issues == 0:
            self.stdout.write(self.style.SUCCESS("  Kontrola pasport H vs matice 3H: OK nebo matice 3H nepouziva."))

    def _print_data_guidance(self) -> None:
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n=== Doporucene kroky po nasazeni ===\n"
                "1. U zkratky H nastavte nazev Hák.\n"
                "2. U zkratky 3H nazev Tri napravove (3H) a podradte pod H (uzsi pozadavky).\n"
                "3. Pasporty haku (napr. 614 Textil) -> druh vozidla Hák (H).\n"
                "4. Restart aplikace po deployi kodu.\n"
            )
        )
