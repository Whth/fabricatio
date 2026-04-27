"""Demonstrates the WriteOutlineCorrectedWorkFlow — a pre-built workflow that reads an article briefing, generates a structured outline proposal, and writes it as a typst file. Shows how to use high-level workflow abstractions instead of composing Actions manually."""

import asyncio

from fabricatio import Event, Task, logger
from fabricatio import Role as RoleBase
from fabricatio.workflows import WriteOutlineCorrectedWorkFlow
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.utils import ok


class Role(RoleBase, ProposeTask):
    """Role that can propose tasks. Uses ProposeTask capability to convert natural-language instructions into structured Tasks."""


async def main() -> None:
    """Run the outline generation pipeline: create a Role with the corrected-outline workflow, propose a task to read article_briefing.txt and write the outline to out.typ, then execute."""
    role = Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        skills={Event.quick_instantiate(ns := "article").collapse(): WriteOutlineCorrectedWorkFlow},
    )

    proposed_task = await role.propose(
        Task,
        "You need to read the `./article_briefing.txt` file and write an outline for the article in typst format. The outline should be saved in the `./out.typ` file.",
    )
    path = await ok(proposed_task).delegate(ns)
    logger.info(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
