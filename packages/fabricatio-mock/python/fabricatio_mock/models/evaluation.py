"""Evaluation responses for the dummy evaluator, in the shape the wire carries them.

A dummy evaluation deployment answers whatever kind of question the router asks, so a test seeds
it with whole responses: one factory per question kind builds the response that kind produces.
"""

from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field

ANSWER_ID: str = "answer"
"""The id a dummy files its one answer under; a single-question evaluation reads it without one."""

DEFAULT_MODEL: str = "dummy/evaluator"
"""The model a dummy response reports as its author."""


class NoulAnswer(BaseModel):
    """The answer to a yes/no question: the probability of yes."""

    type: Literal["noul"] = "noul"
    """The discriminator the API tags this answer with."""

    noul: float
    """The probability of yes."""


class ChoiceAnswer(BaseModel):
    """The answer to a pick-one question."""

    type: Literal["choice"] = "choice"
    """The discriminator the API tags this answer with."""

    choice: str
    """The highest-probability option."""

    probabilities: dict[str, float]
    """Every option, mapped to its probability."""

    confidence: float
    """How certain the model is, derived from the probabilities."""


class ScoreAnswer(BaseModel):
    """The answer to a rating question."""

    type: Literal["score"] = "score"
    """The discriminator the API tags this answer with."""

    score: float
    """The probability-weighted rating across the levels."""

    legend: dict[str, str]
    """Each level number, mapped back to the level description from the question."""

    probabilities: dict[str, float]
    """Each level, mapped to its probability."""

    confidence: float
    """How certain the model is, derived from the probabilities."""


type Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]
"""Any answer a dummy hands back, tagged by its ``type``."""


class EvaluationUsage(BaseModel):
    """What an evaluation cost, in tokens."""

    input_tokens: int = 0
    """The tokens the state, the question, and the instructions took."""

    output_tokens: int = 0
    """The tokens the answer took."""


class EvaluationResponse(BaseModel):
    """One whole evaluation response, as the dummy hands it back."""

    model: str = DEFAULT_MODEL
    """The model that answered."""

    answers: dict[str, Answer]
    """The answers, keyed by the id of the question that produced them."""

    usage: EvaluationUsage = EvaluationUsage()
    """What the evaluation cost."""

    @classmethod
    def judged(cls, probability: float) -> Self:
        """The response a yes/no question gets: the probability of yes.

        Args:
            probability (float): The probability of yes, from 0 to 1.

        Returns:
            EvaluationResponse: The whole response, as the router reads it back.
        """
        return cls(answers={ANSWER_ID: NoulAnswer(noul=probability)})

    @classmethod
    def picked(cls, choice: str, *, probabilities: Mapping[str, float] | None = None) -> Self:
        """The response a pick-one question gets: the option chosen, and the field it was picked from.

        Args:
            choice (str): The option the model picked.
            probabilities (Mapping[str, float] | None): Every option, mapped to its probability;
                by default the picked option takes all of it.

        Returns:
            EvaluationResponse: The whole response, as the router reads it back.
        """
        distribution = dict(probabilities) if probabilities is not None else {choice: 1.0}
        return cls(
            answers={
                ANSWER_ID: ChoiceAnswer(
                    choice=choice,
                    probabilities=distribution,
                    confidence=cls._confidence(distribution),
                )
            }
        )

    @classmethod
    def rated(cls, probabilities: Mapping[str, float]) -> Self:
        """The response a rating question gets: what each level weighs.

        Args:
            probabilities (Mapping[str, float]): Every level, mapped to its probability, lowest
                level first — the order the question's criteria were given in.

        Returns:
            EvaluationResponse: The whole response, as the router reads it back.
        """
        levels = list(probabilities)
        weights = {str(index): probabilities[level] for index, level in enumerate(levels)}
        return cls(
            answers={
                ANSWER_ID: ScoreAnswer(
                    score=sum(index * weight for index, weight in enumerate(probabilities.values())),
                    legend={str(index): level for index, level in enumerate(levels)},
                    probabilities=weights,
                    confidence=cls._confidence(weights),
                )
            }
        )

    @staticmethod
    def _confidence(probabilities: Mapping[str, float]) -> float:
        """How far the likeliest option stands out: zero when every option weighs the same."""
        return max(probabilities.values()) - 1 / len(probabilities) if probabilities else 0.0
