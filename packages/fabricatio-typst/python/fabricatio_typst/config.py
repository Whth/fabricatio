"""Module containing configuration classes for fabricatio-typst."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class TypstConfig:
    """Configuration for fabricatio-typst."""

    # Content Summary Templates
    chap_summary_template: str = "chap_summary"
    """The name of the chap summary template which will be used to generate a chapter summary."""

    research_content_summary_template: str = "research_content_summary"
    """The name of the research content summary template which will be used to generate a summary of research content."""

    paragraph_sep: str = "// - - -"
    """The separator used to separate paragraphs."""

    article_wrapper = "// =-=-=-=-=-=-=-=-=-="
    """The wrapper used to wrap an article."""

    extract_essence_template: str = "extract_essence"
    """The name of the extract essence template which will be used to extract the essence of a text."""

    generate_outline_template: str = "generate_outline"
    """The name of the generate outline template which will be used to generate an outline."""


typst_config = CONFIG.load("typst", TypstConfig)
__all__ = ["typst_config"]
