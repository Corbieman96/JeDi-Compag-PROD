"""
Jednorázová údržba: přečísluje SND pole v DB stejně jako Pruvodka.save()
(skupina = pořadí jízdy v kalendářním roce, ride_sequence = pořadí v daný den pro danou RZ).
"""

from __future__ import annotations

from collections import defaultdict

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from waste_docs.activity_fields import activity_generates_snd, activity_generates_zpo
from waste_docs.models import Pruvodka
from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk


class Command(BaseCommand):
    help = (
        "Jednorázová údržba: přečísluje ride_group_number, ride_sequence a snd_cislo_listu. "
        "Na běžící produkci nespouštět — čísla jízd jsou po přidělení neměnná. "
        "Zápis vyžaduje --force-rewrite."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen vypíše souhrn, databáze se neupraví.",
        )
        parser.add_argument(
            "--force-rewrite",
            action="store_true",
            help="Povinné pro zápis do DB — hromadně přepíše neměnná čísla jízd (jen jednorázová údržba).",
        )
        parser.add_argument(
            "--skip-zpo",
            action="store_true",
            help="Negeneruje ZPO po změně čísel (soubory mohou dál obsahovat staré SND).",
        )
        parser.add_argument(
            "--no-reset-ineligible",
            action="store_true",
            help="Neresetuje průvodky bez SND (chybí RZ nebo činnost má SND vypnuté).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        force_rewrite: bool = options["force_rewrite"]
        skip_zpo: bool = options["skip_zpo"]
        no_reset_ineligible: bool = options["no_reset_ineligible"]

        if not dry_run and not force_rewrite:
            self.stderr.write(
                self.style.ERROR(
                    "Zápis do databáze je zakázán bez --force-rewrite. "
                    "Čísla jízd (SND) jsou po přidělení neměnná — příkaz použij jen jako jednorázovou opravu dat. "
                    "Pro náhled změn použij --dry-run."
                )
            )
            return

        rows = list(Pruvodka.objects.all().order_by("pk"))
        if not rows:
            self.stdout.write("Žádné průvodky v databázi.")
            return

        activity_ids = {p.activity_id for p in rows}
        snd_on = {aid: activity_generates_snd(aid) for aid in activity_ids}
        zpo_on = {aid: activity_generates_zpo(aid) for aid in activity_ids}

        eligible = [p for p in rows if snd_on.get(p.activity_id) and p.vehicle_rz_id]
        eligible.sort(key=lambda p: (p.drive_date.year, p.drive_date, p.created_at, p.pk))
        eligible_pks = {p.pk for p in eligible}

        planned: dict[int, dict[str, object]] = {}
        by_year: dict[int, list[Pruvodka]] = defaultdict(list)
        for p in eligible:
            by_year[p.drive_date.year].append(p)

        for year in sorted(by_year.keys()):
            year_rows = by_year[year]
            group_by_pk: dict[int, int] = {}
            for idx, p in enumerate(year_rows, start=1):
                group_by_pk[p.pk] = idx

            # Pořadí -1,-2,… v rámci dne podle čísla skupiny; při změně RZ oproti předchozímu řádku znovu od 1
            # (stejný vůz po mezikladu s jiným autem zase začíná -1).
            for d in sorted({p.drive_date for p in year_rows}):
                day_rows = [p for p in year_rows if p.drive_date == d]
                day_rows.sort(key=lambda x: (group_by_pk[x.pk], x.pk))
                last_rz = None
                seq_val = 0
                for p in day_rows:
                    rid = p.vehicle_rz_id
                    if last_rz is None or rid != last_rz:
                        seq_val = 1
                        last_rz = rid
                    else:
                        seq_val += 1
                    g = group_by_pk[p.pk]
                    planned[p.pk] = {
                        "ride_group_number": g,
                        "ride_sequence": seq_val,
                        "snd_cislo_listu": Pruvodka._format_snd(g, year, seq_val),
                    }

        ineligible_zpo_clear: set[int] = set()
        if not no_reset_ineligible:
            for p in rows:
                if p.pk in eligible_pks:
                    continue
                needs = (
                    p.ride_group_number != 0
                    or bool((p.snd_cislo_listu or "").strip())
                    or p.ride_sequence != 1
                )
                if not needs:
                    continue
                planned[p.pk] = {
                    "ride_group_number": 0,
                    "ride_sequence": 1,
                    "snd_cislo_listu": "",
                }
                if p.zpo_instance_file and p.zpo_instance_file.name:
                    ineligible_zpo_clear.add(p.pk)

        pk_to_row = {p.pk: p for p in rows}
        changed_eligible = 0
        changed_ineligible = 0
        sample: list[str] = []

        for pk, newvals in planned.items():
            p = pk_to_row[pk]
            new_snd = str(newvals["snd_cislo_listu"])
            new_g = int(newvals["ride_group_number"])
            new_s = int(newvals["ride_sequence"])
            if (
                p.ride_group_number == new_g
                and p.ride_sequence == new_s
                and (p.snd_cislo_listu or "") == new_snd
                and pk not in ineligible_zpo_clear
            ):
                continue
            if pk in eligible_pks:
                changed_eligible += 1
            else:
                changed_ineligible += 1
            if len(sample) < 15:
                sample.append(
                    f"  pk={pk}: "
                    f"{p.snd_cislo_listu!r} -> {new_snd!r} "
                    f"(group {p.ride_group_number}->{new_g}, seq {p.ride_sequence}->{new_s})"
                )

        self.stdout.write(
            f"Způsobilých průvodek (SND): {len(eligible)}, "
            f"změn v přiřazení: {changed_eligible} eligible, {changed_ineligible} reset ne-SND."
        )
        if sample:
            self.stdout.write("Ukázka změn:")
            for line in sample:
                self.stdout.write(line)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run — databáze beze změny."))
            if not skip_zpo and changed_eligible:
                self.stdout.write(
                    f"Bez --dry-run by se po zápisu přegenerovalo až {changed_eligible} ZPO "
                    f"(u činností s povoleným ZPO)."
                )
            return

        batch_eligible: list[Pruvodka] = []
        batch_ineligible: list[Pruvodka] = []

        for pk, newvals in planned.items():
            p = pk_to_row[pk]
            new_snd = str(newvals["snd_cislo_listu"])
            new_g = int(newvals["ride_group_number"])
            new_s = int(newvals["ride_sequence"])
            if (
                p.ride_group_number == new_g
                and p.ride_sequence == new_s
                and (p.snd_cislo_listu or "") == new_snd
                and pk not in ineligible_zpo_clear
            ):
                continue

            p.ride_group_number = new_g
            p.ride_sequence = new_s
            p.snd_cislo_listu = new_snd

            if pk in ineligible_zpo_clear:
                if p.zpo_instance_file and p.zpo_instance_file.name:
                    try:
                        default_storage.delete(p.zpo_instance_file.name)
                    except Exception as exc:
                        self.stderr.write(f"Varování: smazání ZPO {p.zpo_instance_file.name}: {exc}")
                p.zpo_instance_file = None
                p.zpo_instance_for_snd = ""
                p.zpo_generator_revision = 0
                batch_ineligible.append(p)
            else:
                batch_eligible.append(p)

        with transaction.atomic():
            if batch_eligible:
                Pruvodka.objects.bulk_update(
                    batch_eligible,
                    ["ride_group_number", "ride_sequence", "snd_cislo_listu"],
                )
            if batch_ineligible:
                Pruvodka.objects.bulk_update(
                    batch_ineligible,
                    [
                        "ride_group_number",
                        "ride_sequence",
                        "snd_cislo_listu",
                        "zpo_instance_file",
                        "zpo_instance_for_snd",
                        "zpo_generator_revision",
                    ],
                )

        self.stdout.write(self.style.SUCCESS("Hotovo — hodnoty v databázi aktualizovány."))

        if skip_zpo:
            if changed_eligible:
                self.stdout.write(
                    self.style.WARNING(
                        "Přeskočeno přegenerování ZPO (--skip-zpo). "
                        "Spusť příkaz znovu bez této volby, nebo otevři průvodky v aplikaci."
                    )
                )
            return

        zpo_count = 0
        for pk in sorted(eligible_pks):
            if not zpo_on.get(pk_to_row[pk].activity_id):
                continue
            ensure_zpo_instance_for_pruvodka_pk(pk)
            zpo_count += 1
        if zpo_count:
            self.stdout.write(f"Přegenerováno / ověřeno ZPO u {zpo_count} průvodek (s povoleným ZPO).")
