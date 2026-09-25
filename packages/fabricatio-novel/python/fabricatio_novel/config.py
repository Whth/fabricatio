"""Module containing configuration classes for fabricatio-novel.

The config carries the template entries the overhaul pipeline needs: the
novel metadata extraction, the scene writing, the character roster span
proposal, and the per-chapter and per-story span drafting. The trace and
slice machinery was removed entirely; only the flat CharacterSpan design
remains.
"""

from fabricatio_comfyui.models import LoraEntry, Prop
from fabricatio_core import CONFIG
from pydantic import BaseModel, ConfigDict


class BenchmarkKnobs(BaseModel):
    """The sizes a benchmark scorecard reads a run by, under ``[ext.novel.benchmark]``.

    The first seven are read by the Rust measures (``fabricatio_novel.rust.Knobs``), the last two by
    the Python side of the scorecard. A knob left unset keeps the calibrated value it was measured
    at, so a run scored without this table is comparable with every run scored before it.
    """

    model_config = ConfigDict(frozen=True)

    pair_size: int | None = None
    """characters per n-gram when scene pairs are shingled; long enough that sharing one means more than shared vocabulary."""

    seam_size: int | None = None
    """characters per n-gram when a seam is compared; short enough to survive a paraphrase at the seam."""

    seam_window: int | None = None
    """characters read from each side of a seam when measuring an echo."""

    echo_warn: float | None = None
    """pair or seam overlap above which the scorecard flags a repetition; clean runs measured under 0.03, seams that restaged the previous scene 0.10-0.14."""

    vocab_size: int | None = None
    """characters per vocabulary n-gram, at most 6; characters rather than words, so one stream measures every script."""

    vocab_window: int | None = None
    """n-grams per vocabulary window; windows are averaged so a long run does not score as more repetitive than a short one."""

    vocab_tops: int | None = None
    """how many of the most frequent n-grams each n-gram size's table names."""

    duplicate_min_chars: int | None = None
    """shortest whitespace-normalized sentence counted as a verbatim duplicate."""

    long_sentence_chars: int | None = None
    """sentence length from which a sentence counts as long; about fifteen English words, a run-on in Chinese."""


class NovelConfig(BaseModel):
    """Configuration for fabricatio-novel."""

    model_config = ConfigDict(frozen=True)

    benchmark: BenchmarkKnobs = BenchmarkKnobs()
    """the knobs a benchmark scorecard measures a run by; every field unset keeps its calibrated value."""

    novel_metadata_requirement_template: str = "built-in/novel_metadata_requirement"
    """template used to extract the novel metadata (title, synopsis, word count) from the outline."""

    plan_requirement_template: str = "built-in/plan_requirement"
    """template used to plan the chapters of the novel, the stories of a chapter and the scenes of a story."""

    scene_requirement_template: str = "built-in/scene_requirement"
    """template used to write a single scene in full prose."""

    render_chapter_xhtml_template: str = "built-in/render_chapter_xhtml"
    """template used to render a chapter as a full XHTML document."""

    scene_overlap_min_chars: int = 40
    """minimum whitespace-normalized overlap between a new scene's prefix and the previous prose that gets stripped; shorter echoes are kept."""

    scene_overlap_max_ratio: float = 0.6
    """maximum fraction of a generated scene the overlap may cover before the content is kept untouched with a warning instead of stripped."""

    bench_scorecard_template: str = "built-in/bench_scorecard"
    """template used to render one run's benchmark scorecard."""

    bench_comparison_template: str = "built-in/bench_comparison"
    """template used to render two runs' benchmark comparison."""

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

    boundary_requirement_template: str = "built-in/boundary_requirement"
    """template used to draft the N-1 chapter- and the S-1 story-boundary cards from the parent's spans."""

    scene_illustration_prompt_template: str = "built-in/scene_illustration_prompt"
    """template used to propose one image-generation prompt for a composed scene."""

    illustration_constraint: str = ""
    """global style/content constraint merged into every scene illustration prompt proposal; empty when unset."""

    illustration_negative_prompt: str = (
        "worst, lowres, low quality, mulform, sketch, texts, censor, terrible quality, garbage,"
        " multiple arms, multiple legs, multiple fingers, jpeg artifacts, out of frame, watermark,"
        " cropped, signature, blurry,bad,bad anatomy"
    )
    """negative prompt forwarded to ComfyUI for every scene illustration unless the proposal supplies its own."""

    illustration_prompt_suffix: str = "best quality,masterpiece,4k,highres"
    """quality tags appended to every scene illustration render prompt after the LoRA trigger
    augmentation; set empty to append nothing."""

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

    illustration_prop: Prop | None = None
    """aspect-ratio preset of each scene illustration for ComfyUI.

    TOML takes enum member names like ``"prop_2_3"`` (the member values),
    coerced to :class:`~fabricatio_comfyui.models.resolution.Prop` at
    load.  ``None`` falls back to ``[ext.comfyui] prop``, then to the
    active ComfyUI template's ratio.
    """

    illustration_always_loras: list[LoraEntry] = []
    """LoRA entries chained into every scene illustration render before any selection.

    The slot for always-on LoRAs such as a character/style LoRA: each
    entry rides the render chain verbatim and its ``trigger_words``
    activate it in the prompt.  On top of this chain the LLM may pick
    per scene from the comfyui LoRA catalog (``[ext.comfyui] loras``)
    for LoRAs that should be selected rather than always-on; an empty
    catalog or empty pick chains just this list.
    """

    illustration_choose_loras: bool = False
    """Opt-in per-scene LLM LoRA selection from the ``[ext.comfyui] loras`` catalog during
    illustration; off by default. ``illustration_always_loras`` chains regardless of this flag."""

    illustration_judge: bool = False
    """Opt-in per-scene visual judgement of rendered illustrations via a vision LLM; off by
    default. Failed verdicts re-propose the illustration prompt and re-render."""

    illustration_judge_max_tries: int = 3
    """Total generation attempts per scene when ``illustration_judge`` is on; the last
    attempt's image is always kept, judged or not."""

    scene_illustration_feedback_template: str = "built-in/scene_illustration_feedback"
    """Template rendering the rejected-attempt feedback tail appended to the requirement when
    a judged render is retried."""

    illustration_seed: int | None = None
    """scene illustration sampler seed; ``None`` keeps the bundled ComfyUI template's seed."""

    illustration_skip_existing: bool = True
    """skip scenes whose illustration PNG already exists so re-runs fill only the gaps."""

    illustration_timeout_per_image: float = 210.0
    """per-scene illustration generation timeout in seconds; the total render timeout scales linearly with the batch size (this value x pending renders) since every render shares one ComfyUI queue; ``0`` falls back to the global ``[ext.comfyui] timeout``."""


novel_config = CONFIG.load("novel", NovelConfig)

__all__ = ["novel_config"]
