"""Action subclass discovery and MRO traversal."""

import importlib
import pkgutil
from collections import deque
from typing import Iterator, Set, Type

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
        except Exception:  # noqa: BLE001 — missing optional extras must not kill discovery
            continue
        yield root_name
        path = getattr(root, "__path__", None)
        if path is None:
            continue
        for info in pkgutil.walk_packages(path, prefix=f"{root_name}."):
            yield info.name


def _concrete_action_subclasses() -> Set[Type[Action]]:
    """Recursively collect all concrete (non-abstract) Action subclasses."""
    concrete: Set[Type[Action]] = set()
    seen: Set[Type[Action]] = set()

    # Use a deque so we can process breadth-first; Action itself is abstract.
    queue: deque[Type[Action]] = deque(Action.__subclasses__())

    while queue:
        cls = queue.popleft()
        if cls in seen:
            continue
        seen.add(cls)

        # Concrete = instantiable and runnable: no abstract methods and the
        # resolved _execute is a real implementation (not the abstract base
        # stub).  The inherited case matters: generic bases like
        # StoreDocuments implement _execute once and parameterised subclasses
        # (StoreArticleEssence) reuse it without declaring their own.
        is_abstract = getattr(cls, "__abstractmethods__", None)
        is_abstract_class = bool(is_abstract)
        resolves_own_execute = cls._execute is not Action.__dict__["_execute"]
        # Generic aliases (e.g. RetrieveFromPersistent[TypeVar]) are not real
        # classes; their mangled __name__ gives them away.
        is_generic_alias = "[" in cls.__name__

        if not is_abstract_class and resolves_own_execute and not is_generic_alias:
            concrete.add(cls)

        queue.extend(cls.__subclasses__())

    return concrete


def _discover_action_modules() -> None:
    """Import every ecosystem action module so ``__subclasses__()`` sees them."""
    for mod_name in _action_module_names():
        try:
            __import__(mod_name)
        except Exception as exc:  # noqa: BLE001 — one broken third-party module must not kill boot
            logger.debug(f"Skipped action module {mod_name!r}: {exc!r}")
