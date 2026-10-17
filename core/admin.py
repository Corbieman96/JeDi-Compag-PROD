from django.contrib import admin

from core.models import AppSettings


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "default_map_lat",
        "default_map_lng",
        "svoz_disable_yard_daily_submit_limit",
        "enforce_container_passport_move_check",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "default_map_lat",
                    "default_map_lng",
                    "waste_docs_default_range_days",
                    "dashboard_tasks_notes",
                    "role_nav_defaults",
                    "role_permission_defaults",
                ),
            },
        ),
        (
            "Testování — svozy ze sběrného dvora",
            {
                "fields": (
                    "svoz_disable_yard_daily_submit_limit",
                    "enforce_container_passport_move_check",
                ),
                "description": (
                    "Pokud zapnuté, formulář matice povolí více odešlacích šarží ve stejný kalendářní "
                    "(bez mazání databáze). Po testech vypněte."
                ),
            },
        ),
    )
