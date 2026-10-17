"""Kompatibilita migrace 0029 (`upload_to=waste_docs.models_customer_request...`)."""

from waste_docs.models.customer_request import customer_request_attachment_upload_to

__all__ = ["customer_request_attachment_upload_to"]
