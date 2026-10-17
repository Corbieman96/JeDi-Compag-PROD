"""Okamžité odeslání matice SD — deduplikace jen OPEN úkolu v panelu."""



from datetime import date, datetime, time

from unittest.mock import patch



from django.contrib.auth import get_user_model

from django.test import TestCase, override_settings

from django.utils import timezone



from catalogs.models import (

    ActivityCatalog,

    AddressCatalog,

    ContainerPassport,

    IcoCatalog,

    NameCatalog,

    NameSubjectProfile,

    NameSubjectWasteSuffixPair,

    SuffixCatalog,

    VehicleKindCatalog,

    WasteCategoryCatalog,

    WasteCodeCatalog,

    WasteTypeCatalog,

)

from waste_docs.models import Pruvodka, SvozMatrixQueueEntry, SvozTask

from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine

from waste_docs.services.svoz_matrix_queue import enqueue_svoz_matrix_lines

from waste_docs.services.svoz_task_submit import submit_svoz_line_if_allowed

from waste_docs.svoz_schedule import next_svoz_target_date





def _aware_local(day: date, hour: int, minute: int = 0):

    tz = timezone.get_current_timezone()

    return timezone.make_aware(datetime.combine(day, time(hour, minute)), tz)





@override_settings(TIME_ZONE="Europe/Prague")

class SvozImmediateSubmitDedupTests(TestCase):

    def setUp(self):

        User = get_user_model()

        self.actor = User.objects.create_user("imm_sd", password="pw")

        self.submit_day = date(2036, 6, 25)

        self.target = next_svoz_target_date(self.submit_day)



        self.name = NameCatalog.objects.create(value="Imm yard")

        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Imm")

        self.subject.yard_settings.is_collection_yard = True

        self.subject.yard_settings.yard_allow_matrix = True

        self.subject.yard_settings.save()



        self.wt = WasteTypeCatalog.objects.create(code="200601", value="Imm waste")

        self.wt_other = WasteTypeCatalog.objects.create(code="200602", value="Imm other waste")

        self.suf = SuffixCatalog.objects.create(value="I")

        self.suf_other = SuffixCatalog.objects.create(value="IO")

        self.vk = VehicleKindCatalog.objects.create(name="VkImm", shortcut="I", sort_order=0)

        self.activity = ActivityCatalog.objects.create(name="Svc imm")

        self.pair = NameSubjectWasteSuffixPair.objects.create(

            subject_profile=self.subject,

            waste_type=self.wt,

            suffix=self.suf,

            yard_svoz_enabled=True,

            yard_vehicle_kind=self.vk,

            yard_svoz_activity=self.activity,

            yard_svoz_display_label="Imm row",

        )

        ContainerPassport.objects.create(

            container_number="IMM-108",

            vehicle_kind=self.vk,

            color="—",

        )



    def _pline(self) -> SvozPendingLine:

        return SvozPendingLine(

            pair=self.pair,

            matrix_display_label="Imm row",

            yard_contact_note="",

            container_numbers="IMM-108",

        )



    def _ride_on_day(

        self,

        drive_date: date,

        *,

        waste_type=None,

        suffix=None,

        container: str = "IMM-108",

    ) -> Pruvodka:

        addr = AddressCatalog.objects.create(value=f"Imm addr {drive_date}")

        return Pruvodka.objects.create(

            name=self.name,

            ico=IcoCatalog.objects.create(value="88880001"),

            address=addr,

            waste_type=waste_type or self.wt_other,

            waste_code=WasteCodeCatalog.objects.create(value=f"WC{drive_date:%m%d}"),

            waste_category=WasteCategoryCatalog.objects.create(value=f"KC{drive_date:%m%d}"),

            suffix=suffix or self.suf_other,

            activity=self.activity,

            drive_date=drive_date,

            container_number=container,

            created_by=self.actor,

        )



    @patch("waste_docs.services.svoz_task_dedup.timezone.localdate")

    def test_immediate_submit_creates_when_ride_on_submission_day(self, mock_localdate):

        """Bakov OK: jízda v den hlášení neblokuje nový úkol na zítřek."""

        mock_localdate.return_value = self.submit_day

        self._ride_on_day(self.submit_day)



        result = submit_svoz_line_if_allowed(

            self._pline(), self.subject, self.actor, self.target,

        )

        self.assertTrue(result.created)

        self.assertFalse(result.skipped_duplicate)

        self.assertEqual(SvozTask.objects.count(), 1)

        self.assertEqual(SvozTask.objects.get().target_date, self.target)



    def test_immediate_submit_skips_when_open_task_on_target(self):

        SvozTask.objects.create(

            subject_profile=self.subject,

            created_by=self.actor,

            waste_type=self.wt,

            suffix=self.suf,

            source_waste_suffix_pair=self.pair,

            vehicle_kind=self.vk,

            activity=self.activity,

            container_numbers="IMM-108",

            target_date=self.target,

            status=SvozTask.Status.OPEN,

        )

        result = submit_svoz_line_if_allowed(

            self._pline(), self.subject, self.actor, self.target,

        )

        self.assertFalse(result.created)

        self.assertTrue(result.skipped_duplicate)

        self.assertEqual(SvozTask.objects.count(), 1)



    def test_queue_stays_pending_when_ride_on_submission_day(self):

        noon = _aware_local(self.submit_day, 12, 0)

        enqueue_svoz_matrix_lines(

            [self._pline()], self.subject, self.actor, self.target, now=noon,

        )

        entry = SvozMatrixQueueEntry.objects.get()

        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PENDING)



        self._ride_on_day(self.submit_day)

        entry.refresh_from_db()

        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PENDING)


