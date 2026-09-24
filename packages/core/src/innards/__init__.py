"""innards: mechanism shared by every tool (AGENTS.md §4). Imports no tool package."""

from importlib.metadata import version

__version__ = version("innards")
