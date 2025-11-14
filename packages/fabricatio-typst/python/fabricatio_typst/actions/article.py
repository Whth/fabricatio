"""Actions for transmitting tasks to targets."""

from asyncio import gather
from pathlib import Path
from typing import Callable, ClassVar, List, Optional

from fabricatio_capabilities.capabilities.extract import Extract
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.models.task import Task
from fabricatio_core.rust import TEMPLATE_MANAGER, detect_language, word_count
from fabricatio_core.utils import ok, wrap_in_block
from fabricatio_improve.capabilities.correct import Correct
from fabricatio_improve.models.improve import Improvement
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import RuleSet
from fabricatio_tool.fs import dump_text
from more_itertools import filter_map
from pydantic import Field
from rich import print as r_print

from fabricatio_typst.config import typst_config
from fabricatio_typst.models.article_essence import ArticleEssence
from fabricatio_typst.models.article_main import Article, ArticleChapter, ArticleSubsection
from fabricatio_typst.models.article_outline import ArticleOutline
from fabricatio_typst.models.article_proposal import ArticleProposal
from fabricatio_typst.rust import BibManager


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
        reader: Callable[[str], Optional[str]] = lambda p: Path(p).read_text(encoding="utf-8"),
        **_,
    ) -> List[ArticleEssence]:
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
        article_essence: List[ArticleEssence],
        **_,
    ) -> List[ArticleEssence]:
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


class GenerateArticleProposal(Action, Propose):
    """Generate an outline for the article based on the extracted essence."""

    output_key: str = "article_proposal"
    """The key of the output data."""

    async def _execute(
        self,
        task_input: Optional[Task] = None,
        article_briefing: Optional[str] = None,
        article_briefing_path: Optional[str] = None,
        **_,
    ) -> Optional[ArticleProposal]:
        if article_briefing is None and article_briefing_path is None and task_input is None:
            logger.error("Task not approved, since all inputs are None.")
            return None

        briefing = article_briefing or Path(
            ok(
                article_briefing_path
                or await self.awhich_pathstr(
                    f"{ok(task_input).briefing}\nExtract the path of file which contains the article briefing."
                ),
                "Could not find the path of file to read.",
            )
        ).read_text(encoding="utf-8")

        logger.info("Start generating the proposal.")
        return ok(
            await self.propose(
                ArticleProposal,
                f"{briefing}\n\nWrite the value string using `{detect_language(briefing)}` as written language.",
            ),
            "Could not generate the proposal.",
        ).update_ref(briefing)


class GenerateInitialOutline(Action, Extract, Correct):
    """Generate the initial article outline based on the article proposal."""

    output_key: str = "initial_article_outline"
    """The key of the output data."""

    supervisor: bool = False
    """Whether to use the supervisor to fix the outline."""

    extract_kwargs: ValidateKwargs[Optional[ArticleOutline]] = Field(default_factory=ValidateKwargs)
    """The kwargs to extract the outline."""

    async def _execute(
        self,
        article_proposal: ArticleProposal,
        supervisor: Optional[bool] = None,
        **_,
    ) -> Optional[ArticleOutline]:
        raw_outline = await self.aask(
            TEMPLATE_MANAGER.render_template(
                typst_config.generate_outline_template,
                {"proposal": article_proposal.as_prompt(), "language": article_proposal.language},
            )
        )

        if supervisor or (supervisor is None and self.supervisor):
            from questionary import confirm, text

            r_print(raw_outline)
            while not await confirm("Accept this version and continue?").ask_async():
                raw_imp = await text("Enter the improvement:").ask_async()

                imp = ok(
                    await self.propose(Improvement, f"{wrap_in_block(raw_outline, 'Previous Outline')}\n\n{raw_imp}")
                )
                raw_outline = (
                    await self.correct_string(
                        raw_outline, imp, wrap_in_block(article_proposal.as_prompt(), "Article Proposal")
                    )
                ) or raw_outline
                r_print(raw_outline)

        return ok(
            await self.extract(ArticleOutline, raw_outline, **self.extract_kwargs),
            "Could not generate the initial outline.",
        ).update_ref(article_proposal)


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

    ruleset: Optional[RuleSet] = None
    """The ruleset to use to fix the introspected errors."""
    max_error_count: Optional[int] = None
    """The maximum number of errors to fix."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        intro_fix_ruleset: Optional[RuleSet] = None,
        **_,
    ) -> Optional[ArticleOutline]:
        counter = 0
        origin = article_outline
        while pack := article_outline.gather_introspected():
            logger.info(f"Found {counter}th introspected errors")
            logger.warn(f"Found introspected error: {pack}")
            article_outline = ok(
                await self.censor_obj(
                    article_outline,
                    ruleset=ok(intro_fix_ruleset or self.ruleset, "No ruleset provided"),
                    reference=f"{article_outline.display()}\n # Fatal Error of the Original Article Outline\n{pack}",
                ),
                "Could not correct the component.",
            ).update_ref(origin)

            if self.max_error_count and counter > self.max_error_count:
                logger.warn("Max error count reached, stopping.")
                break
            counter += 1

        return article_outline


class GenerateArticle(Action, Censor):
    """Generate the article based on the outline."""

    output_key: str = "article"
    """The key of the output data."""
    ruleset: Optional[RuleSet] = None

    async def _execute(
        self,
        article_outline: ArticleOutline,
        article_gen_ruleset: Optional[RuleSet] = None,
        **_,
    ) -> Optional[Article]:
        article: Article = Article.from_outline(ok(article_outline, "Article outline not specified.")).update_ref(
            article_outline
        )

        await gather(
            *[
                self.censor_obj_inplace(
                    subsec,
                    ruleset=ok(article_gen_ruleset or self.ruleset, "No ruleset provided"),
                    reference=f"{article_outline.as_prompt()}\n# Error Need to be fixed\n{err}\nYou should use `{subsec.language}` to write the new `Subsection`.",
                )
                for _, _, subsec in article.iter_subsections()
                if (err := subsec.introspect()) and logger.warn(f"Found Introspection Error:\n{err}") is None
            ],
        )

        return article


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

    skip_chapters: List[str] = Field(default_factory=list)
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
                    f"Chapter '{chapter_candidate.title}' has no sections and will be skipped for summary generation."
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
                    )
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

        outline = article.extrac_outline()
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
            )
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
