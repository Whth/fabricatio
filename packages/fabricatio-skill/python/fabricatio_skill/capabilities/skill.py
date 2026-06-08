"""Module containing the UseSkill capability for progressive skill resolution."""

from abc import ABC
from typing import List, Optional, Self, Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import LLMKwargs
from pydantic import Field

from fabricatio_skill.config import skill_config
from fabricatio_skill.models.skill import get_skill_registry
from fabricatio_skill.rust import get_skill


class UseSkill(UseLLM, ABC):
    """Mixin that provides progressive skill resolution for LLM calls.

    Skills are text-based instruction files (markdown) that provide context
    to LLM agents.  Skill objects live in the global ``SkillRegistry``;
    this class stores only their **names** as lightweight handles.

    Pipeline levels:

    Level 1 (Rust):   scan / search / get — file discovery + keyword matching
    Level 2 (Python): select / distill — LLM-powered relevance + extraction
    Level 3 (Python): use_skill — full progressive pipeline (select → distill → ask)
    """

    skill_names: List[str] = Field(default_factory=list)
    """Names of loaded skills available for this role/action (resolved via registry)."""

    # ── helpers ───────────────────────────────────────────────────────

    def _resolve_skills(self, names: Optional[List[str]] = None) -> list:
        """Return Skill objects from the registry.

        Args:
            names: Specific names to resolve. ``None`` → ``self.skill_names``.
        """
        target = names if names is not None else self.skill_names
        return get_skill_registry().get_many(target)

    @property
    def skills(self) -> list:
        """Convenience: resolve current skill_names to live Skill objects."""
        return self._resolve_skills()

    # ── Level 1: Register ─────────────────────────────────────────────

    def add_skills(self, skills: list, names: Optional[List[str]] = None) -> Self:
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
        available: Optional[List[str]] = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> list:
        """Use LLM to select skills relevant to a question.

        Args:
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

        response = await self.aask(prompt, **kwargs)
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
        skills: list,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Use LLM to extract the essential parts of skills relevant to a question.

        Args:
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

        result = await self.aask(prompt, **kwargs)
        logger.info(f"Distilled {len(skills)} skill(s) into {len(result)} chars.")
        return result

    # ── Level 3: Full pipeline ───────────────────────────────────────

    async def use_skill(
        self,
        question: str,
        *,
        names: Optional[List[str]] = None,
        select: bool = True,
        distill: bool = True,
        in_content: bool = False,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Progressive skill resolution pipeline, then ask LLM.

        Pipeline stages:
        1. SELECT: pick relevant skills (forced by names, or LLM-powered)
        2. DISTILL: extract essence (LLM-powered, or raw content)
        3. RENDER: prepend distilled context to question, send to LLM

        Args:
            question: The question/task to solve.
            names: Force-select these skill names (skips LLM selection).
                   If None and select=True, uses LLM to pick from self.skill_names.
                   If None and select=False, uses all self.skill_names.
            select: Whether to use LLM for skill selection (default True).
            distill: Whether to use LLM for distillation (default True).
            in_content: Whether search_skills also matches within content body.
            **kwargs: LLM parameters.

        Returns:
            LLM response with skill context injected.
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
            logger.warn("No skills selected. Proceeding without skill context.")
            return await self.aask(question, **kwargs)

        # Stage 2: DISTILL
        if distill:
            context = await self.distill_skills(question, selected, **kwargs)
        else:
            context = "\n\n".join(s.content for s in selected)

        # Stage 3: RENDER — prepend context and ask
        return await self.aask_with_context(question, context, **kwargs)

    # ── Level 3: Composable ──────────────────────────────────────────

    async def aask_with_context(
        self,
        question: str,
        context: str,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Ask LLM with arbitrary context prepended to the question.

        Args:
            question: The question/task.
            context: Context text to prepend.
            **kwargs: LLM parameters.

        Returns:
            LLM response.
        """
        enriched = f"{context}\n\n---\n\n{question}" if context else question
        return await self.aask(enriched, **kwargs)
