"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from users.views_auth import AppLoginView

# Stejné trasy jako django.contrib.auth.urls, ale login řeší AppLoginView (výchozí stránka podle profilu).
accounts_urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password_change/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("core.urls")),
    path("users/", include("users.urls")),
    path("catalogs/", include("catalogs.urls")),
    path("address-data/", include("address_data.urls")),
    path("reports/", include("reports.urls")),
    path("waste-docs/customer-request-templates/", include("customer_requests.request_templates.urls")),
    path("waste-docs/customer-request-series/", include("customer_requests.recurrence_series.urls")),
    path("waste-docs/", include("waste_docs.urls")),
    path("day-reminders/", include("day_reminders.urls")),
    path("driver-portal/", include("driver_portal.urls")),
    path("accounts/", include(accounts_urlpatterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
