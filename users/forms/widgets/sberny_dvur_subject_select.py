"""Widget pro skrytý select — do HTML jen prázdná a aktuálně vybraná položka."""

from __future__ import annotations

from django import forms

from catalogs.models import NameSubjectProfile
from users.services.sberny_dvur_subject_search import sberny_dvur_subject_label


class SbernyDvurSubjectSelectWidget(forms.Select):
    def optgroups(self, name, value, attrs=None):
        selected_values = []
        if value is not None:
            if isinstance(value, (list, tuple)):
                selected_values = [str(v) for v in value if v not in ("", None)]
            else:
                selected_values = [str(value)]

        options = [self.create_option(name, "", "---------", not selected_values, 0, subindex=None)]
        if selected_values:
            pk_raw = selected_values[0]
            try:
                pk = int(pk_raw)
            except (TypeError, ValueError):
                pk = None
            if pk:
                profile = (
                    NameSubjectProfile.objects.select_related("name", "ico", "yard_settings")
                    .filter(pk=pk)
                    .first()
                )
                if profile:
                    label = sberny_dvur_subject_label(profile)
                    options.append(
                        self.create_option(name, str(profile.pk), label, True, 1, subindex=None)
                    )
        return [(None, options, 0)]
