"""
A module-main for running ad-hoc GitHub GraphQL queries.

After installing dinghy, run it like this:

    $ python -m dinghy.adhoc --help

"""

import json
import os
import sys

import click
import click_log

from .cli import main_run
from .graphql_helpers import GraphqlHelper


logger = click_log.basic_config("dinghy")


TYPES = {
    "int": int,
    "str": str,
}


@click.command()
@click_log.simple_verbosity_option(logger)
@click.option(
    "--nodes",
    is_flag=True,
    help="Get paginated list of nodes instead of raw result",
)
@click.argument("query_file", type=click.File("r"))
@click.argument("var", metavar="[VAR[:type]=VAL]...", nargs=-1)
def adhoc(nodes, query_file, var):
    """
    Run an ad-hoc GraphQL query.
    """
    query = query_file.read()
    variables = {}
    for v in var:
        name, val = v.split("=", 1)
        if ":" in name:
            name, type_name = name.split(":")
            val = TYPES[type_name](val)
        variables[name] = val

    token = os.environ.get("GITHUB_TOKEN", "")
    gql = GraphqlHelper("https://api.github.com/graphql", token)
    if nodes:
        data, _ = main_run(
            gql.nodes(query=query, variables=variables, clear_nodes=False)
        )
    else:
        data = main_run(gql.execute(query=query, variables=variables))
    json.dump(data, sys.stdout, indent=2)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    adhoc()
