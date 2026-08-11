"""Inert R11A identity-and-boundary diagnostic implementation.

The package contains only offline implementation candidates. Importing it must
not mutate historical R10/R11 modules, install a workflow, open AWS authority,
or perform network I/O.
"""

from .limits import DEFAULT_LIMITS, R11ALimits

__all__ = ["DEFAULT_LIMITS", "R11ALimits"]
