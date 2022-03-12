"""Dinghy command-line interface."""

import asyncio
import logging
import sys

import click
import click_log

from .digest import make_digest, make_digests_from_config
from .graphql_helpers import GraphqlHelper
from .helpers import DinghyError

logger = logging.getLogger()
click_log.basic_config(logger)


@click.command()
@click_log.simple_verbosity_option(logger)
@click.argument("_input", metavar="[INPUT]", default="dinghy.yaml")
def cli(_input):
    """
    Generate HTML digests of GitHub activity.

    INPUT is a dinghy YAML configuration file (default: dinghy.yaml), or a
    GitHub repo URL.

    """
    if "://" in _input:
        coro = make_digest([_input])
    else:
        coro = make_digests_from_config(_input)

    try:
        asyncio.run(coro)
    except DinghyError as err:
        logger.error(f"dinghy error: {err}")
        sys.exit(1)
    finally:
        lrl = GraphqlHelper.last_rate_limit()
        if lrl is not None:
            logger.debug(
                f"Remaining {lrl['resource']} rate limit: "
                + f"{lrl['remaining']} of {lrl['limit']}, "
                + f"next reset at {lrl['reset_when']}"
            )
