"""This module contains the types for the keyword arguments of the methods in the models module."""

from fabricatio_capabilities.models.generic import SketchedAble
from fabricatio_core.models.kwargs_types import ReferencedKwargs
from fabricatio_improve.models.improve import Improvement


class CorrectKwargs[T: SketchedAble](ReferencedKwargs[T], total=False):
    """Arguments for content correction operations.

    Extends GenerateKwargs with parameters for correcting content based on
    specific criteria and templates.
    """

    improvement: Improvement
