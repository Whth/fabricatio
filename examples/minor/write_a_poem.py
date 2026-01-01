"""Example of a poem writing program using fabricatio."""

from typing import Any, Optional

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio_core.capabilities.usages import UseLLM


class WritePoem(Action, UseLLM):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: Optional[bool] = False

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        return await self.ageneric_string(
            f"{task_input.briefing}\nWrite a poetic",
        )


Role(
    name="poet",
    description="A role that creates poetic content",
    skills={Event.quick_instantiate(ns := "poem").collapse(): WorkFlow(name="poetry_creation", steps=(WritePoem,))},
)

if __name__ == "__main__":
    task = Task(
        name="write poem",
        description="Write a poem about the given topic, in this case, write a poem about the fire",
        goals=["THe poem should be about fire", "The poem should be short"],
    )

    poem = task.delegate_blocking(ns)
    logger.info(f"Poem:\n\n{poem}")
