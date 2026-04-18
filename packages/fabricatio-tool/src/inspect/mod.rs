mod tree;

use pyo3::prelude::*;

/// Registers the tree inspection functions with the Python module.
///
/// Args:
///     py: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(super) fn register(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    tree::register(py, m)?;
    Ok(())
}
