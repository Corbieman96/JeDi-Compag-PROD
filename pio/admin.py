from django.contrib import admin

from pio.models import PioRevision


@admin.register(PioRevision)
class PioRevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "pair", "created_at", "created_by", "note")
    list_filter = ("created_at",)
    search_fields = ("note", "pair__subject_profile__company_name")
    raw_id_fields = ("pair", "created_by")
