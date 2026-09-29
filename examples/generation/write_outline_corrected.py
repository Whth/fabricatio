"""Demonstrates the staged outline pipeline with LLM parameter customization. Shows how to tune temperature and top_p per workflow step for better outline quality — higher temperature for creative planning, lower for structured output."""

import asyncio

from fabricatio import Event, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.actions import (
    DumpOutlineStage,
    InitArticleContext,
    PlanArticleChaptersStage,
    PlanSectionsStage,
    PlanSubsectionsStage,
    ProposeArticlePlanStage,
    ProposeArticleProposalStage,
)
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.utils import ok


class Role(RoleBase, ProposeTask):
    """Role that can propose tasks."""


async def main() -> None:
    """Run the staged outline pipeline with tuned LLM parameters: high temperature (1.3) for the creative planning stages, tighter sampling (0.5) for the structured plans."""
    role = Role.new(
        {
            Event.quick_instantiate(ns := "outline-article").collapse(): WorkFlow(
                name="Write Article Outline",
                description="Plan an article from a briefing and dump its outline in typst format.",
                steps=(
                    InitArticleContext,
                    ProposeArticleProposalStage(llm_send_to="deepseek/deepseek-reasoner", llm_temperature=1.3),
                    ProposeArticlePlanStage(llm_send_to="deepseek/deepseek-reasoner", llm_temperature=1.3),
                    PlanArticleChaptersStage(llm_send_to="deepseek/deepseek-chat", llm_temperature=1.4, llm_top_p=0.5),
                    PlanSectionsStage(llm_send_to="deepseek/deepseek-chat", llm_temperature=1.4, llm_top_p=0.5),
                    PlanSubsectionsStage(llm_send_to="deepseek/deepseek-chat", llm_temperature=1.4, llm_top_p=0.5),
                    DumpOutlineStage,
                ),
            ),
        },
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_top_p=0.8,
        llm_temperature=1.15,
    )

    proposed_task = await role.propose_task(
        "You need to read the `./article_briefing.txt` file and write an outline for the article in typst format. The outline should be saved in the `./out.typ` file.",
    )
    path = await ok(proposed_task).delegate(ns)
    logger.info(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
