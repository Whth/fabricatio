"""Module containing the UseSkill capability for progressive skill resolution."""

from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Self, Unpack, cast

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ChooseKwargs
from fabricatio_core.rust import SMOL
from pydantic import Field, PrivateAttr

from fabricatio_skill.config import skill_config
from fabricatio_skill.rust import Skill, SkillRegistry

if TYPE_CHECKING:
    from fabricatio_core.models.generic import WithBriefing


class UseSkill(UseLLM, ABC):
    """Mixin that provides progressive skill consultation.

    Skills are text-based instruction files (markdown) that provide context
    to LLM agents. Every loaded skill lives in the process-wide
    ``SkillRegistry`` library — **one in-memory copy per skill name** — and
    this class stores only their **names** as lightweight handles. The loaders
    chain::

        role.scan_skills("team-skills").gather_skills(["security", "review"])

    Pipeline levels:

    Level 0 (Rust):   ``SkillRegistry`` — scan / search / get: file discovery +
                      keyword matching. ``search`` doubles as a deterministic
                      pre-filter for large pools (see ``prefilter_threshold``).
    Level 1 (Python): select / distill — LLM-powered relevance + extraction.
                      Selection is a framework ``achoose`` round-trip over skill
                      briefings: the JSON reply is set-validated against the
                      catalog (retried on garbage) and capped at
                      ``max_selected_skills``.
    Level 2 (Python): consult_skills — full progressive pipeline (select → distill),
                      returning the consulted knowledge; answering is the caller's job.

    Progressive exclusion: content that fails an earlier stage never reaches a
    later prompt — keyword pre-filter excludes non-matching skills from the LLM
    pool, selection excludes unlisted bodies from distillation, distillation
    excludes non-essential text from the answer context.
    """

    skill_names: list[str] = Field(default_factory=list)
    """Names of loaded skills available for this role/action (resolved via the library)."""

    _default_dirs_scanned: bool = PrivateAttr(default=False)
    """Whether the default skill dirs were already probed for this instance."""

    # ── helpers ───────────────────────────────────────────────────────

    @property
    def skill_library(self) -> SkillRegistry:
        """The process-wide skill library: one in-memory copy of every loaded skill."""
        return SkillRegistry.instance()

    def _resolve_skills(self, names: list[str] | None = None) -> list[Skill]:
        """Return Skill objects from the library.

        Args:
            names: Specific names to resolve. ``None`` → ``self.skill_names``.
        """
        target = names if names is not None else self.skill_names
        return self.skill_library.get_many(target)

    def _track(self, names: list[str]) -> Self:
        """Track freshly loaded skill names on this role, without duplicating.

        Args:
            names: Names that were just loaded into the library.

        Returns:
            Self for method chaining.
        """
        new_names = list(dict.fromkeys(n for n in names if n not in self.skill_names))
        self.skill_names.extend(new_names)
        logger.info(f"Registered {len(new_names)} skill(s): {new_names}")
        return self

    @property
    def skills(self) -> list[Skill]:
        """Convenience: resolve current skill_names to live Skill objects."""
        return self._resolve_skills()

    # ── Level 1: Register ─────────────────────────────────────────────

    def add_skills(self, skills: list[Skill], names: list[str] | None = None) -> Self:
        """Register already-loaded skills in the library and track their names here.

        Args:
            skills: Skill objects to register.
            names: If given, only register skills whose name is in this list.

        Returns:
            Self for method chaining.
        """
        selected = [s for s in skills if s.name in names] if names else list(skills)
        self.skill_library.add(selected)
        return self._track([s.name for s in selected])

    def scan_skills(self, root: str | Path) -> Self:
        """Load every skill file under ``root`` into the library and track them.

        The bulk loader: walks ``root`` recursively (``<dir>/<name>/SKILL.md``
        and flat ``<dir>/<name>.md`` both parse). Skills already in the library
        keep their first copy, but are still tracked here.

        Args:
            root: Directory to scan recursively (``~`` is expanded).

        Returns:
            Self for method chaining.

        Raises:
            FileNotFoundError: ``root`` is not an existing directory.
        """
        return self._track(self.skill_library.load_scanned([str(Path(root).expanduser())]))

    def gather_skills(self, names: list[str], dirs: list[str | Path] | None = None) -> Self:
        """Gather skills directly by name and track them on this role.

        Resolves each name through the lookup roots (``<dir>/<name>/SKILL.md``
        then ``<dir>/<name>.md`` per root — direct path reads, no directory
        scan), loads the hits into the process-wide library, and extends
        ``skill_names``. Missing names are logged and skipped; names already in
        the library keep their first copy and are not read again.

        Args:
            names: Skill names to gather.
            dirs: Lookup roots (``~`` is expanded). ``None`` →
                ``skill_config.default_skill_dirs``.

        Returns:
            Self for method chaining.
        """
        roots = [str(Path(d).expanduser()) for d in (dirs if dirs is not None else skill_config.default_skill_dirs)]
        wanted = list(dict.fromkeys(names))
        found = self.skill_library.load_by_name(wanted, roots)
        for name in wanted:
            if name not in found:
                logger.warn(f"Skill '{name}' not found in any lookup dir: {roots}")
        return self._track(found)

    def _ensure_default_skills(self) -> None:
        """Auto-load ``default_skill_dirs`` once, when this role has no skills yet.

        Lets ``consult_skills`` work out of the box: drop skill files into the
        default dirs and call it — no explicit loading needed. Idempotent per
        instance; explicit ``scan_skills``/``gather_skills`` take precedence.
        """
        if self._default_dirs_scanned or self.skill_names:
            return
        self._default_dirs_scanned = True
        for skill_dir in skill_config.default_skill_dirs:
            root = Path(skill_dir).expanduser()
            if not root.is_dir():
                continue
            found = self.skill_library.load_scanned([str(root)])
            if found:
                self._track(found)
                logger.info(f"Auto-loaded {len(found)} skill(s) from default dir '{skill_dir}'")

    # ── Level 2: Select ──────────────────────────────────────────────

    async def select_skills(
        self,
        question: str,
        available: list[str] | None = None,
        k: int | None = None,
        send_to: str | None = SMOL,
        **kwargs: Unpack[ChooseKwargs[Skill]],
    ) -> list[Skill] | None:
        """Use the framework chooser to select skills relevant to a question.

        Delegates to ``UseLLM.achoose``: each candidate is presented by its
        ``briefing`` (name + description, never the body), the reply must be a
        JSON array of catalog names, and the framework validates it as a set —
        unknown names are ignored, duplicates collapse, and unparseable
        replies are retried automatically. The library's deterministic keyword
        pre-filter thins the pool first when it exceeds ``prefilter_threshold``,
        and the final selection is trimmed to ``max_selected_skills`` (or ``k``).

        Args:
            question: The question/task to match skills against.
            available: Skill name pool to select from. Defaults to self.skill_names.
            k: Max skills this call may fetch. ``None`` → the ``max_selected_skills`` config;
                    ``0`` → no limit; ``n`` → at most ``n``. Overrides the config cap.
            send_to (str | None): Routing-group variant for the LLM call. Resolved against
                    the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                    ``SMOL`` (small-model tier: selection/distillation are light jobs);
                    pass ``TASK``/``SLOW``/``PLAN`` to escalate, or ``None`` to fall
                    through to the role/config default.
            **kwargs: Extra arguments for the framework chooser (e.g. ``max_validations``).

        Returns:
            Skills deemed relevant by the LLM, capped at ``max_selected_skills`` (or ``k``);
            ``[]`` when nothing matched (or the pool is empty) and ``None`` when
            the LLM failed to produce a parseable selection after retries.
        """
        self._ensure_default_skills()
        pool_names = available if available is not None else self.skill_names
        pool = self.skill_library.get_many(pool_names)
        if not pool:
            logger.warn("No skills available for selection.")
            return []

        threshold = skill_config.prefilter_threshold
        if threshold > 0 and len(pool) > threshold:
            pool = self.skill_library.search(question, names=pool_names, in_content=True)[:threshold]
            logger.info(f"Keyword pre-filter (pool above threshold {threshold}): {len(pool)} candidate(s) remain.")
            if not pool:
                logger.warn("No keyword matches; nothing to select from.")
                return []

        cap = skill_config.max_selected_skills if k is None else k
        instruction = (
            f"{question}\nSelect at most {cap} skills relevant to the question. "
            "Fewer is fine when only some of them are relevant."
            if cap > 0
            else question
        )
        # The Rust ``Skill`` satisfies the ``WithBriefing`` option contract
        # (name + briefing); cast across the FFI boundary for the chooser.
        options = cast("list[WithBriefing]", pool)
        picked = cast(
            "list[Skill] | None",
            await self.achoose(
                instruction=instruction,
                choices=options,
                send_to=send_to,
                **kwargs,
            ),
        )
        if not picked:
            return picked
        if cap > 0 and len(picked) > cap:
            logger.info(f"Selection capped at {cap}: dropped {len(picked) - cap} tail skill(s).")
            picked = picked[:cap]
        logger.info(f"Selected {len(picked)} skill(s): {[s.name for s in picked]}")
        return picked

    # ── Level 2: Distill ─────────────────────────────────────────────

    async def distill_skills(
        self,
        question: str,
        skills: list[Skill],
        send_to: str | None = SMOL,
        **kwargs: Unpack[ChooseKwargs[Skill]],
    ) -> str:
        """Use LLM to extract the essential parts of skills relevant to a question.

        Args:
            question: The question/task to focus distillation on.
            skills: Skills to distill.
            send_to (str | None): Routing-group variant for the LLM call. Resolved against
                    the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                    ``SMOL`` (small-model tier: selection/distillation are light jobs);
                    pass ``TASK``/``SLOW``/``PLAN`` to escalate, or ``None`` to fall
                    through to the role/config default.
            **kwargs: Extra arguments for the LLM call.

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
        k: int | None = None,
        send_to: str | None = SMOL,
        **kwargs: Unpack[ChooseKwargs[Skill]],
    ) -> str:
        """Consult the skill library about a question.

        Progressively resolves relevant skills and returns what they say —
        distilled essence by default, raw bodies with ``distill=False``.
        This package consults only: it never answers the question itself.
        Callers feed the returned knowledge into their own LLM call.

        Pipeline stages:

        1. ENSURE (optional): auto-load skills from ``default_skill_dirs`` when
           this role has none (zero-config usage).
        2. SELECT: pick relevant skills (forced by names, or the framework
           chooser over a keyword pre-filtered, capped pool).
        3. DISTILL: extract essence (LLM-powered, or raw content).

        Args:
            question: The question/task to consult the skills about.
            names: Force-select these skill names (skips LLM selection).
                   If None and select=True, uses LLM to pick from self.skill_names.
                   If None and select=False, uses all self.skill_names.
            select: Whether to use LLM for skill selection (default True).
            distill: Whether to use LLM for distillation (default True).
            k: Max skills this call may fetch. ``None`` → the ``max_selected_skills`` config;
                    ``0`` → no limit; ``n`` → at most ``n``. Ignored with ``names=``.
            send_to (str | None): Routing-group variant for the LLM call. Resolved against
                    the agent variant registry (see ``fabricatio_core.rust``). Defaults to
                    ``SMOL`` (small-model tier: selection/distillation are light jobs);
                    pass ``TASK``/``SLOW``/``PLAN`` to escalate, or ``None`` to fall
                    through to the role/config default.
            **kwargs: Extra arguments for the LLM calls.

        Returns:
            Consulted skill knowledge, or ``""`` when nothing is relevant.
        """
        self._ensure_default_skills()

        # Stage 2: SELECT
        if names:
            selected = self._resolve_skills(names)
            if len(selected) < len(names):
                found = {s.name for s in selected}
                missing = [n for n in names if n not in found]
                logger.warn(f"Skills not found: {missing}")
        elif select:
            selected = await self.select_skills(question, k=k, send_to=send_to, **kwargs)
        else:
            selected = self._resolve_skills()

        if not selected:
            logger.warn("No skills selected.")
            return ""

        # Stage 3: DISTILL
        if distill:
            knowledge = await self.distill_skills(question, selected, send_to=send_to, **kwargs)
        else:
            knowledge = "\n\n".join(s.content for s in selected)
        logger.debug(
            f"consult_skills funnel: {len(selected)} selected skill(s) -> {len(knowledge)} chars of knowledge."
        )
        return knowledge
