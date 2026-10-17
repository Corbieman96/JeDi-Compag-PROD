"""Zpracování fronty matice sběrného dvora (legacy — view už neenqueueuje).

Ponecháno pro dočištění starých PENDING záznamů. Task Scheduler po nasazení zrušit.

    Set-Location C:\\Jedi_2_0
    .\\.venv\\Scripts\\python.exe manage.py process_svoz_matrix_queue

Při výpadku serveru se po restartu zpracují všechny pending záznamy
s process_after v minulosti.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from waste_docs.services.svoz_matrix_queue import process_due_svoz_matrix_queue


class Command(BaseCommand):
    help = "Zpracuje frontu matice SD (deduplikace + SvozTask) pro záznamy po process_after."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Maximální počet záznamů v jednom běhu.",
        )

    def handle(self, *args, **options):
        stats = process_due_svoz_matrix_queue(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Fronta SD ({timezone.localtime().strftime('%H:%M')}): "
                f"zpracováno={stats.processed}, duplicita={stats.skipped_duplicate}, "
                f"chyba={stats.failed}"
            )
        )
