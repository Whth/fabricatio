"""Example of proposing a task to a role."""

import asyncio
from pathlib import Path
from typing import List, Optional

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.actions.article import ExtractArticleEssence
from fabricatio.actions.rag import InjectToDB
from fabricatio.fs.curd import dump_text, gather_files
from fabricatio.models.extra import ArticleEssence


class SaveToFS(Action):
    """Save to file system."""

    async def _execute(self, to_inject: List[Optional[ArticleEssence]], output_dir: Path, **_) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        empty_count = 0
        for i, e in enumerate(to_inject):
            if e is None:
                empty_count += 1
                logger.error(f"Invalid essence at index {i}")
                continue
            dump_text(output_dir / f"{i}.json", e.display())
        logger.info(f"Passed {empty_count} empty essence ")


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        llm_model="openai/deepseek-r1-distill-llama-70b",
        llm_rpm=50,
        llm_tpm=100000,
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(ExtractArticleEssence(output_key="to_inject"), SaveToFS, InjectToDB(output_key="task_output")),
                extra_init_context={"collection_name": "article_essence", "output_dir": Path("output")},
            )
        },
    )

    task: Task[str] = await role.propose_task(
        "Extract the essence of the article from the files in './bpdf_out'",
    )

    col_name = await task.override_dependencies(gather_files("bpdf_out", "md")).delegate("article")

    if col_name is None:
        logger.error("No essence found")
        return
    logger.success(f"Injected to collection: {col_name}")


if __name__ == "__main__":
    asyncio.run(main())
