"""Diagnostika řádku matice (odpad–koncovka) u jedné jízdy."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_source_pair_diagnosis import (
    diagnose_pruvodka_source_pair,
    sync_pruvodka_source_pair,
)

_PRUVODKA_SELECT = (
    "activity",
    "name",
    "waste_type",
    "suffix",
    "vehicle_rz",
    "vehicle_rz__profile",
    "container_passport",
    "container_passport__vehicle_kind",
    "source_waste_suffix_pair",
)


class Command(BaseCommand):
    help = (
        "Vypíše stav řádku matice u jízdy (uložený FK, resolver, kandidáti). "
        "S --fix doplní nebo opraví source_waste_suffix_pair."
    )

    def add_arguments(self, parser):
        parser.add_argument("pk", type=int, help="Primární klíč jízdy (Pruvodka.pk)")
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Zapsat doporučený řádek matice do source_waste_suffix_pair",
        )

    def handle(self, *args, **options):
        pk = options["pk"]
        try:
            item = Pruvodka.objects.select_related(*_PRUVODKA_SELECT).get(pk=pk)
        except Pruvodka.DoesNotExist as exc:
            raise CommandError(f"Jízda #{pk} neexistuje.") from exc

        diag = diagnose_pruvodka_source_pair(item)

        self.stdout.write(self.style.NOTICE(f"Diagnostika páru matice — jízda #{pk}"))
        self.stdout.write(f"  SND: {(item.snd_cislo_listu or '').strip() or '—'}")
        self.stdout.write(
            f"  Subjekt: {item.name_snapshot or getattr(item.name, 'value', None) or item.name_id or '—'}"
        )
        self.stdout.write(
            f"  Odpad: {item.waste_type_snapshot or getattr(item.waste_type, 'value', None) or item.waste_type_id or '—'}"
        )
        self.stdout.write(
            f"  Koncovka: {item.suffix_snapshot or getattr(item.suffix, 'value', None) or item.suffix_id or '—'}"
        )
        self.stdout.write(f"  RZ: {diag['vehicle_rz_label']}")
        self.stdout.write(f"  Pasport: {diag['passport_kind_label']}")
        self.stdout.write("")

        candidates = diag.get("candidates") or []
        if candidates:
            self.stdout.write("  Kandidáti (odpad + koncovka):")
            for row in candidates:
                flags = []
                if row.get("rz_match"):
                    flags.append("RZ: ano")
                else:
                    flags.append("RZ: ne")
                if row.get("passport_match"):
                    flags.append("pasport: ano")
                else:
                    flags.append("pasport: ne")
                marker = ""
                if row.get("is_resolved"):
                    marker = "  <- vyreseno"
                self.stdout.write(
                    f"    pk {row['pk']:>4}  sort {row['sort_order']:<3}  "
                    f"druhy: {row['vehicle_kinds']:<20}  "
                    f"{'  '.join(flags)}{marker}"
                )
        else:
            self.stdout.write("  Kandidáti: žádní")
        self.stdout.write("")

        stored = diag.get("stored_pair_id")
        resolved = diag.get("resolved_pair_id")
        effective = diag.get("effective_pair_id")
        self.stdout.write(f"  Uložený FK:      {stored if stored is not None else '—'}")
        self.stdout.write(f"  Resolver:        {resolved if resolved is not None else '—'}")
        self.stdout.write(f"  Efektivní (ZPO): {effective if effective is not None else '—'}")
        self.stdout.write("")

        status = diag.get("status")
        message = diag.get("message") or ""
        if status == "ok":
            self.stdout.write(self.style.SUCCESS(f"  Stav: OK — {message}"))
        elif status in ("missing_stored", "mismatch"):
            self.stdout.write(self.style.WARNING(f"  Stav: {status} — {message}"))
        else:
            self.stdout.write(self.style.ERROR(f"  Stav: {status} — {message}"))

        if options["fix"]:
            before = stored
            if sync_pruvodka_source_pair(item):
                item.refresh_from_db(fields=["source_waste_suffix_pair_id"])
                after = item.source_waste_suffix_pair_id
                self.stdout.write("")
                self.stdout.write(
                    self.style.SUCCESS(f"  Opraveno: {before or '-'} -> {after}")
                )
            else:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING("  --fix: zápis neproveden (už OK nebo nelze vyřešit).")
                )
