"""The Capabilities module for advanced judging."""

from typing import Optional, Unpack

from fabricatio.capabilities.propose import Propose
from fabricatio.models.extra.advanced_judge import JudgeMent
from fabricatio.models.kwargs_types import ValidateKwargs


class AdvancedJudge(Propose):
    """A class that judges the evidence and makes a final decision."""
    async def evidently_judge(
        self,
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[JudgeMent]:
        """Judge the evidence and make a final decision."""
        return await self.propose(
            JudgeMent,
            prompt,
            **kwargs
        )

