from waste_docs.views.ride_document_email.prepare import ride_group_email_cancel, ride_group_email_prepare
from waste_docs.views.ride_document_email.recipients import (
    ride_email_recipient_add,
    ride_email_recipient_delete,
    ride_email_recipients_list,
)

__all__ = [
    "ride_email_recipient_add",
    "ride_email_recipient_delete",
    "ride_email_recipients_list",
    "ride_group_email_cancel",
    "ride_group_email_prepare",
]
