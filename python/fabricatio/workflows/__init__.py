"""A module containing some builtin workflows."""

__all__ = []

from fabricatio_core.rust import is_installed

if is_installed("fabricatio_typst"):
    from fabricatio_typst.workflows.article import (
        ArticleWorkflow,
        CompileArticleWorkflow,
        OutlineArticleWorkflow,
    )

    __all__ += ["ArticleWorkflow", "CompileArticleWorkflow", "OutlineArticleWorkflow"]

    if is_installed("fabricatio_lancedb"):
        from fabricatio_typst.workflows.rag import RagArticleWorkflow, StoreArticle

        __all__ += ["RagArticleWorkflow", "StoreArticle"]


if is_installed("fabricatio_actions") and is_installed("fabricatio_novel"):
    from fabricatio_novel.workflows.novel import DebugNovelWorkflow

    __all__ += ["DebugNovelWorkflow"]

    if is_installed("fabricatio_lancedb"):
        from fabricatio_novel.workflows.rag import RagDebugNovelWorkflow

        __all__ += ["RagDebugNovelWorkflow"]

    if is_installed("fabricatio_comfyui") and is_installed("fabricatio_judge"):
        from fabricatio_novel.workflows.illustration import RagIllustrationDebugNovelWorkflow

        __all__ += ["RagIllustrationDebugNovelWorkflow"]
