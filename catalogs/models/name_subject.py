from __future__ import annotations

from django.db import models

from .catalogs import AddressCatalog, IcoCatalog, NameCatalog, SuffixCatalog, WasteTypeCatalog
from .zpo_document import ZpoDocument
from .vehicle_rz import VehicleKindCatalog


class NameSubjectProfile(models.Model):
    name = models.OneToOneField(NameCatalog, on_delete=models.CASCADE, related_name="subject_profile")
    ico = models.ForeignKey(
        IcoCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subject_profiles",
    )
    company_name = models.CharField(max_length=255, verbose_name="Jméno společnosti")
    is_municipality = models.BooleanField(default=False, verbose_name="Jedná se o obec")
    nitropodnikovy_subjekt = models.BooleanField(
        default=False,
        verbose_name="Nitropodnikový subjekt",
        help_text="Zaškrtněte u vnitropodnikového subjektu.",
    )
    allowed_waste_types = models.ManyToManyField(
        WasteTypeCatalog,
        blank=True,
        related_name="subject_profiles",
        verbose_name="Povolené odpady",
        help_text="Odvozeno z párů odpad–koncovka (nebo dříve ručně).",
    )
    allowed_suffixes = models.ManyToManyField(
        SuffixCatalog,
        blank=True,
        related_name="subject_profiles",
        verbose_name="Povolené koncovky",
        help_text="Odvozeno z párů odpad–koncovka (nebo dříve ručně).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subjekt F/P osoby"
        verbose_name_plural = "Subjekty F/P osoby"
        ordering = ["company_name"]

    def __str__(self):
        return f"{self.company_name} ({self.ico.value if self.ico else 'bez IČO'})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from catalogs.services.subject_satellites import ensure_subject_satellites

        ensure_subject_satellites(self)

    # --- Delegace na satelitní profily (zpětná kompatibilita pro .contact_phone atd.) ---
    @property
    def contact_phone(self) -> str:
        if not self.pk:
            return ""
        from catalogs.models import SubjectContactProfile

        try:
            return self.contact_profile.contact_phone
        except SubjectContactProfile.DoesNotExist:
            from catalogs.services.subject_satellites import ensure_subject_satellites

            ensure_subject_satellites(self)
            return self.contact_profile.contact_phone

    @contact_phone.setter
    def contact_phone(self, value: str) -> None:
        if not self.pk:
            return
        from catalogs.services.subject_satellites import ensure_subject_satellites

        ensure_subject_satellites(self)
        self.contact_profile.contact_phone = value or ""

    @property
    def contact_note(self) -> str:
        if not self.pk:
            return ""
        from catalogs.models import SubjectContactProfile

        try:
            return self.contact_profile.contact_note
        except SubjectContactProfile.DoesNotExist:
            from catalogs.services.subject_satellites import ensure_subject_satellites

            ensure_subject_satellites(self)
            return self.contact_profile.contact_note

    @contact_note.setter
    def contact_note(self, value: str) -> None:
        if not self.pk:
            return
        from catalogs.services.subject_satellites import ensure_subject_satellites

        ensure_subject_satellites(self)
        self.contact_profile.contact_note = value or ""

    def _address(self):
        from catalogs.models import SubjectAddressProfile

        try:
            return self.address_profile
        except SubjectAddressProfile.DoesNotExist:
            from catalogs.services.subject_satellites import ensure_subject_satellites

            ensure_subject_satellites(self)
            return self.address_profile

    @property
    def facility_address(self):
        if not self.pk:
            return None
        return self._address().facility_address

    @facility_address.setter
    def facility_address(self, value) -> None:
        if not self.pk:
            return
        self._address().facility_address = value

    @property
    def facility_address_id(self):
        if not self.pk:
            return None
        return self._address().facility_address_id

    @facility_address_id.setter
    def facility_address_id(self, value) -> None:
        if not self.pk:
            return
        self._address().facility_address_id = value

    @property
    def fulfillment_address(self):
        if not self.pk:
            return None
        return self._address().fulfillment_address

    @fulfillment_address.setter
    def fulfillment_address(self, value) -> None:
        if not self.pk:
            return
        self._address().fulfillment_address = value

    @property
    def fulfillment_address_id(self):
        if not self.pk:
            return None
        return self._address().fulfillment_address_id

    @fulfillment_address_id.setter
    def fulfillment_address_id(self, value) -> None:
        if not self.pk:
            return
        self._address().fulfillment_address_id = value

    @property
    def facility_latitude(self):
        if not self.pk:
            return None
        return self._address().facility_latitude

    @facility_latitude.setter
    def facility_latitude(self, value) -> None:
        if not self.pk:
            return
        self._address().facility_latitude = value

    @property
    def facility_longitude(self):
        if not self.pk:
            return None
        return self._address().facility_longitude

    @facility_longitude.setter
    def facility_longitude(self, value) -> None:
        if not self.pk:
            return
        self._address().facility_longitude = value

    @property
    def fulfillment_latitude(self):
        if not self.pk:
            return None
        return self._address().fulfillment_latitude

    @fulfillment_latitude.setter
    def fulfillment_latitude(self, value) -> None:
        if not self.pk:
            return
        self._address().fulfillment_latitude = value

    @property
    def fulfillment_longitude(self):
        if not self.pk:
            return None
        return self._address().fulfillment_longitude

    @fulfillment_longitude.setter
    def fulfillment_longitude(self, value) -> None:
        if not self.pk:
            return
        self._address().fulfillment_longitude = value

    @property
    def fulfillment_orp(self) -> str:
        if not self.pk:
            return ""
        return self._address().fulfillment_orp or ""

    @fulfillment_orp.setter
    def fulfillment_orp(self, value: str) -> None:
        if not self.pk:
            return
        self._address().fulfillment_orp = value or ""

    @property
    def fulfillment_iczuj(self) -> str:
        if not self.pk:
            return ""
        return self._address().fulfillment_iczuj or ""

    @fulfillment_iczuj.setter
    def fulfillment_iczuj(self, value: str) -> None:
        if not self.pk:
            return
        self._address().fulfillment_iczuj = value or ""

    def _yard(self):
        from catalogs.models import SubjectYardSettings

        try:
            return self.yard_settings
        except SubjectYardSettings.DoesNotExist:
            from catalogs.services.subject_satellites import ensure_subject_satellites

            ensure_subject_satellites(self)
            return self.yard_settings

    @property
    def is_collection_yard(self) -> bool:
        if not self.pk:
            return False
        return self._yard().is_collection_yard

    @is_collection_yard.setter
    def is_collection_yard(self, value: bool) -> None:
        if not self.pk:
            return
        self._yard().is_collection_yard = bool(value)

    @property
    def yard_allow_pruvodka(self) -> bool:
        if not self.pk:
            return False
        return self._yard().yard_allow_pruvodka

    @yard_allow_pruvodka.setter
    def yard_allow_pruvodka(self, value: bool) -> None:
        if not self.pk:
            return
        self._yard().yard_allow_pruvodka = bool(value)

    @property
    def yard_allow_matrix(self) -> bool:
        if not self.pk:
            return False
        return self._yard().yard_allow_matrix

    @yard_allow_matrix.setter
    def yard_allow_matrix(self, value: bool) -> None:
        if not self.pk:
            return
        self._yard().yard_allow_matrix = bool(value)

    @property
    def yard_svoz_dispatch_group(self) -> str:
        if not self.pk:
            return ""
        return self._yard().yard_svoz_dispatch_group or ""

    @yard_svoz_dispatch_group.setter
    def yard_svoz_dispatch_group(self, value: str) -> None:
        if not self.pk:
            return
        self._yard().yard_svoz_dispatch_group = value or ""

    @property
    def yard_svoz_ratio_min_containers(self) -> int:
        if not self.pk:
            return 5
        return int(self._yard().yard_svoz_ratio_min_containers or 5)

    @yard_svoz_ratio_min_containers.setter
    def yard_svoz_ratio_min_containers(self, value: int) -> None:
        if not self.pk:
            return
        try:
            parsed = max(1, int(value))
        except (TypeError, ValueError):
            parsed = 5
        self._yard().yard_svoz_ratio_min_containers = parsed

    def _zpo(self):
        from catalogs.models import SubjectZpoSettings

        try:
            return self.zpo_settings
        except SubjectZpoSettings.DoesNotExist:
            from catalogs.services.subject_satellites import ensure_subject_satellites

            ensure_subject_satellites(self)
            return self.zpo_settings

    @property
    def system_generates_zpo(self) -> bool:
        if not self.pk:
            return True
        return self._zpo().system_generates_zpo

    @system_generates_zpo.setter
    def system_generates_zpo(self, value: bool) -> None:
        if not self.pk:
            return
        self._zpo().system_generates_zpo = bool(value)

    def _pio(self):
        from catalogs.models import SubjectPioProfile

        try:
            return self.pio_profile
        except SubjectPioProfile.DoesNotExist:
            from catalogs.services.subject_satellites import ensure_subject_satellites

            ensure_subject_satellites(self)
            return self.pio_profile

    @property
    def pio_officer_name(self) -> str:
        if not self.pk:
            return ""
        return self._pio().pio_officer_name or ""

    @pio_officer_name.setter
    def pio_officer_name(self, value: str) -> None:
        if not self.pk:
            return
        self._pio().pio_officer_name = value or ""

    @property
    def pio_officer_phone(self) -> str:
        if not self.pk:
            return ""
        return self._pio().pio_officer_phone or ""

    @pio_officer_phone.setter
    def pio_officer_phone(self, value: str) -> None:
        if not self.pk:
            return
        self._pio().pio_officer_phone = value or ""

    @property
    def pio_officer_email(self) -> str:
        if not self.pk:
            return ""
        return self._pio().pio_officer_email or ""

    @pio_officer_email.setter
    def pio_officer_email(self, value: str) -> None:
        if not self.pk:
            return
        self._pio().pio_officer_email = value or ""

    @property
    def pio_waste_type(self):
        if not self.pk:
            return None
        return self._pio().pio_waste_type

    @pio_waste_type.setter
    def pio_waste_type(self, value) -> None:
        if not self.pk:
            return
        self._pio().pio_waste_type = value

    @property
    def pio_waste_type_id(self):
        if not self.pk:
            return None
        return self._pio().pio_waste_type_id

    @pio_waste_type_id.setter
    def pio_waste_type_id(self, value) -> None:
        if not self.pk:
            return
        self._pio().pio_waste_type_id = value

    @property
    def pio_suffix(self):
        if not self.pk:
            return None
        return self._pio().pio_suffix

    @pio_suffix.setter
    def pio_suffix(self, value) -> None:
        if not self.pk:
            return
        self._pio().pio_suffix = value

    @property
    def pio_suffix_id(self):
        if not self.pk:
            return None
        return self._pio().pio_suffix_id

    @pio_suffix_id.setter
    def pio_suffix_id(self, value) -> None:
        if not self.pk:
            return
        self._pio().pio_suffix_id = value

    @property
    def pio_outside_map_lat(self):
        if not self.pk:
            return None
        return self._pio().pio_outside_map_lat

    @pio_outside_map_lat.setter
    def pio_outside_map_lat(self, value) -> None:
        if not self.pk:
            return
        self._pio().pio_outside_map_lat = value

    @property
    def pio_outside_map_lng(self):
        if not self.pk:
            return None
        return self._pio().pio_outside_map_lng

    @pio_outside_map_lng.setter
    def pio_outside_map_lng(self, value) -> None:
        if not self.pk:
            return
        self._pio().pio_outside_map_lng = value

    @property
    def pio_outside_map_orp(self) -> str:
        if not self.pk:
            return ""
        return self._pio().pio_outside_map_orp or ""

    @pio_outside_map_orp.setter
    def pio_outside_map_orp(self, value: str) -> None:
        if not self.pk:
            return
        self._pio().pio_outside_map_orp = value or ""

    @property
    def pio_outside_map_iczuj(self) -> str:
        if not self.pk:
            return ""
        return self._pio().pio_outside_map_iczuj or ""

    @pio_outside_map_iczuj.setter
    def pio_outside_map_iczuj(self, value: str) -> None:
        if not self.pk:
            return
        self._pio().pio_outside_map_iczuj = value or ""


class NameSubjectWasteSuffixPair(models.Model):
    """Jeden řádek = jeden povolený druh odpadu vázaný na konkrétní koncovku u subjektu."""

    class YardContainerKind(models.TextChoices):
        UNSPECIFIED = "", "—"
        STANDARD = "standard", "Standardní kontejner"
        LIS = "lis", "Lis"
        VELKOOBJEM = "velkoobjem", "Velkoobjem"
        OTHER = "other", "Jiný"

    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="waste_suffix_pairs",
        verbose_name="Subjekt",
    )
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.CASCADE,
        related_name="name_subject_suffix_pairs",
        verbose_name="Druh odpadu",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.CASCADE,
        related_name="name_subject_waste_pairs",
        verbose_name="Koncovka",
    )
    zpo = models.ForeignKey(
        ZpoDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pairs",
        verbose_name="ZPO z knihovny",
    )
    suppress_system_zpo = models.BooleanField(
        default=False,
        verbose_name="Vypnout systémové ZPO u tohoto páru",
        help_text="Pokud je zapnuto, u jízd s tímto odpadem a koncovkou se negeneruje systémové ZPO (přepíše obecné nastavení subjektu).",
    )
    pio_document = models.FileField(
        upload_to="name_subject_pairs/pio/",
        blank=True,
        null=True,
        verbose_name="PIO dokument",
    )
    other_document = models.FileField(
        upload_to="name_subject_pairs/other/",
        blank=True,
        null=True,
        verbose_name="Jiný dokument",
    )
    contract_number = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Číslo smlouvy",
    )
    ride_note = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Poznámka",
        help_text="Po výběru odpadu a koncovky v průvodce se propsíše do pole Poznámka jízdy.",
    )
    fulfillment_address = models.ForeignKey(
        AddressCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pair_fulfillment_rows",
        verbose_name="Adresa plnění (volitelná)",
        help_text="Prázdné = použije se centrální adresa plnění subjektu.",
    )
    yard_svoz_enabled = models.BooleanField(
        default=False,
        verbose_name="Svoz: řádek v matici požadavků",
        help_text="Pár se nabídne sběrnému dvoru k zadání kontejnerů (fronta předprůvodek).",
    )
    yard_pruvodka_enabled = models.BooleanField(
        default=False,
        verbose_name="Průvodka přímo z dvora",
        help_text="Uživatel s rolí Sběrný dvůr smí založit průvodku pro tento pár odpad + koncovka.",
    )
    yard_vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yard_waste_suffix_pairs",
        verbose_name="Druh vozidla pro svoz (hlavní)",
        help_text="Synchronizuje se z prvního vybraného druhu v seznamu níže; pro plán a úkoly.",
    )
    yard_vehicle_kinds = models.ManyToManyField(
        VehicleKindCatalog,
        blank=True,
        related_name="yard_waste_suffix_pairs_multi",
        verbose_name="Druhy vozidla pro svoz",
        help_text="Na stránce subjektu vyberte jeden nebo více druhů (např. Hák i 3H) — bez stromu v číselníku.",
    )
    yard_svoz_activity = models.ForeignKey(
        "catalogs.ActivityCatalog",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yard_svoz_waste_suffix_pairs",
        verbose_name="Činnost (svoz z dvora)",
        help_text="Povinné u zapnutého svozu — jaká činnost se u kontejneru provádí (předvyplní se v průvodce).",
    )
    yard_pruvodka_activity = models.ForeignKey(
        "catalogs.ActivityCatalog",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yard_pruvodka_waste_suffix_pairs",
        verbose_name="Činnost (průvodka z dvora)",
        help_text="Při zapnuté průvodce z dvora — činnost v průvodce. Prázdné = použije se „Činnost (svoz)“, pokud je vyplněná.",
    )
    yard_container_kind = models.CharField(
        max_length=20,
        choices=YardContainerKind.choices,
        default=YardContainerKind.UNSPECIFIED,
        blank=True,
        verbose_name="Druh kontejneru (nápověda)",
        help_text="Zobrazení u matice požadavku; volitelné.",
    )
    yard_svoz_display_label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Název v matici požadavku",
        help_text="Vlastní text pro sběrný dvůr u řádku se zapnutým svozem; prázdné = zobrazit druh odpadu z číselníku. "
        "Ukládají se stále druh odpadu, koncovka, druh vozidla a kontejnery.",
    )
    yard_dispatch_note_title = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Název poznámky (dispečer)",
        help_text="Název jednorázové poznámky v panelu dispečera. Použije se jen při zapnuté volbě „Poznámka pro dispečera“ níže.",
    )
    yard_dispatch_note_text = models.TextField(
        blank=True,
        verbose_name="Text poznámky (dispečer)",
        help_text="Volitelná šablona textu pro dispečera; po hlášení se doplní o kontejnery a poznámku ze sloupce v matici.",
    )
    yard_dispatch_note_enabled = models.BooleanField(
        default=False,
        verbose_name="Poznámka pro dispečera",
        help_text="Po hlášení ze sběrného dvora u tohoto řádku matice vytvořit jednorázovou poznámku "
        "v panelu dispečera (název a text výše). Bez zaškrtnutí se poznámka nezakládá.",
    )
    yard_svoz_auto_assign_driver = models.BooleanField(
        default=True,
        verbose_name="Běžný svoz (řádek jde do plánu dvora)",
        help_text="Vypněte u výjimky — řádek nepatří do běžného fondu řidičů dvora. Pro tento řádek musí být v „Plánu svozů“ na daný den vyplněni řidiči ve sloupci „Výjimky“ (jiný řidič než běžný plán).",
    )
    yard_svoz_exception_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Výjimka — slot plánu (V1–V4)",
        help_text="Povinné u výjimky (vypnutý běžný svoz): který sloupec V1–V4 v Plánu svozů obsluhuje kontejnery z tohoto řádku matice. "
        "Unikátní pro dvůr a hlavní druh vozidla řádku.",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Pořadí řádků",
        help_text="Pořadí v tabulce a v matici požadavku na svoz (přetahováním řádků v úpravě subjektu).",
    )

    def effective_yard_pruvodka_activity_id(self) -> int | None:
        """Činnost pro průvodku z dvora: vlastní pole, případně převzetí ze svozu."""
        if self.yard_pruvodka_activity_id:
            return self.yard_pruvodka_activity_id
        return self.yard_svoz_activity_id

    class Meta:
        verbose_name = "Pár odpad–koncovka u subjektu"
        verbose_name_plural = "Páry odpad–koncovka u subjektu"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.waste_type} → {self.suffix.value}"
