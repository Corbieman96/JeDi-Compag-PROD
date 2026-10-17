from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from customer_requests.request_templates.models import CustomerRequestTemplate


def customer_request_templates_visible_queryset(user: AbstractBaseUser):
    """Dispečer a admin vidí všechny šablony; ostatní jen vlastní."""
    from users.services.access import can_see_all_waste_docs

    if not user.is_authenticated:
        return CustomerRequestTemplate.objects.none()
    if can_see_all_waste_docs(user):
        return CustomerRequestTemplate.objects.all()
    return CustomerRequestTemplate.objects.filter(created_by=user)
