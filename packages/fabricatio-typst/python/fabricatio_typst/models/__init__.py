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

# Resolve forward references after all classes are defined.
ArticleArtifacts.model_rebuild()
ArticleProposal.model_rebuild()
ArticleOutline.model_rebuild()
Article.model_rebuild()

__all__ = [
    "ArticleArtifacts",
    "ArticleProposal",
    "ArticleOutline",
    "ArticleChapterOutline",
    "ArticleSectionOutline",
    "ArticleSubsectionOutline",
    "Article",
    "ArticleChapter",
    "ArticleSection",
    "ArticleSubsection",
    "Paragraph",
]
