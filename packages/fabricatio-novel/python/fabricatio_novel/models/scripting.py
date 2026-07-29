"""This module defines the core data structures for narrative scenes and scripts.

Together, these classes form a foundation for creating structured yet flexible narrative content.
"""

from typing import Any, ClassVar, Dict, List, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble
from fabricatio_core.models.generic import Base, Described, SketchedAble
from pydantic import Field

from fabricatio_novel.config import novel_config


class Scene(PersistentAble, SketchedAble, Described):
    """The most basic narrative unit."""

    tags: List[str]
    """free-form semantic labels for filtering, grouping, or post-processing."""

    prompt: str
    """natural language guidance for tone, style, or constraint."""

    description: str = Field(alias="narrative")
    """dialogue, description, log, poem, monologue, etc."""

    weight: float
    """Relative importance for word-count allocation within the script."""

    location: str = ""
    """Physical or virtual setting where this scene takes place (e.g. 'the inner side of classroom close to the window')."""

    when: str = ""
    """Temporal setting of the scene (e.g. 'the next morning', 'midnight', 'three days later')."""

    characters_present: Dict[str, str] = Field(default_factory=dict)
    """Character names mapped to their detailed acting scripts in this scene (name → what they do/how they appear)."""

    purpose: str = ""
    """Narrative role of this scene."""

    mood: str = ""
    """Emotional atmosphere of the scene."""

    def bulk_append(self, prompts: List[str]) -> Self:
        """Append multiple prompts to the scene in a single call, joined by newlines."""
        self.append_prompt("\n" + "\n".join(prompts))
        return self

    def append_prompt(self, prompt: str) -> Self:
        """Add a prompt to the scene.

        Args:
            prompt (str): The prompt to add.
        """
        self.prompt += f"\n{prompt}"
        return self

    @classmethod
    def with_raw_description(cls, description: str) -> Self:
        """Create a scene with only a narrative description, defaulting weight to 1.0."""
        return cls(tags=[], prompt="", narrative=description, weight=1.0)


class Script(SketchedAble, PersistentAble, AsPrompt):
    """A sequence of scenes forming a cohesive narrative unit especially for a novel chapter."""

    global_prompt: str
    """global writing guidance applied to all scenes."""

    scenes: List[Scene]
    """Ordered list of scenes. Must contain at least one scene. Sequence implies narrative flow."""

    rendering_template: ClassVar[str] = novel_config.render_script_template

    def _as_prompt_inner(self) -> Dict[str, str] | Dict[str, Any] | Any:
        return self.model_dump(by_alias=True)

    def append_global_prompt(self, prompt: str) -> Self:
        """Add a global prompt to the script.

        Args:
            prompt (str): The prompt to add.
        """
        self.global_prompt += f"\n{prompt}"
        return self

    def bulk_append_global_prompt(self, prompt: list[str]) -> Self:
        """Append multiple prompt strings to ``self.global_prompt`` joined by newlines, then return self."""
        self.global_prompt += "\n" + "\n".join(prompt)
        return self

    @classmethod
    def with_raw_synosis(cls, synosis: str) -> Self:
        """Create a script with a single scene containing the synopsis as narrative."""
        return cls(global_prompt="", scenes=[Scene.with_raw_description(synosis)])


class NumericalStat(Base):
    """Store num stats in the novel."""

    desc: str
    """simple desc of num record here"""
    num: float | int


class ChapterSummary(SketchedAble, AsPrompt):
    """Structured summary of a generated chapter for cross-chapter context tracking."""

    key_events: List[str] = Field(default_factory=list)
    """Major plot events that occurred in this chapter."""

    character_states: Dict[str, str] = Field(default_factory=dict)
    """Map of character name to their emotional/physical state at chapter end."""

    character_knowledge: Dict[str, List[str]] = Field(default_factory=dict)
    """Map of character name to list of facts/events they know or experienced up to this chapter."""

    numerical_stat: List[NumericalStat] = Field(default_factory=list)
    """All numerical stats that varies to maintain consistency across chapters. (count,size,attr,time,etc)"""
    emotional_arc: str = ""
    """The emotional trajectory and tone shift across this chapter."""

    unresolved_threads: List[str] = Field(default_factory=list)
    """Plot hooks, tensions, or questions that remain open for future chapters."""

    resolved_threads: List[str] = Field(default_factory=list)
    """Plot hooks or questions that were closed/concluded in or before this chapter. Never resurrect these in later chapters."""

    established_facts: List[str] = Field(default_factory=list)
    """World-level canon the novel must honor regardless of who is present (kingdom names, magic rules, treaties, geography, succession, etc.). Append-only; flag, never silently rewrite, a contradicted entry."""

    last_scene: str = ""
    """Last scene where the chapter ends"""

    rendering_template: ClassVar[str] = novel_config.chapter_summary_as_prompt_template

    def _as_prompt_inner(self) -> Dict[str, str] | Dict[str, Any] | Any:
        return self.model_dump()
