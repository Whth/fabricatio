import asyncio
from typing import Any

from fabricatio import env, Role, Action, Task, logger, WorkFlow

task = Task(name="say hello", goal="say hello", description="say hello to the world")


class Talk(Action):
    name: str = "talk"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = f"Hello fabricatio!"
        logger.info("executing talk action")
        return ret


async def main():
    Role(name="talker", description="talker role", registry={task.pending_label: WorkFlow(name="talk", steps=(Talk,))})
    await env.emit_async(task.pending_label, task)

    print(await task.get_output())


if __name__ == "__main__":
    asyncio.run(main())
