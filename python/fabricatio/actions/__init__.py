from importlib.util import find_spec

__all__ = []

if find_spec("fabricatio_typst"):
    from fabricatio_typst.actions.article import (
        ExtractArticleEssence,
        ExtractOutlineFromRaw,
        GenerateArticle,
        GenerateArticleProposal,
        GenerateInitialOutline,
        WriteChapterSummary,
        WriteResearchContentSummary,
    )

    __all__ += [
        "ExtractArticleEssence",
        "ExtractOutlineFromRaw",
        "GenerateArticle",
        "GenerateArticleProposal",
        "GenerateInitialOutline",
        "WriteChapterSummary",
        "WriteResearchContentSummary"

    ]

    if find_spec("fabricatio_rag"):
        from fabricatio_typst.actions.article_rag import ArticleConsultRAG, TweakArticleRAG, WriteArticleContentRAG

        __all__ += [

            "ArticleConsultRAG",
            "TweakArticleRAG",
            "WriteArticleContentRAG"
        ]

if find_spec("fabricatio_actions"):
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
        "RenderedDump",
        "RetrieveFromLatest",
        "RetrieveFromPersistent"
    ]
