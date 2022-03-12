
.. this will be appended to README.rst

Changelog
=========

..
   All enhancements and patches to dinghy will be documented
   in this file.  It adheres to the structure of http://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (http://semver.org/).

Unreleased
----------

See the fragment files in the `scriv.d directory`_.

.. _scriv.d directory: https://github.com/nedbat/dinghy/tree/master/scriv.d


.. scriv-insert-here

0.7.0 — 2022-03-12
------------------

Added
.....

- The command line now accepts a GitHub URL to quickly get a week's digest of
  activity from a repo (or issues, pull requests, etc).

- The logging level can now be specified with the ``-v``/``--verbosity``
  command-line option.

Fixed
.....

- Dependencies now have minimum pins, fixing `issue 1`_.

.. _issue 1: https://github.com/nedbat/dinghy/issues/1

0.6.0 — 2022-03-10
------------------

Added
.....

- GitHub's @ghost user shows up in GraphQL results as an "author" of None.
  Properly handle that case.

Fixed
.....

- Fixes to the color of labels.

- Correct handling of HTML in bodies.

0.5.2 — 2022-03-08
------------------

Changed
.......

- More HTML tweaks to indentation and information.

0.5.1 — 2022-03-07
------------------

Changed
.......

- Indentation tweaks to make thread structure clearer.

0.5.0 — 2022-03-03
------------------

Changed
.......

- Pull request reviews are displayed more compactly.

0.4.0 — 2022-02-28
------------------

Added
.....

- A repo URL will report on both pull requests and issues in the repo.

0.3.0 — 2022-02-27
------------------

Added
.....

- The configuration file can be specified as the argument on the command line.

- GitHub icons decorate pull requests, issues, and comments to distinguish them
  and indicate their status.

Changed
.......

- The configuration file syntax changed.  Now there is a top-level ``digests``
  clause and an optional ``defaults`` clause.

- The ``bots`` setting is now called ``ignore_users``.

- Pull request review threads are presented hierarchically.

0.2.0 — 2022-02-21
------------------

Added
.....

- Items can have options.  Organization projects have a ``home_repo`` option so
  that issues from other repos will get an indication of the other repo.

- Organizatons can be searched for pull requests.

- If dinghy hits a GraphQL API rate limit, it will sleep until the limit is
  reset.

- Don't report on activity by bot users.  The ``bot`` setting can be used to
  list user accounts that should be considered bots.

0.1.0 — 2022-02-19
------------------

* First release.
