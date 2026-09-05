"""Megapixel + aspect-ratio canvas sizing for ComfyUI generations.

Raw pixel ``width``/``height`` knobs are replaced by two discrete,
LLM-friendly inputs: a total megapixel budget (``mp``) and an
aspect-ratio preset (:class:`Prop`).  :func:`resolve_canvas` derives the
concrete latent canvas from them, snapped to the 64px grid ComfyUI
models expect.
"""

import re
from enum import StrEnum
from math import floor, sqrt
from typing import Self

__all__ = ["Prop", "resolve_canvas"]

_GRID = 64
"""Dimension snapping grid in pixels (ComfyUI latents expect 64-multiples)."""

_MIN_DIM = 64
"""Smallest canvas side in pixels, so degenerate budgets stay valid."""

_PIXELS_PER_MP = 1_000_000
"""Pixel count of one megapixel."""


class Prop(StrEnum):
    """Aspect-ratio presets offered to callers and LLM tool schemas.

    Values are the human-readable ``"w:h"`` forms; member names carry
    the ``prop_<w>_<h>`` spelling.  Both spellings construct a member:
    ``Prop("16:9")`` and ``Prop.of("prop_16_9")`` yield
    :attr:`prop_16_9`.
    """

    prop_1_1 = "1:1"
    prop_4_3 = "4:3"
    prop_3_4 = "3:4"
    prop_3_2 = "3:2"
    prop_2_3 = "2:3"
    prop_16_9 = "16:9"
    prop_9_16 = "9:16"
    prop_5_4 = "5:4"
    prop_4_5 = "4:5"
    prop_21_9 = "21:9"
    prop_9_21 = "9:21"

    @property
    def ratio(self) -> float:
        """Return the width/height ratio of this preset."""
        w, h = (int(part) for part in self.value.split(":"))
        return w / h

    @classmethod
    def of(cls, value: str) -> Self:
        """Resolve a ``"16:9"``-style value or a ``prop_16_9``-style name to a member.

        Accepts configuration values in either spelling so TOML keys do
        not need to name enum members exactly.

        Raises:
            ValueError: when *value* matches no preset.
        """
        if value in cls._value2member_map_:
            return cls(value)
        match = re.fullmatch(r"prop_(\d+)_(\d+)", value)
        if match is not None:
            candidate = f"{match.group(1)}:{match.group(2)}"
            if candidate in cls._value2member_map_:
                return cls(candidate)
        raise ValueError(f"Unknown aspect ratio {value!r}; choose one of {', '.join(m.value for m in cls)}")


def resolve_canvas(
    *,
    mp: float | None = None,
    prop: Prop | str | None = None,
    base: tuple[int, int],
) -> tuple[int, int]:
    """Compute a latent canvas ``(width, height)`` from a megapixel budget and an aspect preset.

    The canvas starts from the active workflow template's *base*
    dimensions; a given *mp* replaces the total pixel area and a given
    *prop* replaces the aspect ratio.  Each side is then snapped to the
    nearest multiple of 64 (half-up), clamped to at least 64.  Knobs
    left unset keep the template's side of the equation, so a partial
    override (only a budget, only a ratio) sizes relative to the
    template's default canvas.

    Args:
        mp: Megapixel budget (``1.0`` = 1,000,000 pixels).
        prop: Aspect preset as a :class:`Prop` member, a ``"16:9"`` value, or a
            ``prop_16_9`` name.
        base: The template canvas to size from when a knob is missing.

    Raises:
        ValueError: when *mp* is not positive, or *prop* names no preset.

    Examples:
        >>> resolve_canvas(mp=1.0, prop=Prop.prop_1_1, base=(768, 512))
        (1024, 1024)
        >>> resolve_canvas(prop="16:9", base=(768, 512))  # keeps the 0.39 MP area
        (832, 448)
    """
    base_w, base_h = base
    area = float(base_w * base_h) if mp is None else float(mp) * _PIXELS_PER_MP
    if area <= 0:
        raise ValueError(f"mp must be positive, got {mp!r}")
    if prop is None:
        ratio = base_w / base_h
    elif isinstance(prop, str):
        ratio = Prop.of(prop).ratio
    else:
        ratio = prop.ratio
    return _snap(sqrt(area * ratio)), _snap(sqrt(area / ratio))


def _snap(value: float) -> int:
    """Round *value* to the nearest :data:`_GRID` multiple (half-up), clamped to :data:`_MIN_DIM`."""
    return max(_MIN_DIM, floor(value / _GRID + 0.5) * _GRID)
