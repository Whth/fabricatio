"""Module containing the process-wide skill library instance."""

from fabricatio_core.decorators import once

from fabricatio_skill.config import skill_config
from fabricatio_skill.rust import SkillRegistry


@once
def get_skill_registry() -> SkillRegistry:
    """The process-wide skill library, created loaded.

    Loads the cross-client skill roots the Agent Skills standard defines — the
    project-local ``.agents/skills`` and the user-level ``~/.agents/skills``,
    both fixed on the Rust side — plus ``skill_config.extra_skill_dirs``, once
    per process; roots that do not exist are skipped. Every caller shares this
    handle and the skills in it.
    """
    registry = SkillRegistry()
    registry.load_skill_dirs(skill_config.extra_skill_dirs)
    return registry


__all__ = ["get_skill_registry"]
