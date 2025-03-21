"""Actions for transmitting tasks to targets."""

from pathlib import Path
from typing import Any, Callable, List, Optional

from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra import Article, ArticleEssence, ArticleOutline, ArticleProposal
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
        **_,
    ) -> Optional[ArticleProposal]:
        if article_briefing is None and article_briefing_path is None and task_input is None:
            logger.info("Task not approved, since ")
            return None
        if article_briefing_path is None and task_input:
            article_briefing_path = await self.awhich_pathstr(
                f"{task_input.briefing}\nExtract the path of file which contains the article briefing."
            )

        return (
            await self.propose(
                ArticleProposal,
                briefing := (
                    article_briefing
                    or safe_text_read(ok(article_briefing_path, "Could not find the path of file to read."))
                ),
                **self.prepend_sys_msg(),
            )
        ).update_ref(briefing)


class GenerateOutline(Action):
    """Generate the article based on the outline."""

    output_key: str = "article_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_proposal: ArticleProposal,
        **_,
    ) -> Optional[ArticleOutline]:
        out = await self.propose(
            ArticleOutline,
            article_proposal.as_prompt(),
            **self.prepend_sys_msg(),
        )

        while err := out.resolve_ref_error():
            logger.warning(f"Found error in the outline: \n{err}")
            out = await self.correct_obj(
                out,
                reference=err,
                topic="This `ArticleOutline` has some references that is not valid.",
                supervisor_check=False,
            )
        return out.update_ref(article_proposal)


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


class GenerateArticle(Action):
    """Generate the article based on the outline."""

    output_key: str = "article"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        **_,
    ) -> Optional[Article]:
        article: Article = Article.from_outline(article_outline).update_ref(article_outline)

        for c, deps in article.iter_dfs_with_deps():
            logger.info(f"Updating the article component: \n{c.display()}")

            out = ok(
                await self.correct_obj(
                    c,
                    reference=f"{article_outline.referenced.as_prompt()}\n" + "\n".join(d.display() for d in deps),
                    topic="If this academic article component is good",
                    supervisor_check=False,
                ),
                "Could not correct the article component.",
            )

            c.update_from(out)
        return article


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
