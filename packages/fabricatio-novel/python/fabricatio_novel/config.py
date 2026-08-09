"""Module containing configuration classes for fabricatio-novel.

The config carries ONLY the template entries the overhaul pipeline needs:
the novel metadata extraction, the scene writing, and the character
evolution analysis. Everything belonging to the deleted chapter pipeline,
the deferred capabilities (state/mental/RAG/illustration/enrich), and their
templates is gone — it returns with the capability when it is integrated
back.
"""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class NovelConfig:
    """Configuration for fabricatio-novel."""

    novel_metadata_requirement_template: str = "built-in/novel_metadata_requirement"
    """template used to extract the novel metadata (title, synopsis, word count) from the outline."""

    chapter_plan_template: str = "built-in/chapter_plan"
    """template used to plan the chapters of the novel from the outline and metadata."""

    story_plan_template: str = "built-in/story_plan"
    """template used to plan the stories (剧情段) of a chapter."""

    scene_plan_template: str = "built-in/scene_plan"
    """template used to plan the scenes of a story."""

    scene_requirement_template: str = "built-in/scene_requirement"
    """template used to write a single scene in full prose."""

    render_chapter_xhtml_template: str = "built-in/render_chapter_xhtml"
    """template used to render a chapter as a full XHTML document."""

    charactor_diff_template: str = "built-in/charactor_diff"
    """template used to analyze how a character evolves inside a scene."""

    setting_bible_characters_template: str = "built-in/setting_bible_characters"
    """template used to propose the bible's character roster as a single string."""

    setting_bible_background_template: str = "built-in/setting_bible_background"
    """template used to propose the bible's background settings as a list of strings."""

    setting_bible_context_template: str = "built-in/setting_bible_context"
    """template used to render the bible block injected into scene prompts."""

    setting_bible_export_template: str = "built-in/setting_bible_export"
    """template used to render the bible as a human-readable markdown document."""

    writing_style_as_prompt_template: str = "built-in/writing_style_as_prompt"
    """template used to render writing style documents as prompts."""

    writing_style_digest_template: str = "built-in/writing_style_digest"
    """template used to condense retrieved writing style documents into a guideline."""

    enriched_as_prompt_template: str = "built-in/enriched_as_prompt"
    """template used to render enriched reference documents as prompts."""


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
