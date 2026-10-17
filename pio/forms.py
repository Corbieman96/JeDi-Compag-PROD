from django import forms

from pio.models import PioRevision
from pio.validators import validate_pio_upload_size


class PioRevisionUploadForm(forms.ModelForm):
    class Meta:
        model = PioRevision
        fields = ("file", "note")
        labels = {
            "file": "Soubor (PDF / JPG / PNG)",
            "note": "Poznámka (volitelně)",
        }
        widgets = {
            "file": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}),
        }

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f:
            validate_pio_upload_size(f)
        return f
