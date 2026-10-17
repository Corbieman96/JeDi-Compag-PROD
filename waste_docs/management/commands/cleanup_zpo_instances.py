from __future__ import annotations

from django.core.management.base import BaseCommand

from waste_docs.services.zpo_instance_cleanup import cleanup_all_zpo_instance_orphans
from waste_docs.zpo_instance_generator import CURRENT_ZPO_GENERATOR_REVISION, ensure_zpo_instance_for_pruvodka_pk
from waste_docs.zpo_policy import system_may_generate_zpo_instance
from waste_docs.models import Pruvodka


class Command(BaseCommand):
    help = (
        "Smaže osiřelé soubory ZPO v media/pruvodky/zpo_instance/ a volitelně "
        "přegeneruje instance se starou revizí generátoru."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen spočítá osiřelé soubory, nic nemazat.",
        )
        parser.add_argument(
            "--regenerate-outdated",
            action="store_true",
            help="Po úklidu přegeneruje ZPO u průvodek se zpo_generator_revision < aktuální.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        regenerate: bool = options["regenerate_outdated"]

        deleted, orphan_count = cleanup_all_zpo_instance_orphans(dry_run=dry_run)
        if dry_run:
            self.stdout.write(f"Osiřelých souborů ZPO: {orphan_count} (dry-run, nic smazáno)")
        else:
            self.stdout.write(f"Smazáno osiřelých souborů ZPO: {deleted} (nalezeno {orphan_count})")

        if not regenerate:
            return

        qs = Pruvodka.objects.filter(is_archived=False).exclude(snd_cislo_listu="")
        outdated_pks = [
            pk
            for pk, rev in qs.values_list("pk", "zpo_generator_revision")
            if (rev or 0) < CURRENT_ZPO_GENERATOR_REVISION
        ]
        regen_ok = 0
        for pk in outdated_pks:
            item = Pruvodka.objects.filter(pk=pk).first()
            if not item or not system_may_generate_zpo_instance(item):
                continue
            if dry_run:
                regen_ok += 1
                continue
            ensure_zpo_instance_for_pruvodka_pk(pk)
            regen_ok += 1
        verb = "K přegenerování" if dry_run else "Přegenerováno"
        self.stdout.write(f"{verb} ZPO u průvodek (stará revize): {regen_ok}")
