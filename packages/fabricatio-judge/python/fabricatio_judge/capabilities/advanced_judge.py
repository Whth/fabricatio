"""The Capabilities module for advanced judging."""

from abc import ABC
from typing import List, Optional, Unpack, overload

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_judge.models.judgement import JudgeMent


class AdvancedJudge(Propose, ABC):
    """A class that judges the evidence and makes a final decision."""

    @overload
    async def evidently_judge(
        self,
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[JudgeMent]: ...
    @overload
    async def evidently_judge(
        self,
        prompt: List[str],
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[List[JudgeMent] | List[JudgeMent | None]]: ...

    async def evidently_judge(
        self,
        prompt: str | List[str],
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> List[JudgeMent] | List[JudgeMent | None] | JudgeMent | None:
        """Judge the evidence and make a final decision."""
        return await self.propose(JudgeMent, prompt, **kwargs)
