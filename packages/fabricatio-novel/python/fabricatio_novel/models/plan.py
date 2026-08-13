"""Flat per-element plan models and their bare-JSON-array list classes."""

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, JSONList, SketchedAble, Titled
from pydantic import Field, PositiveFloat

from fabricatio_novel.models.series_book import SeriesBible


class WeightedPlan(SketchedAble, Titled, Described):
    """Plan of a single novel element: title, description, and word-count weight."""

    weight: PositiveFloat = 1.0
    """Relative importance for allocating the parent's expected word count; assign by narrative importance."""

    writing_style: str = ""
    """Writing technique guidance for this element's prose: narrative voice, point of view,
    tone, rhythm, and recurring techniques; empty when no specific style is required."""


class ScenePlan(WeightedPlan):
    """Plan of a single scene; its weight allocates the story's expected word count."""

    description: str
    """1-2 sentences stating exactly what happens in this scene: where and when it takes place,
    who is present, what they do or say, the conflict or turn, and how the situation changes by
    its end. The model writes the scene's prose directly from this description, so give concrete,
    stageable details — not a theme or a summary."""

    writing_style: str = ""
    """1-2 sentences stating the writing technique for this scene's prose: narrative voice and
    point of view, sentence rhythm, tone and atmosphere, dialogue handling, and description
    density. The model writes the prose directly from this, so name concrete, applicable
    techniques — not a genre label or a theme."""


class StoryPlan(WeightedPlan):
    """Plan of a single story; its weight allocates the chapter's expected word count."""

    description: str
    """1-2 sentences stating this story's narrative beat: the situation its scenes will dramatize,
    the characters involved, and what changes by the end. It is shown when planning the story's
    scenes, so name the concrete events to stage rather than restating the chapter."""

    writing_style: str = ""
    """1-3 sentences stating the writing style its scenes should share: a consistent voice, tone,
    and technique across the story's scenes. Empty when the chapter's style already suffices."""


class ChapterPlan(WeightedPlan):
    """Plan of a single chapter; its weight allocates the novel's expected word count."""

    description: str
    """1-2 sentences stating what concretely happens in this chapter: which storyline advances,
    the key event or reversal, and where it leaves the characters. Focus on the chapter's own
    arc — it is shown when planning the chapter's stories, so name the events that stage it."""

    writing_style: str = ""
    """2-3 sentences stating the writing style its stories should follow: the chapter's narrative
    voice, tone, and pacing. Empty when the novel's style already suffices."""


class NovelPlan(SketchedAble, Titled, Described, WordCount):
    """Plan of the novel itself: metadata only, chapters are planned separately."""

    description: str
    """2-4 sentences stating the novel's premise: who the protagonist is, what they want, the
    central conflict blocking them, and the stakes. Convey genre and tone. This description
    seeds every chapter's planning prompt, so be specific and evocative, never a tagline."""

    writing_style: str = ""
    """4-5 sentences stating the novel's overall writing style: narrative voice, tone, rhythm,
    and recurring techniques. It seeds the style guidance of every chapter, story, and scene;
    empty when the outline implies no particular style."""

    series_bible: SeriesBible = Field(default_factory=SeriesBible)


class ScenePlans(JSONList[ScenePlan]):
    """A bare JSON array of scene plans as the LLM returns it."""


class StoryPlans(JSONList[StoryPlan]):
    """A bare JSON array of story plans as the LLM returns it."""


class ChapterPlans(JSONList[ChapterPlan]):
    """A bare JSON array of chapter plans as the LLM returns it."""
