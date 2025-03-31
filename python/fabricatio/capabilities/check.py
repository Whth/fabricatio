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
    """Class for validating strings/objects against predefined rules and guidelines.

    This capability combines rule-based judgment and proposal generation to provide
    structured validation results with actionable improvement suggestions.
    """

    async def draft_ruleset(
        self, ruleset_requirement: str, rule_count: int = 0, **kwargs: Unpack[ValidateKwargs[Rule]]
    ) -> Optional[RuleSet]:
        """Generate rule set based on requirement description.

        Args:
            ruleset_requirement (str): Natural language description of desired ruleset characteristics
            rule_count (int): Number of rules to generate (0 for default count)
            **kwargs: Validation parameters for rule generation

        Returns:
            Optional[RuleSet]: Validated ruleset object or None if generation fails

        Notes:
            - Requires valid template configuration in configs.templates
            - Returns None if any step in rule generation fails
            - Uses `alist_str` for requirement breakdown and iterative rule proposal
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
            f"You need to write a concise and detailed patch for this ruleset that can be applied to the ruleset nicely.\n"
            f"Note that all fields in this patch will be directly copied to the ruleset obj, including `name` and `description`, so write when knowing the subject.\n",
            **override_kwargs(kwargs, default=None),
        )

        if ruleset_patch is None:
            return None

        return ruleset_patch.apply(RuleSet(rules=rules, name="", description=""))

    async def check_string_against_rule(
        self,
        input_text: str,
        rule: Rule,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Validate text against specific rule.

        Args:
            input_text (str): Text content to validate
            rule (Rule): Rule instance for validation
            reference (str): Reference text for comparison (default: "")
            **kwargs: Configuration for validation process

        Returns:
            Optional[Improvement]: Suggested improvement if violation detected

        Notes:
            - Uses `evidently_judge` to determine violation presence
            - Renders template using `check_string_template` for proposal
            - Proposes Improvement only when violation is confirmed
        """
        if judge := await self.evidently_judge(
            f"# Content to exam\n{input_text}\n\n# Rule Must to follow\n{rule.display()}\nDoes `Content to exam` provided above violate the `Rule Must to follow` provided above?",
            **override_kwargs(kwargs, default=None),
        ):
            return await self.propose(
                Improvement,
                TEMPLATE_MANAGER.render_template(
                    configs.templates.check_string_template,
                    {"to_check": input_text, "rule": rule, "judge": judge.display(), "reference": reference},
                ),
                **kwargs,
            )
        return None

    async def check_obj_against_rule[M: (Display, WithBriefing)](
        self,
        obj: M,
        rule: Rule,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Validate object against rule using text representation.

        Args:
            obj (M): Object implementing Display/WithBriefing interface
            rule (Rule): Validation rule
            reference (str): Reference text for comparison (default: "")
            **kwargs: Validation configuration parameters

        Returns:
            Optional[Improvement]: Improvement suggestion if issues found

        Notes:
            - Requires obj to implement display() or briefing property
            - Raises TypeError for incompatible object types
            - Converts object to text before string validation
        """
        if isinstance(obj, Display):
            input_text = obj.display()
        elif isinstance(obj, WithBriefing):
            input_text = obj.briefing
        else:
            raise TypeError("obj must be either Display or WithBriefing")

        return await self.check_string_against_rule(input_text, rule, reference, **kwargs)

    async def check_string(
        self,
        input_text: str,
        ruleset: RuleSet,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Validate text against full ruleset.

        Args:
            input_text (str): Text content to validate
            ruleset (RuleSet): Collection of validation rules
            reference (str): Reference text for comparison
            **kwargs: Validation configuration parameters

        Returns:
            Optional[Improvement]: First detected improvement

        Notes:
            - Checks rules sequentially and returns first violation
            - Halts validation after first successful improvement proposal
            - Maintains rule execution order from ruleset.rules list
        """
        imp_seq = [
            await self.check_string_against_rule(input_text, rule, reference, **kwargs) for rule in ruleset.rules
        ]
        if all(isinstance(i, Improvement) for i in imp_seq):
            return Improvement.gather(*imp_seq)  # pyright: ignore [reportArgumentType]
        return None

    async def check_obj[M: (Display, WithBriefing)](
        self,
        obj: M,
        ruleset: RuleSet,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Validate object against full ruleset.

        Args:
            obj (M): Object implementing Display/WithBriefing interface
            ruleset (RuleSet): Collection of validation rules
            reference (str): Reference text for comparison (default: "")
            **kwargs: Validation configuration parameters

        Returns:
            Optional[Improvement]: First detected improvement

        Notes:
            - Uses check_obj_against_rule for individual rule checks
            - Maintains same early termination behavior as check_string
            - Validates object through text conversion mechanism
        """
        imp_seq = [await self.check_obj_against_rule(obj, rule, reference, **kwargs) for rule in ruleset.rules]
        if all(isinstance(i, Improvement) for i in imp_seq):
            return Improvement.gather(*imp_seq)  # pyright: ignore [reportArgumentType]
        return None
