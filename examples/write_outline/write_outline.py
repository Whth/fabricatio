"""Example of using the library."""

import asyncio

from fabricatio import Event, Task, logger
from fabricatio import Role as RoleBase
from fabricatio.workflows import WriteOutlineCorrectedWorkFlow
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.utils import ok


class Role(RoleBase, ProposeTask):
    """Role that can propose tasks."""


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
