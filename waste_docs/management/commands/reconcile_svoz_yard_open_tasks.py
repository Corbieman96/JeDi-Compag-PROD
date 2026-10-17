"""Dočištění OPEN SvozTask u sběrných dvorů — reconcile a retry auto-průvodky."""



from __future__ import annotations



from datetime import date



from django.core.management.base import BaseCommand



from catalogs.models import NameSubjectProfile

from waste_docs.models import SvozTask

from waste_docs.services.svoz_task_yard_reconcile import (

    reconcile_open_svoz_task_if_fulfilled,

    retry_auto_pruvodka_for_open_task,

)





class Command(BaseCommand):

    help = (

        "Uzavře OPEN úkoly svozu u SD kde existuje jízda a znovu spustí auto-průvodku."

    )



    def add_arguments(self, parser):

        parser.add_argument(

            "--dry-run",

            action="store_true",

            help="Jen vypsat plánované akce, neukládat.",

        )

        parser.add_argument(

            "--target-date",

            type=str,

            help="Omezit na úkoly s target_date YYYY-MM-DD (volitelné).",

        )



    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        target_filter: date | None = None

        if options.get("target_date"):

            target_filter = date.fromisoformat(options["target_date"])



        yard_ids = list(

            NameSubjectProfile.objects.filter(yard_settings__is_collection_yard=True).values_list(

                "pk", flat=True

            )

        )

        qs = SvozTask.objects.filter(

            subject_profile_id__in=yard_ids,

            status=SvozTask.Status.OPEN,

        ).select_related("subject_profile", "subject_profile__name", "created_by")

        if target_filter:

            qs = qs.filter(target_date=target_filter)



        stats = {

            "reconciled": 0,

            "auto_created": 0,

            "auto_failed": 0,

            "still_open": 0,

        }



        for task in qs.order_by("target_date", "pk"):

            label = (

                f"#{task.pk} {task.subject_profile.name.value} "

                f"cont={task.container_numbers!r} target={task.target_date}"

            )



            if dry_run:

                self.stdout.write(f"CHECK {label} driver={task.assigned_driver_id}")

                continue



            if reconcile_open_svoz_task_if_fulfilled(task):

                stats["reconciled"] += 1

                self.stdout.write(self.style.SUCCESS(f"Uzavřeno (jízda existuje): {label}"))

                continue



            if not task.assigned_driver_id:

                stats["still_open"] += 1

                continue



            ok, err = retry_auto_pruvodka_for_open_task(task)

            task.refresh_from_db()

            if ok or task.status == SvozTask.Status.DONE:

                stats["auto_created"] += 1

                self.stdout.write(self.style.SUCCESS(f"Auto-průvodka OK: {label}"))

            else:

                stats["auto_failed"] += 1

                stats["still_open"] += 1

                self.stdout.write(

                    self.style.WARNING(f"Auto-průvodka selhala: {label} — {err or 'skip'}")

                )



        self.stdout.write(

            self.style.SUCCESS(

                f"Hotovo{' (dry-run)' if dry_run else ''}: "

                f"reconciled={stats['reconciled']}, "

                f"auto_jizda={stats['auto_created']}, "

                f"auto_chyba={stats['auto_failed']}, "

                f"stale_open={stats['still_open']}"

            )

        )


