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


logger = logging.getLogger(__name__)

GITHUB_URL_MAP = []


def github_route(url_pattern):
    """A decorator to associate a GitHub URL path regex with a Digester.get_ method.

    The regexes will be tried in the order the decorator is used in the class,
    so be careful if a path could match multiple patterns.
    """

    def _dec(func):
        GITHUB_URL_MAP.append((url_pattern, func.__name__))
        return func

    return _dec


class Digester:
    """
    Use GitHub GraphQL to get data about recent changes.
    """

    def __init__(self, since, options):
        self.since = since.strftime("%Y-%m-%dT%H:%M:%S")
        self.ignore_users = options.get("ignore_users", [])
        self.user_types = {"User"}
        if options.get("include_bots", False):
            self.user_types.add("Bot")
        self.api_root = options.get("api_root")
        self.github = "github.com"
        self.gql = None

    def prepare(self):
        """Create the network helpers we need."""
        token = os.environ.get("GITHUB_TOKEN", "")
        api_root = self.api_root or f"https://api.{self.github}/graphql"
        self.gql = GraphqlHelper(api_root, token)

    @github_route(r"/orgs/(?P<org>[^/]+)/projects/(?P<number>\d+)/?")
    async def get_org_project_entries(self, org, number, home_repo="", title=None):
        """
        Get entries from a organization project.

        Args:
            org (str): the organization owner of the repo.
            number (int|str): the project number.
            home_repo (str): the owner/name of a repo that most entries are in.
        """
        project, project_data = await self.gql.nodes(
            query=build_query("org_project_entries.graphql"),
            variables=dict(org=org, projectNumber=int(number)),
        )
        entries = [content for data in project_data if (content := data["content"])]
        entries = await self._process_entries(entries)
        for entry in entries:
            entry["other_repo"] = entry["repository"]["nameWithOwner"] != home_repo
            if "children" not in entry:
                entry["children"] = entry["comments"]["nodes"]
        project = glom(project, "data.organization.project")
        container = {
            "url": project["url"],
            "container_kind": "project",
            "title": title or project["title"],
            "kind": "items",
            "entries": entries,
        }
        return container

    async def get_search_results(self, query, title=None):
        """
        Get issues or pull requests returned by a search query.
        """
        query += f" updated:>{self.since}"
        _, entries = await self.gql.nodes(
            query=build_query("search_entries.graphql"),
            variables=dict(query=query),
        )
        entries = await self._process_entries(entries)
        for entry in entries:
            entry["other_repo"] = True
        url_q = urllib.parse.quote_plus(query)
        if "is:pr" in query:
            kind = "pull requests"
        elif "is:issue" in query:
            kind = "issues"
        else:
            kind = "items"
        container = {
            "url": f"https://{self.github}/search?q={url_q}&type=issues",
            "container_kind": "search",
            "title": title or query,
            "kind": kind,
            "entries": entries,
        }
        return container

    @github_route(r"/(?P<owner>[^/]+)/(?P<name>[^/]+)/?")
    async def get_repo_entries(self, owner, name, title=None):
        """
        Get issues, pull requests, and releases from a repo.
        """
        issue_container, pr_container, release_container = await asyncio.gather(
            self.get_repo_issues(owner, name, title=title),
            self.get_repo_pull_requests(owner, name),
            self.get_repo_releases(owner, name),
        )
        entries = (
            issue_container["entries"]
            + pr_container["entries"]
            + release_container["entries"]
        )
        entries = self._trim_unwanted(entries)
        container = {
            **issue_container,
            "kind": "issues, pull requests, and releases",
            "entries": entries,
        }
        return container

    @github_route(r"/(?P<owner>[^/]+)/(?P<name>[^/]+)/issues/?")
    async def get_repo_issues(self, owner, name, title=None):
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
            "title": title or repo["nameWithOwner"],
            "kind": "issues",
            "entries": issues,
        }
        return container

    @github_route(r"/(?P<owner>[^/]+)/(?P<name>[^/]+)/releases/?")
    async def get_repo_releases(self, owner, name, title=None):
        """
        Get releases from a repo updated since a date

        Args:
            owner (str): the owner of the repo.
            name (str): the name of the repo.
        """
        repo, releases = await self.gql.nodes(
            query=build_query("repo_releases.graphql"),
            variables=dict(owner=owner, name=name, since=self.since),
        )
        releases = await self._process_entries(releases)
        repo = glom(repo, "data.repository")
        container = {
            "url": repo["url"],
            "container_kind": "repo",
            "title": title or repo["nameWithOwner"],
            "kind": "releases",
            "entries": releases,
        }
        return container

    @github_route(r"/(?P<owner>[^/]+)/(?P<name>[^/]+)/pulls/?")
    async def get_repo_pull_requests(self, owner, name, title=None):
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
            "title": title or repo["nameWithOwner"],
            "kind": "pull_requests",
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
        parsed = urllib.parse.urlparse(url)
        self.github = parsed.netloc
        for rx, fn_name in GITHUB_URL_MAP:
            if match_url := re.fullmatch(rx, parsed.path):
                return getattr(self, fn_name), match_url.groupdict()

        raise DinghyError(f"Can't understand URL {url!r}")

    async def get_more(
        self, container, graphql, id
    ):  # pylint: disable=redefined-builtin
        """
        If the `container` isn't full yet, get all the nodes.
        """
        if container["totalCount"] > len(container["nodes"]):
            _, all_nodes = await self.gql.nodes(
                query=build_query(graphql),
                variables=dict(id=id),
            )
            container["nodes"] = all_nodes

    def _node_is_interesting(self, node):
        """
        Is a node interesting to show? It has to be new enough, by a real user,
        and not by someone we want to ignore.
        """
        return (
            node["updatedAt"] > self.since
            and node["author"]["__typename"] in self.user_types
            and node["author"]["login"] not in self.ignore_users
        )

    def _trim_unwanted(self, nodes):
        """
        Trim a list to keep only activity since `self.since`, and only by real
        users.

        The returned list is also sorted by updatedAt date.
        """
        nodes = (n for n in nodes if self._node_is_interesting(n))
        nodes = sorted(nodes, key=operator.itemgetter("updatedAt"))
        return nodes

    def _fix_ghosts(self, obj):
        """
        GitHub has a @ghost account for deleted users. That shows up in our
        data as None.  Fix those to have data we can use.
        """
        if isinstance(obj, list):
            for elt in obj:
                self._fix_ghosts(elt)
        elif isinstance(obj, dict):
            for key in obj:
                if key == "author":
                    if obj["author"] is None:
                        obj["author"] = {
                            "__typename": "User",
                            "login": "ghost",
                        }
                else:
                    self._fix_ghosts(obj[key])

    async def _process_entries(self, entries):
        """
        Process entries after they've been retrieved.

        Keep only things updated since our date, and sort them.
        """
        # $set_env.py: DINGHY_SAVE_ENTRIES - save each entry in its own JSON file.
        if int(os.environ.get("DINGHY_SAVE_ENTRIES", 0)):
            for entry in entries:
                try:
                    kind = entry["__typename"].lower()
                    num = entry["number"]
                except KeyError:
                    pass
                else:
                    await json_save(entry, f"save_{kind}_{num}.json")

        self._fix_ghosts(entries)

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
        await self.get_more(issue["comments"], "issue_comments.graphql", issue["id"])
        issue["children"] = self._trim_unwanted(issue["comments"]["nodes"])

    async def _process_pull_request(self, pull):
        """
        Do extra work to make a pull request right for reporting.
        """
        # Pull requests have complex trees of data, with comments in
        # multiple places, and duplications.  Reviews can also be finished
        # with no comment, but we want them to appear in the digest.
        #
        # Pull requests have:
        #   comments:
        #       Standalone comments that should always be included
        #   reviews:
        #       Each is a review by a person, who can add comments all over the
        #       pull request, including in different threads.
        #   reviewThreads:
        #       Each is a sequence of comments that follow one another.
        #

        # Pull all the data from paginated components.
        await asyncio.gather(
            self.get_more(pull["comments"], "pr_comments.graphql", pull["id"]),
            self.get_more(pull["reviews"], "pr_reviews.graphql", pull["id"]),
            self.get_more(
                pull["reviewThreads"], "pr_reviewthreads.graphql", pull["id"]
            ),
        )

        coros = []
        coros.extend(
            self.get_more(r["comments"], "review_comments.graphql", r["id"])
            for r in pull["reviews"]["nodes"]
        )
        coros.extend(
            self.get_more(rt["comments"], "reviewthread_comments.graphql", rt["id"])
            for rt in pull["reviewThreads"]["nodes"]
        )
        await asyncio.gather(*coros)

        children = {}
        reviews = {}

        # Make a map of the reviews.
        for rev in pull["reviews"]["nodes"]:
            rev["review_state"] = rev["state"]
            reviews[rev["id"]] = rev

        # For each thread, attach the thread as a child of the review.  Each
        # comment in the thread can be from a different review (as people
        # respond to each other).  The whole thread will be attached to the
        # review for the first comment.  Make comments 2-N as children of
        # comment 1.
        for thread in pull["reviewThreads"]["nodes"]:
            com0 = thread["comments"]["nodes"][0]
            com0["children"] = thread["comments"]["nodes"][1:]
            com0["isResolved"] = thread["isResolved"]
            rev_id = com0["pullRequestReview"]["id"]
            review_comments = reviews[rev_id].setdefault("children", [])
            review_comments.append(com0)

        # For each review, show it if it has a body, or if it has children, or
        # if it's not just "COMMENTED".
        for rev in reviews.values():
            if rev["bodyText"] or rev.get("children") or rev["state"] != "COMMENTED":
                com = children.setdefault(rev["id"], dict(rev))
                com["review_state"] = rev["state"]

                if not rev["bodyText"] and len(rev.get("children", ())) == 1:
                    # A review with just one comment and no body: the comment should
                    # go where the review would have been.
                    com = rev["children"][0]
                    com["review_state"] = rev["review_state"]
                    children[rev["id"]] = com

        # Comments are simple: they all get shown.
        for com in pull["comments"]["nodes"]:
            children[com["id"]] = com

        # Examine all the resulting threads (children). Keep a thread if it has
        # any comments newer than our since date.  Mark older comments as old.
        kids, _ = self._trim_unwanted_tree(children.values())
        pull["children"] = kids

    def _trim_unwanted_tree(self, nodes):
        """
        Trim a nested list to indicate activity since `self.since`.  A thread
        will be kept if any of its children is newer than since.  Items older
        than that will get ["boring"]=True, and shown grayed in the output.
        """
        keep = []
        any_interesting_total = False
        for node in nodes:
            if self._node_is_interesting(node):
                any_interesting = True
            else:
                any_interesting = False
                node["boring"] = True
            kids, any_interesting_kids = self._trim_unwanted_tree(
                node.get("children", ())
            )
            if any_interesting or any_interesting_kids:
                node["children"] = kids
                keep.append(node)
                any_interesting_total = True
        keep = sorted(keep, key=operator.itemgetter("updatedAt"))
        return keep, any_interesting_total

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
    more_kwargs = {}
    if isinstance(item, str):
        url = item
    elif "url" in item:
        more_kwargs = dict(item)
        url = more_kwargs.pop("url")

    if url:
        fn, kwargs = digester.method_from_url(url)
    else:
        if "search" in item:
            kwargs = dict(item)
            kwargs["query"] = kwargs.pop("search")
            fn = digester.get_search_results
        else:
            raise DinghyError(f"Don't understand item: {item!r}")

    try:
        coro = fn(**kwargs, **more_kwargs)
    except TypeError as type_err:
        raise DinghyError(f"Problem with config item: {item}: {type_err}") from None

    return coro


async def make_digest(items, since="1 week", digest="digest.html", **options):
    """
    Make a single digest.

    Args:
        since (str): a duration spec ("2 day", "3d6h", etc).
        items (list[str|dict]): a list of YAML objects or GitHub URLs to collect entries from.
        digest (str): the HTML file name to write.

    """
    if since == "forever":
        show_date = False
        since_date = datetime.datetime(year=1980, month=1, day=1)
    else:
        show_date = True
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

    digester.prepare()
    results = await asyncio.gather(*coros)

    # $set_env.py: DINGHY_SAVE_RESULT - save digest data in a JSON file.
    if int(os.environ.get("DINGHY_SAVE_RESULT", 0)):
        json_name = digest.replace(".html", ".json")
        await json_save(results, json_name)
        logger.info(f"Wrote results data: {json_name}")

    await render_jinja_to_file(
        "digest.html.j2",
        digest,
        results=results,
        since=since_date if show_date else None,
        now=datetime.datetime.now(),
        __version__=__version__,
        title=options.get("title", ""),
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
