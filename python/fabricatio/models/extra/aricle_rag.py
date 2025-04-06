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

    def _prepare_vectorization_inner(self) -> str:
        return self.chunk

    @classmethod
    def from_file[P: str | Path](
        cls, path: P | List[P], bib_mgr: BibManager, **kwargs: Unpack[ChunkKwargs]
    ) -> List[Self]:
        """Load the article chunks from the file."""
        if isinstance(path, list):
            result = list(flatten(cls._from_file_inner(p, bib_mgr, **kwargs) for p in path))
            logger.debug(f"Number of chunks created from list of files: {len(result)}")
            return result

        return cls._from_file_inner(path, bib_mgr, **kwargs)

    @classmethod
    def _from_file_inner(cls, path: str | Path, bib_mgr: BibManager, **kwargs: Unpack[ChunkKwargs]) -> List[Self]:
        path = Path(path)

        key = bib_mgr.get_cite_key_fuzzy(path.stem)
        if key is None:
            logger.warning(f"no cite key found for {path.as_posix()}, skip.")
            return []
        authors = ok(bib_mgr.get_author_by_key(key), f"no author found for {key}")
        year = ok(bib_mgr.get_year_by_key(key), f"no year found for {key}")
        article_title = ok(bib_mgr.get_title_by_key(key), f"no title found for {key}")

        result = [
            cls(chunk=c, year=year, authors=authors, article_title=article_title, bibtex_cite_key=key)
            for c in split_into_chunks(cls.strip(safe_text_read(path)), **kwargs)
        ]
        logger.debug(f"Number of chunks created from file {path.as_posix()}: {len(result)}")
        return result

    @classmethod
    def strip(cls, string: str) -> str:
        """Strip the head and tail of the string."""
        for split in cls.head_split:
            parts = string.split(split)
            string = split.join(parts[1:]) if len(parts) > 1 else parts[0]
        for split in cls.tail_split:
            parts = string.split(split)
            string = split.join(parts[:-1]) if len(parts) > 1 else parts[0]
        return string
