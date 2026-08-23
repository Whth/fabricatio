"""Module for the Ordering class which provides functionalities to order sequences based on requirements."""

from typing import Any, TypeGuard, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.generic import WithBriefing
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK
from more_itertools.more import duplicates_everseen

from fabricatio_capabilities.capabilities.rating import Rating
from fabricatio_capabilities.config import capabilities_config
from fabricatio_capabilities.models.kwargs_types import CompositeScoreKwargs, OrderStringKwargs


def is_list_str(sq: Any) -> TypeGuard[list[str]]:
    """Check if the input is a list of strings.

    Args:
        sq (Any): Input to be validated.

    Returns:
        TypeGuard[List[str]]: True if input is a list of strings, False otherwise.
    """
    return isinstance(sq, list) and all(isinstance(s, str) for s in sq)


def is_list_briefing(sq: Any) -> TypeGuard[list[WithBriefing]]:
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
        self,
        seq: list[str],
        requirement: str,
        reverse: bool = False,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[list[str]]],
    ) -> list[str] | None:
        """Orders a list of strings based on a given requirement using a language model.

        Args:
            seq (List[str]): The input sequence to be ordered.
            requirement (str): The requirement string guiding the ordering.
            reverse (bool): Whether to reverse the order. Defaults to False.
            send_to: Routing-group variant for the LLM call. Resolved against the agent variant
                registry (see `fabricatio_core.rust`). Defaults to `TASK`; pass `SMOL`/`TINY`/`PLAN`
                to steer to a different model tier.
            **kwargs: Additional keyword arguments.

        Returns:
            List[str] | None: Ordered list of strings if successful, otherwise None.
        """
        rendered = TEMPLATE_MANAGER.render_template(
            capabilities_config.order_string_template,
            {"requirement": requirement, "reverse": reverse, "seq": seq},
        )

        logger.debug(f"Ordering sequence: \n{seq}")
        ordered_raw = await self.alist_v(rendered, value_type=str, k=len(seq), send_to=send_to, **kwargs)

        if (ordered_raw is not None) and (sorted(seq) == sorted(ordered_raw)):
            return ordered_raw
        logger.error(
            f"Ordering failed. The generated sequence is not the same as the original sequence. \n"
            f"Original sequence: {seq}\n"
            f"Generated sequence: {ordered_raw}",
        )
        return None

    async def order_briefed(
        self,
        seq: list[WithBriefing],
        requirement: str,
        send_to: str | None = TASK,
        **kwargs: Unpack[OrderStringKwargs],
    ) -> list[WithBriefing] | None:
        """Orders a list of WithBriefing objects based on a given requirement using their names for language model processing.

        This method extracts the 'name' attributes from the WithBriefing objects to form a sequence of strings,
        then utilizes the order_string method to obtain an ordered list of names. Finally, it reconstructs the
        ordered list using the original WithBriefing objects.

        Args:
            seq (List[WithBriefing]): The input sequence of WithBriefing objects to be ordered.
            requirement (str): The requirement string guiding the ordering.
            send_to: Routing-group variant for the LLM call. Resolved against the agent variant
                registry (see `fabricatio_core.rust`). Defaults to `TASK`; pass `SMOL`/`TINY`/`PLAN`
                to steer to a different model tier.
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
            send_to=send_to,
            **kwargs,
        )
        if ordered_names is None:
            return None
        mapping = {s.name: s for s in seq}
        return [mapping[n] for n in ordered_names]

    @overload
    async def order(
        self,
        seq: list[str],
        requirement: str,
        send_to: str | None = TASK,
        **kwargs: Unpack[OrderStringKwargs],
    ) -> list[str] | None: ...

    @overload
    async def order(
        self,
        seq: list[WithBriefing],
        requirement: str,
        send_to: str | None = TASK,
        **kwargs: Unpack[OrderStringKwargs],
    ) -> list[WithBriefing] | None: ...

    async def order(
        self,
        seq: list[str] | list[WithBriefing],
        requirement: str,
        send_to: str | None = TASK,
        **kwargs: Unpack[OrderStringKwargs],
    ) -> list[str] | list[WithBriefing] | None:
        """Orders a sequence of either strings or WithBriefing objects based on a requirement.

        Args:
            seq (List[str] | List[WithBriefing]): Input sequence to be ordered.
            requirement (str): Requirement guiding the ordering.
            send_to: Routing-group variant for the LLM call. Resolved against the agent variant
                registry (see `fabricatio_core.rust`). Defaults to `TASK`; pass `SMOL`/`TINY`/`PLAN`
                to steer to a different model tier.
            **kwargs: Keyword arguments for further customization.

        Returns:
            None | List[str] | List[WithBriefing]: Ordered sequence or None if invalid input.
        """
        if is_list_str(seq):
            return await self.order_string(seq, requirement, send_to=send_to, **kwargs)
        if is_list_briefing(seq):
            return await self.order_briefed(seq, requirement, send_to=send_to, **kwargs)
        raise ValueError("The sequence must be a list of strings or a list of WithBriefing objects.")

    @overload
    async def order_rated(
        self,
        seq: list[str],
        reverse: bool = False,
        send_to: str | None = TASK,
        **kwargs: Unpack[CompositeScoreKwargs],
    ) -> list[str] | None: ...

    @overload
    async def order_rated(
        self,
        seq: list[WithBriefing],
        reverse: bool = False,
        send_to: str | None = TASK,
        **kwargs: Unpack[CompositeScoreKwargs],
    ) -> list[WithBriefing] | None: ...

    async def order_rated(
        self,
        seq: list[str] | list[WithBriefing],
        reverse: bool = False,
        send_to: str | None = TASK,
        **kwargs: Unpack[CompositeScoreKwargs],
    ) -> list[str] | list[WithBriefing] | None:
        """Orders a sequence based on composite scores calculated from their briefings or content.

        Args:
            seq (List[str] | List[WithBriefing]): Sequence to rate and order.
            reverse (bool): Whether to reverse the sorting order. Defaults to False.
            send_to: Routing-group variant for the LLM call. Resolved against the agent variant
                registry (see `fabricatio_core.rust`). Defaults to `TASK`; pass `SMOL`/`TINY`/`PLAN`
                to steer to a different model tier.
            **kwargs: Arguments for score calculation.

        Returns:
            None | List[str] | List[WithBriefing]: Ordered sequence based on scores.
        """
        to_rate: list[str] = [s.briefing for s in seq] if is_list_briefing(seq) else seq  # pyright: ignore [reportAssignmentType]

        scores = await self.composite_score(to_rate=to_rate, send_to=send_to, **kwargs)
        # order the sequence by the scores
        sorted_pack = sorted(zip(seq, scores, strict=False), key=lambda x: x[1], reverse=reverse)
        return [s[0] for s in sorted_pack]  # pyright: ignore [reportReturnType]
