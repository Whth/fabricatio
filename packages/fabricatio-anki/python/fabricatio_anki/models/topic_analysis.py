"""Module for representing and analyzing a specific topic or question.

This module defines the TopicAnalysis class, which encapsulates an in-depth analysis
of a particular topic or question. It includes attributes such as difficulty coefficient,
relevant subjects, detailed solutions, key points, and brief summaries. Additionally,
it provides functionality to assemble the instance data into a formatted string using
templates.
"""

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import SketchedAble
from pydantic import Field

from fabricatio_anki.config import anki_config


class TopicAnalysis(SketchedAble):
    """A class that represents an in-depth analysis of a specific topic or question."""

    difficulty_coefficient: float = Field(le=1.0, ge=0.0)
    """Difficulty coefficient (0.0-1.0) indicating the expected error rate of students on this question"""

    subjects: list[str]
    """List of subject areas the question belongs to (e.g., ["Math", "Geometry"])"""

    detailed_solution: str
    """Complete solution process of the question, including all steps and logical reasoning"""

    key_points: list[str]
    """List of key knowledge points for solving the question, highlighting critical steps and required knowledge"""

    brief_summary: str
    """Concise summary of the question and solution, explaining the core idea in simple language"""

    def assemble(self) -> str:
        """Assemble the instance into a single string."""
        return TEMPLATE_MANAGER.render_template(anki_config.topic_analysis_assemble_template, self.model_dump())
