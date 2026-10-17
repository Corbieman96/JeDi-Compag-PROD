from waste_docs.forms.customer_request import (
    ALLOWED_ATTACHMENT_EXTS,
    WEEKDAY_CHOICES,
    CustomerRequestForm,
)
from waste_docs.forms.pruvodka import PruvodkaForm
from waste_docs.forms.ride_template import RideTemplateForm
from waste_docs.forms.svoz_task import SvozTaskQuickEditForm

__all__ = [
    "ALLOWED_ATTACHMENT_EXTS",
    "WEEKDAY_CHOICES",
    "CustomerRequestForm",
    "PruvodkaForm",
    "RideTemplateForm",
    "SvozTaskQuickEditForm",
]
