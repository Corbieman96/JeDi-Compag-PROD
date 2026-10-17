from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from customer_requests.models import CustomerRequest, CustomerRequestAuditLog
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_dispatch import customer_requests_visible_for_dispatch
from waste_docs.services.customer_request_status import sync_customer_request_status, sync_for_pruvodka
from waste_docs.services.customer_request_status.align_ride_date import (
    RIDE_RESCHEDULED_AUDIT_ACTION,
    latest_ride_rescheduled_banner,
)
from waste_docs.services.customer_request_status.sync import SYNC_AUDIT_ACTION
from waste_docs.services.ride_soft_delete import soft_delete_pruvodka


class CustomerRequestStatusSyncTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("cr_sync_user", password="pw", is_superuser=True)
        self.day = date(2037, 3, 10)
        self.other_day = self.day + timedelta(days=1)

        self.activity = ActivityCatalog.objects.create(name="Sync svoz")
        self.driver = DriverProfile.objects.create(personal_number="CRS1", last_name="Sync")
        self.rz = VehicleRzCatalog.objects.create(value="9S11111")
        VehicleRzProfile.objects.create(rz=self.rz)
        self.name = NameCatalog.objects.create(value="Sync subjekt")
        self.address = AddressCatalog.objects.create(value="Sync ulice 1")
        self.wt = WasteTypeCatalog.objects.create(code="191199", value="Sync odpad")
        self.suf = SuffixCatalog.objects.create(value="Sx")
        self.ico = IcoCatalog.objects.create(value="99112233")

        self.ride_defaults = dict(
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCCRS"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCCRS"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.day,
            vehicle_rz=self.rz,
            driver=self.driver,
            created_by=self.user,
            container_number="",
        )

    def _create_ride(self, **kwargs) -> Pruvodka:
        ride = Pruvodka(**{**self.ride_defaults, **kwargs})
        ride.save()
        return ride

    def _create_request(self, **kwargs) -> CustomerRequest:
        defaults = dict(
            created_by=self.user,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.PLANNED,
        )
        defaults.update(kwargs)
        return CustomerRequest.objects.create(**defaults)

    def test_planned_becomes_done_when_ride_generated(self):
        ride = self._create_ride(status=Pruvodka.Status.GENERATED)
        cr = self._create_request(planned_pruvodka=ride)

        self.assertTrue(sync_customer_request_status(cr, actor=self.user))
        cr.refresh_from_db()
        self.assertEqual(cr.status, CustomerRequest.Status.DONE)
        self.assertTrue(
            CustomerRequestAuditLog.objects.filter(
                request=cr,
                action=SYNC_AUDIT_ACTION,
            ).exists()
        )

    def test_soft_delete_after_dispatcher_review_closes_request(self):
        ride = self._create_ride()
        cr = self._create_request(
            planned_pruvodka=ride,
            dispatcher_review_by=self.user,
            dispatcher_reviewed_at=timezone.now(),
        )

        soft_delete_pruvodka(pruvodka=ride, actor=self.user, reason="Test archivace sync")
        cr.refresh_from_db()

        self.assertEqual(cr.status, CustomerRequest.Status.CANCELLED)
        self.assertIsNone(cr.planned_pruvodka_id)

    def test_soft_delete_without_dispatcher_review_requires_reschedule(self):
        ride = self._create_ride()
        cr = self._create_request(planned_pruvodka=ride)

        soft_delete_pruvodka(pruvodka=ride, actor=self.user, reason="Test ztráta jízdy sync")
        cr.refresh_from_db()

        self.assertEqual(cr.status, CustomerRequest.Status.REQUIRES_RESCHEDULE)
        self.assertIsNone(cr.planned_pruvodka_id)

    def test_date_mismatch_aligns_target_and_keeps_done_link(self):
        ride = self._create_ride(drive_date=self.other_day, status=Pruvodka.Status.GENERATED)
        cr = self._create_request(
            planned_pruvodka=ride,
            status=CustomerRequest.Status.DONE,
        )

        self.assertTrue(sync_customer_request_status(cr, actor=self.user))
        cr.refresh_from_db()

        self.assertEqual(cr.status, CustomerRequest.Status.DONE)
        self.assertEqual(cr.target_date, self.other_day)
        self.assertEqual(cr.planned_pruvodka_id, ride.pk)
        log = CustomerRequestAuditLog.objects.filter(
            request=cr,
            action=RIDE_RESCHEDULED_AUDIT_ACTION,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn(f"Jízda #{ride.pk} přeplánována", log.note)
        self.assertFalse(
            CustomerRequestAuditLog.objects.filter(
                request=cr,
                action=SYNC_AUDIT_ACTION,
                note__contains="requires_reschedule",
            ).exists()
        )

    def test_workflow_locked_statuses_are_not_changed(self):
        ride = self._create_ride(status=Pruvodka.Status.GENERATED)

        for locked in (
            CustomerRequest.Status.SUBMITTED,
            CustomerRequest.Status.DISPATCHER_REVIEW,
            CustomerRequest.Status.REQUIRES_RESCHEDULE,
        ):
            with self.subTest(status=locked):
                cr = self._create_request(status=locked, planned_pruvodka=ride)
                self.assertFalse(sync_customer_request_status(cr, actor=self.user))
                cr.refresh_from_db()
                self.assertEqual(cr.status, locked)

    def test_sync_for_pruvodka_updates_linked_request(self):
        ride = self._create_ride(status=Pruvodka.Status.RECORDED)
        cr = self._create_request(planned_pruvodka=ride)
        ride.status = Pruvodka.Status.GENERATED
        ride.save(update_fields=["status"])

        updated = sync_for_pruvodka(ride, actor=self.user)
        cr.refresh_from_db()

        self.assertEqual(updated, 1)
        self.assertEqual(cr.status, CustomerRequest.Status.DONE)

    def test_dispatcher_reschedule_not_promoted_to_dispatch_panel(self):
        cr = self._create_request(
            status=CustomerRequest.Status.REQUIRES_RESCHEDULE,
            dispatcher_review_by=self.user,
            dispatcher_reviewed_at=timezone.now(),
        )

        self.assertFalse(sync_customer_request_status(cr, actor=self.user))
        cr.refresh_from_db()

        self.assertEqual(cr.status, CustomerRequest.Status.REQUIRES_RESCHEDULE)
        self.assertEqual(list(customer_requests_visible_for_dispatch(self.user, self.day)), [])

    def test_auto_sync_requires_reschedule_restores_done_link(self):
        ride = self._create_ride(drive_date=self.other_day, status=Pruvodka.Status.GENERATED)
        cr = self._create_request(status=CustomerRequest.Status.REQUIRES_RESCHEDULE)
        CustomerRequestAuditLog.objects.create(
            request=cr,
            actor=self.user,
            action=SYNC_AUDIT_ACTION,
            note=f"Sync po jízdě #{ride.pk}",
        )
        CustomerRequestAuditLog.objects.create(
            request=cr,
            actor=self.user,
            action=SYNC_AUDIT_ACTION,
            note="done → requires_reschedule",
        )

        self.assertTrue(sync_customer_request_status(cr, actor=self.user))
        cr.refresh_from_db()

        self.assertEqual(cr.status, CustomerRequest.Status.DONE)
        self.assertEqual(cr.planned_pruvodka_id, ride.pk)
        self.assertEqual(cr.target_date, self.other_day)
        self.assertTrue(
            CustomerRequestAuditLog.objects.filter(
                request=cr,
                action=RIDE_RESCHEDULED_AUDIT_ACTION,
            ).exists()
        )
        banner = latest_ride_rescheduled_banner(cr)
        self.assertIsNotNone(banner)
        self.assertIn("přeplánován dispečerem", banner)
        self.assertIn(f"#{ride.pk}", banner)

        self.client.force_login(self.user)
        page = self.client.get(reverse("waste_docs:customer_request_detail", kwargs={"pk": cr.pk}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Přeplánováno dispečerem")
        self.assertNotContains(page, "Opravit požadavek")

    def test_dispatcher_button_requires_reschedule_not_restored(self):
        ride = self._create_ride(status=Pruvodka.Status.GENERATED)
        cr = self._create_request(status=CustomerRequest.Status.REQUIRES_RESCHEDULE)
        CustomerRequestAuditLog.objects.create(
            request=cr,
            actor=self.user,
            action=SYNC_AUDIT_ACTION,
            note=f"Sync po jízdě #{ride.pk}",
        )
        CustomerRequestAuditLog.objects.create(
            request=cr,
            actor=self.user,
            action="dispatcher_requires_reschedule",
            note="Posuňte termín",
        )

        self.assertFalse(sync_customer_request_status(cr, actor=self.user))
        cr.refresh_from_db()
        self.assertEqual(cr.status, CustomerRequest.Status.REQUIRES_RESCHEDULE)
        self.assertIsNone(cr.planned_pruvodka_id)
