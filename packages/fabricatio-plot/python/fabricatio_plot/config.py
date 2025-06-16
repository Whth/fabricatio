"""Module containing configuration classes for fabricatio-plot."""
from dataclasses import dataclass
from fabricatio_core import CONFIG
@dataclass(frozen=True)
class PlotConfig:
    """ Configuration for fabricatio-plot"""



plot_config = CONFIG.load("plot",  PlotConfig)
__all__ = [
    "plot_config"
]