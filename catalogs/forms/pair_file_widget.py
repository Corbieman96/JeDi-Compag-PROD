from django import forms


class PairClearableFileInput(forms.ClearableFileInput):
    """PIO / dokument u páru — ikona místo dlouhé cesty k souboru."""

    template_name = "catalogs/forms/widgets/pair_clearable_file_input.html"
