from django.contrib import admin

from .models import Pruvodka


@admin.register(Pruvodka)
class PruvodkaAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name_snapshot", "ico_snapshot", "vehicle_rz_snapshot")
