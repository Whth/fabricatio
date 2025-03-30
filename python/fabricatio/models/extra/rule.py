"""A module containing classes related to rule sets and rules."""

from typing import List

from fabricatio.models.generic import Display, PersistentAble, ProposedAble, WithBriefing


class Rule(WithBriefing,ProposedAble,Display):
    """Represents a rule or guideline for a specific topic."""

    violation_examples: List[str]
    """Examples of violations of the rule."""
    compliance_examples: List[str]
    """Examples of how to comply with the rule."""


class RuleSet(ProposedAble, Display, PersistentAble, WithBriefing):
    """Represents a collection of rules and guidelines for a particular topic."""

    rules: List[Rule]
    """The rules and guidelines contained in the rule set."""
