from django.contrib import admin
from django.utils.html import format_html

from driver_portal.models import DriverPortalPairingToken
from driver_portal.services.pairing_link import (
    absolute_pairing_url_token,
    pairing_url_is_relative,
    qr_png_data_uri,
)


@admin.register(DriverPortalPairingToken)
class DriverPortalPairingTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "display_code", "driver", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("display_code", "driver__personal_number", "driver__last_name", "note")
    readonly_fields = ("secret", "display_code", "created_at", "pairing_url_display", "qr_display")
    fields = ("driver", "status", "note", "display_code", "secret", "created_at", "pairing_url_display", "qr_display")

    @admin.display(description="Odkaz (URL)")
    def pairing_url_display(self, obj: DriverPortalPairingToken):
        if not obj.pk:
            return "Uložte záznam pro vygenerování tajného klíče."
        url = absolute_pairing_url_token(obj)
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, url)

    @admin.display(description="QR kód")
    def qr_display(self, obj: DriverPortalPairingToken):
        if not obj.pk:
            return "—"
        url = absolute_pairing_url_token(obj)
        if pairing_url_is_relative(url):
            return format_html(
                "<p><strong>Nastavte proměnnou PUBLIC_BASE_URL</strong> (např. <code>http://192.168.68.62:8000</code>) "
                "pro správný odkaz v QR.</p><p>Relativní cesta: <code>{}</code></p>",
                url,
            )
        data_uri = qr_png_data_uri(url)
        if not data_uri:
            return "—"
        return format_html(
            '<img alt="QR" src="{}" style="max-width:280px;height:auto;border-radius:8px;" />',
            data_uri,
        )
