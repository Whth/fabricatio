"""Module containing configuration classes for fabricatio-question."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class QuestionConfig:
    """Configuration for fabricatio-question."""

    selection_template: str = "selection"
    """Template name for selection question"""


question_config = CONFIG.load("question", QuestionConfig)
__all__ = ["question_config"]
