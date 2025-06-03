"""The Capabilities module for advanced judging."""

from abc import ABC
from typing import Optional, Unpack

from fabricatio_capabilities.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_judge.models.advanced_judge import JudgeMent


class AdvancedJudge(Propose, ABC):
    """A class that judges the evidence and makes a final decision."""

    async def evidently_judge(
        self,
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[JudgeMent]:
        """Judge the evidence and make a final decision."""
        return await self.propose(JudgeMent, prompt, **kwargs)
