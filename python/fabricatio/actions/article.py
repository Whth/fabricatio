"""Actions for transmitting tasks to targets."""

from os import PathLike
from pathlib import Path
from typing import Callable, List

from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra import ArticleEssence
from fabricatio.models.task import Task


class ExtractArticleEssence(Action):
    """Extract the essence of article(s)."""

    name: str = "extract article essence"
    """The name of the action."""
    description: str = "Extract the essence of an article. output as json"
    """The description of the action."""

    output_key: str = "article_essence"
    """The key of the output data."""

    async def _execute[P: PathLike | str](
        self,
        task_input: Task,
        reader: Callable[[P], str] = lambda p: Path(p).read_text(encoding="utf-8"),
        **_,
    ) -> List[ArticleEssence]:
        if not await self.ajudge(
            f"= Task\n{task_input.briefing}\n\n\n= Role\n{self.briefing}",
            affirm_case="The task does not violate the role, and could be approved since the file dependencies are specified.",
            deny_case="The task does violate the role, and could not be approved.",
        ):
            logger.info(err := "Task not approved.")
            raise RuntimeError(err)

        # trim the references
        contents = ["References".join(c.split("References")[:-1]) for c in map(reader, task_input.dependencies)]
        return await self.propose(
            ArticleEssence,
            contents,
            system_message=f"# your personal briefing: \n{self.briefing}",
        )
