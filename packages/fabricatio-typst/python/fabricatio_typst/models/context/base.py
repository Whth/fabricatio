"""Base machinery of the article context tree: the channels every level shares.

A context is the pipeline's channel for one article element: the plan it was handed,
the run-wide constants copied down to it, its own writing channels, and — for the
non-leaf levels — the child contexts it owns. The tree is built top-down by the
planning stages and filled bottom-up by composition; nothing here calls the model.
"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Self, final

from fabricatio_capabilities.models.generic import PersistentAble, UpdateFrom, WordCount
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import Described, Titled
from fabricatio_core.rust import detect_language
from fabricatio_core.utils import wrap_in_block
from fabricatio_skill import get_skill_registry
from fabricatio_skill.config import skill_config
from pydantic import Field

from fabricatio_typst.models.context.log import ContextEntry, ContextLog
from fabricatio_typst.models.plan import WeightedPlan


class ContextBase[P: WeightedPlan](Described, Titled, WordCount, PersistentAble, UpdateFrom[P], ABC):
    """Base class for the hierarchical article contexts shared across chapter, section and subsection levels."""

    plan: P | None = None
    """The plan this element composes from: the planning stage hands it over with ``set_plan``, and every
    prompt of this element renders it."""

    language: str = Field("", exclude=True)
    """Written language; run-wide constant, set progressively during context creation."""

    briefing: str = Field("", exclude=True)
    """The run's briefing; run-wide constant, copied down every creation chain so each planning prompt
    grounds on the source requirements instead of a compressed parent description."""

    proposal: str = Field("", exclude=True)
    """The rendered research proposal; run-wide constant, copied down every creation chain so each planner
    stays aligned with the paper's problem, approaches and aims."""

    skill_names: list[str] = Field(default_factory=list)
    """Names of the skills the user selected for this run; run-wide constant, copied down every creation
    chain so each element renders the same skills."""

    writing_styles: list[str] = Field(default_factory=list)
    """Writing style directives accumulated down the tree: inherited guidance first, this element's own plan
    entry last. Never filled by ``update_from`` — the composing capability seeds it explicitly."""

    writing_constraints: list[str] = Field(default_factory=list)
    """The hard writing constraints binding this element alone. The parent's entries are never merged in —
    they are shown to this element's planner as the rules in force, and the prose prompt of a subsection
    renders only the subsection's own list. Empty when no constraint applies. Never filled by
    ``update_from`` — the composing capability seeds it explicitly."""

    prefix_log: ContextLog = Field(default_factory=ContextLog, exclude=True)
    """Everything composed before this element as an append-only entry log; injected by the parent before
    composition."""

    @classmethod
    def create(
        cls,
        briefing: str,
        *,
        language: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> Self:
        """Build a context from the run-wide briefing, detecting the language when none is given."""
        return cls(
            briefing=briefing,
            language=language or detect_language(briefing),
            title=title or "",
            description=description or "",
        )

    def update_pre_check(self, other: P) -> Self:
        """Reject update sources that are not the expected weighted plan."""
        if not isinstance(other, WeightedPlan):
            raise TypeError(f"Expected a {type(self).__name__} plan, got {type(other).__name__}")
        return self

    def update_from_inner(self, other: P) -> Self:
        """Adopt the plan's scalar fields onto this context: its heading and its elaboration.

        The style and constraint channels are deliberately left alone — they are seeded
        explicitly by the composing capability through ``set_writing_styles`` /
        ``set_writing_constraints``, which know whether the plan's entries augment or
        replace what the context already carries.
        """
        self.title = other.title
        self.description = other.description
        return self

    def set_language(self, language: str) -> Self:
        """Set the written language of this element and return self."""
        self.language = language
        return self

    def set_briefing(self, briefing: str) -> Self:
        """Set the run's briefing carried into this element's prompts and return self."""
        self.briefing = briefing
        return self

    def set_proposal(self, proposal: str) -> Self:
        """Set the rendered research proposal carried into this element's planning prompts and return self."""
        self.proposal = proposal
        return self

    def with_skills(self, names: list[str]) -> Self:
        """Bind the run's selected skill names — resolved through the library's own roots — and return self."""
        self.skill_names = list(names)
        return self

    def with_skills_from[Q: WeightedPlan](self, parent: "ContextBase[Q]") -> Self:
        """Carry the run's skill selection off the parent context so this element renders the same skills."""
        return self.with_skills(parent.skill_names)

    def skill_references(self) -> list[str]:
        """The run's selected skills, fetched by name through the process-wide skill library.

        Only the names travel on the context; the bodies stay in the library, which
        parses a skill once per process and hands the same text to every walk, so a run
        renders byte-identical prompts and a tree rebuilt in a fresh process re-reads
        exactly the files the run named. Each reference is the skill rendered through
        the library as ``<name>body</name>``, so a prompt separates one skill's
        instructions from the next by name. A name that no longer resolves is reported
        by the library and dropped from the section instead of crashing the walk that
        renders it. The references come back in name order rather than the order the
        user assigned the skills, so spelling the selection ``-s b -s a`` renders the
        same bytes as ``-s a -s b`` and the provider's prefix cache holds across either
        spelling.
        """
        if not self.skill_names:
            return []
        library = get_skill_registry()
        # Roots are the library's own: the cross-client dirs plus ``[ext.skill] extra_skill_dirs``.
        # The library reports the names it could not resolve; the run carries on with the rest.
        library.load_by_name(self.skill_names, None, skill_config.extra_skill_dirs)
        skills = sorted(library.get_many(self.skill_names), key=lambda skill: skill.name)
        return [skill.render() for skill in skills]

    def skill_section(self) -> str:
        """The run's selected skills as the one byte-stable section every prompt that shows them renders.

        The plan prompts, the prose prompt and the refinements all render the section
        from these same bytes, so a run's calls to one model lead with an identical head
        and the provider's prefix cache carries over from one call to the next. An empty
        selection renders an empty string, which callers guard on.
        """
        references = self.skill_references()
        if not references:
            return ""
        return wrap_in_block(
            "The user selected the skills below for this article; follow them throughout.\n\n"
            + "\n\n".join(references),
            title="Article Skills",
        )

    def set_writing_styles(self, writing_styles: list[str]) -> Self:
        """Replace this element's accumulated writing style entries and return self."""
        self.writing_styles = writing_styles
        return self

    def add_writing_styles(self, styles: list[str]) -> Self:
        """Append non-empty writing style entries and return self."""
        self.writing_styles.extend(style for style in styles if style)
        return self

    def set_writing_constraints(self, writing_constraints: list[str]) -> Self:
        """Replace this element's own writing constraints, the ones binding it alone, and return self."""
        self.writing_constraints = writing_constraints
        return self

    def set_prefix_log(self, prefix_log: ContextLog) -> Self:
        """Set the append-only log of everything composed before this element and return self."""
        self.prefix_log = prefix_log
        return self

    def set_plan(self, plan: P) -> Self:
        """Set this element's plan and return self."""
        self.plan = plan
        return self

    def prefixed_header_entry(self) -> ContextEntry | None:
        """This element's heading block as an entry seeded into every child's prefix.

        The article renders nothing of its own — its heading belongs to the typst
        document, not to the running text — and a subsection is a leaf. Only the
        chapter and the section contribute a heading; the elaboration of neither is
        seeded, since an element's description is a synopsis of text that follows and
        seeding it would leak the beats of later subsections into every descendant
        prompt.
        """
        return None

    @abstractmethod
    def prefixed_entries(self) -> tuple[ContextEntry, ...]:
        """This element's blocks contributed to every following sibling's prefix.

        A subsection contributes its composed prose; the chapter and the section
        contribute their own heading entry followed by their children's entries.
        """
        ...


class ParentContextBase[C: ContextBase, P: WeightedPlan](ContextBase[P], ABC):
    """Base for non-leaf contexts: a plan-typed channel that owns and iterates child contexts."""

    child_contexts: list[C] = Field(default_factory=list)
    """The child contexts this element owns, in reading order."""

    def add_context(self, child_ctx: C) -> Self:
        """Append one child context and return self."""
        self.child_contexts.append(child_ctx)
        return self

    def iter_child_contexts(self) -> Generator[C, None, None]:
        """Yield this context's child contexts, in composition order."""
        yield from self.child_contexts

    @final
    def iter_prefixed_contexts(self) -> Generator[C, None, None]:
        """Set each child's running prefix log in place and yield it.

        The running log seeds with this element's incoming prefix plus its own
        heading entry, so each child sees exactly the history that precedes its
        content in the final manuscript. Seeding is pure — logs rebind fresh
        tuples — so repeated walks are idempotent and readers holding an earlier
        log never observe later appends.
        """
        seed = self.prefix_log
        if header := self.prefixed_header_entry():
            seed = seed.with_entry(header)
        for child in self.iter_child_contexts():
            child.set_prefix_log(seed)
            logger.trace(seed.render())
            yield child
            seed = seed.with_entries(child.prefixed_entries())


__all__ = ["ContextBase", "ParentContextBase"]
