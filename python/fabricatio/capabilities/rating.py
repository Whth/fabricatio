"""A module that provides functionality to rate tasks based on a rating manual and score range."""

from itertools import permutations
from random import sample
from typing import Dict, List, Optional, Set, Tuple, Union, Unpack, overload

from more_itertools import flatten, windowed
from pydantic import Field, NonNegativeInt, PositiveInt, create_model

from fabricatio.capabilities.propose import Propose
from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.generic import Display, ProposedAble
from fabricatio.models.kwargs_types import CompositeScoreKwargs, ValidateKwargs
from fabricatio.parser import JsonCapture
from fabricatio.rust_instances import TEMPLATE_MANAGER
from fabricatio.utils import fallback_kwargs, ok, override_kwargs


class Rating(Propose):
    """A class that provides functionality to rate tasks based on a rating manual and score range.

    References:
        Lu X, Li J, Takeuchi K, et al. AHP-powered LLM reasoning for multi-criteria evaluation of open-ended responses[A/OL]. arXiv, 2024. DOI: 10.48550/arXiv.2410.01246.
    """

    async def rate_fine_grind(
        self,
        to_rate: str | List[str],
        rating_manual: Dict[str, str],
        score_range: Tuple[float, float],
        **kwargs: Unpack[ValidateKwargs[Dict[str, float]]],
    ) -> Dict[str, float] | List[Dict[str, float]] | List[Optional[Dict[str, float]]] | None:
        """Rate a given string based on a rating manual and score range.

        Args:
            to_rate (str): The string to be rated.
            rating_manual (Dict[str, str]): A dictionary containing the rating criteria.
            score_range (Tuple[float, float]): A tuple representing the valid score range.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Dict[str, float]: A dictionary with the ratings for each dimension.
        """
        min_score, max_score = score_range
        tip = (max_score - min_score) / 9

        model = create_model(  # pyright: ignore [reportCallIssue]
            "RatingResult",
            __base__=ProposedAble,
            __doc__=f"The rating result contains the scores against each criterion, with min_score={min_score} and max_score={max_score}.",
            **{  # pyright: ignore [reportArgumentType]
                criterion: (
                    float,
                    Field(
                        ge=min_score,
                        le=max_score,
                        description=desc,
                        examples=[round(min_score + tip * i, 2) for i in range(10)],
                    ),
                )
                for criterion, desc in rating_manual.items()
            },
        )

        res = await self.propose(
            model,
            TEMPLATE_MANAGER.render_template(
                configs.templates.rate_fine_grind_template,
                {"to_rate": to_rate, "min_score": min_score, "max_score": max_score},
            )
            if isinstance(to_rate, str)
            else [
                TEMPLATE_MANAGER.render_template(
                    configs.templates.rate_fine_grind_template,
                    {"to_rate": t, "min_score": min_score, "max_score": max_score},
                )
                for t in to_rate
            ],
            **override_kwargs(kwargs, default=None),
        )
        default = kwargs.get("default")
        if isinstance(res, list):
            return [r.model_dump() if r else default for r in res]
        if res is None:
            return default
        return res.model_dump()

    @overload
    async def rate(
        self,
        to_rate: str,
        topic: str,
        criteria: Set[str],
        manual: Optional[Dict[str, str]] = None,
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> Dict[str, float]: ...

    @overload
    async def rate(
        self,
        to_rate: List[str],
        topic: str,
        criteria: Set[str],
        manual: Optional[Dict[str, str]] = None,
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> List[Dict[str, float]]: ...

    async def rate(
        self,
        to_rate: Union[str, List[str]],
        topic: str,
        criteria: Set[str],
        manual: Optional[Dict[str, str]] = None,
        score_range: Tuple[float, float] = (0.0, 1.0),
        **kwargs: Unpack[ValidateKwargs],
    ) -> Dict[str, float] | List[Dict[str, float]] | List[Optional[Dict[str, float]]] | None:
        """Rate a given string or a sequence of strings based on a topic, criteria, and score range.

        Args:
            to_rate (Union[str, List[str]]): The string or sequence of strings to be rated.
            topic (str): The topic related to the task.
            criteria (Set[str]): A set of criteria for rating.
            manual (Optional[Dict[str, str]]): A dictionary containing the rating criteria. If not provided, then this method will draft the criteria automatically.
            score_range (Tuple[float, float], optional): A tuple representing the valid score range. Defaults to (0.0, 1.0).
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Union[Dict[str, float], List[Dict[str, float]]]: A dictionary with the ratings for each criterion if a single string is provided,
            or a list of dictionaries with the ratings for each criterion if a sequence of strings is provided.
        """
        manual = (
            manual
            or await self.draft_rating_manual(topic, criteria, **override_kwargs(kwargs, default=None))
            or dict(zip(criteria, criteria, strict=True))
        )

        return await self.rate_fine_grind(to_rate, manual, score_range, **fallback_kwargs(kwargs, co_extractor={}))

    async def draft_rating_manual(
        self, topic: str, criteria: Optional[Set[str]] = None, **kwargs: Unpack[ValidateKwargs[Dict[str, str]]]
    ) -> Optional[Dict[str, str]]:
        """Drafts a rating manual based on a topic and dimensions.

        Args:
            topic (str): The topic for the rating manual.
            criteria (Optional[Set[str]], optional): A set of criteria for the rating manual. If not specified, then this method will draft the criteria automatically.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Dict[str, str]: A dictionary representing the drafted rating manual.
        """

        def _validator(response: str) -> Dict[str, str] | None:
            if (
                (json_data := JsonCapture.validate_with(response, target_type=dict, elements_type=str)) is not None
                and json_data.keys() == criteria
                and all(isinstance(v, str) for v in json_data.values())
            ):
                return json_data
            return None

        criteria = criteria or await self.draft_rating_criteria(topic, **override_kwargs(dict(kwargs), default=None))

        if criteria is None:
            logger.error(f"Failed to draft rating criteria for topic {topic}")
            return None

        return await self.aask_validate(
            question=(
                TEMPLATE_MANAGER.render_template(
                    configs.templates.draft_rating_manual_template,
                    {
                        "topic": topic,
                        "criteria": list(criteria),
                    },
                )
            ),
            validator=_validator,
            **kwargs,
        )

    async def draft_rating_criteria(
        self,
        topic: str,
        criteria_count: NonNegativeInt = 0,
        **kwargs: Unpack[ValidateKwargs[Set[str]]],
    ) -> Optional[Set[str]]:
        """Drafts rating dimensions based on a topic.

        Args:
            topic (str): The topic for the rating dimensions.
            criteria_count (NonNegativeInt, optional): The number of dimensions to draft, 0 means no limit. Defaults to 0.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Set[str]: A set of rating dimensions.
        """
        return await self.aask_validate(
            question=(
                TEMPLATE_MANAGER.render_template(
                    configs.templates.draft_rating_criteria_template,
                    {
                        "topic": topic,
                        "criteria_count": criteria_count,
                    },
                )
            ),
            validator=lambda resp: set(out)
            if (out := JsonCapture.validate_with(resp, list, str, criteria_count)) is not None
            else out,
            **kwargs,
        )

    async def draft_rating_criteria_from_examples(
        self,
        topic: str,
        examples: List[str],
        m: NonNegativeInt = 0,
        reasons_count: PositiveInt = 2,
        criteria_count: PositiveInt = 5,
        **kwargs: Unpack[ValidateKwargs],
    ) -> Optional[Set[str]]:
        """Asynchronously drafts a set of rating criteria based on provided examples.

        This function generates rating criteria by analyzing examples and extracting reasons for comparison,
        then further condensing these reasons into a specified number of criteria.

        Parameters:
            topic (str): The subject topic for the rating criteria.
            examples (List[str]): A list of example texts to analyze.
            m (NonNegativeInt, optional): The number of examples to sample from the provided list. Defaults to 0 (no sampling).
            reasons_count (PositiveInt, optional): The number of reasons to extract from each pair of examples. Defaults to 2.
            criteria_count (PositiveInt, optional): The final number of rating criteria to draft. Defaults to 5.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for validation.

        Returns:
            Set[str]: A set of drafted rating criteria.

        Warnings:
            Since this function uses pairwise comparisons, it may not be suitable for large lists of examples.
            For that reason, consider using a smaller list of examples or setting `m` to a non-zero value smaller than the length of the examples.
        """
        if m:
            examples = sample(examples, m)

        # extract reasons from the comparison of ordered pairs of extracted from examples
        reasons = flatten(
            await self.aask_validate(  # pyright: ignore [reportArgumentType]
                question=[
                    TEMPLATE_MANAGER.render_template(
                        configs.templates.extract_reasons_from_examples_template,
                        {
                            "topic": topic,
                            "first": pair[0],
                            "second": pair[1],
                            "reasons_count": reasons_count,
                        },
                    )
                    for pair in (permutations(examples, 2))
                ],
                validator=lambda resp: JsonCapture.validate_with(
                    resp, target_type=list, elements_type=str, length=reasons_count
                ),
                **kwargs,
            )
        )
        # extract certain mount of criteria from reasons according to their importance and frequency
        return await self.aask_validate(
            question=(
                TEMPLATE_MANAGER.render_template(
                    configs.templates.extract_criteria_from_reasons_template,
                    {
                        "topic": topic,
                        "reasons": list(reasons),
                        "criteria_count": criteria_count,
                    },
                )
            ),
            validator=lambda resp: set(out)
            if (out := JsonCapture.validate_with(resp, target_type=list, elements_type=str, length=criteria_count))
            else None,
            **kwargs,
        )

    async def drafting_rating_weights_klee(
        self,
        topic: str,
        criteria: Set[str],
        **kwargs: Unpack[ValidateKwargs[float]],
    ) -> Dict[str, float]:
        """Drafts rating weights for a given topic and criteria using the Klee method.

        Args:
            topic (str): The topic for the rating weights.
            criteria (Set[str]): A set of criteria for the rating weights.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Dict[str, float]: A dictionary representing the drafted rating weights for each criterion.
        """
        if len(criteria) < 2:  # noqa: PLR2004
            raise ValueError("At least two criteria are required to draft rating weights")

        criteria_seq = list(criteria)  # freeze the order
        windows = windowed(criteria_seq, 2)

        # get the importance multiplier indicating how important is second criterion compared to the first one
        relative_weights = await self.aask_validate(
            question=[
                TEMPLATE_MANAGER.render_template(
                    configs.templates.draft_rating_weights_klee_template,
                    {
                        "topic": topic,
                        "first": pair[0],
                        "second": pair[1],
                    },
                )
                for pair in windows
            ],
            validator=lambda resp: JsonCapture.validate_with(resp, target_type=float),
            **kwargs,
        )
        if not all(relative_weights):
            raise ValueError(f"found illegal weight: {relative_weights}")
        weights = [1.0]
        for rw in relative_weights:
            weights.append(weights[-1] * rw)  # pyright: ignore [reportOperatorIssue]
        total = sum(weights)
        return dict(zip(criteria_seq, [w / total for w in weights], strict=True))

    async def composite_score(
        self,
        topic: str,
        to_rate: List[str],
        criteria: Optional[Set[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        manual: Optional[Dict[str, str]] = None,
        **kwargs: Unpack[ValidateKwargs[List[Dict[str, float]]]],
    ) -> List[float]:
        """Calculates the composite scores for a list of items based on a given topic and criteria.

        Args:
            topic (str): The topic for the rating.
            to_rate (List[str]): A list of strings to be rated.
            criteria (Optional[Set[str]]): A set of criteria for the rating. Defaults to None.
            weights (Optional[Dict[str, float]]): A dictionary of rating weights for each criterion. Defaults to None.
            manual (Optional[Dict[str, str]]): A dictionary of manual ratings for each item. Defaults to None.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            List[float]: A list of composite scores for the items.
        """
        criteria = ok(
            criteria
            or await self.draft_rating_criteria_from_examples(topic, to_rate, **override_kwargs(kwargs, default=None))
        )
        weights = ok(
            weights or await self.drafting_rating_weights_klee(topic, criteria, **override_kwargs(kwargs, default=None))
        )
        logger.info(f"Criteria: {criteria}\nWeights: {weights}")
        ratings_seq = await self.rate(to_rate, topic, criteria, manual, **kwargs)

        return [sum(ratings[c] * weights[c] for c in criteria) for ratings in ratings_seq]

    @overload
    async def best(self, candidates: List[str], k: int = 1, **kwargs: Unpack[CompositeScoreKwargs]) -> List[str]: ...
    @overload
    async def best[T: Display](
        self, candidates: List[T], k: int = 1, **kwargs: Unpack[CompositeScoreKwargs]
    ) -> List[T]: ...

    async def best[T: Display](
        self, candidates: List[str] | List[T], k: int = 1, **kwargs: Unpack[CompositeScoreKwargs]
    ) -> Optional[List[str] | List[T]]:
        """Choose the best candidates from the list of candidates based on the composite score.

        Args:
            k (int): The number of best candidates to choose.
            candidates (List[str]): A list of candidates to choose from.
            **kwargs (CompositeScoreKwargs): Additional keyword arguments for the composite score calculation.

        Returns:
            List[str]: The best candidates.
        """
        if (leng := len(candidates)) == 0:
            logger.warning(f"No candidates, got {leng}, return None.")
            return None

        if leng == 1:
            logger.warning(f"Only one candidate, got {leng}, return it.")
            return candidates
        logger.info(f"Choose best {k} from {leng} candidates.")

        rating_seq = await self.composite_score(
            to_rate=[c.display() if isinstance(c, Display) else c for c in candidates], **kwargs
        )
        return [a[0] for a in sorted(zip(candidates, rating_seq, strict=True), key=lambda x: x[1], reverse=True)[:k]]  # pyright: ignore [reportReturnType]
