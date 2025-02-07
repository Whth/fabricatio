import asyncio
from typing import Any

from fabricatio import env, Role, Action, Task, logger, WorkFlow

task = Task(name="world", goal="say hello", description="say hello to the world")


class Talk(Action):
    name: str = "talk"
    description: str = "talk to the world"
    output_key: str = "echo"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = f"Hello {task_input.name}"
        logger.info("executing talk action")
        return ret


async def main():
    Role(name="talker", description="talker role", registry={task.pending_label: WorkFlow(name="talk", steps=(Talk,))})
    await env.emit_async(task.pending_label, task)
    print(await task.get_output())


if __name__ == "__main__":
    asyncio.run(main())
