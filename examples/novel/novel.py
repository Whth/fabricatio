"""This module sets up a novel-writing workflow using the Fabricatio framework.

It initializes a role, registers a workflow for writing a novel, and dispatches the task.
"""

from asyncio.runners import run
from pathlib import Path

from fabricatio_core import Event, Role, Task
from fabricatio_core.utils import ok
from fabricatio_novel.workflows.novel import WriteNovelWorkflow

# Initialize the role
(Role(name="writer").register_workflow(Event.quick_instantiate(ns := "write"), WriteNovelWorkflow).dispatch())


async def main() -> None:
    """Main function."""
    # Dispatch the task
    path = await (
        Task(
            name="write eng novel",
        )
        .update_init_context(
            novel_prompt="write a novel about a girl who discovers she has the ability to time travel, "
                         "but only to moments she has already lived through. 1 chap in total, 900 words.",
            output_path=Path("./eng_novel.epub"),
        )
        .delegate(ns)
    )
    ok(path, "Failed to write eng novel!")

    # Dispatch the task
    path = await (
        Task(
            name="write zh novel",
        )
        .update_init_context(
            novel_prompt="写一部关于一个女孩发现自己能够时间旅行的小说，但只能回到她已经经历过的时刻。总共1章，900字。",
            output_path=Path("./zh_novel.epub"),
        )
        .delegate(ns)
    )
    ok(path, "Failed to write zh novel!")


run(main())
