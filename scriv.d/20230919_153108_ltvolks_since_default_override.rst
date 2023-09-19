Fixed
.....

- fix: override default since param only if explicitly provided by cli #36
  952bdfb introduced a regression ignoring the `since` parameter defined via
  YAML config in favor of the default defined by the cli option

.. _issue 36: https://github.com/nedbat/dinghy/issues/36
