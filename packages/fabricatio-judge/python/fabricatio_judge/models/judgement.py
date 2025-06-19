"""Module containing the JudgeMent class for holding judgment results."""

from typing import List

from fabricatio_core.models.generic import SketchedAble


class JudgeMent(SketchedAble):
    """Represents a judgment result containing supporting/denying evidence and final verdict.

    The class stores both affirmative and denies evidence, truth and reasons lists along with the final boolean judgment.
    """

    issue_to_judge: str
    """The issue to be judged, including the original question and context"""

    deny_evidence: List[str]
    """List of clues supporting the denial."""

    affirm_evidence: List[str]
    """List of clues supporting the affirmation."""

    final_judgement: bool
    """The final judgment made according to all extracted clues. true for the `issue_to_judge` is correct and false for incorrect."""

    def __bool__(self) -> bool:
        """Return the final judgment value.

        Returns:
            bool: The stored final_judgement value indicating the judgment result.
        """
        return self.final_judgement
