"""Enable 'python -m dinghy'."""

from .cli import cli

# pylint: disable=unexpected-keyword-arg
# pylint: disable=no-value-for-parameter
cli(prog_name="dinghy")
