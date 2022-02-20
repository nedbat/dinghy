######
Dinghy 
######

|pypi-badge| |pyversions-badge| |license-badge|

Dinghy daily digest tool.

Dinghy uses the GitHub GraphQL API to find recent activity on issues and pull
requests, and writes a compact HTML digest.  Write your configuration in a
``dinghy.yaml`` file, then:

.. code-block:: bash

    $ pip install dinghy
    $ python -m dinghy


Configuration
=============

Dinghy configuration is read from a ``dinghy.yaml`` file:

.. code-block:: yaml

    - digest: lastweek.html
      since: 1 week
      items:
        - https://github.com/orgs/myorg/projects/17
        - https://github.com/orgs/anotherorg/projects/8
        - https://github.com/myorg/myrepo/pulls
    
    - digest: hotnews.html
      since: 1 day
      items:
        - https://github.com/myorg/churnchurn/issues
        - url: https://github.com/orgs/anotherorg/projects/8
          home_repo: anotherorg/wg

The file is a list of digests to produce.  Each entry specifies what to digest:

- The ``digest`` setting is the HTML file path to produce.  

- The ``since`` setting indicates how far back to look for activity. It can use
  units of weeks, days, hours, minutes and seconds, and can also be
  abbreviated, like ``1d6h``.

- The ``items`` setting is a list of things to report on.  The things are
  specified with a GitHub URL in the ``url`` setting, and each can also have
  other options.

  Three forms of GitHub URL are understood:

  - An organization project URL will report on the issues in the project.
    Options for organization projects include:

    - ``home_repo`` is the owner/repo of the repo in which most issues will be
      created.  Issues in other repos will have the repo indicated in the
      digest.

  - A URL to a repo's issues will report on the issues in the repo.

  - A URL to a repo's pull requests will report on the pull requests in the
    repo.

  If an item only needs to specify a URL, then it can simply be the URL string.


.. |pypi-badge| image:: https://img.shields.io/pypi/v/dinghy.svg
    :target: https://pypi.python.org/pypi/dinghy/
    :alt: PyPI

.. |pyversions-badge| image:: https://img.shields.io/pypi/pyversions/dinghy.svg
    :target: https://pypi.python.org/pypi/dinghy/
    :alt: Supported Python versions

.. |license-badge| image:: https://img.shields.io/github/license/nedbat/dinghy.svg
    :target: https://github.com/nedbat/dinghy/blob/master/LICENSE.txt
    :alt: License
