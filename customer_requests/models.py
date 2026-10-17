from __future__ import annotations

import os

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)


class CustomerRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rozpracováno"
        SUBMITTED = "submitted", "Čeká na schválení zálohy"
        INVOICE_OVERDUE = "invoice_overdue", "Záloha po splatnosti (nezaplaceno)"
        INVOICE_REJECTED = "invoice_rejected", "Záloha zamítnuta"
        DISPATCHER_REVIEW = "dispatcher_review", "Čeká na kontrolu dispečera"
        RETURNED_FOR_FIX = "returned_for_fix", "Vráceno k opravě"
        REQUIRES_RESCHEDULE = "requires_reschedule", "Nutné přeplánovat"
        VISIBLE_FOR_DISPATCH = "visible_for_dispatch", "Viditelné dispečerovi"
        PLANNED = "planned", "Naplánováno"
        DONE = "done", "Dokončeno"
        CANCELLED = "cancelled", "Zrušeno"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_requests_created",
        verbose_name="Zadavatel",
    )
    name = models.ForeignKey(
        NameCatalog,
        on_delete=models.PROTECT,
        related_name="customer_requests",
        verbose_name="Název F/P osoby",
    )
    activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        related_name="customer_requests",
        verbose_name="Činnost",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        related_name="customer_requests",
        null=True,
        blank=True,
        verbose_name="Druh vozidla",
    )
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.PROTECT,
        related_name="customer_requests",
        verbose_name="Druh odpadu",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="customer_requests",
        verbose_name="Koncovka",
        null=True,
        blank=True,
    )
    address = models.ForeignKey(
        AddressCatalog,
        on_delete=models.PROTECT,
        related_name="customer_requests",
        verbose_name="Adresa plnění",
    )
    fulfillment_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Zeměpisná šířka (plnění)",
    )
    fulfillment_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Zeměpisná délka (plnění)",
    )
    facility_address_snapshot = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Adresa provozovny (snapshot)",
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Telefon",
    )
    contact_note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Poznámka ke kontaktu",
    )
    target_date = models.DateField(verbose_name="Datum požadavku", db_index=True)
    contract_number = models.CharField(max_length=120, blank=True, verbose_name="Číslo smlouvy")
    note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka")

    has_follow_up = models.BooleanField(default=False, verbose_name="Má navazující činnost")
    follow_up_activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_requests_follow_up",
        verbose_name="Navazující činnost",
    )
    follow_up_target_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Datum navazující činnosti",
    )
    follow_up_parent_request = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="follow_up_child_requests",
        verbose_name="Základní požadavek (návaznost)",
    )

    is_recurring = models.BooleanField(default=False, verbose_name="Pravidelný požadavek")
    recurrence_weekdays = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="Dny v týdnu",
        help_text="CSV indexů dnů 0-6 (Po=0 ... Ne=6).",
    )
    recurrence_until = models.DateField(null=True, blank=True, verbose_name="Pravidelnost do")
    recurrence_parent_request = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recurrence_child_requests",
        verbose_name="Základní požadavek (opakování)",
    )

    requires_advance_invoice = models.BooleanField(default=False, verbose_name="Vyžaduje zálohovou fakturu")
    advance_invoice_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Výše zálohové faktury",
    )
    invoice_due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Splatnost zálohy",
    )
    invoice_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_requests_invoice_confirmed",
        verbose_name="Zálohu potvrdil",
    )
    invoice_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Potvrzeno")
    invoice_note = models.CharField(max_length=300, blank=True, verbose_name="Poznámka k záloze")

    dispatcher_review_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_requests_dispatcher_reviewed",
        verbose_name="Dispečer",
    )
    dispatcher_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Kontrolováno")
    dispatcher_note = models.CharField(max_length=300, blank=True, verbose_name="Poznámka dispečera")

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT, db_index=True)
    planned_pruvodka = models.ForeignKey(
        "waste_docs.Pruvodka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_requests_primary",
        verbose_name="Vytvořená primární jízda",
    )
    planned_follow_up_pruvodka = models.ForeignKey(
        "waste_docs.Pruvodka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_requests_follow_up",
        verbose_name="Vytvořená navazující jízda",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "waste_docs_customerrequest"
        ordering = ["-created_at"]
        verbose_name = "Požadavek"
        verbose_name_plural = "Požadavky"

    def __str__(self):
        return f"Požadavek #{self.pk} — {self.name.value} ({self.get_status_display()})"

    def mark_invoice_approved(self, actor, note: str = "") -> None:
        self.invoice_confirmed_by = actor
        self.invoice_confirmed_at = timezone.now()
        self.invoice_note = (note or "").strip()
        self.status = self.Status.DISPATCHER_REVIEW

    def mark_dispatcher_approved(self, actor, note: str = "") -> None:
        self.dispatcher_review_by = actor
        self.dispatcher_reviewed_at = timezone.now()
        self.dispatcher_note = (note or "").strip()
        self.status = self.Status.VISIBLE_FOR_DISPATCH

    def resolve_waste_code_and_category(self):
        wt = self.waste_type
        waste_code, _ = WasteCodeCatalog.objects.get_or_create(value=(wt.code or "").strip() or "000000")
        waste_cat, _ = WasteCategoryCatalog.objects.get_or_create(
            value=(wt.category or "").strip() or "O",
        )
        return waste_code, waste_cat


def customer_request_attachment_upload_to(instance, filename: str) -> str:
    req_id = instance.request_id or "new"
    return f"customer_requests/{req_id}/{filename}"


class CustomerRequestAttachment(models.Model):
    request = models.ForeignKey(
        CustomerRequest,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Požadavek",
    )
    sort_order = models.PositiveSmallIntegerField(default=1, verbose_name="Pořadí")
    file = models.FileField(upload_to=customer_request_attachment_upload_to, verbose_name="Příloha")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "waste_docs_customerrequestattachment"
        ordering = ["sort_order", "id"]
        verbose_name = "Příloha požadavku"
        verbose_name_plural = "Přílohy požadavku"

    def __str__(self):
        return f"Příloha #{self.pk} k požadavku #{self.request_id}"

    @property
    def filename_display(self) -> str:
        return os.path.basename(self.file.name or "") or f"Příloha #{self.pk}"


class CustomerRequestAuditLog(models.Model):
    request = models.ForeignKey(
        CustomerRequest,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name="Požadavek",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_request_audit_logs",
        verbose_name="Uživatel",
    )
    action = models.CharField(max_length=80, verbose_name="Akce")
    note = models.CharField(max_length=500, blank=True, verbose_name="Poznámka")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "waste_docs_customerrequestauditlog"
        ordering = ["-created_at", "-id"]
        verbose_name = "Audit požadavku"
        verbose_name_plural = "Audit požadavků"

    def __str__(self):
        return f"{self.request_id} {self.action}"


class CustomerRequestDateClosure(models.Model):
    """Ruční uzavření kalendářního dne pro nové zákaznické požadavky (dispečer)."""

    closure_date = models.DateField(unique=True, db_index=True, verbose_name="Datum")
    is_closed = models.BooleanField(default=True, verbose_name="Uzavřeno")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_request_date_closures",
        verbose_name="Naposledy změnil",
    )

    class Meta:
        db_table = "waste_docs_customerrequestdateclosure"
        verbose_name = "Uzavření dne pro požadavky"
        verbose_name_plural = "Uzavření dnů pro požadavky"
        ordering = ["-closure_date"]

    def __str__(self) -> str:
        state = "uzavřeno" if self.is_closed else "otevřeno"
        return f"{self.closure_date} ({state})"


class NoServiceCalendarDay(models.Model):
    """Konkrétní den bez svozu (svátek) a volitelný cílový den pro posun termínu."""

    closed_date = models.DateField(unique=True, db_index=True, verbose_name="Den bez svozu")
    redirect_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Přesunout na",
        help_text="Prázdné = první následující provozní den.",
    )
    note = models.CharField(max_length=120, blank=True, verbose_name="Poznámka")

    class Meta:
        db_table = "waste_docs_noservicecalendarday"
        verbose_name = "Den bez svozu"
        verbose_name_plural = "Dny bez svozu"
        ordering = ["closed_date"]

    def __str__(self) -> str:
        return str(self.closed_date)


class CustomerRequestVehicleKindClosure(models.Model):
    """Ruční uzavření konkrétního druhu vozidla pro zákaznické požadavky v daný den."""

    closure_date = models.DateField(db_index=True, verbose_name="Datum")
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.CASCADE,
        related_name="customer_request_kind_closures",
        verbose_name="Druh vozidla",
    )
    is_closed = models.BooleanField(default=True, verbose_name="Uzavřeno")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_request_vehicle_kind_closures",
        verbose_name="Naposledy změnil",
    )

    class Meta:
        db_table = "waste_docs_customerrequestvehiclekindclosure"
        verbose_name = "Uzavření druhu vozidla pro požadavky"
        verbose_name_plural = "Uzavření druhů vozidel pro požadavky"
        ordering = ["-closure_date", "vehicle_kind_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["closure_date", "vehicle_kind"],
                name="uniq_cr_vehicle_kind_closure_day_kind",
            )
        ]

    def __str__(self) -> str:
        state = "uzavřeno" if self.is_closed else "otevřeno"
        return f"{self.closure_date} / {self.vehicle_kind_id} ({state})"


from customer_requests.request_templates.models import CustomerRequestTemplate  # noqa: E402, F401
