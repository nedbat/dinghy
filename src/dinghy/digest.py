"""
Summarize issue activity in GitHub repos and projects.
"""

import asyncio
import datetime
import json
import operator
import os
import re
import urllib.parse

import yaml
from glom import glom as g

from . import __version__
from .graphql_helpers import build_query, GraphqlHelper
from .helpers import DinghyError, json_save, parse_timedelta
from .jinja_helpers import render_jinja_to_file


class Digester:
    """
    Use GitHub GraphQL to get data about recent changes.
    """

    def __init__(self, since, options):
        self.since = since.strftime("%Y-%m-%dT%H:%M:%S")
        token = os.environ.get("GITHUB_TOKEN", "")
        self.gql = GraphqlHelper("https://api.github.com/graphql", token)
        self.ignore_users = options.get("ignore_users", [])

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

    async def get_repo_items(self, owner, name):
        """
        Get issues and pull requests from a repo.
        """
        (repo, issues), (_, pull_requests) = await asyncio.gather(
            self.get_repo_issues(owner, name),
            self.get_repo_pull_requests(owner, name),
        )
        repo["kind"] = "issues and pull requests"
        items = self._trim_unwanted(issues + pull_requests)
        return repo, items

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
                r"https://github.com/(?P<owner>[^/]+)/(?P<name>[^/]+)/issues/?",
                self.get_repo_issues,
            ),
            (
                r"https://github.com/(?P<owner>[^/]+)/(?P<name>[^/]+)/pulls/?",
                self.get_repo_pull_requests,
            ),
            (
                r"https://github.com/(?P<owner>[^/]+)/(?P<name>[^/]+)/?",
                self.get_repo_items,
            ),
            (
                r"https://github.com/orgs/(?P<org>[^/]+)/projects/(?P<number>\d+)/?",
                self.get_project_items,
            ),
        ]:
            if match_url := re.fullmatch(rx, url):
                return fn, match_url.groupdict()

        raise DinghyError(f"Can't understand URL {url!r}")

    def _trim_unwanted(self, nodes):
        """
        Trim a list to keep only activity since `self.since`, and only by real
        users.

        The returned list is also sorted by updatedAt date.
        """
        nodes = (n for n in nodes if n["updatedAt"] > self.since)
        nodes = (n for n in nodes if n["author"]["__typename"] == "User")
        nodes = (n for n in nodes if n["author"]["login"] not in self.ignore_users)
        nodes = sorted(nodes, key=operator.itemgetter("updatedAt"))
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
        reviews = {}
        seen = set()
        for rev in pull["reviews"]["nodes"]:
            rev["show"] = True
            rev["review_state"] = rev["state"]
            reviews[rev["id"]] = rev

        for thread in pull["reviewThreads"]["nodes"]:
            com0 = thread["comments"]["nodes"][0]
            com0["comments_to_show"] = thread["comments"]["nodes"][1:]
            rev_id = com0["pullRequestReview"]["id"]
            review_comments = reviews[rev_id].setdefault("comments_to_show", [])
            review_comments.append(com0)
            seen.add(com0["id"])
            for com in com0["comments_to_show"]:
                seen.add(com["id"])
                rev_id = com["pullRequestReview"]["id"]
                seen.add(rev_id)
                reviews[rev_id]["show"] = False

        for rev in reviews.values():
            if not rev["show"]:
                continue
            had_comment = False
            for com in rev["comments"]["nodes"]:
                com_id = com["id"]
                if com_id in seen or com_id in comments:
                    continue
                comments[com_id] = com
                com["review_state"] = rev["state"]
                had_comment = True
            if rev["body"] or not had_comment:
                # A completed review with no comment, make it into a comment.
                com = comments.setdefault(rev["id"], dict(rev))
                com["review_state"] = rev["state"]

            if not rev["body"] and len(rev["comments"]["nodes"]) == 1:
                # A review with just one comment and no body: the comment should
                # go where they review would have been.
                com = rev["comments_to_show"][0]
                com["review_state"] = rev["review_state"]
                comments[com["id"]] = com
                rev["show"] = False
                del comments[rev["id"]]

            if rev["show"]:
                comments[rev["id"]] = rev

        for com in pull["comments"]["nodes"]:
            comments[com["id"]] = com

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


def coro_from_item(digester, item):
    """
    Parse a single item, and make a digester coro for it.
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
            coro = fn(**kwargs, **more_kwargs)
        except TypeError as type_err:
            raise DinghyError(f"Problem with config item: {item}: {type_err}") from None
    else:
        if "pull_requests" in item:
            where = item["pull_requests"]
            if where.startswith("org:"):
                org = where.partition(":")[2]
                coro = digester.get_org_pull_requests(org)
            else:
                raise DinghyError(f"Don't understand pull_requests scope: {where!r}")
        else:
            raise DinghyError(f"Don't understand item: {item!r}")
    return coro


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

    coros = []
    for item in items:
        try:
            coros.append(coro_from_item(digester, item))
        except:
            for coro in coros:
                coro.close()
            raise
    results = await asyncio.gather(*coros)

    # $set_env.py: DIGEST_SAVE_RESULT - save digest data in a JSON file.
    if int(os.environ.get("DIGEST_SAVE_RESULT", 0)):
        json_name = digest.replace(".html", ".json")
        await json_save(results, json_name)
        print(f"Wrote results data: {json_name}")

    await render_jinja_to_file(
        "digest.html.j2",
        digest,
        results=results,
        since=since_date,
        now=datetime.datetime.now(),
        __version__=__version__,
    )
    print(f"Wrote digest: {digest}")


async def make_digests(conf_file):
    """
    Make all the digests specified by a configuration file.

    Args:
        conf_file (file): an open file object to read the configuration from.

    """
    config = yaml.safe_load(conf_file)
    defaults = config.get("defaults", {})
    coros = []
    for spec in config.get("digests", []):
        args = {**defaults, **spec}
        coros.append(make_digest(**args))
    await asyncio.gather(*coros)


def just_render(result_file):
    """Helper function to re-render stored results.

    For iterating on rendering changes without using up GitHub rate limits.

    $ python -c "import sys,dinghy.digest as dd; dd.just_render(sys.argv[1])" /tmp/lots.json

    """
    with open(result_file, encoding="utf-8") as j:
        results = json.load(j)

    asyncio.run(
        render_jinja_to_file(
            "digest.html.j2",
            result_file.replace(".json", ".html"),
            results=results,
            since=datetime.datetime.now(),
            now=datetime.datetime.now(),
        )
    )
