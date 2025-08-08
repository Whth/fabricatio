"""A collection of utility functions for the fabricatio package."""

from typing import Any, Dict, Iterable, Mapping, Optional


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


def first_available[T](iterable: Iterable[Optional[T]], msg: str = "No available item found in the iterable.") -> T:
    """Return the first available item in the iterable that's not None.

    This function searches through the provided iterable and returns the first
    item that is not None. If all items are None or the iterable is empty,
    it raises a ValueError.

    Args:
        iterable: The iterable collection to search through.
        msg: The message to include in the ValueError if no non-None item is found.

    Returns:
        T: The first non-None item found in the iterable.
        If no non-None item is found, it raises a ValueError.

    Raises:
        ValueError: If no non-None item is found in the iterable.

    Examples:
        >>> first_available([None, None, "value", "another"])
        'value'
        >>> first_available([1, 2, 3])
        1
        >>> assert (first_available([None, None]))
        ValueError: No available item found in the iterable.
    """
    if (first := next((item for item in iterable if item is not None), None)) is not None:
        return first
    raise ValueError(msg)


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
