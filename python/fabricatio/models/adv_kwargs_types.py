"""A module containing kwargs types for content correction and checking operations."""
from fabricatio.models.extra.problem import Improvement
from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.generic import SketchedAble
from fabricatio.models.kwargs_types import ReferencedKwargs


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
