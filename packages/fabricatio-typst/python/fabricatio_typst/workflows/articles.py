"""Store article essence in the database."""

from fabricatio_actions.actions.output import DumpFinalizedOutput
from fabricatio_core.models.action import WorkFlow
from fabricatio_rag.actions.rag import InjectToDB

from fabricatio_typst.actions.article import ExtractArticleEssence, GenerateArticleProposal, GenerateInitialOutline

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


StoreArticle = WorkFlow(
    name="Extract Article Essence",
    description="Extract the essence of an article in the given path, and store it in the database.",
    steps=(ExtractArticleEssence(output_key="to_inject"), InjectToDB(output_key="task_output")),
)
