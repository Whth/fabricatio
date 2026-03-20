"""Synthetic Data Generation Toolbox Module (Minimalist).

This module provides simple, flat functions for generating synthetic data columns.
Each function returns a pandas Series. Designed for direct LLM invocation.
"""

from typing import List

import numpy as np
import pandas as pd
from fabricatio_tool.models.tool import ToolBox

# Initialize the synthetic data toolbox
data_syn_toolbox = ToolBox(name="DataSynToolbox", description="A minimal toolbox for generating synthetic datasets")


@data_syn_toolbox.collect_tool
def numeric_column(n_rows: int, low: float = 0.0, high: float = 1.0) -> pd.Series:
    """Generate a uniform numeric column.

    Args:
        n_rows: Number of values to generate.
        low: Minimum value.
        high: Maximum value.

    Returns:
        pd.Series: Generated numeric series.
    """
    return pd.Series(np.random.uniform(low, high, size=n_rows))


@data_syn_toolbox.collect_tool
def normal_column(n_rows: int, mean: float = 0.0, std: float = 1.0) -> pd.Series:
    """Generate a normally distributed numeric column.

    Args:
        n_rows: Number of values to generate.
        mean: Mean of the distribution.
        std: Standard deviation.

    Returns:
        pd.Series: Generated numeric series.
    """
    return pd.Series(np.random.normal(mean, std, size=n_rows))


@data_syn_toolbox.collect_tool
def categorical_column(n_rows: int, categories: List[str]) -> pd.Series:
    """Generate a categorical column.

    Args:
        n_rows: Number of values to generate.
        categories: List of possible categories.

    Returns:
        pd.Series: Generated categorical series.
    """
    return pd.Series(np.random.choice(categories, size=n_rows))


@data_syn_toolbox.collect_tool
def datetime_column(n_rows: int, start: str = "2020-01-01", end: str = "2023-12-31") -> pd.Series:
    """Generate a random datetime column.

    Args:
        n_rows: Number of values to generate.
        start: Start date (ISO format).
        end: End date (ISO format).

    Returns:
        pd.Series: Generated datetime series.
    """
    dates = pd.date_range(start=start, end=end, freq="D")
    return pd.Series(np.random.choice(dates, size=n_rows))


@data_syn_toolbox.collect_tool
def text_column(n_rows: int, prefix: str = "item_") -> pd.Series:
    """Generate a simple text column with random suffixes.

    Args:
        n_rows: Number of values to generate.
        prefix: Prefix for each text item.

    Returns:
        pd.Series: Generated text series.
    """
    texts = []
    for _ in range(n_rows):
        length = np.random.randint(3, 10)
        suffix = "".join(chr(np.random.randint(97, 123)) for _ in range(length))
        texts.append(f"{prefix}{suffix}")
    return pd.Series(texts)


@data_syn_toolbox.collect_tool
def correlated_column(base_series: pd.Series, correlation: float = 0.8) -> pd.Series:
    """Generate a new column correlated with a base series using closure and vectorized ops.

    This function creates a new series that has approximately the specified correlation
    with the input base_series. It uses numpy's random functions internally.

    Args:
        base_series: The existing pandas Series to correlate with.
        correlation: Target correlation coefficient (between 0 and 1).

    Returns:
        pd.Series: New series with desired correlation.
    """
    if not 0.0 <= correlation <= 1.0:
        raise ValueError("Correlation must be between 0.0 and 1.0")

    x = base_series.values
    x_mean, x_std = np.mean(x), np.std(x)
    if x_std == 0:
        x_std = 1

    # Standardize
    x_stdz = (x - x_mean) / x_std

    # Generate correlated noise
    noise = np.random.standard_normal(len(x))
    y_stdz = correlation * x_stdz + np.sqrt(1 - correlation**2) * noise

    # Rescale to original distribution
    y = y_stdz * x_std + x_mean
    return pd.Series(y, index=base_series.index)


@data_syn_toolbox.collect_tool
def inject_missing(series: pd.Series, rate: float = 0.05) -> pd.Series:
    """Inject missing (NaN) values into a series.

    Args:
        series: Input pandas Series.
        rate: Proportion of values to set as NaN (0.0 to 1.0).

    Returns:
        pd.Series: Series with injected missing values.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError("Rate must be between 0.0 and 1.0")

    mask = np.random.random(len(series)) < rate
    result = series.copy()
    result[mask] = np.nan
    return result
