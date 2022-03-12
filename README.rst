######
Dinghy
######

Dinghy, a GitHub activity digest tool.

|pypi-badge| |pyversions-badge| |license-badge|

Dinghy uses the GitHub GraphQL API to find recent activity on issues and pull
requests, and writes a compact HTML digest.  The simplest way to run dinghy is
with a GitHub repo URL:

.. code-block:: bash

    $ pip install dinghy
    $ python -m dinghy https://github.com/Me/MyProject
    Wrote digest: digest.html

You will have a digest of the last week's activity in digest.html. It will look
`something like this`__.

__ https://nedbatchelder.com/files/black_dinghy.html

You can also write a YAML configuration file to digest multiple sources, or
with different time periods.


Configuration
=============

Dinghy configuration is read from a YAML file (``dinghy.yaml`` by default).
Here's an example:

.. code-block:: yaml

    digests:
      - digest: lastweek.html
        since: 1 week
        items:
          - https://github.com/orgs/myorg/projects/17
          - https://github.com/orgs/anotherorg/projects/8
          - https://github.com/myorg/myrepo/pulls

      - digest: hotnews.html
        since: 1 day
        items:
          - url: https://github.com/orgs/anotherorg/projects/8
            home_repo: anotherorg/wg
          - https://github.com/myorg/churnchurn/issues

      - digest: all_prs.html
        since: 1 day
        items:
          - pull_requests: org:myorg

    defaults:
      ignore_users:
        - app-user
        - fake-bot

The ``digests`` clause is a list of digests to produce.  The ``defaults``
clause sets defaults for the digest options in the rest of the file.  Each
``digests`` clause specifies what to digest:

- The ``digest`` setting is the HTML digest file to write.

- The ``since`` setting indicates how far back to look for activity. It can use
  units of weeks, days, hours, minutes and seconds, and can also be
  abbreviated, like ``1d6h``.

- The ``items`` setting is a list of things to report on, specified in a few
  different ways:

  - The ``url`` setting is a GitHub URL, in a number of forms:

    - An organization project URL will report on the issues and pull requests
      in the project.

    - A URL to a repo will report on the issues and pull requests in the repo.

    - A URL to a repo's issues will report on the issues in the repo.

    - A URL to a repo's pull requests will report on the pull requests in the
      repo.

  - The ``pull_requests`` setting can specify an organization to search for
    pull requests.

  - If an item only needs to specify a GitHub URL, then it can simply be the
    URL string.

Items can have additional options:

- No activity is reported for bot users.  Some applications act as real users,
  but should be ignored anyway.  You can list those user names that should be
  ignored in the ``ignore_users`` setting.

- Options for organization projects include:

  - ``home_repo`` is the owner/repo of the repo in which most issues will be
    created.  Issues in other repos will have the repo indicated in the
    digest.



.. |pypi-badge| image:: https://img.shields.io/pypi/v/dinghy.svg
    :target: https://pypi.python.org/pypi/dinghy/
    :alt: PyPI

.. |pyversions-badge| image:: https://img.shields.io/pypi/pyversions/dinghy.svg
    :target: https://pypi.python.org/pypi/dinghy/
    :alt: Supported Python versions

.. |license-badge| image:: https://img.shields.io/github/license/nedbat/dinghy.svg
    :target: https://github.com/nedbat/dinghy/blob/master/LICENSE.txt
    :alt: License
