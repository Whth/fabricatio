"""Store article essence in the database."""

from fabricatio.actions.output import DumpFinalizedOutput
from fabricatio_core.models.action import WorkFlow

from fabricatio_typst.actions.article import GenerateArticleProposal, GenerateInitialOutline

WriteOutlineWorkFlow = WorkFlow(
    name="Generate Article Outline",
    description="Generate an outline for an article. dump the outline to the given path. in typst format.",
    steps=(
        GenerateArticleProposal,
        GenerateInitialOutline(output_key="article_outline"),
        DumpFinalizedOutput(output_key="task_output"),
    ),
)
WriteOutlineCorrectedWorkFlow = WorkFlow(
    name="Generate Article Outline",
    description="Generate an outline for an article. dump the outline to the given path. in typst format.",
    steps=(
        GenerateArticleProposal,
        GenerateInitialOutline(output_key="article_outline"),
        DumpFinalizedOutput(output_key="task_output"),
    ),
)
