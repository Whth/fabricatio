"""A collection of utility functions for the fabricatio package."""

from typing import Any, Dict, List, Mapping, Optional


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
    from questionary import text

    res = []
    for i, t in enumerate(text_seq):
        edited = await text(f"[{i}] ", default=t).ask_async()
        if edited:
            res.append(edited)
    return res


def override_kwargs(kwargs: Mapping[str, Any], **overrides) -> Dict[str, Any]:
    """Override the values in kwargs with the provided overrides."""
    new_kwargs = dict(kwargs.items())
    new_kwargs.update({k: v for k, v in overrides.items() if v is not None})
    return new_kwargs


def fallback_kwargs(kwargs: Mapping[str, Any], **overrides) -> Dict[str, Any]:
    """Fallback the values in kwargs with the provided overrides."""
    new_kwargs = dict(kwargs.items())
    new_kwargs.update({k: v for k, v in overrides.items() if k not in new_kwargs and v is not None})
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


def wrapp_in_block(string: str, title: str) -> str:
    """Wraps a string in a block with a title.

    Args:
        string: The string to wrap.
        title: The title of the block.

    Returns:
        str: The wrapped string.
    """
    return f"--- Start of {title} ---\n{string}\n--- End of {title} ---"



def replace_brackets(s: str) -> str:
    """Replace sequences within double brackets with each number wrapped in double brackets.

    This function processes a string to find sequences enclosed in double brackets (e.g., [[1, 2, 3-5]]).
    It splits these sequences by commas and hyphens, expands any ranges (e.g., 3-5 becomes 3, 4, 5),
    and wraps each number in double brackets.

    Args:
        s (str): The input string containing sequences within double brackets.

    Returns:
        str: The processed string with each number in the sequences wrapped in double brackets.
    """
    import regex
    # Find all sequences within double brackets
    matches = regex.findall(r'\[\[(.*?)\]\]', s)

    # Process each match to wrap each number in double brackets
    processed_sequences = []
    for match in matches:
        # Split the match by commas and hyphens, and strip whitespace
        parts = [part.strip() for part in regex.split(r'[,]', match)]

        numbers = []
        for part in parts:
            if '-' in part:
                # Expand the range if there's a hyphen
                start, end = map(int, part.split('-'))
                numbers.extend(str(i) for i in range(start, end + 1))
            else:
                numbers.append(part)

        # Wrap each number in double brackets
        wrapped_numbers = ''.join(f'[[{num}]]' for num in numbers)
        processed_sequences.append(wrapped_numbers)

    # Replace the original matches with the processed sequences
    for original, processed in zip(matches, processed_sequences, strict=False):
        s = s.replace(f'[[{original}]]', processed)

    return s

