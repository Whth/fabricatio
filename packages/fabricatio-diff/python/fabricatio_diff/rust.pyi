"""Rust bindings for the Rust API of fabricatio-diff."""

def rate(a: str, b: str) -> float:
    """Calculates the similarity rate between two strings using the normalized Damerau-Levenshtein distance.

    This function returns a float value between 0.0 and 1.0, where:
    - 1.0 means the strings are identical
    - 0.0 means the strings are completely different

    Args:
        a (str): The first string to compare.
        b (str): The second string to compare.

    Returns:
        float: A f64 value representing the similarity rate between the two input strings.

    Example:
        codeblock ::python

            assert rate("hello", "helo")==0.75
    """

def match_lines(haystack: str, needle: str, match_precision: float = 0.9) -> str | None:
    r"""Searches for a sequence of lines in `haystack` that approximately matches `needle`.

    This function uses the normalized Damerau-Levenshtein distance to find a matching block
    of lines with similarity score equal to or greater than `match_precision`.

    Args:
        haystack (str): The full text to search within
        needle (str): The text pattern to find within the haystack
        match_precision (float): Threshold for similarity score between 0.0 and 1.0 (default: 0.9)

    Returns:
        str | None: The first matching block of lines if found, otherwise None.

    Example:
        codeblock::python

            haystack = "Hello\\nWorld\\nRust"
            needle = "W0rld"
            matched = match_lines(haystack, needle, 0.8)
            assert matched is not None
    """

def show_diff(a: str, b: str) -> str:
    r"""Generates a unified diff between two strings showing line-level changes.

    The diff output follows unified diff format conventions where:
    - Lines prefixed with `-` indicate deletions from `a`
    - Lines prefixed with `+` indicate additions from `b`
    - Unchanged lines are prefixed with a space

    Args:
        a (str): The original/old text content
        b (str): The modified/new text content

    Returns:
        str: The diff output string with each line prefixed by its change type.

    Example:
        codeblock::python

            old_text = "Hello\\nWorld"
            new_text = "Hallo\\nWorld\\n!"
            diff = show_diff(old_text, new_text)
            assert "-Hello" in diff
            assert "+Hallo" in diff
            assert "+!" in diff
    """
