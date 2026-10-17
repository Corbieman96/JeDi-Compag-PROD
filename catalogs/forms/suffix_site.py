from django import forms
from django.urls import reverse
from django.utils.html import format_html

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    SuffixCatalog,
    SuffixSiteProfile,
    WasteTypeCatalog,
)
from catalogs.services import normalize_czech_address
from catalogs.waste_catalog_code import normalize_waste_catalog_code


class SuffixSiteProfileForm(forms.ModelForm):
    suffix_value = forms.CharField(label="Koncovka", max_length=255)
    ico_value = forms.CharField(label="IČO", max_length=8, required=False)
    address_value = forms.CharField(label="Adresa", max_length=255, required=False)
    latitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    longitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())

    class Meta:
        model = SuffixSiteProfile
        fields = (
            "name",
            "icz",
            "facility_type",
            "zuj",
            "accepted_waste_types",
            "produced_waste_types",
        )
        labels = {
            "name": "Název",
            "icz": "IČZ",
            "facility_type": "Typ zařízení",
            "zuj": "ZUJ",
            "accepted_waste_types": "Odpad, který přijímá",
            "produced_waste_types": "Odpad, který vyprodukuje",
        }
        widgets = {
            "accepted_waste_types": forms.SelectMultiple(attrs={"size": 12}),
            "produced_waste_types": forms.SelectMultiple(attrs={"size": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        def _waste_label(obj: WasteTypeCatalog) -> str:
            code = normalize_waste_catalog_code(obj.code)
            value = (obj.value or "").strip()
            if code and value:
                return f"{code} — {value}"
            return code or value or str(obj.pk)

        self.fields["accepted_waste_types"].required = True
        self.fields["produced_waste_types"].required = True
        self.fields["accepted_waste_types"].queryset = WasteTypeCatalog.objects.order_by("value")
        self.fields["produced_waste_types"].queryset = WasteTypeCatalog.objects.order_by("value")
        self.fields["accepted_waste_types"].label_from_instance = _waste_label
        self.fields["produced_waste_types"].label_from_instance = _waste_label
        self.fields["accepted_waste_types"].help_text = "Podržte Ctrl (Cmd) pro výběr více položek."
        self.fields["produced_waste_types"].help_text = "Podržte Ctrl (Cmd) pro výběr více položek."
        if self.instance and self.instance.pk:
            self.fields["suffix_value"].initial = self.instance.suffix.value
            self.fields["ico_value"].initial = self.instance.ico.value if self.instance.ico else ""
            self.fields["address_value"].initial = self.instance.address.value if self.instance.address else ""

    def clean_ico_value(self):
        ico = (self.cleaned_data.get("ico_value") or "").strip()
        if not ico:
            return ""
        if not ico.isdigit() or len(ico) != 8:
            raise forms.ValidationError("IČO musí mít přesně 8 číslic.")
        return ico

    def clean_address_value(self):
        return normalize_czech_address(self.cleaned_data.get("address_value") or "")

    def clean_suffix_value(self):
        value = (self.cleaned_data.get("suffix_value") or "").strip()
        if not value:
            raise forms.ValidationError("Zadejte koncovku.")
        # Při úpravě nesmí cílový text patřit jinému řádku SuffixCatalog (unique value).
        if self.instance and self.instance.pk and self.instance.suffix_id:
            if (
                SuffixCatalog.objects.exclude(pk=self.instance.suffix_id)
                .filter(value=value)
                .exists()
            ):
                raise forms.ValidationError(
                    "Koncovka s tímto textem už v číselníku existuje (u jiného záznamu). "
                    "Zadejte jiný text nebo upravte příslušný záznam v číselníku koncovek."
                )
        suffix_obj = SuffixCatalog.objects.filter(value=value).first()
        if not suffix_obj:
            return value
        current_suffix_id = self.instance.suffix_id if self.instance and self.instance.pk else None
        if current_suffix_id and suffix_obj.pk == current_suffix_id:
            return value
        existing_profile = SuffixSiteProfile.objects.filter(suffix=suffix_obj).only("id").first()
        if existing_profile:
            edit_url = reverse("catalogs:suffix_edit", args=[existing_profile.id])
            raise forms.ValidationError(
                format_html(
                    "Profil s touto koncovkou už existuje (ID: {}). "
                    '<a href="{}">Otevřít existující záznam</a>.',
                    existing_profile.id,
                    edit_url,
                )
            )
        return value

    def clean_accepted_waste_types(self):
        values = self.cleaned_data.get("accepted_waste_types")
        if not values:
            raise forms.ValidationError("Vyberte alespoň jeden odpad, který přijímá.")
        return values

    def clean_produced_waste_types(self):
        values = self.cleaned_data.get("produced_waste_types")
        if not values:
            raise forms.ValidationError("Vyberte alespoň jeden odpad, který vyprodukuje.")
        return values

    def save(self, commit=True):
        suffix_value = (self.cleaned_data.get("suffix_value") or "").strip()
        ico_value = (self.cleaned_data.get("ico_value") or "").strip()
        address_value = (self.cleaned_data.get("address_value") or "").strip()

        profile = super().save(commit=False)
        # Úprava: přepsat text na existujícím řádku SuffixCatalog (stejné PK), ne založit nový řádek.
        if profile.pk and profile.suffix_id:
            sc = SuffixCatalog.objects.get(pk=profile.suffix_id)
            if sc.value != suffix_value:
                sc.value = suffix_value
                sc.save(update_fields=["value"])
            profile.suffix = sc
        else:
            suffix, _ = SuffixCatalog.objects.get_or_create(value=suffix_value)
            profile.suffix = suffix

        profile.ico = IcoCatalog.objects.get_or_create(value=ico_value)[0] if ico_value else None
        profile.address = AddressCatalog.objects.get_or_create(value=address_value)[0] if address_value else None
        profile.latitude = self.cleaned_data.get("latitude") or None
        profile.longitude = self.cleaned_data.get("longitude") or None

        if commit:
            profile.save()
            self.save_m2m()
        return profile
