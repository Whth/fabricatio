"""Decorators for Fabricatio."""

from functools import wraps
from inspect import signature
from shutil import which
from typing import Callable, Optional

from questionary import confirm

from fabricatio.config import configs
from fabricatio.journal import logger


def depend_on_external_cmd[**P, R](
    bin_name: str, install_tip: Optional[str], homepage: Optional[str] = None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to check for the presence of an external command.

    Args:
        bin_name (str): The name of the required binary.
        install_tip (Optional[str]): Installation instructions for the required binary.
        homepage (Optional[str]): The homepage of the required binary.

    Returns:
        Callable[[Callable[P, R]], Callable[P, R]]: A decorator that wraps the function to check for the binary.

    Raises:
        RuntimeError: If the required binary is not found.
    """

    def _decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if which(bin_name) is None:
                err = f"`{bin_name}` is required to run {func.__name__}{signature(func)}, please install it the to `PATH` first."
                if install_tip is not None:
                    err += f"\nInstall tip: {install_tip}"
                if homepage is not None:
                    err += f"\nHomepage: {homepage}"
                logger.error(err)
                raise RuntimeError(err)
            return func(*args, **kwargs)

        return _wrapper

    return _decorator


def confirm_to_execute[**P, R](func: Callable[P, R]) -> Callable[P, Optional[R]] | Callable[P, R]:
    """Decorator to confirm before executing a function.

    Args:
        func (Callable): The function to be executed

    Returns:
        Callable: A decorator that wraps the function to confirm before execution.
    """
    if not configs.general.confirm_on_fs_ops:
        # Skip confirmation if the configuration is set to False
        return func

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[R]:
        if confirm(
            f"Are you sure to execute function: {func.__name__}{signature(func)} \n📦 Args:{args}\n🔑 Kwargs:{kwargs}\n",
            instruction="Please input [Yes/No] to proceed (default: Yes):",
        ).ask():
            return func(*args, **kwargs)
        logger.warning(f"Function: {func.__name__}{signature(func)} canceled by user.")
        return None

    return _wrapper
