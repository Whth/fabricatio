"""The retrieval workflows of the article pipeline: compose from the corpus, and build it.

``RagArticleWorkflow`` is the full pipeline with the content stage backed by the
article-essence table; ``StoreArticle`` is the side pipeline that fills that table from
the run's own documents.
"""

from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_core.models.action import WorkFlow

from fabricatio_typst.actions.article import (
    AssembleArticleStage,
    DumpArticleStage,
    ExtractArticleEssence,
    InitArticleContext,
    PlanArticleChaptersStage,
    PlanSectionsStage,
    PlanSubsectionsStage,
    ProposeArticlePlanStage,
    ProposeArticleProposalStage,
)
from fabricatio_typst.actions.rag import RagComposeSubsectionsStage, StoreArticleEssence

__all__ = ["RagArticleWorkflow", "StoreArticle"]

RagArticleWorkflow = WorkFlow(
    name="Write Article with References",
    description=(
        "Write an article from a briefing against the retrieved reference corpus: the plain "
        "pipeline with the content stage retrieving each subsection's references and landing "
        "them as inline citations."
    ),
    steps=(
        InitArticleContext,
        ProposeArticleProposalStage,
        ProposeArticlePlanStage,
        PlanArticleChaptersStage,
        PlanSectionsStage,
        PlanSubsectionsStage,
        RagComposeSubsectionsStage,
        AssembleArticleStage,
        DumpArticleStage,
    ),
)

StoreArticle = WorkFlow(
    name="Extract Article Essence",
    description="Extract the essence of an article in the given path, and store it in the database.",
    steps=(ExtractArticleEssence(output_key="documents"), StoreArticleEssence(output_key="task_output")),
)
