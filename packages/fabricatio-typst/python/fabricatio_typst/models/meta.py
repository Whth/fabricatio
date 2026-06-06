"""Lightweight metadata model and Typst code mixins for article components."""

from abc import ABC
from enum import StrEnum
from typing import List, Optional, Self, Tuple

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, Language, SketchedAble, Titled
from fabricatio_core.rust import detect_language, word_count
from fabricatio_core.utils import fallback_kwargs
from pydantic import Field

from fabricatio_typst.rust import split_out_metadata, to_metadata


class ReferringType(StrEnum):
    """Enumeration of different types of references that can be made in an article."""

    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"


type RefKey = Tuple[str, Optional[str], Optional[str]]


class ArticleMetaData(SketchedAble, Described, WordCount, Titled, Language):
    """Metadata for an article component."""

    description: str = Field(
        alias="elaboration",
        description=Described.model_fields["description"].description,
    )

    title: str = Field(alias="heading", description=Titled.model_fields["title"].description)

    aims: List[str]
    """List of writing aims of the research component in academic style."""

    _unstructured_body: str = ""
    """Store the source of the unknown information."""

    @property
    def typst_metadata_comment(self) -> str:
        """Generates a comment for the metadata of the article component."""
        data = self.model_dump(
            include={"description", "aims", "expected_word_count"},
            by_alias=True,
        )
        return to_metadata({k: v for k, v in data.items() if v})

    @property
    def unstructured_body(self) -> str:
        """Returns the unstructured body of the article component."""
        return self._unstructured_body

    def update_unstructured_body[S: "ArticleMetaData"](self: S, body: str) -> S:
        """Update the unstructured body of the article component."""
        self._unstructured_body = body
        return self

    @property
    def language(self) -> str:
        """Get the language of the article component."""
        return detect_language(self.title)


class FromTypstCode(ArticleMetaData, ABC):
    """Base class for article components that can be created from a Typst code snippet."""

    @classmethod
    def from_typst_code(cls, title: str, body: str, **kwargs) -> Self:
        """Converts a Typst code snippet into an article component."""
        data, body = split_out_metadata(body)

        return cls(
            heading=title.strip(),
            **fallback_kwargs(data or {}, elaboration="", expected_word_count=word_count(body), aims=[]),
            **kwargs,
        )


class ToTypstCode(ArticleMetaData, ABC):
    """Base class for article components that can be converted to a Typst code snippet."""

    def to_typst_code(self) -> str:
        """Converts the component into a Typst code snippet for rendering."""
        return f"{self.title}\n{self.typst_metadata_comment}\n\n{self._unstructured_body}"
