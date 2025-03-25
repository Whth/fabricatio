"""Actions for transmitting tasks to targets."""

from asyncio import gather
from pathlib import Path
from typing import Any, Callable, List, Optional

from fabricatio.capabilities.advanced_judge import AdvancedJudge
from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.article_base import ArticleRefPatch
from fabricatio.models.extra.article_essence import ArticleEssence
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.task import Task
from fabricatio.models.utils import ok


class ExtractArticleEssence(Action):
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
        reader: Callable[[str], str] = lambda p: Path(p).read_text(encoding="utf-8"),
        **_,
    ) -> Optional[List[ArticleEssence]]:
        if not task_input.dependencies:
            logger.info(err := "Task not approved, since no dependencies are provided.")
            raise RuntimeError(err)

        # trim the references
        contents = ["References".join(c.split("References")[:-1]) for c in map(reader, task_input.dependencies)]
        return await self.propose(
            ArticleEssence,
            contents,
            system_message=f"# your personal briefing: \n{self.briefing}",
        )


class GenerateArticleProposal(Action):
    """Generate an outline for the article based on the extracted essence."""

    output_key: str = "article_proposal"
    """The key of the output data."""

    async def _execute(
        self,
        task_input: Optional[Task] = None,
        article_briefing: Optional[str] = None,
        article_briefing_path: Optional[str] = None,
        langauge: Optional[str] = None,
        **_,
    ) -> Optional[ArticleProposal]:
        if article_briefing is None and article_briefing_path is None and task_input is None:
            logger.error("Task not approved, since all inputs are None.")
            return None

        proposal = ok(
            await self.propose(
                ArticleProposal,
                briefing := (
                    article_briefing
                    or safe_text_read(
                        ok(
                            article_briefing_path
                            or await self.awhich_pathstr(
                                f"{ok(task_input).briefing}\nExtract the path of file which contains the article briefing."
                            ),
                            "Could not find the path of file to read.",
                        )
                    )
                ),
                **self.prepend_sys_msg(),
            ),
            "Could not generate the proposal.",
        ).update_ref(briefing)
        if langauge:
            proposal.language = langauge

        return proposal


class GenerateInitialOutline(Action):
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
                article_proposal.as_prompt(),
                **self.prepend_sys_msg(),
            ),
            "Could not generate the initial outline.",
        ).update_ref(article_proposal)


class FixIntrospectedErrors(Action):
    """Fix introspected errors in the article outline."""

    output_key: str = "introspected_errors_fixed_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        supervisor_check: bool = False,
        **_,
    ) -> Optional[ArticleOutline]:
        introspect_manual = ok(
            await self.draft_rating_manual(
                topic=(
                    intro_topic
                    := "Fix the error in the article outline, make sure there is no more error in the article outline."
                ),
            ),
            "Could not generate the rating manual.",
        )

        while pack := article_outline.find_introspected():
            component, err = ok(pack)
            logger.warning(f"Found introspected error: {err}")
            corrected = ok(
                await self.correct_obj(
                    component,
                    reference=f"# Original Article Outline\n{article_outline.display()}\n# Error Need to be fixed\n{err}",
                    topic=intro_topic,
                    rating_manual=introspect_manual,
                    supervisor_check=supervisor_check,
                ),
                "Could not correct the component.",
            )
            component.update_from(corrected)

        return article_outline


class FixIllegalReferences(Action):
    """Fix illegal references in the article outline."""

    output_key: str = "illegal_references_fixed_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        supervisor_check: bool = False,
        **_,
    ) -> Optional[ArticleOutline]:
        ref_manual = ok(
            await self.draft_rating_manual(
                topic=(
                    ref_topic
                    := "Fix the internal referring error, make sure there is no more `ArticleRef` pointing to a non-existing article component."
                ),
            ),
            "Could not generate the rating manual.",
        )

        while pack := article_outline.find_illegal_ref():
            ref, err = ok(pack)
            logger.warning(f"Found illegal referring error: {err}")
            ok(
                await self.correct_obj_inplace(
                    ref,
                    reference=f"# Original Article Outline\n{article_outline.display()}\n# Error Need to be fixed\n{err}",
                    topic=ref_topic,
                    rating_manual=ref_manual,
                    supervisor_check=supervisor_check,
                )
            )
        return article_outline.update_ref(article_outline)


class TweakOutlineBackwardRef(Action, AdvancedJudge):
    """Tweak the backward references in the article outline.

    Ensures that the prerequisites of the current chapter are correctly referenced in the `depend_on` field.
    """

    output_key: str = "article_outline_bw_ref_checked"

    async def _execute(self, article_outline: ArticleOutline, supervisor_check: bool = False, **cxt) -> ArticleOutline:
        tweak_depend_on_manual = ok(
            await self.draft_rating_manual(
                topic := "Ensure prerequisites are correctly referenced in the `depend_on` field."
            ),
            "Could not generate the rating manual.",
        )

        for a in article_outline.iter_dfs():
            if await self.evidently_judge(
                f"{article_outline.as_prompt()}\n\n{a.display()}\n"
                f"Does the `{a.__class__.__name__}`'s `depend_on` field need to be extended or tweaked?"
            ):
                patch = ArticleRefPatch.default()
                patch.tweaked = a.depend_on

                await self.correct_obj_inplace(
                    patch,
                    topic=topic,
                    reference=f"{article_outline.as_prompt()}\nThe Article component whose `depend_on` field needs to be extended or tweaked",
                    rating_manual=tweak_depend_on_manual,
                    supervisor_check=supervisor_check,
                )

        return article_outline


class TweakOutlineForwardRef(Action, AdvancedJudge):
    """Tweak the forward references in the article outline.

    Ensures that the conclusions of the current chapter effectively support the analysis of subsequent chapters.
    """

    output_key: str = "article_outline_fw_ref_checked"

    async def _execute(self, article_outline: ArticleOutline, supervisor_check: bool = False, **cxt) -> ArticleOutline:
        tweak_support_to_manual = ok(
            await self.draft_rating_manual(
                topic := "Ensure conclusions support the analysis of subsequent chapters, sections or subsections."
            ),
            "Could not generate the rating manual.",
        )

        for a in article_outline.iter_dfs():
            if await self.evidently_judge(
                f"{article_outline.as_prompt()}\n\n{a.display()}\n"
                f"Does the `{a.__class__.__name__}`'s `support_to` field need to be extended or tweaked?"
            ):
                patch = ArticleRefPatch.default()
                patch.tweaked = a.support_to

                await self.correct_obj_inplace(
                    patch,
                    topic=topic,
                    reference=f"{article_outline.as_prompt()}\nThe Article component whose `support_to` field needs to be extended or tweaked",
                    rating_manual=tweak_support_to_manual,
                    supervisor_check=supervisor_check,
                )

        return article_outline


class GenerateArticle(Action):
    """Generate the article based on the outline."""

    output_key: str = "article"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        supervisor_check: bool = False,
        **_,
    ) -> Optional[Article]:
        article: Article = Article.from_outline(ok(article_outline, "Article outline not specified.")).update_ref(
            article_outline
        )

        write_para_manual = ok(
            await self.draft_rating_manual(w_topic := "write the following paragraph in the subsection.")
        )

        await gather(
            *[
                self.correct_obj_inplace(
                    subsec,
                    reference=f"# Original Article Outline\n{article_outline.display()}\n# Error Need to be fixed\n{err}",
                    topic=w_topic,
                    rating_manual=write_para_manual,
                    supervisor_check=supervisor_check,
                )
                for _, __, subsec in article.iter_subsections()
                if (err := subsec.introspect())
            ],
            return_exceptions=True,
        )

        return article


class CorrectProposal(Action):
    """Correct the proposal of the article."""

    output_key: str = "corrected_proposal"

    async def _execute(self, article_proposal: ArticleProposal, **_) -> Any:
        return (await self.censor_obj(article_proposal, reference=article_proposal.referenced)).update_ref(
            article_proposal
        )


class CorrectOutline(Action):
    """Correct the outline of the article."""

    output_key: str = "corrected_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        **_,
    ) -> ArticleOutline:
        return (await self.censor_obj(article_outline, reference=article_outline.referenced.as_prompt())).update_ref(
            article_outline
        )


class CorrectArticle(Action):
    """Correct the article based on the outline."""

    output_key: str = "corrected_article"
    """The key of the output data."""

    async def _execute(
        self,
        article: Article,
        article_outline: ArticleOutline,
        **_,
    ) -> Article:
        return await self.censor_obj(article, reference=article_outline.referenced.as_prompt())
