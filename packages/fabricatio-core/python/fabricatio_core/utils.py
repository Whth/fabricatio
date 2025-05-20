"""A collection of utility functions for the fabricatio package."""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Type, overload

from fabricatio_core.decorators import precheck_package


def is_subclass_of_base(cls: Type, base_module: str, base_name: str) -> bool:
    """Determines if the given class is a subclass of an unimported base class.

    Args:
        cls: The class to check
        base_module: The module name of the base class
        base_name: The class name of the base class

    Returns:
        bool: True if cls is a subclass of the specified base class, False otherwise
    """
    return any(ancestor.__module__ == base_module and ancestor.__name__ == base_name for ancestor in cls.__mro__)


def is_subclass_of_any_base(cls: Type, bases: List[Tuple[str, str]]) -> bool:
    """Determines if the given class is a subclass of the candidate base classes.

    Args:
        cls: The class to check
        bases: A list of tuples where each tuple contains (module_name, class_name)

    Returns:
        bool: True if cls is a subclass of the specified base classes, False otherwise
    """
    for ancestor in cls.__mro__:
        for base_module, base_name in bases:
            if ancestor.__module__ == base_module and ancestor.__name__ == base_name:
                return True
    return False


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


def first_available[T](iterable: Iterable[T], msg: str = "No available item found in the iterable.") -> T:
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
