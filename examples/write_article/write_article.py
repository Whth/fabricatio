"""Example of using the library."""

import asyncio
from pathlib import Path
from typing import List, Optional

import typer
from fabricatio import Event, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.actions.article import (
    ExtractOutlineFromRaw,
    GenerateArticleProposal,
    GenerateInitialOutline,
    WriteChapterSummary,
)
from fabricatio.actions.article_rag import ArticleConsultRAG, WriteArticleContentRAG
from fabricatio.actions.output import DumpFinalizedOutput, PersistentAll, RenderedDump
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.task import Task
from fabricatio.models.usages import LLMUsage
from fabricatio.utils import ok
from typer import Typer

# from pydantic import HttpUrl


class Role(RoleBase, LLMUsage):
    """Role class for article writing."""


Role(
    name="Undergraduate Researcher",
    description="Write an outline for an article in typst format.",
    llm_model="openai/qwen-plus",
    llm_stream=True,
    llm_max_tokens=8191,
    llm_rpm=600,
    llm_tpm=900000,
    llm_timeout=10,
    registry={
        Event.quick_instantiate(ns := "article"): WorkFlow(
            name="Generate Article",
            description="Generate an article. dump the outline to the given path. in typst format.",
            steps=(
                GenerateArticleProposal,
                GenerateInitialOutline(output_key="article_outline"),
                PersistentAll,
                (
                    a := WriteArticleContentRAG(
                        output_key="to_dump",
                        ref_limit=18,
                        threshold=0.58,
                        result_per_query=2,
                        extractor_model={"model": "openai/qwen-max"},
                        query_model={"model": "openai/qwen-turbo"},
                    )
                ),
                PersistentAll,
                DumpFinalizedOutput(dump_path="median.typ"),
                RenderedDump(template_name="article").to_task_output(),
            ),
        ),
        Event.quick_instantiate(ns2 := "complete"): WorkFlow(
            name="Generate Article",
            description="Generate an article with given raw article outline. dump the outline to the given path. in typst format.",
            steps=(
                ExtractOutlineFromRaw(output_key="article_outline"),
                PersistentAll,
                a,
                PersistentAll,
                DumpFinalizedOutput(dump_path="median.typ"),
                RenderedDump(template_name="article").to_task_output(),
            ),
        ),
        Event.quick_instantiate(ns3 := "finish"): WorkFlow(
            name="Finish Article",
            description="Finish an article with given article outline. dump the outline to the given path. in typst format.",
            steps=(
                a,
                PersistentAll,
                DumpFinalizedOutput(dump_path="median.typ"),
                RenderedDump(template_name="article").to_task_output(),
            ),
        ),
        Event.quick_instantiate(ns4 := "consult"): WorkFlow(
            name="Consult Article",
            description="Consult an article with given article outline. dump the outline to the given path. in typst format.",
            steps=(ArticleConsultRAG(ref_q_model={"model": "openai/qwen-turbo"}).to_task_output(),),
        ),
        Event.quick_instantiate(ns5 := "chap-suma"): WorkFlow(
            name="Chapter Summary",
            description="Generate chapter summary based on given article outline. dump the outline to the given path. in typst format.",
            steps=(WriteChapterSummary().to_task_output(),),
        ),
    },
)


app = Typer()


@app.command()
def consult(
    collection_name: str = typer.Option("article_chunks", "-c", "--collection-name", help="Name of the collection."),
    tei_endpoint: Optional[str] = typer.Option(None, "-t", "--tei-endpoint", help="TEI endpoint."),
) -> None:
    """Consult an article based on a given article outline."""
    _ = asyncio.run(
        Task(name="Answer Question")
        .update_init_context(collection_name=collection_name, tei_endpoint=tei_endpoint)
        .delegate(ns4)
    )

    logger.info("Finished")


@app.command()
def finish(
    article_outline_path: Path = typer.Argument(  # noqa: B008
        help="Path to the article outline raw file."
    ),
    dump_path: Path = typer.Option(Path("out.typ"), "-d", "--dump-path", help="Path to dump the final output."),  # noqa: B008
    persist_dir: Path = typer.Option(  # noqa: B008
        Path("persistent"), "-p", "--persist-dir", help="Directory to persist the output."
    ),
    collection_name: str = typer.Option("article_chunks", "-c", "--collection-name", help="Name of the collection."),
    supervisor: bool = typer.Option(False, "-s", "--supervisor", help="Whether to use the supervisor mode."),
) -> None:
    """Finish an article based on a given article outline."""
    path = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_outline=ArticleOutline.from_persistent(article_outline_path),
                dump_path=dump_path,
                persist_dir=persist_dir,
                collection_name=collection_name,
                supervisor=supervisor,
            )
            .delegate(ns3)
        ),
        "Failed to generate an article ",
    )
    logger.success(f"The outline is saved in:\n{path}")


@app.command()
def completion(
    article_outline_raw_path: Path = typer.Option(  # noqa: B008
        Path("article_outline_raw.txt"), "-a", "--article-outline-raw", help="Path to the article outline raw file."
    ),
    dump_path: Path = typer.Option(Path("out.typ"), "-d", "--dump-path", help="Path to dump the final output."),  # noqa: B008
    persist_dir: Path = typer.Option(  # noqa: B008
        Path("persistent"), "-p", "--persist-dir", help="Directory to persist the output."
    ),
    collection_name: str = typer.Option("article_chunks", "-c", "--collection-name", help="Name of the collection."),
    supervisor: bool = typer.Option(False, "-s", "--supervisor", help="Whether to use the supervisor mode."),
) -> None:
    """Write an article based on a raw article outline."""
    path = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_outline_raw_path=article_outline_raw_path,
                dump_path=dump_path,
                persist_dir=persist_dir,
                collection_name=collection_name,
                supervisor=supervisor,
            )
            .delegate(ns2)
        ),
        "Failed to generate an article ",
    )
    logger.success(f"The outline is saved in:\n{path}")


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
    supervisor: bool = typer.Option(False, "-s", "--supervisor", help="Whether to use the supervisor mode."),
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
                supervisor=supervisor,
            )
            .delegate(ns)
        ),
        "Failed to generate an article ",
    )
    logger.success(f"The outline is saved in:\n{path}")


@app.command()
def suma(
    article_path: Path = typer.Option(  # noqa: B008
        Path("article.typ"), "-a", "--article-path", help="Path to the article file."
    ),
    skip_chapters: List[str] = typer.Option(  # noqa: B008
        [], "-s", "--skip-chapters", help="Chapters to skip."
    ),
    suma_title: str = typer.Option("Chapter Summary", "-t", "--suma-title", help="Title of the chapter summary."),
) -> None:
    """Write chap summary based on given article."""
    _ = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_path=article_path,
                summary_title=suma_title,
                skip_chapters=skip_chapters,
            )
            .delegate(ns5)
        ),
        "Failed to generate an article ",
    )
    logger.success(f"The outline is saved in:\n{article_path.as_posix()}")


if __name__ == "__main__":
    app()
