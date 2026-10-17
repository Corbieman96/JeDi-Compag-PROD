"""Sdílená stránkování seznamů (GET page, per_page, elided range)."""

from __future__ import annotations

from typing import Any

from django.core.paginator import Paginator
from django.http import HttpRequest

PER_PAGE_CHOICES = (25, 50, 100, 200)
DEFAULT_PER_PAGE = 50


def parse_per_page(raw: str | None, *, choices: tuple[int, ...] = PER_PAGE_CHOICES) -> int:
    try:
        per_page = int((raw or "").strip() or DEFAULT_PER_PAGE)
    except ValueError:
        per_page = DEFAULT_PER_PAGE
    if per_page not in choices:
        return DEFAULT_PER_PAGE
    return per_page


def build_elided_pages(paginator: Paginator, page_number: int) -> list[dict[str, Any]]:
    if paginator.num_pages <= 1:
        return []
    out: list[dict[str, Any]] = []
    for page in paginator.get_elided_page_range(page_number, on_each_side=2, on_ends=1):
        if isinstance(page, int):
            out.append({"ellipsis": False, "number": page})
        else:
            out.append({"ellipsis": True})
    return out


def preserve_get_query(request: HttpRequest, *, exclude: tuple[str, ...] = ("page",)) -> str:
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def paginate_queryset(qs, request: HttpRequest, *, per_page: int | None = None) -> dict[str, Any]:
    resolved_per_page = per_page if per_page is not None else parse_per_page(request.GET.get("per_page"))
    paginator = Paginator(qs, resolved_per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return {
        "page_obj": page_obj,
        "per_page": resolved_per_page,
        "per_page_choices": PER_PAGE_CHOICES,
        "elided_pages": build_elided_pages(paginator, page_obj.number),
        "pagination_preserve_query": preserve_get_query(request),
    }
