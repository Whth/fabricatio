"""Example of proposing a task to a role."""

import asyncio
from pathlib import Path

from fabricatio import Event, Role, Task, WorkFlow, logger
from fabricatio.actions.article import ExtractArticleEssence
from fabricatio.actions.output import PersistentAll
from fabricatio.actions.rag import InjectToDB
from fabricatio.fs.curd import gather_files
from fabricatio.utils import ok
from pydantic import HttpUrl


async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        llm_api_endpoint=HttpUrl("https://dashscope.aliyuncs.com/compatible-mode/v1"),
        llm_model="openai/qwq-plus",
        llm_stream=True,
        llm_rpm=500,
        llm_tpm=5000000,
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(
                    ExtractArticleEssence(output_key="to_inject"),
                    PersistentAll(persist_dir="output"),
                    InjectToDB(output_key="task_output"),
                ),
            ).update_init_context(
                override_inject=True, collection_name="article_essence_max", output_dir=Path("output")
            )
        },
    )

    task: Task[str] = ok(
        await role.propose_task(
            "Extract the essence of the article from the files in './bpdf_out'",
        )
    )

    col_name = await task.override_dependencies(gather_files("bpdf_out", "md")).delegate("article")

    if col_name is None:
        logger.error("No essence found")
        return
    logger.success(f"Injected to collection: {col_name}")


if __name__ == "__main__":
    asyncio.run(main())
