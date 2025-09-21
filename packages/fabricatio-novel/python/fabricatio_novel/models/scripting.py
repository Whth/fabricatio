"""This module defines the core data structures for narrative scenes and scripts.

Together, these classes form a foundation for creating structured yet flexible narrative content.
"""

from typing import Any, ClassVar, Dict, List, Self

from fabricatio_capabilities.models.generic import AsPrompt
from fabricatio_core.models.generic import SketchedAble, Titled

from fabricatio_novel.config import novel_config


class Scene(SketchedAble):
    """A self-contained narrative moment for storytelling, games, film, or AI generation."""

    narrative: str
    """dialogue, description, log, poem, monologue, etc."""

    prompt: str
    """natural language guidance for tone, style, or constraint."""

    tags: List[str]
    """free-form semantic labels for filtering, grouping, or post-processing."""

    def append_prompt(self, prompt: str) -> Self:
        """Add a prompt to the scene.

        Args:
            prompt (str): The prompt to add.
        """
        self.prompt += f"\n{prompt}"
        return self


class Script(SketchedAble, Titled, AsPrompt):
    """A sequence of scenes forming a cohesive narrative unit."""

    title: str
    """Title of the thing the script is about"""

    scenes: List[Scene]
    """Ordered list of scenes. Must contain at least one scene. Sequence implies narrative flow."""

    global_prompt: str
    """global writing guidance applied to all scenes."""

    expected_word_count: int
    """Expected word count for the script."""

    rendering_template: ClassVar[str] = novel_config.render_script_template

    def _as_prompt_inner(self) -> Dict[str, str] | Dict[str, Any] | Any:
        return self.model_dump()

    def append_global_prompt(self, prompt: str) -> Self:
        """Add a global prompt to the script.

        Args:
            prompt (str): The global prompt to add.
        """
        self.global_prompt += f"\n{prompt}"
        return self

    def set_expected_word_count(self, word_count: int) -> Self:
        """Set the expected word count for the script.

        Args:
            word_count (int): The expected word count.
        """
        self.expected_word_count = word_count
        return self
