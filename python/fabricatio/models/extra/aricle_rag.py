"""A Module containing the article rag models."""

import re
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Self, Unpack

from fabricatio.fs import safe_text_read
from fabricatio.journal import logger
from fabricatio.models.extra.rag import MilvusDataBase
from fabricatio.models.generic import AsPrompt
from fabricatio.models.kwargs_types import ChunkKwargs
from fabricatio.rust import BibManager, is_chinese, split_into_chunks
from fabricatio.utils import ok
from more_itertools.recipes import flatten, unique
from pydantic import Field


class ArticleChunk(MilvusDataBase, AsPrompt):
    """The chunk of an article."""

    etc_word: ClassVar[str] = "等"
    and_word: ClassVar[str] = "与"
    _cite_number: Optional[int] = None

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
            f"[[{ok(self._cite_number, 'You need to update cite number first.')}]] reference `{self.article_title}`": self.chunk
        }

    @property
    def cite_number(self) -> int:
        """Get the cite number."""
        return ok(self._cite_number, "cite number not set")

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
            for c in split_into_chunks(cls.purge_numeric_citation(cls.strip(safe_text_read(path))), **kwargs)
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

    def as_typst_cite(self) -> str:
        """As typst cite."""
        return f"#cite(<{self.bibtex_cite_key}>)"

    @staticmethod
    def purge_numeric_citation(string: str) -> str:
        """Purge numeric citation."""
        import re

        return re.sub(r"\[[\d\s,\\~–-]+]", "", string)

    @property
    def auther_firstnames(self) -> List[str]:
        """Get the first name of the authors."""
        ret = []
        for n in self.authors:
            if is_chinese(n):
                ret.append(n[0])
            else:
                ret.append(n.split()[-1])
        return ret

    def as_auther_seq(self) -> str:
        """Get the auther sequence."""
        match len(self.authors):
            case 0:
                raise ValueError("No authors found")
            case 1:
                return f"（{self.auther_firstnames[0]}，{self.year}）{self.as_typst_cite()}"
            case 2:
                return f"（{self.auther_firstnames[0]}{self.and_word}{self.auther_firstnames[1]}，{self.year}）{self.as_typst_cite()}"
            case 3:
                return f"（{self.auther_firstnames[0]}，{self.auther_firstnames[1]}{self.and_word}{self.auther_firstnames[2]}，{self.year}）{self.as_typst_cite()}"
            case _:
                return f"（{self.auther_firstnames[0]}，{self.auther_firstnames[1]}{self.and_word}{self.auther_firstnames[2]}{self.etc_word}，{self.year}）{self.as_typst_cite()}"

    def update_cite_number(self, cite_number: int) -> Self:
        """Update the cite number."""
        self._cite_number = cite_number
        return self


class CitationManager(AsPrompt):
    """Citation manager."""

    article_chunks: List[ArticleChunk] = Field(default_factory=list)
    """Article chunks."""

    pat: str = r"(\[\[([\d\s,-]*)]])"
    """Regex pattern to match citations."""
    sep: str = ","
    """Separator for citation numbers."""
    abbr_sep: str = "-"
    """Separator for abbreviated citation numbers."""

    def update_chunks(self, article_chunks: List[ArticleChunk], set_cite_number: bool = True) -> Self:
        """Update article chunks."""
        self.article_chunks.clear()
        self.article_chunks.extend(article_chunks)
        if set_cite_number:
            self.set_cite_number_all()
        return self

    def set_cite_number_all(self) -> Self:
        """Set citation numbers for all article chunks."""
        for i, a in enumerate(self.article_chunks, 1):
            a.update_cite_number(i)
        return self

    def _as_prompt_inner(self) -> Dict[str, str]:
        """Generate prompt inner representation."""
        return {"References": "\n".join(r.as_prompt() for r in self.article_chunks)}

    def apply(self, string: str) -> str:
        """Apply citation replacements to the input string."""
        for origin,m in re.findall(self.pat, string):
            logger.info(f"Matching citation: {m}")
            notations = self.convert_to_numeric_notations(m)
            logger.info(f"Citing Notations: {notations}")
            citation_number_seq = list(flatten(self.decode_expr(n) for n in notations))
            logger.info(f"Citation Number Sequence: {citation_number_seq}")
            dedup = self.deduplicate_citation(citation_number_seq)
            logger.info(f"Deduplicated Citation Number Sequence: {dedup}")
            string=string.replace(origin, self.unpack_cite_seq(dedup))
        return string

    def decode_expr(self, string: str) -> List[int]:
        """Decode citation expression into a list of integers."""
        if self.abbr_sep in string:
            start, end = string.split(self.abbr_sep)
            return list(range(int(start), int(end) + 1))
        return [int(string)]

    def convert_to_numeric_notations(self, string: str) -> List[str]:
        """Convert citation string into numeric notations."""
        return [s.strip() for s in string.split(self.sep)]

    def deduplicate_citation(self, citation_seq: List[int]) -> List[int]:
        """Deduplicate citation sequence."""
        chunk_seq = [a for a in self.article_chunks if a.cite_number in citation_seq]
        deduped = unique(chunk_seq, lambda a: a.cite_number)
        return [a.cite_number for a in deduped]

    def unpack_cite_seq(self, citation_seq: List[int]) -> str:
        """Unpack citation sequence into a string."""
        chunk_seq = [a for a in self.article_chunks if a.cite_number in citation_seq]
        return "".join(a.as_typst_cite() for a in chunk_seq)
