"""A module that provides functionality to rate tasks based on a rating manual and score range."""

from asyncio import gather
from typing import Dict, List, Optional, Set, Tuple, Union, Unpack, overload

import orjson
from fabricatio import JsonCapture, template_manager
from fabricatio.config import configs
from fabricatio.models.generic import WithBriefing
from fabricatio.models.kwargs_types import ValidateKwargs
from fabricatio.models.usages import LLMUsage
from pydantic import NonNegativeInt


class GiveRating(WithBriefing, LLMUsage):
    """A class that provides functionality to rate tasks based on a rating manual and score range."""

    async def rate_fine_grind(
        self,
        to_rate: str,
        rating_manual: Dict[str, str],
        score_range: Tuple[float, float],
        **kwargs: Unpack[ValidateKwargs],
    ) -> Dict[str, float]:
        """Rate a given string based on a rating manual and score range.

        Args:
            to_rate: The string to be rated.
            rating_manual: A dictionary containing the rating criteria.
            score_range: A tuple representing the valid score range.
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A dictionary with the ratings for each dimension.
        """

        def _validator(response: str) -> Dict[str, float] | None:
            if (
                (json_data := JsonCapture.convert_with(response, orjson.loads)) is not None
                and isinstance(json_data, dict)
                and json_data.keys() == rating_manual.keys()
                and all(isinstance(v, float) for v in json_data.values())
                and all(score_range[0] <= v <= score_range[1] for v in json_data.values())
            ):
                return json_data
            return None

        return await self.aask_validate(
            question=(
                template_manager.render_template(
                    configs.templates.rate_fine_grind_template,
                    {
                        "to_rate": to_rate,
                        "min_score": score_range[0],
                        "max_score": score_range[1],
                        "rating_manual": rating_manual,
                    },
                )
            ),
            validator=_validator,
            system_message=f"# your personal briefing: \n{self.briefing}",
            **kwargs,
        )

    @overload
    async def rate(
        self,
        to_rate: str,
        topic: str,
        criteria: Set[str],
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> Dict[str, float]: ...

    @overload
    async def rate(
        self,
        to_rate: List[str],
        topic: str,
        criteria: Set[str],
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> List[Dict[str, float]]: ...

    async def rate(
        self,
        to_rate: Union[str, List[str]],
        topic: str,
        criteria: Set[str],
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> Union[Dict[str, float], List[Dict[str, float]]]:
        """Rate a given string or a sequence of strings based on a topic, dimensions, and score range.

        Args:
            to_rate: The string or sequence of strings to be rated.
            topic: The topic related to the task.
            criteria: A set of dimensions for rating.
            score_range: A tuple representing the valid score range
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A dictionary with the ratings for each dimension if a single string is provided,
            or a list of dictionaries with the ratings for each dimension if a sequence of strings is provided.
        """
        manual = await self.draft_rating_manual(topic, criteria, **kwargs)
        if isinstance(to_rate, str):
            return await self.rate_fine_grind(to_rate, manual, score_range, **kwargs)
        if isinstance(to_rate, list):
            return await gather(*[self.rate_fine_grind(item, manual, score_range, **kwargs) for item in to_rate])
        raise ValueError("to_rate must be a string or a list of strings")

    async def draft_rating_manual(
        self, topic: str, criteria: Set[str], **kwargs: Unpack[ValidateKwargs]
    ) -> Dict[str, str]:
        """Drafts a rating manual based on a topic and dimensions.

        Args:
            topic: The topic for the rating manual.
            criteria: A set of dimensions for the rating manual.
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A dictionary representing the drafted rating manual.
        """

        def _validator(response: str) -> Dict[str, str] | None:
            if (
                (json_data := JsonCapture.convert_with(response, orjson.loads)) is not None
                and isinstance(json_data, dict)
                and json_data.keys() == criteria
                and all(isinstance(v, str) for v in json_data.values())
            ):
                return json_data
            return None

        return await self.aask_validate(
            question=(
                template_manager.render_template(
                    configs.templates.draft_rating_manual_template,
                    {
                        "topic": topic,
                        "criteria": criteria,
                    },
                )
            ),
            validator=_validator,
            system_message=f"# your personal briefing: \n{self.briefing}",
            **kwargs,
        )

    async def draft_rating_criteria(
        self,
        topic: str,
        criteria_count: NonNegativeInt = 0,
        examples: Optional[List[str]] = None,
        **kwargs: Unpack[ValidateKwargs],
    ) -> Set[str]:
        """Drafts rating dimensions based on a topic.

        Args:
            topic: The topic for the rating dimensions.
            criteria_count: The number of dimensions to draft, 0 means no limit.
            examples: A list of examples which is rated based on the rating dimensions.
            **kwargs: Additional keyword arguments for the LLM usage.

        Returns:
            A set of rating dimensions.
        """

        def _validator(response: str) -> Set[str] | None:
            if (
                (json_data := JsonCapture.convert_with(response, orjson.loads)) is not None
                and isinstance(json_data, list)
                and all(isinstance(v, str) for v in json_data)
                and (criteria_count == 0 or len(json_data) == criteria_count)
            ):
                return set(json_data)
            return None

        return await self.aask_validate(
            question=(
                template_manager.render_template(
                    configs.templates.draft_rating_criteria_template,
                    {
                        "topic": topic,
                        "examples": examples,
                        "dimensions_count": criteria_count,
                    },
                )
            ),
            validator=_validator,
            system_message=f"# your personal briefing: \n{self.briefing}",
            **kwargs,
        )
