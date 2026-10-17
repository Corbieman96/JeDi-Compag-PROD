"""Cílový den submitu matice a reconcile OPEN úkolů."""



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

from waste_docs.models import Pruvodka, SvozTask

from waste_docs.services.svoz_auto_pruvodka_skip import auto_pruvodka_skip_reason_for_svoz_task

from waste_docs.services.svoz_task_yard_reconcile import reconcile_open_svoz_task_if_fulfilled

from waste_docs.svoz_schedule import svoz_target_date_for_matrix_submit





def _aware(day: date, hour: int = 12):

    tz = timezone.get_current_timezone()

    return timezone.make_aware(datetime.combine(day, time(hour)), tz)





@override_settings(TIME_ZONE="Europe/Prague")

class SvozTargetDateSubmitTests(TestCase):

    def test_matrix_submit_uses_tomorrow(self):
        now = _aware(date(2036, 6, 25), 16)
        with patch("waste_docs.svoz_schedule.timezone.localdate", return_value=date(2036, 6, 25)):
            self.assertEqual(
                svoz_target_date_for_matrix_submit(now=now),
                date(2036, 6, 26),
            )





@override_settings(TIME_ZONE="Europe/Prague")

class SvozAutoPruvodkaScopeTests(TestCase):

    def setUp(self):

        User = get_user_model()

        self.actor = User.objects.create_user("scope_sd", password="pw")

        self.submit_day = date(2036, 6, 25)

        self.target = date(2036, 6, 26)



        self.name_yard = NameCatalog.objects.create(value="Scope yard")

        self.subject = NameSubjectProfile.objects.create(name=self.name_yard, company_name="SD Scope")

        self.name_other = NameCatalog.objects.create(value="Other yard")

        self.other_subject = NameSubjectProfile.objects.create(name=self.name_other, company_name="SD Other")

        self.other_subject.yard_settings.is_collection_yard = True

        self.other_subject.yard_settings.save()



        self.wt = WasteTypeCatalog.objects.create(code="200701", value="Scope waste")

        self.suf = SuffixCatalog.objects.create(value="SC")

        self.vk = VehicleKindCatalog.objects.create(name="VkSc", shortcut="SC", sort_order=0)

        self.activity = ActivityCatalog.objects.create(name="Svc scope")

        self.pair = NameSubjectWasteSuffixPair.objects.create(

            subject_profile=self.subject,

            waste_type=self.wt,

            suffix=self.suf,

            yard_svoz_enabled=True,

            yard_vehicle_kind=self.vk,

            yard_svoz_activity=self.activity,

        )

        ContainerPassport.objects.create(container_number="SC-218", vehicle_kind=self.vk, color="—")



        created_at = _aware(self.submit_day, 16)

        self.task = SvozTask.objects.create(

            subject_profile=self.subject,

            created_by=self.actor,

            waste_type=self.wt,

            suffix=self.suf,

            source_waste_suffix_pair=self.pair,

            vehicle_kind=self.vk,

            activity=self.activity,

            container_numbers="SC-218",

            target_date=self.target,

        )

        SvozTask.objects.filter(pk=self.task.pk).update(created_at=created_at)

        self.task.refresh_from_db()



    @patch(

        "waste_docs.services.svoz_dispatch.matrix_plan_match.matrix_pair_resolves_to_plan_assignment",

        return_value=True,

    )

    def test_old_ride_other_yard_does_not_block_auto_pruvodka(self, _mock_plan):

        addr = AddressCatalog.objects.create(value="Other addr")

        Pruvodka.objects.create(

            name=self.name_other,

            ico=IcoCatalog.objects.create(value="77770001"),

            address=addr,

            waste_type=self.wt,

            waste_code=WasteCodeCatalog.objects.create(value="WCO1"),

            waste_category=WasteCategoryCatalog.objects.create(value="KCO1"),

            suffix=self.suf,

            activity=self.activity,

            drive_date=date(2036, 6, 20),

            container_number="SC-218",

            created_by=self.actor,

        )

        self.assertIsNone(auto_pruvodka_skip_reason_for_svoz_task(self.task))





@override_settings(TIME_ZONE="Europe/Prague")

class SvozTaskYardReconcileTests(TestCase):

    def setUp(self):

        User = get_user_model()

        self.actor = User.objects.create_user("recon_sd", password="pw")

        self.submit_day = date(2036, 6, 25)

        self.target_day = date(2036, 6, 26)



        self.name = NameCatalog.objects.create(value="Recon yard")

        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Recon")

        self.subject.yard_settings.is_collection_yard = True

        self.subject.yard_settings.save()



        self.wt = WasteTypeCatalog.objects.create(code="200702", value="Recon waste")

        self.suf = SuffixCatalog.objects.create(value="RC")

        self.vk = VehicleKindCatalog.objects.create(name="VkRc", shortcut="RC", sort_order=0)

        self.activity = ActivityCatalog.objects.create(name="Svc recon")

        self.pair = NameSubjectWasteSuffixPair.objects.create(

            subject_profile=self.subject,

            waste_type=self.wt,

            suffix=self.suf,

            yard_svoz_enabled=True,

            yard_vehicle_kind=self.vk,

            yard_svoz_activity=self.activity,

        )



        created_at = _aware(self.submit_day, 16)

        self.task = SvozTask.objects.create(

            subject_profile=self.subject,

            created_by=self.actor,

            waste_type=self.wt,

            suffix=self.suf,

            source_waste_suffix_pair=self.pair,

            vehicle_kind=self.vk,

            activity=self.activity,

            container_numbers="RC-99",

            target_date=self.target_day,

            status=SvozTask.Status.OPEN,

        )

        SvozTask.objects.filter(pk=self.task.pk).update(created_at=created_at)

        self.task.refresh_from_db()



    def test_reconcile_does_not_close_open_task_when_unlinked_ride_exists(self):
        addr = AddressCatalog.objects.create(value="Recon addr")
        Pruvodka.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="77770002"),
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCR1"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCR1"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.target_day,
            container_number="RC-99",
            created_by=self.actor,
        )
        self.assertFalse(reconcile_open_svoz_task_if_fulfilled(self.task))
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, SvozTask.Status.OPEN)


