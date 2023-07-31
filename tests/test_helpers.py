"""
Test dinghy.helpers
"""

import datetime

import freezegun
import pytest

from dinghy.helpers import find_dict_with_key, parse_since, parse_timedelta


@pytest.mark.parametrize(
    "tds, kwargs",
    [
        ("1d", dict(days=1)),
        ("1day", dict(days=1)),
        ("1d2h3m", dict(days=1, hours=2, minutes=3)),
        (
            "6 day  7.5 hours   8 min .25 s",
            dict(days=6, hours=7.5, minutes=8, seconds=0.25),
        ),
        ("10 weeks 2minutes", dict(weeks=10, minutes=2)),
    ],
)
def test_parse_timedelta(tds, kwargs):
    assert parse_timedelta(tds) == datetime.timedelta(**kwargs)


@pytest.mark.parametrize(
    "tds",
    [
        "",
        "one",
        "123",
        "1month",
        "2 years",
    ],
)
def test_bad_parse_timedelta(tds):
    assert parse_timedelta(tds) is None


@freezegun.freeze_time("2023-06-16")
@pytest.mark.parametrize(
    "since, dtargs",
    [
        ("20230730", (2023, 7, 30)),
        ("2023-06-16T12:34:56", (2023, 6, 16, 12, 34, 56)),
        ("forever", (1980, 1, 1)),
        ("1day", (2023, 6, 15)),
        ("2 weeks", (2023, 6, 2)),
        ("1 week 1 day", (2023, 6, 8)),
    ],
)
def test_parse_since(since, dtargs):
    assert parse_since(since) == datetime.datetime(*dtargs)


@pytest.mark.parametrize(
    "d, k, res",
    [
        ({"a": 1, "b": {"k": 1}, "c": "hello"}, "k", {"k": 1}),
        (
            {"a": 1, "b": {"x": 0, "d": {"k": 1, "z": 2}}, "c": "hello"},
            "k",
            {"k": 1, "z": 2},
        ),
        ({"a": 1, "b": {"k": 1}, "c": "hello"}, "z", None),
    ],
)
def test_find_dict_with_key(d, k, res):
    assert find_dict_with_key(d, k) == res
