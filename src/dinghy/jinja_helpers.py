"""
Utilities for working with Jina2 templates.
"""

import datetime
from pathlib import Path

import wcag_contrast_ratio
import jinja2


def datetime_format(value, fmt="%m-%d %H:%M"):
    """Format a datetime or ISO datetime string, for Jinja filtering."""
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.strftime(fmt)


def textcolor(bg_color):
    """Calculate a text color for a background color `bg_color`."""
    rgb = [int(bg_color[i : i + 2], 16) / 255 for i in [0, 2, 4]]
    bcontrast = wcag_contrast_ratio.rgb(rgb, (0, 0, 0))
    wcontrast = wcag_contrast_ratio.rgb(rgb, (1, 1, 1))
    return "black" if bcontrast > wcontrast else "white"


def render_jinja(template_filename, **variables):
    """Render a template file, with variables."""
    jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(Path(__file__).parent))
    jenv.filters["datetime"] = datetime_format
    jenv.filters["textcolor"] = textcolor
    template = jenv.get_template(f"templates/{template_filename}")
    html = template.render(**variables)
    return html
