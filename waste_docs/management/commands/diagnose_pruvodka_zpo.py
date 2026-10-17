"""Diagnostika stavu ZPO u jedné průvodky."""

from __future__ import annotations

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_pair_docs import pair_docs_for_pruvodka
from waste_docs.services.zpo_instance_status import (
    explain_missing_zpo_instance,
    last_zpo_ensure_failure,
    zpo_instance_is_ready,
    zpo_template_url_for_pruvodka,
)
from waste_docs.zpo_policy import explain_system_zpo_generation_block, system_may_generate_zpo_instance
from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka, effective_zpo_file


class Command(BaseCommand):
    help = "Vypíše stav ZPO u průvodky (instance, vzor, důvod blokace / chyby)."

    def add_arguments(self, parser):
        parser.add_argument("pk", type=int, help="Primární klíč průvodky (Pruvodka.pk)")

    def handle(self, *args, **options):
        pk = options["pk"]
        try:
            item = Pruvodka.objects.select_related(
                "activity",
                "name",
                "waste_type",
                "suffix",
            ).get(pk=pk)
        except Pruvodka.DoesNotExist as exc:
            raise CommandError(f"Průvodka #{pk} neexistuje.") from exc

        pair = pair_docs_for_pruvodka(item)
        template = effective_zpo_file(pair)
        display = display_zpo_file_for_pruvodka(item, pair)
        ready = zpo_instance_is_ready(item)
        may = system_may_generate_zpo_instance(item)
        block = explain_system_zpo_generation_block(item)
        missing = explain_missing_zpo_instance(item, pair=pair)
        template_url = zpo_template_url_for_pruvodka(item, pair=pair)
        last_fail = last_zpo_ensure_failure(pk)

        self.stdout.write(self.style.NOTICE(f"Diagnostika ZPO — průvodka #{pk}"))
        self.stdout.write(f"  SND: {(item.snd_cislo_listu or '').strip() or '—'}")
        self.stdout.write(f"  Subjekt: {item.name_snapshot or item.name_id or '—'}")
        self.stdout.write(f"  Odpad: {item.waste_type_snapshot or item.waste_type_id or '—'}")
        self.stdout.write(f"  Koncovka: {item.suffix_snapshot or item.suffix_id or '—'}")
        self.stdout.write(f"  Činnost: {item.activity_snapshot or item.activity_id or '—'}")
        self.stdout.write("")
        self.stdout.write(f"  Pár v číselníku: {'ano' if pair else 'ne'}")
        self.stdout.write(f"  Vzor ZPO (effective): {'ano' if template else 'ne'}")
        if template and getattr(template, "name", None):
            on_disk = default_storage.exists(template.name)
            self.stdout.write(f"  Vzor na disku ({template.name}): {'ano' if on_disk else 'NE'}")
        self.stdout.write(f"  URL vzoru: {template_url or '—'}")
        self.stdout.write("")
        self.stdout.write(f"  system_may_generate_zpo: {may}")
        if block:
            self.stdout.write(self.style.WARNING(f"  Blokace generování: {block}"))
        self.stdout.write(f"  zpo_instance_file: {item.zpo_instance_file.name if item.zpo_instance_file else '—'}")
        if item.zpo_instance_file and item.zpo_instance_file.name:
            inst_ok = default_storage.exists(item.zpo_instance_file.name)
            self.stdout.write(f"  Instance na disku: {'ano' if inst_ok else 'NE'}")
        self.stdout.write(f"  zpo_instance_for_snd: {(item.zpo_instance_for_snd or '').strip() or '—'}")
        self.stdout.write(f"  zpo_generator_revision: {getattr(item, 'zpo_generator_revision', 0)}")
        self.stdout.write("")
        self.stdout.write(f"  Instance připravena (display): {'ano' if ready else 'ne'}")
        if display:
            self.stdout.write(f"  Display URL: {display.url}")
        if missing:
            self.stdout.write(self.style.WARNING(f"  Důvod chybějící instance: {missing}"))
        elif ready:
            self.stdout.write(self.style.SUCCESS("  ZPO je v pořádku."))
        if last_fail:
            self.stdout.write(f"  Poslední chyba ensure (session): {last_fail}")
