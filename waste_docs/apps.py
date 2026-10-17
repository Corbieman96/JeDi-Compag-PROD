from django.apps import AppConfig


class WasteDocsConfig(AppConfig):
    name = "waste_docs"

    def ready(self):
        from waste_docs.signals import svoz_matrix_queue  # noqa: F401
