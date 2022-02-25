"""Dinghy command-line interface."""

import asyncio

import click

from .digest import make_digests
from .graphql_helpers import GraphqlHelper


@click.command()
@click.argument("config_file", type=click.File("rb"), default="dinghy.yaml")
def cli(config_file):
    """
    Generate HTML digests of GitHub activity.
    """
    try:
        asyncio.run(make_digests(config_file))
    finally:
        print(GraphqlHelper.last_rate_limit())
