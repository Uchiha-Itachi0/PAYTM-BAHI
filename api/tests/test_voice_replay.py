"""The numbers on slide 4, held to the code that runs today.

1,338 recordings, heard by Sarvam and read by Sarvam-105B on 24 Sep 2026, are
replayed through the app's checker (`make voice-eval` prints the whole table).
A change to the checker that moves any recording's grade fails here.
"""

from __future__ import annotations

from collections import Counter

from bahi.voice.replay import BUCKET, load, run


def test_every_recording_is_graded_as_it_was_on_the_day() -> None:
    test = load()
    ours = run(test)["sarvam-105b + checks"]
    assert len(ours) == 1338
    assert [r["graded"] for r in test.recordings] == ours


def test_the_slide_two_point_one_percent_wrong() -> None:
    test = load()
    graded = run(test)
    ours = Counter(BUCKET[g] for g in graded["sarvam-105b + checks"])
    assert (ours["voice"], ours["tap"], ours["again"], ours["wrong"]) == (
        982,
        226,
        102,
        28,
    )
    rules = Counter(BUCKET[g] for g in graded["V2 rules, as graded on the day"])
    assert rules["wrong"] == 148
