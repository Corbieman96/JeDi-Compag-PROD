from django.apps import AppConfig


class CatalogsConfig(AppConfig):
    name = "catalogs"

    def ready(self) -> None:
        from catalogs.signals import zpo_document  # noqa: F401
