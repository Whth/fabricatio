"""Example of proposing a task to a role."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, List

from fabricatio import Event, Role, Task, WorkFlow, logger
from fabricatio.actions.article import ExtractArticleEssence
from fabricatio.fs.curd import dump_text, gather_files

if TYPE_CHECKING:
    from fabricatio.models.extra import ArticleEssence


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

    unchecked_ess = await task.override_dependencies(gather_files("bpdf_out", "md")).delegate("article")

    if unchecked_ess is None:
        logger.error("No essence found")
        return
    ess = list(filter(lambda x: x is not None, unchecked_ess))
    logger.success(f"Essence Count:{len(ess)}, invalid count: {len(unchecked_ess) - len(ess)}")

    Path("output").mkdir(exist_ok=True)
    for i, e in enumerate(ess):
        dump_text(f"output/{i}.json", e.display())


if __name__ == "__main__":
    asyncio.run(main())
