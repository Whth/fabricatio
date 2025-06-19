"""Decorators for Fabricatio."""

from asyncio import iscoroutinefunction
from functools import wraps
from importlib.util import find_spec
from inspect import signature
from shutil import which
from typing import Callable, Coroutine, Optional

from fabricatio_core.journal import logger
from fabricatio_core.rust import CONFIG


def precheck_package[**P, R](package_name: str, msg: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to check if a required package exists in the current environment before executing a function.

    This decorator ensures that a specified package is available in the environment. If the package is not found,
    it raises a `RuntimeError` with a custom error message.

    Args:
        package_name (str): The name of the package to check for existence.
        msg (str): Custom error message to be raised if the package is not found.

    Raises:
        RuntimeError: If the specified package is not found in the current environment.

    Note:
        - This decorator can be applied to both synchronous and asynchronous functions.
        - It uses `importlib.util.find_spec` internally to determine package availability.

    Returns:
        Callable[[Callable[P, R]], Callable[P, R]]: A wrapped function that performs the package check before execution.
    """

    def _wrapper(
        func: Callable[P, R] | Callable[P, Coroutine[None, None, R]],
    ) -> Callable[P, R] | Callable[P, Coroutine[None, None, R]]:
        if iscoroutinefunction(func):

            @wraps(func)
            async def _async_inner(*args: P.args, **kwargs: P.kwargs) -> R:
                if find_spec(package_name):
                    return await func(*args, **kwargs)
                raise RuntimeError(msg)

            return _async_inner

        @wraps(func)
        def _inner(*args: P.args, **kwargs: P.kwargs) -> R:
            if find_spec(package_name):
                return func(*args, **kwargs)
            raise RuntimeError(msg)

        return _inner

    return _wrapper


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


def logging_execution_info[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to log the execution of a function.

    Args:
        func (Callable): The function to be executed

    Returns:
        Callable: A decorator that wraps the function to log the execution.
    """

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.info(f"Executing function: {func.__name__}{signature(func)}")
        logger.debug(f"{func.__name__}{signature(func)}\nArgs: {args}\nKwargs: {kwargs}")
        return func(*args, **kwargs)

    return _wrapper


@precheck_package(
    "questionary", "'questionary' is required to run this function. Have you installed `fabricatio[qa]`?."
)
def confirm_to_execute[**P, R](func: Callable[P, R]) -> Callable[P, Optional[R]] | Callable[P, R]:
    """Decorator to confirm before executing a function.

    Args:
        func (Callable): The function to be executed

    Returns:
        Callable: A decorator that wraps the function to confirm before execution.
    """
    if not CONFIG.general.confirm_on_ops:
        # Skip confirmation if the configuration is set to False
        return func
    from questionary import confirm

    if iscoroutinefunction(func):

        @wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[R]:
            if await confirm(
                f"Are you sure to execute function: {func.__name__}{signature(func)} \n📦 Args:{args}\n🔑 Kwargs:{kwargs}\n",
                instruction="Please input [Yes/No] to proceed (default: Yes):",
            ).ask_async():
                return await func(*args, **kwargs)
            logger.warning(f"Function: {func.__name__}{signature(func)} canceled by user.")
            return None

    else:

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


def logging_exec_time[**P, R](
    func: Callable[P, R] | Callable[P, Coroutine[None, None, R]],
) -> Callable[P, R] | Callable[P, Coroutine[None, None, R]]:
    """Decorator to log the execution time of a function.

    Args:
        func (Callable): The function to be executed

    Returns:
        Callable: A decorator that wraps the function to log the execution time.
    """
    from time import time

    if iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start_time = time()
            logger.debug(
                f"Starting execution of {func.__name__}",
            )
            result = await func(*args, **kwargs)
            logger.debug(
                f"Execution time of `{func.__name__}`: {time() - start_time:.2f} s",
            )
            return result

        return _async_wrapper

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time()
        logger.debug(
            f"Starting execution of {func.__name__}",
        )
        result = func(*args, **kwargs)
        logger.debug(
            f"Execution time of {func.__name__}: {(time() - start_time) * 1000:.2f} ms",
        )
        return result

    return _wrapper


def once[**P, R](
    func: Callable[P, R] | Callable[P, Coroutine[None, None, R]],
) -> Callable[P, R] | Callable[P, Coroutine[None, None, R]]:
    """Decorator to ensure a function is called only once.

    Subsequent calls will return the cached result from the first call.

    Args:
        func (Callable): The function to be executed only once

    Returns:
        Callable: A decorator that wraps the function to execute it only once
    """
    _called = False
    _result = None

    if iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal _called, _result
            if not _called:
                _result = await func(*args, **kwargs)
                _called = True
            return _result

        return _async_wrapper

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        nonlocal _called, _result
        if not _called:
            _result = func(*args, **kwargs)
            _called = True
        return _result

    return _wrapper
