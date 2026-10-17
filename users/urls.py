from django.urls import path

from .views import (
    sberny_dvur_subject_search,
    user_create,
    user_delete,
    user_edit,
    user_list,
)

app_name = "users"

urlpatterns = [
    path("", user_list, name="list"),
    path("new/", user_create, name="create"),
    path("sberny-dvur-subject-search/", sberny_dvur_subject_search, name="sberny_dvur_subject_search"),
    path("<int:pk>/edit/", user_edit, name="edit"),
    path("<int:pk>/delete/", user_delete, name="delete"),
]
