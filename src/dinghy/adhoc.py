"""
A module-main for running ad-hoc GitHub GraphQL queries.
"""

import json
import os
import sys

import click
import click_log

from .cli import main_run
from .graphql_helpers import GraphqlHelper


logger = click_log.basic_config("dinghy")


@click.command()
@click_log.simple_verbosity_option(logger)
@click.argument("query_file", type=click.File("r"))
@click.argument("var", metavar="[VAR=VAL]...", nargs=-1)
def adhoc(query_file, var):
    """
    Run an ad-hoc GraphQL query.
    """
    query = query_file.read()
    variables = dict(v.split("=", 1) for v in var)

    token = os.environ.get("GITHUB_TOKEN", "")
    gql = GraphqlHelper("https://api.github.com/graphql", token)
    data, _ = main_run(gql.nodes(query=query, variables=variables, clear_nodes=False))
    json.dump(data, sys.stdout, indent=2)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    adhoc()
