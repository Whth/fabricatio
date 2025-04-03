"""Store article essence in the database."""

from fabricatio.actions.article import GenerateArticleProposal, GenerateInitialOutline
from fabricatio.actions.output import DumpFinalizedOutput
from fabricatio.models.action import WorkFlow

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
