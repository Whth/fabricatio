"""Flat per-element plan models and their bare-JSON-array list classes."""

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, JSONList, SketchedAble, Titled
from pydantic import Field, PositiveFloat

from fabricatio_novel.models.series_book import SeriesBible


class WeightedPlan(SketchedAble, Titled, Described):
    """Plan of a single novel element: title, description, and word-count weight."""

    weight: PositiveFloat = 1.0
    """Relative importance for allocating the parent's expected word count."""


class ScenePlan(WeightedPlan):
    """Plan of a single scene; its weight allocates the story's expected word count."""


class StoryPlan(WeightedPlan):
    """Plan of a single story; its weight allocates the chapter's expected word count."""


class ChapterPlan(WeightedPlan):
    """Plan of a single chapter; its weight allocates the novel's expected word count."""


class NovelPlan(SketchedAble, Titled, Described, WordCount):
    """Plan of the novel itself: metadata only, chapters are planned separately."""

    series_bible: SeriesBible = Field(default_factory=SeriesBible)


class ScenePlans(JSONList[ScenePlan]):
    """A bare JSON array of scene plans as the LLM returns it."""


class StoryPlans(JSONList[StoryPlan]):
    """A bare JSON array of story plans as the LLM returns it."""


class ChapterPlans(JSONList[ChapterPlan]):
    """A bare JSON array of chapter plans as the LLM returns it."""
