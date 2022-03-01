"""Dinghy command-line interface."""

import asyncio
import sys

import click

from .digest import make_digests
from .graphql_helpers import GraphqlHelper
from .helpers import DinghyError


@click.command()
@click.argument("config_file", type=click.File("rb"), default="dinghy.yaml")
def cli(config_file):
    """
    Generate HTML digests of GitHub activity.
    """
    try:
        asyncio.run(make_digests(config_file))
    except DinghyError as err:
        print(f"dinghy error: {err}")
        sys.exit(1)
    finally:
        lrl = GraphqlHelper.last_rate_limit()
        if lrl is not None:
            print(
                f"Remaining {lrl['resource']} rate limit: "
                + f"{lrl['remaining']} of {lrl['limit']}, "
                + f"next reset at {lrl['reset_when']}"
            )
