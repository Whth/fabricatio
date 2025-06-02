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
    as_prompt_template: str = "as_prompt"
    """The name of the as prompt template which will be used to convert a string to a prompt."""


typst_config = CONFIG.load("typst", TypstConfig)
__all__ = ["typst_config"]
