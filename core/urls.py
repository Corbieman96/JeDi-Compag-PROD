from django.urls import path

from .views import app_settings, dashboard, help_page, session_close, session_keepalive
from .ride_group_reorder_views import (
    ride_group_ai_prompt,
    ride_group_optimize,
    ride_group_optimize_apply,
    ride_group_reorder,
)

app_name = "core"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("settings/", app_settings, name="settings"),
    path("help/", help_page, name="help"),
    path("session-close/", session_close, name="session_close"),
    path("session-keepalive/", session_keepalive, name="session_keepalive"),
    path("dashboard/ride-group/reorder/", ride_group_reorder, name="ride_group_reorder"),
    path("dashboard/ride-group/ai-prompt/", ride_group_ai_prompt, name="ride_group_ai_prompt"),
    path("dashboard/ride-group/optimize/", ride_group_optimize, name="ride_group_optimize"),
    path("dashboard/ride-group/optimize-apply/", ride_group_optimize_apply, name="ride_group_optimize_apply"),
]
