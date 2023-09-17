"""
Misc helpers.
"""

import datetime
import json
import re

import aiofiles
from backports.datetime_fromisoformat import MonkeyPatch

MonkeyPatch.patch_fromisoformat()


class DinghyError(Exception):
    """An error in how Dinghy is being used."""


async def json_save(data, filename):
    """Write `data` to `filename` as JSON."""
    async with aiofiles.open(filename, "w", encoding="utf-8") as json_out:
        await json_out.write(json.dumps(data, indent=4))


def parse_timedelta(timedelta_str):
    """
    Parse a timedelta string ("2h13m") into a timedelta object.

    From https://stackoverflow.com/a/51916936/14343

    Args:
        timedelta_str (str): A string identifying a duration, like "2h13m".

    Returns:
        A datetime.timedelta object, or None if it can't be parsed.

    """
    parts = re.match(
        r"""(?x)
        ^
        ((?P<weeks>[.\d]+)w(eeks?)?)?
        ((?P<days>[.\d]+)d(ays?)?)?
        ((?P<hours>[.\d]+)h(ours?)?)?
        ((?P<minutes>[.\d]+)m(in(utes?)?)?)?
        ((?P<seconds>[.\d]+)s(ec(onds?)?)?)?
        $
        """,
        timedelta_str.replace(" ", ""),
    )
    if not timedelta_str or parts is None:
        return None
    kwargs = {name: float(val) for name, val in parts.groupdict().items() if val}
    return datetime.timedelta(**kwargs)


def parse_since(since):
    """
    Parse a since specification:

    - "forever" uses a long-ago date.
    - A time delta (like "1 week") computes that long ago.
    - A specific time (like "2023-07-30") is used as-is.

    """
    if since == "forever":
        since_date = datetime.datetime(year=1980, month=1, day=1)
    else:
        delta = parse_timedelta(since)
        if delta is not None:
            since_date = datetime.datetime.now() - delta
        else:
            try:
                since_date = datetime.datetime.fromisoformat(since)
            except ValueError:
                raise DinghyError(f"Can't parse 'since' value: {since!r}") from None
    return since_date


def find_dict_with_key(d, key):
    """Return the subdict of `d` that has `key`."""
    if key in d:
        return d
    for dd in d.values():
        if isinstance(dd, dict):
            sd = find_dict_with_key(dd, key)
            if sd is not None:
                return sd
    return None
