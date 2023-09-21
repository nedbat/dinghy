"""Dinghy command-line interface."""

import asyncio
import sys

import click
import click_log

from .digest import make_digest, make_digests_from_config
from .graphql_helpers import GraphqlHelper
from .helpers import DinghyError

# Fix for https://github.com/nedbat/dinghy/issues/9
# Work around a known problem (https://github.com/python/cpython/issues/83413)
# that is fixed in 3.10.6 (https://github.com/python/cpython/pull/92904).
if sys.version_info < (3, 10, 6) and sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = click_log.basic_config("dinghy")


def main_run(coro):
    """
    Run a coroutine for a Dinghy command.
    """
    try:
        return asyncio.run(coro)
    except DinghyError as err:
        logger.error(f"dinghy error: {err}")
        sys.exit(1)
    finally:
        lrl = GraphqlHelper.last_rate_limit()
        if lrl is not None:
            resource = lrl.get("resource", "general")
            logger.debug(
                f"Remaining {resource} rate limit: "
                + f"{lrl['remaining']} of {lrl['limit']}, "
                + f"next reset at {lrl['reset_when']}"
            )


@click.command()
@click_log.simple_verbosity_option(logger)
@click.version_option()
@click.option(
    "--since",
    metavar="DELTA-OR-DATE",
    help="Specify a since date. [default: 1 week]",
)
@click.argument("_input", metavar="[INPUT]", default="dinghy.yaml")
@click.argument("digests", metavar="[DIGEST ...]", nargs=-1)
def cli(since, _input, digests):
    """
    Generate HTML digests of GitHub activity.

    INPUT is a dinghy YAML configuration file (default: dinghy.yaml), or a
    GitHub repo URL.

    DIGEST(s) are the file names of digests from the configuration file to
    create.  If none are specified, all of the digests are written.

    """
    if "://" in _input:
        coro = make_digest([_input], since=since)
    else:
        coro = make_digests_from_config(_input, digests or None, since=since)

    main_run(coro)
