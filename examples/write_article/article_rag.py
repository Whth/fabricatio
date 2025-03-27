"""Example of using the library."""

import asyncio
from pathlib import Path

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.article_rag import TweakArticleRAG
from fabricatio.actions.output import DumpFinalizedOutput, PersistentAll, RetrieveFromPersistent
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.task import Task


class Connect(Action):
    """Connect the article to the outline."""

    async def _execute(
        self,
        article_briefing: str,
        article_proposal: ArticleProposal,
        article_outline: ArticleOutline,
        article: Article,
        **cxt,
    ) -> None:
        article.update_ref(article_outline.update_ref(article_proposal.update_ref(article_briefing)))


async def main() -> None:
    """Main function."""
    Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_top_p=0.4,
        llm_temperature=1.15,
        llm_model="openai/qwen-turbo",
        llm_stream=True,
        llm_rpm=1000,
        llm_tpm=1000000,
        llm_max_tokens=8190,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    RetrieveFromPersistent(
                        load_path="persistent/article_proposal/ArticleProposal_20250326_142916_0e0848.json",
                        retrieve_cls=ArticleProposal,
                        output_key="article_proposal",
                    ),
                    RetrieveFromPersistent(
                        load_path="persistent/article_outline/ArticleOutline_20250326_142916_826cab.json",
                        retrieve_cls=ArticleOutline,
                        output_key="article_outline",
                    ),
                    RetrieveFromPersistent(
                        load_path="persistent/article/Article_20250326_153723_422d42.json",
                        retrieve_cls=Article,
                        output_key="article",
                    ),
                    Connect,
                    TweakArticleRAG(output_key="to_dump", llm_temperature=1.12, llm_top_p=0.36),
                    PersistentAll,
                    DumpFinalizedOutput(output_key="task_output"),
                ),
            ).update_init_context(
                article_briefing=Path("./article_briefing.txt").read_text(),
                dump_path="out.typ",
                persist_dir="persistent",
                collection_name="article_essence_max",
                parallel=False,
            )
        },
    )

    proposed_task = Task(name="write an article")
    path = await proposed_task.delegate(ns)
    logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main())
