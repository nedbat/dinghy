"""
Summarize issue activity in GitHub repos and projects.
"""

import asyncio
import datetime
import json
import logging
import operator
import os
import re
import urllib.parse

import yaml
from glom import glom

from . import __version__
from .graphql_helpers import build_query, GraphqlHelper
from .helpers import DinghyError, json_save, parse_timedelta
from .jinja_helpers import render_jinja_to_file


logger = logging.getLogger()


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
            variables=dict(owner=owner, name=name, since=self.since),
        )
        issues = await self._process_entries(issues)
        repo = glom(repo, "data.repository")
        container = {
            "url": repo["url"],
            "container_kind": "repo",
            "title": repo["nameWithOwner"],
            "kind": "issues",
            "entries": issues,
        }
        return container

    async def get_project_entries(self, org, number, home_repo=""):
        """
        Get entries from a project.

        Args:
            org (str): the organization owner of the repo.
            number (int|str): the project number.
            home_repo (str): the owner/name of a repo that most entries are in.
        """
        project, project_data = await self.gql.nodes(
            query=build_query("project_entries.graphql"),
            variables=dict(org=org, projectNumber=int(number)),
        )
        entries = [content for data in project_data if (content := data["content"])]
        entries = await self._process_entries(entries)
        for entry in entries:
            entry["other_repo"] = entry["repository"]["nameWithOwner"] != home_repo
            if "comments_to_show" not in entry:
                entry["comments_to_show"] = entry["comments"]["nodes"]
        project = glom(project, "data.organization.project")
        container = {
            "url": project["url"],
            "container_kind": "project",
            "title": project["title"],
            "kind": "items",
            "entries": entries,
        }
        return container

    async def get_repo_pull_requests(self, owner, name):
        """
        Get pull requests from a repo updated since a date, with comments since that date.

        Args:
            owner (str): the owner of the repo.
            name (str): the name of the repo.
        """
        repo, pulls = await self.gql.nodes(
            query=build_query("repo_pull_requests.graphql"),
            variables=dict(owner=owner, name=name),
            donefn=(lambda nodes: nodes[-1]["updatedAt"] < self.since),
        )
        pulls = await self._process_entries(pulls)

        repo = glom(repo, "data.repository")
        container = {
            "url": repo["url"],
            "container_kind": "repo",
            "title": repo["nameWithOwner"],
            "kind": "pull_requests",
            "entries": pulls,
        }
        return container

    async def get_repo_entries(self, owner, name):
        """
        Get issues and pull requests from a repo.
        """
        issue_container, pr_container = await asyncio.gather(
            self.get_repo_issues(owner, name),
            self.get_repo_pull_requests(owner, name),
        )
        entries = issue_container["entries"] + pr_container["entries"]
        entries = self._trim_unwanted(entries)
        container = {
            **issue_container,
            "kind": "issues and pull requests",
            "entries": entries,
        }
        return container

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
            query=build_query("search_entries.graphql"),
            variables=dict(query=search_query),
        )
        pulls = await self._process_entries(pulls)
        url_q = urllib.parse.quote_plus(search_query)
        container = {
            "url": f"https://github.com/search?q={url_q}&type=issues",
            "container_kind": "search",
            "title": search_query,
            "kind": "pull requests",
            "entries": pulls,
        }
        return container

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
                self.get_repo_entries,
            ),
            (
                r"https://github.com/orgs/(?P<org>[^/]+)/projects/(?P<number>\d+)/?",
                self.get_project_entries,
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

    async def _process_entries(self, entries):
        """
        Process entries after they've been retrieved.

        Keep only things updated since our date, and sort them.
        """
        # GitHub has a @ghost account for deleted users.  That shows up in our
        # data as a None author. Fix those.
        for entry in entries:
            if entry["author"] is None:
                entry["author"] = {
                    "__typename": "User",
                    "login": "ghost",
                }

        entries = self._trim_unwanted(entries)
        entries = await asyncio.gather(*map(self._process_entry, entries))
        return entries

    async def _process_entry(self, entry):
        """
        Apply entry-specific processing to an entry.
        """
        if entry["__typename"] == "Issue":
            await self._process_issue(entry)
        elif entry["__typename"] == "PullRequest":
            await self._process_pull_request(entry)
        self._add_reasons(entry)
        return entry

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
            if rev["bodyText"] or not had_comment:
                # A completed review with no comment, make it into a comment.
                com = comments.setdefault(rev["id"], dict(rev))
                com["review_state"] = rev["state"]

            if not rev["bodyText"] and len(rev["comments"]["nodes"]) == 1:
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

    def _add_reasons(self, entry):
        """
        Populate an entry with the reasons it's been included.

        Args:
            entry (dict): the issue or pull request data.

        """
        # write "reasonCreated" based on "createdAt", etc.
        for slug in ["Created", "Closed", "Merged"]:
            at = slug.lower() + "At"
            entry[f"reason{slug}"] = bool(entry.get(at) and entry[at] > self.since)


def coro_from_item(digester, item):
    """
    Parse a single config item, and make a digester coro for it.
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


async def make_digest(items, since="1 week", digest="digest.html", **options):
    """
    Make a single digest.

    Args:
        since (str): a duration spec ("2 day", "3d6h", etc).
        items (list[str|dict]): a list of YAML objects or GitHub URLs to collect entries from.
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
        logger.info(f"Wrote results data: {json_name}")

    await render_jinja_to_file(
        "digest.html.j2",
        digest,
        results=results,
        since=since_date,
        now=datetime.datetime.now(),
        __version__=__version__,
    )
    logger.info(f"Wrote digest: {digest}")


async def make_digests_from_config(conf_file):
    """
    Make all the digests specified by a configuration file.

    Args:
        conf_file (str): a file path to read as a config file.

    """
    try:
        with open(conf_file, encoding="utf-8") as cf:
            config = yaml.safe_load(cf)
    except Exception as err:
        raise DinghyError(f"Couldn't read config file {conf_file!r}: {err}") from err

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
            __version__=__version__,
        )
    )
