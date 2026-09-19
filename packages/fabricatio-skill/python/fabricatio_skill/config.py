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

    extra_skill_dirs: list[str] = field(default_factory=list)
    """Additional skill directories to load besides the cross-client Agent Skills roots.

    The library always loads the standard cross-client locations — the
    project-local ``.agents/skills`` and the user-level ``~/.agents/skills``,
    fixed on the Rust side
    (https://agentskills.io/client-implementation/adding-skills-support) — then
    these, so a skill in a standard location wins over the same name here.
    Client-specific locations (``.claude/skills``, a bundled ``skills/`` dir,
    ...) are deliberately not part of the standard: list them here to search
    them process-wide, or pass ``dirs=`` to ``gather_skills`` / ``scan_skills``
    for a single call. ``~`` is expanded at use time, and only markdown files
    are ever read, so other files dropped in these dirs are ignored."""


skill_config = CONFIG.load("skill", SkillConfig)

__all__ = ["skill_config"]
