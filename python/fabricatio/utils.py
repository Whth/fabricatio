"""A collection of utility functions for the fabricatio package."""

from typing import Any, Dict, List, Mapping, Optional, overload

from fabricatio.decorators import precheck_package


@precheck_package(
    "questionary", "'questionary' is required to run this function. Have you installed `fabricatio[qa]`?."
)
async def ask_edit(text_seq: List[str]) -> List[str]:
    """Asks the user to edit a list of texts.

    Args:
        text_seq (List[str]): A list of texts to be edited.

    Returns:
        List[str]: A list of edited texts.
        If the user does not edit a text, it will not be included in the returned list.
    """
    from questionary import text

    res = []
    for i, t in enumerate(text_seq):
        edited = await text(f"[{i}] ", default=t).ask_async()
        if edited:
            res.append(edited)
    return res


@overload
async def ask_retain[V](candidates: List[str]) -> List[str]: ...


@overload
async def ask_retain[V](candidates: List[str], value_mapping: List[V]) -> List[V]: ...


@precheck_package(
    "questionary", "'questionary' is required to run this function. Have you installed `fabricatio[qa]`?."
)
async def ask_retain[V](candidates: List[str], value_mapping: Optional[List[V]] = None) -> List[str] | List[V]:
    """Asks the user to retain a list of candidates."""
    from questionary import Choice, checkbox

    return await checkbox(
        "Please choose those that should be retained.",
        choices=[Choice(p, value=p, checked=True) for p in candidates]
        if value_mapping is None
        else [Choice(p, value=v, checked=True) for p, v in zip(candidates, value_mapping, strict=True)],
    ).ask_async()


def override_kwargs(kwargs: Mapping[str, Any], **overrides) -> Dict[str, Any]:
    """Override the values in kwargs with the provided overrides."""
    new_kwargs = dict(kwargs.items())
    new_kwargs.update(overrides)
    return new_kwargs


def fallback_kwargs(kwargs: Mapping[str, Any], **fallbacks) -> Dict[str, Any]:
    """Fallback the values in kwargs with the provided fallbacks."""
    new_kwargs = dict(kwargs.items())
    new_kwargs.update({k: v for k, v in fallbacks.items() if k not in new_kwargs})
    return new_kwargs


def ok[T](val: Optional[T], msg: str = "Value is None") -> T:
    """Check if a value is None and raise a ValueError with the provided message if it is.

    Args:
        val: The value to check.
        msg: The message to include in the ValueError if val is None.

    Returns:
        T: The value if it is not None.
    """
    if val is None:
        raise ValueError(msg)
    return val


def wrapp_in_block(string: str, title: str, style: str = "-") -> str:
    """Wraps a string in a block with a title.

    Args:
        string: The string to wrap.
        title: The title of the block.
        style: The style of the block.

    Returns:
        str: The wrapped string.
    """
    return f"--- Start of {title} ---\n{string}\n--- End of {title} ---".replace("-", style)
