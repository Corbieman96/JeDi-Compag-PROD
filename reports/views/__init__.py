from reports.views.customer_requests_report import customer_requests_report
from reports.views.drivers_report import drivers_report
from reports.views.index import index
from reports.views.print_report import print_report
from reports.views.rides_report import rides_report
from reports.views.svoz_report import svoz_report

__all__ = [
    "index",
    "rides_report",
    "svoz_report",
    "drivers_report",
    "customer_requests_report",
    "print_report",
]
