"""The article context tree: one channel per pipeline level.

Each level of the article owns a context — the plan it was handed, the run-wide
constants copied down to it, its own writing channels and, for the non-leaf levels,
the child contexts it writes. The planning stages build the tree top-down; the
composition stages fill it and contribute their entries to the running prefix.
"""

from fabricatio_typst.models.context.article import ArticleContext
from fabricatio_typst.models.context.base import ContextBase, ParentContextBase
from fabricatio_typst.models.context.chapter import ChapterContext
from fabricatio_typst.models.context.log import ContextEntry, ContextLog, EntryKind
from fabricatio_typst.models.context.section import SectionContext
from fabricatio_typst.models.context.subsection import SubsectionContext

__all__ = [
    "ArticleContext",
    "ChapterContext",
    "ContextBase",
    "ContextEntry",
    "ContextLog",
    "EntryKind",
    "ParentContextBase",
    "SectionContext",
    "SubsectionContext",
]
