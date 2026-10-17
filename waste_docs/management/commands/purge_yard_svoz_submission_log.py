from django.core.management.base import BaseCommand

from waste_docs.services.yard_svoz_submission_log import (
    LOG_RETENTION_DAYS,
    purge_yard_svoz_submission_logs_older_than,
)


class Command(BaseCommand):
    help = (
        "Smaže textový log odeslání matice sběrného dvora starší než "
        f"{LOG_RETENTION_DAYS} dní (SvozTask a úkoly dispečera se nemění)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=LOG_RETENTION_DAYS,
            help=f"Počet dní uchování logu (výchozí {LOG_RETENTION_DAYS}).",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        deleted = purge_yard_svoz_submission_logs_older_than(retention_days=days)
        self.stdout.write(self.style.SUCCESS(f"Smazáno záznamů logu: {deleted}"))
