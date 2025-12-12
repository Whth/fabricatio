"""Module containing configuration classes for fabricatio-question."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class QuestionConfig:
    """Configuration for fabricatio-question."""

    selection_template: str = "built-in/selection"
    """Template name for selection question"""

    selection_display_template: str = "built-in/selection_display"
    """Template name for selection display."""


question_config = CONFIG.load("question", QuestionConfig)
__all__ = ["question_config"]
