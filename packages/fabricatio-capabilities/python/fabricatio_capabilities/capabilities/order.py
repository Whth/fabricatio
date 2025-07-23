"""Module for the Ordering class which provides functionalities to order sequences based on requirements."""

from typing import Any, List, TypeGuard, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.generic import WithBriefing
from fabricatio_core.models.kwargs_types import ValidateKwargs
from more_itertools.more import duplicates_everseen

from fabricatio_capabilities.capabilities.rating import Rating
from fabricatio_capabilities.config import capabilities_config
from fabricatio_capabilities.models.kwargs_types import CompositeScoreKwargs, OrderStringKwargs


def is_list_str(sq: Any) -> TypeGuard[List[str]]:
    """Check if the input is a list of strings.

    Args:
        sq (Any): Input to be validated.

    Returns:
        TypeGuard[List[str]]: True if input is a list of strings, False otherwise.
    """
    return isinstance(sq, list) and all(isinstance(s, str) for s in sq)


def is_list_briefing(sq: Any) -> TypeGuard[List[WithBriefing]]:
    """Check if the input is a list of WithBriefing objects.

    Args:
        sq (Any): Input to be validated.

    Returns:
        TypeGuard[List[WithBriefing]]: True if input is a list of WithBriefing objects, False otherwise.
    """
    return isinstance(sq, list) and all(isinstance(s, WithBriefing) for s in sq)


class Ordering(Rating):
    """Class providing methods to order sequences either directly via language model or by scores."""

    async def order_string(
        self, seq: List[str], requirement: str, reverse: bool = False, **kwargs: Unpack[ValidateKwargs[List[str]]]
    ) -> List[str] | None:
        """Orders a list of strings based on a given requirement using a language model.

        Args:
            seq (List[str]): The input sequence to be ordered.
            requirement (str): The requirement string guiding the ordering.
            reverse (bool): Whether to reverse the order. Defaults to False.
            **kwargs: Additional keyword arguments.

        Returns:
            List[str] | None: Ordered list of strings if successful, otherwise None.
        """
        rendered = TEMPLATE_MANAGER.render_template(
            capabilities_config.order_string_template, {"requirement": requirement, "reverse": reverse, "seq": seq}
        )

        logger.debug(f"Ordering sequence: \n{seq}")
        ordered_raw = await self.alist_str(rendered, k=len(seq), **kwargs)

        if (ordered_raw is not None) and (sorted(seq) == sorted(ordered_raw)):
            return ordered_raw
        logger.error(
            f"Ordering failed. The generated sequence is not the same as the original sequence. \n"
            f"Original sequence: {seq}\n"
            f"Generated sequence: {ordered_raw}"
        )
        return None

    async def order_briefed(
        self, seq: List[WithBriefing], requirement: str, **kwargs: Unpack[OrderStringKwargs]
    ) -> List[WithBriefing] | None:
        """Orders a list of WithBriefing objects based on a given requirement using their names for language model processing.

        This method extracts the 'name' attributes from the WithBriefing objects to form a sequence of strings,
        then utilizes the order_string method to obtain an ordered list of names. Finally, it reconstructs the
        ordered list using the original WithBriefing objects.

        Args:
            seq (List[WithBriefing]): The input sequence of WithBriefing objects to be ordered.
            requirement (str): The requirement string guiding the ordering.
            **kwargs: Additional keyword arguments unpacked and passed to the order_string method.

        Returns:
            List[WithBriefing] | None: Ordered list of WithBriefing objects if successful, otherwise None.
        """
        if dup := list(duplicates_everseen(seq)):
            raise ValueError(f"Duplicate names found in the sequence: {dup}")

        ordered_names = await self.order_string(
            [s.name for s in seq],
            TEMPLATE_MANAGER.render_template(
                capabilities_config.order_briefed_template,
                {
                    "requirement": requirement,
                    "with_briefings": [{"name": s.name, "briefing": s.briefing} for s in seq],
                },
            ),
            **kwargs,
        )
        if ordered_names is None:
            return None
        mapping = {s.name: s for s in seq}
        return [mapping[n] for n in ordered_names]

    @overload
    async def order(
        self, seq: List[str], requirement: str, **kwargs: Unpack[OrderStringKwargs]
    ) -> List[str] | None: ...

    @overload
    async def order(
        self, seq: List[WithBriefing], requirement: str, **kwargs: Unpack[OrderStringKwargs]
    ) -> List[WithBriefing] | None: ...

    async def order(
        self, seq: List[str] | List[WithBriefing], requirement: str, **kwargs: Unpack[OrderStringKwargs]
    ) -> None | List[str] | List[WithBriefing]:
        """Orders a sequence of either strings or WithBriefing objects based on a requirement.

        Args:
            seq (List[str] | List[WithBriefing]): Input sequence to be ordered.
            requirement (str): Requirement guiding the ordering.
            **kwargs: Keyword arguments for further customization.

        Returns:
            None | List[str] | List[WithBriefing]: Ordered sequence or None if invalid input.
        """
        if is_list_str(seq):
            return await self.order_string(seq, requirement, **kwargs)
        if is_list_briefing(seq):
            return await self.order_briefed(seq, requirement, **kwargs)
        raise ValueError("The sequence must be a list of strings or a list of WithBriefing objects.")

    @overload
    async def order_rated(
        self, seq: List[str], reverse: bool = False, **kwargs: Unpack[CompositeScoreKwargs]
    ) -> List[str] | None: ...

    @overload
    async def order_rated(
        self, seq: List[WithBriefing], reverse: bool = False, **kwargs: Unpack[CompositeScoreKwargs]
    ) -> List[WithBriefing] | None: ...

    async def order_rated(
        self, seq: List[str] | List[WithBriefing], reverse: bool = False, **kwargs: Unpack[CompositeScoreKwargs]
    ) -> None | List[str] | List[WithBriefing]:
        """Orders a sequence based on composite scores calculated from their briefings or content.

        Args:
            seq (List[str] | List[WithBriefing]): Sequence to rate and order.
            reverse (bool): Whether to reverse the sorting order. Defaults to False.
            **kwargs: Arguments for score calculation.

        Returns:
            None | List[str] | List[WithBriefing]: Ordered sequence based on scores.
        """
        to_rate: List[str] = [s.briefing for s in seq] if is_list_briefing(seq) else seq  # pyright: ignore [reportAssignmentType]

        scores = await self.composite_score(to_rate=to_rate, **kwargs)
        # order the sequence by the scores
        sorted_pack = sorted(zip(seq, scores, strict=False), key=lambda x: x[1], reverse=reverse)
        return [s[0] for s in sorted_pack]  # pyright: ignore [reportReturnType]
