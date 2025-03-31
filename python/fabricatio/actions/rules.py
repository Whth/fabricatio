"""A module containing the DraftRuleSet action."""

from typing import Optional

from fabricatio.capabilities.check import Check
from fabricatio.models.action import Action
from fabricatio.models.extra.rule import RuleSet
from fabricatio.utils import ok


class DraftRuleSet(Action, Check):
    """Action to draft a ruleset based on a given requirement description."""

    output_key: str = "drafted_ruleset"
    """The key used to store the drafted ruleset in the context dictionary."""

    ruleset_requirement: Optional[str] = None
    """The natural language description of the desired ruleset characteristics."""
    rule_count: int = 0
    """The number of rules to generate in the ruleset (0 for no restriction)."""
    async def _execute(
        self,
        ruleset_requirement: Optional[str]=None,
        **_,
    ) -> Optional[RuleSet]:
        """Draft a ruleset based on the requirement description.

        Args:
            ruleset_requirement (str): Natural language description of desired ruleset characteristics
            rule_count (int): Number of rules to generate (0 for no restriction)
            **kwargs: Validation parameters for rule generation

        Returns:
            Optional[RuleSet]: Drafted ruleset object or None if generation fails
        """
        return await self.draft_ruleset(
            ruleset_requirement=ok(ruleset_requirement or self.ruleset_requirement,"No ruleset requirement provided"),
            rule_count=self.rule_count,
        )
