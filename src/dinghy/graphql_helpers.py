"""
GraphQL helpers.
"""

import asyncio
import collections
import datetime
import itertools
import logging
import os
import pkgutil
import re
import time

import aiohttp

from .helpers import find_dict_with_key, json_save


logger = logging.getLogger()


def _summarize_rate_limit(response):
    """
    Create a dict of information about the current rate limit.

    Reads GitHub X-RateLimit- headers.
    """
    rate_limit_info = {
        k.rpartition("-")[-1].lower(): v
        for k, v in response.headers.items()
        if k.startswith("X-RateLimit-")
    }
    rate_limit_helpfully = {
        **rate_limit_info,
        "reset_when": time.strftime(
            "%H:%M:%S",
            time.localtime(int(rate_limit_info["reset"])),
        ),
        "when": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    return rate_limit_helpfully


def _raise_if_error(data):
    """
    If `data` is an error response, raise a useful exception.
    """
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


class GraphqlHelper:
    """
    A helper for GraphQL, including error handling and pagination.
    """

    json_names = (f"out_{i:04}.json" for i in itertools.count())
    rate_limit_history = collections.deque(maxlen=50)

    def __init__(self, endpoint, token):
        self.endpoint = endpoint
        self.headers = {"Authorization": f"Bearer {token}"}

    @classmethod
    def save_rate_limit(cls, rate_limit):
        """Keep rate limit history."""
        cls.rate_limit_history.append(rate_limit)

    @classmethod
    def last_rate_limit(cls):
        """Get the latest rate limit info."""
        if not cls.rate_limit_history:
            return None
        return cls.rate_limit_history[-1]

    async def _raw_execute(self, query, variables=None):
        """
        Execute one GraphQL query, and return the JSON data.
        """
        jbody = {"query": query}
        if variables:
            jbody["variables"] = variables
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(self.endpoint, json=jbody) as response:
                response.raise_for_status()
                self.save_rate_limit(_summarize_rate_limit(response))
                return await response.json()

    async def execute(self, query, variables=None):
        """
        Execute one GraphQL query, with logging, retrying, and error handling.
        """
        args = ", ".join(f"{k}: {v!r}" for k, v in variables.items())
        query_head = next(
            line for line in query.splitlines() if not line.startswith("#")
        )
        logger.debug(query_head + args + ")")

        while True:
            data = await self._raw_execute(query=query, variables=variables)
            if "errors" in data:
                if data["errors"][0].get("type") == "RATE_LIMITED":
                    reset_when = self.last_rate_limit()["reset_when"]
                    logger.info(f"Waiting for rate limit to reset at {reset_when}")
                    await asyncio.sleep(
                        int(self.last_rate_limit()["reset"]) - time.time() + 10
                    )
                    continue
            break

        # $set_env.py: DIGEST_SAVE_RESPONSES - save every query response in a JSON file.
        if int(os.environ.get("DIGEST_SAVE_RESPONSES", 0)):
            json_name = next(self.json_names)
            await json_save(data, json_name)
            logger.info(f"Wrote query data: {json_name}")

        _raise_if_error(data)
        return data

    async def nodes(self, query, variables=None, donefn=None):
        """
        Execute a GraphQL query, and follow the pagination to get all the nodes.

        Returns the last query result (for the information outside the pagination),
        and the list of all paginated nodes.
        """
        nodes = []
        variables = dict(variables)
        while True:
            data = await self.execute(query, variables)
            fetched = find_dict_with_key(data, "pageInfo")
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
