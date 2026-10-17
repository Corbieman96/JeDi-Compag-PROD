from customer_requests.models import CustomerRequest, CustomerRequestAuditLog


def log_customer_request_action(request_obj: CustomerRequest, actor, action: str, note: str = "") -> None:
    CustomerRequestAuditLog.objects.create(
        request=request_obj,
        actor=actor,
        action=action[:80],
        note=(note or "")[:500],
    )
