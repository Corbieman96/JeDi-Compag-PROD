from django.urls import path

from .views import address_create, address_delete, address_list

app_name = "address_data"

urlpatterns = [
    path("", address_list, name="list"),
    path("new/", address_create, name="create"),
    path("<int:pk>/delete/", address_delete, name="delete"),
]
