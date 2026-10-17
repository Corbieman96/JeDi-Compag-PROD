from django.conf import settings


def jedis_version(request):
    environment = getattr(settings, "JEDIS_ENVIRONMENT", "PROD")
    return {
        "jedis_version": getattr(settings, "JEDIS_VERSION", ""),
        "jedis_environment": environment,
        "jedis_is_test": environment.upper() == "TEST",
    }
