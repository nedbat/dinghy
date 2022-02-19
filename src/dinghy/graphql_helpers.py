"""
GraphQL helpers.
"""

import itertools
import os
import pkgutil
import re

import aiohttp
from glom import glom as g

from .helpers import json_save


JSON_NAMES = (f"out_{i:02}.json" for i in itertools.count())


class GraphqlHelper:
    """
    A helper for GraphQL, including error handling and pagination.
    """

    def __init__(self, endpoint, token):
        self.endpoint = endpoint
        self.headers = {"Authorization": f"Bearer {token}"}

    async def raw_execute(self, query, variables=None):
        """
        Execute one GraphQL query, and return the JSON data.
        """
        jbody = {"query": query}
        if variables:
            jbody["variables"] = variables
        async with aiohttp.ClientSession(
            headers=self.headers, raise_for_status=True
        ) as session:
            async with session.post(self.endpoint, json=jbody) as response:
                return await response.json()

    async def execute(self, query, variables=None):
        """
        Execute one GraphQL query, with logging and error handling.
        """
        args = ", ".join(f"{k}: {v!r}" for k, v in variables.items())
        print(query.splitlines()[0] + args + ")")

        data = await self.raw_execute(query=query, variables=variables)

        # $set_env.py: DIGEST_SAVE_RESPONSES - save every query response in a JSON file.
        if int(os.environ.get("DIGEST_SAVE_RESPONSES", 0)):
            await json_save(data, next(JSON_NAMES))

        if "message" in data:
            raise Exception(data["message"])
        if "errors" in data:
            err = data["errors"][0]
            msg = f"GraphQL error: {err['message']}"
            if "path" in err:
                msg += f" @{'.'.join(err['path'])}"
            if "locations" in err:
                loc = err["locations"][0]
                msg += f", line {loc['line']} column {loc['column']}"
            raise Exception(msg)
        if "data" in data and data["data"] is None:
            # Another kind of failure response?
            raise Exception("GraphQL query returned null")

        return data

    async def nodes(self, query, path, variables=None, donefn=None):
        """
        Execute a GraphQL query, and follow the pagination to get all the nodes.

        Returns the last query result (for the information outside the pagination),
        and the list of all paginated nodes.
        """
        nodes = []
        variables = dict(variables)
        while True:
            data = await self.execute(query, variables)
            fetched = g(data, f"data.{path}")
            nodes.extend(fetched["nodes"])
            if not fetched["pageInfo"]["hasNextPage"]:
                break
            if donefn is not None and donefn(fetched["nodes"]):
                break
            variables["after"] = fetched["pageInfo"]["endCursor"]
        # Remove the nodes from the top-level data we return, to keep things clean.
        fetched["nodes"] = []
        return data, nodes


def build_query(gql_filename):
    """Read a GraphQL file, and complete it with requested fragments."""
    filenames = [gql_filename]
    query = []

    seen_filenames = set()
    while filenames:
        next_filenames = []
        for filename in filenames:
            gtext = pkgutil.get_data("dinghy", f"graphql/{filename}").decode("utf-8")
            query.append(gtext)

            for match in re.finditer(r"#\s*fragment: ([.\w]+)", gtext):
                frag_name = match[1]
                if frag_name not in seen_filenames:
                    next_filenames.append(frag_name)
                    seen_filenames.add(frag_name)
        filenames = next_filenames

    return "\n".join(query)
