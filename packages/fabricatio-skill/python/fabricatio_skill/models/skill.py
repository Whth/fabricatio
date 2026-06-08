"""Singleton accessor for the Rust-backed SkillRegistry."""

from fabricatio_core.decorators import once

from fabricatio_skill.rust import SkillRegistry


@once
def get_skill_registry() -> SkillRegistry:
    """Get the process-wide singleton SkillRegistry."""
    return SkillRegistry()


__all__ = ["get_skill_registry"]
