"""A module containing some builtin actins."""

from fabricatio_actions.actions.fs import DumpText, ReadText, SmartDumpText, SmartReadText
from fabricatio_actions.actions.output import (
    DumpFinalizedOutput,
    Forward,
    GatherAsList,
    PersistentAll,
    RenderedDump,
    RetrieveFromLatest,
    RetrieveFromPersistent,
)

__all__ = [
    "DumpFinalizedOutput",
    "DumpText",
    "Forward",
    "GatherAsList",
    "PersistentAll",
    "ReadText",
    "RenderedDump",
    "RetrieveFromLatest",
    "RetrieveFromPersistent",
    "SmartDumpText",
    "SmartReadText",
]
