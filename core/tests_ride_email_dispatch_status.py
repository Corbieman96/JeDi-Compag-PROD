from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import VehicleRzCatalog
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from core.services.ride_email_dispatch_status import attach_email_dispatch_to_ride_groups
from waste_docs.services.ride_document_email.dispatch_record import record_group_dispatch

User = get_user_model()


class RideEmailDispatchStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="odesilatel",
            password="pw",
            first_name="Jan",
            last_name="Dispečer",
            is_superuser=True,
        )
        set_user_role(self.user, ROLE_ADMIN)
        self.drive_date = date(2026, 6, 8)
        self.rz = VehicleRzCatalog.objects.create(value="1A11111")

    def test_attach_includes_dispatched_by_in_tooltip_data(self):
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="ridic@example.com",
            subject="Test",
            ride_count=1,
            attachment_count=2,
            user=self.user,
        )
        groups = [{"vehicle_rz_id": self.rz.pk}]
        attach_email_dispatch_to_ride_groups(groups, self.drive_date)
        dispatch = groups[0]["email_dispatch"]
        self.assertEqual(dispatch["dispatched_by"], "Jan Dispečer")
        self.assertEqual(dispatch["recipient_email"], "ridic@example.com")

    def test_attach_falls_back_to_username(self):
        user = User.objects.create_user(username="karel_ops", password="pw", is_superuser=True)
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="a@b.cz",
            subject="Test",
            ride_count=1,
            attachment_count=2,
            user=user,
        )
        groups = [{"vehicle_rz_id": self.rz.pk}]
        attach_email_dispatch_to_ride_groups(groups, self.drive_date)
        self.assertEqual(groups[0]["email_dispatch"]["dispatched_by"], "karel_ops")
