"""A module containing all the capabilities of the Fabricatio framework."""

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseEmbedding, UseLLM

__all__ = ["Propose", "UseEmbedding", "UseLLM"]

from fabricatio_core.rust import is_installed

if is_installed("fabricatio_tool"):
    from fabricatio_tool.capabilities.handle import Handle
    from fabricatio_tool.capabilities.handle_task import HandleTask
    from fabricatio_tool.capabilities.use_tool import UseTool

    __all__ += ["Handle", "HandleTask", "UseTool"]


if is_installed("fabricatio_capabilities"):
    from fabricatio_capabilities.capabilities.extract import Extract
    from fabricatio_capabilities.capabilities.rating import Rating
    from fabricatio_capabilities.capabilities.task import DispatchTask, ProposeTask

    __all__ += ["DispatchTask", "Extract", "HandleTask", "ProposeTask", "Rating"]

if is_installed("fabricatio_rag"):
    from fabricatio_rag.capabilities.rag import RAG

    __all__ += ["RAG"]
    if is_installed("fabricatio_write"):
        from fabricatio_typst.capabilities.citation_rag import CitationRAG

    __all__ += ["CitationRAG"]

if is_installed("fabricatio_rule"):
    from fabricatio_rule.capabilities.censor import Censor
    from fabricatio_rule.capabilities.check import Check

    __all__ += ["Censor", "Check"]

if is_installed("fabricatio_improve"):
    from fabricatio_improve.capabilities.correct import Correct
    from fabricatio_improve.capabilities.review import Review

    __all__ += ["Correct", "Review"]

if is_installed("fabricatio_judge"):
    from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge, VoteJudge

    __all__ += ["EvidentlyJudge", "VoteJudge"]

if is_installed("fabricatio_digest"):
    from fabricatio_digest.capabilities.digest import Digest

    __all__ += ["Digest"]

if is_installed("fabricatio_anki"):
    from fabricatio_anki.capabilities.generate_analysis import GenerateAnalysis
    from fabricatio_anki.capabilities.generate_deck import GenerateDeck

    __all__ += ["GenerateAnalysis", "GenerateDeck"]

if is_installed("fabricatio_tagging"):
    from fabricatio_tagging.capabilities.tagging import Tagging

    __all__ += ["Tagging"]
if is_installed("fabricatio_question"):
    from fabricatio_question.capabilities.questioning import Questioning

    __all__ += ["Questioning"]

if is_installed("fabricatio_yue"):
    from fabricatio_yue.capabilities.genre import SelectGenre
    from fabricatio_yue.capabilities.lyricize import Lyricize

    __all__ += ["Lyricize", "SelectGenre"]
if is_installed("fabricatio_memory"):
    from fabricatio_memory.capabilities.remember import Remember

    __all__ += ["Remember"]
    if is_installed("fabricatio_judge"):
        from fabricatio_memory.capabilities.selective_remember import SelectiveRemember

        __all__ += ["SelectiveRemember"]

if is_installed("fabricatio_translate"):
    from fabricatio_translate.capabilities.translate import Translate

    __all__ += ["Translate"]

    if is_installed("fabricatio_locale"):
        from fabricatio_locale.capabilities.localize import Localize

        __all__ += ["Localize"]

if is_installed("fabricatio_diff"):
    from fabricatio_diff.capabilities.diff_edit import DiffEdit

    __all__ += ["DiffEdit"]

if is_installed("fabricatio_thinking"):
    from fabricatio_thinking.capabilities.thinking import Thinking

    __all__ += ["Thinking"]
if is_installed("fabricatio_novel"):
    from fabricatio_novel.capabilities.novel import NovelCompose

    __all__ += ["NovelCompose"]

if is_installed("fabricatio_character"):
    from fabricatio_character.capabilities.character import CharacterCompose

    __all__ += ["CharacterCompose"]
