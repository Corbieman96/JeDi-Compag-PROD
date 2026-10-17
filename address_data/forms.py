from django import forms

from catalogs.services.address import normalize_czech_address, normalize_czech_postal_code

from .models import OfflineAddress


class OfflineAddressForm(forms.ModelForm):
    class Meta:
        model = OfflineAddress
        fields = ("label", "city", "street", "house_number", "postal_code", "lat", "lng")

    def clean_label(self):
        return normalize_czech_address((self.cleaned_data.get("label") or "").strip())

    def clean_postal_code(self):
        return normalize_czech_postal_code((self.cleaned_data.get("postal_code") or "").strip())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].required = True
        self.fields["street"].required = True
        self.fields["house_number"].required = True

    def save(self, commit=True):
        item = super().save(commit=False)
        if item.street and item.house_number and item.city:
            item.label = normalize_czech_address(
                f"{item.street} {item.house_number}, {item.postal_code} {item.city}".replace("  ", " ").strip()
            ).strip(", ")
        item.city_norm = normalize_czech_address(item.city).lower()
        item.street_norm = normalize_czech_address(item.street).lower()
        item.label_norm = normalize_czech_address(item.label).lower()
        if commit:
            item.save()
        return item
