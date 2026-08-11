"""Inert R11A identity-and-boundary diagnostic implementation.

Importing this package performs no network I/O, mutates no R10/R11 global
resource limit and creates no workflow, approval or release authority.
"""

from .activity import ActivitySnapshot, ActivityTracker
from .diagnostic import DiagnosticReport, Taxon, TerminalClass, classify
from .identity import BlockObservation, Observation, RawBlockLocator, RawObservationLocator
from .limits import DEFAULT_LIMITS, R11ALimits

__all__ = [
    "ActivitySnapshot",
    "ActivityTracker",
    "BlockObservation",
    "DEFAULT_LIMITS",
    "DiagnosticReport",
    "Observation",
    "R11ALimits",
    "RawBlockLocator",
    "RawObservationLocator",
    "Taxon",
    "TerminalClass",
    "classify",
]
