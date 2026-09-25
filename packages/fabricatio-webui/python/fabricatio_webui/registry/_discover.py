"""Action subclass discovery and MRO traversal."""

import importlib
import pkgutil
from collections import deque
from collections.abc import Iterator

from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action

from fabricatio_webui.discovery import installed_fabricatio_packages


def _action_module_names() -> Iterator[str]:
    """Yield every ``<pkg>.actions[.<sub>]`` module across installed packages.

    Every installed ``fabricatio_*`` distribution contributes its whole
    ``actions`` subtree, so ecosystem packages are picked up without any
    hardcoded module list.
    """
    for pkg in installed_fabricatio_packages():
        root_name = f"{pkg}.actions"
        try:
            root = importlib.import_module(root_name)
        except Exception as exc:  # noqa: BLE001 — missing optional extras must not kill discovery
            logger.debug(f"Skipped action package {root_name!r}: {exc!r}")
            continue
        yield root_name
        path = getattr(root, "__path__", None)
        if path is None:
            continue
        for info in pkgutil.walk_packages(path, prefix=f"{root_name}."):
            yield info.name


def _action_subclasses() -> Iterator[type[Action]]:
    """Breadth-first iteration over every Action subclass known to the runtime.

    The single traversal shared by concrete-class discovery and by the
    executor's name lookup: deduped, so each class is yielded exactly once.
    """
    seen: set[type[Action]] = set()
    queue: deque[type[Action]] = deque(Action.__subclasses__())

    while queue:
        cls = queue.popleft()
        if cls in seen:
            continue
        seen.add(cls)
        yield cls
        queue.extend(cls.__subclasses__())


def _is_concrete_action(cls: type[Action]) -> bool:
    """True when *cls* is an instantiable, runnable Action subclass.

    Concrete = instantiable and runnable: no abstract methods and the
    resolved ``_execute`` is a real implementation (not the abstract base
    stub).  The inherited case matters: generic bases like
    ``StoreDocuments`` implement ``_execute`` once and parameterised
    subclasses (``StoreArticleEssence``) reuse it without declaring their
    own.  Generic aliases (e.g. ``RetrieveFromPersistent[TypeVar]``) are not
    real classes; their mangled ``__name__`` gives them away.
    """
    if getattr(cls, "__abstractmethods__", None):
        return False
    if cls._execute is Action.__dict__["_execute"]:
        return False
    return "[" not in cls.__name__


def _concrete_action_subclasses() -> set[type[Action]]:
    """Recursively collect all concrete (non-abstract) Action subclasses."""
    return {cls for cls in _action_subclasses() if _is_concrete_action(cls)}


def _discover_action_modules() -> None:
    """Import every ecosystem action module so ``__subclasses__()`` sees them."""
    for mod_name in _action_module_names():
        try:
            __import__(mod_name)
        except Exception as exc:  # noqa: BLE001 — one broken third-party module must not kill boot
            logger.debug(f"Skipped action module {mod_name!r}: {exc!r}")
