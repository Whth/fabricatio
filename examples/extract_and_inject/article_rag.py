"""Example of proposing a task to a role."""

import asyncio

from fabricatio import Event, Task, WorkFlow, logger
from fabricatio import Role as BaseRole
from fabricatio.actions import RAGTalk
from fabricatio_capabilities.capabilities.task import ProposeTask
from fabricatio_core.utils import ok


class Role(BaseRole, ProposeTask):
    """Role class for article writing."""


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        llm_model="openai/deepseek-r1-distill-llama-70b",
        llm_rpm=50,
        llm_tpm=100000,
        registry={
            Event.quick_instantiate(e := "answer"): WorkFlow(
                name="answer",
                steps=(RAGTalk,),
            ).update_init_context(collection_name="article_essence"),
        },
    )

    task: Task[int] = ok(
        await role.propose_task(
            "Answer to all user questions properly and patiently",
        )
    )

    logger.info(f"Complete {await task.delegate(e)} times qa.")


if __name__ == "__main__":
    asyncio.run(main())
