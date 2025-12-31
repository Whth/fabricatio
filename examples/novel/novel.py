"""This module sets up a novel-writing workflow using the Fabricatio framework.

It initializes a role, registers a workflow for writing a novel, and dispatches the task.
"""

from asyncio.runners import run
from pathlib import Path

from fabricatio_core import Event, Role, Task
from fabricatio_core.utils import ok
from fabricatio_novel.workflows.novel import DebugNovelWorkflow

# Initialize the role
(Role(name="writer").add_skill(Event.quick_instantiate(ns := "write"), DebugNovelWorkflow).dispatch())


async def main() -> None:
    """Main function."""
    # Dispatch the task
    path = await (
        Task(
            name="write eng novel",
        )
        .update_init_context(
            novel_outline="write a novel about a girl who discovers she has the ability to time travel, "
            "but only to moments she has already lived through. 1 chap in total, 900 words.",
            output_path=Path("./eng_novel.epub"),
            novel_font_file=Path("./font.ttf"),
            cover_image=Path("./cover.png"),
            novel_language="English",
            chapter_guidance="Use words that are beautiful",
            persist_dir=Path("./persist"),
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
            novel_outline="编写一个关于一个少女在已经度过的某时某刻时，她被发现具有时间旅行能力，但只能回到她已经度过的某些时刻。",
            output_path=Path("./zh_novel.epub"),
            novel_font_file=Path("./font.ttf"),
            cover_image=Path("./cover.png"),
            novel_language="简体中文",
            chapter_guidance="用词必须华丽",
            persist_dir=Path("./persist"),
        )
        .delegate(ns)
    )
    ok(path, "Failed to write zh novel!")


if __name__ == "__main__":
    run(main())
