"""Example of using the library."""

import asyncio

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.article import GenerateArticleProposal, GenerateInitialOutline
from fabricatio.actions.output import DumpFinalizedOutput


async def main() -> None:
    """Main function."""
    role = Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_top_p=0.8,
        llm_temperature=1.15,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    GenerateArticleProposal(llm_model="deepseek/deepseek-reasoner", llm_temperature=1.3),
                    GenerateInitialOutline(llm_model="deepseek/deepseek-chat", llm_temperature=1.4, llm_top_p=0.5),
                    DumpFinalizedOutput(output_key="task_output"),
                ),
            )
        },
    )

    proposed_task = await role.propose_task(
        "You need to read the `./article_briefing.txt` file and write an outline for the article in typst format. The outline should be saved in the `./out.typ` file.",
    )
    path = await proposed_task.delegate(ns)
    logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
