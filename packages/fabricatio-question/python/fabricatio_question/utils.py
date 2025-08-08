"""Utility functions for asking questions."""

from typing import List, Optional, overload


@overload
async def ask_retain[V](candidates: List[str]) -> List[str]: ...


@overload
async def ask_retain[V](candidates: List[str], value_mapping: List[V]) -> List[V]: ...


async def ask_retain[V](candidates: List[str], value_mapping: Optional[List[V]] = None) -> List[str] | List[V]:
    """Asks the user to retain a list of candidates."""
    from questionary import Choice, checkbox

    return await checkbox(
        "Please choose those that should be retained.",
        choices=[Choice(p, value=p, checked=True) for p in candidates]
        if value_mapping is None
        else [Choice(p, value=v, checked=True) for p, v in zip(candidates, value_mapping, strict=True)],
    ).ask_async()


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
