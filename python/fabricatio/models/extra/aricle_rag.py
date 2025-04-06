"""A Module containing the article rag models."""

from pathlib import Path
from typing import ClassVar, List, Self, Unpack

from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.extra.rag import MilvusDataBase
from fabricatio.models.kwargs_types import ChunkKwargs
from fabricatio.rust import BibManager, split_into_chunks
from fabricatio.utils import ok
from more_itertools.recipes import flatten
from pydantic import Field


class ArticleChunk(MilvusDataBase):
    """The chunk of an article."""

    head_split: ClassVar[List[str]] = ["Introduction", "引言", "绪论"]
    tail_split: ClassVar[List[str]] = ["Reference", "参考文献"]
    chunk: str
    """The segment of the article"""
    year: int
    """The year of the article"""
    authors: List[str] = Field(default_factory=list)
    """The authors of the article"""
    article_title: str
    """The title of the article"""
    bibtex_cite_key: str
    """The bibtex cite key of the article"""

    @property
    def to_vectorize(self) -> str:
        """The text to vectorize."""
        return self.chunk

    @classmethod
    def from_file[P: str | Path](
        cls, path: P | List[P], bib_mgr: BibManager, **kwargs: Unpack[ChunkKwargs]
    ) -> List[Self]:
        """Load the article chunks from the file."""
        if isinstance(path, list):
            return list(flatten(cls._from_file_inner(p, bib_mgr, **kwargs) for p in path))

        return cls._from_file_inner(path, bib_mgr, **kwargs)

    @classmethod
    def _from_file_inner(cls, path: str | Path, bib_mgr: BibManager, **kwargs: Unpack[ChunkKwargs]) -> List[Self]:
        path = Path(path)

        key = bib_mgr.get_cite_key_fuzzy(path.stem)
        if key is None:
            logger.warning(f"no cite key found for {path.as_posix()}")
            return []
        authors = ok(bib_mgr.get_author_by_key(key), f"no author found for {key}")
        year = ok(bib_mgr.get_year_by_key(key), f"no year found for {key}")
        article_title = ok(bib_mgr.get_title_by_key(key), f"no title found for {key}")

        return [
            cls(chunk=c, year=year, authors=authors, article_title=article_title, bibtex_cite_key=key)
            for c in split_into_chunks(cls.strip(safe_text_read(path)), **kwargs)
        ]

    @classmethod
    def strip(cls, string: str) -> str:
        """Strip the head and tail of the string."""
        for split in cls.head_split:
            string = string.split(split)[-1]
        for split in cls.tail_split:
            string = string.split(split)[0]
        return string
