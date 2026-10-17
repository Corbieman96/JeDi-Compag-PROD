from django.conf import settings


def jedis_version(request):
    return {"jedis_version": getattr(settings, "JEDIS_VERSION", "")}
