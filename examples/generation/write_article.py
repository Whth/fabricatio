"""Demonstrates the staged article pipeline through Typer CLI commands (write, outline, rag-write, suma, rcsuma).

``write`` runs the full staged pipeline from a briefing — proposal, plan tree, subsection
prose — and dumps the article's typst source; ``outline`` stops after the planning stages
and dumps the structure alone; ``rag-write`` writes every subsection against the
article-essence corpus in LanceDB, with the retrieval knobs set on the RAG stage; ``suma``
and ``rcsuma`` post-process an existing article document, which must carry the configured
``ARTICLE_WRAPPER`` markers.
"""

import asyncio
from pathlib import Path

import typer
from fabricatio import Event, Task, WorkFlow, logger
from fabricatio import Role as RoleBase
from fabricatio.actions import WriteChapterSummary, WriteResearchContentSummary
from fabricatio.workflows import ArticleWorkflow, OutlineArticleWorkflow
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.utils import ok
from fabricatio_typst.actions.article import (
    AssembleArticleStage,
    DumpArticleStage,
    InitArticleContext,
    PlanArticleChaptersStage,
    PlanSectionsStage,
    PlanSubsectionsStage,
    ProposeArticlePlanStage,
    ProposeArticleProposalStage,
)
from fabricatio_typst.actions.rag import RagComposeSubsectionsStage
from typer import Typer


class Role(RoleBase, UseLLM):
    """Role class for article writing."""


Role.new(
    {
        Event.quick_instantiate(ns := "write-article").collapse(): ArticleWorkflow,
        Event.quick_instantiate(ns_outline := "outline-article").collapse(): OutlineArticleWorkflow,
        Event.quick_instantiate(ns_rag := "rag-article").collapse(): WorkFlow(
            name="Write Article with References",
            description="Write an article from a briefing against the retrieved reference corpus.",
            steps=(
                InitArticleContext,
                ProposeArticleProposalStage,
                ProposeArticlePlanStage,
                PlanArticleChaptersStage,
                PlanSectionsStage,
                PlanSubsectionsStage,
                RagComposeSubsectionsStage(ref_limit=18, result_per_query=2),
                AssembleArticleStage,
                DumpArticleStage,
            ),
        ),
        Event.quick_instantiate(ns5 := "chap-suma").collapse(): WorkFlow(
            name="Chapter Summary",
            description="Write a summary section into every chapter of an existing article document.",
            steps=(WriteChapterSummary().to_task_output(),),
        ),
        Event.quick_instantiate(ns6 := "resc-suma").collapse(): WorkFlow(
            name="Research Content Summary",
            description="Write a research content summary section into an existing article document.",
            steps=(WriteResearchContentSummary().to_task_output(),),
        ),
    },
    name="Undergraduate Researcher",
    description="Write an article in typst format from a briefing.",
    llm_send_to="openai/qwen-plus",
    llm_stream=True,
    llm_max_completion_tokens=8191,
)

app = Typer()


@app.command()
def write(
    article_briefing_path: Path = typer.Option(
        Path("article_briefing.txt"),
        "-a",
        "--article-briefing",
        help="Path to the article briefing file.",
    ),
    output_path: Path = typer.Option(
        Path("article.typ"),
        "-o",
        "--output-path",
        help="Path to dump the article's typst source.",
    ),
    persist_dir: Path = typer.Option(
        Path("persistent"),
        "-p",
        "--persist-dir",
        help="Directory to persist the run's stage snapshots.",
    ),
    language: str | None = typer.Option(
        None,
        "-l",
        "--language",
        help="Language of the article; detected from the briefing when unset.",
    ),
    constraint: str = typer.Option("", "-c", "--constraint", help="The author's writing constraint intent."),
) -> None:
    """Write an article from a briefing through the full staged pipeline."""
    path = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_briefing_path=article_briefing_path,
                article_output_path=output_path,
                persist_dir=persist_dir,
                article_language=language,
                writing_constraint=constraint,
            )
            .delegate(ns),
        ),
        "Failed to generate an article",
    )
    logger.info(f"The article is saved in:\n{path}")


@app.command()
def outline(
    article_briefing_path: Path = typer.Option(
        Path("article_briefing.txt"),
        "-a",
        "--article-briefing",
        help="Path to the article briefing file.",
    ),
    output_path: Path = typer.Option(
        Path("outline.typ"),
        "-o",
        "--output-path",
        help="Path to dump the outline.",
    ),
    persist_dir: Path = typer.Option(
        Path("persistent"),
        "-p",
        "--persist-dir",
        help="Directory to persist the run's stage snapshots.",
    ),
    language: str | None = typer.Option(
        None,
        "-l",
        "--language",
        help="Language of the outline; detected from the briefing when unset.",
    ),
) -> None:
    """Plan an article from a briefing and dump its outline, without writing the prose."""
    path = ok(
        asyncio.run(
            Task(name="write an article outline")
            .update_init_context(
                article_briefing_path=article_briefing_path,
                article_output_path=output_path,
                persist_dir=persist_dir,
                article_language=language,
            )
            .delegate(ns_outline),
        ),
        "Failed to generate an article outline",
    )
    logger.info(f"The outline is saved in:\n{path}")


@app.command()
def rag_write(
    article_briefing_path: Path = typer.Option(
        Path("article_briefing.txt"),
        "-a",
        "--article-briefing",
        help="Path to the article briefing file.",
    ),
    output_path: Path = typer.Option(
        Path("article.typ"),
        "-o",
        "--output-path",
        help="Path to dump the article's typst source.",
    ),
    persist_dir: Path = typer.Option(
        Path("persistent"),
        "-p",
        "--persist-dir",
        help="Directory to persist the run's stage snapshots.",
    ),
    language: str | None = typer.Option(
        None,
        "-l",
        "--language",
        help="Language of the article; detected from the briefing when unset.",
    ),
    constraint: str = typer.Option("", "-c", "--constraint", help="The author's writing constraint intent."),
) -> None:
    """Write an article from a briefing, citing the references retrieved for every subsection."""
    path = ok(
        asyncio.run(
            Task(name="write an article with references")
            .update_init_context(
                article_briefing_path=article_briefing_path,
                article_output_path=output_path,
                persist_dir=persist_dir,
                article_language=language,
                writing_constraint=constraint,
            )
            .delegate(ns_rag),
        ),
        "Failed to generate an article",
    )
    logger.info(f"The article is saved in:\n{path}")


@app.command()
def suma(
    article_path: Path = typer.Option(Path("article.typ"), "-a", "--article-path", help="Path to the article file."),
    skip_chapters: list[str] = typer.Option([], "-s", "--skip-chapters", help="Chapters to skip."),
    suma_title: str = typer.Option("Chapter Summary", "-t", "--suma-title", help="Title of the chapter summary."),
    summary_word_count: int = typer.Option(220, "-w", "--word-count", help="Word count for the summary."),
) -> None:
    """Write chap summary based on given article."""
    _ = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_path=article_path,
                summary_title=suma_title,
                skip_chapters=skip_chapters,
                summary_word_count=summary_word_count,
            )
            .delegate(ns5),
        ),
        "Failed to generate an article ",
    )
    logger.info(f"The outline is saved in:\n{article_path.as_posix()}")


@app.command()
def rcsuma(
    article_path: Path = typer.Option(Path("article.typ"), "-a", "--article-path", help="Path to the article file."),
    suma_title: str = typer.Option("Research Content", "-t", "--suma-title", help="Title of the summary."),
    summary_word_count: int = typer.Option(220, "-w", "--word-count", help="Word count for the summary."),
    paragraph_count: int = typer.Option(1, "-p", "--paragraph-count", help="Number of paragraphs for the summary."),
) -> None:
    """Write research summary based on given article."""
    _ = ok(
        asyncio.run(
            Task(name="write an article")
            .update_init_context(
                article_path=article_path,
                summary_title=suma_title,
                summary_word_count=summary_word_count,
                paragraph_count=paragraph_count,
            )
            .delegate(ns6),
        ),
        "Failed to generate an article ",
    )
    logger.info(f"The outline is saved in:\n{article_path.as_posix()}")


if __name__ == "__main__":
    app()
