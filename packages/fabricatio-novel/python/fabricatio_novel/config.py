"""Module containing configuration classes for fabricatio-novel."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class NovelConfig:
    """Configuration for fabricatio-novel."""

    render_script_template: str = "built-in/render_script"
    """template used to render scripts."""

    character_requirement_template: str = "built-in/character_requirement"
    """template used to render character requirements."""
    script_requirement_template: str = "built-in/script_requirement"
    """template used to render script requirements."""
    chapter_requirement_template: str = "built-in/chapter_requirement"
    """template used to render chapter requirements."""
    render_chapter_xhtml_template: str = "built-in/render_chapter_xhtml"
    """template used to render chapter xhtml."""
    novel_draft_requirement_template: str = "built-in/novel_draft_requirement"
    """template used to render novel draft requirements."""


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
