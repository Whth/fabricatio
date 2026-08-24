"""Image rating capability using a vision-capable LLM.

Mirrors :class:`Rating.rate` but attaches an image to the completion request.
Routing defaults to the ``VISION`` variant slot (see :data:`fabricatio_core.rust.VISION`),
which the variant system resolves to the configured image-understanding model;
pass ``send_to=...`` explicitly to steer elsewhere.
"""

from abc import ABC
from pathlib import Path
from typing import Unpack

from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER, VISION
from fabricatio_core.utils import ok

from fabricatio_capabilities.capabilities.rating import Rating
from fabricatio_capabilities.config import capabilities_config
from fabricatio_capabilities.utils import build_rating_model


class RatingImage(Rating, ABC):
    """Capability that rates images against criteria via a vision-capable LLM."""

    async def rate_image(
        self,
        image: str | Path,
        topic: str,
        criteria: set[str],
        manual: dict[str, str] | None = None,
        score_range: tuple[float, float] = (0.0, 1.0),
        send_to: str | None = VISION,
        **kwargs: Unpack[LLMKwargs],
    ) -> dict[str, float] | None:
        """Rate a single attached image against each criterion in the rating manual.

        When *manual* is not provided, one is drafted from the topic and criteria
        via the LLM (falling back to identity descriptions when drafting fails).

        Args:
            image: Path to the image file to attach to the request.  This method
                owns the ``images`` attachment — do not pass ``images=`` here.
            topic: The topic related to the task.
            criteria: A set of criteria for rating.
            manual: A dictionary containing the rating criteria.  If not provided,
                then this method will draft the criteria automatically.
            score_range: A tuple representing the valid score range. Defaults to (0.0, 1.0).
            send_to: Routing-group variant for the LLM call; defaults to the
                ``VISION`` slot so the configured vision model is used.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Dict[str, float]: The ratings for each criterion, or ``None`` when the
                model failed to produce a valid rating within the validation budget.
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

        res = await self.propose(
            model,
            rendered,
            send_to=send_to,
            images=[Path(image).read_bytes()],
            **kwargs,
        )
        return None if res is None else res.model_dump()
