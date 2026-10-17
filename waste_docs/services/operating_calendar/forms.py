"""Formulář a formset dnů bez svozu pro /settings/."""

from __future__ import annotations

from django import forms
from django.forms import BaseModelFormSet, modelformset_factory

from customer_requests.models import NoServiceCalendarDay

_DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y")


def _date_widget():
    return forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})


class NoServiceCalendarDayForm(forms.ModelForm):
    closed_date = forms.DateField(
        required=False,
        input_formats=_DATE_INPUT_FORMATS,
        widget=_date_widget(),
        label="Den bez svozu",
    )
    redirect_date = forms.DateField(
        required=False,
        input_formats=_DATE_INPUT_FORMATS,
        widget=_date_widget(),
        label="Přesunout na",
    )

    class Meta:
        model = NoServiceCalendarDay
        fields = ("closed_date", "redirect_date", "note")
        widgets = {
            "note": forms.TextInput(attrs={"maxlength": "120", "placeholder": "Svátek"}),
        }

    def clean(self):
        cleaned = super().clean()
        closed = cleaned.get("closed_date")
        redirect = cleaned.get("redirect_date")
        if closed and redirect and redirect == closed:
            self.add_error("redirect_date", "Přesunout na musí být jiný den než den bez svozu.")
        return cleaned


class BaseNoServiceCalendarDayFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()
        seen: set = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            data = form.cleaned_data
            if not data or data.get("DELETE"):
                continue
            day = data.get("closed_date")
            if not day:
                continue
            if day in seen:
                raise forms.ValidationError("Stejný den bez svozu je v tabulce víckrát.")
            seen.add(day)


NoServiceCalendarDayFormSet = modelformset_factory(
    NoServiceCalendarDay,
    form=NoServiceCalendarDayForm,
    formset=BaseNoServiceCalendarDayFormSet,
    extra=3,
    can_delete=True,
)
