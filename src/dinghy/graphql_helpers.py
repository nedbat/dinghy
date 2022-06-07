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

from .helpers import DinghyError, find_dict_with_key, json_save


logger = logging.getLogger(__name__)


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


# GraphQL error types that could be user mistakes.
USER_FIXABLE_ERR_TYPES = {
    "INSUFFICIENT_SCOPES": "Insufficient GitHub token scope.",
}


def _raise_if_error(data):
    """
    If `data` is an error response, raise a useful exception.
    """
    if "message" in data:
        raise Exception(data["message"])
    if "errors" in data:
        err = data["errors"][0]
        if user_fix_msg := USER_FIXABLE_ERR_TYPES.get(err.get("type")):
            raise DinghyError(f"{user_fix_msg} {err['message']}")
        msg = f"GraphQL error: {err['message']}"
        if "path" in err:
            msg += f" @{'.'.join(err['path'])}"
        if "locations" in err:
            loc = err["locations"][0]
            msg += f", line {loc['line']} column {loc['column']}"
        logger.debug(f"Error data: {data}")
        raise Exception(msg)
    if "data" in data and data["data"] is None:
        # Another kind of failure response?
        raise Exception("GraphQL query returned null")


def _query_synopsis(query, variables):
    """
    Create a one-line synopsis of the query, for debugging and error messages.
    """
    args = ", ".join(f"{k}: {v!r}" for k, v in variables.items())
    query_head = next(line for line in query.splitlines() if not line.startswith("#"))
    return query_head + args + ")"


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
            NUM_TRIES = 200
            PAUSE = 5
            total_wait = 0
            for trynum in range(NUM_TRIES):
                async with session.post(self.endpoint, json=jbody) as response:
                    if response.status == 401:
                        raise DinghyError(
                            "Unauthorized. You need to create a GITHUB_TOKEN environment variable."
                        )
                    if response.status in {403, 502} and trynum < NUM_TRIES - 1:
                        # GitHub sometimes gives us these. 403 seems like an ad-hoc
                        # unreported rate limit.  502 seems like straight-up
                        # flakiness.  If we wait them out, it goes away.
                        logger.debug(f"Wait out a 403... {total_wait} so far.")
                        await asyncio.sleep(PAUSE)
                        total_wait += PAUSE
                        continue
                    response.raise_for_status()
                    self.save_rate_limit(_summarize_rate_limit(response))
                    return await response.json()

    async def execute(self, query, variables=None):
        """
        Execute one GraphQL query, with logging, retrying, and error handling.
        """
        logger.debug(_query_synopsis(query, variables))

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

        # $set_env.py: DINGHY_SAVE_RESPONSES - save every query response in a JSON file.
        if int(os.environ.get("DINGHY_SAVE_RESPONSES", 0)):
            json_name = next(self.json_names)
            await json_save(data, json_name)
            logger.info(f"Wrote query data: {json_name}")

        _raise_if_error(data)
        return data

    async def nodes(self, query, variables=None, donefn=None, clear_nodes=True):
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
            if fetched is None:
                raise DinghyError(
                    "Query returned no data, you may need more permissions in your token: "
                    + _query_synopsis(query, variables)
                )
            nodes.extend(fetched["nodes"])
            if not fetched["pageInfo"]["hasNextPage"]:
                break
            if donefn is not None and donefn(fetched["nodes"]):
                break
            variables["after"] = fetched["pageInfo"]["endCursor"]
        # Remove the nodes from the top-level data we return, to keep things clean.
        if clear_nodes:
            fetched["nodes"] = []
        else:
            fetched["nodes"] = nodes
        return data, nodes


# $set_env.py: DINGHY_FAKE_PAGE - smaller page size to force pagination
FAKE_PAGE = int(os.environ.get("DINGHY_FAKE_PAGE", 0))


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

    full_query = "\n".join(query)
    if FAKE_PAGE:
        full_query = full_query.replace("first: 100", f"first: {FAKE_PAGE}")
    return full_query
