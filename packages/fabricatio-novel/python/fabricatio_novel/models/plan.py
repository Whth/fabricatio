"""Flat per-element plan models and LLM list-parsing helpers."""

import json
from typing import Any, Callable, Generic, Self, TypeVar

from pydantic import BaseModel, Field, PositiveFloat, RootModel

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core import CONFIG, TEMPLATE_MANAGER
from fabricatio_core.models.generic import Described, SketchedAble, Titled
from fabricatio_core.rust import TextCapturer
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


_T = TypeVar("_T")

_CODE_BLOCK = TextCapturer.capture_code_block()


class JSONList(SketchedAble, RootModel[list[_T]], Generic[_T]):  # pyright: ignore[reportGeneralTypeIssues]
    """A bare JSON array of models as the LLM returns it, optionally wrapped in a code fence.

    The SketchedAble machinery supplies the create-JSON prompt and display
    sides; :meth:`instantiate_from_string` unwraps an optional code fence via
    the core capturer before validating, so raw model responses parse without
    any manual cleanup. The element type may itself be a list (per-child
    slices).
    """

    @classmethod
    def instantiate_from_string(cls, string: str) -> Self | None:
        """Instantiate the list from a raw model response, unwrapping an optional code fence."""
        inner = _CODE_BLOCK.cap1(string)
        return cls.model_validate_json(inner if inner is not None else string)


_P = TypeVar("_P", bound=BaseModel)


def json_list_question(requirement: str, list_type: type[JSONList[Any]]) -> str:
    """Build the create-JSON prompt for a bare JSON array described by the list type."""
    return TEMPLATE_MANAGER.render_template(
        CONFIG.templates.create_json_obj_template,
        {
            "requirement": requirement,
            "json_schema": json.dumps(list_type.model_json_schema(), indent=2),
        },
    )


def plan_list_question(requirement: str, plan_type: type[_P]) -> str:
    """Build the create-JSON prompt for a bare array of plans (mirrors create_json_prompt)."""
    return json_list_question(requirement, JSONList[plan_type])


def plan_list_validator(plan_type: type[_P]) -> Callable[[str], list[_P] | None]:
    """Build a validator that parses a bare JSON array into a list of plans."""

    def _validate(string: str) -> list[_P] | None:
        parsed = JSONList[plan_type].instantiate_from_string(string)
        return parsed.root if parsed is not None else None

    return _validate
