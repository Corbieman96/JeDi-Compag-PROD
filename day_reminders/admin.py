from django.contrib import admin
from day_reminders.models import DayReminder, DayReminderException
from day_reminders.services import actions


class DayReminderExceptionInline(admin.TabularInline):
    model = DayReminderException
    extra = 0


@admin.register(DayReminder)
class DayReminderAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "kind", "note_group", "card_color", "text_preview", "pinned_date", "completed_at", "created_at")
    list_filter = ("kind", "note_group", "completed_at")
    search_fields = ("text",)
    inlines = [DayReminderExceptionInline]
    readonly_fields = ("created_at", "updated_at", "created_by")

    @admin.display(description="Text")
    def text_preview(self, obj):
        return (obj.text or "")[:80]

    actions = ["admin_purge_all_completed", "admin_purge_stale_weekly"]

    @admin.action(description="Smazat všechny dokončené připomínky")
    def admin_purge_all_completed(self, request, queryset):
        n = actions.purge_completed(all_completed=True)
        self.message_user(request, f"Smazáno záznamů: {n}.")

    @admin.action(description="Smazat dokončené týdenní po repeat_active_until")
    def admin_purge_stale_weekly(self, request, queryset):
        n = actions.purge_stale_weekly_ended()
        self.message_user(request, f"Smazáno: {n}.")


@admin.register(DayReminderException)
class DayReminderExceptionAdmin(admin.ModelAdmin):
    list_display = ("id", "reminder", "original_date", "rescheduled_to")
