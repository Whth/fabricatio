"""Example of review usage."""

from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.capabilities import Correct, Review
from fabricatio_core.utils import ok


class WritePoem(Action, Review, Correct):
    """an Action about Review and Correct"""
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        body = await self.ageneric_string(
            f"{task_input.briefing}\nWrite a poetic",
        )

        imp = ok(await self.review_string(body, topic="Should be rich in meaning"))
        # Method review_string comes from Review
        # body: content of the review
        # topic: review rules (will automatically analyze the rule and complete the rule)
        # output: modification suggestions
        # ok--> if return = None: throw an error,

        corrected = await self.correct_string(body, improvement=imp)
        # Modify the body according to imp

        return f"{corrected}\nWrite a poetic"


role = Role(
    name="poet",
    description="A role that creates poetic content",
    skills={Event.quick_instantiate(ns := "poem").collapse(): WorkFlow(name="poetry_creation", steps=(WritePoem,))},
).dispatch()

if __name__ == "__main__":
    task = Task(
        name="write poem",
        description="Write a poem about the given topic, in this case, write a poem about the fire",
        goals=["Keep it brief"],
    )

    poem = task.delegate_blocking(ns)
    logger.info(f"Poem:\n\n{poem}")
