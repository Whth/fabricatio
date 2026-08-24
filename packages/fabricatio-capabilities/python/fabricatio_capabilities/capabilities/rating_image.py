"""Image rating capability using a vision-capable LLM.

Mirrors :class:`Rating.rate` but attaches an image to the completion request.
Routing defaults to the ``VISION`` variant slot (see :data:`fabricatio_core.rust.VISION`),
which the variant system resolves to the configured image-understanding model;
pass ``send_to=...`` explicitly to steer elsewhere.
"""

from abc import ABC
from asyncio import gather
from pathlib import Path
from typing import Unpack, overload

from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER, VISION
from fabricatio_core.utils import ok

from fabricatio_capabilities.capabilities.rating import Rating
from fabricatio_capabilities.config import capabilities_config
from fabricatio_capabilities.utils import build_rating_model


class RatingImage(Rating, ABC):
    """Capability that rates images against criteria via a vision-capable LLM."""

    @overload
    async def rate_image(
        self,
        image: Path,
        topic: str,
        criteria: set[str],
        manual: dict[str, str] | None = None,
        score_range: tuple[float, float] = (0.0, 1.0),
        send_to: str | None = VISION,
        **kwargs: Unpack[LLMKwargs],
    ) -> dict[str, float] | None: ...

    @overload
    async def rate_image(
        self,
        image: list[Path],
        topic: str,
        criteria: set[str],
        manual: dict[str, str] | None = None,
        score_range: tuple[float, float] = (0.0, 1.0),
        send_to: str | None = VISION,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[dict[str, float] | None]: ...

    async def rate_image(
        self,
        image: Path | list[Path],
        topic: str,
        criteria: set[str],
        manual: dict[str, str] | None = None,
        score_range: tuple[float, float] = (0.0, 1.0),
        send_to: str | None = VISION,
        **kwargs: Unpack[LLMKwargs],
    ) -> dict[str, float] | list[dict[str, float] | None] | None:
        """Rate attached image(s) against each criterion in the rating manual.

        When *manual* is not provided, one is drafted from the topic and criteria
        via the LLM (falling back to identity descriptions when drafting fails).

        Args:
            image: Path to the image file to attach, or a list of paths to rate
                independently (one request per image — the router broadcasts a
                shared ``images`` list to every message, so per-image requests
                are issued instead).  This method owns the ``images`` attachment;
                do not pass ``images=`` here.
            topic: The topic related to the task.
            criteria: A set of criteria for rating.
            manual: A dictionary containing the rating criteria.  If not provided,
                then this method will draft the criteria automatically.
            score_range: A tuple representing the valid score range. Defaults to (0.0, 1.0).
            send_to: Routing-group variant for the LLM call; defaults to the
                ``VISION`` slot so the configured vision model is used.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            The ratings for each criterion; ``None`` when the model failed to
            produce a valid rating within the validation budget.  A single path
            yields ``dict | None``, a list of paths yields a list of the same.
        """
        manual = (
            manual
            or await self.draft_rating_manual(topic, criteria, send_to=send_to, **kwargs)
            or dict(zip(criteria, criteria, strict=True))
        )

        min_score, max_score = score_range
        model = build_rating_model(ok(manual), min_score, max_score)
        rendered = TEMPLATE_MANAGER.render_template(
            capabilities_config.rate_image_template,
            {"topic": topic, "criteria": sorted(criteria), "min_score": min_score, "max_score": max_score},
        )

        async def _inner(img: Path) -> dict[str, float] | None:
            res = await self.propose(model, rendered, send_to=send_to, images=[img.read_bytes()], **kwargs)
            return None if res is None else res.model_dump()

        if isinstance(image, list):
            return list(await gather(*(_inner(img) for img in image)))
        return await _inner(image)
