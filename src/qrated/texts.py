"""Spoken-text helpers: English dates and template rendering."""

from __future__ import annotations

from datetime import date, datetime


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def spoken_date(d: date | datetime, weekday: bool = True) -> str:
    """'Tuesday, September 29th' (or 'September 29th' without weekday)."""
    text = f"{d:%B} {ordinal(d.day)}"
    return f"{d:%A}, {text}" if weekday else text


def lead_for(index: int, total: int) -> str:
    if index == 0:
        return "First up"
    if index == total - 1 and total > 2:
        return "And finally"
    return "Next up"


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(template: str, **values) -> str:
    """Format a template, leaving unknown placeholders untouched."""
    return template.format_map(_Safe(values))
