"""A class that provides the capability to check strings and objects against rules and guidelines."""
from typing import Optional, Unpack

from fabricatio import TEMPLATE_MANAGER
from fabricatio.capabilities.advanced_judge import AdvancedJudge
from fabricatio.capabilities.propose import Propose
from fabricatio.config import configs
from fabricatio.models.extra.problem import Improvement
from fabricatio.models.extra.rule import Rule, RuleSet
from fabricatio.models.generic import Display, WithBriefing
from fabricatio.models.kwargs_types import ValidateKwargs
from fabricatio.utils import override_kwargs


class Check(AdvancedJudge, Propose):
    """Class that provides the capability to validate strings/objects against predefined rules and guidelines."""

    async def draft_ruleset(
        self, ruleset_requirement: str, **kwargs: Unpack[ValidateKwargs[RuleSet]]
    ) -> Optional[RuleSet]:
        """Generate a rule set based on specified requirements.

        Args:
            ruleset_requirement (str): Description of desired rule set characteristics
            **kwargs: Validation configuration parameters

        Returns:
            Optional[RuleSet]: Generated rule set if successful
        """
        return await self.propose(RuleSet, ruleset_requirement, **kwargs)

    async def draft_rule(self, rule_requirement: str, **kwargs: Unpack[ValidateKwargs[Rule]]) -> Optional[Rule]:
        """Create a specific rule based on given specifications.

        Args:
            rule_requirement (str): Detailed rule description requirements
            **kwargs: Validation configuration parameters

        Returns:
            Optional[Rule]: Generated rule instance if successful
        """
        return await self.propose(Rule, rule_requirement, **kwargs)

    async def check_string(
        self,
        input_text: str,
        rule: Rule,
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Evaluate text against a specific rule.

        Args:
            input_text (str): Text content to be evaluated
            rule (Rule): Rule instance used for validation
            **kwargs: Validation configuration parameters

        Returns:
            Optional[Improvement]: Suggested improvement if violations found, else None
        """
        if judge := await self.evidently_judge(
            f"# Content to exam\n{input_text}\n\n# Rule Must to follow\n{rule.display()}\nDoes `Content to exam` provided above violate the `Rule Must to follow` provided above?",
            **override_kwargs(kwargs, default=None),
        ):
            return await self.propose(
                Improvement,
                TEMPLATE_MANAGER.render_template(
                    configs.templates.check_string_template,
                    {"to_check": input_text, "rule": rule, "judge": judge.display()},
                ),
                **kwargs,
            )
        return None

    async def check_obj[M: (Display, WithBriefing)](
        self,
        obj: M,
        rule: Rule,
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Validate an object against specified rule.

        Args:
            obj (M): Object implementing Display or WithBriefing interface
            rule (Rule): Validation rule to apply
            **kwargs: Validation configuration parameters

        Returns:
            Optional[Improvement]: Improvement suggestion if issues detected
        """
        if isinstance(obj, Display):
            input_text = obj.display()
        elif isinstance(obj, WithBriefing):
            input_text = obj.briefing
        else:
            raise TypeError("obj must be either Display or WithBriefing")

        return await self.check_string(input_text, rule, **kwargs)
