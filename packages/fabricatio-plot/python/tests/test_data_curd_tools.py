"""Test suite for DataCrudToolBox in fabricatio_plot package.

This test suite covers functionality related to core CRUD operations:
- CREATE: Creating data structures and columns
- READ: Inspecting and retrieving data
- UPDATE: Transforming and modifying data
- DELETE: Removing data elements

Each test ensures correct behavior of the corresponding function,
including proper error handling for invalid inputs and edge cases.
"""

import pandas as pd
import pytest
from fabricatio_plot.toolboxes import dataframe_curd as dt


# =====================
# Test Data Setup
# =====================
@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for testing CRUD operations."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "product": ["A", "B", "A", "C", "B"],
            "quantity": [10, 5, 15, 8, 12],
            "price": [100.0, 200.0, 150.0, 250.0, 180.0],
            "discount": [0.1, None, 0.0, 0.15, None],
        },
        index=["row1", "row2", "row3", "row4", "row5"],
    )


@pytest.fixture
def empty_dataframe() -> pd.DataFrame:
    """Create an empty DataFrame with defined schema."""
    return pd.DataFrame(columns=["name", "age", "active"])


# =====================
# CREATE Operations Tests
# =====================
def test_create_empty_dataframe() -> None:
    """Test creating an empty DataFrame with column definitions."""
    df = dt.create_empty_dataframe(columns=["col1", "col2", "col3"])
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["col1", "col2", "col3"]
    assert df.shape == (0, 3)


def test_create_empty_dataframe_with_dtypes() -> None:
    """Test creating an empty DataFrame with specified data types."""
    df = dt.create_empty_dataframe(columns=["id", "name", "score"], dtypes=["int", "string", "float"])
    assert str(df["id"].dtype) == "int64"
    assert str(df["name"].dtype) in ["string", "object"]  # Handle pandas version differences
    assert str(df["score"].dtype) == "float64"


def test_create_empty_dataframe_mismatched_dtypes() -> None:
    """Test error handling for mismatched columns and dtypes."""
    with pytest.raises(ValueError, match="Length of columns and dtypes must match"):
        dt.create_empty_dataframe(columns=["col1", "col2"], dtypes=["int", "float", "str"])


def test_add_computed_column(sample_dataframe: pd.DataFrame) -> None:
    """Test adding a computed column using expression."""
    df = dt.add_computed_column(
        sample_dataframe, new_column="total_price", expression="price * quantity * (1 - discount)"
    )
    assert "total_price" in df.columns
    assert df["total_price"].iloc[0] == pytest.approx(900.0)  # 100 * 10 * (1-0.1)
    assert df["total_price"].iloc[2] == pytest.approx(2250.0)  # 150 * 15 * (1-0.0)


def test_add_computed_column_with_dtype(sample_dataframe: pd.DataFrame) -> None:
    """Test adding a computed column with explicit data type."""
    df = dt.add_computed_column(sample_dataframe, new_column="is_expensive", expression="price > 150", dtype="bool")
    assert "is_expensive" in df.columns
    assert df["is_expensive"].dtype == bool
    assert df["is_expensive"].tolist() == [False, True, False, True, True]


def test_add_computed_column_invalid_expression(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for invalid expressions."""
    from pandas.errors import UndefinedVariableError

    with pytest.raises(UndefinedVariableError):  # pandas.eval throws various exceptions
        dt.add_computed_column(sample_dataframe, new_column="invalid", expression="nonexistent_column * 2")


# =====================
# READ Operations Tests
# =====================
def test_get_column_metadata(sample_dataframe: pd.DataFrame) -> None:
    """Test retrieving detailed column metadata."""
    metadata = dt.get_column_metadata(sample_dataframe)

    # Check structure
    assert isinstance(metadata, dict)
    assert set(metadata.keys()) == set(sample_dataframe.columns)

    # Check content for numeric column
    assert metadata["price"]["dtype"] == "float64"
    assert len(metadata["price"]["sample_values"]) <= 3
    assert metadata["price"]["null_count"] == 0

    # Check content for categorical column
    assert metadata["product"]["dtype"] == "object"
    assert metadata["product"]["null_count"] == 0

    # Check content for column with nulls
    assert metadata["discount"]["null_count"] == 2


def test_get_row_by_index(sample_dataframe: pd.DataFrame) -> None:
    """Test retrieving a row by index value."""
    row = dt.get_row_by_index(sample_dataframe, "row3")
    assert isinstance(row, pd.Series)
    assert row["product"] == "A"
    assert row["quantity"] == 15
    assert row["price"] == 150.0


def test_get_row_by_index_invalid(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for invalid index."""
    with pytest.raises(KeyError):
        dt.get_row_by_index(sample_dataframe, "nonexistent_row")


# =====================
# UPDATE Operations Tests
# =====================
def test_fill_missing_values_mean(sample_dataframe: pd.DataFrame) -> None:
    """Test filling missing values using mean strategy."""
    df = dt.fill_missing_values(sample_dataframe, column="discount", strategy="mean")
    assert df["discount"].isnull().sum() == 0
    # Mean of [0.1, 0.0, 0.15] is 0.083333... (1/12)
    # Using more precise expected value and reasonable tolerance
    assert df["discount"].iloc[1] == pytest.approx(1 / 12, rel=1e-6)


def test_fill_missing_values_constant(sample_dataframe: pd.DataFrame) -> None:
    """Test filling missing values with constant."""
    df = dt.fill_missing_values(sample_dataframe, column="discount", strategy="constant", constant_value=0.05)
    assert df["discount"].isnull().sum() == 0
    assert df["discount"].iloc[1] == 0.05
    assert df["discount"].iloc[4] == 0.05


def test_fill_missing_values_mode(sample_dataframe: pd.DataFrame) -> None:
    """Test filling missing values using mode strategy."""
    df = dt.fill_missing_values(sample_dataframe, column="product", strategy="mode")
    assert df["product"].isnull().sum() == 0
    # Mode of ["A", "B", "A", "C", "B"] is "A" or "B" (both appear twice)
    # We'll check it's one of the modes
    assert df["product"].iloc[0] in ["A", "B"]


def test_fill_missing_values_invalid_strategy(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for invalid fill strategy."""
    with pytest.raises(ValueError, match="Unsupported strategy"):
        dt.fill_missing_values(sample_dataframe, column="discount", strategy="invalid_strategy")


def test_fill_missing_values_missing_constant(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling when constant_value is missing."""
    with pytest.raises(ValueError, match="constant_value required"):
        dt.fill_missing_values(sample_dataframe, column="discount", strategy="constant")


def test_transform_column_log(sample_dataframe: pd.DataFrame) -> None:
    """Test log transformation on numeric column."""
    df = dt.transform_column(sample_dataframe, column="price", transformation="log")
    # Original prices: [100, 200, 150, 250, 180]
    # Log(1+x) values should be positive and ordered similarly
    assert df["price"].min() > 0
    assert df["price"].iloc[0] < df["price"].iloc[1]  # 100 < 200


def test_transform_column_normalize(sample_dataframe: pd.DataFrame) -> None:
    """Test normalization transformation."""
    df = dt.transform_column(sample_dataframe, column="quantity", transformation="normalize")
    assert df["quantity"].min() == 0.0
    assert df["quantity"].max() == 1.0
    # Correct calculation: (10-5)/(15-5) = 5/10 = 0.5
    assert df["quantity"].iloc[0] == pytest.approx(0.5, rel=1e-6)  # Corrected to the right value of 0.5


def test_transform_column_invalid_type(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for non-numeric column transformation."""
    with pytest.raises(ValueError, match="must be numeric"):
        dt.transform_column(sample_dataframe, column="product", transformation="log")


def test_transform_column_invalid_transformation(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for invalid transformation type."""
    with pytest.raises(ValueError, match="Unsupported transformation"):
        dt.transform_column(sample_dataframe, column="price", transformation="invalid_transform")


# =====================
# DELETE Operations Tests
# =====================
def test_drop_columns(sample_dataframe: pd.DataFrame) -> None:
    """Test dropping multiple columns."""
    df = dt.drop_columns(sample_dataframe, columns=["discount", "id"])
    assert "discount" not in df.columns
    assert "id" not in df.columns
    assert "product" in df.columns
    assert df.shape == (5, 3)


def test_drop_columns_invalid(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for dropping non-existent columns."""
    with pytest.raises(KeyError, match="Columns not found"):
        dt.drop_columns(sample_dataframe, columns=["nonexistent_column"])


def test_drop_rows_by_condition(sample_dataframe: pd.DataFrame) -> None:
    """Test dropping rows based on condition."""
    # Note: price > 200 will only drop the row with price=250 (row4), not price=200 (row2)
    # because 200 > 200 is False
    df = dt.drop_rows_by_condition(sample_dataframe, condition="price > 200")
    assert df.shape == (4, 5)  # Should drop 1 row, leaving 4 rows
    assert 250.0 not in df["price"].values  # Ensure 250 was dropped
    assert 200.0 in df["price"].values  # 200 should still be present


def test_drop_rows_by_condition_complex(sample_dataframe: pd.DataFrame) -> None:
    """Test dropping rows with complex condition."""
    df = dt.drop_rows_by_condition(sample_dataframe, condition="quantity < 10 | discount.isnull()")
    assert df.shape == (2, 5)  # Keeps only rows 0 and 2
    assert df.index.tolist() == ["row1", "row3"]


# =====================
# Atomic Utility Operations Tests
# =====================
def test_rename_column(sample_dataframe: pd.DataFrame) -> None:
    """Test renaming a single column."""
    df = dt.rename_column(sample_dataframe, old_name="product", new_name="item")
    assert "item" in df.columns
    assert "product" not in df.columns
    assert df["item"].equals(sample_dataframe["product"])


def test_rename_column_invalid(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for renaming non-existent column."""
    with pytest.raises(KeyError, match="Column 'nonexistent' not found"):
        dt.rename_column(sample_dataframe, old_name="nonexistent", new_name="new_name")


def test_set_index_from_column(sample_dataframe: pd.DataFrame) -> None:
    """Test setting index from column."""
    df = dt.set_index_from_column(sample_dataframe, column="id", drop=True)
    assert df.index.name == "id"
    assert "id" not in df.columns
    assert df.index.tolist() == [1, 2, 3, 4, 5]


def test_set_index_from_column_keep_column(sample_dataframe: pd.DataFrame) -> None:
    """Test setting index while keeping the column."""
    df = dt.set_index_from_column(sample_dataframe, column="id", drop=False)
    assert df.index.name == "id"
    assert "id" in df.columns

    # Verify that index and column have same values
    assert df.index.tolist() == df["id"].tolist()

    # Verify that the index series equals the column series
    index_series = pd.Series(df.index, index=df.index, name="id")
    assert index_series.equals(df["id"])


def test_set_index_from_column_invalid(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for invalid column in set_index."""
    with pytest.raises(KeyError, match="Column 'nonexistent' not found"):
        dt.set_index_from_column(sample_dataframe, column="nonexistent")
