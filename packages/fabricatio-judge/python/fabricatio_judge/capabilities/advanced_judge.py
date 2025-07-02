"""The Capabilities module for advanced judging."""

from abc import ABC
from asyncio import gather
from typing import Dict, List, Optional, Unpack, overload

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import override_kwargs

from fabricatio_judge.models.judgement import JudgeMent


class EvidentlyJudge(Propose, ABC):
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


class VoteLLMConfig(ScopedConfig):
    """A class that uses a language model to vote on the evidence."""

    vote_llm: Dict[float, ValidateKwargs[JudgeMent]]
    """Config that specify the models used to make a decision."""

    vote_pass_threshold: Optional[float] = None
    """The threshold for passing the vote."""


class VoteJudge(EvidentlyJudge, VoteLLMConfig, ABC):
    """A class that votes on the evidence and makes a final decision."""

    @overload
    async def vote_judge(
        self,
        prompt: str,
        vote_pass_threshold: Optional[float] = None,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[bool]:
        """Vote on the evidence and make a final decision for a single prompt.

        Args:
            prompt (str): The input prompt to be judged.
            vote_pass_threshold (Optional[float], optional):
                The threshold for passing the vote. Defaults to None.
            **kwargs (Unpack[ValidateKwargs[JudgeMent]]): Additional keyword arguments
                for configuring the judgment process.

        Returns:
            Optional[bool]: A boolean result indicating whether the vote passed,
        """

    @overload
    async def vote_judge(
        self,
        prompt: List[str],
        vote_pass_threshold: Optional[float] = None,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[List[bool | None]]:
        """Vote on the evidence and make a final decision for a list of prompts.

        Args:
            prompt (List[str]): The input prompts to be judged.
            vote_pass_threshold (Optional[float], optional):
                The threshold for passing the vote. Defaults to None.
            **kwargs (Unpack[ValidateKwargs[JudgeMent]]): Additional keyword arguments
                for configuring the judgment process.

        Returns:
            Optional[List[bool | None]]: A list of boolean results indicating
                whether each vote passed, or None if no prompt is provided.
        """

    async def vote_judge(
        self,
        prompt: str | List[str],
        vote_pass_threshold: Optional[float] = None,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[List[bool] | List[bool | None]]:
        """Vote on the evidence and make a final decision.

        Args:
            prompt (str | List[str]): The input prompt(s) to be judged.
            vote_pass_threshold (Optional[float], optional):
                The threshold for passing the vote. Defaults to None.
            **kwargs (Unpack[ValidateKwargs[JudgeMent]]): Additional keyword arguments
                for configuring the judgment process.

        Returns:
            Optional[List[bool] | List[bool | None]]: A list of boolean results indicating
                whether each vote passed, or None if no prompt is provided.
        """
        was_str = isinstance(prompt, str)
        prompt = [prompt] if was_str else prompt

        vote_pass_threshold = vote_pass_threshold or self.vote_pass_threshold
        weights = list(self.vote_llm.keys())

        # Fully concurrent execution using gather for all operations
        judgments_list = await gather(
            *[
                gather(*[self.evidently_judge(p, **override_kwargs(kw, **kwargs)) for kw in self.vote_llm.values()])
                for p in prompt
            ]
        )

        passes = [self.resolve_pass(weights, judgments, vote_pass_threshold) for judgments in judgments_list]

        return passes[0] if was_str else passes

    @staticmethod
    def resolve_pass(
        weights: List[float],
        judgments: List[JudgeMent],
        vote_pass_threshold: float,
    ) -> bool:
        """Determine if the vote passes based on the provided weights and judgments.

        Args:
            weights (List[float]): The weights assigned to each judge.
            judgments (List[JudgeMent]): The list of judgments from the judges.
            vote_pass_threshold (float): The threshold for a successful vote.

        Returns:
            bool: True if the weighted sum of judgments meets or exceeds the threshold,
                  False otherwise.
        """
        return sum(weights) * vote_pass_threshold <= sum(
            w * p.final_judgement for w, p in zip(weights, judgments, strict=True)
        )
