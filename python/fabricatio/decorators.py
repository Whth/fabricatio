from functools import wraps
from shutil import which
from typing import Callable

from fabricatio.journal import logger


def depend_on_external_cmd[**P, R](bin_name: str, install_tip: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to check for the presence of an external command.

    Args:
        bin_name (str): The name of the required binary.
        install_tip (str): Installation instructions for the required binary.

    Returns:
        Callable[[Callable[P, R]], Callable[P, R]]: A decorator that wraps the function to check for the binary.

    Raises:
        RuntimeError: If the required binary is not found.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        """Decorator to wrap the function with binary presence check.

        Args:
            func (Callable[P, R]): The function to be decorated.

        Returns:
            Callable[P, R]: The wrapped function.
        """

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrapper function to check for the presence of the required binary.

            Args:
                *args: Positional arguments for the function.
                **kwargs: Keyword arguments for the function.

            Returns:
                R: The result of the function call.

            Raises:
                RuntimeError: If the required binary is not found.
            """
            if which(bin_name) is None:
                err = (
                    f"{bin_name} is required to run function: {func.__name__}, please install it first.\n{install_tip}"
                )
                logger.critical(err)
                raise RuntimeError(err)
            return func(*args, **kwargs)

        return wrapper

    return decorator
