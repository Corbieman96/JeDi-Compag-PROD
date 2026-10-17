from django.db import models

from .vehicle_rz import VehicleKindCatalog, VehicleRzProfile


class DriverProfile(models.Model):
    class RequirementStatus(models.TextChoices):
        UNSPECIFIED = "unspecified", "neuvedeno"
        REQUIRED = "required", "vyzadovana"
        NOT_REQUIRED = "not_required", "nevyzadovana"

    title = models.CharField(max_length=50, blank=True, verbose_name="Titul")
    first_name = models.CharField(max_length=120, blank=True, verbose_name="Jmeno")
    last_name = models.CharField(max_length=120, blank=True, verbose_name="Prijmeni")
    personal_number = models.CharField(max_length=50, unique=True, verbose_name="Osobni cislo")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    job_position = models.CharField(max_length=120, blank=True, verbose_name="Pracovni pozice")
    employment_type = models.CharField(max_length=80, blank=True, verbose_name="Typ pomeru")
    start_date = models.DateField(blank=True, null=True, verbose_name="Datum nastupu")
    availability_note = models.TextField(blank=True, verbose_name="Poznamka k dostupnosti")

    driver_license_number = models.CharField(max_length=50, blank=True, verbose_name="Cislo RP")
    driver_license_groups = models.CharField(max_length=120, blank=True, verbose_name="Skupiny")
    driver_license_valid_until = models.DateField(blank=True, null=True, verbose_name="Platnost RP do")
    driver_license_restrictions = models.CharField(max_length=255, blank=True, verbose_name="Omezeni RP")
    driver_license_last_check = models.DateField(blank=True, null=True, verbose_name="Posledni kontrola RP")

    professional_competence_required = models.CharField(
        max_length=20,
        choices=RequirementStatus.choices,
        default=RequirementStatus.UNSPECIFIED,
        verbose_name="Profesni zpusobilost vyzadovana",
    )
    professional_competence_document = models.CharField(max_length=120, blank=True, verbose_name="Doklad")
    professional_competence_valid_until = models.DateField(blank=True, null=True, verbose_name="Platnost dokladu do")
    professional_competence_last_training = models.DateField(
        blank=True,
        null=True,
        verbose_name="Posledni skoleni",
    )
    professional_competence_next_training = models.DateField(
        blank=True,
        null=True,
        verbose_name="Pristi skoleni",
    )

    tachograph_card_number = models.CharField(max_length=50, blank=True, verbose_name="Cislo karty tachografu")
    tachograph_card_issued = models.DateField(blank=True, null=True, verbose_name="Karta tachografu vydano")
    tachograph_card_valid_until = models.DateField(blank=True, null=True, verbose_name="Karta tachografu platnost do")
    tachograph_card_note = models.TextField(blank=True, verbose_name="Poznamka ke karte tachografu")

    medical_entry_exam_date = models.DateField(blank=True, null=True, verbose_name="Vstupni prohlidka")
    medical_periodic_exam_date = models.DateField(blank=True, null=True, verbose_name="Periodicka prohlidka")
    medical_certificate_valid_until = models.DateField(blank=True, null=True, verbose_name="Platnost posudku")
    medical_restrictions = models.CharField(max_length=255, blank=True, verbose_name="Omezeni zdravotni")
    medical_provider = models.CharField(max_length=120, blank=True, verbose_name="Poskytovatel")

    hds_certificate_number = models.CharField(max_length=50, blank=True, verbose_name="HDS cislo prukazu")
    hds_valid_until = models.DateField(blank=True, null=True, verbose_name="HDS platnost")
    sling_certificate_number = models.CharField(max_length=50, blank=True, verbose_name="Vazac cislo prukazu")
    sling_valid_until = models.DateField(blank=True, null=True, verbose_name="Vazac platnost")
    vzv_certificate_number = models.CharField(max_length=50, blank=True, verbose_name="VZV cislo prukazu")
    vzv_valid_until = models.DateField(blank=True, null=True, verbose_name="VZV platnost")

    machine_tractor = models.BooleanField(default=False, verbose_name="Strojnik traktor")
    machine_loader = models.BooleanField(default=False, verbose_name="Strojnik nakladac")
    machine_skid_loader = models.BooleanField(default=False, verbose_name="Strojnik bobek")
    machine_wheel_loader = models.BooleanField(default=False, verbose_name="Strojnik kolovy nakladac")
    machine_telehandler = models.BooleanField(default=False, verbose_name="Strojnik teleskopicky nakladac")
    machine_mini_loader = models.BooleanField(default=False, verbose_name="Strojnik mini nakladac")
    machine_excavator = models.BooleanField(default=False, verbose_name="Strojnik bagr")
    machine_mini_excavator = models.BooleanField(default=False, verbose_name="Strojnik minibagr")
    machine_backhoe_loader = models.BooleanField(default=False, verbose_name="Strojnik rypadlonakladac")
    machine_unc = models.BooleanField(default=False, verbose_name="Strojnik UNC")
    machine_spreader_plow = models.BooleanField(default=False, verbose_name="Strojnik sypac pluh")
    machine_vzv = models.BooleanField(default=False, verbose_name="Strojnik VZV")
    machine_crane_operator = models.BooleanField(default=False, verbose_name="Jerabnik")
    special_attachments = models.TextField(blank=True, verbose_name="Specialni nastavby")

    allowed_vehicle_rz = models.ManyToManyField(
        VehicleRzProfile,
        blank=True,
        related_name="allowed_drivers",
        verbose_name="Prirazene RZ vozidlo",
    )
    allowed_vehicle_kinds = models.ManyToManyField(
        VehicleKindCatalog,
        blank=True,
        related_name="allowed_drivers",
        verbose_name="Druhy vozidel, ktere muze ridit",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ridic"
        verbose_name_plural = "Ridici"
        ordering = ["personal_number"]

    def __str__(self):
        full_name = " ".join(part for part in [self.title, self.first_name, self.last_name] if part).strip()
        return f"{self.personal_number} - {full_name}" if full_name else self.personal_number
