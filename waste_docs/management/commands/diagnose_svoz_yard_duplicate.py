"""Diagnostika duplicitních jízd po hlášení matice ze sběrného dvora."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from catalogs.models import NameCatalog, NameSubjectProfile
from waste_docs.models import Pruvodka, SvozMatrixQueueEntry, SvozTask
from waste_docs.services.container_passport_ride_validation import normalize_container_number


class Command(BaseCommand):
    help = (
        "Vypíše jízdy, SvozTask a záznamy fronty pro subjekt/kontejner kolem zadaného dne."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yard",
            required=True,
            help="Název subjektu (NameCatalog.value), např. Bakov — částečná shoda.",
        )
        parser.add_argument(
            "--container",
            required=True,
            help="Číslo kontejneru, např. 108.",
        )
        parser.add_argument(
            "--date",
            required=True,
            help="Referenční datum (YYYY-MM-DD), typicky den svezení.",
        )

    def handle(self, *args, **options):
        yard_q = (options["yard"] or "").strip()
        container = normalize_container_number(options["container"])
        if not container:
            raise CommandError("Neplatné číslo kontejneru.")

        try:
            ref_day = date.fromisoformat(options["date"])
        except ValueError as exc:
            raise CommandError("Neplatné --date, očekávám YYYY-MM-DD.") from exc

        names = list(
            NameCatalog.objects.filter(value__icontains=yard_q).values_list("pk", "value")
        )
        if not names:
            raise CommandError(f"Subjekt obsahující '{yard_q}' nenalezen.")

        self.stdout.write(
            self.style.NOTICE(
                f"Diagnostika: yard~{yard_q!r}, kontejner={container}, datum={ref_day}"
            )
        )

        for name_id, name_value in names:
            subjects = NameSubjectProfile.objects.filter(name_id=name_id).select_related("name")
            if not subjects.exists():
                self.stdout.write(f"\n=== {name_value} (name_id={name_id}) — bez profilu subjektu ===")
                continue

            for subject in subjects:
                self._report_subject(subject, container, ref_day)

    def _container_q(self, number: str) -> Q:
        return (
            Q(container_number__iexact=number)
            | Q(container_number_2__iexact=number)
            | Q(container_passport__container_number__iexact=number)
        )

    def _report_subject(self, subject: NameSubjectProfile, container: str, ref_day: date):
        name_value = subject.name.value if subject.name_id else "?"
        self.stdout.write(
            f"\n=== {name_value} / profil #{subject.pk} ({subject.company_name or '—'}) ==="
        )

        days = sorted({ref_day, ref_day + timedelta(days=1)})
        self.stdout.write(f"Kontrolované dny: {', '.join(str(d) for d in days)}")

        rides = (
            Pruvodka.objects.filter(name_id=subject.name_id)
            .filter(self._container_q(container))
            .filter(drive_date__in=days)
            .select_related("waste_type", "suffix", "activity")
            .order_by("drive_date", "pk")
        )
        self.stdout.write(f"\nJízdy (Pruvodka): {rides.count()}")
        for ride in rides:
            archived = "archiv" if ride.is_archived else "aktivní"
            wt = ride.waste_type.value if ride.waste_type_id else "—"
            suf = ride.suffix.value if ride.suffix_id else "—"
            created = timezone.localtime(ride.created_at).strftime("%Y-%m-%d %H:%M") if ride.created_at else "—"
            self.stdout.write(
                f"  #{ride.pk} drive={ride.drive_date} {archived} "
                f"odpad={wt} suffix={suf} c1={ride.container_number!r} "
                f"vytvořeno={created}"
            )

        tasks = (
            SvozTask.objects.filter(subject_profile_id=subject.pk, container_numbers__iexact=container)
            .filter(target_date__in=days)
            .select_related("waste_type", "suffix")
            .order_by("target_date", "pk")
        )
        self.stdout.write(f"\nPožadavky svozu (SvozTask): {tasks.count()}")
        for task in tasks:
            wt = task.waste_type.value if task.waste_type_id else "—"
            suf = task.suffix.value if task.suffix_id else "—"
            created = timezone.localtime(task.created_at).strftime("%Y-%m-%d %H:%M") if task.created_at else "—"
            resolved = f"průvodka #{task.resolved_pruvodka_id}" if task.resolved_pruvodka_id else "—"
            self.stdout.write(
                f"  #{task.pk} target={task.target_date} status={task.status} "
                f"odpad={wt} suffix={suf} vytvořeno={created} vyřízeno={resolved}"
            )

        queue = (
            SvozMatrixQueueEntry.objects.filter(
                subject_profile_id=subject.pk,
                container_numbers__iexact=container,
            )
            .filter(Q(target_date__in=days) | Q(submitted_at__date__in=days))
            .select_related("source_waste_suffix_pair", "result_svoz_task")
            .order_by("submitted_at", "pk")
        )
        self.stdout.write(f"\nFronta matice (SvozMatrixQueueEntry): {queue.count()}")
        for entry in queue:
            submitted = timezone.localtime(entry.submitted_at).strftime("%Y-%m-%d %H:%M")
            process_after = timezone.localtime(entry.process_after).strftime("%Y-%m-%d %H:%M")
            processed = (
                timezone.localtime(entry.processed_at).strftime("%Y-%m-%d %H:%M")
                if entry.processed_at
                else "—"
            )
            pair = entry.source_waste_suffix_pair
            pair_label = f"wt={pair.waste_type_id} suf={pair.suffix_id}" if pair else "—"
            result = f"task #{entry.result_svoz_task_id}" if entry.result_svoz_task_id else "—"
            err = (entry.last_error or "").strip()
            err_part = f" err={err!r}" if err else ""
            self.stdout.write(
                f"  #{entry.pk} status={entry.status} target={entry.target_date} "
                f"odesláno={submitted} process_after={process_after} "
                f"zpracováno={processed} {pair_label} výsledek={result}{err_part}"
            )
