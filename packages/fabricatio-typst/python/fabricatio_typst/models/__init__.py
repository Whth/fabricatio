"""This module contains model definitions for the fabricatio-typst package.

It includes classes and data structures that represent typst documents, formatting rules, and related entities within the system.
"""

from fabricatio_typst.models.article_main import Article, ArticleChapter, ArticleSection, ArticleSubsection, Paragraph
from fabricatio_typst.models.article_outline import (
    ArticleChapterOutline,
    ArticleOutline,
    ArticleSectionOutline,
    ArticleSubsectionOutline,
)
from fabricatio_typst.models.article_proposal import ArticleProposal
from fabricatio_typst.models.artifacts import ArticleArtifacts
from fabricatio_typst.models.context import (
    ArticleContext,
    ChapterContext,
    ContextBase,
    ContextEntry,
    ContextLog,
    EntryKind,
    ParentContextBase,
    SectionContext,
    SubsectionContext,
)
from fabricatio_typst.models.plan import (
    ArticlePlan,
    ChapterPlan,
    ChapterPlans,
    SectionPlan,
    SectionPlans,
    SubsectionPlan,
    SubsectionPlans,
    WeightedPlan,
)

# Resolve forward references after all classes are defined.
ArticleArtifacts.model_rebuild()
ArticleProposal.model_rebuild()
ArticleOutline.model_rebuild()
Article.model_rebuild()

__all__ = [
    "Article",
    "ArticleArtifacts",
    "ArticleChapter",
    "ArticleChapterOutline",
    "ArticleContext",
    "ArticleOutline",
    "ArticlePlan",
    "ArticleProposal",
    "ArticleSection",
    "ArticleSectionOutline",
    "ArticleSubsection",
    "ArticleSubsectionOutline",
    "ChapterContext",
    "ChapterPlan",
    "ChapterPlans",
    "ContextBase",
    "ContextEntry",
    "ContextLog",
    "EntryKind",
    "Paragraph",
    "ParentContextBase",
    "SectionContext",
    "SectionPlan",
    "SectionPlans",
    "SubsectionContext",
    "SubsectionPlan",
    "SubsectionPlans",
    "WeightedPlan",
]
