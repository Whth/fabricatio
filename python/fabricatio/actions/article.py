"""Actions for transmitting tasks to targets."""

from asyncio import gather
from pathlib import Path
from typing import Any, Callable, List, Optional

from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action
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


class GenerateOutline(Action):
    """Generate the article based on the outline."""

    output_key: str = "article_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_proposal: ArticleProposal,
        **_,
    ) -> Optional[ArticleOutline]:
        out = ok(
            await self.propose(
                ArticleOutline,
                article_proposal.as_prompt(),
                **self.prepend_sys_msg(),
            ),
            "Could not generate the outline.",
        )

        introspect_manual = ok(
            await self.draft_rating_manual(
                topic=(
                    intro_topic
                    := "Fix the error in the article outline, make sure there is no more error in the article outline."
                ),
            ),
            "Could not generate the rating manual.",
        )

        while pack := out.find_introspected():
            component, err = ok(pack)
            logger.warning(f"Found introspected error: {err}")
            corrected = ok(
                await self.correct_obj(
                    component,
                    reference=f"# Original Article Outline\n{out.display()}\n# Error Need to be fixed\n{err}",
                    topic=intro_topic,
                    rating_manual=introspect_manual,
                    supervisor_check=False,
                ),
                "Could not correct the component.",
            )
            component.update_from(corrected)

        ref_manual = ok(
            await self.draft_rating_manual(
                topic=(
                    ref_topic
                    := "Fix the internal referring error, make sure there is no more `ArticleRef` pointing to a non-existing article component."
                ),
            ),
            "Could not generate the rating manual.",
        )

        while pack := out.find_illegal_ref():
            ref, err = ok(pack)
            logger.warning(f"Found illegal referring error: {err}")
            ok(
                await self.correct_obj_inplace(
                    ref,
                    reference=f"# Original Article Outline\n{out.display()}\n# Error Need to be fixed\n{err}\n\n",
                    topic=ref_topic,
                    rating_manual=ref_manual,
                    supervisor_check=False,
                )
            )
        return out.update_ref(article_proposal)


class GenerateArticle(Action):
    """Generate the article based on the outline."""

    output_key: str = "article"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
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
                    supervisor_check=False,
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
