from django import forms

from catalogs.models import DriverProfile, VehicleKindCatalog, VehicleRzProfile


class DateInput(forms.DateInput):
    """HTML5 date – hodnota musí být vždy Y-m-d, jinak prohlížeč pole „vyprázdní“ a datum se neuloží."""

    input_type = "date"
    format = "%Y-%m-%d"


class DriverProfileForm(forms.ModelForm):
    class Meta:
        model = DriverProfile
        fields = (
            "last_name",
            "first_name",
            "title",
            "personal_number",
            "phone",
            "job_position",
            "employment_type",
            "start_date",
            "availability_note",
            "driver_license_number",
            "driver_license_groups",
            "driver_license_valid_until",
            "driver_license_restrictions",
            "driver_license_last_check",
            "professional_competence_required",
            "professional_competence_document",
            "professional_competence_valid_until",
            "professional_competence_last_training",
            "professional_competence_next_training",
            "tachograph_card_number",
            "tachograph_card_issued",
            "tachograph_card_valid_until",
            "tachograph_card_note",
            "medical_entry_exam_date",
            "medical_periodic_exam_date",
            "medical_certificate_valid_until",
            "medical_restrictions",
            "medical_provider",
            "hds_certificate_number",
            "hds_valid_until",
            "sling_certificate_number",
            "sling_valid_until",
            "vzv_certificate_number",
            "vzv_valid_until",
            "machine_tractor",
            "machine_loader",
            "machine_skid_loader",
            "machine_wheel_loader",
            "machine_telehandler",
            "machine_mini_loader",
            "machine_excavator",
            "machine_mini_excavator",
            "machine_backhoe_loader",
            "machine_unc",
            "machine_spreader_plow",
            "machine_vzv",
            "machine_crane_operator",
            "special_attachments",
            "allowed_vehicle_rz",
            "allowed_vehicle_kinds",
        )
        labels = {
            "last_name": "Příjmení",
            "first_name": "Jméno",
            "title": "Titul",
            "personal_number": "Osobní číslo",
            "phone": "Telefon",
            "job_position": "Pracovní pozice",
            "employment_type": "Typ poměru",
            "start_date": "Datum nástupu",
            "availability_note": "Poznámka k dostupnosti",
            "driver_license_number": "Číslo ŘP",
            "driver_license_groups": "Skupiny",
            "driver_license_valid_until": "Platnost do",
            "driver_license_restrictions": "Omezení",
            "driver_license_last_check": "Poslední kontrola",
            "professional_competence_required": "Vyžadována",
            "professional_competence_document": "Doklad",
            "professional_competence_valid_until": "Platnost do",
            "professional_competence_last_training": "Poslední školení",
            "professional_competence_next_training": "Příští školení",
            "tachograph_card_number": "Číslo karty",
            "tachograph_card_issued": "Vydáno",
            "tachograph_card_valid_until": "Platnost do",
            "tachograph_card_note": "Poznámka",
            "medical_entry_exam_date": "Vstupní prohlídka",
            "medical_periodic_exam_date": "Periodická prohlídka",
            "medical_certificate_valid_until": "Platnost posudku",
            "medical_restrictions": "Omezení",
            "medical_provider": "Poskytovatel",
            "hds_certificate_number": "Číslo průkazu",
            "hds_valid_until": "Platnost",
            "sling_certificate_number": "Číslo průkazu",
            "sling_valid_until": "Platnost",
            "vzv_certificate_number": "Číslo průkazu",
            "vzv_valid_until": "Platnost",
            "machine_tractor": "Traktor",
            "machine_loader": "Nakladač",
            "machine_skid_loader": "Smykem řízený nakladač (Bobek)",
            "machine_wheel_loader": "Kolový nakladač",
            "machine_telehandler": "Teleskopický nakladač",
            "machine_mini_loader": "Mini nakladač",
            "machine_excavator": "Bagr",
            "machine_mini_excavator": "Minibagr",
            "machine_backhoe_loader": "Rypadlonakladač",
            "machine_unc": "UNC",
            "machine_spreader_plow": "Sypač/pluh",
            "machine_vzv": "VZV",
            "machine_crane_operator": "Jeřábník",
            "special_attachments": "Speciální nástavby",
            "allowed_vehicle_rz": "Přiřazené RZ vozidlo",
            "allowed_vehicle_kinds": "Druhy vozidel, které může řídit",
        }
        widgets = {
            "start_date": DateInput(format="%Y-%m-%d"),
            "driver_license_valid_until": DateInput(format="%Y-%m-%d"),
            "driver_license_last_check": DateInput(format="%Y-%m-%d"),
            "professional_competence_valid_until": DateInput(format="%Y-%m-%d"),
            "professional_competence_last_training": DateInput(format="%Y-%m-%d"),
            "professional_competence_next_training": DateInput(format="%Y-%m-%d"),
            "tachograph_card_issued": DateInput(format="%Y-%m-%d"),
            "tachograph_card_valid_until": DateInput(format="%Y-%m-%d"),
            "medical_entry_exam_date": DateInput(format="%Y-%m-%d"),
            "medical_periodic_exam_date": DateInput(format="%Y-%m-%d"),
            "medical_certificate_valid_until": DateInput(format="%Y-%m-%d"),
            "hds_valid_until": DateInput(format="%Y-%m-%d"),
            "sling_valid_until": DateInput(format="%Y-%m-%d"),
            "vzv_valid_until": DateInput(format="%Y-%m-%d"),
            "allowed_vehicle_rz": forms.SelectMultiple(attrs={"size": 8, "class": "select-multiple"}),
            "allowed_vehicle_kinds": forms.SelectMultiple(attrs={"size": 8, "class": "select-multiple"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _date_input_formats = ["%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d. %m. %Y", "%d. %m. %y"]
        for _name, _field in self.fields.items():
            if isinstance(_field, forms.DateField):
                _field.input_formats = _date_input_formats
        self.fields["allowed_vehicle_rz"].queryset = VehicleRzProfile.objects.select_related("rz").order_by("rz__value")
        from catalogs.services.vehicle_kind_display import bind_vehicle_kind_select_labels

        self.fields["allowed_vehicle_kinds"].queryset = VehicleKindCatalog.objects.order_by("name")
        bind_vehicle_kind_select_labels(self, "allowed_vehicle_kinds")
        self.fields["phone"].widget.attrs.update({"placeholder": "000 000 000"})
        self.fields["driver_license_groups"].widget.attrs.update({"placeholder": "B, C, C+E"})
        self.fields["personal_number"].help_text = "Musí být unikátní (bez duplicity)."
        self.fields["last_name"].widget.attrs.update({"placeholder": "Např. Novák"})
        self.fields["first_name"].widget.attrs.update({"placeholder": "Např. Jan"})
