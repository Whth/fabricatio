"""Actions for transmitting tasks to targets."""

from asyncio import gather
from pathlib import Path
from typing import Callable, List, Optional

from more_itertools import filter_map
from pydantic import Field
from rich import print as r_print

from fabricatio.capabilities.censor import Censor
from fabricatio.capabilities.extract import Extract
from fabricatio.capabilities.propose import Propose
from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.article_essence import ArticleEssence
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.kwargs_types import ValidateKwargs
from fabricatio.models.task import Task
from fabricatio.rust import BibManager, detect_language
from fabricatio.utils import ok, wrapp_in_block


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
            [
                f"{c}\n\n\nBased the provided academic article above, you need to extract the essence from it.\n\nWrite the value string using `{detect_language(c)}`"
                for c in contents
            ],
        ):
            if ess is None:
                logger.warning("Could not extract article essence")
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
                logger.warning(f"No key found for {a.title}")
                count += 1
        if count:
            logger.warning(f"{count} articles have no key")
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

        briefing = article_briefing or safe_text_read(
            ok(
                article_briefing_path
                or await self.awhich_pathstr(
                    f"{ok(task_input).briefing}\nExtract the path of file which contains the article briefing."
                ),
                "Could not find the path of file to read.",
            )
        )

        logger.info("Start generating the proposal.")
        return ok(
            await self.propose(
                ArticleProposal,
                f"{briefing}\n\nWrite the value string using `{detect_language(briefing)}` as written language.",
            ),
            "Could not generate the proposal.",
        ).update_ref(briefing)


class GenerateInitialOutline(Action, Extract):
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
        req = (
            f"Design each chapter of a proper and academic and ready for release manner.\n"
            f"You Must make sure every chapter have sections, and every section have subsections.\n"
            f"Make the chapter and sections and subsections bing divided into a specific enough article component.\n"
            f"Every chapter must have sections, every section must have subsections.\n"
            f"Note that you SHALL use `{article_proposal.language}` as written language",
        )

        raw_outline = await self.aask(f"{(article_proposal.as_prompt())}\n{req}")

        if supervisor or (supervisor is None and self.supervisor):
            from questionary import confirm, text

            r_print(raw_outline)
            while not await confirm("Accept this version and continue?", default=True).ask_async():
                imp = await text("Enter the improvement:").ask_async()
                raw_outline = await self.aask(
                    f"{article_proposal.as_prompt()}\n{wrapp_in_block(raw_outline, 'Previous ArticleOutline')}\n{req}\n{wrapp_in_block(imp, title='Improvement')}"
                )
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
            await self.extract(ArticleOutline, safe_text_read(article_outline_raw_path)),
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
            logger.warning(f"Found introspected error: {pack}")
            article_outline = ok(
                await self.censor_obj(
                    article_outline,
                    ruleset=ok(intro_fix_ruleset or self.ruleset, "No ruleset provided"),
                    reference=f"{article_outline.display()}\n # Fatal Error of the Original Article Outline\n{pack}",
                ),
                "Could not correct the component.",
            ).update_ref(origin)

            if self.max_error_count and counter > self.max_error_count:
                logger.warning("Max error count reached, stopping.")
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
                if (err := subsec.introspect()) and logger.warning(f"Found Introspection Error:\n{err}") is None
            ],
        )

        return article


class LoadArticle(Action):
    """Load the article from the outline and typst code."""

    output_key: str = "loaded_article"

    async def _execute(self, article_outline: ArticleOutline, typst_code: str, **cxt) -> Article:
        return Article.from_mixed_source(article_outline, typst_code)
