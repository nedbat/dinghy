"""
Test dinghy.helpers
"""

import datetime

import pytest

from dinghy.helpers import parse_timedelta


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
        "2 years",
    ],
)
def test_bad_parse_timedelta(tds):
    with pytest.raises(ValueError, match=f"Couldn't parse time delta from {tds!r}"):
        parse_timedelta(tds)
