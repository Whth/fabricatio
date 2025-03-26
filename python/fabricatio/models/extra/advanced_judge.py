"""Module containing the JudgeMent class for holding judgment results."""

from typing import List

from fabricatio.models.generic import ProposedAble


class JudgeMent(ProposedAble):
    """Represents a judgment result containing supporting/denying evidence and final verdict.

    The class stores both affirmative and denies evidence lists along with the final boolean judgment.
    """

    affirm_evidence: List[str]
    """List of evidence supporting the affirmation."""

    deny_evidence: List[str]
    """List of evidence supporting the denial."""

    final_judgement: bool
    """The final judgment made according to all extracted evidence."""

    def __bool__(self) -> bool:
        """Return the final judgment value.

        Returns:
            bool: The stored final_judgement value indicating the judgment result.
        """
        return self.final_judgement
