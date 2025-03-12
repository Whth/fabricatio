"""Store article essence in the database."""

from fabricatio.actions.article import CorrectOutline, CorrectProposal, GenerateArticleProposal, GenerateOutline
from fabricatio.actions.output import DumpFinalizedOutput
from fabricatio.models.action import WorkFlow

WriteOutlineWorkFlow = WorkFlow(
    name="Generate Article Outline",
    description="Generate an outline for an article. dump the outline to the given path. in typst format.",
    steps=(
        GenerateArticleProposal,
        GenerateOutline(output_key="to_dump"),
        DumpFinalizedOutput(output_key="task_output"),
    ),
)
WriteOutlineCorrectedWorkFlow = WorkFlow(
    name="Generate Article Outline",
    description="Generate an outline for an article. dump the outline to the given path. in typst format.",
    steps=(
        GenerateArticleProposal,
        CorrectProposal(output_key="article_proposal"),
        GenerateOutline,
        CorrectOutline(output_key="to_dump"),
        DumpFinalizedOutput(output_key="task_output"),
    ),
)
