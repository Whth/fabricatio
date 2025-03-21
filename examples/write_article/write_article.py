"""Example of using the library."""

import asyncio
from pathlib import Path

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.article import (
    GenerateArticle,
    GenerateArticleProposal,
    GenerateOutline,
)
from fabricatio.actions.output import DumpFinalizedOutput
from fabricatio.models.task import Task


async def main() -> None:
    """Main function."""
    Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_top_p=0.8,
        llm_temperature=1.15,
        llm_max_tokens=8192,
        llm_model="openai/qwen-max",
        llm_stream=True,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    GenerateArticleProposal(llm_temperature=1.18),
                    GenerateOutline(llm_temperature=1.21, llm_top_p=0.3),
                    GenerateArticle(output_key="to_dump", llm_temperature=1.2, llm_top_p=0.45),
                    DumpFinalizedOutput(output_key="task_output"),
                ),
            ).update_init_context(article_briefing=Path("./article_briefing.txt").read_text(), dump_path="out.typ")
        },
    )

    proposed_task = Task(name="write an article")
    path = await proposed_task.delegate(ns)
    logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
