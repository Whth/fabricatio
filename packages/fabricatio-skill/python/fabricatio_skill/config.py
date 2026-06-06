"""Module containing configuration classes for fabricatio-skill."""

from dataclasses import dataclass, field
from typing import List

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class SkillConfig:
    """Configuration for the text-based skill system."""

    select_skills_template: str = "built-in/select_skills"
    """Template name for the LLM prompt that selects relevant skills from a question."""

    distill_skills_template: str = "built-in/distill_skills"
    """Template name for the LLM prompt that distills skill content to its essence."""

    default_skill_dirs: List[str] = field(default_factory=lambda: ["skills", "extra/skills"])
    """Default directories to scan for skill files."""


skill_config = CONFIG.load("skill", SkillConfig)

__all__ = ["skill_config"]
