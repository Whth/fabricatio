"""Chat with the LLM: each user message is sent with the task briefing as system context, enabling a stateful conversation."""

import asyncio

from fabricatio import Action, Event, Task, WorkFlow
from fabricatio import Role as RoleBase
from fabricatio.capabilities import ProposeTask, UseLLM
from fabricatio_core.utils import ok


class Role(RoleBase, ProposeTask):
    """Basic role."""


class Talk(Action, UseLLM):
    """Chat action answering a fixed set of user messages. Each message is sent to the LLM with the task briefing as system context."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0
        for user_say in ["Hello!", "What can you help me with?"]:
            gpt_say = await self.aask(
                f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}\n{user_say}",
            )
            print(f"GPT: {gpt_say}")
            counter += 1
        return counter


async def main() -> None:
    """Set up a chat Role with a single Talk workflow, propose a task describing the assistant persona, then run the conversation."""
    role = (
        Role.with_bio(name="talker", description="talker role")
        .subscribe(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Talk,)))
        .dispatch()
    )

    task = await role.propose_task(
        "you have to act as a helpful assistant, answer to all user questions properly and patiently",
    )
    _ = await ok(task).delegate("talk")


if __name__ == "__main__":
    asyncio.run(main())
