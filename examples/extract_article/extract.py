"""Example of proposing a task to a role."""

import asyncio
from typing import TYPE_CHECKING, List

from fabricatio import Event, Role, Task, WorkFlow, logger
from fabricatio.actions.article import ExtractArticleEssence

if TYPE_CHECKING:
    from fabricatio.models.extra.article_essence import ArticleEssence


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(ExtractArticleEssence(output_key="task_output"),),
            )
        },
    )
    task: Task[List[ArticleEssence]] = await role.propose_task(
        "Extract the essence of the article from the file at './7.md'"
    )
    ess = (await task.delegate("article")).pop()
    logger.success(f"Essence:\n{ess.display()}")


if __name__ == "__main__":
    asyncio.run(main())
