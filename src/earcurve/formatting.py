"""Small number/frequency formatters shared by the pages."""

from __future__ import annotations

from .core.eq import round1


def num(value: float | None) -> str:
    if value is None:
        return ""
    rounded = round1(value)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:g}"


def freq_label(freq: float) -> str:
    value = int(round(freq))
    return f"{value // 1000}k" if value >= 1000 else str(value)


def signed(value: float, digits: int = 0) -> str:
    rounded = round1(value)
    text = f"{rounded:.1f}" if digits else num(rounded)
    return ("+" if rounded > 0 else "") + text
