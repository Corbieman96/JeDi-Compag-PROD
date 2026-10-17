from django.urls import path

from driver_portal.views import pairing, portal

app_name = "driver_portal"

urlpatterns = [
    path("pristup/", portal.access_gate, name="gate"),
    path("odhlasit/", portal.driver_portal_logout, name="logout"),
    path("", portal.day_list, name="day_list"),
    path("jizda/<int:pk>/", portal.ride_detail, name="ride_detail"),
    path(
        "pripojit/<str:secret>/odhlasit-a-znovu/",
        pairing.pairing_logout_and_retry,
        name="pair_logout_retry",
    ),
    path("pripojit/<str:secret>/", pairing.pair_by_token, name="pair"),
]
