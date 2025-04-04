"""Actions for transmitting tasks to targets."""

from asyncio import gather
from pathlib import Path
from typing import Callable, List, Optional

from more_itertools import filter_map

from fabricatio.capabilities.censor import Censor
from fabricatio.capabilities.propose import Propose
from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.article_base import SubSectionBase
from fabricatio.models.extra.article_essence import ArticleEssence
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.task import Task
from fabricatio.rust import BibManager, detect_language
from fabricatio.utils import ok


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
            if key := (bib_mgr.get_cite_key(a.title) or bib_mgr.get_cite_key_fuzzy(a.title)):
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


class GenerateInitialOutline(Action, Propose):
    """Generate the initial article outline based on the article proposal."""

    output_key: str = "initial_article_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_proposal: ArticleProposal,
        **_,
    ) -> Optional[ArticleOutline]:
        return ok(
            await self.propose(
                ArticleOutline,
                f"{(article_proposal.as_prompt())}\n\nNote that you should use `{article_proposal.language}` to write the `ArticleOutline`\n"
                f"You Must make sure every chapter have sections, and every section have subsections.",
            ),
            "Could not generate the initial outline.",
        ).update_ref(article_proposal)


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
                    reference=f"{article_outline.as_prompt()}\n # Fatal Error of the Original Article Outline\n{pack}",
                ),
                "Could not correct the component.",
            ).update_ref(origin)

            if self.max_error_count and counter > self.max_error_count:
                logger.warning("Max error count reached, stopping.")
                break
            counter += 1

        return article_outline


class FixIllegalReferences(Action, Censor):
    """Fix illegal references in the article outline."""

    output_key: str = "illegal_references_fixed_outline"
    """The key of the output data."""

    ruleset: Optional[RuleSet] = None
    """Ruleset to use to fix the illegal references."""
    max_error_count: Optional[int] = None
    """The maximum number of errors to fix."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        ref_fix_ruleset: Optional[RuleSet] = None,
        **_,
    ) -> Optional[ArticleOutline]:
        counter = 0
        while pack := article_outline.find_illegal_ref(gather_identical=True):
            logger.info(f"Found {counter}th illegal references")
            ref_seq, err = ok(pack)
            logger.warning(f"Found illegal referring error: {err}")
            new = ok(
                await self.censor_obj(
                    ref_seq[0],
                    ruleset=ok(ref_fix_ruleset or self.ruleset, "No ruleset provided"),
                    reference=f"{article_outline.as_prompt()}\n# Some Basic errors found that need to be fixed\n{err}",
                ),
                "Could not correct the component",
            )
            for r in ref_seq:
                r.update_from(new)
            if self.max_error_count and counter > self.max_error_count:
                logger.warning("Max error count reached, stopping.")
                break
            counter += 1

        return article_outline


class TweakOutlineForwardRef(Action, Censor):
    """Tweak the forward references in the article outline.

    Ensures that the conclusions of the current chapter effectively support the analysis of subsequent chapters.
    """

    output_key: str = "article_outline_fw_ref_checked"
    ruleset: Optional[RuleSet] = None
    """Ruleset to use to fix the illegal references."""

    async def _execute(
        self, article_outline: ArticleOutline, ref_twk_ruleset: Optional[RuleSet] = None, **cxt
    ) -> ArticleOutline:
        return await self._inner(
            article_outline,
            ruleset=ok(ref_twk_ruleset or self.ruleset, "No ruleset provided"),
            field_name="support_to",
        )

    async def _inner(self, article_outline: ArticleOutline, ruleset: RuleSet, field_name: str) -> ArticleOutline:
        await gather(
            *[self._loop(a[-1], article_outline, field_name, ruleset) for a in article_outline.iter_subsections()],
        )

        return article_outline

    async def _loop(
        self, a: SubSectionBase, article_outline: ArticleOutline, field_name: str, ruleset: RuleSet
    ) -> None:
        if judge := await self.evidently_judge(
            f"{article_outline.as_prompt()}\n\n{a.display()}\n"
            f"Does the `{a.__class__.__name__}`'s `{field_name}` field need to be extended or tweaked?"
        ):
            await self.censor_obj_inplace(
                a,
                ruleset=ruleset,
                reference=f"{article_outline.as_prompt()}\n"
                f"The Article component titled `{a.title}` whose `{field_name}` field needs to be extended or tweaked.\n"
                f"# Judgement\n{judge.display()}",
            )


class TweakOutlineBackwardRef(TweakOutlineForwardRef):
    """Tweak the backward references in the article outline.

    Ensures that the prerequisites of the current chapter are correctly referenced in the `depend_on` field.
    """

    output_key: str = "article_outline_bw_ref_checked"
    ruleset: Optional[RuleSet] = None

    async def _execute(
        self, article_outline: ArticleOutline, ref_twk_ruleset: Optional[RuleSet] = None, **cxt
    ) -> ArticleOutline:
        return await self._inner(
            article_outline,
            ruleset=ok(ref_twk_ruleset or self.ruleset, "No ruleset provided"),
            field_name="depend_on",
        )


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
