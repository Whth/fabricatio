"""Example of proposing a task to a role."""

import asyncio

from fabricatio import Event, Task, WorkFlow, logger
from fabricatio import Role as BaseRole
from fabricatio.actions import MilvusRAGTalk
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.utils import ok


class Role(BaseRole, ProposeTask):
    """Role class for article writing."""


async def main() -> None:
    """Main function."""
    role = (
        Role.with_bio(
            name="Researcher",
            description="Extract article essence",
        )
        .subscribe(
            Event.quick_instantiate(e := "answer"),
            WorkFlow(
                name="answer",
                steps=(MilvusRAGTalk,),
            ).update_init_context(collection_name="article_essence"),
        )
        .dispatch()
    )

    task: Task[int] = ok(
        await role.propose_task(
            "Answer to all user questions properly and patiently",
        )
    )

    logger.info(f"Complete {await task.delegate(e)} times qa.")


if __name__ == "__main__":
    asyncio.run(main())
