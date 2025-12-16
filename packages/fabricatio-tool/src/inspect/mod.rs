mod tree;

use pyo3::prelude::*;
pub(super) fn register(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    tree::register(py, m)?;
    Ok(())
}
