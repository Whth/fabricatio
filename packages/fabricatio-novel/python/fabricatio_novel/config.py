"""Module containing configuration classes for fabricatio-novel.

The config carries ONLY the template entries the overhaul pipeline needs:
the outline stage (draft/characters/scripts), the summary derivation, the
bible pipeline (creation/export/sync), and the event pipeline (prompt,
splitter, format block, bible context excerpts). Everything belonging to the
deleted chapter pipeline, the deferred capabilities (state/mental/RAG/
illustration/enrich), and their templates is gone — it returns with the
capability when it is integrated back.
"""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class NovelConfig:
    """Configuration for fabricatio-novel."""

    ...


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
