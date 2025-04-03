"""A module containing classes related to rule sets and rules.

This module provides the `Rule` and `RuleSet` classes, which are used to define and manage
individual rules and collections of rules, respectively. These classes are designed to
facilitate the creation, organization, and application of rules in various contexts,
ensuring clarity, consistency, and enforceability. The module supports detailed
descriptions, examples, and metadata for each rule and rule set, making it suitable for
complex rule management systems.
"""

from typing import List, Self, Tuple, Unpack

from fabricatio.models.generic import Language, PersistentAble, SketchedAble, WithBriefing
from more_itertools import flatten


class Rule(WithBriefing, Language, SketchedAble, PersistentAble):
    """Represents a rule or guideline for a specific topic."""

    violation_examples: List[str]
    """A list of concrete examples demonstrating violations of this rule. Each example should
    be a clear scenario or case that illustrates how the rule can be broken, including the
    context, actions, and consequences of the violation. These examples should help in
    understanding the boundaries of the rule."""

    compliance_examples: List[str]
    """A list of concrete examples demonstrating proper compliance with this rule. Each example
    should be a clear scenario or case that illustrates how to correctly follow the rule,
    including the context, actions, and positive outcomes of compliance. These examples should
    serve as practical guidance for implementing the rule correctly."""


class RuleSet(SketchedAble, PersistentAble, WithBriefing, Language):
    """Represents a collection of rules and guidelines for a particular topic."""

    rules: List[Rule]
    """The collection of rules and guidelines contained in this rule set. Each rule should be
    a well-defined, specific guideline that contributes to the overall purpose of the rule set.
    The rules should be logically organized and consistent with each other, forming a coherent
    framework for the topic or domain covered by the rule set."""

    @classmethod
    def gather(cls, *rulesets: Unpack[Tuple["RuleSet",...]]) -> Self:
        """Gathers multiple rule sets into a single rule set."""
        if not rulesets:
            raise ValueError("No rulesets provided")
        return cls(
            language=rulesets[0].language,
            name=";".join(ruleset.name for ruleset in rulesets),
            description=";".join(ruleset.description for ruleset in rulesets),
            rules=list(flatten(r.rules for r in rulesets)),
        )
