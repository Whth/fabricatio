"""Decorators for confirming before executing a function."""

from asyncio import iscoroutinefunction
from functools import wraps
from inspect import signature
from typing import Callable, Coroutine, Optional

from fabricatio_core import logger


def confirm_to_execute[**P, R](
    func: Callable[P, R],
) -> Callable[P, Optional[R]] | Callable[P, Coroutine[None, None, Optional[R]]]:
    """Decorator to confirm before executing a function.

    Args:
        func (Callable): The function to be executed

    Returns:
        Callable: A decorator that wraps the function to confirm before execution.
    """
    from questionary import confirm

    if iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[R]:
            if await confirm(
                f"Are you sure to execute function: {func.__name__}{signature(func)} \n📦 Args:{args}\n🔑 Kwargs:{kwargs}\n",
                instruction="Please input [Yes/No] to proceed (default: Yes):",
            ).ask_async():
                return await func(*args, **kwargs)
            logger.warn(f"Function: {func.__name__}{signature(func)} canceled by user.")
            return None

        return _async_wrapper

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[R]:
        if confirm(
            f"Are you sure to execute function: {func.__name__}{signature(func)} \n📦 Args:{args}\n🔑 Kwargs:{kwargs}\n",
            instruction="Please input [Yes/No] to proceed (default: Yes):",
        ).ask():
            return func(*args, **kwargs)
        logger.warn(f"Function: {func.__name__}{signature(func)} canceled by user.")
        return None

    return _wrapper
