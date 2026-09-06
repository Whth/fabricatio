"""Module containing configuration classes for fabricatio-judge."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class JudgeConfig:
    """Configuration for fabricatio-judge."""

    image_verdict_template: str = "built-in/image_verdict"
    """Template used by :meth:`VisuallyJudge.visually_judge` to render the image-verdict prompt."""


judge_config = CONFIG.load("judge", JudgeConfig)

__all__ = ["judge_config"]
