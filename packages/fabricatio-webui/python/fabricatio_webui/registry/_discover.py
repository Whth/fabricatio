"""Action subclass discovery and MRO traversal."""

import contextlib
from collections import deque
from typing import List, Set, Type

from fabricatio_core.models.action import Action

_ACTION_MODULE_CANDIDATES: List[str] = [
    "fabricatio_actions.actions",
    "fabricatio_actions.actions.output",
    "fabricatio_actions.actions.fs",
    "fabricatio_novel.actions.novel",
    "fabricatio_novel.actions.novel_mental",
    "fabricatio_novel.actions.novel_rag",
    "fabricatio_novel.actions.enrich",
    "fabricatio_novel.actions.illustration",
    "fabricatio_anki.actions",
    "fabricatio_typst.actions",
    "fabricatio_typst.actions.article",
    "fabricatio_typst.actions.article_rag",
    "fabricatio_comfyui.actions",
    "fabricatio_capabilities.actions",
    "fabricatio_improve.actions",
    "fabricatio_question.actions",
    "fabricatio_rule.actions",
    "fabricatio_webui.actions",
]


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
    """Try to import known action modules so __subclasses__() can find them."""
    for mod_name in _ACTION_MODULE_CANDIDATES:
        with contextlib.suppress(ImportError):
            __import__(mod_name)
