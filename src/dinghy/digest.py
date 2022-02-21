"""
Summarize issue activity in GitHub repos and projects.
"""

import asyncio
import datetime
import itertools
import operator
import os
import re
import urllib.parse

import yaml
from glom import glom as g

from .graphql_helpers import build_query, GraphqlHelper
from .helpers import json_save, parse_timedelta
from .jinja_helpers import render_jinja_to_file


class Digester:
    """
    Use GitHub GraphQL to get data about recent changes.
    """

    def __init__(self, since, options):
        self.since = since.strftime("%Y-%m-%dT%H:%M:%S")
        token = os.environ.get("GITHUB_TOKEN", "")
        self.gql = GraphqlHelper("https://api.github.com/graphql", token)
        self.bots = options.get("bots", [])

    async def get_repo_issues(self, owner, name):
        """
        Get issues from a repo updated since a date, with comments since that date.

        Args:
            owner (str): the owner of the repo.
            name (str): the name of the repo.

        """
        repo, issues = await self.gql.nodes(
            query=build_query("repo_issues.graphql"),
            path="repository.issues",
            variables=dict(owner=owner, name=name, since=self.since),
        )
        issues = await self._process_items(issues)
        repo = g(repo, "data.repository")
        repo["container_kind"] = "repo"
        repo["kind"] = "issues"
        return repo, issues

    async def get_project_items(self, org, number, home_repo=""):
        """
        Get items from a project.

        Args:
            org (str): the organization owner of the repo.
            number (int|str): the project number.
            home_repo (str): the owner/name of a repo that most items are in.
        """
        project, project_data = await self.gql.nodes(
            query=build_query("project_items.graphql"),
            path="organization.project.items",
            variables=dict(org=org, projectNumber=int(number)),
        )
        items = [content for data in project_data if (content := data["content"])]
        items = await self._process_items(items)
        for item in items:
            item["other_repo"] = item["repository"]["nameWithOwner"] != home_repo
            if "comments_to_show" not in item:
                item["comments_to_show"] = item["comments"]["nodes"]
        project = g(project, "data.organization.project")
        project["container_kind"] = "project"
        project["kind"] = "items"
        return project, items

    async def get_repo_pull_requests(self, owner, name):
        """
        Get pull requests from a repo updated since a date, with comments since that date.

        Args:
            owner (str): the owner of the repo.
            name (str): the name of the repo.
        """
        repo, pulls = await self.gql.nodes(
            query=build_query("repo_pull_requests.graphql"),
            path="repository.pullRequests",
            variables=dict(owner=owner, name=name),
            donefn=(lambda nodes: nodes[-1]["updatedAt"] < self.since),
        )
        pulls = await self._process_items(pulls)

        repo = g(repo, "data.repository")
        repo["container_kind"] = "repo"
        repo["kind"] = "pull requests"
        return repo, pulls

    async def get_org_pull_requests(self, org):
        """
        Get pull requests across an organization.  Uses GitHub search.
        """
        search_terms = {
            "org": org,
            "is": "pr",
            "updated": f">{self.since}",
        }
        search_query = " ".join(f"{k}:{v}" for k, v in search_terms.items())
        _, pulls = await self.gql.nodes(
            query=build_query("search_items.graphql"),
            path="search",
            variables=dict(query=search_query),
        )
        pulls = await self._process_items(pulls)
        url_q = urllib.parse.quote_plus(search_query)
        search = {
            "query": search_query,
            "url": f"https://github.com/search?q={url_q}&type=issues",
            "container_kind": "search",
            "kind": "pull requests",
        }
        return search, pulls

    def method_from_url(self, url):
        """
        Dispatch to a get_* method from a GitHub URL.

        Args:
            url (str): A GitHub URL

        Returns:
            A method, and a dict of **kwargs.

        """
        for rx, fn in [
            (
                r"https://github.com/(?P<owner>.*?)/(?P<name>.*?)/issues",
                self.get_repo_issues,
            ),
            (
                r"https://github.com/(?P<owner>.*?)/(?P<name>.*?)/pulls",
                self.get_repo_pull_requests,
            ),
            (
                r"https://github.com/orgs/(?P<org>.*?)/projects/(?P<number>\d+)",
                self.get_project_items,
            ),
        ]:
            if match_url := re.fullmatch(rx, url):
                return fn, match_url.groupdict()

        raise Exception(f"Can't understand URL {url!r}")

    def _trim_unwanted(self, nodes):
        """
        Trim a list to keep only activity since `self.since`, and only by real
        users.

        The returned list is also sorted by updatedAt date.
        """
        nodes = (n for n in nodes if n["updatedAt"] > self.since)
        nodes = (n for n in nodes if n["author"]["__typename"] == "User")
        nodes = (n for n in nodes if n["author"]["login"] not in self.bots)
        nodes = sorted(nodes, key=operator.itemgetter("updatedAt"))
        return nodes

    def _trim_author_type(self, nodes):
        """
        Keep only things authored by users, not bots.
        """
        return nodes

    async def _process_items(self, items):
        """
        Process items after they've been retrieved.

        Keep only things updated since our date, and sort them.
        """
        items = self._trim_unwanted(items)
        items = await asyncio.gather(*map(self._process_item, items))
        return items

    async def _process_item(self, item):
        """
        Apply item-specific processing to an item.
        """
        if item["__typename"] == "Issue":
            await self._process_issue(item)
        elif item["__typename"] == "PullRequest":
            await self._process_pull_request(item)
        self._add_reasons(item)
        return item

    async def _process_issue(self, issue):
        """
        Add more comments to an issue.

        We can't paginate the comments on issues while paginating issues, so
        this method gets the rest of the comments.

        Args:
            issue (dict): the issue to populate.

        """
        if issue["comments"]["totalCount"] > len(issue["comments"]["nodes"]):
            comments = await self.gql.nodes(
                query=build_query("issue_comments.graphql"),
                path="repository.issue.comments",
                variables=dict(
                    owner=issue["repository"]["owner"]["login"],
                    name=issue["repository"]["name"],
                    number=issue["number"],
                ),
            )
        else:
            comments = issue["comments"]["nodes"]
        issue["comments_to_show"] = self._trim_unwanted(comments)

    async def _process_pull_request(self, pull):
        """
        Do extra work to make a pull request right for reporting.
        """
        # Pull requests have complex trees of data, with comments in
        # multiple places, and duplications.  Reviews can also be finished
        # with no comment, but we want them to appear in the digest.
        comments = {}
        reviews = itertools.chain(
            pull["latestReviews"]["nodes"],
            pull["latestOpinionatedReviews"]["nodes"],
            pull["reviews"]["nodes"],
        )
        for rev in reviews:
            had_comment = False
            for com in rev["comments"]["nodes"]:
                com = comments.setdefault(com["id"], dict(com))
                com["review_state"] = rev["state"]
                had_comment = True
            if rev["body"] or not had_comment:
                # A completed review with no comment, make it into a comment.
                com = comments.setdefault(rev["id"], dict(rev))
                com["review_state"] = rev["state"]
        for thread in pull["reviewThreads"]["nodes"]:
            for com in thread["comments"]["nodes"]:
                comments.setdefault(com["id"], com)
        for com in pull["comments"]["nodes"]:
            comments.setdefault(com["id"], com)

        pull["comments_to_show"] = self._trim_unwanted(comments.values())

    def _add_reasons(self, item):
        """
        Populate an item with the reasons it's been included.

        Args:
            item (dict): the issue or pull request data.

        """
        item["reasonCreated"] = item["createdAt"] > self.since
        item["reasonClosed"] = bool(
            item["closedAt"] and (item["closedAt"] > self.since)
        )
        item["reasonMerged"] = bool(
            item.get("mergedAt") and (item["mergedAt"] > self.since)
        )


def task_from_item(digester, item):
    """
    Parse a single item, and make a digester task for it.
    """
    url = None
    if isinstance(item, str):
        url = item
        more_kwargs = {}
    elif "url" in item:
        url = item["url"]
        more_kwargs = dict(item)
        more_kwargs.pop("url")
    if url:
        fn, kwargs = digester.method_from_url(url)
        try:
            task = fn(**kwargs, **more_kwargs)
        except TypeError as type_err:
            raise Exception(f"Problem with config item: {item}: {type_err}") from None
    else:
        if "pull_requests" in item:
            where = item["pull_requests"]
            if where.startswith("org:"):
                org = where.partition(":")[2]
                task = digester.get_org_pull_requests(org)
            else:
                raise Exception(f"Don't understand pull_requests scope: {where!r}")
        else:
            raise Exception(f"Don't understand item: {item!r}")
    return task


async def make_digest(since, items, digest, **options):
    """
    Make a single digest.

    Args:
        since (str): a duration spec ("2 day", "3d6h", etc).
        items (list[str|dict]): a list of YAML objects or GitHub URLs to collect items from.
        digest (str): the HTML file name to write.

    """
    since_date = datetime.datetime.now() - parse_timedelta(since)
    digester = Digester(since=since_date, options=options)

    tasks = [task_from_item(digester, item) for item in items]
    results = await asyncio.gather(*tasks)

    # $set_env.py: DIGEST_SAVE_RESULT - save digest data in a JSON file.
    if int(os.environ.get("DIGEST_SAVE_RESULT", 0)):
        json_name = digest.replace(".html", ".json")
        await json_save(results, json_name)
        print(f"Wrote results data: {json_name}")

    await render_jinja_to_file(
        "digest.html.j2", digest, results=results, since=since_date
    )
    print(f"Wrote digest: {digest}")


async def make_digests(conf_file):
    """
    Make all the digests specified by a configuration file.

    Args:
        conf_file (str): the yaml configuration file name.

    """
    with open(conf_file, encoding="utf-8") as y:
        config = yaml.safe_load(y)
    await asyncio.gather(*(make_digest(**spec) for spec in config))


def main(conf_file="dinghy.yaml"):
    """
    Digest all the things!
    """
    try:
        asyncio.run(make_digests(conf_file))
    finally:
        print(GraphqlHelper.last_rate_limit())
