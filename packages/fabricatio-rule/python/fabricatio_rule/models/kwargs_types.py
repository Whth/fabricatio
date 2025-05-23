"""This module contains the types for the keyword arguments of the methods in the models module."""

from fabricatio_capabilities.models.generic import SketchedAble
from fabricatio_capabilities.models.kwargs_types import ReferencedKwargs
from fabricatio_improve.models.improve import Improvement

from fabricatio_rule.models.rule import RuleSet


class CorrectKwargs[T: SketchedAble](ReferencedKwargs[T], total=False):
    """Arguments for content correction operations.

    Extends GenerateKwargs with parameters for correcting content based on
    specific criteria and templates.
    """

    improvement: Improvement


class CheckKwargs(ReferencedKwargs[Improvement], total=False):
    """Arguments for content checking operations.

    Extends GenerateKwargs with parameters for checking content against
    specific criteria and templates.
    """

    ruleset: RuleSet
