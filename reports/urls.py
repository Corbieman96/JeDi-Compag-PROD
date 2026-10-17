from django.contrib.auth.decorators import login_required
from django.urls import path

from reports.views.customer_requests_report import customer_requests_report
from reports.views.drivers_export import drivers_export_xlsx
from reports.views.drivers_report import drivers_report
from reports.views.index import index
from reports.views.operations_report import operations_report
from reports.views.period_digest import period_digest_page, period_digest_txt
from reports.views.rides_report import rides_report
from reports.views.suffix_workload_export import suffix_workload_export_xlsx
from reports.views.suffix_workload_report import suffix_workload_report
from reports.views.print_report import print_report
from reports.views.svoz_report import svoz_report
from users.decorators import reports_nav_required

app_name = "reports"

urlpatterns = [
    path("", login_required(reports_nav_required(index)), name="index"),
    path("jizdy/", login_required(reports_nav_required(rides_report)), name="rides"),
    path("koncovky/", login_required(reports_nav_required(suffix_workload_report)), name="suffix_workload"),
    path("koncovky.xlsx", login_required(reports_nav_required(suffix_workload_export_xlsx)), name="suffix_workload_xlsx"),
    path("provoz/", login_required(reports_nav_required(operations_report)), name="operations"),
    path("svozy/", login_required(reports_nav_required(svoz_report)), name="svoz"),
    path("ridici/", login_required(reports_nav_required(drivers_report)), name="drivers"),
    path("ridici.xlsx", login_required(reports_nav_required(drivers_export_xlsx)), name="drivers_xlsx"),
    path("pozadavky/", login_required(reports_nav_required(customer_requests_report)), name="customer_requests"),
    path("tisk/", login_required(reports_nav_required(print_report)), name="print"),
    path("vyucuc/", login_required(reports_nav_required(period_digest_page)), name="period_digest"),
    path("vyucuc.txt", login_required(reports_nav_required(period_digest_txt)), name="period_digest_txt"),
]
