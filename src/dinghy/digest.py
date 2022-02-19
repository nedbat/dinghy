"""
Summarize issue activity in GitHub repos and projects.
"""

import asyncio
import datetime
import itertools
import operator
import os
import re

import aiofiles
import yaml
from glom import glom as g

from .graphql_helpers import build_query, GraphqlHelper
from .helpers import json_save, parse_timedelta
from .jinja_helpers import render_jinja


class Summarizer:
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
            number (int): the project number.
            home_repo (str): the owner/name of a repo that most issues are in.
        """
        project, project_data = await self.gql.nodes(
            query=build_query("project_issues.graphql"),
            path="organization.project.items",
            variables=dict(org=org, projectNumber=number),
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

    async def get_pull_requests(self, owner, name):
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
        repo = g(repo, "data.repository")
        repo["container_kind"] = "repo"
        repo["kind"] = "pull requests"
        return repo, pulls

    def methods_from_url(self, url):
        """Dispatch to a get_* method from a GitHub url."""
        if m := re.fullmatch(r"https://github.com/(.*?)/(.*?)/issues", url):
            return self.get_repo_issues, m[1], m[2]
        elif m := re.fullmatch(r"https://github.com/(.*?)/(.*?)/pulls", url):
            return self.get_pull_requests, m[1], m[2]
        elif m := re.fullmatch(r"https://github.com/orgs/(.*?)/projects/(\d+)", url):
            return self.get_project_issues, m[1], int(m[2])
        else:
            raise Exception(f"Can't understand URL {url!r}")

    def _trim_since(self, nodes):
        nodes = [n for n in nodes if n["updatedAt"] > self.since]
        nodes.sort(key=operator.itemgetter("updatedAt"))
        return nodes

    async def _populate_issue_comments(self, issues):
        # Need to get full comments.
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

    def _add_reasons(self, issues):
        # Why were these issues in the list?
        for iss in issues:
            iss["reasonCreated"] = iss["createdAt"] > self.since
            iss["reasonClosed"] = bool(
                iss["closedAt"] and (iss["closedAt"] > self.since)
            )
            iss["reasonMerged"] = bool(
                iss.get("mergedAt") and (iss["mergedAt"] > self.since)
            )


async def make_digest(since, items, digest):
    since_date = datetime.datetime.now() - parse_timedelta(since)
    summarizer = Summarizer(since=since_date)
    tasks = [fn(*args) for fn, *args in map(summarizer.methods_from_url, items)]
    results = await asyncio.gather(*tasks)
    # $set_env.py: DIGEST_SAVE_RESULT - save digest data in a JSON file.
    if int(os.environ.get("DIGEST_SAVE_RESULT", 0)):
        await json_save(results, "out_digest.json")
    html = render_jinja("digest.html.j2", results=results, since=since_date)
    async with aiofiles.open(digest, "w", encoding="utf-8") as html_out:
        await html_out.write(html)


async def make_digests(conf_file):
    with open(conf_file, encoding="utf-8") as y:
        config = yaml.safe_load(y)
    await asyncio.gather(*(make_digest(**spec) for spec in config))


def main(conf_file="dinghy.yaml"):
    """
    Digest all the things!
    """
    asyncio.run(make_digests(conf_file))
