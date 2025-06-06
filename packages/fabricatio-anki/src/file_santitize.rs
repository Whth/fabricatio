use pyo3::prelude::*;
use sanitize_filename::sanitize;
#[pyfunction]
fn fname_santitize(filename: &str) -> PyResult<String> {
    Ok(sanitize(filename))
}
/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fname_santitize, m)?)?;
    Ok(())
}
