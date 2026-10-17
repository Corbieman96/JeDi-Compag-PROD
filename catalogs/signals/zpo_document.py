from django.db.models.signals import pre_delete
from django.dispatch import receiver

from catalogs.models import ZpoDocument


@receiver(pre_delete, sender=ZpoDocument)
def delete_zpo_document_file(sender, instance: ZpoDocument, **kwargs) -> None:
    if not instance.file or not instance.file.name:
        return
    path = instance.file.name
    others = ZpoDocument.objects.filter(file=path)
    if instance.pk is not None:
        others = others.exclude(pk=instance.pk)
    if others.exists():
        return
    instance.file.delete(save=False)
