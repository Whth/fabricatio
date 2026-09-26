"""The scene refusal guard: the settings a refusal is judged by, and the error it ends in.

A model that declines a scene answers with a few hundred characters of policy prose
instead of the scene. Measured on a real refused run, those replies came back at
0.15-0.78 of the scene's word budget while every composed scene ran 1.03-2.11, so
the guard reads the shortfall first and asks a judge only where the ratio leaves the
question open.
"""

from fabricatio_core.models.generic import ScopedConfig

__all__ = ["SceneRefusalScopedConfig", "SceneRefusedError"]


class SceneRefusalScopedConfig(ScopedConfig):
    """Per-instance refusal-guard settings with hierarchical fallback.

    Every field defaults to ``None`` (unset at this scope) and resolves through the
    global ``[ext.novel] scene_refusal_*``: a role that judges its scenes by other
    numbers sets the field, an unset one reads the package default.
    """

    refusal_ratio_floor: float | None = None
    """word count satisfaction below which a reply is a refusal without asking a judge; unset reads the global floor."""

    refusal_ratio_accept: float | None = None
    """word count satisfaction at or above which a reply is prose without asking a judge; unset reads the global accept."""

    refusal_max_retries: int | None = None
    """how many times a refused scene is asked again before the run fails; unset reads the global retries."""


class SceneRefusedError(RuntimeError):
    """Raised when every attempt at one scene read as a refusal.

    A refusal is not prose. Serializing one would put policy text into the chapter,
    into the prefix log every later scene reads, and into the EPUB, with nothing
    downstream to flag it — so the run fails instead, naming the scene and how far
    short of its budget the reply fell.
    """
