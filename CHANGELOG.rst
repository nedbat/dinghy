
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

.. _changelog-1.3.1:

1.3.1 — 2023-09-17
------------------

Fixed
.....

- When using a URL on the command line, the ``--since`` option was ignored.
  This is now fixed, closing `issue 35`_.

.. _issue 35: https://github.com/nedbat/dinghy/issues/35

.. _changelog-1.3.0:

1.3.0 — 2023-07-31
------------------

Added
.....

- The ``since`` date can now be specified on the command line with ``--since``.
  This will override any specification in the YAML file.

- The ``since`` value can be specified as a specific ISO 8601 date or datetime,
  closing `issue 26`_.

.. _issue 26: https://github.com/nedbat/dinghy/issues/26


.. _changelog-1.2.0:

1.2.0 — 2023-01-27
------------------

Added
.....

- Now you can additionally specify digests on the command line to write, which
  will choose just those digests from the configuration file.

Fixed
.....

- If the config file has no ``digests:`` clause, it could be because it's not a
  dinghy config file at all, so print an error message about it.

.. _changelog-1.1.0:

1.1.0 — 2023-01-25
------------------

Added
.....

- A digest can specify ``template``, a Jinja2 template file to produce the
  digest.  This opens the possibility for other output formats than HTML.

.. _changelog-1.0.0:

1.0.0 — 2022-12-03
------------------

- Nothing has changed, just decided Dinghy was stable enough to call 1.0.0.

.. _changelog-0.15.0:

0.15.0 — 2022-11-09
-------------------

Added
.....

- Show releases in the digest. Thanks, Simon de Vlieger.

- A new setting ``include_bots: true`` will include pull requests, issues, or
  comments created by bot users.  The default remains False, to exclude them.
  Closes `issue 25`_.

.. _issue 25: https://github.com/nedbat/dinghy/issues/25


.. _changelog-0.14.0:

0.14.0 — 2022-10-25
-------------------

Added
.....

- Now a CLI command is registered so you can use ``dinghy`` as a command
  instead of ``python -m dinghy`` (though that still works).

- You can now specify ``since: forever`` to include all activity regardless of
  when it happened.

Changed
.......

- Search results now always show the repo containing the item.

Fixed
.....

- Comments by deleted GitHub users would cause a crash.  This is now fixed
  (`issue 23`_).

.. _issue 23: https://github.com/nedbat/dinghy/issues/23

.. _changelog-0.13.4:

0.13.4 — 2022-10-06
-------------------

Fixed
.....

- Comments on pull requests were only filtered by their age, not their authors,
  so bot comments, and comments by "ignored users" were still included.  This
  is now fixed.

.. _changelog-0.13.3:

0.13.3 — 2022-09-29
-------------------

Fixed
.....

- The hover tip for icons on pull requests and issues has text in the same
  order as the icons, making them easier to understand.

.. _changelog-0.13.2:

0.13.2 — 2022-08-13
-------------------

Fixed
.....

- Add an HTML `<meta>` tag to ensure content is properly decoded as UTF-8.
  Fixes `issue 12`_.  Thanks, Bill Mill.

.. _issue 12: https://github.com/nedbat/dinghy/issues/12

.. _changelog-0.13.1:

0.13.1 — 2022-08-03
-------------------

Fixed
.....

- On Windows, an alarming but harmless error would appear when finishing.
  This is now fixed, closing `issue 9`.  Thanks, Carlton Gibson.

.. _issue 9: https://github.com/nedbat/dinghy/issues/9

.. _changelog-0.13.0:

0.13.0 — 2022-07-29
-------------------

Removed
.......

- Removed the deprecated "pull_requests" setting.

Added
.....

- The `api_root` setting lets GitHub Enterprise users control the GraphQL
  endpoint to use.

Changed
.......

- Adapt to the `2022-06-23 GitHub issues update`__, using the ProjectsV2 API
  instead of the ProjectsNext API.

__ https://github.blog/changelog/2022-06-23-the-new-github-issues-june-23rd-update/

.. _changelog-0.12.0:

0.12.0 — 2022-06-12
-------------------

Added
.....

- The `title` option can be used on individual digests to add text to the
  title of the report. Thanks, Doug Hellmann.

.. _changelog-0.11.5:

0.11.5 — 2022-06-07
-------------------

Fixed
.....

- Closed issues now distinguish between "completed" and "not planned".

.. _changelog-0.11.4:

0.11.4 — 2022-05-10
-------------------

Added
.....

- HTML escaping is applied to the text pulled from GitHub (oops!)

- Emojis are displayed as emojis rather than as text.

.. _changelog-0.11.3:

0.11.3 — 2022-05-06
-------------------

Fixed
.....

- GitHub sometimes responds with "502 Bad Gateway".  Pause and retry if that
  happens.

.. _changelog-0.11.2:

0.11.2 — 2022-04-12
-------------------

Added
.....

- Added a ``--version`` option.

Fixed
.....

- Pull requests with many reviews would skip some reviews.  Now all pull
  request data is fully retrieved.

- On large digests, GitHub sometimes returns 403 as a rate limit.  Retry when
  this happens to finish the queries.

.. _changelog-0.11.1:

0.11.1 — 2022-03-29
-------------------

Fixed
.....

- Corrected a packaging mistake (missing Changelog entry).


.. _changelog-0.11.0:

0.11.0 — 2022-03-29
-------------------

Added
.....

- Resolved comments are now indicated with a checkbox icon, and hover text of
  "resolved comment".

Fixed
.....

- Fixed a crash trying to get the repository for an issue in a project.

.. _changelog-0.10.0:

0.10.0 — 2022-03-28
-------------------

Changed
.......

- Pull request data was not properly displayed: comments weren't included in
  the digest that should have been.

- Pull request comments older than the cutoff date will be included if they are
  needed to show the discussion threads of newer comments.  The old comments
  are shown in gray to help stay focused on recent activity.

- Parsing of time durations was made stricter, so that "1 month" isn't
  mistaken for "1 minute".  Fixes `issue 7`_

.. _issue 7: https://github.com/nedbat/dinghy/issues/7

Removed
.......

- Oops, it turns out there's no such thing as a repo project for "Projects
  (beta)".  That thing that wouldn't have worked has been removed.


0.9.0 — 2022-03-17
------------------

Added
.....

- GitHub enterprise support: you can use URLs pointing to your own GitHub
  Enterprise installation.  Only a single host can be used.  Thanks, Henry
  Gessau.

- A "search:" entry in the configuration file will find issues or pull requests
  matching the query.

- Items in the configuration file can have ``title:`` to set an explicit title.

Deprecated
..........

- The ``pull_requests:`` configuration setting is deprecated in favor of
  ``search:``.   ``pull_requests: org:my_org`` becomes ``search: org:my_org
  is:pr``.

0.8.0 — 2022-03-16
------------------

Added
.....

- Repo projects are supported.

Fixed
.....

- Error handling failed on certain errors.  This is now fixed, closing
  `issue 4`_.

.. _issue 4: https://github.com/nedbat/dinghy/issues/4

0.7.1 — 2022-03-13
------------------

Fixed
.....

- Better handling of authorization problems, with error message presented so
  that the user can fix them.

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
