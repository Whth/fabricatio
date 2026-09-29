"""Ruleset-driven repair of composed subsections: fix what the article's own checks reject."""

from abc import ABC
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import RuleSet

from fabricatio_typst.models.article_main import ArticleSubsection
from fabricatio_typst.models.context.subsection import SubsectionContext


class CensoredSubsectionRepair[CTX: SubsectionContext](Censor, ABC):
    """Repairs a subsection the article's own checks reject, against a ruleset.

    The repair is opt-in: a run with no configured ruleset composes plain prose and this
    hook passes every subsection through unchanged.
    """

    ruleset: RuleSet | None = None
    """The ruleset the repair pass checks and corrects a rejected subsection against."""

    async def post_process_subsection(
        self,
        ctx: CTX,
        subsection: ArticleSubsection,
        **kwargs: Unpack[LLMKwargs],
    ) -> ArticleSubsection:
        """Repair the subsection in place when its own checks reject it.

        The reference handed to the censor is the running text plus the exact error the
        checks reported, so the correction is asked to keep the subsection inside the
        article it belongs to.
        """
        if self.ruleset is None:
            logger.debug(f"No ruleset configured; skipping the repair pass for subsection '{subsection.title}'")
            return subsection
        err = subsection.introspect()
        if not err:
            return subsection
        logger.warn(f"Repairing subsection '{subsection.title}':\n{err}")
        await self.censor_obj_inplace(
            subsection,
            ruleset=self.ruleset,
            reference=(
                f"{ctx.prefix_log.render()}\n# Error Need to be fixed\n{err}\n"
                f"You should use `{subsection.language}` to write the new `{subsection.__class__.__name__}`."
            ),
        )
        return subsection


__all__ = ["CensoredSubsectionRepair"]
