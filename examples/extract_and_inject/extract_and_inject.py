"""Example of proposing a task to a role."""

import asyncio
from typing import Optional

from fabricatio import BibManager, Event, Role, Task, WorkFlow, logger
from fabricatio.actions.article import ExtractArticleEssence, FixArticleEssence
from fabricatio.actions.output import PersistentAll
from fabricatio.actions.rag import InjectToDB
from fabricatio.fs import safe_text_read
from fabricatio.fs.curd import gather_files
from litellm.utils import token_counter

MAX_TOKEN = 64000


def _reader(path:str)->Optional[str]:
    string=safe_text_read(path)
    string=string.split("References\n")[0]
    string=string.split("参考文献\n")[0]
    if (leng:=token_counter(text=string))> MAX_TOKEN:
        logger.warning(f'{path} is too long, got {leng} tokens, skip.')
        return None
    logger.info(f'Read {path} get {leng} tokens.')
    return string
async def main() -> None:
    """Main function."""
    Role(
        name="Researcher",
        description="Extract article essence",
        llm_model="openai/deepseek-v3-250324",
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(
                    ExtractArticleEssence(output_key="article_essence"),
                    FixArticleEssence(output_key="to_inject"),
                    PersistentAll,
                    InjectToDB(output_key="task_output"),
                ),
            ).update_init_context(
                override_inject=True,
                collection_name="article_essence_0324",
                persist_dir="output_0324",
                bib_mgr=BibManager("ref.bib"),
                reader=_reader
            )
        },
    )

    task: Task[str] = Task(
        name="Extract Article Essence",
        description="Extract the essence of the article from the files in './bpdf_out'",
        dependencies=gather_files("bpdf_out", "md"),
    )

    col_name = await task.delegate("article")

    if col_name is None:
        logger.error("No essence found")
        return
    logger.success(f"Injected to collection: {col_name}")


if __name__ == "__main__":
    asyncio.run(main())
