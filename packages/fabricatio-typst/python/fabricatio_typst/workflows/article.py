"""Pre-composed article generation and compilation workflows."""

from fabricatio_actions.actions.output import DumpFinalizedOutput
from fabricatio_core.models.action import WorkFlow

from fabricatio_typst.actions.article import (
    CompileArticle,
    GenerateArticleProposal,
    GenerateInitialOutline,
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

CompileArticleWorkflow = WorkFlow(
    name="Compile Article to PDF",
    description="Compile a previously generated article's .typ file to PDF using the Typst compiler.",
    steps=(CompileArticle(output_key="task_output"),),
)
