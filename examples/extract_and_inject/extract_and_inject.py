"""Example of proposing a task to a role."""

import asyncio
from pathlib import Path
from typing import List

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.actions.article import ExtractArticleEssence
from fabricatio.actions.rag import InjectToDB
from fabricatio.fs.curd import dump_text, gather_files
from fabricatio.models.extra import ArticleEssence
from pydantic import HttpUrl


class SaveToFS(Action):
    """Save to file system."""

    async def _execute(self, to_inject: List[ArticleEssence], output_dir: Path, **_) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for i, e in enumerate(to_inject):
            dump_text(output_dir / f"{i}.json", e.display())


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        llm_api_endpoint=HttpUrl("https://dashscope.aliyuncs.com/compatible-mode/v1"),
        llm_model="deepseek-r1-distill-llama-70b",
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(ExtractArticleEssence(output_key="to_inject"), InjectToDB(output_key="task_output")),
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
