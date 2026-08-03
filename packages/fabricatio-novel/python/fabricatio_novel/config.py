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
    writing_style_query_refine_template: str = "built-in/writing_style_query_refine"
    """template used to build the query refinement input for writing style retrieval."""
    writing_style_inject_script_template: str = "built-in/writing_style_inject_script"
    """template used to render the script-scope writing style injection sentence."""
    writing_style_inject_scene_template: str = "built-in/writing_style_inject_scene"
    """template used to render the scene-scope writing style injection sentence."""
    chapter_summary_as_prompt_template: str = "built-in/chapter_summary_as_prompt"
    """template used to render chapter summaries as prompts (content only, no metadata)."""
    writing_styles_table_name: str = "writing_styles"
    """table name for storing writing style documents in LanceDB."""

    enriched_as_prompt_template: str = "built-in/enriched_as_prompt"
    """template used to render enriched documents as prompts (content only, no metadata)."""
    enriched_table_name: str = "enriched_chunks"
    """table name for storing LLM-enriched text chunks in LanceDB."""

    allocate_image_budget_template: str = "built-in/allocate_image_budget"
    """template used to allocate image budget across chapters."""

    select_paragraphs_template: str = "built-in/select_paragraphs_for_illustration"
    """template used to select which paragraphs to illustrate (stage 1 of two-stage pipeline)."""

    illustration_constrain_template: str = "built-in/illustration_constrain"
    """template used to propose an :class:`IllustrationConstrain` (frame
    proportion + image-generation prompt) for a single paragraph (stage 2 of
    the two-stage pipeline)."""

    character_base_look_template: str = "built-in/character_base_look"
    """template used to distill character look into permanent physical traits only."""
    illustration_selection_guideline_template: str = "built-in/illustration_selection_guideline"
    """template used to render the illustration selection guideline."""

    image_prompt_guideline_template: str = "built-in/image_prompt_guideline"
    """template used to render the image prompt generation guideline."""

    comfyui_timeout_per_image: float = 240.0
    """Timeout in seconds per image for ComfyUI generation. Total timeout = num_images * this value."""

    rerank_scale_factor: float = 3.0
    """Multiplier for embedding search limit when a rerank target is provided.

    When `writing_style_requirement` is set, embedding search fetches
    limit * rerank_scale_factor docs, then the reranker filters down to
    the original limit. Higher values give the reranker more candidates
    to choose from but increase embedding search cost.
    """


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
