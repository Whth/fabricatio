"""SelectiveRemember class enables conditional memory recording based on judgments.

It combines functionalities from Remember and AdvancedJudge classes.
"""

from fabricatio_core.utils import cfg

cfg(feats=["selective"])
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge

from fabricatio_memory.capabilities.remember import Remember
from fabricatio_memory.config import memory_config
from fabricatio_memory.models.note import Note


class SelectiveRemember(Remember, EvidentlyJudge):
    """A class that implements selective memory recording by leveraging judgment capabilities.

    It decides whether to remember certain data based on the outcome of a judgment process.
    """

    async def sremember(
        self, prerequisite: str, raw: str, *, send_to: str | None = TASK, **kwargs: Unpack[ValidateKwargs[Note]]
    ) -> Note | None:
        """Conditionally records a memory based on a judgment.

        Args:
            prerequisite: A string representing the condition or context for remembering.
            raw: The raw data to be potentially remembered.
            send_to: Routing group for LLM calls (TASK, SMOL, TINY, SLOW, PLAN).
            **kwargs: Additional keyword arguments for validation and customization.

        Returns:
            A Note object if the data is recorded, otherwise None.
        """
        if await self.evidently_judge(
            TEMPLATE_MANAGER.render_template(
                memory_config.sremember_template, {"prerequisite": prerequisite, "raw": raw}
            ),
            send_to=send_to,
        ):
            return await self.record(raw, send_to=send_to, **kwargs)
        return None
