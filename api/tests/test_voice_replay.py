"""The numbers on slide 4, held to the code that runs today.

1,338 recordings, heard by Sarvam and read by Sarvam-105B on 24 Sep 2026, are
replayed through the app's checker (`make voice-eval` prints the whole table).
The grades from the day are kept in the file; the checker may only ever do
better than them, and every recording it does better on is named here.
"""

from __future__ import annotations

from collections import Counter

from bahi.voice.replay import BUCKET, BUCKETS, load, run

#: Recordings graded better than on the day, and why.
#: 30 Sep: the tag counts, so "मेडिकल वाले अनुभव" is Anubhav Jain of the Medical shop
#: rather than a question among the twenty Anubhavs.
BETTER = {"मेडिकल वाले अनुभव को दो सौ"}


def test_no_recording_is_graded_worse_than_on_the_day() -> None:
    test = load()
    ours = run(test)["sarvam-105b + checks"]
    assert len(ours) == 1338
    rank = {b: i for i, b in enumerate(BUCKETS)}  # voice best, wrong worst
    moved = [
        (test.lines[rec["line"]].said, BUCKET[rec["graded"]], BUCKET[now])
        for rec, now in zip(test.recordings, ours, strict=True)
        if rec["graded"] != now
    ]
    assert all(rank[now] < rank[then] for _, then, now in moved)
    assert {said for said, _, _ in moved} == BETTER


def test_the_slide_two_point_one_percent_wrong() -> None:
    graded = run(load())
    ours = Counter(BUCKET[g] for g in graded["sarvam-105b + checks"])
    assert (ours["voice"], ours["tap"], ours["again"], ours["wrong"]) == (
        1003,
        205,
        102,
        28,
    )
    rules = Counter(BUCKET[g] for g in graded["V2 rules, as graded on the day"])
    assert rules["wrong"] == 148
