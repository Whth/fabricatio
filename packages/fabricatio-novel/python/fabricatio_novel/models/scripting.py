"""This module defines the core data structures for narrative scenes and scripts.

Together, these classes form a foundation for creating structured yet flexible narrative content.
"""

from typing import Any, ClassVar, Dict, List

from fabricatio_capabilities.models.generic import AsPrompt
from fabricatio_core.models.generic import SketchedAble, Titled

from fabricatio_novel.config import novel_config


class Scene(SketchedAble):
    """A self-contained narrative moment for storytelling, games, film, or AI generation.

    Captures content + guidance + semantic tags. No structure enforced — only intention guided.
    """

    narrative: str
    """dialogue, description, log, poem, monologue, etc."""

    prompt: str
    """natural language guidance for tone, style, or constraint."""

    tags: List[str]
    """free-form semantic labels for filtering, grouping, or post-processing."""


class Script(SketchedAble, Titled, AsPrompt):
    """A sequence of scenes forming a cohesive narrative unit — chapter, episode, act, or event.

    Title + ordered scenes + global writing guidance.
    """

    title: str
    """Title of the script, chapter, or sequence. Must contain at least one character."""

    scenes: List[Scene]
    """Ordered list of scenes. Must contain at least one scene. Sequence implies narrative flow."""

    global_prompt: str
    """global writing guidance applied to all scenes."""

    rendering_template: ClassVar[str] = novel_config.render_script_template

    def _as_prompt_inner(self) -> Dict[str, str] | Dict[str, Any] | Any:
        return self.model_dump()
