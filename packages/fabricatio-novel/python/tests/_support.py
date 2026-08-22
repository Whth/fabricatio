"""Shared builders and mock roles for the fabricatio-novel test modules."""

from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import Value
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGCompose
from fabricatio_novel.models.context.log import ContextEntry, ContextLog


def card(name: str = "Hero", look: str = "tall") -> CharacterCard:
    """Build a default protagonist CharacterCard for tests."""
    return CharacterCard(
        name=name,
        roles=["protagonist"],
        activated_role="protagonist",
        look=look,
        act="brave",
        want="seek truth",
        flaw="stubborn",
        where="starting village",
        condition="healthy",
        mood="determined",
    )


def raw_value(text: str) -> Value[str]:
    """Wrap a plain scene response for mixed router usage."""
    return Value(text, "raw", convertor=lambda s: s)


def prefix_log(body: str, *, title: str = "S1") -> ContextLog:
    """Build a one-entry scene-content prefix log for tests."""
    return ContextLog(entries=(ContextEntry(kind="scene_content", title=title, body=body),))


class NovelRole(LLMTestRole, NovelCompose):
    """Test role combining mock LLM with the novel composition chain."""


class RAGRole(LLMTestRole, NovelCompose, RAGCompose):
    """Test role combining mock LLM with RAG-extended novel composition."""
