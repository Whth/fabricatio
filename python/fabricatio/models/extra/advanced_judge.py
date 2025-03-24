"""A module containing the JudgeMent class."""

from typing import List

from fabricatio.models.generic import ProposedAble


class JudgeMent(ProposedAble):
    """A class representing a judgment made by a judge."""

    affirm_evidence: List[str]
    """List of evidence supporting the affirmation."""

    deny_evidence: List[str]
    """List of evidence supporting the denial."""

    final_judgement: bool
    """The final judgement."""

    def __bool__(self) -> bool:
        """Return the final judgement."""
        return self.final_judgement
