"""This is the initialization file for the 'fabricatio.actions' package.

It imports various action classes from different modules based on the availability of certain packages.
The imported classes are then added to the '__all__' list, making them accessible when the package is imported.
"""

__all__ = []

from fabricatio_core.rust import is_installed

if is_installed("fabricatio_typst"):
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

    if is_installed("fabricatio_rag"):
        from fabricatio_typst.actions.article_rag import (
            ArticleConsultRAG,
            ChunkArticle,
            TweakArticleRAG,
            WriteArticleContentRAG,
        )

        __all__ += ["ArticleConsultRAG", "ChunkArticle", "TweakArticleRAG", "WriteArticleContentRAG"]
if is_installed("fabricatio_rag"):
    from fabricatio_rag.actions.rag import InjectToDB, RAGTalk

    __all__ += ["InjectToDB", "RAGTalk"]

if is_installed("fabricatio_actions"):
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

if is_installed("fabricatio_yue"):
    from fabricatio_yue.actions.compose import Compose

    __all__ += ["Compose"]

if is_installed("fabricatio_locale"):
    from fabricatio_locale.actions.localize import LocalizePoFile

    __all__ += ["LocalizePoFile"]
if is_installed("fabricatio_novel"):
    from fabricatio_novel.actions.novel import (
        AssembleNovelFromComponents,
        DumpNovel,
        GenerateChaptersFromScripts,
        GenerateCharactersFromDraft,
        GenerateNovel,
        GenerateNovelDraft,
        GenerateScriptsFromDraftAndCharacters,
        ValidateNovel,
    )

    __all__ += [
        "AssembleNovelFromComponents",
        "DumpNovel",
        "GenerateChaptersFromScripts",
        "GenerateCharactersFromDraft",
        "GenerateNovel",
        "GenerateNovelDraft",
        "GenerateScriptsFromDraftAndCharacters",
        "ValidateNovel",
    ]
