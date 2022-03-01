"""
Misc helpers.
"""

import datetime
import json
import re

import aiofiles


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
        A datetime.timedelta object.

    """
    parts = re.match(
        r"""(?x)
        ^
        ((?P<weeks>[.\d]+)w[a-z]*)?
        ((?P<days>[.\d]+)d[a-z]*)?
        ((?P<hours>[.\d]+)h[a-z]*)?
        ((?P<minutes>[.\d]+)m[a-z]*)?
        ((?P<seconds>[.\d]+)s[a-z]*)?
        $
        """,
        timedelta_str.replace(" ", ""),
    )
    if not timedelta_str or parts is None:
        raise ValueError(f"Couldn't parse time delta from {timedelta_str!r}")
    kwargs = {name: float(val) for name, val in parts.groupdict().items() if val}
    return datetime.timedelta(**kwargs)
