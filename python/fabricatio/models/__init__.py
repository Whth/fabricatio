"""A module for the usage of the fabricatio package."""

from importlib.util import find_spec

from fabricatio_core.models.usages import EmbeddingUsage, LLMUsage, ToolBoxUsage

__all__ = [
    "EmbeddingUsage",
    "LLMUsage",
    "ToolBoxUsage",
]

if find_spec("fabricatio_typst"):
    from fabricatio_typst.models.article_essence import ArticleEssence
    from fabricatio_typst.models.article_main import Article, ArticleOutline
    from fabricatio_typst.models.article_proposal import ArticleProposal

    __all__ += [
        "Article",
        "ArticleEssence",
        "ArticleOutline",
        "ArticleProposal",
    ]

    if find_spec("fabricatio_typst"):
        from fabricatio_typst.models.aricle_rag import ArticleChunk

        __all__ += [
            "ArticleChunk"

        ]

if find_spec():
    from fabricatio_judge.models.advanced_judge import JudgeMent

    __all__ += [
        "JudgeMent"
    ]
