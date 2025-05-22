"""Example of proposing a task to a role."""

import asyncio

from fabricatio import Event, Role, Task, WorkFlow, logger
from fabricatio.actions import ChunkArticle, InjectToDB
from fabricatio_core.fs import gather_files
from fabricatio_core.utils import ok
from fabricatio_typst.rust import BibManager


async def main() -> None:
    """Main function."""
    Role(
        name="Researcher",
        description="chunk the article",
        registry={
            Event.quick_instantiate(e := "Chunk"): WorkFlow(
                name="Chunk",
                steps=(
                    ChunkArticle(output_key="to_inject"),
                    InjectToDB(collection_name="article_chunks").to_task_output(),
                ),
            ).update_init_context(
                article_path=gather_files("bare_md", "md"),
                bib_manager=BibManager(path="ref.bib"),
                max_chunk_size=600,
                max_overlapping_rate=0.3,
                override_inject=True,
            ),
        },
    )

    task: Task[str] = Task(name="Chunk Article")
    res = ok(await task.delegate(e))
    logger.success(f"Injected to {res}")


if __name__ == "__main__":
    asyncio.run(main())
