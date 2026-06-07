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
    chapter_summarization_template: str = "built-in/chapter_summarization"
    """template used to render chapter summarization prompts for cross-chapter context tracking."""
    writing_style_as_prompt_template: str = "built-in/writing_style_as_prompt"
    """template used to render writing style documents as prompts (content only, no metadata)."""
    chapter_summary_as_prompt_template: str = "built-in/chapter_summary_as_prompt"
    """template used to render chapter summaries as prompts (content only, no metadata)."""
    writing_styles_table_name: str = "writing_styles"
    """table name for storing writing style documents in LanceDB."""

    allocate_image_budget_template: str = "built-in/allocate_image_budget"
    """template used to allocate image budget across chapters."""

    select_illustrations_template: str = "built-in/select_illustrations"
    """template used to select paragraphs for illustration."""

    illustration_selection_guideline_template: str = "built-in/illustration_selection_guideline"
    """template used to render the illustration selection guideline."""

    image_prompt_guideline_template: str = "built-in/image_prompt_guideline"
    """template used to render the image prompt generation guideline."""


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
