"""This module defines the core data structures for narrative scenes and scripts.

Together, these classes form a foundation for creating structured yet flexible narrative content.
"""

from typing import Any, ClassVar, Dict, List, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble
from fabricatio_core.models.generic import Described, SketchedAble
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

    @classmethod
    def with_raw_synosis(cls, synosis: str) -> Self:
        """Create a script with a single scene containing the synopsis as narrative."""
        return cls(global_prompt="", scenes=[Scene.with_raw_description(synosis)])
