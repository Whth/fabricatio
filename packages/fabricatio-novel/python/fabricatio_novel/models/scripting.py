"""This module defines the core data structures for narrative scenes and scripts.

Together, these classes form a foundation for creating structured yet flexible narrative content.
"""

from typing import Any, ClassVar, Dict, List, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble, WordCount
from fabricatio_core.models.generic import Described, SketchedAble, Titled
from pydantic import Field

from fabricatio_novel.config import novel_config


class Scene(PersistentAble, SketchedAble, WordCount, Described):
    """The most basic narrative unit."""

    expected_word_count: int
    """Expected word count when writing the content that the Scene is narrating."""

    tags: List[str]
    """free-form semantic labels for filtering, grouping, or post-processing."""

    prompt: str
    """natural language guidance for tone, style, or constraint."""

    description: str = Field(alias="narrative")
    """dialogue, description, log, poem, monologue, etc."""

    def append_prompt(self, prompt: str) -> Self:
        """Add a prompt to the scene.

        Args:
            prompt (str): The prompt to add.
        """
        self.prompt += f"\n{prompt}"
        return self


class Script(SketchedAble, PersistentAble, Titled, AsPrompt, WordCount):
    """A sequence of scenes forming a cohesive narrative unit especially for a novel chapter."""

    title: str = Field(examples=["Ch1: A Chapter Title For Example", "Ch1: 一个示例章节标题"])
    """Title of the chapter."""

    expected_word_count: int
    """Expected word count for this chapter."""

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
