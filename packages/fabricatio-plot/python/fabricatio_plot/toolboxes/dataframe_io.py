"""Data I/O Operations Toolbox Module.

Handles file-based data input/output operations separately from in-memory data manipulation.
"""

from pathlib import Path
from typing import Literal, Union

import pandas as pd
from fabricatio_core.decorators import cfg_on
from fabricatio_core.utils import cfg
from fabricatio_tool.models.tool import ToolBox

# =====================
# Dedicated I/O Toolbox
# =====================
data_io_toolbox = ToolBox(
    name="DataIoToolBox", description="Dedicated toolbox for file-based data input/output operations"
)


@data_io_toolbox.collect_tool
def load_csv(file_path: Union[str, Path]) -> pd.DataFrame:
    """Load data from a CSV file into a pandas DataFrame."""
    return pd.read_csv(file_path)


@data_io_toolbox.collect_tool
@cfg_on(feats=["excel"])
def load_excel(file_path: Union[str, Path], sheet_name: str | int = 0) -> pd.DataFrame:
    """Load data from an Excel file into a pandas DataFrame."""
    return pd.read_excel(file_path, sheet_name=sheet_name)


@data_io_toolbox.collect_tool
@cfg_on(feats=["parquet"])
def load_parquet(file_path: Union[str, Path]) -> pd.DataFrame:
    """Load data from a Parquet file into a pandas DataFrame."""
    return pd.read_parquet(file_path)


@data_io_toolbox.collect_tool
def save_data(df: pd.DataFrame, file_path: Union[str, Path], fmt: Literal["csv", "excel", "parquet"] = "csv") -> None:
    """Save DataFrame to file (CSV/Excel/Parquet)."""
    if fmt == "csv":
        df.to_csv(file_path, index=False)
    elif fmt == "excel":
        cfg(feats=["excel"])
        df.to_excel(file_path, index=False)

    elif fmt == "parquet":
        cfg(feats=["parquet"])
        df.to_parquet(file_path, index=False)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
