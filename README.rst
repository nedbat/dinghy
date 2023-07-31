######
Dinghy
######

Dinghy, a GitHub activity digest tool.

|pypi-badge| |pyversions-badge| |license-badge|
|sponsor-badge| |mastodon-nedbat|

Dinghy uses the GitHub GraphQL API to find recent activity on releases, issues
and pull requests, and writes a compact HTML digest `like this <sample_>`_.


Sample Digest
=============

Here's a sample of a Dinghy digest reporting on `some PSF repos: black,
requests, and PEPs <sample_>`_.


Getting Started
===============

1. Install dinghy:

   .. code-block:: bash

    $ python -m pip install dinghy

2. To run dinghy you will need a GitHub `personal access token`_. The scopes
   you need to assign to it depend on what repos you'll be accessing.  If you
   are only accessing public repos, then you don't need any scopes.  If you
   will be accessing any private repos, then you need the "repo" scope.  Create
   a token and define the GITHUB_TOKEN environment variable with the value:

   .. code-block:: bash

    $ export GITHUB_TOKEN=ghp_Y2oxDn9gHJ3W2NcQeyJsrMOez

.. _personal access token: https://github.com/settings/tokens

3. Then run dinghy with a GitHub URL:

   .. code-block:: bash

    $ dinghy https://github.com/Me/MyProject
    Wrote digest: digest.html

   You will have a digest of the repo's last week of activity in digest.html.
   It will look `something like this <sample_>`_.

   You can also write a YAML configuration file to digest multiple sources, or
   with different time periods:

   .. code-block:: bash

    $ dinghy my-dinghy-config.yaml
    Wrote digest: proj1.html
    Wrote digest: proj2-daily.html
    Wrote digest: proj2-weekly.html

   Extra arguments specify which digests to write:

   .. code-block:: bash

    $ dinghy my-dinghy-config.yaml proj1.html
    Wrote digest: proj1.html



Configuration
=============

Dinghy configuration is read from a YAML file (``dinghy.yaml`` by default).
Here's an example:

.. code-block:: yaml

    digests:
      - digest: lastweek.html
        title: My projects last week
        since: 1 week
        items:
          - https://github.com/orgs/myorg/projects/17
          - https://github.com/orgs/anotherorg/projects/8
          - https://github.com/myorg/myrepo/pulls

      - digest: hotnews.html
        title: Today's news
        since: 1 day
        items:
          - url: https://github.com/orgs/anotherorg/projects/8
            home_repo: anotherorg/wg
          - https://github.com/myorg/churnchurn/issues

      - digest: all_prs.html
        since: 1 day
        items:
          - search: org:myorg is:pr
            title: MyOrg pull requests

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
  abbreviated, like ``1d6h``. Using ``since: forever`` will include all
  activity regardless of when it happened.  If ``since`` is omitted, it
  defaults to one week.  You can specify ``--since=<SINCE>`` on the dinghy
  command line to provide an explicit value.

- The ``items`` setting is a list of things to report on, specified in a few
  different ways:

  - The ``url`` setting is a GitHub URL, in a number of forms:

    - An organization project URL will report on the issues and pull requests
      in the project. Your GitHub token will need the "read:project" scope.

    - A URL to a repo will report on the issues, pull requests and releases in
      the repo.

    - A URL to a repo's issues will report on the issues in the repo.

    - A URL to a repo's pull requests will report on the pull requests in the
      repo.

    - A URL to a repo's releases will report on the releases in the repo.

    - Any of these URLs can point to a GitHub Enterprise installation instead
      of https://github.com.

  - The ``search`` setting can specify a GitHub search query to find issues or
    pull requests. The query will have an ``updated:`` term added to it to
    account for the ``since:`` setting.

  - If an item only needs to specify a GitHub URL, then it can simply be the
    URL string.

- The optional ``title`` setting will be used to construct the title
  and main header of the HTML page.

- The ``template`` setting is the name of a Jinja2 template file to use to
  produce the digest. It defaults to "digest.html.j2", which is packaged with
  dinghy.  The data passed to the template is under-specified; if you want to
  write a template of your own, model it on the built-in `digest.html.j2`_.

.. _digest.html.j2: https://github.com/nedbat/dinghy/blob/main/src/dinghy/templates/digest.html.j2

- For GitHub Enterprise, you can specify ``api_root``, which is the URL to
  build on for GraphQL API requests. It defaults to
  "https://api.github.com/graphql".

Items can have additional options:

- By default, no activity is reported for bot users.  If you want to include
  them, use ``include_bots: true``.

- Some applications perform actions using real user accounts, but you'd like to
  ignore them anyway.  You can list those user names that should be ignored in
  the ``ignore_users`` setting.

- Digests can have an explicit title set with the ``title`` setting.

- Options for organization projects include:

  - ``home_repo`` is the owner/repo of the repo in which most issues will be
    created.  Issues in other repos will have the repo indicated in the
    digest.


Daily Publishing
================

The `sample digest <sample_>`_ is published daily using a GitHub Action from
its own repo: `nedbat/dinghy_sample <sample_repo_>`_.  You can use it as a
starting point for your own publishing.


.. _sample: https://nedbat.github.io/dinghy_sample/3day.html
.. _sample_repo: https://github.com/nedbat/dinghy_sample



.. |pypi-badge| image:: https://img.shields.io/pypi/v/dinghy.svg
    :target: https://pypi.python.org/pypi/dinghy/
    :alt: PyPI
.. |pyversions-badge| image:: https://img.shields.io/pypi/pyversions/dinghy.svg
    :target: https://pypi.python.org/pypi/dinghy/
    :alt: Supported Python versions
.. |license-badge| image:: https://img.shields.io/github/license/nedbat/dinghy.svg
    :target: https://github.com/nedbat/dinghy/blob/master/LICENSE.txt
    :alt: License
.. |mastodon-nedbat| image:: https://img.shields.io/badge/dynamic/json?style=flat&labelColor=450657&logo=mastodon&logoColor=ffffff&link=https%3A%2F%2Fhachyderm.io%2F%40nedbat&url=https%3A%2F%2Fhachyderm.io%2Fusers%2Fnedbat%2Ffollowers.json&query=totalItems&label=Mastodon
    :target: https://hachyderm.io/@nedbat
    :alt: nedbat on Mastodon
.. |sponsor-badge| image:: https://img.shields.io/badge/%E2%9D%A4-Sponsor%20me-brightgreen?style=flat&logo=GitHub
    :target: https://github.com/sponsors/nedbat
    :alt: Sponsor me on GitHub
