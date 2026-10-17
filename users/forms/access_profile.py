from django import forms

from catalogs.catalog_nav_registry import catalog_index_rows
from catalogs.models import NameSubjectProfile
from users.forms.widgets.sberny_dvur_subject_select import SbernyDvurSubjectSelectWidget
from users.models import UserAccessProfile

_PROFILE_CORE_FIELDS = (
    "can_edit_existing_pruvodka",
    "can_create_pruvodka",
    "can_delete_all_pruvodky",
    "can_manage_dashboard_notes",
    "driver_profile",
    "sberny_dvur_subject",
    "can_toggle_subject_is_municipality",
    "can_toggle_subject_collection_yard",
    "can_toggle_subject_yard_allow_pruvodka",
    "can_toggle_subject_yard_allow_matrix",
    "can_toggle_subject_dispatch_group",
    "can_toggle_subject_nitropodnikovy",
    "can_toggle_subject_system_generates_zpo",
    "export_pio_profile",
    "nav_dashboard",
    "nav_pruvodky",
    "nav_customer_requests",
    "nav_invoice_queue",
    "nav_catalogs",
    "nav_settings",
    "nav_address_data",
    "nav_reports",
)

SUBJECT_TOGGLE_PERMISSION_FIELDS = (
    "can_toggle_subject_is_municipality",
    "can_toggle_subject_collection_yard",
    "can_toggle_subject_yard_allow_pruvodka",
    "can_toggle_subject_yard_allow_matrix",
    "can_toggle_subject_dispatch_group",
    "can_toggle_subject_nitropodnikovy",
    "can_toggle_subject_system_generates_zpo",
)


class UserAccessProfileForm(forms.ModelForm):
    """Jádro profilu + dynamická pole catnav_<slug> pro řádky na /catalogs/."""

    CORE_FIELDS = _PROFILE_CORE_FIELDS

    class Meta:
        model = UserAccessProfile
        fields = _PROFILE_CORE_FIELDS
        labels = {
            "can_edit_existing_pruvodka": "Smí upravovat existující jízdy",
            "can_create_pruvodka": "Smí založit novou jízdu",
            "can_delete_all_pruvodky": "Smí mazat jízdy (včetně „Smazat jízdu (bezpečně)“)",
            "can_manage_dashboard_notes": "Smí přidávat a upravovat denní poznámky (dashboard)",
            "driver_profile": "Propojený řidič (portál v telefonu)",
            "sberny_dvur_subject": "Subjekt sběrného dvora (F/P)",
            "can_toggle_subject_is_municipality": "Jedná se o obec",
            "can_toggle_subject_collection_yard": "Lokalita sběrného dvora",
            "can_toggle_subject_yard_allow_pruvodka": "Povolit průvodku z dvora",
            "can_toggle_subject_yard_allow_matrix": "Povolit matici požadavků",
            "can_toggle_subject_dispatch_group": "Skupina v plánu svozů",
            "can_toggle_subject_nitropodnikovy": "Nitropodnikový subjekt",
            "can_toggle_subject_system_generates_zpo": "Generovat systémové ZPO k jízdám",
            "export_pio_profile": "PIO — profilová šablona (.xlsx) u subjektu F/P",
            "nav_dashboard": "Zobrazení: Dashboard (menu)",
            "nav_pruvodky": "Zobrazení: Jízdy (menu)",
            "nav_catalogs": "Zobrazení: Číselníky (menu)",
            "nav_customer_requests": "Zobrazení: Požadavky (menu)",
            "nav_invoice_queue": "Zobrazení: Schvalování záloh (menu)",
            "nav_settings": "Zobrazení: Nastavení",
            "nav_address_data": "Zobrazení: Adresy (offline)",
            "nav_reports": "Zobrazení: Reporty",
        }
        help_texts = {
            "sberny_dvur_subject": "Začněte psát název firmy, IČO nebo F/P jméno (min. 2 znaky). Položky se značkou [SBĚR] mají zapnutou lokalitu sběrného dvora.",
            "can_create_pruvodka": "Platí pro tlačítko Nová jízda, formulář, založení ze sběrného dvora i automatické založení z úkolu svozu.",
            "can_delete_all_pruvodky": "Pro administrátora zapne i akci „Smazat jízdu (bezpečně)“ na detailu jízdy.",
            "nav_catalogs": "Odkaz v horní liště. Jednotlivé řádky v přehledu číselníků nastavte níže.",
            "nav_dashboard": "Odkaz v horní liště (stejně jako u ostatních položek menu).",
            "nav_pruvodky": "Odkaz Jízdy v menu a přístup na /waste-docs/ (seznam a detail jen pro čtení, pokud není oprávnění k úpravě).",
            "nav_customer_requests": "Odkaz v horní liště na požadavky.",
            "nav_invoice_queue": "Odkaz v horní liště na schvalovací frontu záloh.",
            "can_toggle_subject_system_generates_zpo": "Výchozí: zapnuto. Vypněte, pokud uživatel nemá mít možnost toto pole u subjektu měnit.",
            "export_pio_profile": "Dědit z role = hodnota z Nastavení (tabulka Oprávnění). Vždy povolit / Vypnout přepíše výchozí roli.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        subj = self.fields.get("sberny_dvur_subject")
        if subj:
            subj.queryset = NameSubjectProfile.objects.all()
            subj.required = False
            subj.widget = SbernyDvurSubjectSelectWidget()
        drv = self.fields.get("driver_profile")
        if drv:
            from catalogs.models import DriverProfile

            drv.queryset = DriverProfile.objects.order_by("last_name", "first_name", "personal_number")
            drv.required = False
        overrides = {}
        if self.instance and getattr(self.instance, "pk", None):
            raw = self.instance.catalog_item_nav
            if isinstance(raw, dict):
                overrides = raw
        allowed = {c[0] for c in UserAccessProfile.NavOverride.choices}
        catnav_names = []
        for slug, label in catalog_index_rows():
            fname = f"catnav_{slug}"
            initial = overrides.get(slug, UserAccessProfile.NavOverride.INHERIT)
            if initial not in allowed:
                initial = UserAccessProfile.NavOverride.INHERIT
            self.fields[fname] = forms.ChoiceField(
                label=f'Číselníky — řádek „{label}“',
                choices=UserAccessProfile.NavOverride.choices,
                initial=initial,
                required=True,
            )
            catnav_names.append(fname)
        self.order_fields(
            [
                "can_edit_existing_pruvodka",
                "can_create_pruvodka",
                "can_delete_all_pruvodky",
                "can_manage_dashboard_notes",
                "driver_profile",
                "sberny_dvur_subject",
                "can_toggle_subject_is_municipality",
                "can_toggle_subject_collection_yard",
                "can_toggle_subject_yard_allow_pruvodka",
                "can_toggle_subject_yard_allow_matrix",
                "can_toggle_subject_dispatch_group",
                "can_toggle_subject_nitropodnikovy",
                "can_toggle_subject_system_generates_zpo",
                "export_pio_profile",
                "nav_dashboard",
                "nav_pruvodky",
                "nav_customer_requests",
                "nav_invoice_queue",
                "nav_catalogs",
                *catnav_names,
                "nav_settings",
                "nav_address_data",
                "nav_reports",
            ]
        )

    @classmethod
    def core_profile_keys(cls):
        return cls.CORE_FIELDS

    @classmethod
    def catalog_overrides_from_cleaned(cls, cleaned):
        out = {}
        for slug, _ in catalog_index_rows():
            key = f"catnav_{slug}"
            if key in cleaned:
                out[slug] = cleaned[key]
        return out
