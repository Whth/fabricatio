"""Rust bindings for the Rust API of fabricatio-tool."""
from typing import List, Set


def gather_violations(
        source: str,
        forbidden_modules: Set[str],
        forbidden_imports: Set[str],
        forbidden_calls: Set[str]
) -> List[str]:
    """Gather violations from the given Python source code.

    Args:
        source (str): The Python source code to analyze.
        forbidden_modules (Set[str]): Set of forbidden module names.
        forbidden_imports (Set[str]): Set of forbidden import names.
        forbidden_calls (Set[str]): Set of forbidden function call names.

    Returns:
        List[str]: A list of violation messages found in the source code.
    """
