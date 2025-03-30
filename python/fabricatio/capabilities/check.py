"""A class that provides the capability to check strings and objects against rules and guidelines."""

from typing import Optional, Unpack

from fabricatio import TEMPLATE_MANAGER
from fabricatio.capabilities.advanced_judge import AdvancedJudge
from fabricatio.capabilities.propose import Propose
from fabricatio.config import configs
from fabricatio.models.extra.patches import BriefingPatch
from fabricatio.models.extra.problem import Improvement
from fabricatio.models.extra.rule import Rule, RuleSet
from fabricatio.models.generic import Display, WithBriefing
from fabricatio.models.kwargs_types import ValidateKwargs
from fabricatio.utils import override_kwargs


class Check(AdvancedJudge, Propose):
    """Class that provides the capability to validate strings/objects against predefined rules and guidelines."""

    async def draft_ruleset(
        self, ruleset_requirement: str, rule_count: int = 0, **kwargs: Unpack[ValidateKwargs[Rule]]
    ) -> Optional[RuleSet]:
        """Generate a rule set based on specified requirements.

        Args:
            ruleset_requirement (str): Description of desired rule set characteristics
            rule_count (int): Number of rules to generate
            **kwargs: Validation configuration parameters

        Returns:
            Optional[RuleSet]: Generated rule set if successful
        """
        rule_reqs = await self.alist_str(
            TEMPLATE_MANAGER.render_template(
                configs.templates.ruleset_requirement_breakdown_template, {"ruleset_requirement": ruleset_requirement}
            ),
            rule_count,
            **override_kwargs(kwargs, default=None),
        )

        if rule_reqs is None:
            return None

        rules = await self.propose(Rule, rule_reqs, **kwargs)
        if any(r for r in rules if r is None):
            return None

        ruleset_patch = await self.propose(
            BriefingPatch,
            f"# Rules Requirements\n{rule_reqs}\n# Generated Rules\n{Display.seq_display(rules)}\n\n"
            f"You need to write a concise and detailed patch for this ruleset that can be applied to the ruleset nicely",
            **override_kwargs(kwargs, default=None),
        )

        if ruleset_patch is None:
            return None

        return ruleset_patch.apply(RuleSet(rules=rules, name="", description=""))

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
