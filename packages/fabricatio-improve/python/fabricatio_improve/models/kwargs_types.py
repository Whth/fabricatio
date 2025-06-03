"""This module contains the types for the keyword arguments of the methods in the models module."""

from typing import Dict, Required

from fabricatio_capabilities.models.kwargs_types import ReferencedKwargs
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_improve.models.improve import Improvement


class CorrectKwargs[T: SketchedAble](ReferencedKwargs[T], total=False):
    """Arguments for content correction operations.

    Extends GenerateKwargs with parameters for correcting content based on
    specific criteria and templates.
    """

    improvement: Improvement


class ReviewInnerKwargs[T](ValidateKwargs[T], total=False):
    """Arguments for content review operations."""

    criteria: set[str]


class ReviewKwargs[T](ReviewInnerKwargs[T], total=False):
    """Arguments for content review operations.

    Extends GenerateKwargs with parameters for evaluating content against
    specific topics and review criteria.
    """

    rating_manual: Dict[str, str]
    topic: Required[str]
