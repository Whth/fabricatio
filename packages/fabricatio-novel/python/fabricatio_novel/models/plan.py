"""Flat per-element plan models and LLM list-parsing helpers."""

import json
from typing import Callable, TypeVar

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core import CONFIG, TEMPLATE_MANAGER
from fabricatio_core.models.generic import Described, SketchedAble, Titled
from pydantic import BaseModel, Field, TypeAdapter

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


_P = TypeVar("_P", bound=BaseModel)


def plan_list_question(requirement: str, plan_type: type[_P]) -> str:
    """Build the create-JSON prompt for a bare array of plans (mirrors create_json_prompt)."""
    schema = TypeAdapter(list[plan_type]).json_schema()
    return TEMPLATE_MANAGER.render_template(
        CONFIG.templates.create_json_obj_template,
        {
            "requirement": requirement,
            "json_schema": json.dumps(schema, indent=2),
        },
    )


def plan_list_validator(plan_type: type[_P]) -> Callable[[str], list[_P] | None]:
    """Build a validator that parses a bare JSON array into a list of plans."""
    adapter = TypeAdapter(list[plan_type])

    def _validate(string: str) -> list[_P] | None:
        lines = string.strip().splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return adapter.validate_json("\n".join(lines))

    return _validate
