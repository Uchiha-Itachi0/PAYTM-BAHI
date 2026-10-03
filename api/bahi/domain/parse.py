"""What the shopkeeper said, taken apart by rule: the amount, and maybe a name.

The transcript comes from speech recognition; everything after it is here, and
none of it is a model. The amount is whatever the number words add up to, by the
grammar in `numerals.value`. The name is whatever is left once the number words and
the small words around them ("ko", "udhaar", "likh do", "rupaye") are taken out.

It refuses rather than guesses. Two different amounts in one sentence, a number that
isn't well formed ("tera do"), or a fraction of a rupee all come back as
`unclear_amount`, and the screen asks again instead of sending something.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from bahi.domain.numerals import Numeral, key, numeral, value
from bahi.domain.script import tokens

Problem = Literal["no_amount", "unclear_amount"]

# Words around an amount that are neither the amount nor a name. Spelled as a
# transcript might; compared by key, so "udhaar"/"udhar"/"उधार" are one entry.
_FILLER = """
ko ka ki ke kaa naam name par pe pr wala wale wali waala udhaar udhar udhari
likho likh likha likhna likhdo likhlo jodo jod jodna daalo daal dalo dedo de dena
dijiye lo le lelo lena rupaye rupay rupees rupee rupiya rupiye rupaiya rs inr
aur and hai hain tha mein me se ne sirf bas total khata khaate account add karo
kar kardo karna rakh rakho bhej bhejo chadha chadhao credit entry haan han ha ok
okay achha accha thik theek please plz abhi aaj for to of the a is bhi wo woh ye
yeh isko usko inko unko iska uska
को का की के नाम पर पे वाला वाले वाली उधार उधारी लिखो लिख लिखना जोड़ो जोड़ डालो
डाल दे देना दीजिए लो ले लेना रुपये रुपए रुपया रुपैया और है हैं था में से ने सिर्फ़
बस खाता करो कर करना हाँ हां ठीक अच्छा अभी आज भी वो ये इसको उसको इनका उनका
"""
_FILLERS = frozenset(key(w) for w in _FILLER.split())

# "do" is also "give": "de do", "likh do". After one of these it is not 2.
_GIVE = """
de le kar likh jod daal dal rakh bhej chadha likha
दे ले कर लिख जोड़ डाल रख भेज चढ़ा
"""
_VERBS = frozenset(key(w) for w in _GIVE.split())
_DO = frozenset((key("do"), key("दो")))
# "do sau aur pachaas": "and" between two number words keeps them one amount.
_AND = frozenset((key("aur"), key("and"), key("और")))


@dataclass(frozen=True, slots=True)
class Heard:
    text: str
    #: The words taken as a name, as they were said. None if nothing was left.
    name: str | None
    amount_paise: int | None
    #: The words taken as the amount, as they were said.
    amount_words: str | None
    problem: Problem | None


def heard(text: str) -> Heard:
    words = tokens(text)
    nums: list[Numeral | None] = []
    give: set[int] = set()
    for i, w in enumerate(words):
        n = numeral(w)
        if n is not None and key(w) in _DO and i > 0 and key(words[i - 1]) in _VERBS:
            n = None  # "de do": give
            give.add(i)
        nums.append(n)

    # Runs of consecutive number words; "aur" between two of them joins them.
    runs: list[list[int]] = []
    for i, n in enumerate(nums):
        if n is None:
            continue
        joined = (
            runs
            and runs[-1][-1] == i - 2
            and key(words[i - 1]) in _AND
            and nums[i - 1] is None
        )
        if runs and (runs[-1][-1] == i - 1 or joined):
            runs[-1].append(i)
        else:
            runs.append([i])

    in_amount = {i for run in runs for i in run}
    in_amount |= {i for run in runs for i in range(run[0], run[-1] + 1)}  # the "aur"
    name_words = [
        w
        for i, w in enumerate(words)
        if i not in in_amount | give and key(w) not in _FILLERS
    ]
    name = " ".join(name_words) or None

    if not runs:
        return Heard(text, name, None, None, "no_amount")

    values: set[Fraction | None] = set()
    for run in runs:
        parts = [nums[i] for i in run]
        values.add(value([p for p in parts if p is not None]))
    words_said = " / ".join(" ".join(words[run[0] : run[-1] + 1]) for run in runs)

    # Several runs are fine only if they agree: "do sau, haan do sau".
    if len(values) != 1 or None in values:
        return Heard(text, name, None, words_said, "unclear_amount")
    rupees = values.pop()
    assert rupees is not None
    paise = rupees * 100
    if paise <= 0 or paise.denominator != 1 or paise % 100:
        return Heard(text, name, None, words_said, "unclear_amount")
    return Heard(text, name, int(paise), words_said, None)
