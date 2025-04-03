"""A module containing the DraftRuleSet action."""

from typing import List, Optional

from fabricatio.capabilities.check import Check
from fabricatio.journal import logger
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
        ruleset_requirement: Optional[str] = None,
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
        ruleset = await self.draft_ruleset(
            ruleset_requirement=ok(ruleset_requirement or self.ruleset_requirement, "No ruleset requirement provided"),
            rule_count=self.rule_count,
        )
        if ruleset:
            logger.info(f"Drafted Ruleset length: {len(ruleset.rules)}\n{ruleset.display()}")
        else:
            logger.warning(f"Drafting Rule Failed for:\n{ruleset_requirement}")
        return ruleset


class GatherRuleset(Action):
    """Action to gather a ruleset from a given requirement description."""

    output_key: str = "gathered_ruleset"
    """The key used to store the drafted ruleset in the context dictionary."""

    to_gather: List[str]
    """the cxt name of RuleSet to gather"""

    async def _execute(self, **cxt) -> RuleSet:
        logger.info(f"Gathering Ruleset from {self.to_gather}")
        # Fix for not_found
        not_found = next((t for t in self.to_gather if t not in cxt), None)
        if not_found:
            raise ValueError(
                f"Not all required keys found in context: {self.to_gather}|`{not_found}` not found in context."
            )

        # Fix for invalid RuleSet check
        invalid = next((t for t in self.to_gather if not isinstance(cxt[t], RuleSet)), None)
        if invalid is not None:
            raise TypeError(f"Invalid RuleSet instance for key `{invalid}`")

        return RuleSet.gather(*[cxt[t] for t in self.to_gather])
