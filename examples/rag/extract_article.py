"""Demonstrates article essence extraction: reads a markdown article file, uses LLM to extract structured ArticleEssence objects (key findings, methodology, contributions), and displays the result."""

import asyncio
from typing import TYPE_CHECKING, List

from fabricatio import Event, Task, WorkFlow, logger
from fabricatio import Role as BaseRole
from fabricatio.actions import ExtractArticleEssence
from fabricatio_capabilities.capabilities.task import ProposeTask

if TYPE_CHECKING:
    from fabricatio.models import ArticleEssence


class Role(BaseRole, ProposeTask):
    """A researcher role that can propose extraction tasks from natural language."""


async def main() -> None:
    """Set up an extraction Role with an ExtractArticleEssence workflow, propose a task from a natural-language instruction to extract from './7.md', and display the extracted essence."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        skills={
            Event.quick_instantiate("article").collapse(): WorkFlow(
                name="extract",
                steps=(ExtractArticleEssence(output_key="task_output"),),
            )
        },
    )
    task: Task[List[ArticleEssence]] = await role.propose_task(
        "Extract the essence of the article from the file at './7.md'"
    )
    ess = (await task.delegate("article")).pop()
    logger.info(f"Essence:\n{ess.display()}")


if __name__ == "__main__":
    asyncio.run(main())
