"""A Module containing the article rag models."""

from pathlib import Path
from typing import ClassVar, Dict, List, Self, Unpack

from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.extra.rag import MilvusDataBase
from fabricatio.models.generic import AsPrompt
from fabricatio.models.kwargs_types import ChunkKwargs
from fabricatio.rust import BibManager, split_into_chunks
from fabricatio.utils import ok, wrapp_in_block
from more_itertools.recipes import flatten
from pydantic import Field


class ArticleChunk(MilvusDataBase, AsPrompt):
    """The chunk of an article."""

    head_split: ClassVar[List[str]] = [
        "引 言",
        "引言",
        "绪 论",
        "绪论",
        "前言",
        "INTRODUCTION",
        "Introduction",
    ]
    tail_split: ClassVar[List[str]] = [
        "参 考 文 献",
        "参  考  文  献",
        "参考文献",
        "REFERENCES",
        "References",
        "Bibliography",
        "Reference",
    ]
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

    def _as_prompt_inner(self) -> Dict[str, str]:
        return {
            self.article_title: f"{wrapp_in_block(self.chunk, 'Referring Content')}\n"
            f"Authors: {';'.join(self.authors)}\n"
            f"Published Year: {self.year}\n"
            f"Bibtex Key: {self.bibtex_cite_key}\n",
        }

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

        title_seg = path.stem.split(" - ").pop()

        key = (
            bib_mgr.get_cite_key_by_title(title_seg)
            or bib_mgr.get_cite_key_by_title_fuzzy(title_seg)
            or bib_mgr.get_cite_key_fuzzy(path.stem)
        )
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
        logger.debug(f"String length before strip: {(original := len(string))}")
        for split in (s for s in cls.head_split if s in string):
            logger.debug(f"Strip head using {split}")
            parts = string.split(split)
            string = split.join(parts[1:]) if len(parts) > 1 else parts[0]
            break
        logger.debug(
            f"String length after head strip: {(stripped_len := len(string))}, decreased by {(d := original - stripped_len)}"
        )
        if not d:
            logger.warning("No decrease at head strip, which is might be abnormal.")
        for split in (s for s in cls.tail_split if s in string):
            logger.debug(f"Strip tail using {split}")
            parts = string.split(split)
            string = split.join(parts[:-1]) if len(parts) > 1 else parts[0]
            break
        logger.debug(f"String length after tail strip: {len(string)}, decreased by {(d := stripped_len - len(string))}")
        if not d:
            logger.warning("No decrease at tail strip, which is might be abnormal.")

        return string
