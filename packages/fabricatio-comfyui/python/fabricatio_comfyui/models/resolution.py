"""Megapixel + aspect-ratio canvas sizing for ComfyUI generations.

Raw pixel ``width``/``height`` knobs are replaced by two discrete,
LLM-friendly inputs: a total megapixel budget (``mp``) and an
aspect-ratio preset (:class:`Prop`).  :func:`resolve_canvas` derives the
concrete latent canvas from them, snapped to the 64px grid ComfyUI
models expect.
"""

from enum import StrEnum, auto
from math import floor, sqrt

__all__ = ["Prop", "resolve_canvas"]

_GRID = 64
"""Dimension snapping grid in pixels (ComfyUI latents expect 64-multiples)."""

_MIN_DIM = 64
"""Smallest canvas side in pixels, so degenerate budgets stay valid."""

_PIXELS_PER_MP = 1_000_000
"""Pixel count of one megapixel."""


_PARTS: dict[str, tuple[int, int]] = {
    "prop_1_1": (1, 1),
    "prop_4_3": (4, 3),
    "prop_3_4": (3, 4),
    "prop_3_2": (3, 2),
    "prop_2_3": (2, 3),
    "prop_16_9": (16, 9),
    "prop_9_16": (9, 16),
    "prop_5_4": (5, 4),
    "prop_4_5": (4, 5),
    "prop_21_9": (21, 9),
    "prop_9_21": (9, 21),
}
"""Aspect-ratio ``(width, height)`` parts keyed by member name, resolved on demand."""


class Prop(StrEnum):
    """Aspect-ratio presets offered to callers and LLM tool schemas.

    Members are declared with :func:`auto`, so the member name doubles as
    the value: ``Prop("prop_16_9")`` and ``Prop["prop_16_9"]`` both fetch
    the member, and pydantic coerces the same strings natively.  The
    width/height parts live in the module-level :data:`_PARTS` table and
    are resolved on demand.
    """

    prop_1_1 = auto()
    prop_4_3 = auto()
    prop_3_4 = auto()
    prop_3_2 = auto()
    prop_2_3 = auto()
    prop_16_9 = auto()
    prop_9_16 = auto()
    prop_5_4 = auto()
    prop_4_5 = auto()
    prop_21_9 = auto()
    prop_9_21 = auto()

    def w(self) -> int:
        """Return the width part of this preset."""
        return _PARTS[self.name][0]

    def h(self) -> int:
        """Return the height part of this preset."""
        return _PARTS[self.name][1]

    def ratio(self) -> float:
        """Return the width/height ratio of this preset."""
        return self.w() / self.h()

    def canvas(
        self,
        *,
        mp: float | None = None,
        base: tuple[int, int],
        scale: float = 1.0,
    ) -> tuple[int, int]:
        """Return the latent canvas ``(width, height)`` this preset sizes from *base*.

        A given *mp* replaces the total pixel area (divided by
        ``scale**2`` for templates that upscale after the base pass);
        without it the template's own area is kept.  Both sides snap to
        the nearest multiple of 64 (half-up), clamped to at least 64.

        Raises:
            ValueError: when *mp* is not positive or *scale* is not positive.
        """
        return _snap_by_ratio(_area(mp=mp, base=base, scale=scale), self.ratio())


def resolve_canvas(
    *,
    mp: float | None = None,
    prop: Prop | str | None = None,
    base: tuple[int, int],
    scale: float = 1.0,
) -> tuple[int, int]:
    """Compute a base latent canvas ``(width, height)`` from an image budget and an aspect preset.

    The canvas starts from the active workflow template's *base*
    dimensions; a given *mp* replaces the total **final-image** pixel
    area and a given *prop* replaces the aspect ratio.  Templates that
    upscale the base canvas before their refine pass pass their linear
    *scale* factor, so the base canvas carries ``mp / scale**2`` and the
    finished image lands at the megapixel budget.  Each side is then
    snapped to the nearest multiple of 64 (half-up), clamped to at least
    64.  Knobs left unset keep the template's side of the equation, so a
    partial override (only a budget, only a ratio) sizes relative to the
    template's default canvas.

    Args:
        mp: Megapixel budget of the finished image (``1.0`` = 1,000,000 pixels).
        prop: Aspect preset as a :class:`Prop` member or its value (e.g. ``"prop_16_9"``).
        base: The template canvas to size from when a knob is missing.
        scale: Linear upscale factor the template applies after the base canvas
            (``1.0`` when the workflow has no upscale step).  Used only when *mp*
            is given.

    Raises:
        ValueError: when *mp* is not positive, *scale* is not positive, or *prop*
            names no preset.

    Examples:
        >>> resolve_canvas(mp=1.0, prop=Prop.prop_1_1, base=(768, 512))
        (1024, 1024)
        >>> resolve_canvas(mp=1.0, prop=Prop.prop_1_1, base=(768, 512), scale=2.3)
        (448, 448)
        >>> resolve_canvas(prop="prop_16_9", base=(768, 512))  # keeps the 0.39 MP area
        (832, 448)
    """
    if prop is None:
        base_w, base_h = base
        return _snap_by_ratio(_area(mp=mp, base=base, scale=scale), base_w / base_h)
    return Prop(prop).canvas(mp=mp, base=base, scale=scale)


def _snap(value: float) -> int:
    """Round *value* to the nearest :data:`_GRID` multiple (half-up), clamped to :data:`_MIN_DIM`."""
    return max(_MIN_DIM, floor(value / _GRID + 0.5) * _GRID)


def _area(mp: float | None, base: tuple[int, int], scale: float) -> float:
    """Return the pixel budget of the base canvas: the template area, or *mp* rescaled by *scale*."""
    if mp is None:
        area = float(base[0] * base[1])
    elif scale <= 0:
        raise ValueError(f"scale must be positive, got {scale!r}")
    else:
        area = mp * _PIXELS_PER_MP / (scale * scale)
    if area <= 0:
        raise ValueError(f"mp must be positive, got {mp!r}")
    return area


def _snap_by_ratio(area: float, ratio: float) -> tuple[int, int]:
    """Snap an *area* at aspect *ratio* to the 64px grid."""
    return _snap(sqrt(area * ratio)), _snap(sqrt(area / ratio))
