"""This module contains the types for the keyword arguments of the methods in the models module."""

from fabricatio_capabilities.models.kwargs_types import ReferencedKwargs
from fabricatio_improve.models.improve import Improvement

from fabricatio_rule.models.rule import RuleSet


class CheckKwargs(ReferencedKwargs[Improvement], total=False):
    """Arguments for content checking operations.

    Extends GenerateKwargs with parameters for checking content against
    specific criteria and templates.
    """

    ruleset: RuleSet
