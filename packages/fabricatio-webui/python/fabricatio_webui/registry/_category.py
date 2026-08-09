"""Category derivation for the node palette."""

from typing import Set


def _mro_class_names(cls: type) -> Set[str]:
    """Return the set of class names in *cls*'s MRO."""
    return {c.__name__ for c in cls.__mro__}


def _derive_category(cls: type) -> str:  # noqa: PLR0911
    """Derive the node-palette category from an Action subclass's MRO."""
    mro = _mro_class_names(cls)
    class_name = cls.__name__

    # Capability-based categories (checked before name heuristics).
    has_llm = bool({"UseLLM", "Propose"} & mro)

    if {"NovelCompose", "IllustratedNovelCompose"} & mro:
        return "novel"
    if "Comfyui" in mro:
        return "comfyui"
    if {"LancedbRAG", "MilvusRAG"} & mro:
        return "rag"
    if {"GenerateDeck", "GenerateAnalysis"} & mro:
        return "anki"
    if "CharacterCompose" in mro:
        return "character"

    # Name-based heuristics — only apply when no LLM capability is present.
    if not has_llm:
        if any(kw in class_name for kw in ("Read", "Dump", "Write")):
            return "io"
        if any(kw in class_name for kw in ("Forward", "Gather", "Connect")):
            return "data"

    # Broad LLM capability goes to 'llm' unless already captured above.
    if has_llm:
        return "llm"

    return "general"
