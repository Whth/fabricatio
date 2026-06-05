# `fabricatio-plot`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-plot)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-plot)](https://pypi.org/project/fabricatio-plot/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-plot/week)](https://pepy.tech/projects/fabricatio-plot)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-plot)](https://pepy.tech/projects/fabricatio-plot)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Data visualization, synthetic data generation, and dataframe manipulation for the Fabricatio LLM agent framework.

---

## Installation

```bash
pip install fabricatio[plot]
# or
uv pip install fabricatio[plot]
```

For optional file-format support:

```bash
pip install fabricatio[plot,excel]    # Excel I/O
pip install fabricatio[plot,parquet]  # Parquet I/O
```

Install with all Fabricatio components:

```bash
pip install fabricatio[full]
```

## Overview

`fabricatio-plot` equips LLM agents with tools for matplotlib-based charting, programmatic synthetic data generation, dataframe CRUD operations, and file I/O. Toolboxes expose fine-grained functions agents can call; capabilities wrap them into higher-level LLM-driven workflows.

## Key Components

### Toolboxes

Low-level tools grouped by domain, exposed to agents via `fabricatio-tool`'s `ToolBox`.

**PlottingToolBox** — matplotlib chart construction

| Function | Description |
|---|---|
| `create_figure(figsize, dpi)` | Create a new matplotlib `Figure` |
| `create_subplots(nrows, ncols, figsize)` | Create a figure with a grid of subplots |
| `plot_line(ax, x, y, ...)` | Draw a line chart on given axes |
| `plot_bar(ax, categories, values, ...)` | Draw a vertical bar chart |
| `plot_scatter(ax, x, y, ...)` | Draw a scatter plot |
| `set_labels(ax, title, xlabel, ylabel)` | Set title and axis labels |
| `set_legend(ax, location, fontsize)` | Add a legend to the chart |
| `configure_grid(ax, visible, linestyle, alpha)` | Configure grid lines |
| `save_plot(fig, save_path, dpi, transparent)` | Save figure to file |

**DataSynToolbox** — synthetic column generation

| Function | Description |
|---|---|
| `numeric_column(n_rows, low, high)` | Uniform-distribution numeric column |
| `normal_column(n_rows, mean, std)` | Normally distributed numeric column |
| `categorical_column(n_rows, categories)` | Random categorical column |
| `datetime_column(n_rows, start, end)` | Random datetime column in a range |
| `text_column(n_rows, prefix)` | Sequential text column (`item_0`, `item_1`, …) |
| `correlated_column(base_series, correlation)` | Column correlated with an existing series |
| `inject_missing(series, rate)` | Inject NaN values at a given rate |

**DataCrudToolbox** — dataframe create/read/update/delete

| Function | Description |
|---|---|
| `create_empty_dataframe(columns, dtypes)` | Create an empty DataFrame with typed columns |
| `add_computed_column(df, new_column, expression)` | Add a column via pandas expression |
| `get_row_by_index(df, index_value)` | Retrieve a single row by index |
| `fill_missing_values(df, column, strategy)` | Fill NaN with mean, median, mode, or constant |
| `transform_column(df, column, transformation)` | Apply log, sqrt, square, or normalize |
| `drop_columns(df, columns)` | Remove specified columns |
| `drop_rows_by_condition(df, condition)` | Remove rows matching a query condition |
| `rename_column(df, old_name, new_name)` | Rename a single column |
| `set_index_from_column(df, column, drop)` | Set the DataFrame index from a column |

**DataIoToolBox** — file-based I/O

| Function | Description |
|---|---|
| `load_csv(file_path)` | Read CSV into DataFrame |
| `load_excel(file_path, sheet_name)` | Read Excel into DataFrame (requires `excel` extra) |
| `load_parquet(file_path)` | Read Parquet into DataFrame (requires `parquet` extra) |
| `save_data(df, file_path, fmt)` | Save DataFrame as CSV, Excel, or Parquet |

### Capabilities

Higher-level abstractions that orchestrate toolboxes with LLM reasoning.

- **`Plot`** — aggregates `PlottingToolBox`, `DataCrudToolbox`, and `DataIoToolBox`. The `plot(requirement, data, output_spec)` method accepts a natural-language requirement and delegates to its toolboxes to produce charts.
- **`SynthesizeData`** — uses LLM to generate structured data from a natural-language description. `generate_header()` produces column names; `generate_csv_data()` returns a DataFrame; `synthesize_data()` handles large datasets by batching parallel generation.

### Actions

Concrete `fabricatio-core` `Action` implementations ready to wire into task pipelines.

- **`MakeCharts`** — takes a plot requirement (or the task's assembled prompt) and produces a chart, optionally saving to a specified path.
- **`MakeSynthesizedData`** — synthesizes a DataFrame from the task prompt and stores it under the key `synthesized_data`.
- **`SaveDataCSV`** — saves a DataFrame to a path (given explicitly or determined by the LLM from the task context).

## Usage

Toolboxes are stateless and can be called directly:

```python
from fabricatio_plot.toolboxes.plot import create_figure, plot_line, set_labels, save_plot

fig = create_figure(figsize=(10, 4))
ax = fig.subplots()
plot_line(ax, x=[1, 2, 3], y=[4, 5, 6], label="Series A")
set_labels(ax, title="Sample Chart", xlabel="X", ylabel="Y")
save_plot(fig, "output.png")
```

Capabilities drive LLM-orchestrated workflows:

```python
from fabricatio_plot.capabilities.plot import Plot

handler = Plot()
result = await handler.plot("Create a bar chart of monthly sales from the CSV at data/sales.csv")
```

Actions plug into Fabricatio task graphs:

```python
from fabricatio_plot.actions.plot import MakeCharts

action = MakeCharts(plot_requirement="Scatter plot of x vs y", chart_save_path="scatter.png")
await action.execute(task)
```

## Dependencies

- `fabricatio-core` — core interfaces, configuration, and task model
- `fabricatio-tool` — `ToolBox` and `Handle` abstractions
- `matplotlib` — chart rendering
- `numpy` — array operations
- `pandas` — DataFrame manipulation
- Optional: `openpyxl` (Excel I/O), `pyarrow` (Parquet I/O)

## License

MIT — see [LICENSE](LICENSE)
