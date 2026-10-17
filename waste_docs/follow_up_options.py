from __future__ import annotations


def allowed_follow_up_activity_ids(activity) -> list[int]:
    if not activity:
        return []
    resolver = getattr(activity, "follow_up_activity_ids_allowed", None)
    if callable(resolver):
        return resolver()
    if getattr(activity, "follow_up_activity_id", None):
        return [activity.follow_up_activity_id]
    return []


def has_follow_up_option(activity) -> bool:
    return bool(allowed_follow_up_activity_ids(activity))


def primary_follow_up_activity(activity):
    if not activity:
        return None
    resolver = getattr(activity, "primary_follow_up_activity", None)
    if callable(resolver):
        return resolver()
    return getattr(activity, "follow_up_activity", None)
