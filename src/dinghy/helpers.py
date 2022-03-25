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
        raise ValueError(f"Couldn't parse time delta from {timedelta_str!r}")
    kwargs = {name: float(val) for name, val in parts.groupdict().items() if val}
    return datetime.timedelta(**kwargs)


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
