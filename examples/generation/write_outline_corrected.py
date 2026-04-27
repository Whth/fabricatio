"""Demonstrates the WriteOutlineCorrectedWorkFlow with LLM parameter customization. Shows how to tune temperature and top_p per workflow step for better outline quality — higher temperature for creative proposal generation, lower for structured output."""

import asyncio

from fabricatio import Event, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.actions import DumpFinalizedOutput, GenerateArticleProposal, GenerateInitialOutline
from fabricatio_capabilities.capabilities.task import ProposeTask


class Role(RoleBase, ProposeTask):
    """Role that can propose tasks."""


async def main() -> None:
    """Run the corrected outline pipeline with tuned LLM parameters: high temperature (1.15) for creative proposals, top_p filtering (0.8) for diverse output."""
    role = Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_top_p=0.8,
        llm_temperature=1.15,
        skills={
            Event.quick_instantiate(ns := "article").collapse(): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    GenerateArticleProposal(llm_send_to="deepseek/deepseek-reasoner", llm_temperature=1.3),
                    GenerateInitialOutline(llm_send_to="deepseek/deepseek-chat", llm_temperature=1.4, llm_top_p=0.5),
                    DumpFinalizedOutput(output_key="task_output"),
                ),
            )
        },
    )

    proposed_task = await role.propose_task(
        "You need to read the `./article_briefing.txt` file and write an outline for the article in typst format. The outline should be saved in the `./out.typ` file.",
    )
    path = await proposed_task.delegate(ns)
    logger.info(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
