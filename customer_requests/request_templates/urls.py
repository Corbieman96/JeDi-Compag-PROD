from django.urls import path

from customer_requests.request_templates.views.pages import (
    template_api_list,
    template_api_save,
    template_create,
    template_delete,
    template_edit,
    template_list,
)

app_name = "customer_request_templates"

urlpatterns = [
    path("", template_list, name="list"),
    path("new/", template_create, name="create"),
    path("<int:pk>/edit/", template_edit, name="edit"),
    path("<int:pk>/delete/", template_delete, name="delete"),
    path("api/list/", template_api_list, name="api_list"),
    path("api/save/", template_api_save, name="api_save"),
]
