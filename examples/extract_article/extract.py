"""Example of proposing a task to a role."""

import asyncio
from typing import List

from fabricatio import ArticleEssence, Event, ExtractArticleEssence, Role, WorkFlow, logger


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
    task = await role.propose_task("Extract the essence of the article from the file at './7.md'")
    ess: List[ArticleEssence] = await task.delegate("article")
    logger.success(f"Essence:\n{ess.pop().display()}")


if __name__ == "__main__":
    asyncio.run(main())
