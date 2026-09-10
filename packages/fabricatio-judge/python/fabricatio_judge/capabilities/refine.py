"""The bounded generate-judge-revise loop shared by judged re-generation features."""

from abc import ABC
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.models.kwargs_types import LLMKwargs

from fabricatio_judge.models.refine import Attempt, AttemptHistory, RefinePlan

__all__ = ["RefineLoop"]


class RefineLoop(Propose, ABC):
    """Re-generate an artifact until a judge accepts it, or the try budget runs out.

    The loop owns the invariants so consumers cannot get them wrong:
    ``max_tries`` counts TOTAL generation attempts, the last attempt is
    kept unjudged (no retry budget remains), a judge answering ``None``
    degrades open (the artifact is kept), a failing generation raises out
    of the loop (the consumer degrades at its own boundary), and every
    rejection accumulates into the revision requirement so the next
    proposal sees all prior defects. The varying parts — how to generate,
    judge, and describe an artifact — arrive as a
    :class:`~fabricatio_judge.models.refine.RefinePlan`.
    """

    async def refine_until_accepted[M: ProposedAble, R](
        self,
        cls: type[M],
        requirement: str,
        spec: M,
        plan: RefinePlan[M, R],
        *,
        max_tries: int,
        feedback_template: str,
        send_to: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> R:
        """Generate ``spec`` once, then revise and re-generate while the judge rejects.

        Args:
            cls: Model class re-proposed from the requirement plus the accumulated feedback tail.
            requirement: Base requirement the feedback tail is appended to.
            spec: The initially proposed spec; never re-proposed, only revised.
            plan: Generate/judge/request seams owned by the consumer.
            max_tries: Total generation attempts; the last is kept unjudged, and 1 renders exactly once without
                judging — the gate-off shape. Clamped to at least 1.
            feedback_template: Template rendering the rejected-attempt history into the revision tail.
            send_to: Routing override forwarded to every revision proposal.
            **kwargs: Additional LLM kwargs forwarded to every revision proposal.

        Returns:
            The last generated artifact.
        """
        budget = max(1, max_tries)
        history = AttemptHistory()
        for attempt in range(1, budget + 1):
            result = await plan.generate(spec)
            if attempt == budget:
                break  # last try kept unjudged: no retry budget remains
            verdict = await plan.judge(result)
            if verdict is None:
                logger.warn(f"Judge unavailable for {plan.label}; keeping the generated artifact")
                return result
            if verdict.passed:
                logger.info(f"{plan.label} passed inspection on attempt {attempt}")
                return result
            plan.reject(result, attempt)
            history = history.with_attempt(Attempt(plan.request_of(result), verdict.feedback))
            logger.info(f"{plan.label} rejected on attempt {attempt} ({verdict.feedback}); revising")
            revised = await self.propose(
                cls, f"{requirement}\n\n{history.tail(feedback_template)}", send_to=send_to, **kwargs
            )
            if revised is None:
                logger.warn(f"Revision proposal failed for {plan.label}; keeping the generated artifact")
                return result
            spec = revised
        return result
