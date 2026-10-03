"""Money is integer paise everywhere. This is the only place it becomes text."""

from __future__ import annotations


def rupees(paise: int) -> str:
    """20000 -> "₹200", 12400000 -> "₹1,24,000", 1250 -> "₹12.50".

    Indian grouping (lakh, crore), because that is how the shopkeeper reads a
    number. Whole rupees print without ".00"; a paise remainder always prints both
    digits.
    """
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(paise), 100)
    text = f"{sign}₹{_group(whole)}"
    return f"{text}.{frac:02d}" if frac else text


def _group(n: int) -> str:
    digits = str(n)
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    pairs: list[str] = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *pairs, tail])
