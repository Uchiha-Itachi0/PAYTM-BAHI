"""An amount, said back the way a shopkeeper says it.

The Soundbox repeats the amount before it is sent, because a wrong amount in the
customer's favour is the one mistake the customer won't catch. So the words must
be the ones a kirana counter uses: 150 is "dedh sau", 250 "dhaai sau", 350 "saade
teen sau", 1200 "barah sau". Never a name: the Soundbox says only the amount.

Roman for the screen, Devanagari for the voice (a Hindi voice reads Devanagari far
better than romanised Hindi). A test checks `parse` reads every one of them back
to the same amount, for every whole rupee up to ₹1 lakh.
"""

from __future__ import annotations

from dataclasses import dataclass

from bahi.domain.numerals import (
    DEVA_DEDH,
    DEVA_DHAI,
    DEVA_SAADE,
    DEVANAGARI,
    HUNDRED,
    LAKH,
    MULTIPLIERS,
    ROMAN,
    SAY_DEDH,
    SAY_DHAI,
    SAY_SAADE,
    THOUSAND,
)


@dataclass(frozen=True, slots=True)
class Said:
    roman: str
    devanagari: str


@dataclass(frozen=True, slots=True)
class _Words:
    units: dict[int, tuple[str, ...]]
    sau: str
    hazaar: str
    lakh: str
    dedh: str
    dhai: str
    saade: str

    def unit(self, n: int) -> str:
        return self.units[n][0]

    def hundreds(self, n: int) -> list[str]:
        """1 to 999."""
        h, rest = divmod(n, HUNDRED)
        if h == 0:
            return [self.unit(rest)]
        if rest == 50 and h in (1, 2):
            return [self.dedh if h == 1 else self.dhai, self.sau]
        if rest == 50:
            return [self.saade, self.unit(h), self.sau]
        head = [self.sau] if h == 1 and rest == 0 else [self.unit(h), self.sau]
        return head + ([self.unit(rest)] if rest else [])

    def thousands(self, n: int) -> list[str]:
        """1 to 99,999."""
        t, rest = divmod(n, THOUSAND)
        if t == 0:
            return self.hundreds(rest)
        if rest == 500 and t in (1, 2):
            return [self.dedh if t == 1 else self.dhai, self.hazaar]
        if rest == 500 and t < 100:
            return [self.saade, self.unit(t), self.hazaar]
        if rest == 0:
            return [self.unit(t), self.hazaar]
        if n < 10 * THOUSAND and n % HUNDRED == 0:
            return [self.unit(n // HUNDRED), self.sau]  # 1200 is "barah sau"
        return [self.unit(t), self.hazaar, *self.hundreds(rest)]

    def say(self, n: int) -> str:
        lakhs, rest = divmod(n, LAKH)
        if lakhs == 0:
            return " ".join(self.thousands(rest))
        head = [self.unit(lakhs), self.lakh]
        return " ".join(head + (self.thousands(rest) if rest else []))


_ROMAN = _Words(
    ROMAN,
    MULTIPLIERS[HUNDRED][0],
    MULTIPLIERS[THOUSAND][0],
    MULTIPLIERS[LAKH][0],
    SAY_DEDH,
    SAY_DHAI,
    SAY_SAADE,
)
_DEVA = _Words(DEVANAGARI, "सौ", "हज़ार", "लाख", DEVA_DEDH, DEVA_DHAI, DEVA_SAADE)


def say(amount_paise: int) -> Said:
    """20000 -> "do sau" / "दो सौ". Whole rupees from ₹1 up to ₹99,99,999."""
    rupees, paise = divmod(amount_paise, 100)
    if paise or not 0 < rupees < 100 * LAKH:
        raise ValueError(
            f"only whole rupees from 1 to 99,99,999 are said, not {amount_paise}"
        )
    return Said(_ROMAN.say(rupees), _DEVA.say(rupees))
