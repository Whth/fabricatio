"""Module containing configuration classes for fabricatio-skill."""

from dataclasses import dataclass, field

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class SkillConfig:
    """Configuration for the text-based skill system."""

    distill_skills_template: str = "built-in/distill_skills"
    """Template name for the LLM prompt that distills skill content to its essence."""

    max_selected_skills: int = 8
    """Maximum number of skills the LLM may select in one call (0 = unlimited)."""

    prefilter_threshold: int = 100
    """Pool size above which ``select_skills`` keyword-prefilters the pool with the
    library's ``SkillRegistry.search`` before the LLM stage (0 disables the prefilter)."""

    default_skill_dirs: list[str] = field(default_factory=lambda: ["skills", "extra/skills", "~/.agents/skills"])
    """Default directories scanned on first consult, and the roots used to
    resolve by-name gathering (``gather_skills``/``scan_skills``). ``~`` is
    expanded at use time; the last entry is the user-level agent-skills
    library (``<name>/SKILL.md`` convention)."""


skill_config = CONFIG.load("skill", SkillConfig)

__all__ = ["skill_config"]
