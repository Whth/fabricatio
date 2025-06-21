"""This is the initialization file for the 'fabricatio.actions' package.

It imports various action classes from different modules based on the availability of certain packages.
The imported classes are then added to the '__all__' list, making them accessible when the package is imported.
"""

from importlib.util import find_spec

__all__ = []

if find_spec("fabricatio_typst"):
    from fabricatio_typst.actions.article import (
        ExtractArticleEssence,
        ExtractOutlineFromRaw,
        FixArticleEssence,
        GenerateArticle,
        GenerateArticleProposal,
        GenerateInitialOutline,
        WriteChapterSummary,
        WriteResearchContentSummary,
    )

    __all__ += [
        "ExtractArticleEssence",
        "ExtractOutlineFromRaw",
        "FixArticleEssence",
        "GenerateArticle",
        "GenerateArticleProposal",
        "GenerateInitialOutline",
        "WriteChapterSummary",
        "WriteResearchContentSummary",
    ]

    if find_spec("fabricatio_rag"):
        from fabricatio_typst.actions.article_rag import (
            ArticleConsultRAG,
            ChunkArticle,
            TweakArticleRAG,
            WriteArticleContentRAG,
        )

        __all__ += ["ArticleConsultRAG", "ChunkArticle", "TweakArticleRAG", "WriteArticleContentRAG"]
if find_spec("fabricatio_rag"):
    from fabricatio_rag.actions.rag import InjectToDB, RAGTalk

    __all__ += ["InjectToDB", "RAGTalk"]

if find_spec("fabricatio_actions"):
    from fabricatio_actions.actions.fs import ReadText
    from fabricatio_actions.actions.output import (
        DumpFinalizedOutput,
        Forward,
        GatherAsList,
        PersistentAll,
        RenderedDump,
        RetrieveFromLatest,
        RetrieveFromPersistent,
    )

    __all__ += [
        "DumpFinalizedOutput",
        "Forward",
        "GatherAsList",
        "PersistentAll",
        "ReadText",
        "RenderedDump",
        "RetrieveFromLatest",
        "RetrieveFromPersistent",
    ]

if find_spec("fabricatio_yue"):
    from fabricatio_yue.actions.compose import Compose

    __all__ += ["Compose"]

if find_spec("fabricatio_locale"):
    from fabricatio_locale.actions.localize import LocalizePoFile

    __all__ += ["LocalizePoFile"]
