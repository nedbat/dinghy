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

    def __init__(self, since):
        self.since = since.strftime("%Y-%m-%dT%H:%M:%S")
        token = os.environ.get("GITHUB_TOKEN", "")
        self.gql = GraphqlHelper("https://api.github.com/graphql", token)

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
        issues = await self._populate_issue_comments(issues)
        self._add_reasons(issues)
        for iss in issues:
            iss["comments_to_show"] = iss["comments"]["nodes"]
        repo = g(repo, "data.repository")
        repo["container_kind"] = "repo"
        repo["kind"] = "issues"
        return repo, issues

    async def get_project_issues(self, org, number, home_repo=""):
        """
        Get issues from a project.

        Args:
            org (str): the organization owner of the repo.
            number (int|str): the project number.
            home_repo (str): the owner/name of a repo that most issues are in.
        """
        project, project_data = await self.gql.nodes(
            query=build_query("project_issues.graphql"),
            path="organization.project.items",
            variables=dict(org=org, projectNumber=int(number)),
        )
        issues = [content for data in project_data if (content := data["content"])]
        issues = self._trim_since(issues)
        issues = await self._populate_issue_comments(issues)
        self._add_reasons(issues)
        for iss in issues:
            iss["other_repo"] = iss["repository"]["nameWithOwner"] != home_repo
            iss["comments_to_show"] = iss["comments"]["nodes"]
        project = g(project, "data.organization.project")
        project["container_kind"] = "project"
        project["kind"] = "issues"
        return project, issues

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
        self._process_pull_requests(pulls)

        repo = g(repo, "data.repository")
        repo["container_kind"] = "repo"
        repo["kind"] = "pull requests"
        return repo, pulls

    def _process_pull_requests(self, pulls):
        """
        Do extra work to make pull requests right for reporting.
        """
        pulls = self._trim_since(pulls)
        for pull in pulls:
            # Pull requests have complex trees of data, with comments in
            # multiple places, and duplications.  Reviews can also be finished
            # with no comment, but we want them to appear in the digest.
            comments = {}
            reviews = itertools.chain(
                pull["latestReviews"]["nodes"],
                pull["latestOpinionatedReviews"]["nodes"],
            )
            for rev in reviews:
                ncom = 0
                for com in rev["comments"]["nodes"]:
                    com = comments.setdefault(com["id"], dict(com))
                    com["review_state"] = rev["state"]
                    ncom += 1
                if ncom == 0:
                    # A completed review with no comment, make it into a comment.
                    com = comments.setdefault(rev["id"], dict(rev))
                    com["review_state"] = rev["state"]
            for thread in pull["reviewThreads"]["nodes"]:
                for com in thread["comments"]["nodes"]:
                    comments.setdefault(com["id"], com)
            for com in pull["comments"]["nodes"]:
                comments.setdefault(com["id"], com)

            pull["comments_to_show"] = self._trim_since(comments.values())

        self._add_reasons(pulls)

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
        self._process_pull_requests(pulls)
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
                self.get_project_issues,
            ),
        ]:
            if match_url := re.fullmatch(rx, url):
                return fn, match_url.groupdict()

        raise Exception(f"Can't understand URL {url!r}")

    def _trim_since(self, nodes):
        """
        Trim a list to keep only activity since `self.since`.

        The returned list is also sorted by updatedAt date.
        """
        nodes = [n for n in nodes if n["updatedAt"] > self.since]
        nodes.sort(key=operator.itemgetter("updatedAt"))
        return nodes

    async def _populate_issue_comments(self, issues):
        """
        Add more comments to issues.

        We can't paginate the comments on issues while paginating issues, so
        this method gets the rest of the comments.

        Args:
            issues (list[dict]): the issues to populate.

        """
        queried_issues = []
        issue_queries = []
        for iss in issues:
            if iss["comments"]["totalCount"] > len(iss["comments"]["nodes"]):
                queried_issues.append(iss)
                comments = self.gql.nodes(
                    query=build_query("issue_comments.graphql"),
                    path="repository.issue.comments",
                    variables=dict(
                        owner=iss["repository"]["owner"]["login"],
                        name=iss["repository"]["name"],
                        number=iss["number"],
                    ),
                )
                issue_queries.append(comments)
        commentss = await asyncio.gather(*issue_queries)
        for iss, (_, comments) in zip(queried_issues, commentss):
            iss["comments"]["nodes"] = comments

        # Trim comments to those since our since date.
        for iss in issues:
            comments = iss["comments"]
            comments["nodes"] = self._trim_since(comments["nodes"])

        return issues

    def _add_reasons(self, items):
        """
        Populate items with the reasons they've been included.

        Args:
            items (list[dict]): the issues or pull requests data.

        """
        for item in items:
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


async def make_digest(since, items, digest):
    """
    Make a single digest.

    Args:
        since (str): a duration spec ("2 day", "3d6h", etc).
        items (list[str|dict]): a list of YAML objects or GitHub URLs to collect items from.
        digest (str): the HTML file name to write.

    """
    since_date = datetime.datetime.now() - parse_timedelta(since)
    digester = Digester(since=since_date)

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
