"""Decorators for Fabricatio."""

from asyncio import iscoroutinefunction
from functools import wraps
from inspect import signature
from shutil import which
from types import ModuleType
from typing import Callable, List, Optional

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


def confirm_to_execute[**P, R](func: Callable[P, R]) -> Callable[P, Optional[R]] | Callable[P, R]:
    """Decorator to confirm before executing a function.

    Args:
        func (Callable): The function to be executed

    Returns:
        Callable: A decorator that wraps the function to confirm before execution.
    """
    if not configs.general.confirm_on_ops:
        # Skip confirmation if the configuration is set to False
        return func

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
                f"Are you sure to execute function: {func.__name__}{signature(func)} \n📦 Args:{args}\n��� Kwargs:{kwargs}\n",
                instruction="Please input [Yes/No] to proceed (default: Yes):",
            ).ask():
                return func(*args, **kwargs)
            logger.warning(f"Function: {func.__name__}{signature(func)} canceled by user.")
            return None

    return _wrapper


def use_temp_module[**P, R](modules: ModuleType | List[ModuleType]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Temporarily inject modules into sys.modules during function execution.

    This decorator allows you to temporarily inject one or more modules into sys.modules
    while the decorated function executes. After execution, it restores the original
    state of sys.modules.

    Args:
        modules (ModuleType | List[ModuleType]): A single module or list of modules to
            temporarily inject into sys.modules.

    Returns:
        Callable[[Callable[P, R]], Callable[P, R]]: A decorator that handles temporary
            module injection.

    Examples:
        ```python
        from types import ModuleSpec, ModuleType, module_from_spec

        # Create a temporary module
        temp_module = module_from_spec(ModuleSpec("temp_math", None))
        temp_module.pi = 3.14

        # Use the decorator to temporarily inject the module
        @use_temp_module(temp_module)
        def calculate_area(radius: float) -> float:
            from temp_math import pi
            return pi * radius ** 2

        # The temp_module is only available inside the function
        result = calculate_area(5.0)  # Uses temp_module.pi
        ```

        Multiple modules can also be injected:
        ```python
        module1 = module_from_spec(ModuleSpec("mod1", None))
        module2 = module_from_spec(ModuleSpec("mod2", None))

        @use_temp_module([module1, module2])
        def process_data():
            import mod1, mod2
            # Work with temporary modules
            ...
        ```
    """
    module_list = [modules] if isinstance(modules, ModuleType) else modules

    def _decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            import sys

            # Store original modules if they exist
            for module in module_list:
                if module.__name__ in sys.modules:
                    raise RuntimeError(
                        f"Module '{module.__name__}' is already present in sys.modules and cannot be overridden."
                    )
                sys.modules[module.__name__] = module

            try:
                return func(*args, **kwargs)
            finally:
                # Restore original state
                for module in module_list:
                    del sys.modules[module.__name__]

        return _wrapper

    return _decorator


def logging_exec_time[**P, R](func: Callable[P, R]) -> Callable[P, R]:
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
            result = await func(*args, **kwargs)
            logger.debug(f"Execution time of `{func.__name__}`: {time() - start_time:.2f} s")
            return result

        return _async_wrapper

    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time()
        result = func(*args, **kwargs)
        logger.debug(f"Execution time of {func.__name__}: {(time() - start_time) * 1000:.2f} ms")
        return result

    return _wrapper
