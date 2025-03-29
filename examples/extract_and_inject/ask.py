"""Simple chat example."""

import asyncio

from fabricatio import RAG, Action, Role, Task, WorkFlow, logger
from fabricatio.models.events import Event
from fabricatio.utils import ok
from questionary import text


class Talk(Action, RAG):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0

        self.init_client()

        try:
            while True:
                user_say = await text("User: ").ask_async()
                if user_say is None:
                    break
                gpt_say = await self.aask_refined(
                    user_say,
                    "article_essence_max",
                    extra_system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}\nYou should explicitly say write a label if you draw a conclusion from the references, the label shall contain names.",
                    result_per_query=16,
                    final_limit=40,
                    similarity_threshold=0.31,
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter


async def main() -> None:
    """Main function."""
    role = Role(
        name="talker",
        description="talker role but with rag",
        registry={Event.instantiate_from("talk").push_wildcard().push("pending"): WorkFlow(name="talk", steps=(Talk,))},
    )

    task = ok(
        await role.propose_task(
            "you have to act as a helpful assistant, answer to all user questions properly and patiently"
        ),
        "Failed to propose task",
    )
    _ = await task.delegate("talk")


if __name__ == "__main__":
    asyncio.run(main())
