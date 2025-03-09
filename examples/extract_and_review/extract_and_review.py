"""Example of proposing a task to a role."""

import asyncio
from pathlib import Path
from typing import List

from fabricatio import ArticleEssence, Event, ExtractArticleEssence, Role, Task, WorkFlow, logger
from fabricatio.fs.curd import dump_text, gather_files


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(ExtractArticleEssence(output_key="task_output"),),
            )
        },
    )

    task: Task[List[ArticleEssence]] = await role.propose_task(
        "Extract the essence of the article from the files in './bpdf_out'",
    )

    ess = await task.override_dependencies(gather_files("bpdf_out", "md")).delegate("article")
    logger.success(f"Essence Count:{len(ess)}")

    Path("output").mkdir(exist_ok=True)
    for i, e in enumerate(ess):
        dump_text(f"output/{i}.json", e.display())


if __name__ == "__main__":
    asyncio.run(main())
