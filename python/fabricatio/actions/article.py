"""Actions for transmitting tasks to targets."""

from os import PathLike
from pathlib import Path
from typing import Any, Callable, List, Optional

from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra import ArticleEssence, ArticleOutline, ArticleProposal
from fabricatio.models.task import Task
from questionary import confirm, text
from rich import print as rprint


class ExtractArticleEssence(Action):
    """Extract the essence of article(s) in text format from the paths specified in the task dependencies.

    Notes:
        This action is designed to extract vital information from articles with Markdown format, which is pure text, and
        which is converted from pdf files using `magic-pdf` from the `MinerU` project, see https://github.com/opendatalab/MinerU
    """

    output_key: str = "article_essence"
    """The key of the output data."""

    async def _execute[P: PathLike | str](
        self,
        task_input: Task,
        reader: Callable[[P], str] = lambda p: Path(p).read_text(encoding="utf-8"),
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
        task_input: Task,
        **_,
    ) -> Optional[ArticleProposal]:
        input_path = await self.awhich_pathstr(
            f"{task_input.briefing}\nExtract the path of file, which contains the article briefing that I need to read."
        )

        return await self.propose(
            ArticleProposal,
            safe_text_read(input_path),
            system_message=f"# your personal briefing: \n{self.briefing}",
        )


class GenerateOutline(Action):
    """Generate the article based on the outline."""

    output_key: str = "article_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_proposal: ArticleProposal,
        **_,
    ) -> Optional[ArticleOutline]:
        return await self.propose(
            ArticleOutline,
            article_proposal.display(),
            system_message=f"# your personal briefing: \n{self.briefing}",
        )


class CorrectProposal(Action):
    """Correct the proposal of the article."""

    output_key: str = "corrected_proposal"

    async def _execute(self, task_input: Task, article_proposal: ArticleProposal, **_) -> Any:
        input_path = await self.awhich_pathstr(
            f"{task_input.briefing}\nExtract the path of file, which contains the article briefing that I need to read."
        )

        ret = None
        while await confirm("Do you want to correct the Proposal?").ask_async():
            rprint(article_proposal.display())
            while not (topic := await text("What is the topic of the proposal reviewing?").ask_async()):
                ...
            ret = await self.correct_obj(
                article_proposal,
                safe_text_read(input_path),
                topic=topic,
            )
        return ret or article_proposal


class CorrectOutline(Action):
    """Correct the outline of the article."""

    output_key: str = "corrected_outline"
    """The key of the output data."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        article_proposal: ArticleProposal,

        **_,
    ) -> Optional[str]:
        ret = None
        while await confirm("Do you want to correct the outline?").ask_async():
            rprint(article_outline.finalized_dump())
            while not (topic := await text("What is the topic of the outline reviewing?").ask_async()):
                ...
            ret = await self.correct_obj(article_outline, article_proposal.display(), topic=topic)
        return ret or article_outline
