"""Data Toolbox Module for Fabricatio Plot.

This module provides a collection of data manipulation functions,
organized into a toolbox for streamlined data operations such as loading, saving,
cleaning, transforming, analyzing, and sampling data.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
import pandas as pd
from fabricatio_core.decorators import cfg_on
from fabricatio_tool.models.tool import ToolBox

data_toolbox = ToolBox(name="DataToolBox", description="A toolbox for data operations with pandas and numpy")


# =====================
# Data Loading & Saving
# =====================
@data_toolbox.collect_tool
def load_csv(file_path: Union[str, Path]) -> pd.DataFrame:
    """Load data from a CSV file into a pandas DataFrame.

    Args:
        file_path: Path to the CSV file.

    Returns:
        Loaded DataFrame.
    """
    return pd.read_csv(file_path)


@data_toolbox.collect_tool
@cfg_on(feats=["excel"])
def load_excel(file_path: Union[str, Path], sheet_name: str = "Sheet1") -> pd.DataFrame:
    """Load data from an Excel file into a pandas DataFrame.

    Args:
        file_path: Path to the Excel file.
        sheet_name: Name of the sheet to load (default: 'Sheet1').

    Returns:
        Loaded DataFrame.
    """
    return pd.read_excel(file_path, sheet_name=sheet_name)


@data_toolbox.collect_tool
def save_data(df: pd.DataFrame, file_path: Union[str, Path], fmt: Literal["csv", "excel"] = "csv") -> None:
    """Save DataFrame to file in specified format.

    Args:
        df: DataFrame to save.
        file_path: Output file path.
        fmt: File format ('csv' or 'excel', default: 'csv').
    """
    if fmt == "csv":
        df.to_csv(file_path, index=False)
    elif fmt == "excel":
        df.to_excel(file_path, index=False)
    else:
        raise ValueError("Unsupported format. Use 'csv' or 'excel'.")


@data_toolbox.collect_tool
def get_column_names(df: pd.DataFrame) -> List[str]:
    """Get the column names of the DataFrame.

    Args:
        df: Input DataFrame.

    Returns:
        List of column names.
    """
    return list(df.columns)


# =====================
# Data Exploration & Summary
# =====================
@data_toolbox.collect_tool
def get_data_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Get statistical summary of a DataFrame.

    Args:
        df: Input DataFrame.

    Returns:
        Dictionary containing:
        - 'shape': Tuple of (rows, columns)
        - 'dtypes': Data types per column
        - 'numeric_summary': Statistics for numeric columns
        - 'categorical_summary': Statistics for categorical columns
    """
    summary = {
        "shape": df.shape,
        "dtypes": df.dtypes.astype(str).to_dict(),
        "numeric_summary": None,
        "categorical_summary": None,
    }

    # Numeric columns summary
    numeric_cols = df.select_dtypes(include=np.number).columns
    if not numeric_cols.empty:
        summary["numeric_summary"] = df[numeric_cols].describe().to_dict()

    # Categorical columns summary
    categorical_cols = df.select_dtypes(exclude=np.number).columns
    if not categorical_cols.empty:
        summary["categorical_summary"] = {
            col: {
                "unique_count": df[col].nunique(),
                "top_value": df[col].mode().iloc[0] if not df[col].mode().empty else None,
                "top_frequency": df[col].value_counts().iloc[0] if not df[col].value_counts().empty else 0,
            }
            for col in categorical_cols
        }

    return summary


# =====================
# Data Cleaning & Transformation
# =====================
@data_toolbox.collect_tool
def handle_missing_values(
    df: pd.DataFrame, strategy: str = "drop", fill_value: Optional[Union[int, float, str]] = None
) -> pd.DataFrame:
    """Handle missing values in the DataFrame.

    Args:
        df: Input DataFrame.
        strategy: Handling strategy ('drop', 'fill', default: 'drop').
        fill_value: Value to use when strategy is 'fill'.

    Returns:
        DataFrame with missing values handled.
    """
    if strategy == "drop":
        return df.dropna()
    if strategy == "fill":
        if fill_value is None:
            raise ValueError("fill_value must be provided when using 'fill' strategy")
        return df.fillna(fill_value)
    raise ValueError("Invalid strategy. Use 'drop' or 'fill'.")


@data_toolbox.collect_tool
def normalize_column(df: pd.DataFrame, column_name: str, method: str = "minmax") -> pd.DataFrame:
    """Normalize a numeric column.

    Args:
        df: Input DataFrame.
        column_name: Name of the column to normalize.
        method: Normalization method ('minmax', 'zscore', default: 'minmax').

    Returns:
        DataFrame with normalized column.
    """
    if df[column_name].dtype not in [np.int64, np.float64]:
        raise ValueError(f"Column '{column_name}' must be numeric")

    df = df.copy()

    if method == "minmax":
        min_val = df[column_name].min()
        max_val = df[column_name].max()
        df[column_name] = (df[column_name] - min_val) / (max_val - min_val)
    elif method == "zscore":
        mean_val = df[column_name].mean()
        std_val = df[column_name].std()
        df[column_name] = (df[column_name] - mean_val) / std_val
    else:
        raise ValueError("Invalid method. Use 'minmax' or 'zscore'.")

    return df


# =====================
# Data Analysis & Aggregation
# =====================
@data_toolbox.collect_tool
def filter_data(df: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Filter DataFrame rows based on a query expression.

    Args:
        df: Input DataFrame.
        condition: Query string for filtering (e.g., "age > 30", "category == 'A'").

    Returns:
        Filtered DataFrame.
    """
    return df.query(condition)


@data_toolbox.collect_tool
def groupby_aggregate(
    df: pd.DataFrame, group_column: str, agg_columns: List[str], agg_functions: List[str]
) -> pd.DataFrame:
    """Group data and compute aggregations.

    Args:
        df: Input DataFrame.
        group_column: Column to group by.
        agg_columns: Columns to aggregate.
        agg_functions: Aggregation functions ('sum', 'mean', 'count', etc.).

    Returns:
        Aggregated DataFrame.
    """
    if not set(agg_columns).issubset(df.columns):
        missing = set(agg_columns) - set(df.columns)
        raise ValueError(f"Columns not found: {missing}")

    return df.groupby(group_column)[agg_columns].agg(agg_functions).reset_index()


# =====================
# Data Sampling & Splitting
# =====================
@data_toolbox.collect_tool
def sample_data(
    df: pd.DataFrame, n: Optional[int] = None, frac: Optional[float] = None, random_state: int = 42
) -> pd.DataFrame:
    """Randomly sample rows from the DataFrame.

    Args:
        df: Input DataFrame.
        n: Number of samples to return.
        frac: Fraction of data to sample.
        random_state: Random seed for reproducibility.

    Returns:
        Sampled DataFrame.
    """
    if n is None and frac is None:
        raise ValueError("Either 'n' or 'frac' must be specified")

    return df.sample(n=n, frac=frac, random_state=random_state)
