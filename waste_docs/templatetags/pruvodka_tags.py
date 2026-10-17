from django import template

from waste_docs.follow_up_display import (
    follow_up_child_link_symbol,
    follow_up_child_symbol_is_custom,
    follow_up_parent_link_symbol,
    follow_up_parent_symbol_is_custom,
    is_exchange_style_follow_up,
)
from waste_docs.services.customer_request_ride_note import ride_note_for_customer_request
from waste_docs.services.customer_request_vehicle_kind import effective_vehicle_kind_label

register = template.Library()


@register.filter
def follow_up_parent_symbol(pruvodka):
    return follow_up_parent_link_symbol(pruvodka)


@register.filter
def follow_up_child_symbol(pruvodka):
    return follow_up_child_link_symbol(pruvodka)


@register.filter
def follow_up_is_exchange_style(pruvodka):
    return is_exchange_style_follow_up(pruvodka)


@register.filter
def follow_up_child_symbol_custom(pruvodka):
    return follow_up_child_symbol_is_custom(pruvodka)


@register.filter
def follow_up_parent_symbol_custom(pruvodka):
    return follow_up_parent_symbol_is_custom(pruvodka)


@register.filter
def customer_request_effective_vehicle_kind_label(cr):
    return effective_vehicle_kind_label(cr)


@register.filter
def customer_request_ride_note(cr):
    return ride_note_for_customer_request(cr)


@register.filter
def customer_request_recurrence_label(cr):
    from waste_docs.services.customer_request_recurrence import recurrence_display_label

    return recurrence_display_label(cr)


_WEEKDAY_SHORT = ("Po", "Út", "St", "Čt", "Pá", "So", "Ne")


@register.filter
def czech_weekday_short(value):
    """Zkratka dne v týdnu (Po–Ne) pro date/datetime; prázdné při chybě."""
    if value is None:
        return ""
    try:
        return _WEEKDAY_SHORT[value.weekday()]
    except Exception:
        return ""
