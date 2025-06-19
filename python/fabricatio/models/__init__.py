"""A module for the usage of the fabricatio package."""

from importlib.util import find_spec

__all__ = []

if find_spec("fabricatio_typst"):
    from fabricatio_typst.models.article_essence import ArticleEssence
    from fabricatio_typst.models.article_main import Article
    from fabricatio_typst.models.article_outline import ArticleOutline
    from fabricatio_typst.models.article_proposal import ArticleProposal

    __all__ += [
        "Article",
        "ArticleEssence",
        "ArticleOutline",
        "ArticleProposal",
    ]

    if find_spec("fabricatio_typst"):
        from fabricatio_typst.models.aricle_rag import ArticleChunk

        __all__ += ["ArticleChunk"]

if find_spec("fabricatio_judge"):
    from fabricatio_judge.models.judgement import JudgeMent

    __all__ += ["JudgeMent"]

if find_spec("fabricatio_digest"):
    from fabricatio_digest.models.tasklist import TaskList

    __all__ += ["TaskList"]


if find_spec("fabricatio_anki"):
    from fabricatio_anki.models.deck import Deck, Model
    from fabricatio_anki.models.template import Template
    from fabricatio_anki.models.topic_analysis import TopicAnalysis

    __all__ += ["Deck", "Model", "Template", "TopicAnalysis"]

if find_spec("fabricatio_question"):
    from fabricatio_question.models.questions import SelectionQuestion

    __all__ += ["SelectionQuestion"]


if find_spec("fabricatio_yue"):
    from fabricatio_yue.models.segment import Segment, Song

    __all__ += ["Segment", "Song"]

if find_spec("fabricatio_memory"):
    from fabricatio_memory.models.note import Note

    __all__ += ["Note"]
