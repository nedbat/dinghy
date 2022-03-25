"""
Test dinghy.helpers
"""

import datetime

import pytest

from dinghy.helpers import find_dict_with_key, parse_timedelta


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
    with pytest.raises(ValueError, match=f"Couldn't parse time delta from {tds!r}"):
        parse_timedelta(tds)


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
