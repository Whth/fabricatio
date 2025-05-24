"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Dict, List, Required

from fabricatio_core.models.kwargs_types import ValidateKwargs


class CompositeScoreKwargs(ValidateKwargs[List[Dict[str, float]]], total=False):
    """Arguments for composite score generation operations.

    Extends GenerateKwargs with parameters for generating composite scores
    based on specific criteria and weights.
    """

    topic: str
    criteria: set[str]
    weights: Dict[str, float]
    manual: Dict[str, str]


class BestKwargs(CompositeScoreKwargs, total=False):
    """Arguments for choose top-k operations."""

    k: int


class ReviewInnerKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations."""

    criteria: set[str]


# noinspection PyTypedDict
class ReviewKwargs[T](ReviewInnerKwargs[T], total=False):
    """Arguments for content review operations.

    Extends GenerateKwargs with parameters for evaluating content against
    specific topics and review criteria.
    """

    rating_manual: Dict[str, str]
    topic: Required[str]


class ReferencedKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations."""

    reference: str

# noinspection PyTypedDict
