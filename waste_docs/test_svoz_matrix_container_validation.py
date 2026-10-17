"""Blokace odeslání matice, pokud pasport kontejneru nesedí k plánu / druhu vozidla."""

from datetime import date

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from users.models import UserAccessProfile

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile

from waste_docs.models import Pruvodka, SvozYardDriverPlan
from waste_docs.services.svoz_matrix_post_collect import collect_pending_svoz_matrix_lines


class SvozMatrixContainerValidationTests(TestCase):
    def setUp(self):
        self.target = date(2026, 5, 19)
        self.name = NameCatalog.objects.create(value="Yard passport block")
        self.ico = IcoCatalog.objects.create(value="88888888")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name, company_name="Yard PB", ico=self.ico
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.wt = WasteTypeCatalog.objects.create(code="200110", value="Textil PB")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk_chain = VehicleKindCatalog.objects.create(name="Řetěz PB", shortcut="R", sort_order=0)
        self.vk_hook = VehicleKindCatalog.objects.create(name="Hák PB", shortcut="H", sort_order=1)
        self.activity = ActivityCatalog.objects.create(name="Svoz PB")

        self.driver = DriverProfile.objects.create(personal_number="PB-1", last_name="Mašek")
        self.rz = VehicleRzCatalog.objects.create(value="5S19968")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk_chain)

        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk_chain,
            sort_order=0,
        )

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk_chain,
            yard_svoz_activity=self.activity,
            yard_svoz_display_label="Textil",
            yard_svoz_auto_assign_driver=False,
        )

        ContainerPassport.objects.create(
            container_number="614",
            vehicle_kind=self.vk_hook,
            color="—",
        )

    def _open_ride_with_container(self, container_number: str, drive_date: date) -> Pruvodka:
        addr = AddressCatalog.objects.create(value=f"Adr {container_number}")
        return Pruvodka.objects.create(
            name=self.name,
            ico=self.ico,
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value=f"WC{container_number}"),
            waste_category=WasteCategoryCatalog.objects.create(value=f"KC{container_number}"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=drive_date,
            container_number=container_number,
            created_by=get_user_model().objects.create_user(
                f"ride_{container_number}", password="x"
            ),
        )

    def test_collect_blocks_when_passport_vehicle_kind_mismatches_plan_rz(self):
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "614"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(pending, [])
        self.assertEqual(len(errs), 1)
        self.assertIn("614", errs[0])
        self.assertIn("pasport", errs[0].casefold())
        self.assertIn("dispečer", errs[0].casefold())

    def test_collect_allows_matching_passport(self):
        ContainerPassport.objects.filter(container_number__iexact="614").delete()
        ContainerPassport.objects.create(
            container_number="614",
            vehicle_kind=self.vk_chain,
            color="—",
        )
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "614"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 1)

    def test_collect_allows_container_on_open_ride_other_day(self):
        ContainerPassport.objects.filter(container_number__iexact="614").delete()
        ContainerPassport.objects.create(
            container_number="614",
            vehicle_kind=self.vk_chain,
            color="—",
        )
        self._open_ride_with_container("614", date(2026, 5, 10))
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "614"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 1)

    def test_validate_container_ajax_ok_when_open_ride_elsewhere(self):
        ContainerPassport.objects.filter(container_number__iexact="614").delete()
        ContainerPassport.objects.create(
            container_number="614",
            vehicle_kind=self.vk_chain,
            color="—",
        )
        self._open_ride_with_container("614", date(2026, 5, 10))
        self._login_yard_user()
        url = reverse("waste_docs:svoz_matrix_validate_container")
        r = self.client.get(url, {"pair_pk": self.pair.pk, "containers": "614"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])

    def test_collect_blocks_unknown_without_confirmation(self):
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "999-novy"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(pending, [])
        self.assertEqual(len(errs), 1)
        self.assertIn("není v číselníku pasportů", errs[0])

    def test_collect_allows_unknown_with_confirmation(self):
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "999-novy"
        qd["unknown_passport_confirmed"] = "999-novy"
        qd["unknown_passport_confirmer"] = "Yard Operator"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].container_numbers, "")
        self.assertEqual(pending[0].claimed_unknown_container, "999-novy")
        self.assertIn("999-novy", pending[0].yard_contact_note)
        self.assertIn("Yard Operator", pending[0].yard_contact_note)

    def _login_yard_user(self):
        from users.constants import ROLE_SBERNY_DVUR
        from users.services.roles import set_user_role

        User = get_user_model()
        yard_user = User.objects.create_user("yard_ajax", password="pw")
        set_user_role(yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=yard_user)
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])
        self.client.force_login(yard_user)

    def test_validate_container_ajax_returns_error_for_mismatch(self):
        self._login_yard_user()
        url = reverse("waste_docs:svoz_matrix_validate_container")
        r = self.client.get(url, {"pair_pk": self.pair.pk, "containers": "614"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["ok"])
        self.assertTrue(data.get("errors"))

    def test_validate_container_ajax_ok_with_unknown_numbers(self):
        self._login_yard_user()
        url = reverse("waste_docs:svoz_matrix_validate_container")
        r = self.client.get(url, {"pair_pk": self.pair.pk, "containers": "888-new"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data.get("errors") or [], [])
        self.assertIn("888-new", data.get("unknown_numbers") or [])
