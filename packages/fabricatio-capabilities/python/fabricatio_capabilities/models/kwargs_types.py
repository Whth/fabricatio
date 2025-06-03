"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Dict, List

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


class ReferencedKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations."""

    reference: str
