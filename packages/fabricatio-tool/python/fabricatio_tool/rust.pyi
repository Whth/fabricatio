"""Rust bindings for the Rust API of fabricatio-tool."""

from typing import List, Literal, Optional, Set

class CheckConfig:
    def __init__(self, targets: Set[str], mode: Literal["whitelist", "blacklist"]) -> None:
        """Initialize a CheckConfig instance with specified targets and mode.

        Args:
            targets (Set[str]): A set of target items to be checked.
            mode (str): The checking mode, either 'whitelist' or 'blacklist'.

        Raises:
            RuntimeError: If the provided mode is neither 'whitelist' nor 'blacklist'.
        """
        ...

def gather_violations(
    source: str,
    modules: Optional[CheckConfig] = None,
    imports: Optional[CheckConfig] = None,
    calls: Optional[CheckConfig] = None,
) -> List[str]:
    """Gather violations from the given Python source code based on check configurations.

    Args:
        source (str): The Python source code to analyze.
        modules (Optional[CheckConfig]): Configuration for module checks.
        imports (Optional[CheckConfig]): Configuration for import checks.
        calls (Optional[CheckConfig]): Configuration for function call checks.

    Returns:
        List[str]: A list of violation messages found in the source code.
    """
