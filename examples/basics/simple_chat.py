"""Interactive chat loop where user messages are sent to the LLM with task briefing as system context, enabling a stateful conversation."""

import asyncio

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.capabilities import UseLLM
from questionary import text


class Talk(Action, UseLLM):
    """Interactive chat action that loops on user input. Each user message is sent to the LLM with the task briefing as system context, enabling a stateful conversation."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0
        try:
            while True:
                user_say = await text("User: ").ask_async()
                gpt_say = await self.aask(
                    f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}\n{user_say}",
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter


async def main() -> None:
    """Set up a chat Role with a single Talk workflow, propose a task describing the assistant persona, then enter the interactive loop."""
    role = Role(
        name="talker",
        description="talker role",
        skills={Event.quick_instantiate("talk").collapse(): WorkFlow(name="talk", steps=(Talk,))},
    )

    task = await role.propose_task(
        "you have to act as a helpful assistant, answer to all user questions properly and patiently"
    )
    _ = await task.delegate("talk")


if __name__ == "__main__":
    asyncio.run(main())
