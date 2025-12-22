"""Synthetic Data Generation Toolbox Module.

This module provides a collection of tools for generating synthetic datasets
with customizable structures, distributions, and relationships between columns.
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fabricatio_core.utils import ok
from fabricatio_tool.models.tool import ToolBox
from numpy.random import PCG64, Generator

# Initialize the synthetic data toolbox
data_syn_toolbox = ToolBox(
    name="DataSynToolbox", description="A toolbox for generating customizable synthetic datasets"
)

# =====================
# Core Data Generation Tools
# =====================


@data_syn_toolbox.collect_tool
def define_schema(
    columns: Dict[str, Dict[str, Any]], n_rows: int = 100, random_seed: Optional[int] = None
) -> Dict[str, Any]:
    """Define a schema for synthetic data generation.

    Args:
        columns: Column definitions with generation parameters.
                 Format: {
                     "column_name": {
                         "type": "numeric"|"categorical"|"datetime"|"text",
                         "params": { ... }  # Type-specific parameters
                     },
                     ...
                 }
        n_rows: Number of rows to generate (default: 100)
        random_seed: Seed for reproducibility (default: None)

    Returns:
        Schema configuration dictionary ready for data generation
    """
    return {
        "columns": columns,
        "n_rows": n_rows,
        "random_seed": random_seed,
        "rg": Generator(PCG64(random_seed)) if random_seed is not None else Generator(PCG64()),
    }


@data_syn_toolbox.collect_tool
def generate_column(schema: Dict[str, Any], column_name: str) -> pd.Series:
    """Generate a single column based on schema definition.

    Args:
        schema: Schema configuration from define_schema()
        column_name: Name of the column to generate

    Returns:
        Generated pandas Series
    """
    col_config = schema["columns"][column_name]
    n_rows = schema["n_rows"]
    rg = schema["rg"]
    col_type = col_config["type"].lower()
    params = col_config.get("params", {})

    if col_type == "numeric":
        return _generate_numeric_column(rg, n_rows, params)
    if col_type == "categorical":
        return _generate_categorical_column(rg, n_rows, params)
    if col_type == "datetime":
        return _generate_datetime_column(rg, n_rows, params)
    if col_type == "text":
        return _generate_text_column(rg, n_rows, params)
    raise ValueError(f"Unsupported column type: {col_type}")


@data_syn_toolbox.collect_tool
def build_dataframe(schema: Dict[str, Any], columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Build a complete DataFrame from schema definition.

    Args:
        schema: Schema configuration from define_schema()
        columns: Specific columns to generate (default: all columns in schema)

    Returns:
        Generated pandas DataFrame
    """
    if columns is None:
        columns = list(schema["columns"].keys())

    data = {}
    for col_name in columns:
        data[col_name] = generate_column(schema, col_name)

    # Handle empty columns case - create DataFrame with correct number of rows
    if not data:
        return pd.DataFrame(index=range(schema["n_rows"]))

    return pd.DataFrame(data)


# =====================
# Column Generation Helpers (Internal)
# =====================


def _generate_numeric_column(rg: Generator, n_rows: int, params: Dict[str, Any]) -> pd.Series:
    """Internal helper for generating numeric columns."""
    dist = params.get("dist", "uniform").lower()

    if dist == "uniform":
        low = params.get("low", 0.0)
        high = params.get("high", 1.0)
        return pd.Series(rg.uniform(low, high, n_rows))

    if dist == "normal":
        mean = params.get("mean", 0.0)
        std = params.get("std", 1.0)
        return pd.Series(rg.normal(mean, std, n_rows))

    if dist == "exponential":
        scale = params.get("scale", 1.0)
        return pd.Series(rg.exponential(scale, n_rows))

    if dist == "poisson":
        lam = params.get("lam", 1.0)
        return pd.Series(rg.poisson(lam, n_rows))

    raise ValueError(f"Unsupported numeric distribution: {dist}")


def _generate_categorical_column(rg: Generator, n_rows: int, params: Dict[str, Any]) -> pd.Series:
    """Internal helper for generating categorical columns."""
    categories = params.get("categories", ["A", "B", "C"])
    weights = params.get("weights")

    if weights is not None and len(weights) != len(categories):
        raise ValueError("Length of weights must match number of categories")

    return pd.Series(rg.choice(categories, n_rows, p=weights))


def _generate_datetime_column(rg: Generator, n_rows: int, params: Dict[str, Any]) -> pd.Series:
    """Internal helper for generating datetime columns."""
    start_date = params.get("start", "2020-01-01")
    end_date = params.get("end", "2023-12-31")
    freq = params.get("freq", "D")

    date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
    indices = rg.integers(0, len(date_range), n_rows)
    return pd.Series(date_range[indices])


def _generate_text_column(rg: Generator, n_rows: int, params: Dict[str, Any]) -> pd.Series:
    """Internal helper for generating text columns."""
    prefix = params.get("prefix", "item_")
    suffix = params.get("suffix", "")
    min_len = params.get("min_len", 3)
    max_len = params.get("max_len", 10)

    texts = []
    for _ in range(n_rows):
        length = rg.integers(min_len, max_len + 1)
        chars = [chr(rg.integers(97, 123)) for _ in range(length)]  # a-z
        texts.append(f"{prefix}{''.join(chars)}{suffix}")

    return pd.Series(texts)


# =====================
# Post-Processing Tools
# =====================


@data_syn_toolbox.collect_tool
def add_correlated_column(
    df: pd.DataFrame, base_column: str, new_column: str, correlation: float = 0.8, random_seed: Optional[int] = None
) -> pd.DataFrame:
    """Add a new column correlated with an existing column.

    Args:
        df: Input DataFrame
        base_column: Name of existing column to correlate with
        new_column: Name of new column to create
        correlation: Target correlation coefficient (0.0 to 1.0)
        random_seed: Seed for reproducibility

    Returns:
        DataFrame with new correlated column added
    """
    if not 0.0 <= correlation <= 1.0:
        raise ValueError("Correlation must be between 0.0 and 1.0")

    rg = Generator(PCG64(random_seed)) if random_seed is not None else Generator(PCG64())
    base_data = df[base_column].values
    n_rows = len(base_data)

    # Standardize the base column
    base_mean = np.mean(base_data)
    base_std = np.std(base_data)
    if base_std == 0:
        base_std = 1  # Handle constant columns

    base_standardized = (base_data - base_mean) / base_std

    # Generate uncorrelated noise
    noise = rg.standard_normal(n_rows)

    # Create correlated data in standardized space
    correlated_standardized = correlation * base_standardized + np.sqrt(1 - correlation**2) * noise

    # Transform back to original scale
    new_data = correlated_standardized * base_std + base_mean

    df = df.copy()
    df[new_column] = new_data
    return df


@data_syn_toolbox.collect_tool
def inject_missing_values(
    df: pd.DataFrame, missing_rate: float = 0.05, columns: Optional[List[str]] = None, random_seed: Optional[int] = None
) -> pd.DataFrame:
    """Inject missing values into a DataFrame.

    Args:
        df: Input DataFrame
        missing_rate: Proportion of values to make missing (0.0 to 1.0)
        columns: Columns to affect (default: all columns)
        random_seed: Seed for reproducibility

    Returns:
        DataFrame with injected missing values
    """
    if not 0.0 <= missing_rate <= 1.0:
        raise ValueError("missing_rate must be between 0.0 and 1.0")

    rg = Generator(PCG64(random_seed)) if random_seed is not None else Generator(PCG64())
    df = df.copy()

    columns = ok(columns or df.columns.tolist())

    for col in columns:
        mask = rg.random(len(df)) < missing_rate
        df.loc[mask, col] = np.nan

    return df
