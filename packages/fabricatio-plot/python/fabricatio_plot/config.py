"""Module containing configuration classes for fabricatio-plot."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class PlotConfig:
    """Configuration for fabricatio-plot."""

    generate_header_template: str = "built-in/generate_header"
    """Template for generating header."""
    generate_csv_data_template: str = "built-in/generate_csv_data"
    """Template for generating CSV data."""

    csv_sep: str = ","
    """Separator for CSV files."""

    csv_codeblock_lang: str = "csv"
    """Language for CSV code blocks."""


plot_config = CONFIG.load("plot", PlotConfig)
__all__ = ["plot_config"]
