"""Module for creating and customizing plots using matplotlib.

This module provides a toolbox with various functions to create figures, add different types of plots,
customize plot appearance, and save or display plots. It is built on top of matplotlib and offers a
simplified interface for common plotting tasks.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from fabricatio_tool.models.tool import ToolBox
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

plot_toolbox = ToolBox(name="PlottingToolBox", description="A toolbox for plotting based on matplotlib.")


@plot_toolbox.collect_tool
def create_figure(figsize: Tuple[float, float] = (8, 6), dpi: int = 200) -> Figure:
    """Create a new matplotlib figure.

    Args:
        figsize: Width and height of the figure in inches (default: (8, 6)).
        dpi: Dots per inch resolution (default: 200).

    Returns:
        Newly created Figure object.
    """
    return plt.figure(figsize=figsize, dpi=dpi)


@plot_toolbox.collect_tool
def create_subplots(nrows: int = 1, ncols: int = 1, figsize: Tuple[float, float] = (8, 6)) -> Tuple[Figure, np.ndarray]:
    """Create a figure and grid of subplots.

    Args:
        nrows: Number of rows in subplot grid.
        ncols: Number of columns in subplot grid.
        figsize: Width and height of the figure in inches.

    Returns:
        Tuple containing:
        - Figure object
        - Numpy array of Axes objects
    """
    fig, axs = plt.subplots(nrows, ncols, figsize=figsize)
    return fig, np.array(axs).reshape(nrows, ncols)  # Ensure consistent shape


@plot_toolbox.collect_tool
def plot_line(
    ax: Axes,
    x: List[float],
    y: List[float],
    label: Optional[str] = None,
    color: str = "blue",
    linewidth: float = 2.0,
    linestyle: str = "-",
) -> None:
    """Plot a line chart on specified axes.

    Args:
        ax: Target axes object.
        x: X-axis data points.
        y: Y-axis data points.
        label: Legend label for the line.
        color: Line color (default: 'blue').
        linewidth: Line width in points (default: 2.0).
        linestyle: Line style (e.g., '-', '--', ':', '-.').
    """
    ax.plot(x, y, label=label, color=color, linewidth=linewidth, linestyle=linestyle)


@plot_toolbox.collect_tool
def plot_bar(ax: Axes, categories: List[str], values: List[float], color: str = "skyblue", width: float = 0.8) -> None:
    """Plot a vertical bar chart.

    Args:
        ax: Target axes object.
        categories: Category labels for each bar.
        values: Height values for each bar.
        color: Bar fill color (default: 'skyblue').
        width: Bar width (default: 0.8).
    """
    ax.bar(categories, values, color=color, width=width)


@plot_toolbox.collect_tool
def plot_scatter(
    ax: Axes,
    x: List[float],
    y: List[float],
    color: str = "red",
    size: float = 20,
    marker: str = "o",
    alpha: float = 0.7,
) -> None:
    """Create a scatter plot.

    Args:
        ax: Target axes object.
        x: X-coordinates of points.
        y: Y-coordinates of points.
        color: Point color (default: 'red').
        size: Marker size in points (default: 20).
        marker: Marker style (e.g., 'o', 's', '^').
        alpha: Opacity (0=transparent, 1=opaque, default: 0.7).
    """
    ax.scatter(x, y, c=color, s=size, marker=marker, alpha=alpha)


@plot_toolbox.collect_tool
def set_labels(
    ax: Axes, title: Optional[str] = None, xlabel: Optional[str] = None, ylabel: Optional[str] = None
) -> None:
    """Set axis labels and chart title.

    Args:
        ax: Target axes object.
        title: Chart title text.
        xlabel: X-axis label text.
        ylabel: Y-axis label text.
    """
    if title:
        ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)


@plot_toolbox.collect_tool
def set_legend(ax: Axes, location: str = "best", fontsize: int = 10) -> None:
    """Add legend to the chart.

    Args:
        ax: Target axes object.
        location: Legend position (e.g., 'upper right', 'lower left').
        fontsize: Legend text size (default: 10).
    """
    ax.legend(loc=location, fontsize=fontsize)


@plot_toolbox.collect_tool
def configure_grid(ax: Axes, visible: bool = True, linestyle: str = "--", alpha: float = 0.5) -> None:
    """Configure grid lines on the chart.

    Args:
        ax: Target axes object.
        visible: Toggle grid visibility (default: True).
        linestyle: Grid line style (default: '--').
        alpha: Grid opacity (0-1, default: 0.5).
    """
    ax.grid(visible=visible, linestyle=linestyle, alpha=alpha)


@plot_toolbox.collect_tool
def save_plot(fig: Figure, save_path: str | Path, dpi: int = 300, transparent: bool = False) -> None:
    """Save figure to file.

    Args:
        fig: Figure object to save.
        save_path: Output path (include extension: .png, .jpg, .pdf).
        dpi: Output resolution (default: 300).
        transparent: Save with transparent background (default: False).
    """
    fig.savefig(save_path, dpi=dpi, transparent=transparent, bbox_inches="tight")
