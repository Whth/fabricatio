"""Example of proposing a task to a role."""

import asyncio
from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.actions.output import PersistentAll
from fabricatio.capabilities.propose import Propose
from fabricatio.fs import safe_text_read
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.utils import ok


class ProposeObj(Action, Propose):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, briefing: str, **_) -> Any:
        return await self.propose(
            ArticleOutline,
            f"{briefing}\n\n\n\n\nAccording to the above plaintext article outline, "
            f"I need you to create an `ArticleOutline` obj against it."
            f"Note the heading shall not contain any heading numbers.",
        )

async def main() -> None:
    """Main function."""
    Role(
        name="talker",
        description="talker role",
        llm_model="openai/qwq-plus",
        llm_max_tokens=8190,
        llm_stream=True,
        llm_temperature=0.6,
        registry={
            Event.quick_instantiate("talk"): WorkFlow(
                name="talk", steps=(ProposeObj, PersistentAll(persist_dir="persis"))
            ).update_init_context(briefing=safe_text_read("briefing.txt"))
        },
    )

    task: Task[ArticleOutline] = Task(name="write outline")
    article_outline = ok(await task.delegate("talk"))
    logger.success(f"article_outline:\n{article_outline.display()}")


if __name__ == "__main__":
    asyncio.run(main())
