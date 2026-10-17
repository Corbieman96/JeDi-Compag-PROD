from django.urls import path

from day_reminders import views
from day_reminders.note_print.views import print_day_notes

app_name = "day_reminders"

urlpatterns = [
    path("create/", views.reminder_create, name="create"),
    path("<int:pk>/complete/", views.reminder_complete, name="complete"),
    path("<int:pk>/snooze/", views.reminder_snooze, name="snooze"),
    path("<int:pk>/exception/", views.reminder_exception, name="exception"),
    path("<int:pk>/update/", views.reminder_update, name="update"),
    path("<int:pk>/delete/", views.reminder_delete, name="delete"),
    path("purge/", views.reminder_purge, name="purge"),
    path("print/", print_day_notes, name="print_day"),
]
