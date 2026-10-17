from django import forms
from django.utils import timezone

from catalogs.models import ActivityFieldKey, ActivityFieldMode
from waste_docs.activity_fields import get_effective_mode
from waste_docs.models import Pruvodka


class DriverRideUpdateForm(forms.ModelForm):
    mark_completed = forms.BooleanField(
        required=False,
        label="Označit jízdu jako dokončenou",
    )

    class Meta:
        model = Pruvodka
        fields = ("container_number", "container_number_2")
        labels = {
            "container_number": "Číslo kontejneru (1)",
            "container_number_2": "Číslo kontejneru (2)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aid = self.instance.activity_id if getattr(self.instance, "pk", None) else None
        if get_effective_mode(aid, ActivityFieldKey.CONTAINER_1) == ActivityFieldMode.OFF:
            self.fields.pop("container_number", None)
        if get_effective_mode(aid, ActivityFieldKey.CONTAINER_2) == ActivityFieldMode.OFF:
            self.fields.pop("container_number_2", None)
        if self.instance.pk and self.instance.driver_completed_at:
            self.fields.pop("mark_completed", None)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("mark_completed"):
            obj.driver_completed_at = timezone.now()
        if commit:
            obj.save()
        return obj
