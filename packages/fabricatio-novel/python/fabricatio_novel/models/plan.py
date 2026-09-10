"""Flat per-element plan models and their bare-JSON-array list classes."""

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, JSONList, SketchedAble, Titled
from pydantic import Field, PositiveFloat


class WeightedPlan(SketchedAble, Titled, Described):
    """Plan of a single novel element: title, description, and word-count weight."""

    weight: PositiveFloat = 1.0
    """Relative importance for allocating the parent's expected word count; assign by narrative importance."""

    writing_styles: list[str]
    """Style directives for this element's prose: narrative voice, point of view, tone,
    rhythm, and recurring techniques; empty list when no specific style is required."""

    writing_constraints: list[str]
    """Hard writing constraints binding this element: point of view, tense, perspective,
    prohibitions. The constraints in force at the level above are shown when planning this
    element's children; this list is never merged with the parent's, so each element carries
    its own rules alone and a scene's prose prompt shows the scene's own entries only. Empty
    list when no constraint applies."""

    cast: list[str] = Field(default_factory=list)
    """Names of the characters on stage in this element; the planner proposes the cast.
    Empty when no character appears in this element."""


class ScenePlan(WeightedPlan):
    """Plan of a single scene; its weight allocates the story's expected word count."""

    description: str
    """1-2 sentences stating exactly what happens in this scene: where and when it takes place,
    who is present, what they do or say, the conflict or turn, and how the situation changes by
    its end. The model writes the scene's prose directly from this description, so give concrete,
    stageable details — not a theme or a summary."""

    writing_styles: list[str]
    """1-2 directive entries stating the writing technique for this scene's prose: narrative
    voice and point of view, sentence rhythm, tone and atmosphere, dialogue handling, and
    description density. The model writes the prose directly from these, so name concrete,
    applicable techniques — not a genre label or a theme."""

    writing_constraints: list[str]
    """1-2 entries stating the hard writing constraints that bind this scene's prose: whose
    head it stays in (no head-hopping), where this beat may start or end, and scene-specific
    dialogue or sensory restrictions. Keep this scene inside its own Description: never order
    events that belong to another scene. The story's constraints are shown above as the rules
    in force — carry forward the ones that must still bind this scene, since this list alone
    reaches the prose prompt."""


class StoryPlan(WeightedPlan):
    """Plan of a single story; its weight allocates the chapter's expected word count."""

    description: str
    """1-2 sentences stating this story's narrative beat: the situation its scenes will dramatize,
    the characters involved, and what changes by the end. It is shown when planning the story's
    scenes, so name the concrete events to stage rather than restating the chapter."""

    writing_styles: list[str]
    """1-2 directive entries stating the writing style its scenes should share: a consistent
    voice, tone, and technique across the story's scenes. Empty list when the chapter's
    style already suffices."""

    writing_constraints: list[str]
    """1-2 entries stating the hard writing constraints binding this story as a whole: its own
    point of view or tense, how its scenes progress, and prohibitions spanning its scenes.
    Never an event order spanning other stories — the ordered story list already fixes the
    chapter's sequencing. The chapter's constraints are shown above as the rules in force;
    carry forward the ones that must still bind this story."""


class ChapterPlan(WeightedPlan):
    """Plan of a single chapter; its weight allocates the novel's expected word count."""

    description: str
    """1-2 sentences stating what concretely happens in this chapter: which storyline advances,
    the key event or reversal, and where it leaves the characters. Focus on the chapter's own
    arc — it is shown when planning the chapter's stories, so name the events that stage it."""

    writing_styles: list[str]
    """1-2 directive entries stating the writing style its stories should follow: the
    chapter's narrative voice, tone, and pacing. Empty list when the novel's style
    already suffices."""

    writing_constraints: list[str]
    """2-3 entries stating the hard writing constraints binding this chapter: its own point of
    view or tense and prohibitions spanning its stories. Never an event order spanning the
    whole chapter — the ordered story list you propose is what sequences it, so an order
    written here would be re-planned inside whichever story reads it. The novel's constraints
    are shown above as the rules in force; carry forward the ones that must still bind this
    chapter."""


class NovelPlan(WeightedPlan, WordCount):
    """Plan of the novel itself: metadata only, chapters are planned separately."""

    description: str
    """6-10 sentences stating the novel's premise: who the protagonist is, what they want, the
    central conflict blocking them, and the stakes. Convey genre and tone. This description
    seeds every chapter's planning prompt, so be specific and evocative, never a tagline."""

    writing_styles: list[str]
    """2-4 directive entries stating the novel's overall writing style: narrative voice,
    tone, rhythm, and recurring techniques. They seed the style guidance of every chapter,
    story, and scene."""

    writing_constraints: list[str]
    """3-6 entries stating the novel's standing rules: point of view, tense, quality standards
    extracted carefully from the outline. They are shown to every chapter planner as the rules
    in force and are never merged into the chapters' own lists."""


class ScenePlans(JSONList[ScenePlan]):
    """A bare JSON array of scene plans as the LLM returns it."""


class StoryPlans(JSONList[StoryPlan]):
    """A bare JSON array of story plans as the LLM returns it."""


class ChapterPlans(JSONList[ChapterPlan]):
    """A bare JSON array of chapter plans as the LLM returns it."""
