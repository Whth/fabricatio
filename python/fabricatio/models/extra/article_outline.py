"""A module containing the ArticleOutline class, which represents the outline of an academic paper."""

from typing import Generator, List, Optional, Self, Tuple, Union, override

import regex
from fabricatio.models.extra.article_base import (
    ArticleBase,
    ArticleOutlineBase,
    ChapterBase,
    SectionBase,
    SubSectionBase,
)
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.generic import CensoredAble, Display, PersistentAble, WithRef
from fabricatio.models.utils import ok


class ArticleSubsectionOutline(ArticleOutlineBase, SubSectionBase):
    """Atomic research component specification for academic paper generation."""



class ArticleSectionOutline(ArticleOutlineBase, SectionBase[ArticleSubsectionOutline]):
    """A slightly more detailed research component specification for academic paper generation, Must contain subsections."""


    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        super().update_from_inner(other)
        super(ArticleOutlineBase, self).update_from_inner(other)
        return self


class ArticleChapterOutline(ArticleOutlineBase, ChapterBase[ArticleSectionOutline]):
    """Macro-structural unit implementing standard academic paper organization. Must contain sections."""

    def update_from_inner(self, other: Self) -> Self:
        """Updates the current instance with the attributes of another instance."""
        super().update_from_inner(other)
        super(ArticleOutlineBase, self).update_from_inner(other)
        return self


class ArticleOutline(
    Display,
    CensoredAble,
    WithRef[ArticleProposal],
    PersistentAble,
    ArticleBase[ArticleChapterOutline],
):
    """A class representing the outline of an academic paper."""

    abstract: str
    """The abstract is a concise summary of the academic paper's main findings."""

    prospect: str
    """Consolidated research statement with four pillars:
    1. Problem Identification: Current limitations
    2. Methodological Response: Technical approach
    3. Empirical Validation: Evaluation strategy
    4. Scholarly Impact: Field contributions
    """

    title: str
    """Title of the academic paper."""

    language: str
    """Written language of the article. SHALL be aligned to the language of the article proposal provided."""

    def finalized_dump(self) -> str:
        """Generates standardized hierarchical markup for academic publishing systems.

        Implements ACL 2024 outline conventions with four-level structure:
        = Chapter Title (Level 1)
        == Section Title (Level 2)
        === Subsection Title (Level 3)
        ==== Subsubsection Title (Level 4)

        Returns:
            str: Strictly formatted outline with academic sectioning

        Example:
            = Methodology
            == Neural Architecture Search Framework
            === Differentiable Search Space
            ==== Constrained Optimization Parameters
            === Implementation Details
            == Evaluation Protocol
        """
        lines: List[str] = []
        for i, chapter in enumerate(self.chapters, 1):
            lines.append(f"= Chapter {i}: {chapter.title}")
            for j, section in enumerate(chapter.sections, 1):
                lines.append(f"== {i}.{j} {section.title}")
                for k, subsection in enumerate(section.subsections, 1):
                    lines.append(f"=== {i}.{j}.{k} {subsection.title}")
        return "\n".join(lines)

    @override
    def iter_dfs(
        self,
    ) -> Generator[ArticleChapterOutline | ArticleSectionOutline | ArticleSubsectionOutline, None, None]: 
        return super().iter_dfs()
    def find_illegal(self) -> Optional[Tuple[ArticleOutlineBase, str]]:
        """Finds the first illegal component in the outline.

        Returns:
            Tuple[ArticleOutlineBase, str]: A tuple containing the illegal component and an error message.
        """
        summary = ""
        for component in self.iter_dfs():
            for ref in component.depend_on:
                if not ref.deref(self):
                    summary += f"Invalid internal reference in {component.__class__.__name__} titled `{component.title}` at `depend_on` field, because the referred {ref.referring_type} is not exists within the article, see the original obj dump: {ref.model_dump()}\n"
            for ref in component.support_to:
                if not ref.deref(self):
                    summary += f"Invalid internal reference in {component.__class__.__name__} titled `{component.title}` at `support_to` field, because the referred {ref.referring_type} is not exists within the article, see the original obj dump: {ref.model_dump()}\n"
            summary += component.introspect()
            if summary:
                return component, summary
        return None

    @classmethod
    def from_typst_code(
        cls, typst_code: str, title: str = "", article_language: str = "en", prospect: str = "", abstract: str = ""
    ) -> "ArticleOutline":
        """Parses a Typst code string and creates an ArticleOutline instance."""
        self = cls(language=article_language, prospect=prospect, abstract=abstract, chapters=[], title=title)
        stack = [self]  # 根节点为ArticleOutline实例

        for line in typst_code.splitlines():
            parsed = cls._parse_line(line)
            if not parsed:
                continue
            level, title = parsed
            cls._adjust_stack(stack, level)
            parent = stack[-1]
            component = cls._create_component(level, title)
            cls._add_to_parent(parent, component, level)
            stack.append(component)

        return self

    @classmethod
    def _parse_line(cls, line: str) -> Optional[Tuple[int, str]]:
        stripped = line.strip()
        if not stripped.startswith("="):
            return None
        match = regex.match(r"^(\=+)(.*)", stripped)
        if not match:
            return None
        eqs, title_part = match.groups()
        return len(eqs), title_part.strip()

    @classmethod
    def _adjust_stack(cls, stack: List[object], target_level: int) -> None:
        while len(stack) > target_level:
            stack.pop()

    @classmethod
    def _create_component(cls, level: int, title: str) -> ArticleOutlineBase:
        default_kwargs = {
            "writing_aim": [],
            "depend_on": [],
            "support_to": [],
            "description": [],
        }
        component_map = {
            1: lambda: ArticleChapterOutline(title=title, sections=[], **default_kwargs),
            2: lambda: ArticleSectionOutline(title=title, subsections=[], **default_kwargs),
            3: lambda: ArticleSubsectionOutline(title=title, **default_kwargs),
        }
        return ok(component_map.get(level, lambda: None)(), "Invalid level")

    @classmethod
    def _add_to_parent(
        cls,
        parent: Union["ArticleOutline", ArticleChapterOutline, ArticleSectionOutline],
        component: ArticleOutlineBase,
        level: int,
    ) -> None:
        if level == 1 and isinstance(component, ArticleChapterOutline):
            parent.chapters.append(component)
        elif level == 2 and isinstance(component, ArticleSectionOutline):  # noqa: PLR2004
            parent.sections.append(component)
        elif level == 3 and isinstance(component, ArticleSubsectionOutline):  # noqa: PLR2004
            parent.subsections.append(component)
