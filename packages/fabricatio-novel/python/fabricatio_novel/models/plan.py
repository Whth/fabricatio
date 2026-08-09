from typing import List

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, SketchedAble, Titled
from pydantic import Field

from fabricatio_novel.models.series_book import SeriesBible


class ScenePlan(SketchedAble, Titled, Described, WordCount):
    """Plan of a single scene: title, description, expected word count."""


class StoryPlan(SketchedAble, Titled, Described, WordCount):
    """Plan of a single story (剧情段): title, description, expected word count."""


class ChapterPlan(SketchedAble, Titled, Described, WordCount):
    """Plan of a single chapter: title, description, expected word count."""


class NovelPlan(SketchedAble, Titled, Described, WordCount):
    """Plan of the novel itself: metadata only, chapters are planned separately."""

    series_bible: SeriesBible = Field(default_factory=SeriesBible)


class ChapterPlans(SketchedAble):
    """LLM response container for a novel's chapter plans."""

    chapters: List[ChapterPlan] = Field(default_factory=list)


class StoryPlans(SketchedAble):
    """LLM response container for a chapter's story plans."""

    stories: List[StoryPlan] = Field(default_factory=list)


class ScenePlans(SketchedAble):
    """LLM response container for a story's scene plans."""

    scenes: List[ScenePlan] = Field(default_factory=list)
