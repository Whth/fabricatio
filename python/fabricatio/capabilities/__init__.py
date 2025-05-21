"""A module containing all the capabilities of the Fabricatio framework."""

from importlib.util import find_spec

__all__ = []

if find_spec("fabricatio_capabilities"):
    from fabricatio_capabilities.capabilities.extract import Extract
    from fabricatio_capabilities.capabilities.propose import Propose
    from fabricatio_capabilities.capabilities.rating import Rating
    from fabricatio_capabilities.capabilities.task import ProposeTask

    __all__ += ["Extract", "Propose", "ProposeTask", "Rating"]

if find_spec("fabricatio_rag"):
    from fabricatio_rag.capabilities.rag import RAG

    __all__ += ["RAG"]
    if find_spec("fabricatio_write"):
        from fabricatio_typst.capabilities.citation_rag import CitationRAG

    __all__ += [
        "CitationRAG",
    ]

if find_spec("fabricatio_rule"):
    from fabricatio_rule.capabilities.censor import Censor
    from fabricatio_rule.capabilities.check import Check

    __all__ += ["Censor", "Check"]

if find_spec("fabricatio_improve"):
    from fabricatio_improve.capabilities.correct import Correct

    __all__ += ["Correct"]

if find_spec():
    from fabricatio_judge.capabilities.advanced_judge import AdvancedJudge

    __all__ += ["AdvancedJudge"]
