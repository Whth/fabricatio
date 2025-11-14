"""A collection of utility functions for the fabricatio package."""

from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from fabricatio_core.rust import extras_satisfied


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


def cfg(feats: Sequence[str], pkg_name: Optional[str] = None) -> None:
    """Configure the package based on the provided manifest and features.

    If any module in `manifest` is missing, raises ModuleNotFoundError with
    ready-to-run installation commands for both pip and uv.

    Automatically converts '_' to '-' in package name to match PyPI naming convention.

    Example:
        Missing dependencies. Please install with:
          pip install my-novel-pkg[workflow,debug]
          uv add "my-novel-pkg[workflow,debug]"

    Args:
        feats: Extra feature names required (e.g., ["workflow", "debug"]).
        pkg_name: Optional package name, defaults to detected source package name
    Raises:
        ModuleNotFoundError: If any module is not found.
    """
    pkg_name = (pkg_name or get_source_pkgname()).replace("_", "-")
    if not extras_satisfied(pkg_name, feats):
        raise ModuleNotFoundError(build_install_msg(feats, pkg_name))


def build_install_msg(feats: Iterable[str], pkg: Optional[str] = None) -> str:
    """Builds an installation message for missing modules with pip and uv commands.

    Args:
        feats: Iterable of feature names required
        pkg: Optional package name, defaults to detected source package name

    Returns:
        str: Formatted error message with installation instructions for both pip and uv
    """
    pkg = pkg or get_source_pkgname()

    # Build features string
    feat_str = ",".join(feats) if feats else ""
    extras = f"[{feat_str}]" if feat_str else ""

    # Generate commands
    pip_cmd = f"pip install {pkg}{extras}"
    uv_cmd = f"uv pip install {pkg}{extras}"

    # Build error message
    msg = f"Module imports failed for {pkg} because of missing dependencies.\nYou may install them with one of the following commands:\n  with pip: {pip_cmd}\n  with uv: {uv_cmd}"

    if pkg == "unknown":
        msg += (
            "\n\nNote: Package name could not be auto-detected. "
            "Replace 'unknown' with the correct package name (PyPI names use hyphens, e.g., 'my-package')."
        )
    return msg


def get_source_pkgname(depth: int = 2) -> str:
    """Get the top-level package name from a module at the given call stack depth.

    Attempts to automatically detect the package name by inspecting the caller's
    module information at the specified depth. Converts underscores to hyphens
    to match PyPI naming convention. Returns 'unknown' if package name cannot be determined.

    Args:
        depth (int): The number of frames to go back in the call stack.
                     Depth 1 means the immediate caller, 2 is the caller's caller, etc.
                     Must be >= 1.

    Returns:
        str: The detected top-level package name or 'unknown' as fallback.
    """
    import inspect

    frame = inspect.currentframe()

    # Traverse up the call stack 'depth' times
    for _ in range(depth):
        if frame is None:
            break
        frame = frame.f_back

    if frame is None:
        return "unknown"

    mod = inspect.getmodule(frame)
    if mod is None:
        return "unknown"

    try:
        pkg = mod.__name__.split(".")[0]
    except AttributeError:
        pkg = "unknown"

    return pkg


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


def wrap_in_block(string: str, title: str, style: str = "-") -> str:
    """Wraps a string in a block with a title.

    Args:
        string: The string to wrap.
        title: The title of the block.
        style: The style of the block.

    Returns:
        str: The wrapped string.
    """
    return f"--- Start of {title} ---\n{string}\n--- End of {title} ---".replace("-", style)
