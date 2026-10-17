from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import DriverAbsence, DriverProfile
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.access import can_manage_driver_absences
from users.services.roles import set_user_role

User = get_user_model()


class DriverAbsenceAccessTests(TestCase):
    def setUp(self):
        self.dispecer = User.objects.create_user("disp_abs", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("zad_abs", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.admin = User.objects.create_user("adm_abs", password="pw", is_superuser=True)
        self.driver = DriverProfile.objects.create(personal_number="ABS-1", last_name="Test", first_name="Řidič")

    def test_can_manage_driver_absences_roles(self):
        self.assertTrue(can_manage_driver_absences(self.admin))
        self.assertTrue(can_manage_driver_absences(self.dispecer))
        self.assertFalse(can_manage_driver_absences(self.zadavatel))

    def test_dispecer_can_quick_add_absence(self):
        c = Client()
        c.force_login(self.dispecer)
        r = c.post(
            reverse("catalogs:driver_absence_quick_add"),
            {
                "driver": self.driver.pk,
                "absence_type": DriverAbsence.AbsenceType.VACATION,
                "date_from": "2026-06-15",
                "date_to": "2026-06-15",
                "next_date": "2026-06-15",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            DriverAbsence.objects.filter(driver=self.driver, absence_type=DriverAbsence.AbsenceType.VACATION).exists()
        )

    def test_zadavatel_cannot_quick_add_absence(self):
        c = Client()
        c.force_login(self.zadavatel)
        r = c.post(
            reverse("catalogs:driver_absence_quick_add"),
            {
                "driver": self.driver.pk,
                "absence_type": DriverAbsence.AbsenceType.VACATION,
                "date_from": "2026-06-15",
                "date_to": "2026-06-15",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(DriverAbsence.objects.filter(driver=self.driver).exists())

    def test_dispecer_sees_absence_menu_on_dashboard(self):
        c = Client()
        c.force_login(self.dispecer)
        r = c.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dash-absence-mini-form")
        self.assertContains(r, "Zapsat nepřítomnost")
