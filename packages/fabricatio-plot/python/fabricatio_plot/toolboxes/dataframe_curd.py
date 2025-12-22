"""CRUD Data Operations Toolbox Module.

This module provides focused tools for core data operations following CRUD principles:
- Create: Generate new data structures/columns
- Read: Extract and inspect data
- Update: Transform and modify existing data
- Delete: Remove data elements

Designed for clear separation of concerns with minimal dependencies.
"""

from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from fabricatio_tool.models.tool import ToolBox

# =====================
# Core CRUD Toolbox
# =====================
data_crud_toolbox = ToolBox(
    name="DataFrameCrudToolBox",
    description="Focused toolbox for atomic data operations following CRUD principles, No I/O tools.",
)


# =====================
# CREATE Operations
# =====================
@data_crud_toolbox.collect_tool
def create_empty_dataframe(columns: List[str], dtypes: Optional[List[str]] = None) -> pd.DataFrame:
    """Create an empty DataFrame with specified columns and optional data types.

    Args:
        columns: List of column names
        dtypes: Optional list of data types corresponding to columns (e.g., ['int', 'float', 'str'])

    Returns:
        Empty DataFrame with schema defined
    """
    if dtypes and len(columns) != len(dtypes):
        raise ValueError("Length of columns and dtypes must match")

    df = pd.DataFrame(columns=columns)
    if dtypes:
        for col, dtype in zip(columns, dtypes, strict=False):
            df[col] = df[col].astype(dtype)
    return df


@data_crud_toolbox.collect_tool
def add_computed_column(
    df: pd.DataFrame, new_column: str, expression: str, dtype: Optional[str] = None
) -> pd.DataFrame:
    """Create a new column by evaluating an expression on existing columns.

    Args:
        df: Input DataFrame
        new_column: Name for the new column
        expression: Python expression using existing columns (e.g., "price * quantity")
        dtype: Optional data type for the new column

    Returns:
        DataFrame with new computed column added
    """
    df = df.copy()
    df[new_column] = df.eval(expression)
    if dtype:
        df[new_column] = df[new_column].astype(dtype)
    return df


# =====================
# READ Operations
# =====================
@data_crud_toolbox.collect_tool
def get_column_metadata(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Get detailed metadata for all columns including type and sample values.

    Args:
        df: Input DataFrame

    Returns:
        Dictionary mapping column names to metadata:
        {
            "column_name": {
                "dtype": "data type",
                "sample_values": [list of 3 sample values],
                "null_count": number of nulls
            },
            ...
        }
    """
    metadata = {}
    for col in df.columns:
        metadata[col] = {
            "dtype": str(df[col].dtype),
            "sample_values": df[col].dropna().head(3).tolist(),
            "null_count": df[col].isnull().sum(),
        }
    return metadata


@data_crud_toolbox.collect_tool
def get_row_by_index(df: pd.DataFrame, index_value: Any) -> pd.Series:
    """Retrieve a single row by its index value.

    Args:
        df: Input DataFrame
        index_value: Value of the index to retrieve

    Returns:
        Row as a pandas Series

    Raises:
        KeyError: If index_value not found in index
    """
    return df.loc[index_value]


# =====================
# UPDATE Operations
# =====================
@data_crud_toolbox.collect_tool
def fill_missing_values(
    df: pd.DataFrame,
    column: str,
    strategy: Literal["mean", "median", "mode", "constant"] = "mean",
    constant_value: Optional[Any] = None,
) -> pd.DataFrame:
    """Update missing values in a single column using specified strategy.

    Args:
        df: Input DataFrame
        column: Column name to process
        strategy: Filling strategy ('mean', 'median', 'mode', 'constant')
        constant_value: Value to use when strategy='constant'

    Returns:
        DataFrame with missing values filled in specified column
    """
    df = df.copy()
    col_data = df[column]

    if strategy == "mean":
        fill_val = col_data.mean()
    elif strategy == "median":
        fill_val = col_data.median()
    elif strategy == "mode":
        fill_val = col_data.mode().iloc[0] if not col_data.mode().empty else np.nan
    elif strategy == "constant":
        if constant_value is None:
            raise ValueError("constant_value required for 'constant' strategy")
        fill_val = constant_value
    else:
        raise ValueError(f"Unsupported strategy: {strategy}")

    df[column] = col_data.fillna(fill_val)
    return df


@data_crud_toolbox.collect_tool
def transform_column(
    df: pd.DataFrame, column: str, transformation: Literal["log", "sqrt", "square", "normalize"]
) -> pd.DataFrame:
    """Apply mathematical transformation to a numeric column.

    Args:
        df: Input DataFrame
        column: Column name to transform
        transformation: Type of transformation ('log', 'sqrt', 'square', 'normalize')

    Returns:
        DataFrame with transformed column
    """
    df = df.copy()
    col_data = df[column]

    if not pd.api.types.is_numeric_dtype(col_data):
        raise ValueError(f"Column '{column}' must be numeric for transformation")

    if transformation == "log":
        df[column] = np.log1p(col_data)  # log(1+x) handles zeros
    elif transformation == "sqrt":
        df[column] = np.sqrt(col_data)
    elif transformation == "square":
        df[column] = col_data**2
    elif transformation == "normalize":
        min_val = col_data.min()
        max_val = col_data.max()
        df[column] = (col_data - min_val) / (max_val - min_val) if max_val != min_val else 0
    else:
        raise ValueError(f"Unsupported transformation: {transformation}")

    return df


# =====================
# DELETE Operations
# =====================
@data_crud_toolbox.collect_tool
def drop_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Delete specified columns from DataFrame.

    Args:
        df: Input DataFrame
        columns: List of column names to drop

    Returns:
        DataFrame with columns removed

    Raises:
        KeyError: If any column in 'columns' doesn't exist in DataFrame
    """
    missing = set(columns) - set(df.columns)
    if missing:
        raise KeyError(f"Columns not found: {missing}")
    return df.drop(columns=columns)


@data_crud_toolbox.collect_tool
def drop_rows_by_condition(df: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Delete rows that meet a specified condition.

    Args:
        df: Input DataFrame
        condition: Query string for rows to drop (e.g., "price < 0", "category.isna()")

    Returns:
        DataFrame with matching rows removed
    """
    return df.query(f"~({condition})")


# =====================
# Atomic Utility Operations
# =====================
@data_crud_toolbox.collect_tool
def rename_column(df: pd.DataFrame, old_name: str, new_name: str) -> pd.DataFrame:
    """Atomically rename a single column.

    Args:
        df: Input DataFrame
        old_name: Current column name
        new_name: New column name

    Returns:
        DataFrame with column renamed

    Raises:
        KeyError: If old_name not found in columns
    """
    if old_name not in df.columns:
        raise KeyError(f"Column '{old_name}' not found in DataFrame")
    return df.rename(columns={old_name: new_name})


@data_crud_toolbox.collect_tool
def set_index_from_column(df: pd.DataFrame, column: str, drop: bool = True) -> pd.DataFrame:
    """Set DataFrame index from an existing column.

    Args:
        df: Input DataFrame
        column: Column name to use as index
        drop: Whether to drop the column after setting index (default: True)

    Returns:
        DataFrame with new index set

    Raises:
        KeyError: If column not found in DataFrame
    """
    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in DataFrame")
    return df.set_index(column, drop=drop)
