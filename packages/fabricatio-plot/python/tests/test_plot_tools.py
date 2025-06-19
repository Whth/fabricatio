"""Module-level docstring explaining the purpose of this test file.

This module contains unit tests for the fabricatio_plot.toolboxes.plot module,
validating the correct behavior of functions related to matplotlib-based plotting.
Each test ensures proper interaction with matplotlib objects and correct
parameter passing, using pytest-mock for mocking purposes.
"""

from pathlib import Path

import matplotlib.axes as mpl_axes
import matplotlib.figure as mpl_figure
import numpy as np
import pytest_mock
from fabricatio_plot.toolboxes import plot as plot_module


def test_create_figure(mocker: pytest_mock.MockerFixture) -> None:
    """Test create_figure creates a matplotlib Figure with correct parameters.

    Args:
        mocker: Pytest mock fixture for mocking matplotlib calls.
    """
    mock_figure = mocker.patch("matplotlib.pyplot.figure")
    fig = plot_module.create_figure(figsize=(10, 5), dpi=200)

    mock_figure.assert_called_once_with(figsize=(10, 5), dpi=200)
    assert fig is not None  # Basic existence check


def test_create_subplots(mocker: pytest_mock.MockerFixture) -> None:
    """Test create_subplots generates correct figure and axes array.

    Args:
        mocker: Pytest mock fixture for mocking matplotlib calls.
    """
    mock_return = (mocker.Mock(), np.array([[1, 2], [3, 4]]))
    mocker.patch("matplotlib.pyplot.subplots", return_value=mock_return)
    fig, axs = plot_module.create_subplots(nrows=2, ncols=2, figsize=(8, 6))

    assert fig is not None
    assert axs.shape == (2, 2)
    assert isinstance(axs, np.ndarray)


def test_plot_line(mocker: pytest_mock.MockerFixture) -> None:
    """Test plot_line calls axes.plot with correct parameters.

    Args:
        mocker: Pytest mock fixture for mocking axes methods.
    """
    mock_ax = mocker.Mock(spec=mpl_axes.Axes)
    plot_module.plot_line(
        ax=mock_ax, x=[1, 2, 3], y=[4, 5, 6], label="test", color="red", linewidth=1.5, linestyle="--"
    )

    mock_ax.plot.assert_called_once_with([1, 2, 3], [4, 5, 6], label="test", color="red", linewidth=1.5, linestyle="--")


def test_set_labels(mocker: pytest_mock.MockerFixture) -> None:
    """Test set_labels configures title, xlabel, and ylabel correctly.

    Args:
        mocker: Pytest mock fixture for mocking axes methods.
    """
    mock_ax = mocker.Mock(spec=mpl_axes.Axes)
    plot_module.set_labels(ax=mock_ax, title="My Plot", xlabel="X Axis", ylabel="Y Axis")

    mock_ax.set_title.assert_called_once_with("My Plot")
    mock_ax.set_xlabel.assert_called_once_with("X Axis")
    mock_ax.set_ylabel.assert_called_once_with("Y Axis")


def test_save_plot(mocker: pytest_mock.MockerFixture) -> None:
    """Test save_plot calls figure.savefig with correct parameters.

    Args:
        mocker: Pytest mock fixture for mocking figure methods.
    """
    mock_fig = mocker.Mock(spec=mpl_figure.Figure)
    save_path = Path("test_output.png")
    plot_module.save_plot(fig=mock_fig, save_path=save_path, dpi=300, transparent=True)

    mock_fig.savefig.assert_called_once_with(save_path, dpi=300, transparent=True, bbox_inches="tight")
