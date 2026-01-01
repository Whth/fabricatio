"""Example of using the library."""

import asyncio

from fabricatio import Event, Role, Task, logger
from fabricatio.workflows import WriteOutlineCorrectedWorkFlow
from fabricatio_core.utils import ok


async def main() -> None:
    """Main function."""
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
