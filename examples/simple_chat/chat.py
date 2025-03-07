"""Simple chat example."""

import asyncio

from fabricatio import Action, Role, Task, WorkFlow, logger
from fabricatio.models.events import Event
from questionary import text


class Talk(Action):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0
        try:
            while True:
                user_say = await text("User: ").ask_async()
                gpt_say = await self.aask(
                    user_say,
                    system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}",
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
        description="talker role",
        registry={Event.instantiate_from("talk").push_wildcard().push("pending"): WorkFlow(name="talk", steps=(Talk,))},
    )

    task = await role.propose_task(
        "you have to act as a helpful assistant, answer to all user questions properly and patiently"
    )
    _ = await task.delegate("talk")


if __name__ == "__main__":
    asyncio.run(main())
