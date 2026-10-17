"""Paleta barev karet denních poznámek na dashboardu."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import models


class CardColor(models.TextChoices):
    YELLOW = "yellow", "Žlutá"
    GREEN = "green", "Zelená"
    BLUE = "blue", "Modrá"
    RED = "red", "Červená"
    PURPLE = "purple", "Fialová"
    GRAY = "gray", "Šedá"


@dataclass(frozen=True)
class CardColorStyle:
    background: str
    border: str
    body_divider: str
    shadow: str


PALETTE: dict[str, CardColorStyle] = {
    CardColor.YELLOW: CardColorStyle(
        background="#fffbeb",
        border="#fde68a",
        body_divider="rgba(253, 230, 138, 0.9)",
        shadow="0 1px 2px rgba(180, 140, 40, 0.08)",
    ),
    CardColor.GREEN: CardColorStyle(
        background="#ecfdf3",
        border="#86efac",
        body_divider="rgba(134, 239, 172, 0.9)",
        shadow="0 1px 2px rgba(25, 120, 70, 0.08)",
    ),
    CardColor.BLUE: CardColorStyle(
        background="#eff6ff",
        border="#93c5fd",
        body_divider="rgba(147, 197, 253, 0.9)",
        shadow="0 1px 2px rgba(37, 99, 235, 0.08)",
    ),
    CardColor.RED: CardColorStyle(
        background="#fef2f2",
        border="#fca5a5",
        body_divider="rgba(252, 165, 165, 0.9)",
        shadow="0 1px 2px rgba(185, 28, 28, 0.08)",
    ),
    CardColor.PURPLE: CardColorStyle(
        background="#faf5ff",
        border="#d8b4fe",
        body_divider="rgba(216, 180, 254, 0.9)",
        shadow="0 1px 2px rgba(126, 34, 206, 0.08)",
    ),
    CardColor.GRAY: CardColorStyle(
        background="#f4f4f5",
        border="#d4d4d8",
        body_divider="rgba(212, 212, 216, 0.9)",
        shadow="0 1px 2px rgba(82, 82, 91, 0.08)",
    ),
}


def normalize_card_color(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    valid = {choice.value for choice in CardColor}
    if value in valid:
        return value
    return CardColor.YELLOW


def card_color_choices() -> list[tuple[str, str]]:
    return list(CardColor.choices)


def card_color_picker_options() -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for slug, label in CardColor.choices:
        style = PALETTE[slug]
        options.append(
            {
                "slug": slug,
                "label": label,
                "background": style.background,
                "border": style.border,
            }
        )
    return options


def card_color_style(slug: str | None) -> CardColorStyle:
    return PALETTE.get(normalize_card_color(slug), PALETTE[CardColor.YELLOW])


def card_color_style_dict(slug: str | None) -> dict[str, str]:
    style = card_color_style(slug)
    return {
        "background": style.background,
        "border": style.border,
        "body_divider": style.body_divider,
        "shadow": style.shadow,
    }


def attach_card_styles(reminders: list[Any]) -> None:
    for reminder in reminders:
        reminder.card_style = card_color_style_dict(getattr(reminder, "card_color", None))
