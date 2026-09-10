"""Judgment models: the ``JudgeMent`` evidence record and the ``Verdict`` contract refine loops consume."""

from abc import ABC, abstractmethod

from fabricatio_core.models.generic import SketchedAble
from pydantic import Field


class Verdict(ABC):
    """Nominal contract of any verdict a refine loop can consume.

    A verdict is accepted through two properties: whether the artifact
    :attr:`passed` inspection as-is, and the actionable ``feedback`` to
    feed a re-generation when it did not. Verdict models mix this in
    (:class:`ImageVerdict` does) so the loop types against a nominal
    base instead of a structural stand-in.
    """

    @property
    @abstractmethod
    def passed(self) -> bool:
        """Whether the inspected artifact is accepted."""
        ...

    @property
    @abstractmethod
    def feedback(self) -> str:
        """Re-generation instruction built from the recorded defects; empty when passed."""
        ...


class JudgeMent(SketchedAble):
    """Represents a judgment result containing supporting/denying evidence and final verdict.

    The class stores both affirmative and denies evidence, truth and reasons lists along with the final boolean judgment.
    """

    issue_to_judge: str
    """The issue to be judged, including the original question and context"""

    deny_evidence: list[str]
    """List of clues supporting the denial."""

    affirm_evidence: list[str]
    """List of clues supporting the affirmation."""

    final_judgement: bool
    """The final judgment made according to all extracted clues. true for the `issue_to_judge` is correct and false for incorrect."""

    def __bool__(self) -> bool:
        """Return the final judgment value.

        Returns:
            bool: The stored final_judgement value indicating the judgment result.
        """
        return self.final_judgement


class ImageVerdict(JudgeMent, Verdict):
    """Judgment over a rendered image: glitch-freeness, coherence with the request, and actionable feedback.

    Extends :class:`JudgeMent` with structured reason lists and mixes in the
    :class:`Verdict` contract, so a failed verdict converts directly into a
    re-generation instruction — the feedback loop needs no extra LLM call to
    know what to fix.
    """

    glitch_reasons: list[str] = Field(default_factory=list)
    """Technical defects seen in the image (artifacts, broken anatomy, garbled text); empty when clean."""

    coherence_reasons: list[str] = Field(default_factory=list)
    """Ways the image drifts from the requested subject or composition; empty when on-brief."""

    @property
    def passed(self) -> bool:
        """Whether the verdict accepts the artifact as-is."""
        return self.final_judgement

    @property
    def feedback(self) -> str:
        """Re-prompt instruction built from every recorded reason; empty string when the verdict passes."""
        if self.final_judgement:
            return ""
        return "; ".join([*self.glitch_reasons, *self.coherence_reasons])
