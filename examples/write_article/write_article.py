"""Example of using the library."""

import asyncio
from pathlib import Path

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.article import (
    GenerateArticleProposal,
    GenerateInitialOutline,
)
from fabricatio.actions.article_rag import WriteArticleContentRAG
from fabricatio.actions.output import (
    DumpFinalizedOutput,
    PersistentAll,
)
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.task import Task
from fabricatio.utils import ok


class Connect(Action):
    """Connect the article with the article_outline and article_proposal."""

    output_key: str = "article"
    """Connect the article with the article_outline and article_proposal."""

    async def _execute(
        self,
        article_briefing: str,
        article_proposal: ArticleProposal,
        article_outline: ArticleOutline,
        article: Article,
        **cxt,
    ) -> Article:
        """Connect the article with the article_outline and article_proposal."""
        return article.update_ref(article_outline.update_ref(article_proposal.update_ref(article_briefing)))


async def main(article: bool) -> None:
    """Main function."""
    Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_model="openai/qwen-max",
        llm_temperature=0.63,
        llm_stream=True,
        llm_top_p=0.85,
        llm_max_tokens=8191,
        llm_rpm=600,
        llm_tpm=900000,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    GenerateArticleProposal,
                    GenerateInitialOutline(output_key="article_outline", supervisor=False),
                    PersistentAll,
                    WriteArticleContentRAG(
                        output_key="to_dump",
                        llm_top_p=0.9,
                        ref_limit=60,
                        llm_model="openai/qwq-plus",
                        target_collection="article_chunks",
                        extractor_model="openai/qwen-plus",
                        query_model="openai/qwen-max",
                    ),
                    DumpFinalizedOutput(output_key="task_output"),
                    PersistentAll,
                ),
            ).update_init_context(
                article_briefing=Path("./article_briefing.txt").read_text(),
                dump_path="out.typ",
                persist_dir="persistent",
                collection_name="article_chunks",
            ),
        },
    )

    if article:
        proposed_task = Task(name="write an article")
        path = ok(await proposed_task.delegate(ns), "Failed to generate an article ")
        logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main(True))
