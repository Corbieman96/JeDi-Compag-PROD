from django import forms

from catalogs.models import SuffixCatalog, WasteTypeCatalog, ZpoDocument
from pio.validators import validate_pio_upload_size


class ZpoDocumentForm(forms.ModelForm):
    class Meta:
        model = ZpoDocument
        fields = ("label", "file", "waste_type", "suffix")
        labels = {
            "label": "Popisek",
            "file": "Soubor ZPO",
            "waste_type": "Druh odpadu",
            "suffix": "Koncovka",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["label"].required = True
        self.fields["waste_type"].required = False
        self.fields["suffix"].required = False
        self.fields["waste_type"].queryset = WasteTypeCatalog.objects.order_by("code", "value")
        self.fields["suffix"].queryset = SuffixCatalog.objects.order_by("value")
        self.fields["file"].widget.attrs["accept"] = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f:
            lower = f.name.lower()
            if not (
                lower.endswith(".pdf")
                or lower.endswith(".jpg")
                or lower.endswith(".jpeg")
                or lower.endswith(".png")
            ):
                raise forms.ValidationError("Soubor musí být PDF, JPG nebo PNG.")
            validate_pio_upload_size(f)
        elif not self.instance.pk:
            raise forms.ValidationError("Vyberte soubor.")
        return f
