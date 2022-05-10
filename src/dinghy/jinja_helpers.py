"""
Utilities for working with Jina2 templates.
"""

import colorsys
import datetime
from pathlib import Path

import aiofiles
import emoji
import jinja2


def datetime_format(value, fmt="%m-%d %H:%M"):
    """Format a datetime or ISO datetime string, for Jinja filtering."""
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime(fmt)


def label_color_css(bg_color):
    """Create CSS for a label color."""
    r, g, b = [int(bg_color[i : i + 2], 16) / 255 for i in [0, 2, 4]]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return "".join(
        f"--label-{ltr}:{int(val * fac)};"
        for ltr, val, fac in zip(
            "rgbhsl", [r, g, b, h, s, l], [255, 255, 255, 360, 100, 100]
        )
    )


def render_jinja(template_filename, **variables):
    """Render a template file, with variables."""
    jenv = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent),
        autoescape=True,
    )
    jenv.filters["datetime"] = datetime_format
    jenv.filters["label_color_css"] = label_color_css
    template = jenv.get_template(f"templates/{template_filename}")
    html = template.render(**variables)
    return html


async def render_jinja_to_file(template_filename, output_file, **variables):
    """Render a template file with variables, and write it to a file."""
    text = render_jinja(template_filename, **variables)
    text = emoji.emojize(text, language="alias")
    async with aiofiles.open(output_file, "w", encoding="utf-8") as out:
        await out.write(text)
