"""A module containing all the capabilities of the Fabricatio framework."""

from importlib.util import find_spec

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseEmbedding, UseLLM

__all__ = ["Propose", "UseEmbedding", "UseLLM"]

if find_spec("fabricatio_tool"):
    from fabricatio_tool.capabilities.handle import Handle
    from fabricatio_tool.capabilities.handle_task import HandleTask
    from fabricatio_tool.capabilities.use_tool import UseTool

    __all__ += ["Handle", "HandleTask", "UseTool"]


if find_spec("fabricatio_capabilities"):
    from fabricatio_capabilities.capabilities.extract import Extract
    from fabricatio_capabilities.capabilities.rating import Rating
    from fabricatio_capabilities.capabilities.task import DispatchTask, ProposeTask

    __all__ += ["DispatchTask", "Extract", "HandleTask", "ProposeTask", "Rating"]

if find_spec("fabricatio_rag"):
    from fabricatio_rag.capabilities.rag import RAG

    __all__ += ["RAG"]
    if find_spec("fabricatio_write"):
        from fabricatio_typst.capabilities.citation_rag import CitationRAG

    __all__ += ["CitationRAG"]

if find_spec("fabricatio_rule"):
    from fabricatio_rule.capabilities.censor import Censor
    from fabricatio_rule.capabilities.check import Check

    __all__ += ["Censor", "Check"]

if find_spec("fabricatio_improve"):
    from fabricatio_improve.capabilities.correct import Correct
    from fabricatio_improve.capabilities.review import Review

    __all__ += ["Correct", "Review"]

if find_spec("fabricatio_judge"):
    from fabricatio_judge.capabilities.advanced_judge import AdvancedJudge

    __all__ += ["AdvancedJudge"]

if find_spec("fabricatio_digest"):
    from fabricatio_digest.capabilities.digest import Digest

    __all__ += ["Digest"]

if find_spec("fabricatio_anki"):
    from fabricatio_anki.capabilities.generate_analysis import GenerateAnalysis
    from fabricatio_anki.capabilities.generate_deck import GenerateDeck

    __all__ += ["GenerateAnalysis", "GenerateDeck"]

if find_spec("fabricatio_tagging"):
    from fabricatio_tagging.capabilities.tagging import Tagging

    __all__ += ["Tagging"]
if find_spec("fabricatio_question"):
    from fabricatio_question.capabilities.questioning import Questioning

    __all__ += ["Questioning"]

if find_spec("fabricatio_yue"):
    from fabricatio_yue.capabilities.genre import SelectGenre
    from fabricatio_yue.capabilities.lyricize import Lyricize

    __all__ += ["Lyricize", "SelectGenre"]
if find_spec("fabricatio_memory"):
    from fabricatio_memory.capabilities.memory import Remember

    __all__ += ["Remember"]


if find_spec("fabricatio_translate"):
    from fabricatio_translate.capabilities.translate import Translate

    __all__ += ["Translate"]

    if find_spec("fabricatio_locale"):
        from fabricatio_locale.capabilities.localize import Localize

        __all__ += ["Localize"]
