"""A collection of utility functions for the fabricatio package."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from questionary import text

if TYPE_CHECKING:
    from fabricatio.models.generic import WithBriefing


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


def prepend_sys_msg[D: (Dict[str, Any], str)](with_briefing: "WithBriefing", system_msg_like: D = "") -> Dict[str, Any]:
    """Prepend the system message with the briefing.

    Args:
        with_briefing (WithBriefing): The object with the briefing.
        system_msg_like (str | dict): The system message or a dictionary containing the system message.

    Returns:
        dict: The system message with the briefing prepended.
    """
    match system_msg_like:
        case dict(d):
            d["system_message"] = f"# your personal briefing: \n{with_briefing.briefing}\n{d.get('system_message', '')}"
            return d
        case str(s):
            return {"system_message": f"# your personal briefing: \n{with_briefing.briefing}\n{s}"}
        case _:
            raise TypeError(f"{system_msg_like} is not a dict or str")
