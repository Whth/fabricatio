"""Shared helpers for fabricatio-capabilities."""

from fabricatio_core.models.generic import ProposedAble
from pydantic import Field, create_model

__all__ = ["build_rating_model"]


def build_rating_model(rating_manual: dict[str, str], min_score: float, max_score: float) -> type[ProposedAble]:
    """Build a rating result model: one bounded float field per criterion.

    Each field is clamped to ``[min_score, max_score]`` and carries the criterion's
    manual entry as its description plus ten evenly-spaced example scores, steering
    the LLM toward calibrated values.
    """
    tip = (max_score - min_score) / 9
    return create_model(  # pyright: ignore [reportCallIssue]
        "RatingResult",
        __base__=ProposedAble,
        __doc__=f"The rating result contains the scores against each criterion, with min_score={min_score} and max_score={max_score}.",
        **{  # pyright: ignore [reportArgumentType]
            criterion: (
                float,
                Field(
                    ge=min_score,
                    le=max_score,
                    description=desc,
                    examples=[round(min_score + tip * i, 2) for i in range(10)],
                ),
            )
            for criterion, desc in rating_manual.items()
        },
    )
