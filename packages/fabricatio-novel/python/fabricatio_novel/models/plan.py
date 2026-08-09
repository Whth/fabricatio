"""Flat per-element plan models and LLM list-parsing helpers."""

import json
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field, TypeAdapter, PositiveFloat

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core import CONFIG, TEMPLATE_MANAGER
from fabricatio_core.models.generic import Described, SketchedAble, Titled
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


_P = TypeVar("_P", bound=BaseModel)


def json_list_question(requirement: str, adapter: TypeAdapter[Any]) -> str:
    """Build the create-JSON prompt for a bare JSON array described by the adapter."""
    return TEMPLATE_MANAGER.render_template(
        CONFIG.templates.create_json_obj_template,
        {
            "requirement": requirement,
            "json_schema": json.dumps(adapter.json_schema(), indent=2),
        },
    )


def plan_list_question(requirement: str, plan_type: type[_P]) -> str:
    """Build the create-JSON prompt for a bare array of plans (mirrors create_json_prompt)."""
    return json_list_question(requirement, TypeAdapter(list[plan_type]))


def strip_code_fence(string: str) -> str:
    """Remove an optional wrapping code fence from a model response."""
    lines = string.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def plan_list_validator(plan_type: type[_P]) -> Callable[[str], list[_P] | None]:
    """Build a validator that parses a bare JSON array into a list of plans."""
    adapter = TypeAdapter(list[plan_type])

    def _validate(string: str) -> list[_P] | None:
        return adapter.validate_json(strip_code_fence(string))

    return _validate
