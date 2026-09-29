"""The plain staged article workflows: the full pipeline, its outline-only prefix, and compilation.

The retrieval variants live in :mod:`fabricatio_typst.workflows.rag`.
"""

from fabricatio_core.models.action import WorkFlow

from fabricatio_typst.actions.article import (
    AssembleArticleStage,
    CompileArticle,
    ComposeSubsectionsStage,
    DumpArticleStage,
    DumpOutlineStage,
    InitArticleContext,
    PlanArticleChaptersStage,
    PlanSectionsStage,
    PlanSubsectionsStage,
    ProposeArticlePlanStage,
    ProposeArticleProposalStage,
)

__all__ = ["ArticleWorkflow", "CompileArticleWorkflow", "OutlineArticleWorkflow"]

ArticleWorkflow = WorkFlow(
    name="Write Article",
    description=(
        "Write an article from a briefing: propose the research proposal, plan the article, "
        "its chapters, sections and subsections, write every subsection, then dump the "
        "article's typst source. Every stage persists a whole-tree snapshot into the given "
        "persist_dir, so a wrong result can be traced to the stage that produced it."
    ),
    steps=(
        InitArticleContext,
        ProposeArticleProposalStage,
        ProposeArticlePlanStage,
        PlanArticleChaptersStage,
        PlanSectionsStage,
        PlanSubsectionsStage,
        ComposeSubsectionsStage,
        AssembleArticleStage,
        DumpArticleStage,
    ),
)

OutlineArticleWorkflow = WorkFlow(
    name="Write Article Outline",
    description=(
        "Plan an article from a briefing and dump its outline in typst format: the "
        "structure-only deliverable of the same staged pipeline."
    ),
    steps=(
        InitArticleContext,
        ProposeArticleProposalStage,
        ProposeArticlePlanStage,
        PlanArticleChaptersStage,
        PlanSectionsStage,
        PlanSubsectionsStage,
        DumpOutlineStage,
    ),
)

CompileArticleWorkflow = WorkFlow(
    name="Compile Article to PDF",
    description="Compile a previously generated article's .typ file to PDF using the Typst compiler.",
    steps=(CompileArticle(output_key="task_output"),),
)
