"""Module containing configuration classes for fabricatio-novel.

The config carries the template entries the overhaul pipeline needs: the
novel metadata extraction, the scene writing, the character roster span
proposal, and the per-chapter and per-story span drafting. The trace and
slice machinery was removed entirely; only the flat CharacterSpan design
remains.
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
    """template used to plan the stories of a chapter."""

    scene_plan_template: str = "built-in/scene_plan"
    """template used to plan the scenes of a story."""

    scene_requirement_template: str = "built-in/scene_requirement"
    """template used to write a single scene in full prose."""

    render_chapter_xhtml_template: str = "built-in/render_chapter_xhtml"
    """template used to render a chapter as a full XHTML document."""

    scene_overlap_min_chars: int = 40
    """minimum whitespace-normalized overlap between a new scene's prefix and the previous prose that gets stripped; shorter echoes are kept."""

    scene_overlap_max_ratio: float = 0.6
    """maximum fraction of a generated scene the overlap may cover before the content is kept untouched with a warning instead of stripped."""

    setting_bible_characters_template: str = "built-in/setting_bible_characters"
    """template used to propose the bible's character roster as one string per character."""

    setting_bible_background_template: str = "built-in/setting_bible_background"
    """template used to propose the bible's background settings as a list of strings."""

    setting_bible_context_template: str = "built-in/setting_bible_context"
    """template used to render the bible block injected into scene prompts."""

    setting_bible_export_template: str = "built-in/setting_bible_export"
    """template used to render the bible as a human-readable markdown document."""

    writing_style_as_prompt_template: str = "built-in/writing_style_as_prompt"
    """template used to render writing style documents as prompts."""

    enriched_as_prompt_template: str = "built-in/enriched_as_prompt"
    """template used to render enriched reference documents as prompts."""

    novel_character_span_template: str = "built-in/novel_character_span"
    """template used to propose the novel roster as one CharacterSpan per character."""

    chapter_character_span_template: str = "built-in/chapter_character_span"
    """template used to draft the N-1 chapter-boundary cards from the novel roster spans."""

    story_character_span_template: str = "built-in/story_character_span"
    """template used to draft the S-1 story-boundary cards from the chapter's spans."""

    scene_illustration_prompt_template: str = "built-in/scene_illustration_prompt"
    """template used to propose one image-generation prompt for a composed scene."""

    illustration_constraint: str = ""
    """global style/content constraint merged into every scene illustration prompt proposal; empty when unset."""

    illustration_negative_prompt: str = (
        "worst, lowres, low quality, mulform, sketch, texts, censor, terrible quality, garbage,"
        " multiple arms, multiple legs, multiple fingers, jpeg artifacts, out of frame, watermark,"
        " cropped, signature, blurry"
    )
    """negative prompt forwarded to ComfyUI for every scene illustration unless the proposal supplies its own."""

    illustration_mp: float | None = None
    """megapixel budget of each scene illustration's finished image (``1.0`` = 1,000,000 pixels).

    The ComfyUI template derives its base canvas from this budget and
    its upscale factor, so the output lands at this size.  ``None``
    falls back to ``[ext.comfyui] mp``, then to the active
    ComfyUI template's built-in canvas.
    """

    illustration_mp_max: float = 1.2
    """hard ceiling on every scene illustration's finished-image megapixel budget.

    Enforced at render time even when the LLM proposes a larger ``mp``;
    the renderable quality brink (``512x512x2.2x2.2``) is ~1.27 MP, so
    1.2 keeps a margin under it.
    """

    illustration_prop: str | None = None
    """aspect ratio of each scene illustration for ComfyUI.

    Accepts enum member names (the member values, e.g. ``"prop_2_3"``
    for a portrait scene).  ``None`` falls back to
    ``[ext.comfyui] prop``, then to the active ComfyUI template's ratio.
    """

    illustration_seed: int | None = None
    """scene illustration sampler seed; ``None`` keeps the bundled ComfyUI template's seed."""

    illustration_skip_existing: bool = True
    """skip scenes whose illustration PNG already exists so re-runs fill only the gaps."""

    illustration_timeout_per_image: float = 210.0
    """per-scene illustration generation timeout in seconds; the total render timeout scales linearly with the batch size (this value x pending renders) since every render shares one ComfyUI queue; ``0`` falls back to the global ``[ext.comfyui] timeout``."""


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
