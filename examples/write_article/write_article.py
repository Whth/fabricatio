"""Example of using the library."""

import asyncio
from pathlib import Path

import typer
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
from typer import Typer


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
        ),
    },
)


app = Typer()


@app.command()
def write(
    article_briefing: Path = typer.Option(  # noqa: B008
        Path("article_briefing.txt"), "-a", "--article-briefing", help="Path to the article briefing file."
    ),
    dump_path: Path = typer.Option(Path("out.typ"), "-d", "--dump-path", help="Path to dump the final output."),  # noqa: B008
    persist_dir: Path = typer.Option(  # noqa: B008
        Path("persistent"), "-p", "--persist-dir", help="Directory to persist the output."
    ),
    collection_name: str = typer.Option("article_chunks", "-c", "--collection-name", help="Name of the collection."),
) -> None:
    """Write an article based on a briefing.

    This function generates an article outline and content based on the provided briefing.
    The outline and content are then dumped to the specified path and persisted in the given directory.
    """
    path = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_briefing=article_briefing.read_text(),
                dump_path=dump_path,
                persist_dir=persist_dir,
                collection_name=collection_name,
            )
            .delegate(ns)
        ),
        "Failed to generate an article ",
    )
    logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    app()
