from django.urls import path

from customer_requests.recurrence_series.views.pages import (
    series_cancel_range,
    series_manage,
)

app_name = "customer_request_recurrence_series"

urlpatterns = [
    path("<int:pk>/", series_manage, name="manage"),
    path("<int:pk>/cancel/", series_cancel_range, name="cancel_range"),
]
