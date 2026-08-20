"""This module contains the models for the character."""

from typing import ClassVar, Dict, Self

from fabricatio_capabilities.models.generic import AsPrompt, PersistentAble
from fabricatio_core.models.generic import JSONList, Named, SketchedAble
from pydantic import Field, ValidationInfo, field_validator

from fabricatio_character.config import character_config


class CharacterCard(SketchedAble, Named, AsPrompt, PersistentAble):
    """A character as they currently are: a stable identity plus the mutable state of the moment.

    The identity fields (``name``, ``roles``, ``activated_role``, ``want``) change slowly; the state fields
    (``look``, ``act``, ``flaw``, ``where``, ``condition``, ``mood``) describe
    how the character is right now and evolve as the story progresses. All fields are
    required and non-empty; ``metric`` is an optional map of tracked numerical stats.
    """

    name: str
    """The character's identifying name (can be real name, alias, or title)."""

    roles: list[str]
    """All narrative or functional roles the character holds within the story (e.g. ``["protagonist", "mentor"]``)."""

    activated_role: str
    """The role the character is currently playing; must be one of the entries in ``roles``."""

    look: str
    """How the character currently appears: clothing, physique, distinguishing features, wounds, disguise."""

    act: str
    """How the character currently behaves: mannerisms and reactions under stress."""

    want: str
    """The character's core motivation driving their actions (slow-changing)."""

    flaw: str
    """The character's current vulnerability: weakness, moral failing, or psychological pressure."""

    where: str
    """Where the character currently is and what surrounds them: location and immediate situation."""

    condition: str
    """The character's current physical state: health, energy, injuries, resources."""

    mood: str
    """The character's current emotional state."""

    metric: dict[str, int | float] = Field(default_factory=dict)
    """Tracked numerical stats of the character (e.g. ``{"hp": 80, "reputation": 30}``).

    Entries are surfaced via :meth:`metric_prompt` and rendered into the prompt
    as inline ``name=value`` pairs when non-empty.
    """

    @field_validator("roles")
    @classmethod
    def _roles_non_empty(cls, value: list[str]) -> list[str]:
        """Reject an empty ``roles`` list so the field matches the other required-text-field convention."""
        if not value:
            raise ValueError("roles must contain at least one entry")
        return value

    @field_validator("activated_role")
    @classmethod
    def _activated_role_in_roles(cls, value: str, info: ValidationInfo) -> str:
        """Reject an ``activated_role`` that is not one of the character's roles."""
        roles = info.data.get("roles") or []
        if value not in roles:
            raise ValueError(f"activated_role '{value}' must be one of roles: {roles}")
        return value

    metric: dict[str, int | float] = Field(default_factory=dict)
    """Tracked numerical stats of the character (e.g. ``{"hp": 80, "reputation": 30}``).

    Any measurable quantity, including physical stats such as body weight or
    height. Empty when no stats are tracked; diffs merge entries instead of
    replacing the map.
    """

    rendering_template: ClassVar[str] = character_config.render_character_card_template

    def metric_prompt(self) -> str:
        """Render the tracked metrics inline as ``name=value`` pairs."""
        return ", ".join(f"{name}={value}" for name, value in self.metric.items())

    def _as_prompt_inner(self) -> Dict[str, str]:
        data = self.model_dump()
        data["metric"] = self.metric_prompt()
        return data

    def apply(self, diff: "CharacterCardDiff") -> Self:
        """Apply a character card diff to this card.

        Diff ``metric`` entries are merged into this card's metric map rather than
        replacing it, so a diff only needs to name the stats it changes.

        Returns:
            Self: A new card updated with the diff fields, excluding unset (``None``)
            values and the diff's ``reason`` field.
        """
        update = diff.model_dump(exclude_none=True, exclude={"reason"})
        if diff.metric is not None:
            update["metric"] = {**self.metric, **diff.metric}
        return self.model_copy(update=update)


class CharacterCardDiff(CharacterCard):
    """A partial character card used to express incremental updates to an existing character.

    Every field except ``reason`` is optional; only the fields that are
    set will be applied.
    """

    name: str | None = None
    """The character's identifying name (can be real name, alias, or title)."""

    roles: list[str] | None = None
    """Replace the character's roles list wholesale; entries are not merged."""

    activated_role: str | None = None
    """Replace the currently activated role; must be one of the post-apply roles."""

    look: str | None = None
    """How the character currently appears: clothing, physique, distinguishing features, wounds, disguise."""

    act: str | None = None
    """How the character currently behaves: mannerisms and reactions under stress."""

    def model_dump(self, **kwargs) -> dict:
        """Serialize this card with ``exclude_none=True`` by default so unset fields are dropped."""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def _as_prompt_inner(self) -> Dict[str, str]:
        data = self.model_dump()
        if self.metric is not None:
            data["metric"] = self.metric_prompt()
        return data

    want: str | None = None
    """The character's core motivation driving their actions (slow-changing)."""

    flaw: str | None = None
    """The character's current vulnerability: weakness, moral failing, or psychological pressure."""

    where: str | None = None
    """Where the character currently is and what surrounds them: location and immediate situation."""

    condition: str | None = None
    """The character's current physical state: health, energy, injuries, resources."""

    mood: str | None = None
    """The character's current emotional state."""

    metric: dict[str, int | float] | None = None
    """Numerical stats changed in this step (e.g. ``{"hp": 60, "weight_kg": 61}``); entries merge into the card."""

    reason: str
    """Reason why the change happen"""


class CharacterCardDiffs(JSONList[CharacterCardDiff]):
    """A bare JSON array of character-card diffs as the LLM returns it."""


class CharacterCardBoundaries(JSONList[list[CharacterCard]]):
    """A bare JSON array of per-character boundary card lists as the LLM returns it.

    One inner list per roster character, in roster order; each inner list
    carries the character's state at every element boundary except the
    parent's start and end, which the parent span already fixes.
    """
