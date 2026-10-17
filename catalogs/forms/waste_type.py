from django import forms

from catalogs.models import WasteTypeCatalog
from catalogs.waste_catalog_code import normalize_waste_catalog_code


class WasteTypeCatalogForm(forms.ModelForm):
    class Meta:
        model = WasteTypeCatalog
        fields = ("code", "value", "category", "description_fo", "description_po")
        labels = {
            "code": "Kód odpadu",
            "value": "Název odpadu",
            "category": "Kategorie",
            "description_fo": "Popis odpadu pro FO",
            "description_po": "Popis odpadu pro PO",
        }

    def clean_code(self):
        raw = (self.cleaned_data.get("code") or "").strip()
        normalized = normalize_waste_catalog_code(raw)
        if not normalized:
            raise forms.ValidationError("Zadejte platný kód odpadu (např. 02 07 05 nebo 020705).")
        return normalized
