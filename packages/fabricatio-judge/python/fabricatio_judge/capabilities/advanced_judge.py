"""The Capabilities module for advanced judging."""

from abc import ABC
from asyncio import gather
from pathlib import Path
from typing import Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TINY, VISION
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_judge.config import judge_config
from fabricatio_judge.models.judgement import ImageVerdict, JudgeMent


class EvidentlyJudge(Propose, ABC):
    """A class that judges the evidence and makes a final decision."""

    @overload
    async def evidently_judge(
        self,
        prompt: str,
        send_to: str | None = TINY,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> JudgeMent | None: ...
    @overload
    async def evidently_judge(
        self,
        prompt: list[str],
        send_to: str | None = TINY,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> list[JudgeMent] | list[JudgeMent | None] | None: ...

    async def evidently_judge(
        self,
        prompt: str | list[str],
        send_to: str | None = TINY,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> list[JudgeMent] | list[JudgeMent | None] | JudgeMent | None:
        """Judge the evidence and make a final decision."""
        return await self.propose(JudgeMent, prompt, send_to=send_to, **kwargs)


class VoteLLMConfig(ScopedConfig):
    """A class that uses a language model to vote on the evidence."""

    vote_llm: dict[float, ValidateKwargs[JudgeMent]]
    """Config that specify the models used to make a decision."""

    vote_pass_threshold: float | None = None
    """The threshold for passing the vote."""


class VoteJudge(EvidentlyJudge, VoteLLMConfig, ABC):
    """A class that votes on the evidence and makes a final decision."""

    @overload
    async def vote_judge(
        self,
        prompt: str,
        vote_pass_threshold: float | None = None,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> bool | None:
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
        prompt: list[str],
        vote_pass_threshold: float | None = None,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> list[bool | None] | None:
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
        prompt: str | list[str],
        vote_pass_threshold: float | None = None,
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> bool | list[bool | None] | None:
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

        vote_pass_threshold = ok(vote_pass_threshold or self.vote_pass_threshold, "vote_pass_threshold not provided.")
        weights = list(self.vote_llm.keys())

        # Fully concurrent execution using gather for all operations
        judgments_list = await gather(
            *[
                gather(*[self.evidently_judge(p, **override_kwargs(kw, **kwargs)) for kw in self.vote_llm.values()])
                for p in prompt
            ],
        )
        passes = []
        for judgments in judgments_list:
            if any(j is None for j in judgments):
                logger.warn("Some judgments failed, assuming judgment is False.")
                passes.append(False)
                continue
            passes.append(self.resolve_pass(weights, judgments, vote_pass_threshold))  # pyright: ignore [reportArgumentType]

        return passes[0] if was_str else passes

    @staticmethod
    def resolve_pass(
        weights: list[float],
        judgments: list[JudgeMent],
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


class VisuallyJudge(EvidentlyJudge, ABC):
    """A class that judges a rendered image against an issue via a vision-capable LLM."""

    async def visually_judge(
        self,
        image: str | Path,
        *,
        issue_to_judge: str,
        send_to: str | None = VISION,
        **kwargs: Unpack[ValidateKwargs[ImageVerdict]],
    ) -> ImageVerdict | None:
        """Judge the attached image on glitch-freeness and coherence with *issue_to_judge*.

        Args:
            image: Path of the PNG (or any image the router can MIME-detect) to inspect.
            issue_to_judge: What the image is supposed to show.
            send_to: Routing group for the vision LLM; defaults to the ``VISION`` variant slot so the configured image-understanding model is used.
            **kwargs: Extra LLM knobs forwarded to the proposal call.

        Returns:
            The structured verdict, or ``None`` when the LLM output fails validation.
        """
        image_path = Path(image)
        if not image_path.is_file():
            logger.error(f"Image to judge does not exist: {image_path}")
            return None
        prompt = TEMPLATE_MANAGER.render_template(
            judge_config.image_verdict_template,
            {"issue_to_judge": issue_to_judge},
        )
        verdict = await self.propose(
            ImageVerdict,
            prompt,
            send_to=send_to,
            images=[image_path.read_bytes()],
            **kwargs,
        )
        if not isinstance(verdict, ImageVerdict):
            logger.error(f"Failed to obtain an image verdict for: {issue_to_judge}")
            return None
        return verdict
