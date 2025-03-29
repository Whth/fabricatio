"""A collection of utility functions for the fabricatio package."""

from typing import Dict, List, Optional

from questionary import text


async def ask_edit(
    text_seq: List[str],
) -> List[str]:
    """Asks the user to edit a list of texts.

    Args:
        text_seq (List[str]): A list of texts to be edited.

    Returns:
        List[str]: A list of edited texts.
        If the user does not edit a text, it will not be included in the returned list.
    """
    res = []
    for i, t in enumerate(text_seq):
        edited = await text(f"[{i}] ", default=t).ask_async()
        if edited:
            res.append(edited)
    return res


def override_kwargs[T](kwargs: Dict[str, T], **overrides) -> Dict[str, T]:
    """Override the values in kwargs with the provided overrides."""
    kwargs.update({k: v for k, v in overrides.items() if v is not None})
    return kwargs


def fallback_kwargs[T](kwargs: Dict[str, T], **overrides) -> Dict[str, T]:
    """Fallback the values in kwargs with the provided overrides."""
    kwargs.update({k: v for k, v in overrides.items() if k not in kwargs})
    return kwargs


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
