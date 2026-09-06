"""Verified re-generation: render, VLM-verdict, and retry on failed verdicts.

:class:`RerenderImages` composes :class:`~fabricatio_comfyui.capabilities.comfyui.UseComfyUI`
with :class:`~fabricatio_judge.capabilities.advanced_judge.VisuallyJudge`:
each render is judged against the requested description, and a failed
verdict's :attr:`~fabricatio_judge.models.judgement.ImageVerdict.feedback`
rides the next prompt until the retry budget runs out — the best attempt
(fewest recorded reasons) wins.
"""

from dataclasses import dataclass
from pathlib import Path
from abc import ABC
from typing import Unpack

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs
from fabricatio_judge.capabilities.advanced_judge import VisuallyJudge
from fabricatio_judge.models.judgement import ImageVerdict
from fabricatio_core.journal import logger

__all__ = ["RenderAttempt", "RerenderImages"]


@dataclass(frozen=True)
class RenderAttempt:
    """One judged render: its image, prompt, verdict, and which try produced it."""

    image_path: Path
    """Local path of the rendered PNG."""

    prompt: str
    """The positive prompt the render was queued with."""

    verdict: ImageVerdict
    """The VLM verdict over the image."""

    attempts: int
    """1-based index of the try that produced this render."""

    @property
    def passed(self) -> bool:
        """Whether the verdict passed."""
        return bool(self.verdict)

    @property
    def reason_count(self) -> int:
        """Number of recorded defects; the tie-breaker for ``best`` attempts."""
        return len(self.verdict.glitch_reasons) + len(self.verdict.coherence_reasons)


class RerenderImages(UseComfyUI, VisuallyJudge, ABC):
    """Capability mixin: generate an image, judge it, and re-render on failed verdicts."""

    async def generate_verified(
        self,
        description: str,
        *,
        retries: int | None = None,
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> RenderAttempt | None:
        """Render *description* and loop render-verdict until it passes or the budget is spent.

        Args:
            description: What the image is supposed to show; also the seed of every prompt.
            retries: Regeneration budget after the first render; ``None`` uses
                :data:`fabricatio_comfyui.config.comfyui_config.verdict_max_retries`.
            download_dir: Directory receiving the PNGs; ``None`` falls back to config.
            **kwargs: Generation knobs forwarded to :meth:`UseComfyUI.generate_image`.

        Returns:
            The passing attempt, or the best-scoring attempt when every try failed —
            ``None`` only when nothing rendered at all.
        """
        budget = retries if retries is not None else comfyui_config.verdict_max_retries
        prompt = description
        best: RenderAttempt | None = None
        for attempt_no in range(1, budget + 2):  # first render + `budget` re-renders
            image_path = await self.generate_image(prompt, download_dir=download_dir, **kwargs)
            if image_path is None:
                logger.error(f"Verified generation failed at attempt {attempt_no}; aborting")
                return best
            verdict = await self.visually_judge(image_path, issue_to_judge=description)
            if verdict is None:
                logger.error(f"Image verdict unavailable at attempt {attempt_no}; aborting")
                return best
            attempt = RenderAttempt(image_path=image_path, prompt=prompt, verdict=verdict, attempts=attempt_no)
            if attempt.passed:
                logger.info(f"Verified generation passed at attempt {attempt_no}: {image_path}")
                return attempt
            if best is None or attempt.reason_count < best.reason_count:
                best = attempt
            if attempt_no > budget:
                break
            prompt = f"{description}\nFix the previous image's issues: {verdict.feedback}"
        logger.warn(f"Verified generation exhausted its budget; keeping the best attempt(s)")
        return best
