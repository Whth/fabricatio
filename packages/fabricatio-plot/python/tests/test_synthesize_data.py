"""Test suite for DataSynToolbox in fabricatio_plot package.

This test suite covers functionality related to synthetic data generation:
- Schema definition and validation
- Column generation for different data types
- Complete DataFrame construction
- Post-processing operations (correlation, missing values)
- Error handling for invalid inputs and edge cases

Each test ensures correct behavior of the corresponding function,
including proper error handling and reproducibility guarantees.
"""

import re
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest
from fabricatio_plot.toolboxes import synthesize as dt


# =====================
# Test Data Setup
# =====================
@pytest.fixture
def basic_schema() -> Dict[str, Any]:
    """Create a basic schema for testing."""
    return {
        "columns": {
            "id": {"type": "numeric", "params": {"dist": "uniform", "low": 1, "high": 1000}},
            "category": {"type": "categorical", "params": {"categories": ["A", "B", "C"], "weights": [0.5, 0.3, 0.2]}},
            "date": {"type": "datetime", "params": {"start": "2022-01-01", "end": "2023-12-31", "freq": "D"}},
        },
        "n_rows": 100,
        "random_seed": 42,
    }


# =====================
# Schema Definition Tests
# =====================
def test_define_schema() -> None:
    """Test schema definition with basic parameters."""
    columns = {
        "numeric_col": {"type": "numeric", "params": {"dist": "normal", "mean": 0, "std": 1}},
        "cat_col": {"type": "categorical", "params": {"categories": ["X", "Y"]}},
    }

    schema = dt.define_schema(columns, n_rows=50, random_seed=123)

    assert "columns" in schema
    assert schema["n_rows"] == 50
    assert schema["random_seed"] == 123
    assert "rg" in schema
    assert schema["columns"] == columns


def test_define_schema_default_values() -> None:
    """Test schema definition with default parameters."""
    columns = {"col1": {"type": "numeric"}}
    schema = dt.define_schema(columns)

    assert schema["n_rows"] == 100
    assert schema["random_seed"] is None


# =====================
# Column Generation Tests
# =====================
def test_generate_numeric_column_uniform() -> None:
    """Test generating numeric column with uniform distribution."""
    schema = dt.define_schema(
        {"col": {"type": "numeric", "params": {"dist": "uniform", "low": 10, "high": 20}}}, n_rows=1000, random_seed=42
    )

    series = dt.generate_column(schema, "col")

    assert len(series) == 1000
    assert series.min() >= 10
    assert series.max() <= 20
    assert series.dtype in [np.float64, np.int64]


def test_generate_numeric_column_normal() -> None:
    """Test generating numeric column with normal distribution."""
    schema = dt.define_schema(
        {"col": {"type": "numeric", "params": {"dist": "normal", "mean": 100, "std": 15}}}, n_rows=1000, random_seed=42
    )

    series = dt.generate_column(schema, "col")

    assert len(series) == 1000
    assert series.mean() == pytest.approx(100, rel=0.1)
    assert series.std() == pytest.approx(15, rel=0.1)


def test_generate_categorical_column() -> None:
    """Test generating categorical column with weights."""
    schema = dt.define_schema(
        {
            "col": {
                "type": "categorical",
                "params": {"categories": ["High", "Medium", "Low"], "weights": [0.6, 0.3, 0.1]},
            }
        },
        n_rows=1000,
        random_seed=42,
    )

    series = dt.generate_column(schema, "col")

    assert len(series) == 1000
    assert set(series.unique()) == {"High", "Medium", "Low"}

    # Check approximate distribution
    value_counts = series.value_counts(normalize=True)
    assert value_counts["High"] == pytest.approx(0.6, abs=0.05)
    assert value_counts["Medium"] == pytest.approx(0.3, abs=0.05)
    assert value_counts["Low"] == pytest.approx(0.1, abs=0.05)


def test_generate_datetime_column() -> None:
    """Test generating datetime column."""
    schema = dt.define_schema(
        {"col": {"type": "datetime", "params": {"start": "2022-01-01", "end": "2022-12-31", "freq": "D"}}},
        n_rows=100,
        random_seed=42,
    )

    series = dt.generate_column(schema, "col")

    assert len(series) == 100
    assert pd.api.types.is_datetime64_any_dtype(series)
    assert series.min() >= pd.Timestamp("2022-01-01")
    assert series.max() <= pd.Timestamp("2022-12-31")


def test_generate_text_column() -> None:
    """Test generating text column."""
    schema = dt.define_schema(
        {"col": {"type": "text", "params": {"prefix": "prod_", "suffix": "_end", "min_len": 4, "max_len": 8}}},
        n_rows=10,
        random_seed=42,
    )

    series = dt.generate_column(schema, "col")

    assert len(series) == 10
    for text in series:
        assert text.startswith("prod_")
        assert text.endswith("_end")
        assert 4 <= len(text) - len("prod__end") <= 8  # Subtract prefix/suffix length


def test_generate_column_invalid_type() -> None:
    """Test error handling for unsupported column type."""
    schema = dt.define_schema({"col": {"type": "invalid_type"}}, n_rows=10)

    with pytest.raises(ValueError, match="Unsupported column type"):
        dt.generate_column(schema, "col")


def test_generate_categorical_invalid_weights() -> None:
    """Test error handling for invalid categorical weights."""
    schema = dt.define_schema(
        {
            "col": {
                "type": "categorical",
                "params": {
                    "categories": ["A", "B", "C"],
                    "weights": [0.5, 0.5],  # Wrong length
                },
            }
        },
        n_rows=10,
    )

    with pytest.raises(ValueError, match="Length of weights must match"):
        dt.generate_column(schema, "col")


# =====================
# DataFrame Construction Tests
# =====================
def test_build_dataframe_basic(basic_schema: Dict[str, Any]) -> None:
    """Test building complete DataFrame from schema."""
    # Extract just the columns part for the function
    columns_only = basic_schema["columns"]
    schema = dt.define_schema(columns_only, n_rows=100, random_seed=42)

    df = dt.build_dataframe(schema)

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (100, 3)
    assert set(df.columns) == {"id", "category", "date"}
    assert len(df["id"].unique()) > 0
    assert set(df["category"].unique()).issubset({"A", "B", "C"})
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_build_dataframe_specific_columns(basic_schema: Dict[str, Any]) -> None:
    """Test building DataFrame with specific columns only."""
    columns_only = basic_schema["columns"]
    schema = dt.define_schema(columns_only, n_rows=50, random_seed=42)

    df = dt.build_dataframe(schema, columns=["id", "category"])

    assert df.shape == (50, 2)
    assert set(df.columns) == {"id", "category"}
    assert "date" not in df.columns


def test_build_dataframe_empty_columns() -> None:
    """Test building DataFrame with empty schema."""
    schema = dt.define_schema({}, n_rows=10)
    df = dt.build_dataframe(schema)

    assert df.shape == (10, 0)


# =====================
# Post-Processing Tests
# =====================
def test_add_correlated_column() -> None:
    """Test adding correlated column."""
    # Use fixed data for reproducible test
    np.random.seed(42)
    base_data = np.random.normal(50, 10, 1000)
    df = pd.DataFrame({"base": base_data})

    df_corr = dt.add_correlated_column(df, base_column="base", new_column="correlated", correlation=0.8, random_seed=42)

    assert "correlated" in df_corr.columns
    assert len(df_corr) == 1000

    # Calculate actual correlation
    actual_corr = df_corr["base"].corr(df_corr["correlated"])
    # With proper algorithm, should be very close to target
    assert actual_corr == pytest.approx(0.8, abs=0.02)  # Tighter tolerance


def test_add_correlated_column_uniform_dist() -> None:
    """Test adding correlated column (distribution parameter is ignored in current implementation)."""
    # Note: The dist parameter is not used in the current correlation algorithm
    # since we work in standardized space
    np.random.seed(42)
    base_data = np.random.uniform(0, 100, 500)
    df = pd.DataFrame({"base": base_data})

    df_corr = dt.add_correlated_column(df, base_column="base", new_column="correlated", correlation=0.6, random_seed=42)

    assert "correlated" in df_corr.columns
    actual_corr = df_corr["base"].corr(df_corr["correlated"])
    assert actual_corr == pytest.approx(0.6, abs=0.02)


def test_add_correlated_column_invalid_correlation() -> None:
    """Test error handling for invalid correlation values."""
    df = pd.DataFrame({"base": [1, 2, 3, 4, 5]})

    with pytest.raises(ValueError, match=re.escape("between 0.0 and 1.0")):
        dt.add_correlated_column(df, "base", "new_col", correlation=1.5)

    with pytest.raises(ValueError, match=re.escape("between 0.0 and 1.0")):
        dt.add_correlated_column(df, "base", "new_col", correlation=-0.1)


def test_add_correlated_column_nonexistent_base() -> None:
    """Test error handling for nonexistent base column."""
    df = pd.DataFrame({"other": [1, 2, 3]})

    with pytest.raises(KeyError):
        dt.add_correlated_column(df, "nonexistent", "new_col")


def test_inject_missing_values() -> None:
    """Test injecting missing values."""
    df = pd.DataFrame({"col1": range(100), "col2": ["A"] * 100, "col3": np.random.random(100)})

    df_missing = dt.inject_missing_values(df, missing_rate=0.1, random_seed=42)

    assert df_missing.shape == df.shape
    assert df_missing.isnull().sum().sum() > 0

    # Approximate missing rate check
    total_cells = 100 * 3
    actual_missing_rate = df_missing.isnull().sum().sum() / total_cells
    assert actual_missing_rate == pytest.approx(0.1, abs=0.03)


def test_inject_missing_values_specific_columns() -> None:
    """Test injecting missing values in specific columns."""
    df = pd.DataFrame({"col1": range(10), "col2": range(10, 20), "col3": range(20, 30)})

    df_missing = dt.inject_missing_values(df, missing_rate=0.3, columns=["col1", "col3"], random_seed=42)

    # col2 should have no missing values
    assert df_missing["col2"].isnull().sum() == 0
    assert df_missing["col1"].isnull().sum() > 0
    assert df_missing["col3"].isnull().sum() > 0


def test_inject_missing_values_invalid_rate() -> None:
    """Test error handling for invalid missing rate."""
    df = pd.DataFrame({"col": [1, 2, 3]})

    with pytest.raises(ValueError, match=re.escape("between 0.0 and 1.0")):
        dt.inject_missing_values(df, missing_rate=1.5)

    with pytest.raises(ValueError, match=re.escape("between 0.0 and 1.0")):
        dt.inject_missing_values(df, missing_rate=-0.1)


# =====================
# Reproducibility Tests
# =====================
def test_reproducible_generation() -> None:
    """Test that generation is reproducible with same seed."""
    columns = {
        "numeric": {"type": "numeric", "params": {"dist": "normal", "mean": 0, "std": 1}},
        "category": {"type": "categorical", "params": {"categories": ["X", "Y", "Z"]}},
    }

    # Generate twice with same seed
    schema1 = dt.define_schema(columns, n_rows=50, random_seed=123)
    df1 = dt.build_dataframe(schema1)

    schema2 = dt.define_schema(columns, n_rows=50, random_seed=123)
    df2 = dt.build_dataframe(schema2)

    pd.testing.assert_frame_equal(df1, df2)


def test_different_seeds_produce_different_results() -> None:
    """Test that different seeds produce different results."""
    columns = {"col": {"type": "numeric", "params": {"dist": "uniform", "low": 0, "high": 1}}}

    schema1 = dt.define_schema(columns, n_rows=10, random_seed=1)
    df1 = dt.build_dataframe(schema1)

    schema2 = dt.define_schema(columns, n_rows=10, random_seed=2)
    df2 = dt.build_dataframe(schema2)

    # Should be different (very high probability)
    assert not df1.equals(df2)


# =====================
# Integration Tests
# =====================
def test_complete_workflow() -> None:
    """Test complete synthetic data generation workflow."""
    # Define schema
    schema = dt.define_schema(
        columns={
            "product_id": {"type": "text", "params": {"prefix": "PROD-", "min_len": 5, "max_len": 8}},
            "region": {"type": "categorical", "params": {"categories": ["North", "South", "East", "West"]}},
            "sales": {"type": "numeric", "params": {"dist": "poisson", "lam": 25}},
            "date": {"type": "datetime", "params": {"start": "2023-01-01", "end": "2023-12-31"}},
        },
        n_rows=200,
        random_seed=42,
    )

    # Build base DataFrame
    df = dt.build_dataframe(schema)

    # Add correlated column
    df = dt.add_correlated_column(df, base_column="sales", new_column="revenue", correlation=0.85, random_seed=42)

    # Inject missing values
    df = dt.inject_missing_values(df, missing_rate=0.05, columns=["sales", "revenue"], random_seed=42)

    # Validate final result
    assert df.shape == (200, 5)
    assert set(df.columns) == {"product_id", "region", "sales", "date", "revenue"}
    assert df["product_id"].str.startswith("PROD-").all()
    assert set(df["region"].dropna().unique()).issubset({"North", "South", "East", "West"})
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df.isnull().sum().sum() > 0  # Should have some missing values
