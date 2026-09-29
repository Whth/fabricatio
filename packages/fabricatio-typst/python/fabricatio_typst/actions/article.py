"""Actions for the staged article pipeline plus the standalone article utilities.

The pipeline stages at the top mirror the ``compose_article`` chain one segment at a
time; the actions below them are the run's side utilities — extracting and repairing the
reference corpus, loading or summarizing an article the run already holds, and compiling
a typst source to its deliverable format.
"""

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, TypedDict, Unpack

from fabricatio_capabilities.capabilities.extract import Extract
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.journal import logger
from fabricatio_core.models.action import OUTPUT_KEY, Action
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.models.task import Task
from fabricatio_core.rust import PLAN, TASK, TEMPLATE_MANAGER, detect_language, word_count
from fabricatio_core.utils import ok
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import RuleSet
from fabricatio_tool.fs import dump_text
from more_itertools import filter_map
from pydantic import Field

from fabricatio_typst.actions.stage import StageAction, StageName
from fabricatio_typst.capabilities.article import ArticleCompose
from fabricatio_typst.config import typst_config
from fabricatio_typst.models.article_essence import ArticleEssence
from fabricatio_typst.models.article_main import Article, ArticleChapter, ArticleSubsection
from fabricatio_typst.models.article_outline import ArticleOutline
from fabricatio_typst.models.context.article import ArticleContext
from fabricatio_typst.rust import BibManager

__all__ = [
    "AssembleArticleStage",
    "CompileArticle",
    "CompileKwargs",
    "CompileTypstDocument",
    "ComposeSubsectionsStage",
    "DumpArticleStage",
    "DumpOutlineStage",
    "ExtractArticleEssence",
    "ExtractOutlineFromRaw",
    "FixArticleEssence",
    "FixIntrospectedErrors",
    "InitArticleContext",
    "LoadArticle",
    "PlanArticleChaptersStage",
    "PlanSectionsStage",
    "PlanSubsectionsStage",
    "ProposeArticlePlanStage",
    "ProposeArticleProposalStage",
    "WriteChapterSummary",
    "WriteResearchContentSummary",
    "compile_typst_source",
]


class InitArticleContext(StageAction, ArticleCompose):
    """Build the article context from the task init context, fire ``before_compose_article_context``, persist."""

    output_key: str = "article_ctx"
    stage: ClassVar[StageName] = "01_init"
    send_to_slot: ClassVar[str | None] = TASK

    async def init_article_context(
        self,
        briefing: str,
        *,
        language: str | None = None,
        constraint: str = "",
        skills: list[str] | None = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleContext:
        """Build the root from the run's settings and fire the before hook on it.

        The user's skills are resolved by name onto the root before the hook runs, so the
        hook — and every stage after it — sees a complete root.
        """
        ctx = ArticleContext.create(briefing, language=language)
        if constraint:
            ctx.set_writing_constraints([constraint])
        if skills:
            ctx = self.apply_skills(ctx, skills)
        return await self.before_compose_article_context(ctx, send_to=send_to, **kwargs)

    async def _execute(
        self,
        article_briefing: str | None = None,
        article_briefing_path: Path | None = None,
        article_language: str | None = None,
        writing_constraint: str = "",
        skills: list[str] | None = None,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> ArticleContext:
        """Build the run's article context from the briefing the task carries.

        The briefing is the run's source material: it arrives as text or as a path to a
        file holding it, and a missing briefing is a task error rather than an empty run.
        """
        briefing = article_briefing or ok(
            article_briefing_path,
            "`article_briefing` or `article_briefing_path` is required in the task init context",
        ).read_text(encoding="utf-8")
        ctx = await self.init_article_context(
            briefing,
            language=article_language,
            constraint=writing_constraint,
            skills=skills,
            send_to=self.routed(send_to),
            **cxt,
        )
        await self.snapshot(ctx, persist_dir)
        return ctx


class ProposeArticleProposalStage(StageAction, ArticleCompose):
    """Propose the research proposal from the briefing and record it on the context."""

    output_key: str = "proposal_ok"
    stage: ClassVar[StageName] = "02_proposal"
    send_to_slot: ClassVar[str | None] = PLAN

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> bool:
        return await self.run_phase(
            article_ctx, self.propose_article_proposal, send_to=send_to, persist_dir=persist_dir, **cxt
        )


class ProposeArticlePlanStage(StageAction, ArticleCompose):
    """Propose the article's own plan and adopt it onto the context."""

    output_key: str = "plan_ok"
    stage: ClassVar[StageName] = "03_article"
    send_to_slot: ClassVar[str | None] = PLAN

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> bool:
        return await self.run_phase(
            article_ctx, self.propose_article_plan, send_to=send_to, persist_dir=persist_dir, **cxt
        )


class PlanArticleChaptersStage(StageAction, ArticleCompose):
    """Plan the article's chapters and materialize their contexts."""

    output_key: str = "chapter_plans_ok"
    stage: ClassVar[StageName] = "04_chapter_plans"
    send_to_slot: ClassVar[str | None] = PLAN

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> bool:
        return await self.run_phase(
            article_ctx, self.plan_chapters_phase, send_to=send_to, persist_dir=persist_dir, **cxt
        )


class PlanSectionsStage(StageAction, ArticleCompose):
    """Plan every chapter's sections and materialize them as child contexts."""

    output_key: str = "section_plans_ok"
    stage: ClassVar[StageName] = "05_section_plans"
    send_to_slot: ClassVar[str | None] = PLAN

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> bool:
        return await self.run_phase(
            article_ctx, self.plan_chapter_sections_phase, send_to=send_to, persist_dir=persist_dir, **cxt
        )


class PlanSubsectionsStage(StageAction, ArticleCompose):
    """Plan every section's subsections and materialize them as child contexts."""

    output_key: str = "subsection_plans_ok"
    stage: ClassVar[StageName] = "06_subsection_plans"
    send_to_slot: ClassVar[str | None] = PLAN

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> bool:
        return await self.run_phase(
            article_ctx, self.plan_section_subsections_phase, send_to=send_to, persist_dir=persist_dir, **cxt
        )


class ComposeSubsectionsStage(StageAction, ArticleCompose):
    """Write every subsection of the article serially in prefix order, closing each unit out after its parts."""

    output_key: str = "content_ok"
    stage: ClassVar[StageName] = "07_content"
    send_to_slot: ClassVar[str | None] = TASK

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> bool:
        return await self.run_phase(
            article_ctx, self.compose_chapters_phase, send_to=send_to, persist_dir=persist_dir, **cxt
        )


class AssembleArticleStage(StageAction, ArticleCompose):
    """Fire ``after_compose_article_context``, then materialize the composed context tree as an Article."""

    output_key: str = "article"
    stage: ClassVar[StageName] = "08_article"
    send_to_slot: ClassVar[str | None] = TASK

    async def _execute(
        self,
        article_ctx: ArticleContext,
        send_to: str | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> Article:
        return await self.run_phase(article_ctx, self.finish_article, send_to=send_to, persist_dir=persist_dir, **cxt)


class DumpArticleStage(Action, ArticleCompose):
    """Fire ``post_process_article``, then dump the article's typst source to the run's output path.

    The task's ``article_output_path`` names the file; a run that names none dumps
    ``article.typ`` under the run's ``persist_dir``, so a persisted run always ends with
    its deliverable beside its snapshots.
    """

    output_key: str = OUTPUT_KEY

    async def _execute(
        self,
        article_ctx: ArticleContext,
        article: Article,
        article_output_path: str | Path | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> Path:
        article = await self.post_process_article(article_ctx, article, **cxt)
        out = (
            Path(article_output_path)
            if article_output_path
            else Path(ok(persist_dir, "`article_output_path` nor `persist_dir` is set in the task init context"))
            / "article.typ"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        article.finalized_dump_to(out)
        logger.info(f"Article '{article.title}' dumped to {out.as_posix()}")
        return out


class DumpOutlineStage(Action, ArticleCompose):
    """Materialize the planned outline from the context tree and dump it to the run's output path.

    The outline is the pipeline's structure-only deliverable: the same tree every prose
    write is grounded on, rendered in typst format for a run that stops before composing.
    """

    output_key: str = OUTPUT_KEY

    async def _execute(
        self,
        article_ctx: ArticleContext,
        article_output_path: str | Path | None = None,
        persist_dir: str | Path | None = None,
        **cxt,
    ) -> Path:
        outline = ArticleOutline.from_context(article_ctx)
        article_ctx.artifacts.update_outline(outline)
        out = (
            Path(article_output_path)
            if article_output_path
            else Path(ok(persist_dir, "`article_output_path` nor `persist_dir` is set in the task init context"))
            / "outline.typ"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        outline.finalized_dump_to(out)
        logger.info(f"Article outline '{outline.title}' dumped to {out.as_posix()}")
        return out


class ExtractArticleEssence(Action, Propose):
    """Extract the essence of article(s) in text format from the paths specified in the task dependencies.

    Notes:
        This action is designed to extract vital information from articles with Markdown format, which is pure text, and
        which is converted from pdf files using `magic-pdf` from the `MinerU` project, see https://github.com/opendatalab/MinerU
    """

    output_key: str = "article_essence"
    """The key of the output data."""

    async def _execute(
        self,
        task_input: Task,
        reader: Callable[[str], str | None] = lambda p: Path(p).read_text(encoding="utf-8"),
        **_,
    ) -> list[ArticleEssence]:
        if not task_input.dependencies:
            logger.info(err := "Task not approved, since no dependencies are provided.")
            raise RuntimeError(err)
        logger.info(f"Extracting article essence from {len(task_input.dependencies)} files.")
        # trim the references
        contents = list(filter_map(reader, task_input.dependencies))
        logger.info(f"Read {len(task_input.dependencies)} to get {len(contents)} contents.")

        out = []

        for ess in await self.propose(
            ArticleEssence,
            TEMPLATE_MANAGER.render_template(typst_config.extract_essence_template, [{"content": c} for c in contents]),
        ):
            if ess is None:
                logger.warn("Could not extract article essence")
            else:
                out.append(ess)
        logger.info(f"Extracted {len(out)} article essence from {len(task_input.dependencies)} files.")
        return out


class FixArticleEssence(Action):
    """Fix the article essence based on the bibtex key."""

    output_key: str = "fixed_article_essence"
    """The key of the output data."""

    async def _execute(
        self,
        bib_mgr: BibManager,
        article_essence: list[ArticleEssence],
        **_,
    ) -> list[ArticleEssence]:
        out = []
        count = 0
        for a in article_essence:
            if key := (bib_mgr.get_cite_key_by_title(a.title) or bib_mgr.get_cite_key_fuzzy(a.title)):
                a.title = bib_mgr.get_title_by_key(key) or a.title
                a.authors = bib_mgr.get_author_by_key(key) or a.authors
                a.publication_year = bib_mgr.get_year_by_key(key) or a.publication_year
                a.bibtex_cite_key = key
                logger.info(f"Updated {a.title} with {key}")
                out.append(a)
            else:
                logger.warn(f"No key found for {a.title}")
                count += 1
        if count:
            logger.warn(f"{count} articles have no key")
        return out


class ExtractOutlineFromRaw(Action, Extract):
    """Extract the outline from the raw outline."""

    output_key: str = "article_outline_from_raw"

    async def _execute(self, article_outline_raw_path: str | Path, **cxt) -> ArticleOutline:
        logger.info(f"Extracting outline from raw: {Path(article_outline_raw_path).as_posix()}")

        return ok(
            await self.extract(ArticleOutline, Path(article_outline_raw_path).read_text(encoding="utf-8")),
            "Could not extract the outline from raw.",
        )


class FixIntrospectedErrors(Action, Censor):
    """Fix introspected errors in the article outline."""

    output_key: str = "introspected_errors_fixed_outline"
    """The key of the output data."""

    ruleset: RuleSet | None = None
    """The ruleset to use to fix the introspected errors."""
    max_error_count: int | None = None
    """The maximum number of errors to fix."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        intro_fix_ruleset: RuleSet | None = None,
        **_,
    ) -> ArticleOutline | None:
        counter = 0
        origin = article_outline
        while pack := article_outline.gather_introspected():
            logger.info(f"Found {counter}th introspected errors")
            logger.warn(f"Found introspected error: {pack}")
            corrected = ok(
                await self.censor_obj(
                    article_outline,
                    ruleset=ok(intro_fix_ruleset or self.ruleset, "No ruleset provided"),
                    reference=f"{article_outline.display()}\n # Fatal Error of the Original Article Outline\n{pack}",
                ),
                "Could not correct the component.",
            )
            corrected.artifacts = origin.artifacts
            article_outline = corrected

            if self.max_error_count and counter > self.max_error_count:
                logger.warn("Max error count reached, stopping.")
                break
            counter += 1

        return article_outline


class LoadArticle(Action):
    """Load the article from the outline and typst code."""

    output_key: str = "loaded_article"

    async def _execute(self, article_outline: ArticleOutline, typst_code: str, **cxt) -> Article:
        return Article.from_mixed_source(article_outline, typst_code)


class WriteChapterSummary(Action, UseLLM):
    """Write the chapter summary."""

    ctx_override: ClassVar[bool] = True

    paragraph_count: int = 1
    """The number of paragraphs to generate in the chapter summary."""

    summary_word_count: int = 120
    """The number of words to use in each chapter summary."""
    output_key: str = "summarized_article"
    """The key under which the summarized article will be stored in the output."""
    summary_title: str = "Chapter Summary"
    """The title to be used for the generated chapter summary section."""

    skip_chapters: list[str] = Field(default_factory=list)
    """A list of chapter titles to skip during summary generation."""

    async def _execute(self, article_path: Path, **cxt) -> Article:
        article = Article.from_article_file(article_path, article_path.stem)

        chaps = [c for c in article.chapters if c.title not in self.skip_chapters]

        retained_chapters = []
        # Count chapters before filtering based on section presence,
        # chaps at this point has already been filtered by self.skip_chapters
        initial_chaps_for_summary_step_count = len(chaps)

        for chapter_candidate in chaps:
            if chapter_candidate.sections:  # Check if the sections list is non-empty
                retained_chapters.append(chapter_candidate)
            else:
                # Log c warning for each chapter skipped due to lack of sections
                logger.warn(
                    f"Chapter '{chapter_candidate.title}' has no sections and will be skipped for summary generation.",
                )

        chaps = retained_chapters  # Update chaps to only include chapters with sections

        # If chaps is now empty, but there were chapters to consider at the start of this step,
        # log c specific warning.
        if not chaps and initial_chaps_for_summary_step_count > 0:
            raise ValueError("No chapters with sections were found. Please check your input data.")

        # This line was part of the original selection.
        # It will now log the titles of the chapters that are actually being processed (those with sections).
        # If 'chaps' is empty, this will result in logger.info(""), which is acceptable.
        logger.info(";".join(a.title for a in chaps))
        ret = [
            ArticleSubsection.from_typst_code(self.summary_title, raw)
            for raw in (
                await self.aask(
                    TEMPLATE_MANAGER.render_template(
                        typst_config.chap_summary_template,
                        [
                            {
                                "chapter": c.to_typst_code(),
                                "title": c.title,
                                "language": c.language,
                                "summary_word_count": self.summary_word_count,
                                "paragraph_count": self.paragraph_count,
                            }
                            for c in chaps
                        ],
                    ),
                )
            )
        ]

        for c, n in zip(chaps, ret, strict=True):
            c: ArticleChapter
            n: ArticleSubsection
            if c.sections[-1].title == self.summary_title:
                logger.debug(f"Removing old summary `{self.summary_title}` at {c.title}")
                c.sections.pop()

            c.sections[-1].subsections.append(n)

        article.update_article_file(article_path)

        dump_text(
            article_path,
            Path(article_path).read_text("utf-8").replace(f"=== {self.summary_title}", f"== {self.summary_title}"),
        )
        return article


class WriteResearchContentSummary(Action, UseLLM):
    """Write the research content summary."""

    ctx_override: ClassVar[bool] = True
    summary_word_count: int = 160
    """The number of words to use in the research content summary."""

    output_key: str = "summarized_article"
    """The key under which the summarized article will be stored in the output."""
    summary_title: str = "Research Content"
    """The title to be used for the generated research content summary section."""

    paragraph_count: int = 1
    """The number of paragraphs to generate in the research content summary."""

    async def _execute(self, article_path: Path, **cxt) -> Article:
        article = Article.from_article_file(article_path, article_path.stem)
        if not article.chapters:
            raise ValueError("No chapters found in the article.")
        chap_1 = article.chapters[0]
        if not chap_1.sections:
            raise ValueError("No sections found in the first chapter of the article.")

        outline = article.extract_outline()
        suma: str = await self.aask(
            TEMPLATE_MANAGER.render_template(
                typst_config.research_content_summary_template,
                {
                    "title": outline.title,
                    "outline": outline.to_typst_code(),
                    "language": detect_language(self.summary_title),
                    "summary_word_count": self.summary_word_count,
                    "paragraph_count": self.paragraph_count,
                },
            ),
        )
        logger.info(f"{self.summary_title}|Wordcount: {word_count(suma)}|Expected: {self.summary_word_count}\n{suma}")

        if chap_1.sections[-1].title == self.summary_title:
            # remove old
            logger.debug(f"Removing old summary `{self.summary_title}`")
            chap_1.sections.pop()

        chap_1.sections[-1].subsections.append(ArticleSubsection.from_typst_code(self.summary_title, suma))

        article.update_article_file(article_path)
        dump_text(
            article_path,
            Path(article_path).read_text("utf-8").replace(f"=== {self.summary_title}", f"== {self.summary_title}"),
        )
        return article


class CompileKwargs(TypedDict, total=False):
    """Keyword arguments passed to `typst.compile()`."""

    format: str
    ppi: float
    pdf_standards: list[str]
    sys_inputs: dict[str, str]


def compile_typst_source(
    typst_source: str | Path,
    output_path: Path,
    **kwargs: Unpack[CompileKwargs],
) -> Path:
    """Compile a Typst source to disk using the `typst` compiler.

    Args:
        typst_source: Path to a `.typ` file, or source content as a string.
        output_path: Where to write the compiled output.
        **kwargs: Forwarded to `typst.compile()`. Key options:
            format: Output format ("pdf", "png", "svg"). Defaults to "pdf".
            ppi: Pixels per inch for raster output (png only). Defaults to 144.0.
            pdf_standards: PDF standards, e.g. ["a-2a", "ua-1"].
            sys_inputs: Values passed to Typst's `sys.inputs`.

    Returns:
        Path to the compiled file.
    """
    import typst

    # Normalize: Path → file path string, str → source bytes
    source: str | bytes = str(typst_source) if isinstance(typst_source, Path) else typst_source.encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    typst.compile(input=source, output=str(output_path), **kwargs)
    logger.info(f"Compiled typst document to {output_path.as_posix()}")
    return output_path


class CompileTypstDocument(Action):
    """Compile a Typst document to PDF, PNG, or SVG using the typst compiler.

    Accepts a Path to a `.typ` file or source content as a string.
    """

    output_key: str = "compiled_path"

    async def _execute(
        self,
        typst_source: str | Path,
        output_path: Path,
        **kwargs: Unpack[CompileKwargs],
    ) -> Path:
        """Compile a Typst document and write to disk.

        Args:
            typst_source: Path to a `.typ` file, or source content as a string.
            output_path: Where to write the compiled output.
            **kwargs: Forwarded to `typst.compile()`. See `CompileKwargs`.

        Returns:
            Path to the compiled file.
        """
        return compile_typst_source(
            typst_source=typst_source,
            output_path=output_path,
            **kwargs,
        )


class CompileArticle(Action):
    """Compile a generated Article's `.typ` file to PDF.

    Expects the article to have been previously dumped to a `.typ` file via DumpFinalizedOutput.
    Reads the `.typ` from disk, compiles it, and writes the output next to the source.
    """

    output_key: str = "compiled_path"

    async def _execute(
        self,
        article_path: Path,
        output_path: Path | None = None,
        **kwargs: Unpack[CompileKwargs],
    ) -> Path:
        """Compile an article's `.typ` file to the configured output format.

        Args:
            article_path: Path to the `.typ` source file.
            output_path: Override output path. Defaults to same name with format suffix.
            **kwargs: Forwarded to `typst.compile()`. See `CompileKwargs`.

        Returns:
            Path to the compiled output file.
        """
        fmt = kwargs.get("format", "pdf")
        out = output_path or article_path.with_suffix(f".{fmt}")

        return compile_typst_source(
            typst_source=article_path,
            output_path=out,
            **kwargs,
        )
