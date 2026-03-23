"""Example of a poem writing program using fabricatio."""

from typing import Any, Optional

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio_core.capabilities.usages import UseLLM


# You may encounter warnings that the LLM failed to access the GitHub price list link,
# which can be ignored. Usually, it is possible to access the local price list.
# In the project files, you can create configuration files mentioned in the readme,
# such as .env or fabricatio.toml, to connect to the AI.
# Warning: Do not write the key in the script, otherwise it is easy to accidentally leak it.
class WritePoem(Action, UseLLM):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: Optional[bool] = False

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        return await self.ageneric_string(
            f"{task_input.briefing}\nWrite a poetic",
        )

    # Extract the task summary of task_input.briefing,
    # that is, the prompt given to the AI


# If you're curious, you can use logger.info(f"{WritePoem.__mro__}") to see inheritance
# print((dir(WritePoem))) to check function names and usage


class WritePoem2(Action, UseLLM):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: Optional[bool] = False

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        return await self.ageneric_string(
            "Say a sentence that includes 'good night'",
        )

    # The function self.ageneric_string interacts with AI,
    # with the parameter being a prompt


role = Role(
    name="poet",
    description="A role that creates poetic content",
    skills={Event.quick_instantiate(ns := "poem").collapse(): WorkFlow(name="poetry_creation", steps=(WritePoem,))},
    # Skills and their corresponding workflows initialized directly
    # through the parameter skills can be added later via add._skillt
).dispatch()
# add_skill is a method of the class instance
role.add_skill(
    event=Event.quick_instantiate("unlike"), workflow=WorkFlow(name="poetry_creation", steps=(WritePoem2,))
).dispatch()  # Needs to be reactivated

if __name__ == "__main__":
    task = Task(
        name="write poem",
        description="Write a poem about the given topic, in this case, write a poem about the fire",
        goals=["Keep it brief"],
    )

    poem = task.delegate_blocking("unlike")
    # Actions to Find Characters with the 'unlike' Skill
    logger.info(f"Poem:\n\n{poem}")
