from __future__ import annotations

from django import forms

from waste_docs.forms.customer_request import WEEKDAY_CHOICES


class SeriesDefinitionForm(forms.Form):
    recurrence_weekdays_pick = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Dny opakování",
    )
    recurrence_until = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=True,
        label="Opakovat do",
    )

    def weekdays_csv(self) -> str:
        picked = self.cleaned_data.get("recurrence_weekdays_pick") or []
        return ",".join(sorted(picked, key=int))


class SeriesShiftForm(forms.Form):
    delta_days = forms.IntegerField(
        label="Posun o dny",
        help_text="Kladné = později, záporné = dříve. Jen otevřené / vybrané.",
    )


class SeriesCancelSelectedForm(forms.Form):
    reason = forms.CharField(
        max_length=500,
        required=True,
        label="Důvod zrušení",
        widget=forms.TextInput(attrs={"style": "width:100%;max-width:36rem;"}),
    )
    occurrence_ids = forms.CharField(required=False, widget=forms.HiddenInput)


class SeriesCancelAllForm(forms.Form):
    reason = forms.CharField(
        max_length=500,
        required=True,
        label="Důvod zrušení",
        widget=forms.TextInput(attrs={"style": "width:100%;max-width:36rem;"}),
    )
    from_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Od data (volitelné)",
        help_text="Prázdné = všechna otevřená.",
    )


class SeriesCancelRangeForm(forms.Form):
    reason = forms.CharField(
        max_length=500,
        required=True,
        label="Důvod zrušení",
        widget=forms.Textarea(attrs={"rows": 2, "style": "width:100%;max-width:36rem;"}),
    )
    from_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Od",
    )
    to_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Do",
    )

    def clean(self):
        cleaned = super().clean()
        from_date = cleaned.get("from_date")
        to_date = cleaned.get("to_date")
        if from_date and to_date and from_date > to_date:
            self.add_error("to_date", "Datum „do“ musí být stejné nebo pozdější než „od“.")
        return cleaned
