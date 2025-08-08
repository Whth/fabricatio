"""Example of proposing a task to a role."""

from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.actions import PersistentAll
from fabricatio.capabilities import Propose
from fabricatio.models import ArticleOutline
from fabricatio_core.utils import ok
from fabricatio_tool.fs import safe_text_read


class ProposeObj(Action, Propose):
    """Action that says hello to the world."""

    llm_model: str | None = "openai/qwq-plus"
    llm_max_tokens: int | None = 8190
    llm_stream: bool | None = True
    llm_temperature: float | None = 0.6
    output_key: str = "task_output"

    async def _execute(self, briefing: str, **_) -> Any:
        return await self.propose(
            ArticleOutline,
            f"{briefing}\n\n\n\n\nAccording to the above plaintext article outline, "
            f"I need you to create an `ArticleOutline` obj against it."
            f"Note the heading shall not contain any heading numbers.",
        )


Role(
    name="talker",
    registry={
        Event.quick_instantiate("talk"): WorkFlow(
            name="talk", steps=(ProposeObj, PersistentAll(persist_dir="persis"))
        ).update_init_context(briefing=safe_text_read("briefing.txt"))
    },
)


if __name__ == "__main__":
    task: Task[ArticleOutline] = Task(name="write outline")
    article_outline = ok(task.delegate_blocking("talk"))
    logger.success(f"article_outline:\n{article_outline.display()}")
