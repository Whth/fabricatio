"""Models of the judged refine loop: rejected-attempt records and the loop's seams.

:class:`~fabricatio_judge.capabilities.refine.RefineLoop` owns the loop
invariants; everything that varies per consumer — how to generate an
artifact, how to judge it, and how to describe its request — arrives as a
:class:`RefinePlan` built from the models below.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fabricatio_core import TEMPLATE_MANAGER

from fabricatio_judge.models.judgement import Verdict

__all__ = ["Attempt", "AttemptHistory", "RefinePlan"]


@dataclass(frozen=True)
class Attempt:
    """One rejected generation attempt: its final request prose and the judge's defect list."""

    prompt: str
    """The generation request that produced the rejected artifact."""

    feedback: str
    """The judge's joined defect list; drives the next revision."""


@dataclass(frozen=True)
class AttemptHistory:
    """Cumulative record of rejected attempts, rendered into the revision requirement tail."""

    attempts: tuple[Attempt, ...] = ()
    """Rejected attempts in rejection order."""

    def with_attempt(self, attempt: Attempt) -> "AttemptHistory":
        """Return a new history carrying ``attempt`` appended."""
        return AttemptHistory((*self.attempts, attempt))

    def tail(self, template: str) -> str:
        """Render the accumulated feedback through ``template``; empty when no attempt was recorded.

        Args:
            template: Template receiving ``{"history": [{"prompt": ..., "feedback": ...}, ...]}``.

        Returns:
            The rendered feedback block, or an empty string before any rejection.
        """
        return TEMPLATE_MANAGER.render_template(
            template,
            {"history": [{"prompt": a.prompt, "feedback": a.feedback} for a in self.attempts]},
        )


@dataclass(frozen=True)
class RefinePlan[M, R]:
    """The consumer-owned seams of one refine loop.

    The loop calls :attr:`generate` for a spec, hands the artifact to
    :attr:`judge`, records :attr:`request_of` prose into the feedback
    history, and fires :attr:`on_reject` with the rejected artifact and its
    1-based attempt number before revising.
    """

    generate: Callable[[M], Awaitable[R]]
    """Produces the artifact from a spec; a failure must raise — the exception propagates out of the loop."""

    judge: Callable[[R], Awaitable[Verdict | None]]
    """Inspects an artifact; ``None`` means the judge is unavailable and the artifact is kept."""

    request_of: Callable[[R], str]
    """Extracts the generation-request prose recorded into the feedback history."""

    on_reject: Callable[[R, int], None] | None = None
    """Optional archive hook fired with the rejected artifact and its 1-based attempt number."""

    label: str = ""
    """Human-readable unit name used in loop logging."""

    def reject(self, artifact: R, attempt: int) -> None:
        """Fire the archive hook when the consumer supplied one; absence is a no-op."""
        if self.on_reject is not None:
            self.on_reject(artifact, attempt)
