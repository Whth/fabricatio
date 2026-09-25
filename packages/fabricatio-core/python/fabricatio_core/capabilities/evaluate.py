"""Judging, picking, and rating states, through the evaluation route group."""

from abc import ABC
from collections.abc import Mapping, Sequence
from typing import Unpack

from fabricatio_core import rust
from fabricatio_core.models.generic import EvaluationScopedConfig
from fabricatio_core.models.kwargs_types import EvaluationKwargs


class UseEvaluation(EvaluationScopedConfig, ABC):
    """Asks a state's questions of an evaluation model, and answers with the answers themselves.

    The other mixins' judgement and choice are completions shaped by a template; these three go
    through the evaluation router, which asks about a state instead of continuing a conversation.
    That is why they are named for the modality: each carries one question and returns the value
    it produced — a verdict, the candidate that was picked, or what every level weighs — rather
    than a wire shape to pick apart.
    """

    async def evaluate_verdict(
        self,
        state: str,
        field: str,
        *,
        affirm_case: str | None = None,
        deny_case: str | None = None,
        **kwargs: Unpack[EvaluationKwargs],
    ) -> bool:
        """Judges a state against one yes/no question.

        Args:
            state (str): The text to judge.
            field (str): The yes/no question to judge the state against.
            affirm_case (str | None): What a yes means, when that needs saying.
            deny_case (str | None): What a no means, when that needs saying.
            **kwargs (Unpack[EvaluationKwargs]): The router group to evaluate with, and the cache
                knobs of the call.

        Returns:
            bool: The verdict.
        """
        kw = self._resolve_evaluation_params(**kwargs)
        return await rust.ROUTER.evaluate_verdict(
            state=state,
            field=field,
            affirm_case=affirm_case,
            deny_case=deny_case,
            **kw,
        )

    async def evaluate_choice(
        self,
        state: str,
        field: str,
        candidates: Mapping[str, str | None],
        **kwargs: Unpack[EvaluationKwargs],
    ) -> str:
        """Picks one of `candidates` for a state.

        Args:
            state (str): The text to pick for.
            field (str): What the model should decide.
            candidates (Mapping[str, str | None]): Every option, mapped to the rubric that
                describes when it applies, or `None` when the name speaks for itself.
            **kwargs (Unpack[EvaluationKwargs]): The router group to evaluate with, and the cache
                knobs of the call.

        Returns:
            str: The candidate the model picked.
        """
        kw = self._resolve_evaluation_params(**kwargs)
        return await rust.ROUTER.evaluate_choice(
            state=state,
            field=field,
            candidates=dict(candidates),
            **kw,
        )

    async def evaluate_rating(
        self,
        state: str,
        field: str,
        criteria: Sequence[str],
        **kwargs: Unpack[EvaluationKwargs],
    ) -> dict[str, float]:
        """Rates a state over an ordered set of levels.

        Args:
            state (str): The text to rate.
            field (str): What the model should rate.
            criteria (Sequence[str]): The levels, lowest first, between two and ten of them.
            **kwargs (Unpack[EvaluationKwargs]): The router group to evaluate with, and the cache
                knobs of the call.

        Returns:
            dict[str, float]: Every level, mapped to the probability the model gave it.
        """
        kw = self._resolve_evaluation_params(**kwargs)
        return await rust.ROUTER.evaluate_rating(
            state=state,
            field=field,
            criteria=list(criteria),
            **kw,
        )
