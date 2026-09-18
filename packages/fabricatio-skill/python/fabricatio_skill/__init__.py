"""Fabricatio-skill: Text-based skill system for LLM agents.

Provides progressive skill resolution — load markdown skill files, select
relevant skills via LLM, distill to essential context, and inject into prompts.
"""

from fabricatio_skill.capabilities.skill import UseSkill, fetch_skills
from fabricatio_skill.models.skill import get_skill_registry
from fabricatio_skill.rust import Skill, SkillMeta, SkillRegistry, fetch_skill, get_skill, scan_skills, search_skills

__all__ = [
    "Skill",
    "SkillMeta",
    "SkillRegistry",
    "UseSkill",
    "fetch_skill",
    "fetch_skills",
    "get_skill",
    "get_skill_registry",
    "scan_skills",
    "search_skills",
]
