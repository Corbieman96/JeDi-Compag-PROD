from django.contrib import admin

from .models import OfflineAddress


@admin.register(OfflineAddress)
class OfflineAddressAdmin(admin.ModelAdmin):
    list_display = ("label", "postal_code", "city", "lat", "lng")
    search_fields = ("label", "city", "street", "postal_code")
