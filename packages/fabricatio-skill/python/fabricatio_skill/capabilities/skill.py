"""Module containing the UseSkill capability for progressive skill resolution."""

from abc import ABC
from typing import Self, Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from pydantic import Field

from fabricatio_skill.config import skill_config
from fabricatio_skill.models.skill import get_skill_registry
from fabricatio_skill.rust import Skill, get_skill


class UseSkill(UseLLM, ABC):
    """Mixin that provides progressive skill consultation.

    Skills are text-based instruction files (markdown) that provide context
    to LLM agents.  Skill objects live in the global ``SkillRegistry``;
    this class stores only their **names** as lightweight handles.

    Pipeline levels:

    Level 1 (Rust):   scan / search / get — file discovery + keyword matching
    Level 2 (Python): select / distill — LLM-powered relevance + extraction
    Level 3 (Python): consult_skills — full progressive pipeline (select → distill),
                      returning the consulted knowledge; answering is the caller's job.
    """

    skill_names: list[str] = Field(default_factory=list)
    """Names of loaded skills available for this role/action (resolved via registry)."""

    # ── helpers ───────────────────────────────────────────────────────

    def _resolve_skills(self, names: list[str] | None = None) -> list[Skill]:
        """Return Skill objects from the registry.

        Args:
            names: Specific names to resolve. ``None`` → ``self.skill_names``.
        """
        target = names if names is not None else self.skill_names
        return get_skill_registry().get_many(target)

    @property
    def skills(self) -> list[Skill]:
        """Convenience: resolve current skill_names to live Skill objects."""
        return self._resolve_skills()

    # ── Level 1: Register ─────────────────────────────────────────────

    def add_skills(self, skills: list[Skill], names: list[str] | None = None) -> Self:
        """Register skills in the global registry and track their names here.

        Args:
            skills: Skill objects to register.
            names: If given, only register skills whose name is in this list.

        Returns:
            Self for method chaining.
        """
        selected = [s for s in skills if s.name in names] if names else list(skills)
        get_skill_registry().register(selected)
        new_names = [s.name for s in selected if s.name not in self.skill_names]
        self.skill_names.extend(new_names)
        logger.info(f"Registered {len(new_names)} skill(s): {new_names}")
        return self

    # ── Level 2: Select ──────────────────────────────────────────────

    async def select_skills(
        self,
        question: str,
        available: list[str] | None = None,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[Skill]:
        """Use LLM to select skills relevant to a question.

        Args:
            send_to (str | None): Routing-group variant for the LLM call. Resolved against
                    the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                    ``TASK``.
            question: The question/task to match skills against.
            available: Skill name pool to select from. Defaults to self.skill_names.
            **kwargs: LLM parameters.

        Returns:
            Skills deemed relevant by the LLM, in relevance order.
        """
        pool_names = available if available is not None else self.skill_names
        pool = get_skill_registry().get_many(pool_names)
        if not pool:
            logger.warn("No skills available for selection.")
            return []

        skill_summaries = "\n".join(f"- **{s.name}**: {s.description} [tags: {', '.join(s.tags)}]" for s in pool)
        prompt = TEMPLATE_MANAGER.render_template(
            skill_config.select_skills_template,
            {"question": question, "skills": skill_summaries},
        )

        response = await self.aask(prompt, send_to=send_to, **kwargs)
        names = [n.strip().strip("*").strip('"').strip("'") for n in response.split(",") if n.strip()]

        matched = []
        for name in names:
            skill = get_skill(name, pool)
            if skill is not None:
                matched.append(skill)
            else:
                logger.warn(f"LLM selected unknown skill: '{name}'")

        logger.info(f"Selected {len(matched)} skill(s): {[s.name for s in matched]}")
        return matched

    # ── Level 2: Distill ─────────────────────────────────────────────

    async def distill_skills(
        self,
        question: str,
        skills: list[Skill],
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Use LLM to extract the essential parts of skills relevant to a question.

        Args:
            send_to (str | None): Routing-group variant for the LLM call. Resolved against
                    the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                    ``TASK``.
            question: The question/task to focus distillation on.
            skills: Skills to distill.
            **kwargs: LLM parameters.

        Returns:
            Condensed skill text relevant to the question.
        """
        if not skills:
            return ""

        skill_blocks = "\n\n".join(f"--- skill: {s.name} ---\n{s.content}" for s in skills)
        prompt = TEMPLATE_MANAGER.render_template(
            skill_config.distill_skills_template,
            {"question": question, "skills": skill_blocks},
        )

        result = await self.aask(prompt, send_to=send_to, **kwargs)
        logger.info(f"Distilled {len(skills)} skill(s) into {len(result)} chars.")
        return result

    # ── Level 3: Full pipeline ───────────────────────────────────────

    async def consult_skills(
        self,
        question: str,
        *,
        names: list[str] | None = None,
        select: bool = True,
        distill: bool = True,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Consult the skill library about a question.

        Progressively resolves relevant skills and returns what they say —
        distilled essence by default, raw bodies with ``distill=False``.
        This package consults only: it never answers the question itself.
        Callers feed the returned knowledge into their own LLM call.

        Pipeline stages:
        1. SELECT: pick relevant skills (forced by names, or LLM-powered)
        2. DISTILL: extract essence (LLM-powered, or raw content)

        Args:
            send_to (str | None): Routing-group variant for the LLM call. Resolved against
                    the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                    ``TASK``.
            question: The question/task to consult the skills about.
            names: Force-select these skill names (skips LLM selection).
                   If None and select=True, uses LLM to pick from self.skill_names.
                   If None and select=False, uses all self.skill_names.
            select: Whether to use LLM for skill selection (default True).
            distill: Whether to use LLM for distillation (default True).
            **kwargs: LLM parameters.

        Returns:
            Consulted skill knowledge, or ``""`` when nothing is relevant.
        """
        # Stage 1: SELECT
        if names:
            selected = self._resolve_skills(names)
            if len(selected) < len(names):
                found = {s.name for s in selected}
                missing = [n for n in names if n not in found]
                logger.warn(f"Skills not found: {missing}")
        elif select:
            selected = await self.select_skills(question, **kwargs)
        else:
            selected = self._resolve_skills()

        if not selected:
            logger.warn("No skills selected.")
            return ""

        # Stage 2: DISTILL
        if distill:
            return await self.distill_skills(question, selected, **kwargs)
        return "\n\n".join(s.content for s in selected)
